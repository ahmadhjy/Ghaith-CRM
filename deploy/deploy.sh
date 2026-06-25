#!/usr/bin/env bash
# =============================================================================
# Ghaith CRM — production-safe deploy script for PythonAnywhere
#
# Usage (from PythonAnywhere Bash console):
#   cd /home/ghaithtravel/ghaithleads
#   bash deploy/deploy.sh
#
# Options:
#   --dry-run       Show what would happen; do not change anything
#   --skip-migrate  Skip database migrations (code/static only)
#   --skip-backup   Skip pre-deploy backup (not recommended on production)
#   --help          Show help
#
# Exit codes: 0 = success, non-zero = failed (deployment stopped)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/pythonanywhere.env"

DRY_RUN=0
SKIP_MIGRATE=0
SKIP_BACKUP=0

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { log "ERROR: $*"; exit 1; }

usage() {
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)      DRY_RUN=1; shift ;;
        --skip-migrate) SKIP_MIGRATE=1; shift ;;
        --skip-backup)  SKIP_BACKUP=1; shift ;;
        --help|-h)      usage ;;
        *) fail "Unknown option: $1 (use --help)" ;;
    esac
done

[[ -f "$CONFIG_FILE" ]] || fail "Missing ${CONFIG_FILE}. Copy deploy/pythonanywhere.env.example and edit it."

# shellcheck source=/dev/null
source "$CONFIG_FILE"

: "${PA_USERNAME:?Set PA_USERNAME in pythonanywhere.env}"
: "${PA_DOMAIN:?Set PA_DOMAIN in pythonanywhere.env}"
: "${PA_WSGI_FILE:?Set PA_WSGI_FILE in pythonanywhere.env}"
: "${PROJECT_DIR:?Set PROJECT_DIR in pythonanywhere.env}"
: "${VENV_DIR:?Set VENV_DIR in pythonanywhere.env}"
: "${DJANGO_SETTINGS_MODULE:?Set DJANGO_SETTINGS_MODULE in pythonanywhere.env}"
: "${GIT_REMOTE:=origin}"
: "${GIT_BRANCH:=main}"
: "${BACKUP_ROOT:=/home/${PA_USERNAME}/deploy-backups}"
: "${SYNC_SYSTEM_TO_GHAITHLEADS:=yes}"
: "${REPO_SYSTEM_DIR:=system}"
: "${PROD_SETTINGS_PACKAGE:=ghaithleads}"
: "${RELOAD_METHOD:=touch}"
: "${REQUIRE_CLEAN_GIT:=no}"
: "${RUN_COLLECTSTATIC:=no}"

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
LOG_DIR="${BACKUP_ROOT}/logs"
DEPLOY_LOG="${LOG_DIR}/deploy_${TIMESTAMP}.log"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

mkdir -p "$LOG_DIR"

exec > >(tee -a "$DEPLOY_LOG") 2>&1

log "========== Ghaith CRM deploy started =========="
log "Log file: ${DEPLOY_LOG}"
[[ "$DRY_RUN" -eq 1 ]] && log "MODE: DRY RUN (no changes will be made)"

run() {
    log "+ $*"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        return 0
    fi
    "$@"
}

# ── Preflight ───────────────────────────────────────────────────────────────
[[ -d "$PROJECT_DIR" ]] || fail "PROJECT_DIR does not exist: ${PROJECT_DIR}"
[[ "$(realpath "$PROJECT_DIR")" == "$(realpath "$PWD")" ]] || \
    fail "Run this script from the project root (${PROJECT_DIR}). Current: ${PWD}"

[[ -d "$VENV_DIR" ]] || fail "Virtualenv not found: ${VENV_DIR}. Set VENV_DIR in pythonanywhere.env (see Web → Virtualenv path)."

PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"
[[ -x "$PYTHON" ]] || fail "Python not found in venv: ${PYTHON}"

MANAGE_PY="${PROJECT_DIR}/manage.py"
[[ -f "$MANAGE_PY" ]] || fail "manage.py not found at ${MANAGE_PY}"

[[ -f "$PROJECT_DIR/requirements.txt" ]] || fail "requirements.txt not found"

