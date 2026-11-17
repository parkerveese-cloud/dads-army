"""The rest of the UK (1.15.0): the regional providers behind the warnings and the wider picture. Scotland (SEPA),
Wales (Natural Resources Wales), Northern Ireland (NIE Networks, NI Water), Electricity North West and more water
companies, each only for the homes it covers. Stand-in feeds in the shapes the real ones had on 17 November 2026,
and homes in city centres. No internet."""
import datetime as dt
import json

import feeds
import test_live
from feeds import (BELFAST, BIRMINGHAM, CARDIFF, GLASGOW, LONDON, MANCHESTER, PLYMOUTH, WHITBY, FakeFeeds,
                   regional_routes, regional_urls, wider_routes, wider_urls)
from support import AppTest, server

NOW = dt.datetime.now(dt.timezone.utc)
CARLISLE = (54.892, -2.932)   # England, near Scotland


def home(p):
    return {"lat": p[0], "lon": p[1]}


class WhereHomeIsTest(AppTest):
    def test_nations(self):
        for p, want in ((LONDON, "england"), (WHITBY, "england"), (BIRMINGHAM, "england"), (MANCHESTER, "england"),
                        (PLYMOUTH, "england"), (CARLISLE, "england"), (GLASGOW, "scotland"), (CARDIFF, "wales"),
                        (BELFAST, "northern ireland"), ((60.15, -1.15), "scotland"), ((53.3, -4.4), "wales"),
                        ((53.19, -2.89), "england"), ((55.07, -3.6), "scotland"),
                        ((53.35, -6.26), ""), ((54.2, -4.5), ""), ((48.86, 2.35), "")):   # Dublin, Isle of Man, Paris
            self.assertEqual(server.uk_nation(*p), want, p)
        self.assertEqual(server.home_nation(None), "")

    def test_kintyre_is_scotland(self):
        for p in ((55.32, -5.64), (55.30, -5.75), (55.425, -5.605), (55.28, -5.58)):   # Southend, the Mull, Campbeltown
            self.assertEqual(server.uk_nation(*p), "scotland", p)
            self.assertEqual(server.dno_area(*p), 17, p)
        for p in ((55.20, -6.24), (55.29, -6.20), (54.85, -5.82), (54.38, -5.55)):   # Ballycastle, Rathlin, Larne
            self.assertEqual(server.uk_nation(*p), "northern ireland", p)

    def test_covers_reaches_over_a_border(self):
        self.assertTrue(server.covers(home(GLASGOW), ("scotland",)))
        self.assertFalse(server.covers(home(LONDON), ("scotland",), 25))
        self.assertTrue(server.covers(home(CARLISLE), ("scotland",), 25))   # Scotland's gauges reach over the border
        self.assertFalse(server.covers(None, ("wales",), 25))

    def test_licence_areas(self):
        for p, want in ((LONDON, 12), (MANCHESTER, 16), (GLASGOW, 18), (CARDIFF, 21), (WHITBY, 15), (BIRMINGHAM, 14),
                        (PLYMOUTH, 22), (BELFAST, "ni"), ((57.478, -4.224), 17), ((53.35, -6.26), None)):
            self.assertEqual(server.dno_area(*p), want, p)
        self.assertEqual(server.DNO_NAMES[server.dno_area(*GLASGOW)], "SP Energy Networks")
        self.assertEqual(server.DNO_NAMES[server.dno_area(*WHITBY)], "Northern Powergrid")
        self.assertTrue(server.dno_covers({"lat": 53.55, "lon": -1.95}, {15, 23}, 10))   # near Yorkshire's edge
        self.assertFalse(server.dno_covers(home(MANCHESTER), {15, 23}, 10))

    def test_grid_conversions(self):
        lat, lon = server.bng_to_latlon(651409.903, 313177.270)   # the Ordnance Survey's worked example
        self.assertAlmostEqual(lat, 52.65757, places=4)
        self.assertAlmostEqual(lon, 1.71792, places=4)
        lat, lon = server.ig_to_latlon(333770, 374061)            # Belfast, on the Irish Grid
        self.assertAlmostEqual(lat, BELFAST[0], places=2)
        self.assertAlmostEqual(lon, BELFAST[1], places=2)

    def test_uk_times(self):
        def utc(v):
            return server.iso_utc(server.uk_local_to_utc(v))
        self.assertEqual(utc("2026-07-01T10:00:00"), "2026-07-01T09:00:00+00:00")        # BST, no zone given
        self.assertEqual(utc("2026-11-17T08:30:00"), "2026-11-17T08:30:00+00:00")        # GMT
        self.assertEqual(utc("2026-03-29T02:30:00"), "2026-03-29T01:30:00+00:00")        # just after the clocks change
        self.assertEqual(utc("2026-07-01T10:00:00Z"), "2026-07-01T10:00:00+00:00")       # says it's UTC: kept
        self.assertEqual(utc("2026-07-01T10:00:00+01:00"), "2026-07-01T09:00:00+00:00")
        self.assertEqual(utc(1794909600000), "2026-11-17T10:00:00+00:00")               # epoch milliseconds (ArcGIS)
        self.assertEqual(utc("1794909600"), "2026-11-17T10:00:00+00:00")                # epoch seconds
        self.assertIsNone(server.uk_local_to_utc("nonsense"))

    def test_met_office_region_within_home_nation(self):
        self.assertEqual(server.guess_region(home(CARDIFF)), "wl")   # not the South West, however near Bristol is
        self.assertEqual(server.guess_region(home(GLASGOW)), "st")
        self.assertEqual(server.guess_region(home(BELFAST)), "ni")
        self.assertEqual(server.guess_region(home(PLYMOUTH)), "sw")
        self.assertEqual(server.guess_region({"lat": 55.0, "lon": -3.6}), "dg")
        self.assertEqual(server.MET_NAME["dg"], "Dumfries, Galloway, Lothian & Borders")   # as the feed names it
        rss = ('<?xml version="1.0"?><rss version="2.0"><channel><item><title>Yellow warning of snow affecting Dumfries, '
               'Galloway, Lothian &amp; Borders</title><description>Yellow warning of snow affecting Dumfries, Galloway, '
               'Lothian &amp; Borders: Scottish Borders valid from 0000 Tue to 1100 Tue</description></item></channel></rss>')
        self.assertEqual(len(server.parse_met(rss.encode(), server.MET_NAME["dg"])), 1)


