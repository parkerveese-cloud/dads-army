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


GEMINI_REPLY = REPLY.rsplit("\nSOURCES:", 1)[0].replace("HEADLINE:", "**HEADLINE:**")   # Gemini likes bold
REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQ" + "x" * 300   # Google's links: long
CHIPS = ('<style>.container{display:flex}</style><div class="container"><a class="chip" '
         'href="https://www.google.com/search?q=London+news+today">London news today</a></div>')


CHIPS2 = CHIPS.replace("London+news+today", "UK+cyber+news").replace(">London news today<", ">UK cyber news<")


def gemini_answer(text=GEMINI_REPLY, queries=("London news today", "UK cyber news"), chips=(CHIPS, CHIPS2), cited=True,
                  titles=("bbc.co.uk", "ncsc.gov.uk")):
    """1.27.0: an Interactions reply, the shape Gemini 4 Hydrogen's real one had (23 Nov 2026): rounds of searches,
    each with Google's search suggestions, its thinking, then the answer. That one had no citations or result links:
    cited=True adds them as Google's docs show them."""
    rounds, steps = [list(queries[:1]), list(queries[1:])], []
    for n, qs in enumerate(rounds):
        found = [{"search_suggestions": chips[n]}] if n < len(chips) and chips[n] else []
        if cited and n == 0:
            found += [{"url": REDIRECT + "1", "title": titles[0], "snippet": "..."},
                      {"url": REDIRECT + "2", "title": titles[1], "snippet": "..."},
                      {"url": "javascript:alert(1)", "title": "bad"}]
        steps += [{"type": "google_search_call", "id": "call%d" % n, "signature": "x", "search_type": "web_search",
                   "arguments": {"queries": qs}},
                  {"type": "google_search_result", "call_id": "call%d" % n, "signature": "x", "is_error": False,
                   "result": found}]
    out = [{"type": "text", "text": text}]
    if cited:
        out[0]["annotations"] = [
            {"type": "url_citation", "url": REDIRECT + "2", "title": titles[1], "start_index": 0, "end_index": 40},
            {"type": "url_citation", "url": REDIRECT + "1", "title": titles[0], "start_index": 41, "end_index": 90},
            {"type": "url_citation", "url": "javascript:alert(1)", "title": "bad", "start_index": 41, "end_index": 90}]
    steps += [{"type": "thought", "signature": "x", "summary": [{"type": "text", "text": "Thinking it over"}]},
              {"type": "model_output", "content": out}]
    return {"created": "2026-11-23T00:52:28Z", "model": "gemini-4-hydrogen", "object": "interaction",
            "service_tier": "standard", "status": "completed", "steps": steps, "updated": "2026-11-23T00:52:28Z",
            "usage": {"total_tokens": 6000, "total_input_tokens": 2000, "total_tool_use_tokens": 3000,
                      "total_output_tokens": 300, "total_thought_tokens": 700,
                      "grounding_tool_count": [{"type": "google_search", "count": len(queries)}]}}


