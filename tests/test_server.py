"""Tests for the Dads Army server. Standard library only:

    python3 -m unittest discover -s tests -v

Each test class starts the real server as a subprocess on a free localhost port,
with its own temporary data folder.
"""
import csv
import datetime as dt
import io
import json
import re
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "dadsarmy", "server.py")
sys.path.insert(0, os.path.join(ROOT, "dadsarmy"))

TODAY = dt.date.today()


def day(n):
    return (TODAY + dt.timedelta(days=n)).isoformat()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# The database as Dads Army 1.4.0 made it (copied from that version's SCHEMA).
V140_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'other',
    unit            TEXT    NOT NULL DEFAULT '',
    kcal_per_unit   REAL    NOT NULL DEFAULT 0,
    litres_per_unit REAL    NOT NULL DEFAULT 0,
    target_qty      REAL    NOT NULL DEFAULT 0,
    notes           TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS batches (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id   INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    qty       REAL    NOT NULL DEFAULT 0,
    expiry    TEXT,
    location  TEXT    NOT NULL DEFAULT '',
    added_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_batches_item ON batches(item_id);
CREATE TABLE IF NOT EXISTS shopping (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT    NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,
    action TEXT NOT NULL,
    item   TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ha_todo (
    key     TEXT PRIMARY KEY,
    uid     TEXT    NOT NULL DEFAULT '',
    summary TEXT    NOT NULL DEFAULT '',
    done    INTEGER NOT NULL DEFAULT 0
);
"""


def make_v140_db(data_dir, adults=0, children=0):
    """A 1.4.0 database with a little in it (and nobody in the household, which 1.4.0 allowed)."""
    os.makedirs(data_dir, exist_ok=True)
    con = sqlite3.connect(os.path.join(data_dir, "dadsarmy.db"))
    con.executescript(V140_SCHEMA)
    ts = "2026-01-01 10:00:00"
    settings = {"adults": adults, "children": children, "kcal_adult": 2200, "kcal_child": 1600,
                "water_per_person": 3, "target_days": 30, "warn_days": 30}
    con.executemany("INSERT INTO settings(key, value) VALUES (?, ?)",
                    [(k, json.dumps(v)) for k, v in settings.items()])
    con.execute("INSERT INTO items(name, category, unit, kcal_per_unit, litres_per_unit, target_qty, notes,"
                " created_at, updated_at) VALUES ('Baked beans', 'food', 'tin', 340, 0, 10, '', ?, ?)", (ts, ts))
    con.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at) VALUES (1, 4, ?, 'Larder', ?)",
                (day(200), ts))
    # From 1.4.0's starter list: one untouched (2 people x 30 days x 0.25), one changed by hand.
    for name, target in (("Toilet roll", 15), ("Soap", 9)):
        con.execute("INSERT INTO items(name, category, unit, target_qty, created_at, updated_at)"
                    " VALUES (?, 'hygiene', 'roll', ?, ?, ?)", (name, target, ts, ts))
    con.execute("INSERT INTO shopping(text, done, created_at) VALUES ('Spare fuses', 0, ?)", (ts,))
    con.execute("INSERT INTO ha_todo(key, uid, summary, done) VALUES ('x:abc', 'abc', '', 0)")
    con.commit()
    con.close()


class Server(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.port = free_port()
        env = {k: v for k, v in os.environ.items() if k not in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN")}
        env.update(DADSARMY_DATA=data_dir, DADSARMY_PORT=str(self.port), DADSARMY_HOST="127.0.0.1",
                   PYTHONDONTWRITEBYTECODE="1", DADSARMY_INTEL_OFF="1")
        self.proc = subprocess.Popen([sys.executable, SERVER], env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
        deadline = time.time() + 15
        while True:
            try:
                if self.call("GET", "/api/health")[0] == 200:
                    break
            except OSError:
                pass
            if self.proc.poll() is not None or time.time() > deadline:
                out = self.proc.stdout.read().decode("utf-8", "replace") if self.proc.stdout else ""
                self.stop()
                raise RuntimeError("server didn't start:\n" + out)
            time.sleep(0.1)

    def call(self, method, path, body=None, raw=False):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), method=method, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                status, payload, headers = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            status, payload, headers = e.code, e.read(), e.headers
            e.close()
        if raw:
            return status, payload, headers
        return status, (json.loads(payload.decode("utf-8")) if payload else None)

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if self.proc.stdout:
            self.proc.stdout.close()


class ServerTest(unittest.TestCase):
    """One server per test class; tests tidy up after themselves where it matters."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="dadsarmy-test-")
        cls.prepare(cls.tmp)
        cls.srv = Server(cls.tmp)

    @classmethod
    def prepare(cls, data_dir):
        pass

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # -- helpers ------------------------------------------------------------
    def ok(self, method, path, body=None):
        status, out = self.srv.call(method, path, body)
        self.assertEqual(status, 200, "%s %s -> %s %s" % (method, path, status, out))
        return out

    def fails(self, status, method, path, body=None):
        got, out = self.srv.call(method, path, body)
        self.assertEqual(got, status, "%s %s -> %s %s" % (method, path, got, out))
        self.assertIn("error", out)
        return out

    def add_item(self, name, category="other", unit="each", target=0, kcal=0, litres=0, batches=()):
        item_id = self.ok("POST", "/api/items", {"name": name, "category": category, "unit": unit,
                                                  "target_qty": target, "kcal_per_unit": kcal,
                                                  "litres_per_unit": litres})["id"]
        for qty, expiry in batches:
            self.ok("POST", "/api/items/%d/stock" % item_id, {"qty": qty, "expiry": expiry})
        return item_id

    def item(self, item_id):
        for it in self.ok("GET", "/api/state")["items"]:
            if it["id"] == item_id:
                return it
        return None

    def wipe(self):
        ids = [it["id"] for it in self.ok("GET", "/api/state")["items"]]
        if ids:
            self.ok("POST", "/api/items/delete", {"ids": ids})
        for s in self.ok("GET", "/api/state")["shopping"]:
            self.ok("DELETE", "/api/shopping/%d" % s["id"])

    @staticmethod
    def find(rows, name):
        for r in rows:
            if r["name"] == name:
                return r
        return None


# ---------------------------------------------------------------------------
class TestSummary(ServerTest):
    def setUp(self):
        self.wipe()

    def test_expired_stock_does_not_count_towards_target(self):     # fix 1
        self.add_item("Beans", "food", "tin", target=4, kcal=340, batches=[(2, day(-5)), (1, day(100))])
        self.add_item("Torch", "power", "each", target=2, batches=[(2, day(-1))])
        s = self.ok("GET", "/api/summary")
        beans = self.find(s["low_stock"], "Beans")
        self.assertIsNotNone(beans)
        self.assertEqual((beans["have"], beans["get"], beans["expired"]), (1, 3, 2))
        self.assertEqual(beans["text"], "Get 3 tins · have 1 of 4 · 2 expired")
        torch = self.find(s["out_of_stock"], "Torch")
        self.assertIsNotNone(torch, "only expired stock left counts as out of stock")
        self.assertEqual(torch["text"], "Get 2 each · 2 expired")
        self.assertEqual(s["kit_stocked_pct"], 0)
        run = [e["name"] for e in s["supply_run"]["below_target"]]
        self.assertEqual(sorted(run), ["Beans", "Torch"])

    def test_newly_expired_checks_every_batch(self):                 # fix 12
        self.add_item("Soup", "food", "tin", batches=[(1, day(-10)), (3, day(-1)), (2, day(5))])
        self.add_item("Milk", "food", "carton", batches=[(1, day(-1))])
        self.add_item("Rice", "food", "bag", batches=[(1, day(-3)), (2, day(0))])
        s = self.ok("GET", "/api/summary")
        newly = {r["name"]: r for r in s["newly_expired"]}
        self.assertEqual(sorted(newly), ["Milk", "Soup"])
        self.assertEqual(newly["Soup"]["qty"], 3)
        self.assertEqual(newly["Soup"]["days"], -1)
        self.assertEqual(newly["Soup"]["expiry"], day(-1))
        self.assertEqual([r["name"] for r in s["expires_today"]], ["Rice"])
        self.add_item("Pasta", "food", "bag", batches=[(2, day(7)), (1, day(7)), (5, day(8))])
        week = self.ok("GET", "/api/summary")["expires_in_7_days"]
        self.assertEqual([(r["name"], r["qty"], r["days"]) for r in week], [("Pasta", 3, 7)])

    def test_per_category_warning_days(self):                          # enhancement A
        self.add_item("Plasters", "medical", "box", batches=[(1, day(60))])
        self.add_item("Oats", "food", "bag", batches=[(1, day(60))])
        names = lambda: sorted(r["name"] for r in self.ok("GET", "/api/summary")["expiring_soon"])
        self.assertEqual(names(), [])
        out = self.ok("PUT", "/api/settings", {"category_warn_days": {"medical": 90}})
        self.assertIn("category_warn_days", out["changed"])
        self.assertEqual(names(), ["Plasters"])
        self.ok("PUT", "/api/settings", {"category_warn_days": {"food": 61}})   # adds, keeps medical
        self.assertEqual(self.ok("GET", "/api/state")["settings"]["category_warn_days"], {"medical": 90, "food": 61})
        self.assertEqual(names(), ["Oats", "Plasters"])
        self.ok("PUT", "/api/settings", {"category_warn_days": {"medical": None, "food": ""}})
        self.assertEqual(self.ok("GET", "/api/state")["settings"]["category_warn_days"], {})
        self.assertEqual(names(), [])
        self.fails(400, "PUT", "/api/settings", {"category_warn_days": {"spaceships": 10}})
        self.fails(400, "PUT", "/api/settings", {"category_warn_days": {"food": "soon"}})
        self.fails(400, "PUT", "/api/settings", {"category_warn_days": [1, 2]})


class TestSettings(ServerTest):
    def tearDown(self):
        self.ok("PUT", "/api/settings", {"adults": 2, "children": 0, "pets": 0, "kcal_per_pet": 0,
                                         "water_per_pet": 0})

    def test_household_needs_someone(self):                             # fix 11
        self.fails(400, "PUT", "/api/settings", {"adults": 0, "children": 0})
        self.ok("PUT", "/api/settings", {"adults": 1})
        self.fails(400, "PUT", "/api/settings", {"adults": 0})
        self.ok("PUT", "/api/settings", {"adults": 0, "children": 1})
        st = self.ok("GET", "/api/state")["settings"]
        self.assertEqual((st["adults"], st["children"]), (0, 1))

    def test_pets_count_towards_food_and_water(self):                  # enhancement E
        self.wipe()
        self.add_item("Rations", "food", "pack", kcal=4400, batches=[(10, None)])   # 44,000 kcal
        self.add_item("Water", "water", "bottle", litres=6, batches=[(10, None)])   # 60 L
        s = self.ok("GET", "/api/summary")
        self.assertEqual((s["food_days"], s["water_days"], s["pets"]), (10, 10, 0))  # 2 adults: 4400 kcal, 6 L
        self.ok("PUT", "/api/settings", {"pets": 2, "kcal_per_pet": 550, "water_per_pet": 1.5})
        s = self.ok("GET", "/api/summary")
        self.assertEqual((s["food_days"], s["water_days"], s["pets"], s["people"]), (8, 6.6, 2, 2))
        self.fails(400, "PUT", "/api/settings", {"pets": "lots"})


class TestTargetRules(ServerTest):                                       # enhancement F
    def tearDown(self):
        self.ok("PUT", "/api/settings", {"adults": 2, "children": 0, "pets": 0, "target_days": 30})

    def test_starter_targets_rescale(self):
        self.wipe()
        self.ok("PUT", "/api/settings", {"adults": 2, "children": 0, "target_days": 30})
        self.assertGreater(self.ok("POST", "/api/seed", {})["added"], 50)
        items = {it["name"]: it for it in self.ok("GET", "/api/state")["items"]}
        water, torch, coffee = items["Bottled water (5L)"], items["LED torch"], items["Coffee"]
        self.assertEqual(json.loads(water["target_rule"]), ["water", 1.0])
        self.assertEqual(water["target_qty"], 36)          # 2 people x 3 L x 30 days / 5 L
        self.assertEqual(torch["target_qty"], 2)
        self.assertEqual(coffee["target_rule"], "")        # a fixed target
        # Set the torch target by hand: it stops scaling.
        self.ok("PUT", "/api/items/%d" % torch["id"], {"target_qty": 5})
        # Saving the water without changing its target keeps it scaling.
        self.ok("PUT", "/api/items/%d" % water["id"], {"notes": "Garage", "target_qty": 36})
        out = self.ok("PUT", "/api/settings", {"adults": 4})
        self.assertGreater(out["rescaled"], 10)
        items = {it["name"]: it for it in self.ok("GET", "/api/state")["items"]}
        self.assertEqual(items["Bottled water (5L)"]["target_qty"], 72)
        self.assertEqual(items["LED torch"]["target_qty"], 5)
        self.assertEqual(items["LED torch"]["target_rule"], "")
        self.assertEqual(items["Coffee"]["target_qty"], 2)
        self.ok("PUT", "/api/settings", {"pets": 1, "water_per_pet": 6})   # pets drink too
        self.assertEqual(self.item(water["id"])["target_qty"], 108)
        self.ok("PUT", "/api/settings", {"target_days": 7})
        self.assertEqual(self.item(water["id"])["target_qty"], 26)        # 18 L a day x 7 / 5, rounded up
        # Undo and backups keep the rule.
        res = self.ok("DELETE", "/api/items/%d" % water["id"])
        self.ok("POST", "/api/restore-item", res["undo"])
        self.assertEqual(json.loads(self.item(water["id"])["target_rule"]), ["water", 1.0])


class TestUndo(ServerTest):
    def setUp(self):
        self.wipe()

    def test_undo_use(self):
        i = self.add_item("Candles", "power", batches=[(5, None)])
        res = self.ok("POST", "/api/items/%d/use" % i, {"qty": 2})
        self.assertIn("updated_at", res["undo"])
        self.ok("POST", "/api/restore-item", res["undo"])
        self.assertEqual(sum(b["qty"] for b in self.item(i)["batches"]), 5)

    def test_undo_refused_after_a_later_change(self):                  # fix 5
        i = self.add_item("Matches", "cooking", batches=[(5, None)])
        res = self.ok("POST", "/api/items/%d/use" % i, {"qty": 1})
        self.ok("POST", "/api/items/%d/stock" % i, {"qty": 10})     # straight after, same second
        out = self.fails(409, "POST", "/api/restore-item", res["undo"])
        self.assertIn("changed since", out["error"])
        self.assertEqual(sum(b["qty"] for b in self.item(i)["batches"]), 14)   # the newer change survives

    def test_undo_add_stock(self):                                        # enhancement D (Add stock, Got it)
        i = self.add_item("Plasters", "medical", target=3, batches=[(1, day(300))])
        res = self.ok("POST", "/api/items/%d/stock" % i, {"qty": 2, "expiry": day(400), "location": "Shelf"})
        self.assertTrue(res["ok"])
        self.assertEqual(len(self.item(i)["batches"]), 2)
        self.ok("POST", "/api/restore-item", res["undo"])
        batches = self.item(i)["batches"]
        self.assertEqual([(b["qty"], b["expiry"]) for b in batches], [(1, day(300))])
        self.fails(409, "POST", "/api/restore-item", res["undo"])   # already undone (and changed by it)

    def test_undo_delete_only_once(self):
        i = self.add_item("Rope", "tools", batches=[(1, None)])
        res = self.ok("DELETE", "/api/items/%d" % i)
        self.ok("POST", "/api/restore-item", res["undo"])
        self.assertIsNotNone(self.item(i))
        self.fails(409, "POST", "/api/restore-item", res["undo"])

    def test_old_style_snapshot_still_works(self):
        i = self.add_item("Tape", "tools", batches=[(3, None)])
        res = self.ok("POST", "/api/items/%d/use" % i, {"qty": 1})
        snap = dict(res["undo"])
        del snap["updated_at"]
        self.ok("POST", "/api/restore-item", snap)
        self.assertEqual(sum(b["qty"] for b in self.item(i)["batches"]), 3)


class TestValidation(ServerTest):
    def test_ascii_digits_only(self):                                    # fix 13
        i = self.add_item("Gloves", "tools")
        self.fails(400, "POST", "/api/items/%d/stock" % i, {"qty": 1, "expiry": "٢٠٢٧-٠١-٠١"})
        self.fails(400, "POST", "/api/items/%d/stock" % i, {"qty": 1, "expiry": "２０２７-01-01"})
        self.fails(400, "POST", "/api/items/%d/stock" % i, {"qty": "٣"})
        self.fails(400, "POST", "/api/items/%d/stock" % i, {"qty": "inf"})
        self.ok("POST", "/api/items/%d/stock" % i, {"qty": "2.5", "expiry": "2027-01-01"})
        self.fails(400, "POST", "/api/items/delete", {"ids": ["١"]})
        status, _ = self.srv.call("GET", "/api/items/%s" % urllib.request.quote("١"))
        self.assertEqual(status, 404)
        status, _ = self.srv.call("DELETE", "/api/items/%s" % urllib.request.quote("١"))
        self.assertEqual(status, 404)

    def test_shopping_done_must_be_boolean(self):                        # fix 14
        sid = self.ok("POST", "/api/shopping", {"text": "Fuses"})["id"]
        for bad in ("yes", "true", "1", None, 2, [], {}):
            self.fails(400, "PUT", "/api/shopping/%d" % sid, {"done": bad})
        for good, want in ((True, 1), (False, 0), (1, 1), (0, 0), (1.0, 1)):
            self.ok("PUT", "/api/shopping/%d" % sid, {"done": good})
            row = [s for s in self.ok("GET", "/api/state")["shopping"] if s["id"] == sid][0]
            self.assertEqual(row["done"], want)
        self.ok("PUT", "/api/shopping/%d" % sid, {"text": "Spare fuses"})   # enhancement C relies on this
        row = [s for s in self.ok("GET", "/api/state")["shopping"] if s["id"] == sid][0]
        self.assertEqual(row["text"], "Spare fuses")

    def test_csv_formula_injection(self):                                # fix 15
        self.add_item("=HYPERLINK(\"http://x\")", "other", unit="+1", batches=[(1, None)])
        self.add_item("@SUM(A1)", "other")
        self.add_item("-2+3", "other")
        self.add_item("\tTabbed", "other")
        self.add_item("Plain beans", "food")
        status, data, headers = self.srv.call("GET", "/api/export.csv", raw=True)
        self.assertEqual(status, 200)
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
        names = [r[1] for r in rows[1:]]
        self.assertIn("'=HYPERLINK(\"http://x\")", names)
        self.assertIn("'@SUM(A1)", names)
        self.assertIn("'-2+3", names)
        self.assertIn("Plain beans", names)
        self.assertFalse([n for n in names if n[:1] in "=+-@\t\r"])
        self.assertIn("'+1", [r[3] for r in rows[1:]])

    def test_health_and_header(self):                                    # fix 7, and fix 19's header
        status, body, headers = self.srv.call("GET", "/api/health", raw=True)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        self.assertTrue(headers.get("X-Dads-Army"))


class TestRestore(ServerTest):
    def backup(self):
        status, data, _ = self.srv.call("GET", "/api/backup.json", raw=True)
        self.assertEqual(status, 200)
        return json.loads(data.decode("utf-8"))

    def backups(self):
        return self.ok("GET", "/api/backups")["backups"]

    def test_empty_restore_needs_confirming(self):                       # fix 10
        self.add_item("Kettle", "cooking", batches=[(1, None)])
        empty = {"app": "dadsarmy", "items": [], "shopping": [], "settings": {}}
        out = self.fails(400, "POST", "/api/restore", empty)
        self.assertIn("empty", out["error"])
        self.assertTrue(self.ok("GET", "/api/state")["items"])
        self.fails(400, "POST", "/api/restore", dict(empty, confirm_empty="yes"))
        self.assertEqual(self.ok("POST", "/api/restore", dict(empty, confirm_empty=True))["items"], 0)
        self.assertEqual(self.ok("GET", "/api/state")["items"], [])

    def test_pre_restore_copies_kept_by_age(self):                        # fix 10
        bdir = os.path.join(self.tmp, "backups")
        now = time.time()
        made = {}
        for n, age_days in enumerate((40, 30, 20, 13, 10, 8, 5)):
            name = "dadsarmy-2020010%d-000000-pre-restore.db" % (n + 1)
            path = os.path.join(bdir, name)
            shutil.copy(os.path.join(self.tmp, "dadsarmy.db"), path)
            os.utime(path, (now - age_days * 86400, now - age_days * 86400))
            made[name] = age_days
        self.add_item("Lantern", "power", batches=[(1, None)])
        before = set(f for f in os.listdir(bdir) if f.endswith("-pre-restore.db"))
        self.ok("POST", "/api/restore", self.backup())
        left = set(f for f in os.listdir(bdir) if f.endswith("-pre-restore.db"))
        for name, age in made.items():
            self.assertEqual(name in left, age < 14, name)
        self.assertEqual(len(left - before), 1)   # the new one
        self.assertFalse([f for f in os.listdir(bdir) if f.endswith(".tmp")])

    def test_restore_from_automatic_backup(self):                       # enhancement B
        self.wipe()
        for n in range(3):
            self.add_item("Item %d" % n, "other", batches=[(n + 1, None)])
        self.ok("PUT", "/api/settings", {"category_warn_days": {"medical": 45}})
        restored = self.ok("POST", "/api/restore", self.backup())          # makes a pre-restore copy of 3 items
        self.assertEqual(restored["items"], 3)
        self.wipe()
        self.ok("PUT", "/api/settings", {"category_warn_days": {"medical": None}})
        listing = self.backups()
        stamps = [b["at"] for b in listing]
        self.assertEqual(stamps, sorted(stamps, reverse=True))   # newest first
        pre = [b for b in listing if b["kind"] == "pre-restore" and b["items"] == 3]
        self.assertTrue(pre, listing)
        b = pre[0]
        self.assertTrue(b["at"][:4].isdigit())
        before = len([x for x in listing if x["kind"] == "pre-restore"])
        out = self.ok("POST", "/api/backups/restore", {"name": b["name"]})
        self.assertEqual(out["items"], 3)
        st = self.ok("GET", "/api/state")
        self.assertEqual(sorted(it["name"] for it in st["items"]), ["Item 0", "Item 1", "Item 2"])
        self.assertEqual(st["settings"]["category_warn_days"], {"medical": 45})
        self.assertEqual(st["log"][0]["action"], "restored")
        # The restore made its own safety copy first.
        self.assertEqual(len([x for x in self.backups() if x["kind"] == "pre-restore"]), before + 1)
        self.fails(404, "POST", "/api/backups/restore", {"name": "../dadsarmy.db"})
        self.fails(404, "POST", "/api/backups/restore", {"name": "dadsarmy-20200101-000000-auto.db"})

    def test_restore_empty_automatic_backup_needs_confirming(self):
        self.add_item("Whistle", "tools")
        bdir = os.path.join(self.tmp, "backups")
        name = "dadsarmy-20200101-120000-auto.db"
        con = sqlite3.connect(os.path.join(bdir, name))
        con.executescript(V140_SCHEMA)   # an old, empty backup
        con.close()
        info = [b for b in self.backups() if b["name"] == name][0]
        self.assertEqual((info["items"], info["kind"], info["at"]), (0, "auto", "2020-01-01 12:00:00"))
        self.fails(400, "POST", "/api/backups/restore", {"name": name})
        self.assertTrue(self.ok("GET", "/api/state")["items"])
        self.ok("POST", "/api/backups/restore", {"name": name, "confirm_empty": True})
        self.assertEqual(self.ok("GET", "/api/state")["items"], [])
        os.remove(os.path.join(bdir, name))


class TestMigrationFrom140(ServerTest):
    @classmethod
    def prepare(cls, data_dir):
        make_v140_db(data_dir)

    def test_old_database_still_works(self):
        st = self.ok("GET", "/api/state")
        with open(SERVER, encoding="utf-8") as f:
            version = re.search(r'^VERSION = "([^"]+)"', f.read(), re.M).group(1)
        self.assertEqual(st["server"]["version"], version)
        beans = sorted(st["items"], key=lambda it: it["id"])[0]
        self.assertEqual((beans["name"], beans["target_qty"], beans["target_rule"]), ("Baked beans", 10, ""))
        self.assertEqual([(b["qty"], b["location"]) for b in beans["batches"]], [(4, "Larder")])
        self.assertEqual([s["text"] for s in st["shopping"]], ["Spare fuses"])
        s = st["settings"]
        self.assertEqual((s["adults"], s["children"]), (1, 0))   # 0 people is read as 1
        self.assertEqual((s["pets"], s["kcal_per_pet"], s["water_per_pet"], s["category_warn_days"]), (0, 0, 0, {}))
        summ = self.ok("GET", "/api/summary")
        self.assertEqual(summ["people"], 1)
        self.assertEqual(self.find(summ["low_stock"], "Baked beans")["get"], 6)
        # The new column is really there, and the 'not ours' to-do marker survived.
        con = sqlite3.connect(os.path.join(self.tmp, "dadsarmy.db"))
        try:
            cols = [r[1] for r in con.execute("PRAGMA table_info(items)")]
            marks = con.execute("SELECT key FROM ha_todo").fetchall()
        finally:
            con.close()
        self.assertIn("target_rule", cols)
        self.assertEqual(marks, [("x:abc",)])
        # Normal use carries on.
        res = self.ok("POST", "/api/items/%d/use" % beans["id"], {"qty": 1})
        self.ok("POST", "/api/restore-item", res["undo"])
        self.assertEqual(self.item(beans["id"])["batches"][0]["qty"], 4)


class TestMigrationRulesFrom140(ServerTest):                             # enhancement F, for old databases
    @classmethod
    def prepare(cls, data_dir):
        make_v140_db(data_dir, adults=2)

    def test_untouched_starter_targets_start_scaling(self):
        items = {it["name"]: it for it in self.ok("GET", "/api/state")["items"]}
        self.assertEqual(json.loads(items["Toilet roll"]["target_rule"]), ["perday", 0.25])   # 15 = 2 x 30 x 0.25
        self.assertEqual(items["Soap"]["target_rule"], "")         # 9 isn't 2 per person: changed by hand
        self.assertEqual(items["Baked beans"]["target_rule"], "")  # not a starter name
        self.ok("PUT", "/api/settings", {"adults": 4})
        items = {it["name"]: it for it in self.ok("GET", "/api/state")["items"]}
        self.assertEqual((items["Toilet roll"]["target_qty"], items["Soap"]["target_qty"]), (30, 9))


# ---------------------------------------------------------------------------
# Home Assistant sync, in-process with a pretend Home Assistant.
class FakeTodo(object):
    def __init__(self):
        self.items = []   # dicts: uid, summary, status
        self.n = 0
        self.calls = []

    def add(self, summary, status="needs_action"):
        self.n += 1
        self.items.append({"uid": "u%d" % self.n, "summary": summary, "status": status})
        return "u%d" % self.n

    def get(self, uid):
        return [i for i in self.items if i["uid"] == uid][0]

    def request(self, method, path, body=None, timeout=10):
        if path.startswith("/states/todo."):
            return 200, {"entity_id": path[8:], "attributes": {"friendly_name": "Supply run"}}
        if path.startswith("/services/todo/"):
            service = path.split("/")[3].split("?")[0]
            self.calls.append((service, body))
            if service == "get_items":
                return 200, {"service_response": {body["entity_id"]: {"items": [dict(i) for i in self.items]}}}
            if service == "add_item":
                self.add(body["item"])
            elif service == "update_item":
                it = self.get(body["item"])
                if "rename" in body:
                    it["summary"] = body["rename"]
                if "status" in body:
                    it["status"] = body["status"]
            elif service == "remove_item":
                gone = body["item"] if isinstance(body["item"], list) else [body["item"]]
                self.items = [i for i in self.items if i["uid"] not in gone]
            return 200, []
        return 404, None


class TestTodoSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server   # the module, against a temporary database
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
            for t in ("items", "batches", "shopping", "ha_todo"):
                db.execute("DELETE FROM %s" % t)
            s.set_setting_raw(db, "ha_todo_fresh", 0)
        self.ha = FakeTodo()
        self._orig = s.ha_request
        s.ha_request = self.ha.request

    def tearDown(self):
        self.s.ha_request = self._orig

    def sync(self):
        return self.s.todo_sync("todo.supply_run", self.s.summary())

    def item(self, name, target, qty):
        with self.s.tx() as db:
            ts = self.s.now_iso()
            cur = db.execute("INSERT INTO items(name, category, unit, target_qty, created_at, updated_at)"
                             " VALUES (?, 'tools', 'roll', ?, ?, ?)", (name, target, ts, ts))
            if qty:
                db.execute("INSERT INTO batches(item_id, qty, added_at) VALUES (?, ?, ?)", (cur.lastrowid, qty, ts))
        return cur.lastrowid

    def tracked(self):
        return {r["key"]: dict(r) for r in self.s.DB.execute("SELECT * FROM ha_todo")}

    def test_emptied_list_keeps_not_ours_markers(self):                  # fix 2
        theirs = self.ha.add("Their own thing")
        with self.s.tx() as db:
            db.execute("INSERT INTO ha_todo(key, uid) VALUES (?, ?)", ("x:" + theirs, theirs))
            for n in range(5):
                sid = db.execute("INSERT INTO shopping(text, created_at) VALUES (?, '')", ("Extra %d" % n,)).lastrowid
                db.execute("INSERT INTO ha_todo(key, uid, summary) VALUES (?, ?, ?)",
                           ("s:%d" % sid, "gone%d" % n, "Extra %d" % n))
        self.sync()
        self.assertIn("x:" + theirs, self.tracked())
        self.assertEqual(len([i for i in self.ha.items if i["summary"] == "Their own thing"]), 1)
        self.assertEqual(len(self.s.DB.execute("SELECT * FROM shopping").fetchall()), 5)   # not deleted
        self.assertEqual(len(self.ha.items), 6)

    def test_rename_unticks(self):                                         # fix 3
        i = self.item("Tape", 4, 1)
        self.sync()
        uid = self.tracked()["i:%d" % i]["uid"]
        self.assertEqual(self.ha.get(uid)["summary"], "Tape: 3 rolls")
        self.ha.get(uid)["status"] = "completed"
        self.sync()
        self.assertEqual(self.tracked()["i:%d" % i]["done"], 1)
        with self.s.tx() as db:
            db.execute("UPDATE batches SET qty = 2 WHERE item_id = ?", (i,))
        self.sync()
        self.assertEqual(self.ha.get(uid), {"uid": uid, "summary": "Tape: 2 rolls", "status": "needs_action"})
        self.assertEqual(self.tracked()["i:%d" % i]["done"], 0)

    def test_changes_made_here_during_sync_win(self):                    # fix 6
        with self.s.tx() as db:
            sid = db.execute("INSERT INTO shopping(text, created_at) VALUES ('Fuses', '')").lastrowid
        self.sync()
        uid = self.tracked()["s:%d" % sid]["uid"]
        self.ha.get(uid)["summary"] = "Fuses 13A"      # renamed in Home Assistant...
        self.item("Rope", 2, 0)                         # (so the sync has something to add there)
        orig = self.ha.request

        def slow(method, path, body=None, timeout=10):  # ...and renamed here while the sync talks to it
            out = orig(method, path, body, timeout)
            if "add_item" in path:
                with self.s.tx() as db:
                    db.execute("UPDATE shopping SET text = 'Fuses 5A' WHERE id = ?", (sid,))
            return out
        self.s.ha_request = slow
        self.sync()
        self.s.ha_request = orig
        text = self.s.DB.execute("SELECT text FROM shopping WHERE id = ?", (sid,)).fetchone()[0]
        self.assertEqual(text, "Fuses 5A")
        self.sync()
        self.assertEqual(self.ha.get(uid)["summary"], "Fuses 5A")

    def test_no_rewrite_when_unchanged(self):                             # fix 8
        self.item("Rope", 2, 0)
        self.sync()
        self.s.DB.execute("CREATE TEMP TRIGGER watch AFTER DELETE ON ha_todo BEGIN"
                          " SELECT RAISE(ABORT, 'rewritten'); END")
        try:
            self.assertFalse(self.sync())   # would raise if ha_todo were rewritten
        finally:
            self.s.DB.execute("DROP TRIGGER temp.watch")


class TestRanOutEvents(unittest.TestCase):                                # fix 4
    def test_event_not_lost_while_home_assistant_is_down(self):
        import server
        posts = []
        state = {"up": False, "rounds": 0}
        levels = [{1: {"id": 1, "name": "Beans", "unit": "tin", "target_qty": 2, "total": 3}},
                  {1: {"id": 1, "name": "Beans", "unit": "tin", "target_qty": 2, "total": 0}}]

        def call(method, path, body=None, timeout=10):
            if path.startswith("/events/"):
                posts.append(body)
                return 200 if state["up"] else 502
            return 200 if state["up"] else 502

        class Stop(Exception):
            pass

        def stock_levels():
            state["rounds"] += 1
            if state["rounds"] == 3:
                state["up"] = True     # Home Assistant is back
            if state["rounds"] > 4:
                raise Stop()
            return levels[0] if state["rounds"] == 1 else levels[1]

        saved = (server.ha_call, server.stock_levels, server.summary, server.todo_entity, server.HA_WAKE,
                 server.time.sleep, server.traceback.print_exc)
        saved_checks = server.checks_entity
        server.checks_entity = lambda: ""   # no checks list linked (it would read the settings table)
        fake_summary = {"readiness_pct": 0, "hold_out_days": 0, "target_days": 30, "food_days": 0,
                        "water_days": 0, "runs_out_first": "", "people": 1, "kit_stocked_pct": 0,
                        "out_of_stock": [], "low_stock": [], "expired": [], "newly_expired": [],
                        "expiring_soon": [], "expires_today": [], "warn_days": 30, "next_expiry": None,
                        "supply_run": {"below_target": [], "extras": []}}

        class Wake(object):
            def wait(self, t):
                return True

            def set(self):
                pass

            def clear(self):
                pass

        def stop_on_stop():
            if isinstance(sys.exc_info()[1], Stop):
                raise sys.exc_info()[1]

        server.ha_call, server.stock_levels = call, stock_levels
        server.summary, server.todo_entity, server.HA_WAKE = (lambda: fake_summary), (lambda: ""), Wake()
        server.time.sleep = lambda s: None
        server.traceback.print_exc = stop_on_stop
        try:
            with self.assertRaises(Stop):
                server.ha_loop()
        finally:
            (server.ha_call, server.stock_levels, server.summary, server.todo_entity, server.HA_WAKE,
             server.time.sleep, server.traceback.print_exc) = saved
            server.checks_entity = saved_checks
        # Round 1: baseline. Round 2: ran out, but Home Assistant is down. Round 3: sent. Round 4: not again.
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[-1]["names"], "Beans")


if __name__ == "__main__":
    unittest.main()
