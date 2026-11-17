"""2.24: water litres from the pack size, drinks counted as water, the fuller label reading, and the stores
review. No internet and no real AI: the Messages API is stood in for."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dadsarmy"))


class TestStores24(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.tmp = tempfile.mkdtemp(prefix="dadsarmy-test-")
        server.DATA_DIR = cls.tmp
        server.DB_PATH = os.path.join(cls.tmp, "dadsarmy.db")
        server.BACKUP_DIR = os.path.join(cls.tmp, "backups")
        server.init_db()
        cls.s = server

    @classmethod
    def tearDownClass(cls):
        cls.s.DB.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        s = self.s
        with s.tx() as db:
            db.execute("DELETE FROM batches")
            db.execute("DELETE FROM items")
            s.set_setting_raw(db, "scan_ai", {"provider": "anthropic", "keys": {"anthropic": "test-key"}})
            s.set_setting_raw(db, "stock_review", None)
        s.DB.execute("DELETE FROM ai_calls")
        self.real_post = s._post_json

    def tearDown(self):
        self.s._post_json = self.real_post

    def add(self, **kw):
        body = dict({"category": "water", "unit": "bottle", "qty": 1}, **kw)
        return self.s.api_item_create(body, {})["id"]

    def test_litres_from_the_pack_size(self):
        it = {"category": "water", "litres_per_unit": 0, "pack_size": 5000, "pack_unit": "g"}
        self.assertEqual(self.s.item_litres(it), 5.0)
        self.assertEqual(self.s.item_litres(dict(it, pack_unit="l", pack_size=2)), 2.0)
        self.assertEqual(self.s.item_litres(dict(it, litres_per_unit=6)), 6.0)
        self.assertEqual(self.s.item_litres(dict(it, category="food")), 0.0)
        self.assertEqual(self.s.item_litres(dict(it, pack_unit="each", pack_size=6)), 0.0)
        self.assertEqual(self.s.item_litres(dict(it, category="drinks", pack_size=250)), 0.0)   # 250 g: not a drink
        self.assertEqual(self.s.item_litres(dict(it, category="drinks", pack_size=200, pack_unit="ml")), 0.2)

    def test_summary_counts_unset_litres_and_drinks(self):
        self.add(name="Still water (5l)", pack_size=5000, pack_unit="g", qty=4)          # 20 L, no litres set
        self.add(name="Water 6 x 2L", litres_per_unit=12, qty=1)                          # 12 L
        self.add(name="Orange juice (1l)", category="drinks", unit="carton", kcal_per_unit=430,
                 pack_size=1000, pack_unit="ml", qty=2)                                    # 2 L, and food
        out = self.s.summary()
        self.assertEqual(out["water_litres"], 32.0)   # plain water
        self.assertEqual(out["drink_litres"], 2.0)    # juice, apart

    def test_drinks_cover_the_drinking_only(self):
        import datetime as dt
        today = dt.date(2026, 1, 1)
        wl = self.s.water_lasts
        self.assertAlmostEqual(wl([(30, None)], [], 10, 4, today)[0], 3.0)
        # 4 L a day of drinks for the drinking: plain water only has to cover 6 L a day
        self.assertAlmostEqual(wl([(30, None)], [(100, None)], 10, 4, today)[0], 5.0)
        # drinks run out after 2 days (8 L), then water covers the whole 10 L: 12 L used, 18 L left: 1.8 more days
        self.assertAlmostEqual(wl([(30, None)], [(8, None)], 10, 4, today)[0], 3.8)
        # juice alone can't make a day: cooking and washing need plain water
        self.assertAlmostEqual(wl([], [(100, None)], 10, 4, today)[0], 0.0)
        # plain water that goes off before it's needed is wasted
        days, waste = wl([(10, "2026-01-01"), (10, None)], [], 5, 0, today)
        self.assertAlmostEqual(days, 3.0)
        self.assertAlmostEqual(waste, 1.0)

    def test_label_reads_everything_and_marks_estimates(self):
        reply = json.dumps({"name": "Hellmann's Real Mayonnaise", "size": "400 ml", "grams": 400, "kcal_100g": None,
                            "kcal_pack": None, "kcal_100g_typical": 720, "category": "food", "unit": "jar",
                            "best_before": "2027-03", "open_days": None, "open_days_typical": 90})
        p = self.s.parse_label_reply(reply)
        self.assertEqual(p["unit"], "jar")
        self.assertEqual(p["kcal_per_unit"], 2880)
        self.assertEqual(p["open_days"], 90)
        self.assertEqual(p["ai_guessed"], "kcal_per_unit,open_days")
        printed = self.s.parse_label_reply(json.dumps({"name": "Juice", "grams": 1000, "kcal_100g": 43,
                                                      "category": "drinks", "unit": "carton", "open_days": 5}))
        self.assertEqual(printed["kcal_per_unit"], 430)
        self.assertEqual(printed["litres_per_unit"], 1.0)
        self.assertEqual(printed["ai_guessed"], "")

    def test_label_builds_on_what_is_known(self):
        sent = {}

        def fake(url, body, headers, timeout=60):
            sent["text"] = body["messages"][0]["content"][-1]["text"]
            return {"content": [{"type": "text", "text": json.dumps({"name": "Beans", "grams": 415, "kcal_100g": 80,
                                                                     "unit": "tin", "category": "food"})}],
                    "usage": {"input_tokens": 10, "output_tokens": 10}, "stop_reason": "end_turn"}
        self.s._post_json = fake
        import base64
        jpeg = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8fakejpeg").decode()
        got = self.s.api_scan_label({"image": jpeg, "known": {"name": "Beans", "unit": "tin", "code": "5000000000001"}}, {})
        self.assertIn("Already known", sent["text"])
        self.assertEqual(got["product"]["kcal_per_unit"], 332)

    def test_new_item_keeps_ai_estimates_marked(self):
        iid = self.add(name="Mayo", category="food", unit="jar", kcal_per_unit=2880, ai_guessed="kcal_per_unit,bogus")
        row = self.s.DB.execute("SELECT ai_guessed FROM items WHERE id = ?", (iid,)).fetchone()
        self.assertEqual(row["ai_guessed"], "kcal_per_unit")

    def test_pack_word(self):
        self.assertEqual(self.s.pack_word({"packaging": "Glass jar, metal lid"}, "Mayonnaise", ""), "jar")
        self.assertEqual(self.s.pack_word({"packaging_tags": ["en:tetra-pak"]}, "Orange juice", ""), "carton")
        self.assertEqual(self.s.pack_word({}, "Peas", "en:canned-foods"), "tin")
        self.assertEqual(self.s.pack_word({}, "Peas", ""), "")

    def test_stores_review(self):
        self.add(name="Tuna (110g)", category="food", unit="tin", kcal_per_unit=120, qty=100)
        sent = {}

        def fake(url, body, headers, timeout=60):
            sent["text"] = body["messages"][0]["content"][-1]["text"]
            sent["max_tokens"] = body["max_tokens"]
            return {"content": [{"type": "text", "text": json.dumps({
                "summary": "It's nearly all tuna: plenty of protein but little else.", "score": 2,
                "wider": "Get a camping stove.", "suggestions": [{"add": "Tinned fruit", "why": "Vitamins and variety.", "category": "food"},
                                {"add": "", "why": "dropped"}]})}],
                "usage": {"input_tokens": 100, "output_tokens": 50}, "stop_reason": "end_turn"}
        self.s._post_json = fake
        got = self.s.api_ai_review({}, {})["review"]
        self.assertEqual(sent["max_tokens"], 8000)   # room for a long list
        self.assertIn("Tuna (110g)", sent["text"])
        self.assertEqual(got["score"], 2)
        self.assertEqual(got["wider"], "Get a camping stove.")
        self.assertIn("NO fridge", sent["text"])
        self.assertIn("stored_water_litres", sent["text"])
        self.assertEqual([g["add"] for g in got["suggestions"]], ["Tinned fruit"])
        self.assertEqual(self.s.api_ai_review_get({}, {})["review"]["items"], 1)
        self.assertEqual(self.s.ai_stats()["tasks"]["review"], 1)

    def test_ai_ready(self):
        self.assertTrue(self.s.ai_ready())   # an Anthropic key is set
        with self.s.tx() as db:
            self.s.set_setting_raw(db, "scan_ai", {"provider": "anthropic", "keys": {}})
        self.assertFalse(self.s.ai_ready())
        with self.s.tx() as db:
            self.s.set_setting_raw(db, "scan_ai", {"provider": "ha"})
        self.s.AI_READY["at"] = 0.0
        self.assertFalse(self.s.ai_ready())   # no Home Assistant here, so no AI Task

    def test_storage(self):
        s = self.s
        self.assertEqual(s.storage_from({}, "Chicken curry (400g)", "en:canned-foods"), "ambient")
        self.assertEqual(s.storage_from({"conservation_conditions": "Keep refrigerated"}, "Chicken curry", ""), "chilled")
        self.assertEqual(s.storage_from({}, "Garden peas", "en:frozen-foods"), "frozen")
        self.assertEqual(s.storage_from({}, "Something", ""), "")
        p = s.parse_label_reply(json.dumps({"name": "Chicken Curry", "grams": 400, "kcal_100g": 120, "category": "food",
                                            "unit": "tin", "storage": "ambient"}))
        self.assertEqual(p["storage"], "ambient")
        iid = self.add(name="Curry (tin)", category="food", unit="tin", kcal_per_unit=480, storage="ambient")
        self.assertEqual(s.DB.execute("SELECT storage FROM items WHERE id = ?", (iid,)).fetchone()["storage"], "ambient")
        iid2 = self.add(name="Milk", category="drinks", storage="lukewarm")   # nonsense: the default, the cupboard
        self.assertEqual(s.DB.execute("SELECT storage FROM items WHERE id = ?", (iid2,)).fetchone()["storage"], "ambient")
        iid3 = self.add(name="Peas", category="food", storage="frozen")
        self.assertEqual(s.DB.execute("SELECT storage FROM items WHERE id = ?", (iid3,)).fetchone()["storage"], "frozen")
        iid4 = self.add(name="Torch", category="power")
        self.assertEqual(s.DB.execute("SELECT storage FROM items WHERE id = ?", (iid4,)).fetchone()["storage"], "")
        self.assertIn("storage", s.fill_wanted({"category": "food", "name": "Curry", "kcal_per_unit": 480, "pack_size": 400,
                                                "open_days": 3, "storage": ""}))
        got = s.parse_fill_reply('[{"id": 1, "storage": "chilled"}, {"id": 2, "storage": "warm"}]',
                                 {1: ["storage"], 2: ["storage"]})
        self.assertEqual(got, {1: {"storage": "chilled"}})

    def test_review_sends_how_its_kept(self):
        self.add(name="Chicken curry (400g)", category="food", unit="tin", kcal_per_unit=480, storage="ambient")
        head, lines = self.s.review_input()
        self.assertIn("cupboard (ambient)", lines[0])
        self.assertIn("Trust it", self.s.REVIEW_PROMPT)

    def test_cold_food_days(self):
        self.add(name="Fish pie", category="food", unit="pack", kcal_per_unit=7000, storage="frozen", qty=1)
        self.add(name="Beans", category="food", unit="tin", kcal_per_unit=7000, storage="ambient", qty=1)
        out = self.s.summary()
        self.assertGreater(out["cold_food_days"], 0)
        self.assertAlmostEqual(out["cold_food_days"] * 2, out["food_days"], delta=0.2)

    def test_review_needs_stock(self):
        with self.assertRaises(self.s.ApiError):
            self.s.api_ai_review({}, {})


if __name__ == "__main__":
    unittest.main()
