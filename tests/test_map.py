"""1.19.0: the live alerts map.

Off unless "Show a map" is ticked in the warnings settings. The Pi works out what it draws from what the feeds already
gave (no new lookups), the browser loads the map pictures from OpenStreetMap, and the web server's security policy
lets those pictures in only while the map is on. Leaflet, which draws it, comes with the app. Home is central London."""
import os

from support import APP_DIR, AppServer, AppTest, server
from test_affecting import CUTS, HOME, KM_LAT, NOW, power, report, ukpn, water

TILES = "https://tile.openstreetmap.org"


def switch_on(**extra):
    body = dict({"on": True, "lat": HOME["lat"], "lon": HOME["lon"]}, **extra)
    return server.api_warnings_set(body, {})["warnings"]


def flood(sev, km, lat=True):
    i = {"id": "flood:%d:%d" % (sev, km), "source": "floods", "kind": "flood", "severity": sev,
         "level": "Flood warning" if sev == 2 else "Flood alert", "title": "Flood warning: Tidal Thames riverside",
         "text": "Flooding is expected.", "area": "Greater London", "when": "", "url": "", "issued": server.iso_utc(NOW),
         "distance_km": km}
    if lat:
        i.update(lat=round(HOME["lat"] + km * KM_LAT, 4), lon=HOME["lon"])
    return i


def station(sid, km, state):
    return {"id": sid, "name": "Gauge " + sid, "river": "River Lea", "where": "River Lea at Gauge " + sid, "km": km,
            "state": state, "lat": HOME["lat"] + km * KM_LAT, "lon": HOME["lon"]}


def seed(items, live):
    stamp = dict(checked_at=server.now_iso(), credit="")
    with server.WARN_LOCK:
        server.WARN_STATE.update({"items": items, "live": dict((k, dict(v, **stamp)) for k, v in live.items())})


class SettingTest(AppTest):
    def tearDown(self):
        server.MAP_TILES_ON["on"] = False
        super().tearDown()

    def test_off_to_start_with(self):
        self.assertIs(server.warn_cfg()["map"], False)
        self.assertEqual(switch_on()["map"], {"on": False})   # warnings on isn't enough

    def test_switching_it_on_and_off(self):
        self.assertIs(switch_on(map=True)["config"]["map"], True)
        self.assertIs(server.warn_cfg()["map"], True)
        server.api_warnings_set({"near_km": 20}, {})   # other settings leave it alone
        self.assertIs(server.warn_cfg()["map"], True)
        self.assertIs(switch_on(map=False)["config"]["map"], False)

    def test_only_true_or_false(self):
        for bad in ("yes", 1, None, [], {"on": True}):
            self.assertApiError(400, server.api_warnings_set, {"map": bad}, {})
        self.assertIs(server.warn_cfg()["map"], False)

    def test_a_damaged_setting_is_off(self):
        with server.tx() as db:
            server.set_setting_raw(db, "warnings", {"on": True, "map": "true"})
        self.assertIs(server.warn_cfg()["map"], False)

    def test_needs_warnings_on_and_somewhere_to_centre_on(self):
        server.api_warnings_set({"map": True}, {})
        self.assertEqual(server.warn_public()["map"], {"on": False})   # warnings are off
        server.api_warnings_set({"on": True}, {})
        m = server.warn_public()["map"]
        self.assertTrue(m["on"])
        self.assertIsNone(m["home"])   # no location yet: the app leaves the map out


