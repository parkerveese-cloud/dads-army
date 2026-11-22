"""1.26.0: when the household alert level changes, the daily briefing is written again, told what's changed and why
(never which room or sensor, or exactly where home is), and Home Assistant hears when it's ready (dads_army_briefing),
for the "Dads Army: spoken sitrep" blueprint to say. At most once an hour and 6 times a day; overnight only for SEVERE
or CRITICAL. No internet and no real AI: the APIs are stood in for."""
import datetime as dt
import os
import time

from support import APP_DIR, AppTest, FakeHA, server
from test_briefing import REPLY, answer, gemini_answer

BLUEPRINT = os.path.join(os.path.dirname(APP_DIR), "blueprints", "automation", "dads_army_spoken_sitrep.yaml")
TODAY = dt.date.today()
NIGHT = dt.datetime.combine(TODAY, dt.time(3, 31))
MORNING = dt.datetime.combine(TODAY, dt.time(6, 1))
EVENING = dt.datetime.combine(TODAY, dt.time(21, 1))


def severe():
    """SEVERE, as it went one evening: a warm room, raised because the water wouldn't last 3 days."""
    return {"level": 4, "name": "SEVERE", "meaning": "Act now.", "escalated": True,
            "escalated_why": "the stores wouldn't last 3 days", "guidance": [], "notes": [],
            "reasons": [{"level": 3, "name": "SUBSTANTIAL", "key": "hot_indoor", "title": "Warmest room 30°C"},
                        {"level": 2, "name": "MODERATE", "key": "water_low", "title": "Water would last 2.8 days"}]}


def change(to="SEVERE", level=4, previous=2, at="21:01:50"):
    return {"from": server.LEVELS[previous - 1][0], "to": to, "previous": previous, "level": level,
            "rising": level > previous, "at": "%s %s" % (TODAY.isoformat(), at)}


def morning(**kw):
    return dict({"day": TODAY.isoformat(), "made_at": TODAY.isoformat() + " 06:01:17", "ai": "anthropic", "by": "schedule",
                 "text": "Quiet this morning near home.", "headline": "Quiet", "alert_level": 2}, **kw)


class Base(AppTest):
    def setUp(self):
        super().setUp()
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "anthropic", "keys": {"anthropic": "test-key"}})
            server.set_setting_raw(db, "briefing", {"on": True, "area": "Greenwich"})
        self.reset()
        self.real_post = server._post_json
        self.calls = []

    def tearDown(self):
        server._post_json = self.real_post
        self.reset()
        super().tearDown()

    def reset(self):
        server.BRIEF.update(busy=False, error="", day="", tries=0, last_try=0.0, redo=None, redo_day="", redos=0,
                            last_redo=0.0)

    def fake(self, answers):
        def post(url, body, headers, timeout=60):
            self.calls.append(body)
            a = answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a
        server._post_json = post

    def claude(self):
        return answer([{"type": "text", "text": REPLY}], searches=3)

    def prompt(self, i=0):
        c = self.calls[i]
        return c["messages"][0]["content"] if "messages" in c else c["contents"][0]["parts"][0]["text"]

    def save(self, *briefings):
        with server.tx() as db:
            server.set_setting_raw(db, "briefings", list(briefings))


class WhatItsToldTest(Base):
    def test_the_level_and_why(self):
        known = server.brief_known({"food_days": 5, "water_days": 2.8, "situation": severe()})
        self.assertIn("- The household alert level (Dads Army's own, from the warnings, the home's sensors and the "
                      "stores: LOW, MODERATE, SUBSTANTIAL, SEVERE, CRITICAL): SEVERE, 4 of 5. Because: Warmest room "
                      "30°C; Water would last 2.8 days. Raised to SEVERE because the stores wouldn't last 3 days.", known)

    def test_never_which_room_or_sensor_or_where(self):
        sit = dict(severe(), escalated=False, reasons=[
            {"key": "smoke_alarm", "title": "Smoke or heat alarm: Bedroom 2 smoke detector"},
            {"key": "leak", "title": "Water leak sensor: Under the kitchen sink"},
            {"key": "power_cut_near", "title": "Power cut in SE10 0, 1.2 km away"},
            {"key": "flood_warning", "title": "Flood warning: River Esk at Sleights"},
            {"key": "cold_indoor", "title": "Coldest room 11°C"}])
        known = server.brief_known({"food_days": 5, "water_days": 5, "situation": sit})
        line = [x for x in known.split("\n") if "household alert level" in x][0]
        self.assertIn("Smoke or heat alarm going off at home; Water leak sensor going off at home", line)
        self.assertIn("Flood warning: River Esk;", line)
        self.assertIn("Coldest room 11°C", line)
        self.assertIn("near home", line)
        for secret in ("Bedroom 2", "kitchen sink", "SE10", "1.2 km", "Sleights"):
            self.assertNotIn(secret, line)

    def test_written_again_says_why_and_what_it_said_earlier(self):
        p = server.brief_prompt("anthropic", TODAY, server.brief_cfg(), [morning()], change(), None)
        self.assertIn("This briefing is being written again, at 21:01, because the household alert level has just "
                      "gone up from MODERATE to SEVERE", p)
        self.assertIn("Today's earlier briefing said: Quiet this morning near home.", p)
        self.assertNotIn("being written again", server.brief_prompt("anthropic", TODAY, server.brief_cfg(), [morning()]))
        # Claude isn't told what Gemini wrote (Google's terms); Gemini can be
        gem = [morning(ai="google")]
        self.assertNotIn("Quiet this morning", server.brief_prompt("anthropic", TODAY, server.brief_cfg(), gem, change()))
        self.assertIn("Quiet this morning", server.brief_prompt("google", TODAY, server.brief_cfg(), gem, change()))


