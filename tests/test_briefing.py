"""The daily briefing (1.15.0) and the sources it reads: the threat level, NCSC, FCDO, drought, the five-day flood
risk, rain, groundwater, the grid and water supply. No internet and no real AI: the Messages API and the feeds are
stood in for."""
import datetime as dt
import json

import feeds
from support import AppTest, server

NOW = dt.datetime.now(dt.timezone.utc)
LONDON = {"lat": 51.507, "lon": -0.128}
BURTON = {"lat": 52.80, "lon": -1.64}      # South Staffs Water
DEVON = {"lat": 50.72, "lon": -3.53}       # Exeter: neither company

REPLY = ("BRIEFING: Overnight things are quiet near home, with a yellow wind warning for the coast tomorrow, so it's worth "
         "charging power banks. Across the UK the terrorism threat level is unchanged at substantial and the NCSC has "
         "warned about a flaw in a common router, so check for updates. Abroad, fighting continues in the usual places "
         "with nothing new that touches the UK directly, and energy prices are steady.\n"
         "HEADLINE: Wind warning tomorrow; router security update advised\n"
         "LEVELS: local=2 national=3 global=3\n"
         "VS_USUAL: local=higher national=same global=same\n"
         "SOURCES: https://www.bbc.co.uk/news/y, https://made.up/page")


def answer(content, stop="end_turn", searches=0):
    return {"content": content, "stop_reason": stop,
            "usage": {"input_tokens": 1000, "output_tokens": 200, "server_tool_use": {"web_search_requests": searches}}}