class FloodsTest(AppTest):
    def test_sepa(self):
        got = server.parse_sepa_floods(feeds.sepa_floods(), home(GLASGOW), 20, "fwa_name")
        self.assertEqual([(i["severity"], i["title"], i["by"], i["area"]) for i in got],
                         [(2, "Flood warning: White Cart Water at Pollokshaws", "SEPA", "Glasgow City")])
        self.assertLessEqual(got[0]["distance_km"], 2)
        self.assertTrue(got[0]["issued"].startswith(ago_day(hours=2)))   # ArcGIS's epoch milliseconds
        alerts = server.parse_sepa_floods(feeds.sepa_alerts(), home(GLASGOW), 1, "name")
        self.assertEqual([(i["severity"], i["title"], i["distance_km"]) for i in alerts],
                         [(1, "Flood alert: Glasgow and Clyde", 0)])     # home's inside it, whatever the distance
        self.assertEqual(server.parse_sepa_floods(feeds.sepa_floods(), home(GLASGOW), 1, "fwa_name"), [])
        with self.assertRaises(ValueError):
            server.parse_sepa_floods(b"[]", home(GLASGOW), 20, "fwa_name")   # a list, not the map's answer

    def test_natural_resources_wales(self):
        got = server.parse_nrw_floods(feeds.nrw_floods(), home(CARDIFF), 20)
        self.assertEqual([(i["severity"], i["title"], i["by"]) for i in got],
                         [(2, "Flood warning: River Taff at Cardiff", "Natural Resources Wales")])
        self.assertEqual(got[0]["distance_km"], 0)
        self.assertEqual(got[0]["url"], "https://flood-warning.naturalresources.wales/Detail/101WAF1/")
        with self.assertRaises(ValueError):
            server.parse_nrw_floods(b"<html>a new design</html>", home(CARDIFF), 20)

    def test_severity_words(self):
        self.assertEqual([server.flood_severity(x) for x in ("1", 2, "Flood Alert", "Severe Flood Warning", "Flood Warning",
                                                             "Warning no longer in force", None, "", 4)],
                         [3, 2, 1, 3, 2, None, None, None, None])


def ago_day(**kw):
    return (NOW - dt.timedelta(**kw)).date().isoformat()


