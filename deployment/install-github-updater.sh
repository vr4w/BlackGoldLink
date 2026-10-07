#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Bitte mit sudo ausführen.'; exit 1; }
umask 0077
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
owner_username=${1:?Discogs-Name des Hauptnutzers angeben.}
# Complete the already reviewed owner-panel baseline if it is not active yet.
version=$(curl --fail --silent --header 'Host: blackgoldlink.almost-everything.de' http://127.0.0.1:5013/api/version | python3 -c 'import sys,json;print(json.load(sys.stdin)["version"])')
expected=$(cd "$source_dir" && /srv/blackgoldlink/venv/bin/python -B -c 'from pathlib import Path;from versioning import release_version;print(release_version(Path.cwd()))')
if [[ "$version" != "$expected" ]]; then
    bash "$source_dir/deployment/activate-admin.sh" "$owner_username"
else
    python3 "$source_dir/deployment/configure-owner.py" --check "$owner_username"
fi
# Keep privileged updater outside the writable app/release tree.
install -d -o root -g root -m 755 /usr/local/lib/blackgoldlink
install -o root -g root -m 644 "$source_dir/deployment/github-updater.py" /usr/local/lib/blackgoldlink/github-updater.py
install -d -o root -g root -m 700 /var/lib/blackgoldlink-deploy
printf '%s\n' '{"repository":"vr4w/BlackGoldLink"}' > /etc/blackgoldlink-deploy.json
chmod 600 /etc/blackgoldlink-deploy.json
install -o root -g root -m 644 "$source_dir/deployment/blackgoldlink-deploy.service" /etc/systemd/system/blackgoldlink-deploy.service
install -o root -g root -m 644 "$source_dir/deployment/blackgoldlink-deploy.timer" /etc/systemd/system/blackgoldlink-deploy.timer
systemd-analyze verify /etc/systemd/system/blackgoldlink-deploy.service /etc/systemd/system/blackgoldlink-deploy.timer
systemctl daemon-reload
systemctl enable --now blackgoldlink-deploy.timer
systemctl start blackgoldlink-deploy.service
systemctl is-active blackgoldlink-deploy.timer blackgoldlink.service blackgoldlink-worker.service
echo 'FERTIG: Admin-Panel und GitHub-Updateprüfung eingerichtet. AE-Portal bleibt unverändert.'
echo 'Live-Updates erst nach Tests und deiner Freigabe im GitHub-Workflow Check and publish.'
