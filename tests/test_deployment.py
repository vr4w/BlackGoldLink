"""Deployment guard and recovery tests; never contact a server or real accounts."""
import importlib.util
from contextlib import closing
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('github_updater',ROOT/'deployment/github-updater.py')
updater=importlib.util.module_from_spec(spec);spec.loader.exec_module(updater)


class Deployment(unittest.TestCase):
    def archive(self,extras=()):
        data=io.BytesIO()
        with tarfile.open(fileobj=data,mode='w:gz') as archive:
            for name in ('app.py','worker.py','requirements.txt','versioning.py','.bgl-commit','tests/test_one.py','templates/base.html','static/style.css'):
                body=(('a'*40)+'\n' if name=='.bgl-commit' else 'example').encode()
                info=tarfile.TarInfo(name);info.size=len(body);archive.addfile(info,io.BytesIO(body))
            for info in extras:archive.addfile(info,io.BytesIO(b'x'*info.size) if info.isfile() else None)
        return data.getvalue()

    def test_safe_source_extracts_and_links_traversal_secrets_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'valid';dest.mkdir()
            updater.extract_source(self.archive(),dest,'a'*40)
            self.assertTrue((dest/'app.py').is_file())
            for name,kind in (('../escape',tarfile.REGTYPE),('/escape',tarfile.REGTYPE),('.env',tarfile.REGTYPE),('instance/collection.db',tarfile.REGTYPE),('link',tarfile.SYMTYPE)):
                info=tarfile.TarInfo(name);info.type=kind;info.linkname='/etc/passwd'
                with self.subTest(name=name),tempfile.TemporaryDirectory() as other:
                    with self.assertRaises(RuntimeError):updater.extract_source(self.archive([info]),Path(other),'a'*40)
                    self.assertFalse((Path(other)/'app.py').exists()) # Entire validation precedes writes.

    def test_wrong_commit_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError,'Commit marker'):updater.extract_source(self.archive(),Path(temp),'b'*40)

    def test_database_and_import_changes_require_manual_release(self):
        with tempfile.TemporaryDirectory() as temp:
            old=Path(temp)/'old';new=Path(temp)/'new'
            for folder in (old,new):
                folder.mkdir()
                for file in updater.STABLE:(folder/file).write_text('same')
                for file,name in updater.SCHEMAS:(folder/file).write_text(name+"='existing schema'")
            updater.compatible(old,new)
            (new/'worker.py').write_text('changed')
            with self.assertRaisesRegex(RuntimeError,'manual release'):updater.compatible(old,new)
            (new/'worker.py').write_text('same');(new/'admin.py').write_text("ADMIN_SCHEMA='changed'")
            with self.assertRaisesRegex(RuntimeError,'manual migration'):updater.compatible(old,new)

    def test_running_import_never_stops_services(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();(base/'releases').mkdir();(base/'releases/old').mkdir();(base/'current').symlink_to(base/'releases/old')
            with patch.object(updater,'BASE',base),patch.object(updater,'pending',return_value=1),patch.object(updater,'systemctl') as service:
                self.assertFalse(updater.activate(base/'releases/new',base/'db','host','https://host'))
                service.assert_not_called()

    def test_failed_health_restores_old_code_without_restoring_database(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();(base/'releases').mkdir();old=base/'releases/old';old.mkdir();new=base/'releases/new';new.mkdir()
            (base/'current').symlink_to(old);env=base/'env';env.write_text('placeholder')
            db=base/'db'
            with closing(sqlite3.connect(db)) as con:
                con.execute('CREATE TABLE messages(text)');con.execute("INSERT INTO messages VALUES('keep me')");con.commit()
            with patch.object(updater,'BASE',base),patch.object(updater,'ENV',env),patch.object(updater,'pending',return_value=0),patch.object(updater,'compatible'),patch.object(updater.subprocess,'run'),patch.object(updater.subprocess,'check_output',return_value='a'*24),patch.object(updater,'systemctl') as service,patch.object(updater,'health',side_effect=RuntimeError('bad health')):
                with self.assertRaisesRegex(RuntimeError,'bad health'):updater.activate(new,db,'host','https://host')
                self.assertEqual((base/'current').resolve(),old)
                service.assert_any_call('restart','blackgoldlink.service','blackgoldlink-worker.service')
                with closing(sqlite3.connect(db)) as con:self.assertEqual(con.execute('SELECT text FROM messages').fetchone()[0],'keep me')
                self.assertTrue((base/'backups/new/collection.db').exists())

    def test_checksum_and_repository_asset_urls_validated(self):
        import hashlib
        repo='owner/project';tag='bgl-live-'+'a'*40;prefix='https://github.com/'+repo+'/releases/download/'+tag+'/'
        release={'tag_name':tag,'assets':[{'name':name,'browser_download_url':prefix+name} for name in ('SHA256SUMS','blackgoldlink-source.tar.gz')]}
        data=b'example';sums=(hashlib.sha256(data).hexdigest()+'  blackgoldlink-source.tar.gz\n').encode()
        with patch.object(updater,'fetch',side_effect=[sums,data]):self.assertEqual(updater.release_archive(repo,release),data)
        with patch.object(updater,'fetch',side_effect=[sums,b'wrong']):
            with self.assertRaisesRegex(RuntimeError,'Checksum'):updater.release_archive(repo,release)
        release['assets'][0]['browser_download_url']='http://127.0.0.1/private'
        with patch.object(updater,'fetch') as fetch:
            with self.assertRaisesRegex(RuntimeError,'asset URL'):updater.release_archive(repo,release)
            fetch.assert_not_called()
