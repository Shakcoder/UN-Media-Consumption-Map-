#!/usr/bin/env python3
"""
build_movers_feed.py — the Topic Explorer's movers list as an RSS feed.

Reads data/trends/topic_intelligence.json (the published daily figures,
verbatim — this script computes nothing) and writes
data/trends/movers_feed.xml: one feed item per measurement day, listing the
same top-five rising and falling topics the Topic Explorer's "Global topic
movers" pane shows, with the same single-edition cue.

Run daily by trend-engine.yml right after compute_topic_intelligence.py.
Anyone who pastes the feed's address into Outlook, Teams or a feed reader
gets each day's movers delivered instead of having to visit the page.

Rules:
- SELECTION IS THE PAGE'S, exactly: topics sorted by global velocity; the
  top five with positive velocity are "rising", the bottom five with
  negative velocity are "falling" (a quiet week may yield fewer than five,
  or none). Keep this in lockstep with renderGlobalMovers() in topics.html.
- One item per measured_as_of date. Re-running on the same day REPLACES that
  day's item (the engine can be re-run by hand); it never duplicates it.
- Earlier items are carried over from the existing feed, newest first, up to
  FEED_MAX_ITEMS. History starts the day this feature shipped — days before
  it are absent, never reconstructed.
- A mover carried >= 70% by one language edition gets the same "driven by X
  Wikipedia" cue as the page: a single-community wave must not read as a
  world story in someone's inbox.
"""

from __future__ import annotations

import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEL_PATH = REPO_ROOT / "data" / "trends" / "topic_intelligence.json"
FEED_PATH = REPO_ROOT / "data" / "trends" / "movers_feed.xml"

# GitHub Pages address of the live site (the trailing dash is part of the
# repository name). A feed travels away from the site, so every link in it
# must be absolute.
SITE = "https://shakcoder.github.io/UN-Media-Consumption-Map-/"
PAGE_URL = SITE + "topics.html"
FEED_URL = SITE + "data/trends/movers_feed.xml"

FEED_MAX_ITEMS = 30

# Keep in lockstep with LANG_NAMES in topics.html.
LANG_NAMES = {
    "en": "English", "fr": "French", "es": "Spanish", "ar": "Arabic",
    "pt": "Portuguese", "ru": "Russian", "zh": "Chinese", "hi": "Hindi",
    "bn": "Bengali", "id": "Indonesian", "sw": "Swahili", "ha": "Hausa",
    "am": "Amharic", "ur": "Urdu", "fa": "Persian", "tr": "Turkish",
    "vi": "Vietnamese", "th": "Thai", "ja": "Japanese", "de": "German",
    "uk": "Ukrainian", "ko": "Korean",
}


def js_round(x: float) -> int:
    """JavaScript's Math.round (a .5 always rounds toward positive infinity).

    Python's round() is half-to-even, and the difference is live: a velocity
    of 4.405 renders as +441% on the page (Math.round) but would round to
    440 here. The feed shows the SAME published figure the page shows, so it
    must round the way the page rounds. Keep in lockstep with
    renderGlobalMovers() in topics.html.
    """
    return math.floor(x + 0.5)


def mover_line(label: str, velocity: float, top_edition: dict) -> str:
    """One list entry, phrased like the page's mover row."""
    pct = js_round(velocity * 100)
    sign = "+" if pct >= 0 else ""
    line = f"{label} {sign}{pct}%"
    lang = (top_edition or {}).get("lang")
    share = (top_edition or {}).get("share")
    if lang in LANG_NAMES and isinstance(share, (int, float)) and share >= 0.7:
        line += f" (driven by {LANG_NAMES[lang]} Wikipedia)"
    return line


