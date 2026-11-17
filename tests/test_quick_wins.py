"""1.16.0: changing what a supply run extra says, restoring one of the Pi's automatic copies from HQ, and the
expiring-soon sensor's list of what has exactly a week to go."""
import os
import sqlite3

from support import AppTest, FakeHA, days_from_today, server


class ShoppingTextTest(AppTest):
    def extra(self, text):
        return server.api_shop_add({"text": text}, {})["id"]

    def texts(self):
        return [(r["text"], r["done"]) for r in server.DB.execute("SELECT text, done FROM shopping ORDER BY id")]

    def test_an_extra_can_be_reworded(self):
        sid = self.extra("Fuses")
        server.api_shop_update({"text": "  Spare 13 A fuses  "}, {}, str(sid))
        self.assertEqual(self.texts(), [("Spare 13 A fuses", 0)])

    def test_a_blank_or_odd_name_is_refused_and_the_old_one_stays(self):
        sid = self.extra("Fuses")
        e = self.assertApiError(400, server.api_shop_update, {"text": "   "}, {}, str(sid))
        self.assertIn("remove it from the list", e.message)
        self.assertApiError(400, server.api_shop_update, {"text": {"x": 1}}, {}, str(sid))
        self.assertEqual(self.texts(), [("Fuses", 0)])

    def test_a_long_name_is_cut_to_fit(self):
        sid = self.extra("Fuses")
        server.api_shop_update({"text": "x" * 500}, {}, str(sid))
        self.assertEqual(len(self.texts()[0][0]), 200)

    def test_ticking_still_works_without_the_text(self):
        sid = self.extra("Fuses")
        server.api_shop_update({"done": True}, {}, str(sid))
        self.assertEqual(self.texts(), [("Fuses", 1)])