class BriefingTest(AppTest):
    def setUp(self):
        super().setUp()
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "anthropic", "keys": {"anthropic": "test-key"}})
        server.BRIEF.update(busy=False, error="", day="", tries=0, last_try=0.0)
        self.real_post = server._post_json
        self.calls = []

    def tearDown(self):
        server._post_json = self.real_post
        super().tearDown()

    def fake(self, answers):
        def post(url, body, headers, timeout=60):
            self.calls.append(body)
            return answers.pop(0)
        server._post_json = post

    def test_reading_the_reply(self):
        got = server.parse_brief_reply(REPLY)
        self.assertTrue(got["text"].startswith("Overnight things are quiet"))
        self.assertNotIn("HEADLINE", got["text"])
        self.assertEqual(got["levels"], {"local": 2, "national": 3, "global": 3})
        self.assertEqual(got["vs_usual"]["local"], "higher")
        self.assertIn("Wind warning", got["headline"])
        self.assertEqual(got["source_urls"], ["https://www.bbc.co.uk/news/y", "https://made.up/page"])
        with self.assertRaises(ValueError):
            server.parse_brief_reply("I couldn't find anything.")

    def test_writing_one(self):
        """Follows pause_turn, keeps only the writing after the last search, counts the searches' cost, and lists
        only sources that really came back from the searches."""
        self.fake([
            answer([{"type": "server_tool_use", "input": {"query": "London news today"}},
                    {"type": "web_search_tool_result", "content": [
                        {"type": "web_search_result", "url": "https://www.bbc.co.uk/news/y", "title": "BBC story"}]},
                    {"type": "text", "text": "Let me look further."}], stop="pause_turn", searches=3),
            answer([{"type": "server_tool_use", "input": {"query": "UK cyber news"}},
                    {"type": "web_search_tool_result", "content": [
                        {"type": "web_search_result", "url": "https://www.ncsc.gov.uk/news/z", "title": "NCSC alert"}]},
                    {"type": "text", "text": REPLY, "citations": [{"url": "https://www.ncsc.gov.uk/news/z", "title": "NCSC alert"}]}],
                   searches=2)])
        with server.tx() as db:
            server.set_setting_raw(db, "briefing", {"on": True, "area": "Greenwich"})
        b = server.make_briefing("test")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[1]["messages"][1]["role"], "assistant")   # pause_turn: sent back to carry on
        self.assertEqual(self.calls[0]["tools"][0]["type"], "web_search_20250305")
        self.assertIn("Greenwich", self.calls[0]["messages"][0]["content"])
        self.assertEqual(b["searches"], 5)
        urls = [x["url"] for x in b["sources"]]
        self.assertEqual(urls, ["https://www.ncsc.gov.uk/news/z", "https://www.bbc.co.uk/news/y"])   # not made.up
        self.assertEqual(b["searched"], ["London news today", "UK cyber news"])
        # Haiku: 2000 in, 400 out, plus 5 searches at a cent each
        self.assertAlmostEqual(b["cost_usd"], 2000 * 0.10 / 1e6 + 400 * 0.50 / 1e6 + 0.05, places=6)
        self.assertEqual(server.ai_stats()["tasks"]["briefing"], 1)
        self.assertEqual(server.brief_public()["latest"]["headline"], b["headline"])

    def test_the_baseline(self):
        past = [{"day": "2026-01-0%d" % d, "levels": {"local": 2, "national": 3, "global": 3}, "text": "Day %d" % d}
                for d in range(1, 5)]
        text = server.brief_baseline(past, "2026-01-04")
        self.assertIn("2026-01-03: local 2, national 3, global 3", text)
        self.assertNotIn("2026-01-04", text)
        self.assertIn("Yesterday's briefing said: Day 3", text)
        self.assertIn("No earlier briefings", server.brief_baseline([], "2026-01-04"))

    def test_when_its_due(self):
        c = {"on": True, "model": "claude-haiku-5-5", "area": ""}
        self.assertFalse(server.brief_due(c, dt.datetime(2026, 1, 5, 5, 59)))
        self.assertTrue(server.brief_due(c, dt.datetime(2026, 1, 5, 6, 1)))
        self.assertFalse(server.brief_due(dict(c, on=False), dt.datetime(2026, 1, 5, 7)))
        server.BRIEF["last_try"] = __import__("time").time()
        self.assertFalse(server.brief_due(c, dt.datetime(2026, 1, 5, 7)))   # 20 minutes between tries

    def test_needs_an_anthropic_key(self):
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "ha"})
        with self.assertRaises(server.ApiError) as e:
            server.api_briefing_put({"on": True}, {})
        self.assertEqual(e.exception.status, 400)
        self.assertFalse(server.brief_public()["available"])
        self.assertFalse(server.brief_due({"on": True, "model": "claude-haiku-5-5", "area": ""}, dt.datetime(2026, 1, 5, 7)))

    def test_a_refused_key_switches_it_off(self):
        def post(url, body, headers, timeout=60):
            raise IOError("HTTP 401: invalid x-api-key")
        server._post_json = post
        with server.tx() as db:
            server.set_setting_raw(db, "briefing", {"on": True})
        with self.assertRaises(server.ApiError):
            server.make_briefing()
        self.assertFalse(server.brief_cfg()["on"])
        self.assertIn("switched off", server.BRIEF["error"])

    def test_the_monthly_limit(self):
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "anthropic", "keys": {"anthropic": "test-key"}, "limit_usd": 0.01})
            server.set_setting_raw(db, "briefing", {"on": True})
        server.record_ai("anthropic", "claude-haiku-5-5", "Dads Army label", {"in": 1, "out": 1}, True, extra_usd=0.02)
        self.fake([])
        with self.assertRaises(server.ApiError) as e:
            server.make_briefing()
        self.assertEqual(e.exception.status, 402)
        self.assertEqual(self.calls, [])

    def test_what_it_knows(self):
        server.api_warnings_set({"on": True}, {})
        with server.WARN_LOCK:
            server.WARN_STATE.update({"items": [{"id": "x", "source": "metoffice", "kind": "weather", "severity": 1,
                                                 "level": "Yellow", "title": "Yellow warning of wind"}],
                                      "live": {"threat": {"level": "SUBSTANTIAL", "means": "an attack is likely", "ni": None,
                                                          "raised_on": None}}})
        known = server.brief_known()
        self.assertIn("Warning (Met Office): Yellow warning of wind, Yellow", known)
        self.assertIn("Threat level: Substantial", known)
        self.assertIn("The household's stores: food for", known)

    def test_the_area(self):
        self.assertEqual(server.brief_area({"area": "Greenwich"}), "Greenwich")
        server.api_warnings_set({"on": True, "lat": LONDON["lat"], "lon": LONDON["lon"]}, {})
        self.assertEqual(server.brief_area({"area": ""}), "London & South East England")
        server.api_warnings_set({"region": "wl"}, {})
        self.assertEqual(server.brief_area({"area": ""}), "Wales")

    def test_home_assistant_sensor_and_routes(self):
        with server.tx() as db:
            server.set_setting_raw(db, "briefing", {"on": True})
            server.set_setting_raw(db, "briefings", [{"day": "2026-01-05", "text": "All quiet.", "headline": "All quiet",
                                                      "levels": {"local": 1, "national": 2, "global": 2}, "sources": []}])
        self.assertEqual(server.api_briefing({}, {})["latest"]["headline"], "All quiet")
        self.assertIn("briefing", server.api_state({}, {}))
        self.assertIn(("GET", "/api/briefing"), [(r[0], r[1].pattern.strip("^$")) for r in server.ROUTES])


