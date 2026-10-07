#!/usr/bin/env bash
set -euo pipefail
CONFIG=/etc/nginx/sites-available/blackgoldlink-preview
RELEASE_SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $EUID == 0 ]] || { echo 'Bitte mit sudo ausführen.'; exit 1; }
[[ -f "$RELEASE_SOURCE/app.py" ]] || { echo 'Vorbereitetes Release fehlt.'; exit 1; }
[[ -f "$CONFIG" ]] && grep -Fq 'auth_basic_user_file /etc/nginx/blackgoldlink.htpasswd;' "$CONFIG" || { echo 'Gemeinsamer Testzugang fehlt. Keine Aktivierung.'; exit 1; }
if ss -ltn 'sport = :5013' | tail -n +2 | grep -q .; then
    systemctl is-active --quiet blackgoldlink.service || { echo 'Port 5013 bereits belegt. Keine Aktivierung.'; exit 1; }
fi
nginx -t
curl --fail --silent --show-error --output /dev/null https://portal.almost-everything.de/login
if ! id blackgoldlink >/dev/null 2>&1; then useradd --system --user-group --home-dir /srv/blackgoldlink --shell /usr/sbin/nologin blackgoldlink; fi
install -d -o blackgoldlink -g blackgoldlink -m 750 /srv/blackgoldlink /var/lib/blackgoldlink
version=$(date +%Y%m%d-%H%M%S)
release="/srv/blackgoldlink/releases/$version"
install -d -o blackgoldlink -g blackgoldlink -m 750 "$release"
cp -a "$RELEASE_SOURCE/." "$release/"
chown -R blackgoldlink:blackgoldlink "$release"
if [[ ! -x /srv/blackgoldlink/venv/bin/python ]]; then runuser -u blackgoldlink -- python3 -m venv /srv/blackgoldlink/venv; fi
runuser -u blackgoldlink -- /srv/blackgoldlink/venv/bin/pip install -r "$release/requirements.txt"
runuser -u blackgoldlink -- bash -c 'cd "$1"; "$2" -m unittest discover -s tests -v' _ "$release" /srv/blackgoldlink/venv/bin/python
if [[ ! -f /etc/blackgoldlink.env ]]; then
    /srv/blackgoldlink/venv/bin/python "$release/deployment/configure-env.py"
else
    echo 'Vorhandene BlackGoldLink-Konfiguration wird übernommen; keine erneute Schlüsseleingabe.'
fi
chown root:blackgoldlink /etc/blackgoldlink.env
chmod 640 /etc/blackgoldlink.env
old_release=$(readlink /srv/blackgoldlink/current || true)
backup="${CONFIG}.before-platform-$version"
cp -p "$CONFIG" "$backup"
changed=false
rollback() {
    echo 'Aktivierung fehlgeschlagen. Rückkehr zur bisherigen BlackGoldLink-Seite.'
    if $changed; then cp -p "$backup" "$CONFIG"; if nginx -t; then systemctl reload nginx; fi; fi
    if [[ -n "$old_release" ]]; then
        ln -sfn "$old_release" /srv/blackgoldlink/current
        systemctl restart blackgoldlink.service blackgoldlink-worker.service || true
    else
        systemctl stop blackgoldlink.service blackgoldlink-worker.service || true
    fi
    echo 'Bestehende Portal-Dienste wurden nicht geändert. Bitte Ausgabe an Codex geben.'
}
trap rollback ERR
ln -sfn "$release" /srv/blackgoldlink/current
install -m 644 "$release/deployment/blackgoldlink.service" /etc/systemd/system/blackgoldlink.service
install -m 644 "$release/deployment/blackgoldlink-worker.service" /etc/systemd/system/blackgoldlink-worker.service
systemctl daemon-reload
systemctl enable blackgoldlink.service blackgoldlink-worker.service
systemctl restart blackgoldlink.service blackgoldlink-worker.service
curl --retry 15 --retry-all-errors --retry-delay 1 --retry-max-time 30 --fail --silent --show-error --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/health
python3 - "$CONFIG" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old='location / { try_files $uri $uri/index.html =404; }'
new='''location / {
        proxy_pass http://127.0.0.1:5013;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization "";
        proxy_read_timeout 180s;
    }'''
if s.count(old)==1:s=s.replace(old,new)
elif 'proxy_pass http://127.0.0.1:5013;' not in s:raise SystemExit('Unerwartete BlackGoldLink-Konfiguration.')
# The application owns CSP: strict pages, explicit YouTube hosts only on signed-in tools.
s='\n'.join(line for line in s.split('\n') if 'add_header Content-Security-Policy ' not in line)
p.write_text(s)
PY
changed=true
nginx -t
systemctl reload nginx
for attempt in $(seq 1 15); do
    code=$(curl --noproxy '*' --resolve blackgoldlink.almost-everything.de:443:127.0.0.1 --silent --output /dev/null --write-out '%{http_code}' https://blackgoldlink.almost-everything.de/)
    [[ "$code" == 401 ]] && break
    sleep 1
done
[[ "$code" == 401 ]] || { echo 'Äußerer Zugangsschutz nicht bestätigt.'; false; }
curl --fail --silent --show-error --output /dev/null https://portal.almost-everything.de/login
systemctl is-active --quiet blackgoldlink.service blackgoldlink-worker.service
trap - ERR
echo 'FERTIG: BlackGoldLink-Plattform und Importdienst sind aktiv. Der gemeinsame Testzugang bleibt erhalten.'
echo 'Jetzt im Browser mit dem Testzugang öffnen und danach deinen eigenen Discogs-Account verbinden.'
