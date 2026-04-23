# Launching the survey — step-by-step for a non-coder

You can have a live survey collecting responses in under 30 minutes. This guide walks through it click-by-click. The survey is **Google Forms** (free, familiar, no account upgrades needed).

Everything you need to paste is already written out below. You do not need to invent any of the question text.

---

## Before you start

- You need a **Google account** (your personal Gmail is fine, but an institutional account is cleaner if you'll be handing over).
- You need **your UN supervisor's sign-off** on [SURVEY_ETHICS.md](SURVEY_ETHICS.md) before going live. Forward them that file and wait for a written OK. This one step protects you, the respondents, and the UN.
- You need a **project email address** for people to contact if they want their response removed. If you don't have one yet, make a free Gmail like `mediaconsumptionatlas@gmail.com`. Put that address in the consent language below where you see `[project email to be added]`.

---

## Step 1 — Create the form (5 min)

1. Go to https://forms.google.com and click the blank "+" to start a new form.
2. Click the **Untitled form** title and change it to:
   > Global Media Consumption Survey
3. Click the description field underneath and paste:
   > A short, anonymous survey for a public research project prepared for the United Nations. Takes about 4 minutes.
4. Top-right, click the **⚙ Settings** gear. Under **Responses**:
   - Turn OFF "Collect email addresses" (we're anonymous).
   - Turn OFF "Limit to 1 response" (we don't want to block people who switch devices).
   - Turn OFF "Allow response editing".
5. Still in Settings → **Presentation**:
   - Turn ON "Show progress bar".
   - Under "Confirmation message", paste:
     > Thank you. Your response will appear in the community-sourced layer of the Global Media Consumption Atlas within a few weeks.
6. Click **Save**.

---

## Step 2 — Add the consent page (2 min)

1. At the top of your form, the first item should be the consent text. Change the first question type to **Title and description** (the icon looks like a letter "T" in the right-side toolbar).
2. Title:
   > Before you begin
3. Description — paste the entire text below exactly as written:

```
This survey is part of an independent research project being prepared for handover to the United Nations. Its goal is to better understand how people around the world consume media — which platforms they use, what kind of content they look for, and how much they trust different sources.

The survey is ANONYMOUS. We do not ask for your name, email address, or any other information that could identify you.

It is VOLUNTARY. You may skip any question, close the page at any point, or decline to participate.

Your answers will be PUBLISHED IN AGGREGATE on our public website — as grouped statistics, never as individual responses.

Your data will be stored SEPARATELY from the official statistics on our map and will always be clearly labeled as community-sourced.

You can request removal of your response (for example, if you change your mind) within 30 days of submission by emailing [project email to be added] with the approximate date and country of your submission.

The survey takes about 4 minutes.
```

4. Below that, add a new question. Type: **Multiple choice**. Required: **yes**.
   - Question: `I have read the information above and I agree to participate.`
   - Option 1: `Yes, I consent and wish to continue`
   - Option 2: `No, I do not consent`
   - Click the three-dot menu on this question → **Go to section based on answer**. We'll configure this in Step 4.

---

## Step 3 — Add the questions (10 min)

Add each of these as a new question. Use the **"+"** button in the right-side toolbar. Keep only the consent question required.

### Q2 — Country of residence
- Type: **Dropdown** · Required: **yes**
- Question: `Which country do you live in?`
- Options: paste the full list of 195 UN member states. **Shortcut:** copy the list from https://www.un.org/en/about-us/member-states (select all, paste into a text editor, then paste into the Google Forms option list — Forms will accept multi-line paste as separate options).

### Q3 — Age band
- Type: **Multiple choice** · Required: **yes**
- Question: `What age range are you in?`
- Options: `Under 18 / 18–24 / 25–34 / 35–44 / 45–54 / 55–64 / 65 or older`
- Click the three dots → **Go to section based on answer** → if "Under 18", jump to a thank-you section (we don't collect data from minors). We'll set this up in Step 4.

### Q4 — Main news medium
- Type: **Multiple choice** · Required: no
- Question: `Which medium do you use most for news and current events?`
- Options: `Television / Radio / Online news site / Social media / Messaging app (WhatsApp, Telegram, etc.) / Printed newspaper / Podcast / I do not follow news`

### Q5 — Hours per day grid
- Type: **Multiple-choice grid** · Required: no
- Question: `On an average day, how many hours do you spend on each of the following?`
- Rows: `Television / Radio / Social media / Reading (print or online) / Streaming video / Podcasts`
- Columns: `0 / Under 1 / 1–2 / 2–4 / 4 or more`

### Q6 — Topics of interest
- Type: **Checkboxes** · Required: no
- Question: `Which topics interest you most? (pick up to five)`
- Options: `Politics / International news / Local news / Climate and environment / Health / Business and economy / Science and technology / Arts and culture / Sports / Lifestyle / Religion`

### Q7 — General trust in news
- Type: **Linear scale** · Required: no
- Question: `How much do you trust the news you consume?`
- Scale: `1` (not at all) → `5` (completely)

### Q8 — Trust by medium
- Type: **Multiple-choice grid** · Required: no
- Question: `How much do you trust each medium?`
- Rows: `Television / Radio / Printed press / Online news sites / Social media`
- Columns: `1 / 2 / 3 / 4 / 5` (1 = no trust, 5 = full trust)

### Q9 — Optional demographics (new section — add a section break before this group)
Click the "add section" button in the toolbar (looks like `=` with a line under it) before this group. Name the section:
> Optional demographics (you may skip any of these)

- **Q9a** — *Multiple choice*, not required. Question: `Gender` · Options: `Woman / Man / Non-binary / Prefer not to say / Prefer to self-describe (short answer)`
- **Q9b** — *Multiple choice*, not required. Question: `Highest level of education completed` · Options: `Primary / Secondary / Vocational / Bachelor's / Master's / Doctorate / Prefer not to say`
- **Q9c** — *Multiple choice*, not required. Question: `Do you live in an urban, suburban, or rural area?` · Options: `Urban / Suburban / Rural / Prefer not to say`

---

## Step 4 — Conditional paths (3 min)

Two places where the form should branch:

1. **Consent** — if the respondent answers "No, I do not consent", send them to the end of the form with this thank-you section:
   > Thank you. No data has been collected. You may close this page.

2. **Age under 18** — if they answer "Under 18" on Q3, send them to the same or a separate end section:
   > Thank you for your interest. This survey is open to respondents aged 18 and older only. No data has been collected.

To set these up: click the three-dot menu on the question → **Go to section based on answer** → pick the section you want them to land on. Add a new section break at the end of the form and mark it as the destination.

---

## Step 5 — Publish it (2 min)

1. Top-right, click **Send**.
2. Click the link icon (🔗), tick **Shorten URL**, and copy the link. That's your public survey URL.
3. Open your `index.html` in your repo, find the line:
   ```html
   <a href="#" data-i18n="nav_survey">Take the survey</a>
   ```
   Change `#` to your survey URL. Add `target="_blank"` so it opens in a new tab:
   ```html
   <a href="https://forms.gle/YOUR-URL" target="_blank" data-i18n="nav_survey">Take the survey</a>
   ```
4. Commit the change on GitHub.

You now have a live public survey linked from the atlas.

---

## Step 6 — Export responses (2 min, repeatable)

Every few weeks you want to feed responses into the site:

1. Open the form, click the **Responses** tab.
2. Click the **green spreadsheet icon** ("Link to Sheets"). Create a new Google Sheet.
3. That sheet updates live. When you have enough responses to add a batch:
   - File → Download → Comma-separated values (.csv).
   - Send the `.csv` to me (or drop it in the repo). I will merge it into the "community-sourced" layer of the site.

---

## What I'll do on my side (you don't need to touch this)

When you send survey CSVs, I will:
- Strip any accidental identifying data.
- Aggregate the responses by country and age band.
- Publish the aggregates in a clearly-labeled "Community insights" section on each country's profile — separate from official statistics, never mixed.

---

## A short note on distribution

Resist the urge to spam the survey link. Safe, legitimate channels in rough order:
- Your UN supervisor's network, and through them formal UN social-media channels.
- Friends of the project at academic institutions (one research-methods lecturer can reach hundreds of students).
- Newsletters of adjacent organizations (Reuters Institute alumni, UNESCO Media section contacts).
- Your own social media, once per platform, with a clear disclaimer that it's a voluntary research project.

Avoid: paid ad campaigns targeting specific demographics (skews the sample), mass outreach via purchased email lists (almost certainly violates GDPR), or anything automated.
