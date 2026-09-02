# AGENTS.md

This repository is the Portal DNMG Django application. Use the project docs below as the primary source of truth for structure, deployment, and verification.

## Start here

- [README.md](README.md): local workflow, testing commands, migration guidance, deployment entry points.
- [DOCKER_DJANGO.md](DOCKER_DJANGO.md): Docker, PostgreSQL, Redis, sync service behavior, and production constraints.
- [TESTING_AND_PRODUCTION_VERIFICATION.md](TESTING_AND_PRODUCTION_VERIFICATION.md): release verification and safety checks.
- [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md): production deployment process and operational safeguards.

## Project layout

- `config/`: Django settings, root URLs, WSGI/ASGI, and overall app wiring.
- `core/`: public homepage and shared site behavior.
- `weather/`: stations, observations, forecast logic, and sync jobs.
- `seismic/`: USGS earthquake integration and cached public data.
- `cms/`: public information, bulletins, content, and job postings.
- `hr/`: employee records, permissions, document access, and HR workflows.
- `users/`: authentication, roles, middleware, and audit logging.
- `templates/`: app-specific Django templates.
- `static/`: frontend CSS, JS, assets, and vendored browser resources.

## Working conventions

- Keep provider or network integrations in each app's `services.py`.
- Keep request validation in small filters or query helpers instead of spreading it through views.
- Keep presentation logic in templates/views; do not mix heavy business logic into templates.
- Treat public provider data as read-only cacheable data: normalize, validate, and cache before exposing it through templates or APIs.
- Do not remove Docker volumes or application databases as a troubleshooting step. Use the project's documented recovery steps instead.
- Never commit `.env` or `.env.production` files. Keep secrets in local environment files only.

## Local development and verification

Use Docker for the app environment and run checks inside the project container:

```bash
docker compose build
docker compose run --rm web python manage.py migrate
docker compose up
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test
```

Focused tests are also common:

```bash
docker compose run --rm web python manage.py test seismic
```

If a test database is left behind after an interrupted run, prefer `--keepdb` or a controlled PostgreSQL cleanup rather than deleting the app database or Docker volumes.

## Production safety

- Production requires a unique `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, explicit `ALLOWED_HOSTS`, trusted CSRF origins, and secure cookie settings.
- The deployment script is the preferred production update path:

```bash
./scripts/deploy-production.sh
```

- Do not use `docker compose down -v` in this project; it can destroy data volumes.
- Treat the `media/` directory and PostgreSQL data as durable state. Back them up as part of a production release.
- The HR document paths under `/media/hr/documents/` and `/media/hr/downloads/` must remain protected by Django and Nginx; they should not be served directly as public static files.

## Preferred approach for changes

1. Start by reading the relevant app and the project docs above.
2. Keep the change within the existing app boundary and follow the repository's Django patterns.
3. Add or update tests for the affected behavior when the change is user-facing or logic-heavy.
4. Verify using the smallest relevant Docker-based Django command before finishing.

This repository favors explicit operational safety over shortcuts, especially around deployment, caching, and database lifecycle.
