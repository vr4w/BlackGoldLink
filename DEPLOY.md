# Deployment and operations

This project uses its own services, data, configuration and releases. Never reuse another application's database, session keys, service user or reverse-proxy block.

## Configuration

The full template is `.env.example`. It is a trusted shell/systemd-compatible configuration file, loaded into both the web app and worker.

- `APP_ENV=production`, HTTPS `BASE_URL`, dedicated `DATABASE_PATH` and `PORT`.
- Strong `SECRET_KEY` and Fernet `TOKEN_ENCRYPTION_KEY`, generated once and preserved. Generate locally with Python `secrets.token_hex(32)` and `Fernet.generate_key()` respectively. Store only in the private server configuration.
- Your Discogs application's `DISCOGS_CONSUMER_KEY` and `DISCOGS_CONSUMER_SECRET`. Register `BASE_URL/oauth/callback` as callback; no personal access token.
- `PUBLIC_SIGNUP`, optional `INVITE_CODE`; the current private test platform also has an outer Nginx login.
- `MATCHING_APPROVED=false` by default. Enable only for a deployment with appropriate Discogs permission. Each participant still separately opts into visibility.
- Real `CONTROLLER_NAME`, `CONTROLLER_ADDRESS`, `PRIVACY_CONTACT`, `HOSTING_PROVIDER`.
- `ADMIN_DISCOGS_IDS`: comma-separated immutable numeric Discogs IDs. Empty disables the owner panel. Editable usernames/handles never grant privileges.

## Current infrastructure defaults

- `/srv/blackgoldlink/releases/`, atomic `current` symlink and dedicated virtual environment.
- `/var/lib/blackgoldlink/collection.db`; `/etc/blackgoldlink.env` (private).
- `blackgoldlink.service` and `blackgoldlink-worker.service`, enabled at boot and restarted on failure.
- Web binds only to `127.0.0.1:5013`; Nginx handles TLS and the outer test-site gate.
- Service templates and legacy incremental activation scripts are in `deployment/`. The activation scripts are guards for particular historical baselines, not generic deployment commands. Do not run them blindly on another installation.

Domain changes use `BASE_URL` plus DNS, TLS and Discogs callback configuration. Paths/ports/service identities are explicit infrastructure settings. The app is independent of any other portal.

## GitHub checks and approval

Repository: `vr4w/BlackGoldLink`. Public source and Issues; real account data stays on the server.

`Check and publish` runs on main pushes and pull requests with read-only GitHub permission. For deployment, a maintainer explicitly runs that same workflow on `main` with **deploy** checked. The publish job waits for the `production` environment approval. The environment is restricted to main and a named maintainer reviewer. It publishes immutable `bgl-live-<40-character commit>` releases containing `blackgoldlink-source.tar.gz` and `SHA256SUMS`.

The archive is built from tracked Git files only, includes the exact commit marker and refuses private file paths. Deployment requires no Discogs credentials or server SSH key in GitHub. Private vulnerability reporting is enabled for sensitive reports.

## One-time server setup

The existing operator stages the audited source at a dedicated location and runs `deployment/install-github-updater.sh <owner Discogs username>` with sudo. On this specific existing installation it first completes the previously prepared admin-panel update if necessary. Unknown baselines abort before activation. On other servers install services and the current schema explicitly instead of using this historical bootstrap.

The installer places a root-owned fixed updater in `/usr/local/lib/blackgoldlink/`, configuration in `/etc/blackgoldlink-deploy.json` and private state in `/var/lib/blackgoldlink-deploy/`. It installs/enables only `blackgoldlink-deploy.service` and `.timer`. Existing app configuration, encryption keys, Nginx gate and unrelated services remain in place.

The updater's repository defaults to this public project. Update `/etc/blackgoldlink-deploy.json` deliberately if the repository moves. The updater reads `BASE_URL` and `DATABASE_PATH` from the existing app environment; service names, directories and loopback port are fixed BGL deployment defaults.

## Automatic update behavior

1. Check published, non-prerelease `bgl-live-*` releases about every two minutes. No approved release means no change.
2. Fetch only assets belonging to that repository/tag over HTTPS; verify SHA-256 and exact commit marker. Refuse unsafe paths, symlinks, private files and oversized archives.
3. Refuse changes to existing DB schemas, requirements, worker/importer, scoring and rate-limit foundations. These need a reviewed manual migration/release. The initial automatic path is deliberately limited to compatible web/UI changes.
4. Execute tests as the unprivileged BGL service user. No newly downloaded deployment script is executed as root.
5. Defer if an import is queued/running. Briefly stop only BGL web, recheck for racing imports, then stop BGL worker. Save a consistent private DB/config backup.
6. Switch code, start both BGL services and verify version, health and the existing public 401 gate. Failure restores the old code and services. Never blindly restore a stale DB over newer chats/accounts.
7. Remember successful releases. Existing users get the reload notice; browser pages are not forcibly reloaded.

A rejected release remains visible in the deployment journal and must be corrected or deployed manually. The timer does not perform dependency upgrades, migrations, proxy changes or updater self-upgrades. Backups and successful release directories are retained for manual recovery; the operator must maintain retention/space and deletion requirements. GitHub/API outages leave the running app unchanged.

## Status, pause and recovery

```sh
sudo systemctl status blackgoldlink-deploy.timer blackgoldlink-deploy.service
sudo journalctl -u blackgoldlink-deploy.service -n 50 --no-pager
sudo systemctl stop blackgoldlink-deploy.timer
```

Stopping the timer prevents future checks; an already running update can still finish. For an emergency stop, stop both timer and deploy service. Its termination handler restores old code if activation is underway. Existing BGL web/worker services continue independently of the timer.

Manual recovery: pause updates, verify the desired release, atomically point `current` to it and restart only the two BGL services. Preserve the current database and environment. Explicitly review schema compatibility before any historical rollback. After rolling back manually, publishing a newly approved commit is the preferred path; do not overwrite a published release asset.

The owner panel is `/admin`, linked from the owner's profile. It can revoke sessions, suspend or restore users. BGL has no user passwords to reset: login belongs to Discogs. Suspension does not delete data; restored users must log in and enable comparison visibility again.
