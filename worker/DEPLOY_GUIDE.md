# Turning on the "Ask the Analyst" AI — click-by-click, **zero cost**

*One-time setup, ~15 minutes, no coding, no credit card, no subscription.*

The chat page (`ask.html`) is already on the website in Demo Mode. This guide switches on real free-text answers using **Cloudflare's free AI allowance** — open AI models that run on Cloudflare's servers at no charge. There is nothing to pay and no payment method is ever requested.

How it stays reliable: the Worker code finds the countries/topics in each question and pulls the exact records from the Atlas's own published data **before** any AI is involved; the AI's only job is to write those records up with citation tags. It cannot browse the web and is instructed to refuse rather than guess.

---

## Part A — Create the Worker (the "switchboard")

1. Go to **dash.cloudflare.com** → **Sign up** (free) → verify your email.
2. In the left sidebar click **Workers & Pages**.
3. Click **Create** → under "Workers" click **Create Worker**.
4. Change the suggested name to **`atlas-analyst`** → click **Deploy**. (It deploys a placeholder — expected.)
5. Click **Edit code**. Delete all the placeholder code (click in the editor, Cmd+A, Delete).
6. Open `worker/analyst-worker.js` from this repository (on the GitHub website, open the file and click the **copy** icon at the top right of the code view).
7. **Paste** into the Cloudflare editor → click **Deploy** (top right).

Your backend now lives at an address like `https://atlas-analyst.YOURNAME.workers.dev` (shown on the Worker's overview page). **Copy this URL** for Part C.

## Part B — Switch on the free AI (one binding, no key)

1. On your **atlas-analyst** Worker page, open the **Settings** tab.
2. Find **Bindings** → click **Add** → choose **Workers AI**.
3. For the variable name enter exactly: **`AI`**
4. Save / Deploy.

That's the entire "AI setup" — no account keys, no billing page, nothing to top up. Cloudflare's free plan includes a daily AI allowance (10,000 "neurons"/day, roughly 20–100+ answers depending on the model used; the Worker automatically drops to a lighter model if the day's allowance runs low).

## Part C — Point the website at the backend

1. In this repository, open **`ask.html`** and find (near the top of the script):
   ```js
   const WORKER_URL = "";
   ```
2. Put your Worker address between the quotes:
   ```js
   const WORKER_URL = "https://atlas-analyst.YOURNAME.workers.dev";
   ```
3. Commit and push (GitHub Desktop). Two minutes later the Ask page switches from the yellow "Demo mode" banner to the green "Live" banner.

## Part D — Test

Try: *"What is trending in Nigeria this week?"*, *"Compare news trust in France and Germany"*, *"Where should we run a vaccination campaign in West Africa?"*
Answers arrive in ~5–20 seconds with numbered evidence beneath them.

---

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| Yellow demo banner still showing | `WORKER_URL` still empty in ask.html, or the push hasn't deployed (wait 2 min, hard-refresh Cmd+Shift+R). |
| "the free AI binding is missing" | Part B — the binding's variable name must be exactly `AI`. |
| Answers stop late in the day | The daily free allowance ran out; it resets at midnight UTC. (If this happens often, that's a *good* problem — usage justifies a budget conversation.) |
| "I couldn't reach the analyst backend" | Check the Worker URL — opening it in a browser should show a small JSON usage message. |

## Optional upgrade path (only if budget ever appears)

If the UN later funds an Anthropic API key (~$5–25/month), add it as a Worker secret named `ANTHROPIC_API_KEY` (Settings → Variables & Secrets). The Worker automatically switches to Claude with multi-step research for higher answer quality. Remove the secret to drop back to the free engine. No other changes needed.

## Facts for supervisors

- **Total running cost: $0.** Data (free public sources) + hosting (GitHub Pages, free) + automation (GitHub Actions, free) + AI answers (Cloudflare free allowance).
- The AI reads only the Atlas's own verified, source-attributed data. Every answer returns its evidence list.
- No personal data is collected or stored; questions are processed transiently.