class PointsTest(AppTest):
    def tearDown(self):
        server.MAP_TILES_ON["on"] = False
        super().tearDown()

    def test_warnings_nearby_and_routine(self):
        p_items, p = power()
        w_items, w = water([report("supply", "No water", 2.5, reach_km=3), report("supply", "Low pressure", 6),
                            report("planned", "Planned work", 3), report("leak", "Reported leak", 4)])
        far = flood(2, 30)
        no_place = dict(flood(1, 3, lat=False), id="flood:noplace")
        items = sorted(p_items + w_items + [far, no_place], key=lambda i: -i["severity"])
        rivers = {"stations": [station("1", 3, "normal"), station("2", 5, "high")]}
        seed(items, {"power": p, "water": w, "rivers": rivers})
        m = switch_on(map=True, near_km=10, water_co="Yorkshire Water")["map"]
        loc = server.warn_public()["location"]
        self.assertEqual((m["on"], m["home"], m["near_km"]), (True, [loc["lat"], loc["lon"]], 10))
        self.assertAlmostEqual(m["home"][0], HOME["lat"], places=3)
        pts = m["points"]
        got = sorted((x["kind"], x["scope"], x["routine"], round(x["distance_km"])) for x in pts)
        self.assertEqual(got, sorted([
            ("power", "yours", False, 1),     # the cut within 2 km: a warning
            ("power", "near", False, 6),      # further out: listed, not a warning
            ("power", "near", True, 5),       # planned work: routine
            ("water", "yours", False, 2),     # the company says it's yours
            ("water", "near", False, 6),      # another street's
            ("water", "near", True, 3),       # planned work
            ("water", "near", True, 4),       # a leak
            ("flood", "yours", False, 30),    # a flood warning further off
            ("river", "near", True, 3),       # a river at its usual level
        ]))
        # The cut 15 km away is past the near distance, the high river has no warning here (only its reading), and
        # the flood alert with no place can't be drawn.
        self.assertFalse([x for x in pts if x["distance_km"] == 15])
        w_all = server.warn_public()
        for x in pts:
            self.assertTrue(-90 <= x["lat"] <= 90 and -180 <= x["lon"] <= 180)
            self.assertIn(x["kind"], ("power", "water", "flood", "river"))
            if x["scope"] == "yours":   # opens the warning itself
                self.assertEqual(w_all["items"][x["i"]]["title"].split(" ")[0], x["title"].split(" ")[0])
                self.assertGreaterEqual(x["severity"], 1)
            else:                       # opens the source's details
                self.assertIn(x["key"], ("power", "water", "rivers"))
                self.assertEqual(x["severity"], 0)
        mine = [x for x in pts if x["kind"] == "power" and x["scope"] == "yours"][0]
        self.assertEqual(mine["title"], "Power cut")   # without the distance, as Affecting you
        self.assertEqual(mine["severity"], 2)

    def test_a_planned_cut_in_your_area_is_routine(self):
        items, p = server.power_live(server.parse_ukpn(ukpn(CUTS[3])), HOME, km=10)
        self.assertEqual(items, [])   # 5 km: not a warning
        near = dict(CUTS[3], geopoint={"lat": HOME["lat"] + 1 * KM_LAT, "lon": HOME["lon"]})
        items, p = server.power_live(server.parse_ukpn(ukpn(near)), HOME)
        self.assertEqual(items[0]["level"], "Planned")
        seed(items, {"power": p})
        pts = switch_on(map=True)["map"]["points"]
        self.assertEqual([(x["scope"], x["routine"]) for x in pts], [("yours", True)])

    def test_the_new_coordinates_are_the_feeds_own(self):
        items, _ = power()
        self.assertAlmostEqual(items[0]["lat"], HOME["lat"] + 1.0 * KM_LAT, places=4)
        items, r = water([report("supply", "No water", 0.5)])
        self.assertAlmostEqual(items[0]["lat"], HOME["lat"] + 0.5 * KM_LAT, places=4)
        self.assertAlmostEqual(r["reports"][0]["lat"], HOME["lat"] + 0.5 * KM_LAT, places=4)

    def test_nothing_new_goes_to_home_assistant_or_the_briefing(self):
        p_items, p = power()
        seed(p_items, {"power": p})
        switch_on(map=True)
        brief = server.warn_brief()
        self.assertTrue(brief["items"])
        for i in brief["items"]:
            self.assertNotIn("lat", i)
            self.assertNotIn("lon", i)
        self.assertNotIn("map", brief)
        known = server.brief_known({})
        self.assertNotIn(str(round(HOME["lat"], 3)), known)

    def test_off_means_no_points(self):
        p_items, p = power()
        seed(p_items, {"power": p})
        self.assertEqual(switch_on()["map"], {"on": False})

    def test_nothing_is_fetched_for_it(self):
        p_items, p = power()
        seed(p_items + [flood(2, 30)], {"power": p})
        asked = []

        def no_fetch(url, *a, **kw):
            asked.append(url)
            raise AssertionError("the map shouldn't fetch anything")
        server.http_get = no_fetch
        m = switch_on(map=True)["map"]
        server.warn_public()
        self.assertTrue(m["points"])
        self.assertEqual(asked, [])


