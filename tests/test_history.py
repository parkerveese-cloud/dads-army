"""Tests for history (one row a day) and usage (stock used), added in 2.0.

    python3 -m unittest discover -s tests -v
"""
import datetime as dt
import json
import os
import re
import sqlite3
import time
import unittest

from test_server import Server, ServerTest, day, make_v140_db

import server as dadsarmy   # for SCHEMA (test_server puts dadsarmy/ on the path)

TODAY = dt.date.today().isoformat()
HISTORY_KEYS = ["date", "readiness_pct", "hold_out_days", "food_days", "water_days", "kit_pct", "items",
                "in_stock", "expired", "expiring", "below_target", "alert_level"]


def ts(n, clock="12:00:00"):
    return "%s %s" % (day(n), clock)


class HistoryTest(ServerTest):
    # -- helpers ------------------------------------------------------------
    def db(self):
        con = sqlite3.connect(os.path.join(self.tmp, "dadsarmy.db"), timeout=10)
        con.row_factory = sqlite3.Row
        return con

    def query(self, sql, args=()):
        con = self.db()
        try:
            return [dict(r) for r in con.execute(sql, args)]
        finally:
            con.close()

    def execute(self, sql, args=()):
        con = self.db()
        try:
            con.execute(sql, args)
            con.commit()
        finally:
            con.close()

    def stored_today(self):
        rows = self.query("SELECT * FROM history WHERE date = ?", (TODAY,))
        return rows[0] if rows else None

    def wait_for(self, pred, what, timeout=12):
        deadline = time.time() + timeout
        while True:
            got = pred()
            if got:
                return got
            if time.time() > deadline:
                self.fail("timed out waiting for " + what)
            time.sleep(0.2)

    def expected(self):
        """Today's history entry, worked out from /api/summary."""
        s = self.ok("GET", "/api/summary")
        return {"date": s["date"], "readiness_pct": s["readiness_pct"], "hold_out_days": s["hold_out_days"],
                "food_days": s["food_days"], "water_days": s["water_days"], "kit_pct": s["kit_stocked_pct"],
                "items": s["items_total"], "in_stock": s["items_in_stock"], "expired": len(s["expired"]),
                "expiring": len(s["expiring_soon"]), "below_target": len(s["supply_run"]["below_target"]),
                "alert_level": "none"}

    def stored_matches(self, want):
        row = self.stored_today()
        return row is not None and {k: row[k] for k in HISTORY_KEYS} == want

    def usage_of(self, item_id):
        return self.item(item_id)["usage"]

    def usage_rows(self, item_id):
        return [(r["qty"],) for r in self.query("SELECT qty FROM usage WHERE item_id = ? ORDER BY id", (item_id,))]


