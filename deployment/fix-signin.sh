#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Bitte mit sudo ausführen.'; exit 1; }
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
old_release=$(readlink -f /srv/blackgoldlink/current)
[[ "$old_release" == /srv/blackgoldlink/releases/* ]] || { echo 'Unerwartetes BlackGoldLink-Release. Keine Änderung.'; exit 1; }
hash=$(sha256sum "$old_release/app.py" | cut -d ' ' -f 1)
[[ "$hash" == d58904d2f25604b2b54eab11097e8df13bdd9830f880fda18cc481076711a6a1 || "$hash" == 0457e81b56711e5c4995e883972e8b821641760a97ff68ad07fefe66752af90e ]] || { echo 'BlackGoldLink wurde zwischenzeitlich geändert. Bitte Ausgabe an Codex geben.'; exit 1; }
release="/srv/blackgoldlink/releases/$(date +%Y%m%d-%H%M%S)-signin-fix"
cp -a "$old_release" "$release"
for file in app.py templates/join.html static/app.js tests/test_profiles_music_language.py; do
    install -o blackgoldlink -g blackgoldlink -m 644 "$source_dir/$file" "$release/$file"
done
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
curl --fail --silent --head --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/invite | python3 -c 'import sys; headers=sys.stdin.read(); assert "https://www.discogs.com" in headers, "Discogs-Weiterleitung nicht freigegeben"'
systemctl is-active --quiet blackgoldlink.service blackgoldlink-worker.service
trap - ERR
echo 'FERTIG: Anmeldeweiterleitung und Button-Rückmeldung korrigiert. Seite im Browser neu laden.'