class RiversAndRainTest(AppTest):
    def test_sepa_rivers(self):
        st, lv = server.parse_sepa_rivers(feeds.sepa_rivers(), home(GLASGOW))
        self.assertEqual([s["id"] for s in st], ["sepa-84001", "sepa-84013"])   # not the tide gauge, or the Spey
        items, r = server.rivers_live(st, lv, {}, home(GLASGOW), NOW)
        self.assertEqual([(x["river"], x["state"]) for x in r["stations"]], [("Kelvin", "normal"), ("White Cart Water", "high")])
        self.assertEqual(r["stations"][1]["url"], "https://waterlevels.sepa.org.uk/Station/84013")
        self.assertEqual([(i["severity"], i["by"]) for i in items], [(1, "SEPA")])
        self.assertIn("White Cart Water at Overlee", items[0]["title"])
        with self.assertRaises(ValueError):
            server.parse_sepa_rivers(b'{"error": "down"}', home(GLASGOW))

    def test_sepa_and_nrw_rain_gauges(self):
        self.assertEqual(server.parse_sepa_rain_stations(feeds.sepa_rain_stations())[0], ["111", "Glasgow gauge", 55.87, -4.29])
        self.assertEqual(server.parse_nrw_rain_stations(feeds.nrw_rain_stations(), feeds.nrw_rain_measures()),
                         [["H1 Rainfall Total 15min", "Llandaff", 51.495, -3.215]])   # the river gauge isn't rain
        rows = json.loads(feeds.sepa_rain())[0]["data"]
        self.assertEqual(server.rain_totals(rows, NOW), (2.0, 7.0))   # the 9-day-old reading is left out
        with self.assertRaises(ValueError):
            server.parse_sepa_rain_stations(b'{"type": "error"}')


class ForecastTest(AppTest):
    def test_scottish_flood_forecast(self):
        items, r = server.sff_live(feeds.sff())
        self.assertEqual((r["risk"], r["word"], r["days"]), ("MEDIUM", "Flooding possible", 3))
        self.assertEqual([(i["severity"], i["title"]) for i in items],
                         [(1, "Minor river flooding is possible in the west on Wednesday (Scottish Flood Forecast)")])
        self.assertEqual(r["url"], "https://scottishfloodforecast.sepa.org.uk?d=new")
        items, r = server.sff_live(feeds.sff(minor=False))   # only the older, quiet one
        self.assertEqual((items, r["risk"], r["word"]), ([], "VERY LOW", "No flooding expected"))

    def test_no_open_forecast_for_wales(self):
        covered, why = server.source_covers("floodrisk", {}, home(CARDIFF))
        self.assertEqual((covered, "Wales" in why), (False, True))   # "Not for your area", not failing


class PowerTest(AppTest):
    def test_electricity_north_west(self):
        cuts = server.parse_enwl(feeds.enwl())
        self.assertEqual([(c["ref"], c["customers"], c["planned"]) for c in cuts], [("INC 1", 126, False)])   # one live
        items, r = server.power_live(cuts, home(MANCHESTER))
        self.assertEqual((r["count"], r["near"]), (1, 1))
        self.assertEqual(items[0]["severity"], 2)
        self.assertIn("Electricity North West", items[0]["text"])
        with self.assertRaises(ValueError):
            server.parse_enwl(b"[]")

    def test_nie_networks(self):
        cuts = server.parse_nie(feeds.nie(), NOW)   # the finished planned job and the one with no place are left out
        self.assertEqual([(c["ref"], c["customers"]) for c in cuts], [("5950522", 17)])
        self.assertTrue(cuts[0]["started"].endswith("08:05:00"))
        items, r = server.power_live(cuts, home(BELFAST))
        self.assertLess(r["cuts"][0]["km"], 0.5)
        self.assertEqual(items[0]["severity"], 2)

    def test_northern_powergrid_uses_the_nearest_row(self):
        rows = [{"reference": "INCD-9", "natureofoutage": "Localised Fault", "totalconfirmedpowercut": 30,
                 "totalpredictedpowercut": 0, "lat": WHITBY[0] + 0.08, "lng": WHITBY[1], "postcode": ["YO21 1AA"]},   # 9 km
                {"reference": "INCD-9", "natureofoutage": "Localised Fault", "totalconfirmedpowercut": 30,
                 "totalpredictedpowercut": 0, "lat": WHITBY[0] + 0.001, "lng": WHITBY[1], "postcode": ["YO21 1AB"]}]
        items, r = server.power_live(server.parse_npg(json.dumps(rows).encode()), home(WHITBY))
        self.assertLess(r["cuts"][0]["km"], 0.5)   # not the 9 km of its first row
        self.assertEqual(len(items), 1)


