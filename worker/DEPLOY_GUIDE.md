# ⛔ DO NOT FOLLOW THIS GUIDE YET — the Worker is out of date

**Nothing is broken and nothing is missing.** The Ask page (`ask.html`) answers every question on its own, in the visitor's browser, using the Atlas's published data. It needs no account, no server, and cannot break after handover. **That is the finished product.** This folder holds an *optional experiment* that is currently switched off.

## Why it is switched off

In **July 2026** the Ask page's built-in analyst was rebuilt. It now guarantees, in code, the honesty rules the Atlas promises its readers:

- every answer carries an **"Advisory"** disclaimer;
- countries rated **Not Free** carry a **partner-vetting warning**;
- online reach is **never claimed above a country's internet penetration**;
- figures are labelled **measured / inferred / unknown**;
- countries with **no survey coverage are named and excluded**, with the reason given.

The Worker in this folder was written *before* that rebuild. It does none of the above — it only *asks* a free AI model to behave well, and a model can quietly leave any of it out. It also never loads the newer data layers (platform use, advertising market, English-language reach).

Because the Ask page tries the Worker **first** whenever a Worker address is configured, switching it on today would **silently replace good answers with weaker ones**. That is a downgrade, not an upgrade — so the Worker code contains a switch (`WORKER_ENABLED`, near the top of `worker/analyst-worker.js`) that is set to `false`. Even if the Worker is deployed and pointed at, it politely refuses every question and the Ask page carries on with its own engine.

## What would have to happen first

Someone with coding experience would need to, in this order:

1. Copy the built-in analyst's rules into `ANALYST_RULES` in `worker/analyst-worker.js` — the Advisory disclaimer, the Not-Free partner-vetting warning, the internet-penetration ceiling on digital reach, and the measured/inferred/unknown labelling.
2. Add the missing data to `countryRecord` in the same file (platform use, advertising market, English-language reach).
3. Add the Worker to the eval harness in `scripts/` so these rules are actually tested, the way the browser engine is.
4. Only then change `WORKER_ENABLED` to `true`.

**If you are not sure whether all four are done, they are not done.** Leave it alone — the Atlas is complete without it.

---

# Reference: the original setup steps

*Kept for whoever does the work above. Following these today produces a deployed Worker that answers nothing.*

## Part A — Create the Worker (the "switchboard")

1. Go to **dash.cloudflare.com** → **Sign up** (free) → verify your email.
2. In the left sidebar click **Workers & Pages**.
3. Click **Create** → under "Workers" click **Create Worker**.
4. Change the suggested name to **`atlas-analyst`** → click **Deploy**. (It deploys a placeholder — expected.)
5. Click **Edit code**. Delete all the placeholder code (click in the editor, Cmd+A, Delete).
6. Open `worker/analyst-worker.js` from this repository (on the GitHub website, open the file and click the **copy** icon at the top right of the code view).
7. **Paste** into the Cloudflare editor → click **Deploy** (top right).

Your backend now lives at an address like `https://atlas-analyst.YOURNAME.workers.dev` (shown on the Worker's overview page).

## Part B — Switch on the free AI (one binding, no key)

1. On your **atlas-analyst** Worker page, open the **Settings** tab.
2. Find **Bindings** → click **Add** → choose **Workers AI**.
3. For the variable name enter exactly: **`AI`**
4. Save / Deploy.

No account keys, no billing page, nothing to top up. Cloudflare's free plan includes a daily AI allowance (10,000 "neurons"/day, roughly 20–100+ answers depending on the model used; the Worker automatically drops to a lighter model if the day's allowance runs low).

## Part C — Point the website at the backend

1. In this repository, open **`ask.html`** and find (near the top of the script):
   ```js
   const WORKER_URL = "";
   ```
2. Put your Worker address between the quotes:
   ```js
   const WORKER_URL = "https://atlas-analyst.YOURNAME.workers.dev";
   ```
3. Commit and push the changed `ask.html`.

## Part D — Test

Try: *"What is trending in Nigeria this week?"*, *"Compare news trust in France and Germany"*, *"Where should we run a vaccination campaign in West Africa?"*

---

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| Every answer looks the same as before | Expected while `WORKER_ENABLED` is `false` — the Worker refuses and the page uses its own engine. **This is the intended state.** Also expected whenever the Worker is unreachable, so visitors never see an outage. |
| Opening the Worker address shows `"disabled": true` | Confirms the Worker is deployed and correctly switched off. Read the top of this guide before changing that. |
| "the free AI binding is missing" | Part B — the binding's variable name must be exactly `AI`. |
| Answers stop late in the day | The daily free allowance ran out; it resets at midnight UTC. |
| "I couldn't reach the analyst backend" | Check the Worker address — opening it in a browser should show a small JSON message. |

## If budget ever appears (paid path)

Adding an Anthropic API key as a Worker secret named `ANTHROPIC_API_KEY` (Settings → Variables & Secrets) makes the Worker use Claude with multi-step research instead of the free model. Two warnings:

- **This path has never been run end-to-end against the live API.** Treat it as untested code, not a supported feature. Test it with a small key and a handful of questions before telling anyone it works.
- It is gated by the same `WORKER_ENABLED` switch and inherits the same out-of-date rules described at the top of this guide. A paid model following stale instructions is still a downgrade.

## Facts for supervisors

- **Total running cost: $0.** Data (free public sources) + hosting (GitHub Pages, free) + automation (GitHub Actions, free). The optional AI layer described here is switched off and costs nothing.
- The Ask page reads only the Atlas's own verified, source-attributed data, and shows the sources behind every answer.
- No personal data is collected or stored; questions are answered in the visitor's own browser.
