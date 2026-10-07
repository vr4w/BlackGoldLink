"""Mutual contacts and private chat, using the existing SQLite and CSRF boundary."""
import re
import time
from flask import abort, g, request, jsonify, render_template, redirect, url_for
from app import TTL, snapshot

SOCIAL_SCHEMA = '''
CREATE TABLE IF NOT EXISTS friendships(
 low_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 high_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 requested_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 state TEXT NOT NULL CHECK(state IN ('pending','accepted')),
 created REAL NOT NULL, PRIMARY KEY(low_id,high_id), CHECK(low_id<high_id));
CREATE TABLE IF NOT EXISTS messages(
 id INTEGER PRIMARY KEY, low_id INTEGER NOT NULL, high_id INTEGER NOT NULL,
 sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 body TEXT NOT NULL, created REAL NOT NULL, nonce TEXT NOT NULL,
 UNIQUE(sender_id,nonce), FOREIGN KEY(low_id,high_id) REFERENCES friendships(low_id,high_id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS thread_messages ON messages(low_id,high_id,id);
CREATE INDEX IF NOT EXISTS sent_message_times ON messages(sender_id,created);
CREATE TABLE IF NOT EXISTS presence(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 active_at REAL NOT NULL, typing_peer INTEGER REFERENCES users(id) ON DELETE CASCADE, typing_at REAL NOT NULL DEFAULT 0);
'''

def pair(uid):
    return tuple(sorted((g.user['id'],uid)))

def available_peer(app,uid,fresh=False):
    if not app.config['MATCHING_APPROVED'] or not g.user['visible'] or uid==g.user['id']:
        abort(403)
    peer=g.db.execute('SELECT id,username,display_name,handle FROM users WHERE id=? AND visible=1',(uid,)).fetchone()
    if not peer:abort(404)
    if fresh and (not snapshot(g.db,uid) or not snapshot(g.db,g.user['id'])):abort(409)
    return peer

def friendship(uid):
    return g.db.execute('SELECT * FROM friendships WHERE low_id=? AND high_id=?',pair(uid)).fetchone()

def chat_peer(app,uid):
    peer=available_peer(app,uid)
    row=friendship(uid)
    if not row or row['state']!='accepted':abort(403)
    return peer

def panel_data(app):
    if not app.config['MATCHING_APPROVED'] or not g.user['visible']:
        return {'contacts':[],'incoming':[],'outgoing':[]}
    rows=g.db.execute('''SELECT u.id,u.username,u.display_name,u.handle,f.state,f.requested_by,
      EXISTS(SELECT 1 FROM snapshots s WHERE s.user_id=u.id AND s.fetched_at>?) AS ready
      FROM friendships f JOIN users u ON u.id=CASE WHEN f.low_id=? THEN f.high_id ELSE f.low_id END
      WHERE (f.low_id=? OR f.high_id=?) AND u.visible=1 ORDER BY u.username''',
      (time.time()-TTL,g.user['id'],g.user['id'],g.user['id']))
    result={'contacts':[],'incoming':[],'outgoing':[]}
    for row in rows:
        result['contacts' if row['state']=='accepted' else 'outgoing' if row['requested_by']==g.user['id'] else 'incoming'].append(dict(row))
    if not snapshot(g.db,g.user['id']):
        for member in result['contacts']:member['ready']=False
    return result

def search_members(app,query):
    """Identity discovery survives import expiry; release comparisons still require fresh data."""
    if not app.config['MATCHING_APPROVED'] or not g.user['visible']:return []
    escaped=query.replace('!','!!').replace('%','!%').replace('_','!_')
    text=query.lower().removeprefix('bgl-').removeprefix('#')
    uid=int(text) if text.isascii() and text.isdigit() and len(text)<10 else -1
    own_ready=bool(snapshot(g.db,g.user['id']))
    return list(g.db.execute("""SELECT u.id,u.username,u.display_name,u.handle,
      (? AND EXISTS(SELECT 1 FROM snapshots s WHERE s.user_id=u.id AND s.fetched_at>?)) AS ready
      FROM users u WHERE u.id!=? AND u.visible=1 AND
      (?='' OR u.id=? OR u.username LIKE ? ESCAPE '!' OR u.display_name LIKE ? ESCAPE '!' OR u.handle LIKE ? ESCAPE '!')
      ORDER BY u.username LIMIT 20""",(own_ready,time.time()-TTL,g.user['id'],query,uid,'%'+escaped+'%','%'+escaped+'%','%'+escaped+'%')))