class WebTest(AppTest):
    def setUp(self):
        super().setUp()
        self.web = AppServer()

    def tearDown(self):
        self.web.close()
        server.MAP_TILES_ON["on"] = False
        super().tearDown()

    def csp(self, path="/"):
        status, _, headers = self.web.call("GET", path, ctype=None)
        self.assertEqual(status, 200)
        return headers.get("Content-Security-Policy", "")

    def test_map_pictures_are_only_allowed_while_its_on(self):
        self.assertEqual(self.csp(), server.CSP)
        self.assertNotIn(TILES, self.csp())
        self.assertNotIn("openstreetmap", self.csp("/app.js"))
        switch_on()
        self.assertNotIn(TILES, self.csp())   # warnings on, map off
        switch_on(map=True)
        on = self.csp()
        self.assertIn("img-src 'self' data: " + TILES + ";", on)
        # Only pictures: scripts, styles and connections are still Dads Army's own.
        self.assertIn("script-src 'self';", on)
        self.assertIn("connect-src 'self';", on)
        self.assertEqual(on.count("openstreetmap"), 1)
        server.api_warnings_set({"on": False}, {})
        self.assertEqual(self.csp(), server.CSP)   # warnings off takes the map with them
        switch_on(map=True)
        switch_on(map=False)
        self.assertEqual(self.csp(), server.CSP)

    def test_a_restart_remembers(self):
        switch_on(map=True)
        server.MAP_TILES_ON["on"] = False   # as when the add-on starts
        server.warn_cfg()                   # what main() does before serving
        self.assertIn(TILES, self.csp())

    def test_leaflet_comes_with_the_app(self):
        for path, ctype in (("/vendor/leaflet/leaflet.js", "javascript"), ("/vendor/leaflet/leaflet.css", "text/css")):
            status, body, headers = self.web.call("GET", path, ctype=None)
            self.assertEqual(status, 200, path)
            self.assertIn(ctype, headers.get("Content-Type"))
            if path.endswith(".js"):
                self.assertIn(b"Leaflet 1.9.4", body[:400])
        with open(os.path.join(APP_DIR, "static", "vendor", "leaflet", "LICENSE"), encoding="utf-8") as f:
            self.assertIn("BSD 2-Clause", f.read())

    def test_the_app_only_loads_it_when_the_map_is_on(self):
        with open(os.path.join(APP_DIR, "static", "index.html"), encoding="utf-8") as f:
            self.assertNotIn("leaflet", f.read().lower())   # not on the page: app.js adds it when there's a map
        with open(os.path.join(APP_DIR, "static", "app.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("'vendor/leaflet/leaflet.js'", js)
        self.assertNotIn("unpkg", js)
        self.assertNotIn("cdnjs", js)
        self.assertEqual(js.count("tile.openstreetmap.org"), 1)
        self.assertIn("OpenStreetMap contributors", js)

    def test_the_state_carries_it(self):
        p_items, p = power()
        seed(p_items, {"power": p})
        switch_on(map=True)
        status, out = self.web.json("GET", "/api/state")
        self.assertEqual(status, 200)
        m = out["warnings"]["map"]
        self.assertTrue(m["on"])
        self.assertEqual(m["home"], [out["warnings"]["location"]["lat"], out["warnings"]["location"]["lon"]])
        self.assertTrue(m["points"])
