#!/usr/bin/env bash
# Safe, repeatable production deployment for the DNMG portal.
#
# This script deliberately never removes Docker volumes, PostgreSQL data, or
# uploaded media. It requires a new PostgreSQL dump before it stops services.

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
compose=(docker compose --env-file "$project_root/.env.production" -f "$project_root/docker-compose.production.yml")
timestamp=$(date -u +%Y%m%dT%H%M%SZ)

die() {
    echo "ERROR: $*" >&2
    exit 1
}

command -v docker >/dev/null || die "Docker is required."
command -v git >/dev/null || die "Git is required."
[[ -f "$project_root/.env.production" ]] || die "Create $project_root/.env.production first."

# .env.production is server-controlled configuration (chmod 600). Loading it
# lets the update stay a single command while using the same DB values as
# Docker Compose.
set -a
# shellcheck disable=SC1090
source "$project_root/.env.production"
set +a
[[ -n ${DB_NAME:-} && -n ${DB_USER:-} && -n ${DB_PASSWORD:-} && -n ${DB_HOST:-} ]] \
    || die "DB_NAME, DB_USER, DB_PASSWORD, and DB_HOST must be set in .env.production."
backup_root=${BACKUP_ROOT:-/srv/dnmg_portal_data/backups}
media_source=${MEDIA_SOURCE:-${MEDIA_HOST_PATH:-$project_root/media}}
pg_dump_host=${PG_DUMP_HOST:-$DB_HOST}
backup_dir="$backup_root/$timestamp"
[[ -d "$media_source" ]] || die "MEDIA_SOURCE does not exist: $media_source"

cd "$project_root"
git diff --quiet || die "The production checkout has uncommitted tracked changes. Commit or stash them first."
git diff --cached --quiet || die "The production checkout has staged changes. Commit or unstage them first."

umask 077
mkdir -p "$backup_dir"

echo "Creating PostgreSQL backup..."
PGPASSWORD="$DB_PASSWORD" pg_dump \
    --host="$pg_dump_host" \
    --port="${DB_PORT:-5432}" \
    --username="$DB_USER" \
    --format=custom \
    "$DB_NAME" > "$backup_dir/postgresql.dump"
[[ -s "$backup_dir/postgresql.dump" ]] || die "PostgreSQL backup is empty; deployment stopped."

echo "Creating media backup..."
tar -C "$media_source" -czf "$backup_dir/media.tar.gz" .

echo "Stopping application containers (volumes are preserved)..."
"${compose[@]}" down --remove-orphans

echo "Pulling the approved Git branch..."
git pull --ff-only

echo "Building the production image..."
"${compose[@]}" build --pull

echo "Applying migrations and production checks..."
"${compose[@]}" run --rm web python manage.py migrate --noinput
"${compose[@]}" run --rm web python manage.py audit_database_schema --fail-on-issues
"${compose[@]}" run --rm web python manage.py check --deploy

echo "Starting application services..."
"${compose[@]}" up -d
"${compose[@]}" ps

cat <<EOF

Deployment completed.
Backups created in: $backup_dir

Next checks:
  curl -f http://127.0.0.1:8000/healthz/
  docker compose --env-file .env.production -f docker-compose.production.yml logs -f web sync

Reload host Nginx after deploying nginx.conf. Do not expose /media/hr/documents/
or /media/hr/downloads/ directly.
EOF