class RestoreAutomaticCopyTest(AppTest):
    def names(self):
        return [b["name"] for b in server.api_backups({}, {})["backups"]]

    def test_the_copies_are_listed_newest_first_with_their_items(self):
        self.add("Beans", 3)
        older = os.path.basename(server.make_backup("auto"))
        os.rename(os.path.join(server.BACKUP_DIR, older),
                  os.path.join(server.BACKUP_DIR, "dadsarmy-20200101-060000-auto.db"))
        self.add("Rice", 1)
        newer = os.path.basename(server.make_backup("auto"))
        out = server.api_backups({}, {})
        self.assertEqual(out["keep"], server.KEEP_BACKUPS)
        self.assertEqual([b["name"] for b in out["backups"]], [newer, "dadsarmy-20200101-060000-auto.db"])
        self.assertEqual([b["items"] for b in out["backups"]], [2, 1])
        self.assertEqual(out["backups"][1]["at"], "2020-01-01 06:00:00")
        self.assertEqual(out["backups"][0]["kind"], "auto")

    def test_other_files_in_the_folder_are_left_out(self):
        server.make_backup("auto")
        for odd in ("notes.txt", "dadsarmy-2020-auto.db", ".dadsarmy-20200101-000000-auto-1.tmp"):
            open(os.path.join(server.BACKUP_DIR, odd), "w").close()
        self.assertEqual(len(self.names()), 1)

    def test_restoring_a_copy_puts_everything_back(self):
        beans = self.add("Beans", 3, days_from_today(200), unit="tin", target_qty=6)
        server.api_use({"qty": 1}, {}, str(beans))
        server.api_shop_add({"text": "Spare fuses"}, {})
        server.api_check_create({"name": "Test the smoke alarms", "every_days": 30}, {})
        server.api_settings({"adults": 3}, {})
        name = os.path.basename(server.make_backup("auto"))

        # Then things change...
        server.api_item_delete({}, {}, str(beans))
        self.add("Candles", 10)
        server.api_settings({"adults": 1}, {})
        server.DB.execute("DELETE FROM shopping")
        server.DB.execute("DELETE FROM checks")

        # ...and the copy brings it all back.
        self.assertEqual(server.api_backups_restore({"name": name}, {})["items"], 1)
        items = server.all_items()
        self.assertEqual([it["name"] for it in items], ["Beans"])
        self.assertEqual(items[0]["batches"][0]["qty"], 2)
        self.assertEqual(items[0]["batches"][0]["expiry"], days_from_today(200))
        self.assertEqual(server.get_settings()["adults"], 3)
        self.assertEqual([s["text"] for s in server.DB.execute("SELECT text FROM shopping")], ["Spare fuses"])
        self.assertEqual([c["name"] for c in server.all_checks()], ["Test the smoke alarms"])
        used = server.DB.execute("SELECT item_id, qty FROM usage").fetchall()
        self.assertEqual([tuple(r) for r in used], [(items[0]["id"], 1)])   # what was used, and when, comes back too
        # A copy of what was there just before is kept, and listed as such.
        kinds = [b["kind"] for b in server.api_backups({}, {})["backups"]]
        self.assertIn("pre-restore", kinds)

    def test_an_empty_copy_asks_first(self):
        name = os.path.basename(server.make_backup("auto"))   # made while the stores were empty
        self.add("Beans", 4)
        e = self.assertApiError(409, server.api_backups_restore, {"name": name}, {})
        self.assertEqual(e.code, "empty_backup")
        self.assertEqual(len(server.all_items()), 1)
        server.api_backups_restore({"name": name, "confirm_empty": True}, {})
        self.assertEqual(server.all_items(), [])

    def test_a_damaged_copy_is_listed_but_cant_be_restored(self):
        self.add("Beans", 4)
        bad = "dadsarmy-20200101-060000-auto.db"
        with open(os.path.join(server.BACKUP_DIR, bad), "wb") as f:
            f.write(b"SQLite format 3\x00" + b"\xff" * 5000)
        listed = server.api_backups({}, {})["backups"]
        self.assertEqual([(b["name"], b["items"]) for b in listed], [(bad, None)])
        self.assertTrue(listed[0]["error"])
        self.assertApiError(400, server.api_backups_restore, {"name": bad}, {})
        self.assertEqual([it["name"] for it in server.all_items()], ["Beans"])
        self.assertFalse([f for f in os.listdir(server.BACKUP_DIR) if f.endswith("-pre-restore.db")])

    def test_only_its_own_copies_can_be_named(self):
        for name in ("../dadsarmy.db", "dadsarmy.db", "dadsarmy-20200101-060000-auto.db", "", None, 5):
            self.assertApiError(404, server.api_backups_restore, {"name": name}, {})

    def test_api_keys_stay_out_of_a_restore(self):
        self.add("Beans", 1)
        name = os.path.basename(server.make_backup("auto"))
        conn = sqlite3.connect(os.path.join(server.BACKUP_DIR, name))
        self.assertIsNone(conn.execute("SELECT value FROM settings WHERE key = 'scan_ai'").fetchone())
        conn.close()
        server.api_backups_restore({"name": name}, {})
        self.assertEqual(len(server.all_items()), 1)


class ExpiresInAWeekTest(AppTest):
    def test_the_summary_lists_what_has_exactly_a_week_to_go(self):
        tins = self.add("Beans", 2, days_from_today(7), unit="tin")
        self.stock(tins, 1, days_from_today(3))   # an earlier batch doesn't hide the one a week away
        self.add("Rice", 1, days_from_today(8))
        self.add("Soup", 1, days_from_today(6))
        week = server.summary()["expires_in_7_days"]
        self.assertEqual([(e["name"], e["qty"], e["days"], e["expiry"]) for e in week],
                         [("Beans", 2, 7, days_from_today(7))])
        self.assertIn("2 tins", week[0]["text"])

    def test_the_expiring_soon_sensor_carries_it(self):
        self.add("Beans", 2, days_from_today(7))
        ha = FakeHA()
        try:
            server.HA_TOKEN = "test-token"
            server.HA_API = ha.api
            server.ha_once(server.ha_state_new())
            attrs = ha.states["sensor.dads_army_expiring_soon"]["attributes"]
        finally:
            ha.close()
        self.assertEqual([e["name"] for e in attrs["expires_in_7_days"]], ["Beans"])
        self.assertEqual(attrs["expires_today"], [])
