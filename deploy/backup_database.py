#!/usr/bin/env python
"""Backup database before deploy (PostgreSQL pg_dump or SQLite file copy)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ghaithleads.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

backup_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/ghaithtravel/deploy-backups")
label = sys.argv[2] if len(sys.argv) > 2 else "manual"
backup_root.mkdir(parents=True, exist_ok=True)

db = settings.DATABASES["default"]
engine = db["ENGINE"]

if "postgresql" in engine:
    out = backup_root / f"postgres_{label}.sql"
    env = os.environ.copy()
    env["PGPASSWORD"] = db.get("PASSWORD", "")
    cmd = [
        "pg_dump",
        "-h", db.get("HOST", "localhost"),
        "-p", str(db.get("PORT", 5432)),
        "-U", db.get("USER", ""),
        "-d", db.get("NAME", ""),
        "-f", str(out),
    ]
    subprocess.run(cmd, env=env, check=True)
    print(out)
elif "sqlite" in engine:
    src = Path(db["NAME"])
    if not src.is_file():
        print(f"SQLite database not found: {src}", file=sys.stderr)
        sys.exit(1)
    out = backup_root / f"sqlite_{label}.sqlite3"
    shutil.copy2(src, out)
    print(out)
else:
    print(f"Unsupported engine: {engine}", file=sys.stderr)
    sys.exit(1)
