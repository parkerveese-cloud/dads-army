#!/usr/bin/env python3
"""
Dads Army - home front stores tracker.

A zero-dependency web app server. It needs nothing but Python 3.7+ (already
installed on Raspberry Pi OS), so it keeps working with no internet access.

    python3 server.py

then open http://<your-pi-address>:8080 on your phone.

Environment variables (all optional):
    DADSARMY_PORT          port to listen on              (default 8080)
    DADSARMY_HOST          address to bind                (default 0.0.0.0 = whole home network)
    DADSARMY_DATA          folder for database + backups  (default ./data)
    DADSARMY_KEEP_BACKUPS  daily backups to keep          (default 14)

Running as a Home Assistant app, it also:
  - publishes sensor.dads_army_* entities (readiness, hold-out days, out of stock,
    running low, expired, expiring soon, checks due, daily supplies and more)
  - works out a household alert level (LOW to CRITICAL) from warnings, the stores and
    the home's own sensors, with guidance, as sensor.dads_army_alert_level
  - fires a dads_army_ran_out event when something runs out, and dads_army_warning
    for new Met Office, flood, Emergency Alert or GDACS warnings, for phone alerts
  - can keep the supply run, and the routine checks that are due, in step with
    Home Assistant to-do lists, and build a ready-made dashboard (HQ screen)
GET /api/summary returns the same figures as JSON for anything else.
"""
import base64
import csv
import hashlib
import datetime as dt
import html as htmllib
import io
import json
import math
import os
import re
import signal
import socket
import sqlite3
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

VERSION = "1.8.1"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.realpath(os.path.join(APP_DIR, "static"))
DATA_DIR = os.path.abspath(os.environ.get("DADSARMY_DATA", os.path.join(APP_DIR, "data")))
DB_PATH = os.path.join(DATA_DIR, "dadsarmy.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
HOST = os.environ.get("DADSARMY_HOST", "0.0.0.0")
PORT = int(os.environ.get("DADSARMY_PORT", "8080"))
KEEP_BACKUPS = max(1, int(os.environ.get("DADSARMY_KEEP_BACKUPS", "14")))
MAX_BODY = 20 * 1024 * 1024

CATEGORIES = ["food", "water", "medical", "power", "cooking", "hygiene",
              "tools", "comms", "shelter", "docs", "pets", "other"]

DEFAULT_SETTINGS = {
    "adults": 2,
    "children": 0,
    "kcal_adult": 2200,
    "kcal_child": 1600,
    "water_per_person": 3,
    "target_days": 30,
    "warn_days": 30,
}
# (min, max, integer?)
SETTING_RULES = {
    "adults": (0, 50, True),
    "children": (0, 50, True),
    "kcal_adult": (500, 6000, True),
    "kcal_child": (300, 4000, True),
    "water_per_person": (0.5, 20, False),
    "target_days": (1, 3650, True),
    "warn_days": (1, 365, True),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'other',
    unit            TEXT    NOT NULL DEFAULT '',
    kcal_per_unit   REAL    NOT NULL DEFAULT 0,
    litres_per_unit REAL    NOT NULL DEFAULT 0,
    target_qty      REAL    NOT NULL DEFAULT 0,
    per_day         REAL    NOT NULL DEFAULT 0,
    price           REAL    NOT NULL DEFAULT 0,
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
-- Links between the supply run and a Home Assistant to-do list (see todo_sync).
--   key: i:<item id> (below target), s:<shopping id> (extra), x:<uid> (not ours, left alone)
CREATE TABLE IF NOT EXISTS ha_todo (
    key     TEXT PRIMARY KEY,
    uid     TEXT    NOT NULL DEFAULT '',
    summary TEXT    NOT NULL DEFAULT '',
    done    INTEGER NOT NULL DEFAULT 0
);
-- Routine checks: test the alarms, charge the power banks, rotate the water...
CREATE TABLE IF NOT EXISTS checks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    every_days INTEGER NOT NULL DEFAULT 90,
    last_done  TEXT,
    notes      TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);
"""
# Columns added to items after 1.0, for databases made by older versions.
ITEM_UPGRADES = [("per_day", "REAL NOT NULL DEFAULT 0"), ("price", "REAL NOT NULL DEFAULT 0")]
ITEM_FIELDS = ("name", "category", "unit", "kcal_per_unit", "litres_per_unit", "target_qty", "per_day", "price",
               "notes")

# --------------------------------------------------------------------------
# Starter list. Targets scale to the household (see resolve_target).
#   ("kcal", share)   -> share of the household's calorie need for the target period
#   ("water", share)  -> share of the household's water need for the target period
#   ("people", n)     -> n per person
#   ("perday", n)     -> n per person per day of the target period
# kcal figures are typical label values - check your own tins.
# --------------------------------------------------------------------------
def K(share): return ("kcal", share)
def P(n): return ("people", n)
def PD(n): return ("perday", n)


STARTER = [
    # name, category, unit, kcal/unit, litres/unit, target, notes
    ("Rice (1kg bag)", "food", "bag", 3600, 0, K(.14), ""),
    ("Pasta (500g)", "food", "pack", 1780, 0, K(.10), ""),
    ("Porridge oats (1kg)", "food", "bag", 3750, 0, K(.08), ""),
    ("Baked beans (415g)", "food", "tin", 340, 0, K(.06), ""),
    ("Tinned chickpeas (400g)", "food", "tin", 280, 0, K(.03), ""),
    ("Tinned fish (mackerel, sardines)", "food", "tin", 250, 0, K(.04), ""),
    ("Corned beef (340g)", "food", "tin", 750, 0, K(.05), ""),
    ("Tinned chilli or stew (400g)", "food", "tin", 400, 0, K(.05), ""),
    ("Tinned soup (400g)", "food", "tin", 200, 0, K(.03), ""),
    ("Chopped tomatoes (400g)", "food", "tin", 80, 0, K(.005), ""),
    ("Tinned vegetables", "food", "tin", 150, 0, K(.02), ""),
    ("Tinned fruit (410g)", "food", "tin", 250, 0, K(.02), ""),
    ("Tinned potatoes (560g)", "food", "tin", 210, 0, K(.02), ""),
    ("Peanut butter (340g)", "food", "jar", 2050, 0, K(.06), ""),
    ("Honey or jam (340g)", "food", "jar", 1000, 0, K(.02), ""),
    ("Crackers or crispbread", "food", "pack", 880, 0, K(.04), ""),
    ("Cereal bars (multipack)", "food", "pack", 600, 0, K(.03), ""),
    ("Nuts & dried fruit (500g)", "food", "bag", 2300, 0, K(.04), ""),
    ("UHT milk (1L)", "food", "carton", 470, 0, K(.02), ""),
    ("Dried milk powder (400g)", "food", "tin", 1440, 0, K(.02), ""),
    ("Sugar (1kg)", "food", "bag", 4000, 0, K(.03), ""),
    ("Cooking oil (1L)", "food", "bottle", 8280, 0, K(.04), ""),
    ("Instant noodles", "food", "pack", 330, 0, K(.03), ""),
    ("Chocolate (100g bar)", "food", "bar", 530, 0, K(.025), "Morale matters."),
    ("Tea bags (80)", "food", "box", 0, 0, PD(.025), ""),
    ("Coffee", "food", "jar", 0, 0, 2, ""),
    ("Salt", "food", "tub", 0, 0, 1, ""),
    ("Stock cubes", "food", "pack", 0, 0, 2, ""),

    ("Bottled water (5L)", "water", "bottle", 0, 5, ("water", 1.0),
     "Store somewhere cool and dark, and rotate it."),
    ("Water purification tablets", "water", "pack", 0, 0, 2, ""),
    ("Water filter (gravity or straw)", "water", "each", 0, 0, 1, ""),
    ("Collapsible water carrier (20L)", "water", "each", 0, 0, 2,
     "Empty container for collecting water - doesn't count towards supply."),

    ("First aid kit", "medical", "kit", 0, 0, 1, ""),
    ("Paracetamol (16)", "medical", "pack", 0, 0, 4, ""),
    ("Ibuprofen (16)", "medical", "pack", 0, 0, 4, ""),
    ("Plasters", "medical", "box", 0, 0, 2, ""),
    ("Antiseptic cream or wipes", "medical", "each", 0, 0, 2, ""),
    ("Oral rehydration sachets", "medical", "pack", 0, 0, P(1), ""),
    ("Antihistamines", "medical", "pack", 0, 0, 2, ""),
    ("Prescription medicines (spare)", "medical", "supply", 0, 0, 1,
     "Ask your GP or pharmacist about holding a spare supply."),
    ("Multivitamins", "medical", "tub", 0, 0, P(1), ""),
    ("Digital thermometer", "medical", "each", 0, 0, 1, ""),
    ("Disposable gloves", "medical", "box", 0, 0, 1, ""),

    ("LED torch", "power", "each", 0, 0, P(1), ""),
    ("Head torch", "power", "each", 0, 0, 2, ""),
    ("AA batteries", "power", "pack", 0, 0, 4, ""),
    ("AAA batteries", "power", "pack", 0, 0, 2, ""),
    ("Power bank", "power", "each", 0, 0, 2, "Keep them charged - top up monthly."),
    ("Candles", "power", "each", 0, 0, 20, "Never leave a lit candle unattended."),
    ("Battery or solar lantern", "power", "each", 0, 0, 1, ""),
    ("Solar phone charger", "power", "each", 0, 0, 1, ""),

    ("Camping stove", "cooking", "each", 0, 0, 1,
     "Only use outdoors or somewhere very well ventilated."),
    ("Stove gas canisters", "cooking", "canister", 0, 0, PD(.1), ""),
    ("Matches", "cooking", "box", 0, 0, 5, ""),
    ("Lighters", "cooking", "each", 0, 0, 4, ""),
    ("Manual tin opener", "cooking", "each", 0, 0, 2, "Essential - most of the food is in tins."),
    ("Camping pan or kettle", "cooking", "each", 0, 0, 1, ""),
    ("Foil & food bags", "cooking", "roll", 0, 0, 2, ""),

    ("Toilet roll", "hygiene", "roll", 0, 0, PD(.25), ""),
    ("Wet wipes", "hygiene", "pack", 0, 0, PD(.1), ""),
    ("Hand sanitiser", "hygiene", "bottle", 0, 0, P(1), ""),
    ("Soap", "hygiene", "bar", 0, 0, P(2), ""),
    ("Toothpaste", "hygiene", "tube", 0, 0, P(1), ""),
    ("Spare toothbrushes", "hygiene", "each", 0, 0, P(1), ""),
    ("Bin bags", "hygiene", "roll", 0, 0, 4, ""),
    ("Sanitary products", "hygiene", "pack", 0, 0, 2, ""),
    ("Bleach (unscented)", "hygiene", "bottle", 0, 0, 2, "For cleaning and disinfecting."),
    ("Bucket with lid", "hygiene", "each", 0, 0, 1, "Emergency toilet if water or sewage fails."),

    ("Multi-tool or penknife", "tools", "each", 0, 0, 1, ""),
    ("Duct tape", "tools", "roll", 0, 0, 2, ""),
    ("Work gloves", "tools", "pair", 0, 0, 2, ""),
    ("Whistle", "tools", "each", 0, 0, P(1), ""),
    ("Paracord or rope", "tools", "length", 0, 0, 1, ""),
    ("Fire extinguisher", "tools", "each", 0, 0, 1, ""),
    ("Dust masks", "tools", "pack", 0, 0, 1, ""),
    ("Plastic sheeting", "tools", "roll", 0, 0, 1, ""),
    ("Basic tool kit", "tools", "kit", 0, 0, 1, ""),

    ("Wind-up or battery radio", "comms", "each", 0, 0, 1,
     "For emergency broadcasts when the internet is down."),
    ("Printed contact list", "comms", "copy", 0, 0, 2, "The numbers you'd need without your phone."),
    ("Walkie-talkies", "comms", "pair", 0, 0, 1, ""),
    ("Spare charging cables", "comms", "each", 0, 0, 2, ""),
    ("Paper map of the area", "comms", "each", 0, 0, 1, ""),
    ("Notebook & pencils", "comms", "set", 0, 0, 1, ""),

    ("Sleeping bags", "shelter", "each", 0, 0, P(1), ""),
    ("Foil emergency blankets", "shelter", "each", 0, 0, P(2), ""),
    ("Waterproof jackets", "shelter", "each", 0, 0, P(1), ""),
    ("Warm hats & gloves", "shelter", "set", 0, 0, P(1), ""),
    ("Thermal base layers", "shelter", "set", 0, 0, P(1), ""),
    ("Tarpaulin", "shelter", "each", 0, 0, 1, ""),

    ("Emergency cash (small notes)", "docs", "£", 0, 0, 200,
     "Card readers and cash machines need power."),
    ("Copies of ID & passports", "docs", "set", 0, 0, 1, ""),
    ("Insurance & bank details (copy)", "docs", "set", 0, 0, 1, ""),
    ("USB stick with scanned documents", "docs", "each", 0, 0, 1, ""),
    ("Spare house & car keys", "docs", "set", 0, 0, 1, ""),

    ("Grab bag (packed & ready)", "other", "bag", 0, 0, 1,
     "A rucksack ready to go if you have to leave in a hurry."),
]


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Raw(object):
    """A non-JSON API response (CSV, file download)."""

    def __init__(self, data, content_type, filename=None):
        self.data = data
        self.content_type = content_type
        self.filename = filename


LOCK = threading.RLock()
DB = None
LAST_BACKUP = {"at": None}


def now_iso():
    return dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


class tx(object):
    """Serialised write transaction."""

    def __enter__(self):
        LOCK.acquire()
        try:
            DB.execute("BEGIN IMMEDIATE")
        except Exception:
            LOCK.release()
            raise
        return DB

    def __exit__(self, exc_type, exc, tb):
        try:
            DB.execute("COMMIT" if exc_type is None else "ROLLBACK")
        finally:
            LOCK.release()
        return False


def init_db():
    global DB
    os.makedirs(BACKUP_DIR, exist_ok=True)
    DB = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    DB.row_factory = sqlite3.Row
    DB.execute("PRAGMA foreign_keys = ON")
    DB.execute("PRAGMA journal_mode = WAL")
    DB.executescript(SCHEMA)
    have = set(r[1] for r in DB.execute("PRAGMA table_info(items)"))
    for col, decl in ITEM_UPGRADES:
        if col not in have:
            DB.execute("ALTER TABLE items ADD COLUMN %s %s" % (col, decl))
    for key, value in DEFAULT_SETTINGS.items():
        DB.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(value)))


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_text(value, maxlen, default=""):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ApiError(400, "Invalid text value")
    return str(value).strip()[:maxlen]


def clean_num(value, default=0.0, lo=0.0, hi=1e7, field="Value"):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ApiError(400, "%s must be a number" % field)
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ApiError(400, "%s must be a number" % field)
    if math.isnan(f) or math.isinf(f):
        raise ApiError(400, "%s must be a number" % field)
    return min(hi, max(lo, round(f, 3)))


def clean_date(value):
    if value in (None, ""):
        return None
    value = str(value).strip()
    if not DATE_RE.match(value):
        raise ApiError(400, "Dates must look like 2027-03-31")
    try:
        dt.date(int(value[:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        raise ApiError(400, "%s isn't a real date" % value)
    return value


def clean_item(body, partial=False):
    out = {}
    if not partial or "name" in body:
        name = clean_text(body.get("name"), 120)
        if not name:
            raise ApiError(400, "Give the item a name")
        out["name"] = name
    if not partial or "category" in body:
        cat = clean_text(body.get("category"), 20, "other")
        out["category"] = cat if cat in CATEGORIES else "other"
    if not partial or "unit" in body:
        out["unit"] = clean_text(body.get("unit"), 30)
    for field, label in (("kcal_per_unit", "Calories"), ("litres_per_unit", "Litres"), ("target_qty", "Target"),
                         ("per_day", "Daily use"), ("price", "Price")):
        if not partial or field in body:
            out[field] = clean_num(body.get(field), 0, 0, 1e7, label)
    if not partial or "notes" in body:
        out["notes"] = clean_text(body.get("notes"), 2000)
    return out


def insert_item(db, data, created, updated, item_id=None):
    cols = (("id",) if item_id is not None else ()) + ITEM_FIELDS + ("created_at", "updated_at")
    vals = ([item_id] if item_id is not None else []) + [data[k] for k in ITEM_FIELDS] + [created, updated]
    return db.execute("INSERT INTO items(%s) VALUES (%s)" % (", ".join(cols), ", ".join("?" * len(cols))),
                      vals).lastrowid


def fq(q):
    """Format a quantity: 3.0 -> '3', 2.50 -> '2.5'."""
    q = round(float(q), 3)
    if q == int(q):
        return str(int(q))
    return ("%.3f" % q).rstrip("0").rstrip(".")


# Same wording as the phone app (static/app.js: plural, qu, span, expiryWords).
NO_PLURAL = {"each", "kg", "g", "ml", "l", "kcal", "oz", "lb", "lbs", "cl"}


def plural(unit, q):
    if (not unit or q == 1 or unit.lower() in NO_PLURAL or not re.match(r"^[a-z]+$", unit, re.I)
            or len(unit) < 3 or unit.lower().endswith("s")):
        return unit
    if re.search(r"(x|ch|sh)$", unit, re.I):
        return unit + "es"
    if re.search(r"[^aeiou]y$", unit, re.I):
        return unit[:-1] + "ies"
    return unit + "s"


def qu(q, unit):
    if unit in ("£", "$", "€"):
        return unit + fq(q)
    return "%s %s" % (fq(q), plural(unit, q)) if unit else fq(q)


def _round(x):
    return int(math.floor(x + 0.5))


def span(n):
    if n < 14:
        return "%d day%s" % (n, "" if n == 1 else "s")
    if n < 60:
        return "%d weeks" % _round(n / 7.0)
    if n < 730:
        return "%d months" % _round(n / 30.44)
    return "%s years" % fq(round(n / 365.25, 1))


def expiry_words(days):
    if days < 0:
        return "Expired %s ago" % span(-days)
    if days == 0:
        return "Expires today"
    return "%s left" % span(days)


def as_int_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, "Bad id")


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------
def add_log(action, item="", detail=""):
    DB.execute("INSERT INTO log(ts, action, item, detail) VALUES (?, ?, ?, ?)",
               (now_iso(), action, item, detail))
    DB.execute("DELETE FROM log WHERE id <= (SELECT MAX(id) FROM log) - 2000")


def get_settings():
    out = dict(DEFAULT_SETTINGS)
    for row in DB.execute("SELECT key, value FROM settings"):
        if row["key"] in out:
            try:
                out[row["key"]] = json.loads(row["value"])
            except ValueError:
                pass
    return out


def setting_raw(key, default=None):
    """A stored value outside the household settings (not in backups)."""
    row = DB.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except ValueError:
        return default


def set_setting_raw(db, key, value):
    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(value)))


def all_items():
    items = [dict(r) for r in DB.execute("SELECT * FROM items ORDER BY name COLLATE NOCASE")]
    by_item = {}
    for b in DB.execute("SELECT * FROM batches ORDER BY expiry IS NULL, expiry, id"):
        by_item.setdefault(b["item_id"], []).append(dict(b))
    for it in items:
        it["batches"] = by_item.get(it["id"], [])
    return items


LIST_LIMIT = 30  # longest list sent to Home Assistant, to keep its database lean


def _num(x):
    """3.0 -> 3, 2.5 -> 2.5 (tidier in dashboards)."""
    x = round(float(x), 3)
    return int(x) if x == int(x) else x


def _days(x):
    """Round days down to one decimal, like the app: never overstate how long you'd last."""
    return _num(min(9999.0, math.floor(x * 10) / 10.0))


def _days_until(ymd, today):
    try:
        return (dt.date(int(ymd[0:4]), int(ymd[5:7]), int(ymd[8:10])) - today).days
    except (TypeError, ValueError):
        return None


def human_date(d):
    """2027-03-05 -> '5 Mar 2027' (like the app)."""
    return "%d %s %d" % (d.day, d.strftime("%b"), d.year)


def lasts_words(days):
    if days <= 0:
        return "Run out"
    if days < 1:
        return "Less than a day"
    return span(int(math.floor(days)))


def every_words(n):
    """How often a check comes round: 30 -> 'every month', 182 -> 'every 6 months'."""
    n = int(n)
    if n == 1:
        return "every day"
    if n % 7 == 0 and n < 28:
        return "every week" if n == 7 else "every %d weeks" % (n // 7)
    months = n / 30.44
    m = _round(months)
    if m >= 1 and abs(months - m) <= 0.08 * m + 0.05:
        if m % 12 == 0:
            return "every year" if m == 12 else "every %d years" % (m // 12)
        return "every month" if m == 1 else "every %d months" % m
    return "every %d days" % n


CHECK_SOON = 7  # days before a check is due that it shows on the Sitrep


def check_status(c, today):
    """(next due date or None, days until it's due or None, words) for a routine check."""
    due = None
    if c["last_done"]:
        try:
            due = dt.date(int(c["last_done"][:4]), int(c["last_done"][5:7]), int(c["last_done"][8:10])) \
                + dt.timedelta(days=int(c["every_days"]))
        except (TypeError, ValueError):
            due = None
    if due is None:
        return None, None, "Not done yet"
    days = (due - today).days
    if days < 0:
        return due, days, "Overdue by %s" % span(-days)
    if days == 0:
        return due, days, "Due today"
    return due, days, "Due in %s" % span(days)


def summary():
    """What matters at a glance: the same figures the Sitrep screen shows."""
    today = dt.date.today()
    with LOCK:
        st = get_settings()
        items = all_items()
        extras = [r["text"] for r in DB.execute("SELECT text FROM shopping WHERE done = 0 ORDER BY id")]
        checks = [dict(r) for r in DB.execute("SELECT * FROM checks")]
        warnings = warn_brief()
    warn = st["warn_days"]
    people = st["adults"] + st["children"]
    kcal_day = st["adults"] * st["kcal_adult"] + st["children"] * st["kcal_child"]
    water_day = people * st["water_per_person"]
    kcal = litres = 0.0
    kit_n, kit_sum = 0, 0.0
    value = cost = 0.0
    priced = 0
    low, out, expired, soon, upcoming, supplies = [], [], [], [], [], []

    for it in items:
        unit, cat = it["unit"] or "", it["category"]
        total = sum(b["qty"] for b in it["batches"])
        target = it["target_qty"] or 0
        price = it.get("price") or 0
        per_day = it.get("per_day") or 0
        food = cat == "food" and (it["kcal_per_unit"] or 0) > 0
        water = cat == "water" and (it["litres_per_unit"] or 0) > 0
        dated = []
        in_date = 0.0
        for b in it["batches"]:
            d = _days_until(b["expiry"], today) if b["expiry"] else None
            fresh = d is None or d >= 0
            if fresh:
                in_date += b["qty"]
            if food and fresh:
                kcal += b["qty"] * it["kcal_per_unit"]
            if water and fresh:
                litres += b["qty"] * it["litres_per_unit"]
            if d is not None and b["qty"] > 0:
                dated.append((d, b))
                if d >= 0:
                    upcoming.append((d, it, b))

        if price > 0:
            priced += 1
            value += total * price
        if per_day > 0:
            # Out-of-date stock doesn't count, just as for food and water.
            lasts = in_date / per_day
            text = "%s · %s left, %s a day" % (lasts_words(lasts), qu(in_date, unit), fq(per_day))
            if total - in_date > 0:
                text += " (+%s out of date)" % fq(total - in_date)
            supplies.append((lasts, {"id": it["id"], "name": it["name"], "category": cat, "unit": unit,
                                     "have": _num(in_date), "per_day": _num(per_day), "days": _days(lasts),
                                     "text": text}))
        if target > 0 and cat not in ("food", "water"):
            kit_n += 1
            kit_sum += min(1.0, total / target)
        if target > 0 and total < target:
            get = round(target - total, 3)
            cost += get * price
            entry = {"id": it["id"], "name": it["name"], "category": cat, "have": _num(total), "target": _num(target),
                     "unit": unit, "get": _num(get),
                     "text": "Get %s" % qu(get, unit) + (" · have %s of %s" % (fq(total), fq(target))
                                                          if total > 0 else "")}
            if price > 0:
                entry["cost"] = round(get * price, 2)
            (out if total <= 0 else low).append((total / target, entry))

        # Like the app, an item's expiry state comes from its soonest-dated batch.
        if dated:
            d0, b0 = min(dated, key=lambda x: (x[0], x[1]["id"]))
            if d0 < 0:
                hit, bucket = [b for d, b in dated if d < 0], expired
            elif d0 <= warn:
                hit, bucket = [b for d, b in dated if 0 <= d <= warn], soon
            else:
                hit, bucket = None, None
            if hit:
                qty = sum(b["qty"] for b in hit)
                bits = [qu(qty, unit), expiry_words(d0)] + ([b0["location"]] if b0["location"] else [])
                bucket.append((d0, {"name": it["name"], "category": cat, "qty": _num(qty), "unit": unit,
                                    "expiry": b0["expiry"], "days": d0, "location": b0["location"] or "",
                                    "text": " · ".join(bits)}))

    food_days = kcal / kcal_day if kcal_day > 0 else 0.0
    water_days = litres / water_day if water_day > 0 else 0.0
    hold = min(food_days, water_days)
    upcoming.sort(key=lambda x: (x[0], x[1]["name"].lower()))
    nxt = None
    if upcoming:
        d, it, b = upcoming[0]
        nxt = {"name": it["name"], "date": b["expiry"], "days": d, "qty": _num(b["qty"]), "unit": it["unit"] or "",
               "location": b["location"] or "", "text": "%s · %s" % (qu(b["qty"], it["unit"] or ""), expiry_words(d))}

    def ordered(rows):
        return [e for _, e in sorted(rows, key=lambda r: (r[0], r[1]["name"].lower()))]

    checks_due, checks_soon, checks_today, checks_later = [], [], [], []
    for c in checks:
        due, d, text = check_status(c, today)
        e = {"id": c["id"], "name": c["name"], "every_days": c["every_days"], "every": every_words(c["every_days"]),
             "last_done": c["last_done"], "due": due.isoformat() if due else None, "days": d,
             "text": text + " · " + every_words(c["every_days"])}
        if d is None or d <= 0:
            checks_due.append((d if d is not None else 0, e))   # overdue longest first
            if d == 0:
                checks_today.append((0, e))
        else:
            (checks_soon if d <= CHECK_SOON else checks_later).append((d, e))
    later = ordered(checks_soon + checks_later)
    next_check = None
    if later:
        n = later[0]
        next_check = {"name": n["name"], "date": n["due"], "days": n["days"],
                      "text": "%s · %s" % (n["name"], human_date(dt.date.fromisoformat(n["due"])))}

    sup = ordered(supplies)
    target_days = st["target_days"]
    out = {
        "version": VERSION,
        "date": today.isoformat(),
        "people": people,
        "target_days": target_days,
        "warn_days": warn,
        # Hold-out against the readiness target; 100 means the target is met.
        "readiness_pct": min(100, int(math.floor(100.0 * hold / target_days))) if target_days > 0 else 0,
        "hold_out_days": _days(hold),
        "food_days": _days(food_days),
        "water_days": _days(water_days),
        "runs_out_first": "food" if food_days < water_days else "water" if water_days < food_days else "",
        "kit_stocked_pct": _round(100.0 * kit_sum / kit_n) if kit_n else 0,
        "kit_items": kit_n,
        "items_total": len(items),
        "out_of_stock": ordered(out),
        "low_stock": ordered(low),
        "expired": ordered(expired),
        "expiring_soon": ordered(soon),
        # Best-before was yesterday, so it went out of date at midnight / it's the last day.
        "newly_expired": ordered([r for r in expired if r[0] == -1]),
        "expires_today": ordered([r for r in soon if r[0] == 0]),
        "next_expiry": nxt,
        "supply_run": {"below_target": ordered(out) + ordered(low), "extras": extras, "cost": round(cost, 2)},
        # Things with a daily use: how long each lasts, shortest first.
        "supplies": {"days": sup[0]["days"] if sup else None, "runs_out_first": sup[0]["name"] if sup else "",
                     "items": sup},
        "stores_value": round(value, 2),
        "priced_items": priced,
        # Routine checks: due (or never done), due within a week, and due today exactly.
        "checks_total": len(checks),
        "checks_due": ordered(checks_due),
        "checks_soon": ordered(checks_soon),
        "checks_due_today": ordered(checks_today),
        "next_check": next_check,
        # Warnings from the Met Office, floods, Emergency Alerts and GDACS (if switched on)
        "warnings": warnings,
    }
    out["situation"] = assess(out, home_snapshot())
    return out


def get_item(db, item_id):
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        raise ApiError(404, "That item no longer exists")
    return row


def snapshot(db, item_id):
    item = dict(get_item(db, item_id))
    batches = [dict(b) for b in db.execute(
        "SELECT qty, expiry, location, added_at FROM batches WHERE item_id = ? ORDER BY id", (item_id,))]
    return {"item": item, "batches": batches}


def touch(db, item_id):
    db.execute("UPDATE items SET updated_at = ? WHERE id = ?", (now_iso(), item_id))


# --------------------------------------------------------------------------
# API routes
# --------------------------------------------------------------------------
ROUTES = []


def route(method, pattern):
    rx = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn))
        return fn
    return deco


@route("GET", "/api/health")
def api_health(body, query):
    return {"ok": True, "version": VERSION}


@route("GET", "/api/state")
def api_state(body, query):
    situation = summary()["situation"]
    home = home_snapshot() if HA_TOKEN else None
    with LOCK:
        if home is not None:
            home["config"] = home_cfg()
        return {
            "situation": situation,
            "home": home,
            "items": all_items(),
            "shopping": [dict(r) for r in DB.execute("SELECT * FROM shopping ORDER BY done, id")],
            "checks": all_checks(),
            "check_suggestions": [c[0] for c in CHECK_SUGGESTIONS],
            "plan": get_plan(),
            "warnings": warn_public(),
            "settings": get_settings(),
            "log": [dict(r) for r in DB.execute("SELECT * FROM log ORDER BY id DESC LIMIT 60")],
            "server": {"version": VERSION, "time": now_iso(), "last_backup": LAST_BACKUP["at"],
                       "backup_dir": BACKUP_DIR, "ha": ha_status()},
        }


@route("GET", "/api/summary")
def api_summary(body, query):
    return summary()


@route("POST", "/api/items")
def api_item_create(body, query):
    data = clean_item(body)
    qty = clean_num(body.get("qty"), 0, 0, 1e7, "Quantity")
    expiry = clean_date(body.get("expiry"))
    location = clean_text(body.get("location"), 80)
    ts = now_iso()
    with tx() as db:
        item_id = insert_item(db, data, ts, ts)
        if qty > 0:
            db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at) VALUES (?, ?, ?, ?, ?)",
                       (item_id, qty, expiry, location, ts))
        add_log("added", data["name"], ("%s %s" % (fq(qty), data["unit"])).strip() if qty else "New item")
    return {"id": item_id}


