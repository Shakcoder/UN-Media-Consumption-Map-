# Google Analytics walkthrough — what to come away with

*The team is walking you through the UN's Google Analytics 360 data (scheduled
for early August 2026). This sheet is what to ask while you're in the room.
The goal is simple: don't leave the meeting with only a dashboard tour. Leave
with a sample file, a name, and answers to the questions below — that is
everything needed to design the integration.*

---

## The three things that matter most

### 1. Walk out with ONE exported file
At any point in the demo, ask:

> "Can you export this report as a CSV and email it to me?"

Any report works — *users by country* or *top pages* over the last 30 days is
ideal. One small file tells us the exact shape of the data (its columns), and
the whole pipeline gets designed from that. Without it, everything downstream
is guesswork.

### 2. Walk out with the administrator's name
> "Who administers this account? If I need view-only access, who do I ask?"

Write the name down. The access request email is already drafted and waiting
in [ACTION_ITEMS.md](../ACTION_ITEMS.md) — it just needs a recipient.

### 3. Ask whether you can get view-only access yourself
> "Could my UN email get *viewer* access, so I can export reports myself?"

Viewer access is read-only and is the cheapest thing for them to grant. If
yes, every follow-up question in this file becomes something you can answer
later without another meeting.

---

## Questions to read out (note the answers next to each)

**About what's there:**
- "Which websites does this cover — un.org, news.un.org, others? Are they
  separate properties?"
- "How far back does the data go?"
- "Which reports do you use most — what does DGC itself look at?"

**About getting data out automatically** (this decides the technical design):
- "Is BigQuery export switched on for this property?" *(yes/no is enough —
  don't worry about what it means)*
- "Can reports be scheduled to email a CSV automatically — daily or weekly?"
- "Is there an API anyone here already uses to pull from it?"

**About privacy** (needed for the security review):
- "Does this collect anything user-level — User-IDs, precise location — or is
  it all aggregate?"
- "Is there a UN data-classification for this? Specifically: may *country-level
  aggregates* be published on a public site?"
- "Who is the data owner I should name in a privacy review?"

---

## Things NOT to promise in the meeting

- **Don't promise to publish anything.** The plan is that raw exports stay
  private (never uploaded to the public repository) and only country-level
  aggregates — the same granularity as everything already on the Atlas — are
  published. But *whether* even aggregates go public is exactly what the
  privacy questions above are for. "We'll aggregate it and check with you
  before anything goes on the site" is the safe sentence.
- **Don't accept the whole dataset yet.** If they offer to send everything,
  ask for the one sample file first. Volume without a design is a liability,
  not a head start.

---

## What happens after the meeting

Hand over: the sample CSV (tell Claude the file's location on your Mac — do
not commit it to the repository), the administrator's name, and your notes on
the questions above. From those three inputs the integration gets designed and
built — including what the analyst will newly be able to answer (content
performance, format comparisons, audience-by-country for *UN content*
specifically — all things the Atlas currently declines for lack of data).
