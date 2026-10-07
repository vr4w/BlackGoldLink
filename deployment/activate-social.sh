#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Bitte mit sudo ausführen.'; exit 1; }
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
old_release=$(readlink -f /srv/blackgoldlink/current)
[[ "$old_release" == /srv/blackgoldlink/releases/* ]] || { echo 'Keine gültige BlackGoldLink-Instanz. Keine Änderung.'; exit 1; }
[[ -f /etc/blackgoldlink.env ]] || { echo 'BlackGoldLink-Konfiguration fehlt.'; exit 1; }
cmp -s "$source_dir/requirements.txt" "$old_release/requirements.txt" || { echo 'Abhängigkeiten verändert. Keine Änderung.'; exit 1; }
if grep -q 'add_header Content-Security-Policy ' /etc/nginx/sites-available/blackgoldlink-preview; then
    echo 'Vorheriges Plattform-Update fehlt: Nginx überschreibt noch die App-Regeln.'; exit 1
fi
systemctl is-active --quiet blackgoldlink.service blackgoldlink-worker.service
release="/srv/blackgoldlink/releases/$(date +%Y%m%d-%H%M%S)-social"
install -d -o blackgoldlink -g blackgoldlink -m 750 "$release"
cp -a "$source_dir/." "$release/"
chown -R blackgoldlink:blackgoldlink "$release"
runuser -u blackgoldlink -- bash -c 'cd "$1"; /srv/blackgoldlink/venv/bin/python -m unittest discover -s tests -q' _ "$release"
worker_stopped=false
rollback() {
    ln -sfn "$old_release" /srv/blackgoldlink/current
    systemctl restart blackgoldlink.service || true
    if [[ "$worker_stopped" == true ]]; then systemctl restart blackgoldlink-worker.service || true; fi
    echo 'BlackGoldLink läuft wieder mit dem vorherigen Code. Bestehende Daten wurden nicht überschrieben.'
}
trap rollback ERR
# Stop new web requests first, while any existing import keeps running.
systemctl stop blackgoldlink.service
python3 - <<'JOBS'
from pathlib import Path
import sqlite3
path='/var/lib/blackgoldlink/collection.db'
for line in Path('/etc/blackgoldlink.env').read_text().splitlines():
    if line.startswith('DATABASE_PATH='):path=line.partition('=')[2].strip().strip("\"'")
with sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True) as db:
    if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:
        raise SystemExit('Ein Import läuft oder wartet noch. Bitte nach dessen Abschluss erneut ausführen. Importdienst bleibt unberührt.')
JOBS
worker_stopped=true
systemctl stop blackgoldlink-worker.service
install -d -o root -g root -m 700 /srv/blackgoldlink/backups
python3 - "$release" <<'CHECK'
from pathlib import Path
import sqlite3,sys
path='/var/lib/blackgoldlink/collection.db'
for line in Path('/etc/blackgoldlink.env').read_text().splitlines():
    if line.startswith('DATABASE_PATH='):path=line.partition('=')[2].strip().strip("\"'")
with sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True) as source:
    if source.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:
        raise SystemExit('Ein Import läuft oder wartet noch. Bitte nach dessen Abschluss erneut ausführen. Kein Update vorgenommen.')
    backup=Path('/srv/blackgoldlink/backups')/(Path(sys.argv[1]).name+'.sqlite')
    if backup.exists():raise SystemExit('Backup-Ziel existiert bereits. Keine Änderung.')
    with sqlite3.connect(backup) as target:source.backup(target)
    backup.chmod(0o600)
CHECK
ln -sfn "$release" /srv/blackgoldlink/current
systemctl restart blackgoldlink.service blackgoldlink-worker.service
curl --retry 15 --retry-all-errors --retry-delay 1 --retry-max-time 30 --fail --silent --show-error --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/health
curl --fail --silent --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/ | python3 -c 'import sys; text=sys.stdin.read(); assert "Compare your collection with others." in text and "Explore the demo" not in text and "/imprint" in text, "Neue Landingpage nicht bestätigt"'
code=$(curl --silent --output /dev/null --write-out '%{http_code}' https://blackgoldlink.almost-everything.de/)
[[ "$code" == 401 ]] || { echo 'Gemeinsamer Zugangsschutz nicht bestätigt.'; false; }
trap - ERR
echo 'FERTIG: Zoom-Regal mit Cover-Vorschau, schlanker Footer, Friends-Panel und privater Chat aktiv.'
echo 'Seite neu laden. Friends → Find people → Anfrage senden → Gegenüber nimmt an → Compare.'
echo 'Nur BlackGoldLink wurde aktualisiert. Datenbanksicherung erstellt; Nginx, Zugangsdaten und AE-Portal unverändert.'
