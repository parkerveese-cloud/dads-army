"""1.17.0: trends in the wider picture. A few counts from the live sources are kept a day at a time for two weeks,
and today's is compared with the usual; the charts in each source's details draw them; and four more Home Assistant
sensors (the trends, England's reservoirs, the UK threat level and the pet food)."""
import datetime as dt

from feeds import FakeFeeds
from support import AppServer, AppTest, server
from test_live import HOME, npg, nged, readings, ssen, stations, ukpn

TODAY = dt.date.today()


def seed(metric, past, today=None):
    """past: the counts for the days before today, oldest first; today: today's (or None for no count today)."""
    for n, v in enumerate(reversed(past), 1):
        server.record_counts({metric: v}, TODAY - dt.timedelta(days=n))
    if today is not None:
        server.record_counts({metric: today}, TODAY)


def warnings_on(*sources):
    server.api_warnings_set({"on": True, "sources": {k: k in sources for k, _, _ in server.WARN_SOURCES}}, {})


class TrendRulesTest(AppTest):
    def test_a_rise_on_the_usual_is_a_trend(self):
        seed("power_networks", [40, 38, 42, 40, 41], today=120)
        t = server.find_trends()
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0]["title"], "Power cuts across the networks: 3× the usual")
        self.assertEqual(t[0]["source"], "power")
        self.assertEqual(t[0]["usual"], 40)
        self.assertIn("over the last 5 days", t[0]["text"])

    def test_a_normal_day_isnt(self):
        seed("power_networks", [40, 38, 42, 40, 41], today=60)   # up, but not twice the usual
        self.assertEqual(server.find_trends(), [])

    def test_too_little_history_isnt(self):
        seed("power_networks", [40, 38, 40], today=200)   # three days: not enough to know what's usual
        self.assertEqual(server.find_trends(), [])
        seed("floods_near", [0, 0, 0, 0, 0])   # nothing today: nothing to compare
        self.assertEqual(server.find_trends(), [])

    def test_a_count_too_small_to_matter_isnt(self):
        seed("power_near", [0, 0, 0, 0, 0], today=1)
        self.assertEqual(server.find_trends(), [])
        server.record_counts({"power_near": 3})
        t = server.find_trends()
        self.assertEqual(t[0]["title"], "Power cuts near you: usually none")
        self.assertIsNone(t[0]["ratio"])

    def test_the_days_highest_is_kept(self):
        server.record_counts({"grid": 5})
        server.record_counts({"grid": 2})
        self.assertEqual(server.count_rows()["grid"], {TODAY.isoformat(): 5})

    def test_only_two_weeks_are_kept(self):
        server.record_counts({"grid": 1}, TODAY - dt.timedelta(days=20))
        server.record_counts({"grid": 1}, TODAY - dt.timedelta(days=14))
        server.record_counts({"grid": 3})
        days = [r[0] for r in server.DB.execute("SELECT day FROM live_counts ORDER BY day")]
        self.assertEqual(days, [(TODAY - dt.timedelta(days=14)).isoformat(), TODAY.isoformat()])

    def test_only_sources_that_are_on(self):
        seed("power_networks", [40, 38, 42, 40, 41], today=120)
        seed("rivers_high", [0, 1, 0, 0, 1], today=4)
        self.assertEqual([t["key"] for t in server.find_trends({"rivers"})], ["rivers_high"])
        self.assertEqual(len(server.find_trends()), 2)

    def test_the_counts_from_a_check(self):
        live = {"power": {"count": 2, "networks": 55}, "rivers": {"high": 1}}
        by_src = {"floods": [{}, {}, {}], "fires": [], "grid": [{}]}
        ok = {"ok": True}
        got = server.trend_counts(live, by_src, {"power": ok, "rivers": ok, "floods": ok, "fires": ok, "grid": ok},
                                  {"flood_total": 140})
        self.assertEqual(got, {"power_near": 2, "power_networks": 55, "floods_near": 3, "floods_england": 140,
                               "rivers_high": 1, "fires": 0, "grid": 1})
        # A feed that's down this time isn't a quiet day: it isn't counted at all.
        got = server.trend_counts(live, by_src, {"power": {"ok": False}, "floods": ok}, {})
        self.assertEqual(got, {"floods_near": 3})