@route("PUT", r"/api/items/(\d+)")
def api_item_update(body, query, item_id):
    item_id = as_int_id(item_id)
    data = clean_item(body, partial=True)
    if not data:
        raise ApiError(400, "Nothing to change")
    with tx() as db:
        get_item(db, item_id)
        cols = ", ".join("%s = ?" % k for k in data)
        db.execute("UPDATE items SET %s, updated_at = ? WHERE id = ?" % cols,
                   list(data.values()) + [now_iso(), item_id])
        add_log("edited", get_item(db, item_id)["name"], "Details updated")
    return {"ok": True}


@route("DELETE", r"/api/items/(\d+)")
def api_item_delete(body, query, item_id):
    item_id = as_int_id(item_id)
    with tx() as db:
        snap = snapshot(db, item_id)
        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        add_log("removed", snap["item"]["name"], "Item deleted")
    return {"undo": snap}


def name_list(names, limit=8):
    """A readable list for the log, cut short when it's long."""
    names = list(names)
    if len(names) <= limit:
        return and_join(names)
    return "%s and %d more" % (", ".join(names[:limit]), len(names) - limit)


@route("POST", "/api/items/delete")
def api_items_delete(body, query):
    """Delete several items at once. The undo puts them all back."""
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids:
        raise ApiError(400, "Pick something to delete")
    if len(ids) > 5000:
        raise ApiError(400, "That's too many at once")
    wanted = []
    for v in ids:
        i = as_int_id(v)
        if i not in wanted:
            wanted.append(i)
    snaps = []
    with tx() as db:
        for item_id in wanted:
            if not db.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone():
                continue   # already gone (deleted on another phone)
            snaps.append(snapshot(db, item_id))
            db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        if not snaps:
            raise ApiError(404, "Those items no longer exist")
        names = [sn["item"]["name"] for sn in snaps]
        if len(snaps) == 1:
            add_log("removed", names[0], "Item deleted")
        else:
            add_log("removed", "%d items" % len(snaps), name_list(names))
    return {"deleted": len(snaps), "name": names[0], "undo": {"many": snaps}}


@route("POST", r"/api/items/(\d+)/stock")
def api_stock_add(body, query, item_id):
    item_id = as_int_id(item_id)
    qty = clean_num(body.get("qty"), 0, 0, 1e7, "Quantity")
    if qty <= 0:
        raise ApiError(400, "Quantity must be more than zero")
    expiry = clean_date(body.get("expiry"))
    location = clean_text(body.get("location"), 80)
    with tx() as db:
        item = get_item(db, item_id)
        same = db.execute(
            "SELECT id FROM batches WHERE item_id = ? AND IFNULL(expiry, '') = ? AND location = ? COLLATE NOCASE",
            (item_id, expiry or "", location)).fetchone()
        if same:
            db.execute("UPDATE batches SET qty = qty + ? WHERE id = ?", (qty, same["id"]))
        else:
            db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at) VALUES (?, ?, ?, ?, ?)",
                       (item_id, qty, expiry, location, now_iso()))
        touch(db, item_id)
        detail = "+%s %s" % (fq(qty), item["unit"])
        if expiry:
            detail += ", best before %s" % expiry
        add_log("stocked", item["name"], detail.strip())
    return {"ok": True}


@route("POST", r"/api/items/(\d+)/use")
def api_use(body, query, item_id):
    """Use stock, oldest expiry first (first in, first out)."""
    item_id = as_int_id(item_id)
    qty = clean_num(body.get("qty"), 1, 0, 1e7, "Quantity")
    if qty <= 0:
        raise ApiError(400, "Quantity must be more than zero")
    with tx() as db:
        snap = snapshot(db, item_id)
        item = snap["item"]
        remaining = qty
        rows = db.execute("SELECT id, qty FROM batches WHERE item_id = ? AND qty > 0 "
                          "ORDER BY expiry IS NULL, expiry, id", (item_id,)).fetchall()
        for b in rows:
            if remaining <= 0:
                break
            take = min(b["qty"], remaining)
            left = round(b["qty"] - take, 3)
            if left <= 0:
                db.execute("DELETE FROM batches WHERE id = ?", (b["id"],))
            else:
                db.execute("UPDATE batches SET qty = ? WHERE id = ?", (left, b["id"]))
            remaining = round(remaining - take, 3)
        used = round(qty - remaining, 3)
        if used <= 0:
            raise ApiError(409, "There's none of that left to use")
        touch(db, item_id)
        add_log("used", item["name"], ("-%s %s" % (fq(used), item["unit"])).strip())
    return {"used": used, "undo": snap}


@route("PUT", r"/api/batches/(\d+)")
def api_batch_update(body, query, batch_id):
    batch_id = as_int_id(batch_id)
    with tx() as db:
        b = db.execute("SELECT b.*, i.name, i.unit FROM batches b JOIN items i ON i.id = b.item_id "
                       "WHERE b.id = ?", (batch_id,)).fetchone()
        if not b:
            raise ApiError(404, "That batch no longer exists")
        snap = snapshot(db, b["item_id"])
        qty = b["qty"]
        if "delta" in body:
            qty = round(qty + clean_num(body.get("delta"), 0, -1e7, 1e7, "Change"), 3)
        elif "qty" in body:
            qty = clean_num(body.get("qty"), 0, 0, 1e7, "Quantity")
        expiry = clean_date(body.get("expiry")) if "expiry" in body else b["expiry"]
        location = clean_text(body.get("location"), 80) if "location" in body else b["location"]
        if qty <= 0:
            db.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
            add_log("adjusted", b["name"], "Batch emptied (%s %s)" % (fq(b["qty"]), b["unit"]))
        else:
            db.execute("UPDATE batches SET qty = ?, expiry = ?, location = ? WHERE id = ?",
                       (qty, expiry, location, batch_id))
            if qty != b["qty"]:
                add_log("adjusted", b["name"], ("%s → %s %s" % (fq(b["qty"]), fq(qty), b["unit"])).strip())
            else:
                add_log("adjusted", b["name"], "Batch details updated")
        touch(db, b["item_id"])
    return {"undo": snap, "removed": qty <= 0}


@route("DELETE", r"/api/batches/(\d+)")
def api_batch_delete(body, query, batch_id):
    batch_id = as_int_id(batch_id)
    with tx() as db:
        b = db.execute("SELECT b.*, i.name, i.unit FROM batches b JOIN items i ON i.id = b.item_id "
                       "WHERE b.id = ?", (batch_id,)).fetchone()
        if not b:
            raise ApiError(404, "That batch no longer exists")
        snap = snapshot(db, b["item_id"])
        db.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
        touch(db, b["item_id"])
        add_log("adjusted", b["name"], ("Batch removed (%s %s)" % (fq(b["qty"]), b["unit"])))
    return {"undo": snap}


@route("POST", "/api/restore-item")
def api_restore_item(body, query):
    """Undo: put an item (or several, as {"many": [...]}) and its batches back exactly as they were."""
    many = body.get("many")
    if many is None:
        snaps = [body]
    elif isinstance(many, list) and many and len(many) <= 5000:
        snaps = many
    else:
        raise ApiError(400, "Nothing to restore")
    for snap in snaps:
        if not isinstance(snap, dict) or not isinstance(snap.get("item"), dict) or not isinstance(snap.get("batches"), list):
            raise ApiError(400, "Nothing to restore")
    with tx() as db:
        names = [restore_snapshot(db, snap) for snap in snaps]
        if len(names) == 1:
            add_log("undo", names[0], "Change undone")
        else:
            add_log("undo", "%d items" % len(names), "Put back: " + name_list(names))
    return {"ok": True, "restored": len(names)}


def restore_snapshot(db, snap):
    item = snap["item"]
    batches = snap["batches"]
    item_id = as_int_id(item.get("id"))
    data = clean_item(item)
    created = clean_text(item.get("created_at"), 30) or now_iso()
    exists = db.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone()
    if exists:
        cols = ", ".join("%s = ?" % k for k in data)
        db.execute("UPDATE items SET %s, updated_at = ? WHERE id = ?" % cols,
                   list(data.values()) + [now_iso(), item_id])
    else:
        insert_item(db, data, created, now_iso(), item_id)
    db.execute("DELETE FROM batches WHERE item_id = ?", (item_id,))
    for b in batches:
        if not isinstance(b, dict):
            continue
        q = clean_num(b.get("qty"), 0, 0, 1e7)
        if q > 0:
            db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at) VALUES (?, ?, ?, ?, ?)",
                       (item_id, q, clean_date(b.get("expiry")), clean_text(b.get("location"), 80),
                        clean_text(b.get("added_at"), 30) or now_iso()))
    return data["name"]


@route("POST", "/api/shopping")
def api_shop_add(body, query):
    text = clean_text(body.get("text"), 200)
    if not text:
        raise ApiError(400, "Type something to add")
    with tx() as db:
        cur = db.execute("INSERT INTO shopping(text, done, created_at) VALUES (?, 0, ?)", (text, now_iso()))
    return {"id": cur.lastrowid}


@route("PUT", r"/api/shopping/(\d+)")
def api_shop_update(body, query, sid):
    sid = as_int_id(sid)
    with tx() as db:
        if "done" in body:
            db.execute("UPDATE shopping SET done = ? WHERE id = ?", (1 if body.get("done") else 0, sid))
        if "text" in body:
            text = clean_text(body.get("text"), 200)
            if text:
                db.execute("UPDATE shopping SET text = ? WHERE id = ?", (text, sid))
    return {"ok": True}


@route("DELETE", r"/api/shopping/(\d+)")
def api_shop_delete(body, query, sid):
    with tx() as db:
        db.execute("DELETE FROM shopping WHERE id = ?", (as_int_id(sid),))
    return {"ok": True}


@route("POST", "/api/shopping/clear-done")
def api_shop_clear(body, query):
    with tx() as db:
        n = db.execute("DELETE FROM shopping WHERE done = 1").rowcount
    return {"cleared": n}


# -- Routine checks ------------------------------------------------------------
# Stores are only any use if the kit works when you need it. Suggestions follow
# the usual advice: test alarms monthly, rotate water you've bottled yourself
# every six months, and go through the grab bag and the plan once a year.
CHECK_SUGGESTIONS = [
    ("Test the smoke and carbon monoxide alarms", 30, "Press the test button on each one."),
    ("Charge the power banks", 30, "Top them up so they're full when the power goes."),
    ("Test the torches, radio and batteries", 91, "Swap out any batteries that are flat or leaking."),
    ("Rotate tap water you've stored", 182,
     "Water you've bottled yourself: empty, rinse and refill the containers every six months."),
    ("Check the first aid kit", 182, "Replace anything used up or out of date."),
    ("Try the camping stove", 182, "Light it outdoors, and check the gas canisters aren't empty."),
    ("Check the fire extinguisher", 182, "The gauge needle should be in the green, and the pin and seal in place."),
    ("Check the grab bag", 365, "Food and water in date, clothes still fit, cash and copies of documents current."),
    ("Go through the emergency plan together", 365,
     "Everyone knows where to meet and who to call. Update any numbers that have changed."),
]


def all_checks():
    return [dict(r) for r in DB.execute("SELECT * FROM checks ORDER BY name COLLATE NOCASE")]


def get_check(db, cid):
    row = db.execute("SELECT * FROM checks WHERE id = ?", (cid,)).fetchone()
    if not row:
        raise ApiError(404, "That check no longer exists")
    return dict(row)


def not_future(d):
    if d and d > dt.date.today().isoformat():
        raise ApiError(400, "That date hasn't happened yet")
    return d


def clean_check(body, partial=False):
    out = {}
    if not partial or "name" in body:
        name = clean_text(body.get("name"), 120)
        if not name:
            raise ApiError(400, "Give the check a name")
        out["name"] = name
    if not partial or "every_days" in body:
        out["every_days"] = int(round(clean_num(body.get("every_days"), 90, 1, 3650, "How often")))
    if not partial or "last_done" in body:
        out["last_done"] = not_future(clean_date(body.get("last_done")))
    if not partial or "notes" in body:
        out["notes"] = clean_text(body.get("notes"), 1000)
    return out