def build_item(intel: dict) -> tuple[str, ET.Element]:
    """Today's feed item. Returns (guid, <item> element)."""
    as_of = intel.get("measured_as_of") or intel.get("generated")
    topics = intel.get("topics", {})
    cov = intel.get("coverage", {})

    ranked = sorted(topics.values(), key=lambda t: -t["global_velocity"])
    risers = [t for t in ranked if t["global_velocity"] > 0][:5]
    fallers = [t for t in ranked if t["global_velocity"] < 0][-5:][::-1]

    unscored = (
        (cov.get("topics_stale_excluded") or 0)
        + (cov.get("topics_below_floor") or 0)
        + (cov.get("topics_quarantined") or 0)
    )

    parts: list[str] = []
    parts.append(
        f"<p><b>Topic movers, measured through {escape(str(as_of))}:</b> attention in the "
        "7 days to that date compared with the prior 30 days.</p>"
    )
    if risers:
        lis = "".join(
            f"<li>{escape(mover_line(t['label_en'], t['global_velocity'], t.get('top_edition')))}</li>"
            for t in risers
        )
        parts.append(f"<p><b>Rising</b></p><ul>{lis}</ul>")
    else:
        parts.append("<p><b>Rising</b>: no topics rising sharply this week.</p>")
    if fallers:
        lis = "".join(
            f"<li>{escape(mover_line(t['label_en'], t['global_velocity'], t.get('top_edition')))}</li>"
            for t in fallers
        )
        parts.append(f"<p><b>Falling</b></p><ul>{lis}</ul>")
    else:
        parts.append("<p><b>Falling</b>: no topics falling sharply this week.</p>")
    coverage_line = f"{len(topics)} topics measured in 22 languages"
    if unscored:
        coverage_line += (
            f"; {unscored} tracked topics could not be measured today "
            "(no current data, too little traffic, or quarantined as non-organic) "
            "and are excluded rather than scored from stale figures"
        )
    parts.append(
        f"<p>{coverage_line}. Velocity is measured from Wikipedia reading patterns "
        "per language edition, volume-weighted: what people look up, not what media "
        "publish. Attention trends are decision support, never a measure of media "
        "coverage or public opinion.</p>"
    )
    parts.append(
        f'<p><a href="{escape(PAGE_URL)}">Open the Topic Explorer</a> for detail, '
        "language breakdowns and custom date ranges.</p>"
    )

    headline = ", ".join(
        f"{t['label_en']} {'+' if t['global_velocity'] > 0 else ''}{js_round(t['global_velocity'] * 100)}%"
        for t in (risers[:2] + fallers[:1])
    )
    title = f"Topic movers {as_of}" + (f": {headline}" if headline else ": a quiet week")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = PAGE_URL
    guid = f"atlas-movers-{as_of}"
    g = ET.SubElement(item, "guid", isPermaLink="false")
    g.text = guid
    ET.SubElement(item, "pubDate").text = format_datetime(datetime.now(timezone.utc))
    ET.SubElement(item, "description").text = "".join(parts)
    return guid, item


def previous_items() -> list[ET.Element]:
    """Items from the existing feed, in their stored (newest-first) order."""
    if not FEED_PATH.exists():
        return []
    try:
        root = ET.parse(FEED_PATH).getroot()
        return root.findall("./channel/item")
    except ET.ParseError as exc:
        # A truncated feed must not kill the day's update; start fresh and
        # say so (the old items are in git history if ever needed).
        print(f"WARNING: existing feed unreadable ({exc}); rebuilding from today.")
        return []


def main() -> int:
    if not INTEL_PATH.exists():
        print(f"ERROR: {INTEL_PATH} missing; nothing to build a feed from.")
        return 1
    intel = json.loads(INTEL_PATH.read_text(encoding="utf-8"))
    if not intel.get("topics"):
        print("ERROR: topic_intelligence.json has no scored topics; leaving the feed as it is.")
        return 1

    guid, item = build_item(intel)
    old = [i for i in previous_items() if (i.findtext("guid") or "") != guid]

    rss = ET.Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = "Topic movers · UN Audience Intelligence Atlas"
    ET.SubElement(ch, "link").text = PAGE_URL
    ET.SubElement(ch, "description").text = (
        "The Topic Explorer's daily movers list: which of the tracked UN-relevant "
        "topics are rising or falling in worldwide Wikipedia attention, published "
        "figures only. Decision support, not a measure of media coverage or "
        "public opinion."
    )
    ET.SubElement(ch, "language").text = "en"
    ET.SubElement(ch, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))
    ET.SubElement(
        ch, "atom:link",
        href=FEED_URL, rel="self", type="application/rss+xml",
    )
    ch.append(item)
    for i in old[: FEED_MAX_ITEMS - 1]:
        ch.append(i)

    ET.indent(rss)
    xml = ET.tostring(rss, encoding="unicode", xml_declaration=True) + "\n"
    # Atomic write, same policy as the rest of the pipeline.
    tmp = FEED_PATH.with_suffix(".xml.tmp")
    tmp.write_text(xml, encoding="utf-8")
    os.replace(tmp, FEED_PATH)
    print(f"Wrote {FEED_PATH} - item {guid} plus {min(len(old), FEED_MAX_ITEMS - 1)} earlier day(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