class GeminiBriefingTest(AppTest):
    """1.22.0: Gemini writes it, searching with Grounding with Google Search, on a Google key saved under Scanning."""

    def setUp(self):
        super().setUp()
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "google", "keys": {"google": "AIza-test-key-0123456789"}})
        server.BRIEF.update(busy=False, error="", day="", tries=0, last_try=0.0)
        self.real_post = server._post_json
        self.calls = []

    def tearDown(self):
        server._post_json = self.real_post
        super().tearDown()

    def fake(self, answers):
        def post(url, body, headers, timeout=60):
            self.calls.append({"url": url, "body": body, "headers": headers})
            a = answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a
        server._post_json = post

    def switch_on(self, **cfg):
        with server.tx() as db:
            server.set_setting_raw(db, "briefing", dict({"on": True, "area": "Greenwich"}, **cfg))

    def test_a_google_key_is_enough(self):
        self.assertEqual(server.brief_cfg()["model"], "gemini-4-hydrogen")   # the key there is decides
        pub = server.brief_public()
        self.assertTrue(pub["available"] and pub["ready"])
        self.assertFalse(pub["models"]["claude-haiku-5-5"]["key"])
        with server.tx() as db:   # today's is written, so switching on doesn't write one in the background
            server.set_setting_raw(db, "briefings", [{"day": server.dt.date.today().isoformat(), "text": "x", "ai": "google"}])
        server.api_briefing_put({"on": True}, {})
        self.assertTrue(server.brief_cfg()["on"])
        self.assertEqual(server.brief_cfg()["model"], "gemini-4-hydrogen")   # saved
        with self.assertRaises(server.ApiError) as e:   # Claude, without an Anthropic key
            server.api_briefing_put({"model": "claude-haiku-5-5"}, {})
        self.assertIn("Anthropic API key", e.exception.message)

    def test_writing_one(self):
        self.switch_on()
        self.fake([gemini_answer()])
        b = server.make_briefing("test")
        call = self.calls[0]
        # 1.27.0: Google's Interactions API, which says what was searched even when Gemini searched while thinking
        self.assertEqual(call["url"], "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(call["headers"], {"x-goog-api-key": "AIza-test-key-0123456789",   # in a header, not the URL
                                           "Api-Revision": "2026-05-20"})
        self.assertNotIn("key=", call["url"])
        self.assertEqual(call["body"]["tools"], [{"type": "google_search"}])
        self.assertEqual(call["body"]["model"], "gemini-4-hydrogen")
        self.assertIs(call["body"]["store"], False)   # Google doesn't keep it for later
        # No location goes with it, and nothing else: just the prompt
        self.assertEqual(sorted(call["body"]), ["generation_config", "input", "model", "store", "tools"])
        prompt = call["body"]["input"]
        self.assertIn("Greenwich", prompt)
        self.assertNotIn("SOURCES:", prompt)   # Google says what the sources were
        self.assertTrue(b["text"].startswith("Overnight things are quiet"))
        self.assertNotIn("Thinking it over", b["text"])
        self.assertEqual(b["headline"], "Wind warning tomorrow; router security update advised")
        self.assertEqual(b["levels"], {"local": 2, "national": 3, "global": 3})
        self.assertEqual((b["ai"], b["model"], b["searches"]), ("google", "gemini-4-hydrogen", 2))
        # The sources it rests on, first used first, with Google's links exactly as they came; never a script link
        self.assertEqual([(x["title"], x["url"]) for x in b["sources"]], [("ncsc.gov.uk", REDIRECT + "2"), ("bbc.co.uk", REDIRECT + "1")])
        self.assertEqual(b["searched"], ["London news today", "UK cyber news"])
        self.assertEqual(b["suggestions"], [CHIPS, CHIPS2])   # one widget for each round of searches
        # Hydrogen: 5000 in (prompt and search results), 1000 out (answer and thinking), and 2 searches at 1.4 cents
        self.assertAlmostEqual(b["cost_usd"], 5000 * 1.50 / 1e6 + 1000 * 7.50 / 1e6 + 2 * 0.014, places=6)
        row = server.DB.execute("SELECT ai, model, tokens_in, tokens_out FROM ai_calls").fetchone()
        self.assertEqual(tuple(row), ("google", "gemini-4-hydrogen", 5000, 1000))
        self.assertEqual(server.ai_stats()["tasks"]["briefing"], 1)
        latest = server.brief_public()["latest"]
        self.assertEqual(latest["suggestions"], 2)   # how many widgets: the HTML itself comes from its own page

    def test_as_gemini_4_answers(self):
        """Gemini 4's real reply had no citations or result links: no sources, but what it searched for, its search
        suggestions and the searches it ran are all there (through generateContent they were all lost)."""
        self.switch_on()
        a = gemini_answer(cited=False)
        a["usage"]["grounding_tool_count"] = [{"type": "google_search", "count": 8}]   # Google's count, if it's more
        self.fake([a])
        b = server.make_briefing("test")
        self.assertEqual((b["sources"], b["searched"], b["searches"]), ([], ["London news today", "UK cyber news"], 8))
        self.assertEqual(b["suggestions"], [CHIPS, CHIPS2])
        self.assertTrue(b["text"].startswith("Overnight things are quiet"))

    def test_nothing_came_back(self):
        self.switch_on()
        a = gemini_answer()
        a["steps"] = [s for s in a["steps"] if s["type"] != "model_output"]
        self.fake([a])
        with self.assertRaises(server.ApiError) as e:
            server.make_briefing()
        self.assertEqual(e.exception.message, "Gemini couldn't answer (no briefing came back)")

    def test_the_search_suggestions_page(self):
        self.switch_on()
        self.fake([gemini_answer()])
        b = server.make_briefing("test")
        page = server.api_briefing_suggestions({}, {"day": [b["day"]]})
        self.assertIsInstance(page, server.Raw)
        self.assertTrue(page.content_type.startswith("text/html"))
        html = page.data.decode("utf-8")
        # As Google made them, one under another
        self.assertIn('<div class="g">%s</div><div class="g">%s</div>' % (CHIPS, CHIPS2), html)
        self.assertIn('<base target="_blank">', html)
        self.assertEqual(page.headers["Content-Security-Policy"], "sandbox allow-popups allow-popups-to-escape-sandbox")
        with self.assertRaises(server.ApiError):
            server.api_briefing_suggestions({}, {"day": ["2001-01-01"]})
        self.switch_on(on=False)
        with self.assertRaises(server.ApiError):
            server.api_briefing_suggestions({}, {"day": [b["day"]]})

    def test_suggestions_kept_before_1_27(self):
        """One widget, kept as a string: still shown, as one."""
        self.switch_on()
        with server.tx() as db:
            server.set_setting_raw(db, "briefings", [{"day": "2026-11-22", "ai": "google", "text": "x", "suggestions": CHIPS}])
        self.assertEqual(server.brief_public()["latest"]["suggestions"], 1)
        page = server.api_briefing_suggestions({}, {"day": ["2026-11-22"]}).data.decode("utf-8")
        self.assertIn('<div class="g">%s</div></body>' % CHIPS, page)

    def test_too_many_suggestions(self):
        """Whole widgets only, as many as fit."""
        one, two = "<div>" + "x" * 35000 + "</div>", "<div>" + "y" * 35000 + "</div>"
        self.fake([gemini_answer(chips=(one, two))])
        kept = server.brief_call_gemini("k", "gemini-4-hydrogen", "prompt", {})[4]
        self.assertEqual(kept, [one])

    def test_the_suggestions_page_over_http(self):
        """Through the real server: the page's own sandbox policy, on top of the app's."""
        import threading
        import urllib.request
        self.switch_on()
        self.fake([gemini_answer()])
        b = server.make_briefing("test")
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/briefing/suggestions?day=%s" % (httpd.server_port, b["day"])) as r:
                policies = r.headers.get_all("Content-Security-Policy")
                body = r.read().decode("utf-8")
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertIn("sandbox allow-popups allow-popups-to-escape-sandbox", policies)
        self.assertTrue(any("script-src 'self'" in p for p in policies))   # and no inline script runs
        self.assertIn(CHIPS, body)

    def test_home_assistant_isnt_given_the_text(self):
        self.switch_on()
        self.fake([gemini_answer()])
        server.make_briefing("test")
        s = server.ha_entities(server.summary())["sensor.dads_army_briefing"]
        self.assertEqual(s["state"], "Written by Gemini: read it in Dads Army")
        self.assertNotIn("briefing", s["attributes"])
        self.assertNotIn("local", s["attributes"])
        self.assertEqual(s["attributes"]["written_by"], "Gemini")
        self.assertEqual(server.brief_public()["history"], [])

    def test_claude_isnt_told_what_gemini_wrote(self):
        past = [{"day": "2026-01-03", "ai": "google", "levels": {"local": 2, "national": 3, "global": 3}, "text": "Gemini's day"},
                {"day": "2026-01-02", "levels": {"local": 1, "national": 2, "global": 2}, "text": "Claude's day"}]
        past.reverse()
        self.assertNotIn("Gemini's day", server.brief_baseline(past, "2026-01-04", "anthropic"))
        self.assertIn("Claude's day", server.brief_baseline(past, "2026-01-04", "anthropic"))
        self.assertIn("Gemini's day", server.brief_baseline(past, "2026-01-04", "google"))

    def test_declined(self):
        self.switch_on()
        a = gemini_answer()
        a.update(status="failed", errors=[{"code": "https://example/blocked", "message": "Blocked for safety"}])
        self.fake([a])
        with self.assertRaises(server.ApiError) as e:
            server.make_briefing()
        self.assertEqual(e.exception.message, "Gemini couldn't answer (no briefing came back: Blocked for safety)")
        self.assertEqual(server.DB.execute("SELECT ok FROM ai_calls").fetchone()[0], 0)

    def test_the_free_tier(self):
        """Google's free tier has no Google Search: the error says what to do."""
        self.switch_on()
        self.fake([IOError("HTTP 429: Quota exceeded for metric: search grounding, limit: 0")])
        with self.assertRaises(server.ApiError) as e:
            server.make_briefing()
        self.assertIn("allowance is used up", e.exception.message)
        self.assertIn("billing switched on", e.exception.message)
        self.assertTrue(server.brief_cfg()["on"])   # not the key's fault: it stays on

    def test_a_refused_key_switches_it_off(self):
        self.switch_on()
        self.fake([IOError("HTTP 400: API key not valid. Please pass a valid API key.")])
        with self.assertRaises(server.ApiError):
            server.make_briefing()
        self.assertFalse(server.brief_cfg()["on"])
        self.assertIn("Gemini didn't accept the API key", server.BRIEF["error"])

    def test_both_keys(self):
        """With both keys saved, the AI chosen under Scanning writes it, until you choose; a choice stays."""
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "anthropic", "keys": {"google": "AIza-test-key-0123456789",
                                                                                      "anthropic": "test-key"}})
        self.assertEqual(server.brief_cfg()["model"], "claude-haiku-5-5")
        server.api_briefing_put({"model": "gemini-4-argon"}, {})
        self.assertEqual(server.brief_cfg()["model"], "gemini-4-argon")
        self.assertEqual(server.brief_public()["models"]["gemini-4-argon"]["about"], "Gemini 4 Argon: about 25p a day")

    def test_scanning_counts_geminis_thinking(self):
        """Gemini's thinking is billed as output, for scanning too (still through generateContent)."""
        self.fake([{"candidates": [{"content": {"parts": [{"text": "Thinking it over", "thought": True},
                                                          {"text": "2027-03-31"}]}, "finishReason": "STOP"}],
                    "usageMetadata": {"promptTokenCount": 2000, "toolUsePromptTokenCount": 3000,
                                      "candidatesTokenCount": 300, "thoughtsTokenCount": 700}}])
        usage = {}
        self.assertEqual(server.ai_direct("google", "k", "", "prompt", usage=usage), "2027-03-31")
        self.assertEqual(usage, {"in": 5000, "out": 1000})


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
            if k not in ("water", "supply"):   # 1.21.0: your power supply is UK Power Networks' only (test_supply)
                self.assertEqual(server.source_covers(k, {}, DEVON), (True, ""), k)
                self.assertEqual(server.source_covers(k, {}, None), (True, ""), k)

    def test_out_of_area_isnt_fetched_or_shown(self):
        server.api_warnings_set({"on": True, "lat": DEVON["lat"], "lon": DEVON["lon"]}, {})
        server.http_get = lambda url, **kw: (_ for _ in ()).throw(AssertionError("fetched " + url)) \
            if "water" in url else (_ for _ in ()).throw(IOError("offline"))
        server.warnings_run()
        w = server.warn_public()
        self.assertNotIn("water", w["live"])
        self.assertEqual(w["unavailable"], {"water": server.WATER_CHOOSE, "supply": server.UKPN_ONLY})   # Devon
        self.assertNotIn("water", w["sources"])
        server.api_warnings_set({"water_co": "Thames Water"}, {})
        self.assertEqual(server.warn_public()["unavailable"], {"water": server.WATER_ONLY, "supply": server.UKPN_ONLY})
        server.api_warnings_set({"lat": "", "lon": ""}, {})
        self.assertEqual(server.warn_public()["unavailable"], {"water": "Needs your home location"})