class TrendsInTheAppTest(AppTest):
    def test_the_api_the_charts_use(self):
        warnings_on("power", "rivers")
        seed("power_networks", [40, 38, 42, 40], today=120)
        server.record_counts({"rivers_high": 1}, TODAY - dt.timedelta(days=2))
        seed("fires", [1, 2, 3, 4], today=5)   # fires are off: not shown
        out = server.api_live_history({}, {})
        self.assertEqual(out["days"], 15)
        by = dict((m["key"], m) for m in out["metrics"])
        self.assertEqual(sorted(by), ["power_networks", "rivers_high"])
        rows = by["power_networks"]["rows"]
        self.assertEqual(len(rows), 15)
        self.assertEqual(rows[-1], {"day": TODAY.isoformat(), "value": 120})
        self.assertEqual(rows[0]["value"], -1)   # no count that day: a gap in the chart
        self.assertEqual(by["power_networks"]["usual"], 40)
        self.assertIsNone(by["rivers_high"]["usual"])   # one day isn't enough for a usual
        self.assertEqual([t["key"] for t in out["trends"]], ["power_networks"])
        self.assertEqual(len(server.api_live_history({}, {"days": ["7"]})["metrics"][0]["rows"]), 7)

    def test_over_http(self):
        warnings_on("power")
        seed("power_networks", [40, 38, 42, 40], today=120)
        app = AppServer()
        try:
            status, out = app.json("GET", "/api/live/history?days=5")
            self.assertEqual(status, 200)
            self.assertEqual([r["value"] for r in out["metrics"][0]["rows"]], [40, 38, 42, 40, 120])
            self.assertEqual(app.json("GET", "/api/live/history?days=x")[0], 400)
        finally:
            app.close()

    def test_nothing_while_warnings_are_off(self):
        seed("power_networks", [40, 38, 42, 40], today=120)
        self.assertEqual(server.api_live_history({}, {})["metrics"], [])
        self.assertEqual(server.warn_public()["trends"], [])

    def test_a_trend_makes_its_live_line_worth_watching(self):
        warnings_on("power")
        with server.WARN_LOCK:
            server.WARN_STATE["live"] = {"power": {"cuts": [], "count": 0, "planned": 0, "networks": 120, "failed": [],
                                                   "no_feed": ""}}
        row = server.warn_public()["live_rows"][0]
        self.assertEqual((row["state"], row.get("trend")), ("good", None))
        seed("power_networks", [40, 38, 42, 40], today=120)
        row = server.warn_public()["live_rows"][0]
        self.assertEqual(row["state"], "warn")
        self.assertEqual(row["trend"], "Power cuts across the networks: 3× the usual")

    def test_the_briefing_hears_about_it(self):
        warnings_on("power")
        seed("power_networks", [40, 38, 42, 40], today=120)
        self.assertIn("- Trend: Power cuts across the networks: 3× the usual", server.brief_known())


