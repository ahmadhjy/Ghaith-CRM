#!/usr/bin/env bash
# Fix inconsistent django_migrations history (PostgreSQL or SQLite).
#
# Usage:
#   cd /home/ghaithtravel/ghaithleads
#   bash deploy/fix_migration_history.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/home/ghaithtravel/ghaithleads"
VENV_DIR="/home/ghaithtravel/djangenv"
BACKUP_ROOT="/home/ghaithtravel/deploy-backups"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ghaithleads.settings}"

PYTHON="${VENV_DIR}/bin/python"
MANAGE="${PROJECT_DIR}/manage.py"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { log "ERROR: $*"; exit 1; }

[[ -f "$MANAGE" ]] || fail "manage.py not found"
[[ -x "$PYTHON" ]] || fail "Python not found: $PYTHON"

cd "$PROJECT_DIR"
export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$BACKUP_ROOT"

log "Backing up database..."
BACKUP_FILE="$("$PYTHON" "${SCRIPT_DIR}/backup_database.py" "$BACKUP_ROOT" "before_migration_fix_${TIMESTAMP}")"
log "DB backup: ${BACKUP_FILE}"

DB_ENGINE="$("$PYTHON" -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '${DJANGO_SETTINGS_MODULE}')
django.setup()
from django.conf import settings
print(settings.DATABASES['default']['ENGINE'])
")"
log "Database engine: ${DB_ENGINE}"

log "=== Migration state BEFORE fix ==="
"$PYTHON" "$MANAGE" showmigrations tasks dashboard display 2>&1 || true

log ""
log "Inserting missing migration records (metadata only, no schema changes)..."
"$PYTHON" "${SCRIPT_DIR}/fix_migrations_db.py"

log ""
log "=== Applying new migrations (e.g. tasks 0006) ==="
"$PYTHON" "$MANAGE" migrate --noinput

log ""
log "=== Migration state AFTER fix ==="
"$PYTHON" "$MANAGE" showmigrations tasks dashboard display

log ""
log "=== Done. Finish with: ==="
log "  $PYTHON $MANAGE collectstatic --noinput"
log "  touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py"
