"""Fixes from a regression run against the real feeds (1.15.0), in the stores: another label photo keeps what the first
read, Open Food Facts drinks, storage only for what's eaten, the review's answer and what's sent, estimates kept by a
restore or an undo, kit, and the Emergency Alert and disaster rules. No internet and no real AI."""
import base64
import datetime as dt
import json

from support import AppTest, server

JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8back of the jar").decode()


def answer(obj):
    return {"content": [{"type": "text", "text": json.dumps(obj)}], "usage": {"input_tokens": 1, "output_tokens": 1},
            "stop_reason": "end_turn"}


class StoresTest(AppTest):
    def setUp(self):
        super().setUp()
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "anthropic", "keys": {"anthropic": "test-key"}})
        self.real_post = server._post_json
        self.sent = []

    def tearDown(self):
        server._post_json = self.real_post
        super().tearDown()

    def ai_says(self, obj):
        def post(url, body, headers, timeout=60):
            self.sent.append(body["messages"][0]["content"][-1]["text"])
            return answer(obj)
        server._post_json = post

    def storage(self, iid):
        return server.DB.execute("SELECT storage FROM items WHERE id = ?", (iid,)).fetchone()["storage"]

    def test_another_photo_keeps_the_date_and_the_estimates(self):
        first = server.parse_label_reply(json.dumps({
            "name": "Real Mayonnaise", "size": "400 ml", "grams": 400, "kcal_100g": None, "kcal_100g_typical": 720,
            "category": "food", "unit": "jar", "best_before": "2027-03-31", "open_days": None, "open_days_typical": 90,
            "storage": "ambient"}))
        prompt = server.label_prompt(dict(first))
        self.assertIn('"best_before": "2027-03-31"', prompt)   # the product says "expiry", the prompt "best_before"
        self.assertIn('"size": "400 ml"', prompt)              # ...and "quantity" is "size"
        self.assertIn('"kcal_100g_typical": 720', prompt)      # an estimate goes back as an estimate
        self.assertNotIn('"kcal_100g": 720', prompt)
        self.assertIn('"open_days_typical": 90', prompt)
        self.ai_says({"name": "Real Mayonnaise", "size": None, "grams": None, "kcal_100g": None, "kcal_100g_typical": None,
                      "category": "food", "unit": "jar", "best_before": None, "open_days": None, "open_days_typical": None})
        back = server.api_scan_label({"image": JPEG, "known": dict(first)}, {})["product"]   # no date or energy on the back
        self.assertEqual(back["expiry"], "2027-03-31")
        self.assertEqual((back["kcal_per_unit"], back["open_days"], back["grams"]), (2880, 90, 400.0))
        self.assertEqual(back["ai_guessed"], "kcal_per_unit,open_days")   # still estimates, not read off the pack
        echoed = server.merge_label(server.parse_label_reply(json.dumps({"name": "Real Mayonnaise", "grams": 400, "kcal_100g": 720,
                                                                         "category": "food", "open_days": 90})), dict(first))
        self.assertEqual(echoed["ai_guessed"], "kcal_per_unit,open_days")   # the estimate said back is still one
        panel = server.merge_label(server.parse_label_reply(json.dumps({"name": "Real Mayonnaise", "grams": 400, "kcal_100g": 680,
                                                                        "category": "food"})), dict(first))
        self.assertEqual((panel["kcal_per_unit"], panel["ai_guessed"]), (2720, "open_days"))   # read off the panel

    def test_open_food_facts_drinks_are_drinks(self):
        def product(name, qty, n, unit, tags):
            return server.product_from("5000000000001", {"product_name_en": name, "quantity": qty, "product_quantity": n,
                                                         "product_quantity_unit": unit, "categories_tags": tags})
        rice = product("Long Grain Rice", "1 kg", 1000, "g", ["en:plant-based-foods-and-beverages", "en:rices"])
        self.assertEqual((rice["category"], rice["litres_per_unit"], rice["pack_unit"]), ("food", 0, "g"))   # not 1 L
        coffee = product("Instant Coffee", "200 g", 200, "g", ["en:beverages", "en:hot-beverages", "en:coffees"])
        self.assertEqual((coffee["category"], coffee["litres_per_unit"]), ("food", 0))
        whisky = product("Scotch Whisky", "70 cl", 700, "ml", ["en:beverages", "en:alcoholic-beverages", "en:spirits"])
        self.assertEqual((whisky["category"], whisky["litres_per_unit"]), ("other", 0))
        juice = product("Orange Juice", "1 l", 1000, "ml", ["en:beverages", "en:juices", "en:fruit-juices"])
        self.assertEqual((juice["category"], juice["litres_per_unit"], juice["pack_unit"]), ("drinks", 1.0, "ml"))
        powder = product("Milkshake powder", "500 g", 500, "g", ["en:beverages", "en:milks"])
        self.assertEqual((powder["category"], powder["litres_per_unit"], powder["pack_unit"]), ("drinks", 0, "g"))
        water = product("Still Water", "1.5 l", 1500, "g", ["en:beverages", "en:waters"])
        self.assertEqual((water["category"], water["litres_per_unit"]), ("water", 1.5))
        # A label: litres for a drink, but not one sold by weight.
        tub = server.parse_label_reply(json.dumps({"name": "Hot chocolate", "size": "500 g", "grams": 500, "category": "drinks"}))
        self.assertEqual((tub["litres_per_unit"], tub["pack_unit"]), (0, "g"))
        carton = server.parse_label_reply(json.dumps({"name": "Apple juice", "size": "1 l", "grams": 1000, "category": "drinks"}))
        self.assertEqual((carton["litres_per_unit"], carton["pack_unit"]), (1.0, "ml"))

    def test_storage_only_for_food_drinks_and_pets(self):
        torch = self.add("Head torch", category="power", unit="each", storage="ambient")   # the hidden choice's value
        self.assertEqual(self.storage(torch), "")
        server.api_item_update({"storage": "chilled"}, {}, str(torch))
        self.assertEqual(self.storage(torch), "")
        beans = self.add("Beans", category="food", unit="tin")
        self.assertEqual(self.storage(beans), "ambient")
        server.api_item_update({"category": "other", "storage": "ambient"}, {}, str(beans))   # no longer food
        self.assertEqual(self.storage(beans), "")
        self.assertEqual(server.clean_item({"name": "Dog food", "category": "pets", "storage": "frozen"})["storage"], "frozen")

    def test_a_review_reply_of_the_wrong_shape(self):
        p = server.parse_review_reply
        for sugg in ({"add": "Tinned fruit"}, 3, "Tinned fruit", None, [["Tinned fruit"]], [{"add": ["x"]}]):
            self.assertEqual(p(json.dumps({"summary": "Mostly tins.", "score": 3, "suggestions": sugg}))["suggestions"], [], sugg)
        got = p(json.dumps({"summary": "Mostly tins.", "score": "4.0", "wider": ["a list"],
                            "suggestions": [{"add": "Tinned fruit", "why": {"x": 1}, "category": ["food"]}]}))
        self.assertEqual((got["score"], got["wider"]), (4, ""))
        self.assertEqual(got["suggestions"], [{"add": "Tinned fruit", "why": "", "category": "food"}])
        self.assertIsNone(p(json.dumps({"summary": {"text": "x"}})))
        self.assertIsNone(p(json.dumps({"summary": "Fine", "score": True}))["score"])

    def test_the_review_sends_what_is_in_date_and_counts_what_it_sent(self):
        iid = self.add("Passata (jar)", 1, category="food", unit="jar", kcal_per_unit=120, open_days=5)
        with server.tx() as db:   # opened 10 days ago, "use within 5 days": gone off, whatever the jar's date
            db.execute("UPDATE batches SET expiry = ?, opened_at = ? WHERE item_id = ?",
                       ((dt.date.today() + dt.timedelta(days=200)).isoformat(),
                        (dt.date.today() - dt.timedelta(days=10)).isoformat(), iid))
        self.add("Rice (1kg)", 1, category="food", unit="bag", kcal_per_unit=3500)
        head, lines = server.review_input()
        self.assertEqual([json.loads(x)["name"] for x in lines], ["Rice (1kg)"])
        with server.tx() as db:
            for n in range(server.REVIEW_MAX_LINES + 5):
                iid = server.insert_item(db, server.clean_item({"name": "Tin %03d" % n, "category": "food", "unit": "tin"}),
                                         server.now_iso(), server.now_iso())
                db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at) VALUES (?, 1, NULL, '', ?)",
                           (iid, server.now_iso()))
        self.ai_says({"summary": "A lot of tins.", "score": 3})
        got = server.api_ai_review({}, {})["review"]
        self.assertEqual(got["items"], server.REVIEW_MAX_LINES)   # what was looked at, not 306
        self.assertEqual(self.sent[0].count('"name"'), server.REVIEW_MAX_LINES)

    def test_kit_leaves_out_what_is_eaten_or_drunk(self):
        self.add("Torch", 1, category="power", unit="each", target_qty=2)      # half stocked
        self.add("Squash", 0, category="drinks", unit="bottle", target_qty=4)  # none, but drinks count as days, not kit
        out = server.summary()
        self.assertEqual((out["kit_items"], out["kit_stocked_pct"]), (1, 50))

    def test_restore_and_undo_keep_the_ai_estimates(self):
        self.add("Beef casserole", 1, category="food", unit="tin", kcal_per_unit=600, ai_guessed="kcal_per_unit,open_days")
        backup = json.loads(server.api_backup({}, {}).data.decode("utf-8"))
        self.assertEqual([it["ai_guessed"] for it in backup["items"]], ["kcal_per_unit,open_days"])
        server.api_restore(dict(backup, confirm_empty=True), {})
        self.assertEqual([r["ai_guessed"] for r in server.DB.execute("SELECT ai_guessed FROM items")], ["kcal_per_unit,open_days"])
        iid = server.DB.execute("SELECT id FROM items").fetchone()["id"]
        undo = server.api_item_delete({}, {}, str(iid))["undo"]
        server.api_restore_item(undo, {})
        self.assertEqual(server.DB.execute("SELECT ai_guessed FROM items WHERE id = ?", (iid,)).fetchone()["ai_guessed"],
                         "kcal_per_unit,open_days")
        older = dict(backup, items=[{k: v for k, v in backup["items"][0].items() if k != "ai_guessed"}])   # before 1.13.0
        server.api_restore(older, {})
        self.assertEqual(server.DB.execute("SELECT ai_guessed FROM items").fetchone()["ai_guessed"], "")