class WaterTest(AppTest):
    def test_the_company_is_chosen_not_guessed(self):
        self.assertEqual(server.water_company({}, home(BIRMINGHAM)), "")   # much of it is Severn Trent, not South Staffs
        self.assertEqual(server.water_company({}, home(WHITBY)), "")
        self.assertEqual(server.water_company({}, home(BELFAST)), "NI Water")   # everyone's, in Northern Ireland
        self.assertEqual(server.water_company({"water_co": "Thames Water"}, home(BELFAST)), "Thames Water")   # a choice wins
        self.assertEqual(server.water_coverage({}, home(BELFAST)), (True, ""))
        self.assertEqual(server.water_coverage({"water_co": "Yorkshire Water"}, home(WHITBY)), (True, ""))

    def test_one_report_a_little_way_off_isnt_yours(self):
        def report(lat, lon, kind="No water"):
            return {"attributes": {"JobGroup__c": "Supply", "JobType__c": kind, "Region__c": "S",
                                   "ReportedDate__c": int(NOW.timestamp() * 1000)}, "geometry": {"x": lon, "y": lat}}

        def run(*rs):
            reports = server.aptumo_reports(json.dumps({"features": list(rs)}).encode(), "S")
            return server.water_live(reports, "South Staffs Water", home(BIRMINGHAM), NOW)
        items, r = run(report(52.4976, -1.9026))                                    # 2 km north
        self.assertEqual((items, r["close"]), ([], 1))
        items, r = run(report(52.4976, -1.9026), report(52.4616, -1.9026, "Low pressure"))   # 2 km north and south
        self.assertEqual(sorted(i["severity"] for i in items), [1, 2])
        items, r = run(report(52.4850, -1.9026))                                    # 600 m
        self.assertEqual([i["severity"] for i in items], [2])

    def test_yorkshire_water(self):
        reports = server.yorkshire_reports(feeds.yorkshire())   # the finished leak and the roadworks are left out
        self.assertEqual([(x["group"], x["what"]) for x in reports],
                         [("supply", "No water or low water pressure"), ("quality", "Your water may look different")])
        items, r = server.water_live(reports, "Yorkshire Water", home(WHITBY), NOW)
        self.assertEqual([(i["severity"], i["by"]) for i in items], [(2, "Yorkshire Water")])
        self.assertTrue(items[0]["title"].startswith("No water or low water pressure reported"))
        self.assertEqual(r["supply"], 1)   # the one far away isn't listed

    def test_south_west_water(self):
        reports = server.sww_reports(feeds.southwest(), NOW)
        self.assertEqual([(x["group"], x["place"]) for x in reports],
                         [("supply", "Union Street, Plymouth, PL1 2AB"), ("leak", "")])   # the street said once
        items, r = server.water_live(reports, "South West Water", home(PLYMOUTH), NOW)
        self.assertEqual([i["severity"] for i in items], [2])   # home is inside the job's outline ([lon, lat] points)
        self.assertEqual(r["reports"][0]["where"], "Union Street, Plymouth, PL1 2AB")
        self.assertNotIn("Union Street", items[0]["title"])

    def test_south_west_waters_next_day_23_59_is_a_stand_in(self):
        def job(start, end):
            return {"categoryTitle": "Planned Interruption", "coordinatesString": "%s %s" % PLYMOUTH,
                    "description": "<P>Off.</P>", "address": "Plymouth", "startDate": start, "endDate": end}
        day = dt.datetime(2026, 11, 17, 10, 0, tzinfo=dt.timezone.utc)
        data = json.dumps({"serviceData": [job("2026-11-16T10:00:00+00:00", "2026-11-17T23:59:00+00:00"),   # yesterday's
                                           job("2026-11-17T09:30:00+00:00", "2026-11-18T23:59:00+00:00"),   # today's
                                           job("2026-11-12T15:49:00+00:00", "2026-11-18T23:59:00+00:00"),   # days long
                                           job("2026-11-16T09:30:00+00:00", "2026-11-16T13:30:00+00:00")]}).encode()
        self.assertEqual([server.iso_utc(x["when"])[:10] for x in server.sww_reports(data, day)], ["2026-11-17", "2026-11-12"])

    def test_ni_water(self):
        reports = server.niwater_reports(feeds.niwater())   # the closed one is left out
        self.assertEqual([x["what"] for x in reports], ["Water Supply Interruption", "Planned Maintenance"])
        self.assertEqual(server.iso_utc(reports[0]["when"]), "2026-11-17T08:15:00+00:00")   # its own start time
        self.assertEqual(server.iso_utc(reports[1]["when"]), "2026-11-17T09:05:00+00:00")   # none given: when updated
        items, r = server.water_live(reports, "NI Water", home(BELFAST), NOW)
        self.assertEqual([i["severity"] for i in items], [2])
        self.assertEqual(len(r["reports"]), 1)   # Newry is too far to list

    def test_bournemouth_water_has_its_own_feed(self):
        server.FEED_URLS.update({"water_bournemouth": "bw", "water_southwest": "sww"})
        asked = []
        server.http_get = lambda url, **kw: asked.append(url) or feeds.southwest()
        self.assertTrue(server.water_reports("Bournemouth Water", NOW))
        self.assertEqual(asked, ["bw"])


