import json,re,time,unittest
from unittest.mock import patch
from app import connection,encrypt
from collection_view import visible_releases,record_spines
from discogs import Discogs
from worker import run_once
from demo import profiles
import test_flow

class CollectionView(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    csrf=test_flow.Flow.csrf
    login=test_flow.Flow.login

    def test_media_filter_and_shelf_deduplication(self):
        items=[dict(id=1,master_id=5,formats=[{'name':'Vinyl'}]),dict(id=1,master_id=5,formats=[{'name':'Vinyl'}]),dict(id=2,master_id=5,formats=[{'name':'Vinyl'}]),dict(id=3,formats=[{'name':'CD'}]),dict(id=4)]
        self.assertEqual([x['id'] for x in visible_releases(items)],[1,2])
        self.assertEqual(len(record_spines(items)),1)
        self.assertEqual([x['id'] for x in visible_releases(items,'all')],[1,2,3,4])
        self.assertEqual([x['id'] for x in visible_releases(items,'other')],[3])
        self.assertEqual([x['id'] for x in visible_releases(items,'unknown')],[4])

    def test_import_preserves_format_metadata(self):
        api=Discogs('k','s','BGL local test')
        info={'id':1,'title':'Vinyl album','formats':[{'name':'Vinyl','qty':'2','descriptions':['LP']}],'artists':[]}
        with patch.object(api,'request',return_value={'pagination':{'pages':1},'releases':[{'basic_information':info}]}):result=api.import_list('user','collection')
        self.assertEqual(result[0]['formats'],info['formats'])

    def test_compact_dashboard_filter_and_source_links(self):
        self.login();run_once(self.app)
        db=connection(self.app);data=profiles()[0]
        data['collection'][0]['formats']=[{'name':'CD'}]
        data['collection'][1].pop('formats')
        data['collection'][2]['title']='<script>alert(1)</script>'
        db.execute('UPDATE snapshots SET data=?',(json.dumps(data),));db.commit();db.close()
        page=self.client.get('/app').data
        self.assertIn(b'album-grid',page);self.assertIn(b'sync-badge',page)
        self.assertNotIn(b'<strong>Import complete</strong>',page)
        self.assertNotIn(b'data-collection-vinyl',page)
        self.assertIn(b'&lt;script&gt;alert(1)&lt;/script&gt;',page)
        self.assertNotIn(b'<script>alert(1)</script>',page)
        self.assertIn(b'target="_blank" rel="noopener noreferrer"',page)
        self.assertIn(b'Some records have no media format',page)
        self.assertNotIn(b'/release/-1"',page)
        self.assertIn(b'/release/-1"',self.client.get('/app?medium=all').data)
        self.assertIn(b'/release/-1"',self.client.get('/app?medium=other').data)

    def test_search_respects_optin_and_literal_wildcards(self):
        self.login();run_once(self.app);self.app.config['MATCHING_APPROVED']=True
        db=connection(self.app);db.execute('UPDATE users SET visible=1')
        for uid,name,visible,age in [(2,'found_user',1,0),(3,'private-person',0,0),(4,'stale-person',1,7*3600)]:
            db.execute('INSERT INTO users(id,discogs_id,username,credentials,consent_at,visible) VALUES(?,?,?,?,?,?)',(uid,uid+200,name,encrypt(self.app,{}),time.time(),visible))
            db.execute('INSERT INTO snapshots VALUES(?,?,?)',(uid,json.dumps(profiles()[1]),time.time()-age))
        db.commit();db.close()
        page=self.client.get('/friends').data
        self.assertIn(b'found_user',page);self.assertNotIn(b'private-person',page);self.assertIn(b'stale-person',page);self.assertNotEqual(self.client.get('/compare/4').status_code,200)
        self.assertIn(b'found_user',self.client.get('/friends?q=BGL-2').data)
        self.assertIn(b'found_user',self.client.get('/friends?q=found_user').data)
        self.assertNotIn(b'found_user',self.client.get('/friends?q=%25').data)
        self.assertNotIn(b'found_user',self.client.get('/friends?q=%27%20OR%201%3D1').data)
        self.client.post('/visibility',data={'csrf':self.csrf()})
        self.assertNotIn(b'found_user',self.client.get('/friends').data)
        self.app.config['MATCHING_APPROVED']=False
        self.assertNotIn(b'found_user',self.client.get('/friends').data)

    def test_radio_invitation_is_scoped_to_each_login(self):
        self.login();run_once(self.app)
        first=self.client.get('/app').data
        nonce=re.search(rb'data-session="([^"]+)"',first).group(1)
        self.assertIn(b'data-ready="true"',first)
        self.assertIn(b'data-music-no',first)
        self.assertEqual(nonce,re.search(rb'data-session="([^"]+)"',self.client.get('/app').data).group(1))
        self.login()
        second=self.client.get('/app').data
        self.assertNotEqual(nonce,re.search(rb'data-session="([^"]+)"',second).group(1))
        self.assertNotIn(b'<iframe',second)