class AlertAreaTest(AppTest):
    """An Emergency Alert's areas are matched as whole names against home's district, county, region, constituency and
    police force area (as postcodes.io gives them), with nations and UK-wide wording counted."""

    def home(self, nation, *names):
        loc = {"lat": 51.0, "lon": -1.0}
        server.HOME_PLACES.update(key=server._places_key(loc), names=[server.area_name(n) for n in names], nation=nation,
                                  busy=False, at=1e12)
        return loc

    def tearDown(self):
        server.HOME_PLACES.update(key=None, names=[], nation="", busy=False, at=0.0)
        super().tearDown()

    def test_wales_and_scotland(self):
        cardiff = self.home("wales", "Cardiff", "Cardiff South and Penarth", "South Wales")
        for area in ("Wales and South West England", "England and Wales", "England, Wales", "UK-wide", "Cardiff", ""):
            self.assertTrue(server.alert_covers_home(area, cardiff), area)
        self.assertFalse(server.alert_covers_home("Scotland", cardiff))
        glasgow = self.home("scotland", "Glasgow City", "Glasgow East", "Scotland")
        for area in ("Northern Ireland and parts of Scotland", "Glasgow", "Great Britain"):
            self.assertTrue(server.alert_covers_home(area, glasgow), area)
        self.assertFalse(server.alert_covers_home("England and Wales", glasgow))
        belfast = self.home("northern ireland", "Belfast")
        self.assertFalse(server.alert_covers_home("Great Britain", belfast))   # not Northern Ireland
        self.assertTrue(server.alert_covers_home("United Kingdom", belfast))

    def test_whole_names_only(self):
        newcastle = self.home("england", "Newcastle upon Tyne", "North East", "Northumbria")
        self.assertFalse(server.alert_covers_home("North East Lincolnshire", newcastle))   # not the North East
        manchester = self.home("england", "Manchester", "North West", "Manchester Central", "Greater Manchester")
        self.assertFalse(server.alert_covers_home("North West Leicestershire", manchester))
        self.assertTrue(server.alert_covers_home("Greater Manchester", manchester))   # its police force area says so
        hereford = self.home("england", "Herefordshire, County of", "West Midlands")
        self.assertTrue(server.alert_covers_home("Herefordshire", hereford))           # ONS: "Herefordshire, County of"
        bristol = self.home("england", "Bristol, City of", "South West")
        self.assertTrue(server.alert_covers_home("Bristol and North Somerset", bristol))
        self.assertEqual(server.area_name("Kingston upon Hull, City of"), "kingston upon hull")

    def test_wards_and_parishes_dont_count(self):
        sent = []

        def answer_for(url, **kw):
            sent.append(url)
            return json.dumps({"result": [{"admin_district": "Bedford", "admin_ward": "Castle", "parish": "Central",
                                           "region": "East of England", "country": "England"}]}).encode()
        server.http_get = answer_for
        loc = {"lat": 52.13567, "lon": -0.46655}
        server._lookup_places(server._places_key(loc))
        self.assertIn("lat=52.136", sent[0])   # to 3 places (about 100 m): 2 can put home in the next borough
        self.assertEqual(server.HOME_PLACES["names"], ["bedford", "east of england"])
        self.assertFalse(server.alert_covers_home("Central Bedfordshire", loc))
        self.assertFalse(server.alert_covers_home("Castle Point", loc))

    def test_a_long_list_is_matched_whole(self):
        areas = ", ".join(["Area %d" % n for n in range(40)] + ["Westminster"])   # Storm Eowyn's ran to 344 characters
        feed = ('<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x</id>'
                '<title>%s</title><summary>Alert area: x. Sent: x [%s GMT].</summary><content type="text">Stay indoors.'
                '</content></entry></feed>' % (areas, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")))
        alert = server.parse_govalerts(feed.encode(), dt.datetime.now(dt.timezone.utc))[0]
        self.assertLess(len(alert["title"]), 230)
        self.assertTrue(alert["title"].endswith(" and more"))
        self.assertTrue(server.alert_covers_home(alert["area"], self.home("england", "Westminster", "London")))


class DisasterTest(AppTest):
    def test_volcanoes_are_kept_to_2000_km(self):
        rss = (b'<?xml version="1.0"?><rss xmlns:gdacs="http://www.gdacs.org" xmlns:georss="http://www.georss.org/georss">'
               b'<channel><item><title>Red volcano in Iceland</title><gdacs:iscurrent>true</gdacs:iscurrent>'
               b'<gdacs:alertlevel>Red</gdacs:alertlevel><gdacs:eventtype>VO</gdacs:eventtype><gdacs:country>Iceland'
               b'</gdacs:country><georss:point>63.63 -19.62</georss:point></item></channel></rss>')
        london = {"lat": 51.507, "lon": -0.128}
        items = server.parse_gdacs(rss, london, 1000)   # 1,800 km: past the 1,000 km setting, but ash travels
        self.assertEqual([(i["event"], server.disaster_reaches_uk(i)) for i in items], [("VO", True)])

    def test_a_list_of_countries_with_ireland_in_it(self):
        self.assertTrue(server.disaster_reaches_uk({"area": "Ireland", "distance_km": 450, "event": "FL"}))
        self.assertTrue(server.disaster_reaches_uk({"area": "United Kingdom, Ireland", "distance_km": 600, "event": "FL"}))
        europe = {"area": "France, Spain, Ireland, Germany, Poland", "distance_km": 1400, "event": "DR"}   # a drought
        self.assertFalse(server.disaster_reaches_uk(europe))
        self.assertTrue(server.disaster_reaches_uk(dict(europe, distance_km=250)))


class GridAndLinksTest(AppTest):
    def test_operators_own_notices_are_left_out(self):
        now = dt.datetime.now(dt.timezone.utc)
        t = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = [{"publishTime": t, "warningType": "IT SYSTEMS OUTAGE",
                 "warningText": "Planned outage of the ELECTRICITY MARGIN NOTICE mechanism website."},
                {"publishTime": t, "warningType": "SO-SO TRADES", "warningText": "Prices for SO to SO transactions"},
                {"publishTime": t, "warningType": "HIGH RISK OF DEMAND REDUCTION", "warningText": "NESO has issued a notice."}]
        items, r = server.parse_grid(json.dumps({"data": rows}).encode(), now)
        self.assertEqual((r["status"], [i["severity"] for i in items]), ("demand", [2]))   # by its warningType

    def test_links_that_work(self):
        now = dt.datetime.now(dt.timezone.utc)
        rss = ('<?xml version="1.0"?><rss version="2.0"><channel><item><title>A story</title><link>http://elsewhere/x</link>'
               '<pubDate>%s</pubDate></item></channel></rss>' % now.strftime("%a, %d %b %Y %H:%M:%S GMT"))
        self.assertEqual(server.parse_ncsc(rss.encode(), now)[0]["url"], "https://www.ncsc.gov.uk/news")
        self.assertEqual(server.rain_link("Environment Agency", "E21637"),
                         "https://check-for-flooding.service.gov.uk/rainfall-station/E21637")
        self.assertEqual(server.rain_link("SEPA", "111"), "https://rainfall.sepa.org.uk/")

    def test_drought_report_names_south_staffordshire_water(self):
        body = ('<h2>Summary</h2><p>Dry.</p><h2>Temporary use bans</h2><ul><li>South Staffordshire Water: a hosepipe ban '
                'from 1 August</li></ul><h2>South Staffordshire Water</h2><p>Reservoirs are low.</p>')
        rep = server.parse_drought_report(body)
        items, r = server.drought_live(rep, dt.date.today(), "", {"water_co": "South Staffs Water"}, dt.datetime.now(dt.timezone.utc))
        self.assertEqual(r["company_text"], "Reservoirs are low.")
        self.assertEqual([i["title"] for i in items], ["Hosepipe ban: South Staffs Water"])


class BriefingPrivacyTest(AppTest):
    def test_titles_say_what_not_exactly_where(self):
        s = server.brief_safe
        self.assertEqual(s("power", "Power cut 1.5 km away"), "Power cut near home")
        self.assertEqual(s("fires", "Possible fire 3 km north-east of home"), "Possible fire near home")
        self.assertEqual(s("rivers", "River Esk at Ruswarp: above its normal range", "River Esk"),
                         "River Esk near home: above its normal range")
        self.assertEqual(s("floods", "Flood alert: River Esk at Sleights"), "Flood alert: River Esk")
        self.assertEqual(s("water", "No water reported 0.4 km away, PL1 2AB"), "No water reported near home")
        self.assertEqual(s("metoffice", "Yellow warning of wind affecting Yorkshire & Humber"),
                         "Yellow warning of wind affecting Yorkshire & Humber")


class AIReadyTest(AppTest):
    def test_home_assistant_is_asked_in_the_background(self):
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "ha"})
        asked = []
        real = server.ai_task_entities
        server.ai_task_entities = lambda strict=False: asked.append(strict) or (_ for _ in ()).throw(IOError("restarting"))
        try:
            server.AI_READY.update(at=0.0, ok=True, busy=False)
            self.assertTrue(server.ai_ready())   # answers at once, with the last answer
            for _ in range(50):
                if not server.AI_READY["busy"]:
                    break
                __import__("time").sleep(0.02)
            self.assertEqual(asked, [True])
            self.assertTrue(server.AI_READY["ok"])   # a failed check keeps the last good answer
        finally:
            server.ai_task_entities = real
            server.AI_READY.update(at=0.0, ok=False, busy=False)
