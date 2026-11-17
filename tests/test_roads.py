"""1.20.0: road closures from National Highways. Parsing their DATEX II JSON, choosing what's near home, the warnings
and the map, and the household's own key (kept out of /api/state and backups). Stand-in feeds only, and home is
central London."""
import datetime as dt
import json
import sqlite3
import time

from feeds import FakeFeeds, nh_payload as payload, nh_record
from support import AppTest, server

HOME = {"lat": 51.5074, "lon": -0.1278}   # central London
NOW = dt.datetime(2026, 11, 17, 12, 0, tzinfo=dt.timezone.utc)
KEY = "k" * 32


def record(start="2026-11-17T11:00:00Z", end="2026-11-17T15:00:00Z", lanes=("closed", "open"), **kw):
    """A closure on 17 Nov 2026 (NOW is noon): a lane closure on the A2 near Blackheath, unless said otherwise."""
    return nh_record(start=start, end=end, lanes=lanes, **kw)


def carriageway(r):
    return r["sitRoadOrCarriagewayOrLaneManagement"]["locationReference"]["locLocationGroupByList"][
        "locationContainedInGroup"][0]["locLinearLocation"]["supplementaryPositionalDescription"]["carriageway"][0]


def comment(r, text):
    r["sitRoadOrCarriagewayOrLaneManagement"]["generalPublicComment"] = [{"comment": text}]
    return r


class ParseTest(AppTest):
    def test_lane_and_full_closures(self):
        got = server.nh_closures(payload(record(), record(lanes=("closed", "closed"), rid="r2"),
                                         record(mtype="roadClosed", lanes=("open",), rid="r3")), True)
        self.assertEqual([c["full"] for c in got], [False, True, True])
        c = got[0]
        self.assertEqual((c["road"], c["where"], c["cause"], c["status"], c["unplanned"]),
                         ("A2", "A2 eastbound near Blackheath", "vehicleObstruction", "active", True))
        self.assertEqual(c["points"], [(51.47, 0.01), (51.471, 0.012)])
        self.assertEqual(c["start"], dt.datetime(2026, 11, 17, 11, 0, tzinfo=dt.timezone.utc))

    def test_only_the_affected_lanes_listed(self):
        """The feed lists just the closed lane: lane 1 of three is a lane closure, not the road closed."""
        r = record(lanes=("closed",))
        carriageway(r)["carriagewayExtensionG"]["impactOnCarriageway"]["numberOfOperationalLanes"] = 2   # lanes left open
        self.assertFalse(server.nh_closures(payload(comment(r, "A2 eastbound - lane 1 closure")), False)[0]["full"])
        r = record(lanes=("closed",))   # a one-lane slip road, closed
        self.assertTrue(server.nh_closures(payload(comment(r, "Jct 2 entry slip road closure")), False)[0]["full"])
        self.assertFalse(server.nh_closures(payload(comment(r, "Jct 14 narrow lanes with speed restriction")), False)[0]["full"])

    def test_counts_as_seen_live(self):
        """Shapes from the live feed (17 Nov 2026): lanes restricted, and lanes left open."""
        def full(shut, open_, mtype="other", text=""):
            r = record(mtype=mtype, lanes=())
            carriageway(r)["carriagewayExtensionG"]["impactOnCarriageway"].update(
                numberOfLanesRestricted=shut, numberOfOperationalLanes=open_)
            return server.nh_closures(payload(comment(r, text)), False)[0]["full"]
        self.assertTrue(full(2, 0, "carriagewayClosures", "Jct 33 exit slip road closure"))
        self.assertFalse(full(2, 1, text="Jct 33 approach lane 1,2 closures"))
        self.assertFalse(full(1, 1, text="Jct 34 entry slip lane closure"))
        self.assertFalse(full(0, 3, "laneClosures"))
        self.assertTrue(full(1, 0, text="Exit slip road closed"))

    def test_point_location_and_odd_shapes(self):
        got = server.nh_closures(payload(record(point=(51.52, -0.10), road="M25")), False)
        self.assertEqual((got[0]["road"], got[0]["points"], got[0]["lines"]), ("M25", [(51.52, -0.1)], []))
        for bad in (None, {}, {"D2Payload": None}, {"D2Payload": {"situation": [None, {"situationRecord": [1, {}]}]}},
                    {"D2Payload": []}):
            self.assertEqual(server.nh_closures(bad, True), [])

    def test_long_stretches_are_cut_down_for_the_map(self):
        pos = " ".join("%.4f %.4f" % (51.47 + n / 10000.0, 0.01) for n in range(500))
        lines = server.nh_closures(payload(record(pos=pos)), True)[0]["lines"]
        self.assertLessEqual(len(lines[0]), 60)
        self.assertEqual(lines[0][-1], [51.5199, 0.01])   # the far end is kept


