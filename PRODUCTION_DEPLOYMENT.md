# DNMG Portal Production Deployment Guide

This guide deploys the portal with `docker-compose.production.yml`, an external
PostgreSQL database, Redis in Docker, host Nginx TLS termination, and media
stored outside the source-code checkout.

The example paths and names below are intentionally explicit. Change the
domain, PostgreSQL hostname, and database credentials for the real server.

After deployment, follow [TESTING_AND_PRODUCTION_VERIFICATION.md](TESTING_AND_PRODUCTION_VERIFICATION.md)
for the repeatable release-test checklist.

## 1. Production layout

Use separate locations for application code, persistent uploads, and backups:

```text
/dnmg_sites/portal_dnmg/           # Git checkout; replaceable application code
/srv/dnmg_portal_data/media/      # persistent uploaded files
/srv/dnmg_portal_data/backups/    # PostgreSQL and media backups
```

Only the `media` and `backups` directories contain persistent user data. Do not
put these directories inside Git or delete them during a release.

## 2. Server prerequisites

Install and verify:

- Docker Engine and Docker Compose v2
- Git
- Nginx
- PostgreSQL client tools, including `pg_dump` and `pg_restore`
- a valid TLS certificate for the production domain

```bash
docker --version
docker compose version
git --version
pg_dump --version
nginx -v
```

The server firewall should expose only HTTP/HTTPS publicly. The Docker web
service is bound to `127.0.0.1:8000`; do not expose port 8000 or Redis to the
internet.

## 3. PostgreSQL setup

Create a dedicated production database and user on the PostgreSQL server. Use
strong credentials and permit only the application server to connect.

Example, run as a PostgreSQL administrator:

```sql
CREATE USER portal_user WITH PASSWORD 'use-a-strong-unique-password';
CREATE DATABASE portal_db OWNER portal_user;
```

For remote PostgreSQL, configure `postgresql.conf`, `pg_hba.conf`, and network
firewall rules to allow the Docker host only. Use TLS for the database connection
when the database is on another server.

## 4. Create persistent directories

```bash
sudo install -d -m 750 -o 1000 -g 1000 /srv/dnmg_portal_data/media
sudo install -d -m 700 -o "$USER" -g "$USER" /srv/dnmg_portal_data/backups
```

The Django containers run as UID/GID `1000`; they must be able to write the
media directory. Backups contain sensitive information, so keep them private.

## 5. Install or update the application checkout

For the first deployment:

```bash
sudo install -d -m 755 /dnmg_sites
sudo git clone <your-repository-url> /dnmg_sites/portal_dnmg
sudo chown -R "$USER":"$USER" /dnmg_sites/portal_dnmg
cd /dnmg_sites/portal_dnmg
```

For an existing checkout:

```bash
cd /dnmg_sites/portal_dnmg
git status
git branch --show-current
```

The deployment script refuses to update a checkout with uncommitted or
untracked files. Store server-only configuration in `.env.production`, and keep
runtime files such as media outside the Git checkout.

## 6. Configure `.env.production`

Create the file with restrictive permissions:

```bash
cd /dnmg_sites/portal_dnmg
cp .env.example .env.production
chmod 600 .env.production
```

Set at least the following values:

```dotenv
DB_NAME=portal_db
DB_USER=portal_user
DB_PASSWORD=use-a-strong-unique-password
DB_HOST=postgres.example.gov.tl
DB_PORT=5432
# Host used only by the deployment script's host-side pg_dump.
# If PostgreSQL runs on this same Linux server, use PG_DUMP_HOST=127.0.0.1.
PG_DUMP_HOST=postgres.example.gov.tl

DJANGO_SECRET_KEY=generate-a-new-long-random-secret
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=dnmg.gov.tl,www.dnmg.gov.tl
DJANGO_CSRF_TRUSTED_ORIGINS=https://dnmg.gov.tl,https://www.dnmg.gov.tl
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
# Enable only after confirming every current and future *.dnmg.gov.tl
# subdomain will always support HTTPS.
DJANGO_SECURE_HSTS_PRELOAD=false
DJANGO_AUDIT_TRUST_PROXY_HEADERS=true

REDIS_URL=redis://redis:6379/1
MEDIA_HOST_PATH=/srv/dnmg_portal_data/media

DJANGO_EMAIL_HOST=smtp.example.gov.tl
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=portal@example.gov.tl
DJANGO_EMAIL_HOST_PASSWORD=use-the-real-smtp-password
DJANGO_EMAIL_USE_TLS=true
DJANGO_DEFAULT_FROM_EMAIL=portal@example.gov.tl
```

Generate the secret key on the server; never reuse the example value:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Do not commit `.env.production`, database passwords, SMTP passwords, or backup
files to Git.

## 7. Move existing media before the first production start

If the current system already has uploads, copy them before changing the volume
mount. Preserve the full directory structure.

```bash
rsync -aHAX --info=progress2 /old/path/to/media/ /srv/dnmg_portal_data/media/
sudo chown -R 1000:1000 /srv/dnmg_portal_data/media
```

Do not move or rename these private paths independently of the database:

```text
hr/documents/
hr/downloads/
```

