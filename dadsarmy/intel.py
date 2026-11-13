"""Live alerts ("intel") for Dads Army: public UK resilience feeds, fetched from the source.

Every source is official open data, fetched directly (no scraping, no middleman):
  - Environment Agency flood warnings      (Open Government Licence v3.0)
  - Met Office severe weather warnings     (Crown copyright, RSS)
  - UK Power Networks live power cuts      (CC BY 4.0)
  - Elexon BMRS system warnings (grid)     (Elexon open data, BMRS licence)
  - DEFRA UK-AIR regional air pollution    (Open Government Licence v3.0)
  - NOAA SWPC planetary K-index            (US Government, public domain)

  - National Grid (NGED) live power cuts    (National Grid Connected Data)
  - NASA FIRMS satellite heat detections    (NASA LANCE open data)
  - National Gas storage stock levels       (National Gas Transmission data portal)
  - Environment Agency river level gauges   (Open Government Licence v3.0)
  - European Central Bank reference rates   (via frankfurter.dev)
  - Yahoo Finance chart data                (unofficial; stock indices and commodities)

Privacy: nothing about where you live is sent to these feeds. Each one is a national list that is
filtered here. The one exception is the optional map postcode, looked up once at postcodes.io when
it's saved.

Stdlib only. One background thread; each source has its own refresh interval, keeps its last good
result when a fetch fails, and the cache survives restarts (DATA_DIR/intel_cache.json).
"""
import datetime as dt
import json
import os
import re
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "DadsArmy/2.0 (self-hosted Home Assistant add-on; household readiness)"
TIMEOUT = 20

# Levels, lowest to highest. "none" means checked and nothing to report.
LEVELS = ["none", "info", "minor", "moderate", "severe"]
LEVEL_RANK = {k: i for i, k in enumerate(LEVELS)}

MET_REGIONS = {
    "ee": "East of England", "em": "East Midlands", "se": "London & South East England",
    "ne": "North East England", "nw": "North West England",
    "sw": "South West England", "wm": "West Midlands", "yh": "Yorkshire & Humber",
    "wl": "Wales", "ni": "Northern Ireland", "dg": "Dumfries, Galloway, Lothian & Borders",
    "st": "Strathclyde", "ta": "Central, Tayside & Fife", "gr": "Grampian",
    "he": "Highlands & Eilean Siar", "os": "Orkney & Shetland",
}
MET_CENTRES = {   # roughly the middle of each warning region, for the map
    "ee": (52.3, 0.6), "em": (52.9, -1.0), "se": (51.3, -0.4), "ne": (54.9, -1.8), "nw": (54.1, -2.7),
    "sw": (50.8, -3.6), "wm": (52.5, -2.2), "yh": (53.9, -1.2), "wl": (52.3, -3.7), "ni": (54.6, -6.7),
    "dg": (55.5, -3.2), "st": (55.8, -4.9), "ta": (56.4, -3.5), "gr": (57.2, -2.6), "he": (57.5, -5.0),
    "os": (59.6, -2.0),
}
AIR_REGIONS = [
    "Central Scotland", "East Midlands", "Eastern", "Edinburgh Urban Area", "Glasgow Urban Area",
    "Greater London", "Highland", "North East", "North East Scotland", "North Wales", "North West & Merseyside",
    "Northern Ireland", "Scottish Borders", "South East", "South Wales", "South West", "West Midlands",
    "Yorkshire & Humberside",
]

# Elexon warning types that matter to a household (others are trading/settlement notices).
GRID_KEEP = re.compile(r"MARGIN|CAPACITY MARKET|DEMAND CONTROL|HIGH RISK|NISM|ELECTRICITY SUPPLY|"
                       r"SYSTEM WARNING|LOAD MANAGEMENT|BLACK START|EMERGENCY", re.I)

DEFAULTS = {
    "intel_enabled": 0,
    "intel_county": "",            # Environment Agency county, e.g. "Cambridgeshire"
    "intel_met_region": "",        # Met Office region code, e.g. "ee"
    "intel_postcodes": "",         # UKPN postcode districts, e.g. "AB12 AB3" (filtered locally)
    "intel_air_region": "",        # UK-AIR region name, e.g. "Eastern"
    "intel_floods": 1,
    "intel_weather": 1,
    "intel_power": 1,
    "intel_grid": 1,
    "intel_air": 1,
    "intel_space": 0,
    "intel_fires": 1,
    "intel_gas": 1,
    "intel_rivers": 1,
    "intel_fx": 1,
    "intel_markets": 1,
    "intel_trends": 1,             # look for worrying trends across checks
    "intel_map": 1,                # show the map (its background tiles come from OpenStreetMap)
    "intel_radius_km": 15,         # "near you" on the map
    "intel_uk": 1,                 # also show alerts elsewhere in the UK on the map (context, not alerts)
    "intel_map_postcode": "",      # centre the map here instead of Home Assistant's home
    "intel_map_where": "",         # [lat, lon] for that postcode, looked up when it's saved
}
RADIUS_LIMITS = (2, 60)


# ---------------------------------------------------------------------------
# Geometry helpers (map)
# ---------------------------------------------------------------------------
def km_between(a, b):
    """Great-circle distance in km between (lat, lon) pairs."""
    import math
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def _simplify(points, tol):
    """Douglas-Peucker on [lon, lat] points (iterative, so long rings don't hit the recursion limit)."""
    if len(points) < 4:
        return points
    if points[0] == points[-1]:
        # A closed ring: start and end are the same point, so split it at the point farthest from
        # the start and simplify each half (otherwise every distance is measured from one point).
        x0, y0 = points[0]
        far = max(range(1, len(points) - 1), key=lambda k: (points[k][0] - x0) ** 2 + (points[k][1] - y0) ** 2)
        return _simplify(points[:far + 1], tol)[:-1] + _simplify(points[far:], tol)
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
            stack.append((i, idx))
            stack.append((idx, j))
    return [p for p, k in zip(points, keep) if k]


def _shrink_geometry(geom, max_points=700):
    """A flood area outline small enough for a phone: simplified rings as [[lat, lon], ...] lists."""
    polys = geom["coordinates"] if geom.get("type") == "MultiPolygon" else [geom.get("coordinates") or []]
    rings = [ring for poly in polys for ring in poly[:1]]   # outer rings only
    tol = 0.0004
    while True:
        out = [_simplify([(float(p[0]), float(p[1])) for p in ring], tol) for ring in rings]
        out = [r for r in out if len(r) >= 4]
        if sum(len(r) for r in out) <= max_points or tol > 0.05:
            break
        tol *= 2
    return [[[round(y, 5), round(x, 5)] for x, y in r] for r in out]


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status != 200:
            raise IOError("HTTP %s" % r.status)
        return r.read()


def _get_json(url):
    return json.loads(_get(url).decode("utf-8"))


def _text(s, n=600):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def _postcode_districts(raw):
    out = []
    for p in re.split(r"[\s,;]+", (raw or "").upper()):
        p = re.sub(r"[^A-Z0-9]", "", p)
        if re.match(r"^[A-Z]{1,2}[0-9][0-9A-Z]?$", p) and p not in out:
            out.append(p)
    return out[:12]


