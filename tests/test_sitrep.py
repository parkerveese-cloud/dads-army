"""1.25.0: the spoken sitrep. What Read to me says is worked out on the Pi, so the app and Home Assistant say the same
thing: the app reads it with the device's own voice, and sensor.dads_army_sitrep carries it for a speaker or display
(the "Dads Army: read the sitrep" and "Dads Army: spoken sitrep" blueprints). Home Assistant's copy never says what a
Gemini briefing says (Google's terms), only that there's one to read in Dads Army."""
import datetime as dt
import os

from support import APP_DIR, AppTest, server

TODAY = dt.date(2026, 11, 21)   # a Saturday
BLUEPRINTS = os.path.join(os.path.dirname(APP_DIR), "blueprints")


def briefing(ai="anthropic", day=TODAY.isoformat(), social=""):
    return {"config": {"on": True}, "available": True, "latest": {
        "day": day, "ai": ai, "text": "Things are quiet near home. Flu is rising.", "social": social,
        "levels": {"local": 2, "national": 3}, "vs_usual": {"local": "higher", "national": "same"}}}


class WordsTest(AppTest):
    """sitrep_words() on its own, from the same summary, warnings and briefing the app gets."""

    def words(self, s=None, w=None, b=None, ha=False):
        return server.sitrep_words(s if s is not None else server.summary(), w or {"on": False},
                                   b or {"config": {"on": False}}, ha=ha, today=TODAY)

    def test_starts_and_ends(self):
        words = self.words()
        self.assertEqual(words[0], "Here's your sitrep for Saturday 21 November.")
        self.assertTrue(words[1].startswith("The household alert level is "))
        self.assertRegex(words[1], r"^The household alert level is [A-Z][a-z]+, [1-5] of 5\. ")   # Moderate, not MODERATE
        self.assertEqual(words[-1], "That's the sitrep.")

    def test_the_stores(self):
        self.add("Baked beans", 4, expiry=(dt.date.today() - dt.timedelta(days=3)).isoformat(), category="food",
                 unit="tins", target_qty=12)
        self.add("Rice", 2, expiry=(dt.date.today() + dt.timedelta(days=2)).isoformat(), category="food", unit="kg")
        s = server.summary()
        text = " ".join(self.words(s))
        self.assertIn("1 item has expired, 1 is expiring soon and 1 is below target.", text)
        s.update(hold_out_days=12.7, target_days=30, runs_out_first="water", people=2)
        self.assertIn("Your stores would last 12 days, against a target of 30 days. Water runs out first.",
                      " ".join(self.words(s)))
        for days, said in ((2.3, "2.3 days"), (4, "4 days"), (1, "1 day"), (0, "0 days"), (1500, "over 999 days")):
            s.update(hold_out_days=days, runs_out_first="")
            self.assertIn("would last %s, against" % said, " ".join(self.words(s)))
        s.update(people=0)
        self.assertNotIn("Your stores would last", " ".join(self.words(s)))

    def test_nothing_in_the_stores(self):
        self.assertFalse([x for x in self.words() if x.startswith("Your stores") or "expired" in x or "below target" in x])

    def test_checks_due(self):
        server.api_check_create({"name": "Test the smoke alarms", "every_days": 30}, {})
        self.assertIn("1 routine check is due.", self.words())
        server.api_check_create({"name": "Charge the power banks", "every_days": 90}, {})
        self.assertIn("2 routine checks are due.", self.words())

    def test_why_and_escalated(self):
        s = server.summary()
        s["situation"] = dict(s["situation"], name="SEVERE", level=4, meaning="Act now.", escalated=True,
                              escalated_why="", reasons=[{"title": t} for t in "ABCDEF"])
        words = self.words(s)
        self.assertIn("The household alert level is Severe, 4 of 5. Act now.", words)
        self.assertIn("Why: A, B, C, D and 2 more.", words)
        self.assertIn("It's raised to Severe because the stores wouldn't last 3 days.", words)

    def test_warnings_where_you_live(self):
        w = {"on": True, "location": {"lat": 51.5, "lon": 0}, "trends": [{"title": "Power cuts near you are rising"}],
             "affecting": {"yours": [{"title": "Yellow warning of wind"}, {"title": "Power cut in SE10 0"}]}}
        words = self.words(w=w)
        self.assertIn("Things to watch: Power cuts near you are rising.", words)
        self.assertIn("Affecting you: Yellow warning of wind and Power cut in SE10 0.", words)
        w["affecting"]["yours"] = []
        self.assertIn("Nothing is affecting your area right now.", self.words(w=w))

    def test_warnings_without_a_location(self):
        w = {"on": True, "location": None, "region": "se", "regions": [["se", "South East England"]], "items": [
            {"title": "Yellow warning of wind", "source": "metoffice", "severity": 1},
            {"title": "Test Emergency Alert", "source": "govalerts", "severity": 1}]}   # a test isn't said
        self.assertIn("Warnings in force: Yellow warning of wind.", self.words(w=w))
        w["items"] = w["items"][1:]
        self.assertIn("No warnings for South East England.", self.words(w=w))
        w["region"] = "UK"
        self.assertIn("No warnings for the whole UK.", self.words(w=w))
        self.assertFalse([x for x in self.words(w={"on": False, "items": w["items"]})
                          if x.startswith(("Warnings in force", "No warnings", "Affecting you", "Nothing is affecting"))])

    def test_the_briefing(self):
        words = self.words(b=briefing(social="People report low water pressure."))
        i = words.index("The daily briefing.")
        self.assertEqual(words[i + 1:i + 4], ["Local: Normal, above usual. UK: Raised.",
                                              "Things are quiet near home. Flu is rising.",
                                              "On social media, and unconfirmed: People report low water pressure."])
        self.assertIn("The daily briefing, from Tuesday 17 November.", self.words(b=briefing(day="2026-11-17")))
        off = briefing()
        off["config"]["on"] = False
        self.assertFalse([x for x in self.words(b=off) if "briefing" in x])

    def test_a_gemini_briefing_isnt_said_in_home_assistant(self):
        """The app shows Google's search suggestions with it, so Read to me reads it. Home Assistant can't."""
        b = briefing(ai="google", social="People report low water pressure.")
        self.assertIn("Things are quiet near home. Flu is rising.", self.words(b=b))
        ha = " ".join(self.words(b=b, ha=True))
        self.assertIn("The daily briefing is ready to read in Dads Army.", ha)
        for secret in ("quiet near home", "Normal", "Raised", "social media", "water pressure"):
            self.assertNotIn(secret, ha)
        old = " ".join(self.words(b=briefing(ai="google", day="2026-11-17"), ha=True))
        self.assertIn("The daily briefing, from Tuesday 17 November, is ready to read in Dads Army.", old)
        # Claude's is said in Home Assistant too, as it already is in sensor.dads_army_briefing
        self.assertIn("Things are quiet near home. Flu is rising.", self.words(b=briefing(), ha=True))

    def test_resilience(self):
        s = server.summary()
        rs = s["resilience"]
        self.assertTrue(rs["areas"])
        said = [x for x in self.words(s) if x.startswith("You're ")][0]
        self.assertTrue(said.startswith("You're %s%% ready across %d areas." % (rs["pct"], len(rs["areas"]))), said)
        step = [m for m in rs["items"] if m["id"] == rs["next"][0]][0]["title"]
        self.assertIn(" Next step: " + step.rstrip("."), said)


