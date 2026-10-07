import re
import tempfile
import unittest
from pathlib import Path
from versioning import release_version
import test_flow

class Versioning(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    login=test_flow.Flow.login
    csrf=test_flow.Flow.csrf

    def test_version_endpoint_matches_every_page_and_discloses_no_account_data(self):
        version=self.client.get('/api/version')
        self.assertEqual(version.status_code,200)
        self.assertEqual(set(version.json),{'version'})
        self.assertRegex(version.json['version'],r'^[a-f0-9]{24}$')
        self.assertEqual(version.headers['Cache-Control'],'no-store')
        for path in ('/','/invite','/privacy','/imprint','/missing'):
            page=self.client.get(path).data
            self.assertIn(('data-version="'+version.json['version']+'"').encode(),page)
            self.assertIn(b'/api/version',page)
            self.assertIn(b'data-version-notice hidden',page)
            self.assertIn(b'/static/version.js',page)
        self.login()
        self.assertEqual(self.client.get('/api/version').json,version.json)
        self.assertNotIn(b'test-user',self.client.get('/api/version').data)
        self.client.set_cookie('bgl_language','de')
        page=self.client.get('/app').data
        self.assertIn('Neue Version verfügbar'.encode(),page)
        self.assertIn(b'Jetzt neu laden',page)

    def test_build_identity_ignores_accounts_secrets_paths_and_file_dates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('a','b'):
                folder=root/name
                (folder/'static').mkdir(parents=True)
                (folder/'templates').mkdir()
                (folder/'app.py').write_text('example app')
                (folder/'static/style.css').write_text('example style')
                (folder/'templates/base.html').write_text('example page')
                (folder/'translations.json').write_text('{}')
            before=release_version(root/'a')
            self.assertEqual(before,release_version(root/'b'))
            (root/'a/instance').mkdir()
            (root/'a/instance/collection.db').write_text('changed accounts and messages')
            (root/'a/.env').write_text('SECRET_KEY=do-not-hash')
            (root/'a/app.py').touch()
            self.assertEqual(before,release_version(root/'a'))
            (root/'a/static/style.css').write_text('updated style')
            self.assertNotEqual(before,release_version(root/'a'))
            (root/'b/templates/base.html').write_text('updated page')
            self.assertNotEqual(before,release_version(root/'b'))
