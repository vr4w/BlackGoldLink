import json
import time
import unittest
from unittest.mock import patch
import test_flow
from app import connection, encrypt
from covers import trusted_image_url, SafeRedirect
from matching import compare, combine_components
from score_comments import COMMENT_POOLS, comments_for_score
from demo import profiles
from worker import run_once

class LinkAlgorithms(unittest.TestCase):
    def test_component_policy(self):
        a,b=profiles();r=compare(a,b)
        self.assertEqual(r['score'],70.7)
        self.assertEqual(r['score_factors'],{'releases':1})
        self.assertIsNone(r['component_scores']['masters'])
        self.assertEqual(combine_components({'releases':50,'artists':100},{'releases':3,'artists':1}),62.5)
        with self.assertRaises(ValueError):combine_components({'masters':None},{'masters':1})
        with self.assertRaises(ValueError):combine_components({'releases':50},{'releases':-1})
    def test_pressings_and_duplicates(self):
        item={'title':'Fiction','artists':[{'id':7,'name':'Artist'}],'genres':['Jazz'],'master_id':42,'styles':['Fusion'],'labels':[{'id':9,'name':'Label'}]}
        a={'collection':[dict(item,id=1),dict(item,id=1)],'wantlist':[]};b={'collection':[dict(item,id=2)],'wantlist':[]}
        r=compare(a,b);self.assertEqual(r['score'],0);self.assertEqual(r['a_size'],1)
        self.assertEqual(r['component_scores']['masters'],100);self.assertEqual(r['component_scores']['labels'],100)
    def test_empty_identical_and_directions(self):
        empty={'collection':[],'wantlist':[]};a,b=profiles()
        self.assertEqual(compare(empty,a)['score'],0);self.assertEqual(compare(a,a)['score'],100)
        self.assertEqual(compare(a,b)['for_a'],compare(b,a)['for_b'])
    def test_comments_boundaries(self):
        self.assertEqual(len(COMMENT_POOLS),7)
        for ceiling,pool in COMMENT_POOLS:
            self.assertGreaterEqual(len(pool),8);self.assertEqual(len(pool),len(set(pool)));self.assertIs(comments_for_score(ceiling),pool)
        self.assertIs(comments_for_score(70.7),COMMENT_POOLS[4][1]);self.assertIs(comments_for_score(95.1),COMMENT_POOLS[6][1])
    def test_oauth_post_and_no_database_writes(self):
        from discogs import Discogs,DiscogsError
        api=Discogs('key','secret','tests')
        with patch.object(api,'request',return_value={}) as call:
            api.request_token('https://blackgoldlink.almost-everything.de/oauth/callback')
            self.assertEqual(call.call_args.kwargs['method'],'POST')
            api.access_token('verified')
            self.assertEqual(call.call_args.kwargs['method'],'POST')
        with self.assertRaises(DiscogsError):api.request('/users/test/wants',method='POST')

    def test_image_hosts_and_redirects(self):
        self.assertTrue(trusted_image_url('https://i.discogs.com/signed/thumb.jpg'))
        for url in ['http://i.discogs.com/x','https://i.discogs.com.evil.test/x','https://127.0.0.1/x','https://user:secret@i.discogs.com/x','https://i.discogs.com:8080/x','file:///etc/passwd']:
            self.assertFalse(trusted_image_url(url))
        with self.assertRaises(ValueError):SafeRedirect().redirect_request(None,None,302,'',{},'https://evil.test/x')

class LinkFlow(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    csrf=test_flow.Flow.csrf
    login=test_flow.Flow.login
    def test_cover_ownership_expiry_and_cache(self):
        self.login()
        own={'collection':[{'id':17,'title':'Owned','artists':[],'genres':[],'thumb_url':'https://i.discogs.com/thumb.jpg'}],'wantlist':[]}
        other={'collection':[{'id':18,'title':'Private','artists':[],'genres':[],'thumb_url':'https://i.discogs.com/private.jpg'}],'wantlist':[]}
        db=connection(self.app);db.execute('INSERT INTO snapshots VALUES(1,?,?)',(json.dumps(own),time.time()))
        db.execute('INSERT INTO users(discogs_id,username,credentials,consent_at) VALUES(202,\'private\',?,?)',(encrypt(self.app,{}),time.time()))
        db.execute('INSERT INTO snapshots VALUES(2,?,?)',(json.dumps(other),time.time()));db.commit();db.close()
        with patch('app.fetch_cover',return_value=(b'\xff\xd8\xffjpeg','image/jpeg')) as fetch:
            self.assertEqual(self.client.get('/cover/17').status_code,200);self.assertEqual(self.client.get('/cover/17').status_code,200)
            self.assertEqual(fetch.call_count,1);self.assertEqual(self.client.get('/cover/18').status_code,404)
            self.assertEqual(self.app.test_client().get('/cover/17').status_code,302)
            db=connection(self.app);db.execute('UPDATE snapshots SET fetched_at=? WHERE user_id=1',(time.time()-21601,));db.commit();db.close()
            self.assertEqual(self.client.get('/cover/17').status_code,404)
    def test_two_independent_oauth_accounts(self):
        self.login();run_once(self.app);first=self.client
        class Peer(test_flow.FakeDiscogs):
            def identity(self):return {'id':202,'username':'second-user'}
            def import_list(self,username,kind,progress):progress(1,1);return profiles()[1][kind]
        self.app.config['DISCOGS_FACTORY']=Peer;self.client=self.app.test_client();self.login();run_once(self.app)
        db=connection(self.app);self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],2)
        db.execute('UPDATE users SET visible=1');db.commit();db.close();self.app.config['MATCHING_APPROVED']=True
        self.assertIn(b'70.7',first.get('/compare/2').data);self.assertIn(b'70.7',self.client.get('/compare/1').data)
        self.assertIn(b'second-user',self.client.get('/app').data);self.assertNotIn(b'second-user',first.get('/export').data)
    def test_scene_and_demo_assets(self):
        page=self.client.get('/demo')
        for text in [b'data-target="70.7"',b'START BLACKGOLD LINK',b'demo-covers/',b'YOU HAVE']:
            self.assertIn(text,page.data)
        with self.client.get('/static/app.js') as script:
            self.assertIn(b'prefers-reduced-motion',script.data)
        self.assertEqual(self.client.get('/demo/').status_code,200)
