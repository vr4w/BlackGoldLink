"""Bind the existing owner to their immutable Discogs ID. Never prints other ENV values."""
import argparse
import os
from pathlib import Path
import shlex
import sqlite3

parser=argparse.ArgumentParser()
parser.add_argument('username')
parser.add_argument('--check',action='store_true')
args=parser.parse_args()
if os.geteuid()!=0:raise SystemExit('Bitte als root ausführen.')
path=Path('/etc/blackgoldlink.env')
lines=path.read_text().splitlines(keepends=True)
values={}
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key,value=line.strip().split('=',1)
        if key in ('DATABASE_PATH','ADMIN_DISCOGS_IDS'):
            parts=shlex.split(value);values[key]=parts[0] if parts else ''
database=Path(values.get('DATABASE_PATH','/var/lib/blackgoldlink/collection.db'))
if not database.is_absolute() or not database.is_file():raise SystemExit('Konfigurierte BlackGoldLink-Datenbank fehlt. Keine Änderung.')
with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
    rows=db.execute('SELECT discogs_id,username FROM users WHERE username=? COLLATE NOCASE',(args.username,)).fetchall()
if len(rows)!=1:raise SystemExit('Hauptnutzer nicht eindeutig gefunden. Keine Änderung. Bitte exakten Discogs-Nutzernamen verwenden.')
uid,username=rows[0]
if not isinstance(uid,int) or not 0<uid<2**63:raise SystemExit('Ungültige Discogs-ID. Keine Änderung.')
ids=set()
for value in values.get('ADMIN_DISCOGS_IDS','').split(','):
    value=value.strip()
    if not value:continue
    if not value.isascii() or not value.isdigit() or not 0<int(value)<2**63:raise SystemExit('Vorhandene Admin-Konfiguration ungültig. Keine Änderung.')
    ids.add(int(value))
ids.add(uid)
print('Geprüfter Hauptnutzer: '+username+' · Discogs-ID '+str(uid))
if not args.check:
    # Preserve all existing settings verbatim, including credentials and approval flags.
    content=''.join(line for line in lines if not line.startswith('ADMIN_DISCOGS_IDS='))
    if content and not content.endswith('\n'):content+='\n'
    content+='ADMIN_DISCOGS_IDS="'+','.join(str(value) for value in sorted(ids))+'"\n'
    temporary=path.with_name('blackgoldlink.env.admin-new')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as file:file.write(content)
    temporary.replace(path)
    print('Admin-Zugang gespeichert. Alle anderen Konfigurationseinträge bleiben erhalten.')
