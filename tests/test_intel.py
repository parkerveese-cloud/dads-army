"""Live alerts: parsers against recorded feed shapes (offline), and the server's /api/intel endpoints."""
import datetime as dt
import json
import urllib.parse
import time
import math
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "dadsarmy"))
sys.path.insert(0, HERE)

import intel  # noqa: E402
from test_server import ServerTest  # noqa: E402

HOME = (52.46, 0.22)   # a stand-in home in Cambridgeshire

EA = {"items": [
    {"severityLevel": 1, "severity": "Severe Flood Warning", "description": "River Great Ouse at Over",
     "message": "Danger to life.", "floodAreaID": "053FWFGO01", "timeRaised": "2026-11-11T09:00:00",
     "floodArea": {"county": "Cambridgeshire", "notation": "053FWFGO01"}},
    {"severityLevel": 3, "severity": "Flood Alert", "description": "River Severn at Shrewsbury", "message": "Be prepared.",
     "floodAreaID": "011WAFSEV", "floodArea": {"county": "Shropshire", "notation": "011WAFSEV"}},
    {"severityLevel": 4, "severity": "Warning no Longer in Force", "description": "Old one", "floodArea": {}},
]}
AREAS = {"053FWFGO01": {"lat": 52.47, "long": 0.23, "label": "Over", "county": "Cambridgeshire"},
         "011WAFSEV": {"lat": 52.71, "long": -2.75, "label": "Shrewsbury", "county": "Shropshire"}}
MET = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Met Office warnings for UK</title>
<item><title>Amber warning of wind affecting East of England, London &amp; South East England</title><description>Strong winds &lt;b&gt;likely&lt;/b&gt;.</description>
<link>https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings#?date=2026-11-12</link><pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Yellow warning of rain affecting Wales</title><description>Rain.</description>
<link>javascript:alert(1)</link><pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""
UKPN = {"total_count": 4, "results": [
    {"powercuttype": "Unplanned", "statusid": "1", "restoreddatetime": None, "nocustomeraffected": "250",
     "postcodesaffected": "AB12 5;AB12 6", "fullpostcodedata": "AB125AB;AB126CD", "operatingzone": "CAMBRIDGE",
     "geopoint": {"lat": 52.45, "lon": 0.2},
     "incidenttypetbcestimatedfriendlydescription": "To be confirmed", "estimatedrestorationdate": "2026-11-11T18:00:00",
     "mainmessage": "We are experiencing problems."},
    {"powercuttype": "Planned", "statusid": "1", "restoreddatetime": None, "noplannedcustomers": "12",
     "postcodesaffected": "AB3 1", "geopoint": {"lat": 52.37, "lon": 0.33},
     "incidenttypetbcestimatedfriendlydescription": "12 Nov 09:00 - 13:00", "plannedincidentreason": "Planned work."},
    {"powercuttype": "Restored", "statusid": "5", "restoreddatetime": "2026-11-11T10:00:00",
     "postcodesaffected": "AB12 5"},
    {"powercuttype": "Unplanned", "statusid": "1", "restoreddatetime": None, "nocustomeraffected": "3",
     "postcodesaffected": "AB120 1;SAB12 9", "geopoint": {"lat": 51.5, "lon": -0.1}},   # not AB12, far, small: hidden
]}
NGED = ("Upload Date,Region,Incident ID,Confirmed Off,Predicted Off,Restored,Status,Planned,Category,Resource Status,"
        "Start Time,ETR,Voltage,Location Latitude,Location Longitude,Postcodes\n"
        "2026-11-11T23:40:00,South Wales,INCD-1,320,0,0,In Progress,false,HV GENERIC,DISP,2026-11-11T21:17:00,"
        "2026-11-12T00:30:00,HV,52.00578,-4.36221,\"SA44 5JT, SA44 5JY\"\n"
        "2026-11-11T23:40:00,South West,INCD-2,0,4,0,Awaiting,false,LV GENERIC,UNASSIGNED,2026-11-11T23:37:00,,LV,"
        "50.87972,-2.784555,\"TA18 8EN\"\n"
        "2026-11-11T23:40:00,South West,INCD-3,0,0,40,Restored,false,LV GENERIC,DONE,2026-11-11T20:00:00,,LV,"
        "50.8,-2.7,\"TA18 8AB\"\n").encode()
