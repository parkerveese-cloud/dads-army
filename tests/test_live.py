"""Live information: rivers, power cuts, the grid, gas storage, air quality, space weather and the pound.
Each feed is the whole country in one go, so nothing about where you live is sent."""
import datetime as dt
import json

from feeds import FakeFeeds, wider_routes, wider_urls
from support import AppTest, server

HOME = {"lat": 54.486, "lon": -0.615}   # Whitby
NOW = dt.datetime.now(dt.timezone.utc)
EA = "http://environment.data.gov.uk/flood-monitoring/id/measures/"


def stations():
    def st(nid, label, river, lat, lon, high, low, recent):
        return {"notation": nid, "label": label, "riverName": river, "town": "Whitby", "lat": lat, "long": lon,
                "measures": [{"@id": EA + nid + "-level-downstage-i-15_min-mASD", "parameter": "level",
                              "qualifier": "Downstream Stage", "unitName": "mASD"},
                             {"@id": EA + nid + "-level-stage-i-15_min-mASD", "parameter": "level", "qualifier": "Stage",
                              "unitName": "mASD"}],
                "stageScale": {"typicalRangeHigh": high, "typicalRangeLow": low, "highestRecent": {"value": recent}}}
    return json.dumps({"items": [
        st("ESK1", "Sleights", "River Esk", 54.457, -0.665, 1.2, 0.2, 3.0),
        st("ESK2", "Ruswarp", "River Esk", 54.47, -0.63, 1.0, 0.1, 2.0),
        st("FAR", "Putney", "River Thames", 51.46, -0.22, 5.0, 1.0, 6.0),
        dict(st("ODD", "Lists", ["Beck"], [54.48], [-0.6], 1.0, 0.1, 2.0), label=["Lists", "x"])]}).encode()


