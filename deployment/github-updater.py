"""Root-installed, fixed BGL updater. No repository-provided script runs as root."""
import ast
from contextlib import closing
import fcntl
import grp
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import sqlite3
import subprocess
import tarfile
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

BASE=Path('/srv/blackgoldlink')
ENV=Path('/etc/blackgoldlink.env')
STATE=Path('/var/lib/blackgoldlink-deploy')
CONFIG=Path('/etc/blackgoldlink-deploy.json')
MAX_ARCHIVE=12*1024*1024
STABLE=('requirements.txt','worker.py','discogs.py','matching.py','covers.py','features.py')
SCHEMAS=(('app.py','SCHEMA'),('social.py','SOCIAL_SCHEMA'),('admin.py','ADMIN_SCHEMA'))


def fetch(url,limit):
    with urlopen(Request(url,headers={'User-Agent':'BlackGoldLink-Release-Updater/1','Accept':'application/vnd.github+json'}),timeout=30) as response:
        data=response.read(limit+1)
    if len(data)>limit:raise RuntimeError('Download too large')
    return data


def latest_release(repo):
    if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+',repo):raise RuntimeError('Invalid repository')
    releases=json.loads(fetch('https://api.github.com/repos/'+repo+'/releases?per_page=20',512*1024))
    releases=[r for r in releases if not r['draft'] and not r['prerelease'] and re.fullmatch(r'bgl-live-[0-9a-f]{40}',r['tag_name'])]
    if not releases:return None
    return max(releases,key=lambda r:r['published_at'])


def release_archive(repo,release):
    prefix='https://github.com/'+repo+'/releases/download/'+release['tag_name']+'/'
    assets={a['name']:a['browser_download_url'] for a in release['assets']}
    for name in ('blackgoldlink-source.tar.gz','SHA256SUMS'):
        if assets.get(name)!=prefix+name:raise RuntimeError('Unexpected release asset URL')
    checksum=fetch(assets['SHA256SUMS'],256).decode().strip()
    if not re.fullmatch(r'[0-9a-f]{64}  blackgoldlink-source\.tar\.gz',checksum):raise RuntimeError('Invalid checksum file')
    data=fetch(assets['blackgoldlink-source.tar.gz'],MAX_ARCHIVE)
    if hashlib.sha256(data).hexdigest()!=checksum.split()[0]:raise RuntimeError('Checksum mismatch')
    return data


def extract_source(data,dest,commit):
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        members=archive.getmembers();total=0;seen=set()
        if len(members)>2000:raise RuntimeError('Too many archive entries')
        for member in members:
            path=PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or member.name in seen:
                raise RuntimeError('Unsafe archive path')
            seen.add(member.name)
            if not (member.isdir() or member.isfile()):raise RuntimeError('Links and special files are forbidden')
            if any(p in ('instance','backups','.git','.venv','__pycache__') for p in path.parts) or (
                member.name!='.env.example' and any(p.startswith('.env') for p in path.parts)
            ) or member.name.endswith(('.db','.pem','.key','.sqlite','.sqlite3')):
                raise RuntimeError('Private file in release')
            total+=member.size
            if member.size<0 or total>40*1024*1024:raise RuntimeError('Expanded archive too large')
        for member in members:
            path=dest.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():path.mkdir(parents=True,exist_ok=True)
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as src,path.open('xb') as dst:shutil.copyfileobj(src,dst)
                path.chmod(0o640)
    if (dest/'.bgl-commit').read_text().strip()!=commit:raise RuntimeError('Commit marker mismatch')
    for required in ('app.py','worker.py','requirements.txt','versioning.py','tests','templates','static'):
        if not (dest/required).exists():raise RuntimeError('Incomplete source release')


def schema(folder,file,name):
    for node in ast.parse((folder/file).read_text()).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError('Missing schema '+name)


def compatible(old,new):
    for file in STABLE:
        if (old/file).read_bytes()!=(new/file).read_bytes():raise RuntimeError(file+' changed; manual release required')
    for file,name in SCHEMAS:
        if schema(old,file,name)!=schema(new,file,name):raise RuntimeError(name+' changed; manual migration required')


def settings():
    values={}
    for line in ENV.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1);parts=shlex.split(value)
            values[key.strip()]=parts[0] if parts else ''
    url=urlsplit(values.get('BASE_URL',''))
    if url.scheme!='https' or not url.hostname:raise RuntimeError('HTTPS BASE_URL missing')
    return Path(values.get('DATABASE_PATH','/var/lib/blackgoldlink/collection.db')),url.hostname,values['BASE_URL'].rstrip('/')