FIRMS = ("latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n"
         "52.50,0.25,330,0.4,0.4,2026-11-11,1342,N20,n,2.0NRT,290,6.1,D\n"     # 4 km from home
         "52.5001,0.2501,331,0.4,0.4,2026-11-11,1343,N21,h,2.0NRT,291,6.0,D\n"  # same fire, another satellite
         "57.1,-4.2,340,0.4,0.4,2026-11-11,1300,N20,n,2.0NRT,295,12,D\n"        # Highlands
         "53.0,-1.0,320,0.4,0.4,2026-11-11,1300,N20,l,2.0NRT,280,1,D\n"         # low confidence: dropped
         "57.7,1.5,360,0.4,0.4,2026-11-11,1300,N20,h,2.0NRT,300,40,D\n"        # North Sea platform: dropped
         "45.0,5.0,330,0.4,0.4,2026-11-11,1300,N20,h,2.0NRT,290,20,D\n").encode()  # France: outside the box
GRID = {"data": [
    {"warningType": "SO-SO TRADES", "warningText": "Interconnector prices", "publishTime": "2099-01-01T00:00:00Z"},
    {"warningType": "ELECTRICITY MARGIN NOTICE", "warningText": "Margin notice for 17:00-19:00",
     "publishTime": "2099-01-01T00:00:00Z"},
    {"warningType": "ELECTRICITY MARGIN NOTICE", "warningText": "Old notice", "publishTime": "2000-01-01T00:00:00Z"},
]}
AIR = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Eastern</title><description>Current pollution level is High at index 8</description></item>
<item><title>East Midlands</title><description>Current pollution level is Low at index 2</description></item>
</channel></rss>"""
def _gas_csv(stocks, space_total=35.0):
    rows = ["Applicable At,Applicable For,Data Item,Value,Generated Time,Quality Indicator"]
    for d, twh in stocks:
        rows.append('x,%s,"Storage, Daily Aggregated Stock level, D+1",%d,x,L' % (d, twh * 1e9))
        rows.append('x,%s,"Storage, Daily Aggregated Available Capacity, D+1",%d,x,L' % (d, (space_total - twh) * 1e9))
    return "\n".join(rows).encode()


GAS = _gas_csv([("%02d/11/2026" % d, 14.0 - 0.1 * d) for d in range(1, 12)])   # 40% full, slowly falling
KP = [{"time_tag": "2026-11-11T06:00:00", "Kp": 2.0}, {"time_tag": "2026-11-11T09:00:00", "Kp": 7.33}]

def _gauge(ref, label, river, lat, lon, low, high, top, qualifier="Stage", status="statusActive"):
    return {"stationReference": ref, "label": label, "riverName": river, "lat": lat, "long": lon, "RLOIid": "9" + ref,
            "status": "http://x/def/core/" + status,
            "measures": [{"@id": "http://x/id/measures/%s-level" % ref, "parameter": "level", "qualifier": qualifier}],
            "stageScale": {"typicalRangeLow": low, "typicalRangeHigh": high, "maxOnRecord": {"value": top}}}


def _level(ref, value, when=None):
    when = when or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"measure": "http://x/id/measures/%s-level" % ref, "value": value, "dateTime": when}


GAUGES = {"items": [
    _gauge("N1", "Earith", "River Great Ouse", 52.50, 0.23, 0.5, 2.5, 3.5),      # near, normal
    _gauge("N2", "Brownshill", "River Great Ouse", 52.48, 0.2, 0.3, 0.9, 2.7),   # near, high
    _gauge("F1", "Warkworth", "River Coquet", 55.3, -1.6, 0.3, 3.0, 4.6),        # far, high
    _gauge("F2", "Bodiam", "River Rother", 51.0, 0.5, 0.1, 1.0, 2.0),            # far, close to its record
    _gauge("F3", "York", "River Ouse", 53.9, -1.1, 0.2, 2.0, 5.0),               # far, normal: left out
    _gauge("F4", "Sonning", "River Thames", 51.47, -0.9, 0.0, 1.0, 2.0),         # far, a hair over: left out
    _gauge("G1", "Borehole", "", 52.46, 0.22, 1.0, 2.0, 3.0, qualifier="Groundwater"),
    _gauge("C1", "Closed", "River Cam", 52.46, 0.22, 0.1, 0.2, 1.0, status="statusClosed"),
    _gauge("S1", "Stale", "River Cam", 52.46, 0.22, 0.1, 0.2, 1.0),
]}
LEVELS = {"items": [
    _level("N1", 1.2), _level("N2", [1.0, 1.4]), _level("F1", 3.5), _level("F2", 1.9), _level("F3", 1.0),
    _level("F4", 1.01), _level("G1", 9.0), _level("C1", 9.0), _level("S1", 9.0, "2020-01-01T00:00:00Z"),
]}

def _days(n):
    return [(dt.date(2026, 8, 1) + dt.timedelta(days=i)).isoformat() for i in range(n)]


# The pound: steady against the euro, down 5% against the dollar in the last week.
FXDATA = {"rates": {d: dict({c: 1.5 for c, _n in intel.FX}, EUR=1.2, USD=1.4 if i < 25 else 1.33)
                    for i, d in enumerate(_days(30))}}


def _yahoo(closes, price=None):
    t0 = 1785000000
    return {"chart": {"result": [{
        "meta": {"currency": "GBP", "regularMarketPrice": price or closes[-1], "regularMarketTime": t0 + 86400 * (len(closes) - 1)},
        "timestamp": [t0 + 86400 * i for i in range(len(closes))], "indicators": {"quote": [{"close": closes}]}}]}}


YAHOO = {"^FTSE": _yahoo([10000.0] * 30, price=10100.0),                 # steady, live price replaces today's close
         "^GSPC": _yahoo([7000.0] * 25 + [6800, 6600, None, 6400, 6300.0]),   # down 10% in a week
         "BZ=F": _yahoo([80.0] * 25 + [84, 88, 92, 96, 100.0]),           # oil up 25% in a week
         "GC=F": _yahoo([4000.0] * 25 + [3000.0] * 5)}                    # gold: never an alert

CFG = dict(intel.DEFAULTS, intel_enabled=1, intel_county="Cambridgeshire", intel_met_region="ee",
           intel_postcodes="AB12 ab3", intel_air_region="Eastern", intel_space=1, intel_radius_km=15)
SENT = []


def fake_get(url, accept="application/json"):
    SENT.append(url)
    if url.endswith("/flood-monitoring/id/floods"):
        return json.dumps(EA).encode()
    if "/flood-monitoring/id/floodAreas/" in url and url.endswith("/polygon"):
        ring = [[0.2 + 0.01 * math.cos(t / 20.0), 52.45 + 0.01 * math.sin(t / 20.0)] for t in range(126)]
        ring.append(ring[0])
        return json.dumps({"features": [{"geometry": {"type": "Polygon", "coordinates": [ring]}}]}).encode()
    if "/flood-monitoring/id/floodAreas/" in url:
        return json.dumps({"items": AREAS[url.rsplit("/", 1)[1]]}).encode()
    if url.endswith("WarningsRSS/Region/UK"):
        return MET
    if "/flood-monitoring/id/stations" in url:
        return json.dumps(GAUGES).encode()
    if "/flood-monitoring/data/readings" in url:
        return json.dumps(LEVELS).encode()
    if "frankfurter" in url:
        return json.dumps(FXDATA).encode()
    if "finance.yahoo.com" in url:
        sym = urllib.parse.unquote(url.split("/chart/")[1].split("?")[0])
        if sym not in YAHOO:
            raise IOError("HTTP 404")
        return json.dumps(YAHOO[sym]).encode()
    if "ukpn-live-faults" in url:
        return json.dumps(UKPN).encode()
    if "connecteddata.nationalgrid.co.uk" in url:
        return NGED
    if "firms.modaps" in url:
        return FIRMS if "J1_" in url else b"latitude,longitude,confidence\n"
    if "nationalgas" in url:
        return GAS
    if "SYSWARN" in url:
        return json.dumps(GRID).encode()
    if "uk-air" in url:
        return AIR
    if "swpc" in url:
        return json.dumps(KP).encode()
    raise AssertionError("unexpected URL " + url)


class TestParsers(unittest.TestCase):
    def setUp(self):
        self.orig = intel._get
        intel._get = fake_get
        del SENT[:]

    def tearDown(self):
        intel._get = self.orig

    def cfg(self, **kw):
        return dict(CFG, _home=HOME, _geo={}, **kw)

    def test_floods_national_with_scope(self):
        items = intel.fetch_floods(self.cfg())
        self.assertEqual([(i["level"], i["scope"]) for i in items], [("severe", "yours"), ("minor", "uk")])
        self.assertIn("053FWFGO01", items[0]["url"])
        self.assertTrue(items[0]["rings"], "outlines for floods near you")
        self.assertEqual(items[1]["rings"], [], "no outlines for the rest of the country")
        self.assertEqual((items[1]["lat"], items[1]["lon"]), (52.71, -2.75))

    def test_nothing_about_home_is_sent(self):
        intel.fetch_floods(self.cfg())
        intel.fetch_weather(self.cfg())
        intel.fetch_power(self.cfg())
        intel.fetch_fires(self.cfg())
        for url in SENT:
            for secret in ("AB12", "cambridgeshire", "52.46", "0.22", "Region/ee"):
                self.assertNotIn(secret.lower(), url.lower(), url)

    def test_weather_regions_and_scope(self):
        items = intel.fetch_weather(self.cfg())
        self.assertEqual([(i["level"], i["scope"]) for i in items], [("moderate", "yours"), ("minor", "uk")])
        self.assertEqual(items[0]["regions"], ["ee", "se"])
        self.assertEqual(items[1]["regions"], ["wl"])
        self.assertEqual(items[0]["detail"], "Strong winds likely .")

    def test_power_both_networks(self):
        items = intel.fetch_power(self.cfg())
        got = sorted((i["scope"], i["title"].split(" · ")[0], i.get("network")) for i in items)
        self.assertEqual(got, [
            ("uk", "Power cut", "National Grid (NGED)"),                     # 320 homes in Wales
            ("yours", "Planned power cut", "UK Power Networks"),             # AB3
            ("yours", "Power cut", "UK Power Networks"),                     # AB12, 250 homes
        ])
        cut = [i for i in items if i["scope"] == "yours" and "250" in i["title"]][0]
        self.assertEqual(cut["level"], "moderate")
        self.assertIn("Back by 2026-11-11 18:00", cut["time"])

    def test_power_one_network_down(self):
        def nged_down(url, accept="application/json"):
            if "nationalgrid" in url:
                raise IOError("down")
            return fake_get(url, accept)
        intel._get = nged_down
        items = intel.fetch_power(self.cfg())
        self.assertTrue(any(i["title"].startswith("Couldn't check National Grid") for i in items))
        self.assertTrue(any(i.get("network") == "UK Power Networks" for i in items))

    def test_grid_notice_levels(self):
        """A cancelled or single-generator instruction isn't a 'take action' warning; demand control is."""
        rows = [("OTHER", "Notification of NESO Cancellation of Emergency Instruction to a BM Participant"),
                ("OTHER", "NESO Emergency Instruction to a BM Participant issued"),
                ("DEMAND CONTROL IMMINENT", "Demand control may be instructed in the next 30 minutes"),
                ("ELECTRICITY MARGIN NOTICE", "Margin notice for 17:00-19:00")]
        data = {"data": [{"warningType": k, "warningText": t, "publishTime": "2099-01-01T00:00:00Z"} for k, t in rows]}
        saved = intel._get_json
        intel._get_json = lambda url, *a, **k: data
        try:
            got = [(i["title"], i["level"]) for i in intel.fetch_grid({})]
        finally:
            intel._get_json = saved
        self.assertEqual(got, [("Grid notice (cancelled)", "info"), ("Grid notice", "minor"),
                               ("Demand Control Imminent", "severe"), ("Electricity Margin Notice", "moderate")])

    def test_rivers(self):
        geo = {}
        items = intel.fetch_rivers(dict(self.cfg(), _geo=geo))
        got = [(i["ref"], i["scope"], i["level"], i["state"]) for i in items]
        self.assertEqual(got, [("N2", "yours", "minor", "high"), ("N1", "near", "none", "normal"),
                               ("F2", "uk", "moderate", "high"), ("F1", "uk", "minor", "high")])
        self.assertEqual(items[0]["title"], "River Great Ouse at Brownshill: 1.40 m, above normal")
        self.assertIn("/station/9N2", items[0]["url"])
        self.assertIn("close to its record", items[2]["title"])
        # Nothing about where you are goes to the Environment Agency: only the two national lists are asked for.
        self.assertEqual(sorted(u.split("flood-monitoring")[1] for u in SENT),
                         ["/data/readings?latest&parameter=level", "/id/stations?parameter=level&_limit=10000&_view=full"])
        # The gauge list is cached; readings for the gauges near you build a trend.
        del SENT[:]
        now = dt.datetime.now(dt.timezone.utc)
        geo["river_hist"]["N2"] = [[(now - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"), 1.0] for h in (5, 4, 3)]
        again = intel.fetch_rivers(dict(self.cfg(), _geo=geo))
        self.assertEqual(len(SENT), 1)
        self.assertEqual((again[0]["trend"], len(again[0]["series"])), ("rising", 4))
        self.assertNotIn("F1", geo["river_hist"])

    def test_pound(self):
        fx = {i["code"]: i for i in intel.fetch_fx(self.cfg())}
        self.assertEqual(len(fx), len(intel.FX))
        self.assertEqual((fx["EUR"]["level"], fx["EUR"]["title"]), ("none", "£1 = 1.2000 EUR"))
        self.assertEqual((fx["USD"]["level"], fx["USD"]["changes"]["w1"]), ("minor", -5.0))
        self.assertEqual(fx["USD"]["watch"], "The pound is down 5.0% in a week against the US dollar")
        self.assertNotIn("watch", fx["CAD"])

    def test_markets(self):
        m = {i["code"]: i for i in intel.fetch_markets(self.cfg())}
        self.assertEqual(sorted(m), ["BZ=F", "GC=F", "^FTSE", "^GSPC"], "a market that can't be fetched is left out")
        self.assertEqual((m["^FTSE"]["level"], m["^FTSE"]["value"], m["^FTSE"]["changes"]["d1"]), ("none", 10100.0, 1.0))
        self.assertEqual((m["^GSPC"]["level"], m["^GSPC"]["watch"]), ("minor", "S&P 500 (US) is down 10.0% in a week"))
        self.assertEqual((m["BZ=F"]["level"], m["BZ=F"]["watch"]), ("moderate", "Brent crude oil is up 25.0% in a week"))
        self.assertEqual(m["GC=F"]["level"], "none")

    def test_trends(self):
        now = 1800000000
        iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        steady = [[now - 3600 * h, 10] for h in range(96, 0, -1)]
        river = {"scope": "near", "state": "normal", "ref": "N1", "name": "River Great Ouse at Earith", "low": 0.5, "high": 2.5,
                 "time": iso(now), "series": [[iso(now - 3600 * h), 2.3 - 0.05 * h] for h in range(8, -1, -1)]}
        gas = {"series": [[d, v] for d, v in zip(_days(16), [20 - 0.1 * i for i in range(9)] + [19.2 - 0.4 * i for i in range(1, 8)])]}
        cache = {"rivers": {"ok": True, "items": [river, dict(river, ref="N3", series=river["series"][:2])]},
                 "gas": {"ok": True, "items": [gas]},
                 "fx": {"ok": True, "items": [{"code": "USD", "level": "minor", "watch": "The pound is down", "detail": "x"}]},
                 "power": {"ok": False, "items": [river]}}
        hist = {"power_uk": steady + [[now, 45]],                      # a jump in three hours
                "floods_uk": [[now - 3600 * h, 5] for h in range(96, 0, -1)] + [[now, 30]],
                "power_near": steady[:-1] + [[now, 10]],                 # nothing new
                "rivers_high": [[now - 3600 * 5, 10], [now - 3600 * 3, 80]]}   # stale: no reading for three hours
        got = {t["id"]: t for t in intel.find_trends(cache, hist, now)}
        self.assertEqual(sorted(got), ["floods_uk", "fx:USD", "gas_rate", "power_uk", "river:N1"])
        self.assertIn("45 now, up from 10 three hours ago", got["power_uk"]["detail"])
        self.assertIn("in about 4 hours", got["river:N1"]["detail"])
        self.assertIn("0.40 TWh a day this week against 0.10", got["gas_rate"]["detail"])
        # Above what's usual, without a sudden jump.
        slow = {"floods_uk": [[now - 3600 * h, 5] for h in range(96, 6, -1)] + [[now - 3600 * h, 30] for h in range(6, -1, -1)]}
        self.assertIn("30 now; 5 is usual", intel.find_trends({}, slow, now)[0]["detail"])
        self.assertEqual(intel.find_trends({}, {"floods_uk": slow["floods_uk"][-10:]}, now), [], "no baseline yet")

    def test_history_is_recorded_and_counted(self):
        tmp = tempfile.mkdtemp()
        try:
            i = intel.Intel(tmp, lambda: CFG, home_fn=lambda: HOME)
            i.refresh(force=True)
            self.assertEqual(i.hist["floods_uk"][-1][1], 2)
            self.assertFalse(i.record(), "one sample every 20 minutes")
            self.assertTrue(i.record(time.time() + 1500))
            snap = i.snapshot()
            self.assertEqual(snap["history"]["floods_uk"]["source"], "floods")
            # The dollar move is the fx source's alert and a trend, counted once.
            self.assertEqual([t["id"] for t in snap["trends"]], ["fx:USD", "markets:^GSPC", "markets:BZ=F"])
            before = snap["active"]
            i.hist["power_uk"] = [[time.time() - 3 * 3600 - 60, 5], [time.time(), 60]]
            after = i.snapshot()
            self.assertEqual(after["active"], before + 1)
            self.assertEqual(intel.Intel(tmp, lambda: dict(CFG, intel_trends=0), home_fn=lambda: HOME).snapshot()["trends"], [])
            self.assertIn("floods_uk", intel.Intel(tmp, lambda: CFG).hist, "history survives a restart")
        finally:
            shutil.rmtree(tmp)

    def test_alert_events(self):
        import server
        snap = {"enabled": True, "sources": [
            {"id": "floods", "name": "Flood warnings", "items": [
                {"level": "severe", "scope": "yours", "title": "Severe flood warning", "detail": "Act now", "url": "https://x/1"},
                {"level": "minor", "scope": "uk", "title": "Elsewhere", "url": "https://x/2"},
                {"level": "none", "scope": "yours", "title": "Quiet"}]},
            {"id": "fx", "name": "The pound", "items": [
                {"level": "minor", "scope": "yours", "code": "USD", "title": "The pound is down", "watch": "The pound is down"}]}],
            "trends": [{"id": "fx:USD", "source": "fx", "level": "minor", "title": "The pound is down", "detail": "5% in a week"}]}
        events, seen = server.alert_events(snap, None, 1000)
        self.assertEqual((events, sorted(seen)), ([], ["floods|https://x/1", "trend|fx:USD"]), "first run announces nothing")
        events, seen = server.alert_events(snap, {}, 1000)
        self.assertEqual([(e["kind"], e["level_word"], e["title"], e["source"]) for e in events],
                         [("alert", "Take action", "Severe flood warning", "Flood warnings"),
                          ("trend", "Be aware", "The pound is down", "The pound")])
        self.assertEqual(server.alert_events(snap, seen, 2000)[0], [], "told once")
        gone, seen = server.alert_events(dict(snap, trends=[]), seen, 3000)
        self.assertEqual(server.alert_events(snap, seen, 4000)[0], [], "back within six hours: no repeat")
        self.assertEqual(len(server.alert_events(snap, seen, 3000 + 7 * 3600)[0]), 2, "back after a long gap: told again")
        many = dict(snap, trends=[dict(snap["trends"][0], id="t%d" % n, title="Trend %d" % n) for n in range(6)])
        events, _ = server.alert_events(many, {}, 1000)
        self.assertEqual((len(events), events[0]["title"], events[0]["level"]), (1, "7 new live alerts", "severe"))

    def test_fires(self):
        items = intel.fetch_fires(self.cfg())
        self.assertEqual(len(items), 2, "duplicate, low-confidence, offshore and out-of-area detections dropped")
        for lat, lon in ((52.3, 0.0), (57.5, -4.2), (60.2, -1.2), (53.4, -0.2), (51.5, 1.4)):
            self.assertFalse(intel._offshore(lat, lon), (lat, lon))
        near, far = items
        self.assertEqual((near["scope"], near["level"], near["fire"]), ("yours", "minor", True))
        self.assertLess(near["km"], 15)
        self.assertEqual((far["scope"], far["level"]), ("uk", "info"))

    def test_gas_storage(self):
        g = intel.fetch_gas(self.cfg())[0]
        self.assertEqual((g["level"], g["scope"], g["full_pct"]), ("none", "yours", 36.9))
        self.assertEqual(g["days_left"], 129)   # 12.9 TWh at 0.1 TWh a day
        self.assertIn("−0.7 TWh on a week ago", g["detail"])
        global GAS
        low = _gas_csv([("%02d/11/2026" % d, 9.0 - 0.5 * d) for d in range(1, 12)])
        orig, GAS = GAS, low
        try:
            g = intel.fetch_gas(self.cfg())[0]
            self.assertEqual(g["level"], "moderate")   # under 15% full / under 10 days left
        finally:
            GAS = orig

    def test_grid_keeps_recent_margin_notices_only(self):
        items = intel.fetch_grid(self.cfg())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["level"], "moderate")

    def test_air_and_space(self):
        self.assertEqual(intel.fetch_air(self.cfg())[0]["level"], "moderate")
        storm = intel.fetch_space(self.cfg())[0]
        self.assertEqual(storm["level"], "moderate")
        self.assertTrue(storm["title"].startswith("Geomagnetic storm G3 (Kp 7.3"), storm["title"])

    def test_simplify_keeps_shape_small(self):
        ring = [[math.cos(t / 500.0 * 2 * math.pi) * 0.1, 52 + math.sin(t / 500.0 * 2 * math.pi) * 0.1] for t in range(501)]
        out = intel._shrink_geometry({"type": "Polygon", "coordinates": [ring]}, max_points=60)
        self.assertEqual(len(out), 1)
        self.assertLessEqual(len(out[0]), 60)
        self.assertGreater(len(out[0]), 8)
        self.assertAlmostEqual(out[0][0][0], 52.0, places=3)   # [lat, lon] order for the map
        self.assertEqual(out[0][0], out[0][-1], "ring stays closed")

    def test_snapshot_counts_only_yours(self):
        tmp = tempfile.mkdtemp()
        try:
            i = intel.Intel(tmp, lambda: CFG, home_fn=lambda: HOME)
            i.refresh(force=True)
            snap = i.snapshot()
            self.assertEqual(snap["level"], "severe")
            # yours: severe flood, amber wind, 250-home cut, fire 4 km away, margin notice, air 8, Kp 7, high river, dollar, S&P, oil
            self.assertEqual(snap["active"], 11)
            # Shropshire flood, Wales rain, Wales power cut, two high rivers
            self.assertEqual(snap["elsewhere"], 5)
            self.assertEqual(snap["map"]["home"], [52.46, 0.22])
            # UK-wide off: the rest of the country disappears from the map.
            j = intel.Intel(tmp, lambda: dict(CFG, intel_uk=0), home_fn=lambda: HOME)
            self.assertEqual(j.snapshot()["elsewhere"], 0)
            # The map postcode wins over Home Assistant's home.
            k = intel.Intel(tmp, lambda: dict(CFG, intel_map_where=[51.5, -0.12]), home_fn=lambda: HOME)
            self.assertEqual(k.snapshot()["map"]["home"], [51.5, -0.12])
            self.assertEqual(k.snapshot()["map"]["home_from"], "postcode")
            self.assertNotIn("intel_map_where", k.snapshot()["settings"])
            # Outage: last good kept, and it survives a restart.
            intel._get = lambda *a, **kw: (_ for _ in ()).throw(IOError("down"))
            i.refresh(force=True)
            floods = [s for s in i.snapshot()["sources"] if s["id"] == "floods"][0]
            self.assertFalse(floods["ok"])
            self.assertEqual(len(floods["items"]), 2, "last good items kept during an outage")
            self.assertEqual(intel.Intel(tmp, lambda: CFG, home_fn=lambda: HOME).snapshot()["level"], "severe")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_postcode_districts(self):
        self.assertEqual(intel._postcode_districts("ab12 5ab, AB3; xx 12 SW1A"), ["AB12", "AB3", "SW1A"])

    def test_met_region_codes(self):
        self.assertNotIn("ls", intel.MET_REGIONS)
        self.assertEqual(intel.MET_REGIONS["se"], "London & South East England")
        self.assertEqual(set(intel.MET_REGIONS), set(intel.MET_CENTRES))


class TestIntelApi(ServerTest):
    def test_defaults_off(self):
        st = self.ok("GET", "/api/state")
        self.assertFalse(st["intel"]["enabled"])
        self.assertEqual(st["intel"]["level"], "none")
        self.assertIn("ee", st["intel"]["met_regions"])

    def test_settings_validated_and_saved(self):
        self.fails(400, "PUT", "/api/intel", {"intel_met_region": "zz"})
        self.fails(400, "PUT", "/api/intel", {"intel_met_region": "ls"})
        self.fails(400, "PUT", "/api/intel", {"intel_air_region": "Atlantis"})
        self.fails(400, "PUT", "/api/intel", {"intel_postcodes": "!!!"})
        self.fails(400, "PUT", "/api/intel", {"intel_enabled": "yes"})
        self.fails(400, "PUT", "/api/intel", {"intel_county": "<script>"})
        self.fails(400, "PUT", "/api/intel", {"intel_map_postcode": "not a postcode"})
        self.fails(400, "PUT", "/api/intel", {"intel_map_where": [1, 2]})   # only set via a postcode
        self.fails(400, "PUT", "/api/intel", {})
        self.ok("PUT", "/api/intel", {"intel_radius_km": 500})   # clamped, like the other settings
        self.assertEqual(self.ok("GET", "/api/intel")["settings"]["intel_radius_km"], 60)
        self.ok("PUT", "/api/intel", {"intel_radius_km": "25", "intel_map": False, "intel_uk": False, "intel_fires": False})
        m = self.ok("GET", "/api/intel")
        self.assertEqual((m["settings"]["intel_radius_km"], m["settings"]["intel_map"], m["map"]["on"],
                          m["settings"]["intel_uk"], m["settings"]["intel_fires"]), (25, 0, False, 0, 0))
        self.ok("PUT", "/api/intel", {"intel_enabled": True, "intel_county": "Cambridgeshire",
                                      "intel_met_region": "EE", "intel_postcodes": "ab12, ab3 1",
                                      "intel_air_region": "eastern", "intel_space": 1, "intel_map_postcode": ""})
        c = self.ok("GET", "/api/intel")["settings"]
        self.assertEqual((c["intel_enabled"], c["intel_met_region"], c["intel_postcodes"], c["intel_air_region"]),
                         (1, "ee", "AB12 AB3", "Eastern"))
        # Area details stay out of stock backups.
        status, payload, _ = self.srv.call("GET", "/api/backup.json", raw=True)
        self.assertEqual(status, 200)
        self.assertNotIn(b"AB12", payload)
        self.assertNotIn(b"intel_", payload)
        self.ok("PUT", "/api/intel", {"intel_enabled": False})


if __name__ == "__main__":
    unittest.main()
