import functools
from collections import OrderedDict
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
import threading
from urllib.parse import urlencode, quote, urlsplit

from itsdangerous import URLSafeTimedSerializer, BadSignature
from cryptography.fernet import Fernet
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for, Response
from discogs import Discogs, DiscogsError
from matching import compare, dna
from collection_view import visible_releases, record_spines
from score_comments import comments_for_score
from versioning import release_version
from covers import fetch_cover, trusted_image_url
from i18n import translate as t

TTL = 6 * 3600
CONSENT_SCOPE = 'collection-comparison-v1'
SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, discogs_id INTEGER UNIQUE NOT NULL, username TEXT NOT NULL, credentials TEXT NOT NULL, consent_at REAL NOT NULL, visible INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS snapshots(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, data TEXT NOT NULL, fetched_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS pending(id TEXT PRIMARY KEY, credentials TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, state TEXT NOT NULL, progress TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', created REAL NOT NULL, started REAL, finished REAL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs(user_id) WHERE state IN ('queued','running');
CREATE TABLE IF NOT EXISTS limiter(id INTEGER PRIMARY KEY, next_at REAL NOT NULL);
INSERT OR IGNORE INTO limiter VALUES(1,0);
CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY, count INTEGER NOT NULL, started REAL NOT NULL);
'''


def create_app(overrides=None):
    app = Flask(__name__)
    app.url_map.strict_slashes = False
    app.extensions['release_version']=release_version(Path(__file__).parent)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
        APP_ENV=os.environ.get('APP_ENV','development'), BASE_URL=os.environ.get('BASE_URL','http://127.0.0.1:5013').rstrip('/'),
        DATABASE_PATH=os.environ.get('DATABASE_PATH',str(Path(__file__).parent/'instance'/'collection.db')),
        TOKEN_ENCRYPTION_KEY=os.environ.get('TOKEN_ENCRYPTION_KEY',''),
        DISCOGS_CONSUMER_KEY=os.environ.get('DISCOGS_CONSUMER_KEY',''), DISCOGS_CONSUMER_SECRET=os.environ.get('DISCOGS_CONSUMER_SECRET',''),
        WORKING_TITLE=os.environ.get('WORKING_TITLE','BlackGoldLink'),
        ADMIN_DISCOGS_IDS=os.environ.get('ADMIN_DISCOGS_IDS',''),
        MATCHING_APPROVED=os.environ.get('MATCHING_APPROVED','false') == 'true',
        INVITE_CODE=os.environ.get('INVITE_CODE',''), PUBLIC_SIGNUP=os.environ.get('PUBLIC_SIGNUP','false') == 'true',
        CONTROLLER_NAME=os.environ.get('CONTROLLER_NAME',''), CONTROLLER_ADDRESS=os.environ.get('CONTROLLER_ADDRESS',''),
        PRIVACY_CONTACT=os.environ.get('PRIVACY_CONTACT',''), HOSTING_PROVIDER=os.environ.get('HOSTING_PROVIDER',''),
        SESSION_COOKIE_NAME='collection_relay_session', SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=16384)
    app.config.update(overrides or {})
    from admin import configured_ids, is_admin, suspended, register_admin, ADMIN_SCHEMA
    app.extensions['admin_ids']=configured_ids(app.config['ADMIN_DISCOGS_IDS'])
    production = app.config['APP_ENV'] == 'production'
    if production:
        required = ['TOKEN_ENCRYPTION_KEY','DISCOGS_CONSUMER_KEY','DISCOGS_CONSUMER_SECRET','CONTROLLER_NAME','CONTROLLER_ADDRESS','PRIVACY_CONTACT','HOSTING_PROVIDER']
        missing = [x for x in required if not app.config[x]]
        if not os.environ.get('SECRET_KEY') and not (overrides or {}).get('SECRET_KEY'):
            missing.append('SECRET_KEY')
        if len(app.config['SECRET_KEY']) < 32:
            missing.append('SECRET_KEY (mindestens 32 Zeichen)')
        if missing or not app.config['BASE_URL'].startswith('https://'):
            raise RuntimeError('Produktionskonfiguration unvollständig: ' + ', '.join(missing) + '; BASE_URL muss HTTPS verwenden.')
        if not app.config['PUBLIC_SIGNUP'] and not app.config['INVITE_CODE']:
            raise RuntimeError('INVITE_CODE für die geschlossene Testphase erforderlich.')
    if production:
        # Only deploy behind the dedicated loopback-bound proxy described in DEPLOY.md.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=0, x_host=0)
    origin = urlsplit(app.config['BASE_URL'])
    if origin.path or origin.query or origin.fragment or not origin.hostname:
        raise RuntimeError('BASE_URL muss eine reine Origin ohne Unterpfad sein.')
    app.config['SESSION_COOKIE_SECURE'] = origin.scheme == 'https'
    Path(app.config['DATABASE_PATH']).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(app.config['DATABASE_PATH'])) as db:
        db.executescript(SCHEMA)
        from social import SOCIAL_SCHEMA
        db.executescript(SOCIAL_SCHEMA)
        db.executescript(ADMIN_SCHEMA)
        # Additive migration: preserve Discogs username and every existing account.
        db.execute('BEGIN IMMEDIATE')
        columns={row[1] for row in db.execute('PRAGMA table_info(users)')}
        for field in ('display_name','handle','bio'):
            if field not in columns: db.execute(f"ALTER TABLE users ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")
        db.executescript("""CREATE UNIQUE INDEX IF NOT EXISTS unique_handle ON users(handle) WHERE handle!='';
        CREATE TABLE IF NOT EXISTS music_cache(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,release_id INTEGER NOT NULL,videos TEXT NOT NULL,expires REAL NOT NULL,PRIMARY KEY(user_id,release_id));
        CREATE TABLE IF NOT EXISTS music_requests(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,requested_at REAL NOT NULL);""")
        db.commit()
    app.extensions['cover_cache'] = OrderedDict()
    app.extensions['cover_cache_lock'] = threading.RLock()
    app.extensions['cipher'] = Fernet(app.config['TOKEN_ENCRYPTION_KEY'].encode()) if app.config['TOKEN_ENCRYPTION_KEY'] else None

    @app.before_request
    def prepare():
        if request.host.split(':')[0] != origin.hostname and not app.testing:
            # Fail before opening a database, without invoking templates that require g.user.
            return 'Invalid host', 400
        g.language=request.cookies.get('bgl_language','en')
        if g.language not in ('en','de'):g.language='en'
        g.db = connection(app)
        g.db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
        g.db.execute('DELETE FROM pending WHERE created < ?', (time.time()-600,))
        g.db.execute('DELETE FROM snapshots WHERE fetched_at < ?', (time.time()-TTL,))
        g.db.execute('DELETE FROM music_cache WHERE expires<=?',(time.time(),))
        g.db.commit()
        g.user = None
        if session.get('sid'):
            g.user = g.db.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.hash=? AND s.expires>?',
                (hashlib.sha256(session['sid'].encode()).hexdigest(),time.time())).fetchone()
        if g.user and suspended(g.db,g.user['id']):
            g.db.execute('DELETE FROM sessions WHERE user_id=?',(g.user['id'],))
            g.db.execute('DELETE FROM presence WHERE user_id=?',(g.user['id'],))
            g.db.commit();g.user=None;session.clear()
        if g.user and 'music_prompt' not in session:
            session['music_prompt']=secrets.token_urlsafe(12)
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        if request.method == 'POST' and not secrets.compare_digest(request.form.get('csrf',''),session['csrf']):
            abort(400, 'Formular abgelaufen. Bitte Seite neu laden.')

    @app.teardown_request
    def close(_):
        if hasattr(g,'db'):
            g.db.close()

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'X-Frame-Options':'DENY','Content-Security-Policy':"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        # Chrome applies form-action to redirects after POST, including OAuth.
        # Allow only Discogs authorization on pages participating in this handshake.
        if request.endpoint in ('invite','connect'):
            response.headers['Content-Security-Policy']=response.headers['Content-Security-Policy'].replace("form-action 'self'", "form-action 'self' https://www.discogs.com")
        if getattr(g,'user',None) and request.endpoint in ('dashboard','profile_settings','member_profile','comparison','friend_invite','friends','admin_panel','admin_account'):
            response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self' https://www.youtube.com https://s.ytimg.com; frame-src https://www.youtube-nocookie.com https://www.youtube.com; connect-src 'self' https://www.youtube.com; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if request.endpoint == 'friend_invite':
            response.headers['Content-Security-Policy']=response.headers['Content-Security-Policy'].replace("form-action 'self'", "form-action 'self' https://www.discogs.com")
        if production:
            response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.context_processor
    def context():
        from social import panel_data
        social_panel=panel_data(app) if g.user else {}
        members=[]
        if g.user and g.user['visible'] and app.config['MATCHING_APPROVED']:
            members=list(g.db.execute('SELECT u.id,u.username,u.display_name,u.handle FROM users u JOIN snapshots s ON u.id=s.user_id WHERE u.id!=? AND u.visible=1 AND s.fetched_at>? ORDER BY u.username LIMIT 100',(g.user['id'],time.time()-TTL)))
        return dict(consent_scope=CONSENT_SCOPE,is_admin=is_admin(app,g.user),release_version=app.extensions['release_version'],social_panel=social_panel,current_year=time.localtime().tm_year,t=t,language=g.language,members=members,title=app.config['WORKING_TITLE'], user=g.user, csrf=session['csrf'], matching_approved=app.config['MATCHING_APPROVED'],
                    configured=bool(app.extensions['cipher'] and app.config['DISCOGS_CONSUMER_KEY'] and app.config['DISCOGS_CONSUMER_SECRET']),
                    base_url=app.config['BASE_URL'], config=app.config,music_prompt=session.get('music_prompt',''),
                    music_ready=bool(g.user and g.db.execute('SELECT user_id FROM snapshots WHERE user_id=? AND fetched_at>?',(g.user['id'],time.time()-TTL)).fetchone()))

    @app.get('/')
    def landing():
        from demo import profiles
        a,b=profiles()
        result=compare(a,b)
        lookup={x['id']:x for x in a['collection']+b['collection']}
        return render_template('landing.html',preview=a['collection'][:5],demo_score=result['score'],demo_common=len(result['common']),
            demo_hits=[lookup[i] for i in sorted(result['for_b'])[:3]],demo_other_hits=[lookup[i] for i in sorted(result['for_a'])[:3]])

    friend_signer = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='bgl-friend-invitation-v1')

    def friend_owner(token):
        if not token or len(token)>200: return None
        try:
            uid = friend_signer.loads(token, max_age=7*86400)
        except BadSignature:
            return None
        if type(uid) is not int: return None
        return g.db.execute('SELECT id,username,display_name,visible FROM users WHERE id=?',(uid,)).fetchone()

    @app.get('/join/<token>')
    def friend_invite(token):
        owner=friend_owner(token)
        if not owner:
            abort(404,'Einladungslink abgelaufen oder nicht mehr verfügbar. Bitte einen neuen Link anfordern.')
        if g.user and owner['id']==g.user['id']:
            return redirect(url_for('dashboard'))
        session['friend_token']=token
        if not g.user:
            # A bearer link authorizes signup, never access to another person's data.
            return render_template('join.html',friend_token=token)
        approved=app.config['MATCHING_APPROVED']
        job=g.db.execute('SELECT * FROM jobs WHERE user_id=? ORDER BY id DESC LIMIT 1',(g.user['id'],)).fetchone()
        data=snapshot(g.db,g.user['id'])
        peer_data=snapshot(g.db,owner['id']) if approved and owner['visible'] and g.user['visible'] else None
        name=(owner['display_name'] or owner['username']) if approved and owner['visible'] and g.user['visible'] else None
        return render_template('friend_invite.html',friend_token=token,peer_name=name,peer_id=owner['id'],
            own_ready=bool(data),peer_ready=bool(peer_data),peer_visible=bool(owner['visible']) if approved else False,job=job)

    @app.get('/invite')
    def invite():
        return render_template('join.html')

    @app.post('/connect')
    def connect():
        configured = app.extensions['cipher'] and app.config['DISCOGS_CONSUMER_KEY'] and app.config['DISCOGS_CONSUMER_SECRET']
        if not configured:
            flash('Die Discogs-Verbindung wird noch eingerichtet.')
            return redirect(url_for('invite'))
        if request.form.get('consent') != 'yes' or request.form.get('adult') != 'yes':
            abort(400,'Bitte Import und Volljährigkeit bestätigen.')
        friend_token=request.form.get('friend_token','')
        owner=friend_owner(friend_token) if friend_token else None
        if friend_token and not owner:
            abort(403,'Einladungslink abgelaufen oder ungültig.')
        if not app.config['PUBLIC_SIGNUP'] and not owner and not secrets.compare_digest(request.form.get('invite_code',''), app.config['INVITE_CODE']):
            abort(403,'Einladungscode erforderlich.')
        # An old browser form described a private import, not collection comparison.
        if request.form.get('consent_scope') != CONSENT_SCOPE:
            flash(t('Sign-in has changed. Please confirm import and collection comparisons.'))
            return redirect(url_for('friend_invite',token=friend_token) if owner else url_for('invite'))
        # All authentication starts share a persisted per-client throttle; IP stored only as keyed hash.
        ipkey = hashlib.sha256((app.config['SECRET_KEY'] + (request.remote_addr or '')).encode()).hexdigest()
        row = g.db.execute('SELECT * FROM attempts WHERE key=?',(ipkey,)).fetchone()
        now = time.time()
        if row and row['started'] > now-600 and row['count'] >= 10:
            abort(429,'Bitte zehn Minuten warten.')
        if not row or row['started'] < now-600:
            g.db.execute('INSERT OR REPLACE INTO attempts VALUES(?,1,?)',(ipkey,now))
        else:
            g.db.execute('UPDATE attempts SET count=count+1 WHERE key=?',(ipkey,))
        g.db.execute('DELETE FROM attempts WHERE started<?',(now-600,))
        g.db.commit()
        try:
            data = client(app).request_token(app.config['BASE_URL'] + '/oauth/callback')
            if data.get('oauth_callback_confirmed') != 'true':
                raise DiscogsError('Discogs hat die Rücksprungadresse nicht bestätigt.')
            data['bgl_consent_scope']=CONSENT_SCOPE
            pending_id = secrets.token_urlsafe(32)
            g.db.execute('INSERT INTO pending VALUES(?,?,?)',(pending_id,encrypt(app,data),now))
            g.db.commit()
            session['pending'] = pending_id
            session.pop('friend_token',None)
            if owner: session['friend_token']=friend_token
            return redirect('https://www.discogs.com/oauth/authorize?' + urlencode({'oauth_token':data['oauth_token']}))
        except DiscogsError as error:
            flash(str(error))
            return redirect(url_for('invite'))

    @app.get('/oauth/callback')
    def callback():
        pending_id = session.pop('pending',None)
        row = g.db.execute('SELECT * FROM pending WHERE id=?',(pending_id,)).fetchone()
        if not row or row['created'] < time.time()-600:
            abort(400,'Verbindung abgelaufen. Bitte erneut verbinden.')
        consumed=g.db.execute('DELETE FROM pending WHERE id=?',(pending_id,)).rowcount
        g.db.commit()
        if consumed!=1:
            abort(400,'Diese Verbindung wurde bereits verwendet.')
        token = decrypt(app,row['credentials'])
        if not secrets.compare_digest(token['oauth_token'],request.args.get('oauth_token','')) or not request.args.get('oauth_verifier'):
            abort(400,'Discogs-Verbindung abgebrochen oder ungültig.')
        if token.get('bgl_consent_scope') != CONSENT_SCOPE:
            flash(t('Sign-in has changed. Please confirm import and collection comparisons.'))
            friend_token=session.get('friend_token')
            return redirect(url_for('friend_invite',token=friend_token) if friend_owner(friend_token) else url_for('invite'))
        try:
            api = client(app,token)
            credentials = api.access_token(request.args['oauth_verifier'])
            identity = client(app,credentials).identity()
            g.db.execute('BEGIN IMMEDIATE')
            existing=g.db.execute('SELECT id FROM users WHERE discogs_id=?',(int(identity['id']),)).fetchone()
            if existing and suspended(g.db,existing['id']):
                abort(403,t('This account is suspended. Please contact the site administrator.'))
            g.db.execute('INSERT INTO users(discogs_id,username,credentials,consent_at,visible) VALUES(?,?,?,?,1) ON CONFLICT(discogs_id) DO UPDATE SET username=excluded.username, credentials=excluded.credentials, consent_at=excluded.consent_at, visible=1',
                         (int(identity['id']),identity['username'],encrypt(app,credentials),time.time()))
            uid = g.db.execute('SELECT id FROM users WHERE discogs_id=?',(identity['id'],)).fetchone()['id']
            sid = secrets.token_urlsafe(32)
            g.db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(sid.encode()).hexdigest(),uid,time.time()+7*86400))
            enqueue(g.db,uid)
            g.db.commit()
            friend_token=session.get('friend_token')
            session.clear()
            session['sid'] = sid
            if friend_owner(friend_token):
                session['friend_token']=friend_token
                return redirect(url_for('friend_invite',token=friend_token))
            return redirect(url_for('dashboard'))
        except DiscogsError as error:
            flash(str(error))
            return redirect(url_for('invite'))

    def login_required(fn):
        @functools.wraps(fn)
        def wrapped(*args,**kwargs):
            if not g.user:
                return redirect(url_for('invite'))
            return fn(*args,**kwargs)
        return wrapped

    @app.get('/app')
    @login_required
    def dashboard():
        data = snapshot(g.db,g.user['id'])
        job = g.db.execute('SELECT * FROM jobs WHERE user_id=? ORDER BY id DESC LIMIT 1',(g.user['id'],)).fetchone()
        matches=[]
        if data and app.config['MATCHING_APPROVED'] and g.user['visible']:
            for row in g.db.execute('SELECT u.id,u.username,u.display_name,s.data FROM users u JOIN snapshots s ON u.id=s.user_id WHERE u.id!=? AND u.visible=1 AND s.fetched_at>?',(g.user['id'],time.time()-TTL)):
                result=compare(data,json.loads(row['data']))
                matches.append(dict(id=row['id'],username=row['display_name'] or row['username'],result=result))
            matches.sort(key=lambda m:m['result']['score'],reverse=True)
        medium=request.args.get('medium','vinyl')
        if medium not in ('vinyl','all','other','unknown'):medium='vinyl'
        lists={key:visible_releases(data[key],medium) if data else [] for key in ('collection','wantlist')}
        unknown=sum(not release.get('formats') for key in ('collection','wantlist') for release in (data[key] if data else []))
        collection_page=max(1,request.args.get('collection_page',1,type=int))
        want_page=max(1,request.args.get('want_page',1,type=int))
        collection_page=min(collection_page,max(1,(len(lists['collection'])+23)//24))
        want_page=min(want_page,max(1,(len(lists['wantlist'])+23)//24))
        return render_template('dashboard.html',data=data,profile=dna(data['collection']) if data else None,job=job,matches=matches,
            collection_page=collection_page,want_page=want_page,medium=medium,lists=lists,unknown_formats=unknown,spines=record_spines(data['collection']) if data else [],friend_link=app.config['BASE_URL']+url_for('friend_invite',token=friend_signer.dumps(g.user['id'])),
            pending_friend=session.get('friend_token') if friend_owner(session.get('friend_token')) else None)

    @app.get('/friends')
    @login_required
    def friends():
        query=request.args.get('q','').strip()[:80]
        from social import search_members
        ready=bool(snapshot(g.db,g.user['id']))
        participants=search_members(app,query)
        return render_template('friends.html',participants=participants,query=query,own_ready=ready)

    @app.post('/sync')
    @login_required
    def sync():
        latest = g.db.execute('SELECT created FROM jobs WHERE user_id=? ORDER BY id DESC LIMIT 1',(g.user['id'],)).fetchone()
        if latest and latest['created'] > time.time()-300:
            flash('Der letzte Import wurde vor weniger als fünf Minuten gestartet.')
        else:
            enqueue(g.db,g.user['id']); g.db.commit()
            flash('Import in der Warteschlange. Die Anzeige aktualisiert sich automatisch.')
        return redirect(url_for('dashboard'))

    @app.get('/api/status')
    @login_required
    def status():
        row=g.db.execute('SELECT state,progress,error FROM jobs WHERE user_id=? ORDER BY id DESC LIMIT 1',(g.user['id'],)).fetchone()
        result=dict(row) if row else {'state':'idle'}
        for key in ('progress','error'):
            if key in result:result[key]=t(result[key])
        return jsonify(result)

    @app.post('/visibility')
    @login_required
    def visibility():
        if not app.config['MATCHING_APPROVED']:
            abort(403,'Nutzervergleiche warten auf die Klärung mit Discogs.')
        g.db.execute('UPDATE users SET visible=? WHERE id=?',(1 if request.form.get('visible')=='yes' else 0,g.user['id']))
        g.db.commit()
        token=request.form.get('friend_token','')
        if friend_owner(token): return redirect(url_for('friend_invite',token=token))
        return redirect(url_for('dashboard'))

    @app.get('/compare/<int:uid>')
    @login_required
    def comparison(uid):
        if not app.config['MATCHING_APPROVED'] or not g.user['visible']:
            abort(403)
        peer = g.db.execute('SELECT * FROM users WHERE id=? AND visible=1',(uid,)).fetchone()
        a,b=snapshot(g.db,g.user['id']),snapshot(g.db,uid)
        if not peer or not a or not b or uid==g.user['id']:
            abort(404,'Profil derzeit nicht verfügbar. Sammlungen müssen frisch synchronisiert sein.')
        return render_comparison(a,b,g.user['display_name'] or g.user['username'],peer['display_name'] or peer['username'],discogs_a=g.user['username'],discogs_b=peer['username'],chat_peer=peer)

    def render_comparison(a,b,name_a,name_b,demo=False,discogs_a=None,discogs_b=None,chat_peer=None):
        result=compare(a,b)
        lookup={x['id']:x for x in a['collection']+a['wantlist']+b['collection']+b['wantlist']}
        artist_names={str(v['id']):v['name'] for x in lookup.values() for v in x['artists']}
        sections=[('Gemeinsame Releases','common'),('Nur in deiner Collection','only_a'),('Nur in der anderen Collection','only_b'),
                  ('Deine Wantlist · andere Collection','for_a'),('Andere Wantlist · deine Collection','for_b'),
                  ('Du hast · andere Person sucht','trade_a'),('Andere Person hat · du suchst','trade_b')]
        return render_template('compare.html',a=a,b=b,name_a=name_a,name_b=name_b,result=result,lookup=lookup,artist_names=artist_names,sections=sections,demo=demo,chat_peer=chat_peer,discogs_a=discogs_a or name_a,discogs_b=discogs_b or name_b,comment_options=[t(comment) for comment in (['No identical releases. The rest is in the details.'] if not result['common'] else comments_for_score(result['score']))])

    @app.get('/demo')
    def demo():
        from demo import profiles
        a,b=profiles()
        return render_comparison(a,b,'Studio Shelf','Night Shift',demo=True)

    @app.get('/cover/<int:release_id>')
    @login_required
    def cover(release_id):
        # A thumbnail needs a fresh authorized snapshot, including on cache hits.
        rows=list(g.db.execute('SELECT s.data,s.fetched_at FROM snapshots s JOIN users u ON u.id=s.user_id WHERE s.fetched_at>? AND (s.user_id=? OR (? AND ? AND u.visible=1))',
            (time.time()-TTL,g.user['id'],int(app.config['MATCHING_APPROVED']),g.user['visible'])))
        image_url=None
        valid_until=0
        for row in rows:
            data=json.loads(row['data'])
            for release in data['collection']+data['wantlist']:
                if release['id']==release_id and trusted_image_url(release.get('thumb_url','')):
                    image_url=release['thumb_url'];valid_until=row['fetched_at']+TTL;break
            if image_url: break
        if not image_url:
            abort(404,'Cover derzeit nicht verfügbar.')
        cache=app.extensions['cover_cache']
        now=time.time()
        with app.extensions['cover_cache_lock']:
            for key in list(cache):
                if cache[key][0]<=now: del cache[key]
            cached=cache.get(image_url)
            if cached:
                cache.move_to_end(image_url)
                content,content_type=cached[1:]
        if not cached:
            try:
                content,content_type=fetch_cover(image_url,app.config['WORKING_TITLE']+'/0.1 +'+app.config['BASE_URL'])
            except Exception:
                return redirect(url_for('static',filename='cover-unavailable.svg'))
            with app.extensions['cover_cache_lock']:
                cache[image_url]=(min(valid_until,now+600),content,content_type)
                while len(cache)>24: cache.popitem(last=False)
        return Response(content,content_type=content_type)

    @app.get('/export')
    @login_required
    def export():
        data=snapshot(g.db,g.user['id'])
        response=jsonify({'username':g.user['username'],'display_name':g.user['display_name'],'handle':g.user['handle'],'bio':g.user['bio'],'consent_at':g.user['consent_at'],'visible':bool(g.user['visible']),'snapshot':data,'contacts':[dict(r) for r in g.db.execute('SELECT * FROM friendships WHERE low_id=? OR high_id=?',(g.user['id'],g.user['id']))],'sent_messages':[dict(r) for r in g.db.execute('SELECT id,low_id,high_id,body,created FROM messages WHERE sender_id=? ORDER BY id',(g.user['id'],))]})
        response.headers['Content-Disposition']='attachment; filename=collection-export.json'
        return response

    @app.post('/disconnect')
    @login_required
    def disconnect():
        if request.form.get('confirm') != 'delete':
            abort(400,'Löschung bitte bestätigen.')
        g.db.execute('DELETE FROM users WHERE id=?',(g.user['id'],))
        g.db.commit()
        with app.extensions['cover_cache_lock']: app.extensions['cover_cache'].clear()
        session.clear()
        flash('Account, Verbindung und importierte Daten wurden gelöscht. Die App zusätzlich in deinen Discogs-Einstellungen widerrufen.')
        return redirect(url_for('landing'))

    @app.post('/logout')
    @login_required
    def logout():
        g.db.execute('DELETE FROM sessions WHERE hash=?',(hashlib.sha256(session['sid'].encode()).hexdigest(),))
        g.db.execute('DELETE FROM presence WHERE user_id=?',(g.user['id'],))
        g.db.commit(); session.clear()
        return redirect(url_for('landing'))

    @app.get('/privacy')
    def privacy():
        return render_template('privacy.html')

    @app.get('/imprint')
    def imprint():
        return render_template('imprint.html')

    @app.get('/about')
    def about():
        return render_template('about.html')

    @app.post('/language')
    def change_language():
        language=request.form.get('language','en')
        if language not in ('en','de'):abort(400)
        target=request.form.get('next','/')
        if not target.startswith('/') or target.startswith('//') or '\\' in target or any(ord(c)<32 for c in target):target='/'
        response=redirect(target)
        response.set_cookie('bgl_language',language,max_age=365*86400,secure=app.config['SESSION_COOKIE_SECURE'],httponly=True,samesite='Lax')
        return response

    from features import register_features
    register_features(app,login_required)
    from social import register_social
    register_social(app,login_required)
    register_admin(app)

    @app.get('/api/version')
    def version_status():
        return jsonify(version=app.extensions['release_version'])

    @app.get('/health')
    def health():
        return jsonify(status='ok',service='collection-relay',matching_enabled=app.config['MATCHING_APPROVED'])

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(429)
    def problem(error):
        return render_template('error.html',message=error.description),error.code

    return app


def connection(app):
    db=sqlite3.connect(app.config['DATABASE_PATH'],timeout=30)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA secure_delete=ON')
    return db


def encrypt(app,data):
    return app.extensions['cipher'].encrypt(json.dumps(data).encode()).decode()


def decrypt(app,data):
    return json.loads(app.extensions['cipher'].decrypt(data.encode()))


def throttle(app):
    db=connection(app)
    try:
        db.execute('BEGIN IMMEDIATE')
        next_at=db.execute('SELECT next_at FROM limiter WHERE id=1').fetchone()['next_at']
        now=time.time(); slot=max(now,next_at)
        db.execute('UPDATE limiter SET next_at=? WHERE id=1',(slot+1.5,)); db.commit()
    finally:
        db.close()
    time.sleep(max(0,slot-now))


def cooldown(app,seconds):
    db=connection(app)
    try:
        db.execute('UPDATE limiter SET next_at=MAX(next_at,?) WHERE id=1',(time.time()+seconds,))
        db.commit()
    finally:
        db.close()


def client(app,credentials=None):
    credentials=credentials or {}
    factory=app.config.get('DISCOGS_FACTORY',Discogs)
    return factory(app.config['DISCOGS_CONSUMER_KEY'],app.config['DISCOGS_CONSUMER_SECRET'],
        app.config['WORKING_TITLE']+'/0.1 +'+app.config['BASE_URL'],lambda:throttle(app),
        credentials.get('oauth_token',''),credentials.get('oauth_token_secret',''),lambda seconds:cooldown(app,seconds))


def enqueue(db,uid):
    db.execute("INSERT OR IGNORE INTO jobs(user_id,state,created) VALUES(?,'queued',?)",(uid,time.time()))


def snapshot(db,uid):
    row=db.execute('SELECT data FROM snapshots WHERE user_id=? AND fetched_at>?',(uid,time.time()-TTL)).fetchone()
    return json.loads(row['data']) if row else None


if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=int(os.environ.get('PORT','5013')),debug=False)
