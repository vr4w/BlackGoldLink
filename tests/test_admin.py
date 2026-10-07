import json
import time
import unittest
from unittest.mock import patch
from app import connection, create_app
from admin import configured_ids
from worker import run_once
import test_social
import test_flow

class Administration(unittest.TestCase):
    setUp=test_social.Social.setUp
    tearDown=test_social.Social.tearDown
    csrf=test_social.Social.csrf
    login=test_social.Social.login
    setup_members=test_social.Social.setup_members
    post=test_social.Social.post
    accept=test_social.Social.accept
    def setup_admin(self):
        self.setup_members();self.app.extensions['admin_ids']=configured_ids('101')
    def owner_action(self,uid,action,confirm='yes'):
        return self.post(self.client,f'/admin/users/{uid}/{action}',confirm=confirm)
    def test_hidden_panel_is_server_authorised_by_immutable_identity(self):
        self.setup_admin()
        self.assertEqual(self.app.test_client().get('/admin').status_code,404)
        self.assertEqual(self.peer.get('/admin').status_code,404)
        self.assertEqual(self.peer.post('/admin/users/1/suspend',data={'csrf':'wrong','confirm':'yes'}).status_code,400)
        self.assertEqual(self.post(self.peer,'/admin/users/1/suspend',confirm='yes').status_code,404)
        self.assertNotIn(b'href="/admin"',self.peer.get('/profile').data)
        self.assertIn(b'href="/admin"',self.client.get('/profile').data)
        # An editable name/handle never creates admin privileges.
        self.post(self.peer,'/profile',display_name='test-user',handle='owner',bio='')
        self.assertEqual(self.peer.get('/admin').status_code,404)
        page=self.client.get('/admin').data
        self.assertIn(b'Registered accounts',page);self.assertIn(b'private-person',page)
        self.assertNotIn(b'access-secret',page);self.assertNotIn(b'access-token',page)
        self.assertEqual(self.client.get('/admin').headers['Cache-Control'],'no-store')
        live=self.client.get('/admin',headers={'Accept':'application/json'})
        self.assertIn('Registered accounts',live.json['html'])
        self.assertNotIn('access-token',live.json['html'])
        self.assertEqual(self.peer.get('/admin',headers={'Accept':'application/json'}).status_code,404)
    def test_signout_revokes_all_sessions_and_keeps_data(self):
        self.setup_admin();before=self.peer.get('/export').json
        self.assertEqual(self.client.get('/admin/users/2/signout').status_code,200)
        self.assertEqual(self.peer.get('/app').status_code,200) # GET confirmation does nothing.
        self.assertEqual(self.owner_action(2,'signout',confirm='').status_code,400)
        self.assertEqual(self.client.post('/admin/users/2/signout',data={'confirm':'yes'}).status_code,400)
        self.assertEqual(self.owner_action(2,'signout').status_code,302)
        self.assertEqual(self.peer.get('/app').status_code,302)
        db=connection(self.app)
        self.assertEqual(db.execute('SELECT count(*) FROM sessions WHERE user_id=2').fetchone()[0],0)
        self.assertEqual(json.loads(db.execute('SELECT data FROM snapshots WHERE user_id=2').fetchone()[0]),before['snapshot'])
        self.assertEqual(db.execute('SELECT count(*) FROM account_moderation').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT action FROM admin_actions').fetchone()[0],'signout');db.close()
    def test_suspend_blocks_oauth_existing_sessions_sharing_and_restore(self):
        self.setup_admin();self.accept()
        self.assertEqual(self.owner_action(2,'suspend').status_code,302)
        self.assertEqual(self.peer.get('/api/chat/1').status_code,302)
        self.assertNotIn('friend</strong>',self.client.get('/api/friends').json['html'])
        self.assertEqual(self.client.get('/compare/2').status_code,404)
        with patch.object(test_flow.FakeDiscogs,'identity',return_value={'id':202,'username':'friend'}):
            self.peer.get('/')
            with self.peer.session_transaction() as session:csrf=session['csrf']
            self.assertEqual(self.peer.post('/connect',data={'csrf':csrf,'consent':'yes','adult':'yes','invite_code':'friends'}).status_code,302)
            self.assertEqual(self.peer.get('/oauth/callback?oauth_token=request-token&oauth_verifier=verified').status_code,403)
        db=connection(self.app);self.assertEqual(db.execute('SELECT count(*) FROM sessions WHERE user_id=2').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT visible FROM users WHERE id=2').fetchone()[0],0);db.close()
        self.assertEqual(self.owner_action(2,'restore').status_code,302)
        self.assertEqual(self.peer.get('/app').status_code,302) # Restoration does not resurrect revoked sessions.
        with patch.object(test_flow.FakeDiscogs,'identity',return_value={'id':202,'username':'friend'}):
            with self.peer.session_transaction() as session:csrf=session['csrf']
            self.peer.post('/connect',data={'csrf':csrf,'consent':'yes','adult':'yes','invite_code':'friends'})
            self.assertEqual(self.peer.get('/oauth/callback?oauth_token=request-token&oauth_verifier=verified').status_code,302)
        self.assertEqual(self.peer.get('/app').status_code,200)
        db=connection(self.app);self.assertEqual(db.execute('SELECT visible FROM users WHERE id=2').fetchone()[0],0)
        self.assertEqual([r[0] for r in db.execute('SELECT action FROM admin_actions ORDER BY id')],['suspend','restore']);db.close()
    def test_owner_protection_search_escape_audit_and_deletion_cascade(self):
        self.setup_admin()
        for action in ('signout','suspend','restore'):
            self.assertEqual(self.owner_action(1,action).status_code,403)
        self.app.extensions['admin_ids']=configured_ids('101,202')
        self.assertEqual(self.owner_action(2,'suspend').status_code,403)
        self.app.extensions['admin_ids']=configured_ids('101')
        self.assertEqual(self.client.get('/admin/users/999/signout').status_code,404)
        self.assertEqual(self.client.get('/admin/users/999999999999999999999/signout').status_code,404)
        self.assertNotIn(b'private-person',self.client.get('/admin?q=%25').data)
        self.assertIn(b'friend',self.client.get('/admin?q=BGL-2').data)
        self.assertEqual(self.owner_action(2,'suspend').status_code,302)
        self.assertIn(b'Suspend account',self.client.get('/admin').data)
        db=connection(self.app);db.execute('DELETE FROM users WHERE id=2');db.commit()
        self.assertEqual(db.execute('SELECT count(*) FROM account_moderation').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT count(*) FROM admin_actions').fetchone()[0],0);db.close()
    def test_configuration_and_additive_initialisation(self):
        for value in ('owner','-1','0','1 OR 1=1','999999999999999999999'):
            with self.assertRaises(RuntimeError):configured_ids(value)
        self.assertEqual(configured_ids(' 101,101, 202 '),frozenset([101,202]))
        self.setup_admin();self.owner_action(2,'suspend')
        reopened=create_app({'TESTING':True,'DATABASE_PATH':self.app.config['DATABASE_PATH'],'SECRET_KEY':'test-secret','ADMIN_DISCOGS_IDS':'101'})
        db=connection(reopened)
        self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],4)
        self.assertEqual(db.execute('SELECT count(*) FROM account_moderation').fetchone()[0],1)
        self.assertEqual(reopened.extensions['admin_ids'],frozenset([101]));db.close()

