# Ghaith CRM — PythonAnywhere Deployment Guide

Production-safe deployment for **https://ghaithtravel.pythonanywhere.com/** using **git pull** (no more delete-and-reclone).

---

## Verified project layout

| Item | Value |
|------|--------|
| **Production project path** | `/home/ghaithtravel/ghaithleads` |
| **WSGI file** | `/var/www/ghaithtravel_pythonanywhere_com_wsgi.py` |
| **Django settings (WSGI)** | `ghaithleads.settings` |
| **GitHub remote** | `https://github.com/ahmadhjy/Ghaith-CRM.git` |
| **Branch** | `main` |
| **manage.py** | `/home/ghaithtravel/ghaithleads/manage.py` |
| **Requirements** | `/home/ghaithtravel/ghaithleads/requirements.txt` |
| **Database** | SQLite at `db.sqlite3` (project root) |
| **Static files** | `STATIC_ROOT = static_root/`, `collectstatic` required |
| **Repo Django package** | `system/` (in GitHub) |
| **Production Django package** | `ghaithleads/` (WSGI name) |

### Important naming note

The GitHub repo uses the Django project folder **`system/`**, but PythonAnywhere WSGI uses **`ghaithleads.settings`**. On the server you should have a **`ghaithleads/`** package (production `settings.py` with `DEBUG=False`, correct `ALLOWED_HOSTS`, etc.).

The deploy script **syncs `system/` → `ghaithleads/`** after each pull and **never overwrites** `ghaithleads/settings.py`.

---

## What the deploy script does (safe steps)

1. Loads config from `deploy/pythonanywhere.env`
2. Writes a timestamped log to `/home/ghaithtravel/deploy-backups/logs/`
3. **Backs up** `db.sqlite3`, `media/`, `ghaithleads/settings.py`, `local_settings.py`
4. **`git fetch` + `git merge --ff-only`** (stops if a manual merge is needed)
5. Syncs `system/` → `ghaithleads/` (preserves production settings)
6. Activates venv and runs **`pip install -r requirements.txt`**
7. Removes **`__pycache__`** and **`.pyc`** only
8. Runs **`manage.py check`**
9. Shows migration plan, then **`manage.py migrate --noinput`** (pending only)
10. Runs **`manage.py collectstatic --noinput --clear`**
11. Reloads the web app (`touch` WSGI file or API)
12. **Stops immediately** on any failed command (`set -e`)

### What it never does

- Does not delete `db.sqlite3` or reset the database
- Does not delete migration files
- Does not delete the project folder or re-clone from scratch
- Does not overwrite production `ghaithleads/settings.py`
- Does not run `migrate --fake` or `flush`

---

## One-time setup on PythonAnywhere

### 1. Find your virtualenv path

In the PythonAnywhere **Web** tab → your app → **Virtualenv** section.  
Example: `/home/ghaithtravel/.virtualenvs/ghaithleads-venv`

### 2. Ensure production settings exist

`/home/ghaithtravel/ghaithleads/ghaithleads/settings.py` should include at minimum:

```python
DEBUG = False
ALLOWED_HOSTS = ['ghaithtravel.pythonanywhere.com', 'www.ghaithtravel.pythonanywhere.com']
SECRET_KEY = '...'  # production secret, not the dev key from git
```

Keep this file **only on the server** (listed in `.git/info/exclude`).

### 3. Configure deploy environment

```bash
cd /home/ghaithtravel/ghaithleads
cp deploy/pythonanywhere.env.example deploy/pythonanywhere.env
nano deploy/pythonanywhere.env   # set VENV_DIR and verify paths
```

### 4. Initialize git (if not already done)

```bash
bash deploy/setup_git_on_pythonanywhere.sh
```

If the project already has `.git` pointing at GitHub, skip this step.

### 5. Dry run

```bash
bash deploy/deploy.sh --dry-run
```

### 6. First real deploy

```bash
bash deploy/deploy.sh
```

---

## Regular deployment (after every GitHub push)

```bash
cd /home/ghaithtravel/ghaithleads
bash deploy/deploy.sh
```

Typical duration: 1–3 minutes.

---

## Migration strategy

| Scenario | Action |
|----------|--------|
| New migration files in GitHub | Deploy runs `migrate --noinput` automatically |
| Migration conflict / merge failure | **Stop.** Fix locally, push to GitHub, redeploy |
| Old manual “delete new migrations” workflow | **Do not use** — migrations in git are the source of truth |
| Production DB ahead of git | Run `showmigrations` on server; resolve with `makemigrations`/`migrate` in dev first |

Before risky model changes, take an extra manual backup:

```bash
cp db.sqlite3 ~/db.sqlite3.manual.$(date +%Y%m%d)
```

---

## Rollback

If a deploy breaks the site:

```bash
BACKUP=/home/ghaithtravel/deploy-backups/YYYYMMDD_HHMMSS   # use latest folder
cp "$BACKUP/db.sqlite3" /home/ghaithtravel/ghaithleads/db.sqlite3
cp "$BACKUP/ghaithleads/settings.py" /home/ghaithtravel/ghaithleads/ghaithleads/settings.py 2>/dev/null || true
cd /home/ghaithtravel/ghaithleads
git checkout "$(cat "$BACKUP/git_commit_before.txt")"
touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py
```

---

## Logs and backups

| Path | Contents |
|------|----------|
| `/home/ghaithtravel/deploy-backups/logs/deploy_*.log` | Full deploy output |
| `/home/ghaithtravel/deploy-backups/YYYYMMDD_HHMMSS/` | DB + settings snapshot per deploy |

---

## Reload methods

| Method | Config | Notes |
|--------|--------|-------|
| `touch` (default) | `RELOAD_METHOD="touch"` | `touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py` |
| API | `RELOAD_METHOD="api"` | Needs `API_TOKEN` from PythonAnywhere Account page |
| Both | `RELOAD_METHOD="both"` | touch + API |

---

## Future: webhook / one-click deploy

1. Push to `main` on GitHub
2. PythonAnywhere **Scheduled task** or **always-on** script polls GitHub, OR GitHub Action SSHes to PA (paid plans)
3. Task runs: `cd /home/ghaithtravel/ghaithleads && bash deploy/deploy.sh`

For now, manual `bash deploy/deploy.sh` after `git push` is the safest approach.

---

## Local vs production checklist

Before pushing to GitHub:

```bash
python manage.py check
python manage.py migrate --plan
git status   # commit migrations with code changes
git push origin main
```

Then on PythonAnywhere:

```bash
bash deploy/deploy.sh
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Virtualenv not found` | Set correct `VENV_DIR` in `pythonanywhere.env` |
| `git merge failed` | Resolve on server or reset to known good commit; never delete whole folder |
| `ModuleNotFoundError: ghaithleads` | Ensure `ghaithleads/` exists; enable `SYNC_SYSTEM_TO_GHAITHLEADS=yes` |
| Static files 404 | Confirm `collectstatic` ran; Web tab static files mapping points to `static_root/` |
| `manage.py` uses wrong settings | On server: `export DJANGO_SETTINGS_MODULE=ghaithleads.settings` (deploy script sets this) |

---

## Files in this folder

| File | Purpose |
|------|---------|
| `deploy.sh` | Main production deploy script |
| `pythonanywhere.env.example` | Config template (copy to `pythonanywhere.env`) |
| `setup_git_on_pythonanywhere.sh` | One-time git initialization |
| `wsgi_reference.py` | Documentation of current WSGI |
| `DEPLOYMENT.md` | This guide |
