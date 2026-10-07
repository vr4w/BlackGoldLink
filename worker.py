"""Single persistent import worker; run separately from the web process."""
import json
import time
from app import create_app, connection, client, decrypt, TTL
from discogs import DiscogsError


def run_once(app):
    db=connection(app)
    try:
        now=time.time()
        db.execute('DELETE FROM snapshots WHERE fetched_at<?',(now-TTL,))
        db.execute('DELETE FROM music_cache WHERE expires<=?',(now,))
        db.execute("UPDATE jobs SET state='failed',error='Import nach Neustart abgebrochen. Bitte erneut starten.',finished=? WHERE state='running' AND started<?",(now,now-180))
        db.execute('DELETE FROM jobs WHERE finished<?',(now-7*86400,))
        db.execute('BEGIN IMMEDIATE') if not db.in_transaction else None
        job=db.execute("SELECT j.*,u.credentials,u.username FROM jobs j JOIN users u ON u.id=j.user_id WHERE j.state='queued' ORDER BY j.id LIMIT 1").fetchone()
        if not job:
            db.commit(); return False
        db.execute("UPDATE jobs SET state='running',started=?,progress='Verbindung wird geprüft' WHERE id=?",(now,job['id']))
        db.commit()
        started=time.time()
        def progress(kind,page,total):
            db.execute('UPDATE jobs SET progress=?,started=? WHERE id=? AND state=\'running\'',(f'{kind}: Seite {page} von {total}',time.time(),job['id']))
            db.commit()
            if not db.execute('SELECT id FROM users WHERE id=?',(job['user_id'],)).fetchone():
                raise DiscogsError('Account wurde entfernt.')
        try:
            api=client(app,decrypt(app,job['credentials']))
            collection=api.import_list(job['username'],'collection',lambda page,total:progress('Collection',page,total))
            wantlist=api.import_list(job['username'],'wantlist',lambda page,total:progress('Wantlist',page,total))
            data={'collection':collection,'wantlist':wantlist}
            # A single transaction publishes both lists. A partial import never replaces the old snapshot.
            if db.execute('SELECT id FROM users WHERE id=?',(job['user_id'],)).fetchone():
                db.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?)',(job['user_id'],json.dumps(data),started))
                db.execute("UPDATE jobs SET state='complete',progress='Collection und Wantlist importiert',finished=? WHERE id=?",(time.time(),job['id']))
                db.commit()
        except Exception as error:
            db.rollback()
            message=str(error) if isinstance(error,DiscogsError) else 'Import konnte nicht abgeschlossen werden. Bitte erneut versuchen.'
            db.execute("UPDATE jobs SET state='failed',error=?,finished=? WHERE id=?",(message,time.time(),job['id'])); db.commit()
        return True
    finally:
        db.close()


if __name__=='__main__':
    app=create_app()
    while True:
        if not run_once(app):
            time.sleep(2)
