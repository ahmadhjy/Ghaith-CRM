#!/usr/bin/env bash
# =============================================================================
# ONE-TIME bootstrap for PythonAnywhere when /home/ghaithtravel/ghaithleads
# is NOT yet a git repository.
#
# Safe: backs up db.sqlite3, media/, and ghaithleads/settings.py first.
# Does NOT delete the project folder or database.
#
# Usage (PythonAnywhere Bash):
#   cd /home/ghaithtravel/ghaithleads
#   bash deploy/bootstrap_pythonanywhere.sh
# =============================================================================
set -euo pipefail

PROJECT_DIR="/home/ghaithtravel/ghaithleads"
STAGING_DIR="/home/ghaithtravel/Ghaith-CRM-staging"
GIT_REPO_URL="https://github.com/ahmadhjy/Ghaith-CRM.git"
GIT_BRANCH="main"
VENV_DIR="/home/ghaithtravel/djangenv"
DJANGO_SETTINGS_MODULE="ghaithleads.settings"
BACKUP_ROOT="/home/ghaithtravel/deploy-backups"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_DIR="${BACKUP_ROOT}/bootstrap_${TIMESTAMP}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { log "ERROR: $*"; exit 1; }

[[ "$(pwd)" == "$PROJECT_DIR" ]] || fail "Run from ${PROJECT_DIR} (cd ${PROJECT_DIR})"
[[ -d "$VENV_DIR" ]] || fail "Virtualenv not found: ${VENV_DIR}"

if [[ -d "${PROJECT_DIR}/.git" ]]; then
    log "Git already initialized. Use: bash deploy/deploy.sh"
    exit 0
fi

log "=== Bootstrap started ==="
log "Backup directory: ${BACKUP_DIR}"
mkdir -p "$BACKUP_DIR"

# ── 1. Backup production-critical files ─────────────────────────────────────
log "Backing up database, media, and settings..."
[[ -f "${PROJECT_DIR}/db.sqlite3" ]] && cp -a "${PROJECT_DIR}/db.sqlite3" "${BACKUP_DIR}/"
[[ -d "${PROJECT_DIR}/media" ]]       && cp -a "${PROJECT_DIR}/media" "${BACKUP_DIR}/"
[[ -f "${PROJECT_DIR}/ghaithleads/settings.py" ]] && cp -a "${PROJECT_DIR}/ghaithleads/settings.py" "${BACKUP_DIR}/"
log "Backup done."

# ── 2. Clone GitHub repo to staging (does not touch live folder structure) ──
if [[ ! -d "${STAGING_DIR}/.git" ]]; then
    log "Cloning ${GIT_REPO_URL} → ${STAGING_DIR}"
    git clone --branch "$GIT_BRANCH" "$GIT_REPO_URL" "$STAGING_DIR"
else
    log "Updating staging clone..."
    git -C "$STAGING_DIR" pull origin "$GIT_BRANCH"
fi

COMMIT="$(git -C "$STAGING_DIR" rev-parse --short HEAD)"
log "Staging at commit: ${COMMIT}"

# ── 3. Rsync code into production (never touch db / media / settings) ───────
log "Syncing application code (preserving db, media, settings)..."
rsync -a --delete \
    --exclude='db.sqlite3' \
    --exclude='media/' \
    --exclude='ghaithleads/settings.py' \
    --exclude='ghaithleads/local_settings.py' \
    --exclude='*.csv' \
    --exclude='.git/' \
    --exclude='deploy/pythonanywhere.env' \
    "${STAGING_DIR}/" "${PROJECT_DIR}/"

# Repo uses system/ — production WSGI uses ghaithleads/
if [[ -d "${STAGING_DIR}/system" && -d "${PROJECT_DIR}/ghaithleads" ]]; then
    log "Syncing system/ → ghaithleads/ (keeping settings.py)..."
    rsync -a --delete \
        --exclude='settings.py' \
        --exclude='local_settings.py' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        "${STAGING_DIR}/system/" "${PROJECT_DIR}/ghaithleads/"
fi

# ── 4. Initialize git in production for future deploy.sh pulls ──────────────
log "Initializing git for future deploys..."
cd "$PROJECT_DIR"
git init -q
git remote add origin "$GIT_REPO_URL" 2>/dev/null || git remote set-url origin "$GIT_REPO_URL"
git fetch origin "$GIT_BRANCH" -q
git branch -f main "origin/${GIT_BRANCH}"
git symbolic-ref HEAD refs/heads/main
git reset --mixed main -q

cat >> .git/info/exclude <<'EOF'
db.sqlite3
media/
ghaithleads/settings.py
ghaithleads/local_settings.py
deploy/pythonanywhere.env
*.csv
static_root/
EOF

log "Git initialized at origin/${GIT_BRANCH} (${COMMIT})"

# ── 5. Deploy config ────────────────────────────────────────────────────────
if [[ ! -f "${PROJECT_DIR}/deploy/pythonanywhere.env" ]]; then
    cp "${PROJECT_DIR}/deploy/pythonanywhere.env.example" "${PROJECT_DIR}/deploy/pythonanywhere.env"
    log "Created deploy/pythonanywhere.env from example"
fi

# ── 6. Dependencies, checks, migrate, static, reload ────────────────────────
export DJANGO_SETTINGS_MODULE
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

log "Installing requirements..."
"$PIP" install -r "${PROJECT_DIR}/requirements.txt" -q

log "Removing __pycache__..."
find "$PROJECT_DIR" -type d -name '__pycache__' -not -path '*/.git/*' -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_DIR" -type f -name '*.pyc' -not -path '*/.git/*' -delete 2>/dev/null || true

log "Running Django checks..."
"$PYTHON" "${PROJECT_DIR}/manage.py" check

log "Applying migrations..."
"$PYTHON" "${PROJECT_DIR}/manage.py" migrate --noinput

log "Collecting static files..."
"$PYTHON" "${PROJECT_DIR}/manage.py" collectstatic --noinput

log "Reloading web app..."
touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py

log "=== Bootstrap complete ==="
log "Backup: ${BACKUP_DIR}"
log "Site:   https://ghaithtravel.pythonanywhere.com/"
log ""
log "Next deploys: cd ${PROJECT_DIR} && bash deploy/deploy.sh"