class SourcesTest(AppTest):
    """The parsers, with small stand-in feeds."""

    def test_threat_level(self):
        level, ni = server.parse_threat(feeds.threat())   # GOV.UK's guide (MI5's feed is behind a bot check)
        self.assertEqual((level, ni), ("SUBSTANTIAL", "SUBSTANTIAL"))
        since = None
        items, r = server.threat_live(level, ni, since, {}, NOW)
        self.assertEqual(items, [])
        items, r2 = server.threat_live("SEVERE", ni, since, r, NOW)   # raised
        self.assertEqual(items[0]["severity"], 1)
        self.assertIn("raised to SEVERE", items[0]["title"])
        items, _ = server.threat_live("SEVERE", ni, since, r2, NOW + dt.timedelta(days=8))   # a week on: no longer news
        self.assertEqual(items, [])
        items, _ = server.threat_live("CRITICAL", ni, since, r2, NOW)
        self.assertEqual(items[0]["severity"], 3)
        self.assertEqual(items[0]["url"], "https://www.gov.uk/terrorism-national-emergency/terrorism-threat-levels")
        with self.assertRaises(ValueError):
            server.parse_threat(b'{"details": {"parts": [{"slug": "terrorism-threat-levels", "body": "<p>Moved.</p>"}]}}')

    def test_threat_level_since(self):
        """GOV.UK doesn't date the level: it's dated when Dads Army sees it change."""
        server.FEED_URLS["threat"] = "stand-in"
        server.http_get = lambda url, **kw: feeds.threat()
        mem = {"live": {}}
        items, r = server.fetch_live("threat", server.warn_cfg(), None, mem, NOW)
        self.assertEqual((r["level"], r["since"]), ("SUBSTANTIAL", ""))   # first look: not known
        mem["live"]["threat"] = dict(r, level="MODERATE")
        items, r = server.fetch_live("threat", server.warn_cfg(), None, mem, NOW)
        self.assertEqual(r["since"], server.iso_utc(NOW))                  # it went up today
        self.assertIn("raised to SUBSTANTIAL", items[0]["title"])
        mem["live"]["threat"] = r
        later = NOW + dt.timedelta(days=1)
        self.assertEqual(server.fetch_live("threat", server.warn_cfg(), None, mem, later)[1]["since"], server.iso_utc(NOW))

    def test_ncsc(self):
        news = server.parse_ncsc(feeds.ncsc(), NOW)
        self.assertEqual(len(news), 2)   # the 40-day-old one is left out
        self.assertTrue(news[0]["urgent"] and not news[1]["urgent"])
        self.assertTrue(all(n["url"].startswith("https://www.ncsc.gov.uk/") for n in news))
        items, r = server.cyber_live(news, NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(r["urgent"], 1)

    def test_fcdo(self):
        changes = server.parse_fcdo(feeds.fcdo(), NOW)
        self.assertEqual([c["country"] for c in changes], ["Ruritania", "Freedonia"])
        self.assertTrue(changes[0]["against"] and not changes[1]["against"])
        self.assertEqual(server.travel_live(changes)[1]["against"], ["Ruritania"])

    def test_drought(self):
        rep = server.parse_drought_report(feeds.DROUGHT_BODY)
        self.assertEqual(rep["storage"], 61.5)
        self.assertEqual(rep["vs_average"], -12.3)
        self.assertEqual(rep["stages"]["Drought"], ["East Anglia", "Thames"])
        when = (NOW - dt.timedelta(days=4)).date()
        items, r = server.drought_live(rep, when, "https://www.gov.uk/x", {"ea_area": "Thames", "water_co": "Thames Water"}, NOW)
        self.assertEqual(r["stage"], "Drought")
        self.assertEqual(sorted(i["title"] for i in items), ["Drought in Thames", "Hosepipe ban: Thames Water"])
        items, r = server.drought_live(rep, when, "", {"ea_area": "Yorkshire"}, NOW)
        self.assertEqual((items, r["stage"]), ([], "Normal"))
        self.assertEqual(server._report_date("Dry weather and drought in England, 30 October to 5 November 2026"),
                         dt.date(2026, 11, 5))

    def test_flood_risk(self):
        whitby = {"lat": 54.486, "lon": -0.615}
        items, r = server.floodrisk_live(feeds.floodrisk(), feeds.floodrisk_areas(), whitby)
        self.assertEqual((r["risk"], r["rising"], r["days"]), ("MEDIUM", True, 5))   # low today, medium from tomorrow
        tomorrow = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).strftime("%A")
        self.assertEqual((items[0]["severity"], items[0]["title"]), (1, "Flood risk medium where you live on " + tomorrow))
        self.assertEqual(r["text"], "River flooding is possible in the north east & Yorkshire.")
        items, r = server.floodrisk_live(feeds.floodrisk(), feeds.floodrisk_areas(), LONDON)   # in no area at risk
        self.assertEqual((items, r["risk"]), ([], "VERY LOW"))
        for bad in (b"null", b"[]", b'{"features": 3}'):
            with self.assertRaises(ValueError):
                server.floodrisk_live(feeds.floodrisk(), bad, LONDON)

    def test_rain(self):
        rows = [(r["dateTime"], r["value"]) for r in json.loads(feeds.rain())["items"]]
        day, week = server.rain_totals(rows, NOW)
        self.assertEqual((day, week), (33.0, 38.0))
        items, r = server.rain_live([(2.0, "Near gauge", day, week, "Environment Agency", "R1")], NOW)
        self.assertEqual((r["day_mm"], items[0]["severity"]), (33.0, 1))
        # The nearest gauge's own page (check-for-flooding's /rainfall page is gone)
        self.assertEqual(items[0]["url"], "https://check-for-flooding.service.gov.uk/rainfall-station/R1")

    def test_groundwater(self):
        got = server.gw_status(json.loads(feeds.gw())["items"], NOW.date())
        self.assertIsNotNone(got)
        self.assertEqual(got[2], 0)   # lower than every reading at this time of year
        self.assertIsNone(server.gw_status([{"date": "2010-01-01", "value": 1}], NOW.date()))

    def test_grid(self):
        cur = json.loads(feeds.ci())["data"][0]
        items, r = server.gridnow_live(cur, json.loads(feeds.cimix())["data"]["generationmix"], [50.01, 49.75], NOW)
        self.assertEqual(r["ci"], 140)
        self.assertEqual([m["fuel"] for m in r["mix"]], ["wind", "gas"])
        self.assertEqual(items[0]["severity"], 1)
        self.assertEqual(server.frequency_check(49.4, 50.0)[0], 2)
        items, r = server.gridstress_live(json.loads(feeds.margin())["data"], json.loads(feeds.margind())["data"],
                                          server.dfs_events(json.loads(feeds.dfs())["result"]["records"], NOW.date()), NOW)
        self.assertEqual((r["margin_mw"], items[0]["severity"]), (2500, 1))
        self.assertEqual(r["dfs"][0]["from"] + "-" + r["dfs"][0]["to"], "17:00-18:00")   # joined into one event

    def test_water_supply(self):
        data = json.loads(feeds.water())
        data["features"][0]["attributes"]["Region__c"] = "S"
        data["features"][0]["geometry"] = {"x": -1.637, "y": 52.805}   # 600 m from BURTON
        reports = server.aptumo_reports(json.dumps(data).encode(), "S")
        items, r = server.water_live(reports, "South Staffs Water", BURTON, NOW)
        self.assertEqual(items[0]["severity"], 2)    # no water, under 1 km away
        self.assertEqual(r["supply"], 1)
        self.assertEqual(server.aptumo_reports(feeds.water(), "S"), [])   # Cambridge Water's report isn't South Staffs'
        with self.assertRaises(ValueError):
            server.aptumo_reports(b'{"error": {"message": "Token required"}}', "S")


