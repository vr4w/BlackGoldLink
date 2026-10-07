import json
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from cryptography.fernet import Fernet
from app import create_app, connection, encrypt
from demo import profiles
from matching import cosine, compare, rarity_weights
from worker import run_once
from discogs import Discogs, DiscogsError, oauth_header

class FakeDiscogs:
    fail=False
    def __init__(self,*args): pass
    def request_token(self,callback):
        assert callback=='http://127.0.0.1:5013/oauth/callback'
        return {'oauth_token':'request-token','oauth_token_secret':'request-secret','oauth_callback_confirmed':'true'}
    def access_token(self,verifier):
        assert verifier=='verified'
        return {'oauth_token':'access-token','oauth_token_secret':'access-secret'}
    def identity(self): return {'id':101,'username':'test-user'}
    def import_list(self,username,kind,progress):
        progress(1,1)
        if self.fail and kind=='wantlist': raise DiscogsError('Test: Wantlist nicht erreichbar')
        return profiles()[0][kind]

class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'SECRET_KEY':'test-secret','DATABASE_PATH':str(Path(self.tmp.name)/'db.sqlite'),
            'TOKEN_ENCRYPTION_KEY':Fernet.generate_key().decode(),'DISCOGS_CONSUMER_KEY':'key','DISCOGS_CONSUMER_SECRET':'secret',
            'DISCOGS_FACTORY':FakeDiscogs,'PUBLIC_SIGNUP':False,'INVITE_CODE':'friends'})
        self.client=self.app.test_client(); FakeDiscogs.fail=False
    def tearDown(self): self.tmp.cleanup()
    def csrf(self):
        self.client.get('/')
        with self.client.session_transaction() as session: return session['csrf']
    def login(self):
        response=self.client.post('/connect',data={'csrf':self.csrf(),'consent':'yes','adult':'yes','invite_code':'friends'})
        self.assertEqual(response.status_code,302)
        self.assertIn('discogs.com/oauth/authorize',response.location)
        self.assertEqual(self.client.get('/oauth/callback?oauth_token=request-token&oauth_verifier=verified').location,'/app')
    def test_vertical_flow_and_deletion(self):
        self.login(); self.assertTrue(run_once(self.app))
        self.assertEqual(self.client.get('/app').status_code,200)
        self.assertEqual(len(self.client.get('/export').json['snapshot']['collection']),8)
        db=connection(self.app); self.assertNotIn('access-token',db.execute('SELECT credentials FROM users').fetchone()[0]);db.close()
        self.assertEqual(self.client.post('/disconnect',data={'csrf':self.csrf(),'confirm':'delete'}).status_code,302)
        db=connection(self.app)
        for table in ['users','snapshots','sessions','jobs']: self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0],0)
        db.close()
    def test_partial_import_preserves_snapshot(self):
        self.login();run_once(self.app)
        db=connection(self.app);old=db.execute('SELECT data FROM snapshots').fetchone()[0]
        db.execute("INSERT INTO jobs(user_id,state,created) VALUES(1,'queued',?)",(time.time(),));db.commit();db.close()
        FakeDiscogs.fail=True;run_once(self.app)
        db=connection(self.app);self.assertEqual(db.execute('SELECT data FROM snapshots').fetchone()[0],old)
        self.assertEqual(db.execute('SELECT state FROM jobs ORDER BY id DESC').fetchone()[0],'failed');db.close()
    def test_expired_data_hidden(self):
        self.login();run_once(self.app)
        db=connection(self.app);db.execute('UPDATE snapshots SET fetched_at=?',(time.time()-21601,));db.commit();db.close()
        self.assertIsNone(self.client.get('/export').json['snapshot'])
    def test_csrf_and_invite_enforced(self):
        self.assertEqual(self.client.post('/connect',data={}).status_code,400)
        self.assertEqual(self.client.post('/connect',data={'csrf':self.csrf(),'consent':'yes','adult':'yes','invite_code':'wrong'}).status_code,403)
    def test_callback_replay(self):
        self.login();self.assertEqual(self.client.get('/oauth/callback?oauth_token=request-token&oauth_verifier=verified').status_code,400)
    def test_cross_user_privacy_gate(self):
        self.login();run_once(self.app)
        self.assertEqual(self.client.get('/compare/2').status_code,403)
        self.assertEqual(self.client.post('/visibility',data={'csrf':self.csrf(),'visible':'yes'}).status_code,403)
        self.assertEqual(self.app.test_client().get('/export').status_code,302)
    def test_approved_optin_compare(self):
        self.login();run_once(self.app)
        db=connection(self.app);db.execute('UPDATE users SET visible=1')
        db.execute('INSERT INTO users(discogs_id,username,credentials,consent_at,visible) VALUES(202,\'peer\',?,?,1)',(encrypt(self.app,{}),time.time()))
        db.execute('INSERT INTO snapshots VALUES(2,?,?)',(json.dumps(profiles()[1]),time.time()));db.commit();db.close()
        self.app.config['MATCHING_APPROVED']=True
        self.assertEqual(self.client.get('/compare/2').status_code,200)
        self.assertIn(b'70.7',self.client.get('/app').data)
        db=connection(self.app);db.execute('UPDATE users SET visible=0 WHERE id=2');db.commit();db.close()
        self.assertEqual(self.client.get('/compare/2').status_code,404)
    def test_pages_and_security_headers(self):
        for path in ['/','/invite','/demo','/privacy','/health','/missing']:
            page=self.client.get(path);self.assertIn(page.status_code,[200,404]);self.assertEqual(page.headers['Cache-Control'],'no-store')
            self.assertIn("frame-ancestors 'none'",page.headers['Content-Security-Policy'])
        self.assertNotIn(b'Data provided by Discogs',self.client.get('/demo').data)
    def test_production_refuses_incomplete_config(self):
        with self.assertRaises(RuntimeError): create_app({'APP_ENV':'production','DATABASE_PATH':str(Path(self.tmp.name)/'other')})

