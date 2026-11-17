"""1.20.0: the grid now, fuller. Home's own region's carbon intensity (the region worked out here from home's electricity
network, so only its number is sent) and the greenest 3 hours in the next day. Stand-in feeds only."""
import datetime as dt

from feeds import GREEN_FROM, LONDON, NOW, FakeFeeds, _halfhours, wider_routes, wider_urls
from support import AppTest, server

HOME = {"lat": LONDON[0], "lon": LONDON[1]}


class RegionTest(AppTest):
    def test_worked_out_here(self):
        self.assertEqual(server.ci_region(HOME), 13)                                # London
        self.assertEqual(server.ci_region({"lat": 55.861, "lon": -4.251}), 2)       # Glasgow: South Scotland
        self.assertEqual(server.ci_region({"lat": 53.479, "lon": -2.245}), 3)       # Manchester: North West England
        self.assertIsNone(server.ci_region({"lat": 54.597, "lon": -5.930}))         # Belfast: not Britain's grid
        self.assertIsNone(server.ci_region(None))
        self.assertEqual(sorted(server.CI_REGION_BY_DNO.values()), list(range(1, 15)))


class GreenestTest(AppTest):
    def test_the_lowest_three_hours(self):
        g = server.greenest_window(_halfhours(), NOW)
        self.assertEqual(g, {"from": server.iso_utc(GREEN_FROM), "to": server.iso_utc(GREEN_FROM + dt.timedelta(hours=3)),
                             "avg": 40})

    def test_gaps_past_slots_and_odd_shapes(self):
        rows = _halfhours()
        self.assertIsNone(server.greenest_window(rows[:5], NOW))                    # under 3 hours of forecast
        gappy = rows[:12] + rows[13:]                                               # a half hour missing in the green run
        self.assertNotEqual(server.greenest_window(gappy, NOW)["from"], server.iso_utc(GREEN_FROM))
        self.assertIsNone(server.greenest_window(rows, NOW + dt.timedelta(days=3)))  # all in the past
        self.assertIsNone(server.greenest_window([None, {}, {"from": "x", "intensity": {"forecast": "low"}}], NOW))


class FetchTest(AppTest):
    def setUp(self):
        super().setUp()
        self.feeds = FakeFeeds(wider_routes())
        server.FEED_URLS.update(wider_urls(self.feeds.base))

    def tearDown(self):
        self.feeds.close()
        super().tearDown()

    def paths(self, key):
        return [r["path"] for r in self.feeds.log if r["path"].strip("/").split("/")[0].split("?")[0] == key]

    def test_home_region_and_greenest(self):
        items, r = server.fetch_gridnow(NOW, HOME)
        self.assertEqual(r["region"], {"id": 13, "name": "London", "ci": 95, "index": "low", "forecast": True})
        self.assertEqual((r["greenest"]["from"], r["greenest"]["avg"], r["greenest"]["where"]),
                         (server.iso_utc(GREEN_FROM), 40, "London"))
        self.assertEqual(self.paths("ciregion"), ["/ciregion/13"])
        self.assertEqual(len(self.paths("ciregionfw")), 1)
        self.assertEqual(self.paths("cifw"), [])
        for req in self.feeds.log:   # the region's number, never where home is
            for needle in ("51.5", "0.12", "lat=", "lon="):
                self.assertNotIn(needle, req["path"])
        row = server.live_rows({"gridnow": r}, items)[0]
        self.assertTrue(row["text"].startswith("London: 95 g CO2/kWh (low) · greenest 3 hours from "), row["text"])
        self.assertTrue(row["brief"].startswith("140 g CO2/kWh (moderate) · greenest 3 hours from "), row["brief"])

    def test_without_home_or_the_region_its_britain(self):
        items, r = server.fetch_gridnow(NOW, None)
        self.assertNotIn("region", r)
        self.assertEqual(r["greenest"]["where"], "Great Britain")
        self.assertEqual((self.paths("ciregion"), len(self.paths("cifw"))), ([], 1))
        self.feeds.broken.update({"ciregion": 503, "ciregionfw": 503})
        items, r = server.fetch_gridnow(NOW, HOME)   # the region's figures failing doesn't fail the source
        self.assertEqual((r["ci"], "region" in r, r["greenest"]["where"]), (140, False, "Great Britain"))
        self.assertEqual(server.live_rows({"gridnow": r}, items)[0]["text"][:24], "140 g CO2/kWh (moderate)")