@route("POST", "/api/checks")
def api_check_create(body, query):
    data = clean_check(body)
    with tx() as db:
        cid = db.execute("INSERT INTO checks(name, every_days, last_done, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                         (data["name"], data["every_days"], data["last_done"], data["notes"], now_iso())).lastrowid
        add_log("added", data["name"], "New check, " + every_words(data["every_days"]))
    return {"id": cid}


@route("PUT", r"/api/checks/(\d+)")
def api_check_update(body, query, cid):
    cid = as_int_id(cid)
    data = clean_check(body, partial=True)
    if not data:
        raise ApiError(400, "Nothing to change")
    with tx() as db:
        get_check(db, cid)
        cols = ", ".join("%s = ?" % k for k in data)
        db.execute("UPDATE checks SET %s WHERE id = ?" % cols, list(data.values()) + [cid])
        add_log("edited", get_check(db, cid)["name"], "Check updated")
    return {"ok": True}


@route("POST", r"/api/checks/(\d+)/done")
def api_check_done(body, query, cid):
    """Tick a check off (today, unless a date is given). It's next due a full period later."""
    cid = as_int_id(cid)
    when = not_future(clean_date(body.get("date"))) or dt.date.today().isoformat()
    with tx() as db:
        before = get_check(db, cid)
        db.execute("UPDATE checks SET last_done = ? WHERE id = ?", (when, cid))
        due = dt.date.fromisoformat(when) + dt.timedelta(days=before["every_days"])
        add_log("checked", before["name"], "Next due %s" % human_date(due))
    return {"undo": {"check": before}, "next_due": due.isoformat()}


@route("DELETE", r"/api/checks/(\d+)")
def api_check_delete(body, query, cid):
    cid = as_int_id(cid)
    with tx() as db:
        before = get_check(db, cid)
        db.execute("DELETE FROM checks WHERE id = ?", (cid,))
        add_log("removed", before["name"], "Check deleted")
    return {"undo": {"check": before}}


@route("POST", "/api/checks/restore")
def api_check_restore(body, query):
    """Undo for checks: put one back exactly as it was."""
    c = body.get("check")
    if not isinstance(c, dict):
        raise ApiError(400, "Nothing to restore")
    cid = as_int_id(c.get("id"))
    data = clean_check(c)
    with tx() as db:
        db.execute("INSERT OR REPLACE INTO checks(id, name, every_days, last_done, notes, created_at)"
                   " VALUES (?, ?, ?, ?, ?, ?)", (cid, data["name"], data["every_days"], data["last_done"],
                                                  data["notes"], clean_text(c.get("created_at"), 30) or now_iso()))
        add_log("undo", data["name"], "Change undone")
    return {"ok": True}


@route("POST", "/api/checks/seed")
def api_checks_seed(body, query):
    """Add the suggested checks, skipping any you already have. They start as not done yet."""
    with tx() as db:
        existing = set(r[0].lower() for r in db.execute("SELECT name FROM checks"))
        added = 0
        for name, every, notes in CHECK_SUGGESTIONS:
            if name.lower() in existing:
                continue
            db.execute("INSERT INTO checks(name, every_days, last_done, notes, created_at) VALUES (?, ?, NULL, ?, ?)",
                       (name, every, notes, now_iso()))
            added += 1
        if added:
            add_log("starter", "", "Added %d suggested checks" % added)
    return {"added": added}


# -- Household emergency plan ------------------------------------------------------
# What everyone needs to know when it happens, kept where it still works with the
# internet down (and printable). Follows the UK Government's household plan:
# contacts, where to meet, how to turn things off, and who needs what.
PLAN_TEXT = (("meet_near", 300), ("meet_far", 300), ("water_off", 600), ("gas_off", 600), ("power_off", 600),
             ("medical", 2000), ("pets", 1000), ("documents", 600), ("radio", 200), ("notes", 3000))
MAX_CONTACTS = 60


def clean_plan(body):
    contacts = body.get("contacts")
    if contacts is None:
        contacts = []
    if not isinstance(contacts, list):
        raise ApiError(400, "Contacts should be a list")
    if len(contacts) > MAX_CONTACTS:
        raise ApiError(400, "That's too many contacts (%d at most)" % MAX_CONTACTS)
    plan = {"contacts": []}
    for c in contacts:
        if not isinstance(c, dict):
            raise ApiError(400, "Contacts should each have a name and number")
        row = {"name": clean_text(c.get("name"), 80), "role": clean_text(c.get("role"), 80),
               "phone": clean_text(c.get("phone"), 40)}
        if row["name"] or row["role"] or row["phone"]:
            plan["contacts"].append(row)
    for key, maxlen in PLAN_TEXT:
        plan[key] = clean_text(body.get(key), maxlen)
    return plan


def get_plan():
    raw = setting_raw("plan", None)
    raw = raw if isinstance(raw, dict) else {}
    try:
        plan = clean_plan(raw)
    except ApiError:
        plan = clean_plan({})
    plan["updated_at"] = raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else None
    return plan


@route("PUT", "/api/plan")
def api_plan(body, query):
    plan = clean_plan(body)
    plan["updated_at"] = now_iso()
    with tx() as db:
        set_setting_raw(db, "plan", plan)
        add_log("plan", "", "Emergency plan updated")
    return {"plan": plan}


@route("PUT", "/api/settings")
def api_settings(body, query):
    changed = []
    with tx() as db:
        for key, (lo, hi, integer) in SETTING_RULES.items():
            if key in body:
                v = clean_num(body.get(key), DEFAULT_SETTINGS[key], lo, hi, key)
                if integer:
                    v = int(round(v))
                db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(v)))
                changed.append(key)
        if changed:
            add_log("settings", "", "Household settings updated")
    return {"changed": changed}


def resolve_target(spec, kcal, litres, ctx):
    if isinstance(spec, (int, float)):
        return spec
    kind, v = spec
    if kind == "kcal":
        return max(1, int(math.ceil(ctx["kcal"] * v / kcal))) if kcal else 1
    if kind == "water":
        return max(1, int(math.ceil(ctx["litres"] * v / litres))) if litres else 1
    if kind == "people":
        return max(1, int(math.ceil(ctx["people"] * v)))
    if kind == "perday":
        return max(1, int(math.ceil(ctx["people"] * ctx["days"] * v)))
    return 1


@route("POST", "/api/seed")
def api_seed(body, query):
    """Add the suggested starter list (at zero stock), skipping names that already exist."""
    with tx() as db:
        st = get_settings()
        people = max(1, st["adults"] + st["children"])
        days = st["target_days"]
        ctx = {
            "people": people,
            "days": days,
            "kcal": max(1, st["adults"] * st["kcal_adult"] + st["children"] * st["kcal_child"]) * days,
            "litres": people * st["water_per_person"] * days,
        }
        existing = set(r[0].lower() for r in db.execute("SELECT name FROM items"))
        ts = now_iso()
        added = 0
        for name, cat, unit, kcal, litres, target, notes in STARTER:
            if name.lower() in existing:
                continue
            # Things used every day also say how long they'll last.
            per_day = round(people * target[1], 3) if isinstance(target, tuple) and target[0] == "perday" else 0
            insert_item(db, {"name": name, "category": cat, "unit": unit, "kcal_per_unit": kcal,
                             "litres_per_unit": litres, "target_qty": resolve_target(target, kcal, litres, ctx),
                             "per_day": per_day, "price": 0, "notes": notes}, ts, ts)
            added += 1
        if added:
            add_log("starter", "", "Loaded %d suggested items" % added)
    return {"added": added}


@route("GET", r"/api/export\.csv")
def api_export_csv(body, query):
    with LOCK:
        items = all_items()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Category", "Item", "Quantity", "Unit", "Best before", "Location",
                "Target", "Kcal per unit", "Litres per unit", "Used a day", "Price each", "Notes"])
    for it in sorted(items, key=lambda i: (CATEGORIES.index(i["category"]) if i["category"] in CATEGORIES else 99,
                                           i["name"].lower())):
        rows = it["batches"] or [{"qty": 0, "expiry": "", "location": ""}]
        for b in rows:
            w.writerow([it["category"], it["name"], fq(b["qty"]), it["unit"], b["expiry"] or "", b["location"],
                        fq(it["target_qty"]), fq(it["kcal_per_unit"]), fq(it["litres_per_unit"]),
                        fq(it["per_day"]) if it["per_day"] else "", "%.2f" % it["price"] if it["price"] else "",
                        it["notes"]])
    data = ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens it as UTF-8
    return Raw(data, "text/csv; charset=utf-8", "dadsarmy-stores-%s.csv" % dt.date.today().isoformat())


@route("GET", r"/api/backup\.json")
def api_backup(body, query):
    with LOCK:
        payload = {
            "app": "dadsarmy",
            "version": VERSION,
            "exported_at": now_iso(),
            "settings": get_settings(),
            "items": all_items(),
            "shopping": [dict(r) for r in DB.execute("SELECT * FROM shopping ORDER BY id")],
            "checks": all_checks(),
            "plan": get_plan(),
        }
    data = json.dumps(payload, indent=1, ensure_ascii=False).encode("utf-8")
    return Raw(data, "application/json; charset=utf-8", "dadsarmy-backup-%s.json" % dt.date.today().isoformat())


@route("POST", "/api/restore")
def api_restore(body, query):
    if body.get("app") != "dadsarmy" or not isinstance(body.get("items"), list):
        raise ApiError(400, "That doesn't look like a Dads Army backup file")
    items = body["items"]
    shopping = body.get("shopping") if isinstance(body.get("shopping"), list) else []
    settings = body.get("settings") if isinstance(body.get("settings"), dict) else {}
    # Validate everything before touching the database.
    clean_items = []
    for it in items:
        if not isinstance(it, dict):
            raise ApiError(400, "Backup file is damaged")
        data = clean_item(it)
        bl = []
        for b in it.get("batches") or []:
            if isinstance(b, dict):
                q = clean_num(b.get("qty"), 0, 0, 1e7)
                if q > 0:
                    bl.append((q, clean_date(b.get("expiry")), clean_text(b.get("location"), 80),
                               clean_text(b.get("added_at"), 30) or now_iso()))
        clean_items.append((data, clean_text(it.get("created_at"), 30) or now_iso(), bl))
    # Checks and the plan arrived in 1.5.0: an older backup leaves the ones you have alone.
    checks = None
    if isinstance(body.get("checks"), list):
        checks = []
        for c in body["checks"]:
            if not isinstance(c, dict):
                raise ApiError(400, "Backup file is damaged")
            checks.append((clean_check(c), clean_text(c.get("created_at"), 30) or now_iso()))
    plan = None
    if isinstance(body.get("plan"), dict):
        plan = clean_plan(body["plan"])
        plan["updated_at"] = clean_text(body["plan"].get("updated_at"), 30) or None
    make_backup("pre-restore")
    ts = now_iso()
    with tx() as db:
        db.execute("DELETE FROM batches")
        db.execute("DELETE FROM items")
        db.execute("DELETE FROM shopping")
        for data, created, bl in clean_items:
            new_id = insert_item(db, data, created, ts)
            for q, exp, loc, added in bl:
                db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at) VALUES (?, ?, ?, ?, ?)",
                           (new_id, q, exp, loc, added))
        for s in shopping:
            if isinstance(s, dict) and clean_text(s.get("text"), 200):
                db.execute("INSERT INTO shopping(text, done, created_at) VALUES (?, ?, ?)",
                           (clean_text(s.get("text"), 200), 1 if s.get("done") else 0, ts))
        for key, (lo, hi, integer) in SETTING_RULES.items():
            if key in settings:
                v = clean_num(settings.get(key), DEFAULT_SETTINGS[key], lo, hi, key)
                db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                           (key, json.dumps(int(round(v)) if integer else v)))
        if checks is not None:
            db.execute("DELETE FROM checks")
            for c, created in checks:
                db.execute("INSERT INTO checks(name, every_days, last_done, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                           (c["name"], c["every_days"], c["last_done"], c["notes"], created))
        if plan is not None:
            set_setting_raw(db, "plan", plan)
        add_log("restored", "", "Restored %d items from backup" % len(clean_items))
    HA_REBASE.set()  # a restore isn't things running out
    return {"items": len(clean_items)}


# --------------------------------------------------------------------------
# Automatic backups (a dated copy of the database, once a day)
# --------------------------------------------------------------------------
def list_backups(suffix="-auto.db"):
    try:
        return sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith(suffix))
    except OSError:
        return []


def make_backup(tag="auto"):
    name = "dadsarmy-%s-%s.db" % (dt.datetime.now().strftime("%Y%m%d-%H%M%S"), tag)
    path = os.path.join(BACKUP_DIR, name)
    with LOCK:
        dest = sqlite3.connect(path)
        try:
            DB.backup(dest)
        finally:
            dest.close()
    for old in list_backups()[:-KEEP_BACKUPS]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass
    for old in list_backups("-pre-restore.db")[:-3]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass
    if tag == "auto":
        LAST_BACKUP["at"] = now_iso()
    return path


def backup_loop():
    while True:
        try:
            existing = list_backups()
            newest = os.path.getmtime(os.path.join(BACKUP_DIR, existing[-1])) if existing else 0
            if newest:
                LAST_BACKUP["at"] = dt.datetime.fromtimestamp(newest).replace(microsecond=0).isoformat(sep=" ")
            if time.time() - newest > 20 * 3600:
                make_backup("auto")
        except Exception:
            traceback.print_exc()
        time.sleep(3600)


# --------------------------------------------------------------------------
# Home Assistant (only when running as a Home Assistant app)
# --------------------------------------------------------------------------
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN") or ""
HA_API = os.environ.get("DADSARMY_HA_API", "http://supervisor/core/api").rstrip("/")
HA_WAKE = threading.Event()
HA_REBASE = threading.Event()  # set after a restore: those stock changes aren't things running out
HA_LAST = {}  # entity_id -> last body sent
TODO_LOCK = threading.Lock()
TODO_STATUS = {"ok": None, "error": "", "synced_at": None, "name": ""}
TODO_RE = re.compile(r"^todo\.[a-z0-9_]+$")
TODO_LIST_NAME = "Supply run"
CHECKS_LIST_NAME = "Dads Army checks"
CHECKS_STATUS = {"ok": None, "error": "", "synced_at": None, "name": ""}
HA_WS = os.environ.get("DADSARMY_HA_WS", "ws://supervisor/core/websocket")
DASH_URL = "dads-army"
DASH_LAYOUT = 3   # bump when the dashboard changes, so the app offers to rebuild it


class HAError(Exception):
    pass


