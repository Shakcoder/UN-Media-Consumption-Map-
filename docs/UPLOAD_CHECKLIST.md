# How to upload changes to GitHub (the safe way)

*Updated 2026-07-20. This replaces the old paste-into-the-editor instructions.*

## ⚠️ One rule above all: ALWAYS use "Upload files", never paste

Pasting file contents into GitHub's web editor **silently truncates large files** — the commit looks fine but the file is cut off partway, and things break in confusing ways later. This has happened on this project. The upload flow below never truncates.

## The standard upload flow (works for any number of files)

1. On the repo's main page, click **Add file → Upload files**.
2. In Finder, select ALL the changed files at once (⌘-click to multi-select) and **drag them into the browser window**.
   - Files that live in folders (e.g. `scripts/refresh_data.py`, `docs/DATA_SOURCES.md`) must be dropped **while you're inside that folder on GitHub** — open the folder first, then Add file → Upload files.
   - Easier for many folders: do one upload per folder (root files → `scripts/` → `docs/` → `.github/workflows/` → `data/` → `worker/`).
3. Write a one-line commit message describing the batch (e.g. "July 2026 upgrade: analyst v2, bug fixes, watchdog").
4. Click **Commit changes**.
5. GitHub Pages redeploys automatically — wait ~2 minutes, then hard-refresh the site (⌘⇧R) in a private window.

## Uploading a whole batch (like today's upgrade)

Upload folder by folder, in this order — the order prevents anything half-working in between:

| Step | Open this folder on GitHub | Upload these files from your Mac |
|---|---|---|
| 1 | *(repo root)* | `index.html`, `ask.html`, `ask-engine.js`, `topics.html`, `README.md` |
| 2 | `scripts/` | every changed `.py` file |
| 3 | `.github/workflows/` | every changed/new `.yml` file |
| 4 | `docs/` | every changed `.md` file |
| 5 | `data/` | `countries.json`, `static_countries.json` (only when told they changed) |
| 6 | `worker/` | `analyst-worker.js`, `DEPLOY_GUIDE.md` (when changed) |

## After uploading: check the automation

1. Click the **Actions** tab.
2. The **Refresh country data** workflow starts by itself whenever `scripts/refresh_data.py` or `data/static_countries.json` changed. Wait for the green checkmark (~2–4 min).
3. If a run goes red: click it, expand the red step, copy the error text into a new session with Claude. (The workflows also open a GitHub Issue automatically when they fail — check the **Issues** tab.)

## If something looks wrong on the site

- Hard-refresh in a private/incognito window first — it's almost always the browser cache.
- The site keeps serving the last good data even when a refresh fails, so nothing is ever "down" while you investigate.
