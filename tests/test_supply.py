"""1.21.0: Your power supply, from UK Power Networks' Open Data Portal. The substation that supplies home, its load, and
the fault records against the network's average; a power cut in home's substation area counts as yours; Resilience
raises backup power for a home on a network with more faults than most; and the household's own key (validated, kept
out of /api/state and backups). The one source that sends home's location: only to UK Power Networks, only when it's on.
Stand-in feeds only, and home is central London, with made-up substation names."""
import io
import json
import sqlite3
import time
import urllib.error
import urllib.parse

from feeds import SUPPLY_ANSWERS, SUPPLY_SQUARE, FakeFeeds, ukpn_portal, ukpn_portal_answer
from support import AppTest, server

HOME = {"lat": 51.5074, "lon": -0.1278}   # central London
KEY = "a1b2c3d4" * 8                      # the portal's keys are 64 letters and numbers
NOW = server.dt.datetime(2026, 11, 18, 12, 0, tzinfo=server.dt.timezone.utc)
ELSEWHERE = {"Glasgow": (55.861, -4.251), "Cardiff": (51.4816, -3.1791), "Belfast": (54.597, -5.930),
             "Manchester": (53.479, -2.245)}


def answers(**kw):
    return dict(SUPPLY_ANSWERS, **kw)


class Portal(object):
    """Stands in for ukpn_get, answering as the portal would and keeping every link asked for."""

    def __init__(self, a=None):
        self.a, self.calls = a, []

    def __call__(self, url, key):
        self.calls.append(urllib.parse.unquote_plus(url))
        assert key == KEY
        return json.loads(ukpn_portal_answer(url[url.index("/", 8):], self.a).decode())


class SupplyTest(AppTest):
    def setUp(self):
        super().setUp()
        server.UKPN_AVG.clear()
        self.real_get = server.ukpn_get

    def tearDown(self):
        server.ukpn_get = self.real_get
        server.UKPN_AVG.clear()
        super().tearDown()

    def fetch(self, a=None, home=HOME):
        portal = Portal(a)
        server.ukpn_get = portal
        return server.fetch_supply(home, {"ukpn_key": KEY}, NOW), portal.calls


class NamesTest(SupplyTest):
    def test_substation_names(self):
        n = server.ukpn_names
        self.assertEqual(n("RIVERSIDE PRIMARY 33/11kV"), ("Riverside Primary", ["RIVERSIDE"]))
        self.assertEqual(n("ST JOHNS WOOD 11KV"), ("St Johns Wood", ["ST JOHNS WOOD"]))         # never "ST" alone
        self.assertEqual(n("NORTH HILL PRIMARY 132/11 kV"), ("North Hill Primary", ["NORTH HILL"]))   # nor "NORTH"
        self.assertEqual(n("ELMBRIDGE GRID 132/33/11kV")[1], ["ELMBRIDGE"])
        self.assertEqual(n("OAK VALE S/S")[1], ["OAK VALE"])                                      # "OAK" is too short alone
        self.assertEqual(n("NORTH")[1], [])
        self.assertEqual(n('BAD" OR 1=1 PRIMARY')[1], ["BAD OR 1 1"])                             # no quotes get through
        self.assertEqual(n(None), ("", []))

    def test_areas(self):
        rings = server.ukpn_rings({"type": "Feature", "geometry": SUPPLY_SQUARE})
        self.assertTrue(server.in_rings(rings, HOME["lat"], HOME["lon"]))
        self.assertFalse(server.in_rings(rings, 51.52, -0.1278))
        multi = {"type": "MultiPolygon", "coordinates": [SUPPLY_SQUARE["coordinates"]]}
        self.assertEqual(server.ukpn_rings(multi), rings)
        big = {"type": "Polygon", "coordinates": [[[-0.1 + n / 1e5, 51.5] for n in range(2000)]]}
        self.assertLessEqual(len(server.ukpn_rings(big)[0]), server.UKPN_RING_MOST)
        for bad in (None, {}, {"type": "Point", "coordinates": [0, 51]}, {"type": "Polygon", "coordinates": [[["x", 1]]]}):
            self.assertEqual(server.ukpn_rings(bad), [])

    def test_one_line_per_fault(self):
        cuts = server.ukpn_cuts(SUPPLY_ANSWERS["recent"] + [{"incident_reference": "X", "start_date_time": "nonsense"}])
        self.assertEqual([(c["mins"], c["homes"]) for c in cuts], [(600, 0), (150, 70), (270, 120)])   # newest first


