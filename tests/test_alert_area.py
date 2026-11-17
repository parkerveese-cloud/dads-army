"""What raises the household alert level: an Emergency Alert only for home's area, and a disaster abroad only
if it can reach a UK home. No internet: home's area is set by hand."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dadsarmy"))

import server  # noqa: E402

HOME = {"lat": 51.5007, "lon": -0.1246}   # Westminster


class TestAlertArea(unittest.TestCase):
    def setUp(self):
        server.HOME_PLACES.update(key=server._places_key(HOME), names=["westminster", "cities of london and westminster",
                                                                       "london"], nation="england", busy=False, at=1e12)

    def tearDown(self):
        server.HOME_PLACES.update(key=None, names=[], nation="", busy=False, at=0.0)

    def test_emergency_alert_for_home(self):
        self.assertTrue(server.alert_covers_home("London", HOME))
        self.assertTrue(server.alert_covers_home("Westminster and surrounding areas", HOME))
        self.assertTrue(server.alert_covers_home("United Kingdom", HOME))
        self.assertTrue(server.alert_covers_home("England", HOME))

    def test_emergency_alert_elsewhere(self):
        self.assertFalse(server.alert_covers_home("North Yorkshire", HOME))
        self.assertFalse(server.alert_covers_home("South West England", HOME))
        self.assertFalse(server.alert_covers_home("Wales", HOME))

    def test_unknown_home_counts_every_alert(self):
        server.HOME_PLACES.update(key=None, names=[], busy=True)   # a lookup in flight
        self.assertTrue(server.alert_covers_home("North Yorkshire", HOME))

    def test_disasters(self):
        quake_norway = {"area": "Norway", "distance_km": 950, "event": "EQ"}
        self.assertFalse(server.disaster_reaches_uk(quake_norway))
        self.assertTrue(server.disaster_reaches_uk({"area": "Ireland", "distance_km": 450, "event": "FL"}))
        self.assertTrue(server.disaster_reaches_uk({"area": "France", "distance_km": 250, "event": "WF"}))
        self.assertTrue(server.disaster_reaches_uk({"area": "Iceland", "distance_km": 1800, "event": "VO"}))
        self.assertFalse(server.disaster_reaches_uk({"area": "Greece", "distance_km": 2400, "event": "VO"}))

    def test_gdacs_event_type(self):
        rss = (b'<?xml version="1.0"?><rss xmlns:gdacs="http://www.gdacs.org" xmlns:georss="http://www.georss.org/georss">'
               b'<channel><item><title>Orange earthquake in Norway</title><link>https://www.gdacs.org/x</link>'
               b'<gdacs:iscurrent>true</gdacs:iscurrent><gdacs:alertlevel>Orange</gdacs:alertlevel>'
               b'<gdacs:eventtype>EQ</gdacs:eventtype><gdacs:country>Norway</gdacs:country>'
               b'<georss:point>60.4 5.3</georss:point></item></channel></rss>')
        items = server.parse_gdacs(rss, HOME, 2000)
        self.assertEqual(items[0]["event"], "EQ")
        self.assertFalse(server.disaster_reaches_uk(items[0]))


if __name__ == "__main__":
    unittest.main()
