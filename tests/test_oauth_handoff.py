"""OAuth handoff: no cross-domain redirect chain from the consent form."""
import time
from contextlib import closing
from app import connection
import test_flow
import unittest

class OAuthHandoff(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    csrf=test_flow.Flow.csrf

    def start(self):
        return self.client.post('/connect',data={'csrf':self.csrf(),'consent':'yes','adult':'yes',
            'consent_scope':'collection-comparison-v1','invite_code':'friends'})

    def test_same_origin_document_then_normal_discogs_link(self):
        response=self.start()
        self.assertEqual(response.location,'/oauth/authorize')
        page=self.client.get(response.location)
        self.assertEqual(page.status_code,200)
        self.assertNotIn('Location',page.headers)
        self.assertIn(b'data-discogs-authorize href="https://www.discogs.com/oauth/authorize?oauth_token=request-token"',page.data)
        self.assertIn(b'oauth-handoff.js',page.data)
        self.assertNotIn(b'request-secret',page.data)
        self.assertEqual(page.headers['Referrer-Policy'],'no-referrer')
        self.assertEqual(page.headers['Cache-Control'],'no-store')
        self.assertIn("form-action 'self'",page.headers['Content-Security-Policy'])
        # Rendering/reloading the handoff neither consumes nor replaces pending credentials.
        self.assertEqual(self.client.get(response.location).status_code,200)
        with closing(connection(self.app)) as db:self.assertEqual(db.execute('SELECT count(*) FROM pending').fetchone()[0],1)
        self.assertEqual(self.client.get('/oauth/callback?oauth_token=request-token&oauth_verifier=verified').location,'/app')
        self.assertEqual(self.client.get('/oauth/authorize').location,'/invite')

    def test_handoff_is_bound_to_browser_session(self):
        self.start()
        other=self.app.test_client()
        page=other.get('/oauth/authorize?oauth_token=request-token&next=https://example.com')
        self.assertEqual(page.location,'/invite')
        self.assertNotIn(b'request-token',page.data)
        # Even the initiating browser cannot substitute a destination or token.
        page=self.client.get('/oauth/authorize?oauth_token=attacker&next=https://example.com')
        self.assertIn(b'oauth_token=request-token',page.data)
        self.assertNotIn(b'href="https://example.com',page.data)
        self.assertNotIn(b'authorize?oauth_token=attacker"',page.data)

    def test_expired_handoff_returns_to_signin_in_both_languages(self):
        for language,copy in [('en',b'Connection expired. Please sign in again.'),('de','Verbindung abgelaufen. Bitte erneut anmelden.'.encode())]:
            self.start()
            with closing(connection(self.app)) as db:db.execute('UPDATE pending SET created=?',(time.time()-601,));db.commit()
            self.client.set_cookie('bgl_language',language)
            response=self.client.get('/oauth/authorize',follow_redirects=True)
            self.assertIn(copy,response.data)
            self.assertNotIn(b'data-discogs-authorize',response.data)
