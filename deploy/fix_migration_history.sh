#!/usr/bin/env bash
# Fix inconsistent django_migrations history on PythonAnywhere production.
#
# Django's "migrate --fake" cannot run when history is already inconsistent,
# so this script inserts missing migration records directly into SQLite
# (metadata only — does NOT change tables or data).
#
# Usage:
#   cd /home/ghaithtravel/ghaithleads
#   bash deploy/fix_migration_history.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

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

DB="$(resolve_database_path "$PYTHON" "$PROJECT_DIR" "$DJANGO_SETTINGS_MODULE")" || {
    log "Could not find database. Check Django settings:"
    log "  grep -A6 DATABASES ghaithleads/settings.py"
    log "  find /home/ghaithtravel -name '*.sqlite3' 2>/dev/null"
    fail "Database file not found (read from ghaithleads.settings)"
}

log "Using database: ${DB}"

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
mkdir -p "$BACKUP_ROOT"
cp -a "$DB" "${BACKUP_ROOT}/db_before_migration_fix_${TIMESTAMP}.sqlite3"
log "DB backup: ${BACKUP_ROOT}/db_before_migration_fix_${TIMESTAMP}.sqlite3"

log "=== Migration state BEFORE fix ==="
"$PYTHON" "$MANAGE" showmigrations tasks dashboard display 2>&1 || true

log ""
log "Inserting missing migration records into django_migrations (metadata only)..."

sqlite3 "$DB" <<'SQL'
-- tasks: required before dashboard.0004 in the dependency chain
INSERT INTO django_migrations (app, name, applied)
SELECT 'tasks', '0002_leadtask_date_of_birth_leadtask_passport_expiry_date', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='tasks' AND name='0002_leadtask_date_of_birth_leadtask_passport_expiry_date');

INSERT INTO django_migrations (app, name, applied)
SELECT 'tasks', '0003_leadtask_return_date', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='tasks' AND name='0003_leadtask_return_date');

INSERT INTO django_migrations (app, name, applied)
SELECT 'tasks', '0004_alter_leadtask_status', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='tasks' AND name='0004_alter_leadtask_status');

INSERT INTO django_migrations (app, name, applied)
SELECT 'tasks', '0005_supplier', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='tasks' AND name='0005_supplier');

-- display: live DB already has schema from older migration names
INSERT INTO django_migrations (app, name, applied)
SELECT 'display', '0002_alter_lead_destination', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='display' AND name='0002_alter_lead_destination');

INSERT INTO django_migrations (app, name, applied)
SELECT 'display', '0003_lead_special_takeover', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='display' AND name='0003_lead_special_takeover');

INSERT INTO django_migrations (app, name, applied)
SELECT 'display', '0004_dailyreport_modified_leads_today', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='display' AND name='0004_dailyreport_modified_leads_today');

INSERT INTO django_migrations (app, name, applied)
SELECT 'display', '0005_lead_net_alter_lead_channel_alter_lead_duration_and_more', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='display' AND name='0005_lead_net_alter_lead_channel_alter_lead_duration_and_more');

INSERT INTO django_migrations (app, name, applied)
SELECT 'display', '0006_lead_email_crmnotification', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='display' AND name='0006_lead_email_crmnotification');

INSERT INTO django_migrations (app, name, applied)
SELECT 'display', '0007_alter_lead_destination', datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM django_migrations WHERE app='display' AND name='0007_alter_lead_destination');
SQL

log "Migration records inserted."

log ""
log "=== Applying new migrations (tasks 0006 — client media) ==="
"$PYTHON" "$MANAGE" migrate --noinput

log ""
log "=== Migration state AFTER fix ==="
"$PYTHON" "$MANAGE" showmigrations tasks dashboard display

log ""
log "=== Done. Finish with: ==="
log "  $PYTHON $MANAGE collectstatic --noinput"
log "  touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py"
