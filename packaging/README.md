# Debian package

`tapir` is built as a self-contained `.deb` for Debian 13 (trixie): CPython 3.14
(via uv), a virtualenv with all dependencies, the built frontend, collected static
files and mjml are bundled under `/opt/tapir`.

| Path | Content |
|---|---|
| `/opt/tapir` | application, venv, Python, mjml (package-owned) |
| `/etc/tapir/tapir.env` | configuration, created on first install with a random `SECRET_KEY` |
| `/var/lib/tapir` | uploads, filepond files, celery beat schedule |
| `/var/log/tapir` | error logs |
| `/usr/bin/tapir-manage` | `manage.py` as the `tapir` user with the configuration loaded |

## Install from the APT repository

```sh
sudo curl -fsSLo /usr/share/keyrings/tapir-archive-keyring.gpg https://beerlesklopfer.github.io/wirgarten-tapir/tapir-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/tapir-archive-keyring.gpg] https://beerlesklopfer.github.io/wirgarten-tapir trixie main" \
  | sudo tee /etc/apt/sources.list.d/tapir.list
sudo apt update && sudo apt install tapir
```

Key fingerprint: `2B97 87BD C831 F2CD 9651  D7EA 341B FAD2 DE6A AC6C`. For a fork, replace
`beerlesklopfer.github.io/wirgarten-tapir` with `<owner>.github.io/<repo>`.

Then edit `/etc/tapir/tapir.env` (database, redis, keycloak, mail), and run:

```sh
sudo tapir-manage migrate && sudo tapir-manage parameter_definitions
sudo systemctl enable --now tapir.target
```

gunicorn listens on `GUNICORN_BIND` (default `127.0.0.1:8000`). On upgrades, the package runs `migrate` (unless
`TAPIR_MIGRATE_ON_UPGRADE` is not `true`) and restarts `tapir.target`.

## nginx

Everything is derived from the public URL. If nginx is installed and the public URL is not `localhost`, the package
writes the site `/etc/nginx/sites-available/tapir`: HTTP→HTTPS redirect, proxy to gunicorn (`GUNICORN_BIND`) and,
unless you answer no to "Serve the Keycloak login under the public URL", the Keycloak login paths `/realms/` and
`/resources/` to the internal Keycloak address. `KEYCLOAK_PUBLIC_URL` and `ALLOWED_HOSTS` follow the public URL.
The package never enables the site or reloads nginx; that stays a manual step:

```sh
sudo ln -s /etc/nginx/sites-available/tapir /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# As long as there is no certificate, the site serves HTTP only, enough to request one:
sudo certbot certonly --webroot -w /var/www/html -d tapir.example.org
sudo dpkg-reconfigure tapir          # rewrites the site with HTTPS
sudo nginx -t && sudo systemctl reload nginx
```

The certificate defaults to `/etc/letsencrypt/live/<host>/`; other paths can be set with
`sudo dpkg-reconfigure -p medium tapir`. Delete the first line of the site (`# Managed by the tapir package`) to keep
local changes; the package then leaves the file alone. Keycloak itself needs `KC_HOSTNAME=<public URL>`,
`KC_PROXY_HEADERS=xforwarded` and the redirect URI `<public URL>/*` for the `tapir-backend` client.

## Keycloak

On a fresh installation with a public URL, debconf offers to set up Keycloak on the same machine
("Set up Keycloak on this machine?", local port, e-mail of the first admin). `tapir-setup-keycloak` then
- runs Keycloak as podman container with the systemd unit `tapir-keycloak`, on `127.0.0.1:<port>` (default 8800),
  with its own PostgreSQL database `keycloak`,
- imports the realm `tapir` for the public URL with a freshly generated client secret and the Tapir login theme,
- takes the mail server for verification and password mails from `/etc/tapir/tapir.env`,
- connects Tapir (`SITE_URL`, `ALLOWED_HOSTS`, `KEYCLOAK_*`) and restarts it,
- creates the first admin (initial password in `/root/tapir-initial-admin.txt`),
- adds the Keycloak login paths to an already enabled nginx site of the domain (backup, `nginx -t`, reload) and
  checks the result.

The script is idempotent and can also be run by hand, e.g. on an existing installation:
`sudo tapir-setup-keycloak --domain tapir.example.org --port 8800 --admin-email you@example.org`.
Secrets are kept in `/etc/tapir/keycloak.env`. The Keycloak admin console is not public; reach it with
`ssh -L 8800:127.0.0.1:8800 root@<server>` and http://localhost:8800/admin (user `admin`).

## Building locally

Needs docker or podman. The build runs as root in a `debian:trixie` container
because the venv must be created at its final path `/opt/tapir`.

```sh
pnpm install && pnpm run build
packaging/build-deb.sh 0.1.0+local1   # -> build-deb/tapir_0.1.0+local1_amd64.deb
```

## CI / APT repository

`.github/workflows/debian-package.yml` (manual or on `v*` tags) builds the `.deb`,
attaches it to a `deb-<version>` prerelease and publishes a signed APT repository
with the latest `KEEP_VERSIONS` packages to GitHub Pages. One-time setup:

1. Settings → Pages → Source: **GitHub Actions**
2. Create a signing key without passphrase and store it as secret `APT_GPG_PRIVATE_KEY`:
   ```sh
   gpg --batch --passphrase '' --quick-gen-key "Tapir APT <apt@example.org>" ed25519 sign never
   gpg --armor --export-secret-keys "Tapir APT" | gh secret set APT_GPG_PRIVATE_KEY
   ```
