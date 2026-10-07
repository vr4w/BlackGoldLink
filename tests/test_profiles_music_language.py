import json
import sqlite3
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from app import create_app,connection
from music import youtube_id
import test_flow

class Features(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    csrf=test_flow.Flow.csrf
    login=test_flow.Flow.login
    # Inherit its setup/helpers only; inherited tests are already covered elsewhere.
    def test_oauth_redirect_policy_is_scoped(self):
        policy=self.client.get('/invite').headers['Content-Security-Policy']
        self.assertIn("form-action 'self' https://www.discogs.com",policy)
        self.assertNotIn('https://www.discogs.com',self.client.get('/').headers['Content-Security-Policy'])
        response=self.client.post('/connect',data={'csrf':self.csrf(),'consent':'yes','adult':'yes','invite_code':'friends'})
        self.assertEqual(response.status_code,302)
        self.assertIn('https://www.discogs.com/oauth/authorize?',response.location)
        self.assertIn("form-action 'self' https://www.discogs.com",response.headers['Content-Security-Policy'])
        self.assertIn(b'data-connect-feedback',self.client.get('/invite').data)

    def test_language_default_switch_and_redirect_guard(self):
        response=self.client.get('/')
        self.assertIn(b'<html lang="en">',response.data)
        self.assertIn(b'Compare your collection with others.',response.data)
        self.assertNotIn('Vergleiche deine Sammlung mit anderen.'.encode(),response.data)
        self.assertEqual(self.client.post('/language',data={'language':'de'}).status_code,400)
        response=self.client.post('/language',data={'csrf':self.csrf(),'language':'de','next':'//evil.example'})
        self.assertEqual(response.location,'/')
        self.assertIn(b'<html lang="de">',self.client.get('/').data)
        self.assertIn('Vergleiche deine Sammlung mit anderen.'.encode(),self.client.get('/').data)
        self.assertEqual(self.client.post('/language',data={'csrf':self.csrf(),'language':'xx'}).status_code,400)

    def test_profile_ownership_bounds_and_export(self):
        self.assertEqual(self.client.get('/profile').status_code,302)
        self.login()
        result=self.client.post('/profile',data={'csrf':self.csrf(),'display_name':'<script>hi</script>','handle':'marv_records','bio':'A small shelf.'})
        self.assertEqual(result.status_code,302)
        page=self.client.get('/profile').data
        self.assertIn(b'&lt;script&gt;hi&lt;/script&gt;',page)
        self.assertNotIn(b'<script>hi</script>',page)
        export=self.client.get('/export').json
        self.assertEqual(export['bio'],'A small shelf.')
        self.assertEqual(export['username'],'test-user')
        self.assertEqual(self.client.post('/profile',data={'csrf':self.csrf(),'bio':'x'*501}).status_code,400)
        self.assertEqual(self.client.get('/profiles/999').status_code,403)

    def test_music_requires_consent_collection_and_valid_links(self):
        self.assertEqual(self.client.post('/api/music/next',data={'csrf':self.csrf(),'consent':'yes'}).status_code,302)
        self.login()
        self.assertEqual(self.client.post('/api/music/next',data={'csrf':self.csrf()}).status_code,400)
        self.assertEqual(self.client.post('/api/music/next',data={'csrf':self.csrf(),'consent':'yes'}).status_code,409)
        test_flow.run_once(self.app)
        fake=SimpleNamespace()
        fake.request=lambda path: {'videos':[{'uri':'https://www.youtube.com/watch?v=dQw4w9WgXcQ','title':'Linked track'},{'uri':'https://evil.example/','title':'Bad'}]}
        with patch('features.client',return_value=fake):
            response=self.client.post('/api/music/next',data={'csrf':self.csrf(),'consent':'yes'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['video_id'],'dQw4w9WgXcQ')
        self.assertEqual(self.client.post('/api/music/next',data={'csrf':self.csrf(),'consent':'yes'}).status_code,429)
        db=connection(self.app)
        self.assertEqual(db.execute('SELECT count(*) FROM music_cache').fetchone()[0],1)
        db.execute('UPDATE snapshots SET fetched_at=?',(time.time()-7*3600,));db.commit();db.close()
        self.assertEqual(self.client.post('/api/music/next',data={'csrf':self.csrf(),'consent':'yes'}).status_code,409)

    def test_personal_vinyl_requires_fresh_collection_and_escapes_label(self):
        self.login()
        self.assertNotIn(b'class="collection-shelf"',self.client.get('/app').data)
        test_flow.run_once(self.app)
        self.client.post('/profile',data={'csrf':self.csrf(),'display_name':'<img onerror=x>','handle':'record_owner','bio':''})
        page=self.client.get('/app').data
        self.assertIn(b'class="collection-shelf"',page)
        self.assertIn(b'&lt;img onerror=x&gt;',page)
        self.assertNotIn(b'<img onerror=x>',page)
        self.assertNotIn(b'data-blackgold-link',page)
        db=connection(self.app)
        db.execute('UPDATE snapshots SET fetched_at=?',(time.time()-7*3600,));db.commit();db.close()
        self.assertNotIn(b'class="collection-shelf"',self.client.get('/app').data)

    def test_player_policy_and_private_members(self):
        self.assertNotIn(b'data-music ',self.client.get('/').data)
        self.login()
        page=self.client.get('/app')
        self.assertIn(b'data-music ',page.data)
        self.assertNotIn(b'<iframe',page.data)
        self.assertIn('https://www.youtube.com',page.headers['Content-Security-Policy'])
        self.assertNotIn('https://www.youtube.com',self.client.get('/invite').headers['Content-Security-Policy'])
        self.assertIn(b'Real user comparisons remain disabled',page.data)

class MigrationAndLinks(unittest.TestCase):
    def test_additive_migration_retains_old_account(self):
        with tempfile.TemporaryDirectory() as folder:
            path=folder+'/old.db';db=sqlite3.connect(path)
            db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,discogs_id INTEGER UNIQUE NOT NULL,username TEXT NOT NULL,credentials TEXT NOT NULL,consent_at REAL NOT NULL,visible INTEGER NOT NULL DEFAULT 0)')
            db.execute("INSERT INTO users VALUES(1,42,'olduser','encrypted',0,0)");db.commit();db.close()
            for _ in range(2):create_app({'TESTING':True,'DATABASE_PATH':path})
            db=sqlite3.connect(path)
            self.assertEqual(db.execute('SELECT username,credentials,bio FROM users').fetchone(),('olduser','encrypted',''));db.close()
    def test_youtube_url_allowlist(self):
        for url in ('https://www.youtube.com/watch?v=dQw4w9WgXcQ','https://youtu.be/dQw4w9WgXcQ','https://www.youtube.com/embed/dQw4w9WgXcQ'):
            self.assertEqual(youtube_id(url),'dQw4w9WgXcQ')
        for url in ('http://youtube.com/watch?v=dQw4w9WgXcQ','https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ','https://youtube.com/watch?v=bad','https://x@youtube.com/watch?v=dQw4w9WgXcQ','https://youtube.com:99/watch?v=dQw4w9WgXcQ'):
            self.assertIsNone(youtube_id(url))

