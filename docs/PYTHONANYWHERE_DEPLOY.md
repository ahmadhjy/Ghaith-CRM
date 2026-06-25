# PythonAnywhere — What You Run

**Site:** https://ghaithtravel.pythonanywhere.com/

You only run commands **on PythonAnywhere**. Code is pushed to GitHub from the dev machine first — when you are told an update is ready, run the steps below.

---

## Paths (your server)

| Item | Path |
|------|------|
| Project folder | `/home/ghaithtravel/ghaithleads` |
| Virtualenv | `/home/ghaithtravel/djangenv` |
| Django settings | `ghaithleads.settings` |
| Deploy script | `bash deploy/deploy.sh` |

---

## Every update (normal deploy)

When dev says *“pushed to GitHub — deploy on PA”*:

### 1. Open a Bash console

PythonAnywhere → **Consoles** → **Bash**

### 2. Run deploy

```bash
cd /home/ghaithtravel/ghaithleads
bash deploy/deploy.sh
```

Wait until you see **`Deploy finished successfully`** (usually 2–5 minutes).

### 3. Check the site

Open https://ghaithtravel.pythonanywhere.com/ and confirm login + pages load.

**That is the whole routine for most releases.** The script automatically:

- Backs up database, media, and settings
- Pulls latest code from GitHub (`main`)
- Installs Python packages
- Runs database migrations
- Reloads the web app

---

## First time only (if not done before)

Run these once when setting up deploy on a new server or after `deploy/` was first added to the repo.

```bash
cd /home/ghaithtravel/ghaithleads

# Config file (paths are pre-filled for your account)
cp deploy/pythonanywhere.env.example deploy/pythonanywhere.env

# Media folder
mkdir -p /home/ghaithtravel/ghaithleads/media

# Test without changing anything
bash deploy/deploy.sh --dry-run

# Real first deploy
bash deploy/deploy.sh
```

If `.git` is missing on the server:

```bash
bash deploy/setup_git_on_pythonanywhere.sh
```

---

## Accounting module — first-time go-live (on PythonAnywhere)

Run **after** a normal `deploy/deploy.sh` that included the accounting code.

### 1. Activate environment

```bash
source /home/ghaithtravel/djangenv/bin/activate
cd /home/ghaithtravel/ghaithleads
export DJANGO_SETTINGS_MODULE=ghaithleads.settings
```

### 2. Set accounting go-live date

Replace `2026-06-24` with your real go-live date. Orders **before** this date will not auto-sync to accounting.

```bash
python manage.py shell -c "
from accounting_bridge.models import AccountingConfig
from datetime import date
c = AccountingConfig.load()
c.invoice_sync_from = date(2026, 6, 24)
c.master_data_sync_enabled = True
c.save()
print(c)
"
```

Or use Django admin → **Accounting integration settings**.

### 3. Sync master data from CRM orders

Creates accounting clients, suppliers, destinations, service types, and employees from existing CRM orders. **Does not** import old invoices.

```bash
python manage.py sync_crm_to_accounting
```

### 4. Main accountant access (Django admin)

1. Open https://ghaithtravel.pythonanywhere.com/admin/
2. **User profiles** → your accountant user → check **Is main accountant** → Save

### 5. Opening balances (in the browser)

1. Log in as main accountant
2. Go to **Accounting** → **Opening balances**
3. Add debit/credit per client and supplier for pre-go-live balances

| Party | Debit | Credit |
|-------|-------|--------|
| Client | What they owe you | Prepayments |
| Supplier | Paid on account | What you owe them |

### 6. Verify

- [ ] https://ghaithtravel.pythonanywhere.com/accounting/ loads (main accountant only)
- [ ] CRM sidebar shows **Accounting** for that user
- [ ] New CRM order (on/after go-live) creates a draft invoice (`TMP-…`)

---

## Optional commands (when asked)

### Prepare salary rows for a month (no auto-payment)

