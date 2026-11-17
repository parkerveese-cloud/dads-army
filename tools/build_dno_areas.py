"""Build Dads Army's outlines of the 14 GB electricity distribution licence areas (which network serves home, and so
which live power cut feed to read).

Source: NESO's "GIS Boundaries for GB DNO License Areas" GeoJSON (British National Grid, EPSG:27700):
    https://www.neso.energy/data-portal/gis-boundaries-gb-dno-license-areas
Supported by National Energy SO Open Data (NESO Open Data Licence).

    python3 tools/build_dno_areas.py gb-dno-license-areas-20240503-as-geojson.geojson dadsarmy/places/dno_areas.json.gz

The outlines are simplified to about 300 m and turned into latitude and longitude (to about 100 m), which is plenty to
say which network a house is on: near a boundary the app also looks at the neighbours (dno_covers). A build tool only:
the app just reads the .json.gz this writes. Standard library, and the app's own grid conversion.
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dadsarmy"))
import server  # noqa: E402   (for bng_to_latlon)

TOLERANCE_M = 300       # how far a simplified outline may stray, in metres (the source is in metres)
MIN_AREA_M2 = 2e6       # islets under 2 km² are dropped: a home there falls back to the nearest area


def ring_area(ring):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]))) / 2.0


def simplify(points, tol):
    """Douglas-Peucker, without recursion (long coastlines). A closed ring is split at its farthest point first."""
    if len(points) < 4:
        return points
    if points[0] == points[-1]:
        x0, y0 = points[0]
        far = max(range(1, len(points) - 1), key=lambda k: (points[k][0] - x0) ** 2 + (points[k][1] - y0) ** 2)
        return simplify(points[:far + 1], tol)[:-1] + simplify(points[far:], tol)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = points[i], points[j]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        best, idx = -1.0, -1
        for k in range(i + 1, j):
            x0, y0 = points[k]
            d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm
            if d > best:
                best, idx = d, k
        if best > tol and idx > 0:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(points, keep) if k]


def main(src, out):
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    areas = []
    for feat in data["features"]:
        p, g = feat["properties"], feat["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = []
        for poly in polys:
            outer = [(float(x), float(y)) for x, y in poly[0]]   # outer rings only: holes are rare and tiny
            if ring_area(outer) < MIN_AREA_M2:
                continue
            simple = simplify(outer, TOLERANCE_M)
            if len(simple) >= 4:
                rings.append([[lon, lat] for lat, lon in (server.bng_to_latlon(x, y) for x, y in simple)])
        areas.append({"id": int(p["ID"]), "dno": p.get("DNO"), "area": p.get("Area"), "name": p.get("DNO_Full"),
                      "rings": [[[round(lon, 4), round(lat, 4)] for lon, lat in r] for r in rings]})
        print(p["ID"], p.get("DNO"), p.get("Area"), len(rings), "rings", sum(len(r) for r in rings), "points")
    areas.sort(key=lambda a: a["id"])
    body = {"source": "NESO GIS Boundaries for GB DNO License Areas (20240503), simplified. "
                      "Supported by National Energy SO Open Data.", "areas": areas}
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(body, f, separators=(",", ":"))
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
