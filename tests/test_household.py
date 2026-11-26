"""1.28.0: each person in the household. Men and women need different calories, diets change what's on the starter
list (lentils for a vegetarian, halal meat, gluten-free pasta...), sanitary products follow the women at home, and
Resilience and the stores review know about it all."""
import json
import math

from support import AppTest, days_from_today, server

MAN = {"sex": "male"}
WOMAN = {"sex": "female"}


def people(adults=(), children=()):
    return {"people": {"adults": list(adults), "children": list(children)}}


class CaloriesTest(AppTest):

    def test_men_and_women_need_different_calories(self):
        server.api_settings(dict(people([MAN, WOMAN]), adults=2, children=1), {})
        st = server.get_settings()
        self.assertEqual(server.household_kcal(st), 2500 + 2000 + 1600)   # the NHS's figures, and a child's
        self.add("Rice", 3, None, category="food", kcal_per_unit=6100)
        self.assertEqual(server.summary()["food_days"], 3)

    def test_someone_who_hasnt_said_is_an_adult(self):
        server.api_settings(dict(people([MAN]), adults=2, kcal_adult=2200), {})
        self.assertEqual(server.household_kcal(server.get_settings()), 2500 + 2200)

    def test_your_own_figures(self):
        server.api_settings(dict(people([MAN, WOMAN]), adults=2, kcal_man=3000, kcal_woman=1800), {})
        self.assertEqual(server.household_kcal(server.get_settings()), 4800)

    def test_details_past_the_count_are_kept_for_later(self):
        server.api_settings(dict(people([MAN, {"sex": "female", "name": "Gran", "diet": "vegetarian"}]), adults=1), {})
        self.assertEqual(server.household_kcal(server.get_settings()), 2500)
        server.api_settings({"adults": 2}, {})
        hh = server.household(server.get_settings())
        self.assertEqual([(p["sex"], p["diet"]) for p in hh], [("male", ""), ("female", "vegetarian")])
        self.assertNotIn("name", hh[1])   # names stay out of what's worked out (and sent)

    def test_nonsense_is_turned_away(self):
        for bad in ({"sex": "x"}, {"diet": "paleo"}, {"avoid": ["eggs"]}, {"avoid": "nuts"}):
            self.assertApiError(400, server.api_settings, people([bad]), {})
        self.assertApiError(400, server.api_settings, {"people": ["Dad"]}, {})
        self.assertApiError(400, server.api_settings, {"people": {"adults": "Dad"}}, {})

    def test_tidied(self):
        server.api_settings(people([{"name": "  Mum  ", "sex": "female", "avoid": ["nuts", "gluten", "nuts"]}]), {})
        self.assertEqual(server.get_settings()["people"]["adults"],
                         [{"name": "Mum", "sex": "female", "diet": "", "avoid": ["gluten", "nuts"]}])

    def test_in_backups(self):
        server.api_settings(dict(people([dict(WOMAN, diet="vegan", name="Mum")]), adults=1, kcal_woman=2100), {})
        backup = json.loads(server.api_backup({}, {}).data.decode("utf-8"))
        server.api_settings(dict(people([]), kcal_woman=2000), {})
        server.api_restore(backup, {})
        st = server.get_settings()
        self.assertEqual((st["people"]["adults"][0]["diet"], st["people"]["adults"][0]["name"], st["kcal_woman"]),
                         ("vegan", "Mum", 2100))

    def test_an_older_backup_leaves_them_alone(self):
        server.api_settings(people([dict(WOMAN, diet="halal")]), {})
        backup = json.loads(server.api_backup({}, {}).data.decode("utf-8"))
        del backup["settings"]["people"]
        server.api_restore(backup, {})
        self.assertEqual(server.get_settings()["people"]["adults"][0]["diet"], "halal")