# ---------------------------------------------------------------------------
class TestHistoryRecording(HistoryTest):
    def setUp(self):
        self.wipe()

    def test_today_matches_summary_and_updates(self):
        self.add_item("Beans", "food", "tin", target=10, kcal=340, batches=[(4, day(200)), (1, day(-3))])
        self.add_item("Water", "water", "bottle", target=4, litres=5, batches=[(2, day(10))])
        self.add_item("Torch", "power", target=2)
        want = self.expected()
        self.assertEqual((want["items"], want["in_stock"], want["expired"], want["expiring"]), (3, 2, 1, 1))
        hist = self.ok("GET", "/api/state")["history"]
        self.assertEqual(hist[-1], want)                         # live, even before anything is written
        self.assertEqual(list(hist[-1]), HISTORY_KEYS)
        self.wait_for(lambda: self.stored_matches(want), "today's row")
        # A change shows up, in the same row.
        self.add_item("Rice", "food", "bag", target=2, kcal=3600, batches=[(2, day(400))])
        want2 = self.expected()
        self.assertNotEqual(want, want2)
        self.assertEqual(self.ok("GET", "/api/state")["history"][-1], want2)
        self.wait_for(lambda: self.stored_matches(want2), "the updated row")
        self.assertEqual(self.query("SELECT COUNT(*) AS n FROM history WHERE date = ?", (TODAY,))[0]["n"], 1)
        self.assertEqual(self.ok("GET", "/api/history")["days"][-1], want2)

    def test_identical_state_does_not_rewrite(self):
        self.add_item("Matches", "cooking", target=5, batches=[(3, None)])
        want = self.expected()
        self.wait_for(lambda: self.stored_matches(want), "today's row")
        time.sleep(2.5)   # let any write still settling land
        before = self.stored_today()["written_at"]
        time.sleep(1.1)   # so a rewrite would show a later written_at
        st = self.ok("GET", "/api/state")["settings"]
        self.ok("PUT", "/api/settings", {"adults": st["adults"]})   # a write that changes nothing
        time.sleep(3.5)
        self.assertEqual(self.stored_today()["written_at"], before)

    def test_burst_of_edits_writes_once_settled(self):
        i = self.add_item("Candles", "power", target=20, batches=[(10, None)])
        self.wait_for(lambda: self.stored_matches(self.expected()), "today's row")
        for _ in range(5):
            self.ok("POST", "/api/items/%d/use" % i, {"qty": 1})
        want = self.expected()
        self.wait_for(lambda: self.stored_matches(want), "the row after the burst")

    def test_starter_list_writes_history(self):
        self.ok("POST", "/api/seed")
        want = self.expected()
        self.assertGreater(want["items"], 50)
        self.wait_for(lambda: self.stored_matches(want), "the row after loading the starter list")

    def test_state_is_stable_between_polls(self):
        i = self.add_item("Beans", "food", "tin", target=10, kcal=340, batches=[(7, day(200))])
        self.ok("POST", "/api/items/%d/use" % i, {"qty": 1})
        self.execute("INSERT OR REPLACE INTO history(date, hold_out_days, food_days, items) VALUES (?, 1.2, 1.2, 1)",
                     (day(-3),))
        time.sleep(3)   # let the history write settle
        polls = []
        for _ in range(2):
            status, raw, _ = self.srv.call("GET", "/api/state", raw=True)
            self.assertEqual(status, 200)
            polls.append(re.sub(rb'"time": "[^"]*"', b'"time": ""', raw))
            time.sleep(1.1)
        self.assertEqual(polls[0], polls[1])
        st = json.loads(polls[0].decode("utf-8"))
        self.assertEqual([h["date"] for h in st["history"]], [day(-3), TODAY])
        self.assertIsNotNone(self.find(st["items"], "Beans")["usage"]["per_week"])


# ---------------------------------------------------------------------------
class TestUsageRecording(HistoryTest):
    def setUp(self):
        self.wipe()

    def test_use_is_recorded_and_undo_reverses_it(self):
        i = self.add_item("Beans", "food", "tin", batches=[(5, day(100))])
        self.assertEqual(self.usage_of(i), {"used_30d": None, "used_90d": None, "per_week": None,
                                            "runs_out_in_days": None})
        res = self.ok("POST", "/api/items/%d/use" % i, {"qty": 2})
        self.assertEqual(self.usage_rows(i), [(2,)])
        u = self.usage_of(i)
        self.assertEqual((u["used_30d"], u["used_90d"]), (2, 2))
        self.ok("POST", "/api/restore-item", res["undo"])
        self.assertEqual(self.usage_rows(i), [])
        self.assertIsNone(self.usage_of(i)["used_30d"])

    def test_use_more_than_there_is_counts_what_was_used(self):
        i = self.add_item("Soup", "food", "tin", batches=[(2, None)])
        self.ok("POST", "/api/items/%d/use" % i, {"qty": 5})
        self.assertEqual(self.usage_rows(i), [(2,)])

    def test_negative_steps_count_and_others_dont(self):
        i = self.add_item("Batteries", "power", "pack", batches=[(3, day(300))])
        b = self.item(i)["batches"][0]["id"]
        self.ok("PUT", "/api/batches/%d" % b, {"delta": 1})                 # + stepper
        self.ok("PUT", "/api/batches/%d" % b, {"qty": 2})                   # edit form, down
        self.ok("PUT", "/api/batches/%d" % b, {"qty": 6})                   # edit form, up
        self.ok("PUT", "/api/batches/%d" % b, {"location": "Drawer"})       # details only
        self.assertEqual(self.usage_rows(i), [])
        res = self.ok("PUT", "/api/batches/%d" % b, {"delta": -2})           # - stepper
        self.assertEqual(self.usage_rows(i), [(2,)])
        self.ok("POST", "/api/restore-item", res["undo"])                    # undo the step
        self.assertEqual(self.usage_rows(i), [])
        b = self.item(i)["batches"][0]["id"]                                 # undo puts batches back anew
        self.ok("PUT", "/api/batches/%d" % b, {"delta": -10})                # empties it: only 6 were there
        self.assertEqual(self.usage_rows(i), [(6,)])

    def test_deleting_and_restoring_dont_count(self):
        i = self.add_item("Tape", "tools", batches=[(3, None), (2, day(50))])
        res = self.ok("POST", "/api/items/%d/stock" % i, {"qty": 4})
        self.ok("POST", "/api/restore-item", res["undo"])                    # undoing an add isn't use
        b = self.item(i)["batches"][0]["id"]
        self.ok("DELETE", "/api/batches/%d" % b)                              # removing a batch isn't use
        self.assertEqual(self.usage_rows(i), [])
        self.ok("POST", "/api/items/%d/use" % i, {"qty": 1})
        res = self.ok("DELETE", "/api/items/%d" % i)
        self.assertEqual(self.usage_rows(i), [])                              # gone with the item
        self.ok("POST", "/api/restore-item", res["undo"])                     # and back with the undo
        self.assertEqual(self.usage_rows(i), [(1,)])
        res = self.ok("POST", "/api/items/delete", {"ids": [i]})
        self.assertEqual(self.usage_rows(i), [])
        self.ok("POST", "/api/restore-item", res["undo"])
        self.assertEqual(self.usage_rows(i), [(1,)])

    def test_foreign_keys_enforced(self):
        i = self.add_item("Rope", "tools", batches=[(3, None)])
        self.ok("POST", "/api/items/%d/use" % i, {"qty": 1})
        self.ok("POST", "/api/items/delete", {"ids": [i]})
        self.assertEqual(self.query("SELECT COUNT(*) AS n FROM usage")[0]["n"], 0)