class NearHomeTest(AppTest):
    def live(self, *recs, unplanned=True, km=15):
        return server.roads_live(server.nh_closures(payload(*recs), unplanned), HOME, NOW, km)

    def test_levels(self):
        full = record(lanes=("closed", "closed"))
        items, r = self.live(full)
        self.assertEqual([(i["severity"], i["level"]) for i in items], [(2, "Road closed")])   # unplanned, closed now
        self.assertEqual(self.live(full, unplanned=False)[0], [])                              # roadworks: no warning
        later = record(lanes=("closed", "closed"), start="2026-11-17T20:00:00Z", end="2026-11-18T05:00:00Z")
        items, r = self.live(later, unplanned=False)
        self.assertEqual((items, r["later"], r["closures"][0]["when"][:5]), ([], 1, "From "))   # tonight
        items, r = self.live(record())
        self.assertEqual(items, [])                                                            # a lane closure
        c = r["closures"][0]
        self.assertTrue(c["title"].startswith("A2 lane closure: A2 eastbound near Blackheath · "))
        self.assertIn("because of a stopped vehicle", c["text"])
        items, _ = self.live(record(cause="environmentalObstruction"))                          # flooding
        self.assertEqual([(i["severity"], i["level"]) for i in items], [(1, "Lane closed")])
        items, r = self.live(full)
        i = items[0]
        self.assertEqual((i["id"], i["source"], i["kind"], i["lines"]), ("roads:r1", "roads", "road", [[[51.47, 0.01], [51.471, 0.012]]]))
        self.assertEqual((i["lat"], i["lon"]), (51.47, 0.01))   # the nearer end
        self.assertEqual(i["issued"], "2026-11-17T11:00:00+00:00")
        self.assertEqual((r["unplanned"], r["closed"], r["later"]), (1, 1, 0))

    def test_left_out(self):
        items, r = self.live(
            record(end="2026-11-16T10:00:00Z"),                                            # finished yesterday
            record(status="suspended", rid="x2"),                                          # cancelled
            record(pos="53.48 -2.24", rid="x3"),                                           # Manchester
            record(start="2026-11-18T09:00:00Z", end="2026-11-18T12:00:00Z", rid="x4"),    # tomorrow
            record(pos="", rid="x5"))                                                      # nowhere
        self.assertEqual((items, r["closures"]), ([], []))
        self.assertEqual(self.live(record(), km=5)[1]["closures"], [])                     # Blackheath is 10.4 km off

    def test_one_line_per_stretch_most_serious(self):
        items, r = self.live(record(), record(rid="r2"), record(lanes=("closed", "closed"), rid="r3"))
        self.assertEqual([c["severity"] for c in r["closures"]], [2, 0])
        self.assertEqual([i["id"] for i in items], ["roads:r3"])

    def test_the_line_in_the_wider_picture(self):
        def text(*recs, **kw):
            items, r = self.live(*recs, **kw)
            return server.live_rows({"roads": r}, items)[0]
        self.assertEqual(text()["text"], "No closures within 15 km")
        row = text(record(lanes=("closed", "closed")), record(where="A2 westbound", rid="r2"),
                   record(where="A3", rid="r3", start="2026-11-17T20:00:00Z"))
        self.assertEqual((row["text"], row["state"]), ("1 road closed within 15 km · 1 lane closure · 1 planned or later today", "bad"))
        row = text(record(cause="poorEnvironment"))
        self.assertEqual((row["text"], row["state"]), ("1 lane closure within 15 km", "warn"))
        self.assertEqual(text(record(), unplanned=False)["text"], "No unplanned closures within 15 km · 1 planned or later today")