class StarterDietTest(AppTest):

    def targets(self):
        return dict((it["name"], it["target_qty"]) for it in server.all_items())

    def kcal(self, targets):
        rows = server.STARTER_BY_NAME
        return sum(t * rows[n][3] for n, t in targets.items()
                   if n in rows and isinstance(rows[n][5], tuple) and rows[n][5][0] == "kcal")

    def test_everyone_eats_everything_as_before(self):
        server.api_settings({"adults": 2, "children": 1, "target_days": 30}, {})
        server.api_seed({}, {})
        t = self.targets()
        ctx = server.starter_ctx(server.get_settings())
        for name, _, _, kcal, _, spec, _ in server.STARTER:
            if isinstance(spec, tuple) and spec[0] == "kcal" and name not in server.FOOD_ALTS:
                self.assertEqual(t[name], max(1, int(math.ceil(ctx["kcal"] * spec[1] / kcal))), name)
        for name in server.FOOD_ALTS | {"Vitamin B12 supplement"}:
            self.assertNotIn(name, t)
        self.assertEqual(t["Sanitary products"], 2)   # nobody's said who's a woman: as before

    def test_a_vegetarian_household(self):
        server.api_settings(dict(people([dict(MAN, diet="vegetarian"), dict(WOMAN, diet="vegetarian")]), adults=2,
                                 target_days=30), {})
        server.api_seed({}, {})
        t = self.targets()
        for meat in ("Corned beef (340g)", "Tinned chilli or stew (400g)", "Tinned fish (mackerel, sardines)",
                     "Halal tinned meat (400g)"):
            self.assertNotIn(meat, t)
        self.assertGreater(t["Tinned lentils or mixed beans (400g)"], 0)
        self.assertGreater(t["Vegetable chilli or curry (400g)"], 0)
        self.assertIn("UHT milk (1L)", t)   # vegetarians drink milk
        # The calories add up to what they'd need, as for anyone (rounding each up to a whole tin or bag adds a bit).
        need = 4500 * 30
        self.assertGreaterEqual(self.kcal(t), need)
        self.assertLess(self.kcal(t), need * 1.15)

    def test_one_vegan_and_a_meat_eater(self):
        server.api_settings(dict(people([MAN, dict(WOMAN, diet="vegan")]), adults=2, target_days=30), {})
        server.api_seed({}, {})
        t = self.targets()
        ctx = server.starter_ctx(server.get_settings())
        # Corned beef for him alone; lentils instead of corned beef and fish for her.
        self.assertEqual(t["Corned beef (340g)"], int(math.ceil(2500 * 30 * .05 / 750)))
        self.assertAlmostEqual(ctx["food"]["Tinned lentils or mixed beans (400g)"], 2000 * 30 * (.05 + .04))
        self.assertAlmostEqual(ctx["food"]["Long-life soya or oat milk (1L)"], 2000 * 30 * .04)
        self.assertIn("Dark chocolate (100g bar)", t)
        self.assertIn("Rice cakes", t)   # cereal bars often have honey in them
        self.assertEqual(t["Vitamin B12 supplement"], 1)
        self.assertNotIn("Seed butter (sunflower or pumpkin)", t)   # peanut butter suits a vegan

    def test_halal_and_kosher(self):
        server.api_settings(dict(people([dict(MAN, diet="halal"), dict(WOMAN, diet="kosher")]), adults=2), {})
        food = server.starter_ctx(server.get_settings())["food"]
        self.assertAlmostEqual(food["Halal tinned meat (400g)"], 2500 * 30 * .05)
        self.assertAlmostEqual(food["Kosher tinned meat (400g)"], 2000 * 30 * .05)
        self.assertAlmostEqual(food["Vegetable chilli or curry (400g)"], 4500 * 30 * .05)
        self.assertNotIn("Corned beef (340g)", food)
        self.assertNotIn("Tinned lentils or mixed beans (400g)", food)
        self.assertIn("Tinned fish (mackerel, sardines)", food)

    def test_what_someone_avoids(self):
        server.api_settings(dict(people([dict(MAN, avoid=["nuts", "gluten", "dairy"])]), adults=1), {})
        food = server.starter_ctx(server.get_settings())["food"]
        for gone, instead in (("Peanut butter (340g)", "Seed butter (sunflower or pumpkin)"),
                              ("Nuts & dried fruit (500g)", "Seeds & dried fruit (500g)"),
                              ("Pasta (500g)", "Gluten-free pasta (500g)"), ("Porridge oats (1kg)", "Gluten-free oats (450g)"),
                              ("Instant noodles", "Rice noodles (250g)"), ("UHT milk (1L)", "Long-life soya or oat milk (1L)"),
                              ("Chocolate (100g bar)", "Dark chocolate (100g bar)")):
            self.assertNotIn(gone, food)
            self.assertIn(instead, food)
        self.assertAlmostEqual(food["Rice cakes"], 2500 * 30 * (.04 + .03))   # for crackers and cereal bars
        self.assertAlmostEqual(sum(food.values()), 2500 * 30)   # every bit of his share goes somewhere

    def test_a_change_follows_the_household(self):
        server.api_settings(dict(people([MAN]), adults=1, target_days=30), {})
        server.api_seed({}, {})
        out = server.api_settings(people([dict(MAN, diet="vegetarian")]), {})
        self.assertEqual(sorted(out["added"]), ["Tinned lentils or mixed beans (400g)", "Vegetable chilli or curry (400g)"])
        self.assertEqual(sorted(out["dropped"]), ["Corned beef (340g)", "Tinned chilli or stew (400g)",
                                                  "Tinned fish (mackerel, sardines)"])
        t = self.targets()
        self.assertEqual(t["Corned beef (340g)"], 0)   # kept (there may be some in), but not on the supply run
        self.assertGreater(t["Tinned lentils or mixed beans (400g)"], 0)
        below = [e["name"] for e in server.summary()["supply_run"]["below_target"]]
        self.assertIn("Tinned lentils or mixed beans (400g)", below)
        self.assertNotIn("Corned beef (340g)", below)
        lentils = [it for it in server.all_items() if it["name"].startswith("Tinned lentils")][0]
        self.assertEqual((lentils["starter"], lentils["auto_target"]), ("Tinned lentils or mixed beans (400g)", 1))
        # And back: corned beef's target returns; the lentils stay, with nothing to get.
        out = server.api_settings(people([MAN]), {})
        self.assertEqual(out["added"], [])
        self.assertEqual(sorted(out["dropped"]), ["Tinned lentils or mixed beans (400g)", "Vegetable chilli or curry (400g)"])
        self.assertGreater(self.targets()["Corned beef (340g)"], 0)

    def test_nothing_added_without_the_starter_list(self):
        self.add("My own beans", 0, None, target_qty=7)
        out = server.api_settings(people([dict(MAN, diet="vegan")]), {})
        self.assertEqual(out["added"], [])
        self.assertEqual([it["name"] for it in server.all_items()], ["My own beans"])

    def test_something_you_deleted_isnt_put_back(self):
        server.api_seed({}, {})
        rice = [it for it in server.all_items() if it["name"] == "Rice (1kg bag)"][0]
        server.api_item_delete({}, {}, str(rice["id"]))
        out = server.api_settings(dict(people([dict(MAN, diet="vegan")]), adults=1), {})
        self.assertNotIn("Rice (1kg bag)", out["added"])
        self.assertIn("Vitamin B12 supplement", out["added"])

    def test_new_pets_get_their_food(self):
        server.api_seed({}, {})
        out = server.api_settings({"dogs": 1}, {})
        self.assertIn("Dry dog food (2kg bag)", out["added"])
        self.assertNotIn("Dry cat food (2kg bag)", out["added"])