class FetchTest(SupplyTest):
    def test_the_reading(self):
        (items, r), calls = self.fetch()
        self.assertEqual(items, [])   # never a warning of its own
        self.assertEqual((r["substation"], r["customers"], r["utilisation"], r["headroom"], r["reinforce"]),
                         ("Riverside Row", 350, "60-80%", "20-40%", "2031"))
        self.assertEqual((r["primary"], r["primary_customers"], r["gsp"]), ("Riverside Primary", 8000, "Example GSP"))
        self.assertEqual((r["year"], r["faults"], r["average"], r["ratio"], r["compare"]), ("2024-25", 60, 40.0, 1.5, "more than"))
        self.assertEqual(r["per_customer"], 0.5)                      # 4,000 customer interruptions over 8,000
        self.assertEqual((r["typical_mins"], r["longest_mins"], r["longest_on"], r["longest_homes"]),
                         (270, 270, "2024-12-24", 120))                # the cut that restored no one is left out
        self.assertEqual(r["history_to"], "2025-03-01")
        self.assertEqual(r["years"], [{"year": "2023-24", "faults": 30, "ci": 1200, "average": 36.0},
                                      {"year": "2024-25", "faults": 60, "ci": 4000, "average": 40.0}])
        self.assertTrue(server.in_rings(r["area"], HOME["lat"], HOME["lon"]))
        self.assertTrue(any('sitefunctionallocation="LPN-PRI-01"' in c for c in calls))

    def test_home_is_sent_rounded_and_only_where_needed(self):
        _, calls = self.fetch()
        sent = [c for c in calls if "POINT" in c]
        self.assertEqual(len(sent), 2)                                # the two substation area look-ups
        for c in sent:
            self.assertIn("geom'POINT(-0.1278 51.5074)'", c)          # 4 decimal places, about 10 m
        self.assertFalse(any("51.5" in c for c in calls if "POINT" not in c))

    def test_found_by_name_when_the_id_misses(self):
        (_, r), calls = self.fetch(answers(match='substation like "RIVERSIDE*"'))
        self.assertEqual((r["faults"], r["compare"]), (60, "more than"))
        self.assertTrue(any('substation like "RIVERSIDE*"' in c for c in calls))
        (_, r), _ = self.fetch(answers(match="NOWHERE"))
        self.assertEqual((r["faults"], r["years"], r["compare"], r["longest_mins"]), (None, [], "", None))

    def test_network_average_asked_once_a_day(self):
        self.fetch()
        _, calls = self.fetch()
        self.assertFalse(any("count(distinct substation)" in c for c in calls))

    def test_comparisons(self):
        for faults, word in ((40, "about the same as"), (30, "fewer than"), (48, "more than"), (47, "about the same as")):
            years = [{"regulatory_year": "2024-25", "faults": faults, "ci": 100}]
            self.assertEqual(self.fetch(answers(years=years))[0][1]["compare"], word, faults)
            server.UKPN_AVG.clear()

    def test_not_in_their_records(self):
        (items, r), _ = self.fetch(answers(secondary=[], primary=[]))
        self.assertEqual((items, r), ([], {"found": False}))
        self.assertEqual(server.live_rows({"supply": r}, [])[0]["text"], "Home isn't in UK Power Networks' substation records")

    def test_nothing_without_a_key_or_off_their_network(self):
        portal = Portal()
        server.ukpn_get = portal
        with self.assertRaises(server.FeedRefused) as cm:
            server.fetch_supply(HOME, {}, NOW)
        self.assertEqual(server.why_failed(cm.exception), server.UKPN_NEEDS_KEY)
        for lat, lon in ELSEWHERE.values():
            with self.assertRaises(server.FeedRefused):
                server.fetch_supply({"lat": lat, "lon": lon}, {"ukpn_key": KEY}, NOW)
        self.assertEqual(portal.calls, [])

    def test_the_key_only_goes_to_uk_power_networks(self):
        server.FEED_URLS["supply"] = "https://portal.example.org/api/explore/v2.1/catalog/datasets/"
        sent = []

        def fake(url, timeout=20, limit=0, headers=None, reply=None):
            sent.append((url, headers))
            return b'{"results": [{"c": 1}]}'
        server.http_get = fake
        self.assertEqual(server.ukpn_data("ukpn-secondary-sites", KEY, limit=1), [{"c": 1}])
        self.assertTrue(sent[0][0].startswith("https://portal.example.org/api/explore/v2.1/catalog/datasets/ukpn-secondary-sites/records?"))
        self.assertEqual(sent[0][1]["Authorization"], "Apikey " + KEY)
        for elsewhere in ("https://example.com/steal", "https://portal.example.org.evil.test/x", "http://portal.example.org/x"):
            with self.assertRaises(ValueError):
                server.ukpn_get(elsewhere, KEY)
        self.assertEqual(len(sent), 1)

    def test_a_wrong_key_is_said(self):
        def refuse(url, **kw):
            raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b""))
        server.http_get = refuse
        with self.assertRaises(server.FeedRefused) as cm:
            server.ukpn_data("ukpn-iis", KEY)
        self.assertEqual(str(cm.exception), "UK Power Networks didn't accept the API key (HTTP 401)")

    def test_the_line(self):
        (_, r), _ = self.fetch()
        row = server.live_rows({"supply": r}, [])[0]
        self.assertEqual((row["name"], row["state"]), ("Your power supply", "good"))
        self.assertEqual(row["text"], "Riverside Primary: 60 faults in 2024-25, more than the network's average of 40 · "
                                      "local substation 60-80% used")
        self.assertNotIn("Riverside", row["brief"])                      # the daily briefing isn't told the substation
        self.assertIn("supply", [g for g in server.LIVE_GROUPS if g[0] == "Power and energy"][0][1])