def ha_request(method, path, body=None, timeout=10):
    """Call Home Assistant's REST API through the Supervisor. Returns (HTTP status, JSON or text)."""
    req = urllib.request.Request(
        HA_API + path, method=method,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + HA_TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            raw = e.read()
        except Exception:
            raw = b""
    text = raw.decode("utf-8", "replace")
    try:
        return status, (json.loads(text) if text else None)
    except ValueError:
        return status, text


def ha_call(method, path, body=None, timeout=10):
    return ha_request(method, path, body, timeout)[0]


def ha_service(domain, service, data, response=False, timeout=15):
    """Run a Home Assistant action (service). Raises HAError if it fails."""
    path = "/services/%s/%s%s" % (domain, service, "?return_response" if response else "")
    status, out = ha_request("POST", path, data, timeout)
    if status != 200:
        why = out.get("message") if isinstance(out, dict) else (out or "")
        raise HAError("%s.%s: Home Assistant answered %s%s" % (domain, service, status,
                                                              (" - " + str(why)[:150]) if why else ""))
    return out


def _ha_list(rows):
    return {"items": rows[:LIST_LIMIT], "total": len(rows), "more": max(0, len(rows) - LIST_LIMIT)}


def ha_entities(s):
    """Turn a summary() into Home Assistant entity states."""
    ents = {}

    def put(eid, state, name, icon, unit=None, attrs=None, measurement=True, device_class=None):
        a = {"friendly_name": name, "icon": icon}
        if unit:
            a["unit_of_measurement"] = unit
        if measurement:
            a["state_class"] = "measurement"
        if device_class:
            a["device_class"] = device_class
        a.update(attrs or {})
        ents[eid] = {"state": str(state), "attributes": a}

    target_met = s["hold_out_days"] >= s["target_days"]
    put("sensor.dads_army_readiness", s["readiness_pct"], "Dads Army readiness", "mdi:gauge", "%", {
        "hold_out_days": s["hold_out_days"], "target_days": s["target_days"], "target_met": target_met})
    put("sensor.dads_army_hold_out", s["hold_out_days"], "Dads Army hold-out", "mdi:shield-home", "days", {
        "food_days": s["food_days"], "water_days": s["water_days"], "runs_out_first": s["runs_out_first"],
        "target_days": s["target_days"], "target_met": target_met, "people": s["people"]})
    put("sensor.dads_army_food_days", s["food_days"], "Dads Army food", "mdi:food-drumstick", "days")
    put("sensor.dads_army_water_days", s["water_days"], "Dads Army water", "mdi:water", "days")
    put("sensor.dads_army_kit_stocked", s["kit_stocked_pct"], "Dads Army kit stocked", "mdi:toolbox", "%")
    put("sensor.dads_army_out_of_stock", len(s["out_of_stock"]), "Dads Army out of stock",
        "mdi:package-variant-remove", "items", _ha_list(s["out_of_stock"]))
    put("sensor.dads_army_low_stock", len(s["low_stock"]), "Dads Army running low", "mdi:package-down", "items",
        dict(_ha_list(s["low_stock"]), below_target_total=len(s["low_stock"]) + len(s["out_of_stock"])))
    put("sensor.dads_army_expired", len(s["expired"]), "Dads Army expired", "mdi:calendar-remove", "items",
        dict(_ha_list(s["expired"]), newly_expired=s["newly_expired"][:LIST_LIMIT]))
    put("sensor.dads_army_expiring_soon", len(s["expiring_soon"]), "Dads Army expiring soon", "mdi:calendar-alert",
        "items", dict(_ha_list(s["expiring_soon"]), warn_days=s["warn_days"],
                      expires_today=s["expires_today"][:LIST_LIMIT]))
    nxt = s["next_expiry"]
    put("sensor.dads_army_next_expiry", nxt["date"] if nxt else "unknown", "Dads Army next to expire",
        "mdi:calendar-clock", attrs=nxt or {}, measurement=False, device_class="date")
    run = s["supply_run"]
    put("sensor.dads_army_supply_run", len(run["below_target"]) + len(run["extras"]), "Dads Army supply run",
        "mdi:cart", "items", dict(_ha_list(run["below_target"]), extras=run["extras"][:LIST_LIMIT], cost=run["cost"]))
    sup = s["supplies"]
    put("sensor.dads_army_supplies", sup["days"] if sup["items"] else "unknown", "Dads Army daily supplies",
        "mdi:timer-sand", "days", dict(_ha_list(sup["items"]), runs_out_first=sup["runs_out_first"],
                                       target_days=s["target_days"]))
    put("sensor.dads_army_checks_due", len(s["checks_due"]), "Dads Army checks due", "mdi:clipboard-check-outline",
        "checks", dict(_ha_list(s["checks_due"]), due_today=s["checks_due_today"][:LIST_LIMIT],
                       due_soon=s["checks_soon"][:LIST_LIMIT], next_check=s["next_check"],
                       checks_total=s["checks_total"]))
    put("sensor.dads_army_stores_value", s["stores_value"], "Dads Army stores value", "mdi:cash", "£", {
        "supply_run_cost": run["cost"], "priced_items": s["priced_items"], "items_total": s["items_total"]})
    w = s["warnings"]
    put("sensor.dads_army_warnings", w["count"], "Dads Army warnings",
        "mdi:alert-octagon" if w["serious"] else "mdi:alert-outline" if w["count"] else "mdi:shield-check-outline",
        "warnings", dict(_ha_list(w["items"]), highest=w["highest"], max_severity=w["max_severity"],
                         enabled=w["enabled"], checked_at=w["checked_at"], health_news=w["news"]))
    sit = s["situation"]
    put("sensor.dads_army_alert_level", sit["name"], "Dads Army alert level", LEVEL_ICONS[sit["level"] - 1],
        attrs={"level": sit["level"], "colour": sit["colour"], "emoji": sit["emoji"], "meaning": sit["meaning"],
               "action": sit["action"],
               "escalated": sit["escalated"], "reasons": sit["reasons"][:LIST_LIMIT], "notes": sit["notes"],
               "guidance": [{"label": g["label"], "source": g["source"], "text": g["text"]} for g in sit["guidance"]],
               "scale": [{"level": x["level"], "name": x["name"], "emoji": x["emoji"], "meaning": x["meaning"],
                          "action": x["action"]} for x in sit["scale"]]},
        measurement=False)
    # Only what needs doing now. Things not bought yet are the supply run's job (they'd keep
    # this on for weeks while the stores are built up), and a check that's never been done
    # isn't overdue.
    reasons = []
    if w["serious"]:
        reasons.append("%d warning%s in force" % (w["serious"], "" if w["serious"] == 1 else "s"))
    if s["expired"]:
        reasons.append("%d expired" % len(s["expired"]))
    overdue = [c for c in s["checks_due"] if c["days"] is not None and c["days"] < 0]
    if overdue:
        reasons.append("%d check%s overdue" % (len(overdue), "" if len(overdue) == 1 else "s"))
    put("binary_sensor.dads_army_attention", "on" if reasons else "off", "Dads Army needs attention",
        "mdi:alert-circle" if reasons else "mdi:check-circle", attrs={"reasons": reasons},
        measurement=False, device_class="problem")
    return ents


# -- "You've run out" events, for phone alerts ------------------------------
def stock_levels():
    with LOCK:
        rows = DB.execute("SELECT i.id, i.name, i.unit, i.target_qty, IFNULL(SUM(b.qty), 0) AS total "
                          "FROM items i LEFT JOIN batches b ON b.item_id = i.id GROUP BY i.id").fetchall()
    return {r["id"]: dict(r) for r in rows}


def and_join(words):
    """['a', 'b', 'c'] -> 'a, b and c'."""
    words = list(words)
    if len(words) < 2:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def ran_out(before, now):
    """Event data for items that had stock last time and have none now (None if nothing ran out)."""
    gone = sorted((now[i] for i in now if i in before and before[i]["total"] > 0 and now[i]["total"] <= 0),
                  key=lambda r: r["name"].lower())
    if not gone:
        return None
    items = [{"name": g["name"], "unit": g["unit"] or "", "target": _num(g["target_qty"] or 0),
              "on_supply_run": (g["target_qty"] or 0) > 0} for g in gone]
    names = [g["name"] for g in gone]
    shown = names[:8] + (["%d more" % (len(names) - 8)] if len(names) > 8 else [])
    if len(gone) == 1:
        g = gone[0]
        message = "%s has run out." % g["name"]
        if g["target_qty"] > 0:
            message += " It's on the supply run: get %s." % qu(g["target_qty"], g["unit"] or "")
    else:
        message = "%d things have run out: %s." % (len(gone), and_join(shown))
        on_run = sum(1 for i in items if i["on_supply_run"])
        if on_run == len(items):
            message += " They're on the supply run."
        elif on_run:
            message += " The ones with a target are on the supply run."
    return {"count": len(gone), "names": and_join(shown), "message": message, "items": items[:LIST_LIMIT]}


# -- Supply run <-> Home Assistant to-do list ---------------------------------
def todo_entity():
    with LOCK:
        return setting_raw("ha_todo_list", "") or ""


def todo_line(e):
    """How a below-target item reads on the to-do list, e.g. 'Bottled water (5L): 16 bottles'."""
    return "%s: %s" % (e["name"], qu(e["get"], e["unit"]))


def todo_items(entity):
    out = ha_service("todo", "get_items", {"entity_id": entity, "status": ["needs_action", "completed"]},
                     response=True)
    try:
        items = out["service_response"][entity]["items"]
    except (KeyError, TypeError):
        raise HAError("Home Assistant didn't send the list's items")
    return [i for i in items if isinstance(i, dict) and i.get("uid")]


def ha_status():
    """For the app: is the supply run linked to a Home Assistant list, and how's it going?"""
    if not HA_TOKEN:
        return None
    with LOCK:
        entity = setting_raw("ha_todo_list", "") or ""
        ticked = [int(r["key"][2:]) for r in DB.execute(
            "SELECT key FROM ha_todo WHERE key LIKE 'i:%' AND uid != '' AND done = 1")] if entity else []
        checks = setting_raw("ha_checks_list", "") or ""
        dash = setting_raw("ha_dashboard", None)
        prompt = setting_raw("ha_dash_prompt", None)
    prompt = prompt if isinstance(prompt, dict) else {}
    offer = (not isinstance(dash, dict) and not prompt.get("never")
             and (not prompt.get("until") or str(prompt["until"]) <= dt.date.today().isoformat()))
    return {"todo": entity, "todo_name": TODO_STATUS["name"] or entity, "ok": TODO_STATUS["ok"],
            "error": TODO_STATUS["error"], "synced_at": TODO_STATUS["synced_at"], "ticked": ticked,
            "checks": checks, "checks_name": CHECKS_STATUS["name"] or checks, "checks_ok": CHECKS_STATUS["ok"],
            "checks_error": CHECKS_STATUS["error"], "checks_synced_at": CHECKS_STATUS["synced_at"],
            "dashboard": dash if isinstance(dash, dict) else None, "dash_prompt": offer,
            "dash_outdated": isinstance(dash, dict) and int(dash.get("layout") or 1) < DASH_LAYOUT}


def todo_sync(entity, s):
    """Two-way sync between the supply run and a Home Assistant to-do list.

    Below-target items belong to Dads Army: they're added, renamed and removed to
    match the stores. Ticking one off in Home Assistant shows on the supply run
    (put it away with Got it, which asks for the date); deleting one there keeps
    it off the list until the amount needed changes.
    Extras ("Also get") are shared: adding, ticking, renaming or deleting on
    either side is copied to the other. Returns True if the supply run changed.
    """
    status, st = ha_request("GET", "/states/" + entity, timeout=8)
    if status == 404:
        raise HAError("the list %s isn't in Home Assistant any more" % entity)
    if status != 200 or not isinstance(st, dict):
        raise HAError("Home Assistant answered %s" % status)
    TODO_STATUS["name"] = (st.get("attributes") or {}).get("friendly_name") or entity
    ha_items = todo_items(entity)
    by_uid = {i["uid"]: i for i in ha_items}
    lines = {"i:%d" % e["id"]: todo_line(e) for e in s["supply_run"]["below_target"]}
    with LOCK:
        extras = {r["id"]: dict(r) for r in DB.execute("SELECT id, text, done FROM shopping")}
        tracked = {r["key"]: dict(r) for r in DB.execute("SELECT key, uid, summary, done FROM ha_todo")}
        fresh = bool(setting_raw("ha_todo_fresh", 0))
    linked = [t for t in tracked.values() if t["uid"] and not t["key"].startswith("x:")]
    if len(linked) > 3 and not any(t["uid"] in by_uid for t in linked):
        # Every linked item has gone at once: the list was emptied or made again. Start
        # afresh rather than deleting the extras here too.
        print("Home Assistant to-do list: %s looks new or emptied, so filling it again" % entity, flush=True)
        tracked = {}

    def done_of(i):
        return 1 if i.get("status") == "completed" else 0

    track = {}       # key -> [uid, summary as Home Assistant has it, done]
    claimed = set()  # Home Assistant items accounted for
    orphans = {}     # uid -> item whose Dads Army side has gone (removed unless something takes it over)
    ha_ops = []      # (action, data) to run in Home Assistant
    app_ops = []     # (sql, args, log text or None, item name)
    dropped = set()  # extras deleted in Home Assistant

    # 1. Everything linked last time.
    for key, t in tracked.items():
        kind, _, ref = key.partition(":")
        it = by_uid.get(t["uid"]) if t["uid"] else None
        if kind == "x":                      # was there before we linked, or already ticked: not ours
            if it:
                claimed.add(it["uid"])
                track[key] = [it["uid"], "", 0]
            continue
        if kind == "i":
            want = lines.get(key)
            if it is None:                   # deleted there: stay off until the amount changes
                if want is not None and want == t["summary"]:
                    track[key] = ["", want, 1]
                continue
            claimed.add(it["uid"])
            if want is None:                 # back up to target
                orphans[it["uid"]] = it
                continue
            if it.get("summary") != want:
                ha_ops.append(("update_item", {"item": it["uid"], "rename": want}))
            track[key] = [it["uid"], want, done_of(it)]
        elif kind == "s":
            ex = extras.get(int(ref)) if ref.isdigit() else None
            if it is None:                   # deleted there, so delete it here
                if ex:
                    dropped.add(ex["id"])
                    app_ops.append(("DELETE FROM shopping WHERE id = ?", (ex["id"],),
                                    "Removed in Home Assistant", ex["text"]))
                continue
            claimed.add(it["uid"])
            if ex is None:                   # deleted or cleared here
                orphans[it["uid"]] = it
                continue
            text, done = ex["text"], ex["done"]
            ha_text, ha_done = it.get("summary") or "", done_of(it)
            if ha_text != t["summary"] and clean_text(ha_text, 200):     # renamed there
                if clean_text(ha_text, 200) != text:
                    text = clean_text(ha_text, 200)
                    app_ops.append(("UPDATE shopping SET text = ? WHERE id = ?", (text, ex["id"]), None, ""))
            elif text != clean_text(t["summary"], 200):                   # renamed here
                ha_ops.append(("update_item", {"item": it["uid"], "rename": text}))
                ha_text = text
            if ha_done != t["done"]:                                      # ticked there
                if ha_done != done:
                    done = ha_done
                    app_ops.append(("UPDATE shopping SET done = ? WHERE id = ?", (done, ex["id"]),
                                    "Ticked off in Home Assistant" if done else None, text))
            elif done != ha_done:                                         # ticked here
                ha_ops.append(("update_item", {"item": it["uid"],
                                               "status": "completed" if done else "needs_action"}))
            track[key] = [it["uid"], ha_text, done]

    # 2. New lines: take over a matching item already on the list (no duplicates), or add one.
    pool = list(orphans.values()) + [i for i in ha_items if i["uid"] not in claimed]

    def adopt(text):
        for i in pool:
            if (i.get("summary") or "") == text:
                pool.remove(i)
                orphans.pop(i["uid"], None)
                claimed.add(i["uid"])
                return i
        return None

    adds = []
    for key, want in lines.items():
        if key not in track:
            i = adopt(want)
            if i:
                track[key] = [i["uid"], want, done_of(i)]
            else:
                adds.append((key, want))
    for sid, ex in extras.items():
        key = "s:%d" % sid
        if key in track or sid in dropped or ex["done"]:
            continue
        i = adopt(ex["text"])
        if i:
            if done_of(i):
                ha_ops.append(("update_item", {"item": i["uid"], "status": "needs_action"}))
            track[key] = [i["uid"], ex["text"], 0]
        else:
            adds.append((key, ex["text"]))

    # 3. Whatever's left on the list: added there (becomes an extra here), or not ours.
    imports = []
    for i in pool:
        if i["uid"] in orphans:
            continue
        text = clean_text(i.get("summary"), 200)
        if fresh or done_of(i) or not text:
            track["x:" + i["uid"]] = [i["uid"], "", 0]
        else:
            imports.append((i, text))

    # 4. Bring Home Assistant up to date.
    for action, data in ha_ops:
        ha_service("todo", action, dict(data, entity_id=entity))
    if orphans:
        ha_service("todo", "remove_item", {"entity_id": entity, "item": list(orphans)})
    for _, text in adds:
        ha_service("todo", "add_item", {"entity_id": entity, "item": text})
    if adds:
        taken = claimed | set(i["uid"] for i, _ in imports) | set(k[2:] for k in track if k.startswith("x:"))
        latest = todo_items(entity)
        for key, text in adds:
            for i in latest:
                if i["uid"] not in taken and i.get("summary") == text:
                    taken.add(i["uid"])
                    track[key] = [i["uid"], text, 0]
                    break

    # 5. Then the supply run, and remember the links.
    changed = bool(app_ops or imports)
    with tx() as db:
        for sql, args, note, name in app_ops:
            db.execute(sql, args)
            if note:
                add_log("supply", name, note)
        for i, text in imports:
            cur = db.execute("INSERT INTO shopping(text, done, created_at) VALUES (?, 0, ?)", (text, now_iso()))
            track["s:%d" % cur.lastrowid] = [i["uid"], i.get("summary") or "", 0]
            add_log("supply", text, "Added in Home Assistant")
        db.execute("DELETE FROM ha_todo")
        db.executemany("INSERT INTO ha_todo(key, uid, summary, done) VALUES (?, ?, ?, ?)",
                       [(k, v[0], v[1], v[2]) for k, v in track.items()])
        if fresh:
            set_setting_raw(db, "ha_todo_fresh", 0)
    return changed


def todo_tick(s):
    entity = todo_entity()
    if not entity:
        return
    with TODO_LOCK:
        if todo_entity() != entity:
            return
        try:
            changed = todo_sync(entity, s)
        except Exception as e:
            if not isinstance(e, (HAError, OSError)):
                traceback.print_exc()
            if TODO_STATUS["ok"] is not False:
                print("Home Assistant to-do list: can't sync with %s yet (%s). Will keep trying." % (entity, e),
                      flush=True)
            TODO_STATUS.update(ok=False, error=str(e))
            return
        if TODO_STATUS["ok"] is False:
            print("Home Assistant to-do list: syncing again", flush=True)
        TODO_STATUS.update(ok=True, error="", synced_at=now_iso())
    if changed:
        HA_WAKE.set()


def todo_link(entity):
    """Sync the supply run with a different Home Assistant to-do list ('' to stop)."""
    with TODO_LOCK:
        with LOCK:
            old = setting_raw("ha_todo_list", "") or ""
            mine = set(r["uid"] for r in DB.execute("SELECT uid FROM ha_todo WHERE key LIKE 'i:%' AND uid != ''"))
        if old == entity:
            return
        if old and mine:
            # Take Dads Army's own lines off the old list. Extras stay: they're yours.
            try:
                there = [i["uid"] for i in todo_items(old) if i["uid"] in mine]
                if there:
                    ha_service("todo", "remove_item", {"entity_id": old, "item": there})
            except Exception as e:
                print("Home Assistant to-do list: couldn't tidy up %s (%s)" % (old, e), flush=True)
        with tx() as db:
            db.execute("DELETE FROM ha_todo")
            set_setting_raw(db, "ha_todo_list", entity)
            set_setting_raw(db, "ha_todo_fresh", 1 if entity else 0)
            add_log("settings", "", ("Supply run linked to Home Assistant (%s)" % entity) if entity
                    else "Supply run no longer linked to Home Assistant")
        TODO_STATUS.update(ok=None, error="", synced_at=None, name="")


def ha_todo_lists():
    status, data = ha_request("GET", "/states", timeout=10)
    if status != 200 or not isinstance(data, list):
        raise HAError("Home Assistant answered %s" % status)
    out = [{"entity_id": e["entity_id"], "name": (e.get("attributes") or {}).get("friendly_name") or e["entity_id"]}
           for e in data if isinstance(e, dict) and str(e.get("entity_id", "")).startswith("todo.")]
    return sorted(out, key=lambda x: x["name"].lower())


MAKE_LIST_HELP = ("Home Assistant didn't let Dads Army make the list. You can make it yourself: "
                  "Settings > Devices & services > Add integration > Local To-do, call it %s, "
                  "then choose it here.")


def ha_make_list(name):
    """Make a Local To-do list in Home Assistant (or find one with that name). Returns its entity id."""
    def find():
        for lst in ha_todo_lists():
            if lst["name"].strip().lower() == name.lower():
                return lst["entity_id"]
        return None

    try:
        found = find()
        if found:
            return found
        status, flow = ha_request("POST", "/config/config_entries/flow",
                                  {"handler": "local_todo", "show_advanced_options": False})
        if status != 200 or not isinstance(flow, dict) or not flow.get("flow_id"):
            raise HAError("starting the Local To-do setup: %s %s" % (status, str(flow)[:200]))
        if flow.get("type") == "form":
            field = "todo_list_name"
            for f in flow.get("data_schema") or []:
                if isinstance(f, dict) and f.get("name"):
                    field = f["name"]
                    break
            status, res = ha_request("POST", "/config/config_entries/flow/" + flow["flow_id"], {field: name})
            if status != 200 or not isinstance(res, dict) or res.get("type") not in ("create_entry", "abort"):
                ha_request("DELETE", "/config/config_entries/flow/" + flow["flow_id"])
                raise HAError("finishing the Local To-do setup: %s %s" % (status, str(res)[:200]))
        for _ in range(30):
            found = find()
            if found:
                return found
            time.sleep(0.5)
    except (HAError, OSError) as e:
        print("Home Assistant to-do list: couldn't make one (%s)" % e, flush=True)
        raise ApiError(502, MAKE_LIST_HELP % name)
    raise ApiError(502, "Home Assistant made the list, but it hasn't appeared yet. Try again in a minute.")


# -- Today's checklist: routine checks <-> a Home Assistant to-do list -------------
def checks_entity():
    with LOCK:
        return setting_raw("ha_checks_list", "") or ""


def check_description(c):
    return ("%s%s" % (every_words(c["every_days"]).capitalize(), (". " + c["notes"]) if c["notes"] else ""))[:500]


def checks_sync(entity):
    """Checks that are due (or never done) go on the list. Ticking one there marks it done here;
    deleting one there leaves it off until it's next due. Anything else on the list is left alone.
    Returns True if a check changed here."""
    status, st = ha_request("GET", "/states/" + entity, timeout=8)
    if status == 404:
        raise HAError("the list %s isn't in Home Assistant any more" % entity)
    if status != 200 or not isinstance(st, dict):
        raise HAError("Home Assistant answered %s" % status)
    CHECKS_STATUS["name"] = (st.get("attributes") or {}).get("friendly_name") or entity
    items = todo_items(entity)
    by_uid = {i["uid"]: i for i in items}
    today = dt.date.today()
    with LOCK:
        checks = {c["id"]: c for c in all_checks()}
        track = setting_raw("ha_checks_track", {}) or {}
    due_now = {}
    for cid, c in checks.items():
        due, d, _ = check_status(c, today)
        if d is None or d <= 0:
            due_now[cid] = (c, due.isoformat() if due else "")
    linked = [x for x in track.values() if isinstance(x, dict) and x.get("uid")]
    if len(linked) > 3 and not any(x["uid"] in by_uid for x in linked):
        print("Home Assistant checklist: %s looks new or emptied, so filling it again" % entity, flush=True)
        track = {}

    keep, claimed, updates, removes, ticked = {}, set(), [], [], []
    for key, x in track.items():
        if not isinstance(x, dict) or not key.isdigit():
            continue
        cid, uid = int(key), x.get("uid") or ""
        want = due_now.get(cid)
        it = by_uid.get(uid) if uid else None
        if it is None:                       # deleted there (or dismissed before): off until it's next due
            if want is not None and want[1] == x.get("due"):
                keep[key] = {"uid": "", "summary": x.get("summary", ""), "due": x.get("due")}
            continue
        claimed.add(uid)
        if it.get("status") == "completed":  # ticked off there
            if want is not None:
                ticked.append(cid)
            removes.append(uid)
            continue
        if want is None:                     # done here, or the check's gone
            removes.append(uid)
            continue
        c, due = want
        if it.get("summary") != c["name"]:
            updates.append({"item": uid, "rename": c["name"]})
        if due != x.get("due") and due:
            updates.append({"item": uid, "due_date": due})
        keep[key] = {"uid": uid, "summary": c["name"], "due": due}

    pool = [i for i in items if i["uid"] not in claimed and i.get("status") != "completed"]
    adds = []
    for cid, (c, due) in sorted(due_now.items(), key=lambda kv: (kv[1][1] or "0", kv[1][0]["name"].lower())):
        key = str(cid)
        if key in keep or cid in ticked:
            continue
        same = next((i for i in pool if (i.get("summary") or "") == c["name"]), None)
        if same:                             # already there: take it over rather than add a second
            pool.remove(same)
            claimed.add(same["uid"])
            keep[key] = {"uid": same["uid"], "summary": c["name"], "due": due}
        else:
            adds.append((key, c, due))

    for u in updates:
        try:
            ha_service("todo", "update_item", dict(u, entity_id=entity))
        except HAError:
            if "rename" in u:
                raise
    if removes:
        ha_service("todo", "remove_item", {"entity_id": entity, "item": removes})
    for key, c, due in adds:
        data = {"entity_id": entity, "item": c["name"], "description": check_description(c)}
        if due:
            data["due_date"] = due
        try:
            ha_service("todo", "add_item", data)
        except HAError:   # an older Home Assistant, or a list that doesn't take dates
            ha_service("todo", "add_item", {"entity_id": entity, "item": c["name"]})
    if adds:
        latest = todo_items(entity)
        for key, c, due in adds:
            for i in latest:
                if i["uid"] not in claimed and i.get("summary") == c["name"]:
                    claimed.add(i["uid"])
                    keep[key] = {"uid": i["uid"], "summary": c["name"], "due": due}
                    break

    when = today.isoformat()
    with tx() as db:
        for cid in ticked:
            c = checks[cid]
            db.execute("UPDATE checks SET last_done = ? WHERE id = ?", (when, cid))
            add_log("checked", c["name"], "Ticked off in Home Assistant · next due %s"
                    % human_date(today + dt.timedelta(days=c["every_days"])))
        set_setting_raw(db, "ha_checks_track", keep)
    return bool(ticked)


def checks_tick():
    entity = checks_entity()
    if not entity:
        return
    with TODO_LOCK:
        if checks_entity() != entity:
            return
        try:
            changed = checks_sync(entity)
        except Exception as e:
            if not isinstance(e, (HAError, OSError)):
                traceback.print_exc()
            if CHECKS_STATUS["ok"] is not False:
                print("Home Assistant checklist: can't sync with %s yet (%s). Will keep trying." % (entity, e),
                      flush=True)
            CHECKS_STATUS.update(ok=False, error=str(e))
            return
        if CHECKS_STATUS["ok"] is False:
            print("Home Assistant checklist: syncing again", flush=True)
        CHECKS_STATUS.update(ok=True, error="", synced_at=now_iso())
    if changed:
        HA_WAKE.set()


def checks_link(entity):
    """Put the checks that are due on a different Home Assistant to-do list ('' to stop)."""
    with TODO_LOCK:
        with LOCK:
            old = setting_raw("ha_checks_list", "") or ""
            track = setting_raw("ha_checks_track", {}) or {}
        if old == entity:
            return
        mine = set(x.get("uid") for x in track.values() if isinstance(x, dict) and x.get("uid"))
        if old and mine:
            try:
                there = [i["uid"] for i in todo_items(old) if i["uid"] in mine]
                if there:
                    ha_service("todo", "remove_item", {"entity_id": old, "item": there})
            except Exception as e:
                print("Home Assistant checklist: couldn't tidy up %s (%s)" % (old, e), flush=True)
        with tx() as db:
            set_setting_raw(db, "ha_checks_track", {})
            set_setting_raw(db, "ha_checks_list", entity)
            add_log("settings", "", ("Checks due now go on Home Assistant's list (%s)" % entity) if entity
                    else "Checks no longer go on a Home Assistant list")
        CHECKS_STATUS.update(ok=None, error="", synced_at=None, name="")


# -- Home Assistant's websocket API (dashboards can only be made through it) ---------
class HAWebSocket(object):
    """Just enough of a websocket client for a few commands, using the standard library."""

    def __init__(self, url=None, token=None, timeout=20):
        u = urlparse(url or HA_WS)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        self.buf, self.n = b"", 0
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
                           % (u.path or "/", u.netloc, key)).encode())
        while b"\r\n\r\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise HAError("Home Assistant closed the connection")
            self.buf += chunk
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        if " 101 " not in lines[0] + " ":
            raise HAError("Home Assistant's websocket answered %s" % lines[0][:60])
        want = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        got = [ln.split(":", 1)[1].strip() for ln in lines[1:] if ln.lower().startswith("sec-websocket-accept:")]
        if got != [want]:
            raise HAError("Home Assistant's websocket handshake didn't check out")
        if self.recv().get("type") != "auth_required":
            raise HAError("Home Assistant didn't ask to log in")
        self.send({"type": "auth", "access_token": token or HA_TOKEN})
        if self.recv().get("type") != "auth_ok":
            raise HAError("Home Assistant didn't accept Dads Army's login")

    def _frame(self, op, data):
        n, mask = len(data), os.urandom(4)
        head = bytearray([0x80 | op])
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126)
            head += n.to_bytes(2, "big")
        else:
            head.append(0x80 | 127)
            head += n.to_bytes(8, "big")
        self.sock.sendall(bytes(head) + mask + bytes(b ^ mask[i & 3] for i, b in enumerate(data)))

    def send(self, obj):
        self._frame(0x1, json.dumps(obj).encode("utf-8"))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise HAError("Home Assistant closed the connection")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        parts = []
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = int.from_bytes(self._read(2), "big")
            elif n == 127:
                n = int.from_bytes(self._read(8), "big")
            mask = self._read(4) if b2 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i & 3] for i, b in enumerate(data))
            if op == 0x9:
                self._frame(0xA, data)
                continue
            if op == 0x8:
                raise HAError("Home Assistant closed the connection")
            if op == 0xA:
                continue
            parts.append(data)
            if b1 & 0x80:
                return json.loads(b"".join(parts).decode("utf-8"))

    def command(self, msg):
        self.n += 1
        self.send(dict(msg, id=self.n))
        while True:
            res = self.recv()
            if res.get("id") == self.n and res.get("type") == "result":
                if not res.get("success"):
                    err = res.get("error") or {}
                    raise HAError(str(err.get("message") or err)[:200])
                return res.get("result")

    def close(self):
        try:
            self._frame(0x8, b"\x03\xe8")
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