class SanitaryProductsTest(AppTest):

    def sanitary(self):
        return [it for it in server.all_items() if it["name"] == "Sanitary products"][0]

    def test_they_follow_the_women_at_home(self):
        server.api_settings({"adults": 2, "target_days": 30}, {})
        server.api_seed({}, {})
        self.assertEqual(self.sanitary()["target_qty"], 2)   # as before, until someone says
        server.api_settings(people([MAN, WOMAN]), {})
        self.assertEqual(self.sanitary()["target_qty"], 2)   # 2 packs a month
        server.api_settings(dict(people([WOMAN, WOMAN]), target_days=90), {})
        self.assertEqual(self.sanitary()["target_qty"], 12)
        server.api_settings(dict(people([MAN, {}]), target_days=30), {})
        self.assertEqual(self.sanitary()["target_qty"], 2)   # someone who hasn't said might need them
        out = server.api_settings(people([MAN, MAN]), {})
        self.assertEqual(self.sanitary()["target_qty"], 0)
        self.assertIn("Sanitary products", out["dropped"])

    def test_not_added_for_a_household_of_men(self):
        server.api_settings(dict(people([MAN]), adults=1), {})
        server.api_seed({}, {})
        self.assertNotIn("Sanitary products", [it["name"] for it in server.all_items()])
        out = server.api_settings(people([WOMAN]), {})
        self.assertIn("Sanitary products", out["added"])

    def test_an_older_list_follows_from_now_on(self):
        server.api_seed({}, {})
        server.DB.execute("UPDATE items SET auto_target = 0 WHERE name = 'Sanitary products'")
        server.DB.execute("DELETE FROM settings WHERE key = 'starter_128'")
        server.init_db()
        self.assertEqual(self.sanitary()["auto_target"], 1)
        server.api_settings(dict(people([MAN, MAN]), adults=2), {})
        self.assertEqual(self.sanitary()["target_qty"], 0)

    def test_one_you_changed_stays_yours(self):
        server.api_seed({}, {})
        server.api_item_update({"target_qty": 5}, {}, str(self.sanitary()["id"]))
        server.DB.execute("DELETE FROM settings WHERE key = 'starter_128'")
        server.init_db()
        server.api_settings(dict(people([MAN, MAN]), adults=2), {})
        self.assertEqual(self.sanitary()["target_qty"], 5)

    def test_bathroom_basics_for_men(self):
        server.api_settings(dict(people([MAN]), adults=1), {})
        self.add("Soap", 2, None, category="hygiene")
        self.add("Toothpaste", 1, None, category="hygiene")
        m = [x for x in server.summary()["resilience"]["items"] if x["id"] == "hyg_rest"][0]
        self.assertEqual((m["title"], m["status"]), ("Soap and toothpaste", "done"))
        server.api_settings(people([WOMAN]), {})
        m = [x for x in server.summary()["resilience"]["items"] if x["id"] == "hyg_rest"][0]
        self.assertEqual((m["title"], m["status"]), ("Soap, toothpaste and sanitary products", "partly"))
        self.assertIn("sanitary products", m["detail"])