class CoverageTest(AppTest):
    def test_sources_that_dont_reach_home(self):
        cfg = {"water_co": ""}
        limited = ("floods", "rivers", "floodrisk", "rain", "ground", "drought", "grid", "gridnow", "gridstress")
        for p, off in ((BELFAST, set(limited)), (CARDIFF, {"floodrisk", "ground", "drought"}), (GLASGOW, {"ground", "drought"}),
                       (LONDON, set()), (None, set())):
            for key in limited + ("power", "air", "threat"):
                covered, why = server.source_covers(key, cfg, home(p) if p else None)
                self.assertEqual(not covered, key in off, (p, key))
                self.assertEqual(bool(why), key in off, (p, key))
        self.assertIn("Northern Ireland", server.source_covers("grid", cfg, home(BELFAST))[1])


class RegionalRunTest(AppTest):
    """Whole checks, as the warnings loop does them, for homes in each nation: each regional provider is asked only
    for the homes it covers, nothing is asked for that hasn't a stand-in, and nothing about home is sent."""

    def setUp(self):
        super().setUp()
        tl = test_live
        self.feeds = FakeFeeds(dict({"rivers": (tl.readings, "application/json"), "stations": (tl.stations, "application/json"),
                                     "ukpn": (tl.ukpn, "application/json"), "nged": (tl.nged, "text/csv"),
                                     "ssen": (tl.ssen, "application/json"), "npg": (tl.npg, "application/json"),
                                     "grid": (tl.syswarn, "application/json")}, **dict(wider_routes(), **regional_routes())))
        b = self.feeds.base
        server.FEED_URLS.update(self.feeds.urls())
        server.FEED_URLS.update({"rivers": b + "rivers", "river_stations": b + "stations", "power_ukpn": b + "ukpn",
                                 "power_nged": b + "nged", "power_ssen": b + "ssen", "power_npg": b + "npg",
                                 "grid": b + "grid?from={start}&to={end}"})
        server.FEED_URLS.update(wider_urls(b))
        server.FEED_URLS.update(regional_urls(b))

    def tearDown(self):
        self.feeds.close()
        super().tearDown()

    def run_for(self, p, **kw):
        on = ("floods", "rivers", "power", "water", "floodrisk", "rain", "ground", "drought", "grid", "gridnow", "gridstress")
        server.api_warnings_set(dict({"on": True, "lat": p[0], "lon": p[1],
                                      "sources": dict((k, k in on) for k, _, _ in server.WARN_SOURCES)}, **kw), {})
        server.warnings_run()
        self.assertEqual(self.feeds.missed, [], "every feed asked for has a stand-in: nothing goes to the internet")
        return server.warn_public()

    def asked(self, *keys):
        return [r["path"] for r in self.feeds.log if r["path"].strip("/").split("/")[0].split("?")[0] in keys]

    def test_glasgow(self):
        w = self.run_for(GLASGOW)
        rows = dict((r["key"], r) for r in w["live_rows"])
        self.assertEqual(sorted(w["unavailable"]), ["drought", "ground", "roads", "supply", "water"])   # England's, UKPN's, and no company chosen
        self.assertEqual(w["unavailable"]["water"], server.WATER_CHOOSE)
        self.assertEqual([i["title"] for i in w["items"] if i["source"] == "floods"],
                         ["Flood warning: White Cart Water at Pollokshaws", "Flood alert: Glasgow and Clyde"])
        self.assertIn("White Cart Water at Overlee", rows["rivers"]["text"])
        self.assertEqual(rows["floodrisk"]["text"], "Flooding possible · next 3 days")
        self.assertEqual(w["live"]["rain"]["by"], "SEPA")
        self.assertIn("SP Energy Networks has no live feed", rows["power"]["text"])
        self.assertEqual(self.asked("nrwfloods", "nrwrainst", "enwl", "nie", "stations", "floods"), [])   # not for Glasgow
        self.assertTrue(all(s["ok"] for s in w["sources"].values()), w["sources"])
        for req in self.feeds.log:   # rain is asked for by gauge, never by where home is
            for needle in ("55.8", "-4.2", "lat=", "lon="):
                self.assertNotIn(needle, req["path"].lower(), req["path"])

    def test_cardiff(self):
        w = self.run_for(CARDIFF)
        self.assertEqual([(i["title"], i["by"]) for i in w["items"] if i["source"] == "floods"],
                         [("Flood warning: River Taff at Cardiff", "Natural Resources Wales")])
        self.assertEqual(w["live"]["rain"]["by"], "Natural Resources Wales")
        self.assertEqual(w["live"]["rain"]["day_mm"], 2.0)
        self.assertIn("measureId=H1+Rainfall+Total+15min", self.asked("nrwrain")[0])
        self.assertEqual(self.asked("sepafloods", "separivers", "sff", "enwl", "nie"), [])
        self.assertEqual(w["region"], "wl")

    def test_belfast(self):
        w = self.run_for(BELFAST)
        self.assertEqual(sorted(w["unavailable"]), ["drought", "floodrisk", "floods", "grid", "gridnow", "gridstress",
                                                    "ground", "rain", "rivers", "roads", "supply"])
        self.assertEqual(sorted(r["key"] for r in w["live_rows"]), ["power", "water"])   # NI Water: not guessed, known
        self.assertEqual(w["live"]["water"]["company"], "NI Water")
        self.assertTrue([i for i in w["items"] if i["source"] == "power" and "NIE Networks" in i["text"]])
        self.assertEqual(self.asked("floods", "stations", "rainst", "floodrisk", "ci", "margin", "grid"), [])   # not fetched
        self.assertEqual(set(w["sources"]), {"power", "water"})   # nothing shows as failing

    def test_manchester_and_whitby(self):
        self.run_for(MANCHESTER)
        self.assertEqual(len(self.asked("enwl")), 1)
        self.assertEqual(self.asked("nie", "yorkshire"), [])
        self.feeds.log[:] = []
        w = self.run_for(WHITBY, water_co="Yorkshire Water")
        self.assertEqual(self.asked("enwl", "nie", "sepafloods", "nrwfloods"), [])
        self.assertEqual(len(self.asked("yorkshire")), 1)
        self.assertTrue([i for i in w["items"] if i["source"] == "water" and i["severity"] == 2])

    def test_a_neighbours_feed_failing_isnt_homes(self):
        self.feeds.broken["separivers"] = 503   # Carlisle is in England: SEPA's gauges are a neighbour's
        w = self.run_for(CARLISLE)
        self.assertTrue(w["sources"]["rivers"]["ok"])
        self.assertTrue(self.asked("separivers"))
        self.feeds.log[:] = []
        w = self.run_for(GLASGOW)   # ...but Glasgow's own
        self.assertFalse(w["sources"]["rivers"]["ok"])
        self.assertIn("503", w["sources"]["rivers"]["error"])

    def test_one_network_down_is_said(self):
        self.feeds.broken["enwl"] = 500
        w = self.run_for(MANCHESTER)
        self.assertTrue(w["sources"]["power"]["ok"])
        self.assertEqual(w["live"]["power"]["failed"], ["Electricity North West"])
        self.assertIn("couldn't check Electricity North West", [r for r in w["live_rows"] if r["key"] == "power"][0]["text"])

    def test_the_briefing_isnt_told_where_home_is(self):
        self.run_for(PLYMOUTH, water_co="South West Water")
        known = server.brief_known()
        self.assertIn("Water supply", known)
        for needle in ("Union Street", "PL1", "km away", "km NE", "Overlee"):
            self.assertNotIn(needle, known)