class AffectingAndMapTest(AppTest):
    def tearDown(self):
        server.MAP_TILES_ON["on"] = False
        super().tearDown()

    def test_a_road_closed_is_affecting_you_and_drawn(self):
        items, r = server.roads_live(server.nh_closures(payload(record(lanes=("closed", "closed"))), True)
                                     + server.nh_closures(payload(record(where="A2 westbound", rid="p1")), False), HOME, NOW, 15)
        aff = server.affecting(items, {"roads": r})
        self.assertEqual([(x["source"], x["title"], x["level"], x["started"]) for x in aff["yours"]],
                         [("roads", "A2 closed: A2 eastbound near Blackheath", "Road closed", "2026-11-17T11:00:00+00:00")])
        cfg = dict(server.warn_cfg(), on=True, map=True)
        pts = server.live_map(cfg, HOME, items, {"roads": r})["points"]
        self.assertEqual([(p["road"], p["scope"], p["routine"], p["severity"], len(p["lines"])) for p in pts],
                         [("unplanned", "yours", False, 2, 1), ("planned", "near", True, 0, 1)])
        self.assertEqual(pts[0]["title"], "A2 closed: A2 eastbound near Blackheath")   # no "km away" on the map


class FetchTest(AppTest):
    def test_needs_a_key(self):
        with self.assertRaises(server.FeedRefused) as cm:
            server.fetch_roads(HOME, {}, NOW, 15)
        self.assertIn("National Highways API key", str(cm.exception))
        self.assertEqual(server.why_failed(cm.exception), server.NH_NEEDS_KEY)

    def test_pages_and_nothing_near(self):
        calls, real = [], server.nh_get

        def fake(url, key):
            calls.append(url)
            self.assertEqual(key, KEY)
            if "pageCursor" in url:
                return payload(record(pos="53.48 -2.24")), None
            return payload(), url + "&pageCursor=2"
        server.nh_get = fake
        try:
            items, r = server.fetch_roads(HOME, {"nh_key": KEY}, NOW, 15)
        finally:
            server.nh_get = real
        self.assertEqual(len(calls), 4)                     # two pages each of unplanned and planned
        self.assertTrue(any("closureType=unplanned" in u for u in calls))
        self.assertEqual((items, r["closures"], r["checked"]), ([], [], 2))
        self.assertNotIn("51.5", " ".join(calls))           # home's location never goes to National Highways

    def test_the_next_page_and_the_key_only_go_to_national_highways(self):
        server.FEED_URLS["roads"] = "https://api.example.org/roads/v2.0/closures"
        sent = []

        def fake(url, timeout=20, limit=0, headers=None, reply=None):
            sent.append((url, headers))
            reply["x-next"] = "/roads/v2.0/closures?pageCursor=2"
            return b"{}"
        server.http_get = fake
        got, nxt = server.nh_get(server.FEED_URLS["roads"] + "?closureType=planned", KEY)
        self.assertEqual((got, nxt), ({}, "https://api.example.org/roads/v2.0/closures?pageCursor=2"))
        self.assertEqual(sent[0][1]["Ocp-Apim-Subscription-Key"], KEY)
        for elsewhere in ("https://example.com/steal", "https://api.example.org.evil.test/x", "http://api.example.org/x"):
            with self.assertRaises(ValueError):
                server.nh_get(elsewhere, KEY)
        self.assertEqual(len(sent), 1)

    def test_england_only(self):
        self.assertEqual(server.source_covers("roads", {}, HOME), (True, ""))
        self.assertFalse(server.source_covers("roads", {}, {"lat": 55.861, "lon": -4.251})[0])    # Glasgow
        self.assertFalse(server.source_covers("roads", {}, {"lat": 51.4816, "lon": -3.1791})[0])  # Cardiff


class KeyTest(AppTest):
    def test_saved_hidden_and_not_backed_up(self):
        self.assertApiError(400, server.api_warnings_set, {"nh_key": "not a key!"}, {})
        self.assertApiError(400, server.api_warnings_set, {"nh_key": "short1"}, {})
        w = server.api_warnings_set({"nh_key": "f00d" * 8}, {})["warnings"]
        self.assertTrue(w["config"]["nh_key_set"])
        self.assertTrue(w["config"]["sources"]["roads"])   # adding a key switches road closures on
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
        self.assertEqual(server.live_keys(), {"nh": "f00d" * 8})   # still here, just not in the copy

    def test_empty_leaves_it_null_removes_it(self):
        server.api_warnings_set({"nh_key": KEY}, {})
        server.api_warnings_set({"sources": {"roads": False}}, {})
        server.api_warnings_set({"nh_key": ""}, {})
        self.assertEqual(server.live_keys(), {"nh": KEY})
        server.api_warnings_set({"nh_key": "b" * 40}, {})
        self.assertFalse(server.warn_cfg()["sources"]["roads"])   # a new key leaves your choice alone
        server.api_warnings_set({"nh_key": None}, {})
        self.assertEqual(server.live_keys(), {})
        self.assertFalse(server.warn_cfg()["nh_key_set"])


