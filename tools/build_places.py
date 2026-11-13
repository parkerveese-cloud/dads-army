"""Build Dads Army's UK list of possible refuges and help points from an OpenStreetMap extract.

Run in WSL with pyosmium (a build tool only: the app itself just reads the .tsv.gz this writes):
    python3 extract_places.py ~/osm/uk.osm.pbf out/uk.tsv.gz
Rows: lat, lon, type code, name, height (hills only). Data (c) OpenStreetMap contributors, ODbL.
"""
import gzip
import re
import sys
import time

import osmium

TYPES = {"community": "c", "leisure": "l", "library": "b", "hospital": "h", "fire": "f", "police": "p",
         "assembly": "a", "high": "e", "park": "k"}
LABEL = {"community": "Community centre", "leisure": "Leisure centre", "library": "Library", "hospital": "Hospital",
         "fire": "Fire station", "police": "Police station", "assembly": "Assembly point", "high": "Hill",
         "park": "Park"}
ELE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(m|metres|meters)?\s*$", re.I)
# "Sports centre" in OpenStreetMap includes private clubs and single-sport venues: no use as a refuge.
NOT_LEISURE = re.compile(
    r"\b(club|cricket|golf|tennis|bowls?|bowling|rugby|football|squash|gym|fitness|dojo|karate|judo|taekwondo|boxing|"
    r"yoga|pilates|riding|equestrian|stables?|sailing|rowing|canoe|kayak|shooting|archery|climbing|bouldering|dance|"
    r"studio|off.?road|paintball|karting|snooker|darts|crossfit|motor|racing|speedway|stadium|ground|pavilion|"
    r"academy|trampoline|gymnastics|skate|ski|ice rink|bowl|racecourse|karts?|go.?karts?|flyers|model|aero|"
    r"powersports|airsoft|laser|quad|motocross|polo|hockey)\b", re.I)


def classify(t, is_node):
    if t.get("access") in ("private", "no"):
        return None
    a, l, n = t.get("amenity"), t.get("leisure"), t.get("natural")
    if a in ("community_centre", "townhall"):
        return "community"
    if a == "library":
        return "library"
    if a == "hospital" and t.get("emergency") == "yes":
        return "hospital"
    if a == "fire_station":
        return "fire"
    if a == "police":
        return "police"
    if l == "sports_centre" and t.get("name") and not NOT_LEISURE.search(t.get("name")):
        return "leisure"
    if t.get("emergency") == "assembly_point":
        return "assembly"
    if is_node and n in ("peak", "hill") and t.get("name") and ELE.match(t.get("ele", "")):
        return "high"
    if l == "park" and t.get("name"):
        return "park"
    return None


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()[:70]


class Places(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []

    def add(self, kind, lat, lon, tags):
        name = clean(tags.get("name")) or LABEL[kind]
        ele = ""
        if kind == "high":
            ele = str(int(round(float(ELE.match(tags.get("ele")).group(1)))))
        self.rows.append((round(lat, 5), round(lon, 5), kind, name, ele))

    def node(self, n):
        if not n.tags:
            return
        kind = classify(n.tags, True)
        if kind and n.location.valid():
            self.add(kind, n.location.lat, n.location.lon, n.tags)

    def way(self, w):
        kind = classify(w.tags, False)
        if not kind:
            return
        pts = [(nd.location.lat, nd.location.lon) for nd in w.nodes if nd.location.valid()]
        if pts:
            self.add(kind, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), w.tags)

    def area(self, a):
        if a.from_way():   # closed ways are done in way()
            return
        kind = classify(a.tags, False)
        if not kind:
            return
        pts = [(nd.lat, nd.lon) for ring in a.outer_rings() for nd in ring if nd.location.valid()]
        if pts:
            self.add(kind, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), a.tags)


def main(src, out):
    t0 = time.time()
    h = Places()
    keys = osmium.filter.KeyFilter("amenity", "leisure", "emergency", "natural")
    h.apply_file(src, locations=True, idx="flex_mem", filters=[keys])
    print("read %d candidates in %.0fs" % (len(h.rows), time.time() - t0), flush=True)
    # The same place as a point and as a building: keep one.
    seen, rows = set(), []
    for r in sorted(h.rows, key=lambda r: (r[2], r[3].lower(), r[0], r[1])):
        key = (r[2], r[3].lower(), round(r[0], 3), round(r[1], 3))
        if key in seen:
            continue
        seen.add(key)
        rows.append(r)
    counts = {}
    for r in rows:
        counts[r[2]] = counts.get(r[2], 0) + 1
    print("kept", len(rows), counts, flush=True)
    rows.sort(key=lambda r: (r[0], r[1]))
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write("# Dads Army places: lat, lon, type, name, height. Data (c) OpenStreetMap contributors, ODbL "
                "(https://www.openstreetmap.org/copyright). Built %s.\n" % time.strftime("%Y-%m-%d"))
        for lat, lon, kind, name, ele in rows:
            f.write("%s\t%s\t%s\t%s\t%s\n" % (repr(lat), repr(lon), TYPES[kind], name.replace("\t", " "), ele))
    print("done in %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