# -- The Home front dashboard ---------------------------------------------------------
def app_panel():
    """The Dads Army panel in Home Assistant's sidebar: the container's hostname is the app's slug."""
    host = socket.gethostname()
    return "/" + host.replace("-", "_") if re.match(r"^[0-9a-f]{8}-dadsarmy$", host) else "/40ee45c0_dadsarmy"


DASH_WARNINGS = """{% set w = state_attr('sensor.dads_army_warnings', 'items') or [] -%}
{% if states('sensor.dads_army_warnings') in ['unknown', 'unavailable'] -%}
Dads Army isn't sending updates. Check the app is running.
{%- elif not state_attr('sensor.dads_army_warnings', 'enabled') -%}
Warnings are switched off. Turn them on in Dads Army under **HQ → Warnings**.
{%- elif w -%}
{% for i in w[:6] %}
- **{{ i.level }}** · {{ i.title }}{% if i.distance_km is defined %} · {{ i.distance_km }} km away{% endif %}
{%- endfor %}
{%- else -%}
<ha-icon icon="mdi:check-circle"></ha-icon> No warnings for where you are.
{%- endif %}"""

# The Home front's alert card: small, so the rest of the dashboard fits on a tablet without
# scrolling. The level and its colour, the main reason, and the whole scale on one line.
DASH_LEVEL = """{% set lv = state_attr('sensor.dads_army_alert_level', 'level') | int(0) -%}
{% set scale = state_attr('sensor.dads_army_alert_level', 'scale') or [] -%}
{% set r = state_attr('sensor.dads_army_alert_level', 'reasons') or [] -%}
{% if lv == 0 or not scale -%}
Dads Army isn't sending updates. Check the app is running.
{%- else -%}
{% set me = scale[lv - 1] -%}
## {{ me.emoji }} {{ me.name }}
<ha-alert alert-type="{{ ['success', 'warning', 'warning', 'error', 'error'][lv - 1] }}"><b>{{ me.action }}.</b> {% if r %}{{ r[0].title | truncate(80) }}{% if r | count > 1 %}, and {{ r | count - 1 }} more{% endif %}.{% else %}Nothing is raising the level.{% endif %}</ha-alert>

<small>{% for s in scale %}{% if s.level == lv %}<b>{{ s.emoji }} {{ s.name }}</b>{% else %}{{ s.emoji }} {{ s.name }}{% endif %}{% if not loop.last %} · {% endif %}{% endfor %}</small>
{%- endif %}"""

# The "Why, and what to do now" page: the level big, with the scale top to bottom...
DASH_LEVEL_FULL = """{% set lv = state_attr('sensor.dads_army_alert_level', 'level') | int(0) -%}
{% set scale = state_attr('sensor.dads_army_alert_level', 'scale') or [] -%}
{% if lv == 0 or not scale -%}
Dads Army isn't sending updates. Check the app is running.
{%- else -%}
{% set me = scale[lv - 1] -%}
# {{ me.emoji }} {{ me.name }}
<ha-alert alert-type="{{ ['success', 'warning', 'warning', 'error', 'error'][lv - 1] }}">{{ me.meaning }}</ha-alert>

| | Household alert level | |
|:-:|:--|:--|
{% for s in scale | reverse -%}
| {{ s.emoji }} | {% if s.level == lv %}**{{ s.name }}**{% else %}{{ s.name }}{% endif %} | {% if s.level == lv %}**◀ you are here**{% endif %} |
{% endfor %}
{%- endif %}"""

# ...then every reason and all the labelled advice.
DASH_WHY = """{% set a = 'sensor.dads_army_alert_level' -%}
{% set scale = state_attr(a, 'scale') or [] -%}
{% set r = state_attr(a, 'reasons') or [] -%}
{% set n = state_attr(a, 'notes') or [] -%}
{% set g = state_attr(a, 'guidance') or [] -%}
#### Why
{% for i in r %}
- {{ scale[i.level - 1].emoji if scale else '' }} {{ i.title }} ({{ i.name | lower }})
{%- endfor %}
{%- if state_attr(a, 'escalated') %}
- ⬆️ Raised to SEVERE because the stores wouldn't last 3 days, so you'd be less able to cope
{%- endif %}
{%- if not r %}
Nothing is raising the level.
{%- endif %}
{%- if n %}

Also worth knowing: {{ n | join(' · ') }}
{%- endif %}

#### What to do now
{% for i in g %}
- **{{ i.label }}:** {{ i.text }}
{%- endfor %}

<small>UK Government advice is put into plain words, not quoted. SAS statements apply the SAS Survival Handbook's PLAN priorities to a home. Always follow official advice and the emergency services. In an emergency, call 999.</small>"""

DASH_LEVELS_PAGE = """## What the household alert levels mean

Dads Army works out a household alert level from the warnings in force where you live, your home's own sensors, and how long your stores would last. It's the household's own level, not the official UK threat level: it borrows the names of the UK's five national threat levels, which are the UK's nearest equivalent to America's DEFCON.

| | Level | What it means for the household |
|:-:|:--|:--|
| 🟩 | **LOW** | Nothing is threatening the household and the stores would last at least 3 days. Carry on as normal. |
| 🟨 | **MODERATE** | Something to keep an eye on: a yellow warning, a minor problem at home, or stores that wouldn't last 3 days. Stay aware. |
| 🟧 | **SUBSTANTIAL** | Disruption is likely: an amber warning, a power cut, a leak, or a cold or hot home. Get ready. |
| 🟥 | **SEVERE** | Disruption is highly likely or under way: a red warning, a flood warning, a long power cut, or a dangerously cold or hot home. Act now. |
| ⬛ | **CRITICAL** | Danger to life, now or very soon: an Emergency Alert, a severe flood warning, or a gas, carbon monoxide or smoke alarm. Follow the emergency services' instructions. |

### How Dads Army decides

The level is the most serious of these. If it's SUBSTANTIAL and your food or water wouldn't last 3 days, it goes up to SEVERE, because you'd be less able to cope. Only real danger makes it CRITICAL.

| Level | Warnings | At home (your sensors) | Stores |
|:--|:--|:--|:--|
| CRITICAL | Emergency Alert; severe flood warning | Gas, carbon monoxide or smoke alarm | |
| SEVERE | Red weather warning; flood warning | Power cut over 12 hours, or with the backup battery under 20%; coldest room under 9°C; warmest room 33°C or more; PM2.5 75 µg/m³ or more | |
| SUBSTANTIAL | Amber weather warning; a possible fire within 3 km | Power cut; water leak; coldest room under 12°C; warmest room 30°C or more; −10°C or colder, or 35°C or hotter, outside; PM2.5 55 or more | |
| MODERATE | Yellow weather warning; flood alert; a disaster near the UK; a possible fire nearby | Coldest room under 16°C; warmest room 27°C or more; −5°C or colder, or 30°C or hotter, outside; humidity 80% or more; internet down; PM2.5 35 or more | Food or water for under 3 days; kit under half stocked |
| LOW | None of the above | | |

UKHSA advises heating the rooms you use to at least 18°C. Below that, Dads Army adds cold-weather advice even at LOW.

### The UK's own levels

The national threat level, set by MI5's Joint Terrorism Analysis Centre, uses the same five names: LOW (an attack is highly unlikely), MODERATE (possible, but not likely), SUBSTANTIAL (likely), SEVERE (highly likely) and CRITICAL (highly likely in the near future). You can check the current national level on MI5's website. Dads Army doesn't read it.

### Where the advice comes from

- **UK Government:** advice from Prepare (gov.uk), the NHS, UKHSA, the Met Office, the Environment Agency, DEFRA, Ofgem, the Foreign Office and the Fire Kills campaign. It's put into plain statements, not quoted word for word.
- **SAS Survival Handbook:** John "Lofty" Wiseman's PLAN priorities (Protection, Location, Acquisition, Navigation), applied to a household. These are paraphrased, not quoted.
- **Fire & rescue services** and **Electricity networks (105):** their standard public advice.
- **Dads Army tip:** practical hints from the app itself.

Always follow official advice and the emergency services. In an emergency, call 999."""

DASH_CHECKS = """{% set c = state_attr('sensor.dads_army_checks_due', 'items') or [] -%}
{% for i in c[:8] %}
- **{{ i.name }}** · {{ i.text }}
{%- endfor %}
{%- if not c %}<ha-icon icon="mdi:check-circle"></ha-icon> Nothing due.{% endif %}"""

DASH_USE_FIRST = """{% set rows = (state_attr('sensor.dads_army_expired', 'items') or [])
   + (state_attr('sensor.dads_army_expiring_soon', 'items') or []) -%}
{% for i in rows[:8] %}
- **{{ i.name }}** · {{ i.text }}
{%- endfor %}
{%- if not rows %}<ha-icon icon="mdi:check-circle"></ha-icon> Nothing close to its best-before date.{% endif %}"""


def dashboard_config():
    """A sections dashboard made of Home Assistant's own cards: nothing extra to install."""
    with LOCK:
        checks = setting_raw("ha_checks_list", "") or ""
        supply = setting_raw("ha_todo_list", "") or ""
    full = {"grid_options": {"columns": "full"}}

    def tile(entity, name, color=None, icon=None):
        c = {"type": "tile", "entity": entity, "name": name}
        if color:
            c["color"] = color
        if icon:
            c["icon"] = icon
        return c

    def heading(text, icon, badges=None):
        h = {"type": "heading", "heading": text, "icon": icon}
        if badges:
            h["badges"] = badges
        return h

    # Home Assistant has no pop-up of its own (only add-ons like browser_mod), so the details
    # open on their own pages, with a back arrow.
    level = "sensor.dads_army_alert_level"
    go_why = {"action": "navigate", "navigation_path": "/%s/alert-level" % DASH_URL}
    go_levels = {"action": "navigate", "navigation_path": "/%s/alert-levels" % DASH_URL}
    info = [{"type": "entity", "entity": level, "icon": "mdi:information-outline", "show_icon": True,
             "show_state": False, "tap_action": go_levels}]

    def nav_tile(name, icon, go):
        return dict({"type": "tile", "entity": level, "name": name, "icon": icon, "hide_state": True,
                     "tap_action": go, "icon_tap_action": go}, **full)

    checklist = ([dict({"type": "todo-list", "entity": checks, "hide_completed": True}, **full)] if checks else
                 [dict({"type": "markdown", "content": DASH_CHECKS}, **full)])
    shopping = ([dict({"type": "todo-list", "entity": supply, "hide_completed": True}, **full)] if supply else [])
    sections = [
        # One column, so the warnings and today's checklist sit beside it.
        {"type": "grid", "cards": [
            heading("Household alert level", "mdi:shield-home", info),
            dict({"type": "markdown", "content": DASH_LEVEL}, **full),
            nav_tile("Why, and what to do now", "mdi:clipboard-list-outline", go_why)]},
        {"type": "grid", "cards": [
            heading("Warnings", "mdi:alert-octagon"),
            dict(tile("sensor.dads_army_warnings", "Warnings in force", "red"), **full),
            dict({"type": "markdown", "content": DASH_WARNINGS}, **full)]},
        {"type": "grid", "cards": [
            heading("Today's checklist", "mdi:clipboard-check-outline"),
            dict(tile("sensor.dads_army_checks_due", "Checks due", "purple"), **full)] + checklist},
        {"type": "grid", "cards": [
            heading("Readiness", "mdi:shield-home"),
            dict({"type": "gauge", "entity": "sensor.dads_army_readiness", "name": "Readiness", "min": 0, "max": 100,
                  "needle": True, "severity": {"green": 100, "yellow": 50, "red": 0}}, **full),
            tile("sensor.dads_army_hold_out", "Hold out", None, "mdi:shield-home"),
            tile("sensor.dads_army_supplies", "Daily supplies"),
            tile("sensor.dads_army_food_days", "Food"),
            tile("sensor.dads_army_water_days", "Water")]},
        {"type": "grid", "cards": [
            heading("Stores", "mdi:package-variant"),
            tile("sensor.dads_army_expired", "Expired", "red"),
            tile("sensor.dads_army_expiring_soon", "Expiring soon", "amber"),
            tile("sensor.dads_army_out_of_stock", "Out of stock", "deep-orange"),
            tile("sensor.dads_army_low_stock", "Running low", "amber"),
            tile("sensor.dads_army_kit_stocked", "Kit stocked"),
            tile("sensor.dads_army_stores_value", "Stores worth"),
            dict({"type": "markdown", "title": "Use first", "content": DASH_USE_FIRST}, **full)]},
        {"type": "grid", "cards": [
            heading("Supply run", "mdi:cart"),
            dict(tile("sensor.dads_army_supply_run", "To get"), **full)] + shopping + [
            dict({"type": "button", "name": "Open Dads Army", "icon": "mdi:open-in-app", "show_state": False,
                  "tap_action": {"action": "navigate", "navigation_path": app_panel()}}, **full)]},
        {"type": "grid", "cards": [
            heading("Days you could last", "mdi:chart-line"),
            dict({"type": "history-graph", "hours_to_show": 720, "entities": [
                {"entity": "sensor.dads_army_food_days", "name": "Food"},
                {"entity": "sensor.dads_army_water_days", "name": "Water"}]}, **full)]},
    ]
    return {"views": [{"title": "Home front", "path": "home-front", "type": "sections", "max_columns": 3,
                       "badges": [{"type": "entity", "entity": level, "name": "Alert level",
                                   "show_name": True, "tap_action": go_why},
                                  {"type": "entity", "entity": "sensor.dads_army_readiness", "name": "Readiness",
                                   "show_name": True},
                                  {"type": "entity", "entity": "sensor.dads_army_hold_out", "name": "Hold out",
                                   "show_name": True},
                                  {"type": "entity", "entity": "binary_sensor.dads_army_attention",
                                   "name": "Needs attention", "show_name": True}],
                       "sections": sections},
                      {"title": "Household alert level", "path": "alert-level", "subview": True, "type": "sections",
                       "max_columns": 3, "back_path": "/%s/home-front" % DASH_URL,
                       "sections": [
                           {"type": "grid", "cards": [
                               heading("Where the household stands", "mdi:shield-home", info),
                               dict({"type": "markdown", "content": DASH_LEVEL_FULL}, **full),
                               nav_tile("What the levels mean", "mdi:information-outline", go_levels)]},
                           {"type": "grid", "column_span": 2, "cards": [
                               heading("Why, and what to do now", "mdi:clipboard-list-outline"),
                               dict({"type": "markdown", "content": DASH_WHY}, **full)]}]},
                      # No back_path: back goes to whichever page opened it.
                      {"title": "What the levels mean", "path": "alert-levels", "subview": True, "type": "panel",
                       "cards": [{"type": "markdown", "content": DASH_LEVELS_PAGE}]}]}


def ha_dashboard():
    """Make (or bring up to date) the Home front dashboard in Home Assistant's sidebar."""
    try:
        ws = HAWebSocket()
    except (HAError, OSError) as e:
        raise ApiError(502, "Couldn't reach Home Assistant to make the dashboard (%s)" % e)
    try:
        boards = ws.command({"type": "lovelace/dashboards/list"}) or []
        made = False
        if not any(isinstance(b, dict) and b.get("url_path") == DASH_URL for b in boards):
            ws.command({"type": "lovelace/dashboards/create", "url_path": DASH_URL, "title": "Home front",
                        "icon": "mdi:shield-home", "show_in_sidebar": True, "require_admin": False,
                        "mode": "storage"})
            made = True
        ws.command({"type": "lovelace/config/save", "url_path": DASH_URL, "config": dashboard_config()})
    except HAError as e:
        raise ApiError(502, "Home Assistant didn't let Dads Army make the dashboard (%s). You can paste the card "
                            "from the app's Documentation tab into a dashboard instead." % e)
    except OSError as e:
        raise ApiError(502, "Lost touch with Home Assistant while making the dashboard (%s)" % e)
    finally:
        ws.close()
    info = {"url": "/" + DASH_URL, "made_at": now_iso(), "layout": DASH_LAYOUT}
    with tx() as db:
        set_setting_raw(db, "ha_dashboard", info)
        add_log("settings", "", "Home front dashboard %s in Home Assistant" % ("made" if made else "brought up to date"))
    return made


def level_change(sit):
    """Fire dads_army_alert_level when the household alert level moves (not when Dads Army restarts)."""
    with LOCK:
        last = setting_raw("alert_level_last", None)
    if last == sit["level"]:
        return
    if isinstance(last, int):
        prev = LEVELS[last - 1][0]
        rising = sit["level"] > last
        why = sit["reasons"][0]["title"] if sit["reasons"] else ""
        todo = sit["guidance"][0] if sit["guidance"] else None
        msg = "Household alert level %s %s (was %s)." % ("up to" if rising else "down to", sit["name"], prev)
        if why:
            msg += " " + why + "."
        if todo and rising:
            msg += " %s: %s" % (todo["label"], todo["text"])
        ha_call("POST", "/events/dads_army_alert_level", {
            "level": sit["level"], "name": sit["name"], "previous": last, "previous_name": prev, "rising": rising,
            "message": msg, "reasons": [r["title"] for r in sit["reasons"][:6]], "meaning": sit["meaning"]})
    with tx() as db:
        set_setting_raw(db, "alert_level_last", sit["level"])


# -- The background loop -------------------------------------------------------
def ha_loop():
    """Keep Home Assistant's Dads Army sensors and to-do list up to date."""
    probe = "sensor.dads_army_hold_out"
    sent, failing, last_full, levels = {}, False, None, None
    HA_WAKE.set()  # first push straight away
    while True:
        HA_WAKE.wait(15 if failing else 30 if (todo_entity() or checks_entity()) else 60)
        HA_WAKE.clear()
        time.sleep(1)  # let a burst of changes settle
        try:
            s = summary()
            now = stock_levels()
        except Exception:
            traceback.print_exc()
            continue
        if HA_REBASE.is_set():
            HA_REBASE.clear()
            levels = None
        try:
            ev = ran_out(levels, now) if levels is not None and not failing else None
            levels = now
            if ev:
                ha_call("POST", "/events/dads_army_ran_out", ev)
            ents = ha_entities(s)
            full = last_full is None or time.monotonic() - last_full > 1800
            if not full and ha_call("GET", "/states/" + probe, timeout=5) == 404:
                full = True  # Home Assistant restarted and forgot them
            for eid, body in ents.items():
                payload = json.dumps(body, sort_keys=True)
                if full or sent.get(eid) != payload:
                    status = ha_call("POST", "/states/" + eid, body)
                    if status not in (200, 201):
                        raise RuntimeError("Home Assistant answered %s" % status)
                    sent[eid] = payload
                    HA_LAST[eid] = body
            if full:
                last_full = time.monotonic()
            level_change(s["situation"])
            if failing:
                print("Home Assistant sensors: connected again", flush=True)
            failing = False
        except Exception as e:
            if not failing:
                print("Home Assistant sensors: can't update them yet (%s). Will keep trying." % e, flush=True)
            failing, last_full = True, None
            sent.clear()
        if not failing:
            todo_tick(s)
            checks_tick()


def ha_mark_unavailable():
    """On shutdown, show the number sensors as unavailable rather than leaving old numbers up.

    Sensors without a unit (needs attention, next to expire) are left as they are: Home
    Assistant's Activity log records their every change, so marking them unavailable added
    an "Unavailable" and a "Problem" line for every update and every nightly backup. The
    number sensors becoming unavailable is enough to show that Dads Army has stopped."""
    for eid, body in list(HA_LAST.items()):
        if "unit_of_measurement" not in body["attributes"]:
            continue
        attrs = {k: v for k, v in body["attributes"].items() if k in
                 ("friendly_name", "icon", "unit_of_measurement", "state_class", "device_class")}
        try:
            ha_call("POST", "/states/" + eid, {"state": "unavailable", "attributes": attrs}, timeout=2)
        except Exception:
            return


# -- API for the HQ screen -------------------------------------------------------
def need_ha():
    if not HA_TOKEN:
        raise ApiError(409, "This only works when Dads Army runs as a Home Assistant app")


@route("GET", "/api/homeassistant")
def api_ha(body, query):
    need_ha()
    try:
        lists, error = ha_todo_lists(), ""
    except Exception as e:
        lists, error = [], "Couldn't get the lists from Home Assistant (%s)" % e
    return {"lists": lists, "error": error, "status": ha_status()}


@route("PUT", "/api/homeassistant")
def api_ha_set(body, query):
    """Link the supply run ("todo_list") and/or the checks that are due ("checks_list") to to-do lists."""
    need_ha()
    want = {}
    for key in ("todo_list", "checks_list"):
        if key in body:
            entity = clean_text(body.get(key), 120)
            if entity and not TODO_RE.match(entity):
                raise ApiError(400, "That isn't a Home Assistant to-do list")
            want[key] = entity
    if not want:
        raise ApiError(400, "Nothing to change")
    with LOCK:
        supply = want.get("todo_list", setting_raw("ha_todo_list", "") or "")
        checks = want.get("checks_list", setting_raw("ha_checks_list", "") or "")
    if supply and supply == checks:
        raise ApiError(400, "Use different lists for the supply run and the checks")
    if "todo_list" in want:
        todo_link(want["todo_list"])
    if "checks_list" in want:
        checks_link(want["checks_list"])
    return {"status": ha_status()}


@route("POST", "/api/homeassistant/todo-list")
def api_ha_make_list(body, query):
    need_ha()
    entity = ha_make_list(TODO_LIST_NAME)
    todo_link(entity)
    return {"status": ha_status(), "entity_id": entity}


@route("POST", "/api/homeassistant/checks-list")
def api_ha_make_checks_list(body, query):
    need_ha()
    entity = ha_make_list(CHECKS_LIST_NAME)
    if entity == todo_entity():
        raise ApiError(400, "Use different lists for the supply run and the checks")
    checks_link(entity)
    HA_WAKE.set()
    return {"status": ha_status(), "entity_id": entity}