class RunTest(AppTest):
    """The whole check, with a stand-in for National Highways."""

    def setUp(self):
        super().setUp()
        self.recs = [record(lanes=("closed", "closed"), start=None, end=None),
                     record(where="A2 westbound near Kidbrooke", rid="r2", start=None, end=None),
                     record(where="A3 at Clapham", rid="r3", road="A3", pos="51.46 -0.14 51.461 -0.141", start=None, end=None)]
        self.planned = []

        def nh():
            planned = "closureType=planned" in self.feeds.log[-1]["path"]
            return json.dumps(payload(*(self.planned if planned else self.recs))).encode()
        self.feeds = FakeFeeds({"nh": (nh, "application/json")})
        server.FEED_URLS["roads"] = self.feeds.base + "nh"
        server.HA_HOME["at"] = time.time()   # nothing to ask Home Assistant
        server.api_warnings_set({"on": True, "lat": HOME["lat"], "lon": HOME["lon"], "map": True, "nh_key": KEY, "near_km": 15,
                                 "sources": {k: k == "roads" for k, _, _ in server.WARN_SOURCES}}, {})

    def tearDown(self):
        self.feeds.close()
        server.MAP_TILES_ON["on"] = False
        super().tearDown()

    def test_closures_near_home(self):
        self.planned = [record(where="A2 near Eltham", rid="p1", start=None, end=None)]
        server.warnings_run()
        w = server.warn_public()
        self.assertTrue(w["sources"]["roads"]["ok"], w["sources"])
        self.assertEqual([(i["title"].split(" · ")[0], i["severity"]) for i in w["items"]],
                         [("A2 closed: A2 eastbound near Blackheath", 2)])
        self.assertEqual([x["source"] for x in w["affecting"]["yours"]], ["roads"])
        self.assertEqual(sorted(p["road"] for p in w["map"]["points"]), ["planned", "unplanned", "unplanned", "unplanned"])
        row = [r for r in w["live_rows"] if r["key"] == "roads"][0]
        self.assertIn("Powered by National Highways' Transport Data Feeds", row["credit"])
        self.assertEqual(len(self.feeds.log), 2)
        for req in self.feeds.log:
            self.assertEqual(req["headers"].get("Ocp-Apim-Subscription-Key"), KEY)
            for needle in ("51.5", "0.12", "lat=", "lon="):
                self.assertNotIn(needle, req["path"], req["path"])
        self.assertNotIn(KEY, json.dumps(w))

    def test_each_closure_warns_once(self):
        events = []
        server.HA_TOKEN = "x"
        real = server.ha_call
        server.ha_call = lambda method, path, body=None, timeout=10: events.append(body)
        try:
            server.warnings_run()
            self.recs.append(record(where="A20 near Lee", road="A20", rid="r4", lanes=("closed", "closed"), start=None, end=None))
            server.WARN_STATE["sources"]["roads"]["t"] = 0   # due again
            server.warnings_run()
            server.WARN_STATE["sources"]["roads"]["t"] = 0
            server.warnings_run()
        finally:
            server.ha_call = real
        self.assertEqual([[i["title"].split(":")[0] for i in e["items"]] for e in events], [["A2 closed"], ["A20 closed"]])

    def test_a_wrong_key_is_said(self):
        self.feeds.broken["nh"] = 401
        server.warnings_run()
        s = server.warn_public()["sources"]["roads"]
        self.assertEqual((s["ok"], s["error"]), (False, "National Highways didn't accept the API key (HTTP 401)"))

    def test_no_key_says_so(self):
        server.api_warnings_set({"nh_key": None}, {})
        server.warnings_run()
        self.assertEqual(server.warn_public()["sources"]["roads"]["error"], server.NH_NEEDS_KEY)
        self.assertEqual(self.feeds.log, [])
