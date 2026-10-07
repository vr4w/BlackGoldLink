# BlackGoldLink

Compare your record collection with others.

BlackGoldLink is a separate Discogs-connected test platform. It imports a consenting user's collection and wantlist, shows a vinyl shelf and collection profile, and compares opted-in participants. The interface defaults to English with a German switch.

## Included

- Discogs OAuth 1.0a sign-in: no separate BGL password.
- Encrypted tokens, server-side sessions and a separate queued import worker.
- Vinyl-first collection/wantlist grids, cover thumbnails and a stylised horizontal shelf.
- Release, artist and genre overlap; collection-to-wantlist crossmatches.
- Friend invitations, user discovery, confirmed contacts and private chat with presence/typing indicators.
- Consent-based visible YouTube shelf radio, starting at 10% volume.
- Owner-only account administration: counts, session revocation, suspension and restoration.
- Account export/deletion, limited snapshot lifetime and an update/reload notice.

Public source does not grant access to the private test platform or any user's data. Real comparisons are disabled by default; each operator must establish appropriate Discogs permission and configure their deployment. See [COMPLIANCE.md](COMPLIANCE.md). The app is not affiliated with Discogs.

## Run locally

Python 3.11 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5013`. The demonstration uses fictional records and accounts. Real account import requires your own Discogs developer app and configuration.

Copy `.env.example` to `.env`, fill in the values and load it into both processes. The app deliberately does not automatically load `.env`.

```sh
set -a
. ./.env
set +a
python app.py
```

In a second terminal, activate the same virtual environment, load the same configuration and run `python worker.py`. Set an absolute `DATABASE_PATH`; preserve `SECRET_KEY` and `TOKEN_ENCRYPTION_KEY` across releases. Never commit the configuration or database. [Deployment and keys](DEPLOY.md).

## How matching works

The main score is `100 × |A ∩ B| / sqrt(|A| × |B|)` over unique release IDs. It is symmetric and accounts for collection size. Duplicate copies count once; different pressings remain different releases. Artist and genre scores use the same formula on separate sets and are shown separately.

The core flow is collection discovery: the dashboard ranks other collectors by collection similarity, with separate artist and genre scores breaking ties. Opening a comparison shows albums on the other shelf that are missing from your own, independently of either wantlist. Known shared master IDs exclude alternative pressings of albums you already own and group multiple peer pressings into one discovery (prefer vinyl); unknown masters stay separate. Vinyl comes first, then shared artists, styles and genres. This is an explainable discovery order, not a claim that an album is required or that you will like it. Empty collections provide no basis for personal discoveries. This view does not change the existing release-based similarity score.

Wantlist crossmatches (`Collection B ∩ Wantlist A` and the reverse) and potential trades remain in a collapsed extra section. They are conversation starters, not a promise that a record is available for trade. Optional platform-frequency weighting is prepared but not enabled in the active score. Zero exact-release overlap does not imply zero shared artists or genres.

## Architecture

Flask/Jinja with plain JavaScript, SQLite, one Gunicorn web service and one import worker. No SPA framework, external chat provider or mail service. SQLite is intended for a small initial group on a single server. Account data stays behind authentication and comparison consent given during Discogs sign-in. Collection snapshots expire after six hours; the worker must run for expiry and queued imports.

Application URLs use `BASE_URL`. Deployment paths, service templates and the updater's loopback port are infrastructure defaults; adjust those deliberately for a new server. A domain move also requires DNS/TLS and a new Discogs callback. Do not change encryption/session keys during a move.

## Tests and feedback

```sh
python -m unittest discover -s tests -v
```

Tests cover OAuth/signatures, import/pagination, ownership/consent/expiry, matching, profiles, friend/chat access, administration and update guards. They use fictional data and simulated API responses, not a replacement for live OAuth/audio/browser checks.

[Report a bug or idea](https://github.com/vr4w/BlackGoldLink/issues/new/choose). English and German are welcome. [Contributing](CONTRIBUTING.md).

## Releases

Each push to `main` and each pull request runs automated tests, JavaScript/shell syntax checks and a source-only package build. A local file save or pull request does not deploy.

To approve a live update, run **Actions → Check and publish → Run workflow**, choose `main`, enable **deploy** and then approve the `production` environment. Only the tested commit is published. Once the updater is installed, the server checks for approved releases about every two minutes. It defers during imports, backs up the BGL database and rolls back code if health checks fail. Schema/dependency/import changes require a manual release. [Operations](DEPLOY.md).

No reuse license has been selected yet. The repository is public for review and feedback; this is not an additional license grant for the source or brand assets.

## Comparison consent at sign-in

The two existing sign-in checks cover collection/wantlist import, discovery and comparison among signed-in members, plus the age confirmation. There is no separate sharing checkbox after sign-in. Successful OAuth sets the existing visibility field for new and returning accounts. Previously private accounts are preserved until they complete the updated normal sign-in once. Older browser forms and in-flight OAuth requests cannot silently expand private-import consent. A versioned marker in the encrypted pending handshake distinguishes the consent copy; no database schema is changed. Pausing comparisons remains available under account controls; signing in again resumes participation.