# ---------------------------------------------------------------------------
class TestUsageMaths(HistoryTest):
    """A database built before the server starts, with usage and history back-dated."""

    @classmethod
    def prepare(cls, data_dir):
        con = sqlite3.connect(os.path.join(data_dir, "dadsarmy.db"))
        con.executescript(dadsarmy.SCHEMA)
        made = "2026-01-01 10:00:00"
        items = [  # id, name, batches [(qty, expiry)], usage [(days ago, qty)]
            (1, "Beans", [(10, day(100)), (3, day(-2))], [(-20, 3), (-10, 2), (-5, 2)]),
            (2, "Rice", [], [(-1, 2)]),
            (3, "Old", [(4, None)], [(-100, 5)]),
            (4, "Never", [(4, None)], []),
            (5, "Water", [(6, None)], [(-120, 50), (-60, 9)]),
            (6, "Ancient", [(1, None)], [(-500, 3)]),
        ]
        for item_id, name, batches, usage in items:
            con.execute("INSERT INTO items(id, name, category, unit, created_at, updated_at) VALUES (?, ?, 'other',"
                        " 'each', ?, ?)", (item_id, name, made, made))
            for qty, exp in batches:
                con.execute("INSERT INTO batches(item_id, qty, expiry, added_at) VALUES (?, ?, ?, ?)",
                            (item_id, qty, exp, made))
            for ago, qty in usage:
                con.execute("INSERT INTO usage(item_id, ts, qty) VALUES (?, ?, ?)", (item_id, ts(ago), qty))
        for n in (-1000, -700, -200, -100, -5, -1, 3):
            con.execute("INSERT INTO history(date, readiness_pct, hold_out_days, items, alert_level)"
                        " VALUES (?, 50, 7.5, 6, 'minor')", (day(n),))
        con.commit()
        con.close()

    def usage(self):
        return {it["name"]: it["usage"] for it in self.ok("GET", "/api/state")["items"]}

    def test_rates_and_forecasts(self):
        u = self.usage()
        # 7 used since the first use 20 days ago (21 days, today counted): 1/3 a day; 10 in date -> 30 days.
        self.assertEqual(u["Beans"], {"used_30d": 7, "used_90d": 7, "per_week": 2.33, "runs_out_in_days": 30})
        # One use yesterday: spread over the 14-day minimum, and there's no stock to run out of.
        self.assertEqual(u["Rice"], {"used_30d": 2, "used_90d": 2, "per_week": 1, "runs_out_in_days": None})
        # Used long ago but not lately.
        self.assertEqual(u["Old"], {"used_30d": 0, "used_90d": 0, "per_week": 0, "runs_out_in_days": None})
        self.assertEqual(u["Never"], {"used_30d": None, "used_90d": None, "per_week": None,
                                      "runs_out_in_days": None})
        # First use 120 days ago: the window is the full 90 days. 9 in 90 days = 0.1 a day; 6 left -> 60 days.
        self.assertEqual(u["Water"], {"used_30d": 0, "used_90d": 9, "per_week": 0.7, "runs_out_in_days": 60})

    def test_old_usage_is_pruned(self):
        self.wait_for(lambda: not self.query("SELECT 1 FROM usage WHERE item_id = 6"), "usage over 400 days old to go")
        self.assertEqual(self.usage()["Ancient"]["used_90d"], None)
        self.assertEqual(len(self.query("SELECT 1 FROM usage WHERE item_id = 5")), 2)

    def test_history_range_and_clamping(self):
        def dates(path):
            return [d["date"] for d in self.ok("GET", path)["days"]]
        state = self.ok("GET", "/api/state")["history"]
        self.assertEqual([d["date"] for d in state], [day(-100), day(-5), day(-1), TODAY])   # gaps stay gaps
        self.assertEqual(state[0], {"date": day(-100), "readiness_pct": 50, "hold_out_days": 7.5, "food_days": 0,
                                    "water_days": 0, "kit_pct": 0, "items": 6, "in_stock": 0, "expired": 0,
                                    "expiring": 0, "below_target": 0, "alert_level": "minor"})
        self.assertEqual(dates("/api/history"), [day(-100), day(-5), day(-1), TODAY])
        self.assertEqual(dates("/api/history?days=5000"), [day(-700), day(-200), day(-100), day(-5), day(-1), TODAY])
        self.assertEqual(dates("/api/history?days=730"), dates("/api/history?days=5000"))
        self.assertEqual(dates("/api/history?days=6"), [day(-5), day(-1), TODAY])
        self.assertEqual(dates("/api/history?days=1"), [TODAY])
        self.assertEqual(dates("/api/history?days=0"), [TODAY])
        self.fails(400, "GET", "/api/history?days=lots")