if [[ -f "$PA_WSGI_FILE" ]]; then
    if ! grep -q "ghaithleads.settings" "$PA_WSGI_FILE" 2>/dev/null; then
        log "WARNING: ${PA_WSGI_FILE} may not reference ghaithleads.settings — verify WSGI config"
    fi
    if ! grep -q "${PROJECT_DIR}" "$PA_WSGI_FILE" 2>/dev/null; then
        log "WARNING: ${PA_WSGI_FILE} may not reference ${PROJECT_DIR}"
    fi
else
    log "WARNING: WSGI file not found at ${PA_WSGI_FILE}"
fi

export DJANGO_SETTINGS_MODULE

# ── Backup ──────────────────────────────────────────────────────────────────
backup_file() {
    local src="$1"
    local dest_dir="$2"
    if [[ -e "$src" ]]; then
        run mkdir -p "$dest_dir"
        run cp -a "$src" "${dest_dir}/"
        log "Backed up: ${src}"
    else
        log "Skip backup (not found): ${src}"
    fi
}

if [[ "$SKIP_BACKUP" -eq 0 ]]; then
    log "--- Creating pre-deploy backup in ${BACKUP_DIR} ---"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        mkdir -p "$BACKUP_DIR"
    fi

    # PostgreSQL or SQLite — via Django settings
    if [[ "$DRY_RUN" -eq 0 && -f "${SCRIPT_DIR}/backup_database.py" ]]; then
        log "Backing up database (PostgreSQL/SQLite)..."
        BACKUP_FILE="$("$PYTHON" "${SCRIPT_DIR}/backup_database.py" "$BACKUP_DIR" "deploy_${TIMESTAMP}")"
        log "DB backup: ${BACKUP_FILE}"
    else
        backup_file "${PROJECT_DIR}/db.sqlite3" "$BACKUP_DIR"
    fi

    MEDIA_PATH="${MEDIA_DIR:-${PROJECT_DIR}/media}"
    if [[ "${BACKUP_MEDIA:-no}" == "yes" && -d "$MEDIA_PATH" ]]; then
        MEDIA_SIZE="$(du -sh "$MEDIA_PATH" 2>/dev/null | cut -f1 || echo '?')"
        log "Backing up media (${MEDIA_SIZE}) — can take several minutes, please wait..."
        backup_file "$MEDIA_PATH" "$BACKUP_DIR"
    else
        log "Skip media backup (BACKUP_MEDIA=${BACKUP_MEDIA:-no} or folder missing)"
    fi

    backup_file "${PROJECT_DIR}/${PROD_SETTINGS_PACKAGE}/settings.py" "$BACKUP_DIR"
    backup_file "${PROJECT_DIR}/local_settings.py" "$BACKUP_DIR"

    if [[ -d "${PROJECT_DIR}/.git" && "$DRY_RUN" -eq 0 ]]; then
        git -C "$PROJECT_DIR" rev-parse HEAD > "${BACKUP_DIR}/git_commit_before.txt" 2>/dev/null || true
        git -C "$PROJECT_DIR" status --short > "${BACKUP_DIR}/git_status_before.txt" 2>/dev/null || true
    fi
    log "Backup complete"
else
    log "WARNING: Skipping backup (--skip-backup)"
fi

