#!/usr/bin/env bash
# Shared helpers for deploy scripts.

resolve_database_path() {
    local python_bin="$1"
    local project_dir="$2"
    local settings_module="${3:-ghaithleads.settings}"

    local db_path
    db_path="$(
        cd "$project_dir" && DJANGO_SETTINGS_MODULE="$settings_module" "$python_bin" -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '${settings_module}')
import django
django.setup()
from django.conf import settings
print(settings.DATABASES['default']['NAME'])
" 2>/dev/null
    )"

    if [[ -n "$db_path" && -f "$db_path" ]]; then
        echo "$db_path"
        return 0
    fi

    # Fallback: common locations
    local candidate
    for candidate in \
        "${project_dir}/db.sqlite3" \
        "${project_dir}/database.sqlite3" \
        "${project_dir}/ghaithleads/db.sqlite3"
    do
        if [[ -f "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}
