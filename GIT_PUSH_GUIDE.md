# Push this project to a clean Git repo

Follow these steps from your project root (the folder that contains `manage.py`).

---

## 1. Create a new repo on GitHub/GitLab/Bitbucket

- **GitHub:** https://github.com/new  
- Create the repo **without** initializing with a README, .gitignore, or license (empty repo).

---

## 2. Open a terminal in the project root

```bash
cd c:\Users\User\systemlb\lebadsyspub\lebadv-sys\system
```

---

## 3. Initialize Git (if not already)

```bash
git init
```

If you already have a `.git` folder and want a **clean** history (no old commits):

```bash
# Remove old git history
rm -rf .git
git init
```

On Windows PowerShell, to remove `.git`:

```powershell
Remove-Item -Recurse -Force .git
git init
```

---

## 4. Add a .gitignore (recommended)

Create a `.gitignore` in the project root so you don’t commit virtualenv, `__pycache__`, DB, secrets, etc.

Example:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
.eggs/
dist/
build/

# Virtual env
djangoenv/
venv/
.venv/
env/

# Django
*.log
local_settings.py
db.sqlite3
media/
staticfiles/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

---

## 5. Stage and commit

```bash
git add .
git status
git commit -m "Initial commit: Django lead/tasks/calendar app"
```

---

## 6. Rename branch to main (optional)

```bash
git branch -M main
```

---

## 7. Add the remote and push

Replace `YOUR_USERNAME` and `YOUR_REPO` with your actual repo URL (e.g. `github.com/yourname/lebadv-sys`).

**HTTPS:**

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

**SSH:**

```bash
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

---

## 8. If the remote already has commits (e.g. README)

If you created the repo with a README and need to overwrite it:

```bash
git pull origin main --allow-unrelated-histories
# Resolve any merge conflicts, then:
git push -u origin main
```

Or force push (only if you’re sure you want to replace the remote):

```bash
git push -u origin main --force
```

---

## Quick reference

| Step              | Command |
|-------------------|--------|
| Go to project     | `cd c:\Users\User\systemlb\lebadsyspub\lebadv-sys\system` |
| Fresh git         | `Remove-Item -Recurse -Force .git` then `git init` |
| Ignore files      | Add `.gitignore` (see above) |
| First commit      | `git add .` → `git commit -m "Initial commit"` |
| Set main          | `git branch -M main` |
| Add remote        | `git remote add origin <your-repo-url>` |
| Push              | `git push -u origin main` |