class Algorithm(unittest.TestCase):
    def test_fairness_and_symmetry(self):
        self.assertEqual(cosine(set(range(10)),set(range(1000))),10)
        self.assertEqual(cosine({1,2},{1,2}),100)
        self.assertEqual(cosine(set(),set()),0)
        self.assertEqual(cosine({1},{2}),0)
        a,b=profiles();self.assertEqual(compare(a,b)['score'],compare(b,a)['score'])
        self.assertEqual(compare(a,b)['for_a'],{-9,-10,-11});self.assertEqual(compare(a,b)['for_b'],{-1,-2})
    def test_rarity_hook(self):
        weights=rarity_weights([{1,2},{1},{1}]);self.assertGreater(weights[2],weights[1])
    def test_oauth_signature_rfc5849(self):
        header=oauth_header('GET','http://photos.example.net/photos?file=vacation.jpg&size=original','dpf43f3p2l4k3l03','kd94hf93k423kf44','nnch734d00sl2jdk','pfkkdhi9sl3r4s00',nonce='kllo9940pd9333jh',timestamp=1191242096)
        self.assertIn('tR3%2BTy81lMeYAr%2FFid0kMTYa%2FWM%3D',header)
    def test_pagination_and_duplicate_instances(self):
        api=Discogs('k','s','tests')
        def page(path,params):
            return {'pagination':{'pages':2},'releases':[{'basic_information':{'id':7,'title':'A','artists':[{'id':3,'name':'Artist'}],'genres':['Jazz']}}]}
        with patch.object(api,'request',side_effect=page) as mocked:
            self.assertEqual(len(api.import_list('a/b','collection')),1)
            self.assertEqual(mocked.call_count,2)
            self.assertEqual(mocked.call_args.args[0],'/users/a%2Fb/collection/folders/0/releases')

if __name__=='__main__': unittest.main()
