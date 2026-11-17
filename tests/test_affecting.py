"""1.18.0: Affecting you, the wider picture in groups, and the "near you" distance.

Affecting you lists what's touching home, item by item: exactly the warnings in force from the practical sources,
which are the same items that turn a source's line amber or red, so the two can never disagree. What a source lists
further out, but doesn't warn about, goes under "Nearby, not in your area". Home here is central London."""
import datetime as dt
import json

from feeds import FakeFeeds
from support import AppTest, server

HOME = {"lat": 51.5072, "lon": -0.1276}
NOW = dt.datetime.now(dt.timezone.utc)
KM_LAT = 1 / 111.2   # about a km north


def cut(ref, km, planned=False, postcodes="SW1A 1", etr="2026-11-14T23:00:00", homes=40):
    return {"incidentreference": ref, "powercuttype": "Planned" if planned else "Unplanned", "statusid": 1,
            "nocustomeraffected": homes, "postcodesaffected": postcodes, "receiveddate": "2026-11-14T05:30:00",
            "estimatedrestorationdate": etr, "geopoint": {"lat": HOME["lat"] + km * KM_LAT, "lon": HOME["lon"]}}


def ukpn(*cuts):
    return json.dumps(list(cuts)).encode()


CUTS = [cut("INCD-1", 1.0, postcodes="SW1A 1, SW1A 2"), cut("INCD-2", 6.0, postcodes="N1 7"),
        cut("INCD-3", 15.0, postcodes="EN1 1"), cut("INCD-4", 5.0, planned=True, postcodes="E1 6")]


def power(km=server.POWER_KM):
    return server.power_live(server.parse_ukpn(ukpn(*CUTS)), HOME, km=km)


def water(reports, km=server.WATER_NEAR_KM):
    return server.water_live(reports, "Yorkshire Water", HOME, NOW, km)


def report(group, what, km, reach_km=None):
    return server._report(group, what, "Somewhere", HOME["lat"] + km * KM_LAT, HOME["lon"], NOW - dt.timedelta(hours=2),
                          "We're fixing a burst main. Supply should be back this evening.", "", None, reach_km)


def agree(test, items, live):
    """The consistency rule: a source is in Affecting you exactly when its line has a warning behind it, and then the
    line isn't green. Nothing is in both lists."""
    aff = server.affecting(items, live)
    rows = dict((r["key"], r) for r in server.live_rows(live, items))
    listed = set(x["source"] for x in aff["yours"])
    for key, row in rows.items():
        warned = any(i["source"] == key and i["severity"] >= 1 for i in items)
        if key in server.AFFECT_SOURCES:
            test.assertEqual(key in listed, warned, key)
        if key in listed:
            test.assertNotEqual(row["state"], "good", "%s: Affecting you lists it, but its line says all's well" % key)
    near = set((x["source"], x["distance_km"]) for x in aff["near"])
    test.assertFalse(near & set((x["source"], x["distance_km"]) for x in aff["yours"]))
    return aff, rows