# ── Git pull ────────────────────────────────────────────────────────────────
if [[ -d "${PROJECT_DIR}/.git" ]]; then
    # Production uses PostgreSQL; a tracked/local db.sqlite3 must not block git pull.
    if [[ -e "${PROJECT_DIR}/db.sqlite3" ]]; then
        quarantine="${PROJECT_DIR}/db.sqlite3.local-backup.${TIMESTAMP}"
        log "--- Quarantining db.sqlite3 → ${quarantine} (live DB is PostgreSQL) ---"
        if [[ "$DRY_RUN" -eq 0 ]]; then
            mv "${PROJECT_DIR}/db.sqlite3" "$quarantine"
        fi
    fi

    log "--- Pulling latest code from ${GIT_REMOTE}/${GIT_BRANCH} ---"

    if [[ "$REQUIRE_CLEAN_GIT" == "yes" ]]; then
        if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain 2>/dev/null)" ]]; then
            fail "Uncommitted changes detected. Commit, stash, or set REQUIRE_CLEAN_GIT=no in config."
        fi
    fi

    run git -C "$PROJECT_DIR" remote get-url "$GIT_REMOTE" || \
        run git -C "$PROJECT_DIR" remote add "$GIT_REMOTE" "${GIT_REPO_URL:-https://github.com/ahmadhjy/Ghaith-CRM.git}"

    run git -C "$PROJECT_DIR" fetch "$GIT_REMOTE" "$GIT_BRANCH"
    log "Commits to be deployed:"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        git -C "$PROJECT_DIR" log --oneline HEAD.."${GIT_REMOTE}/${GIT_BRANCH}" 2>/dev/null | head -20 || true
    fi

    run git -C "$PROJECT_DIR" merge --ff-only "${GIT_REMOTE}/${GIT_BRANCH}" || \
        fail "git merge failed (non-fast-forward). Resolve manually — do NOT delete the project folder."
else
    fail "No .git directory in ${PROJECT_DIR}. Run: bash deploy/setup_git_on_pythonanywhere.sh"
fi

# ── Sync system/ → ghaithleads/ (preserve production settings.py) ─────────────
if [[ "$SYNC_SYSTEM_TO_GHAITHLEADS" == "yes" && -d "${PROJECT_DIR}/${REPO_SYSTEM_DIR}" ]]; then
    log "--- Syncing ${REPO_SYSTEM_DIR}/ → ${PROD_SETTINGS_PACKAGE}/ (preserving settings.py) ---"
    SETTINGS_BACKUP=""
    if [[ -f "${PROJECT_DIR}/${PROD_SETTINGS_PACKAGE}/settings.py" ]]; then
        if [[ "$DRY_RUN" -eq 0 ]]; then
            SETTINGS_BACKUP="$(mktemp)"
            cp "${PROJECT_DIR}/${PROD_SETTINGS_PACKAGE}/settings.py" "$SETTINGS_BACKUP"
        fi
    fi

    if [[ "$DRY_RUN" -eq 0 ]]; then
        mkdir -p "${PROJECT_DIR}/${PROD_SETTINGS_PACKAGE}"
        rsync -a --delete \
            --exclude='settings.py' \
            --exclude='local_settings.py' \
            --exclude='__pycache__/' \
            --exclude='*.pyc' \
            "${PROJECT_DIR}/${REPO_SYSTEM_DIR}/" \
            "${PROJECT_DIR}/${PROD_SETTINGS_PACKAGE}/"
        if [[ -n "$SETTINGS_BACKUP" && -f "$SETTINGS_BACKUP" ]]; then
            cp "$SETTINGS_BACKUP" "${PROJECT_DIR}/${PROD_SETTINGS_PACKAGE}/settings.py"
            rm -f "$SETTINGS_BACKUP"
        fi
        log "Sync complete; production settings.py preserved"
    fi
fi

# ── Patch production settings (notifications app, VAPID) ───────────────────
SETTINGS_PY="${PROJECT_DIR}/${PROD_SETTINGS_PACKAGE}/settings.py"
if [[ -f "$SETTINGS_PY" ]]; then
    log "--- Patching production settings.py (notifications / VAPID) ---"
    run "$PYTHON" "${SCRIPT_DIR}/patch_production_settings.py" "$SETTINGS_PY"
fi

# ── Dependencies ────────────────────────────────────────────────────────────
log "--- Installing/updating Python dependencies ---"
run "$PIP" install -r "${PROJECT_DIR}/requirements.txt"

# ── Clean cache (never touches db or media) ─────────────────────────────────
log "--- Removing __pycache__ and .pyc files ---"
if [[ "$DRY_RUN" -eq 0 ]]; then
    find "$PROJECT_DIR" -type d -name '__pycache__' -not -path '*/.git/*' -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_DIR" -type f -name '*.pyc' -not -path '*/.git/*' -delete 2>/dev/null || true
fi