class SayableTest(AppTest):
    def test_easy_to_say(self):
        say = server.sayable
        self.assertEqual(say("−2°C overnight · frost"), "minus 2 degrees overnight, frost")
        self.assertEqual(say("1 km away & 3.5km on"), "1 kilometre away and 3.5 kilometres on")
        self.assertEqual(say("PM2.5 at 40 µg/m³ 🔴 ⚠️ → see https://example.com/x ."), "PM2.5 at 40 micrograms per cubic metre see.")
        self.assertEqual(say("  Spaces   , and  stops . "), "Spaces, and stops.")
        self.assertEqual(server.say_date(dt.date(2027, 1, 1)), "Friday 1 January")


class HomeAssistantTest(AppTest):
    def test_the_sensor(self):
        self.add("Baked beans", 4, expiry=(dt.date.today() - dt.timedelta(days=3)).isoformat(), category="food")
        e = server.ha_entities(server.summary())["sensor.dads_army_sitrep"]
        self.assertEqual(e["state"], dt.date.today().isoformat())   # the day it's for: never yesterday's
        self.assertEqual(e["attributes"]["device_class"], "date")
        self.assertNotIn("state_class", e["attributes"])
        speech = e["attributes"]["speech"]
        self.assertTrue(speech.startswith("Here's your sitrep for "), speech)
        self.assertTrue(speech.endswith("That's the sitrep."), speech)
        self.assertIn("1 item has expired.", speech)
        self.assertNotIn("\n", speech)

    def test_a_stored_gemini_briefing(self):
        today = dt.date.today().isoformat()
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "google", "keys": {"google": "AIza-test-key-0123456789"}})
            server.set_setting_raw(db, "briefing", {"on": True, "area": "Greenwich"})
            server.set_setting_raw(db, "briefings", [{
                "day": today, "made_at": server.now_iso(), "ai": "google", "text": "Wind is due tomorrow afternoon.",
                "headline": "Wind tomorrow", "levels": {"local": 2}, "social": "Posts say the A206 is shut."}])
        speech = server.ha_entities(server.summary())["sensor.dads_army_sitrep"]["attributes"]["speech"]
        self.assertIn("The daily briefing is ready to read in Dads Army.", speech)
        self.assertNotIn("Wind", speech)
        self.assertNotIn("A206", speech)
        self.assertIn("Wind is due tomorrow afternoon.", server.api_state({}, {})["sitrep"])   # the app shows it, so reads it

    def test_the_app_gets_the_same_words(self):
        st = server.api_state({}, {})
        self.assertEqual(st["sitrep"], server.sitrep_words(server.summary(), st["warnings"], st["briefing"]))
        self.assertEqual(st["sitrep"][-1], "That's the sitrep.")

    def test_the_blueprints(self):
        for path, domain in (("script/dads_army_sitrep.yaml", "script"),
                             ("automation/dads_army_spoken_sitrep.yaml", "automation")):
            with open(os.path.join(BLUEPRINTS, *path.split("/")), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("  domain: %s\n" % domain, text)
            self.assertIn("source_url: https://github.com/parkerveese-cloud/dads-army/blob/main/blueprints/" + path, text)
            self.assertIn("state_attr(s, 'speech')", text)
            self.assertIn("'sensor.dads_army_sitrep'", text)
            self.assertIn("action: tts.speak", text)
            self.assertIn("cache: false", text)   # a new sitrep each time: don't fill Home Assistant's disk with them
        with open(os.path.join(BLUEPRINTS, "automation", "dads_army_spoken_sitrep.yaml"), encoding="utf-8") as f:
            self.assertIn("event_type: dads_army_alert_level", f.read())
