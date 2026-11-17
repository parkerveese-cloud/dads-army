"""1.21.0: nothing that says where home is goes out until it's ticked.

Only alerts for my area (which sends home's location, rounded to about 100 m, to postcodes.io), rainfall and
groundwater near you (which ask for the nearest gauges and boreholes by name) all start off, including for
someone who already had warnings and Emergency Alerts switched on."""
from feeds import FakeFeeds
from support import AppTest, server

HOME = {"lat": 51.5007, "lon": -0.1246}   # Westminster; the stand-in says North Yorkshire, which is the point


class LocationOptInTest(AppTest):

    def setUp(self):
        super().setUp()
        self.feeds = FakeFeeds()
        server.FEED_URLS.update(self.feeds.urls())
        server.HOME_PLACES.update(key=None, names=[], nation="", busy=False, at=0.0)

    def tearDown(self):
        self.feeds.close()
        server.HOME_PLACES.update(key=None, names=[], nation="", busy=False, at=0.0)
        super().tearDown()

    def asked_where(self):
        return [q["path"] for q in self.feeds.log if q["path"].startswith("/places")]

    def warnings(self, **extra):
        body = {"on": True, "lat": HOME["lat"], "lon": HOME["lon"],
                "sources": {k: k == "govalerts" for k, _, _ in server.WARN_SOURCES}}
        body.update(extra)
        server.api_warnings_set(body, {})
        server.warnings_run()

    def test_off_to_begin_with(self):
        cfg = server.warn_cfg()
        self.assertFalse(cfg["alert_area"])
        self.assertFalse(cfg["sources"]["rain"])
        self.assertFalse(cfg["sources"]["ground"])
        self.assertTrue(cfg["sources"]["govalerts"])   # Emergency Alerts themselves are a national feed

    def test_settings_saved_before_1_21_keep_it_off(self):
        """Warnings switched on in 1.14.0, with every source it had: rainfall wasn't one, so it stays off."""
        with server.tx() as db:
            server.set_setting_raw(db, "warnings", {"on": True, "lat": HOME["lat"], "lon": HOME["lon"],
                                                    "sources": {"govalerts": True, "metoffice": True, "rivers": True}})
        cfg = server.warn_cfg()
        self.assertEqual((cfg["alert_area"], cfg["sources"]["rain"], cfg["sources"]["govalerts"]), (False, False, True))

    def test_emergency_alerts_on_their_own_send_nothing(self):
        self.warnings()
        self.assertTrue(any(q["path"].startswith("/govalerts") for q in self.feeds.log))
        self.assertEqual(self.asked_where(), [])
        self.assertTrue(server.alert_covers_home("London", HOME))   # every alert counts, as before 1.15.0
        self.assertTrue(server.alert_covers_home("Cornwall", HOME))

    def test_ticked_it_asks_once_and_forgets_when_unticked(self):
        self.warnings(alert_area=True)
        self.assertEqual(len(self.asked_where()), 1)
        self.assertIn("lat=51.501", self.asked_where()[0])   # rounded to about 100 m
        self.assertFalse(server.alert_covers_home("Cornwall", HOME))
        server.warnings_run()
        self.assertEqual(len(self.asked_where()), 1)   # once, not every check
        self.warnings(alert_area=False)
        self.assertEqual(server.HOME_PLACES["names"], [])
        self.assertTrue(server.alert_covers_home("Cornwall", HOME))
        self.assertEqual(len(self.asked_where()), 1)

    def test_shown_in_the_settings(self):
        self.assertIn("alert_area", server.warn_public()["config"])
        server.api_warnings_set({"alert_area": True}, {})
        self.assertTrue(server.warn_cfg()["alert_area"])

    def test_yes_or_no_only(self):
        with self.assertRaises(server.ApiError):
            server.api_warnings_set({"alert_area": "yes"}, {})