@route("PUT", "/api/homeassistant/prompt")
def api_ha_prompt(body, query):
    """The offer to make the dashboard: ask again in a few days ({"snooze_days": n}), or never ({"never": true})."""
    need_ha()
    if body.get("never"):
        val = {"never": True}
    else:
        days = int(clean_num(body.get("snooze_days"), 14, 1, 365, "Days"))
        val = {"until": (dt.date.today() + dt.timedelta(days=days)).isoformat()}
    with tx() as db:
        set_setting_raw(db, "ha_dash_prompt", val)
    return {"status": ha_status()}


@route("POST", "/api/homeassistant/dashboard")
def api_ha_dashboard(body, query):
    need_ha()
    made = ha_dashboard()
    return {"status": ha_status(), "made": made, "url": "/" + DASH_URL}


# --------------------------------------------------------------------------
# Warnings: Met Office, floods, Emergency Alerts, GDACS, UKHSA and WHO
# --------------------------------------------------------------------------
# Optional, and off until it's switched on in HQ. Dads Army downloads the same
# public files for everyone and works out here which warnings are near you, so
# nothing about you is sent anywhere. Without the internet everything else
# carries on, and the last warnings found stay on show with when they were checked.
FEED_URLS = {
    "metoffice": "https://www.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/UK",
    "floods": "https://environment.data.gov.uk/flood-monitoring/id/floods",
    "floodarea": "https://environment.data.gov.uk/flood-monitoring/id/floodAreas/{id}",
    "govalerts": "https://www.gov.uk/alerts/feed.atom",
    "gdacs": "https://www.gdacs.org/xml/rss.xml",
    "ukhsa": "https://www.gov.uk/search/news-and-communications.atom?organisations%5B%5D=uk-health-security-agency",
    "who": "https://www.who.int/api/news/diseaseoutbreaknews?$top=6&$orderby=PublicationDateAndTime%20desc"
           "&$select=Title,OverrideTitle,UseOverrideTitle,UrlName,PublicationDateAndTime",
    # NASA FIRMS: satellite fire detections for Europe over the last 7 days (free, no account)
    "fires": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_7d.csv",
    "fires_modis": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Europe_7d.csv",
}
try:   # for testing against local copies
    FEED_URLS.update(json.loads(os.environ.get("DADSARMY_FEED_URLS") or "{}"))
except ValueError:
    pass
FEED_UA = "DadsArmy/%s (+https://github.com/parkerveese-cloud/dads-army)" % VERSION
WARN_SOURCES = [  # key, what it is, on by default
    ("metoffice", "Met Office weather warnings", True),
    ("floods", "Flood warnings (England)", True),
    ("govalerts", "UK Emergency Alerts", True),
    ("gdacs", "Disasters near the UK (GDACS)", True),
    ("fires", "Possible fires nearby (NASA satellites)", False),
    ("ukhsa", "UK Health Security Agency news", False),
    ("who", "WHO disease outbreak news", False),
]
WARN_SOURCE_NAMES = {"metoffice": "Met Office", "floods": "Environment Agency", "govalerts": "GOV.UK Emergency Alerts",
                     "gdacs": "GDACS", "fires": "NASA FIRMS", "ukhsa": "UKHSA", "who": "WHO"}
MET_REGIONS = [  # code, name, rough middle (to guess yours from Home Assistant's location)
    ("os", "Orkney & Shetland", 59.6, -2.0), ("he", "Highlands & Eilean Siar", 57.5, -5.0),
    ("gr", "Grampian", 57.2, -2.8), ("st", "Strathclyde", 55.8, -4.8),
    ("ta", "Central, Tayside & Fife", 56.5, -3.6), ("dg", "SW Scotland, Lothian Borders", 55.4, -3.2),
    ("ni", "Northern Ireland", 54.6, -6.7), ("wl", "Wales", 52.3, -3.7),
    ("nw", "North West England", 54.0, -2.7), ("ne", "North East England", 54.9, -1.8),
    ("yh", "Yorkshire & Humber", 53.9, -1.2), ("wm", "West Midlands", 52.5, -2.1),
    ("em", "East Midlands", 52.9, -0.9), ("ee", "East of England", 52.3, 0.7),
    ("sw", "South West England", 50.8, -3.8), ("se", "London & South East England", 51.3, -0.5),
]
MET_NAME = {c: n for c, n, _, _ in MET_REGIONS}
WARN_DEFAULTS = {"on": False, "sources": {k: d for k, _, d in WARN_SOURCES}, "region": "", "lat": None, "lon": None,
                 "flood_km": 20, "gdacs_km": 1000, "fire_km": 10}
WARN_EVERY = 15 * 60      # seconds between checks
FLOOD_LOOKUPS = 80        # flood areas to look up per check (they're kept once found)
WARN_STATE = {"items": [], "news": [], "sources": {}, "checked_at": None, "region": "", "seen": {}}
WARN_LOCK = threading.Lock()
WARN_WAKE = threading.Event()
WARN_DONE = threading.Condition()
WARN_RUNS = {"n": 0, "busy": False}
HA_HOME = {"lat": None, "lon": None, "at": 0.0}


class NeedLocation(Exception):
    pass


def warn_cfg():
    """The warnings settings, with defaults filled in."""
    raw = setting_raw("warnings", None)
    raw = raw if isinstance(raw, dict) else {}
    cfg = json.loads(json.dumps(WARN_DEFAULTS))
    cfg["on"] = bool(raw.get("on"))
    src = raw.get("sources") if isinstance(raw.get("sources"), dict) else {}
    for k in cfg["sources"]:
        if k in src:
            cfg["sources"][k] = bool(src[k])
    if raw.get("region") in MET_NAME or raw.get("region") == "UK":
        cfg["region"] = raw["region"]
    for k, lim in (("lat", 90), ("lon", 180)):
        v = raw.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and -lim <= v <= lim:
            cfg[k] = float(v)
    if cfg["lat"] is None or cfg["lon"] is None:
        cfg["lat"] = cfg["lon"] = None
    for k, lo, hi in (("flood_km", 1, 200), ("gdacs_km", 50, 5000), ("fire_km", 2, 50)):
        v = raw.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            cfg[k] = int(min(hi, max(lo, v)))
    return cfg