class LevelChangeTest(Base):
    def setUp(self):
        super().setUp()
        self.ha = FakeHA()
        server.HA_TOKEN = "test-token"
        server.HA_API = self.ha.api
        with server.tx() as db:
            server.set_setting_raw(db, "alert_level_last", 2)

    def tearDown(self):
        self.ha.close()
        super().tearDown()

    def test_a_change_has_it_written_again(self):
        server.level_change(severe())
        ev = self.ha.events_of("dads_army_alert_level")[0]
        self.assertIs(ev["new_briefing"], True)
        r = server.BRIEF["redo"]
        self.assertEqual((r["from"], r["to"], r["level"], r["previous"], r["rising"]), ("MODERATE", "SEVERE", 4, 2, True))

    def test_not_when_its_switched_off(self):
        server.api_briefing_put({"on_change": False}, {})
        self.assertFalse(server.brief_cfg()["on_change"])
        server.level_change(severe())
        self.assertIs(self.ha.events_of("dads_army_alert_level")[0]["new_briefing"], False)
        self.assertIsNone(server.BRIEF["redo"])

    def test_not_without_the_briefing(self):
        with server.tx() as db:
            server.set_setting_raw(db, "briefing", {"on": False})
        server.level_change(severe())
        self.assertIs(self.ha.events_of("dads_army_alert_level")[0]["new_briefing"], False)
        self.assertIsNone(server.BRIEF["redo"])

    def test_later_within_the_hour(self):
        server.BRIEF["last_redo"] = time.time() - 600
        server.level_change(severe())
        self.assertIs(self.ha.events_of("dads_army_alert_level")[0]["new_briefing"], False)   # not now: within the hour
        self.assertIsNotNone(server.BRIEF["redo"])                                           # but it's kept for then


class WhenTest(Base):
    def due(self, now=EVENING, **redo):
        server.BRIEF["redo"] = dict(change(), **redo)
        return server.brief_redo_due(server.brief_cfg(), now)

    def test_when(self):
        self.assertTrue(self.due())
        self.assertFalse(self.due(NIGHT, level=3, to="SUBSTANTIAL"))   # overnight, waits for the morning's
        self.assertTrue(self.due(NIGHT))                                # unless it's SEVERE or CRITICAL
        server.BRIEF["redo"] = None
        self.assertFalse(server.brief_redo_due(server.brief_cfg(), EVENING))

    def test_how_often(self):
        server.BRIEF["last_redo"] = time.time() - 59 * 60
        self.assertFalse(self.due())   # once an hour at most
        server.BRIEF["last_redo"] = time.time() - 61 * 60
        self.assertTrue(self.due())
        server.BRIEF["last_try"] = time.time() - 60
        self.assertFalse(self.due())   # nor straight after any other
        server.BRIEF["last_try"] = 0.0
        server.BRIEF.update(redo_day=TODAY.isoformat(), redos=server.BRIEF_REDO_MAX)
        self.assertFalse(self.due())   # 6 a day at most
        server.BRIEF["busy"] = True
        server.BRIEF["redos"] = 0
        self.assertFalse(self.due())

    def test_an_overnight_one_isnt_the_mornings(self):
        self.save(morning(made_at=TODAY.isoformat() + " 01:15:00", change=change(at="01:14:00")))
        self.assertTrue(server.brief_due(server.brief_cfg(), MORNING))
        self.save(morning(made_at=TODAY.isoformat() + " 01:15:00"))   # written by hand at 1am: that's today's
        self.assertFalse(server.brief_due(server.brief_cfg(), MORNING))


