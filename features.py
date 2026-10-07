"""Additive personal profile and consent-triggered music routes."""
import json
import re
import secrets
import time
import sqlite3
from flask import g,request,render_template,redirect,url_for,flash,abort,jsonify
from app import snapshot,client,decrypt,TTL
from discogs import DiscogsError
from i18n import translate as t
from music import youtube_id

def register_features(app,login_required):
    @app.route('/profile',methods=['GET','POST'])
    @login_required
    def profile_settings():
        if request.method=='POST':
            display=request.form.get('display_name','').strip()
            handle=request.form.get('handle','').strip().lower()
            bio=request.form.get('bio','').strip()
            if len(display)>40 or len(bio)>500 or (handle and not re.fullmatch(r'[a-z0-9_]{3,30}',handle)):
                abort(400,t('Use a name up to 40 characters, a bio up to 500, and a handle of 3–30 letters, numbers or underscores.'))
            try:
                g.db.execute('UPDATE users SET display_name=?,handle=?,bio=? WHERE id=?',(display,handle,bio,g.user['id']))
                g.db.commit()
            except sqlite3.IntegrityError:
                g.db.rollback();abort(400,t('That handle is already in use.'))
            flash(t('Profile saved.'))
            return redirect(url_for('profile_settings'))
        return render_template('profile.html',owner=g.user,editable=True)

    @app.get('/profiles/<int:uid>')
    @login_required
    def member_profile(uid):
        if uid==g.user['id']:return redirect(url_for('profile_settings'))
        if not app.config['MATCHING_APPROVED'] or not g.user['visible']:abort(403)
        peer=g.db.execute('SELECT * FROM users WHERE id=? AND visible=1',(uid,)).fetchone()
        if not peer or not snapshot(g.db,uid):abort(404)
        return render_template('profile.html',owner=peer,editable=False)

    @app.post('/api/music/next')
    @login_required
    def music_next():
        if request.form.get('consent')!='yes':abort(400,t('Please confirm YouTube playback first.'))
        data=snapshot(g.db,g.user['id'])
        if not data or not data['collection']:
            return jsonify(error=t('Sync your collection before playing music.')),409
        now=time.time()
        g.db.execute('BEGIN IMMEDIATE')
        row=g.db.execute('SELECT requested_at FROM music_requests WHERE user_id=?',(g.user['id'],)).fetchone()
        if row and row['requested_at']>now-10:
            g.db.rollback()
            return jsonify(error=t('Please wait a few seconds before choosing another record.')),429
        g.db.execute('INSERT OR REPLACE INTO music_requests VALUES(?,?)',(g.user['id'],now));g.db.commit()
        # At most five release lookups per click; all use the existing shared Discogs limiter.
        choices=secrets.SystemRandom().sample(data['collection'],min(5,len(data['collection'])))
        previous=request.form.get('previous','')
        for release in choices:
            cached=g.db.execute('SELECT videos FROM music_cache WHERE user_id=? AND release_id=? AND expires>?',(g.user['id'],release['id'],now)).fetchone()
            if cached:
                videos=json.loads(cached['videos'])
            else:
                try:
                    result=client(app,decrypt(app,g.user['credentials'])).request('/releases/'+str(int(release['id'])))
                except DiscogsError as error:
                    return jsonify(error=t(str(error))),502
                videos=[]
                for video in result.get('videos',[])[:20]:
                    video_id=youtube_id(video.get('uri',''))
                    if video_id:videos.append({'id':video_id,'title':str(video.get('title') or release['title'])[:200]})
                expires=g.db.execute('SELECT fetched_at FROM snapshots WHERE user_id=?',(g.user['id'],)).fetchone()
                # Never retain release metadata beyond the snapshot's remaining lifetime.
                if not expires:return jsonify(error=t('Sync your collection before playing music.')),409
                g.db.execute('DELETE FROM music_cache WHERE expires<=?',(now,))
                g.db.execute('INSERT OR REPLACE INTO music_cache VALUES(?,?,?,?)',(g.user['id'],release['id'],json.dumps(videos),min(now+3600,expires['fetched_at']+TTL)))
                g.db.commit()
            available=[v for v in videos if v['id']!=previous] or videos
            if available:
                video=secrets.choice(available)
                return jsonify(video_id=video['id'],title=video['title'],release=release['title'],release_id=release['id'],artist=' · '.join(a['name'] for a in release['artists']))
        return jsonify(error=t('No linked YouTube video found in this selection. Try another record.')),404
