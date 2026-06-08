#!/usr/bin/env bash
# One-time setup: turn /home/ghaithtravel/ghaithleads into a git working tree
# connected to GitHub (without deleting the database or production settings).
#
# Run ONCE from PythonAnywhere Bash:
#   cd /home/ghaithtravel/ghaithleads
#   bash deploy/setup_git_on_pythonanywhere.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/pythonanywhere.env"

GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/ahmadhjy/Ghaith-CRM.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"

if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
fi

echo "Project directory: ${PROJECT_DIR}"
cd "$PROJECT_DIR"

# Never proceed if this looks like a destructive fresh clone into a populated site
if [[ -f "db.sqlite3" && ! -d ".git" ]]; then
    echo "Found existing db.sqlite3 — will initialize git in-place (no folder deletion)."
fi

if [[ -d ".git" ]]; then
    echo "Git already initialized."
    git remote -v
    exit 0
fi

echo "Initializing git repository..."
git init
git remote add origin "${GIT_REPO_URL}"

echo "Fetching from GitHub..."
git fetch origin "${GIT_BRANCH}"

echo ""
echo "IMPORTANT: The next step may report conflicts for files that exist only on"
echo "production (db.sqlite3, ghaithleads/settings.py, media/). That is expected."
echo ""
read -r -p "Create branch '${GIT_BRANCH}' tracking origin/${GIT_BRANCH}? [y/N] " confirm
if [[ "${confirm,,}" != "y" ]]; then
    echo "Aborted. You can run manually:"
    echo "  git checkout -b ${GIT_BRANCH} origin/${GIT_BRANCH}"
    exit 1
fi

# Allow production-only files to remain untracked / local
cat >> .git/info/exclude <<'EOF' || true
db.sqlite3
media/
local_settings.py
ghaithleads/settings.py
deploy/pythonanywhere.env
static_root/
*.log
EOF

git checkout -b "${GIT_BRANCH}" "origin/${GIT_BRANCH}" 2>/dev/null || {
    echo ""
    echo "Checkout failed (likely local files conflict with the repo)."
    echo "Safe option: merge with allow-unrelated-histories after backing up:"
    echo "  cp db.sqlite3 ~/db.sqlite3.backup"
    echo "  git checkout -b ${GIT_BRANCH}"
    echo "  git reset origin/${GIT_BRANCH}"
    echo "  # restore db.sqlite3 and ghaithleads/settings.py from backup"
    exit 1
}

echo ""
echo "Git setup complete. Next steps:"
echo "  1. cp deploy/pythonanywhere.env.example deploy/pythonanywhere.env"
echo "  2. Edit deploy/pythonanywhere.env (venv path, etc.)"
echo "  3. bash deploy/deploy.sh --dry-run"
echo "  4. bash deploy/deploy.sh"