def km_between(lat1, lon1, lat2, lon2):
    r = math.radians
    h = (math.sin(r(lat2 - lat1) / 2) ** 2
         + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(r(lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def home_location(cfg):
    """Where you are: set by hand in HQ, or Home Assistant's home location. None if neither."""
    if cfg["lat"] is not None:
        return {"lat": cfg["lat"], "lon": cfg["lon"], "from": "manual"}
    if HA_HOME["lat"] is not None:
        return {"lat": HA_HOME["lat"], "lon": HA_HOME["lon"], "from": "homeassistant"}
    return None


def refresh_ha_home():
    if not HA_TOKEN or time.time() - HA_HOME["at"] < 3600:
        return
    try:
        status, out = ha_request("GET", "/config", timeout=8)
        if status == 200 and isinstance(out, dict) and out.get("latitude") is not None:
            HA_HOME.update(lat=float(out["latitude"]), lon=float(out["longitude"]), at=time.time())
    except Exception:
        pass


def guess_region(loc):
    if not loc:
        return ""
    return min(MET_REGIONS, key=lambda r: km_between(loc["lat"], loc["lon"], r[2], r[3]))[0]


def http_get(url, timeout=20, limit=8 * 1024 * 1024):
    req = urllib.request.Request(url, headers={"User-Agent": FEED_UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("the feed is too big")
    return data


def parse_xml(data):
    low = data.lower()
    if b"<!doctype" in low or b"<!entity" in low:   # feeds don't need these; refusing them keeps parsing safe
        raise ValueError("the feed isn't plain XML")
    return ET.fromstring(data)


TAG_RE = re.compile(r"<[^>]+>")


def plain(s, maxlen=1500):
    """Feed text without HTML, tidied up."""
    s = htmllib.unescape(TAG_RE.sub(" ", s or ""))
    s = re.sub(r"[ \t\r\f\v ]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()[:maxlen]


def safe_url(u):
    u = (u or "").strip()
    return u[:500] if re.match(r"^https?://[^\s\"'<>]+$", u) else ""


def parse_when(s):
    """An ISO or RSS date as an aware datetime (UTC if no zone given), or None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            from email.utils import parsedate_to_datetime
            d = parsedate_to_datetime(s)
        except (TypeError, ValueError, IndexError):
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def iso_utc(d):
    return d.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat() if d else ""


ATOM = "{http://www.w3.org/2005/Atom}"
GDACS = "{http://www.gdacs.org}"
MET_LEVEL = {"yellow": 1, "amber": 2, "red": 3}
FLOOD_LEVEL = {1: (3, "Severe flood warning"), 2: (2, "Flood warning"), 3: (1, "Flood alert")}
GDACS_LEVEL = {"orange": 2, "red": 3}


def parse_met(data, region_name):
    """Met Office warnings in force, for one region ('' for all of the UK)."""
    out = []
    for it in parse_xml(data).iter("item"):
        title = plain(it.findtext("title"), 300)
        text = plain(it.findtext("description"), 1500)
        if region_name and region_name.lower() not in (title + " " + text).lower():
            continue
        word = title.split(" ", 1)[0].lower() if title else ""
        m = re.search(r"valid from (.+?) to (.+?)(?:\.|\n|$)", text, re.I)
        out.append({"id": "met:" + (it.findtext("guid") or it.findtext("link") or title)[:200], "source": "metoffice",
                    "kind": "weather", "severity": MET_LEVEL.get(word, 1),
                    "level": word.capitalize() if word in MET_LEVEL else "Warning", "title": title, "text": text,
                    "area": region_name, "when": ("%s to %s" % (m.group(1), m.group(2))) if m else "",
                    "url": safe_url(it.findtext("link")) or "https://weather.metoffice.gov.uk/warnings-and-advice/uk-warnings",
                    "issued": iso_utc(parse_when(it.findtext("pubDate")))})
    return out


def parse_floods(data):
    """Every flood alert and warning in force in England (where they are comes separately)."""
    doc = json.loads(data.decode("utf-8"))
    rows = []
    for f in doc.get("items") or []:
        if not isinstance(f, dict) or f.get("severityLevel") not in FLOOD_LEVEL:
            continue
        area = f.get("floodArea") if isinstance(f.get("floodArea"), dict) else {}
        nid = str(f.get("floodAreaID") or area.get("notation") or "")[:60]
        if not re.match(r"^[A-Za-z0-9_-]+$", nid):
            continue
        sev, word = FLOOD_LEVEL[f["severityLevel"]]
        rows.append({"id": "flood:" + nid, "area_id": nid, "source": "floods", "kind": "flood", "severity": sev,
                     "level": word, "title": "%s: %s" % (word, plain(f.get("description"), 200)),
                     "text": plain(f.get("message"), 1500), "area": plain(area.get("county"), 200), "when": "",
                     "url": "https://check-for-flooding.service.gov.uk/target-area/" + nid,
                     "issued": iso_utc(parse_when(f.get("timeRaised")))})
    return rows


def flood_centre(nid):
    doc = json.loads(http_get(FEED_URLS["floodarea"].format(id=nid), timeout=15).decode("utf-8"))
    it = doc.get("items")
    it = (it[0] if it else {}) if isinstance(it, list) else (it or {})
    return [float(it["lat"]), float(it["long"])]


def parse_gdacs(data, home, km):
    """Orange and red disaster alerts in force within km of home."""
    out = []
    for it in parse_xml(data).iter("item"):
        if (it.findtext(GDACS + "iscurrent") or "").strip().lower() != "true":
            continue
        lvl = (it.findtext(GDACS + "alertlevel") or "").strip().lower()
        if lvl not in GDACS_LEVEL:
            continue
        try:
            lat, lon = [float(x) for x in (it.findtext("{http://www.georss.org/georss}point") or "").split()[:2]]
        except ValueError:
            continue
        d = km_between(home["lat"], home["lon"], lat, lon)
        if d > km:
            continue
        out.append({"id": "gdacs:" + (it.findtext("guid") or it.findtext("link") or "")[:200], "source": "gdacs",
                    "kind": "disaster", "severity": GDACS_LEVEL[lvl], "level": lvl.capitalize() + " alert",
                    "title": plain(it.findtext("title"), 300), "text": plain(it.findtext("description"), 1500),
                    "area": plain(it.findtext(GDACS + "country"), 120), "distance_km": int(round(d)), "when": "",
                    "url": safe_url(it.findtext("link")), "issued": iso_utc(parse_when(it.findtext("pubDate")))})
    return out


ALERT_STAMP = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) (BST|GMT|UTC)\]")


def parse_govalerts(data, now):
    """Emergency Alerts still being sent, or that stopped in the last 12 hours."""
    out = []
    for e in parse_xml(data).iter(ATOM + "entry"):
        summ = plain(e.findtext(ATOM + "summary"), 600)
        stamps = [dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(
            tzinfo=dt.timezone(dt.timedelta(hours=1 if m.group(2) == "BST" else 0))) for m in ALERT_STAMP.finditer(summ)]
        sent = stamps[0] if stamps else parse_when(e.findtext(ATOM + "published"))
        stopped = stamps[1] if len(stamps) > 1 and "Stopped" in summ else None
        if sent is None or (stopped is None and now - sent > dt.timedelta(hours=24)) \
                or (stopped is not None and now - stopped > dt.timedelta(hours=12)):
            continue
        content = e.find(ATOM + "content")
        text = plain(" ".join(content.itertext()), 1500) if content is not None else ""
        live = stopped is None or stopped > now
        test = bool(re.search(r"\btest(ing)?\b", text, re.I))
        area = plain(e.findtext(ATOM + "title"), 200)
        link = e.find(ATOM + "link")
        # "Alert area: X. Sent: 5:00pm (GMT) on ... [2026-01-08 17:00 GMT]. Stopped: ..." -> "Sent: 5:00pm (GMT) on .... Stopped: ..."
        when = re.sub(r"^Alert area:.*?\.\s*(?=Sent)", "", re.sub(r"\s*\[[^\]]*\]", "", summ)).strip()
        out.append({"id": "govalert:" + (e.findtext(ATOM + "id") or summ)[:200], "source": "govalerts", "kind": "alert",
                    "severity": 3 if live and not test else 1,
                    "level": "Test" if test else "Emergency Alert" if live else "Ended",
                    "title": "Emergency Alert: " + area, "text": text, "area": area, "when": when,
                    "url": safe_url(link.get("href") if link is not None else "") or "https://www.gov.uk/alerts",
                    "issued": iso_utc(sent)})
    return out


def parse_ukhsa(data, now):
    out = []
    for e in parse_xml(data).iter(ATOM + "entry"):
        when = parse_when(e.findtext(ATOM + "updated"))
        if not when or now - when > dt.timedelta(days=14):
            continue
        link = e.find(ATOM + "link")
        out.append({"id": "ukhsa:" + (e.findtext(ATOM + "id") or "")[:200], "source": "ukhsa", "kind": "news",
                    "severity": 0, "level": "News", "title": plain(e.findtext(ATOM + "title"), 300),
                    "text": plain(e.findtext(ATOM + "summary"), 600), "area": "", "when": "",
                    "url": safe_url(link.get("href") if link is not None else ""), "issued": iso_utc(when)})
    return out[:4]


def parse_who(data, now):
    out = []
    for v in json.loads(data.decode("utf-8")).get("value") or []:
        if not isinstance(v, dict):
            continue
        when = parse_when(v.get("PublicationDateAndTime"))
        if not when or now - when > dt.timedelta(days=21):
            continue
        title = v.get("OverrideTitle") if v.get("UseOverrideTitle") and v.get("OverrideTitle") else v.get("Title")
        slug = str(v.get("UrlName") or "")
        out.append({"id": "who:" + slug[:100], "source": "who", "kind": "news", "severity": 0, "level": "Outbreak news",
                    "title": plain(title, 300), "text": "", "area": "", "when": "",
                    "url": ("https://www.who.int/emergencies/disease-outbreak-news/item/" + slug
                            if re.match(r"^[\w-]+$", slug) else "https://www.who.int/emergencies/disease-outbreak-news"),
                    "issued": iso_utc(when)})
    return out[:4]


# -- Possible fires, from NASA's satellites ---------------------------------------
# A satellite sees any big heat source: wildfires, but also controlled heather
# burning, farm fires and industrial flares. Places that show up again and again
# over weeks are flares and the like, so they're left out; real fires come and go.
FIRE_HISTORY_KM = 50     # remember where hotspots were seen within this distance
FIRE_CLUSTER_KM = 2      # hotspots this close together count as one fire
FIRE_IGNORE_KM = 1.5     # a spot you've said isn't a wildfire covers this far
FIRE_FRESH = dt.timedelta(hours=24)   # only the last day's sightings are shown; the rest is history


def parse_firms(data):
    """(lat, lon, when) for each confident detection in a FIRMS CSV (VIIRS or MODIS)."""
    rows = []
    for r in csv.DictReader(io.StringIO(data.decode("utf-8", "replace"))):
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        conf = (r.get("confidence") or "").strip().lower()
        if conf in ("l", "low") or (conf.isdigit() and int(conf) < 50):
            continue
        try:
            when = dt.datetime.strptime((r.get("acq_date") or "").strip() + (r.get("acq_time") or "").strip().zfill(4),
                                        "%Y-%m-%d%H%M").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        rows.append((lat, lon, when))
    return rows


def compass(lat1, lon1, lat2, lon2):
    """Which way from the first point to the second: 'north-east' and so on."""
    r = math.radians
    y = math.sin(r(lon2 - lon1)) * math.cos(r(lat2))
    x = math.cos(r(lat1)) * math.sin(r(lat2)) - math.sin(r(lat1)) * math.cos(r(lat2)) * math.cos(r(lon2 - lon1))
    deg = (math.degrees(math.atan2(y, x)) + 360) % 360
    return ["north", "north-east", "east", "south-east", "south", "south-west", "west",
            "north-west"][int((deg + 22.5) // 45) % 8]


def fire_cell(lat, lon):
    return "%.2f,%.2f" % (lat, lon)


def fire_is_fixture(hist, lat, lon, today):
    """Seen on 4 or more earlier days in the last 30, starting a week or more ago: a flare or the like."""
    days = set()
    for dlat in (-0.01, 0, 0.01):
        for dlon in (-0.01, 0, 0.01):
            days.update(d for d in hist.get(fire_cell(lat + dlat, lon + dlon), []) if d != today)
    week = (dt.date.fromisoformat(today) - dt.timedelta(days=7)).isoformat()
    return len(days) >= 4 and min(days) <= week


def fires_near(home, km, hist, now, ignore=()):
    pts, worked, err = [], 0, None
    for k in ("fires", "fires_modis"):
        if not FEED_URLS.get(k):
            continue
        try:
            pts += parse_firms(http_get(FEED_URLS[k], timeout=30))
            worked += 1
        except Exception as e:
            err = e
    if not worked:
        raise err or ValueError("no fire feed")
    today = now.date().isoformat()
    near = []
    for lat, lon, when in pts:
        d = km_between(home["lat"], home["lon"], lat, lon)
        if d <= FIRE_HISTORY_KM and not any(km_between(lat, lon, i[0], i[1]) <= FIRE_IGNORE_KM for i in ignore):
            near.append((lat, lon, when, d))
    # Add the week's sightings to the history, then see what's a fixture.
    for lat, lon, when, d in near:
        days = hist.setdefault(fire_cell(lat, lon), [])
        if when.date().isoformat() not in days:
            days.append(when.date().isoformat())
    fresh = [p for p in near if p[3] <= km and now - p[2] <= FIRE_FRESH and not fire_is_fixture(hist, p[0], p[1], today)]
    cutoff = (now.date() - dt.timedelta(days=30)).isoformat()
    for cell in list(hist):
        hist[cell] = sorted(d for d in hist[cell] if d >= cutoff)[-30:]
        if not hist[cell]:
            del hist[cell]
    if len(hist) > 2000:
        for cell in sorted(hist, key=lambda c: hist[c][-1])[:len(hist) - 2000]:
            del hist[cell]
    # Hotspots close together are one possible fire.
    groups = []
    for p in sorted(fresh, key=lambda p: p[2]):
        for g in groups:
            if km_between(g[0][0], g[0][1], p[0], p[1]) <= FIRE_CLUSTER_KM:
                g.append(p)
                break
        else:
            groups.append([p])
    out = []
    for g in groups:
        lat = sum(p[0] for p in g) / len(g)
        lon = sum(p[1] for p in g) / len(g)
        d = km_between(home["lat"], home["lon"], lat, lon)
        latest = max(p[2] for p in g)
        local = latest.astimezone()
        first = g[0]   # the earliest sighting: stays the same as more come in, so it's one warning
        out.append({"id": "fire:%s:%s" % (fire_cell(round(first[0] * 50) / 50, round(first[1] * 50) / 50),
                                          first[2].date().isoformat()),
                    "source": "fires", "kind": "fire", "severity": 1, "level": "Possible fire",
                    "title": "Possible fire %d km %s of home" % (max(1, int(round(d))),
                                                                compass(home["lat"], home["lon"], lat, lon)),
                    "text": ("NASA satellites picked up %d hotspot%s here, the latest at %s on %d %s. It could be a "
                             "wildfire, a controlled burn, or a farm or garden fire. Satellites only pass over a few "
                             "times a day, so it may be a few hours old."
                             % (len(g), "" if len(g) == 1 else "s", local.strftime("%H:%M"), local.day,
                                local.strftime("%b"))),
                    "area": "", "distance_km": int(round(d)), "when": "", "lat": round(lat, 4), "lon": round(lon, 4),
                    "url": "https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@%.3f,%.3f,12.0z" % (lon, lat),
                    "issued": iso_utc(latest)})
    out.sort(key=lambda i: i["distance_km"])
    return out


def fetch_source(key, cfg, home, region, mem, now):
    if key == "metoffice":
        return parse_met(http_get(FEED_URLS["metoffice"]), "" if region == "UK" else MET_NAME.get(region, ""))
    if key == "govalerts":
        return parse_govalerts(http_get(FEED_URLS["govalerts"]), now)
    if key == "ukhsa":
        return parse_ukhsa(http_get(FEED_URLS["ukhsa"]), now)
    if key == "who":
        return parse_who(http_get(FEED_URLS["who"]), now)
    if not home:
        raise NeedLocation()
    if key == "gdacs":
        return parse_gdacs(http_get(FEED_URLS["gdacs"]), home, cfg["gdacs_km"])
    if key == "fires":
        return fires_near(home, cfg["fire_km"], mem["fire_cells"], now, mem["fire_ignore"])
    # Floods: look up where each flood area is (once), then keep the ones near you.
    areas = mem["areas"]
    out, looked = [], 0
    for r in parse_floods(http_get(FEED_URLS["floods"])):
        centre = areas.get(r["area_id"])
        if centre is None:
            if looked >= FLOOD_LOOKUPS:
                continue
            looked += 1
            try:
                centre = areas[r["area_id"]] = flood_centre(r["area_id"])
            except Exception:
                continue
        d = km_between(home["lat"], home["lon"], centre[0], centre[1])
        if d <= cfg["flood_km"]:
            r["distance_km"] = int(round(d))
            out.append(r)
    return out


def why_failed(e):
    if isinstance(e, urllib.error.HTTPError):
        return "the site answered %s" % e.code
    if isinstance(e, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError)):
        return "couldn't reach it (is the internet down?)"
    if isinstance(e, (ValueError, ET.ParseError, KeyError, TypeError)):
        return "the feed didn't make sense (%s)" % str(e)[:80]
    return str(e)[:120]


def warnings_run():
    """Check every source that's switched on, keeping the last good result for any that fail."""
    refresh_ha_home()   # also shows where Home Assistant thinks home is, in the settings
    with LOCK:
        cfg = warn_cfg()
        mem = {"areas": setting_raw("flood_areas", {}) or {}, "fire_cells": setting_raw("fire_cells", {}) or {},
               "fire_ignore": fire_ignore_list()}
    if not cfg["on"]:
        return
    home = home_location(cfg)
    region = cfg["region"] or guess_region(home) or "UK"
    now = dt.datetime.now(dt.timezone.utc)
    with WARN_LOCK:
        prev = json.loads(json.dumps(WARN_STATE))
    by_src = {}
    for it in prev["items"] + prev["news"]:
        by_src.setdefault(it["source"], []).append(it)
    statuses, any_ok = {}, False
    for key, _, _ in WARN_SOURCES:
        if not cfg["sources"][key]:
            by_src.pop(key, None)
            continue
        old = prev["sources"].get(key) or {}
        try:
            got = fetch_source(key, cfg, home, region, mem, now)
            by_src[key] = got
            statuses[key] = {"ok": True, "error": "", "checked_at": now_iso(), "count": len(got)}
            any_ok = True
        except NeedLocation:
            by_src[key] = []
            statuses[key] = {"ok": False, "error": "Needs your location: set it in the warnings settings",
                             "checked_at": None, "count": 0}
        except Exception as e:
            statuses[key] = {"ok": False, "error": why_failed(e), "checked_at": old.get("checked_at"),
                             "count": len(by_src.get(key, []))}
    every = [i for k in by_src for i in by_src[k]]
    every.sort(key=lambda i: i.get("issued") or "", reverse=True)
    every.sort(key=lambda i: -i["severity"])
    warnings = [i for i in every if i["kind"] != "news"]
    # A warning is only news once: remember each one for a day after it was last seen, so one that
    # drops out for a check (a feed hiccup, or a fire spot ignored and then un-ignored) doesn't buzz again.
    seen = prev.get("seen") or {}
    if isinstance(seen, list):   # 1.6.0 kept a plain list
        seen = {i: now_iso() for i in seen}
    new = [w for w in warnings if w["id"] not in seen]
    day_ago = (dt.datetime.now() - dt.timedelta(hours=24)).replace(microsecond=0).isoformat(sep=" ")
    seen = {k: v for k, v in seen.items() if v >= day_ago}
    seen.update((w["id"], now_iso()) for w in warnings)
    state = {"items": warnings, "news": [i for i in every if i["kind"] == "news"], "sources": statuses,
             "checked_at": now_iso() if any_ok else prev["checked_at"], "region": region, "seen": seen}
    areas = mem["areas"]
    if len(areas) > 3000:
        areas = dict(list(areas.items())[-2000:])
    with tx() as db:
        set_setting_raw(db, "warnings_cache", state)
        set_setting_raw(db, "flood_areas", areas)
        set_setting_raw(db, "fire_cells", mem["fire_cells"])
    with WARN_LOCK:
        WARN_STATE.clear()
        WARN_STATE.update(state)
    if new and HA_TOKEN:
        try:
            ha_call("POST", "/events/dads_army_warning", warning_event(new))
        except Exception:
            pass
    HA_WAKE.set()


def warning_event(new):
    """Event data for new warnings, for phone alerts."""
    def line(w):
        return "%s (%s)" % (w["title"], WARN_SOURCE_NAMES.get(w["source"], w["source"]))
    if len(new) == 1:
        message = line(new[0]) + "."
    else:
        message = "%d new warnings: %s." % (len(new), "; ".join(line(w) for w in new[:5])
                                          + ("; and %d more" % (len(new) - 5) if len(new) > 5 else ""))
    return {"count": len(new), "max_severity": max(w["severity"] for w in new), "message": message,
            "items": [{k: w.get(k) for k in ("title", "level", "severity", "source", "area", "url")}
                      for w in new[:LIST_LIMIT]]}


def warnings_loop():
    WARN_WAKE.set()   # first check straight away (if they're switched on)
    while True:
        WARN_WAKE.wait(WARN_EVERY)
        WARN_WAKE.clear()
        with WARN_DONE:
            WARN_RUNS["busy"] = True
        try:
            warnings_run()
        except Exception:
            traceback.print_exc()
        with WARN_DONE:
            WARN_RUNS["busy"] = False
            WARN_RUNS["n"] += 1
            WARN_DONE.notify_all()


def load_warnings():
    with LOCK:
        cached = setting_raw("warnings_cache", None)
    if isinstance(cached, dict):
        with WARN_LOCK:
            for k in WARN_STATE:
                if k in cached:
                    WARN_STATE[k] = cached[k]


def warn_public():
    """For the app: the settings, what's in force and how each source is doing."""
    cfg = warn_cfg()
    loc = home_location(cfg)
    with WARN_LOCK:
        st = json.loads(json.dumps(WARN_STATE))
    on = cfg["on"]
    return {"config": cfg, "on": on, "items": st["items"] if on else [], "news": st["news"] if on else [],
            "sources": st["sources"] if on else {}, "checked_at": st["checked_at"] if on else None,
            "location": loc, "region": cfg["region"] or guess_region(loc) or "UK", "region_guessed": not cfg["region"],
            "regions": [[c, n] for c, n, _, _ in MET_REGIONS], "source_list": [[k, n] for k, n, _ in WARN_SOURCES],
            "fire_ignored": len(fire_ignore_list()), "ha": bool(HA_TOKEN)}


def warn_brief():
    """For Home Assistant and /api/summary."""
    w = warn_public()
    keep = ("title", "level", "severity", "source", "area", "when", "url", "issued", "distance_km")
    items = [dict({k: i.get(k) for k in keep if i.get(k) not in (None, "")}, text=(i.get("text") or "")[:300])
             for i in w["items"]]
    top = max([i["severity"] for i in w["items"]] or [0])
    return {"enabled": w["on"], "count": len(items), "items": items,
            "highest": {0: "", 1: "yellow", 2: "amber", 3: "red"}[top], "max_severity": top,
            "serious": sum(1 for i in w["items"] if i["severity"] >= 2),
            "news": [{k: i.get(k) for k in ("title", "source", "url", "issued")} for i in w["news"]],
            "checked_at": w["checked_at"]}


@route("PUT", "/api/warnings")
def api_warnings_set(body, query):
    cur = warn_cfg()
    if "on" in body:
        cur["on"] = bool(body.get("on"))
    if isinstance(body.get("sources"), dict):
        for k in cur["sources"]:
            if k in body["sources"]:
                cur["sources"][k] = bool(body["sources"][k])
    if "region" in body:
        reg = clean_text(body.get("region"), 4)
        if reg and reg != "UK" and reg not in MET_NAME:
            raise ApiError(400, "That isn't a Met Office region")
        cur["region"] = reg
    if "lat" in body or "lon" in body:
        if body.get("lat") in (None, "") and body.get("lon") in (None, ""):
            cur["lat"] = cur["lon"] = None
        else:
            cur["lat"] = clean_num(body.get("lat"), None, -90, 90, "Latitude")
            cur["lon"] = clean_num(body.get("lon"), None, -180, 180, "Longitude")
            if cur["lat"] is None or cur["lon"] is None:
                raise ApiError(400, "Give both a latitude and a longitude, or neither")
            for k, lim, label in (("lat", 90, "Latitude"), ("lon", 180, "Longitude")):
                if not -lim <= float(body.get(k)) <= lim:
                    raise ApiError(400, "%s must be between -%d and %d" % (label, lim, lim))
    for k, lo, hi, label in (("flood_km", 1, 200, "Flood distance"), ("gdacs_km", 50, 5000, "Disaster distance"),
                             ("fire_km", 2, 50, "Fire distance")):
        if k in body:
            cur[k] = int(clean_num(body.get(k), cur[k], lo, hi, label))
    with tx() as db:
        set_setting_raw(db, "warnings", cur)
        add_log("settings", "", "Warnings switched on" if cur["on"] and "on" in body and body.get("on")
                else "Warnings switched off" if "on" in body and not cur["on"] else "Warnings settings updated")
    WARN_WAKE.set()
    with LOCK:
        return {"warnings": warn_public()}


def fire_ignore_list():
    raw = setting_raw("fire_ignore", [])
    return [p for p in raw if isinstance(p, list) and len(p) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p)] if isinstance(raw, list) else []


@route("POST", "/api/warnings/ignore-fire")
def api_fire_ignore(body, query):
    """Not a wildfire (a flare, a bonfire site...): don't show fires at that spot again. Or undo that."""
    with LOCK:
        spots = fire_ignore_list()
    if body.get("clear"):
        spots, what = [], "Ignored fire spots cleared"
    else:
        point = body.get("remove") if body.get("remove") is not None else [body.get("lat"), body.get("lon")]
        if not isinstance(point, list) or len(point) != 2:
            raise ApiError(400, "Which spot?")
        lat = clean_num(point[0], None, -90, 90, "Latitude")
        lon = clean_num(point[1], None, -180, 180, "Longitude")
        if lat is None or lon is None:
            raise ApiError(400, "Which spot?")
        if body.get("remove") is not None:
            spots = [s for s in spots if km_between(s[0], s[1], lat, lon) > 0.05]
            what = "A fire spot is shown again"
        else:
            spots = (spots + [[round(lat, 4), round(lon, 4)]])[-100:]
            what = "A fire spot is ignored"
    with WARN_LOCK:   # take it off straight away, not at the next check
        WARN_STATE["items"] = [i for i in WARN_STATE["items"] if i.get("source") != "fires" or not any(
            km_between(i.get("lat", 0), i.get("lon", 0), s[0], s[1]) <= FIRE_IGNORE_KM for s in spots)]
        cache = json.loads(json.dumps(WARN_STATE))
    with tx() as db:
        set_setting_raw(db, "fire_ignore", spots)
        set_setting_raw(db, "warnings_cache", cache)
        add_log("settings", "", what)
    if body.get("remove") is not None or body.get("clear"):
        WARN_WAKE.set()   # bring it back
    with LOCK:
        return {"warnings": warn_public()}


@route("POST", "/api/warnings/check")
def api_warnings_check(body, query):
    """Check the feeds now, and wait (up to 45 seconds) for the answer."""
    with WARN_DONE:
        want = WARN_RUNS["n"] + (2 if WARN_RUNS["busy"] else 1)
        WARN_WAKE.set()
        WARN_DONE.wait_for(lambda: WARN_RUNS["n"] >= want, timeout=45)
    with LOCK:
        return {"warnings": warn_public()}



# --------------------------------------------------------------------------
# Household alert level: warnings + home sensors + stores -> LOW .. CRITICAL
# --------------------------------------------------------------------------
# The names are the UK's own threat levels (set by MI5's Joint Terrorism Analysis
# Centre), the nearest British thing to America's DEFCON. Dads Army borrows the names
# and their idea, "how likely is it", for one household. It is not the official level.
LEVELS = [
    # name, colour, emoji for Home Assistant's text cards, what it means here, MI5's meaning
    ("LOW", "#2e7d32", "🟩", "Nothing is threatening the household and the stores would last at least 3 days. "
     "Carry on as normal.", "an attack is highly unlikely"),
    ("MODERATE", "#f9a825", "🟨", "Something to keep an eye on: a yellow warning, a minor problem at home, or "
     "stores that wouldn't last 3 days. Stay aware.", "an attack is possible, but not likely"),
    ("SUBSTANTIAL", "#ef6c00", "🟧", "Disruption is likely: an amber warning, a power cut, a leak, or a cold or "
     "hot home. Get ready.", "an attack is likely"),
    ("SEVERE", "#c62828", "🟥", "Disruption is highly likely or under way: a red warning, a flood warning, a long "
     "power cut, or a dangerously cold or hot home. Act now.", "an attack is highly likely"),
    ("CRITICAL", "#212121", "⬛", "Danger to life, now or very soon: an Emergency Alert, a severe flood warning, or "
     "a gas, carbon monoxide or smoke alarm. Follow the emergency services' instructions.",
     "an attack is highly likely in the near future"),
]
LEVEL_ICONS = ["mdi:shield-check", "mdi:shield-alert-outline", "mdi:shield-alert", "mdi:alert-octagon",
               "mdi:alarm-light"]
# Each level's meaning in a few words, for small spaces like the dashboard's alert card.
LEVEL_ACTIONS = ["Carry on as normal", "Stay aware", "Get ready", "Act now",
                 "Danger to life: follow the emergency services' instructions"]

GOV, SAS, FIRE, TIP, NETWORKS = ("UK Government", "SAS Survival Handbook", "Fire & rescue services", "Dads Army tip",
                                 "Electricity networks")


def say(source, body, text):
    return {"source": source, "body": body, "text": text}


# What to do. UK Government advice is paraphrased from the body named; SAS statements apply
# the SAS Survival Handbook's PLAN priorities (Protection, Location, Acquisition, Navigation)
# to a household. Neither is quoted word for word.
GUIDE = {
    "level1": [
        say(GOV, "Prepare", "Keep an emergency kit at home and build it up over time: water, food, a torch, a battery "
                            "or wind-up radio, spare batteries and a first aid kit."),
        say(SAS, "PLAN", "Work through PLAN before you need it: how you'd protect the household, how people would know "
                         "where you are, how you'd get water and food, and where you'd go."),
    ],
    "level2": [
        say(GOV, "Prepare", "Keep up with the forecast and local news, and keep phones and power banks charged."),
        say(SAS, "PLAN: Protection", "Protection comes first: think through what would keep everyone warm, dry and "
                                     "safe if things got worse."),
    ],
    "level3": [
        say(GOV, "Prepare", "Have enough drinking water for at least 3 days: 3 litres per person per day."),
        say(GOV, "Prepare", "Check on neighbours and relatives who may need help, especially older people."),
        say(SAS, "PLAN: Location", "Let people know your situation: tell your out-of-area contact what's happening and "
                                   "where you are."),
        say(SAS, "PLAN: Acquisition", "Get water and food in hand while you still can, and use what spoils first."),
    ],
    "level4": [
        say(GOV, "Emergency services", "Follow official advice and the emergency services. Call 999 if a life is at "
                                       "risk."),
        say(SAS, "PLAN: Protection", "Protect the household first: keep everyone together, warm or cool, and away "
                                     "from danger."),
        say(SAS, "PLAN: Navigation", "Know where you'd go if you have to leave, and how you'd get there: your meeting "
                                     "place and the route."),
    ],
    "level5": [
        say(GOV, "Emergency services", "Do what the emergency services or the Emergency Alert tell you. Call 999 if a "
                                       "life is at risk."),
        say(SAS, "PLAN: Protection", "Protection first: get everyone away from the danger before anything else."),
    ],
    "emergency_alert": [
        say(GOV, "Emergency Alerts", "Read the Emergency Alert and follow its instructions straight away. They're only "
                                     "sent when there's a danger to life nearby."),
    ],
    "severe_flood": [
        say(GOV, "Environment Agency", "A severe flood warning means danger to life. Follow the emergency services' "
                                       "instructions and be ready to leave."),
        say(GOV, "Environment Agency", "If it's safe, turn off the gas, electricity and water, and move people and pets "
                                       "upstairs."),
    ],
    "flood_warning": [
        say(GOV, "Environment Agency", "A flood warning means flooding is expected and you should act now: move "
                                       "valuables, documents and medicines upstairs."),
        say(GOV, "Environment Agency", "Don't walk or drive through flood water: 30cm of flowing water can float a car."),
    ],
    "flood_alert": [
        say(GOV, "Environment Agency", "A flood alert means flooding is possible: be prepared, and check your flood "
                                       "plan and the latest updates."),
    ],
    "met_red": [
        say(GOV, "Met Office", "A red warning means dangerous weather is expected: take action now to keep yourselves "
                               "and others safe."),
    ],
    "met_amber": [
        say(GOV, "Met Office", "An amber warning means be prepared: think about changing plans and protecting "
                               "yourselves and your home."),
    ],
    "met_yellow": [
        say(GOV, "Met Office", "A yellow warning means be aware: some disruption is possible, so keep up with the "
                               "forecast."),
    ],
    "wx_cold": [
        say(GOV, "UKHSA", "Heat the rooms you use to at least 18°C if you can, especially for anyone over 65 or with a "
                          "health condition."),
        say(GOV, "NHS", "Wear several thin layers, have hot food and drinks, and keep moving."),
    ],
    "wx_heat": [
        say(GOV, "NHS", "Stay out of the sun between 11am and 3pm, drink plenty, and keep rooms cool by closing "
                        "curtains on the sunny side."),
        say(GOV, "NHS", "Check on people most at risk: older people, babies, and anyone with a heart or lung "
                        "condition."),
    ],
    "wx_wind": [
        say(GOV, "Prepare", "Bring in or tie down anything that could blow about, and keep torches handy in case the "
                            "power goes."),
        say(NETWORKS, "105", "To report or check a power cut, call 105. It's free from any phone."),
    ],
    "wx_rain": [
        say(GOV, "Environment Agency", "Check the flood warnings for where you live, and keep documents and medicines "
                                       "somewhere high."),
    ],
    "disaster": [
        say(GOV, "Foreign Office", "If you have family or travel plans in the area, check the Foreign Office travel "
                                   "advice."),
    ],
    "fire_near": [
        say(FIRE, "", "If you see a wildfire, move away from it and call 999. Don't try to put it out yourself."),
        say(FIRE, "", "Keep smoke out: close windows and doors."),
    ],
    "gas_alarm": [
        say(GOV, "NHS", "Gas or carbon monoxide: open doors and windows, don't use switches or flames, get everyone "
                        "outside and call the gas emergency line on 0800 111 999."),
        say(GOV, "NHS", "Headaches, dizziness or feeling sick can mean carbon monoxide poisoning: get fresh air and "
                        "call 111, or 999 in an emergency."),
    ],
    "smoke_alarm": [
        say(GOV, "Fire Kills", "If there's a fire: get out, stay out, and call 999. Close doors behind you as you go."),
    ],
    "leak": [
        say(GOV, "Prepare", "Turn the water off at the stopcock, and keep away from any electrics near the water."),
    ],
    "power_cut": [
        say(NETWORKS, "105", "To report or check a power cut, call 105. It's free from any phone."),
        say(TIP, "", "Keep the fridge and freezer shut to keep food cold for longer, and use torches, not candles, "
                     "where you can."),
        say(SAS, "PLAN: Protection", "Keep warm first: gather in one room, keep its doors closed and add layers."),
    ],
    "power_cut_long": [
        say(GOV, "Ofgem", "If anyone relies on powered medical equipment, tell your network on 105, and join the "
                          "Priority Services Register for next time."),
        say(TIP, "", "Eat food from the fridge first, then the freezer, then the stores."),
    ],
    "battery_low": [
        say(TIP, "", "Your backup battery is running low: Home Assistant and Dads Army will stop when it runs out. "
                     "Keep the printed plan and stores list to hand."),
    ],
    "cold_indoor": [
        say(GOV, "UKHSA", "Heat the rooms you use to at least 18°C if you can, especially for anyone over 65 or with a "
                          "health condition."),
        say(GOV, "NHS", "Wear several thin layers, have hot food and drinks, and keep moving."),
        say(SAS, "PLAN: Protection", "Protection from the cold comes first: keep everyone in one warm room."),
    ],
    "hot_indoor": [
        say(GOV, "NHS", "Keep rooms cool: close curtains on the sunny side, and open windows when it's cooler "
                        "outside, such as at night."),
        say(GOV, "NHS", "Drink plenty, and check on people most at risk: older people, babies, and anyone with a heart "
                        "or lung condition."),
    ],
    "damp": [
        say(GOV, "NHS", "Keep damp down: open windows when you can, use extractor fans, and dry washing outside if "
                        "possible."),
    ],
    "poor_air": [
        say(GOV, "DEFRA", "When air pollution is high, people with heart or lung conditions should cut down on "
                          "strenuous activity, especially outdoors."),
        say(FIRE, "", "If the smoke is from a fire nearby, keep windows and doors closed."),
    ],
    "internet_down": [
        say(GOV, "Prepare", "Without the internet, use a battery or wind-up radio for local news and emergency "
                            "information."),
        say(TIP, "", "Warnings can't update without the internet, so the ones shown may be out of date."),
    ],
    "food_low": [
        say(GOV, "Prepare", "Aim for enough food to last at least 3 days, and build it up over time."),
    ],
    "water_low": [
        say(GOV, "Prepare", "Store at least 3 litres of drinking water per person per day, for at least 3 days."),
    ],
    "kit_low": [
        say(GOV, "Prepare", "The basics: a torch, a battery or wind-up radio, spare batteries, a power bank and a first "
                            "aid kit."),
    ],
}
for _k in ("cool_indoor",):
    GUIDE[_k] = GUIDE["cold_indoor"][:2]
GUIDE["freezing_out"] = GUIDE["wx_cold"]
GUIDE["hot_out"] = GUIDE["wx_heat"]

# -- Home sensors (Home Assistant only) ----------------------------------------
# role, what it is, several allowed, domains, device classes, how it's used
SENSOR_ROLES = [
    ("indoor_temp", "Indoor temperature", True, ("sensor",), ("temperature",),
     "The rooms you live in. Dads Army watches the coldest and the warmest."),
    ("outdoor_temp", "Outdoor temperature", False, ("sensor", "weather"), ("temperature",),
     "An outside sensor, or your weather forecast."),
    ("humidity", "Indoor humidity", True, ("sensor",), ("humidity",), "For damp and mould."),
    ("power", "Mains electricity", False, ("binary_sensor", "sensor"), ("power", "plug", "problem", "voltage"),
     "Something that only changes in a power cut, like a UPS status or a mains voltage sensor. Home Assistant needs a "
     "UPS to keep running in a power cut."),
    ("battery", "Backup battery or UPS charge", False, ("sensor",), ("battery",),
     "How much charge your UPS or home battery has left."),
    ("gas_alarm", "Gas or carbon monoxide alarm", True, ("binary_sensor", "sensor"), ("gas", "carbon_monoxide"), ""),
    ("smoke_alarm", "Smoke or heat alarm", True, ("binary_sensor",), ("smoke", "heat"), ""),
    ("leak", "Water leak sensor", True, ("binary_sensor",), ("moisture",), ""),
    ("internet", "Internet connection", False, ("binary_sensor",), ("connectivity",),
     "Without it, warnings can't update."),
    ("air", "Outdoor air quality (PM2.5)", False, ("sensor",), ("pm25",), "Fine particles, in µg/m³."),
]
ROLE = {r[0]: r for r in SENSOR_ROLES}
ENTITY_RE = re.compile(r"^(sensor|binary_sensor|weather)\.[a-z0-9_]+$")
HOME_STATE = {"readings": {}, "at": None, "power_cut_since": None}
HOME_LOCK = threading.Lock()
SENSOR_WAKE = threading.Event()
SENSOR_EVERY = float(os.environ.get("DADSARMY_SENSOR_EVERY", "15"))


def home_cfg():
    raw = setting_raw("home_sensors", {})
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key, _, multi, doms, _, _ in SENSOR_ROLES:
        v = raw.get(key)
        ids = v if isinstance(v, list) else [v] if isinstance(v, str) and v else []
        ids = [i for i in ids if isinstance(i, str) and ENTITY_RE.match(i) and i.split(".")[0] in doms][:10]
        out[key] = ids if multi else (ids[0] if ids else "")
    return out


def read_entity(eid):
    status, st = ha_request("GET", "/states/" + eid, timeout=6)
    if status != 200 or not isinstance(st, dict):
        return {"entity_id": eid, "name": eid, "state": "missing", "value": None, "unit": "", "device_class": "",
                "ok": False}
    a = st.get("attributes") or {}
    state = st.get("state")
    value, unit = state, a.get("unit_of_measurement") or ""
    if eid.startswith("weather."):
        value, unit = a.get("temperature"), a.get("temperature_unit") or "°C"
    return {"entity_id": eid, "name": a.get("friendly_name") or eid, "state": state, "value": value, "unit": unit,
            "device_class": a.get("device_class") or "", "ok": state not in ("unavailable", "unknown", None)}


def number(r):
    """A reading as a number, in °C for temperatures. None if it isn't one."""
    if not r or not r["ok"]:
        return None
    try:
        v = float(r["value"])
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    if r["unit"] in ("°F", "F"):
        v = (v - 32) * 5 / 9
    return v


def power_is_off(r):
    """True in a power cut, False with power, None if it can't tell."""
    if not r or not r["ok"]:
        return None
    s = str(r["state"]).strip().lower()
    if r["entity_id"].startswith("binary_sensor."):
        return s == "on" if r["device_class"] == "problem" else s == "off"
    try:
        v = float(s)
    except ValueError:
        if re.search(r"\b(ob|onbatt|on ?battery|power ?(failure|cut|outage|lost))\b", s):
            return True
        if re.search(r"\b(ol|online|on ?line|mains)\b", s):
            return False
        return None
    if r["device_class"] == "voltage" or r["unit"].lower() == "v":
        return v < 100
    return v <= 0


def alarm_on(r):
    if not r or not r["ok"]:
        return False
    if r["entity_id"].startswith("binary_sensor."):
        return str(r["state"]).lower() == "on"
    v = number(r)   # a carbon monoxide sensor in ppm
    return v is not None and v >= 50


def poll_home_sensors():
    """Read the chosen Home Assistant sensors, and keep track of how long a power cut has lasted."""
    with LOCK:
        cfg = home_cfg()
        since = setting_raw("power_cut_since", None)
    readings = {}
    for key, _, multi, _, _, _ in SENSOR_ROLES:
        ids = cfg[key] if multi else ([cfg[key]] if cfg[key] else [])
        if ids:
            readings[key] = [read_entity(i) for i in ids]
    off = power_is_off(readings["power"][0]) if readings.get("power") else None
    new_since = since
    if off is True and not since:
        new_since = now_iso()
    elif off is False or not readings.get("power"):
        new_since = None
    if new_since != since:
        with tx() as db:
            set_setting_raw(db, "power_cut_since", new_since)
            add_log("settings", "", "Power cut started" if new_since else "Power back on")
    with HOME_LOCK:
        before = json.dumps(HOME_STATE["readings"], sort_keys=True)
        HOME_STATE.update(readings=readings, at=now_iso(), power_cut_since=new_since)
        changed = json.dumps(readings, sort_keys=True) != before
    return changed or new_since != since


def home_sensors_loop():
    while True:
        try:
            if poll_home_sensors():
                HA_WAKE.set()
        except Exception as e:
            if not isinstance(e, (HAError, OSError)):
                traceback.print_exc()
        SENSOR_WAKE.wait(SENSOR_EVERY)
        SENSOR_WAKE.clear()


def home_snapshot():
    with HOME_LOCK:
        return json.loads(json.dumps(HOME_STATE))


def _f(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def weather_kind(title):
    t = (title or "").lower()
    if re.search(r"snow|ice|cold", t):
        return "wx_cold"
    if re.search(r"heat", t):
        return "wx_heat"
    if re.search(r"wind|storm|thunder|lightning", t):
        return "wx_wind"
    if re.search(r"rain|flood", t):
        return "wx_rain"
    return None


def assess(s, home):
    """Where the household stands, LOW (1) to CRITICAL (5), why, and what to do."""
    factors = []

    def add(level, key, title, extra=None):
        factors.append({"level": level, "key": key, "title": title, "extra": extra})

    # Warnings in force (when they're switched on).
    for w in s["warnings"]["items"] if s["warnings"]["enabled"] else []:
        src, sev, title = w.get("source"), w.get("severity") or 0, w.get("title") or ""
        if src == "govalerts":
            if sev >= 3:
                add(5, "emergency_alert", title)
        elif src == "floods":
            lvl, key = {3: (5, "severe_flood"), 2: (4, "flood_warning")}.get(sev, (2, "flood_alert"))
            add(lvl, key, title)
        elif src == "metoffice":
            lvl, key = {3: (4, "met_red"), 2: (3, "met_amber")}.get(sev, (2, "met_yellow"))
            add(lvl, key, title, weather_kind(title))
        elif src == "gdacs":
            add(2, "disaster", title)
        elif src == "fires":
            near = (w.get("distance_km") if w.get("distance_km") is not None else 99) <= 3
            add(3 if near else 2, "fire_near", title)

    # Home sensors.
    r = home.get("readings") or {}
    for role, lvl in (("gas_alarm", 5), ("smoke_alarm", 5), ("leak", 3)):
        for x in r.get(role, []):
            if alarm_on(x):
                add(lvl, role, "%s: %s" % (ROLE[role][1], x["name"]))
    temps = [v for v in (number(x) for x in r.get("indoor_temp", [])) if v is not None]
    if temps:
        lo, hi = min(temps), max(temps)
        for limit, lvl in ((9, 4), (12, 3), (16, 2), (18, 1)):
            if lo < limit:
                add(lvl, "cold_indoor" if lvl > 1 else "cool_indoor", "Coldest room %s°C" % _f(lo))
                break
        for limit, lvl in ((33, 4), (30, 3), (27, 2)):
            if hi >= limit:
                add(lvl, "hot_indoor", "Warmest room %s°C" % _f(hi))
                break
    out = number((r.get("outdoor_temp") or [None])[0])
    if out is not None:
        if out <= -5:
            add(3 if out <= -10 else 2, "freezing_out", "%s°C outside" % _f(out))
        elif out >= 30:
            add(3 if out >= 35 else 2, "hot_out", "%s°C outside" % _f(out))
    hums = [v for v in (number(x) for x in r.get("humidity", [])) if v is not None]
    if hums and max(hums) >= 80:
        add(2, "damp", "Humidity %s%% indoors" % _f(max(hums)))
    off = power_is_off((r.get("power") or [None])[0])
    if off:
        since = home.get("power_cut_since")
        hours = 0.0
        try:
            hours = (dt.datetime.now() - dt.datetime.fromisoformat(since)).total_seconds() / 3600 if since else 0.0
        except ValueError:
            pass
        mins = max(1, int(hours * 60))
        length = ("for %d hours" % int(hours)) if hours >= 2 else ("for %d minute%s" % (mins, "" if mins == 1 else "s"))
        if hours >= 12:
            add(4, "power_cut_long", "Power cut %s" % length)
        else:
            add(3, "power_cut", "Power cut %s" % length)
        batt = number((r.get("battery") or [None])[0])
        if batt is not None and batt < 20:
            add(4, "battery_low", "Backup battery at %d%%" % int(batt))
    net = (r.get("internet") or [None])[0]
    if net and net["ok"] and str(net["state"]).lower() == "off":
        add(2, "internet_down", "Internet down")
    pm = number((r.get("air") or [None])[0])
    if pm is not None:
        for limit, lvl in ((75, 4), (55, 3), (35, 2)):
            if pm >= limit:
                add(lvl, "poor_air", "Air pollution: PM2.5 at %s µg/m³" % _f(pm))
                break

    # The stores.
    weak = False
    if s["people"]:
        if s["food_days"] < 3:
            add(2, "food_low", "Food would last %s day%s" % (_f(s["food_days"]), "" if s["food_days"] == 1 else "s"))
            weak = True
        if s["water_days"] < 3:
            add(2, "water_low", "Water would last %s day%s" % (_f(s["water_days"]), "" if s["water_days"] == 1 else "s"))
            weak = True
    if s.get("kit_items") and s["kit_stocked_pct"] < 50:
        add(2, "kit_low", "Kit %d%% stocked" % s["kit_stocked_pct"])

    level = max([f["level"] for f in factors] + [1])
    escalated = False
    if level == 3 and weak:
        level, escalated = 4, True   # less able to cope. Only real danger makes it CRITICAL.

    # What to do: the most serious things first, then the level's own advice. No repeats.
    guidance, seen = [], set()
    reasons = sorted([f for f in factors if f["level"] >= 2], key=lambda f: -f["level"])
    keys = []
    for f in reasons + [f for f in factors if f["level"] < 2]:
        keys += [f["key"]] + ([f["extra"]] if f["extra"] else [])
    general = "level%d" % level
    # When it's serious, the top reason's advice comes first, then the level's own (999 and
    # the like), so neither is cut off the end of the list.
    order = (keys[:1] + [general] + keys[1:]) if level >= 4 else (keys + [general])
    for key in order:
        for g in GUIDE.get(key, []):
            if g["text"] not in seen:
                seen.add(g["text"])
                guidance.append(dict(g, label=g["source"] + (" · " + g["body"] if g["body"] else "")))
    if not any(g["source"] == SAS for g in guidance[:12]):   # always some of each
        sas = [g for g in guidance if g["source"] == SAS]
        if sas:
            guidance = guidance[:11] + sas[:1]
    name, colour, emoji, meaning, _ = LEVELS[level - 1]
    return {"level": level, "name": name, "colour": colour, "emoji": emoji, "meaning": meaning,
            "escalated": escalated,
            "reasons": [{"level": f["level"], "name": LEVELS[f["level"] - 1][0], "title": f["title"], "key": f["key"]}
                        for f in reasons],
            "notes": [f["title"] for f in factors if f["level"] < 2],
            "guidance": guidance[:12],
            "sensors": bool(r),
            "action": LEVEL_ACTIONS[level - 1],
            "scale": [{"level": i + 1, "name": n, "colour": c, "emoji": e, "meaning": m, "mi5": d,
                       "action": LEVEL_ACTIONS[i]}
                      for i, (n, c, e, m, d) in enumerate(LEVELS)]}


@route("GET", "/api/homeassistant/sensors")
def api_ha_sensors(body, query):
    """Sensors in Home Assistant that could fill each role, with suggestions."""
    need_ha()
    status, data = ha_request("GET", "/states", timeout=20)
    if status != 200 or not isinstance(data, list):
        raise ApiError(502, "Couldn't get the sensors from Home Assistant (it answered %s)" % status)
    cands = {r[0]: [] for r in SENSOR_ROLES}
    for e in data:
        if not isinstance(e, dict):
            continue
        eid = str(e.get("entity_id") or "")
        if not ENTITY_RE.match(eid) or ".dads_army" in eid:
            continue
        a = e.get("attributes") or {}
        dom, dc = eid.split(".")[0], a.get("device_class") or ""
        row = {"entity_id": eid, "name": str(a.get("friendly_name") or eid)[:80],
               "state": str(e.get("state"))[:40], "unit": str(a.get("unit_of_measurement") or "")[:12]}
        if dom == "weather":
            row.update(state=str(a.get("temperature")), unit=a.get("temperature_unit") or "°C")
        for key, _, _, doms, dcs, _ in SENSOR_ROLES:
            if dom not in doms:
                continue
            ups = dom == "sensor" and re.search(r"ups|nut", eid) and re.search(r"status", eid)
            if dc in dcs or (key == "outdoor_temp" and dom == "weather") or (key == "power" and ups):
                if key == "power" and dom == "binary_sensor" and dc not in ("power", "plug", "problem"):
                    continue
                cands[key].append(row)
    for k in cands:
        cands[k] = sorted(cands[k], key=lambda r: r["name"].lower())[:80]
    with LOCK:
        cfg = home_cfg()
    return {"roles": [{"key": k, "label": l, "multiple": m, "hint": h} for k, l, m, _, _, h in SENSOR_ROLES],
            "candidates": cands, "suggested": suggest_sensors(cands), "config": cfg}


OUTSIDE_RE = re.compile(r"outdoor|outside|garden|external|exterior|weather|forecast|balcony|patio", re.I)
GADGET_RE = re.compile(r"cpu|processor|soc|system|board|nvme|disk|ssd|battery|fridge|freezer|boiler|cylinder|"
                       r"water|flow|return|pool|car|phone|printer|router|nas|server|\bpi\b|thermal|chip|esp|"
                       r"inverter|charger|dew|feels", re.I)


def suggest_sensors(c):
    """A sensible first guess for each role. Nothing is used until it's saved."""
    def text(r):
        return r["entity_id"] + " " + r["name"]
    indoor = [r for r in c["indoor_temp"] if not OUTSIDE_RE.search(text(r)) and not GADGET_RE.search(text(r))]
    hum = [r for r in c["humidity"] if not OUTSIDE_RE.search(text(r)) and not GADGET_RE.search(text(r))]
    outdoor = ([r for r in c["outdoor_temp"] if r["entity_id"].startswith("weather.")]
               + [r for r in c["outdoor_temp"] if OUTSIDE_RE.search(text(r)) and not GADGET_RE.search(text(r))])
    power = [r for r in c["power"] if re.search(r"ups|nut|mains|grid|outage|power", text(r), re.I)]
    batt = [r for r in c["battery"] if re.search(r"ups|nut|backup|powerwall|home ?battery|storage", text(r), re.I)]
    net = [r for r in c["internet"] if re.search(r"internet|wan|online|broadband", text(r), re.I)]
    air = [r for r in c["air"] if OUTSIDE_RE.search(text(r))] or c["air"][:1]
    return {"indoor_temp": [r["entity_id"] for r in indoor[:6]],
            "outdoor_temp": outdoor[0]["entity_id"] if outdoor else "",
            "humidity": [r["entity_id"] for r in hum[:6]],
            "power": power[0]["entity_id"] if power else "",
            "battery": batt[0]["entity_id"] if batt else "",
            "gas_alarm": [r["entity_id"] for r in c["gas_alarm"][:10]],
            "smoke_alarm": [r["entity_id"] for r in c["smoke_alarm"][:10]],
            "leak": [r["entity_id"] for r in c["leak"][:10]],
            "internet": net[0]["entity_id"] if net else "",
            "air": air[0]["entity_id"] if air else ""}


@route("PUT", "/api/homeassistant/sensors")
def api_ha_sensors_set(body, query):
    need_ha()
    cfg = {}
    for key, label, multi, doms, _, _ in SENSOR_ROLES:
        v = body.get(key, [] if multi else "")
        ids = v if isinstance(v, list) else [v] if v else []
        if len(ids) > 10:
            raise ApiError(400, "Ten sensors at most for %s" % label.lower())
        for i in ids:
            if not isinstance(i, str) or not ENTITY_RE.match(i) or i.split(".")[0] not in doms:
                raise ApiError(400, "%s can't use %s" % (label, str(i)[:60]))
        cfg[key] = ids if multi else (ids[0] if ids else "")
    with tx() as db:
        set_setting_raw(db, "home_sensors", cfg)
        add_log("settings", "", "Home sensors updated")
    SENSOR_WAKE.set()
    return {"config": cfg}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self'; connect-src 'self'; frame-ancestors 'self'")


class Handler(BaseHTTPRequestHandler):
    server_version = "DadsArmy/" + VERSION

    def do_GET(self):
        self.dispatch("GET")

    def do_HEAD(self):
        self.dispatch("GET", head=True)

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def log_message(self, fmt, *args):
        pass  # keep the journal quiet; errors are printed separately

    # -- helpers ---------------------------------------------------------
    def common_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)

    def send_bytes(self, status, data, content_type, extra=None, head=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.common_headers()
        self.end_headers()
        if not head:
            self.wfile.write(data)

    def send_json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_bytes(status, data, "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "Bad request")
        if length > MAX_BODY:
            raise ApiError(413, "That's too big")
        if length == 0:
            return {}
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "Bad JSON")
        if not isinstance(body, dict):
            raise ApiError(400, "Bad request")
        return body

    # -- routing ---------------------------------------------------------
    def dispatch(self, method, head=False):
        try:
            url = urlparse(self.path)
            path = unquote(url.path)
            if path.startswith("/api/"):
                self.handle_api(method, path, parse_qs(url.query))
            elif method == "GET":
                self.serve_static(path, head)
            else:
                self.send_json(405, {"error": "Method not allowed"})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle_api(self, method, path, query):
        try:
            # Writes must be JSON: stops other websites posting forms to the Pi behind your back.
            if method in ("POST", "PUT", "DELETE"):
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype != "application/json":
                    raise ApiError(415, "Expected JSON")
            path_matched = False
            for m, rx, fn in ROUTES:
                match = rx.match(path)
                if not match:
                    continue
                path_matched = True
                if m != method:
                    continue
                body = self.read_json() if method in ("POST", "PUT") else {}
                result = fn(body, query, *match.groups())
                if method != "GET":
                    HA_WAKE.set()  # something changed: refresh the Home Assistant sensors
                if isinstance(result, Raw):
                    extra = {"Cache-Control": "no-store"}
                    if result.filename:
                        extra["Content-Disposition"] = 'attachment; filename="%s"' % result.filename
                    self.send_bytes(200, result.data, result.content_type, extra)
                else:
                    self.send_json(200, result)
                return
            raise ApiError(405 if path_matched else 404, "Not found" if not path_matched else "Method not allowed")
        except ApiError as e:
            self.send_json(e.status, {"error": e.message})
        except (BrokenPipeError, ConnectionResetError):
            raise
        except Exception:
            traceback.print_exc()
            self.send_json(500, {"error": "Something went wrong on the Pi - check the server log"})

    def serve_static(self, path, head=False):
        if path in ("", "/"):
            path = "/index.html"
        full = os.path.realpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if not full.startswith(STATIC_DIR + os.sep) or not os.path.isfile(full):
            self.send_bytes(404, b"Not found", "text/plain; charset=utf-8", head=head)
            return
        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as f:
            data = f.read()
        self.send_bytes(200, data, MIME.get(ext, "application/octet-stream"),
                        {"Cache-Control": "no-cache"}, head=head)


def local_addresses():
    addrs = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # no packets are sent
        addrs.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return addrs


def main():
    if sys.version_info < (3, 7):
        sys.exit("Dads Army needs Python 3.7 or newer")
    init_db()
    load_warnings()
    threading.Thread(target=backup_loop, name="backups", daemon=True).start()
    threading.Thread(target=warnings_loop, name="warnings", daemon=True).start()
    if HA_TOKEN:
        threading.Thread(target=home_sensors_loop, name="home-sensors", daemon=True).start()
    if HA_TOKEN:
        threading.Thread(target=ha_loop, name="homeassistant", daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.daemon_threads = True
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    print("Dads Army %s - reporting for duty" % VERSION, flush=True)
    print("  Data:  %s" % DB_PATH, flush=True)
    if os.environ.get("DADSARMY_HOMEASSISTANT"):
        # Inside a container the hostname and IPs are internal, so don't print them.
        print("  Open:  Dads Army in the Home Assistant sidebar,", flush=True)
        print("         or http://<home-assistant-address>:%d on your home network" % PORT, flush=True)
    else:
        print("  Local: http://localhost:%d" % PORT, flush=True)
        host = socket.gethostname()
        print("  Phone: http://%s.local:%d" % (host, PORT), flush=True)
        for ip in local_addresses():
            print("         http://%s:%d" % (ip, PORT), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        if HA_TOKEN:
            ha_mark_unavailable()
        with LOCK:
            DB.close()
        print("Dismissed.", flush=True)


if __name__ == "__main__":
    main()
