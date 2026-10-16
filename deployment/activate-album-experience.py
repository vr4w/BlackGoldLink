"""Explicit one-time album-score upgrade; the installed automatic updater stays unchanged.

Run by the owner with sudo after reviewing the tested source package. Only the
known release-score -> album-score change is permitted. No database migration.
"""
import fcntl
import grp
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing

OLD_SCORE_SHA='efc35beffd1dac6a4256fcb1aad746a4bc29856ea2944057b88636ee9820aa8c'
NEW_SCORE_SHA='68c73705ed35b914d278c1561f5d6802d6629a20f76d746d6e5d7ce645e8233c'


def validate_baseline(old,new,updater):
    for name in updater.STABLE:
        if name=='matching.py':
            if hashlib.sha256((old/name).read_bytes()).hexdigest() not in (OLD_SCORE_SHA,NEW_SCORE_SHA):
                raise RuntimeError('Unbekannte bisherige Score-Version. Keine Änderung.')
            if hashlib.sha256((new/name).read_bytes()).hexdigest()!=NEW_SCORE_SHA:
                raise RuntimeError('Album-Score stimmt nicht mit der geprüften Version überein.')
        elif (old/name).read_bytes()!=(new/name).read_bytes():
            raise RuntimeError(name+' weicht ab. Keine Änderung am Importdienst oder dessen Abhängigkeiten.')
    for file,name in updater.SCHEMAS:
        if updater.schema(old,file,name)!=updater.schema(new,file,name):
            raise RuntimeError('Datenbankschema weicht ab. Keine Änderung.')


def activate(release,updater,db,host,base_url):
    old=(updater.BASE/'current').resolve()
    if old.parent!=(updater.BASE/'releases').resolve():raise RuntimeError('Ungültiger aktiver Release-Pfad.')
    validate_baseline(old,release,updater)
    if updater.pending(db):raise RuntimeError('Import läuft noch. Bitte nach dessen Abschluss erneut starten.')
    python='/srv/blackgoldlink/venv/bin/python'
    command=['runuser','-u','blackgoldlink','--',python,'-B']
    subprocess.run(command+['-m','unittest','discover','-s','tests','-q'],cwd=release,check=True,timeout=180)
    version=subprocess.check_output(command+['-c','from pathlib import Path; from versioning import release_version; print(release_version(Path.cwd()))'],cwd=release,text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{24}',version):raise RuntimeError('Ungültige Build-Version.')
    updater.systemctl('is-active','blackgoldlink.service','blackgoldlink-worker.service')
    try:
        updater.systemctl('stop','blackgoldlink.service')
        if updater.pending(db):raise RuntimeError('Ein neuer Import wurde gestartet. Bitte nach dessen Abschluss erneut versuchen.')
        updater.systemctl('stop','blackgoldlink-worker.service')
        backup=updater.BASE/'backups'/release.name
        backup.mkdir(mode=0o700,parents=True,exist_ok=False)
        with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as source:
            with closing(sqlite3.connect(backup/'collection.db')) as target:source.backup(target)
        shutil.copy2(updater.ENV,backup/'blackgoldlink.env')
        updater.switch(release)
        updater.systemctl('start','blackgoldlink.service','blackgoldlink-worker.service')
        updater.health(host,base_url,version)
    except BaseException:
        updater.switch(old)
        updater.systemctl('restart','blackgoldlink.service','blackgoldlink-worker.service')
        # Never overwrite new messages or sessions with an older database backup.
        raise
    return version


def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo starten.')
    if len(sys.argv)!=4:raise SystemExit('Aufruf: activate-album-experience.py ARCHIV COMMIT SHA256')
    archive,commit,checksum=sys.argv[1:]
    if not re.fullmatch(r'[0-9a-f]{40}',commit) or not re.fullmatch(r'[0-9a-f]{64}',checksum):raise SystemExit('Ungültiger Commit oder Prüfsumme.')
    if Path(archive).stat().st_size>12*1024*1024:raise SystemExit('Archiv zu groß.')
    data=Path(archive).read_bytes()
    if hashlib.sha256(data).hexdigest()!=checksum:raise SystemExit('Archiv-Prüfsumme stimmt nicht. Keine Änderung.')
    installed=Path('/usr/local/lib/blackgoldlink/github-updater.py')
    if not installed.is_file() or installed.stat().st_uid!=0 or installed.stat().st_mode&0o022:
        raise SystemExit('Vorhandener root-eigener BGL-Updater fehlt oder hat unsichere Rechte. Keine Änderung.')
    spec=importlib.util.spec_from_file_location('installed_bgl_updater',installed)
    updater=importlib.util.module_from_spec(spec);spec.loader.exec_module(updater)
    updater.STATE.mkdir(mode=0o700,exist_ok=True)
    with (updater.STATE/'lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Ein anderes BlackGoldLink-Update läuft. Bitte später erneut starten.')
        release=Path(tempfile.mkdtemp(prefix='album-'+commit[:7]+'-',dir=updater.BASE/'releases'))
        try:
            updater.extract_source(data,release,commit)
            gid=grp.getgrnam('blackgoldlink').gr_gid
            for path in (release,*release.rglob('*')):
                os.chown(path,0,gid);path.chmod(0o750 if path.is_dir() else 0o640)
            db,host,base_url=updater.settings()
            version=activate(release,updater,db,host,base_url)
            print('FERTIG: Album-Abgleich, Animation und integrierter Chat aktiv. Version '+version)
            print('Keine Zugangsdaten, API-Verbindungen, Nginx- oder AE-Portal-Konfigurationen geändert.')
        finally:
            if (updater.BASE/'current').resolve()!=release:shutil.rmtree(release)


if __name__=='__main__':
    os.umask(0o077)
    def interrupted(signum,frame):raise SystemExit('Update unterbrochen; bisheriger Stand wird wiederhergestellt.')
    signal.signal(signal.SIGTERM,interrupted)
    main()
