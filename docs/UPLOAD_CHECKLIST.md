# What to upload to GitHub right now

This is a one-time setup: upload these files in this order, then the automation runs itself forever.

---

## File-by-file checklist

Follow the Method B pattern you already know: on GitHub click **Add file → Create new file**, type the filename (with `/` to create folders), paste the contents from the file on your Mac, commit.

Upload them in this order:

### 1. `index.html` (edit existing, don't create new)
Click the existing `index.html` on GitHub → pencil icon → select all → delete → paste new content from `Desktop/UN Project/index.html` → commit.

### 2. `data/static_countries.json`
On GitHub → Add file → Create new file. Filename: `data/static_countries.json`. Paste contents from your Mac copy. Commit.

### 3. `scripts/refresh_data.py`
Same pattern. Filename: `scripts/refresh_data.py`.

### 4. `.github/workflows/refresh-data.yml`
Same pattern. Filename: `.github/workflows/refresh-data.yml`. The `.github` leading dot is important — GitHub recognizes this folder specially.

### 5. `docs/SURVEY_SETUP.md`, `docs/AUTOMATION.md`
Same pattern, into the existing `docs/` folder (or create if needed).

---

## After uploading: trigger the first automation run (1 minute)

Don't wait until Monday 3 AM for the first run.

1. On your repo, click the **Actions** tab in the top bar.
2. In the left sidebar, click **Refresh country data**.
3. Click **Run workflow** (top-right) → pick the `main` branch → **Run workflow** (green button).
4. Wait 30–60 seconds. Refresh the Actions page. You should see a green checkmark.
5. Click into the run to see what it did. You'll see log lines like `→ USA (United States of America)` and the data being fetched.
6. The workflow will auto-commit a new file — `data/countries.json` — into your repo.
7. GitHub Pages rebuilds the site automatically. Wait another 60 seconds, reload your site in Incognito, click a country. The "Preliminary" banner should now read "verified" with a real retrieval date.

---

## What to do if the first run fails

1. Click into the failed run.
2. Expand the step that's red.
3. Copy the error message and send it to me.

The most common cause is permissions. If you see a message about "refusing to allow the bot to push", go to **Settings → Actions → General → Workflow permissions** and set it to **Read and write permissions**. Save. Re-run.

---

## After that, you're done

- The workflow runs every Monday at 03:00 UTC automatically.
- It will also re-run any time you edit `data/static_countries.json` (for example, when you add a country).
- You never need to touch `data/countries.json` by hand — it's overwritten every run.

---

## To add the survey

Follow [SURVEY_SETUP.md](SURVEY_SETUP.md). It's separate from the automation pipeline — no code changes needed beyond swapping one URL in `index.html`.
