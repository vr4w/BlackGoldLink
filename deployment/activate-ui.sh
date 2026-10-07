#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Bitte mit sudo ausführen.'; exit 1; }
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
old_release=$(readlink -f /srv/blackgoldlink/current)
[[ "$old_release" == /srv/blackgoldlink/releases/* ]] || { echo 'Keine gültige BlackGoldLink-Instanz. Keine Änderung.'; exit 1; }
[[ -f /etc/blackgoldlink.env ]] || { echo 'BlackGoldLink-Konfiguration fehlt.'; exit 1; }
cmp -s "$source_dir/requirements.txt" "$old_release/requirements.txt" || { echo 'Abhängigkeiten verändert. Bitte Ausgabe an Codex geben.'; exit 1; }
if grep -q 'add_header Content-Security-Policy ' /etc/nginx/sites-available/blackgoldlink-preview; then
    echo 'Vorheriges Plattform-Update fehlt: Nginx überschreibt noch die App-Regeln.'; exit 1
fi
systemctl is-active --quiet blackgoldlink.service blackgoldlink-worker.service
release="/srv/blackgoldlink/releases/$(date +%Y%m%d-%H%M%S)-player"
install -d -o blackgoldlink -g blackgoldlink -m 750 "$release"
cp -a "$source_dir/." "$release/"
chown -R blackgoldlink:blackgoldlink "$release"
runuser -u blackgoldlink -- bash -c 'cd "$1"; /srv/blackgoldlink/venv/bin/python -m unittest discover -s tests -v' _ "$release"
rollback() {
    ln -sfn "$old_release" /srv/blackgoldlink/current
    systemctl restart blackgoldlink.service || true
    echo 'BlackGoldLink-Webdienst wurde auf den vorherigen Stand zurückgesetzt.'
}
trap rollback ERR
ln -sfn "$release" /srv/blackgoldlink/current
systemctl restart blackgoldlink.service
curl --retry 15 --retry-all-errors --retry-delay 1 --retry-max-time 30 --fail --silent --show-error --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/health
curl --fail --silent --head --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/invite | python3 -c 'import sys; assert "https://www.discogs.com" in sys.stdin.read(), "Discogs-Anmelderegel fehlt"'
code=$(curl --silent --output /dev/null --write-out '%{http_code}' https://blackgoldlink.almost-everything.de/)
[[ "$code" == 401 ]] || { echo 'Gemeinsamer Zugangsschutz nicht bestätigt.'; false; }
trap - ERR
echo 'FERTIG: Kompakter Player, Lautstärkeleiste und eigene Collection-Platte aktiv. Seite neu laden.'
echo 'Importdienst, Datenbank, Zugangsdaten, Nginx und Portal wurden nicht verändert.'
