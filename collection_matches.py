"""Compare the visiting collector with every available member, without friend gates."""
import json
import time

from discovery import collection_discoveries
from matching import compare


def refresh_imports(db, ttl, now=None):
    """Refresh expired participating collections through the existing serial worker.

    Do not import paused/suspended accounts, duplicate active work or continually
    retry a failed connection. The five-minute limit also respects manual syncs.
    """
    now = time.time() if now is None else now
    db.execute("""INSERT OR IGNORE INTO jobs(user_id,state,created)
      SELECT u.id,'queued',? FROM users u LEFT JOIN snapshots s ON s.user_id=u.id
      WHERE u.visible=1 AND (s.user_id IS NULL OR s.fetched_at<=?)
      AND NOT EXISTS(SELECT 1 FROM account_moderation m WHERE m.user_id=u.id)
      AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.user_id=u.id AND j.state IN ('queued','running'))
      AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.user_id=u.id AND j.created>?)
      AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.user_id=u.id AND j.state='failed' AND j.created>?)
      ORDER BY u.id""", (now, now-ttl, now-300, now-3600))


def ranked_collections(db, own_id, own_data, ttl, now=None):
    now = time.time() if now is None else now
    matches = []
    if not own_data or not own_data['collection']:
        return matches
    for row in db.execute("""SELECT u.id,u.username,u.display_name,s.data
      FROM users u JOIN snapshots s ON s.user_id=u.id
      WHERE u.id!=? AND u.visible=1 AND s.fetched_at>?
      AND NOT EXISTS(SELECT 1 FROM account_moderation m WHERE m.user_id=u.id)""", (own_id, now-ttl)):
        peer_data = json.loads(row['data'])
        if not peer_data['collection']:
            continue
        result = compare(own_data, peer_data)
        discoveries = collection_discoveries(own_data['collection'], peer_data['collection'])
        matches.append(dict(id=row['id'], username=row['display_name'] or row['username'],
            result=result, discovery_count=len(discoveries)))
    matches.sort(key=lambda match: (-match['result']['score'], -match['result']['artist_score'],
        -match['result']['genre_score'], match['username'].casefold()))
    return matches


def pending_imports(db):
    return db.execute("""SELECT count(*) FROM jobs j JOIN users u ON u.id=j.user_id
      WHERE j.state IN ('queued','running') AND u.visible=1
      AND NOT EXISTS(SELECT 1 FROM account_moderation m WHERE m.user_id=u.id)""").fetchone()[0]
