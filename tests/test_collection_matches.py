import json
import time
import unittest

from app import TTL, connection, encrypt
from collection_matches import refresh_imports
import test_discovery
import test_flow
from worker import run_once


class AutomaticCollections(unittest.TestCase):
    setUp, tearDown = test_flow.Flow.setUp, test_flow.Flow.tearDown
    csrf, login = test_flow.Flow.csrf, test_flow.Flow.login
    setup_collections = test_discovery.DiscoveryPages.setup_collections

    def add_member(self, db, uid, visible=1):
        db.execute('INSERT INTO users(id,discogs_id,username,credentials,consent_at,visible) VALUES(?,?,?,?,?,?)',
            (uid, 1000+uid, f'Shelf{uid}', encrypt(self.app, {}), time.time(), visible))

    def test_all_imported_members_without_friendships_are_ranked_and_click_starts_animation(self):
        record = test_discovery.record
        self.setup_collections([record(1)], [(uid, f'Shelf{uid}', [record(1), record(uid)]) for uid in range(2, 10)])
        db = connection(self.app)
        self.assertEqual(db.execute('SELECT count(*) FROM friendships').fetchone()[0], 0)
        db.close()
        page = self.client.get('/app').get_data(as_text=True)
        self.assertIn('8 collections compared', page)
        for uid in range(2, 10):
            self.assertIn(f'href="/compare/{uid}?start=1"', page)
        self.assertIn('Your closest collection', page)
        self.assertIn('data-endpoint="/api/collection-matches"', page)
        self.assertIn('data-autostart="true"', self.client.get('/compare/2?start=1').get_data(as_text=True))
        self.assertIn('data-autostart="false"', self.client.get('/compare/2').get_data(as_text=True))

    def test_expired_peer_refreshes_without_peer_login_and_appears_in_live_fragment(self):
        record = test_discovery.record
        self.setup_collections([record(1)], [(2, 'RefreshingShelf', [record(2)])])
        db = connection(self.app)
        db.execute('UPDATE snapshots SET fetched_at=? WHERE user_id=2', (time.time()-TTL-1,))
        db.commit(); db.close()
        initial = self.client.get('/api/collection-matches').json
        self.assertNotIn('<strong>RefreshingShelf</strong>', initial['html'])
        self.assertEqual(initial['refreshing'], 1)
        self.assertIn('Matches appear here automatically', initial['html'])

        class RefreshDiscogs(test_flow.FakeDiscogs):
            def import_list(self, username, kind, progress):
                progress(1, 1)
                return [record(1), record(2)] if kind=='collection' else []

        self.app.config['DISCOGS_FACTORY'] = RefreshDiscogs
        self.assertTrue(run_once(self.app))
        response = self.client.get('/api/collection-matches')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.json['refreshing'], 0)
        self.assertIn('<strong>RefreshingShelf</strong>', response.json['html'])
        self.assertIn('<b>70.7<small>%</small></b>', response.json['html'])
        db = connection(self.app)
        self.assertEqual(db.execute('SELECT count(*) FROM sessions WHERE user_id=2').fetchone()[0], 0)
        db.close()

    def test_auto_refresh_skips_fresh_paused_suspended_active_and_recent_failed_members(self):
        self.login(); run_once(self.app)
        db = connection(self.app); now = time.time()
        for uid in range(2, 9): self.add_member(db, uid, visible=0 if uid==3 else 1)
        db.execute('INSERT INTO account_moderation VALUES(4,?,1)', (now,))
        db.execute("INSERT INTO jobs(user_id,state,created) VALUES(5,'queued',?)", (now-1000,))
        db.execute("INSERT INTO jobs(user_id,state,created) VALUES(6,'failed',?)", (now-1800,))
        db.execute("INSERT INTO jobs(user_id,state,created) VALUES(7,'complete',?)", (now-100,))
        db.execute("INSERT INTO jobs(user_id,state,created) VALUES(8,'failed',?)", (now-3601,))
        refresh_imports(db, TTL, now)
        refresh_imports(db, TTL, now)
        self.assertEqual([row[0] for row in db.execute("SELECT user_id FROM jobs WHERE state='queued' ORDER BY user_id")], [2, 5, 8])
        db.rollback(); db.close()

    def test_expired_own_collection_queues_once_on_dashboard(self):
        self.login(); run_once(self.app); self.app.config['MATCHING_APPROVED'] = True
        db = connection(self.app)
        db.execute('UPDATE snapshots SET fetched_at=?', (time.time()-TTL-1,))
        db.execute('UPDATE jobs SET created=?', (time.time()-TTL-1,))
        db.commit(); db.close()
        page = self.client.get('/app').get_data(as_text=True)
        self.assertIn('data-poll="/api/status"', page)
        self.client.get('/api/collection-matches')
        db = connection(self.app)
        self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE state='queued'").fetchone()[0], 1)
        db.close()

    def test_hidden_suspended_and_empty_collections_do_not_become_matches(self):
        record = test_discovery.record
        self.setup_collections([record(1)], [(2, 'PausedShelf', [record(1)]), (3, 'SuspendedShelf', [record(1)]), (4, 'EmptyShelf', [])])
        db = connection(self.app)
        db.execute('UPDATE users SET visible=0 WHERE id=2')
        db.execute('INSERT INTO account_moderation VALUES(3,?,1)', (time.time(),))
        db.commit(); db.close()
        page = self.client.get('/api/collection-matches').json['html']
        for name in ('PausedShelf', 'SuspendedShelf', 'EmptyShelf'): self.assertNotIn(name, page)
        self.assertNotIn('Your closest collection', page)

    def test_guest_and_paused_or_disabled_comparisons_cannot_poll_or_queue(self):
        self.assertEqual(self.client.get('/api/collection-matches').status_code, 302)
        self.login(); run_once(self.app)
        self.assertEqual(self.client.get('/api/collection-matches').status_code, 403)
        self.app.config['MATCHING_APPROVED'] = True
        db = connection(self.app)
        db.execute('UPDATE users SET visible=0')
        self.add_member(db, 2)
        db.commit(); db.close()
        self.assertEqual(self.client.get('/api/collection-matches').status_code, 403)
        self.client.get('/app')
        db = connection(self.app)
        self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE state='queued'").fetchone()[0], 0)
        db.close()

    def test_zero_percent_is_not_presented_as_a_high_match(self):
        self.setup_collections([test_discovery.record(1)], [(2, 'DistantShelf', [test_discovery.record(2)])])
        page = self.client.get('/app').get_data(as_text=True)
        self.assertIn('0.0 %', page)
        self.assertNotIn('Your closest collection', page)
        self.assertIn('No identical releases yet', page)
