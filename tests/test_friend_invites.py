import re
import time
import unittest
from unittest.mock import patch
from itsdangerous import URLSafeTimedSerializer
from app import connection
from demo import profiles
from worker import run_once
import test_flow

class FriendInvites(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    csrf=test_flow.Flow.csrf
    login=test_flow.Flow.login
    def token(self,uid=1):
        return URLSafeTimedSerializer(self.app.config['SECRET_KEY'],salt='bgl-friend-invitation-v1').dumps(uid)

    def test_invite_to_oauth_import_optin_and_real_compare(self):
        self.app.config['MATCHING_APPROVED']=True
        self.login();run_once(self.app)
        token=self.token();path='/join/'+token
        guest=self.app.test_client()
        page=guest.get(path)
        self.assertEqual(page.status_code,200)
        self.assertNotIn(b'test-user',page.data)
        self.assertNotIn(b'name="invite_code"',page.data)
        self.assertIn(b'name="friend_token"',page.data)
        self.assertIn('https://www.discogs.com',page.headers['Content-Security-Policy'])
        with guest.session_transaction() as session:csrf=session['csrf']
        response=guest.post('/connect',data={'csrf':csrf,'consent':'yes','adult':'yes','friend_token':token})
        self.assertEqual(response.status_code,302)
        with patch.object(test_flow.FakeDiscogs,'identity',return_value={'id':202,'username':'friend-user'}):
            self.assertEqual(guest.get('/oauth/callback?oauth_token=request-token&oauth_verifier=verified').location,path)
        self.assertIn(b'data-poll',guest.get(path).data)
        with patch.object(test_flow.FakeDiscogs,'import_list',side_effect=lambda username,kind,progress:profiles()[1][kind]):
            run_once(self.app)
        page=guest.get(path).data
        self.assertIn(b'Choose to share',page)
        self.assertNotIn(b'test-user',page)
        with guest.session_transaction() as session:csrf=session['csrf']
        self.assertEqual(guest.post('/visibility',data={'csrf':csrf,'visible':'yes','friend_token':token}).location,path)
        self.assertIn(b'friend still needs to enable sharing',guest.get(path).data)
        self.client.post('/visibility',data={'csrf':self.csrf(),'visible':'yes'})
        self.assertIn(b'START BLACKGOLD LINK',guest.get(path).data)
        result=guest.get('/compare/1')
        self.assertEqual(result.status_code,200)
        self.assertIn(b'70.7',result.data)
        self.assertIn(b'test-user',result.data)
        self.client.post('/visibility',data={'csrf':self.csrf()})
        self.assertEqual(guest.get('/compare/1').status_code,404)
        self.assertNotIn(b'test-user',guest.get(path).data)

    def test_invitation_cannot_bypass_gate_or_csrf_and_expires(self):
        self.login();run_once(self.app)
        token=self.token();guest=self.app.test_client()
        guest.get('/join/'+token)
        self.assertEqual(guest.post('/connect',data={'friend_token':token,'consent':'yes','adult':'yes'}).status_code,400)
        with guest.session_transaction() as session:csrf=session['csrf']
        self.assertEqual(guest.post('/connect',data={'csrf':csrf,'friend_token':token+'x','consent':'yes','adult':'yes'}).status_code,403)
        with patch('itsdangerous.timed.TimestampSigner.get_timestamp',return_value=int(time.time())-8*86400):expired=self.token()
        self.assertEqual(guest.get('/join/'+expired).status_code,404)
        self.assertEqual(guest.get('/join/'+self.token(999)).status_code,404)
        self.assertIn(b'name="invite_code"',guest.get('/invite').data)
        self.assertEqual(self.client.get('/compare/2').status_code,403)

    def test_links_use_configured_origin_and_own_link_returns_dashboard(self):
        self.login();self.app.config['BASE_URL']='https://future.example'
        page=self.client.get('/app').data
        self.assertIn(b'https://future.example/join/',page)
        self.assertEqual(self.client.get('/join/'+self.token()).location,'/app')
