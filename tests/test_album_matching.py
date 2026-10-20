import copy
import json
import time
import unittest

from app import connection
from discovery import collection_discoveries
from matching import compare
from score_comments import comments_for_score, conversation_for_score, online_for_score
import test_discovery
import test_flow


def collection(*records):
    return {'collection':list(records),'wantlist':[]}


class AlbumIdentity(unittest.TestCase):
    def test_different_pressings_are_one_album_with_version_details(self):
        first=test_discovery.record(101,master=42)
        reissue=dict(first,id=202,year=2024,formats=[{'name':'Vinyl','descriptions':['LP','Reissue','180g']}])
        a,b=collection(first),collection(reissue)
        result=compare(a,b)
        self.assertEqual(result['score'],100)
        self.assertEqual(result['component_scores']['releases'],0)
        self.assertEqual(result['algorithm_version'],'album-cosine-v2')
        self.assertEqual(len(result['album_common']),1)
        self.assertEqual(result['version_pairs'][0]['a'][0]['id'],101)
        self.assertEqual(result['version_pairs'][0]['b'][0]['formats'][0]['descriptions'],['LP','Reissue','180g'])
        self.assertEqual(collection_discoveries(a['collection'],b['collection']),[])

    def test_multiple_pressings_and_duplicate_copies_do_not_inflate_score(self):
        record=test_discovery.record
        a=collection(record(1,master=42),record(1,master=42),record(2,master=42),record(3,master=77))
        b=collection(record(4,master=42))
        result=compare(a,b)
        self.assertEqual(result['album_a_size'],2)
        self.assertEqual(result['a_size'],3) # Raw release data is retained for version details.
        self.assertEqual(result['score'],70.7)
        self.assertEqual(result['album_a_coverage'],50)
        self.assertEqual(result['album_b_coverage'],100)
        self.assertEqual(compare(b,a)['score'],result['score'])

    def test_master_from_either_import_resolves_exact_release_and_other_pressings(self):
        record=test_discovery.record
        a=collection(record(1))
        b=collection(record(1,master=42),record(2,master=42))
        self.assertEqual(compare(a,b)['score'],100)
        self.assertEqual(collection_discoveries(a['collection'],b['collection']),[])

    def test_titles_are_never_used_as_identity_or_guessed_master(self):
        a=collection(test_discovery.record(1))
        b=collection(dict(test_discovery.record(2),title='Album 1'))
        before=copy.deepcopy((a,b))
        self.assertEqual(compare(a,b)['score'],0)
        self.assertEqual(len(collection_discoveries(a['collection'],b['collection'])),1)
        self.assertEqual((a,b),before)

    def test_conflicting_metadata_keeps_exact_release_identity_symmetric(self):
        record=test_discovery.record
        a=collection(record(1,master=42),record(2,master=42))
        b=collection(record(1,master=99),record(3,master=99))
        self.assertEqual(compare(a,b)['score'],compare(b,a)['score'])
        self.assertEqual(len(compare(a,b)['album_common']),1)

    def test_wantlist_and_specific_trade_versions_remain_exact(self):
        a=collection(test_discovery.record(1,master=42));a['wantlist']=[test_discovery.record(3,master=77)]
        b=collection(test_discovery.record(2,master=42),test_discovery.record(3,master=77));b['wantlist']=[]
        result=compare(a,b)
        self.assertEqual(result['for_a'],{3})
        self.assertEqual(result['score'],70.7)
        self.assertEqual(result['for_b'],set())

    def test_copy_matches_zero_low_and_high_scores_and_never_claims_online(self):
        for score in (0,12,45,80,100):
            self.assertTrue(comments_for_score(score))
            self.assertTrue(conversation_for_score(score))
            self.assertTrue(online_for_score(score))
            self.assertFalse(any('shelf' in text.lower() or 'shelves' in text.lower() for text in comments_for_score(score)))
        self.assertIn('0%',conversation_for_score(0)[0])
        self.assertNotIn('0%',conversation_for_score(None)[0])