def pending(db):
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=10)) as con:
        return con.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]


def systemctl(action,*units):subprocess.run(['systemctl',action,*units],check=True,timeout=60)


def switch(release):
    link=BASE/'.next-release'
    link.unlink(missing_ok=True);link.symlink_to(release);link.replace(BASE/'current')


def health(host,base_url,version):
    for _ in range(20):
        try:
            with urlopen(Request('http://127.0.0.1:5013/api/version',headers={'Host':host}),timeout=3) as response:
                actual=json.load(response)['version']
            with urlopen(Request('http://127.0.0.1:5013/health',headers={'Host':host}),timeout=3) as response:
                status=json.load(response)['status']
            if actual==version and status=='ok':break
        except Exception:pass
        time.sleep(1)
    else:raise RuntimeError('New web version did not become healthy')
    # curl validates TLS. Only 401 confirms the existing private test gate.
    result=subprocess.check_output(['curl','--silent','--show-error','--max-time','20','--output','/dev/null','--write-out','%{http_code}',base_url+'/'],text=True)
    if result!='401':raise RuntimeError('Shared access gate not confirmed')
    systemctl('is-active','blackgoldlink.service','blackgoldlink-worker.service')


def activate(release,db,host,base_url):
    old=(BASE/'current').resolve()
    if old.parent!=(BASE/'releases').resolve():raise RuntimeError('Invalid current release')
    if pending(db):print('Import active; update deferred.');return False
    compatible(old,release)
    # Execute all new application code with the existing unprivileged service identity.
    subprocess.run(['runuser','-u','blackgoldlink','--','/srv/blackgoldlink/venv/bin/python','-B','-m','unittest','discover','-s','tests','-q'],cwd=release,check=True,timeout=180)
    version=subprocess.check_output(['runuser','-u','blackgoldlink','--','/srv/blackgoldlink/venv/bin/python','-B','-c','from pathlib import Path; from versioning import release_version; print(release_version(Path.cwd()))'],cwd=release,text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{24}',version):raise RuntimeError('Invalid build version')
    systemctl('is-active','blackgoldlink.service','blackgoldlink-worker.service')
    try:
        systemctl('stop','blackgoldlink.service')
        if pending(db):systemctl('start','blackgoldlink.service');print('New import; update deferred.');return False
        systemctl('stop','blackgoldlink-worker.service')
        backup=BASE/'backups'/release.name
        backup.mkdir(mode=0o700,parents=True,exist_ok=False)
        with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as source:
            with closing(sqlite3.connect(backup/'collection.db')) as target:source.backup(target)
        shutil.copy2(ENV,backup/'blackgoldlink.env')
        switch(release)
        systemctl('start','blackgoldlink.service','blackgoldlink-worker.service')
        health(host,base_url,version)
    except BaseException:
        switch(old)
        systemctl('restart','blackgoldlink.service','blackgoldlink-worker.service')
        # Never restore a stale database over new user messages or sessions.
        raise
    return True


def main():
    if os.geteuid()!=0:raise SystemExit('Root-installed updater only')
    STATE.mkdir(mode=0o700,exist_ok=True)
    with (STATE/'lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        repo=json.loads(CONFIG.read_text())['repository']
        release=latest_release(repo)
        if not release:print('No approved release yet.');return
        tag=release['tag_name'];commit=tag.removeprefix('bgl-live-');marker=STATE/'installed'
        if marker.exists() and marker.read_text().strip()==tag:return
        db,host,base_url=settings()
        if pending(db):print('Import active; update deferred.');return
        dest=Path(tempfile.mkdtemp(prefix='github-'+commit[:7]+'-',dir=BASE/'releases'))
        installed=False
        try:
            extract_source(release_archive(repo,release),dest,commit)
            gid=grp.getgrnam('blackgoldlink').gr_gid
            for path in [dest,*dest.rglob('*')]:
                os.chown(path,0,gid)
                path.chmod(0o750 if path.is_dir() else 0o640)
            installed=activate(dest,db,host,base_url)
            if installed:
                marker.write_text(tag+'\n');print('Installed '+tag)
        finally:
            if not installed and (BASE/'current').resolve()!=dest:shutil.rmtree(dest)


if __name__=='__main__':
    os.umask(0o077)
    def interrupted(signum,frame):raise SystemExit('Updater interrupted; restoring active release if necessary')
    signal.signal(signal.SIGTERM,interrupted)
    main()