# ---------------------------------------------------------------------------
class TestMigrationFrom140(HistoryTest):
    @classmethod
    def prepare(cls, data_dir):
        make_v140_db(data_dir, adults=2)

    def test_old_database_gains_history_and_usage(self):
        con = self.db()
        try:
            tables = set(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'"))
        finally:
            con.close()
        self.assertTrue({"history", "usage", "items", "batches", "shopping", "ha_todo"} <= tables)
        st = self.ok("GET", "/api/state")
        self.assertEqual(sorted(it["name"] for it in st["items"]), ["Baked beans", "Soap", "Toilet roll"])
        self.assertEqual([s["text"] for s in st["shopping"]], ["Spare fuses"])
        want = self.expected()
        self.wait_for(lambda: self.stored_matches(want), "today's row in an old database (written at start)")
        beans = self.find(st["items"], "Baked beans")
        self.ok("POST", "/api/items/%d/use" % beans["id"], {"qty": 1})
        self.assertEqual(self.usage_of(beans["id"])["used_30d"], 1)


# ---------------------------------------------------------------------------
class TestRestartAndBackups(HistoryTest):
    def test_history_survives_restart(self):
        self.wipe()
        self.execute("DELETE FROM history")
        self.add_item("Beans", "food", "tin", target=10, kcal=340, batches=[(4, day(200))])
        self.execute("INSERT OR REPLACE INTO history(date, readiness_pct, items) VALUES (?, 3, 1)", (day(-2),))
        want = self.expected()
        self.wait_for(lambda: self.stored_matches(want), "today's row")
        self.srv.stop()
        type(self).srv = Server(self.tmp)
        hist = self.ok("GET", "/api/state")["history"]
        self.assertEqual([h["date"] for h in hist], [day(-2), TODAY])
        self.assertEqual(hist[0]["readiness_pct"], 3)
        self.assertEqual(hist[-1], want)
        self.assertTrue(self.stored_matches(want))

    def test_backup_round_trip(self):
        self.wipe()
        a = self.add_item("Beans", "food", "tin", target=10, kcal=340, batches=[(6, day(200))])
        b = self.add_item("Candles", "power", target=20, batches=[(10, None)])
        self.ok("POST", "/api/items/%d/use" % a, {"qty": 2})
        self.ok("PUT", "/api/batches/%d" % self.item(b)["batches"][0]["id"], {"delta": -3})
        self.execute("INSERT OR REPLACE INTO history(date, readiness_pct, hold_out_days, items, alert_level)"
                     " VALUES (?, 40, 12.5, 2, 'moderate')", (day(-7),))
        before = {it["name"]: it["usage"] for it in self.ok("GET", "/api/state")["items"]}
        status, raw, _ = self.srv.call("GET", "/api/backup.json", raw=True)
        self.assertEqual(status, 200)
        backup = json.loads(raw.decode("utf-8"))
        self.assertEqual(sorted((u["item_id"], u["qty"]) for u in backup["usage"]), sorted([(a, 2), (b, 3)]))
        old = self.find([dict(h, name=h["date"]) for h in backup["history"]], day(-7))
        self.assertEqual((old["hold_out_days"], old["alert_level"]), (12.5, "moderate"))
        # Change everything, then restore.
        self.wipe()
        self.execute("DELETE FROM history WHERE date = ?", (day(-7),))
        self.add_item("Something else", batches=[(1, None)])
        self.ok("POST", "/api/restore", backup)
        st = self.ok("GET", "/api/state")
        after = {it["name"]: it["usage"] for it in st["items"]}
        self.assertEqual(after, before)   # matched up with the items' new ids
        self.assertNotIn(a, [it["id"] for it in st["items"]])
        h = self.find([dict(x, name=x["date"]) for x in st["history"]], day(-7))
        self.assertEqual((h["readiness_pct"], h["hold_out_days"], h["alert_level"]), (40, 12.5, "moderate"))
        want = self.expected()
        self.wait_for(lambda: self.stored_matches(want), "today's row after the restore")

        # The automatic copy made before that restore has them too.
        names = [x["name"] for x in self.ok("GET", "/api/backups")["backups"] if x["kind"] == "pre-restore"]
        self.ok("POST", "/api/backups/restore", {"name": names[0]})
        self.assertEqual({it["name"] for it in self.ok("GET", "/api/state")["items"]}, {"Something else"})
        self.ok("POST", "/api/restore", backup)

        # A backup from before 2.0 (no history, no usage) still restores, and leaves history alone.
        old_style = {k: v for k, v in backup.items() if k not in ("history", "usage")}
        self.ok("POST", "/api/restore", old_style)
        st = self.ok("GET", "/api/state")
        self.assertEqual(sorted(it["name"] for it in st["items"]), ["Beans", "Candles"])
        self.assertIsNone(self.find(st["items"], "Beans")["usage"]["used_30d"])
        self.assertIn(day(-7), [x["date"] for x in st["history"]])

    def test_damaged_history_and_usage_rows_are_skipped(self):
        self.wipe()
        a = self.add_item("Beans", "food", "tin", batches=[(6, None)])
        self.ok("POST", "/api/items/%d/use" % a, {"qty": 1})
        status, raw, _ = self.srv.call("GET", "/api/backup.json", raw=True)
        backup = json.loads(raw.decode("utf-8"))
        backup["usage"] += [{"item_id": a, "ts": "yesterday", "qty": 1}, {"item_id": 999, "ts": ts(-1), "qty": 1},
                            "nonsense", {"item_id": a, "ts": ts(-1), "qty": -4}]
        backup["history"] = [{"date": "soon"}, 7, {"date": day(-3), "readiness_pct": "x"},
                             {"date": day(-4), "readiness_pct": 20, "alert_level": "apocalyptic"}]
        self.ok("POST", "/api/restore", backup)
        st = self.ok("GET", "/api/state")
        self.assertEqual(self.find(st["items"], "Beans")["usage"]["used_30d"], 1)
        self.assertEqual([(h["date"], h["alert_level"]) for h in st["history"]], [(day(-4), "none"), (TODAY, "none")])


if __name__ == "__main__":
    unittest.main()