class AlbumExperience(unittest.TestCase):
    setUp,tearDown=test_flow.Flow.setUp,test_flow.Flow.tearDown
    csrf,login=test_flow.Flow.csrf,test_flow.Flow.login
    setup_collections=test_discovery.DiscoveryPages.setup_collections

    def test_header_and_graphic_overview_remove_repeated_profile_and_match_details(self):
        record=test_discovery.record
        self.setup_collections([record(1,master=42)],[(2,'OtherCollector',[record(2,master=42)])])
        page=self.client.get('/app').get_data(as_text=True)
        header,main=page.split('<main',1)
        self.assertIn('header-profile',header)
        self.assertIn('test-user',header)
        self.assertIn('Edit profile',header)
        self.assertNotIn('YOUR COLLECTION DNA',main)
        self.assertNotIn('Edit profile',main)
        self.assertNotIn('OTHER SHELVES',main)
        self.assertNotIn('shared releases',main)
        self.assertNotIn('Similar collections',main)
        self.assertIn('Black Gold Links',main)
        self.assertIn('match-discs',main)

    def test_shared_master_result_and_pressing_specs_appear_below_integrated_chat(self):
        own=test_discovery.record(1,master=42)
        peer=dict(test_discovery.record(2,master=42),formats=[{'name':'Vinyl','descriptions':['LP','Reissue','180g']}])
        self.setup_collections([own],[(2,'OtherCollector',[peer])])
        page=self.client.get('/compare/2').get_data(as_text=True)
        self.assertIn('data-target="100.0"',page)
        self.assertNotIn('COLLECTION COMPARISON',page)
        self.assertNotIn('<h1 class="medium">BLACKGOLD LINK',page)
        self.assertNotIn('zero-link-details',page)
        self.assertIn('data-autostart="true"',page)
        self.assertIn('inline-chat',page)
        self.assertIn('Say hello with a friend request',page)
        self.assertLess(page.index('comparison-conversation'),page.index('pressing-comparison'))
        self.assertIn('Same albums. Different pressings.',page)
        self.assertIn('180g',page)
        self.assertIn('https://www.discogs.com/release/2',page)

    def test_compact_pressing_pairs_have_inline_artist_and_one_owner_heading(self):
        record=test_discovery.record
        self.setup_collections([record(1,artist=12,master=42),record(3,artist=13,master=43)],[(2,'OtherCollector',[record(2,artist=12,master=42),record(4,artist=13,master=43)])])
        page=self.client.get('/compare/2').get_data(as_text=True)
        self.assertNotIn('Same album. Different versions. Still one BlackGoldLink match.',page)
        self.assertIn('<span class="pressing-artist">Artist 12</span><strong>Album 1</strong>',page)
        self.assertNotIn('pressing-album-heading',page)
        self.assertEqual(page.count('pressing-owners'),1)
        self.assertIn('pressing-own',page)
        self.assertIn('pressing-peer',page)
        self.assertIn('Data provided by Discogs. ↗',page)

    def test_open_comparison_lifetime_uses_oldest_of_both_imports(self):
        record=test_discovery.record
        self.setup_collections([record(1,master=42)],[(2,'OtherCollector',[record(2,master=42)])])
        db=connection(self.app)
        db.execute('UPDATE snapshots SET fetched_at=? WHERE user_id=2',(time.time()-6*3600+90,))
        db.commit();db.close()
        import re
        page=self.client.get('/compare/2').get_data(as_text=True)
        lifetime=int(re.search(r'data-discogs-valid-ms="(\d+)"',page).group(1))
        self.assertTrue(85000<lifetime<=90000)
        self.assertIn('/static/freshness.js',page)
        self.assertNotIn('data-discogs-valid-ms',self.client.get('/demo').get_data(as_text=True))

    def test_accepted_chat_keeps_messages_and_score_aware_online_copy(self):
        record=test_discovery.record
        self.setup_collections([record(1,master=42)],[(2,'OtherCollector',[record(2,master=42)])])
        db=connection(self.app)
        db.execute("INSERT INTO friendships VALUES(1,2,1,'accepted',?)",(time.time(),))
        db.execute('INSERT INTO presence VALUES(?,?,NULL,0)',(2,time.time()))
        db.commit();db.close()
        widget=self.client.get('/api/chat/2/widget').json['html']
        self.assertIn('inline-chat',widget)
        self.assertIn('data-online-nudges',widget)
        self.assertIn('Ask who copied whose collection',widget)
        self.assertTrue(self.client.get('/api/chat/2').json['online'])
        response=self.client.post('/api/chat/2',data={'csrf':self.csrf(),'body':'Same album, different pressing.','nonce':'album-version-test-message'})
        self.assertEqual(response.status_code,201)
        self.assertEqual(self.client.get('/api/chat/2').json['messages'][0]['body'],'Same album, different pressing.')