class WritingTest(Base):
    def test_written_again(self):
        self.save(morning())
        server.BRIEF["redo"] = change()
        self.fake([self.claude()])
        self.assertTrue(server.brief_tick(EVENING))
        self.assertIn("gone up from MODERATE to SEVERE", self.prompt())
        self.assertIn("Today's earlier briefing said: Quiet this morning near home.", self.prompt())
        self.assertIn("- The household alert level (Dads Army's own", self.prompt())
        b = server.brief_list()
        self.assertEqual(len(b), 1)   # today's, replaced
        self.assertEqual((b[0]["by"], b[0]["change"]["to"]), ("level", "SEVERE"))
        self.assertEqual(b[0]["alert_level"], server.summary()["situation"]["level"])
        self.assertIsNone(server.BRIEF["redo"])
        self.assertEqual(server.BRIEF["redos"], 1)
        self.assertEqual(server.brief_public()["latest"]["change"]["to"], "SEVERE")   # for the Sitrep's card

    def test_back_where_it_was(self):
        """Up and back down within the hour: the latest one was written at this level, so there's nothing new."""
        self.save(morning(alert_level=2))
        server.BRIEF["redo"] = change(to="MODERATE", level=2, previous=4)
        self.fake([])
        self.assertFalse(server.brief_tick(EVENING))
        self.assertEqual(self.calls, [])
        self.assertIsNone(server.BRIEF["redo"])

    def test_the_morning_says_what_changed_overnight(self):
        self.save(dict(morning(), day=(TODAY - dt.timedelta(days=1)).isoformat()))
        server.BRIEF["redo"] = change(to="MODERATE", level=2, previous=4, at="03:31:58")
        self.fake([self.claude()])
        self.assertFalse(server.brief_tick(NIGHT))   # waits
        self.assertEqual(self.calls, [])
        self.assertTrue(server.brief_tick(MORNING))
        self.assertIn("at 03:31, because the household alert level has just gone down from SEVERE to MODERATE",
                      self.prompt())
        b = server.brief_list()[-1]
        self.assertEqual((b["by"], b["change"]["to"]), ("schedule", "MODERATE"))
        self.assertEqual(server.BRIEF["redos"], 0)   # the morning's doesn't count towards the 6

    def test_if_it_fails_it_tries_again_later(self):
        server.BRIEF["redo"] = change()
        self.fake([IOError("HTTP 529: overloaded")])
        self.assertFalse(server.brief_tick(EVENING))
        self.assertEqual(server.BRIEF["redo"]["to"], "SEVERE")   # kept
        self.assertFalse(server.brief_redo_due(server.brief_cfg(), EVENING))   # in an hour


class HomeAssistantTest(Base):
    def setUp(self):
        super().setUp()
        self.ha = FakeHA()
        server.HA_TOKEN = "test-token"
        server.HA_API = self.ha.api

    def tearDown(self):
        self.ha.close()
        super().tearDown()

    def test_its_said_when_its_ready(self):
        self.fake([self.claude()])
        server.make_briefing("level", change=change())
        ev = self.ha.events_of("dads_army_briefing")[0]
        self.assertTrue(ev["speech"].startswith(
            "Dads Army. The daily briefing, written again after the alert level went up to Severe. Local: Normal, above "
            "usual. UK: Raised. World: Raised. Overnight things are quiet near home"), ev["speech"])
        self.assertEqual((ev["by"], ev["change"]["to"], ev["rising"], ev["written_by"]), ("level", "SEVERE", True, "Claude"))
        self.assertEqual(ev["headline"], "Wind warning tomorrow; router security update advised")
        self.assertNotIn("\n", ev["speech"])

    def test_the_mornings_too_without_a_change(self):
        self.fake([self.claude()])
        server.make_briefing()
        ev = self.ha.events_of("dads_army_briefing")[0]
        self.assertIsNone(ev["change"])   # so the blueprint leaves it for the morning sitrep
        self.assertTrue(ev["speech"].startswith("Dads Army. The daily briefing. Local: Normal"))

    def test_never_what_gemini_wrote(self):
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "google", "keys": {"google": "AIza-test-key-0123456789"}})
        self.fake([gemini_answer()])
        server.make_briefing("level", change=change())
        ev = self.ha.events_of("dads_army_briefing")[0]
        self.assertEqual(ev["speech"], "Dads Army. The daily briefing, written again after the alert level went up to "
                                       "Severe, is ready to read in Dads Army.")
        self.assertEqual((ev["headline"], ev["written_by"]), ("", "Gemini"))

    def test_the_sitrep_says_why_it_was_written_again(self):
        b = {"config": {"on": True}, "available": True, "latest": morning(change=change(to="MODERATE", level=2, previous=4))}
        words = server.sitrep_words(server.summary(), {"on": False}, b, today=TODAY)
        self.assertIn("The daily briefing, written again after the alert level went down to Moderate.", words)


class BlueprintTest(AppTest):
    def test_the_new_briefing_is_said(self):
        with open(BLUEPRINT, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("event_type: dads_army_briefing", text)
        self.assertIn("want_briefing: !input briefing", text)
        self.assertIn("trigger.event.data.change is mapping", text)
        self.assertIn("{{ trigger.event.data.speech }}", text)
        self.assertIn("d.new_briefing and want_briefing", text)