# ── Django checks ───────────────────────────────────────────────────────────
log "--- Running Django system checks ---"
run "$PYTHON" "$MANAGE_PY" check

# ── Migrations (never deletes migration files) ──────────────────────────────
if [[ "$SKIP_MIGRATE" -eq 0 ]]; then
    log "--- Migration plan (pending migrations only) ---"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        "$PYTHON" "$MANAGE_PY" showmigrations --plan | tee -a "$DEPLOY_LOG" || fail "showmigrations failed"
    fi

    log "--- Applying migrations (safe: only runs pending migrations) ---"
    run "$PYTHON" "$MANAGE_PY" migrate --noinput

    log "--- Ensuring auth_user CRM columns (is_sales, administration) ---"
    run "$PYTHON" "$MANAGE_PY" ensure_user_crm_columns
else
    log "Skipping migrations (--skip-migrate)"
fi

# ── Static files ────────────────────────────────────────────────────────────
# PythonAnywhere serves /static/ directly from PROJECT_DIR/static/.
# NEVER run collectstatic --clear here — STATIC_ROOT equals that folder and
# --clear deletes all theme CSS/JS (only Django admin files get re-collected).
verify_theme_static() {
    local missing=0
    local f
    for f in css/navbar-unified.css css/requests-modern.css css/app-modern-global.css JS/navbar-unified.js; do
        if [[ ! -f "${PROJECT_DIR}/static/${f}" ]]; then
            log "WARNING: Missing static/${f}"
            missing=1
        fi
    done
    if [[ "$missing" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
        log "Restoring static/ from git..."
        git -C "$PROJECT_DIR" checkout HEAD -- static/ 2>/dev/null || true
    fi
}

verify_theme_static

if [[ "$RUN_COLLECTSTATIC" == "yes" ]]; then
    log "WARNING: RUN_COLLECTSTATIC=yes can wipe theme CSS on PythonAnywhere."
    log "Collecting static files (without --clear)..."
    run "$PYTHON" "$MANAGE_PY" collectstatic --noinput
else
    log "Static files: served from ${PROJECT_DIR}/static/ (collectstatic skipped)"
fi

# ── Reload web app ──────────────────────────────────────────────────────────
reload_webapp() {
    log "--- Reloading PythonAnywhere web app (${PA_DOMAIN}) ---"
    case "$RELOAD_METHOD" in
        touch)
            run touch "$PA_WSGI_FILE"
            ;;
        api)
            local token="${PA_API_TOKEN:-${API_TOKEN:-}}"
            [[ -n "$token" ]] || fail "API reload requires PA_API_TOKEN or API_TOKEN in environment"
            if [[ "$DRY_RUN" -eq 0 ]]; then
                local code
                code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
                    -H "Authorization: Token ${token}" \
                    "https://www.pythonanywhere.com/api/v0/user/${PA_USERNAME}/webapps/${PA_DOMAIN}/reload/")
                [[ "$code" == "200" ]] || fail "API reload failed (HTTP ${code})"
            fi
            ;;
        both)
            RELOAD_METHOD="touch" reload_webapp
            RELOAD_METHOD="api" reload_webapp
            ;;
        *)
            fail "Invalid RELOAD_METHOD: ${RELOAD_METHOD}"
            ;;
    esac
    log "Web app reload triggered"
}

reload_webapp

if [[ "$DRY_RUN" -eq 0 ]]; then
    git -C "$PROJECT_DIR" rev-parse HEAD > "${BACKUP_DIR}/git_commit_after.txt" 2>/dev/null || true
fi

if [[ ! -f "${PROJECT_DIR}/deploy/vapid.env" ]]; then
    log "NOTE: Browser push not configured. Run on server:"
    log "  python manage.py generate_vapid_keys --write"
    log "  Then add _load_vapid_env() from deploy/ghaithleads_settings_production.SNIPPET.py to ghaithleads/settings.py"
fi

log "========== Deploy finished successfully =========="
log "Site: https://${PA_DOMAIN}/"
log "Backup: ${BACKUP_DIR}"
log "Log: ${DEPLOY_LOG}"
