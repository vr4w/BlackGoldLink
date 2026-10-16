"""Explicit owner-run activation of public BGL entry; no portal configuration changes."""
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def main():
    if os.geteuid()!=0:raise SystemExit('Bitte mit sudo ausführen.')
    archive,commit,checksum=sys.argv[1:]
    data=Path(archive).read_bytes()
    import re
    if not re.fullmatch('[0-9a-f]{40}',commit) or hashlib.sha256(data).hexdigest()!=checksum:raise SystemExit('Release-Prüfung fehlgeschlagen.')
    spec=importlib.util.spec_from_file_location('bgl_updater','/usr/local/lib/blackgoldlink/github-updater.py')
    updater=importlib.util.module_from_spec(spec);spec.loader.exec_module(updater)
    with (updater.STATE/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        release=updater.BASE/'releases'/('public-entry-'+commit[:12])
        if release.exists():
            raise SystemExit('Release existiert bereits. Bitte Ausgabe an Codex geben.')
        else:
            release.mkdir(mode=0o750);updater.extract_source(data,release,commit)
        subprocess.run(['chown','-R','root:blackgoldlink',str(release)],check=True)
        for folder in [release,*[p for p in release.rglob('*') if p.is_dir()]]:folder.chmod(0o750)
        db,host,url=updater.settings()
        if host!='blackgoldlink.almost-everything.de':raise SystemExit('Unerwartetes Ziel.')
        if not updater.activate(release,db,host,url):raise SystemExit('Import läuft. Bitte später erneut ausführen.')
        config=Path('/etc/nginx/sites-available/blackgoldlink-preview')
        original=config.read_bytes()
        text=original.decode()
        if 'server_name blackgoldlink.almost-everything.de;' not in text or 'proxy_pass http://127.0.0.1:5013;' not in text:raise SystemExit('Unerwartete Nginx-Konfiguration.')
        updated='\n'.join(line for line in text.splitlines() if not line.strip().startswith(('auth_basic ','auth_basic_user_file ')))+'\n'
        backup=updater.BASE/'backups'/('public-entry-'+str(int(time.time())))
        backup.mkdir(mode=0o700)
        shutil.copy2(config,backup/'nginx.conf')
        installed=Path('/usr/local/lib/blackgoldlink/github-updater.py')
        shutil.copy2(installed,backup/'github-updater.py')
        marker=updater.STATE/'public-access';was_public=marker.exists()
        try:
            config.write_text(updated)
            subprocess.run(['nginx','-t'],check=True)
            subprocess.run(['systemctl','reload','nginx'],check=True)
            for route,expected in [('/',200),('/app',302),('/admin',302),('/api/friends',302)]:
                code=subprocess.check_output(['curl','--silent','--show-error','--max-time','20','--output','/dev/null','--write-out','%{http_code}',url+route],text=True)
                if code!=str(expected):raise RuntimeError('Zugangsprüfung fehlgeschlagen: '+route+' '+code)
            shutil.copyfile(release/'deployment/github-updater.py',installed);installed.chmod(0o644)
            marker.write_text('Public landing page authorised by owner.\n');marker.chmod(0o600)
        except BaseException:
            config.write_bytes(original);shutil.copyfile(backup/'github-updater.py',installed)
            if not was_public:marker.unlink(missing_ok=True)
            subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True)
            raise
    print('FERTIG: BlackGoldLink direkt erreichbar. Persönliche Anmeldung und Admin-Rechte bleiben geschützt.')

if __name__=='__main__':main()