class CoverageTest(SupplyTest):
    def test_uk_power_networks_homes_only(self):
        self.assertEqual(server.source_covers("supply", {}, HOME), (True, ""))
        self.assertEqual(server.source_covers("supply", {}, {"lat": 51.27, "lon": 1.08}), (True, ""))    # Kent
        self.assertEqual(server.source_covers("supply", {}, {"lat": 52.63, "lon": 1.30}), (True, ""))    # Norwich
        self.assertEqual(server.source_covers("supply", {}, None), (True, ""))                           # says it needs one
        for town, (lat, lon) in ELSEWHERE.items():
            self.assertEqual(server.source_covers("supply", {}, {"lat": lat, "lon": lon}), (False, server.UKPN_ONLY), town)


def cut(ref, lat, lon, planned=False, customers=40):
    return server._cut("UK Power Networks", ref, lat, lon, customers, planned, "2026-11-18T18:00:00", "2026-11-18T10:00:00",
                       "SW1A 1")


class YourSubstationTest(SupplyTest):
    """A cut inside the area home's substation supplies is yours, however far its point is from home."""
    AREA = [[[-0.20, 51.47], [-0.05, 51.47], [-0.05, 51.55], [-0.20, 51.55], [-0.20, 51.47]]]   # wide, for the test

    def test_a_cut_at_your_substation_is_yours(self):
        cuts = [cut("in", 51.48, -0.10), cut("out", 51.56, -0.13), cut("near", 51.50, -0.13)]
        items, r = server.power_live(cuts, HOME, km=15, area=self.AREA)
        mine = [i for i in items if i.get("own_substation")]
        self.assertEqual([(i["id"], i["title"], i["severity"]) for i in mine],
                         [("power:UK Power Networks:in", "Power cut at your substation", 2),
                          ("power:UK Power Networks:near", "Power cut at your substation", 2)])
        self.assertIn("your power is likely to be off too", mine[0]["text"])
        self.assertEqual((r["own"], r["near"], r["cuts"][0]["text"][:18]), (2, 2, "Your substation · "))
        aff = server.affecting(items, {"power": r})
        self.assertEqual([x["title"] for x in aff["yours"]], ["Power cut at your substation"] * 2)
        self.assertEqual([x["postcodes"] for x in aff["near"]], ["SW1A 1"])   # the one outside: nearby only
        self.assertTrue(server.live_rows({"power": r}, items)[0]["text"].startswith("Power cut at your substation · "))
        cfg = dict(server.warn_cfg(), on=True, map=True)
        try:
            pts = server.live_map(cfg, HOME, items, {"power": r})["points"]
        finally:
            server.MAP_TILES_ON["on"] = False
        self.assertEqual(sorted(p["scope"] for p in pts), ["near", "yours", "yours"])   # each once

    def test_planned_and_without_an_area(self):
        items, _ = server.power_live([cut("p", 51.48, -0.10, planned=True)], HOME, km=15, area=self.AREA)
        self.assertEqual([(i["title"], i["severity"]) for i in items], [("Planned power cut at your substation", 1)])
        items, r = server.power_live([cut("in", 51.48, -0.10)], HOME, km=15)
        self.assertEqual((items, r["own"]), ([], 0))                     # 3 km off, and no area: nearby only

    def test_a_move_leaves_the_old_area_out(self):
        live = {"supply": {"area": server.ukpn_rings(SUPPLY_SQUARE)}}
        self.assertTrue(server.supply_area(live, HOME))
        self.assertEqual(server.supply_area(live, {"lat": 51.6, "lon": -0.2}), [])