class AffectingYouTest(AppTest):
    def test_a_power_cut_in_your_area_is_yours_and_one_further_out_is_nearby(self):
        items, r = power()
        aff, rows = agree(self, items, {"power": r})
        self.assertEqual([x["source"] for x in aff["yours"]], ["power"])
        mine = aff["yours"][0]
        self.assertEqual(mine["title"], "Power cut")   # without "1.0 km away": the distance is on the line below
        self.assertEqual(mine["distance_km"], 1)
        self.assertEqual(mine["postcodes"], "SW1A 1, SW1A 2")
        self.assertTrue(mine["back_by"])
        self.assertEqual(mine["key"], "power")         # opens the power cuts' details
        self.assertTrue(mine["detail"].startswith("UK Power Networks is working on a power cut"))
        self.assertNotIn(". ", mine["detail"])          # the first sentence only
        # The 6 km one is listed, not a warning; the planned work 5 km away is routine; 15 km is too far.
        self.assertEqual([(x["title"], x["distance_km"], x["postcodes"]) for x in aff["near"]], [("Power cut", 6.0, "N1 7")])
        self.assertEqual(aff["near_count"], 1)
        self.assertEqual(rows["power"]["state"], "bad")

    def test_only_a_cut_further_out_isnt_affecting_you(self):
        items, r = server.power_live(server.parse_ukpn(ukpn(CUTS[1])), HOME)
        aff, rows = agree(self, items, {"power": r})
        self.assertEqual(aff["yours"], [])
        self.assertEqual(len(aff["near"]), 1)
        self.assertEqual(rows["power"]["state"], "warn")   # a cut within 10 km is worth watching, but not yours

    def test_water_the_company_says_is_yours_and_another_streets(self):
        reports = [report("supply", "No water", 2.5, reach_km=3), report("supply", "Low pressure", 6),
                   report("leak", "Reported leak", 4)]
        items, r = water(reports)
        aff, rows = agree(self, items, {"water": r})
        self.assertEqual([x["title"] for x in aff["yours"]], ["No water reported"])
        self.assertEqual(aff["yours"][0]["severity"], 2)   # no water at all
        self.assertTrue(aff["yours"][0]["started"])
        self.assertEqual([x["title"] for x in aff["near"]], ["Low pressure"])   # a leak isn't a supply problem
        self.assertEqual(rows["water"]["state"], "bad")

    def test_a_supply_report_further_out_leaves_the_line_green_and_affecting_you_empty(self):
        items, r = water([report("supply", "Low pressure", 6)])
        aff, rows = agree(self, items, {"water": r})
        self.assertEqual((aff["yours"], rows["water"]["state"]), ([], "good"))
        self.assertEqual(len(aff["near"]), 1)

    def test_only_the_practical_sources_and_worst_first(self):
        items = [
            {"source": "floods", "kind": "flood", "severity": 1, "level": "Flood alert", "title": "Flood alert: Tidal Thames",
             "text": "Flooding is possible. Be prepared.", "distance_km": 3, "issued": server.iso_utc(NOW)},
            {"source": "metoffice", "kind": "weather", "severity": 2, "level": "Amber", "title": "Amber warning of wind",
             "text": "Strong winds. Delays likely.", "when": "06:00 Sat to 21:00 Sat"},
            {"source": "pound", "kind": "money", "severity": 1, "level": "The pound", "title": "The pound fell 3%", "text": ""},
            {"source": "govalerts", "kind": "alert", "severity": 1, "level": "Test", "title": "A test alert", "text": ""},
            {"source": "ukhsa", "kind": "news", "severity": 0, "level": "News", "title": "Health news", "text": ""},
        ]
        aff = server.affecting(items, {})
        self.assertEqual([x["source"] for x in aff["yours"]], ["metoffice", "floods"])
        self.assertEqual(aff["yours"][0]["key"], "")   # not a live line: it opens the warning itself
        self.assertEqual(aff["yours"][0]["i"], 1)
        self.assertEqual(aff["yours"][0]["when"], "06:00 Sat to 21:00 Sat")
        self.assertEqual(aff["yours"][1]["detail"], "Flooding is possible")

    def test_nothing_affecting_you(self):
        aff = server.affecting([], {})
        self.assertEqual(aff, {"yours": [], "near": [], "near_count": 0})

    def test_the_app_gets_it_with_the_warnings(self):
        items, r = power()
        with server.WARN_LOCK:
            server.WARN_STATE.update({"items": items, "live": {"power": dict(r, checked_at=server.now_iso(), credit="")}})
        server.api_warnings_set({"on": True, "lat": HOME["lat"], "lon": HOME["lon"],
                                 "sources": {k: k == "power" for k, _, _ in server.WARN_SOURCES}}, {})
        w = server.warn_public()
        self.assertEqual([x["source"] for x in w["affecting"]["yours"]], ["power"])
        self.assertEqual(w["live_layout"]["attention"], ["power"])
        mine = w["affecting"]["yours"][0]
        self.assertEqual(w["items"][mine["i"]]["source"], "power")


