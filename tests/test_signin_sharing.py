"""The ordinary Discogs sign-in includes discovery and comparison consent."""
from contextlib import closing
import re
import unittest
from unittest.mock import patch
from app import CONSENT_SCOPE, connection, create_app, decrypt, encrypt
from worker import run_once
import test_flow


class SigninSharing(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    csrf=test_flow.Flow.csrf
    login=test_flow.Flow.login

    def test_two_existing_checks_explain_comparisons_in_both_languages(self):
        for language,copy in [('en','visible to signed-in BlackGoldLink members'),('de','für angemeldete BlackGoldLink-Mitglieder sichtbar')]:
            self.client.set_cookie('bgl_language',language)
            page=self.client.get('/invite').data.decode()
            self.assertEqual(len(re.findall('type="checkbox"',page)),2)
            self.assertIn(copy,page)
            self.assertIn('name="consent_scope" value="'+CONSENT_SCOPE+'"',page)
            self.assertNotIn('private profile',page)
            privacy=self.client.get('/privacy').data.decode()
            self.assertNotIn('require a separate voluntary',privacy)
            self.assertNotIn('zusätzliche freiwillige Aktivierung',privacy)

    def test_new_signin_is_discoverable_before_import_and_ready_afterwards(self):
        self.app.config['MATCHING_APPROVED']=True
        self.login()
        peer=self.app.test_client();peer.get('/invite')
        with peer.session_transaction() as session:csrf=session['csrf']
        peer.post('/connect',data={'csrf':csrf,'invite_code':'friends','consent':'yes','adult':'yes','consent_scope':CONSENT_SCOPE})
        with patch.object(test_flow.FakeDiscogs,'identity',return_value={'id':202,'username':'new-member'}):
            peer.get('/oauth/callback?oauth_token=request-token&oauth_verifier=verified')
        self.assertIn('new-member',self.client.get('/api/friends?q=new-member').json['html'])
        self.assertIn('test-user',peer.get('/api/friends?q=test-user').json['html'])
        self.assertEqual(self.client.get('/compare/2').status_code,404)
        run_once(self.app);run_once(self.app)
        self.assertEqual(self.client.get('/compare/2').status_code,200)
        self.assertNotIn(b'name="visible"',self.client.get('/app').data)
        self.assertNotIn(b'Save visibility',self.client.get('/app').data)
        # Participation can still be withdrawn; returning uses the normal sign-in.
        self.client.post('/visibility',data={'csrf':self.csrf()})
        self.assertNotIn('test-user',peer.get('/api/friends?q=test-user').json['html'])
        self.assertEqual(peer.get('/compare/1').status_code,404)
        self.login();self.assertIn('test-user',peer.get('/api/friends?q=test-user').json['html'])

    def test_legacy_private_account_preserved_until_normal_reauthentication(self):
        self.login();run_once(self.app)
        with closing(connection(self.app)) as db:
            db.execute("UPDATE users SET visible=0,display_name='Keep name',bio='Keep bio',consent_at=1");db.commit()
        create_app(dict(self.app.config)) # No blanket visibility migration on startup.
        with closing(connection(self.app)) as db:self.assertEqual(db.execute('SELECT visible FROM users').fetchone()[0],0)
        self.app.config['MATCHING_APPROVED']=True
        self.assertIn(b'Sign in with Discogs once more',self.client.get('/app').data)
        self.login()
        with closing(connection(self.app)) as db:
            user=db.execute('SELECT * FROM users').fetchone()
            self.assertEqual(user['visible'],1);self.assertEqual(user['display_name'],'Keep name');self.assertEqual(user['bio'],'Keep bio')
            self.assertGreater(user['consent_at'],1)
            self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM snapshots').fetchone()[0],1)

    def test_old_forms_and_pending_oauth_do_not_expand_private_import_consent(self):
        with patch.object(test_flow.FakeDiscogs,'request_token') as api:
            response=self.client.post('/connect',data={'csrf':self.csrf(),'invite_code':'friends','consent':'yes','adult':'yes'})
            self.assertEqual(response.location,'/invite');api.assert_not_called()
        csrf=self.csrf()
        self.client.post('/connect',data={'csrf':csrf,'invite_code':'friends','consent':'yes','adult':'yes','consent_scope':CONSENT_SCOPE})
        with self.client.session_transaction() as session:pending=session['pending']
        with closing(connection(self.app)) as db:
            row=db.execute('SELECT credentials FROM pending WHERE id=?',(pending,)).fetchone()
            old=decrypt(self.app,row[0]);old.pop('bgl_consent_scope')
            db.execute('UPDATE pending SET credentials=? WHERE id=?',(encrypt(self.app,old),pending));db.commit()
        with patch.object(test_flow.FakeDiscogs,'access_token') as api:
            response=self.client.get('/oauth/callback?oauth_token=request-token&oauth_verifier=verified')
            self.assertEqual(response.location,'/invite');api.assert_not_called()
        with closing(connection(self.app)) as db:self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)
