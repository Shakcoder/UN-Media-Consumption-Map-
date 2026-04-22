# Getting the site online — a non-technical walkthrough

You don't need to know any code to follow this. Everything happens in your web browser. Plan for about 20 minutes.

---

## What we're doing and why (in plain English)

We need a place on the internet where our website lives. We're going to use **GitHub**, a free service used by millions of organizations (including the UN and the US government) to store and publish websites.

Two concepts to know:

- **Repository** (a.k.a. "repo") = a folder on GitHub that holds all the files for one project. Ours will hold the website.
- **GitHub Pages** = a free built-in feature of GitHub that turns any repository into a public website. No extra setup, no hosting fees.

That's it. Those are the only two words you need.

---

## Step 1 — Create a GitHub account (5 minutes)

1. In your browser, go to **https://github.com**
2. Click **"Sign up"** (top-right).
3. Pick an email. *Suggestion:* use a professional email you'll have access to after the internship ends, because this account will own the website.
4. Pick a password.
5. Pick a **username**. This is public and will appear in your site's URL — something like `un-media-map` or `media-consumption-atlas` is better than `shakti-cool-2026`. Pick something you'd be comfortable seeing on a UN-published page.
6. Verify the puzzle, click through email verification, and you're in.
7. On the "pick a plan" screen, choose **Free**. Always free. Skip any "Copilot trial" upsells for now — we'll address Copilot separately.

**When this step is done:** take a screenshot of your GitHub profile page and send it to me so I can confirm the setup.

---

## Step 2 — Create the repository (3 minutes)

1. Click the **"+"** icon in the top-right, then **"New repository"**.
2. **Repository name:** `un-media-consumption-map` (or whatever you prefer — just let me know what you chose).
3. **Description:** "Interactive public map of global media consumption patterns."
4. Set visibility to **Public**. (This *must* be public for the free GitHub Pages hosting to work.)
5. Tick the box **"Add a README file"**. (This creates a starter file so we can begin uploading.)
6. Leave everything else at default.
7. Click **"Create repository"**.

You should now be looking at an almost-empty repository page with one file (`README.md`) in it.

---

## Step 3 — Upload the starter files (5 minutes)

I'll have a folder ready for you with all the files you need. Here's how to get them into GitHub:

1. On your repository page, click **"Add file"** → **"Upload files"**.
2. Open your file browser, go to `Desktop/UN Project`, and **drag every file and folder** into the GitHub upload area.
3. Scroll down. In the box that says "Commit changes", type a short message like: `Phase 0 — initial upload`.
4. Click the green **"Commit changes"** button.

GitHub is now storing all your project files. Any time you update a file, you just repeat this upload step, and GitHub keeps a full history of every change.

---

## Step 4 — Turn on GitHub Pages (2 minutes)

This is the magic step that turns the repository into a live public website.

1. In your repository, click **"Settings"** (top bar, looks like a gear).
2. In the left sidebar, click **"Pages"**.
3. Under **"Source"**, choose **"Deploy from a branch"**.
4. Under **"Branch"**, choose **`main`** and folder **`/ (root)`**, then click **"Save"**.
5. Wait about 60 seconds. Refresh the page.
6. You'll see a green banner: *"Your site is live at https://your-username.github.io/your-repo-name/"*.

**Click that link.** You should see the "Coming Soon" page with UN branding.

**That's your site. It's on the public internet. It's free. It will stay up forever.**

---

## Step 5 — Send me the URL

Copy the link and send it to me. Once I can confirm it loads correctly from my end, Phase 0 is officially done, and we move into Phase 1 (building the real map).

---

## What to do if something goes wrong

- **"The page shows 404."** You probably just need to wait another minute or two. Refresh. Still nothing? Check Settings → Pages and make sure it says *"Your site is live"*.
- **"I can't upload a folder."** GitHub's web upload accepts folders in modern Chrome/Edge/Firefox. If drag-and-drop fails, upload files one at a time or in small batches.
- **"I got a weird error."** Screenshot it and send it to me. Do *not* click any "Fix with Copilot" or "Resolve conflicts" buttons without asking me first — those aren't dangerous but they can create confusion.
- **"I accidentally deleted something."** Don't worry. GitHub remembers every version of every file forever. I can recover anything.

---

## A note on security and privacy

- Everything in a public repository is publicly visible — **do not put anything sensitive in there** (personal info, passwords, survey responses with names). I'll make sure our file layout respects this.
- Your GitHub account password is the keys to the castle. Enable **two-factor authentication** (Settings → Password and authentication → Two-factor authentication) — GitHub will soon require it anyway.