class ResilienceTest(SupplyTest):
    def run_with(self, reading):
        server.api_warnings_set({"on": True, "sources": {"supply": True}}, {})
        with server.WARN_LOCK:
            server.WARN_STATE["live"] = {"supply": reading}
        return dict((m["id"], m) for m in server.summary()["resilience"]["items"])

    def test_backup_power_matters_more(self):
        (_, r), _ = self.fetch()
        calm = dict(r, ratio=1.0, longest_mins=120)
        before = self.run_with(calm)
        after = self.run_with(r)
        self.assertEqual((before["power_ups"]["priority"], after["power_ups"]["priority"]), (2, 3))
        self.assertEqual((before["power_backup"]["priority"], after["power_backup"]["priority"]), (1, 2))
        self.assertIn("Your local network (Riverside Primary) had more faults than most last year (60, against the "
                      "network's average of 40).", after["power_ups"]["why"])
        long_cut = self.run_with(dict(calm, longest_mins=400))
        self.assertIn("had a cut lasting 7 hours recently", long_cut["power_backup"]["why"])
        server.api_warnings_set({"sources": {"supply": False}}, {})
        self.assertEqual(dict((m["id"], m) for m in server.summary()["resilience"]["items"])["power_ups"]["priority"], 2)


class KeyTest(SupplyTest):
    def test_saved_hidden_and_not_backed_up(self):
        for bad in ("not a key!", "short1", "x" * 101, "a1b2-c3d4-e5f6-a1b2-c3d4"):
            self.assertApiError(400, server.api_warnings_set, {"ukpn_key": bad}, {})
        w = server.api_warnings_set({"ukpn_key": "f00d" * 16}, {})["warnings"]
        self.assertTrue(w["config"]["ukpn_key_set"])
        self.assertTrue(w["config"]["sources"]["supply"])   # adding a key switches it on
        self.assertNotIn("f00df00d", json.dumps(server.api_state({}, {})))
        self.assertNotIn("f00df00d", json.dumps(server.setting_raw("warnings")))
        self.assertNotIn(b"f00df00d", server.api_backup({}, {}).data)
        path = server.make_backup("auto")
        con = sqlite3.connect(path)
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM settings WHERE key = 'live_keys'").fetchone()[0], 0)
        finally:
            con.close()
        with open(path, "rb") as f:
            self.assertNotIn(b"f00df00d", f.read())
        self.assertEqual(server.live_keys(), {"ukpn": "f00d" * 16})

    def test_empty_leaves_it_null_removes_it(self):
        server.api_warnings_set({"ukpn_key": KEY, "nh_key": "b" * 32}, {})
        server.api_warnings_set({"sources": {"supply": False}}, {})
        server.api_warnings_set({"ukpn_key": ""}, {})
        self.assertEqual(server.live_keys()["ukpn"], KEY)
        server.api_warnings_set({"ukpn_key": "c" * 40}, {})
        self.assertFalse(server.warn_cfg()["sources"]["supply"])   # a new key leaves your choice alone
        server.api_warnings_set({"ukpn_key": None}, {})
        self.assertEqual(server.live_keys(), {"nh": "b" * 32})      # National Highways' key stays
        self.assertFalse(server.warn_cfg()["ukpn_key_set"])


