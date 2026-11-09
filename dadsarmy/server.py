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
    running low, expired, expiring soon and more)
  - fires a dads_army_ran_out event when something runs out, for phone alerts
  - can keep the supply run in step with a Home Assistant to-do list (HQ screen)
GET /api/summary returns the same figures as JSON for anything else.
"""
import csv
import datetime as dt
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

VERSION = "1.4.0"
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
"""

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
    for field, label in (("kcal_per_unit", "Calories"), ("litres_per_unit", "Litres"), ("target_qty", "Target")):
        if not partial or field in body:
            out[field] = clean_num(body.get(field), 0, 0, 1e7, label)
    if not partial or "notes" in body:
        out["notes"] = clean_text(body.get("notes"), 2000)
    return out


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


def summary():
    """What matters at a glance: the same figures the Sitrep screen shows."""
    today = dt.date.today()
    with LOCK:
        st = get_settings()
        items = all_items()
        extras = [r["text"] for r in DB.execute("SELECT text FROM shopping WHERE done = 0 ORDER BY id")]
    warn = st["warn_days"]
    people = st["adults"] + st["children"]
    kcal_day = st["adults"] * st["kcal_adult"] + st["children"] * st["kcal_child"]
    water_day = people * st["water_per_person"]
    kcal = litres = 0.0
    kit_n, kit_sum = 0, 0.0
    low, out, expired, soon, upcoming = [], [], [], [], []

    for it in items:
        unit, cat = it["unit"] or "", it["category"]
        total = sum(b["qty"] for b in it["batches"])
        target = it["target_qty"] or 0
        food = cat == "food" and (it["kcal_per_unit"] or 0) > 0
        water = cat == "water" and (it["litres_per_unit"] or 0) > 0
        dated = []
        for b in it["batches"]:
            d = _days_until(b["expiry"], today) if b["expiry"] else None
            fresh = d is None or d >= 0
            if food and fresh:
                kcal += b["qty"] * it["kcal_per_unit"]
            if water and fresh:
                litres += b["qty"] * it["litres_per_unit"]
            if d is not None and b["qty"] > 0:
                dated.append((d, b))
                if d >= 0:
                    upcoming.append((d, it, b))

        if target > 0 and cat not in ("food", "water"):
            kit_n += 1
            kit_sum += min(1.0, total / target)
        if target > 0 and total < target:
            get = round(target - total, 3)
            entry = {"id": it["id"], "name": it["name"], "category": cat, "have": _num(total), "target": _num(target),
                     "unit": unit, "get": _num(get),
                     "text": "Get %s" % qu(get, unit) + (" · have %s of %s" % (fq(total), fq(target))
                                                          if total > 0 else "")}
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

    target_days = st["target_days"]
    return {
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
        "items_total": len(items),
        "out_of_stock": ordered(out),
        "low_stock": ordered(low),
        "expired": ordered(expired),
        "expiring_soon": ordered(soon),
        # Best-before was yesterday, so it went out of date at midnight / it's the last day.
        "newly_expired": ordered([r for r in expired if r[0] == -1]),
        "expires_today": ordered([r for r in soon if r[0] == 0]),
        "next_expiry": nxt,
        "supply_run": {"below_target": ordered(out) + ordered(low), "extras": extras},
    }


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
    with LOCK:
        return {
            "items": all_items(),
            "shopping": [dict(r) for r in DB.execute("SELECT * FROM shopping ORDER BY done, id")],
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
        cur = db.execute(
            "INSERT INTO items(name, category, unit, kcal_per_unit, litres_per_unit, target_qty, notes,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (data["name"], data["category"], data["unit"], data["kcal_per_unit"], data["litres_per_unit"],
             data["target_qty"], data["notes"], ts, ts))
        item_id = cur.lastrowid
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
        db.execute(
            "INSERT INTO items(id, name, category, unit, kcal_per_unit, litres_per_unit, target_qty, notes,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, data["name"], data["category"], data["unit"], data["kcal_per_unit"],
             data["litres_per_unit"], data["target_qty"], data["notes"], created, now_iso()))
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
            db.execute(
                "INSERT INTO items(name, category, unit, kcal_per_unit, litres_per_unit, target_qty, notes,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, cat, unit, kcal, litres, resolve_target(target, kcal, litres, ctx), notes, ts, ts))
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
                "Target", "Kcal per unit", "Litres per unit", "Notes"])
    for it in sorted(items, key=lambda i: (CATEGORIES.index(i["category"]) if i["category"] in CATEGORIES else 99,
                                           i["name"].lower())):
        rows = it["batches"] or [{"qty": 0, "expiry": "", "location": ""}]
        for b in rows:
            w.writerow([it["category"], it["name"], fq(b["qty"]), it["unit"], b["expiry"] or "", b["location"],
                        fq(it["target_qty"]), fq(it["kcal_per_unit"]), fq(it["litres_per_unit"]), it["notes"]])
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
    make_backup("pre-restore")
    ts = now_iso()
    with tx() as db:
        db.execute("DELETE FROM batches")
        db.execute("DELETE FROM items")
        db.execute("DELETE FROM shopping")
        for data, created, bl in clean_items:
            cur = db.execute(
                "INSERT INTO items(name, category, unit, kcal_per_unit, litres_per_unit, target_qty, notes,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (data["name"], data["category"], data["unit"], data["kcal_per_unit"], data["litres_per_unit"],
                 data["target_qty"], data["notes"], created, ts))
            for q, exp, loc, added in bl:
                db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at) VALUES (?, ?, ?, ?, ?)",
                           (cur.lastrowid, q, exp, loc, added))
        for s in shopping:
            if isinstance(s, dict) and clean_text(s.get("text"), 200):
                db.execute("INSERT INTO shopping(text, done, created_at) VALUES (?, ?, ?)",
                           (clean_text(s.get("text"), 200), 1 if s.get("done") else 0, ts))
        for key, (lo, hi, integer) in SETTING_RULES.items():
            if key in settings:
                v = clean_num(settings.get(key), DEFAULT_SETTINGS[key], lo, hi, key)
                db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                           (key, json.dumps(int(round(v)) if integer else v)))
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
        "mdi:cart", "items", dict(_ha_list(run["below_target"]), extras=run["extras"][:LIST_LIMIT]))
    reasons = []
    if s["expired"]:
        reasons.append("%d expired" % len(s["expired"]))
    if s["out_of_stock"]:
        reasons.append("%d out of stock" % len(s["out_of_stock"]))
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
    return {"todo": entity, "todo_name": TODO_STATUS["name"] or entity, "ok": TODO_STATUS["ok"],
            "error": TODO_STATUS["error"], "synced_at": TODO_STATUS["synced_at"], "ticked": ticked}


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
                  "Settings > Devices & services > Add integration > Local To-do, call it Supply run, "
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
        raise ApiError(502, MAKE_LIST_HELP)
    raise ApiError(502, "Home Assistant made the list, but it hasn't appeared yet. Try again in a minute.")


# -- The background loop -------------------------------------------------------
def ha_loop():
    """Keep Home Assistant's Dads Army sensors and to-do list up to date."""
    probe = "sensor.dads_army_hold_out"
    sent, failing, last_full, levels = {}, False, None, None
    HA_WAKE.set()  # first push straight away
    while True:
        HA_WAKE.wait(15 if failing else 30 if todo_entity() else 60)
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


def ha_mark_unavailable():
    """On shutdown, show the sensors as unavailable rather than leaving old numbers up."""
    for eid, body in list(HA_LAST.items()):
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
    need_ha()
    entity = clean_text(body.get("todo_list"), 120)
    if entity and not TODO_RE.match(entity):
        raise ApiError(400, "That isn't a Home Assistant to-do list")
    todo_link(entity)
    return {"status": ha_status()}


@route("POST", "/api/homeassistant/todo-list")
def api_ha_make_list(body, query):
    need_ha()
    entity = ha_make_list(TODO_LIST_NAME)
    todo_link(entity)
    return {"status": ha_status(), "entity_id": entity}


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
    threading.Thread(target=backup_loop, name="backups", daemon=True).start()
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
