"""Build the small west-Indonesia outline used by the region bubble map.

Source: Natural Earth 1:50m land (public domain), via the world-atlas TopoJSON redistribution
(npm `world-atlas` 2.0.2, `land-50m.json`). Run once when the outline needs to change:

    npm pack world-atlas && tar xzf world-atlas-2.0.2.tgz
    uv run python scripts/build_map.py package/land-50m.json

Writes src/dk_sales/web/static/geo/indonesia-west.json: the projected, simplified outline path plus
the bounding box, so dk_sales.web.views can place region circles with the same projection.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BBOX = (94.5, 119.5, -9.5, 6.5)  # lon min, lon max, lat min, lat max: Sumatera to Kalimantan and Jawa
SCALE = 10  # svg units per degree
TOLERANCE = 2.0  # svg units (0,2 degree): plenty for a 300px wide map
OUT = Path(__file__).resolve().parents[1] / "src/dk_sales/web/static/geo/indonesia-west.json"


def decode(topo: dict) -> list[list[tuple[float, float]]]:
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx: list[int]) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(a[1:] if out else a)
        return out

    rings = []
    for g in topo["objects"]["land"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        for poly in polys:
            rings.extend(ring(r) for r in poly)
    return rings


def simplify(pts: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker: drop points closer than tol to the line between their neighbours."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = (dx * dx + dy * dy) ** 0.5 or 1e-9
    i, dmax = 0, 0.0
    for k in range(1, len(pts) - 1):
        x, y = pts[k]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm if (dx or dy) else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        if d > dmax:
            i, dmax = k, d
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[: i + 1], tol)[:-1] + simplify(pts[i:], tol)


def project(lon: float, lat: float) -> tuple[float, float]:
    return (lon - BBOX[0]) * SCALE, (BBOX[3] - lat) * SCALE


def main(src: str) -> None:
    topo = json.loads(Path(src).read_text())
    parts = []
    for r in decode(topo):
        lons = [p[0] for p in r]
        lats = [p[1] for p in r]
        if max(lons) < BBOX[0] or min(lons) > BBOX[1] or max(lats) < BBOX[2] or min(lats) > BBOX[3]:
            continue
        if (max(lons) - min(lons)) * (max(lats) - min(lats)) < 0.08:  # drop islets smaller than ~30 km across
            continue
        w, h = (BBOX[1] - BBOX[0]) * SCALE, (BBOX[3] - BBOX[2]) * SCALE
        pts: list[tuple[float, float]] = []
        for x, y in simplify([project(lon, lat) for lon, lat in r], TOLERANCE):
            # Clamp to the map box (plus a margin) so mainland Asia does not spill outside the map.
            p = (round(min(max(x, -4), w + 4)), round(min(max(y, -4), h + 4)))
            if not pts or p != pts[-1]:
                pts.append(p)
        if len(pts) >= 4:
            parts.append("M" + "L".join(f"{x} {y}" for x, y in pts) + "Z")
    w, h = (BBOX[1] - BBOX[0]) * SCALE, (BBOX[3] - BBOX[2]) * SCALE
    OUT.write_text(json.dumps({"source": "Natural Earth 1:50m land (public domain), world-atlas 2.0.2", "bbox": BBOX, "scale": SCALE, "width": w, "height": h, "path": "".join(parts)}))
    print(f"{OUT}: {len(parts)} shapes, {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main(sys.argv[1])
