import copy
import json
import time
import unittest

from app import connection, encrypt
from discovery import collection_discoveries
from matching import compare
import test_flow
from worker import run_once


def record(uid, artist=1, master=0, medium='Vinyl', genres=('Jazz',), styles=()):
    return dict(id=uid, title=f'Album {uid}', master_id=master, year=2000,
        artists=[dict(id=artist, name=f'Artist {artist}')], genres=list(genres),
        styles=list(styles), formats=[dict(name=medium)])


class Discoveries(unittest.TestCase):
    def test_direction_and_independence_from_wantlist(self):
        own, peer = [record(1)], [record(1), record(2)]
        before = copy.deepcopy((own, peer))
        self.assertEqual([item['release']['id'] for item in collection_discoveries(own, peer)], [2])
        self.assertEqual(collection_discoveries(peer, own), [])
        self.assertEqual((own, peer), before)
        # A useful collection gap exists despite zero wanted/trade hits.
        result = compare(dict(collection=own, wantlist=[]), dict(collection=peer, wantlist=[]))
        self.assertFalse(result['for_a'] or result['for_b'] or result['trade_a'] or result['trade_b'])
        self.assertEqual(result['score'], 70.7)

    def test_known_album_pressings_are_excluded_and_deduplicated(self):
        own = [record(1, master=11)]
        peer = [record(2, master=11), record(3, master=22, medium='CD'),
                record(4, master=22), record(4, master=22)]
        self.assertEqual([item['release']['id'] for item in collection_discoveries(own, peer)], [4])

    def test_unknown_masters_are_not_guessed_from_titles(self):
        own = [record(1)]
        peer = [dict(record(2), title='Album 1'), dict(record(3), title='Album 1')]
        self.assertEqual(len(collection_discoveries(own, peer)), 2)

    def test_prioritizes_vinyl_and_explains_familiar_artist_and_style(self):
        own = [record(1, styles=('Soul-Jazz',))]
        peer = [record(2, artist=9, genres=('Rock',)), record(3, artist=8, styles=('Soul-Jazz',)),
                record(4), record(5, medium='CD')]
        result = collection_discoveries(own, peer)
        self.assertEqual([item['release']['id'] for item in result], [4, 3, 2, 5])
        self.assertEqual(result[0]['shared_artists'], ['Artist 1'])
        self.assertEqual(result[1]['shared_styles'], ['Soul-Jazz'])
        self.assertEqual(result[2]['shared_genres'], [])

    def test_empty_collection_does_not_invent_personal_discoveries(self):
        self.assertEqual(collection_discoveries([], [record(1)]), [])
        self.assertEqual(collection_discoveries([record(1)], []), [])


class DiscoveryPages(unittest.TestCase):
    setUp, tearDown = test_flow.Flow.setUp, test_flow.Flow.tearDown
    csrf, login = test_flow.Flow.csrf, test_flow.Flow.login

    def setup_collections(self, own, peers):
        self.login()
        run_once(self.app)
        self.app.config['MATCHING_APPROVED'] = True
        db = connection(self.app)
        db.execute('UPDATE snapshots SET data=? WHERE user_id=1', (json.dumps(dict(collection=own, wantlist=[])),))
        for uid, name, collection in peers:
            db.execute('INSERT INTO users(id,discogs_id,username,credentials,consent_at,visible) VALUES(?,?,?,?,?,1)',
                (uid, 100+uid, name, encrypt(self.app, {}), time.time()))
            db.execute('INSERT INTO snapshots VALUES(?,?,?)', (uid, json.dumps(dict(collection=collection, wantlist=[])), time.time()))
        db.commit()
        db.close()

    def test_gap_is_primary_even_without_any_wantlist(self):
        self.setup_collections([record(1)], [(2, 'SimilarShelf', [record(1), record(2)])])
        page = self.client.get('/compare/2').get_data(as_text=True)
        self.assertIn('1 record to discover', page)
        self.assertIn('No wantlist needed.', page)
        self.assertIn('https://www.discogs.com/release/2" target="_blank"', page)
        self.assertLess(page.index('class="collection-discoveries"'), page.index('class="comparison-bonus"'))
        self.assertIn('<details class="comparison-bonus"', page)
        self.assertNotIn('<details class="comparison-bonus" open', page)
        self.assertIn('Artist on your shelf: Artist 1', page)

    def test_zero_release_overlap_does_not_hide_discoveries(self):
        self.setup_collections([record(1)], [(2, 'OtherShelf', [record(2)])])
        page = self.client.get('/compare/2').get_data(as_text=True)
        self.assertIn('1 record to discover', page)
        self.assertLess(page.index('class="collection-discoveries"'), page.index('class="zero-link-details"'))
        self.assertIn('No identical releases.', page)

    def test_dashboard_ranks_collection_similarity_before_gap_or_want_counts(self):
        self.setup_collections([record(1), record(2)], [
            (2, 'DistantShelf', [record(3), record(4), record(5)]),
            (3, 'CloseShelf', [record(1), record(2), record(6)])])
        page = self.client.get('/app').get_data(as_text=True)
        self.assertLess(page.index('<strong>CloseShelf</strong>'), page.index('<strong>DistantShelf</strong>'))
        self.assertLess(page.index('Similar collections'), page.index('class="collection-shelf"'))
        self.assertIn('2 shared releases · 1 record to discover', page)
        self.assertIn('81.6 %', page)

    def test_landing_and_german_show_collection_discovery_as_core(self):
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('New to your shelf', page)
        self.assertNotIn('YOU HAVE · THEY WANT', page)
        response = self.client.post('/language', data={'csrf': self.csrf(), 'language': 'de', 'next': '/'})
        self.assertEqual(response.status_code, 302)
        page = self.client.get('/demo').get_data(as_text=True)
        self.assertIn('Noch nicht in deinem Regal', page)
        self.assertIn('Keine Wantlist nötig.', page)
        self.assertIn('Extra: Wantlist-Treffer &amp; mögliche Tauschtreffer', page)