# ---------------------------------------------------------------------------
# Sources. Each returns a list of items: {level, title, detail, area, time, url, scope, lat?, lon?}
#   scope: "yours" (your county/region/postcode: counts as an alert), "near" (within the map radius)
#   or "uk" (elsewhere: shown on the map for context only).
# ---------------------------------------------------------------------------
def _radius(cfg):
    try:
        return min(RADIUS_LIMITS[1], max(RADIUS_LIMITS[0], float(cfg.get("intel_radius_km") or 15)))
    except (TypeError, ValueError):
        return 15.0


def _scope(yours, km, cfg):
    if yours:
        return "yours"
    return "near" if km is not None and km <= _radius(cfg) else "uk"


def _km(cfg, lat, lon):
    home = cfg.get("_home")
    if not home or lat is None or lon is None:
        return None
    return round(km_between(home, (lat, lon)), 1)


def flood_area(code, geo, budget):
    """Where a flood warning area is (cached for a month). budget limits new lookups per refresh."""
    areas = geo.setdefault("area", {})
    have = areas.get(code)
    if have and time.time() - have.get("at", 0) < 30 * 24 * 3600:
        return have
    if budget[0] <= 0:
        return have or {}
    budget[0] -= 1
    try:
        a = _get_json("https://environment.data.gov.uk/flood-monitoring/id/floodAreas/" + urllib.parse.quote(code))
        a = a.get("items") or {}
        a = a[0] if isinstance(a, list) else a
        have = {"at": time.time(), "lat": round(float(a["lat"]), 5), "lon": round(float(a["long"]), 5),
                "label": _text(a.get("label"), 120), "county": _text(a.get("county"), 120)}
    except Exception:
        have = {"at": time.time() - 29 * 24 * 3600}   # try again in a day
    areas[code] = have
    for old in sorted(areas, key=lambda c: areas[c].get("at", 0))[:-600]:
        areas.pop(old, None)
    return have


def flood_outline(code, geo):
    """A simplified outline for one flood area (only for alerts near you), cached for a week."""
    polys = geo.setdefault("poly", {})
    have = polys.get(code)
    if have and time.time() - have.get("at", 0) < 7 * 24 * 3600:
        return have["rings"]
    try:
        g = _get_json("https://environment.data.gov.uk/flood-monitoring/id/floodAreas/%s/polygon"
                      % urllib.parse.quote(code))
        rings = _shrink_geometry(g["features"][0]["geometry"])
    except Exception:
        rings = []
    polys[code] = {"at": time.time(), "rings": rings}
    for old in sorted(polys, key=lambda c: polys[c]["at"])[:-40]:   # keep the cache small
        polys.pop(old, None)
    return rings


def fetch_floods(cfg):
    """Every flood warning in force in England (nothing about you is sent); yours = your county or radius."""
    county = cfg["intel_county"].strip().lower()
    geo = cfg.get("_geo") if isinstance(cfg.get("_geo"), dict) else {}
    data = _get_json("https://environment.data.gov.uk/flood-monitoring/id/floods")
    items, budget = [], [80]
    lvl = {1: "severe", 2: "moderate", 3: "minor"}
    for f in data.get("items") or []:
        sev = int(f.get("severityLevel") or 4)
        if sev not in lvl:
            continue  # 4 = no longer in force
        area = f.get("floodArea") or {}
        code = str(f.get("floodAreaID") or area.get("notation") or "")
        spot = flood_area(code, geo, budget) if code else {}
        lat, lon = spot.get("lat"), spot.get("lon")
        km = _km(cfg, lat, lon)
        counties = str(area.get("county") or spot.get("county") or "")
        scope = _scope(bool(county) and county in counties.lower(), km, cfg)
        items.append({
            "code": code, "lat": lat, "lon": lon, "km": km, "scope": scope,
            "rings": flood_outline(code, geo) if code and scope != "uk" and "_geo" in cfg else [],
            "level": lvl[sev],
            "title": "%s: %s" % (f.get("severity") or "Flood alert", _text(f.get("description"), 160)),
            "detail": _text(f.get("message"), 500),
            "area": _text(counties, 80),
            "time": f.get("timeMessageChanged") or f.get("timeRaised") or "",
            "url": ("https://check-for-flooding.service.gov.uk/target-area/" + urllib.parse.quote(code))
                   if code else "https://check-for-flooding.service.gov.uk/",
        })
    items.sort(key=lambda i: (i["scope"] != "yours", -LEVEL_RANK[i["level"]]))
    return items


RIVER_API = "https://environment.data.gov.uk/flood-monitoring"


def _num(v):
    if isinstance(v, list):   # the feed occasionally gives a pair of values: take the last
        v = v[-1] if v else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def river_gauges(geo):
    """Every river gauge in England that has a normal range, keyed by its measure id (cached for a week)."""
    have = geo.get("gauges") if isinstance(geo.get("gauges"), dict) else None
    if have and time.time() - have.get("at", 0) < 7 * 24 * 3600:
        return have["g"]
    try:
        data = _get_json(RIVER_API + "/id/stations?parameter=level&_limit=10000&_view=full")
    except (urllib.error.URLError, IOError, ValueError):
        if have:
            return have["g"]   # keep using the old list
        raise
    out = {}
    for s in data.get("items") or []:
        scale = s.get("stageScale") if isinstance(s.get("stageScale"), dict) else {}
        lat, lon = _num(s.get("lat")), _num(s.get("long"))
        low, high = _num(scale.get("typicalRangeLow")), _num(scale.get("typicalRangeHigh"))
        if lat is None or lon is None or low is None or high is None or high <= low:
            continue
        if "Active" not in str(s.get("status") or "Active"):
            continue
        measures = s.get("measures") or []
        measures = [measures] if isinstance(measures, dict) else measures
        stage = [m for m in measures if isinstance(m, dict) and m.get("parameter") == "level"
                 and m.get("qualifier") == "Stage"]
        if not stage:
            continue   # groundwater and tidal gauges aren't rivers
        top = scale.get("maxOnRecord") if isinstance(scale.get("maxOnRecord"), dict) else {}
        out[str(stage[0].get("@id") or "").rsplit("/", 1)[-1]] = {
            "ref": str(s.get("stationReference") or ""), "label": _text(s.get("label"), 80),
            "river": _text(s.get("riverName"), 80), "lat": round(lat, 5), "lon": round(lon, 5),
            "low": low, "high": high, "max": _num(top.get("value")), "rloi": str(s.get("RLOIid") or ""),
        }
    if not out:
        raise ValueError("No river gauges in the Environment Agency feed")
    geo["gauges"] = {"at": time.time(), "g": out}
    return out


def _river_name(g):
    river, label = g["river"], g["label"]
    if not river or river.lower() == label.lower():
        return label
    return "%s at %s" % (river, label)