```bash
source /home/ghaithtravel/djangenv/bin/activate
cd /home/ghaithtravel/ghaithleads
export DJANGO_SETTINGS_MODULE=ghaithleads.settings
python manage.py post_employee_salaries --month 2026-06
```

Payroll is then completed in the UI: **Operating expenses → Salaries** tab.

### Manual migration (only if deploy failed on migrate)

```bash
source /home/ghaithtravel/djangenv/bin/activate
cd /home/ghaithtravel/ghaithleads
export DJANGO_SETTINGS_MODULE=ghaithleads.settings
python manage.py migrate --noinput
touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py
```

### Extra database backup before a big change

```bash
cd /home/ghaithtravel/ghaithleads
source /home/ghaithtravel/djangenv/bin/activate
export DJANGO_SETTINGS_MODULE=ghaithleads.settings
python deploy/backup_database.py
```

### Quick deploy (skip slow media backup)

```bash
cd /home/ghaithtravel/ghaithleads
BACKUP_MEDIA=no bash deploy/deploy.sh
```

### Test deploy without applying changes

```bash
cd /home/ghaithtravel/ghaithleads
bash deploy/deploy.sh --dry-run
```

### If CSS looks broken after deploy

**Do not run collectstatic on PythonAnywhere.**

```bash
cd /home/ghaithtravel/ghaithleads
bash deploy/restore_static.sh
```

Then hard-refresh the browser (Ctrl+F5).

---

## If something goes wrong

### Read the deploy log

```bash
ls -lt /home/ghaithtravel/deploy-backups/logs/ | head -5
tail -100 /home/ghaithtravel/deploy-backups/logs/deploy_YYYYMMDD_HHMMSS.log
```

### PythonAnywhere error log

Web tab → your app → **Error log**, or:

```bash
tail -50 /var/log/ghaithtravel.pythonanywhere.com.error.log
```

### Rollback to previous deploy

```bash
# List backups (newest first)
ls -lt /home/ghaithtravel/deploy-backups/

# Use the folder from BEFORE the bad deploy
BACKUP=/home/ghaithtravel/deploy-backups/YYYYMMDD_HHMMSS

# Restore DB backup (script name may vary — check BACKUP folder contents)
cp "$BACKUP/db"* /home/ghaithtravel/ghaithleads/ 2>/dev/null || true
cp -a "$BACKUP/media" /home/ghaithtravel/ghaithleads/ 2>/dev/null || true
cp "$BACKUP/settings.py" /home/ghaithtravel/ghaithleads/ghaithleads/settings.py 2>/dev/null || true

cd /home/ghaithtravel/ghaithleads
git checkout "$(cat "$BACKUP/git_commit_before.txt")"
touch /var/www/ghaithtravel_pythonanywhere_com_wsgi.py
```

Tell dev what error you saw so the fix can be pushed to GitHub.

---

## Quick reference (copy-paste)

```bash
# Normal deploy
cd /home/ghaithtravel/ghaithleads && bash deploy/deploy.sh

# Accounting bootstrap (one-time)
source /home/ghaithtravel/djangenv/bin/activate
cd /home/ghaithtravel/ghaithleads
export DJANGO_SETTINGS_MODULE=ghaithleads.settings
python manage.py shell -c "from accounting_bridge.models import AccountingConfig; from datetime import date; c=AccountingConfig.load(); c.invoice_sync_from=date(2026,6,24); c.master_data_sync_enabled=True; c.save(); print(c)"
python manage.py sync_crm_to_accounting
```

---

## What you do **not** need to do

| Task | Who handles it |
|------|----------------|
| `git commit` / `git push` to GitHub | Dev machine |
| Writing or editing code | Dev machine |
| Creating migration files | Dev machine |
| Editing `ghaithleads/settings.py` secrets | Already on server only |
| Running tests before release | Dev machine |

You only run commands on **PythonAnywhere** after dev confirms the push is on GitHub.
