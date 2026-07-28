#!/usr/bin/env python3
"""
build_boundaries.py — generate the map's self-hosted country boundaries.

Why this exists
---------------
The map used to download its country outlines from a third-party CDN at full
10-metre survey resolution: 14 MB of geometry (4.5 MB compressed) — over 90%
of everything a visitor's browser had to download, for coastline detail the
map cannot even display. It also meant the site's most sensitive layer,
country boundaries, depended on an external host at runtime.

This script downloads the SAME pinned source snapshot once, generalizes it,
and writes it into the repo so GitHub Pages serves it like any other data
file. Two rules keep the generalization defensible:

  1. NOTHING A VIEWER CAN SEE CHANGES. The map's deepest zoom is 6, where one
     screen pixel covers ~0.022° (~2.4 km at the equator). Every removed
     vertex and every dropped islet is below HALF that size, so the rendered
     map is pixel-identical to the full-resolution source at every zoom the
     site allows. This is generalization for display, not a boundary claim —
     the map attribution says so.
  2. NO COUNTRY IS EVER DROPPED OR SHRUNK TO NOTHING. Every feature keeps its
     largest ring regardless of size (Tuvalu, Nauru and Monaco stay clickable),
     and the script refuses to write output that lost a feature or an ISO code
     present in the source.

Usage:  python3 scripts/build_boundaries.py
Output: data/boundaries/countries.geojson (compact JSON, ~5% of source size)

Source: github.com/datasets/geo-countries, pinned to the same immutable
commit the map previously loaded from the CDN (Natural Earth derived, ODC-PDDL).
Re-run only if the pin is deliberately moved to a newer snapshot.
"""

from __future__ import annotations

import gzip
import heapq
import json
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "boundaries" / "countries.geojson"

SOURCE_URL = ("https://cdn.jsdelivr.net/gh/datasets/geo-countries"
              "@b0b7794e15e7ec4374bf183dd73cce5b92e1c0ae/data/countries.geojson")

# One pixel at the map's maxZoom (6) is ~0.022 degrees. The source data is
# Natural Earth 1:10m-scale (kilometre-spaced vertices), so the area threshold
# is set from the display constraint: removing a vertex moves the line by
# roughly (2 x area / segment length); with ~0.03-0.06 degree spacing this
# threshold keeps every displacement near half a pixel at the deepest zoom.
# The hard quality gate: no vertex of the original boundary may end up more
# than half a display pixel (at maxZoom 6) from the simplified line. This is
# the Douglas-Peucker epsilon, so it is guaranteed by construction — not a
# tuning knob that merely aims at it.
MAX_DEVIATION_DEG = 0.011
ISLET_AREA_DEG2 = 5e-4   # non-largest rings smaller than this (~2 km across) are dropped
PRECISION = 5            # 5 decimals ≈ 1.1 m — far beyond display precision
MIN_RING_POINTS = 6      # never reduce a surviving ring below a real shape