def register_social(app,login_required):
    @app.context_processor
    def social_context():
        return {'friend_state':friendship}

    @app.get('/api/friends')
    @login_required
    def friends_panel():
        query=request.args.get('q','').strip()[:80]
        participants=search_members(app,query)
        data=panel_data(app)
        uid=request.args.get('peer',0,type=int)
        if not 0<=uid<2**63:abort(400)
        relation=friendship(uid) if uid and uid!=g.user['id'] else None
        peer_visible=g.db.execute('SELECT id,username,display_name,handle FROM users WHERE id=? AND visible=1',(uid,)).fetchone() if uid else None
        enabled=bool(app.config['MATCHING_APPROVED'] and g.user['visible'])
        response=jsonify(html=render_template('components/friend_results.html',participants=participants,query=query),
          contacts_html=render_template('components/contact_list.html',social_panel=data),
          pending_count=len(data['incoming']),enabled=enabled,
          chat_action_html=render_template('components/friend_action.html',member=peer_visible) if enabled and peer_visible else '',
          chat_enabled=bool(enabled and peer_visible and relation and relation['state']=='accepted'))
        response.headers['Cache-Control']='no-store'
        return response

    @app.post('/friends/<int:uid>/<action>')
    @login_required
    def friend_action(uid,action):
        if action not in ('request','accept','decline'):abort(404)
        peer=available_peer(app,uid)
        g.db.execute('BEGIN IMMEDIATE')
        row=friendship(uid)
        if action=='request':
            if not row:
                recent=g.db.execute('SELECT count(*) FROM friendships WHERE requested_by=? AND created>?',(g.user['id'],time.time()-3600)).fetchone()[0]
                if recent>=30:abort(429)
                g.db.execute("INSERT INTO friendships VALUES(?,?,?,'pending',?)",(*pair(uid),g.user['id'],time.time()))
        else:
            if not row or row['state']!='pending' or row['requested_by']==g.user['id']:abort(403)
            if action=='accept':g.db.execute("UPDATE friendships SET state='accepted' WHERE low_id=? AND high_id=?",pair(uid))
            else:g.db.execute("DELETE FROM friendships WHERE low_id=? AND high_id=?",pair(uid))
        g.db.commit()
        if request.accept_mimetypes.best=='application/json':
            return jsonify(ok=True,html=render_template('components/friend_action.html',member=peer))
        target=request.form.get('next','/friends')
        if not target.startswith('/') or target.startswith('//') or '\\' in target or any(ord(c)<32 for c in target):target='/friends'
        return redirect(target)

    @app.post('/api/presence')
    @login_required
    def heartbeat():
        if not app.config['MATCHING_APPROVED'] or not g.user['visible']:return jsonify(ok=True)
        now=time.time()
        uid=request.form.get('peer',0,type=int)
        typing=bool(uid and request.form.get('typing')=='yes')
        if uid:chat_peer(app,uid)
        g.db.execute('INSERT INTO presence VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET active_at=excluded.active_at,typing_peer=excluded.typing_peer,typing_at=excluded.typing_at',
                     (g.user['id'],now,uid or None,now if typing else 0))
        g.db.commit()
        return jsonify(ok=True)

    @app.get('/api/chat/<int:uid>/widget')
    @login_required
    def chat_widget(uid):
        peer=chat_peer(app,uid)
        response=jsonify(html=render_template('components/chat.html',chat_peer=peer,name_b=peer['display_name'] or peer['username']))
        response.headers['Cache-Control']='no-store'
        return response

    @app.get('/api/chat/<int:uid>')
    @login_required
    def chat_read(uid):
        chat_peer(app,uid)
        after=request.args.get('after',0,type=int);before=request.args.get('before',0,type=int)
        if not 0<=after<2**63 or not 0<=before<2**63:abort(400)
        low,high=pair(uid)
        if before:
            rows=list(g.db.execute('SELECT id,sender_id,body,created FROM messages WHERE low_id=? AND high_id=? AND id<? ORDER BY id DESC LIMIT 61',(low,high,before)))
            older=len(rows)>60;rows=rows[:60][::-1]
        elif after:
            rows=list(g.db.execute('SELECT id,sender_id,body,created FROM messages WHERE low_id=? AND high_id=? AND id>? ORDER BY id LIMIT 60',(low,high,after)))
            older=False
        else:
            rows=list(g.db.execute('SELECT id,sender_id,body,created FROM messages WHERE low_id=? AND high_id=? ORDER BY id DESC LIMIT 61',(low,high)))
            older=len(rows)>60;rows=rows[:60][::-1]
        peer=g.db.execute('SELECT * FROM presence WHERE user_id=?',(uid,)).fetchone()
        online=bool(peer and peer['active_at']>time.time()-60)
        typing=bool(online and peer['typing_peer']==g.user['id'] and peer['typing_at']>time.time()-6)
        return jsonify(messages=[dict(r) for r in rows],online=online,typing=typing,older=older)

    @app.post('/api/chat/<int:uid>')
    @login_required
    def chat_send(uid):
        chat_peer(app,uid)
        body=request.form.get('body','').strip()
        nonce=request.form.get('nonce','')
        if not body or len(body)>2000 or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',nonce):abort(400)
        low,high=pair(uid);now=time.time()
        g.db.execute('BEGIN IMMEDIATE')
        duplicate=g.db.execute('SELECT id,low_id,high_id FROM messages WHERE sender_id=? AND nonce=?',(g.user['id'],nonce)).fetchone()
        if duplicate:
            if (duplicate['low_id'],duplicate['high_id'])!=(low,high):abort(400)
            g.db.rollback();return jsonify(id=duplicate['id'])
        count=g.db.execute('SELECT count(*),max(created) FROM messages WHERE sender_id=? AND created>?',(g.user['id'],now-60)).fetchone()
        if count[0]>=30 or (count[1] and count[1]>now-1):abort(429)
        cursor=g.db.execute('INSERT INTO messages(low_id,high_id,sender_id,body,created,nonce) VALUES(?,?,?,?,?,?)',(low,high,g.user['id'],body,now,nonce))
        g.db.execute('UPDATE presence SET typing_at=0 WHERE user_id=?',(g.user['id'],))
        g.db.commit()
        return jsonify(id=cursor.lastrowid),201
