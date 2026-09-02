# Portal DNMG

Portal DNMG is a Django application for the National Directorate of Meteorology and Geophysics. It provides public weather, climate, marine, seismic, news, and bulletin information, plus authenticated staff workflows for weather operations, content management, and HR.

## Project layout

- `config/` — Django settings, root URLs, WSGI/ASGI, and health checks.
- `core/` — public homepage and shared site behavior.
- `weather/` — weather stations, observations, forecasts, warnings, and synchronization services.
- `seismic/` — USGS earthquake integration, cached provider data, public explorer, and homepage summary.
- `cms/` — public news, bulletins, careers, and staff content management.
- `hr/` — employee records, documents, reports, and HR permissions.
- `users/` — authentication, roles, permissions, profiles, and audit logging.
- `templates/` — Django templates grouped by application.
- `static/` — application CSS, JavaScript, maps, and vendored browser assets.

Keep provider/network code in an application's `services.py`, request validation in a small filter/query module, and presentation logic in views/templates. Public read-only provider data should be cached and normalized before it reaches a template or API response.

### Shared UI and content conventions

- Public navigation lives in `templates/components/public_navigation.html`.
  Add or reorganize public menu items there instead of duplicating navigation
  markup in `base.html`.
- Public warnings use `weather.queries.current_public_warnings()` and the
  reusable templates under `templates/components/public_alert_*.html`.
- Shared admin rich-text behavior lives in
  `static/js/admin-content-editor.js`; editor markup belongs in reusable
  components such as `templates/components/admin_rich_text_field.html`.
- CMS rich text must pass through `cms/sanitizers.py` before storage or safe
  public rendering. Do not mark editor HTML safe without sanitizing it.
- Tetun and Portuguese translations live in `locale/tet/` and `locale/pt/`.
  Docker builds compile `.po` catalogs automatically. After editing a catalog,
  rebuild the web image and verify the affected language in the browser.

## Local Docker workflow

1. Create a local environment file and configure a local PostgreSQL database:

   ```bash
   cp .env.example .env
   mkdir -p media
   sudo chown -R 1000:1000 media
   ```

   Local uploads stay in this project-level `media/` directory, which Compose
   mounts at `/app/media`. The container runs Django as UID/GID `1000`, so the
   ownership step keeps that directory writable while uploaded contents remain
   excluded from Git.

2. Build the application image and apply migrations:

   ```bash
   docker compose build
   docker compose run --rm web python manage.py migrate
   ```

3. Start the web, Redis, and station synchronization services:

   ```bash
   docker compose up
   ```

The application is available at <http://localhost:8000>. Local Docker settings use `.env`; production uses `.env.production` with `docker-compose.production.yml`. Never commit either environment file.

## Tests and checks

Run checks and tests inside the same Docker image used by the application:

```bash
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test
```

Before committing model or translation changes, also run:

```bash
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose build web
```

For a focused seismic test run:

```bash
docker compose run --rm web python manage.py test seismic
```

If a previous interrupted test run leaves the PostgreSQL test database behind, use `--keepdb` or remove only that test database through the PostgreSQL administrator tools. Never remove the application database or Docker volumes to fix a test issue.

## Migrations

Create migrations after changing database models, review the generated file, and apply them in the container:

```bash
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py migrate
```

The seismic module currently stores no local event model; it reads USGS GeoJSON through a cached service, so seismic-only changes do not require a migration.

## Production releases

Use the guarded deployment script from the production checkout:

```bash
./scripts/deploy-production.sh
```

It creates database and media backups, performs a fast-forward pull, rebuilds the image, applies migrations, runs deployment checks, and starts the services. Read [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) before the first deployment and [TESTING_AND_PRODUCTION_VERIFICATION.md](TESTING_AND_PRODUCTION_VERIFICATION.md) for release verification.

## Configuration and security

Production must set a unique `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, explicit allowed hosts, HTTPS CSRF origins, secure cookies, and production database/email settings. Confidential HR paths under `/media/hr/documents/` and `/media/hr/downloads/` must remain blocked by Nginx and served only through authenticated Django views.

The USGS earthquake service is an external dependency. It uses a short timeout, validates provider responses, normalizes malformed records out, and caches successful results in Redis when available.