Their filenames are stored in PostgreSQL. The supplied Compose file mounts
`MEDIA_HOST_PATH` into `/app/media`, so the existing database references keep
working.

## 8. Configure Nginx

Copy the repository `nginx.conf` to the host Nginx site configuration and set
the media alias to the external media directory:

```nginx
location /media/ {
    alias /srv/dnmg_portal_data/media/;
    try_files $uri @media_unavailable;
}
```

Keep these blocks **above** the general `/media/` block:

```nginx
location ^~ /media/hr/documents/ { return 404; }
location ^~ /media/hr/downloads/ { return 404; }
```

They prevent direct URL access to confidential HR records. Django serves those
files only through authenticated download routes.

Validate and reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 9. First deployment

Build and run the production services using the production environment file:

```bash
cd /dnmg_sites/portal_dnmg
docker compose --env-file .env.production -f docker-compose.production.yml build
docker compose --env-file .env.production -f docker-compose.production.yml run --rm web python manage.py migrate --noinput
docker compose --env-file .env.production -f docker-compose.production.yml run --rm web python manage.py audit_database_schema --fail-on-issues
docker compose --env-file .env.production -f docker-compose.production.yml run --rm web python manage.py check --deploy
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

Never use `docker compose down -v` for this application. The `-v` option can
delete Docker volumes, including the Redis persistence volume.

## 10. Verify the deployment

```bash
curl -f http://127.0.0.1:8000/healthz/
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=100 web sync awos-sync
```

Check from a browser:

1. HTTPS redirects correctly and login works.
2. Public news images and bulletins load.
3. An HR user can download an employee document through the portal.
4. A direct URL under `/media/hr/documents/` or `/media/hr/downloads/` returns
   HTTP 404.
5. `/healthz/` returns HTTP 200.
6. The `sync` container becomes healthy after a successful station sync.
7. Forecast data appears after the sync loop warms its cache. The production
   network must be able to reach the DNMG station and forecast APIs.
8. If AWOS credentials are configured, the production host can reach the AWOS
   MariaDB server and `awos-sync` becomes healthy after its first run. AWOS is
   optional; leave all three AWOS credential settings empty when it is not in
   use.

## 11. Subsequent safe updates

The deployment script uses `docker-compose.production.yml` automatically. It
reads PostgreSQL values from `.env.production`, creates a timestamped database
dump and media archive, stops containers, pulls Git changes with `--ff-only`,
rebuilds, migrates, audits, and starts the services again.

```bash
cd /dnmg_sites/portal_dnmg
./scripts/deploy-production.sh
```

After a release that changes `nginx.conf`, run `sudo nginx -t` and reload Nginx.

## 12. Backup and restore

Back up both PostgreSQL and media. A database backup alone restores file links
but not the actual files.

Create a manual backup:

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p /srv/dnmg_portal_data/backups/$stamp
pg_dump --host=postgres.example.gov.tl --port=5432 --username=portal_user --format=custom portal_db \
  > /srv/dnmg_portal_data/backups/$stamp/postgresql.dump
tar -C /srv/dnmg_portal_data/media -czf /srv/dnmg_portal_data/backups/$stamp/media.tar.gz .
```

Restore only after stopping the application and confirming the target database:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml down
dropdb --host=postgres.example.gov.tl --username=portal_user portal_db
createdb --host=postgres.example.gov.tl --username=portal_user portal_db
pg_restore --host=postgres.example.gov.tl --username=portal_user --dbname=portal_db --clean --if-exists /path/to/postgresql.dump
tar -C /srv/dnmg_portal_data/media -xzf /path/to/media.tar.gz
sudo chown -R 1000:1000 /srv/dnmg_portal_data/media
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

The restore commands are intentionally destructive. Confirm the database name
and backup path before running them, and preferably rehearse a restore on a
staging server first.

## 13. Rollback

If a new application release fails before migrations are applied, check out the
previous Git commit and run the deployment script again.

If migrations have been applied, do not automatically reverse them on production.
First restore the PostgreSQL and media backups on staging, test the recovery,
then follow an approved rollback plan. Some schema migrations are intentionally
data-protective and may stop if legacy values cannot be mapped safely.

### Legacy HR schema repair

If a previously created database stops during `hr.0003` with
`there is no unique constraint matching given keys for referenced table
"hr_department"` or `"hr_employee"`, deploy the current code and run
`migrate` again. The preceding HR repair migrations validate that legacy IDs are
non-null and unique, then add only the missing primary keys. They do not change
department or employee data. If a repair reports NULL or duplicate IDs,
restore/correct those rows before retrying; do not fake the migration as
applied.

## 14. Routine operations

Useful commands:

```bash
# Service state
docker compose --env-file .env.production -f docker-compose.production.yml ps

# Follow application and synchronization logs
docker compose --env-file .env.production -f docker-compose.production.yml logs -f web sync

# Run the database integrity audit manually
docker compose --env-file .env.production -f docker-compose.production.yml run --rm web python manage.py audit_database_schema --fail-on-issues

# Restart only the application services; persistent media and database remain intact
docker compose --env-file .env.production -f docker-compose.production.yml restart web sync
```

Review backups regularly by restoring one to a non-production environment. Keep
backup copies on separate storage or another server.
