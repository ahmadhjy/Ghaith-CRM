#!/usr/bin/env bash
# Emergency restore of theme CSS/JS after collectstatic --clear wiped static/.
# PythonAnywhere serves files directly from /home/ghaithtravel/ghaithleads/static/
#
# Usage:
#   cd /home/ghaithtravel/ghaithleads
#   bash deploy/restore_static.sh
#
set -euo pipefail

PROJECT_DIR="/home/ghaithtravel/ghaithleads"
REQUIRED=(
    "css/navbar-unified.css"
    "css/requests-modern.css"
    "css/app-modern-global.css"
    "JS/navbar-unified.js"
)

cd "$PROJECT_DIR"

echo "Restoring static/ from git..."
git checkout HEAD -- static/ 2>/dev/null || git restore static/ 2>/dev/null || {
    echo "Git restore failed — copying from staging clone..."
    rsync -av ~/Ghaith-CRM-staging/static/ "${PROJECT_DIR}/static/"
}

echo "Verifying required files..."
missing=0
for f in "${REQUIRED[@]}"; do
    if [[ -f "static/${f}" ]]; then
        echo "  OK  static/${f}"
    else
        echo "  MISSING  static/${f}"
        missing=1
    fi
done

[[ "$missing" -eq 0 ]] || { echo "Some files still missing. Run: git pull origin main"; exit 1; }

touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py
echo "Done. Hard-refresh the site (Ctrl+F5)."
