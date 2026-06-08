#!/usr/bin/env bash
# Fix inconsistent django_migrations history on PythonAnywhere production.
# Safe when the database schema already matches (live site was running fine).
#
# Usage:
#   cd /home/ghaithtravel/ghaithleads
#   bash deploy/fix_migration_history.sh
#
set -euo pipefail

PROJECT_DIR="/home/ghaithtravel/ghaithleads"
VENV_DIR="/home/ghaithtravel/djangenv"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ghaithleads.settings}"

PYTHON="${VENV_DIR}/bin/python"
MANAGE="${PROJECT_DIR}/manage.py"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { log "ERROR: $*"; exit 1; }

[[ -f "$MANAGE" ]] || fail "manage.py not found"
[[ -x "$PYTHON" ]] || fail "Python not found: $PYTHON"

cd "$PROJECT_DIR"

log "=== Migration state BEFORE fix ==="
"$PYTHON" "$MANAGE" showmigrations tasks dashboard display 2>&1 || true

log ""
log "Recording tasks 0002–0005 as applied (--fake)."
log "This only updates django_migrations; it does NOT change your data."
log "Your live DB already has these schema changes from prior deploys."
"$PYTHON" "$MANAGE" migrate tasks 0005 --fake

log ""
log "=== Applying any remaining real migrations (e.g. tasks 0006) ==="
"$PYTHON" "$MANAGE" migrate --noinput

log ""
log "=== Migration state AFTER fix ==="
"$PYTHON" "$MANAGE" showmigrations tasks dashboard display

log ""
log "=== Done. Finish deploy with: ==="
log "  $PYTHON $MANAGE collectstatic --noinput"
log "  touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py"
