# Deploy Ghaith CRM on PythonAnywhere — Step by Step

Your confirmed paths (from the Web tab):

| Setting | Path |
|---------|------|
| **Project** | `/home/ghaithtravel/ghaithleads` |
| **Virtualenv** | `/home/ghaithtravel/djangenv` |
| **Static files** | `/home/ghaithtravel/ghaithleads/static` → URL `/static/` |
| **Media files** | `/home/ghaithtravel/ghaithleads/media` → URL `/media/` |
| **WSGI** | `/var/www/ghaithtravel_pythonanywhere_com_wsgi.py` |
| **GitHub** | `https://github.com/ahmadhjy/Ghaith-CRM.git` |

---

## Part A — One-time setup (do this once)

### Step 1 — Push deploy files to GitHub (from your PC)

On your local machine, commit and push the `deploy/` folder:

```bash
cd path/to/Ghaith-CRM
git add deploy/
git commit -m "Add PythonAnywhere deployment automation"
git push origin main
```

### Step 2 — Open PythonAnywhere Bash console

1. Log in at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Open the **Consoles** tab
3. Start a **Bash** console

### Step 3 — Go to the project folder

```bash
cd /home/ghaithtravel/ghaithleads
```

### Step 4 — Pull the latest code (if deploy folder is not there yet)

If this folder is already a git repo:

```bash
git pull origin main
```

If you still use the old manual copy workflow, copy the `deploy/` folder from the repo first, then continue.

### Step 5 — Create the deploy config file

```bash
cp deploy/pythonanywhere.env.example deploy/pythonanywhere.env
```

The example already has your paths. Verify with:

```bash
cat deploy/pythonanywhere.env
```

You should see:

```
VENV_DIR="/home/ghaithtravel/djangenv"
STATIC_SERVE_DIR="/home/ghaithtravel/ghaithleads/static"
MEDIA_DIR="/home/ghaithtravel/ghaithleads/media"
```

No edits needed unless something on your server is different.

### Step 6 — Ensure production settings exist

Your WSGI uses `ghaithleads.settings`. Confirm this file exists:

```bash
ls -la /home/ghaithtravel/ghaithleads/ghaithleads/settings.py
```

If missing, create it from your live settings (or see `deploy/ghaithleads_settings_production.SNIPPET.py`).

Production settings must include at least:

- `DEBUG = False`
- `ALLOWED_HOSTS` includes `ghaithtravel.pythonanywhere.com`
- `MEDIA_ROOT` pointing to `/home/ghaithtravel/ghaithleads/media` (if you use uploads)

### Step 7 — Ensure media folder exists

```bash
mkdir -p /home/ghaithtravel/ghaithleads/media
```

This matches your Web tab mapping (`/media/` → `ghaithleads/media`).

### Step 8 — Initialize git on the server (only if `.git` does not exist)

```bash
cd /home/ghaithtravel/ghaithleads
ls -la .git
```

If `.git` is missing:

```bash
bash deploy/setup_git_on_pythonanywhere.sh
```

If `.git` already exists and points to GitHub, skip this step.

### Step 9 — Dry run (safe test, no changes)

```bash
cd /home/ghaithtravel/ghaithleads
bash deploy/deploy.sh --dry-run
```

Read the output. Fix any errors before the real deploy.

### Step 10 — First real deploy

```bash
bash deploy/deploy.sh
```

Wait until you see: `Deploy finished successfully`

### Step 11 — Confirm the site works

Open: **https://ghaithtravel.pythonanywhere.com/**

Check:

- Login works
- Static CSS/JS loads (`/static/`)
- Uploaded files still work (`/media/`)

### Step 12 — Check logs if something fails

```bash
# Deploy log (latest)
ls -lt /home/ghaithtravel/deploy-backups/logs/ | head -5

# PythonAnywhere error log (from Web tab)
tail -50 /var/log/ghaithtravel.pythonanywhere.com.error.log
```

---

## Part B — Every future deploy (after you push to GitHub)

### On your PC

```bash
cd path/to/Ghaith-CRM
git pull origin main
git push origin main   # after your commits
```

### On PythonAnywhere Bash

```bash
cd /home/ghaithtravel/ghaithleads
export DJANGO_SETTINGS_MODULE=ghaithleads.settings

# 1) Confirm deploy config (one-time; edit if needed)
grep RUN_COLLECTSTATIC deploy/pythonanywhere.env
# Must be: RUN_COLLECTSTATIC="no"

# 2) Deploy
bash deploy/deploy.sh
```

Typical time: 2–5 minutes (media backup can take 1–2 min).

### After this release (passengers, tooltips, calendar toggles)

The deploy applies new DB migrations automatically. If you want to run them manually first:

```bash
cd /home/ghaithtravel/ghaithleads
export DJANGO_SETTINGS_MODULE=ghaithleads.settings
/home/ghaithtravel/djangenv/bin/python manage.py migrate display
```

### If CSS/JS looks broken after deploy

Never run `collectstatic --clear` on PythonAnywhere. Restore theme files from git:

```bash
cd /home/ghaithtravel/ghaithleads
bash deploy/restore_static.sh
```

Then hard-refresh the browser (Ctrl+F5).

### Quick deploy (skip slow media backup)

```bash
BACKUP_MEDIA=no bash deploy/deploy.sh
```

---

## What the script does each time

1. Backs up Postgres (via `deploy/backup_database.py`), `media/`, and `ghaithleads/settings.py`
2. `git fetch` + `git merge --ff-only` from GitHub (no delete, no reclone)
3. Syncs `system/` → `ghaithleads/` (keeps your production `settings.py`)
4. Activates `/home/ghaithtravel/djangenv`
5. `pip install -r requirements.txt`
6. Removes `__pycache__` / `.pyc` only
7. `manage.py check`
8. `manage.py migrate` (pending migrations only)
9. Verifies theme CSS/JS in `static/` — **does not** run `collectstatic --clear` (see `RUN_COLLECTSTATIC=no`)
10. Reloads the web app (`touch` WSGI file)

---

## Rollback (if a deploy breaks the site)

```bash
# List backups (newest first)
ls -lt /home/ghaithtravel/deploy-backups/

# Replace YYYYMMDD_HHMMSS with the backup folder name before the bad deploy
BACKUP=/home/ghaithtravel/deploy-backups/YYYYMMDD_HHMMSS

cp "$BACKUP/db.sqlite3" /home/ghaithtravel/ghaithleads/db.sqlite3
cp -a "$BACKUP/media" /home/ghaithtravel/ghaithleads/ 2>/dev/null || true
cp "$BACKUP/settings.py" /home/ghaithtravel/ghaithleads/ghaithleads/settings.py 2>/dev/null || true

cd /home/ghaithtravel/ghaithleads
git checkout "$(cat "$BACKUP/git_commit_before.txt")"
touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py
```

---

## Quick reference

```bash
cd /home/ghaithtravel/ghaithleads
bash deploy/deploy.sh              # normal deploy
bash deploy/deploy.sh --dry-run    # test only
bash deploy/deploy.sh --skip-migrate   # code/static only (no DB changes)
```
