# DNMG Portal Testing and Production Verification

Use this checklist for every release. Do not run development tests against the
production database. Production commands use `/dnmg_sites/portal_dnmg` and
`.env.production`.

## 1. Development checks before pushing code

Run these from your development checkout. Django creates a temporary test
database named `test_<DB_NAME>` and removes it when the test run finishes.

```bash
cd "/path/to/portal_dnmg"
docker compose build web
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py test
```

Expected result:

```text
No changes detected
Ran ... tests
OK
```

If tests ask whether to delete an existing `test_...` database, answer `yes`
only when it is the disposable test database, never the real development or
production database.

## 2. Deploy on the production server

Confirm `.env.production` has production HTTPS settings:

```dotenv
DJANGO_DEBUG=false
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
MEDIA_HOST_PATH=/srv/dnmg_portal_data/media
```

Deploy with the script. It creates PostgreSQL and media backups, builds the
images, applies migrations, audits the schema, checks deployment settings, and
starts the services.

```bash
cd /dnmg_sites/portal_dnmg
sudo ./scripts/deploy-production.sh
```

Expected deployment messages include:

```text
Schema audit passed: all reviewed tables have valid PK/FK metadata and data rules.
Deployment completed.
```

Never use `docker compose down -v`; `-v` can delete Docker volumes.

## 3. Database verification

Run this after a deployment or database migration:

```bash
cd /dnmg_sites/portal_dnmg
sudo docker compose --env-file .env.production -f docker-compose.production.yml run --rm web python manage.py showmigrations
sudo docker compose --env-file .env.production -f docker-compose.production.yml run --rm web python manage.py audit_database_schema --fail-on-issues
```

Every applied migration should show `[X]`. The audit must end with:

```text
Schema audit passed: all reviewed tables have valid PK/FK metadata and data rules.
```

Do not use `--fake` for migrations unless a developer has investigated the
database state and specifically instructs you to do so.

## 4. Django production-security check

```bash
cd /dnmg_sites/portal_dnmg
sudo docker compose --env-file .env.production -f docker-compose.production.yml run --rm web python manage.py check --deploy
```

The HTTPS redirect, session-cookie, and CSRF-cookie warnings must not appear.
The optional `security.W021` HSTS preload warning may remain. Do not enable HSTS
preload unless every current and future `*.dnmg.gov.tl` subdomain will always
support HTTPS.

## 5. Service and health checks

Wait about one minute after `up -d`, then run:

```bash
cd /dnmg_sites/portal_dnmg
curl -f -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/healthz/
sudo docker compose --env-file .env.production -f docker-compose.production.yml ps
sudo docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=100 web sync awos-sync
```

Expected result:

- Health endpoint returns success (HTTP 200).
- `web` is running and bound only to `127.0.0.1:8000`.
- `redis` is healthy.
- `sync` moves from `health: starting` to healthy after its first successful
  synchronization. It can take up to five minutes.
- When `AWOS_DILI_DATABASE_URL`, `AWOS_DILI_USER`, and
  `AWOS_DILI_PASSWORD` are configured and the production host is on the AWOS
  network, `awos-sync` becomes healthy after its first successful run and then
  refreshes every five minutes. If the AWOS integration is intentionally not
  configured, it logs that synchronization is disabled and remains a healthy
  no-op.
- Logs contain no repeated traceback, database, permission, or network errors.

For ongoing log viewing, press `Ctrl+C` to stop:

```bash
sudo docker compose --env-file .env.production -f docker-compose.production.yml logs -f web sync awos-sync
```

## 6. Nginx and HTTPS checks

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -I http://dnmg.gov.tl
curl -I https://dnmg.gov.tl
```

Expected result:

- HTTP returns a `301` or `308` redirect to HTTPS.
- HTTPS returns `200`, `302`, or another expected application response.
- The browser shows a valid Certbot certificate without a warning.

## 7. Browser acceptance test

Test these from a normal browser:

1. Open `https://dnmg.gov.tl` and verify HTTP redirects to HTTPS.
2. Log in with an authorized account, then log out and log in again.
3. Open public news, bulletins, careers, forecasts, and observations.
4. Create and edit one safe test record only if your deployment procedure allows it.
5. Download an authorized HR document through the portal.
6. Confirm a direct URL under `/media/hr/documents/` or `/media/hr/downloads/`
   returns `404`; private HR files must not be publicly served by Nginx.
7. Upload a safe test media file, confirm it displays correctly, then remove the
   test record/file through the application if it is no longer needed.

## 8. Backup confirmation

The deployment script creates backups under:

```text
/srv/dnmg_portal_data/backups/<timestamp>/
```

Confirm the newest directory contains both the PostgreSQL backup and media
backup before considering a release complete:

```bash
sudo ls -lah /srv/dnmg_portal_data/backups
```

Keep backups outside the Git checkout and restrict their permissions because
they can contain personal and confidential data.

## 9. When a check fails

- Stop before running the next deployment step.
- Copy the complete command output, including the first error line.
- Do not delete the database, run destructive Docker commands, or fake
  migrations to bypass an error.
- Restore from the latest backup only after the problem has been diagnosed.
