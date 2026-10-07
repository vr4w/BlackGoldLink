"""Run only on the server via the root installer. Never prints credential values."""
from pathlib import Path
import getpass
import secrets
import shlex
from cryptography.fernet import Fernet

path=Path('/etc/blackgoldlink.env')
config={}
if path.exists():
    for line in path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key,value=line.split('=',1)
            parsed=shlex.split(value)
            config[key]=parsed[0] if parsed else ''
print('BlackGoldLink: eigene Server-Konfiguration. Eingaben werden nicht als Befehle gespeichert.')
for key,label in [('DISCOGS_CONSUMER_KEY','Discogs Consumer Key'),('DISCOGS_CONSUMER_SECRET','Discogs Consumer Secret')]:
    value=getpass.getpass(label+(' (Enter behält vorhandenen Wert)' if config.get(key) else '')+': ').strip()
    if value:config[key]=value
    if not config.get(key):raise SystemExit(label+' fehlt. Keine neue Konfiguration gespeichert.')
for key,label in [('CONTROLLER_NAME','Anbietername / verantwortliche Person'),('CONTROLLER_ADDRESS','Anbieteradresse'),('PRIVACY_CONTACT','Datenschutzkontakt (E-Mail)'),('HOSTING_PROVIDER','Hostinganbieter und Standort')]:
    value=input(label+(' (Enter behält vorhandenen Wert)' if config.get(key) else '')+': ').strip()
    if value:config[key]=value
    if not config.get(key):raise SystemExit(label+' fehlt. Keine neue Konfiguration gespeichert.')
if not config.get('SECRET_KEY'): config['SECRET_KEY']=secrets.token_hex(32)
if not config.get('TOKEN_ENCRYPTION_KEY'): config['TOKEN_ENCRYPTION_KEY']=Fernet.generate_key().decode()
config.update(APP_ENV='production',BASE_URL='https://blackgoldlink.almost-everything.de',DATABASE_PATH='/var/lib/blackgoldlink/collection.db',WORKING_TITLE='BlackGoldLink',PUBLIC_SIGNUP='true',MATCHING_APPROVED='false')
# Values are safely quoted for systemd, never sourced as shell code.
def quoted(value):
    return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('\n',' ').replace('\r',' ')+'"'
temporary=path.with_suffix('.env.new')
fd=__import__('os').open(temporary,__import__('os').O_WRONLY|__import__('os').O_CREAT|__import__('os').O_TRUNC,0o600)
with __import__('os').fdopen(fd,'w') as file:
    for key,value in sorted(config.items()):file.write(key+'='+quoted(value)+'\n')
temporary.replace(path)
print('Eigene Konfiguration gespeichert. Nutzervergleich bleibt deaktiviert.')