class TrendSensorsTest(AppTest):
    def ents(self):
        return server.ha_entities(server.summary())

    def test_the_trends_sensor(self):
        warnings_on("power", "rivers")
        e = self.ents()["sensor.dads_army_trends"]
        self.assertEqual((e["state"], e["attributes"]["trends"]), ("0", []))
        seed("power_networks", [40, 38, 42, 40], today=120)
        e = self.ents()["sensor.dads_army_trends"]
        self.assertEqual(e["state"], "1")
        self.assertEqual(e["attributes"]["unit_of_measurement"], "trends")
        t = e["attributes"]["trends"][0]
        self.assertEqual(t["title"], "Power cuts across the networks: 3× the usual")
        self.assertEqual((t["value"], t["usual"], t["source"]), (120, 40, "power"))

    def test_reservoirs_and_the_threat_level(self):
        ents = self.ents()
        self.assertNotIn("sensor.dads_army_reservoirs", ents)   # nothing to say yet
        self.assertNotIn("sensor.dads_army_uk_threat_level", ents)
        warnings_on("drought", "threat")
        with server.WARN_LOCK:
            server.WARN_STATE["live"] = {
                "drought": {"storage": 71.5, "vs_average": -9.2, "week": "9 November", "url": "https://www.gov.uk/x",
                            "counts": {}, "area": "Thames", "stage": "Prolonged dry weather", "company": "",
                            "company_text": "", "ban": "", "stale": False},
                "threat": {"level": "SUBSTANTIAL", "means": "an attack is likely", "ni": "SUBSTANTIAL",
                           "raised_on": None, "since": "2026-02-01T00:00:00Z"}}
        ents = self.ents()
        r = ents["sensor.dads_army_reservoirs"]
        self.assertEqual((r["state"], r["attributes"]["unit_of_measurement"]), ("71.5", "%"))
        self.assertEqual(r["attributes"]["vs_average"], -9.2)
        self.assertEqual(r["attributes"]["drought_stage"], "Prolonged dry weather")
        self.assertFalse(r["attributes"]["hosepipe_ban"])
        t = ents["sensor.dads_army_uk_threat_level"]
        self.assertEqual(t["state"], "Substantial")
        self.assertEqual(t["attributes"]["northern_ireland"], "Substantial")
        self.assertIn("Critical", t["attributes"]["options"])
        self.assertNotIn("state_class", t["attributes"])   # a word, not a measurement

    def test_pet_food(self):
        self.assertNotIn("sensor.dads_army_pet_food_days", self.ents())
        server.api_settings({"dogs": 1}, {})
        self.add("Dog food", 3, None, category="pets", unit="bag", per_day=0.15)
        e = self.ents()["sensor.dads_army_pet_food_days"]
        self.assertEqual((e["state"], e["attributes"]["unit_of_measurement"]), ("20", "days"))
        self.assertEqual(e["attributes"]["runs_out_first"], "Dog food")


class ChecksRecordCountsTest(AppTest):
    """A warnings check keeps today's counts, from the feeds it already fetches."""

    def setUp(self):
        super().setUp()
        self.feeds = FakeFeeds({"rivers": (readings, "application/json"), "stations": (stations, "application/json"),
                                "ukpn": (ukpn, "application/json"), "nged": (nged, "text/csv"),
                                "ssen": (ssen, "application/json"), "npg": (npg, "application/json")})
        b = self.feeds.base
        server.FEED_URLS.update(self.feeds.urls())
        server.FEED_URLS.update({"rivers": b + "rivers", "river_stations": b + "stations", "power_ukpn": b + "ukpn",
                                 "power_nged": b + "nged", "power_ssen": b + "ssen", "power_npg": b + "npg"})
        server.api_warnings_set({"on": True, "lat": HOME["lat"], "lon": HOME["lon"],
                                 "sources": {k: k in ("power", "rivers", "floods") for k, _, _ in server.WARN_SOURCES}}, {})

    def tearDown(self):
        self.feeds.close()
        super().tearDown()

    def test_a_check_records_the_counts(self):
        server.warnings_run()
        live = server.warn_public()["live"]
        got = dict((k, v[TODAY.isoformat()]) for k, v in server.count_rows().items())
        self.assertEqual(got["power_near"], live["power"]["count"])
        self.assertEqual(got["power_networks"], live["power"]["networks"])
        self.assertGreater(got["power_networks"], got["power_near"])   # cuts far from home count across the networks
        self.assertEqual(got["rivers_high"], live["rivers"]["high"])
        self.assertGreaterEqual(got["floods_england"], got["floods_near"])
        self.assertNotIn("grid", got)   # switched off