def fetch_rivers(cfg):
    """River levels against each gauge's normal range: the gauges near you, and any running high elsewhere.

    Two national lists (the gauges, weekly; the latest readings) filtered here: nothing about you is sent."""
    geo = cfg.get("_geo") if isinstance(cfg.get("_geo"), dict) else {}
    gauges = river_gauges(geo)
    data = _get_json(RIVER_API + "/data/readings?latest&parameter=level")
    hist = geo.setdefault("river_hist", {})
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%SZ")
    near, far = [], []
    for r in data.get("items") or []:
        g = gauges.get(str(r.get("measure") or "").rsplit("/", 1)[-1])
        v, when = _num(r.get("value")), str(r.get("dateTime") or "")
        if not g or v is None or when < old:
            continue   # not a river gauge, or it has stopped reporting
        low, high, top = g["low"], g["high"], g["max"]
        km = _km(cfg, g["lat"], g["lon"])
        is_near = km is not None and km <= _radius(cfg)
        if v <= high and not is_near:
            continue   # normal and far away: nothing to show
        near_record = top is not None and top > high and v >= high + 0.8 * (top - high)
        clear = high + max(0.02, 0.05 * (high - low))   # a hair over the line isn't worth a warning
        if v <= clear and not is_near:
            continue
        state = "high" if v > clear else "low" if v < low else "normal"
        level = "none" if state != "high" else "moderate" if near_record else "minor"
        bits = ["Normal range %.2f to %.2f m." % (low, high)]
        if top is not None:
            bits.append("Highest on record %.2f m." % top)
        item = {
            "river": True, "ref": g["ref"], "lat": g["lat"], "lon": g["lon"], "km": km,
            "scope": ("yours" if level != "none" else "near") if is_near else "uk", "level": level,
            "state": state, "value": round(v, 3), "low": low, "high": high, "max": top,
            "name": _river_name(g),
            "title": "%s: %.2f m, %s" % (_river_name(g), v, {
                "high": "close to its record" if near_record else "above normal", "low": "below normal",
                "normal": "normal"}[state]),
            "area": ("%g km away" % km) if is_near else "", "time": when,
            "url": ("https://check-for-flooding.service.gov.uk/station/" + urllib.parse.quote(g["rloi"]))
                   if g["rloi"] else "https://check-for-flooding.service.gov.uk/river-and-sea-levels",
        }
        if is_near:   # remember recent readings for the gauges near you, for a trend
            series = [p for p in hist.get(g["ref"], []) if p[0] != when][-95:] + [[when, round(v, 3)]]
            series.sort()
            hist[g["ref"]] = series
            back = [p for p in series if p[0] <= (dt.datetime.strptime(when[:19], "%Y-%m-%dT%H:%M:%S")
                                                  - dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")]
            if back:
                diff = v - back[-1][1]
                item["trend"] = "rising" if diff > 0.02 else "falling" if diff < -0.02 else "steady"
                bits.append(item["trend"].capitalize() + ".")
            if len(series) >= 3:
                item["series"] = series[-48:]
        item["detail"] = " ".join(bits) + (" Flooding is possible when a river is above its normal range."
                                             if state == "high" else "")
        (near if is_near else far).append(item)
    seen = set(i["ref"] for i in near)
    for ref in [k for k in hist if k not in seen]:   # moved house, or a smaller radius
        hist.pop(ref, None)
    near.sort(key=lambda i: (-LEVEL_RANK[i["level"]], i["km"]))
    far.sort(key=lambda i: -(i["value"] - i["high"]) / (i["high"] - i["low"]))
    return near[:30] + far[:150]


def fetch_weather(cfg):
    """Every Met Office warning in the UK; yours = it covers your region."""
    region = cfg["intel_met_region"].strip().lower()
    raw = _get("https://www.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/UK",
               "application/rss+xml, application/xml")
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):
        title = _text(it.findtext("title"), 300)
        t = title.lower()
        level = "severe" if "red" in t else "moderate" if "amber" in t else "minor" if "yellow" in t else "info"
        covers = [c for c, name in MET_REGIONS.items() if name.lower() in t]
        items.append({
            "level": level,
            "title": title,
            "detail": _text(it.findtext("description"), 500),
            "area": ", ".join(MET_REGIONS[c] for c in covers) or "UK",
            "regions": covers,
            "scope": "yours" if region and region in covers else "uk",
            "time": _text(it.findtext("pubDate"), 40),
            "url": (it.findtext("link") or "https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings").strip(),
        })
    items.sort(key=lambda i: (i["scope"] != "yours", -LEVEL_RANK[i["level"]]))
    return items


def _int(v):
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def _power_item(cfg, rx, *, planned, homes, lat, lon, postcodes, when, detail, zone, url, network):
    pcs = " " + re.sub(r"([A-Z]{1,2}[0-9][0-9A-Z]?)([0-9][A-Z]{2})", r"\1 \2",
                       postcodes.upper().replace(";", " ").replace(",", " "))
    yours = bool(rx and rx.search(pcs))
    km = _km(cfg, lat, lon)
    scope = _scope(yours, km, cfg)
    if scope == "uk" and (planned or homes < 50):
        return None   # the rest of the country: only the bigger unplanned cuts, or the map fills with dots
    level = "info" if planned else ("moderate" if homes >= 100 else "minor")
    return {
        "level": level, "scope": scope, "km": km, "lat": lat, "lon": lon, "network": network,
        "title": ("Planned power cut" if planned else "Power cut")
                 + (" · %d home%s" % (homes, "" if homes == 1 else "s") if homes else "")
                 + (" · %g km away" % km if scope == "near" and km is not None else ""),
        "detail": _text(detail, 400),
        "area": _text(", ".join(p.strip() for p in re.split(r"[;,]", postcodes) if p.strip())[:120], 120)
                + (" (%s)" % zone if zone else ""),
        "time": when, "url": url,
    }


def _ukpn(cfg, rx):
    base = "https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-live-faults/records"
    rows, offset = [], 0
    while offset < 2000:  # whole network list, filtered here so the postcode never leaves the box
        page = _get_json(base + "?limit=100&offset=%d" % offset)
        res = page.get("results") or []
        rows.extend(res)
        offset += len(res)
        if not res or offset >= int(page.get("total_count") or 0):
            break
    out = []
    for r in rows:
        kind = (r.get("powercuttype") or "").strip().lower()
        if r.get("restoreddatetime") or kind == "restored" or str(r.get("statusid")) == "5":
            continue  # power is back
        gp = r.get("geopoint") or {}
        try:
            lat, lon = round(float(gp["lat"]), 5), round(float(gp["lon"]), 5)
        except (KeyError, TypeError, ValueError):
            lat = lon = None
        when = _text(r.get("incidenttypetbcestimatedfriendlydescription"), 80)
        if not when or when.lower() == "to be confirmed":
            eta = _text(r.get("estimatedrestorationdate"), 30)
            when = ("Back by " + eta.replace("T", " ")[:16]) if eta else "Restore time to be confirmed"
        it = _power_item(cfg, rx, planned=kind == "planned",
                         homes=_int(r.get("nocustomeraffected")) or _int(r.get("noplannedcustomers")),
                         lat=lat, lon=lon,
                         postcodes=str(r.get("postcodesaffected") or "") + ";" + str(r.get("fullpostcodedata") or ""),
                         when=when,
                         detail=r.get("mainmessage") or r.get("message") or r.get("plannedincidentreason")
                         or r.get("incidentcategorycustomerfriendlydescription"),
                         zone=_text(r.get("operatingzone"), 40).title(), network="UK Power Networks",
                         url="https://www.ukpowernetworks.co.uk/power-cut/map")
        if it:
            it["area"] = _text((r.get("postcodesaffected") or "").replace(";", ", "), 120) + \
                (" (%s)" % _text(r.get("operatingzone"), 40).title() if r.get("operatingzone") else "")
            out.append(it)
    return out


NGED_CSV = ("https://connecteddata.nationalgrid.co.uk/dataset/d6672e1e-c684-4cea-bb78-c7e5248b62a2/resource/"
            "292f788f-4339-455b-8cc0-153e14509d4d/download/power_outage_ext.csv")


def _nged(cfg, rx):
    import csv
    import io
    text = _get(NGED_CSV, "text/csv").decode("utf-8-sig", "replace")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        status = (r.get("Status") or "").lower()
        if "restor" in status or "closed" in status or "cancel" in status:
            continue
        try:
            lat, lon = round(float(r["Location Latitude"]), 5), round(float(r["Location Longitude"]), 5)
        except (KeyError, TypeError, ValueError):
            lat = lon = None
        etr = _text(r.get("ETR"), 30)
        it = _power_item(cfg, rx, planned=(r.get("Planned") or "").strip().lower() == "true",
                         homes=_int(r.get("Confirmed Off")) or _int(r.get("Predicted Off")), lat=lat, lon=lon,
                         postcodes=r.get("Postcodes") or "",
                         when=("Back by " + etr.replace("T", " ")[:16]) if etr else "Restore time to be confirmed",
                         detail="%s (%s)" % (r.get("Status") or "Power cut", _text(r.get("Category"), 40).title()),
                         zone=_text(r.get("Region"), 40), network="National Grid (NGED)",
                         url="https://powercuts.nationalgrid.co.uk/")
        if it:
            out.append(it)
    return out


def fetch_power(cfg):
    """Live power cuts from UK Power Networks and National Grid (NGED), filtered here."""
    districts = _postcode_districts(cfg["intel_postcodes"])
    # A district followed by a space and the inward digit: "AB12 5" matches AB12, "AB120 1" doesn't.
    rx = re.compile(r"(?<![A-Z0-9])(%s) [0-9]" % "|".join(map(re.escape, districts))) if districts else None
    items, errors = [], []
    for name, fn in (("UK Power Networks", _ukpn), ("National Grid (NGED)", _nged)):
        try:
            items.extend(fn(cfg, rx))
        except (urllib.error.URLError, IOError, ValueError, KeyError) as e:
            errors.append("%s: %s" % (name, str(getattr(e, "reason", e))[:80]))
    if len(errors) == 2:
        raise IOError("; ".join(errors))
    if errors:   # one network down: keep the other, and say so
        items.append({"level": "info", "scope": "yours", "title": "Couldn't check " + errors[0].split(":")[0],
                      "detail": errors[0], "area": "", "time": "", "url": ""})
    items.sort(key=lambda i: ({"yours": 0, "near": 1}.get(i.get("scope"), 2), -LEVEL_RANK[i["level"]]))
    return items


FIRMS = [  # NASA FIRMS public 24-hour files for Europe (no key needed for these)
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv",
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-21-viirs-c2/csv/J2_VIIRS_C2_Europe_24h.csv",
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Europe_24h.csv",
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Europe_24h.csv",
]
UK_BOX = (49.8, 60.95, -8.7, 1.9)   # south, north, west, east (UK and Ireland)


def _offshore(lat, lon):
    """Roughly the North Sea off eastern England and Scotland (where the platform flares are)."""
    if lat > 59.5:
        return False   # Orkney and Shetland: leave alone
    return (lat > 53.6 and lon > 0.3) or (lat > 55.9 and lon > -1.4)


def fetch_fires(cfg):
    """Satellite heat detections in the last 24 hours across the UK and Ireland."""
    import csv
    import io
    seen, items, ok = set(), [], 0
    for url in FIRMS:
        try:
            text = _get(url, "text/csv").decode("utf-8", "replace")
            ok += 1
        except (urllib.error.URLError, IOError):
            continue
        for r in csv.DictReader(io.StringIO(text)):
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (UK_BOX[0] <= lat <= UK_BOX[1] and UK_BOX[2] <= lon <= UK_BOX[3]):
                continue
            if _offshore(lat, lon):
                continue   # North Sea oil and gas platforms flare all day: not wildfires
            conf = str(r.get("confidence") or "").strip().lower()
            if conf in ("l", "low") or (conf.isdigit() and int(conf) < 50):
                continue   # low-confidence detections are mostly noise
            key = (round(lat, 2), round(lon, 2))   # several satellites see the same fire
            if key in seen:
                continue
            seen.add(key)
            km = _km(cfg, lat, lon)
            scope = _scope(False, km, cfg)
            t = str(r.get("acq_time") or "").zfill(4)
            items.append({
                "level": "minor" if scope == "near" else "info", "scope": scope, "fire": True,
                "lat": round(lat, 4), "lon": round(lon, 4), "km": km,
                "title": "Satellite heat detection" + (" · %g km away" % km if km is not None and scope == "near" else ""),
                "detail": "Seen by %s at %s:%s UTC (fire radiative power %s MW). Could be a wildfire, a controlled "
                          "burn or an industrial heat source." % (r.get("satellite") or "satellite", t[:2], t[2:],
                                                                  r.get("frp") or "?"),
                "area": "%.3f, %.3f" % (lat, lon), "time": "%s %s:%s UTC" % (r.get("acq_date") or "", t[:2], t[2:]),
                "url": "https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@%.4f,%.4f,12.0z" % (lon, lat),
            })
    if not ok:
        raise IOError("NASA FIRMS couldn't be reached")
    # Near ones count as yours: worth knowing about a fire within your radius.
    for i in items:
        if i["scope"] == "near":
            i["scope"] = "yours"
    items.sort(key=lambda i: (i["km"] if i["km"] is not None else 1e9))
    return items[:300]


GAS_URL = ("https://data.nationalgas.com/api/find-gas-data-download?applicableFor=Y&dateFrom=%s&dateTo=%s"
           "&dateType=GASDAY&latestFlag=Y&ids=PUBOBJ330,PUBOBJ333&type=CSV")


def fetch_gas(cfg):
    """Great Britain's gas in storage (National Gas Transmission data portal): how full, and how fast it's going."""
    import csv
    import io
    today = dt.date.today()
    text = _get(GAS_URL % ((today - dt.timedelta(days=45)).isoformat(), today.isoformat()), "text/csv")
    stock, space = {}, {}
    for r in csv.DictReader(io.StringIO(text.decode("utf-8-sig", "replace"))):
        try:
            day = dt.datetime.strptime(r["Applicable For"], "%d/%m/%Y").date()
            val = float(r["Value"]) / 1e9   # kWh -> TWh
        except (KeyError, TypeError, ValueError):
            continue
        item = (r.get("Data Item") or "").lower()
        (stock if "stock level" in item else space if "available capacity" in item else {})[day] = val
    days = sorted(d for d in stock if d in space)
    if not days:
        raise ValueError("No storage figures in the National Gas feed")
    last = days[-1]
    full = stock[last] / (stock[last] + space[last]) if stock[last] + space[last] > 0 else 0
    week = [d for d in days if d <= last - dt.timedelta(days=7)]
    change = stock[last] - stock[week[-1]] if week else None
    per_day = -change / max(1, (last - week[-1]).days) if week else None
    lasts = stock[last] / per_day if per_day and per_day > 0.05 else None
    level = "moderate" if full < 0.15 or (lasts is not None and lasts < 10) else \
        "minor" if full < 0.25 or (lasts is not None and lasts < 20) else "none"
    title = "Gas storage %d%% full (%.1f TWh)" % (round(full * 100), stock[last])
    bits = []
    if change is not None:
        bits.append("%s%.1f TWh on a week ago" % ("+" if change >= 0 else "−", abs(change)))
    if lasts is not None:
        bits.append("about %d days at this week's rate of use" % round(lasts))
    return [{"level": level, "scope": "yours", "title": title,
             "detail": (("; ".join(bits))[:1].upper() + ("; ".join(bits))[1:] + ". " if bits else "") +
                       "Storage tops up imports and North Sea gas on cold days; most of Britain's gas doesn't come from storage.",
             "area": "Great Britain", "time": last.isoformat(), "url": "https://data.nationalgas.com/",
             "series": [[d.isoformat(), round(stock[d], 3)] for d in days],
             "full_pct": round(full * 100, 1), "days_left": round(lasts) if lasts else None}]


def fetch_grid(cfg):
    data = _get_json("https://data.elexon.co.uk/bmrs/api/v1/datasets/SYSWARN?format=json")
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)
    items = []
    for w in data.get("data") or []:
        kind = str(w.get("warningType") or "")
        text = str(w.get("warningText") or "")
        if not GRID_KEEP.search(kind + " " + text[:200]) or "SO-SO" in kind.upper():
            continue
        try:
            when = dt.datetime.fromisoformat(str(w.get("publishTime")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if when < cutoff:
            continue
        t = (kind + " " + text).upper()
        # An emergency instruction to one generator ("BM participant") is routine balancing, not a risk to supply.
        routine = "EMERGENCY INSTRUCTION" in t and not re.search(r"DEMAND CONTROL|HIGH RISK", t)
        cancelled = bool(re.search(r"\bCANCEL", t))
        if cancelled:
            level = "info"
        elif routine:
            level = "minor"
        else:
            level = "severe" if re.search(r"DEMAND CONTROL|HIGH RISK|EMERGENCY", t) else "moderate"
        name = "Grid notice" if kind.strip().lower() in ("", "other") else kind.title()
        items.append({
            "level": level, "scope": "yours",
            "title": name + (" (cancelled)" if cancelled else ""),
            "detail": _text(text.replace("\\n", " "), 500),
            "area": "Great Britain",
            "time": w.get("publishTime") or "",
            "url": "https://bmrs.elexon.co.uk/system-warnings",
        })
    return items


def fetch_air(cfg):
    region = cfg["intel_air_region"].strip()
    if not region:
        raise ValueError("Choose your air quality region in HQ")
    root = ET.fromstring(_get("https://uk-air.defra.gov.uk/assets/rss/current_region_levels.xml",
                              "application/rss+xml, application/xml"))
    for it in root.iter("item"):
        if (it.findtext("title") or "").strip().lower() != region.lower():
            continue
        desc = _text(it.findtext("description"), 200)
        m = re.search(r"index\s+(\d+)", desc, re.I)
        idx = int(m.group(1)) if m else 0
        if idx <= 3:
            return [{"level": "none", "scope": "yours", "title": "Air pollution low (index %d)" % idx, "detail": desc,
                     "area": region, "time": "", "url": "https://uk-air.defra.gov.uk/"}]
        level = "minor" if idx <= 6 else "moderate" if idx <= 9 else "severe"
        band = "moderate" if idx <= 6 else "high" if idx <= 9 else "very high"
        return [{"level": level, "scope": "yours", "title": "Air pollution %s (index %d)" % (band, idx), "detail": desc,
                 "area": region, "time": "", "url": "https://uk-air.defra.gov.uk/"}]
    raise ValueError("Region %r isn't in the UK-AIR feed" % region)


def fetch_space(cfg):
    rows = _get_json("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json")
    last = None
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("Kp") is not None:
            last = r
        elif isinstance(r, list) and len(r) > 1 and r[0] != "time_tag":  # older array format
            last = {"time_tag": r[0], "Kp": r[1]}
    if not last:
        raise ValueError("No K-index in the feed")
    kp = float(last["Kp"])
    if kp < 5:
        return [{"level": "none", "scope": "yours", "title": "Geomagnetic activity quiet (Kp %.1f)" % kp, "detail": "",
                 "area": "Global", "time": str(last.get("time_tag") or ""), "url": "https://www.swpc.noaa.gov/"}]
    g = min(5, int(kp) - 4)
    level = "minor" if g <= 2 else "moderate" if g <= 3 else "severe"
    return [{"level": level, "scope": "yours", "title": "Geomagnetic storm G%d (Kp %.1f)" % (g, kp),
             "detail": "Strong storms can disrupt power grids, GPS and radio.", "area": "Global",
             "time": str(last.get("time_tag") or ""), "url": "https://www.swpc.noaa.gov/"}]


# ---------------------------------------------------------------------------
# Money: the pound and the markets. Context for a household, not advice.
# ---------------------------------------------------------------------------
FX = [("USD", "US dollar"), ("EUR", "Euro"), ("JPY", "Japanese yen"), ("CNY", "Chinese yuan"),
      ("CAD", "Canadian dollar"), ("AUD", "Australian dollar"), ("CHF", "Swiss franc")]
MARKETS = [   # symbol, name, kind
    ("^FTSE", "FTSE 100", "index"), ("^FTMC", "FTSE 250", "index"), ("^GSPC", "S&P 500 (US)", "index"),
    ("^IXIC", "Nasdaq (US)", "index"), ("^GDAXI", "DAX (Germany)", "index"),
    ("^STOXX50E", "Euro Stoxx 50", "index"), ("^N225", "Nikkei 225 (Japan)", "index"),
    ("^HSI", "Hang Seng (Hong Kong)", "index"), ("000001.SS", "Shanghai Composite", "index"),
    ("BZ=F", "Brent crude oil", "commodity"), ("ZW=F", "Wheat", "commodity"), ("GC=F", "Gold", "commodity"),
]


def _pct(now, then):
    return round((now / then - 1) * 100, 2) if then else None


def _changes(series):
    """Percentage change over a day, a week (5 sessions) and a month (21 sessions) for [[date, value], ...]."""
    vals = [p[1] for p in series]
    out = {}
    for key, back in (("d1", 1), ("w1", 5), ("m1", 21)):
        out[key] = _pct(vals[-1], vals[-1 - back]) if len(vals) > back else None
    return out


def _move_level(ch, week, month, up=False):
    """How worrying a move is. week/month are (minor, moderate) thresholds in percent; up=True watches for rises."""
    sign = 1 if up else -1
    w = sign * ch["w1"] if ch.get("w1") is not None else 0
    m = sign * ch["m1"] if ch.get("m1") is not None else 0
    if w >= week[1] or m >= month[1]:
        return "moderate"
    if w >= week[0] or m >= month[0]:
        return "minor"
    return "none"


def _move_words(ch, up=False):
    sign = 1 if up else -1
    w = sign * ch["w1"] if ch.get("w1") is not None else 0
    m = sign * ch["m1"] if ch.get("m1") is not None else 0
    word = "up" if up else "down"
    return ("%s %.1f%% in a week" % (word, w)) if w >= m * 0.6 else ("%s %.1f%% in a month" % (word, m))


def fetch_fx(cfg):
    """The pound against the major currencies: European Central Bank daily reference rates (via frankfurter.dev)."""
    start = (dt.date.today() - dt.timedelta(days=100)).isoformat()
    data = _get_json("https://api.frankfurter.dev/v1/%s..?base=GBP&symbols=%s" % (start, ",".join(c for c, _n in FX)))
    rates = data.get("rates") or {}
    days = sorted(rates)
    if len(days) < 2:
        raise ValueError("No exchange rates in the feed")
    items = []
    for code, name in FX:
        series = [[d, float(rates[d][code])] for d in days if isinstance(rates[d].get(code), (int, float))]
        if len(series) < 2:
            continue
        ch = _changes(series)
        level = _move_level(ch, (3, 6), (6, 10)) if code in ("USD", "EUR") else "none"   # the two that set UK prices
        last = series[-1][1]
        item = {
            "level": level, "scope": "yours", "money": "fx", "code": code, "name": name, "value": last,
            "title": "£1 = %s %s" % (("%.2f" if last >= 20 else "%.4f") % last, code),
            "detail": "%s per pound. A weaker pound makes imported food, fuel and goods dearer." % name,
            "area": "", "time": series[-1][0], "url": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/"
                                                      "euro_reference_exchange_rates/html/index.en.html",
            "changes": ch, "series": series[-66:],
        }
        if level != "none":
            item["watch"] = "The pound is %s against the %s" % (_move_words(ch), name.lower() if code != "USD" else "US dollar")
            item["title"] = item["watch"]
        items.append(item)
    if not items:
        raise ValueError("No exchange rates in the feed")
    return items


def _market(symbol):
    d = _get_json("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=6mo&interval=1d"
                  % urllib.parse.quote(symbol))
    res = ((d.get("chart") or {}).get("result") or [None])[0] or {}
    meta = res.get("meta") or {}
    closes = (((res.get("indicators") or {}).get("quote") or [{}])[0].get("close")) or []
    series = [[dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat(), float(c)]
              for t, c in zip(res.get("timestamp") or [], closes) if isinstance(c, (int, float))]
    price = meta.get("regularMarketPrice")
    if isinstance(price, (int, float)) and series:
        today = dt.datetime.fromtimestamp(meta.get("regularMarketTime") or time.time(), dt.timezone.utc).date().isoformat()
        if series[-1][0] == today:
            series[-1][1] = float(price)
        else:
            series.append([today, float(price)])
    if len(series) < 2:
        raise ValueError("no prices")
    return series, str(meta.get("currency") or ""), meta.get("regularMarketTime")


def fetch_markets(cfg):
    """Major stock markets and a few commodities that reach household bills (Yahoo Finance chart data)."""
    items = []
    for symbol, name, kind in MARKETS:
        try:
            series, currency, when = _market(symbol)
        except (urllib.error.URLError, IOError, ValueError, KeyError, TypeError):
            continue
        ch = _changes(series)
        up = kind == "commodity" and symbol != "GC=F"   # dearer oil, gas and wheat is the worry; gold is a barometer
        level = "none" if symbol == "GC=F" else \
            _move_level(ch, (15, 25), (25, 40), up=True) if up else _move_level(ch, (7, 12), (12, 20))
        last = series[-1][1]
        item = {
            "level": level, "scope": "yours", "money": kind, "code": symbol, "name": name, "value": last,
            "currency": currency,
            "title": "%s: %s" % (name, ("{:,.0f}" if last >= 1000 else "{:,.2f}").format(last)),
            "detail": "", "area": "", "url": "https://finance.yahoo.com/quote/" + urllib.parse.quote(symbol),
            "time": dt.datetime.fromtimestamp(when, dt.timezone.utc).replace(microsecond=0).isoformat() if when else "",
            "changes": ch, "series": series[-66:],
        }
        if level != "none":
            item["watch"] = "%s is %s" % (name, _move_words(ch, up=up))
            item["title"] = item["watch"]
            item["detail"] = ("Dearer %s tends to reach household bills and shop prices within weeks."
                              % {"BZ=F": "oil", "ZW=F": "wheat"}.get(symbol, "commodities")) if up else \
                "A sharp fall in a major market. Context only: this isn't financial advice."
        items.append(item)
    if not items:
        raise IOError("The market feed couldn't be reached")
    return items


# ---------------------------------------------------------------------------
# Trends: a few numbers are kept from every check, and rules look for a worrying direction of travel.
# ---------------------------------------------------------------------------
TREND_KEEP = 14 * 24 * 3600
TREND_EVERY = 20 * 60
METRICS = {   # id: (source, label)
    "power_near": ("power", "Power cuts near you"),
    "power_uk": ("power", "Bigger power cuts across the networks"),
    "power_homes": ("power", "Homes without power"),
    "floods_near": ("floods", "Flood warnings near you"),
    "floods_uk": ("floods", "Flood warnings in force in England"),
    "rivers_high": ("rivers", "Rivers above their normal range"),
    "fires_uk": ("fires", "Satellite heat detections"),
    "grid": ("grid", "Grid notices"),
}


def measure(cache):
    """The numbers worth keeping from the current alerts: {metric: value}. Only sources with a good last check."""
    def items(sid):
        c = cache.get(sid) or {}
        return c.get("items") or [] if c.get("ok") else None
    out = {}
    power = items("power")
    if power is not None:
        cuts = [i for i in power if not i.get("title", "").startswith("Planned")]
        out["power_near"] = sum(1 for i in cuts if i.get("scope") != "uk")
        out["power_uk"] = len(cuts)
        out["power_homes"] = sum(int(m.group(1)) for m in (re.search(r"· (\d+) home", i.get("title", "")) for i in cuts) if m)
    floods = items("floods")
    if floods is not None:
        out["floods_near"] = sum(1 for i in floods if i.get("scope") != "uk")
        out["floods_uk"] = len(floods)
    rivers = items("rivers")
    if rivers is not None:
        out["rivers_high"] = sum(1 for i in rivers if i.get("state") == "high")
    fires = items("fires")
    if fires is not None:
        out["fires_uk"] = len(fires)
    grid = items("grid")
    if grid is not None:
        out["grid"] = sum(1 for i in grid if LEVEL_RANK.get(i.get("level"), 0) >= LEVEL_RANK["minor"])
    return out


def _at(series, now, hours):
    """The value about `hours` ago: the last sample at least that old (but not more than twice that old)."""
    old = [p for p in series if now - hours * 7200 <= p[0] <= now - hours * 3600]
    return old[-1][1] if old else None


def _usual(series, now):
    """The middle value over the days before today, once there are three days of history. None until then."""
    past = sorted(p[1] for p in series if p[0] < now - 24 * 3600)
    if not past or now - series[0][0] < 3 * 24 * 3600:
        return None
    return past[len(past) // 2]


def find_trends(cache, hist, now=None):
    """Worrying directions of travel: [{id, source, level, title, detail, metric?}]."""
    now = now or time.time()
    out = []

    def add(tid, source, level, title, detail, **more):
        out.append(dict(id=tid, source=source, level=level, title=title, detail=detail, **more))

    def ok(sid):
        c = cache.get(sid) or {}
        return (c.get("items") or []) if c.get("ok") else []

    def surge(metric, jump, usual_x, least, title, why):
        series = hist.get(metric) or []
        if not series or now - series[-1][0] > 2 * 3600:
            return
        v, before, usual = series[-1][1], _at(series, now, 3), _usual(series, now)
        if before is not None and v >= least and v >= before * jump and v - before >= least / 2.0:
            add(metric, METRICS[metric][0], "minor", title, "%d now, up from %d three hours ago. %s" % (v, before, why),
                metric=metric)
        elif usual is not None and v >= least and v >= max(usual * usual_x, usual + least):
            add(metric, METRICS[metric][0], "minor", title, "%d now; %d is usual. %s" % (v, usual, why), metric=metric)

    surge("power_near", 2, 3, 3, "Power cuts near you are increasing", "Charge phones and power banks while the power is on.")
    surge("power_uk", 1.6, 3, 20, "Power cuts are increasing across the networks",
          "Usually weather: check the forecast for your area.")
    surge("floods_near", 1.5, 3, 2, "More flood warnings near you", "Check the warnings on the map.")
    surge("floods_uk", 1.5, 3, 20, "Flood warnings are rising across England", "Rivers respond to rain for a day or two after it stops.")
    surge("rivers_high", 1.6, 3, 25, "Rivers are rising across England", "More gauges are above their normal range than usual.")

    # A river near you that keeps rising towards the top of its normal range.
    for i in ok("rivers"):
        s = i.get("series") or []
        if i.get("scope") == "uk" or i.get("state") == "high" or len(s) < 4 or not i.get("time"):
            continue
        try:
            stamp = lambda t: dt.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
            last_t, v = stamp(s[-1][0]), s[-1][1]
            back = [p for p in s if 4 * 3600 <= last_t - stamp(p[0]) <= 12 * 3600]
        except (ValueError, TypeError):
            continue
        if not back or now - last_t > 6 * 3600:
            continue
        hours = (last_t - stamp(back[0][0])) / 3600.0
        rate = (v - back[0][1]) / hours
        low, high = i.get("low"), i.get("high")
        if rate <= 0.005 or low is None or high is None or high <= low:
            continue
        rising = all(b[1] >= a[1] - 0.005 for a, b in zip(s[s.index(back[0]):], s[s.index(back[0]) + 1:]))
        left = (high - v) / rate
        if rising and (v - low) / (high - low) >= 0.6 and left <= 18:
            add("river:" + str(i.get("ref")), "rivers", "minor", "%s is rising" % i.get("name", "A river near you"),
                "%.2f m and up %.2f m in %d hours. At this rate it passes the top of its normal range (%.2f m) in about %d hour%s."
                % (v, v - back[0][1], round(hours), high, max(1, round(left)), "" if round(left) <= 1 else "s"),
                ref=i.get("ref"))

    # Gas in storage emptying faster than it was.
    for i in ok("gas"):
        s = i.get("series") or []
        if len(s) < 12:
            continue
        vals = [p[1] for p in s]
        this_week, last_week = (vals[-8] - vals[-1]) / 7.0, (vals[-15] - vals[-8]) / 7.0 if len(vals) >= 15 else None
        falling_days = 0
        for a, b in zip(reversed(vals[:-1]), reversed(vals)):
            if b < a:
                falling_days += 1
            else:
                break
        days_left = vals[-1] / this_week if this_week > 0 else None
        if this_week >= 0.15 and last_week is not None and this_week >= max(last_week, 0.05) * 1.5 and days_left and days_left < 60:
            add("gas_rate", "gas", "minor", "Gas storage is emptying faster",
                "Falling %.2f TWh a day this week against %.2f last week: about %d days at this rate."
                % (this_week, max(last_week, 0), round(days_left)))
        elif falling_days >= 10 and days_left and days_left < 30:
            add("gas_run", "gas", "minor", "Gas storage has fallen %d days running" % falling_days,
                "About %d days left at this week's rate of use." % round(days_left))

    # Money: the fetchers decide what counts as a sharp move.
    for sid in ("fx", "markets"):
        for i in ok(sid):
            if i.get("watch"):
                add("%s:%s" % (sid, i.get("code")), sid, i.get("level", "minor"), i["watch"], i.get("detail", ""),
                    from_item=True)
    return out


SOURCES = [
    # id, setting toggle, name, fetcher, refresh seconds, attribution, info link
    ("floods", "intel_floods", "Flood warnings", fetch_floods, 15 * 60,
     "Environment Agency real-time data, England (Open Government Licence v3.0). Not for safety-critical use.",
     "https://check-for-flooding.service.gov.uk/"),
    ("rivers", "intel_rivers", "River levels", fetch_rivers, 30 * 60,
     "Environment Agency river level gauges, England (Open Government Licence v3.0). Not for safety-critical use.",
     "https://check-for-flooding.service.gov.uk/river-and-sea-levels"),
    ("weather", "intel_weather", "Severe weather", fetch_weather, 15 * 60,
     "Met Office National Severe Weather Warnings, Crown copyright.",
     "https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings"),
    ("power", "intel_power", "Power cuts", fetch_power, 10 * 60,
     "UK Power Networks (CC BY 4.0) and National Grid Electricity Distribution live power cuts. Together they cover "
     "London, the South East, East of England, the Midlands, the South West and Wales.",
     "https://www.ukpowernetworks.co.uk/power-cut/map"),
    ("fires", "intel_fires", "Wildfires", fetch_fires, 30 * 60,
     "NASA FIRMS satellite heat detections, last 24 hours (NASA LANCE, open data).",
     "https://firms.modaps.eosdis.nasa.gov/map/"),
    ("gas", "intel_gas", "Gas storage", fetch_gas, 6 * 3600,
     "National Gas Transmission data portal (daily aggregated storage stock and available capacity).",
     "https://data.nationalgas.com/"),
    ("fx", "intel_fx", "The pound", fetch_fx, 6 * 3600,
     "European Central Bank daily reference rates, via frankfurter.dev. Context only, not financial advice.",
     "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"),
    ("markets", "intel_markets", "Markets", fetch_markets, 3 * 3600,
     "Yahoo Finance chart data (unofficial feed, may be delayed). Context only, not financial advice.",
     "https://finance.yahoo.com/world-indices/"),
    ("grid", "intel_grid", "National grid", fetch_grid, 30 * 60,
     "Elexon BMRS system warnings (open data).",
     "https://bmrs.elexon.co.uk/system-warnings"),
    ("air", "intel_air", "Air quality", fetch_air, 60 * 60,
     "DEFRA UK-AIR (Open Government Licence v3.0).",
     "https://uk-air.defra.gov.uk/"),
    ("space", "intel_space", "Space weather", fetch_space, 60 * 60,
     "NOAA Space Weather Prediction Center (public domain).",
     "https://www.swpc.noaa.gov/"),
]
SOURCE_IDS = [s[0] for s in SOURCES]


class Intel:
    """Background poller with a per-source cache. settings_fn() returns a dict of intel_* settings."""

    def __init__(self, data_dir, settings_fn, on_change=None, home_fn=None):
        self.path = os.path.join(data_dir, "intel_cache.json")
        self.geo_path = os.path.join(data_dir, "intel_geo.json")
        self.settings_fn = settings_fn
        self.home_fn = home_fn
        self.on_change = on_change
        self.lock = threading.Lock()
        self.run_lock = threading.Lock()   # one refresh at a time ("Check now" vs the background loop)
        self.wake = threading.Event()
        self.cache = {}
        self.geo = {}
        self.cfg_seen = None
        self.trend_path = os.path.join(data_dir, "intel_trends.json")
        self.hist = {}
        for path, attr, ok in ((self.path, "cache", lambda k: k in SOURCE_IDS), (self.geo_path, "geo", lambda k: True),
                               (self.trend_path, "hist", lambda k: k in METRICS)):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    setattr(self, attr, {k: v for k, v in saved.items()
                                         if ok(k) and isinstance(v, list if attr == "hist" else dict)})
            except (OSError, ValueError):
                pass

    def home(self):
        """(lat, lon) for the map: the postcode set in HQ, else Home Assistant's home, else None."""
        try:
            where = self.cfg().get("intel_map_where")
            if isinstance(where, list) and len(where) == 2:
                return (float(where[0]), float(where[1]))
            h = self.home_fn() if self.home_fn else None
            return (float(h[0]), float(h[1])) if h else None
        except Exception:
            return None

    def cfg(self):
        raw = dict(DEFAULTS)
        try:
            raw.update({k: v for k, v in (self.settings_fn() or {}).items() if k in DEFAULTS})
        except Exception:
            traceback.print_exc()
        return raw

    def _save(self):
        for path, data in ((self.path, self.cache), (self.geo_path, self.geo), (self.trend_path, self.hist)):
            tmp = path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                os.replace(tmp, path)
            except OSError:
                pass

    def refresh(self, force=False):
        """Fetch every enabled source that is due. Returns True if anything changed."""
        with self.run_lock:
            return self._refresh(force)

    def _refresh(self, force=False):
        cfg = self.cfg()
        home = self.home()
        key = json.dumps({"cfg": {k: cfg[k] for k in sorted(cfg)}, "home": home})
        if key != self.cfg_seen:  # settings changed: refetch everything now
            self.cfg_seen, force = key, True
        changed = False
        for sid, toggle, name, fn, every, _attr, _link in SOURCES:
            if not (cfg["intel_enabled"] and cfg[toggle]):
                if sid in self.cache:
                    with self.lock:
                        self.cache.pop(sid, None)
                    changed = True
                continue
            prev = self.cache.get(sid) or {}
            due = force or time.time() - float(prev.get("tried") or 0) >= (every if prev.get("ok") else min(every, 300))
            if not due:
                continue
            entry = dict(prev)
            entry["tried"] = time.time()
            try:
                items = fn(dict(cfg, _home=home, _geo=self.geo))
                entry.update(ok=True, error="", items=items, checked_at=_now_iso())
            except (urllib.error.URLError, IOError, ValueError, ET.ParseError, KeyError, TypeError) as e:
                msg = str(e.reason if isinstance(e, urllib.error.URLError) else e)[:200]
                entry.update(ok=False, error=msg)  # keep the last good items
            except Exception as e:
                traceback.print_exc()
                entry.update(ok=False, error="Unexpected error: %s" % str(e)[:150])
            if json.dumps({k: entry.get(k) for k in ("ok", "error", "items")}, sort_keys=True) != \
                    json.dumps({k: prev.get(k) for k in ("ok", "error", "items")}, sort_keys=True):
                changed = True
            with self.lock:
                self.cache[sid] = entry
        if cfg["intel_enabled"] and self.record():
            changed = True
        if changed:
            self._save()
        return changed

    def record(self, now=None):
        """Keep a sample of each metric (at most every 20 minutes, for two weeks). True if anything was added."""
        now = now or time.time()
        added = False
        with self.lock:
            for metric, value in measure(self.cache).items():
                series = self.hist.setdefault(metric, [])
                if series and now - series[-1][0] < TREND_EVERY:
                    continue
                series.append([int(now), value])
                while series and series[0][0] < now - TREND_KEEP:
                    series.pop(0)
                added = True
        return added

    def loop(self):
        while True:
            try:
                if self.refresh() and self.on_change:
                    self.on_change()
            except Exception:
                traceback.print_exc()
            self.wake.wait(60)
            self.wake.clear()

    def start(self):
        threading.Thread(target=self.loop, name="intel", daemon=True).start()

    def kick(self):
        self.wake.set()

    def snapshot(self):
        """Public view for the API, the UI and Home Assistant sensors.

        Only items in scope "yours" (no scope means yours) raise the alert level, the active count and the
        Home Assistant sensors. "near" and "uk" items are map context."""
        cfg = self.cfg()
        out, worst, active, elsewhere = [], "none", 0, 0
        with self.lock:
            cache = json.loads(json.dumps(self.cache))
            hist = json.loads(json.dumps(self.hist))
        live = {sid: c for sid, c in cache.items()
                if cfg["intel_enabled"] and cfg[dict((s[0], s[1]) for s in SOURCES)[sid]]}
        trends = find_trends(live, hist) if cfg["intel_enabled"] and cfg["intel_trends"] else []
        for t in trends:
            if not t.pop("from_item", False):   # money moves are already counted as their source's alert
                active += 1
                if LEVEL_RANK[t["level"]] > LEVEL_RANK[worst]:
                    worst = t["level"]
        for sid, toggle, name, _fn, every, attr, link in SOURCES:
            on = bool(cfg["intel_enabled"] and cfg[toggle])
            c = cache.get(sid) or {}
            items = (c.get("items") or []) if on else []
            if not cfg["intel_uk"]:
                items = [i for i in items if i.get("scope", "yours") != "uk"]
            mine = []
            for i in items:
                if i.get("level") not in LEVEL_RANK:
                    i["level"] = "info"
                i.setdefault("scope", "yours")
                if i["scope"] == "yours":
                    mine.append(i)
                    if LEVEL_RANK[i["level"]] >= LEVEL_RANK["minor"]:
                        active += 1
                    if LEVEL_RANK[i["level"]] > LEVEL_RANK[worst]:
                        worst = i["level"]
                elif LEVEL_RANK[i["level"]] >= LEVEL_RANK["minor"]:
                    elsewhere += 1
            src_level = max((i["level"] for i in mine), key=lambda l: LEVEL_RANK[l], default="none")
            out.append({
                "id": sid, "name": name, "enabled": on, "ok": c.get("ok") if on else None,
                "error": c.get("error", "") if on else "", "checked_at": c.get("checked_at") if on else None,
                "level": src_level, "items": items, "attribution": attr, "link": link,
                "refresh_minutes": every // 60,
            })
        home = self.home()
        def thin(series, n=140):   # enough points for a chart
            step = max(1, len(series) // n)
            keep = series[::step]
            return keep if not series or keep[-1] == series[-1] else keep + [series[-1]]
        history = {m: {"source": METRICS[m][0], "label": METRICS[m][1],
                       "points": [[dt.datetime.fromtimestamp(p[0], dt.timezone.utc).replace(microsecond=0).isoformat(), p[1]]
                                  for p in thin(hist.get(m) or [])]}
                   for m in METRICS if len(hist.get(m) or []) >= 2 and cfg["intel_enabled"]}
        return {"enabled": bool(cfg["intel_enabled"]), "level": worst, "active": active, "elsewhere": elsewhere,
                "trends": trends, "history": history,
                "sources": out, "settings": {k: cfg[k] for k in DEFAULTS if k != "intel_map_where"},
                "met_regions": MET_REGIONS, "air_regions": AIR_REGIONS,
                "map": {
                    "on": bool(cfg["intel_enabled"] and cfg["intel_map"]),
                    # Rounded to about 100 m: enough to centre the map.
                    "home": [round(home[0], 3), round(home[1], 3)] if home else None,
                    "home_from": "postcode" if cfg.get("intel_map_where") else ("home assistant" if home else None),
                    "radius_km": cfg["intel_radius_km"],
                    "met_centres": MET_CENTRES,
                }}
