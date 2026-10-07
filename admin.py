"""Small owner-only account controls. Admin identities come from server configuration."""
import functools
import time
from datetime import datetime, timezone
from flask import abort, flash, g, jsonify, redirect, render_template, request, url_for
from i18n import translate as t

ADMIN_SCHEMA='''
CREATE TABLE IF NOT EXISTS account_moderation(
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 suspended_at REAL NOT NULL, actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS admin_actions(
 id INTEGER PRIMARY KEY, actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
 target_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 action TEXT NOT NULL CHECK(action IN ('signout','suspend','restore')), created REAL NOT NULL);
'''


def configured_ids(value):
    result=set()
    for part in str(value or '').split(','):
        part=part.strip()
        if not part:continue
        if not part.isascii() or not part.isdigit() or not 0<int(part)<2**63:
            raise RuntimeError('ADMIN_DISCOGS_IDS must contain positive numeric Discogs IDs.')
        result.add(int(part))
    return frozenset(result)


def is_admin(app,user):
    return bool(user and user['discogs_id'] in app.extensions['admin_ids'])


def suspended(db,uid):
    return bool(db.execute('SELECT 1 FROM account_moderation WHERE user_id=?',(uid,)).fetchone())


def register_admin(app):
    def admin_required(fn):
        @functools.wraps(fn)
        def wrapped(*args,**kwargs):
            # A hidden link is convenience, not authorisation.
            if not is_admin(app,g.user):abort(404)
            return fn(*args,**kwargs)
        return wrapped

    @app.template_filter('admin_date')
    def date(value):
        return datetime.fromtimestamp(value,timezone.utc).strftime('%d %b %Y · %H:%M UTC') if value else '—'

    @app.get('/admin')
    @admin_required
    def admin_panel():
        query=request.args.get('q','').strip()[:80]
        escaped=query.replace('!','!!').replace('%','!%').replace('_','!_')
        id_text=query.lower().removeprefix('bgl-').removeprefix('#')
        uid=int(id_text) if id_text.isascii() and id_text.isdigit() and len(id_text)<10 else -1
        page=max(1,min(request.args.get('page',1,type=int),100000))
        where="(?='' OR u.id=? OR u.username LIKE ? ESCAPE '!' OR u.display_name LIKE ? ESCAPE '!' OR u.handle LIKE ? ESCAPE '!')"
        params=(query,uid,'%'+escaped+'%','%'+escaped+'%','%'+escaped+'%')
        total=g.db.execute('SELECT count(*) FROM users').fetchone()[0]
        found=g.db.execute('SELECT count(*) FROM users u WHERE '+where,params).fetchone()[0]
        page=min(page,max(1,(found+24)//25));now=time.time()
        rows=list(g.db.execute('''SELECT u.id,u.discogs_id,u.username,u.display_name,u.handle,u.visible,
          m.suspended_at,coalesce(s.fetched_at,(SELECT finished FROM jobs WHERE user_id=u.id AND state='complete' ORDER BY id DESC LIMIT 1)) AS fetched_at,
          min(u.consent_at,coalesce((SELECT min(created) FROM jobs WHERE user_id=u.id),u.consent_at)) AS first_recorded,
          (SELECT count(*) FROM sessions WHERE user_id=u.id AND expires>?) AS sessions,
          (SELECT state FROM jobs WHERE user_id=u.id ORDER BY id DESC LIMIT 1) AS import_state
          FROM users u LEFT JOIN account_moderation m ON m.user_id=u.id LEFT JOIN snapshots s ON s.user_id=u.id
          WHERE '''+where+' ORDER BY u.id DESC LIMIT 25 OFFSET ?', (now,*params,(page-1)*25)))
        online=g.db.execute('SELECT count(*) FROM users u JOIN presence p ON p.user_id=u.id WHERE p.active_at>? AND NOT EXISTS(SELECT 1 FROM account_moderation m WHERE m.user_id=u.id)',(now-60,)).fetchone()[0]
        signed_in=g.db.execute('SELECT count(DISTINCT user_id) FROM sessions WHERE expires>?',(now,)).fetchone()[0]
        blocked=g.db.execute('SELECT count(*) FROM account_moderation').fetchone()[0]
        actions=list(g.db.execute('''SELECT a.action,a.created,u.username,actor.username AS actor
          FROM admin_actions a JOIN users u ON u.id=a.target_id LEFT JOIN users actor ON actor.id=a.actor_id
          ORDER BY a.id DESC LIMIT 12'''))
        data=dict(participants=rows,query=query,page=page,found=found,total=total,online=online,
            signed_in=signed_in,blocked=blocked,actions=actions,admin_ids=app.extensions['admin_ids'])
        if request.accept_mimetypes.best=='application/json':
            return jsonify(html=render_template('components/admin_content.html',**data),page=page)
        return render_template('admin.html',**data)

    @app.route('/admin/users/<int:uid>/<action>',methods=['GET','POST'])
    @admin_required
    def admin_account(uid,action):
        if not 0<uid<2**63 or action not in ('signout','suspend','restore'):abort(404)
        if request.method=='POST':g.db.execute('BEGIN IMMEDIATE')
        target=g.db.execute('SELECT id,discogs_id,username,display_name FROM users WHERE id=?',(uid,)).fetchone()
        if not target:abort(404)
        # Protect every configured owner, including the currently signed-in owner.
        if is_admin(app,target):abort(403)
        if request.method=='POST':
            if request.form.get('confirm')!='yes':abort(400,t('Please confirm this account action.'))
            now=time.time()
            if action=='restore':
                g.db.execute('DELETE FROM account_moderation WHERE user_id=?',(uid,))
            else:
                g.db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
                g.db.execute('DELETE FROM presence WHERE user_id=?',(uid,))
                if action=='suspend':
                    g.db.execute('INSERT OR IGNORE INTO account_moderation VALUES(?,?,?)',(uid,now,g.user['id']))
                    g.db.execute('UPDATE users SET visible=0 WHERE id=?',(uid,))
                    g.db.execute("UPDATE jobs SET state='failed',error='Account suspended.',finished=? WHERE user_id=? AND state='queued'",(now,uid))
            g.db.execute('INSERT INTO admin_actions(actor_id,target_id,action,created) VALUES(?,?,?,?)',(g.user['id'],uid,action,now))
            g.db.commit();flash(t('Account action saved.'))
            return redirect(url_for('admin_panel'))
        return render_template('admin_account.html',target=target,action=action)