class RunTest(SupplyTest):
    """The whole check, with stand-ins for UK Power Networks' portal and its live power cuts."""

    def setUp(self):
        super().setUp()
        self.cuts = []
        self.feeds = FakeFeeds({"ukpnodp": (ukpn_portal(), "application/json"),
                                "ukpn": (lambda: json.dumps(self.cuts).encode(), "application/json")})
        server.FEED_URLS.update({"supply": self.feeds.base + "ukpnodp/", "power_ukpn": self.feeds.base + "ukpn"})
        server.HA_HOME["at"] = time.time()   # nothing to ask Home Assistant
        server.api_warnings_set({"on": True, "lat": HOME["lat"], "lon": HOME["lon"], "map": True,
                                 "sources": {k: k == "power" for k, _, _ in server.WARN_SOURCES}}, {})

    def tearDown(self):
        self.feeds.close()
        server.MAP_TILES_ON["on"] = False
        super().tearDown()

    def portal_asks(self):
        return [r for r in self.feeds.log if r["path"].startswith("/ukpnodp/")]

    def test_off_or_without_a_key_nothing_is_sent(self):
        server.warnings_run()
        self.assertEqual(self.portal_asks(), [])
        server.api_warnings_set({"sources": {"supply": True}}, {})   # on, but no key
        server.warnings_run()
        self.assertEqual(self.portal_asks(), [])
        self.assertEqual(server.warn_public()["sources"]["supply"]["error"], server.UKPN_NEEDS_KEY)
        for req in self.feeds.log:
            self.assertNotIn("51.5", req["path"])

    def test_your_supply_and_a_cut_at_your_substation(self):
        self.cuts = [{"powercuttype": "Unplanned", "incidentreference": "INC-1", "nocustomeraffected": 30,
                      "geopoint": {"lat": 51.510, "lon": -0.125}, "postcodesaffected": "WC2N 5",
                      "estimatedrestorationdate": "2026-11-18T18:00:00", "receiveddate": "2026-11-18T10:00:00"}]
        server.api_warnings_set({"ukpn_key": KEY}, {})            # switches it on
        server.warnings_run()
        w = server.warn_public()
        self.assertTrue(w["sources"]["supply"]["ok"], w["sources"])
        self.assertNotIn("area", w["live"]["supply"])                # home's substation area stays on the Pi
        row = [r for r in w["live_rows"] if r["key"] == "supply"][0]
        self.assertTrue(row["text"].startswith("Riverside Primary: 60 faults in 2024-25"))
        self.assertIn("CC BY 4.0", row["credit"])
        self.assertIn("supply", [k for g in w["live_layout"]["groups"] if g["name"] == "Power and energy" for k in g["keys"]])
        self.assertEqual([i["title"] for i in w["items"]], ["Power cut 0.4 km away"])   # power was checked first
        server.WARN_STATE["sources"]["power"]["t"] = 0               # due again: now with home's substation known
        server.warnings_run()
        w = server.warn_public()
        self.assertEqual([(i["title"], i.get("own_substation")) for i in w["items"]], [("Power cut at your substation", True)])
        self.assertEqual([x["title"] for x in w["affecting"]["yours"]], ["Power cut at your substation"])
        state = json.dumps(server.api_state({}, {}))
        self.assertNotIn(KEY, state)
        self.assertNotIn("-0.135", state)                            # the area's outline isn't sent to the app
        asks = self.portal_asks()
        self.assertEqual(len(asks), 6)                               # once a day: the second check asked nothing
        for req in self.feeds.log:
            mine = req["path"].startswith("/ukpnodp/")
            self.assertEqual(req["headers"].get("Authorization"), "Apikey " + KEY if mine else None)
            if not mine:
                self.assertNotIn("51.5", req["path"])                # home's location only to UK Power Networks
        where = [urllib.parse.unquote_plus(r["path"]) for r in asks if "POINT" in urllib.parse.unquote_plus(r["path"])]
        self.assertEqual(len(where), 2)
        # Home as the warnings settings keep it (3 decimal places), never more finely than 4.
        self.assertTrue(all("POINT(-0.1280 51.5070)" in p for p in where), where)
