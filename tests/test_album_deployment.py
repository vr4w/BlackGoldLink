import hashlib
import importlib.util
from pathlib import Path
import tempfile
import sqlite3
from contextlib import closing
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('album_installer',Path(__file__).resolve().parents[1]/'deployment/activate-album-experience.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
spec=importlib.util.spec_from_file_location('album_test_updater',Path(__file__).resolve().parents[1]/'deployment/github-updater.py')
updater=importlib.util.module_from_spec(spec);spec.loader.exec_module(updater)


class AlbumUpgrade(unittest.TestCase):
    def test_failed_health_restores_code_and_keeps_new_messages(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp).resolve();(base/'releases').mkdir()
            old,new=base/'releases/old',base/'releases/new';old.mkdir();new.mkdir()
            (base/'current').symlink_to(old);env=base/'env';env.write_text('fictional test config')
            db=base/'db.sqlite'
            with closing(sqlite3.connect(db)) as con:
                con.execute('CREATE TABLE messages(body TEXT)');con.execute("INSERT INTO messages VALUES('original')");con.commit()
            def fail_after_new_message(*args):
                with closing(sqlite3.connect(db)) as con:
                    con.execute("INSERT INTO messages VALUES('arrived during update')");con.commit()
                raise RuntimeError('health failed')
            with patch.object(updater,'BASE',base),patch.object(updater,'ENV',env),patch.object(installer,'validate_baseline'),patch.object(updater,'pending',return_value=0),patch.object(installer.subprocess,'run'),patch.object(installer.subprocess,'check_output',return_value='a'*24),patch.object(updater,'systemctl') as service,patch.object(updater,'health',side_effect=fail_after_new_message):
                with self.assertRaisesRegex(RuntimeError,'health failed'):installer.activate(new,updater,db,'host','https://host')
                self.assertEqual((base/'current').resolve(),old)
                service.assert_any_call('restart','blackgoldlink.service','blackgoldlink-worker.service')
                with closing(sqlite3.connect(db)) as con:self.assertEqual(con.execute('SELECT count(*) FROM messages').fetchone()[0],2)
                with closing(sqlite3.connect(base/'backups/new/collection.db')) as con:self.assertEqual(con.execute('SELECT count(*) FROM messages').fetchone()[0],1)

    def test_installer_pins_the_actual_new_score(self):
        score=Path(__file__).resolve().parents[1]/'matching.py'
        self.assertEqual(hashlib.sha256(score.read_bytes()).hexdigest(),installer.NEW_SCORE_SHA)

    def test_one_time_guard_allows_only_pinned_score_and_unchanged_imports_and_schemas(self):
        with tempfile.TemporaryDirectory() as temp:
            old,new=Path(temp)/'old',Path(temp)/'new'
            old.mkdir();new.mkdir()
            for folder in (old,new):
                for name in updater.STABLE:(folder/name).write_text('unchanged')
                for file,name in updater.SCHEMAS:(folder/file).write_text(name+"='existing schema'")
            (old/'matching.py').write_text('old-score');(new/'matching.py').write_text('new-score')
            with patch.object(installer,'OLD_SCORE_SHA',hashlib.sha256(b'old-score').hexdigest()),patch.object(installer,'NEW_SCORE_SHA',hashlib.sha256(b'new-score').hexdigest()):
                installer.validate_baseline(old,new,updater)
                (new/'worker.py').write_text('changed')
                with self.assertRaisesRegex(RuntimeError,'worker.py'):installer.validate_baseline(old,new,updater)
                (new/'worker.py').write_text('unchanged')
                (new/'social.py').write_text("SOCIAL_SCHEMA='different'")
                with self.assertRaisesRegex(RuntimeError,'schema'):installer.validate_baseline(old,new,updater)
                (new/'social.py').write_text("SOCIAL_SCHEMA='existing schema'")
                (new/'matching.py').write_text('unreviewed-score')
                with self.assertRaisesRegex(RuntimeError,'Album-Score'):installer.validate_baseline(old,new,updater)

    def test_automatic_updater_still_rejects_score_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            old,new=Path(temp)/'old',Path(temp)/'new'
            old.mkdir();new.mkdir()
            for folder in (old,new):
                for name in updater.STABLE:(folder/name).write_text('unchanged')
                for file,name in updater.SCHEMAS:(folder/file).write_text(name+"='existing schema'")
            (new/'matching.py').write_text('new album score')
            with self.assertRaisesRegex(RuntimeError,'manual release'):updater.compatible(old,new)