class CoverageTest(AppTest):
    """Water supply only covers six water companies' customers, once you've said which is yours. (The nations' and
    networks' coverage is in test_regional.)"""

    def test_water_companies(self):
        cov = server.water_coverage
        self.assertEqual(cov({}, None), (False, "Needs your home location"))
        self.assertEqual(cov({}, BURTON), (False, server.WATER_CHOOSE))   # not guessed: choose it in the settings
        self.assertEqual(cov({}, LONDON), (False, server.WATER_CHOOSE))
        self.assertEqual(cov({"water_co": "South Staffs Water"}, BURTON), (True, ""))
        self.assertEqual(cov({"water_co": "South West Water"}, DEVON), (True, ""))
        self.assertEqual(cov({"water_co": "Thames Water"}, LONDON), (False, server.WATER_ONLY))   # no feed of its own
        self.assertIn("Yorkshire Water", server.WATER_ONLY)

    def test_everything_else_covers_everyone(self):
        for k in server.LIVE_KEYS:
            if k != "water":
                self.assertEqual(server.source_covers(k, {}, DEVON), (True, ""), k)
                self.assertEqual(server.source_covers(k, {}, None), (True, ""), k)

    def test_out_of_area_isnt_fetched_or_shown(self):
        server.api_warnings_set({"on": True, "lat": DEVON["lat"], "lon": DEVON["lon"]}, {})
        server.http_get = lambda url, **kw: (_ for _ in ()).throw(AssertionError("fetched " + url)) \
            if "water" in url else (_ for _ in ()).throw(IOError("offline"))
        server.warnings_run()
        w = server.warn_public()
        self.assertNotIn("water", w["live"])
        self.assertEqual(w["unavailable"], {"water": server.WATER_CHOOSE})
        self.assertNotIn("water", w["sources"])
        server.api_warnings_set({"water_co": "Thames Water"}, {})
        self.assertEqual(server.warn_public()["unavailable"], {"water": server.WATER_ONLY})
        server.api_warnings_set({"lat": "", "lon": ""}, {})
        self.assertEqual(server.warn_public()["unavailable"], {"water": "Needs your home location"})