class ResilienceDietTest(AppTest):

    def rec(self):
        got = [x for x in server.summary()["resilience"]["items"] if x["id"] == "food_diets"]
        return got[0] if got else None

    def test_only_with_diets(self):
        self.assertIsNone(self.rec())
        server.api_settings(people([MAN]), {})
        self.assertIsNone(self.rec())

    def test_what_it_looks_for(self):
        server.api_settings(dict(people([dict(WOMAN, diet="vegan"), dict(MAN, avoid=["nuts"])]), adults=2), {})
        m = self.rec()
        self.assertEqual(m["why"], "For a vegan and someone who avoids nuts: the starter list has things they can eat "
                                   "instead of what's on the usual list. Check the labels.")
        self.assertEqual((m["status"], m["act"]["kind"]), ("todo", "add"))
        self.assertIn("vitamin B12", m["detail"])
        self.add("Red lentils", 4, None, category="food", kcal_per_unit=300)   # your own names count too
        self.add("Oat milk", 2, None, category="food", kcal_per_unit=400)
        m = self.rec()
        self.assertEqual(m["status"], "partly")
        self.assertNotIn("lentils", m["detail"])
        out = server.api_res_add({"id": "food_diets"}, {})
        self.assertIn("Vitamin B12 supplement", out["added"])
        self.assertIn("Seed butter (sunflower or pumpkin)", out["added"])
        self.assertNotIn("Tinned lentils or mixed beans (400g)", out["added"])   # you have lentils

    def test_words(self):
        w = server.diets_words
        self.assertEqual(w([{"diet": "vegetarian", "avoid": []}] * 2 + [{"diet": "halal", "avoid": ["gluten"]}]),
                         "2 vegetarians, someone who eats halal and someone who avoids gluten")
        self.assertEqual(w([{"diet": "", "avoid": ["dairy"]}] * 3), "3 people who avoid dairy")


class ReviewTest(AppTest):

    def test_the_review_knows_who_eats_what_but_not_their_names(self):
        self.add("Beans", 2, None, category="food", kcal_per_unit=340)
        head, _ = server.review_input()
        self.assertNotIn("people", head)   # nothing said: as before
        server.api_settings(dict(people([dict(WOMAN, name="Mum", diet="vegan", avoid=["nuts"])], [{"name": "Tom"}]),
                                 adults=1, children=1), {})
        head, _ = server.review_input()
        self.assertEqual(head["people"], [{"age": "adult", "sex": "female", "diet": "vegan", "avoids": ["nuts"]},
                                          {"age": "child", "diet": "eats anything"}])
        self.assertEqual(head["kcal_needed_a_day"], 2000 + 1600)
        self.assertNotIn("Mum", json.dumps(head))
        self.assertNotIn("Tom", json.dumps(head))
        self.assertIn("respect each one's diet", server.REVIEW_PROMPT)


class StockAddedTest(AppTest):

    def test_a_vegans_food_days_use_her_calories(self):
        server.api_settings(dict(people([dict(WOMAN, diet="vegan")]), adults=1, children=0), {})
        self.add("Lentils", 6, days_from_today(400), category="food", kcal_per_unit=1000)
        self.assertEqual(server.summary()["food_days"], 3)