class NearDistanceTest(AppTest):
    def test_default_and_limits(self):
        self.assertEqual(server.warn_cfg()["near_km"], 10)
        server.api_warnings_set({"near_km": 25}, {})
        self.assertEqual(server.warn_cfg()["near_km"], 25)
        for bad in (4, 41, -10, "far", True, 7.5):
            with self.assertRaises(server.ApiError, msg=repr(bad)):
                server.api_warnings_set({"near_km": bad}, {})
        self.assertEqual(server.warn_cfg()["near_km"], 25)
        with server.tx() as db:   # something odd saved by hand is brought back into range
            server.set_setting_raw(db, "warnings", {"near_km": 400})
        self.assertEqual(server.warn_cfg()["near_km"], server.NEAR_KM_MAX)

    def test_it_widens_whats_nearby_but_not_whats_yours(self):
        items, r = power(km=20)
        aff, rows = agree(self, items, {"power": r})
        self.assertEqual([x["distance_km"] for x in aff["near"]], [6.0, 15.0])
        self.assertEqual([x["distance_km"] for x in aff["yours"]], [1])   # still only within 2 km
        self.assertIn("within 20 km", rows["power"]["text"])
        items, r = water([report("supply", "Low pressure", 15)], km=20)
        self.assertEqual((items, len(server.affecting(items, {"water": r})["near"])), ([], 1))
        self.assertIn("within 20 km", server.live_rows({"water": r}, [])[0]["text"])

    def test_the_setting_reaches_the_power_cuts_and_fetches_again(self):
        feeds = FakeFeeds({"ukpn": (lambda: ukpn(*CUTS), "application/json")})
        try:
            for k, _, _ in server.POWER_FEEDS:
                server.FEED_URLS[k] = ""
            server.FEED_URLS["power_ukpn"] = feeds.base + "ukpn"
            server.api_warnings_set({"on": True, "lat": HOME["lat"], "lon": HOME["lon"],
                                     "sources": {k: k == "power" for k, _, _ in server.WARN_SOURCES}}, {})
            server.warnings_run()
            w = server.warn_public()
            self.assertEqual([x["distance_km"] for x in w["affecting"]["near"]], [6.0])
            server.api_warnings_set({"near_km": 20}, {})
            server.warnings_run()   # within the 14 minutes it'd usually wait: a new distance doesn't wait
            w = server.warn_public()
            self.assertEqual([x["distance_km"] for x in w["affecting"]["near"]], [6.0, 15.0])
            self.assertIn("within 20 km", w["live_rows"][0]["text"])
            self.assertEqual(len([q for q in feeds.log if q["path"].startswith("/ukpn")]), 2)
        finally:
            feeds.close()


class GroupedLayoutTest(AppTest):
    def row(self, key, state="good"):
        return {"key": key, "state": state}

    def test_attention_first_worst_first_then_the_groups(self):
        rows = [self.row(k) for k in server.LIVE_KEYS]
        rows[server.LIVE_KEYS.index("air")]["state"] = "warn"
        rows[server.LIVE_KEYS.index("power")]["state"] = "bad"
        rows[server.LIVE_KEYS.index("threat")]["state"] = "warn"
        lay = server.live_layout(rows)
        self.assertEqual(lay["attention"], ["power", "air", "threat"])
        self.assertEqual([g["name"] for g in lay["groups"]],
                         ["Water and weather", "Power and energy", "Home", "The wider world"])
        self.assertEqual(lay["groups"][2]["keys"], ["water"])   # air needs attention, so it's up top instead
        placed = lay["attention"] + [k for g in lay["groups"] for k in g["keys"]]
        self.assertEqual(sorted(placed), sorted(server.LIVE_KEYS))   # every line once

    def test_nothing_needs_attention(self):
        lay = server.live_layout([self.row("rivers"), self.row("pound")])
        self.assertEqual(lay["attention"], [])
        self.assertEqual([(g["name"], g["keys"]) for g in lay["groups"]],
                         [("Water and weather", ["rivers"]), ("The wider world", ["pound"])])

    def test_a_line_without_a_group_isnt_lost(self):
        lay = server.live_layout([self.row("rivers"), self.row("something_new")])
        self.assertEqual(lay["groups"][-1], {"name": "Other", "keys": ["something_new"]})
