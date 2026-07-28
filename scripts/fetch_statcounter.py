#!/usr/bin/env python3
"""
fetch_statcounter.py — per-country social-platform web-traffic shares.

Source: Statcounter GlobalStats (gs.statcounter.com), free CSV endpoint.

WHAT THIS MEASURES (and what it does not): Statcounter tracks page views
across ~1.5M websites carrying its analytics tag and reports which social
platform REFERRED that web traffic. It is a real, measured, monthly signal —
but it is a *web-referral* share, not an app-usage share. App-first platforms
(WhatsApp, TikTok, Telegram) barely refer web traffic and are mostly
invisible here, so in WhatsApp-first markets the top Statcounter platform is
NOT the country's leading platform. The Atlas therefore presents this as
"social web-traffic share" alongside — never instead of — the curated
leading-platform data. Small markets have thin tracker coverage; we smooth
with a 3-month average and record the window.

Output: data/platform_web_shares.json
Cadence: monthly data; safe to re-run weekly with the main refresh.

If a run comes back with far fewer countries than the published file has, it
stops with an error instead of writing — see the check in main(). Statcounter
failures are silent per country, so "wrote 3 countries" would otherwise look
like a successful run and replace a good 195-country file.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

# Reuse the project's ISO3→ISO2 map and SSL context so the two scripts can
# never drift apart on country identity.
sys.path.insert(0, str(Path(__file__).parent))
from refresh_data import ISO3_TO_ISO2, _CTX  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC_PATH = ROOT / "data" / "static_countries.json"
OUTPUT_PATH = ROOT / "data" / "platform_web_shares.json"

UA = "UN-Media-Consumption-Atlas/1.0 (+github actions)"


def month_window(months_back: int = 3) -> tuple[str, str]:
    """(from, to) as YYYYMM strings covering the last `months_back` complete months."""
    today = date.today()
    # last complete month
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    end = y * 100 + m
    fy, fm = y, m - (months_back - 1)
    while fm < 1:
        fm += 12
        fy -= 1
    return f"{fy:04d}{fm:02d}", f"{end:06d}"


def fetch_country(iso2: str, frm: str, to: str) -> dict[str, float] | None:
    """3-month average share per platform for one country, or None."""
    url = (
        "https://gs.statcounter.com/social-media-stats/all/chart.php"
        f"?device=&device_hidden=all&statType_hidden=social_media"
        f"&region_hidden={iso2}&granularity=monthly&statType=Social%20Media"
        f"&region={iso2}&fromInt={frm}&toInt={to}"
        f"&fromMonthYear={frm[:4]}-{frm[4:]}&toMonthYear={to[:4]}-{to[4:]}&csv=1"
    )
    for attempt in range(2):
        try:
            req = Request(url, headers={"User-Agent": UA})
            with urlopen(req, timeout=25, context=_CTX) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            lines = [ln for ln in text.strip().splitlines() if ln.strip()]
            if len(lines) < 2 or not lines[0].startswith('"Date"'):
                return None
            header = [h.strip('"') for h in lines[0].split(",")]
            sums: dict[str, float] = {}
            n_rows = 0
            for ln in lines[1:]:
                cells = ln.split(",")
                if len(cells) != len(header):
                    continue
                n_rows += 1
                for name, val in zip(header[1:], cells[1:]):
                    try:
                        sums[name] = sums.get(name, 0.0) + float(val)
                    except ValueError:
                        pass
            if not n_rows:
                return None
            avg = {k: round(v / n_rows, 2) for k, v in sums.items() if v / n_rows >= 0.5}
            return avg or None
        except Exception:
            if attempt == 0:
                time.sleep(2)
    return None


def previous_country_count() -> int:
    """How many countries the published file currently has (0 if none)."""
    if not OUTPUT_PATH.exists():
        return 0
    try:
        prev = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    return len(prev.get("countries") or {}) if isinstance(prev, dict) else 0


def main() -> int:
    static = json.loads(STATIC_PATH.read_text(encoding="utf-8"))
    iso3s = sorted(k for k in static if not k.startswith("_"))
    frm, to = month_window(3)
    had = previous_country_count()

    out: dict[str, object] = {}
    got = 0
    for i, iso3 in enumerate(iso3s):
        iso2 = ISO3_TO_ISO2.get(iso3)
        if not iso2:
            continue
        shares = fetch_country(iso2, frm, to)
        if shares:
            top = sorted(shares.items(), key=lambda kv: -kv[1])
            out[iso3] = {
                "shares": dict(top[:6]),
                "top_web_platform": top[0][0],
            }
            got += 1
        if (i + 1) % 25 == 0:
            print(f"  · {i + 1}/{len(iso3s)} countries fetched, {got} with data")
        time.sleep(0.4)  # polite pacing

    # Every failure above is per-country and silent (Statcounter changing its
    # CSV header, an error page, throttling half-way through), so a run can
    # "succeed" with far fewer countries than last week — and the workflow
    # commits whatever it finds. Refuse to publish a shrunken file: exiting
    # non-zero is what makes the workflow keep the previous one and print a
    # warning. The 10% margin is normal week-to-week wobble in Statcounter's
    # thin-coverage markets (observed: 195 one week, 193 the next).
    floor = int(0.9 * had)
    if got == 0 or got < floor:
        print(
            f"\nERROR: only {got} countries returned data"
            + (f" (the published file has {had})." if had else ".")
            + "\nRefusing to overwrite data/platform_web_shares.json — the previous file stays."
            "\nUsually this means Statcounter changed its CSV format or rate-limited the run;"
            "\ncheck the URL in fetch_country() in a browser before re-running.",
            file=sys.stderr,
        )
        return 1

    result = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "window": f"{frm[:4]}-{frm[4:]} to {to[:4]}-{to[4:]} (3-month average)",
            "source": "Statcounter GlobalStats (gs.statcounter.com), free CSV API",
            "method_note": (
                "Share of social-platform REFERRALS to Statcounter-tracked websites. "
                "A real measured monthly signal, but web-referral based: app-first "
                "platforms (WhatsApp, TikTok, Telegram) barely refer web traffic and "
                "are mostly invisible here. Never read the top platform in this table "
                "as 'the country's leading platform'; the curated leading-platform "
                "field measures actual usage. Platforms under 0.5% share are dropped; "
                "small markets have thin tracker coverage."
            ),
            "country_count": got,
        },
        "countries": out,
    }
    # ATOMIC write (same policy as refresh_data.py): a direct write_text leaves
    # the published file truncated if the process is killed mid-write, and the
    # site reads this file live.
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, OUTPUT_PATH)
    print(f"\nWrote {OUTPUT_PATH} — {got} countries with web-referral share data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