def readings(esk1=0.5, esk2=1.4):
    when = (NOW - dt.timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return json.dumps({"items": [
        {"measure": EA + "ESK1-level-stage-i-15_min-mASD", "value": esk1, "dateTime": when},
        {"measure": EA + "ESK1-level-downstage-i-15_min-mASD", "value": 9.9, "dateTime": when},
        {"measure": EA + "ESK2-level-stage-i-15_min-mASD", "value": esk2, "dateTime": when},
        {"measure": EA + "FAR-level-stage-i-15_min-mASD", "value": 5.5, "dateTime": when}]}).encode()


def ukpn():
    return json.dumps([
        {"incidentreference": "INCD-1", "powercuttype": "Unplanned", "statusid": 1, "nocustomeraffected": 40,
         "postcodesaffected": "YO21 1", "receiveddate": "2026-11-14T05:30:00", "estimatedrestorationdate": "2026-11-14T23:00:00",
         "geopoint": {"lat": 54.49, "lon": -0.62}},
        {"incidentreference": "INCD-2", "powercuttype": "Restored", "statusid": 5, "geopoint": {"lat": 54.49, "lon": -0.62}},
        {"incidentreference": "INCD-3", "powercuttype": "Unplanned", "statusid": 1, "nocustomeraffected": 9,
         "geopoint": {"lat": 51.5, "lon": -0.1}},
        {"incidentreference": "INCD-4", "powercuttype": "Unplanned", "statusid": 1}]).encode()


def nged():
    return ('"Upload Date","Region","Incident ID","Confirmed Off","Predicted Off","Restored","Status","Planned","Category",'
            '"Resource Status","Start Time","ETR","Voltage","Location Latitude","Location Longitude","Postcodes"\n'
            '"2026-11-14T21:55:00","x","INCD-9","0","5","0","In Progress","true","PLANNED","ONS","%s","","LV","54.52","-0.60","YO21 3AA"\n'
            % (NOW + dt.timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%S")).encode()


def ssen():
    return json.dumps({"faults": [{"reference": "S1", "type": "LV", "location": {"latitude": 50.7, "longitude": -2.0},
                                   "customerCount": 16, "title": "BH18 Area"}]}).encode()


def npg():
    row = {"reference": "INCD-77", "totalconfirmedpowercut": 120, "totalpredictedpowercut": 0, "natureofoutage": "Fault",
           "estimatedtimetillresolution": "2026-11-14T22:00:00+00:00", "loggedtime": "2026-11-14T16:39:00+00:00",
           "postcode": ["YO22  4AA"], "lat": 54.44, "lng": -0.55}
    return json.dumps([row, dict(row, postcode=["YO22  4AB"], lat=54.441)]).encode()


def syswarn(kind="ELECTRICITY MARGIN NOTICE", cancel=False):
    start = NOW - dt.timedelta(hours=1)
    local = dt.datetime.now() + dt.timedelta(hours=2)
    text = ("From : Power System Manager – NESO Electricity Control Centre\\r\\n\\r\\nELECTRICITY MARGIN NOTICE \\r\\n"
            "For the period:\\r\\nfrom %s hrs to %s hrs on Wednesday %s \\r\\nThere is a reduced system margin."
            % ((local - dt.timedelta(hours=3)).strftime("%H:%M"), local.strftime("%H:%M"), local.strftime("%d/%m/%Y")))
    rows = [{"publishTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "warningType": kind, "warningText": text},
            {"publishTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "warningType": "OTHER",
             "warningText": "NATIONAL GRID NOTIFICATION - DEMAND CONTROL BY VR TEST"},
            {"publishTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "warningType": "SO-SO TRADES", "warningText": "prices"}]
    if cancel:
        rows.append({"publishTime": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "warningType": kind,
                     "warningText": "ELECTRICITY MARGIN NOTICE NOTIFICATION CANCELLATION"})
    return json.dumps(rows).encode()


def gas_csv(end, pct_now, draw):
    """A National Gas CSV: 21 days ending on end, so full that it's pct_now, drawn down by draw GWh a day."""
    total = 35000.0
    lines = ["Applicable At,Applicable For,Data Item,Value,Generated Time,Quality Indicator"]
    for i in range(21):
        day = end - dt.timedelta(days=i)
        stock = total * pct_now / 100 + draw * i
        d = day.strftime("%d/%m/%Y")
        lines.append('%s 15:30:00,%s,"Storage, Daily Aggregated Stock level, D+1",%d,x,L' % (d, d, stock * 1e6))
        lines.append('%s 15:30:00,%s,"Storage, Daily Aggregated Available Capacity, D+1",%d,x,L' % (d, d, (total - stock) * 1e6))
    return "\n".join(lines).encode()


AIR_SITES = ('<?xml version="1.0"?><rss version="2.0"><channel>'
             '<item><title>High Muffles</title><description><![CDATA[Location: 54&deg;20&acute;4.32&quot;N    0&deg;48&acute;28.08&quot;W '
             '<br />Current Pollution level is High at index 8]]></description><pubDate>x</pubDate></item>'
             '<item><title>Far Away</title><description><![CDATA[Location: 50&deg;20&acute;4.32&quot;N    4&deg;48&acute;28.08&quot;W '
             '<br />Current Pollution level is Low at index 1]]></description></item></channel></rss>').encode()


def air_forecast():
    today = dt.date.today()
    days = " ".join("%s: %d" % ((today + dt.timedelta(days=i)).strftime("%a"), n) for i, n in enumerate([3, 7, 2, 2, 2]))
    return ('<?xml version="1.0"?><rss version="2.0"><channel><item><title>WHITBY</title><description><![CDATA['
            'Location: 54&deg;29&acute;10.00&quot;N    0&deg;36&acute;54.00&quot;W <br />index levels are forecast to be  <br />'
            '%s ]]></description></item></channel></rss>' % days).encode()


def scales(g_now="0", g_next="4"):
    def day(g):
        return {"R": {"Scale": None}, "S": {"Scale": None}, "G": {"Scale": g, "Text": "x"}}
    return json.dumps({"-1": day("0"), "0": day(g_now), "1": day(g_next), "2": day("0"), "3": day(None)}).encode()


def boe(drop=0.0):
    rows = ["DATE,XUDLUSS,XUDLERS,IUDBEDR"]
    d = dt.date.today() - dt.timedelta(days=30)
    usd = 1.34
    while d <= dt.date.today():
        if d.weekday() < 5:
            late = d > dt.date.today() - dt.timedelta(days=7)
            rows.append("%s,%s,%s,%s" % (d.strftime("%d %b %Y"), round(usd * (1 - drop) if late else usd, 4), 1.2,
                                         "4" if d > dt.date.today() - dt.timedelta(days=10) else "3.75"))
        d += dt.timedelta(days=1)
    return "\n".join(rows).encode()


class ParseTest(AppTest):
    def test_degrees_minutes_seconds(self):
        lat, lon = server.dms("Location: 55&deg;47&acute;31.78&quot;N    3&deg;14&acute;34.44&quot;W <br />")
        self.assertAlmostEqual(lat, 55.7922, places=3)
        self.assertAlmostEqual(lon, -3.2429, places=3)
        self.assertIsNone(server.dms("nowhere"))

    def test_rivers(self):
        st = server.parse_river_stations(stations(), HOME)
        self.assertEqual(sorted(s["id"] for s in st), ["ESK1", "ESK2", "ODD"])
        esk = [s for s in st if s["id"] == "ESK1"][0]
        self.assertTrue(esk["measure"].endswith("ESK1-level-stage-i-15_min-mASD"))
        items, r = server.rivers_live(st, server.parse_river_readings(readings()), {}, HOME, NOW)
        self.assertEqual([x["id"] for x in r["stations"]], ["ESK2", "ESK1"])
        self.assertEqual([x["state"] for x in r["stations"]], ["high", "normal"])
        self.assertEqual(r["stations"][1]["pct"], 30)
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["severity"], items[0]["kind"]), (1, "river"))
        self.assertIn("River Esk at Ruswarp", items[0]["title"])

    def test_a_rising_river(self):
        st = server.parse_river_stations(stations(), HOME)
        hist = {"ESK2": [[server.time.time() - 3 * 3600, 1.1]]}
        items, r = server.rivers_live(st, server.parse_river_readings(readings(esk2=2.5)), hist, HOME, NOW)
        esk2 = [x for x in r["stations"] if x["id"] == "ESK2"][0]
        self.assertEqual((esk2["state"], esk2["trend"]), ("very_high", "rising"))
        self.assertEqual(items[0]["severity"], 2)
        self.assertTrue(items[0]["title"].endswith("and rising"))

    def test_power_cuts_from_four_networks(self):
        cuts = (server.parse_ukpn(ukpn()) + server.parse_nged(nged(), NOW) + server.parse_ssen(ssen())
                + server.parse_npg(npg()))
        self.assertEqual(sorted(c["ref"] for c in cuts), ["INCD-1", "INCD-3", "INCD-77", "INCD-9", "S1"])
        items, r = server.power_live(cuts, HOME)
        self.assertEqual((r["count"], r["planned"], r["near"]), (2, 1, 1))
        self.assertEqual(r["homes"], 160)
        near = [i for i in items if i["severity"] == 2]
        self.assertEqual(len(near), 1)
        self.assertIn("Power cut", near[0]["title"])
        self.assertIn("105", near[0]["text"])

    def test_grid_notices(self):
        items, r = server.parse_grid(syswarn(), NOW)
        self.assertEqual(r["status"], "notice")
        self.assertEqual([i["severity"] for i in items], [1])
        self.assertIn("margin notice", items[0]["title"].lower())
        items, r = server.parse_grid(syswarn(cancel=True), NOW)
        self.assertEqual((items, r["status"]), ([], "normal"))

    def test_gas_storage_trend(self):
        today = dt.date.today()
        now = server.parse_gas(gas_csv(today, 25, 150))
        year_ago = server.parse_gas(gas_csv(today.replace(year=today.year - 1), 48, 40))
        items, r = server.gas_live(now, year_ago, today)
        self.assertEqual((round(r["pct"]), round(r["year_ago_pct"]), r["trend"]), (25, 48, "emptying"))
        self.assertEqual(round(r["draw_gwh_day"]), 150)
        self.assertTrue([i for i in items if "faster than this time last year" in i["title"]])
        items, r = server.gas_live(server.parse_gas(gas_csv(today, 50, 30)), year_ago, today)
        self.assertEqual(items, [])

    def test_air_quality(self):
        sites = server.parse_air_sites(AIR_SITES)
        fc = server.parse_air_forecast(air_forecast(), HOME)
        self.assertEqual(fc["place"], "Whitby")
        items, r = server.air_live(sites, fc, HOME, NOW)
        self.assertEqual((r["site"], r["index"], r["band"]), ("High Muffles", 8, "High"))
        self.assertEqual([f["index"] for f in r["forecast"]], [3, 7, 2])
        self.assertEqual(len(items), 1)
        self.assertIn("index 8", items[0]["title"])

    def test_space_weather(self):
        items, r = server.parse_space(scales(), NOW)
        self.assertEqual((r["g_now"], r["g_next"]), (0, 4))
        self.assertEqual([i["severity"] for i in items], [1])
        items, r = server.parse_space(scales("1", "2"), NOW)
        self.assertEqual((items, r["text"]), ([], "Minor storm (G1)"))

    def test_the_pound(self):
        items, r = server.pound_live(server.parse_pound(boe()), NOW)
        self.assertEqual((r["usd"], r["rate"]), (1.34, 4.0))
        self.assertEqual([i["kind"] for i in items], ["news"])        # Bank Rate went up: news, not a warning
        items, r = server.pound_live(server.parse_pound(boe(drop=0.04)), NOW)
        self.assertLessEqual(r["usd_week"], -3.9)
        self.assertTrue([i for i in items if i["kind"] == "money" and "fallen" in i["title"]])


class LiveRunTest(AppTest):
    def setUp(self):
        super().setUp()
        today = dt.date.today()
        self.fc = {"ly": False}

        def gas():   # this year's figures, or last year's (the request says which dates)
            if ("from=%d-" % today.year) in self.feeds.log[-1]["path"]:
                return gas_csv(today, 25, 150)
            return gas_csv(today.replace(year=today.year - 1), 48, 40)
        self.feeds = FakeFeeds({
            "rivers": (readings, "application/json"), "stations": (stations, "application/json"),
            "ukpn": (ukpn, "application/json"), "nged": (nged, "text/csv"), "ssen": (ssen, "application/json"),
            "npg": (npg, "application/json"), "grid": (syswarn, "application/json"), "gas": (gas, "text/csv"),
            "air": (lambda: AIR_SITES, "application/xml"), "airfc": (air_forecast, "application/xml"),
            "space": (scales, "application/json"), "pound": (boe, "text/csv"), **wider_routes()})
        b = self.feeds.base
        server.FEED_URLS.update(self.feeds.urls())
        server.FEED_URLS.update({"rivers": b + "rivers", "river_stations": b + "stations", "power_ukpn": b + "ukpn",
                                 "power_nged": b + "nged", "power_ssen": b + "ssen", "power_npg": b + "npg",
                                 "grid": b + "grid?from={start}&to={end}", "gas": b + "gas?from={start}&to={end}",
                                 "air": b + "air", "air_forecast": b + "airfc", "space": b + "space",
                                 "pound": b + "pound?from={start}"})
        server.FEED_URLS.update(wider_urls(b))   # 1.15.0's sources
        server.api_warnings_set({"on": True, "lat": HOME["lat"], "lon": HOME["lon"], "nh_key": "k" * 32,   # 1.20.0's roads
                                 "sources": {k: True for k in server.LIVE_KEYS}}, {})

    def tearDown(self):
        self.feeds.close()
        super().tearDown()

    def test_all_seven_come_through(self):
        server.warnings_run()
        w = server.warn_public()
        # Water supply needs your water company choosing (it isn't guessed), so not yet; and Whitby isn't on UK Power
        # Networks' network, so there's no "Your power supply" (1.21.0).
        self.assertEqual([r["key"] for r in w["live_rows"]], [k for k in server.LIVE_KEYS if k not in ("water", "supply")])
        self.assertEqual(w["unavailable"], {"water": server.WATER_CHOOSE, "supply": server.UKPN_ONLY})
        bad = dict((k, v) for k, v in w["sources"].items() if not v["ok"])
        self.assertEqual(bad, {})
        rows = dict((r["key"], r) for r in w["live_rows"])
        self.assertEqual(rows["power"]["state"], "bad")
        self.assertEqual(rows["rivers"]["state"], "warn")
        self.assertIn("% full", rows["gas"]["text"])
        self.assertTrue(rows["pound"]["text"].startswith("$1.34"))
        kinds = set(i["kind"] for i in w["items"])
        self.assertTrue({"river", "power", "grid", "gas", "air", "space"} <= kinds, kinds)
        self.assertTrue([n for n in w["news"] if n["source"] == "pound"])

    def test_they_count_towards_the_alert_level(self):
        server.warnings_run()
        sit = server.summary()["situation"]
        keys = set(r["key"] for r in sit["reasons"])
        self.assertTrue({"power_cut_near", "river_high", "poor_air", "space_storm"} <= keys, keys)

    def test_where_you_live_is_never_sent(self):
        server.warnings_run()
        self.assertTrue(len(self.feeds.log) >= 12)
        for req in self.feeds.log:
            for needle in ("54.4", "54.5", "0.61", "0.62", "lat=", "lon=", "yo21", "whitby"):
                self.assertNotIn(needle, req["path"].lower(), req["path"])
            self.assertEqual(req["headers"].get("Accept-Encoding"), "gzip")

    def test_slow_feeds_arent_fetched_every_time(self):
        server.warnings_run()
        n = len([r for r in self.feeds.log if r["path"].startswith("/gas")])
        server.warnings_run()
        self.assertEqual(len([r for r in self.feeds.log if r["path"].startswith("/gas")]), n)
        self.assertEqual(len([r for r in self.feeds.log if r["path"].startswith("/stations")]), 1)
        self.assertTrue(server.warn_public()["live"]["gas"]["pct"])

    def test_one_network_down_doesnt_hide_the_others(self):
        self.feeds.broken["ukpn"] = 503
        server.warnings_run()
        w = server.warn_public()
        self.assertTrue(w["sources"]["power"]["ok"])
        self.assertEqual(w["live"]["power"]["count"], 1)    # Northern Powergrid's

    def test_switched_off_means_gone(self):
        server.warnings_run()
        server.api_warnings_set({"sources": {"pound": False}}, {})
        server.warnings_run()
        w = server.warn_public()
        self.assertNotIn("pound", w["live"])
        self.assertNotIn("pound", [r["key"] for r in w["live_rows"]])

    def test_home_assistant_gets_the_wider_picture(self):
        server.warnings_run()
        ents = server.ha_entities(server.summary())
        live = ents["sensor.dads_army_live"]
        self.assertEqual(len(live["attributes"]["rows"]), len(server.LIVE_KEYS) - 2)   # all but water and power supply
        self.assertGreaterEqual(int(live["state"]), 4)
        self.assertIn("sensor.dads_army_live", json.dumps(server.dashboard_config()))
