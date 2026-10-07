import hashlib
import json
import time
import unittest
from unittest.mock import patch
from app import connection,encrypt,create_app
from demo import profiles
from worker import run_once
import test_flow

class Social(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    csrf=test_flow.Flow.csrf
    login=test_flow.Flow.login
    def setup_members(self):
        self.app.config['MATCHING_APPROVED']=True
        self.login();run_once(self.app)
        db=connection(self.app);db.execute('UPDATE users SET visible=1')
        for uid,name,visible in [(2,'friend',1),(3,'stranger',1),(4,'private-person',0)]:
            db.execute('INSERT INTO users(id,discogs_id,username,credentials,consent_at,visible) VALUES(?,?,?,?,?,?)',(uid,uid+200,name,encrypt(self.app,{}),time.time(),visible))
            db.execute('INSERT INTO snapshots VALUES(?,?,?)',(uid,json.dumps(profiles()[1]),time.time()))
            sid='test-session-'+str(uid)
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(sid.encode()).hexdigest(),uid,time.time()+3600))
        db.commit();db.close()
        self.peer=self.app.test_client();self.stranger=self.app.test_client()
        for client,uid in [(self.peer,2),(self.stranger,3)]:
            with client.session_transaction() as session:session['sid']='test-session-'+str(uid)
            client.get('/app')
    def post(self,client,path,**data):
        client.get('/')
        with client.session_transaction() as session:csrf=session['csrf']
        return client.post(path,data={'csrf':csrf,**data})
    def accept(self):
        self.assertEqual(self.post(self.client,'/friends/2/request').status_code,302)
        self.assertEqual(self.post(self.peer,'/friends/1/accept').status_code,302)
    def test_mutual_acceptance_before_chat_and_contacts(self):
        self.setup_members()
        self.assertEqual(self.client.get('/api/chat/2').status_code,403)
        self.assertNotIn(b'data-chat data-endpoint',self.client.get('/compare/2').data)
        self.post(self.client,'/friends/2/request')
        self.assertEqual(self.post(self.client,'/friends/2/accept').status_code,403)
        self.assertEqual(self.client.get('/api/chat/2').status_code,403)
        self.assertIn(b'Accept',self.peer.get('/app').data)
        self.post(self.peer,'/friends/1/accept')
        page=self.client.get('/compare/2').data
        self.assertIn(b'data-chat data-endpoint',page)
        self.assertIn(b'contacts-list',page)
        self.assertEqual(self.client.get('/api/chat/2').status_code,200)
        self.assertEqual(self.stranger.get('/api/chat/2').status_code,403)
    def test_send_persistence_idempotence_and_history(self):
        self.setup_members();self.accept()
        body='<script>alert(1)</script> 💿'
        sent=self.post(self.client,'/api/chat/2',body=body,nonce='abcdefghijklmnop')
        self.assertEqual(sent.status_code,201)
        self.assertEqual(self.post(self.client,'/api/chat/2',body=body,nonce='abcdefghijklmnop').json['id'],sent.json['id'])
        self.assertEqual(self.peer.get('/api/chat/1').json['messages'][0]['body'],body)
        self.assertEqual(self.client.get('/api/chat/2?after='+str(sent.json['id'])).json['messages'],[])
        reopened=create_app({'TESTING':True,'SECRET_KEY':'test-secret','DATABASE_PATH':self.app.config['DATABASE_PATH']})
        db=connection(reopened);self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],1);db.close()
        db=connection(self.app)
        for i in range(65):db.execute('INSERT INTO messages(low_id,high_id,sender_id,body,created,nonce) VALUES(1,2,1,?,?,?)',(str(i),time.time()-100+i,'history-nonce-'+str(i)))
        db.commit();db.close()
        page=self.peer.get('/api/chat/1').json;self.assertEqual(len(page['messages']),60);self.assertTrue(page['older'])
        older=self.peer.get('/api/chat/1?before='+str(page['messages'][0]['id'])).json
        self.assertEqual(len(older['messages']),6);self.assertFalse(older['older'])
    def test_csrf_throttle_and_message_bounds(self):
        self.setup_members();self.accept()
        self.assertEqual(self.client.post('/api/chat/2',data={'body':'no','nonce':'abcdefghijklmnop'}).status_code,400)
        self.assertEqual(self.post(self.client,'/api/chat/2',body='x'*2001,nonce='abcdefghijklmnop').status_code,400)
        self.assertEqual(self.post(self.client,'/api/chat/2',body='ok',nonce='bad').status_code,400)
        self.assertEqual(self.post(self.client,'/api/chat/2',body='ok',nonce='abcdefghijklmnop').status_code,201)
        self.assertEqual(self.post(self.client,'/api/chat/2',body='quick',nonce='qrstuvwxyz123456').status_code,429)
        self.assertEqual(self.post(self.stranger,'/api/chat/2',body='intrusion',nonce='abcdefghijklmnop').status_code,403)
        self.assertEqual(self.client.get('/api/chat/2?after=9999999999999999999999').status_code,400)
    def test_presence_private_and_expires(self):
        self.setup_members();self.accept()
        self.post(self.peer,'/api/presence',peer='1',typing='yes')
        data=self.client.get('/api/chat/2').json;self.assertTrue(data['online']);self.assertTrue(data['typing'])
        with patch('social.time.time',return_value=time.time()+7):
            self.assertFalse(self.client.get('/api/chat/2').json['typing'])
        with patch('social.time.time',return_value=time.time()+61):
            self.assertFalse(self.client.get('/api/chat/2').json['online'])
        self.assertEqual(self.post(self.stranger,'/api/presence',peer='2',typing='yes').status_code,403)
        self.post(self.peer,'/logout')
        self.assertFalse(self.client.get('/api/chat/2').json['online'])
    def test_privacy_revoke_deletion_export_and_request_gate(self):
        self.setup_members()
        self.assertEqual(self.post(self.client,'/friends/4/request').status_code,404)
        self.assertEqual(self.post(self.client,'/friends/1/request').status_code,403)
        self.accept();self.post(self.client,'/api/chat/2',body='Stored',nonce='abcdefghijklmnop')
        exported=self.client.get('/export').json
        self.assertEqual(len(exported['sent_messages']),1);self.assertEqual(len(exported['contacts']),1)
        self.post(self.peer,'/visibility')
        self.assertEqual(self.client.get('/api/chat/2').status_code,404)
        self.assertNotIn(b'friend</strong>',self.client.get('/app').data)
        self.post(self.peer,'/disconnect',confirm='delete')
        db=connection(self.app)
        self.assertEqual(db.execute('SELECT count(*) FROM friendships').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT count(*) FROM messages').fetchone()[0],0);db.close()
    def test_decline_and_search_escape(self):
        self.setup_members();self.post(self.client,'/friends/2/request')
        self.post(self.peer,'/friends/1/decline')
        self.assertEqual(self.client.get('/api/chat/2').status_code,403)
        result=self.client.get('/api/friends?q=BGL-2').json['html'];self.assertIn('friend',result)
        self.assertNotIn('private-person',self.client.get('/api/friends?q=private').json['html'])
        self.assertNotIn('friend</strong>',self.client.get('/api/friends?q=%25').json['html'])
        self.app.config['MATCHING_APPROVED']=False
        self.assertEqual(self.post(self.client,'/friends/2/request').status_code,403)
        self.assertNotIn('friend</strong>',self.client.get('/api/friends?q=friend').json['html'])
    def test_live_requests_acceptance_and_widget_without_navigation(self):
        self.setup_members()
        self.client.get('/')
        with self.client.session_transaction() as session:csrf=session['csrf']
        sent=self.client.post('/friends/2/request',data={'csrf':csrf},headers={'Accept':'application/json'})
        self.assertEqual(sent.status_code,200);self.assertTrue(sent.json['ok'])
        incoming=self.peer.get('/api/friends?peer=1').json
        self.assertEqual(incoming['pending_count'],1);self.assertIn('Accept',incoming['contacts_html']);self.assertIn('Accept',incoming['chat_action_html'])
        self.assertFalse(incoming['chat_enabled'])
        self.assertEqual(self.peer.get('/api/chat/1/widget').status_code,403)
        with self.peer.session_transaction() as session:peer_csrf=session['csrf']
        accepted=self.peer.post('/friends/1/accept',data={'csrf':peer_csrf},headers={'Accept':'application/json'})
        self.assertEqual(accepted.status_code,200)
        contacts=self.client.get('/api/friends?peer=2')
        self.assertEqual(self.client.get('/api/friends?peer=9999999999999999999999').status_code,400)
        self.assertTrue(contacts.json['chat_enabled']);self.assertEqual(contacts.json['pending_count'],0)
        self.assertIn('friend',contacts.json['contacts_html'])
        widget=self.client.get('/api/chat/2/widget')
        self.assertEqual(widget.status_code,200);self.assertIn('data-chat data-endpoint',widget.json['html'])
        self.assertEqual(widget.headers['Cache-Control'],'no-store')
        self.assertEqual(self.stranger.get('/api/chat/2/widget').status_code,403)
        self.assertEqual(self.client.post('/friends/3/request',headers={'Accept':'application/json'}).status_code,400)
        self.post(self.peer,'/visibility')
        self.assertFalse(self.client.get('/api/friends?peer=2').json['chat_enabled'])
        self.assertEqual(self.client.get('/api/chat/2/widget').status_code,404)
    def test_discovery_with_empty_query_and_expired_imports(self):
        self.setup_members()
        db=connection(self.app);db.execute('UPDATE snapshots SET fetched_at=?',(time.time()-7*3600,));db.commit();db.close()
        page=self.client.get('/api/friends').json['html']
        self.assertIn('friend</strong>',page);self.assertIn('stranger</strong>',page)
        self.assertNotIn('private-person',page)
        self.assertEqual(self.post(self.client,'/friends/2/request').status_code,302)
        self.post(self.peer,'/friends/1/accept')
        self.assertIn('Sync required',self.client.get('/api/friends?q=BGL-2').json['html'])
        self.assertNotEqual(self.client.get('/compare/2').status_code,200)
        self.assertEqual(self.client.get('/api/chat/2').status_code,200)
    def test_comparison_ownership_plain_labels_and_zero_details(self):
        self.setup_members()
        db=connection(self.app)
        record={'id':9001,'title':'Own pressing','artists':[{'id':1,'name':'Shared artist'}],'genres':['Jazz']}
        peer_record=dict(record,id=9002,title='Other pressing')
        for uid,item in [(1,record),(2,peer_record)]:
            db.execute('UPDATE snapshots SET data=? WHERE user_id=?',(json.dumps({'collection':[item],'wantlist':[]}),uid))
        db.commit();db.close()
        page=self.client.get('/compare/2').data
        self.assertIn(b'Your collection',page);self.assertIn(b'Their collection',page)
        self.assertNotIn(b'COLLECTION A',page);self.assertNotIn(b'SIDE A',page);self.assertNotIn(b'>BLACKGOLD</text>',page)
        self.assertIn(b'No identical releases',page);self.assertIn(b'1 shared artists',page);self.assertIn(b'100.0%',page)
        self.assertIn(b'<details class="zero-link-details" data-link-reveal>',page)
        self.assertIn(b'Show details anyway',page);self.assertIn(b'Own pressing',page)
        self.assertNotIn(b'compare-a-surface"><stop offset="0"',page)
        # Empty data must never be described as unrelated music tastes.
        db=connection(self.app);db.execute('UPDATE snapshots SET data=? WHERE user_id=1',(json.dumps({'collection':[],'wantlist':[]}),));db.commit();db.close()
        self.assertIn(b'Not enough records yet',self.client.get('/compare/2').data)
    def test_normal_comparison_keeps_visible_detail_sections(self):
        self.setup_members()
        page=self.client.get('/compare/2').data
        self.assertNotIn(b'zero-link-details',page)
        self.assertIn(b'id="collection-details"',page)