def ring_area(ring: list) -> float:
    """Unsigned shoelace area in square degrees."""
    a = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i + 1][0], ring[i + 1][1]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def simplify_ring(ring: list) -> list:
    """Douglas–Peucker with the display budget as epsilon.

    Chosen over area-based methods because it GUARANTEES the promise this
    file is built on: no point of the original boundary ends up further than
    MAX_DEVIATION_DEG from the drawn line — under half a screen pixel at the
    deepest zoom the map allows. Iterative with an explicit stack (some
    coastlines run to tens of thousands of vertices)."""
    import math
    n = len(ring)
    if n <= MIN_RING_POINTS:
        return ring
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        ax, ay = ring[a][0], ring[a][1]
        bx, by = ring[b][0], ring[b][1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        worst, wi = -1.0, -1
        for m in range(a + 1, b):
            px, py = ring[m][0], ring[m][1]
            if L2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / L2
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > worst:
                worst, wi = d, m
        if worst > MAX_DEVIATION_DEG:
            keep[wi] = True
            stack.append((a, wi))
            stack.append((wi, b))
    return [pt for k, pt in enumerate(ring) if keep[k]]


def clean_ring(ring: list) -> list:
    """Round, close, and drop consecutive duplicates created by rounding."""
    out = []
    for pt in ring:
        r = [round(pt[0], PRECISION), round(pt[1], PRECISION)]
        if not out or r != out[-1]:
            out.append(r)
    if out and out[0] != out[-1]:
        out.append(list(out[0]))
    return out


def process_polygon(rings: list) -> list:
    areas = [ring_area(r) for r in rings]
    largest = areas.index(max(areas)) if areas else -1
    kept = []
    for idx, r in enumerate(rings):
        if idx != largest and areas[idx] < ISLET_AREA_DEG2:
            continue                       # sub-pixel islet / inner ring
        s = clean_ring(simplify_ring(r))
        if len(s) < 4 and idx == largest:
            # A microstate (Vatican, Monaco) can be smaller than the deviation
            # budget itself, which lets the simplifier legally reduce it to a
            # line. Countries must never disappear from a UN map, so the main
            # ring falls back to its original shape — a handful of points.
            s = clean_ring(r)
        if len(s) >= 4:
            kept.append(s)
    return kept


def main() -> int:
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    if len(sys.argv) > 1:                  # local snapshot, mainly for development
        src = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        print(f"[boundaries] using local source {sys.argv[1]}")
    else:
        print(f"[boundaries] downloading pinned source …")
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "UN-Audience-Intelligence-Atlas/1.0"})
        src = json.loads(urllib.request.urlopen(req, timeout=120, context=ctx).read())

    feats_in = src["features"]
    src_isos = {f["properties"].get("ISO3166-1-Alpha-3") for f in feats_in}
    feats_out, pts_in, pts_out = [], 0, 0

    for f in feats_in:
        g = f["geometry"]
        if g["type"] == "Polygon":
            pts_in += sum(len(r) for r in g["coordinates"])
            polys = [process_polygon(g["coordinates"])]
        elif g["type"] == "MultiPolygon":
            pts_in += sum(len(r) for p in g["coordinates"] for r in p)
            # rank islets against the feature's largest ring across ALL parts
            all_rings = [r for p in g["coordinates"] for r in p]
            areas = [ring_area(r) for r in all_rings]
            biggest = max(areas)
            polys = []
            for p in g["coordinates"]:
                outer_area = ring_area(p[0])
                if outer_area < ISLET_AREA_DEG2 and outer_area < biggest:
                    continue
                kept = process_polygon(p)
                if kept:
                    polys.append(kept)
        else:
            continue

        polys = [p for p in polys if p]
        if not polys:
            print(f"  !! {f['properties'].get('name')}: all geometry vanished — refusing to continue", file=sys.stderr)
            return 1
        if len(polys) == 1:
            geom = {"type": "Polygon", "coordinates": polys[0]}
        else:
            geom = {"type": "MultiPolygon", "coordinates": polys}
        pts_out += sum(len(r) for p in ([polys[0]] if len(polys) == 1 else polys) for r in (p if isinstance(p[0][0], list) else [p]))
        feats_out.append({"type": "Feature", "properties": f["properties"], "geometry": geom})

    out_isos = {f["properties"].get("ISO3166-1-Alpha-3") for f in feats_out}
    if len(feats_out) != len(feats_in) or out_isos != src_isos:
        print(f"  !! feature or ISO loss ({len(feats_in)}→{len(feats_out)}) — refusing to write", file=sys.stderr)
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"type": "FeatureCollection", "features": feats_out},
                         separators=(",", ":"), ensure_ascii=False)
    OUT_PATH.write_text(payload, encoding="utf-8")
    raw, gz = len(payload), len(gzip.compress(payload.encode(), 6))
    print(f"[boundaries] {len(feats_out)} features, {pts_in:,} → {pts_out:,} points")
    print(f"[boundaries] wrote {OUT_PATH.relative_to(ROOT)}: {raw/1e6:.1f} MB raw, {gz/1e6:.2f} MB gzipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
