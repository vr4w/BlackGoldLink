#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Bitte mit sudo ausführen.'; exit 1; }
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
old_release=$(readlink -f /srv/blackgoldlink/current)
[[ "$old_release" == /srv/blackgoldlink/releases/* ]] || { echo 'Keine gültige BlackGoldLink-Instanz. Keine Änderung.'; exit 1; }
[[ -f /etc/blackgoldlink.env ]] || { echo 'BlackGoldLink-Konfiguration fehlt.'; exit 1; }
# Only the web service changes. Import and comparison foundations must match.
for file in requirements.txt worker.py discogs.py matching.py covers.py features.py; do
    cmp -s "$source_dir/$file" "$old_release/$file" || { echo "Vorheriger Stand stimmt bei $file nicht überein. Keine Änderung."; exit 1; }
done
# Existing account, contact and message schemas must remain byte-identical.
python3 - "$source_dir" "$old_release" <<'PY_SCHEMA'
import ast,sys
from pathlib import Path
def schema(folder,file,name):
    tree=ast.parse((Path(folder)/file).read_text())
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id==name for target in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError('Schema fehlt: '+file)
for file,name in [('app.py','SCHEMA'),('social.py','SOCIAL_SCHEMA')]:
    if schema(sys.argv[1],file,name)!=schema(sys.argv[2],file,name):
        raise SystemExit('Datenbankschema weicht ab. Keine Änderung.')
PY_SCHEMA
systemctl is-active --quiet blackgoldlink.service blackgoldlink-worker.service
release="/srv/blackgoldlink/releases/$(date +%Y%m%d-%H%M%S)-live-social"
install -d -o blackgoldlink -g blackgoldlink -m 750 "$release"
cp -a "$source_dir/." "$release/"
chown -R blackgoldlink:blackgoldlink "$release"
runuser -u blackgoldlink -- bash -c 'cd "$1"; /srv/blackgoldlink/venv/bin/python -m unittest discover -s tests -q' _ "$release"
expected_version=$(runuser -u blackgoldlink -- bash -c 'cd "$1"; /srv/blackgoldlink/venv/bin/python -c "from pathlib import Path; from versioning import release_version; print(release_version(Path.cwd()))"' _ "$release")
rollback() {
    ln -sfn "$old_release" /srv/blackgoldlink/current
    systemctl restart blackgoldlink.service || true
    echo 'BlackGoldLink-Webdienst wurde auf den vorherigen Code zurückgesetzt. Importdienst bleibt unberührt.'
}
trap rollback ERR
ln -sfn "$release" /srv/blackgoldlink/current
systemctl restart blackgoldlink.service
# Expected startup retries stay quiet; report an actual timeout instead.
curl --retry 15 --retry-all-errors --retry-delay 1 --retry-max-time 30 --fail --silent --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/health || { echo 'Webdienst nicht rechtzeitig bereit. Update wird zurückgenommen.'; false; }
actual_version=$(curl --fail --silent --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/api/version | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])')
[[ "$actual_version" == "$expected_version" ]] || { echo 'Versionsprüfung fehlgeschlagen.'; false; }
curl --fail --silent --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/ | python3 -c 'import sys; page=sys.stdin.read(); assert ("data-version=\""+sys.argv[1]+"\"") in page and "data-version-reload" in page, "Update-Hinweis fehlt"' "$expected_version"
code=$(curl --silent --output /dev/null --write-out '%{http_code}' https://blackgoldlink.almost-everything.de/)
[[ "$code" == 401 ]] || { echo 'Gemeinsamer Zugangsschutz nicht bestätigt.'; false; }
trap - ERR
echo 'FERTIG: Live-Anfragen, Suche, Chat und neue Vergleichsansicht aktiv.'
echo 'Alle Nutzer laden jetzt einmal neu. Danach aktualisieren sich Kontakte und Anfragen etwa alle 3 Sekunden, Chat und Tippstatus etwa alle 2 Sekunden. Bei künftigen Updates erscheint der Versionshinweis.'
echo 'Nur BlackGoldLink-Webdienst neu gestartet. Laufende Imports, Daten, Zugangsdaten, Nginx und AE-Portal bleiben erhalten.'
