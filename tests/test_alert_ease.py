"""1.28.0: the household alert level is less twitchy. A room at 29.9 and 30°C in turn (read every 15 seconds) used to
switch it between MODERATE and SEVERE, with a phone alert, a spoken sitrep and a new briefing each time. Now a reading
has to come back past its line before it stops counting, and the level goes up at once but only comes down once
what raised it has been gone, or lower, for half an hour. Alarms and the stores count as they are now."""
from support import AppTest, server

HOUR = 3600.0


def temp(v, name="Loft"):
    return {"entity_id": "sensor.t", "name": name, "state": str(v), "value": str(v), "unit": "°C",
            "device_class": "temperature", "ok": True}


def alarm(on):
    return {"entity_id": "binary_sensor.smoke", "name": "Hall", "state": "on" if on else "off", "value": None,
            "unit": "", "device_class": "smoke", "ok": True}


def stores(water=10.0, warnings=()):
    return {"warnings": {"enabled": True, "items": list(warnings)}, "people": 2, "food_days": 10.0,
            "water_days": water, "resilience": {"areas": []}}


class EaseTest(AppTest):

    def setUp(self):
        super().setUp()
        self.mem, self.t = {"band": {}, "held": {}}, 1000000.0

    def look(self, s=None, wait=0.0, **readings):
        self.t += wait
        return server.assess(s or stores(), {"readings": readings}, self.mem, self.t)

    def test_a_room_at_the_line_doesnt_flap(self):
        self.assertEqual(self.look(indoor_temp=[temp(30.0)])["level"], 3)
        for v in (29.9, 30.0, 29.8, 29.1):   # a degree's grace
            sit = self.look(wait=15, indoor_temp=[temp(v)])
            self.assertEqual(sit["level"], 3, v)
            self.assertEqual(sit["reasons"][0]["title"], "Warmest room %s°C" % server._f(v))
            self.assertNotIn("easing", sit["reasons"][0])
        sit = self.look(wait=15, indoor_temp=[temp(28.9)])   # cooler: but it only comes down in half an hour
        self.assertEqual(sit["level"], 3)
        self.assertEqual(sit["reasons"][0], {"level": 3, "name": "SUBSTANTIAL", "key": "hot_indoor", "easing": True,
                                             "title": "Warmest room 29.1°C (until just now)"})
        self.assertEqual(len(sit["reasons"]), 1)   # not "Warmest room 28.9°C" as well
        self.assertEqual(self.look(wait=600, indoor_temp=[temp(28.9)])["reasons"][0]["title"],
                         "Warmest room 29.1°C (until 10 minutes ago)")
        sit = self.look(wait=1300, indoor_temp=[temp(28.9)])
        self.assertEqual((sit["level"], sit["reasons"][0]["title"]), (2, "Warmest room 28.9°C"))

    def test_back_up_within_the_half_hour_starts_again(self):
        self.look(indoor_temp=[temp(30.5)])
        self.look(wait=60, indoor_temp=[temp(28)])
        self.assertEqual(self.look(wait=1500, indoor_temp=[temp(30.2)])["level"], 3)
        self.assertEqual(self.look(wait=1500, indoor_temp=[temp(28)])["level"], 3)   # half an hour from the last time
        self.assertEqual(self.look(wait=400, indoor_temp=[temp(28)])["level"], 2)

    def test_it_goes_up_at_once(self):
        self.assertEqual(self.look(indoor_temp=[temp(27.5)])["level"], 2)
        self.assertEqual(self.look(wait=15, indoor_temp=[temp(33)])["level"], 4)

    def test_cold_holds_a_degree_too(self):
        self.assertEqual(self.look(indoor_temp=[temp(11.9)])["level"], 3)
        sit = self.look(wait=15, indoor_temp=[temp(12.8)])
        self.assertEqual((sit["level"], sit["reasons"][0]["title"]), (3, "Coldest room 12.8°C"))
        self.assertEqual(self.mem["band"]["cold_in"], 3)
        self.look(wait=15, indoor_temp=[temp(13.1)])
        self.assertEqual(self.mem["band"]["cold_in"], 2)   # past the grace: the reading's MODERATE now...
        self.assertEqual(self.look(wait=HOUR, indoor_temp=[temp(13.1)])["level"], 2)   # ...and so, later, is the level

    def test_the_lines_themselves_are_as_before(self):
        b = server.band
        self.assertEqual([b(v, ((33, 4), (30, 3), (27, 2)), 0, 1, ">=") for v in (26.9, 27, 30, 33)], [0, 2, 3, 4])
        self.assertEqual([b(v, ((9, 4), (12, 3), (16, 2), (18, 1)), 0, 1, "<") for v in (18, 17.9, 12, 11.9, 8.9)],
                         [0, 1, 2, 3, 4])
        self.assertEqual([b(v, ((-10, 3), (-5, 2)), 0, 1, "<=") for v in (-4.9, -5, -10)], [0, 2, 3])
        self.assertEqual(b(-4.5, ((-10, 3), (-5, 2)), 2, 1, "<="), 2)
        self.assertEqual(b(77, ((80, 2),), 2, 5, ">="), 2)
        self.assertEqual(b(74, ((80, 2),), 2, 5, ">="), 0)

    def test_hot_room_and_low_water_dont_flap_between_moderate_and_severe(self):
        """What happened at home: water for 2.8 days, and a room at 30°C, then 29.9°C, then 30°C..."""
        low = stores(water=2.8)
        levels = [self.look(low, wait=15, indoor_temp=[temp(v)])["level"] for v in (30, 29.9, 30, 29.9, 29.8, 30)]
        self.assertEqual(levels, [4] * 6)
        # Stocking up shows at once: the stores count as they are.
        sit = self.look(stores(water=3.5), wait=15, indoor_temp=[temp(29.9)])
        self.assertEqual((sit["level"], sit["escalated"]), (3, False))

    def test_an_alarm_clears_as_soon_as_it_stops(self):
        self.assertEqual(self.look(smoke_alarm=[alarm(True)])["level"], 5)
        self.assertEqual(self.look(wait=15, smoke_alarm=[alarm(False)])["level"], 1)

    def test_a_warning_missing_from_one_check(self):
        amber = {"source": "metoffice", "severity": 2, "title": "Amber warning of wind"}
        first = self.look(stores(warnings=[amber]))
        self.assertEqual(first["level"], 3)
        sit = self.look(stores(), wait=300)
        self.assertEqual((sit["level"], sit["reasons"][0]["title"]), (3, "Amber warning of wind (until 5 minutes ago)"))
        self.assertEqual(sit["guidance"], first["guidance"])   # its advice (for wind) stays too
        self.assertEqual(self.look(stores(warnings=[amber]), wait=300)["reasons"][0]["title"], "Amber warning of wind")
        self.assertEqual(self.look(stores(), wait=HOUR)["level"], 1)

    def test_a_power_cut_eases_off(self):
        power = {"entity_id": "binary_sensor.mains", "name": "Mains", "state": "off", "value": None, "unit": "",
                 "device_class": "power", "ok": True}
        self.assertEqual(self.look(power=[power])["level"], 3)
        sit = self.look(wait=120, power=[dict(power, state="on")])
        self.assertEqual(sit["level"], 3)
        self.assertTrue(sit["reasons"][0]["title"].endswith("(until 2 minutes ago)"))

    def test_the_summary_remembers(self):
        """summary() keeps its own memory (ALERT_MEM), shared by everything that asks."""
        server.api_settings({"adults": 0}, {})   # no stores to count, so nothing raises it to SEVERE
        with server.HOME_LOCK:
            server.HOME_STATE["readings"] = {"indoor_temp": [temp(30)]}
        try:
            self.assertEqual(server.summary()["situation"]["level"], 3)
            server.HOME_STATE["readings"] = {"indoor_temp": [temp(29.5)]}
            self.assertEqual(server.summary()["situation"]["level"], 3)
            self.assertEqual(server.ALERT_MEM["band"], {"cold_in": 0, "hot_in": 3})
        finally:
            with server.HOME_LOCK:
                server.HOME_STATE["readings"] = {}
