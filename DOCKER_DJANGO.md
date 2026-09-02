# Django Docker deployment

The Django services use an external PostgreSQL server. Redis runs in Docker and
is used only for cache entries and the distributed station-sync lock.

## Local development and testing

1. Create a local environment file from `.env.example`, then set the PostgreSQL
   connection values for your machine. If PostgreSQL runs directly on the same
   host as Docker, use `DB_HOST=host.docker.internal`, not `localhost`.
2. Build the shared Django image and apply migrations:

   ```bash
   docker compose build
   docker compose run --rm web python manage.py migrate
   ```

3. Start Django, Redis, and the five-minute sync service:

   ```bash
   docker compose up
   ```

4. The portal is available at `http://localhost:8000`. Redis is bound only to
   `127.0.0.1:6379` for host-side diagnostics. View sync logs with:

   ```bash
   docker compose logs -f sync
   ```

The sync service runs `sync_live_stations` immediately and then every five
minutes, then refreshes the public rainfall-forecast cache. When the AWOS
reader variables are configured, the separate `awos-sync` service copies the
selected Dili Airport AWOS values every five minutes. It reads MariaDB with its
dedicated `SELECT`-only account, stores UTC timestamps in PostgreSQL, and keeps
48 hours of portal observations plus 30 days of METAR reports by default. The
homepage and live-stations API only read cached/database data and never wait on
an external API.

The sync container becomes healthy after its first successful synchronization.
It becomes unhealthy if no successful run is recorded for 15 minutes, which is
an indication to inspect `docker compose logs sync`.

## Production

### Safe update command

The deployment script preserves Docker volumes and uploaded files. It makes a
timestamped PostgreSQL and media backup, stops only the application containers,
performs a fast-forward Git pull, rebuilds, migrates, audits the schema, runs
the deployment checks, and starts the services again.

On the production server, first ensure the media directory is outside the
source checkout and is mounted into `/app/media`. With `pg_dump` installed on
the server and database values in `.env.production`, run:

```bash
./scripts/deploy-production.sh
```

The script reads the database values from `.env.production` and stops before
changing anything if a fresh database or media backup cannot be created. It does **not** run
`docker compose down -v`, remove images, remove volumes, or delete media.

When PostgreSQL runs on the same Linux server, containers use
`DB_HOST=host.docker.internal`, but host-side backups use
`PG_DUMP_HOST=127.0.0.1`.

After the script completes, reload the host Nginx configuration and verify
`/healthz/`, protected HR downloads, and the sync logs.

### Manual deployment

1. Create `.env.production` from `.env.example`. Set `DJANGO_DEBUG=false`, a
   unique `DJANGO_SECRET_KEY`, the external PostgreSQL details, real hostnames,
   HTTPS CSRF origins, and secure-cookie settings. Use
   `DB_HOST=host.docker.internal` only when PostgreSQL runs directly on the same
   server as Docker; otherwise use the PostgreSQL server's DNS name or IP.
2. Ensure the external PostgreSQL server accepts connections from the Docker
   host on port 5432.
3. Build the image and apply migrations explicitly:

   ```bash
   docker compose -f docker-compose.production.yml build
   docker compose -f docker-compose.production.yml run --rm web python manage.py migrate
   ```

4. Start the services:

   ```bash
   docker compose -f docker-compose.production.yml up -d
   ```

5. Configure the host Nginx server with `nginx.conf`, changing its media
   alias to this repository's absolute `media` directory. It proxies application
   traffic only to `127.0.0.1:8000`; Redis has no published production port.
   Keep the `/media/hr/documents/` and `/media/hr/downloads/` deny rules: those
   files are served by authenticated Django download routes and must never be
   directly public.
   Ensure the bind-mounted `media/` directory is writable by the container's
   `django` user (UID/GID `1000`), for example with `chown -R 1000:1000 media`
   before the first upload.
6. After the first successful sync, verify health and the map endpoint:

   ```bash
   curl -f http://127.0.0.1:8000/healthz/
   curl -f http://127.0.0.1:8000/en/weather/api/live-stations/
   ```

Only one `sync` container must run. Redis persistence is useful for warm cache
and locking, but PostgreSQL remains the durable record of every observation.
The production Compose file bind-mounts `MEDIA_HOST_PATH` (falling back to
`./media` only when the variable is absent), so existing uploads remain
available after deployment; back up that directory along with PostgreSQL.
