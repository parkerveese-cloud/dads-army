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
import gzip
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
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

VERSION = "1.14.0"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.realpath(os.path.join(APP_DIR, "static"))
DATA_DIR = os.path.abspath(os.environ.get("DADSARMY_DATA", os.path.join(APP_DIR, "data")))
DB_PATH = os.path.join(DATA_DIR, "dadsarmy.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
HOST = os.environ.get("DADSARMY_HOST", "0.0.0.0")
PORT = int(os.environ.get("DADSARMY_PORT", "8080"))
KEEP_BACKUPS = max(1, int(os.environ.get("DADSARMY_KEEP_BACKUPS", "14")))
MAX_BODY = 20 * 1024 * 1024

CATEGORIES = ["food", "water", "drinks", "medical", "power", "cooking", "hygiene",
              "tools", "comms", "shelter", "docs", "pets", "other"]

DEFAULT_SETTINGS = {
    "adults": 2,
    "children": 0,
    "kcal_adult": 2200,
    "kcal_child": 1600,
    "water_per_person": 3,
    "target_days": 30,
    "warn_days": 30,
    # Pets (1.11.0): their water counts towards the household's, and pet food has its own days.
    # Typical drinking water: about 50 ml per kg a day, so roughly a litre for a medium dog, a quarter for a cat.
    "dogs": 0,
    "cats": 0,
    "other_pets": 0,
    "water_per_dog": 1.0,
    "water_per_cat": 0.25,
    "water_per_other_pet": 0.2,
    # Earlier warning for some categories, e.g. {"medical": 90}. Others use warn_days.
    "warn_by_cat": {},
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
    "dogs": (0, 20, True),
    "cats": (0, 20, True),
    "other_pets": (0, 50, True),
    "water_per_dog": (0, 10, False),
    "water_per_cat": (0, 5, False),
    "water_per_other_pet": (0, 5, False),
}
SETTING_LABELS = {"adults": "Adults", "children": "Children", "kcal_adult": "Calories per adult",
                  "kcal_child": "Calories per child", "water_per_person": "Water per person",
                  "target_days": "The readiness target", "warn_days": "The expiry warning", "dogs": "Dogs", "cats": "Cats",
                  "other_pets": "Other pets", "water_per_dog": "Water per dog", "water_per_cat": "Water per cat",
                  "water_per_other_pet": "Water per pet"}
# Settings that change what the starter list's targets should be.
SCALES_TARGETS = ("adults", "children", "kcal_adult", "kcal_child", "water_per_person", "target_days",
                  "dogs", "cats", "other_pets", "water_per_dog", "water_per_cat", "water_per_other_pet")


def clean_warn_by_cat(value):
    if not isinstance(value, dict):
        raise ApiError(400, "Expiry warnings by category should be a list of categories and days")
    out = {}
    for k, v in value.items():
        if k not in CATEGORIES:
            raise ApiError(400, "%s isn't a category" % clean_text(k, 30))
        if v in (None, "", 0):
            continue
        out[k] = int(round(clean_num(v, None, 1, 365, "Days before it expires")))
    return out


def warn_for(cat, st):
    """How many days before its best-before date a thing in this category counts as expiring soon."""
    by = st.get("warn_by_cat") or {}
    return by.get(cat) or st["warn_days"]


def pets_water(st):
    return (st["dogs"] * st["water_per_dog"] + st["cats"] * st["water_per_cat"]
            + st["other_pets"] * st["water_per_other_pet"])


def pets_count(st):
    return st["dogs"] + st["cats"] + st["other_pets"]

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
-- What gets used and when, for "about 2 a week, lasts 6 weeks". Use adds a row; its undo takes it off.
-- No foreign key: an undone delete puts the item back with the same id, and its history with it.
CREATE TABLE IF NOT EXISTS usage (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    ts      TEXT    NOT NULL,
    qty     REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_item ON usage(item_id, ts);
-- One row a day: how ready the household was, for the trend charts.
CREATE TABLE IF NOT EXISTS history (
    day          TEXT PRIMARY KEY,
    readiness    INTEGER NOT NULL DEFAULT 0,
    hold_out     REAL    NOT NULL DEFAULT 0,
    food_days    REAL    NOT NULL DEFAULT 0,
    water_days   REAL    NOT NULL DEFAULT 0,
    resilience   INTEGER NOT NULL DEFAULT 0,
    level        INTEGER NOT NULL DEFAULT 1,
    items        INTEGER NOT NULL DEFAULT 0,
    expired      INTEGER NOT NULL DEFAULT 0,
    below_target INTEGER NOT NULL DEFAULT 0,
    value        REAL    NOT NULL DEFAULT 0
);
"""
# Columns added to items after 1.0, for databases made by older versions.
ITEM_UPGRADES = [("per_day", "REAL NOT NULL DEFAULT 0"), ("price", "REAL NOT NULL DEFAULT 0"),
                 # 1.13.0: what one holds (a 500 g bag, a 6-pack), so part of one can be used; and how long it
                 # keeps once opened (an open tin of beans: 3 days)
                 ("pack_size", "REAL NOT NULL DEFAULT 0"), ("pack_unit", "TEXT NOT NULL DEFAULT ''"),
                 ("open_days", "REAL NOT NULL DEFAULT 0"),
                 # 1.11.0: a change counter, so an undo can't overwrite a newer change made on another phone;
                 # and, for things from the starter list, which one (so targets can follow the household).
                 ("rev", "INTEGER NOT NULL DEFAULT 0"), ("starter", "TEXT NOT NULL DEFAULT ''"),
                 ("auto_target", "INTEGER NOT NULL DEFAULT 0"),
                 # 1.13.0: fields the AI estimated ("kcal_per_unit,open_days"), until you change them
                 ("ai_guessed", "TEXT NOT NULL DEFAULT ''"),
                 # 1.14.0: how it's kept before opening: ambient (cupboard), chilled (fridge) or frozen, '' if not said
                 ("storage", "TEXT NOT NULL DEFAULT ''")]
STORAGE = ("ambient", "chilled", "frozen")
KCAL_CATS = ("food", "drinks")   # what feeds the household: juice and milk count as food, not drinking water
ITEM_FIELDS = ("name", "category", "unit", "kcal_per_unit", "litres_per_unit", "target_qty", "per_day", "price",
               "notes", "pack_size", "pack_unit", "open_days", "storage")
ITEM_DEFAULTS = {"pack_size": 0, "pack_unit": "", "open_days": 0, "storage": ""}
PACK_UNITS = ("g", "kg", "ml", "l", "oz", "lb", "each")   # "each": a multipack, counted in single ones
WATER_CATS = ("water", "drinks")   # what you can drink (juice and milk stand in for drinking water only)


def item_litres(it):
    """Drinkable litres in one unit: "litres per unit" if set, else the pack size (5000 g or ml of water is 5 L)."""
    if it["category"] not in WATER_CATS:
        return 0.0
    if (it["litres_per_unit"] or 0) > 0:
        return float(it["litres_per_unit"])
    keys = it.keys() if hasattr(it, "keys") else ()
    size = float((it["pack_size"] if "pack_size" in keys else 0) or 0)
    unit = ((it["pack_unit"] if "pack_unit" in keys else "") or "").lower()
    solid = it["category"] == "water"   # a 5000 g bottle of water is 5 L; a 250 g "drink" is probably rice
    return size / 1000.0 if unit == "ml" or (solid and unit == "g") else size if unit == "l" or (solid and unit == "kg") else 0.0



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

    # Only added when there are pets in the household (HQ → Household).
    ("Dry dog food (2kg bag)", "pets", "bag", 0, 0, ("dogday", 0.15),
     "About 300 g a day for a medium dog: check the bag for your dog's size."),
    ("Dry cat food (2kg bag)", "pets", "bag", 0, 0, ("catday", 0.03),
     "About 60 g a day for a typical cat."),
    ("Pet medicines & flea treatment", "pets", "pack", 0, 0, ("pets", 1),
     "Any regular medicines, and a copy of the vaccination record."),
    ("Pet carrier or spare lead", "pets", "each", 0, 0, ("pets", 1),
     "In case you have to leave in a hurry. Most rest centres only take pets in a carrier or on a lead."),
]
STARTER_BY_NAME = {s[0]: s for s in STARTER}
PET_SPECS = ("dogday", "catday", "pets")


class ApiError(Exception):
    def __init__(self, status, message, code=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code   # for the app to act on (e.g. "empty_backup": ask before going ahead)


class Raw(object):
    """A non-JSON API response (CSV, file download)."""

    def __init__(self, data, content_type, filename=None):
        self.data = data
        self.content_type = content_type
        self.filename = filename


ROUTES = []


def route(method, pattern):
    rx = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn))
        return fn
    return deco


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
    if "opened_at" not in set(r[1] for r in DB.execute("PRAGMA table_info(batches)")):
        DB.execute("ALTER TABLE batches ADD COLUMN opened_at TEXT")   # 1.13.0: the part-used pack, and when
    DB.execute("CREATE TABLE IF NOT EXISTS barcodes (code TEXT PRIMARY KEY, "
               "item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE, product TEXT NOT NULL DEFAULT '', "
               "added_at TEXT NOT NULL)")   # 1.13.0: barcodes scanned, each pointing at one item
    DB.execute("CREATE TABLE IF NOT EXISTS ai_calls (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, "
               "ai TEXT NOT NULL, model TEXT NOT NULL DEFAULT '', task TEXT NOT NULL DEFAULT '', "
               "tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0, cost_usd REAL, "
               "ok INTEGER NOT NULL DEFAULT 1, note TEXT NOT NULL DEFAULT '')")   # 1.13.0: what the AI cost
    DB.execute("CREATE INDEX IF NOT EXISTS idx_ai_calls_ts ON ai_calls(ts)")
    # 1.13.0: one code per product (a 12-digit UPC-A is kept as its 13-digit EAN, a 0 in front).
    DB.execute("UPDATE OR IGNORE barcodes SET code = '0' || code WHERE length(code) = 12")
    DB.execute("DELETE FROM barcodes WHERE length(code) = 12")
    for key, value in DEFAULT_SETTINGS.items():
        DB.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(value)))
    with tx() as db:
        mark_starter_items(db)


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
# Strict on purpose: plain ASCII digits only (no "١٢", "1_000", "nan", "1e400" or trailing newlines).
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
NUM_RE = re.compile(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
ID_RE = re.compile(r"[0-9]{1,15}")
YEARS = (1900, 2200)   # best-before and done dates outside these are typing mistakes


def clean_text(value, maxlen, default=""):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ApiError(400, "Invalid text value")
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ApiError(400, "Invalid text value")
    # Control characters (other than new lines and tabs) have no business in a name or a note.
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value)).strip()[:maxlen]


def _fmt_lim(x):
    return fq(x) if abs(x) < 1e6 else "{:,}".format(int(x))


def clean_num(value, default=0.0, lo=0.0, hi=1e7, field="Value", ndigits=3):
    """A number in [lo, hi], from a JSON number or a plain decimal string. Anything else is refused."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ApiError(400, "%s must be a number" % field)
    if isinstance(value, str):
        s = value.strip()
        if len(s) > 32 or not NUM_RE.fullmatch(s):
            raise ApiError(400, "%s must be a number" % field)
        value = s
    elif not isinstance(value, (int, float)):
        raise ApiError(400, "%s must be a number" % field)
    try:
        f = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ApiError(400, "%s must be a number" % field)
    if math.isnan(f) or math.isinf(f):
        raise ApiError(400, "%s must be a number" % field)
    f = round(f, ndigits)
    if f < lo or f > hi:
        if lo == 0 and f < 0:
            raise ApiError(400, "%s can't be less than zero" % field)
        raise ApiError(400, "%s must be between %s and %s" % (field, _fmt_lim(lo), _fmt_lim(hi)))
    return f


def clean_date(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ApiError(400, "Dates must look like 2027-03-31")
    value = value.strip()
    if not DATE_RE.fullmatch(value):
        raise ApiError(400, "Dates must look like 2027-03-31")
    try:
        d = dt.date(int(value[:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        raise ApiError(400, "%s isn't a real date" % value)
    if not YEARS[0] <= d.year <= YEARS[1]:
        raise ApiError(400, "Check the year: %s" % value)
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
    if not partial or "pack_size" in body or "pack_unit" in body:
        size = clean_num(body.get("pack_size"), 0, 0, 1e6, "Pack size")
        unit = clean_text(body.get("pack_unit"), 4).lower()
        if size and unit not in PACK_UNITS:
            raise ApiError(400, "Pack size is in g, kg, ml, l, oz, lb or each")
        out["pack_size"], out["pack_unit"] = (size, unit) if size else (0, "")
    if not partial or "open_days" in body:
        out["open_days"] = int(round(clean_num(body.get("open_days"), 0, 0, 365, "Days once opened")))
    if not partial or "storage" in body:
        v = str(body.get("storage") or "").strip().lower()
        out["storage"] = v if v in STORAGE else ""
    return out


def insert_item(db, data, created, updated, item_id=None):
    cols = (("id",) if item_id is not None else ()) + ITEM_FIELDS + ("created_at", "updated_at")
    # new food (the starter list) is cupboard food unless it says otherwise
    defaults = dict(ITEM_DEFAULTS, storage="ambient" if data.get("category") in KCAL_CATS + ("pets",) else "")
    vals = ([item_id] if item_id is not None else []) + [data.get(k, defaults.get(k)) for k in ITEM_FIELDS] + [created, updated]
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
    """A record id: a whole number from 1 up, as a JSON integer or a string of digits. Not 1.5, True or "1e3"."""
    if isinstance(value, bool):
        raise ApiError(400, "Bad id")
    if isinstance(value, int):
        n = value
    elif isinstance(value, str) and ID_RE.fullmatch(value):
        n = int(value)
    else:
        raise ApiError(400, "Bad id")
    if n < 1 or n > 2 ** 53:
        raise ApiError(400, "Bad id")
    return n


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------
def add_log(action, item="", detail=""):
    DB.execute("INSERT INTO log(ts, action, item, detail) VALUES (?, ?, ?, ?)",
               (now_iso(), action, item, detail))
    DB.execute("DELETE FROM log WHERE id <= (SELECT MAX(id) FROM log) - 2000")


def get_settings():
    out = dict(DEFAULT_SETTINGS)
    out["warn_by_cat"] = {}
    for row in DB.execute("SELECT key, value FROM settings"):
        if row["key"] in out:
            try:
                out[row["key"]] = json.loads(row["value"])
            except ValueError:
                pass
    try:
        out["warn_by_cat"] = clean_warn_by_cat(out["warn_by_cat"])
    except ApiError:
        out["warn_by_cat"] = {}
    return out


def setting_raw(key, default=None):
    """A stored value outside the household settings (not in backups)."""
    row = DB.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):   # damaged, or empty (NULL)
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


def open_dated(items):
    """Items with each opened pack's expiry brought forward to its "use within N days once opened" date
    (whichever is sooner), as the app shows it. For working things out; backups keep the printed date."""
    for it in items:
        days = it.get("open_days") or 0
        for b in it["batches"]:
            if days > 0 and b.get("opened_at"):
                try:
                    until = (dt.date.fromisoformat(b["opened_at"][:10]) + dt.timedelta(days=days)).isoformat()
                except ValueError:
                    continue
                if not b["expiry"] or until < b["expiry"]:
                    b["expiry"] = until
        it["batches"].sort(key=lambda b: (b.get("opened_at") is None, b["expiry"] is None, b["expiry"] or "", b["id"]))
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


def lasts_days(lots, per_day, today):
    """How many days stock lasts, eating whatever goes off first, and how much (in days' worth) goes off before
    it can be eaten. lots: [(amount, expiry ISO date or None)], amounts in the same units as per_day.
    Each day's share comes from the batch that goes off soonest; a batch can be eaten up to and including its
    date, and what's left of it then is wasted. (Eating soonest-first wastes the least.)"""
    if per_day <= 0:
        return 0.0, 0.0
    t = wasted = 0.0
    for amount, exp in sorted(lots, key=lambda x: (x[1] is None, x[1] or "")):
        if amount <= 0:
            continue
        days = amount / per_day
        if exp:
            room = (dt.date.fromisoformat(exp[:10]) - today).days + 1 - t   # days left to eat it in
            if room <= 0:
                wasted += days
                continue
            if days > room:
                wasted += days - room
                days = room
        t += days
    return t, wasted


DRINK_CAP = 1.5   # litres a person a day of drinking that juice, milk and other drinks can stand in for


def drink_cap(st):
    """Litres a day that drinks can cover: each person's drinking, not cooking, washing or the pets' water."""
    return (st["adults"] + st["children"]) * min(DRINK_CAP, st["water_per_person"])


def water_lasts(water_lots, drink_lots, per_day, cap, today):
    """How many days the water lasts when drinks can cover up to `cap` litres of each day's `per_day` (the
    drinking), and plain water the rest (cooking, washing, pets), a day at a time, using whatever goes off first.
    Returns (days, plain water that passes its date before it's needed, in days' worth)."""
    if per_day <= 0:
        return 0.0, 0.0
    cap = min(cap, per_day)

    def lots(raw):
        out = []
        for amount, exp in raw:
            if amount > 0:
                out.append([amount, (dt.date.fromisoformat(exp[:10]) - today).days if exp else None])
        return sorted(out, key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0))
    water, drinks = lots(water_lots), lots(drink_lots)
    t, wasted = 0.0, 0.0

    def take(pool, want):
        got = 0.0
        for lot in pool:
            if got >= want:
                break
            n = min(lot[0], want - got)
            lot[0] -= n
            got += n
        return got
    for day in range(3660):
        for pool in (water, drinks):
            for lot in pool:
                if lot[1] is not None and lot[1] < day and lot[0] > 0:
                    if pool is water:
                        wasted += lot[0]
                    lot[0] = 0.0
        w_av = sum(l[0] for l in water)
        d_av = sum(l[0] for l in drinks)
        d_use = min(cap, d_av)
        if w_av >= per_day - d_use - 1e-9:
            take(drinks, d_use)
            take(water, per_day - d_use)
            t += 1
            continue
        # The last, part day: as much of it as the water (and drinks, for the drinking) will cover.
        f = (w_av + d_use) / per_day
        if per_day > cap:
            f = min(f, w_av / (per_day - cap)) if d_av >= cap else f
        t += max(0.0, min(1.0, f))
        break
    return t, wasted / per_day


def summary():
    """What matters at a glance: the same figures the Sitrep screen shows."""
    today = dt.date.today()
    with LOCK:
        st = get_settings()
        items = open_dated(all_items())
        extras = [r["text"] for r in DB.execute("SELECT text FROM shopping WHERE done = 0 ORDER BY id")]
        checks = [dict(r) for r in DB.execute("SELECT * FROM checks")]
        warnings = warn_brief()
        plan = get_plan()
    warn = st["warn_days"]
    people = st["adults"] + st["children"]
    kcal_day = st["adults"] * st["kcal_adult"] + st["children"] * st["kcal_child"]
    pet_water = pets_water(st)
    water_day = people * st["water_per_person"] + pet_water
    kcal = litres = drink_litres = cold_kcal = 0.0
    kcal_lots, litre_lots, drink_lots = [], [], []
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
        food = cat in KCAL_CATS and (it["kcal_per_unit"] or 0) > 0
        cold = it.get("storage") in ("chilled", "frozen")
        lpu = item_litres(it)
        water = lpu > 0
        dated = []
        in_date = 0.0
        for b in it["batches"]:
            d = _days_until(b["expiry"], today) if b["expiry"] else None
            fresh = d is None or d >= 0
            if fresh:
                in_date += b["qty"]
            if food and fresh:
                kcal += b["qty"] * it["kcal_per_unit"]
                if cold:
                    cold_kcal += b["qty"] * it["kcal_per_unit"]
                kcal_lots.append((b["qty"] * it["kcal_per_unit"], b["expiry"]))
            if water and fresh:
                if cat == "water":
                    litres += b["qty"] * lpu
                    litre_lots.append((b["qty"] * lpu, b["expiry"]))
                else:   # juice, milk: can stand in for drinking water, not for cooking or washing
                    drink_litres += b["qty"] * lpu
                    drink_lots.append((b["qty"] * lpu, b["expiry"]))
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
        # Only stock that's in date counts towards the target: out-of-date tins need replacing.
        old = round(total - in_date, 3)
        if target > 0 and cat not in ("food", "water"):
            kit_n += 1
            kit_sum += min(1.0, in_date / target)
        if target > 0 and in_date < target:
            get = round(target - in_date, 3)
            cost += get * price
            text = "Get %s" % qu(get, unit)
            if in_date > 0:
                text += " · have %s of %s" % (fq(in_date), fq(target))
            if old > 0:
                text += " · %s out of date" % fq(old)
            entry = {"id": it["id"], "name": it["name"], "category": cat, "have": _num(in_date),
                     "target": _num(target), "unit": unit, "get": _num(get), "out_of_date": _num(old), "text": text}
            if price > 0:
                entry["cost"] = round(get * price, 2)
            (out if in_date <= 0 else low).append((in_date / target, entry))

        # Like the app, an item's expiry state comes from its soonest-dated batch.
        if dated:
            d0, b0 = min(dated, key=lambda x: (x[0], x[1]["id"]))
            soon_days = warn_for(cat, st)
            if d0 < 0:
                hit, bucket = [b for d, b in dated if d < 0], expired
            elif d0 <= soon_days:
                hit, bucket = [b for d, b in dated if 0 <= d <= soon_days], soon
            else:
                hit, bucket = None, None
            if hit:
                qty = sum(b["qty"] for b in hit)
                bits = [qu(qty, unit), expiry_words(d0)] + ([b0["location"]] if b0["location"] else [])
                bucket.append((d0, {"name": it["name"], "category": cat, "qty": _num(qty), "unit": unit,
                                    "expiry": b0["expiry"], "days": d0, "location": b0["location"] or "",
                                    "text": " · ".join(bits)}))

    # Eaten in date order, a day at a time: food that goes off before you'd get to it doesn't count.
    food_days, food_waste = lasts_days(kcal_lots, kcal_day, today)
    water_days, water_waste = water_lasts(litre_lots, drink_lots, water_day, drink_cap(st), today)
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
    # Pets: their water is in water_days already; their food lasts as long as the pet food with a daily use.
    pet_food = [e for e in sup if e["category"] == "pets"]
    pets = {"count": pets_count(st), "dogs": st["dogs"], "cats": st["cats"], "other": st["other_pets"],
            "water_litres": _num(round(pet_water, 2)),
            "food_days": pet_food[0]["days"] if pet_food else None,
            "food_runs_out_first": pet_food[0]["name"] if pet_food else ""}
    out = {
        "version": VERSION,
        "date": today.isoformat(),
        "people": people,
        "pets": pets,
        "target_days": target_days,
        "warn_days": warn,
        "warn_by_cat": st["warn_by_cat"],
        # Hold-out against the readiness target; 100 means the target is met.
        "readiness_pct": min(100, int(math.floor(100.0 * hold / target_days))) if target_days > 0 else 0,
        "hold_out_days": _days(hold),
        "food_days": _days(food_days),
        "water_days": _days(water_days),
        "water_litres": round(litres, 1),          # plain drinking water in date
        "drink_litres": round(drink_litres, 1),    # juice, milk and other drinks: these can cover the drinking
        "drink_cap_litres": round(drink_cap(st), 2),   # ...up to this much a day (not cooking, washing or pets)
        # Days' worth that goes off before it can be eaten (or drunk), eating the soonest first.
        "food_wasted_days": _days(food_waste),
        # Days' worth of the food that needs a fridge or freezer: only good for the first day or two of a power cut.
        "cold_food_days": _days(cold_kcal / kcal_day) if kcal_day > 0 else 0,
        "water_wasted_days": _days(water_waste),
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
        # Ten areas of resilience, of which food and water are two.
        "resilience": resilience(res_context(items, st, plan, checks, warnings["enabled"], food_days, water_days,
                                             today)),
    }
    out["situation"] = assess(out, home_snapshot())
    with LOCK:
        out["places"] = places_view(out)
    return out


# -- Daily history, for the trend charts ---------------------------------------------
HISTORY_FIELDS = ("readiness", "hold_out", "food_days", "water_days", "resilience", "level", "items", "expired",
                  "below_target", "value")
HISTORY_KEEP_DAYS = 5 * 366
USAGE_KEEP_DAYS = 400
HISTORY_EVERY = float(os.environ.get("DADSARMY_HISTORY_EVERY", "1800"))


def history_row(s):
    return {"readiness": s["readiness_pct"], "hold_out": s["hold_out_days"], "food_days": s["food_days"],
            "water_days": s["water_days"], "resilience": s["resilience"]["pct"], "level": s["situation"]["level"],
            "items": s["items_total"], "expired": len(s["expired"]), "below_target": len(s["supply_run"]["below_target"]),
            "value": s["stores_value"]}


def record_history(s=None):
    """Today's row: written through the day, so it ends up as how things stood at the end of it."""
    s = s or summary()
    row = history_row(s)
    with tx() as db:
        db.execute("INSERT OR REPLACE INTO history(%s) VALUES (%s)" % (
            ", ".join(("day",) + HISTORY_FIELDS), ", ".join("?" * (len(HISTORY_FIELDS) + 1))),
            [s["date"]] + [row[k] for k in HISTORY_FIELDS])
        today = dt.date.fromisoformat(s["date"])
        db.execute("DELETE FROM history WHERE day < ?", ((today - dt.timedelta(days=HISTORY_KEEP_DAYS)).isoformat(),))
        db.execute("DELETE FROM usage WHERE ts < ?", ((today - dt.timedelta(days=USAGE_KEEP_DAYS)).isoformat(),))
    return row


def history_loop():
    time.sleep(5)
    while True:
        try:
            record_history()
        except Exception:
            traceback.print_exc()
        time.sleep(HISTORY_EVERY)


BACKFILL = {"sensor.dads_army_food_days": "food_days", "sensor.dads_army_water_days": "water_days",
            "sensor.dads_army_hold_out": "hold_out", "sensor.dads_army_readiness": "readiness",
            "sensor.dads_army_resilience": "resilience"}


def backfill_history():
    """Daily history started in 1.11.0, but Home Assistant keeps its own record of the Dads Army sensors
    (ten days, unless you've changed it). Once, fill in the days it has, so the trend charts aren't empty
    to begin with. Anything it doesn't know is -1, which the charts leave out."""
    with LOCK:
        if setting_raw("history_backfilled", False):
            return 0
    start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=HISTORY_KEEP_DAYS)).replace(microsecond=0)
    status, data = ha_request("GET", "/history/period/%s?filter_entity_id=%s&minimal_response&no_attributes" % (
        quote(start.isoformat()), ",".join(sorted(BACKFILL))), timeout=60)
    if status != 200 or not isinstance(data, list):
        if 400 <= status < 500:   # no history to be had (the recorder's off): don't keep asking
            with tx() as db:
                set_setting_raw(db, "history_backfilled", True)
        return 0   # Home Assistant busy or restarting: try again next time
    points = {}
    for series in data:
        if not isinstance(series, list) or not series or not isinstance(series[0], dict):
            continue
        key = BACKFILL.get(series[0].get("entity_id"))
        if not key:
            continue
        for pt in series:
            v = _f0(pt.get("state")) if isinstance(pt, dict) else None
            when = parse_when(pt.get("last_changed") or pt.get("last_updated")) if isinstance(pt, dict) else None
            if v is not None and when:
                points.setdefault(key, []).append((when.astimezone().date(), v))
    today = dt.date.today()
    rows = {}
    for key, pts in points.items():
        pts.sort(key=lambda x: x[0])
        day, i, last = pts[0][0], 0, None
        while day < today:   # the value at the end of each day, carried forward over days with no change
            while i < len(pts) and pts[i][0] <= day:
                last = pts[i][1]
                i += 1
            rows.setdefault(day.isoformat(), {})[key] = last
            day += dt.timedelta(days=1)
    n = 0
    with tx() as db:
        have = set(r[0] for r in db.execute("SELECT day FROM history"))
        for day in sorted(rows):
            if day in have:
                continue
            row = dict((k, -1) for k in HISTORY_FIELDS)
            row.update((k, v) for k, v in rows[day].items() if v is not None)
            db.execute("INSERT INTO history(%s) VALUES (%s)" % (
                ", ".join(("day",) + HISTORY_FIELDS), ", ".join("?" * (len(HISTORY_FIELDS) + 1))),
                [day] + [row[k] for k in HISTORY_FIELDS])
            n += 1
        set_setting_raw(db, "history_backfilled", True)
    return n


@route("GET", "/api/history")
def api_history(body, query):
    """Up to five years of daily rows, oldest first: ?days=90 for the last 90."""
    days = (query.get("days") or ["365"])[0]
    days = int(clean_num(days, 365, 1, HISTORY_KEEP_DAYS, "Days"))
    since = (dt.date.today() - dt.timedelta(days=days - 1)).isoformat()
    with LOCK:
        rows = [dict(r) for r in DB.execute("SELECT * FROM history WHERE day >= ? ORDER BY day", (since,))]
    return {"days": days, "rows": rows}


# -- How fast things get used ------------------------------------------------------------
USAGE_WINDOW = 91   # days of using things that count towards "about 2 a week"


def _nice(n):
    """A friendly 'about' number: 0.3 -> 0.5, 1.7 -> 1.5, 2.4 -> 2.5, 13.6 -> 14."""
    if n >= 10:
        return float(_round(n))
    return max(0.5, _round(n * 2) / 2.0)


def rate_words(per_day, unit=""):
    """0.29 a day -> 'about 2 a week' (with the unit, 'about 2 tins a week')."""
    week = per_day * 7
    if week >= 14:
        n, per = per_day, "day"
    elif week >= 1:
        n, per = week, "week"
    else:
        n, per = per_day * 30.44, "month"
        if n < 0.75:
            return "less than one a month" if not unit else "less than %s a month" % qu(1, unit)
    n = _nice(n)
    return "about %s a %s" % (qu(n, unit) if unit else fq(n), per)


def usage_rates(items, today=None):
    """{item id: how fast it goes} from the last three months of using it. It takes two uses or more, and
    a week at least, so one tin opened yesterday doesn't read as a tin a day."""
    today = today or dt.date.today()
    since = (today - dt.timedelta(days=USAGE_WINDOW)).isoformat()
    with LOCK:
        rows = DB.execute("SELECT item_id, MIN(ts) AS first, COUNT(*) AS n, SUM(qty) AS qty FROM usage "
                          "WHERE ts >= ? GROUP BY item_id", (since,)).fetchall()
    by_id = dict((it["id"], it) for it in items)
    out = {}
    for r in rows:
        it = by_id.get(r["item_id"])
        if not it or r["n"] < 2:
            continue
        try:
            first = dt.date.fromisoformat(r["first"][:10])
        except ValueError:
            continue
        span_days = max(7, (today - first).days + 1)
        per_day = r["qty"] / float(span_days)
        have = sum(b["qty"] for b in it["batches"]
                   if not b["expiry"] or (_days_until(b["expiry"], today) or 0) >= 0)
        lasts = have / per_day if per_day > 0 else None
        words = rate_words(per_day, it["unit"] or "")
        if lasts is None:
            tail = ""
        elif have <= 0:
            tail = ", none left"
        else:
            tail = ", lasts " + lasts_words(lasts).lower()
        out[it["id"]] = {"per_day": round(per_day, 4), "uses": r["n"], "since": first.isoformat(),
                         "days": span_days, "lasts_days": _days(lasts) if lasts is not None else None,
                         "text": words + tail}
    return out


def get_item(db, item_id):
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        raise ApiError(404, "That item no longer exists")
    return row


def snapshot(db, item_id):
    item = dict(get_item(db, item_id))
    batches = [dict(b) for b in db.execute(
        "SELECT qty, expiry, location, added_at, opened_at FROM batches WHERE item_id = ? ORDER BY id", (item_id,))]
    return {"item": item, "batches": batches}


def with_barcodes(db, snap):
    """For deleting an item: its barcodes go with it (ON DELETE CASCADE), and come back with an undo."""
    snap["barcodes"] = [[r["code"], r["product"], r["added_at"]] for r in db.execute(
        "SELECT code, product, added_at FROM barcodes WHERE item_id = ?", (snap["item"]["id"],))]
    return snap


def touch(db, item_id):
    db.execute("UPDATE items SET updated_at = ?, rev = rev + 1 WHERE id = ?", (now_iso(), item_id))


def item_rev(db, item_id):
    row = db.execute("SELECT rev FROM items WHERE id = ?", (item_id,)).fetchone()
    return row["rev"] if row else None


def undo_of(db, snap, item_id):
    """An undo for a change just made: the item as it was, and its change count now (None if it's gone)."""
    snap["after"] = item_rev(db, item_id)
    return snap


# --------------------------------------------------------------------------
# API routes
# --------------------------------------------------------------------------
@route("GET", "/api/health")
def api_health(body, query):
    return {"ok": True, "version": VERSION}


@route("GET", "/api/state")
def api_state(body, query):
    sm = summary()
    home = home_snapshot() if HA_TOKEN else None
    with LOCK:
        if home is not None:
            home["config"] = home_cfg()
        items = all_items()
        return {
            "situation": sm["situation"],
            "pets": sm["pets"],
            "usage": dict((str(k), v) for k, v in usage_rates(items).items()),
            "resilience": sm["resilience"],
            "places": sm["places"],
            "place_hazards": [[k, w, e] for k, w, e, _, _ in PLACE_HAZARDS],
            "home": home,
            "items": items,
            "shopping": [dict(r) for r in DB.execute("SELECT * FROM shopping ORDER BY done, id")],
            "checks": all_checks(),
            "check_suggestions": [c[0] for c in CHECK_SUGGESTIONS],
            "plan": get_plan(),
            "warnings": warn_public(),
            "settings": get_settings(),
            "stock_review": setting_raw("stock_review", None),
            "ai_ready": ai_ready(),
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
    if not data["storage"] and data["category"] in KCAL_CATS + ("pets",):
        data["storage"] = "ambient"   # a new item is cupboard food unless the scan, the label or you say otherwise
    qty = clean_num(body.get("qty"), 0, 0, 1e7, "Quantity")
    expiry = clean_date(body.get("expiry"))
    location = clean_text(body.get("location"), 80)
    ts = now_iso()
    with tx() as db:
        item_id = insert_item(db, data, ts, ts)
        if qty > 0:
            db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at) VALUES (?, ?, ?, ?, ?)",
                       (item_id, qty, expiry, location, ts))
        guessed = [g for g in str(body.get("ai_guessed") or "").split(",") if g in ("kcal_per_unit", "open_days", "pack_size", "storage")]
        if guessed:   # read from a photo: values the AI estimated are marked until you change them
            db.execute("UPDATE items SET ai_guessed = ? WHERE id = ?", (",".join(guessed), item_id))
        code = clean_barcode(body.get("barcode"), required=False)
        if code:   # scanned: next time this barcode goes straight to the item
            db.execute("INSERT OR REPLACE INTO barcodes(code, item_id, product, added_at) VALUES (?, ?, ?, ?)",
                       (code, item_id, clean_text(body.get("product"), 160), ts))
        add_log("added", data["name"], ("%s %s" % (fq(qty), data["unit"])).strip() if qty else "New item")
    return {"id": item_id}


@route("PUT", r"/api/items/(\d+)")
def api_item_update(body, query, item_id):
    item_id = as_int_id(item_id)
    data = clean_item(body, partial=True)
    if not data:
        raise ApiError(400, "Nothing to change")
    with tx() as db:
        before = get_item(db, item_id)
        if "target_qty" in data and before["auto_target"] and abs(data["target_qty"] - before["target_qty"]) > 1e-9:
            data["auto_target"] = 0   # you've set your own target: it no longer follows the household
        guessed = [g for g in (before["ai_guessed"] or "").split(",") if g]
        if guessed:   # a value you've changed by hand isn't an estimate any more
            data["ai_guessed"] = ",".join(g for g in guessed if g not in data or before[g] == data[g])
        cols = ", ".join("%s = ?" % k for k in data)
        db.execute("UPDATE items SET %s, updated_at = ?, rev = rev + 1 WHERE id = ?" % cols,
                   list(data.values()) + [now_iso(), item_id])
        add_log("edited", get_item(db, item_id)["name"], "Details updated")
    return {"ok": True}


@route("DELETE", r"/api/items/(\d+)")
def api_item_delete(body, query, item_id):
    item_id = as_int_id(item_id)
    with tx() as db:
        snap = with_barcodes(db, snapshot(db, item_id))
        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        add_log("removed", snap["item"]["name"], "Item deleted")
        undo_of(db, snap, item_id)
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
            snaps.append(with_barcodes(db, snapshot(db, item_id)))
            db.execute("DELETE FROM items WHERE id = ?", (item_id,))
            snaps[-1]["after"] = None
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
            "SELECT id FROM batches WHERE item_id = ? AND IFNULL(expiry, '') = ? AND location = ? COLLATE NOCASE "
            "AND opened_at IS NULL", (item_id, expiry or "", location)).fetchone()   # never into an opened pack
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


def snap_left(left, step=None):
    """What's left, tidied: a count multipack (6 cans) moves in sixths, so 0.998 is 1 and 0.001 is none."""
    if step:
        n = round(left / step)
        if abs(left - n * step) < 0.02:
            left = round(n * step, 3)
    if abs(left - round(left)) < 0.005:
        left = float(round(left))
    return max(0.0, left)


def settle_batch(db, b, left, step=None):
    """A batch after some was used. Part of one left means it's been opened: that part becomes its own batch,
    dated today, so it can go off sooner ("use within 3 days once opened") and is used first."""
    left = snap_left(left, step)
    if left <= 0:
        db.execute("DELETE FROM batches WHERE id = ?", (b["id"],))
        return
    whole = math.floor(left + 1e-6)
    part = round(left - whole, 3)
    today = dt.date.today().isoformat()
    if part < 0.001:
        db.execute("UPDATE batches SET qty = ?, opened_at = NULL WHERE id = ?", (float(whole), b["id"]))
    elif b["opened_at"] or whole == 0:
        db.execute("UPDATE batches SET qty = ?, opened_at = IFNULL(opened_at, ?) WHERE id = ?", (left, today, b["id"]))
    else:
        db.execute("UPDATE batches SET qty = ? WHERE id = ?", (float(whole), b["id"]))
        db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at, opened_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (b["item_id"], part, b["expiry"], b["location"], b["added_at"], today))


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
        pk = db.execute("SELECT pack_size, pack_unit FROM items WHERE id = ?", (item_id,)).fetchone()
        step = 1.0 / pk["pack_size"] if pk and pk["pack_unit"] == "each" and (pk["pack_size"] or 0) >= 2 else None
        rows = db.execute("SELECT id, item_id, qty, expiry, location, added_at, opened_at FROM batches "
                          "WHERE item_id = ? AND qty > 0 ORDER BY opened_at IS NULL, expiry IS NULL, expiry, id",
                          (item_id,)).fetchall()
        if body.get("batch_id") is not None:
            # The one in your hand (picked, or matched from a photo of its date): take from that batch first.
            want = as_int_id(body.get("batch_id"))
            if not any(r["id"] == want for r in rows):
                raise ApiError(404, "That batch isn't in this item any more")
            rows = sorted(rows, key=lambda r: r["id"] != want)
        for b in rows:
            if remaining <= 0:
                break
            take = min(b["qty"], remaining)
            settle_batch(db, b, round(b["qty"] - take, 3), step)
            remaining = snap_left(round(remaining - take, 3), step)
        used = round(qty - remaining, 3)
        if used <= 0:
            raise ApiError(409, "There's none of that left to use")
        touch(db, item_id)
        add_log("used", item["name"], ("-%s %s" % (fq(used), item["unit"])).strip())
        snap["usage"] = db.execute("INSERT INTO usage(item_id, ts, qty) VALUES (?, ?, ?)",
                                   (item_id, now_iso(), used)).lastrowid
        undo_of(db, snap, item_id)
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
        undo_of(db, snap, b["item_id"])
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
        undo_of(db, snap, b["item_id"])
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
        names, skipped = [], []
        for snap in snaps:
            name = restore_snapshot(db, snap)
            (names if name[1] else skipped).append(name[0])
        if not names:
            if len(skipped) == 1:
                raise ApiError(409, "%s has been changed since (on another phone, or by Home Assistant), "
                                    "so it wasn't undone" % skipped[0])
            raise ApiError(409, "Those have been changed since, so they weren't undone")
        if len(names) == 1:
            add_log("undo", names[0], "Change undone")
        else:
            add_log("undo", "%d items" % len(names), "Put back: " + name_list(names))
    return {"ok": True, "restored": len(names), "skipped": skipped}


def restore_snapshot(db, snap):
    """Put an item back as it was: (name, True). If it has been changed since the change being undone
    (another phone used some, or deleted it), leave it alone: (name, False)."""
    item = snap["item"]
    batches = snap["batches"]
    item_id = as_int_id(item.get("id"))
    data = clean_item(item)
    created = clean_text(item.get("created_at"), 30) or now_iso()
    exists = db.execute("SELECT rev FROM items WHERE id = ?", (item_id,)).fetchone()
    if "after" in snap:   # undos from 1.11.0 on say what the item should look like now
        after = snap["after"]
        if after is not None and not isinstance(after, int):
            raise ApiError(400, "Nothing to restore")
        if (after is None) != (exists is None) or (exists is not None and exists["rev"] != after):
            return data["name"], False
    old_rev = item.get("rev") if isinstance(item.get("rev"), int) and not isinstance(item.get("rev"), bool) else 0
    if exists:
        cols = ", ".join("%s = ?" % k for k in data)
        db.execute("UPDATE items SET %s, updated_at = ?, rev = rev + 1 WHERE id = ?" % cols,
                   list(data.values()) + [now_iso(), item_id])
    else:
        insert_item(db, data, created, now_iso(), item_id)
        db.execute("UPDATE items SET rev = ? WHERE id = ?", (max(0, old_rev) + 1, item_id))
    for col in ("starter", "auto_target"):   # not part of clean_item: put them back as they were
        if col in item:
            v = clean_text(item.get(col), 120) if col == "starter" else (1 if item.get(col) else 0)
            db.execute("UPDATE items SET %s = ? WHERE id = ?" % col, (v, item_id))
    if not exists and isinstance(snap.get("barcodes"), list):   # undoing a delete: its barcodes come back
        for c in snap["barcodes"][:200]:
            if isinstance(c, list) and len(c) == 3 and safe_barcode(c[0]):
                db.execute("INSERT OR IGNORE INTO barcodes(code, item_id, product, added_at) VALUES (?, ?, ?, ?)",
                           (safe_barcode(c[0]), item_id, clean_text(c[1], 160), clean_text(c[2], 30) or now_iso()))
    usage = snap.get("usage")
    if isinstance(usage, int) and not isinstance(usage, bool):
        db.execute("DELETE FROM usage WHERE id = ? AND item_id = ?", (usage, item_id))
    db.execute("DELETE FROM batches WHERE item_id = ?", (item_id,))
    for b in batches:
        if not isinstance(b, dict):
            continue
        q = clean_num(b.get("qty"), 0, 0, 1e7)
        if q > 0:
            db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at, opened_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (item_id, q, clean_date(b.get("expiry")), clean_text(b.get("location"), 80),
                        clean_text(b.get("added_at"), 30) or now_iso(), clean_date(b.get("opened_at"))))
    return data["name"], True


# --------------------------------------------------------------------------
# Scanning (1.13.0). Barcodes are read on the phone; a new one is looked up in Open Food Facts (only the
# barcode is sent). Photos of best before dates and labels are read by an AI: Home Assistant's AI Task
# (whatever AI is set up there), or a provider chosen in HQ with its own key. A photo is only kept for as
# long as the question takes.
# --------------------------------------------------------------------------
OFF_URL = ("https://world.openfoodfacts.org/api/v2/product/%s.json?lc=en&fields=product_name,product_name_en,"
           "generic_name_en,abbreviated_product_name_en,lang,brands,quantity,product_quantity,product_quantity_unit,"
           "nutriments,categories_tags")
OFF_CACHE = {}
SCAN_DIR = os.environ.get("DADSARMY_MEDIA", "/media/dadsarmy")   # Home Assistant's media folder (mapped in config.yaml)
AI_PREFER = ("google", "gemini", "anthropic", "claude", "openai", "ollama")
AI_PROVIDERS = {
    "ha": {"name": "Home Assistant AI Task", "model": ""},
    "anthropic": {"name": "Anthropic Claude", "model": "claude-haiku-5-5"},
    "google": {"name": "Google Gemini", "model": "gemini-flash-latest"},
    "openai": {"name": "OpenAI", "model": "gpt-4.1-mini"},
}
# US dollars per million tokens (in, out), for working out what each call cost. Others aren't priced.
AI_PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0),
             "claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-5": (2.0, 10.0),
             # Google's and OpenAI's list prices for the default models, rounded up (check their pricing pages).
             "gemini-flash-latest": (0.30, 2.50), "gpt-4.1-mini": (0.40, 1.60)}
# Any other model is costed at this, on the high side, so the monthly limit still stops it.
AI_PRICE_UNKNOWN = (3.0, 15.0)
AI_NAMES = (("anthropic", "Claude"), ("claude", "Claude"), ("google", "Gemini"), ("gemini", "Gemini"), ("openai", "OpenAI"))


def ai_name(who):
    return next((n for k, n in AI_NAMES if k in str(who).lower()), "The AI")


def friendly_ai_error(who, text):
    """What went wrong, in plain words: busy, allowance used up, no credit, or the key refused."""
    t, name = str(text or ""), ai_name(who)
    low = t.lower()
    code = lambda n: re.search(r"(?<!\d)%s(?!\d)" % n, t)
    if "timed out" in low or "timeout" in low:
        return "%s took too long to answer. Try again." % name
    if code(503) or code(529) or "high demand" in low or "overloaded" in low or "unavailable" in low:
        return "%s is busy right now (on their side, not your allowance). Try again in a minute." % name
    if "insufficient funds" in low or "credit" in low or "billing" in low:
        return "%s's account has no credit left." % name
    if code(429) or "quota" in low or "resource_exhausted" in low or "rate limit" in low:
        return "%s's allowance is used up for now. Try again later, or check your plan." % name
    if code(401) or code(403) or "api key" in low or "api_key" in low or "authentication" in low or "permission" in low:
        return "%s didn't accept the API key." % name
    t = re.sub(r"(sk-|AIza|key[=: ]+)[A-Za-z0-9*_\-]{6,}", r"\1…", t)   # never a key, even a masked one
    return "%s couldn't answer (%s)" % (name, t[:120])


def record_ai(ai, model, task, usage, ok, note=""):
    tin, tout = int(usage.get("in") or 0), int(usage.get("out") or 0)
    # Home Assistant's AI Task is paid for there (no token counts come back); direct calls are costed here.
    price = AI_PRICES.get(model, AI_PRICE_UNKNOWN) if model else None
    cost = round((tin * price[0] + tout * price[1]) / 1e6, 6) if price else None
    try:
        with tx() as db:
            db.execute("INSERT INTO ai_calls(ts, ai, model, task, tokens_in, tokens_out, cost_usd, ok, note) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (now_iso(), ai, model or "", task, tin, tout, cost, 1 if ok else 0,
                                                               str(note)[:200]))
            db.execute("DELETE FROM ai_calls WHERE ts < ?", ((dt.date.today() - dt.timedelta(days=400)).isoformat(),))
    except Exception:
        traceback.print_exc()
    HA_WAKE.set()   # the spend sensor in Home Assistant catches up straight away


def month_spend(today=None):
    today = today or dt.date.today()
    start = today.replace(day=1).isoformat()
    row = DB.execute("SELECT COUNT(*), IFNULL(SUM(cost_usd), 0), SUM(ok) FROM ai_calls WHERE ts >= ?", (start,)).fetchone()
    return {"calls": row[0], "ok": row[2] or 0, "cost_usd": round(row[1], 6), "since": start}


AI_TASKS = (("Dads Army best before", "dates"), ("Dads Army label", "labels"), ("Dads Army nutrition", "labels"),
            ("Dads Army fill in", "filled"), ("Dads Army stores review", "review"))


def ai_stats(today=None):
    """This month, today and last month, and what the AI was used for: for the stats in HQ and Home Assistant."""
    today = today or dt.date.today()
    m = month_spend(today)
    last_start = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1).isoformat()

    def span(a, b):
        r = DB.execute("SELECT COUNT(*), IFNULL(SUM(cost_usd), 0), IFNULL(SUM(ok), 0) FROM ai_calls WHERE ts >= ? AND ts < ?",
                       (a, b)).fetchone()
        return {"calls": r[0], "ok": r[2], "cost_usd": round(r[1], 6)}
    tasks = {"dates": 0, "labels": 0, "filled": 0, "review": 0, "other": 0}
    for r in DB.execute("SELECT task, COUNT(*) FROM ai_calls WHERE ts >= ? AND ok = 1 GROUP BY task", (m["since"],)):
        tasks[next((k for t, k in AI_TASKS if r[0] == t), "other")] += r[1]
    tok = DB.execute("SELECT IFNULL(SUM(tokens_in), 0), IFNULL(SUM(tokens_out), 0) FROM ai_calls WHERE ts >= ?", (m["since"],)).fetchone()
    limit = scan_ai_cfg()["limit_usd"]
    return dict(m, failed=m["calls"] - m["ok"], tokens_in=tok[0], tokens_out=tok[1], tasks=tasks,
                avg_usd=round(m["cost_usd"] / m["ok"], 6) if m["ok"] else None,
                limit_usd=limit, left_usd=round(max(0.0, limit - m["cost_usd"]), 4) if limit else None,
                today=span(today.isoformat(), (today + dt.timedelta(days=1)).isoformat()),
                last_month=span(last_start, m["since"]))


def ai_limit_check(c):
    """Stop before a paid call once this month's limit is reached."""
    limit = float(c.get("limit_usd") or 0)
    if limit > 0 and month_spend()["cost_usd"] >= limit:
        nxt = (dt.date.today().replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        raise ApiError(402, "This month's AI limit ($%.2f) is used up. It starts again on %s, or raise it in HQ → Scanning."
                       % (limit, nxt.strftime("%-d %B")))


DATE_PROMPT = ("Read the best before, best before end or use by date printed on this food or drink packaging. "
               "Reply with only the date as YYYY-MM-DD. If only a month and year are printed, use the last day of "
               "that month. If there's no date you can read, reply NONE.")
LABEL_PROMPT = (
    "This is a photo of a food, drink or household product (the front, back or side of the pack). Read everything "
    "the packaging shows and reply with only a JSON object, in English (translate if the packaging isn't), with "
    'these keys: "name" (short product name with brand if shown, e.g. "Heinz Baked Beans"), "size" (pack size as '
    'printed, e.g. "415 g", or null), "grams" (net weight in grams or volume in millilitres of the WHOLE pack as a '
    'number, so 1980 for 6 x 330 ml, or null), "kcal_100g" (energy in kcal per 100 g or 100 ml as printed, or null), '
    '"kcal_pack" (kcal for the whole pack if printed, or null), "kcal_100g_typical" (only if no energy is printed: a '
    'typical kcal per 100 g for this kind of product, or null for non-food), "count" (how many in a multipack, e.g. 6 '
    'for 6 x 330 ml, or null), "category" (one of food, water (plain drinking water only), drinks (juice, milk, '
    'squash, fizzy drinks), medical, power, cooking, hygiene, tools, comms, shelter, docs, pets, other), "unit" '
    '(what the pack is, as you would count it: tin, can, jar, bottle, carton, box, bag, pouch, tub, packet, tube, '
    'pack, each), "best_before" (best before or use by date as YYYY-MM-DD, last day of the month if only month and '
    'year, or null), "open_days" (the number of days from "once opened, use within N days" if printed, or null), '
    '"open_days_typical" (only if that is not printed: how many days it typically keeps once opened, in the fridge '
    'if it needs it, or null if it keeps for months), "storage" (how it is kept BEFORE opening: "ambient" for the '
    'cupboard (tins, cans, jars, dried, UHT, long-life), "chilled" if it must be kept in the fridge, "frozen" if '
    'frozen; from the storage instructions or what the pack is, or null for non-food). Use null for anything you '
    'can\'t read. No other text.')


def label_prompt(known):
    """The label prompt, with what earlier photos (or Open Food Facts) already found, to build on."""
    keep = {k: known.get(k) for k in ("name", "size", "grams", "kcal_100g", "count", "category", "unit", "best_before",
                                      "open_days", "storage") if known.get(k) not in (None, "", 0)}
    if not keep:
        return LABEL_PROMPT
    return (LABEL_PROMPT + " Already known about this product from another photo or a database: " +
            json.dumps(keep)[:600] + ". Keep these unless this photo clearly shows otherwise, and fill in what this "
            "photo adds; reply with the whole object.")


def clean_barcode(v, required=True):
    v = re.sub(r"\s+", "", str(v or ""))
    if not v and not required:
        return ""
    if not re.fullmatch(r"[0-9]{6,14}", v):
        raise ApiError(400, "That isn't a product barcode")
    # One product, one code: a 12-digit UPC-A is the 13-digit EAN with a 0 in front, and a 14-digit
    # GTIN starting 0 (from a DataBar) is the same 13-digit one.
    if len(v) == 12:
        v = "0" + v
    elif len(v) == 14 and v.startswith("0"):
        v = v[1:]
    return v


def safe_barcode(v):
    try:
        return clean_barcode(v)
    except ApiError:
        return None


def off_product(code):
    """Name (in English), size, calories and a category guess for a barcode: from the offline UK list if it's there,
    otherwise from Open Food Facts online. None if unknown."""
    if code in OFF_CACHE:
        return OFF_CACHE[code]
    local = offline_lookup(code)
    if local:
        out = product_from(code, local)
        out["offline"] = True
        OFF_CACHE[code] = out
        return out
    try:
        d = json.loads(http_get(OFF_URL % code).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            OFF_CACHE[code] = None
            return None
        raise
    p = d.get("product") if d.get("product") else None
    if not p:
        OFF_CACHE[code] = None
        return None
    out = product_from(code, p)
    OFF_CACHE[code] = out
    return out


def multipack_total(text):
    """'6 x 330 ml' -> (6, 1980.0): how many, and the whole pack in grams or millilitres. None if it isn't one."""
    m = re.search(r"(\d{1,3})\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(kg|g|ml|cl|l)\b", str(text or ""), re.I)
    if not m or int(m.group(1)) < 2:
        return None
    each = float(m.group(2).replace(",", ".")) * {"kg": 1000, "g": 1, "ml": 1, "cl": 10, "l": 1000}[m.group(3).lower()]
    return int(m.group(1)), each * int(m.group(1))


DRINK_TAGS = r"beverages|juices|sodas|soft-drinks|milks|smoothies|plant-based-milks"
PACK_WORDS = (("jar", r"\bjars?\b|glass"), ("carton", r"cartons?|tetra|brick"),
              ("tin", r"\btins?\b|canned|tinned|\bcans?\b|metal"), ("bottle", r"bottles?"),
              ("box", r"\bbox(es)?\b|cardboard"), ("bag", r"\bbags?\b|sack"), ("pouch", r"pouch"),
              ("tub", r"\btubs?\b"), ("packet", r"packet|sachet"))


def storage_from(p, name, tags):
    """Cupboard, fridge or freezer, from Open Food Facts' storage instructions and categories (or the name)."""
    how = " ".join([str(p.get("conservation_conditions") or ""), str(p.get("conservation_conditions_en") or "")]).lower()
    text = " ".join([tags, (name or "").lower()])
    if re.search(r"frozen|freez|-18", how) or re.search(r"frozen", text):
        return "frozen"
    if re.search(r"refrigerat|fridge|0-5|below 5|chilled", how) or re.search(r"chilled|refrigerated|fresh-meats|yogurts|"
                                                                           r"fresh-cheeses|fresh-milks", text):
        return "chilled"
    if re.search(r"cool,? dry|ambient|room temperature", how) or re.search(r"canned|tinned|\btins?\b|\bcans?\b|"
                                                                          r"dried|pastas|rices|cereals|uht|long-?life|"
                                                                          r"jams|biscuits|crisps", text):
        return "ambient"
    return ""


def pack_word(p, name, tags):
    """What the pack is, from Open Food Facts' packaging (or the name): jar, carton, tin..."""
    pack = " ".join([str(p.get("packaging") or ""), " ".join(p.get("packaging_tags") or []), name or ""]).lower()
    for word, rx in PACK_WORDS:
        if re.search(rx, pack):
            return word
    if re.search(r"canned|tinned", tags):
        return "tin"
    return ""



def product_from(code, p):
    """An Open Food Facts product (online JSON, or a row of the offline list) shaped for Dads Army."""
    english = (p.get("product_name_en") or p.get("abbreviated_product_name_en") or p.get("generic_name_en") or "").strip()
    name = english or (p.get("product_name") or "").strip()
    if name and not english and str(p.get("lang") or "en") != "en":
        name = translate_name(name) or name   # e.g. a German product: ask the AI for the English
    brand = (p.get("brands") or "").split(",")[0].strip()
    qty_text = (p.get("quantity") or "").strip()
    grams = None
    try:
        if p.get("product_quantity") and str(p.get("product_quantity_unit") or "g").lower() in ("g", "ml"):
            grams = float(p["product_quantity"])
    except (TypeError, ValueError):
        grams = None
    # A multipack ("6 x 330 ml"): calories and size are for the whole pack, as that's what's counted.
    # Open Food Facts sometimes gives one can's weight; the printed quantity says what the pack holds.
    multi = multipack_total(qty_text)
    if multi and (not grams or grams < multi[1] * 0.9):
        grams = multi[1]
    kcal100 = (p.get("nutriments") or {}).get("energy-kcal_100g")
    try:
        kcal = round(float(kcal100) * grams / 100.0) if kcal100 is not None and grams else 0
    except (TypeError, ValueError):
        kcal = 0
    tags = " ".join(p.get("categories_tags") or [])
    mcount = re.match(r"^\s*(\d{1,3})\s*[x×]\s*", qty_text, re.I)
    count = int(mcount.group(1)) if mcount and int(mcount.group(1)) > 1 else 0
    drink = re.search(r"waters|bottled-water|mineral-water", tags)
    juice = not drink and re.search(DRINK_TAGS, tags)
    full = (brand + " " if brand and brand.lower() not in name.lower() else "") + name
    out = {"code": code, "name": (full + (" (%s)" % qty_text if qty_text else "")).strip()[:120] or code,
           "brand": brand, "quantity": qty_text, "grams": grams, "kcal_per_unit": kcal,
           "kcal_100g": kcal100, "category": "water" if drink else "drinks" if juice else "food", "count": count,
           "litres_per_unit": round(grams / 1000.0, 2) if (drink or juice) and grams else 0,
           "unit": "pack" if count else pack_word(p, name, tags) or ("bottle" if drink or juice else "pack"),
           "storage": "" if drink else storage_from(p, name, tags)}
    if drink:
        out["kcal_per_unit"] = 0
    return out


def scan_ai_cfg():
    """{"provider", "model", "keys": {provider: key}}: kept apart from the household settings, so never in backups."""
    raw = setting_raw("scan_ai", {}) or {}
    prov = raw.get("provider") if raw.get("provider") in AI_PROVIDERS else "ha"
    keys = dict((k, v) for k, v in (raw.get("keys") or {}).items() if k in AI_PROVIDERS and isinstance(v, str) and v)
    return {"provider": prov, "model": str(raw.get("model") or ""), "keys": keys, "limit_usd": float(raw.get("limit_usd") or 0)}


def sweep_scan_photos():
    """Photos are deleted once the AI has read them; one left by a restart mid-question goes now."""
    try:
        for n in os.listdir(SCAN_DIR):
            if n.startswith("scan-") and n.endswith(".jpg"):
                os.remove(os.path.join(SCAN_DIR, n))
    except OSError:
        pass


AI_READY = {"at": 0.0, "ok": False}


def ai_ready():
    """Is an AI set up to use: an API key for the chosen provider, or an AI Task in Home Assistant (checked at
    most every 10 minutes, as that asks Home Assistant)."""
    c = scan_ai_cfg()
    if c["provider"] != "ha":
        return bool(c["keys"].get(c["provider"]))
    if time.time() - AI_READY["at"] > 600:
        try:
            AI_READY["ok"] = bool(ai_task_entities())
        except Exception:
            AI_READY["ok"] = False
        AI_READY["at"] = time.time()
    return AI_READY["ok"]


def ai_task_entities():
    """Home Assistant's AI Task entities, the one chosen first, then Gemini, Claude, OpenAI."""
    if not HA_TOKEN:
        return []
    status, out = ha_request("GET", "/states", timeout=15)
    ents = [st["entity_id"] for st in out if isinstance(st, dict) and str(st.get("entity_id", "")).startswith("ai_task.")
            and st.get("state") != "unavailable"] if status == 200 and isinstance(out, list) else []

    def rank(e):
        return next((i for i, w in enumerate(AI_PREFER) if w in e), len(AI_PREFER))
    return sorted(ents, key=rank)


def _post_json(url, body, headers, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers=dict({"Content-Type": "application/json", "User-Agent": FEED_UA}, **headers))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
            msg = (err.get("error") or {}).get("message") if isinstance(err.get("error"), dict) else err.get("error") or err.get("message")
        except Exception:
            msg = ""
        raise IOError("HTTP %d%s" % (e.code, (": " + str(msg)[:120]) if msg else ""))


def ai_direct(provider, key, model, prompt, img_b64=None, usage=None, max_tokens=2048):
    """Ask one provider directly, with an optional JPEG. Returns the model's reply text; tokens go in `usage`."""
    usage = usage if usage is not None else {}
    if provider == "anthropic":
        # Messages API over plain HTTPS (the add-on is standard library only, so no SDK).
        content = ([{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}}]
                   if img_b64 else []) + [{"type": "text", "text": prompt}]
        out = _post_json("https://api.anthropic.com/v1/messages", {
            "model": model or AI_PROVIDERS["anthropic"]["model"], "max_tokens": max_tokens,
            "output_config": {"effort": "low"},
            "messages": [{"role": "user", "content": content}]},
            {"x-api-key": key, "anthropic-version": "2026-10-21"})
        u = out.get("usage") or {}
        usage.update({"in": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0), "out": u.get("output_tokens", 0)})
        if out.get("stop_reason") == "refusal":
            raise IOError("Claude declined to read it")
        return " ".join(b.get("text", "") for b in out.get("content") or [] if b.get("type") == "text")
    if provider == "google":
        parts = ([{"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}] if img_b64 else []) + [{"text": prompt}]
        out = _post_json("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" %
                         urllib.parse.quote(model or AI_PROVIDERS["google"]["model"]), {"contents": [{"parts": parts}]},
                         {"x-goog-api-key": key})
        u = out.get("usageMetadata") or {}
        usage.update({"in": u.get("promptTokenCount", 0), "out": u.get("candidatesTokenCount", 0)})
        return " ".join(p.get("text", "") for c in out.get("candidates") or [] for p in (c.get("content") or {}).get("parts") or [])
    if provider == "openai":
        content = [{"type": "text", "text": prompt}] + ([{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_b64}}]
                                                       if img_b64 else [])
        out = _post_json("https://api.openai.com/v1/chat/completions", {
            "model": model or AI_PROVIDERS["openai"]["model"], "messages": [{"role": "user", "content": content}]},
            {"Authorization": "Bearer " + key})
        u = out.get("usage") or {}
        usage.update({"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0)})
        return ((out.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    raise ValueError("Unknown provider")


def read_date_direct(provider, key, model, img_b64):
    return ai_direct(provider, key, model, DATE_PROMPT, img_b64)


def ai_ask(prompt, img=None, task="Dads Army", max_tokens=2048):
    """Ask whichever AI is chosen in HQ → Scanning. Returns (reply text, which AI)."""
    c = scan_ai_cfg()
    if c["provider"] != "ha":
        key = c["keys"].get(c["provider"])
        if not key:
            raise ApiError(400, "Add your %s API key in HQ → Scanning" % AI_PROVIDERS[c["provider"]]["name"])
        ai_limit_check(c)
        model = c["model"] or AI_PROVIDERS[c["provider"]]["model"]
        for attempt in (1, 2):
            usage = {}
            try:
                reply = ai_direct(c["provider"], key, c["model"], prompt, base64.b64encode(img).decode("ascii") if img else None, usage, max_tokens)
                record_ai(c["provider"], model, task, usage, True)
                return reply, c["provider"]
            except (urllib.error.URLError, IOError, ValueError) as e:
                msg = str(getattr(e, "reason", e))
                record_ai(c["provider"], model, task, usage, False, friendly_ai_error(c["provider"], msg))
                if attempt == 1 and ("503" in msg or "529" in msg or "overloaded" in msg.lower()):
                    time.sleep(2)   # busy: one more go
                    continue
                raise ApiError(502, friendly_ai_error(c["provider"], msg))
    ents = ai_task_entities()
    if not ents:
        raise ApiError(400, "Set up an AI in Home Assistant, or add an API key in HQ → Scanning")
    path = name = None
    if img:
        os.makedirs(SCAN_DIR, exist_ok=True)
        name = "scan-%s.jpg" % uuid.uuid4().hex
        path = os.path.join(SCAN_DIR, name)
        with open(path, "wb") as f:
            f.write(img)
    errors = []
    try:
        for ent in ents[:3]:
            req = {"task_name": task, "entity_id": ent, "instructions": prompt}
            if name:
                req["attachments"] = [{"media_content_id": "media-source://media_source/local/%s/%s" % (os.path.basename(SCAN_DIR), name),
                                       "media_content_type": "image/jpeg"}]
            for attempt in (1, 2):
                status, out = ha_request("POST", "/services/ai_task/generate_data?return_response", req, timeout=60)
                if status == 200 and isinstance(out, dict):
                    record_ai(ent, "", task, {}, True)
                    return str((out.get("service_response") or {}).get("data") or ""), ent
                msg = (out.get("message") if isinstance(out, dict) else str(out or status)) or str(status)
                record_ai(ent, "", task, {}, False, friendly_ai_error(ent, msg))
                if attempt == 1 and ("503" in msg or "high demand" in msg.lower() or "overloaded" in msg.lower()):
                    time.sleep(2)   # busy: one more go before trying the next AI
                    continue
                break
            errors.append(friendly_ai_error(ent, msg))
    finally:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
    raise ApiError(502, " ".join(errors)[:300])


def translate_name(name):
    """A product name in English, via the chosen AI. None if there's no AI or it can't."""
    try:
        reply, _ai = ai_ask("Translate this food or household product name into short, natural UK English. Keep the "
                            "brand name as it is. Reply with only the translated name.\n\n" + name[:200], None,
                            "Dads Army translate")
    except ApiError:
        return None
    t = clean_text(str(reply or "").strip().strip('"').splitlines()[0] if reply else "", 100)
    return t or None


def read_date_reply(text):
    """'2027-03-31' (or that inside other words) to an ISO date; None for NONE or nonsense."""
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", str(text or ""))
    if not m:
        return None
    try:
        d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return d.isoformat() if dt.date(2000, 1, 1) <= d <= dt.date(2100, 1, 1) else None


def parse_label_reply(text):
    """The AI's JSON (possibly wrapped in prose or a code fence) to a product dict, or None.
    Estimated values (no energy or "once opened" printed) are listed in "ai_guessed", as Fill in does."""
    m = re.search(r"\{.*\}", str(text or ""), re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(d, dict) or not str(d.get("name") or "").strip():
        return None

    def number(v, top=100000):
        try:
            f = float(v)
            return f if 0 < f < top else None
        except (TypeError, ValueError):
            return None
    grams, kcal100 = number(d.get("grams")), number(d.get("kcal_100g"), 1000)
    catg = d.get("category") if d.get("category") in CATEGORIES else "food"
    size = clean_text(d.get("size"), 30) if d.get("size") else ""
    multi = multipack_total(size)
    if multi and (not grams or grams < multi[1] * 0.9):
        grams = multi[1]   # the whole pack, not one can
    name = clean_text(d.get("name"), 100)
    unit = clean_text(d.get("unit"), 20).lower() if d.get("unit") else ""
    count = number(d.get("count"), 1000)
    guessed = []
    eats = catg in KCAL_CATS + ("pets",)
    kcal = 0
    if eats and kcal100 and grams:
        kcal = round(kcal100 * grams / 100.0)
    elif eats and number(d.get("kcal_pack")):
        kcal = round(number(d.get("kcal_pack")))
    elif eats and grams and number(d.get("kcal_100g_typical"), 1000):
        kcal100 = number(d.get("kcal_100g_typical"), 1000)
        kcal = round(kcal100 * grams / 100.0)
        guessed.append("kcal_per_unit")
    open_days = number(d.get("open_days"), 366)
    if not open_days and number(d.get("open_days_typical"), 366):
        open_days = number(d.get("open_days_typical"), 366)
        guessed.append("open_days")
    n = int(count) if count and count > 1 and count == int(count) else 0
    drinkable = catg in WATER_CATS and grams
    return {"code": "", "count": n,
            "name": (name + (" (%s)" % size if size and size.lower() not in name.lower() else "")).strip(),
            "brand": "", "quantity": size, "grams": grams, "kcal_100g": kcal100,
            "kcal_per_unit": kcal,
            "litres_per_unit": round(grams / 1000.0, 2) if drinkable else 0,
            "open_days": int(round(open_days)) if open_days else 0,
            "category": catg, "unit": unit if re.fullmatch(r"[a-z]{2,12}", unit) else ("bottle" if catg in WATER_CATS else "pack"),
            "expiry": read_date_reply(d.get("best_before")) if d.get("best_before") else None, "from_ai": True,
            "storage": d.get("storage") if d.get("storage") in STORAGE and eats else "",
            "ai_guessed": ",".join(guessed)}


def photo_from(body):
    raw = str(body.get("image") or "")
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[-1]
    try:
        img = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError):
        raise ApiError(400, "That isn't a photo")
    if not img.startswith(b"\xff\xd8") or len(img) > 3000000:
        raise ApiError(400, "Send a JPEG photo under 3 MB")
    return img


# --------------------------------------------------------------------------
# The offline barcode list: every product Open Food Facts lists as sold in the UK (about 200,000), kept on the
# Pi so scanning works with the internet down. Built from Open Food Facts' public export (about 1.5 GB,
# compressed), read as it downloads, once a month at night and whenever asked. Kept in its own small database
# beside Dads Army's, left out of Home Assistant backups (config.yaml), as it can always be downloaded again.
# Data © Open Food Facts contributors, under the Open Database Licence.
# --------------------------------------------------------------------------
OFFLINE_URL = os.environ.get("DADSARMY_OFF_EXPORT", "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz")
OFFLINE_EVERY_DAYS = 30
OFFLINE_HOURS = (2, 5)   # build between 2 and 5 in the morning, when no one's scanning
OFFLINE = {"building": False, "read_mb": 0, "total_mb": 0, "rows": 0, "kept": 0, "conn": None, "path": None}
OFFLINE_LOCK = threading.Lock()
OFFLINE_COLS = ("code", "product_name", "brands", "quantity", "product_quantity", "energy-kcal_100g",
                "categories_tags", "countries_en")


def offline_cfg():
    try:
        c = (setting_raw("offline_barcodes", {}) or {}) if DB is not None else {}
    except sqlite3.Error:   # no database (yet): off
        c = {}
    return {"enabled": bool(c.get("enabled")), "built_at": c.get("built_at"), "count": int(c.get("count") or 0),
            "error": str(c.get("error") or ""), "tried_at": c.get("tried_at")}


def offline_save(**kw):
    c = setting_raw("offline_barcodes", {}) or {}
    c.update(kw)
    with tx() as db:
        set_setting_raw(db, "offline_barcodes", c)


def offline_db():
    return os.path.join(DATA_DIR, "barcodes_uk.db")


def offline_conn():
    with OFFLINE_LOCK:
        if OFFLINE["conn"] is not None and OFFLINE["path"] != offline_db():
            OFFLINE["conn"].close()
            OFFLINE["conn"] = None
        if OFFLINE["conn"] is None and os.path.exists(offline_db()):
            try:
                OFFLINE["conn"] = sqlite3.connect("file:%s?mode=ro" % offline_db(), uri=True, check_same_thread=False)
                OFFLINE["path"] = offline_db()
            except sqlite3.Error:
                OFFLINE["conn"] = None
        return OFFLINE["conn"]


def offline_lookup(code):
    """The offline list's row for a barcode (as an Open Food Facts product), or None."""
    if not offline_cfg()["enabled"]:
        return None
    conn = offline_conn()
    if conn is None:
        return None
    codes = [code] + ([code.zfill(13)] if len(code) < 13 else []) + ([code.lstrip("0")] if code.startswith("0") else [])
    try:
        with OFFLINE_LOCK:
            row = None
            for c in codes:
                row = conn.execute("SELECT name, brand, quantity, grams, kcal100, cats FROM products WHERE code = ?", (c,)).fetchone()
                if row:
                    break
    except sqlite3.Error:
        return None
    if not row:
        return None
    return {"product_name": row[0], "brands": row[1], "quantity": row[2], "product_quantity": row[3],
            "product_quantity_unit": "g", "nutriments": {"energy-kcal_100g": row[4]},
            "categories_tags": (row[5] or "").split(","), "lang": "en"}


class _Counted(object):
    """A file that counts what's been read from it (for progress)."""
    def __init__(self, f):
        self.f, self.n = f, 0

    def read(self, size=-1):
        b = self.f.read(size)
        self.n += len(b)
        OFFLINE["read_mb"] = round(self.n / 1048576.0)
        return b

    def readable(self):
        return True


def build_offline(url=None):
    """Download the export, keep the UK products, and swap the new list in. Runs on its own thread."""
    with OFFLINE_LOCK:
        if OFFLINE["building"]:
            return False
        OFFLINE.update(building=True, read_mb=0, total_mb=0, rows=0, kept=0)
    tmp = offline_db() + ".new"
    try:
        try:
            os.remove(tmp)
        except OSError:
            pass
        out = sqlite3.connect(tmp)
        out.execute("PRAGMA journal_mode = OFF")
        out.execute("PRAGMA synchronous = OFF")
        out.execute("CREATE TABLE products (code TEXT PRIMARY KEY, name TEXT, brand TEXT, quantity TEXT, grams REAL, "
                    "kcal100 REAL, cats TEXT)")
        req = urllib.request.Request(url or OFFLINE_URL, headers={"User-Agent": FEED_UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            OFFLINE["total_mb"] = round(int(r.headers.get("Content-Length") or 0) / 1048576.0)
            raw = _Counted(r)
            text = io.TextIOWrapper(gzip.GzipFile(fileobj=raw), encoding="utf-8", errors="replace", newline="\n")
            head = text.readline().rstrip("\n").split("\t")
            try:
                ix = dict((c, head.index(c)) for c in OFFLINE_COLS)
            except ValueError as e:
                raise ValueError("Open Food Facts changed its export (%s)" % e)
            width, batch = len(head), []
            ci = ix["countries_en"]
            for line in text:
                OFFLINE["rows"] += 1
                if "United Kingdom" not in line:
                    continue
                f = line.rstrip("\n").split("\t")
                if len(f) != width or "United Kingdom" not in f[ci]:
                    continue
                code = f[ix["code"]].strip()
                name = f[ix["product_name"]].strip()
                if not name or not re.fullmatch(r"[0-9]{6,14}", code):
                    continue

                def num(v):
                    try:
                        x = float(v)
                        return x if 0 < x < 100000 else None
                    except ValueError:
                        return None
                batch.append((code, name[:120], f[ix["brands"]].strip()[:80], f[ix["quantity"]].strip()[:40],
                              num(f[ix["product_quantity"]]), num(f[ix["energy-kcal_100g"]]),
                              f[ix["categories_tags"]][:400]))
                if len(batch) >= 5000:
                    out.executemany("INSERT OR REPLACE INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
                    OFFLINE["kept"] += len(batch)
                    batch = []
                    if not offline_cfg()["enabled"]:
                        raise ValueError("switched off while updating")
            if batch:
                out.executemany("INSERT OR REPLACE INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
                OFFLINE["kept"] += len(batch)
        out.commit()
        count = out.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        out.close()
        if count < 1000:
            raise ValueError("only %d UK products came through, so the old list was kept" % count)
        with OFFLINE_LOCK:
            if OFFLINE["conn"] is not None:
                OFFLINE["conn"].close()
                OFFLINE["conn"] = None
            os.replace(tmp, offline_db())
        OFF_CACHE.clear()
        offline_save(built_at=now_iso(), count=count, error="", tried_at=now_iso())
        add_log("settings", "", "Offline barcode list updated: %d UK products" % count)
        return True
    except Exception as e:
        offline_save(error=str(getattr(e, "reason", e))[:200], tried_at=now_iso())
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
    finally:
        OFFLINE["building"] = False


def offline_due(c, now=None):
    now = now or dt.datetime.now()
    if not c["enabled"] or OFFLINE["building"]:
        return False
    if c["tried_at"] and (now - dt.datetime.fromisoformat(c["tried_at"][:19])).total_seconds() < 20 * 3600:
        return False   # tried in the last day (and maybe failed): not again yet
    if not c["built_at"]:
        return True
    old = (now - dt.datetime.fromisoformat(c["built_at"][:19])).days >= OFFLINE_EVERY_DAYS
    return old and OFFLINE_HOURS[0] <= now.hour < OFFLINE_HOURS[1]


def offline_loop():
    while True:
        try:
            if offline_due(offline_cfg()):
                build_offline()
        except Exception:
            traceback.print_exc()
        time.sleep(600)


def offline_status():
    c = offline_cfg()
    size = os.path.getsize(offline_db()) if os.path.exists(offline_db()) else 0
    return dict(c, building=OFFLINE["building"], read_mb=OFFLINE["read_mb"], total_mb=OFFLINE["total_mb"],
                kept=OFFLINE["kept"], size_mb=round(size / 1048576.0, 1))


@route("GET", "/api/scan/offline")
def api_scan_offline(body, query):
    return offline_status()


@route("PUT", "/api/scan/offline")
def api_scan_offline_set(body, query):
    if body.get("enabled") not in (True, False):
        raise ApiError(400, "Say on or off")
    offline_save(enabled=bool(body["enabled"]), tried_at=None if body["enabled"] else offline_cfg()["tried_at"])
    if body["enabled"] and not offline_cfg()["built_at"]:
        threading.Thread(target=build_offline, name="offline-barcodes", daemon=True).start()   # the first one now
    add_log("settings", "", "Offline barcode list %s" % ("on" if body["enabled"] else "off"))
    return offline_status()


@route("POST", "/api/scan/offline/update")
def api_scan_offline_update(body, query):
    if not offline_cfg()["enabled"]:
        raise ApiError(400, "Switch the offline list on first")
    if not OFFLINE["building"]:
        threading.Thread(target=build_offline, name="offline-barcodes", daemon=True).start()
    return dict(offline_status(), building=True)


@route("GET", "/api/scan/barcode")
def api_scan_barcode(body, query):
    code = clean_barcode((query.get("code") or [""])[0])
    with LOCK:
        row = DB.execute("SELECT item_id, product FROM barcodes WHERE code = ?", (code,)).fetchone()
    if row:
        print("Scan: %s is one of yours" % code, flush=True)
        return {"code": code, "item_id": row["item_id"], "product": {"name": row["product"]} if row["product"] else None}
    try:
        product = off_product(code)
    except (urllib.error.URLError, IOError, ValueError) as e:
        print("Scan: %s couldn't be looked up (%s)" % (code, str(getattr(e, "reason", e))[:80]), flush=True)
        return {"code": code, "item_id": None, "product": None, "lookup_error": str(getattr(e, "reason", e))[:120]}
    print("Scan: %s %s" % (code, ("found: " + product["name"][:60]) if product else "not in Open Food Facts"), flush=True)
    return {"code": code, "item_id": None, "product": product}


SCAN_NOTES = {"live-refused": "the live camera wasn't allowed", "live-none": "no camera found",
              "live-other": "the live camera isn't available", "photo-nobarcode": "no barcode found in a photo",
              "photo-failed": "a photo couldn't be opened", "not-product": "read a code that isn't a product barcode"}


@route("POST", "/api/scan/note")
def api_scan_note(body, query):
    """The phone says how a scan went, so the add-on log shows why one didn't work. Nothing else is kept."""
    what = str(body.get("what") or "")
    if what in SCAN_NOTES:
        detail = clean_text(body.get("detail"), 60)
        print("Scan: %s%s" % (SCAN_NOTES[what], " (%s)" % detail if detail else ""), flush=True)
    return {"ok": True}


@route("POST", "/api/scan/link")
def api_scan_link(body, query):
    """This barcode is this item from now on (another brand of baked beans goes on the same line)."""
    code = clean_barcode(body.get("code"))
    item_id = as_int_id(body.get("item_id"))
    with tx() as db:
        if not db.execute("SELECT 1 FROM items WHERE id = ?", (item_id,)).fetchone():
            raise ApiError(404, "That item doesn't exist")
        db.execute("INSERT OR REPLACE INTO barcodes(code, item_id, product, added_at) VALUES (?, ?, ?, ?)",
                   (code, item_id, clean_text(body.get("product"), 160), now_iso()))
    return {"ok": True}


@route("POST", "/api/scan/date")
def api_scan_date(body, query):
    """Read the best before date from a photo."""
    reply, ai = ai_ask(DATE_PROMPT, photo_from(body), "Dads Army best before")
    return {"date": read_date_reply(reply), "reply": str(reply or "")[:40], "ai": ai}


# --------------------------------------------------------------------------
# Filling in what's missing (1.13.0): calories for a whole pack, what one holds, and how long it keeps once
# opened, estimated by the AI from the name, for you to check. Nothing is saved until you say so, and what
# was estimated is marked until you change it.
# --------------------------------------------------------------------------
FILL_MAX = 40
NO_KCAL_RE = re.compile(r"\b(tea|coffee|salt|stock|spice|herb|pepper|water|vinegar|yeast|baking)\b", re.I)


def fill_wanted(it):
    """The fields worth estimating for an item: [] if it has what it needs."""
    cat = it["category"]
    if cat not in KCAL_CATS + ("pets",):
        return []
    want = []
    if not (it["kcal_per_unit"] or 0) > 0 and not NO_KCAL_RE.search(it["name"]):
        want.append("kcal_per_unit")
    if not (it["pack_size"] or 0) > 0:
        want.append("pack_size")
    if not (it["open_days"] or 0) > 0 and cat in KCAL_CATS:
        want.append("open_days")
    if not it.get("storage"):
        want.append("storage")
    return want


FILL_PROMPT = (
    "These are items in a UK household's emergency food stores. For each one, estimate what's missing, from the "
    "name and unit, using typical UK supermarket products. Reply with only a JSON array, one object per item, with "
    '"id" and only the keys asked for: "kcal_per_unit" (energy in kcal for ONE WHOLE unit as counted, e.g. a whole '
    "400 g tin of baked beans is about 320, a 1 kg bag of rice about 3600, a pack of 6 cans is all six), "
    '"pack_size" and "pack_unit" (what one unit holds: pack_unit one of g, kg, ml, l, each; "each" with a count for '
    'a multipack), "open_days" (days it keeps once opened, stored as the label says: an open tin about 3, an open '
    "jar of jam about 30, dry pasta about 365), \"storage\" (how it is kept before opening: \"ambient\" for the cupboard: "
    "tins, cans, jars, dried, UHT; \"chilled\" if it needs the fridge; \"frozen\"; a tinned curry is ambient, a "
    "supermarket chilled curry is chilled; if the name doesn't say, assume the way it's usually kept for long "
    "storage). Use null if you can't tell. No other text.\n\n")


def parse_fill_reply(text, asked):
    """The AI's JSON array to {id: {field: value}}, keeping only fields asked for, with sane values."""
    m = re.search(r"\[.*\]", str(text or ""), re.S)
    try:
        rows = json.loads(m.group(0)) if m else []
    except ValueError:
        rows = []
    out = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        try:
            iid = int(r.get("id"))
        except (TypeError, ValueError):
            continue
        if iid not in asked:
            continue
        got = {}
        for f, lo, hi in (("kcal_per_unit", 1, 100000), ("pack_size", 0.01, 100000), ("open_days", 1, 3650)):
            if f not in asked[iid]:
                continue
            try:
                v = float(r.get(f))
            except (TypeError, ValueError):
                continue
            if lo <= v <= hi:
                got[f] = round(v) if f != "pack_size" else round(v, 2)
        if "storage" in asked[iid] and r.get("storage") in STORAGE:
            got["storage"] = r.get("storage")
        if "pack_size" in got:
            u = str(r.get("pack_unit") or "").lower()
            if u in PACK_UNITS:
                got["pack_unit"] = u
            else:
                got.pop("pack_size")
        if got:
            out[iid] = got
    return out


@route("POST", "/api/ai/fill")
def api_ai_fill(body, query):
    """Estimates for what's missing, for you to check. Nothing is saved here."""
    with LOCK:
        items = [dict(r) for r in DB.execute("SELECT id, name, category, unit, kcal_per_unit, pack_size, pack_unit, "
                                             "open_days, storage FROM items ORDER BY name COLLATE NOCASE")]
    only = body.get("ids")
    if isinstance(only, list):
        keep = set(as_int_id(i) for i in only[:FILL_MAX])
        items = [it for it in items if it["id"] in keep]
    asked = {}
    lines = []
    for it in items:
        want = fill_wanted(it)
        if want and len(asked) < FILL_MAX:
            asked[it["id"]] = want
            lines.append(json.dumps({"id": it["id"], "name": it["name"], "unit": it["unit"] or "", "category": it["category"],
                                     "asked": [w for w in want], "known": {k: it[k] for k in ("pack_size", "pack_unit")
                                                                          if it[k] and "pack_size" not in want}}))
    if not asked:
        return {"suggestions": [], "left": 0}
    reply, _ai = ai_ask(FILL_PROMPT + "\n".join(lines), None, "Dads Army fill in")
    got = parse_fill_reply(reply, asked)
    names = dict((it["id"], it) for it in items)
    left = sum(1 for it in items if fill_wanted(it)) - len(asked)
    return {"suggestions": [{"id": i, "name": names[i]["name"], "unit": names[i]["unit"], "fields": f}
                            for i, f in got.items()], "left": max(0, left)}


# --------------------------------------------------------------------------
# Reviewing the stores (1.14.0): would the food feed the household with no water, power, gas or fridge, as a
# balanced diet, and what's missing?
# Only names, amounts and the household's make-up are sent. Asked for, never automatic.
# --------------------------------------------------------------------------
REVIEW_PROMPT = (
    "You're helping a UK household check their emergency food stores. The aim: the stores must feed this family "
    "for the target time with NO mains water, NO power, NO gas and NO fridge or freezer. The only water is what's "
    "stored, and the only way to heat anything is what's in the stores (a camping stove and its fuel, say). "
    "Judge the FOOD against that, in this order: (1) can it be eaten as it is, cold, or with a little heat from "
    "what's stored, without much water (dried pasta, rice and noodles need both water and fuel to cook; anything "
    "frozen or chilled is no use); (2) once opened, will it keep without a fridge, or is a pack too big to finish "
    "at one meal for this family (a large tin or jar that has to be refrigerated after opening); (3) is it a "
    "reasonably balanced diet for these people for that long: protein, carbohydrate, fruit and vegetables, fats, "
    "fibre, salt and sugar, and enough variety that people keep eating, including anything the children or pets "
    "need; (4) does enough of it keep (dates). Only then, briefly, the wider stores (water, light, heat for "
    "cooking, can opener, first aid, hygiene). Be practical and kind, British English, no lecturing, no brand "
    "names. Each food has \"kept\": how it's stored before opening, as the household recorded it. Trust it: cupboard "
    "(ambient) food needs no fridge until opened, so don't say a tinned or canned item needs chilling. Where it's "
    "\"not recorded\", judge from the name and unit (a tin or can is ambient). Fridge and freezer food only lasts a "
    "day or two with no power, so count it as the first meals, not as stores. Reply with only a JSON object: "
    "\"summary\" (one paragraph, 80 to 140 words, about the food only: "
    "how well it would feed the family with no water, power, gas or fridge, and the biggest gaps), \"score\" "
    "(1 to 5 for the food: 1 would not do, 5 would feed them well), \"wider\" (one or two sentences on the wider "
    "stores, or null if nothing stands out), and \"suggestions\" (up to 6 objects, food first and most useful "
    "first, at most 2 that aren't food, at the end, \"why\" under 20 words; each {\"add\": short thing to buy, e.g. \"Tinned fruit in "
    "small tins\", \"why\": one short sentence, \"category\": one of food, water, drinks, medical, power, "
    "cooking, hygiene, tools, comms, shelter, docs, pets, other}). No other text.\n\n")


def review_input():
    st = get_settings()
    s_ = summary()
    lines = []
    for it in all_items():
        have = sum(b["qty"] for b in it["batches"] if not b["expiry"] or b["expiry"] >= dt.date.today().isoformat())
        if have <= 0:
            continue
        bits = {"name": it["name"], "category": it["category"], "have": round(have, 2), "unit": it["unit"] or ""}
        if it["kcal_per_unit"]:
            bits["kcal_total"] = round(have * it["kcal_per_unit"])
        if it.get("pack_size"):
            bits["each_holds"] = "%s %s" % (fq(it["pack_size"]), it.get("pack_unit") or "")
        if it.get("open_days"):
            bits["once_opened_days"] = it["open_days"]
        if it["category"] in KCAL_CATS + ("pets",):
            bits["kept"] = {"ambient": "cupboard (ambient)", "chilled": "fridge (chilled)",
                            "frozen": "freezer (frozen)"}.get(it.get("storage") or "", "not recorded")
        lines.append(json.dumps(bits))
    head = {"adults": st["adults"], "children": st["children"], "pets": pets_count(st), "target_days": st["target_days"],
            "food_days": s_.get("food_days"), "water_days": s_.get("water_days"),
            "stored_water_litres": s_.get("water_litres"), "water_litres_needed_a_day": (st["adults"] + st["children"]) * st["water_per_person"] + pets_water(st)}
    return head, lines


def parse_review_reply(text):
    m = re.search(r"\{.*\}", str(text or ""), re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except ValueError:
        d = None
    if not isinstance(d, dict) or not str(d.get("summary") or "").strip():
        return None
    try:
        score = max(1, min(5, int(d.get("score"))))
    except (TypeError, ValueError):
        score = None
    sugg = []
    for g in (d.get("suggestions") or [])[:6]:
        if isinstance(g, dict) and str(g.get("add") or "").strip():
            sugg.append({"add": clean_text(g.get("add"), 120), "why": clean_text(g.get("why"), 200),
                         "category": g.get("category") if g.get("category") in CATEGORIES else "food"})
    return {"summary": clean_text(d.get("summary"), 1500), "score": score, "suggestions": sugg,
            "wider": clean_text(d.get("wider"), 400) if d.get("wider") else ""}


@route("GET", "/api/ai/review")
def api_ai_review_get(body, query):
    return {"review": setting_raw("stock_review", None)}


@route("POST", "/api/ai/review")
def api_ai_review(body, query):
    """Ask the AI whether the stores make a balanced diet, and what's missing. Kept until the next one."""
    with LOCK:
        head, lines = review_input()
    if not lines:
        raise ApiError(400, "There's nothing in the stores to review yet")
    reply, ai = ai_ask(REVIEW_PROMPT + "Household: " + json.dumps(head) + "\nIn the stores:\n" + "\n".join(lines[:300]),
                       None, "Dads Army stores review", max_tokens=8000)   # a long list: plenty of room for the answer
    got = parse_review_reply(reply)
    if not got:
        print("Stores review: couldn't read the AI's answer (%d characters, ending %r)" % (len(reply or ""), str(reply or "")[-80:]),
              flush=True)
        raise ApiError(502, "The AI's answer couldn't be read (it may have been cut off). Try again.")
    got.update(made_at=now_iso(), items=len(lines))
    with tx() as db:
        set_setting_raw(db, "stock_review", got)
    return {"review": got, "ai": ai}


@route("POST", "/api/ai/fill/apply")
def api_ai_fill_apply(body, query):
    """Save the estimates you kept, marked as estimated until you change them."""
    rows = body.get("items")
    if not isinstance(rows, list) or not rows or len(rows) > 200:
        raise ApiError(400, "Nothing to save")
    n = 0
    with tx() as db:
        for r in rows:
            if not isinstance(r, dict):
                continue
            iid = as_int_id(r.get("id"))
            if not db.execute("SELECT 1 FROM items WHERE id = ?", (iid,)).fetchone():
                continue
            data = clean_item(dict((k, r[k]) for k in ("kcal_per_unit", "pack_size", "pack_unit", "open_days", "storage") if k in r),
                              partial=True)
            if not data:
                continue
            old = db.execute("SELECT ai_guessed FROM items WHERE id = ?", (iid,)).fetchone()["ai_guessed"]
            guessed = sorted(set(filter(None, old.split(","))) | set(k for k in data if k != "pack_unit"))
            cols = ", ".join("%s = ?" % k for k in data)
            db.execute("UPDATE items SET %s, ai_guessed = ?, updated_at = ?, rev = rev + 1 WHERE id = ?" % cols,
                       list(data.values()) + [",".join(guessed), now_iso(), iid])
            n += 1
        if n:
            add_log("edited", "%d item%s" % (n, "" if n == 1 else "s"), "Details filled in by the AI")
    return {"saved": n}


# --------------------------------------------------------------------------
# The nutrition panel (1.13.0): calories for the whole pack from a photo of the back, for something already in
# Open Food Facts without calories, or already in the stores. Read from the label, so it's not an estimate.
# --------------------------------------------------------------------------
NUTRITION_PROMPT = (
    "This is a photo of the nutrition information (and maybe the weight) on a food or drink pack. Reply with only "
    "a JSON object with these keys: \"kcal_100g\" (energy in kcal per 100 g or per 100 ml as a number: use the "
    "kcal figure, not kJ; if only kJ is printed, divide by 4.184), \"grams\" (net weight or volume of the WHOLE pack "
    "in grams or millilitres, if printed anywhere in the photo, e.g. 1980 for 6 x 330 ml, or null), \"count\" (how "
    "many in a multipack, or null), \"kcal_pack\" (kcal for the whole pack if printed, or null), "
    "\"serving_g\" and \"kcal_serving\" (a serving's size and kcal, if printed, or null). Use null for anything "
    "you can't read. No other text.")


def _lnum(v, lo=0, hi=100000):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if lo < f < hi else None


def parse_nutrition_reply(text, grams=None, count=None):
    """The AI's reading, plus what's known about the pack, to calories for one whole unit, with the working out.
    grams: what one unit weighs, if the item already says (the label's own figure wins)."""
    m = re.search(r"\{.*\}", str(text or ""), re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except ValueError:
        d = None
    if not isinstance(d, dict):
        return None
    k100 = _lnum(d.get("kcal_100g"), 0, 1000)
    g = _lnum(d.get("grams")) or grams
    n = _lnum(d.get("count"), 1, 1000)
    kpack = _lnum(d.get("kcal_pack"))
    out = {"kcal_100g": k100, "grams": g, "count": int(n) if n and n == int(n) else None,
           "serving_g": _lnum(d.get("serving_g")), "kcal_serving": _lnum(d.get("kcal_serving"))}
    if k100 and g:
        out["kcal_per_unit"] = int(round(k100 * g / 100.0))
        out["how"] = "%s kcal per 100 g × %s g = %s kcal" % (fq(k100), fq(g), out["kcal_per_unit"])
    elif kpack:
        out["kcal_per_unit"] = int(round(kpack))
        out["how"] = "%s kcal for the whole pack, as printed" % fq(kpack)
    elif k100:
        out["kcal_per_unit"] = None
        out["how"] = "%s kcal per 100 g: add the weight of the whole pack to work out the total" % fq(k100)
    else:
        return None
    return out


@route("POST", "/api/scan/nutrition")
def api_scan_nutrition(body, query):
    """Calories for one whole unit from a photo of the nutrition panel. grams: what one weighs, if known."""
    grams = _lnum(body.get("grams"))
    reply, ai = ai_ask(NUTRITION_PROMPT, photo_from(body), "Dads Army nutrition")
    got = parse_nutrition_reply(reply, grams)
    if not got:
        raise ApiError(422, "Couldn't read the calories in that photo. Try the nutrition table, closer up and flat on.")
    return dict(got, ai=ai)


@route("POST", "/api/scan/label")
def api_scan_label(body, query):
    """Read the name, size, what it's in, calories, dates and "once opened" days from a photo of the pack,
    building on what's already known (an earlier photo, or Open Food Facts)."""
    known = body.get("known") if isinstance(body.get("known"), dict) else {}
    reply, ai = ai_ask(label_prompt(known), photo_from(body), "Dads Army label")
    product = parse_label_reply(reply)
    if not product:
        raise ApiError(422, "Couldn't make out the product from that photo. Try the front of the pack, closer up.")
    return {"product": product, "ai": ai}


@route("GET", "/api/scan/ai")
def api_scan_ai_get(body, query):
    c = scan_ai_cfg()
    try:
        ents = ai_task_entities()
    except Exception:
        ents = []
    recent = [dict(r) for r in DB.execute("SELECT ts, ai, model, task, tokens_in, tokens_out, cost_usd, ok, note FROM ai_calls "
                                          "ORDER BY id DESC LIMIT 15")]
    return {"provider": c["provider"], "model": c["model"], "keys_set": sorted(c["keys"]), "ha_entities": ents,
            "limit_usd": c["limit_usd"], "month": month_spend(), "stats": ai_stats(), "recent": recent,
            "providers": dict((k, {"name": v["name"], "model": v["model"]}) for k, v in AI_PROVIDERS.items())}


@route("PUT", "/api/scan/ai")
def api_scan_ai_put(body, query):
    AI_READY["at"] = 0.0   # the AI setting changed: check Home Assistant again
    raw = setting_raw("scan_ai", {}) or {}
    raw.setdefault("keys", {})
    if "provider" in body:
        if body["provider"] not in AI_PROVIDERS:
            raise ApiError(400, "Choose Home Assistant, Anthropic, Google or OpenAI")
        raw["provider"] = body["provider"]
    if "model" in body:
        m = clean_text(body.get("model"), 80)
        if m and not re.fullmatch(r"[A-Za-z0-9._:/-]+", m):
            raise ApiError(400, "That isn't a model name")
        raw["model"] = m
    if "limit_usd" in body:
        raw["limit_usd"] = round(clean_num(body.get("limit_usd"), 0, 0, 1000, "Monthly limit"), 2)
    for prov in ("anthropic", "google", "openai"):
        k = "key_" + prov
        if k in body:
            v = str(body.get(k) or "").strip()
            if v and not re.fullmatch(r"[A-Za-z0-9_\-.]{20,300}", v):
                raise ApiError(400, "That doesn't look like an API key")
            if v:
                raw["keys"][prov] = v
            elif body.get(k) is None:
                raw["keys"].pop(prov, None)   # null removes it; an empty box leaves it alone
    with tx() as db:
        set_setting_raw(db, "scan_ai", raw)
        add_log("settings", "", "Scanning settings updated")
    return api_scan_ai_get({}, {})


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


def check_print(c):
    """What an undo expects a check to still look like."""
    return [c["name"], c["every_days"], c["last_done"], c["notes"]]


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
        after = check_print(get_check(db, cid))
    return {"undo": {"check": before, "after": after}, "next_due": due.isoformat()}


@route("DELETE", r"/api/checks/(\d+)")
def api_check_delete(body, query, cid):
    cid = as_int_id(cid)
    with tx() as db:
        before = get_check(db, cid)
        db.execute("DELETE FROM checks WHERE id = ?", (cid,))
        add_log("removed", before["name"], "Check deleted")
    return {"undo": {"check": before, "after": None}}


@route("POST", "/api/checks/restore")
def api_check_restore(body, query):
    """Undo for checks: put one back exactly as it was."""
    c = body.get("check")
    if not isinstance(c, dict):
        raise ApiError(400, "Nothing to restore")
    cid = as_int_id(c.get("id"))
    data = clean_check(c)
    with tx() as db:
        if "after" in body:   # from 1.11.0: don't undo over a newer change (another phone, or Home Assistant)
            row = db.execute("SELECT * FROM checks WHERE id = ?", (cid,)).fetchone()
            if (body["after"] is None) != (row is None) or (row is not None and check_print(row) != body["after"]):
                raise ApiError(409, "%s has been changed since, so it wasn't undone" % data["name"])
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


# -- Resilience ----------------------------------------------------------------------
# Food and water are two areas of ten. Each area has recommendations: things to have, know
# or do, mostly from the UK Government's Be Ready checklist, Ofcom and Fire Kills. Dads Army
# ticks off what it can see for itself (the stores, the plan, the checks, Home Assistant);
# you tick the rest, or say it's not for you.
AREAS = [
    # id, name, short name (for the dashboard), emoji
    ("water", "Water", "Water", "💧"),
    ("food", "Food & cooking", "Food", "🥫"),
    ("power", "Power & light", "Power", "🔋"),
    ("warmth", "Warmth", "Warmth", "🧣"),
    ("comms", "Communications", "Comms", "📻"),
    ("health", "Health & medicines", "Health", "🩹"),
    ("hygiene", "Hygiene & sanitation", "Hygiene", "🧻"),
    ("safety", "Fire & home safety", "Safety", "🧯"),
    ("money", "Money & documents", "Money", "💷"),
    ("plan", "Plan & getting out", "Getting out", "🎒"),
]
AREA = {a[0]: a for a in AREAS}
ESSENTIAL, RECOMMENDED, EXTRA = 3, 2, 1
PRIORITY_WORD = {3: "Essential", 2: "Recommended", 1: "Extra"}
# Things a recommendation can add to the stores that aren't on the starter list.
EXTRA_ITEMS = [
    ("UPS for the router & Home Assistant", "power", "each", 0, 0, 1,
     "An uninterruptible power supply. Plug in the broadband router and the Home Assistant box, and test it every "
     "few months."),
]
RES_SOURCES = {"bready": ("UK Government", "Be Ready"), "ofcom": ("UK Government", "Ofcom"),
               "firekills": ("UK Government", "Fire Kills"), "alerts": ("UK Government", "Emergency Alerts"),
               "fire": ("Fire & rescue services", ""), "sas": ("SAS Survival Handbook", "PLAN: Protection"),
               "tip": ("Dads Army tip", "")}


def _rx(p):
    return re.compile(p, re.I)


def I(label, rx, add=None, cats=None, excl=None):
    """Something in the stores: what it is, how to spot it by name, and what to add if it's missing."""
    return {"label": label, "rx": _rx(rx), "add": add, "cats": cats, "excl": _rx(excl) if excl else None}


def R(mid, area, pri, title, brief, why, src, test, when=None):
    return {"id": mid, "area": area, "priority": pri, "title": title, "brief": brief, "why": why, "src": src,
            "test": test, "when": when}


MANUAL = ("manual",)
RECOMMENDATIONS = [
    # Water
    R("water_3", "water", ESSENTIAL, "Drinking water for at least 3 days", "3 days of water",
      "3 litres per person per day, just for drinking. You'd need more for cooking and washing.", "bready",
      ("days", "water", 3)),
    R("water_target", "water", RECOMMENDED, "Water for your whole {target}-day target", "Water for {target} days",
      "Your readiness target, set in HQ. Rotate bottled water before its date.", "tip",
      ("days", "water", "target"), when="target>3"),
    R("water_safe", "water", RECOMMENDED, "A way to make water safe to drink: purification tablets or a filter",
      "Water purification", "If the supply stops or isn't safe, you can treat other water. Boiling works too, if you "
      "can heat it.", "tip",
      ("items", [I("purification tablets or a filter", r"purif|filter|sterili[sz]", "Water purification tablets",
                   cats=("water", "medical", "other"))])),
    R("water_carrier", "water", EXTRA, "Containers to carry water", "Water containers",
      "When the supply fails, water companies set up bottled water stations. You'll need something to carry it "
      "home in.", "tip",
      ("items", [I("a water carrier", r"carrier|jerry|container|water butt", "Collapsible water carrier (20L)",
                   cats=("water", "other"))])),
    R("water_stopcock", "water", ESSENTIAL, "Know where the stopcock is, and how to turn it off", "Find the stopcock",
      "For a burst pipe or a flood. Write it in the emergency plan.", "bready", ("plan", ["water_off"])),
    # Food & cooking
    R("food_3", "food", ESSENTIAL, "Food for at least 3 days that needs no fridge", "3 days of food",
      "Tins and dried food you'd usually eat, so nothing goes to waste.", "bready", ("days", "food", 3)),
    R("food_target", "food", RECOMMENDED, "Food for your whole {target}-day target", "Food for {target} days",
      "Your readiness target, set in HQ. Build it up over time.", "tip", ("days", "food", "target"), when="target>3"),
    R("food_opener", "food", ESSENTIAL, "A manual tin opener", "Tin opener", "Most stored food comes in tins.", "tip",
      ("items", [I("a tin opener", r"tin.?opener|can.?opener", "Manual tin opener")])),
    R("food_cook", "food", RECOMMENDED, "A way to heat food without mains power: a camping stove and fuel",
      "Camping stove and fuel", "Only ever use it outdoors or somewhere very well ventilated: stoves give off "
      "carbon monoxide.", "tip",
      ("items", [I("a camping stove", r"stove|cooker", "Camping stove", excl=r"gas|canister|fuel|cartridge"),
                 I("fuel for it", r"canister|cartridge|stove fuel|gas bottle", "Stove gas canisters")])),
    R("food_dates", "food", RECOMMENDED, "Nothing out of date", "Use up old stock",
      "Use the oldest first, and check the dates every six months.", "bready", ("noexpired", ("food", "water"))),
    R("food_pets", "food", ESSENTIAL, "Food and water for your pets", "Pet food",
      "Enough for 3 days, and any medicines they need.", "bready", ("cat", "pets"), when="pets"),
    R("food_baby", "food", RECOMMENDED, "For a baby: ready-to-feed formula, nappies and wipes", "Baby supplies",
      "Ready-to-feed formula needs no clean water. Say it's not for you if you don't have a baby.", "bready",
      ("any", [MANUAL, ("items", [I("formula or nappies", r"formula|napp(y|ies)", None)])]), when="children"),
    # Power & light
    R("power_torch", "power", ESSENTIAL, "A torch for everyone, and spare batteries", "Torches and batteries",
      "Torches are safer than candles.", "bready",
      ("items", [I("torches", r"torch|lantern", "LED torch", excl=r"solar.*charger"),
                 I("spare batteries", r"batteries", "AA batteries")])),
    R("power_bank", "power", ESSENTIAL, "A charged power bank", "Power bank",
      "Keeps phones going through a power cut. Top it up every month.", "bready",
      ("items", [I("a power bank", r"power.?bank|battery pack", "Power bank")])),
    R("power_ups", "power", RECOMMENDED, "A UPS for the router and Home Assistant", "UPS for the router",
      "Broadband, Wi-Fi calling and digital landlines stop in a power cut. An uninterruptible power supply keeps "
      "them, Home Assistant and Dads Army running for a while.", "ofcom",
      ("any", [("items", [I("a UPS", r"\bups\b|uninterruptible", "UPS for the router & Home Assistant")]),
               ("sensors", ["battery"])])),
    R("power_105", "power", RECOMMENDED, "105 written down for power cuts", "Note down 105",
      "Free from any phone, to report or check a power cut. In Northern Ireland it's 03457 643643.", "bready",
      ("phone", "105")),
    R("power_fusebox", "power", ESSENTIAL, "Know where the fuse box and main switch are", "Find the fuse box",
      "Write it in the emergency plan, with how to turn the electricity off.", "bready", ("plan", ["power_off"])),
    R("power_psr", "power", RECOMMENDED, "On the Priority Services Register, if you can be",
      "Priority Services Register", "It's free. Energy and water companies give extra help in a cut to households "
      "with children under 5, older or disabled people, or anyone relying on powered medical equipment. Sign up with "
      "each company. Say it's not for you if you can't join.", "bready", MANUAL),
    R("power_kept", "power", RECOMMENDED, "Power banks charged and torches tested on schedule", "Charge and test",
      "Kit only helps if it works when you need it.", "tip", ("checks", [r"power bank", r"torch"])),
    R("power_backup", "power", EXTRA, "Longer-lasting power: a portable power station or solar charger",
      "Solar charger or power station", "For cuts that last more than a day. Never run a generator indoors.", "tip",
      ("items", [I("a solar charger or power station", r"power station|solar|generator", "Solar phone charger",
                   excl=r"lantern|torch|light")])),
    # Warmth
    R("warm_bedding", "warmth", ESSENTIAL, "Blankets or sleeping bags for everyone", "Blankets or sleeping bags",
      "Keeping warm comes first in a winter power cut.", "bready",
      ("items", [I("blankets or sleeping bags", r"sleeping bag|duvet|blanket", "Sleeping bags",
                   excl=r"foil|space|emergency|fire")])),
    R("warm_clothes", "warmth", ESSENTIAL, "Warm clothes: layers, hats and gloves", "Warm layers",
      "Several thin layers keep you warmer than one thick one.", "bready",
      ("items", [I("hats and gloves", r"\bhats?\b|glove|scarf", "Warm hats & gloves", cats=("shelter", "other"),
                   excl=r"work glove|disposable"),
                 I("warm layers", r"thermal|base layer|fleece|jumper", "Thermal base layers")])),
    R("warm_room", "warmth", RECOMMENDED, "Plan one room to keep warm", "A warm room",
      "A small room you can close off. Draught-proof it, keep the curtains shut at night, and gather there.", "sas",
      MANUAL),
    R("warm_foil", "warmth", EXTRA, "Foil emergency blankets", "Foil blankets",
      "Light and cheap, and they hold your body heat in.", "tip",
      ("items", [I("foil blankets", r"foil|space blanket|emergency blanket", "Foil emergency blankets")])),
    R("warm_sensor", "warmth", EXTRA, "A temperature sensor in the coldest room", "Room temperature sensor",
      "Choose it in Home sensors: Dads Army raises the alert level if a room gets dangerously cold.", "tip",
      ("sensors", ["indoor_temp"]), when="ha"),
    # Communications
    R("comms_radio", "comms", ESSENTIAL, "An FM radio that works without mains: battery, wind-up or solar", "Radio",
      "For news and official advice when the internet and phones are down.", "bready",
      ("items", [I("a radio", r"radio", "Wind-up or battery radio", excl=r"walkie|two.?way|pmr|\bcb\b")])),
    R("comms_numbers", "comms", ESSENTIAL, "Important numbers written down on paper", "Numbers on paper",
      "Family, neighbours, the GP, and your energy, water and broadband providers. Your phone may be flat or lost.",
      "bready", ("any", [("contacts", 3), ("items", [I("a printed contact list", r"contact list", None)])])),
    R("comms_station", "comms", RECOMMENDED, "Your local radio station and its frequency", "Local radio station",
      "Written in the emergency plan, so you can find it fast.", "bready", ("plan", ["radio"])),
    R("comms_touch", "comms", RECOMMENDED, "Agree how you'll keep in touch if the phones are down", "Keeping in touch",
      "Who calls whom, a contact outside the area, and texting if calls won't connect.", "ofcom", MANUAL),
    R("comms_alerts", "comms", RECOMMENDED, "Phones ready for Emergency Alerts", "Emergency Alerts",
      "They reach phones on 4G and 5G: iPhones on iOS 14.5 or later, and Android 11 or later. Keep phones updated.",
      "alerts", MANUAL),
    R("comms_warnings", "comms", RECOMMENDED, "Warnings switched on in Dads Army", "Switch on warnings",
      "Met Office, flood and Emergency Alert warnings for where you live, on the Sitrep and your phone.", "tip",
      ("warnings",)),
    R("comms_flood", "comms", RECOMMENDED, "Signed up for flood warnings", "Flood warnings",
      "Free calls, texts or emails: from the Environment Agency in England, SEPA in Scotland, or Natural Resources "
      "Wales. Say it's not for you if you're not near a river or the coast.", "bready", MANUAL),
    R("comms_landline", "comms", EXTRA, "If you rely on a landline: a battery backup for it", "Landline backup",
      "Digital landlines stop in a power cut. Tell your provider if you rely on yours: they must offer a free backup to "
      "eligible customers, lasting at least an hour.", "ofcom", MANUAL),
    R("comms_walkie", "comms", EXTRA, "Walkie-talkies for keeping in touch nearby", "Walkie-talkies",
      "PMR446 radios need no licence in the UK. Handy for checking on neighbours without phones.", "tip",
      ("items", [I("walkie-talkies", r"walkie|pmr|two.?way radio", "Walkie-talkies")])),
    # Health & medicines
    R("health_kit", "health", ESSENTIAL, "A first aid kit", "First aid kit", "Check it twice a year.", "bready",
      ("items", [I("a first aid kit", r"first.?aid", "First aid kit")])),
    R("health_meds", "health", ESSENTIAL, "Spare essential medicines", "Spare medicines",
      "Order repeat prescriptions in good time: up to 5 working days before you need them. Say it's not for you if "
      "nobody takes regular medicine.", "bready",
      ("items", [I("spare medicines", r"prescription|medicine|medication", "Prescription medicines (spare)")])),
    R("health_list", "health", RECOMMENDED, "A written list of medicines, doses and medical needs", "Medicines list",
      "In the emergency plan, for whoever's helping.", "bready", ("plan", ["medical"])),
    R("health_basics", "health", RECOMMENDED, "Painkillers, plasters and rehydration sachets", "Medicine cabinet",
      "For the everyday things, when the chemist may be shut.", "tip",
      ("items", [I("painkillers", r"paracetamol|ibuprofen|painkiller", "Paracetamol (16)"),
                 I("plasters", r"plaster", "Plasters"),
                 I("rehydration sachets", r"rehydrat", "Oral rehydration sachets")])),
    R("health_ice", "health", RECOMMENDED, "Emergency contacts (ICE) or Medical ID on everyone's phone",
      "ICE on phones", "Paramedics can see it even when the phone's locked.", "bready", MANUAL),
    R("health_check", "health", RECOMMENDED, "First aid kit checked on schedule", "Check the first aid kit",
      "Replace anything used up or out of date.", "tip", ("checks", [r"first aid"])),
    R("health_skills", "health", EXTRA, "Someone at home knows basic first aid", "First aid skills",
      "A short course, such as from the British Red Cross or St John Ambulance.", "tip", MANUAL),
    # Hygiene & sanitation
    R("hyg_basics", "hygiene", ESSENTIAL, "Hand sanitiser, wet wipes and toilet roll", "Sanitiser, wipes, loo roll",
      "For keeping clean when the water's off.", "bready",
      ("items", [I("hand sanitiser", r"saniti[sz]er", "Hand sanitiser"), I("wet wipes", r"wipes", "Wet wipes", cats=("hygiene", "other")),
                 I("toilet roll", r"toilet (roll|paper|tissue)|loo roll", "Toilet roll")])),
    R("hyg_toilet", "hygiene", RECOMMENDED, "An emergency toilet: a bucket with a lid, and strong bags",
      "Emergency toilet", "If the water or the sewers stop working.", "tip",
      ("items", [I("a bucket with a lid", r"bucket", "Bucket with lid"),
                 I("strong bags", r"bin bag|refuse|rubbish bag", "Bin bags")])),
    R("hyg_rest", "hygiene", RECOMMENDED, "Soap, toothpaste and sanitary products", "Bathroom basics",
      "Everyday bathroom products, for a few days at least.", "bready",
      ("items", [I("soap", r"soap", "Soap"), I("toothpaste", r"toothpaste", "Toothpaste"),
                 I("sanitary products", r"sanitary|period|tampon", "Sanitary products")])),
    R("hyg_bleach", "hygiene", EXTRA, "Unscented bleach, for cleaning and disinfecting", "Bleach", "", "tip",
      ("items", [I("bleach", r"bleach|disinfect", "Bleach (unscented)")])),
    # Fire & home safety
    R("safe_smoke", "safety", ESSENTIAL, "A working smoke alarm on every floor", "Smoke alarms",
      "They give you the time to get out. Test them every month.", "firekills",
      ("any", [MANUAL, ("sensors", ["smoke_alarm"])])),
    R("safe_co", "safety", ESSENTIAL, "A carbon monoxide alarm near the boiler, fire or stove", "CO alarm",
      "You can't see, smell or taste carbon monoxide: an alarm is the only way to know. Say it's not for you if "
      "nothing at home burns fuel.", "firekills", ("any", [MANUAL, ("sensors", ["gas_alarm"])])),
    R("safe_gas", "safety", ESSENTIAL, "Know how to turn off the gas", "Find the gas tap",
      "Usually a lever by the meter. If you smell gas, call 0800 111 999. Say it's not for you if you have no gas.",
      "bready", ("plan", ["gas_off"])),
    R("safe_tested", "safety", RECOMMENDED, "Smoke and CO alarms tested every month", "Test the alarms",
      "Press the test button on each one.", "firekills", ("checks", [r"smoke|alarm"])),
    R("safe_ext", "safety", RECOMMENDED, "A fire blanket or extinguisher", "Fire blanket or extinguisher",
      "For a small fire only. If it's not small: get out, stay out and call 999.", "tip",
      ("items", [I("a fire blanket or extinguisher", r"extinguisher|fire blanket", "Fire extinguisher")])),
    R("safe_visit", "safety", EXTRA, "A free home fire safety visit", "Fire safety visit",
      "Many fire and rescue services offer one, and fit smoke alarms if you need them.", "fire", MANUAL),
    R("safe_sensors", "safety", EXTRA, "Smoke, carbon monoxide and leak sensors chosen in Home sensors",
      "Alarm sensors", "Dads Army raises the alert level and says what to do when one goes off.", "tip",
      ("sensors", ["smoke_alarm", "gas_alarm", "leak"]), when="ha"),
    # Money & documents
    R("money_cash", "money", ESSENTIAL, "Cash in coins and notes", "Emergency cash",
      "Card machines and cash machines need power and the internet.", "bready",
      ("items", [I("cash", r"cash", "Emergency cash (small notes)", cats=("docs", "other"))])),
    R("money_copies", "money", ESSENTIAL, "Copies of ID and important documents", "Copies of documents",
      "Passports, birth certificates, and instructions for any medical equipment.", "bready",
      ("items", [I("copies of documents", r"cop(y|ies)|passport|\bid\b", "Copies of ID & passports",
                   cats=("docs", "other"), excl=r"insurance|bank")])),
    R("money_insurance", "money", RECOMMENDED, "Insurance and bank details to hand", "Insurance details",
      "Policy numbers and claim lines, for after a flood or fire.", "bready",
      ("items", [I("insurance details", r"insurance", "Insurance & bank details (copy)")])),
    R("money_where", "money", RECOMMENDED, "Where the originals are kept, written in the plan", "Where documents are",
      "So anyone can grab them in a hurry.", "tip", ("plan", ["documents"])),
    R("money_keys", "money", EXTRA, "Spare house and car keys", "Spare keys", "", "tip",
      ("items", [I("spare keys", r"\bkeys?\b", "Spare house & car keys")])),
    R("money_scans", "money", EXTRA, "Scans of the documents, on a USB stick or secure cloud storage",
      "Scanned documents", "", "tip", ("items", [I("scans", r"usb|scan", "USB stick with scanned documents")])),
    # Plan & getting out
    R("plan_made", "plan", ESSENTIAL, "A household emergency plan everyone knows", "Emergency plan",
      "Who to call, where to meet, and how to turn things off. Keep a printed copy with your documents.", "bready",
      ("planmade",)),
    R("plan_meet", "plan", ESSENTIAL, "Two meeting places: one near home, one further away", "Meeting places",
      "In case you can't get home, or the area has to be evacuated.", "bready", ("plan", ["meet_near", "meet_far"])),
    R("plan_bag", "plan", RECOMMENDED, "A grab bag packed and ready", "Grab bag",
      "If you have to leave in a hurry: water, snacks, a torch, a radio, medicines, copies of documents, cash and "
      "chargers.", "bready", ("items", [I("a grab bag", r"grab.?bag|go.?bag|bug.?out", "Grab bag (packed & ready)")])),
    R("plan_escape", "plan", RECOMMENDED, "Escape routes for a fire or a flood", "Escape routes",
      "Two ways out of the house, and where you'd go.", "bready", MANUAL),
    R("plan_neighbours", "plan", RECOMMENDED, "Know who nearby might need checking on", "Check on neighbours",
      "Older or disabled neighbours, and anyone living alone. Agree a plan with them for a power cut.", "bready",
      MANUAL),
    R("plan_school", "plan", RECOMMENDED, "School or childcare has your up-to-date numbers", "School contacts", "",
      "bready", MANUAL, when="children"),
    R("plan_review", "plan", RECOMMENDED, "The plan gone through together in the last year", "Go through the plan",
      "Everyone knows where to meet and who to call.", "tip", ("checks", [r"emergency plan"])),
    R("plan_car", "plan", EXTRA, "A car kit for winter journeys", "Winter car kit",
      "Warm layers, a blanket, a torch, water, snacks and a phone charger. Say it's not for you if you don't drive.",
      "bready", MANUAL),
    R("plan_map", "plan", EXTRA, "A paper map of the area", "Paper map", "For when phones and sat-navs don't work.",
      "tip", ("items", [I("a paper map", r"\bmap\b|road atlas", "Paper map of the area")])),
]
RES = {r["id"]: r for r in RECOMMENDATIONS}
# These two have their own rules in the alert level (stores for under 3 days).
DAYS_IDS = ("water_3", "food_3")
PLAN_CORE = ("meet_near", "water_off", "power_off", "medical", "documents")


def and_list(words, most=3):
    """["Power", "Warmth", "Safety"] -> "Power, Warmth and Safety"; longer lists end "and 2 more"."""
    if len(words) > most:
        return ", ".join(words[:most]) + " and %d more" % (len(words) - most)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def res_answers():
    raw = setting_raw("resilience", {})
    return {k: v for k, v in (raw if isinstance(raw, dict) else {}).items()
            if k in RES and isinstance(v, dict) and v.get("status") in ("yes", "na")}


def _have(it):
    return sum(b["qty"] for b in it["batches"])


def _found(items, spec):
    return [it for it in items if spec["rx"].search(it["name"])
            and not (spec["excl"] and spec["excl"].search(it["name"]))
            and not (spec["cats"] and it["category"] not in spec["cats"])]


def _items_frac(found):
    """How much of these you have: against their targets, or simply any at all."""
    if not found:
        return 0.0
    got = [it for it in found if _have(it) > 0]
    if any((it["target_qty"] or 0) <= 0 for it in got):
        return 1.0
    tg = [it for it in found if (it["target_qty"] or 0) > 0]
    need = sum(it["target_qty"] for it in tg)
    return min(1.0, sum(min(_have(it), it["target_qty"]) for it in tg) / need) if need else 0.0


def res_test(test, c):
    """(fraction done, what Dads Army can see, what you could do about it)."""
    kind = test[0]
    if kind == "manual":
        return 0.0, "", {"kind": "manual"}
    if kind == "items":
        parts, missing, none, short, first, addable = [], [], [], [], None, False
        for spec in test[1]:
            found = _found(c["items"], spec)
            f = _items_frac(found)
            parts.append(f)
            if not found:
                missing.append(spec["label"])
                addable = addable or bool(spec["add"])
            elif f < 1:
                (short if f > 0 else none).append(spec["label"])
                first = first or next((it["id"] for it in found if (it["target_qty"] or 0) > _have(it)), found[0]["id"])
        frac = sum(parts) / len(parts)
        if frac >= 1:
            return 1.0, "In your stores", None
        bits = []
        if missing:
            bits.append("Not in your stores yet: " + ", ".join(missing))
        if none:
            bits.append("None in stock yet: " + ", ".join(none))
        if short:
            bits.append("Below target: " + ", ".join(short))
        act = {"kind": "add"} if addable else {"kind": "open", "item": first} if first else None
        return frac, ". ".join(bits), act
    if kind == "days":
        days = c["food_days"] if test[1] == "food" else c["water_days"]
        goal = c["target"] if test[2] == "target" else test[2]
        frac = min(1.0, days / goal) if goal else 1.0
        cat = test[1]
        if frac >= 1:
            return 1.0, "%s days stored" % fq(round(days, 1)), None
        have = [it for it in c["items"] if it["category"] == cat
                and ((it["kcal_per_unit"] or 0) > 0 if cat == "food" else item_litres(it) > 0)]
        act = ({"kind": "add"} if cat == "water" and not have else {"kind": "cat", "cat": cat})
        return frac, "%s of %s days stored" % (fq(round(days, 1)), fq(goal)), act
    if kind == "plan":
        filled = [k for k in test[1] if c["plan"].get(k)]
        frac = len(filled) / float(len(test[1]))
        return frac, ("In your plan" if frac >= 1 else "Not in your plan yet" if not filled else "Partly in your plan"), \
            (None if frac >= 1 else {"kind": "plan"})
    if kind == "planmade":
        n = len([k for k in PLAN_CORE if c["plan"].get(k)]) + (1 if c["plan"].get("contacts") else 0)
        frac = min(1.0, n / 4.0)
        return frac, ("Your plan has %d of the main parts" % n if frac < 1 else "Made"), \
            (None if frac >= 1 else {"kind": "plan"})
    if kind == "contacts":
        n = len([x for x in c["plan"].get("contacts") or [] if x.get("phone")])
        frac = min(1.0, n / float(test[1]))
        return frac, "%d number%s in your plan" % (n, "" if n == 1 else "s"), (None if frac >= 1 else {"kind": "plan"})
    if kind == "phone":
        ok = any(re.sub(r"\D", "", x.get("phone") or "") == test[1] for x in c["plan"].get("contacts") or [])
        return (1.0, "In your plan", None) if ok else (0.0, "Not in your plan yet", {"kind": "plan"})
    if kind == "checks":
        parts, todo = [], None
        for rx in test[1]:
            ck = next((x for x in c["checks"] if re.search(rx, x["name"], re.I)), None)
            if not ck:
                parts.append((0.0, "Not on your routine checks"))
                todo = todo or {"kind": "addcheck"}
                continue
            due, d, text = check_status(ck, c["today"])
            f = 1.0 if (d is not None and d > 0) else 0.5 if ck["last_done"] else 0.25
            parts.append((f, "%s: %s" % (ck["name"], text.lower() if f < 1 else "done")))
            if f < 1:
                todo = todo or {"kind": "check", "check": ck["id"]}
        frac = sum(p[0] for p in parts) / len(parts)
        return frac, ". ".join(p[1] for p in parts if p[0] < 1) or "Up to date", (None if frac >= 1 else todo)
    if kind == "sensors":
        roles = test[1]
        got = [r for r in roles if c["home"].get(r)]
        frac = len(got) / float(len(roles))
        return frac, ("Chosen in Home sensors" if frac >= 1 else "Not chosen in Home sensors yet" if not got else
                      "%d of %d chosen in Home sensors" % (len(got), len(roles))), \
            (None if frac >= 1 else {"kind": "sensors"})
    if kind == "warnings":
        return (1.0, "Switched on", None) if c["warnings_on"] else (0.0, "Switched off", {"kind": "warnings"})
    if kind == "noexpired":
        stocked = [b for it in c["items"] if it["category"] in test[1] for b in it["batches"] if b["qty"] > 0]
        if not stocked:
            return 0.0, "Nothing stored yet", {"kind": "cat", "cat": test[1][0]}
        n = len([1 for b in stocked if b["expiry"] and b["expiry"] < c["today"].isoformat()])
        return (1.0, "Nothing out of date", None) if not n else \
            (0.0, "%d batch%s out of date" % (n, "" if n == 1 else "es"), {"kind": "expired"})
    if kind == "cat":
        its = [it for it in c["items"] if it["category"] == test[1]]
        frac = _items_frac(its)
        return frac, ("In your stores" if frac >= 1 else "Not in your stores yet" if not its else "Below target"), \
            (None if frac >= 1 else {"kind": "cat", "cat": test[1]})
    if kind == "any":
        best = None
        for t in test[1]:
            if t[0] == "sensors" and not c["ha"]:
                continue
            r = res_test(t, c)
            if best is None or r[0] > best[0] or (r[0] == best[0] and best[2] and best[2]["kind"] == "manual"):
                best = r
        return best
    return 0.0, "", None


def res_applies(r, c):
    w = r["when"]
    return (not w or (w == "ha" and c["ha"]) or (w == "children" and c["children"] > 0)
            or (w == "pets" and c["pets"]) or (w == "target>3" and c["target"] > 3))


def resilience(c):
    """Every recommendation, how far along each one is, and a score for each area."""
    answers = c["answers"]
    out, by_area = [], {}
    for r in RECOMMENDATIONS:
        if not res_applies(r, c):
            continue
        frac, detail, act = res_test(r["test"], c)
        ans = (answers.get(r["id"]) or {}).get("status")
        if ans == "yes":
            frac = 1.0
        status = "na" if ans == "na" else "done" if frac >= 0.999 else "partly" if frac > 0 else "todo"
        src, body = RES_SOURCES[r["src"]]
        m = {"id": r["id"], "area": r["area"], "priority": r["priority"], "priority_word": PRIORITY_WORD[r["priority"]],
             "title": r["title"].format(target=c["target"]), "brief": r["brief"].format(target=c["target"]),
             "why": r["why"], "source": src, "label": src + (" · " + body if body else ""),
             "frac": round(frac, 3), "status": status, "detail": detail, "answer": ans,
             "act": None if status in ("done", "na") else act, "manual": r["test"] == MANUAL}
        out.append(m)
        by_area.setdefault(r["area"], []).append(m)
    areas = []
    for aid, name, short, emoji in AREAS:
        ms = [m for m in by_area.get(aid, []) if m["status"] != "na"]
        weight = sum(m["priority"] for m in ms)
        pct = _round(100.0 * sum(m["priority"] * m["frac"] for m in ms) / weight) if weight else 100
        missing = [m for m in ms if m["priority"] == ESSENTIAL and m["status"] != "done"]
        todo = sorted([m for m in ms if m["status"] != "done"], key=lambda m: (-m["priority"], m["frac"]))
        areas.append({"id": aid, "name": name, "short": short, "emoji": emoji, "pct": pct,
                      "state": "good" if pct >= 80 else "fair" if pct >= 50 else "poor",
                      "done": len([m for m in ms if m["status"] == "done"]), "total": len(ms),
                      "essentials_missing": [m["id"] for m in missing],
                      "next": todo[0]["brief"] if todo else ""})
    rank = {a["id"]: (i, a["pct"]) for i, a in enumerate(areas)}
    nxt = sorted([m for m in out if m["status"] not in ("done", "na")],
                 key=lambda m: (-m["priority"], rank[m["area"]][1], rank[m["area"]][0]))
    return {"pct": _round(sum(a["pct"] for a in areas) / float(len(areas))) if areas else 0,
            "done": len([m for m in out if m["status"] == "done"]),
            "total": len([m for m in out if m["status"] != "na"]),
            "areas": areas, "next": [m["id"] for m in nxt[:8]], "items": out}


def res_context(items, st, plan, checks, warnings_on, food_days, water_days, today):
    with LOCK:
        answers = res_answers()
        home = home_cfg() if HA_TOKEN else {}
    return {"items": items, "plan": plan, "checks": checks, "warnings_on": warnings_on, "home": home,
            "ha": bool(HA_TOKEN), "answers": answers, "food_days": food_days, "water_days": water_days,
            "target": st["target_days"], "children": st["children"], "today": today,
            "pets": bool(plan.get("pets")) or pets_count(st) > 0 or any(it["category"] == "pets" for it in items)}


@route("POST", "/api/resilience/answer")
def api_res_answer(body, query):
    """You've done it ("yes"), it's not for you ("na"), or take your answer back ("")."""
    mid = clean_text(body.get("id"), 40)
    if mid not in RES:
        raise ApiError(404, "That recommendation doesn't exist")
    status = clean_text(body.get("status"), 10)
    if status not in ("yes", "na", ""):
        raise ApiError(400, "Say yes, na, or nothing")
    title = RES[mid]["brief"].format(target=get_settings()["target_days"])
    with tx() as db:
        answers = res_answers()
        before = (answers.get(mid) or {}).get("status") or ""
        if status:
            answers[mid] = {"status": status, "at": now_iso()}
        else:
            answers.pop(mid, None)
        set_setting_raw(db, "resilience", answers)
        if status != before:
            add_log("resilience", title, {"yes": "Marked as done", "na": "Not for us", "": "Answer cleared"}[status])
    return {"undo": {"id": mid, "status": before}}


@route("POST", "/api/resilience/add")
def api_res_add(body, query):
    """Put what a recommendation needs into the stores (at zero, so it's on the supply run), or add its check."""
    mid = clean_text(body.get("id"), 40)
    r = RES.get(mid)
    if not r:
        raise ApiError(404, "That recommendation doesn't exist")
    tests = r["test"][1] if r["test"][0] == "any" else [r["test"]]
    specs = [s for t in tests if t[0] == "items" for s in t[1]]
    rxs = [x for t in tests if t[0] == "checks" for x in t[1]]
    if mid == "water_3" or (r["test"][0] == "days" and r["test"][1] == "water"):
        specs = [I("drinking water", r"bottled water|water \(", "Bottled water (5L)", cats=("water",))]
    added, ids, checks = [], [], []
    rows = starter_rows()
    with tx() as db:
        ctx = starter_ctx(get_settings())
        items = all_items()
        names = set(it["name"].lower() for it in items)
        ts = now_iso()
        for spec in specs:
            if _found(items, spec) or not spec["add"] or spec["add"].lower() in names:
                continue
            row = rows[spec["add"]]
            ids.append(add_starter(db, row, ctx, ts))
            added.append(row[0])
            names.add(row[0].lower())
        have = [row[0] for row in db.execute("SELECT name FROM checks")]
        for rx in rxs:
            if any(re.search(rx, n, re.I) for n in have):
                continue
            sug = next((s for s in CHECK_SUGGESTIONS if re.search(rx, s[0], re.I)), None)
            if sug:
                db.execute("INSERT INTO checks(name, every_days, last_done, notes, created_at) VALUES (?, ?, NULL, ?, ?)",
                           (sug[0], sug[1], sug[2], ts))
                checks.append(sug[0])
                have.append(sug[0])
        if added:
            add_log("added", ", ".join(added), "From the resilience recommendations: on the supply run")
        if checks:
            add_log("added", ", ".join(checks), "New routine check, from the resilience recommendations")
    if not added and not checks:
        raise ApiError(409, "Nothing to add: it's already in your stores or checks")
    return {"added": added, "checks": checks, "undo": {"ids": ids} if ids else None}


@route("PUT", "/api/settings")
def api_settings(body, query):
    changed = []
    rescaled = 0
    with tx() as db:
        before = get_settings()
        for key, (lo, hi, integer) in SETTING_RULES.items():
            if key in body:
                v = clean_num(body.get(key), DEFAULT_SETTINGS[key], lo, hi, SETTING_LABELS.get(key, key))
                if integer:
                    v = int(round(v))
                db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(v)))
                if v != before[key]:
                    changed.append(key)
        if "warn_by_cat" in body:
            v = clean_warn_by_cat(body.get("warn_by_cat"))
            set_setting_raw(db, "warn_by_cat", v)
            if v != before["warn_by_cat"]:
                changed.append("warn_by_cat")
        if changed:
            add_log("settings", "", "Household settings updated")
        if any(k in SCALES_TARGETS for k in changed):
            rescaled = rescale_targets(db, before, get_settings())
            if rescaled:
                add_log("settings", "", "Targets for %d thing%s from the starter list now suit the household"
                        % (rescaled, "" if rescaled == 1 else "s"))
    return {"changed": changed, "rescaled": rescaled}


def starter_ctx(st):
    people = max(1, st["adults"] + st["children"])
    days = st["target_days"]
    return {"people": people, "days": days, "dogs": st["dogs"], "cats": st["cats"], "pets": pets_count(st),
            "kcal": max(1, st["adults"] * st["kcal_adult"] + st["children"] * st["kcal_child"]) * days,
            "litres": (people * st["water_per_person"] + pets_water(st)) * days}


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
    # Pets' things: none wanted if there are no such pets.
    if kind == "dogday":
        return int(math.ceil(ctx["dogs"] * ctx["days"] * v - 1e-9))
    if kind == "catday":
        return int(math.ceil(ctx["cats"] * ctx["days"] * v - 1e-9))
    if kind == "pets":
        return int(math.ceil(ctx["pets"] * v)) if ctx["pets"] else 0
    return 1


def starter_per_day(spec, ctx):
    """Things used every day also say how long they'll last."""
    if not isinstance(spec, tuple):
        return 0
    n = {"perday": ctx["people"], "dogday": ctx["dogs"], "catday": ctx["cats"]}.get(spec[0])
    return round(n * spec[1], 3) if n is not None else 0


def starter_wanted(spec, ctx):
    """Pet food only when there are pets of that kind."""
    if isinstance(spec, tuple) and spec[0] in PET_SPECS:
        return {"dogday": ctx["dogs"], "catday": ctx["cats"], "pets": ctx["pets"]}[spec[0]] > 0
    return True


def add_starter(db, row, ctx, ts):
    name, cat, unit, kcal, litres, target, notes = row
    item_id = insert_item(db, {"name": name, "category": cat, "unit": unit, "kcal_per_unit": kcal,
                               "litres_per_unit": litres, "target_qty": resolve_target(target, kcal, litres, ctx),
                               "per_day": starter_per_day(target, ctx), "price": 0, "notes": notes}, ts, ts)
    db.execute("UPDATE items SET starter = ?, auto_target = ? WHERE id = ?",
               (name, 1 if isinstance(target, tuple) else 0, item_id))
    return item_id


def starter_rows():
    return dict((r[0], r) for r in STARTER + EXTRA_ITEMS)


def rescale_targets(db, old_st, new_st):
    """The household or the readiness target changed: targets from the starter list that you haven't
    changed yourself follow it. So do their daily use, if that's still what the starter list set."""
    rows = starter_rows()
    old, new = starter_ctx(old_st), starter_ctx(new_st)
    n = 0
    for it in db.execute("SELECT id, starter, target_qty, per_day, auto_target FROM items WHERE starter != ''").fetchall():
        row = rows.get(it["starter"])
        if not row or not isinstance(row[5], tuple):
            continue
        spec, kcal, litres = row[5], row[3], row[4]
        sets = {}
        if it["auto_target"]:
            t = resolve_target(spec, kcal, litres, new)
            if abs(t - it["target_qty"]) > 1e-9:
                sets["target_qty"] = t
        if it["per_day"] and abs(it["per_day"] - starter_per_day(spec, old)) < 1e-6:
            p = starter_per_day(spec, new)
            if abs(p - it["per_day"]) > 1e-9:
                sets["per_day"] = p
        if sets:
            db.execute("UPDATE items SET %s, updated_at = ?, rev = rev + 1 WHERE id = ?"
                       % ", ".join("%s = ?" % k for k in sets), list(sets.values()) + [now_iso(), it["id"]])
            n += 1
    return n


def guess_starter(name, target, ctx, rows=None):
    """(starter name, follows the household?) for something that may have come from the starter list. A target
    still at what the starter list would give now is taken to be the starter list's."""
    row = (rows or starter_rows()).get(name)
    if not row:
        return "", 0
    auto = isinstance(row[5], tuple) and abs(resolve_target(row[5], row[3], row[4], ctx) - target) < 1e-9
    return row[0], 1 if auto else 0


def mark_starter_items(db):
    """Databases from before 1.11.0: find what came from the starter list, once."""
    if setting_raw("starter_marked", False):
        return
    rows, ctx = starter_rows(), starter_ctx(get_settings())
    for it in db.execute("SELECT id, name, target_qty FROM items WHERE starter = ''").fetchall():
        name, auto = guess_starter(it["name"], it["target_qty"], ctx, rows)
        if name:
            db.execute("UPDATE items SET starter = ?, auto_target = ? WHERE id = ?", (name, auto, it["id"]))
    set_setting_raw(db, "starter_marked", True)


@route("POST", "/api/seed")
def api_seed(body, query):
    """Add the suggested starter list (at zero stock), skipping names that already exist."""
    with tx() as db:
        ctx = starter_ctx(get_settings())
        existing = set(r[0].lower() for r in db.execute("SELECT name FROM items"))
        ts = now_iso()
        added = 0
        for row in STARTER:
            if row[0].lower() in existing or not starter_wanted(row[5], ctx):
                continue
            add_starter(db, row, ctx, ts)
            added += 1
        if added:
            add_log("starter", "", "Loaded %d suggested items" % added)
    return {"added": added}


FORMULA_START = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")


def csv_text(s):
    """Text for a spreadsheet cell. Excel, Numbers and Google Sheets run a cell that starts with = + - or @
    as a formula, so a name like '=HYPERLINK(...)' could do something when the file is opened. A leading
    apostrophe makes it plain text (the usual fix; spreadsheets hide the apostrophe)."""
    s = "" if s is None else str(s)
    return "'" + s if s.lstrip(" ").startswith(FORMULA_START) else s


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
            w.writerow([csv_text(it["category"]), csv_text(it["name"]), fq(b["qty"]), csv_text(it["unit"]),
                        b["expiry"] or "", csv_text(b["location"]),
                        fq(it["target_qty"]), fq(it["kcal_per_unit"]), fq(it["litres_per_unit"]),
                        fq(it["per_day"]) if it["per_day"] else "", "%.2f" % it["price"] if it["price"] else "",
                        csv_text(it["notes"])])
    data = ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens it as UTF-8
    return Raw(data, "text/csv; charset=utf-8", "dadsarmy-stores-%s.csv" % dt.date.today().isoformat())


@route("GET", r"/api/backup\.json")
def api_backup(body, query):
    with LOCK:
        items = all_items()
        used = {}
        for r in DB.execute("SELECT item_id, ts, qty FROM usage ORDER BY id"):
            used.setdefault(r["item_id"], []).append([r["ts"], r["qty"]])
        codes = {}
        for r in DB.execute("SELECT code, item_id, product FROM barcodes ORDER BY code"):
            codes.setdefault(r["item_id"], []).append({"code": r["code"], "product": r["product"]})
        for it in items:
            it["usage"] = used.get(it["id"], [])
            it["barcodes"] = codes.get(it["id"], [])
        payload = {
            "app": "dadsarmy",
            "version": VERSION,
            "exported_at": now_iso(),
            "settings": get_settings(),
            "items": items,
            "history": [dict(r) for r in DB.execute("SELECT * FROM history ORDER BY day")],
            "shopping": [dict(r) for r in DB.execute("SELECT * FROM shopping ORDER BY id")],
            "checks": all_checks(),
            "plan": get_plan(),
            "resilience": res_answers(),
            "places": own_places(),
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
    if len(items) > 20000:
        raise ApiError(400, "That backup has more items than Dads Army can take")
    # Validate everything before touching the database.
    clean_items = []
    for it in items:
        if not isinstance(it, dict):
            raise ApiError(400, "Backup file is damaged")
        data = clean_item(it)
        data["_barcodes"] = []   # 1.13.0 on: codes, or {"code", "product"}; a damaged one is skipped
        for c in (it.get("barcodes") if isinstance(it.get("barcodes"), list) else [])[:50]:
            code = safe_barcode(c.get("code") if isinstance(c, dict) else c)
            if code:
                data["_barcodes"].append((code, clean_text(c.get("product"), 160) if isinstance(c, dict) else ""))
        bl = []
        batches = it.get("batches") or []
        if not isinstance(batches, list):
            raise ApiError(400, "Backup file is damaged")
        for b in batches:
            if isinstance(b, dict):
                q = clean_num(b.get("qty"), 0, 0, 1e7)
                if q > 0:
                    bl.append((q, clean_date(b.get("expiry")), clean_text(b.get("location"), 80),
                               clean_text(b.get("added_at"), 30) or now_iso(), clean_date(b.get("opened_at"))))
        used = []   # 1.11.0 on: what was used when
        for u in (it.get("usage") if isinstance(it.get("usage"), list) else [])[-2000:]:
            if isinstance(u, list) and len(u) == 2 and isinstance(u[0], str) and DATE_RE.match(u[0][:10]):
                q = clean_num(u[1], 0, 0, 1e7)
                if q > 0:
                    used.append((clean_text(u[0], 30), q))
        starter = None
        if isinstance(it.get("starter"), str):
            starter = (clean_text(it.get("starter"), 120), 1 if it.get("auto_target") else 0)
        clean_items.append((data, clean_text(it.get("created_at"), 30) or now_iso(), bl, used, starter))
    # A backup with nothing in it would empty the stores: make sure that's what you meant.
    with LOCK:
        have = DB.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if not clean_items and have and body.get("confirm_empty") is not True:
        raise ApiError(409, "That backup has nothing in the stores. Restoring it would delete all %d things you have "
                            "now." % have, "empty_backup")
    settings_in = {}
    for key, (lo, hi, integer) in SETTING_RULES.items():
        if key in settings:
            v = clean_num(settings.get(key), DEFAULT_SETTINGS[key], lo, hi, SETTING_LABELS.get(key, key))
            settings_in[key] = int(round(v)) if integer else v
    warn_by_cat = clean_warn_by_cat(settings["warn_by_cat"]) if isinstance(settings.get("warn_by_cat"), dict) else None
    history = None
    if isinstance(body.get("history"), list):
        history = []
        for h in body["history"][-4000:]:
            if isinstance(h, dict) and isinstance(h.get("day"), str) and DATE_RE.fullmatch(h["day"]):
                history.append(dict((k, clean_num(h.get(k), 0, -1, 1e9, k)) for k in HISTORY_FIELDS))
                history[-1]["day"] = h["day"]
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
    # Your own places arrived in 1.10.0.
    places = None
    if isinstance(body.get("places"), list):
        places = clean_places({"places": body["places"]})
    # Your resilience answers arrived in 1.9.0.
    answers = None
    if isinstance(body.get("resilience"), dict):
        answers = dict((k, {"status": v["status"], "at": clean_text(v.get("at"), 30) or now_iso()})
                       for k, v in body["resilience"].items()
                       if k in RES and isinstance(v, dict) and v.get("status") in ("yes", "na"))
    try:
        make_backup("pre-restore")
    except Exception as e:
        raise ApiError(500, "Couldn't save a copy of what you have now, so nothing was restored (%s)" % e)
    ts = now_iso()
    has_codes = any(isinstance(it, dict) and "barcodes" in it for it in items)
    with tx() as db:
        # A backup from before 1.13.0 has no barcodes: keep yours, matched back up to the items by name.
        kept_codes = [] if has_codes else [dict(r) for r in db.execute(
            "SELECT b.code, b.product, b.added_at, lower(i.name) AS name FROM barcodes b JOIN items i ON i.id = b.item_id")]
        db.execute("DELETE FROM batches")
        db.execute("DELETE FROM items")
        db.execute("DELETE FROM shopping")
        db.execute("DELETE FROM usage")
        db.execute("DELETE FROM barcodes")
        for key, v in settings_in.items():
            db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(v)))
        if warn_by_cat is not None:
            set_setting_raw(db, "warn_by_cat", warn_by_cat)
        ctx, rows = starter_ctx(get_settings()), starter_rows()
        for data, created, bl, used, starter in clean_items:
            new_id = insert_item(db, data, created, ts)
            for q, exp, loc, added, opened in bl:
                db.execute("INSERT INTO batches(item_id, qty, expiry, location, added_at, opened_at) VALUES (?, ?, ?, ?, ?, ?)",
                           (new_id, q, exp, loc, added, opened))
            for when, q in used:
                db.execute("INSERT INTO usage(item_id, ts, qty) VALUES (?, ?, ?)", (new_id, when, q))
            for code, product in data.get("_barcodes") or []:
                db.execute("INSERT OR REPLACE INTO barcodes(code, item_id, product, added_at) VALUES (?, ?, ?, ?)",
                           (code, new_id, product, ts))
            name, auto = starter if starter is not None else guess_starter(data["name"], data["target_qty"], ctx, rows)
            if name:
                db.execute("UPDATE items SET starter = ?, auto_target = ? WHERE id = ?", (name, auto, new_id))
        if kept_codes:
            by_name = dict((r["name"].lower(), r["id"]) for r in db.execute("SELECT id, name FROM items"))
            for c in kept_codes:
                if c["name"] in by_name:
                    db.execute("INSERT OR REPLACE INTO barcodes(code, item_id, product, added_at) VALUES (?, ?, ?, ?)",
                               (c["code"], by_name[c["name"]], c["product"], c["added_at"]))
        for s in shopping:
            if isinstance(s, dict) and clean_text(s.get("text"), 200):
                db.execute("INSERT INTO shopping(text, done, created_at) VALUES (?, ?, ?)",
                           (clean_text(s.get("text"), 200), 1 if s.get("done") else 0, ts))
        if history is not None:
            for h in history:
                db.execute("INSERT OR REPLACE INTO history(%s) VALUES (%s)" % (
                    ", ".join(("day",) + HISTORY_FIELDS), ", ".join("?" * (len(HISTORY_FIELDS) + 1))),
                    [h["day"]] + [h[k] for k in HISTORY_FIELDS])
        if checks is not None:
            db.execute("DELETE FROM checks")
            for c, created in checks:
                db.execute("INSERT INTO checks(name, every_days, last_done, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                           (c["name"], c["every_days"], c["last_done"], c["notes"], created))
        if plan is not None:
            set_setting_raw(db, "plan", plan)
        if answers is not None:
            set_setting_raw(db, "resilience", answers)
        if places is not None:
            set_setting_raw(db, "places", places)
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


class BackupError(Exception):
    pass


def check_backup(path):
    """Open a backup copy on its own and make sure it's sound and really is Dads Army's: SQLite's own
    integrity check, the tables there, and the same number of items as the live database."""
    conn = sqlite3.connect("file:%s?mode=ro" % path.replace("?", "%3f").replace("#", "%23"), uri=True)
    try:
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise BackupError("the copy is damaged (%s)" % ok)
        tables = set(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"))
        if not {"items", "batches", "settings"} <= tables:
            raise BackupError("the copy is missing tables")
        return conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    except sqlite3.DatabaseError as e:
        raise BackupError("the copy can't be read (%s)" % e)
    finally:
        conn.close()


def scrub_secrets(con):
    """API keys stay out of backup copies (they go into Home Assistant's backups too): paste them in again after a restore."""
    con.execute("PRAGMA secure_delete = ON")   # overwrite the old values, not just unlink them
    row = con.execute("SELECT value FROM settings WHERE key = 'scan_ai'").fetchone()
    if row:
        try:
            raw = json.loads(row[0])
            if isinstance(raw, dict) and raw.get("keys"):
                raw["keys"] = {}
                con.execute("UPDATE settings SET value = ? WHERE key = 'scan_ai'", (json.dumps(raw),))
        except ValueError:
            pass
    con.commit()
    con.execute("VACUUM")   # and no old copies left in free pages


def make_backup(tag="auto"):
    """Copy the database to a new, dated file. The copy is written under a temporary name and checked;
    only then is it given its real name, and only then are old copies cleared out. A name that's
    already taken (two backups in the same second) gets a number, so nothing is ever overwritten."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    tmp = os.path.join(BACKUP_DIR, ".dadsarmy-%s-%s-%d.tmp" % (stamp, tag, os.getpid()))
    try:
        with LOCK:
            dest = sqlite3.connect(tmp)
            try:
                DB.backup(dest)
                scrub_secrets(dest)
                dest.execute("PRAGMA journal_mode = DELETE")   # one self-contained file, no -wal beside it
            finally:
                dest.close()
            want = DB.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        got = check_backup(tmp)
        if got != want:
            raise BackupError("the copy has %d items, not %d" % (got, want))
        n = 0
        while True:
            name = "dadsarmy-%s-%s.db" % (stamp + ("" if not n else chr(96 + n)), tag)   # ...-101010b-auto.db
            path = os.path.join(BACKUP_DIR, name)
            try:   # O_EXCL: claim the name, so a copy made at the same moment can't take it too
                os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                break
            except FileExistsError:
                n += 1
                if n > 26:
                    raise BackupError("no free name for the copy")
        os.replace(tmp, path)
    except Exception:
        for f in (tmp, tmp + "-wal", tmp + "-shm", tmp + "-journal"):
            try:
                os.remove(f)
            except OSError:
                pass
        raise
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
    for f in os.listdir(BACKUP_DIR) if os.path.isdir(BACKUP_DIR) else []:
        if f.startswith(".dadsarmy-") and f.endswith(".tmp"):   # left by a power cut mid-backup
            try:
                os.remove(os.path.join(BACKUP_DIR, f))
            except OSError:
                pass
    while True:
        try:
            existing = list_backups()
            newest = os.path.getmtime(os.path.join(BACKUP_DIR, existing[-1])) if existing else 0
            if newest:
                LAST_BACKUP["at"] = dt.datetime.fromtimestamp(newest).replace(microsecond=0).isoformat(sep=" ")
            if time.time() - newest > 20 * 3600:
                make_backup("auto")
        except BackupError as e:
            print("Daily backup: not kept, because %s. The earlier backups are still there; "
                  "will try again in an hour." % e, flush=True)
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
RAN_OUT_PENDING = {}  # item id -> when it ran out, until Home Assistant has been told (see ha_loop)
TODO_LOCK = threading.Lock()
TODO_STATUS = {"ok": None, "error": "", "synced_at": None, "name": ""}
TODO_RE = re.compile(r"^todo\.[a-z0-9_]+$")
TODO_LIST_NAME = "Supply run"
CHECKS_LIST_NAME = "Dads Army checks"
CHECKS_STATUS = {"ok": None, "error": "", "synced_at": None, "name": ""}
HA_WS = os.environ.get("DADSARMY_HA_WS", "ws://supervisor/core/websocket")
DASH_URL = "dads-army"
DASH_LAYOUT = 6   # bump when the dashboard changes, so the app offers to rebuild it


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
    try:
        ai = ai_stats()
        put("sensor.dads_army_ai_spend", round(ai["cost_usd"], 4), "Dads Army AI spend this month", "mdi:robot-outline", "USD", {
            "ai_answers": ai["ok"], "failed": ai["failed"], "today_answers": ai["today"]["ok"], "today_usd": round(ai["today"]["cost_usd"], 4),
            "limit_usd": ai["limit_usd"] or None, "left_usd": ai["left_usd"], "last_month_usd": round(ai["last_month"]["cost_usd"], 4),
            "dates_read": ai["tasks"]["dates"], "labels_read": ai["tasks"]["labels"], "since": ai["since"]})
    except sqlite3.Error:
        pass
    put("sensor.dads_army_food_days", s["food_days"], "Dads Army food", "mdi:food-drumstick", "days",
        {"goes_off_first_days": s["food_wasted_days"]})
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
    live = w.get("live") or []
    watch = sum(1 for r in live if r["state"] != "good")
    put("sensor.dads_army_live", watch, "Dads Army wider picture",
        "mdi:earth-box" if not watch else "mdi:earth-box-minus", "alerts",
        {"rows": live, "enabled": w["enabled"], "checked_at": w["checked_at"]})
    sit = s["situation"]
    put("sensor.dads_army_alert_level", sit["name"], "Dads Army alert level", LEVEL_ICONS[sit["level"] - 1],
        attrs={"level": sit["level"], "colour": sit["colour"], "emoji": sit["emoji"], "meaning": sit["meaning"],
               "action": sit["action"], "escalated_why": sit["escalated_why"],
               "escalated": sit["escalated"], "reasons": sit["reasons"][:LIST_LIMIT], "notes": sit["notes"],
               "guidance": [{"label": g["label"], "source": g["source"], "text": g["text"]} for g in sit["guidance"]],
               "scale": [{"level": x["level"], "name": x["name"], "emoji": x["emoji"], "meaning": x["meaning"],
                          "action": x["action"]} for x in sit["scale"]]},
        measurement=False)
    res = s["resilience"]
    dots = {"good": "🟢", "fair": "🟡", "poor": "🔴"}
    by_id = dict((m["id"], m) for m in res["items"])
    put("sensor.dads_army_resilience", res["pct"], "Dads Army resilience", "mdi:shield-half-full", "%", {
        "done": res["done"], "total": res["total"],
        "areas": [{"id": a["id"], "name": a["name"], "short": a["short"], "emoji": a["emoji"], "pct": a["pct"],
                   "state": a["state"], "dot": dots[a["state"]], "done": a["done"], "total": a["total"],
                   "essentials_missing": len(a["essentials_missing"]), "next": a["next"]} for a in res["areas"]],
        "next_steps": [{"area": by_id[i]["area"], "emoji": AREA[by_id[i]["area"]][3], "title": by_id[i]["brief"],
                        "priority": by_id[i]["priority_word"]} for i in res["next"][:5]],
        # Short keys: every recommendation, by area, for the dashboard's Resilience page.
        "measures": dict((a[0], [{"t": m["title"], "s": m["status"], "p": m["priority"], "l": m["label"]}
                                 for m in res["items"] if m["area"] == a[0]]) for a in AREAS)})
    # Places to go: a summary, and each place as a point for Home Assistant's map card
    # (geo_location entities with source "dads_army").
    pl = s["places"]
    brief = lambda p: {"name": p["name"], "what": p["what"], "text": p["text"], "short": p["short"], "km": p["km"],
                       "dir": p["dir"], "own": p["own"]}
    put("sensor.dads_army_places", pl["count"], "Dads Army places to go", "mdi:map-marker-radius", attrs={
        "located": bool(pl["home"]), "active": pl["active"], "error": pl["error"],
        "hazards": [{"key": h["key"], "what": h["what"], "emoji": h["emoji"], "active": h["active"],
                     "advice": h["advice"], "avoiding": h["avoiding"], "places": [brief(p) for p in h["places"]]}
                    for h in pl["hazards"]],
        "help": [brief(p) for p in pl["help"]]}, measurement=False)
    if pl["home"]:
        uses = {}
        for h in pl["hazards"]:
            for p in h["places"]:
                uses.setdefault((p["lat"], p["lon"]), []).append(h["what"])
        points = [("home", {"name": "Home", "what": "Home", "icon": "mdi:home", "lat": pl["home"]["lat"],
                            "lon": pl["home"]["lon"], "km": 0, "dir": "", "own": False})]
        counts = {}
        for p in pl["map"]:
            base = "own" if p["own"] else p["kind"]
            counts[base] = counts.get(base, 0) + 1
            points.append(("%s_%d" % (base, counts[base]), p))
        for slug, p in points:
            put("geo_location.dads_army_" + slug, p["km"],
                p["name"] if slug == "home" else "%s (%s)" % (p["name"], p["what"]), p["icon"], attrs={
                    # Far-off places (a hospital, Gran's house) have their own source, so the map
                    # can show them without zooming right out to fit them in.
                    "latitude": p["lat"], "longitude": p["lon"],
                    "source": "dads_army" if p["km"] <= MAP_NEAR_KM else "dads_army_far", "distance_km": p["km"],
                    "direction": p["dir"], "what": p["what"], "for": uses.get((p["lat"], p["lon"]), [])},
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
    return ran_out_event([now[i] for i in now if i in before and before[i]["total"] > 0 and now[i]["total"] <= 0])


def ran_out_event(gone):
    gone = sorted(gone, key=lambda r: r["name"].lower())
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


DASH_LIVE = """{% set a = 'sensor.dads_army_live' -%}
{% set rows = state_attr(a, 'rows') or [] -%}
{% if states(a) in ['unknown', 'unavailable'] -%}
Dads Army isn't sending updates. Check the app is running.
{%- elif not state_attr(a, 'enabled') -%}
Comes with warnings: turn them on in Dads Army under **HQ → Warnings**.
{%- elif not rows -%}
Nothing yet: Dads Army checks the feeds every 15 minutes.
{%- else -%}
{% for r in rows %}{{ r.dot }} {{ r.emoji }} **{{ r.name }}:** {{ r.text }}<br>
{% endfor %}<small>From the Environment Agency, the power networks, NESO, National Gas, Defra, NOAA and the Bank of England.</small>
{%- endif %}"""

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
- ⬆️ Raised to SEVERE because {{ state_attr(a, 'escalated_why') or "the stores wouldn't last 3 days" }}, so you'd be less able to cope
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

The level is the most serious of these. If it's SUBSTANTIAL and you'd be less able to cope, it goes up to SEVERE: when your food or water wouldn't last 3 days, when there's a power cut and you have no torches or power bank, or when the home is cold and you have no blankets or warm clothes. Only real danger makes it CRITICAL.

| Level | Warnings | At home (your sensors) | Stores |
|:--|:--|:--|:--|
| CRITICAL | Emergency Alert; severe flood warning | Gas, carbon monoxide or smoke alarm | |
| SEVERE | Red weather warning; flood warning | Power cut over 12 hours, or with the backup battery under 20%; coldest room under 9°C; warmest room 33°C or more; PM2.5 75 µg/m³ or more | |
| SUBSTANTIAL | Amber weather warning; a possible fire within 3 km | Power cut; water leak; coldest room under 12°C; warmest room 30°C or more; −10°C or colder, or 35°C or hotter, outside; PM2.5 55 or more | |
| MODERATE | Yellow weather warning; flood alert; a disaster near the UK; a possible fire nearby | Coldest room under 16°C; warmest room 27°C or more; −5°C or colder, or 30°C or hotter, outside; humidity 80% or more; internet down; PM2.5 35 or more | Food or water for under 3 days; an area of resilience missing its essentials |
| LOW | None of the above | | |

UKHSA advises heating the rooms you use to at least 18°C. Below that, Dads Army adds cold-weather advice even at LOW.

### The UK's own levels

The national threat level, set by MI5's Joint Terrorism Analysis Centre, uses the same five names: LOW (an attack is highly unlikely), MODERATE (possible, but not likely), SUBSTANTIAL (likely), SEVERE (highly likely) and CRITICAL (highly likely in the near future). You can check the current national level on MI5's website. Dads Army doesn't read it.

### Where the advice comes from

- **UK Government:** advice from Be Ready (gov.uk), Ofcom, the NHS, UKHSA, the Met Office, the Environment Agency, DEFRA, Ofgem, the Foreign Office and the Fire Kills campaign. It's put into plain statements, not quoted word for word.
- **SAS Survival Handbook:** John "Lofty" Wiseman's PLAN priorities (Protection, Location, Acquisition, Navigation), applied to a household. These are paraphrased, not quoted.
- **Fire & rescue services** and **Electricity networks (105):** their standard public advice.
- **Dads Army tip:** practical hints from the app itself.

Always follow official advice and the emergency services. In an emergency, call 999."""

# Resilience on the Home front: the ten areas two to a row, and what to do next.
DASH_RESILIENCE = """{% set a = 'sensor.dads_army_resilience' -%}
{% set ar = state_attr(a, 'areas') or [] -%}
{% set nx = state_attr(a, 'next_steps') or [] -%}
{% if not ar -%}
Dads Army isn't sending updates. Check the app is running.
{%- else -%}
## {{ states(a) }}% ready
<small>{{ state_attr(a, 'done') }} of {{ state_attr(a, 'total') }} recommendations done, across {{ ar | count }} areas</small>

| | Area | Ready | | Area | Ready |
|:-:|:--|--:|:-:|:--|--:|
{% for i in range(0, ar | count, 2) -%}
{%- set x = ar[i] -%}
{%- set y = ar[i + 1] if i + 1 < ar | count else none -%}
| {{ x.emoji }} | {{ x.short }} | {{ x.dot }} {{ x.pct }}% | {% if y %}{{ y.emoji }} | {{ y.short }} | {{ y.dot }} {{ y.pct }}%{% else %} | | {% endif %} |
{% endfor %}
{%- if nx %}

**Next:** {% for n in nx[:3] %}{{ n.emoji }} {{ n.title }}{% if not loop.last %} · {% endif %}{% endfor %}
{%- endif %}
{%- endif %}"""

DASH_RES_INTRO = """{% set a = 'sensor.dads_army_resilience' -%}
{% if state_attr(a, 'areas') -%}
## {{ states(a) }}% ready
{{ state_attr(a, 'done') }} of {{ state_attr(a, 'total') }} recommendations done.
{%- endif %}

Being ready isn't just food and water. Each area has things to have, know or do, mostly from the UK Government's **Be Ready** checklist, Ofcom and Fire Kills.

✅ done · 🔶 partly · ⬜ not yet · ➖ not for you

Dads Army ticks off what it can see in your stores, plan, checks and Home Assistant. Tick the rest off in Dads Army, or say they're not for you."""

DASH_RES_AREA = """{% set ar = (state_attr('sensor.dads_army_resilience', 'areas') or []) | selectattr('id', 'eq', 'AREA_ID') | list -%}
{% set ms = (state_attr('sensor.dads_army_resilience', 'measures') or {}).get('AREA_ID', []) -%}
{% if ar -%}
**{{ ar[0].dot }} {{ ar[0].pct }}% ready** · {{ ar[0].done }} of {{ ar[0].total }} done
{% for m in ms %}
- {{ {'done': '✅', 'partly': '🔶', 'na': '➖'}.get(m.s, '⬜') }} {% if m.s == 'na' %}~~{{ m.t }}~~{% else %}{{ m.t }}{% endif %}{% if m.p == 3 and m.s not in ('done', 'na') %} · **essential**{% endif %} <small>({{ m.l }})</small>
{%- endfor %}
{%- else -%}
Dads Army isn't sending updates. Check the app is running.
{%- endif %}"""

# Under the map: where to go for each kind of emergency, with what's happening now first.
DASH_PLACES = """{% set a = 'sensor.dads_army_places' -%}
{% set hz = state_attr(a, 'hazards') or [] -%}
{% if states(a) in ['unknown', 'unavailable'] -%}
Dads Army isn't sending updates. Check the app is running.
{%- elif not state_attr(a, 'located') -%}
Dads Army doesn't know where home is. Set your home's location in Home Assistant, or in Dads Army's warnings settings.
{%- else -%}
{% for h in hz | selectattr('active') %}
<ha-alert alert-type="warning" title="{{ h.emoji }} {{ h.what }}: now">{{ h.advice }}</ha-alert>
{% endfor %}
| | If it's… | Where you could go |
|:-:|:--|:--|
{% for h in hz -%}
| {{ h.emoji }} | {% if h.active %}**{{ h.what }}**{% else %}{{ h.what }}{% endif %} | {% for p in h.places[:2] %}{% if p.own %}⭐ {% endif %}{{ p.name }} <small>· {{ p.what }}, {{ p.short }}</small>{% if not loop.last %}<br>{% endif %}{% else %}<small>{{ 'Stay indoors, away from the trouble. Add family or friends in Dads Army.' if h.key == 'unrest' else 'Nothing close by in the list' }}</small>{% endfor %} |
{% endfor %}
<small>Possibilities, not official refuges: councils say where rest centres open at the time. ⭐ your own places. Place data © OpenStreetMap contributors.</small>
{%- endif %}"""

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

    def heading(text, icon=None, badges=None):
        h = {"type": "heading", "heading": text}
        if icon:
            h["icon"] = icon
        if badges:
            h["badges"] = badges
        return h

    # Home Assistant has no pop-up of its own (only add-ons like browser_mod), so the details
    # open on their own pages, with a back arrow.
    level = "sensor.dads_army_alert_level"
    go_why = {"action": "navigate", "navigation_path": "/%s/alert-level" % DASH_URL}
    go_levels = {"action": "navigate", "navigation_path": "/%s/alert-levels" % DASH_URL}
    go_res = {"action": "navigate", "navigation_path": "/%s/resilience" % DASH_URL}
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
        # Ten areas, not just food and water.
        {"type": "grid", "cards": [
            heading("Resilience", "mdi:shield-half-full"),
            dict({"type": "markdown", "content": DASH_RESILIENCE}, **full),
            tile("sensor.dads_army_hold_out", "Hold out", None, "mdi:shield-home"),
            tile("sensor.dads_army_supplies", "Daily supplies"),
            dict({"type": "tile", "entity": "sensor.dads_army_resilience", "name": "All recommendations",
                  "icon": "mdi:format-list-checks", "hide_state": True, "tap_action": go_res,
                  "icon_tap_action": go_res}, **full)]},
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
        # The wider picture: rivers, power cuts, the grid, gas, air, space weather, the pound.
        {"type": "grid", "cards": [
            heading("The wider picture", "mdi:earth"),
            dict({"type": "markdown", "content": DASH_LIVE}, **full)]},
        {"type": "grid", "cards": [
            heading("Days you could last", "mdi:chart-line"),
            dict({"type": "history-graph", "hours_to_show": 720, "entities": [
                {"entity": "sensor.dads_army_food_days", "name": "Food"},
                {"entity": "sensor.dads_army_water_days", "name": "Water"}]}, **full)]},
        # Places to go: Home Assistant's own map, with home and the places near it.
        {"type": "grid", "column_span": 2, "cards": [
            heading("Places to go", "mdi:map-marker-radius"),
            {"type": "map", "geo_location_sources": [
                {"source": "dads_army", "label_mode": "icon"},
                {"source": "dads_army_far", "label_mode": "icon", "focus": False}],
             "default_zoom": 13, "theme_mode": "auto", "grid_options": {"columns": "full", "rows": 7}},
            dict({"type": "markdown", "content": DASH_PLACES}, **full),
            dict({"type": "tile", "entity": "sensor.dads_army_places", "name": "Add family, friends and meeting places",
                  "icon": "mdi:map-marker-plus", "hide_state": True,
                  "tap_action": {"action": "navigate", "navigation_path": app_panel()},
                  "icon_tap_action": {"action": "navigate", "navigation_path": app_panel()}}, **full)]},
    ]
    return {"views": [{"title": "Home front", "path": "home-front", "type": "sections", "max_columns": 3,
                       "badges": [{"type": "entity", "entity": level, "name": "Alert level",
                                   "show_name": True, "tap_action": go_why},
                                  {"type": "entity", "entity": "sensor.dads_army_resilience", "name": "Resilience",
                                   "show_name": True, "tap_action": go_res},
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
                       "cards": [{"type": "markdown", "content": DASH_LEVELS_PAGE}]},
                      {"title": "Resilience", "path": "resilience", "subview": True, "type": "sections",
                       "max_columns": 3, "back_path": "/%s/home-front" % DASH_URL,
                       "sections": [{"type": "grid", "cards": [
                           heading("Resilience", "mdi:shield-half-full"),
                           dict({"type": "markdown", "content": DASH_RES_INTRO}, **full),
                           dict({"type": "button", "name": "Tick things off in Dads Army", "icon": "mdi:open-in-app",
                                 "show_state": False, "tap_action": {"action": "navigate",
                                                                     "navigation_path": app_panel()}}, **full)]}] + [
                           {"type": "grid", "cards": [
                               heading("%s %s" % (emoji, name)),
                               dict({"type": "markdown", "content": DASH_RES_AREA.replace("AREA_ID", aid)}, **full)]}
                           for aid, name, _, emoji in AREAS]}]}


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
    state = ha_state_new()
    HA_WAKE.set()  # first push straight away
    while True:
        HA_WAKE.wait(15 if state["failing"] else 30 if (todo_entity() or checks_entity()) else 60)
        HA_WAKE.clear()
        time.sleep(1)  # let a burst of changes settle
        refresh_ha_home()   # where home is, for Places when warnings are off (once an hour at most)
        ha_once(state)


def ha_state_new():
    return {"sent": {}, "failing": False, "last_full": None, "levels": None}


def ha_once(state):
    """One round: tell Home Assistant what's run out and what's changed. Returns True if it all got through."""
    probe = "sensor.dads_army_hold_out"
    sent = state["sent"]
    try:
        s = summary()
        now = stock_levels()
    except Exception:
        traceback.print_exc()
        return False
    if HA_REBASE.is_set():
        HA_REBASE.clear()
        state["levels"] = None
    # Things that have run out since last time, even while Home Assistant can't be reached: they're
    # kept until it can be told. Anything restocked or deleted before then is dropped, as is anything
    # still untold after a week.
    levels = state["levels"]
    if levels is not None:
        for i in now:
            if i in levels and levels[i]["total"] > 0 and now[i]["total"] <= 0:
                RAN_OUT_PENDING.setdefault(i, time.time())
    state["levels"] = now
    for i in list(RAN_OUT_PENDING):
        if i not in now or now[i]["total"] > 0 or time.time() - RAN_OUT_PENDING[i] > 7 * 86400:
            RAN_OUT_PENDING.pop(i, None)
    try:
        if RAN_OUT_PENDING:
            ev = ran_out_event([now[i] for i in RAN_OUT_PENDING])
            status = ha_call("POST", "/events/dads_army_ran_out", ev)
            if status not in (200, 201):
                raise RuntimeError("Home Assistant answered %s" % status)
            RAN_OUT_PENDING.clear()
        ents = ha_entities(s)
        full = state["last_full"] is None or time.monotonic() - state["last_full"] > 1800
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
        # Map points that are no longer wanted (home moved, a place deleted): take them off.
        geo_now = sorted(e for e in ents if e.startswith("geo_location.dads_army_"))
        with LOCK:
            geo_old = setting_raw("ha_geo_ids", []) or []
        if geo_old != geo_now:
            for eid in set(geo_old) - set(geo_now):
                ha_call("DELETE", "/states/" + eid)
                sent.pop(eid, None)
                HA_LAST.pop(eid, None)
            with tx() as db:
                set_setting_raw(db, "ha_geo_ids", geo_now)
        if full:
            state["last_full"] = time.monotonic()
        level_change(s["situation"])
        if state["failing"]:
            print("Home Assistant sensors: connected again", flush=True)
        state["failing"] = False
    except Exception as e:
        if not state["failing"]:
            print("Home Assistant sensors: can't update them yet (%s). Will keep trying." % e, flush=True)
        state["failing"], state["last_full"] = True, None
        sent.clear()
    if not state["failing"]:
        todo_tick(s)
        checks_tick()
        try:
            backfill_history()
        except Exception:
            traceback.print_exc()
    return not state["failing"]


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
    # Live information (1.11.0). Each is the whole country (or the whole network) in one go.
    "rivers": "https://environment.data.gov.uk/flood-monitoring/data/readings?latest&parameter=level",
    "river_stations": "https://environment.data.gov.uk/flood-monitoring/id/stations?parameter=level&_view=full",
    "power_ukpn": "https://ukpowernetworks.opendatasoft.com/api/explore/v2.1/catalog/datasets/ukpn-live-faults/exports/json",
    "power_nged": "https://connecteddata.nationalgrid.co.uk/dataset/d6672e1e-c684-4cea-bb78-c7e5248b62a2/resource/"
                  "292f788f-4339-455b-8cc0-153e14509d4d/download/power_outage_ext.csv",
    "power_ssen": "https://external.distribution.prd.ssen.co.uk/opendataportal-prd/v4/api/getallfaults",
    "power_npg": "https://northernpowergrid.opendatasoft.com/api/explore/v2.1/catalog/datasets/live-power-cuts-data/"
                 "exports/json",
    "grid": "https://data.elexon.co.uk/bmrs/api/v1/datasets/SYSWARN/stream?publishDateTimeFrom={start}"
            "&publishDateTimeTo={end}",
    "gas": "https://data.nationalgas.com/api/find-gas-data-download?applicableFor=Y&dateFrom={start}&dateTo={end}"
           "&dateType=GASDAY&latestFlag=Y&ids=PUBOBJ330,PUBOBJ333,PUBOBJ331,PUBOBJ332&type=CSV",
    "air": "https://uk-air.defra.gov.uk/assets/rss/current_site_levels.xml",
    "air_forecast": "https://uk-air.defra.gov.uk/assets/rss/forecast.xml",
    "space": "https://services.swpc.noaa.gov/products/noaa-scales.json",
    "pound": "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom={start}"
             "&Dateto=now&SeriesCodes=XUDLUSS,XUDLERS,IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N",
    # Credits (1.12.0): only when someone taps "Check GitHub for new names".
    "credits": "https://raw.githubusercontent.com/parkerveese-cloud/dads-army/main/dadsarmy/CREDITS.md",
    "contributors": "https://api.github.com/repos/parkerveese-cloud/dads-army/contributors?per_page=100",
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
    # Live information (1.12.0)
    ("rivers", "River levels near you (England)", True),
    ("power", "Power cuts near you", True),
    ("grid", "Electricity grid notices", True),
    ("gas", "Gas storage", True),
    ("air", "Air quality near you", True),
    ("space", "Space weather", True),
    ("pound", "The pound and Bank Rate", True),
]
WARN_SOURCE_NAMES = {"metoffice": "Met Office", "floods": "Environment Agency", "govalerts": "GOV.UK Emergency Alerts",
                     "gdacs": "GDACS", "fires": "NASA FIRMS", "ukhsa": "UKHSA", "who": "WHO",
                     "rivers": "Environment Agency", "power": "the power networks", "grid": "NESO / Elexon",
                     "gas": "National Gas", "air": "Defra UK-AIR", "space": "NOAA", "pound": "Bank of England"}
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
WARN_STATE = {"items": [], "news": [], "sources": {}, "checked_at": None, "region": "", "seen": {}, "live": {}}
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
    """Fetch a public feed. Nothing goes with it but Dads Army's name: no cookies, no referrer, no location.
    Asks for it compressed (some feeds are ten times smaller that way) and unpacks it here."""
    req = urllib.request.Request(url, headers={"User-Agent": FEED_UA, "Accept": "*/*", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
        packed = (r.headers.get("Content-Encoding") or "").lower() == "gzip"
    if len(data) > limit:
        raise ValueError("the feed is too big")
    if packed:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as g:
            data = g.read(limit + 1)
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


# -- Places to go -----------------------------------------------------------------
# Possible refuges and help points near home, for when staying put isn't safe. The UK list
# ships with the app (built from OpenStreetMap, see places/README.md), so finding them needs
# no internet and tells nobody where you live. Your own places (family, friends, meeting
# places) are added in the app.
PLACES_FILE = os.environ.get("DADSARMY_PLACES", os.path.join(APP_DIR, "places", "uk.tsv.gz"))
PLACE_KINDS = [
    # code in the file, kind, what it is, emoji, Home Assistant icon, how far to look (km)
    ("c", "community", "Community centre or hall", "🏛️", "mdi:home-group", 10),
    ("l", "leisure", "Leisure centre", "🏊", "mdi:pool", 15),
    ("b", "library", "Library", "📚", "mdi:library", 15),
    ("h", "hospital", "Hospital (emergency care)", "🏥", "mdi:hospital-building", 60),
    ("f", "fire", "Fire station", "🚒", "mdi:fire-truck", 20),
    ("p", "police", "Police station", "🚓", "mdi:police-badge", 20),
    ("a", "assembly", "Emergency assembly point", "📍", "mdi:account-group", 5),
    ("e", "high", "High ground", "⛰️", "mdi:image-filter-hdr", 15),
    ("k", "park", "Park or open space", "🌳", "mdi:tree", 5),
]
KIND_BY_CODE = {k[0]: k for k in PLACE_KINDS}
KIND = {k[1]: k for k in PLACE_KINDS}
OWN_KINDS = {"family": ("Family or friends", "🏠", "mdi:home-heart"),
             "meet": ("Meeting place", "🚩", "mdi:flag"),
             "other": ("Your place", "📌", "mdi:map-marker-star")}
# What could make you leave home, where to think about going, and the gist of what to do.
PLACE_HAZARDS = [
    ("flood", "Flooding", "🌊", ("high", "community", "leisure"),
     "Move to higher ground, away from the water, and never walk or drive through flood water. If you have to leave, "
     "councils open rest centres, often in leisure centres and community halls: check yours isn't in the flood area."),
    ("storm", "Storms and high winds", "🌬️", ("community", "leisure", "library"),
     "Stay indoors if your home is safe. If it isn't, go to a sturdy public building, keeping away from trees."),
    ("fire", "A wildfire", "🔥", ("community", "leisure", "library"),
     "Go away from the fire and the smoke, upwind if you can, to a built-up area. When there's a fire nearby, Dads "
     "Army leaves out places nearer to it than you are."),
    ("quake", "An earthquake", "🫨", ("park", "assembly"),
     "While it shakes: drop, cover and hold on. Afterwards, go to open ground away from buildings, walls and power "
     "lines."),
    ("unrest", "Civil unrest", "🚧", (),
     "Stay indoors, away from windows, and keep away from the trouble. If you have to leave, go to family or friends "
     "outside the area."),
    ("heat", "A heatwave", "🌡️", ("library", "leisure", "community"),
     "Libraries, leisure centres and community centres are cool places for the hottest part of the day. Many "
     "councils list cool spaces."),
    ("cold", "Cold, or a long power cut", "🧣", ("library", "community", "leisure"),
     "Libraries and community centres are warm places to go. Many councils list warm spaces in winter."),
    ("leave", "Having to leave home", "🎒", ("leisure", "community"),
     "Councils open rest centres when people have to leave, often in leisure centres, schools and community halls. "
     "Local radio will say where. Or go to family or friends."),
    ("medical", "A medical emergency", "🏥", ("hospital",),
     "Call 999 in an emergency, or 111 if it isn't. A&E is for serious injuries and illnesses."),
]
HAZARD_KEYS = [h[0] for h in PLACE_HAZARDS]
NEARBY_KM = 60
MAP_NEAR_KM = 20   # the dashboard map zooms to fit places this close; further ones are there if you zoom out
DIR_SHORT = {"north": "N", "north-east": "NE", "east": "E", "south-east": "SE", "south": "S", "south-west": "SW",
             "west": "W", "north-west": "NW", "": ""}
PLACES_CACHE = {"key": None, "rows": [], "error": "", "built": ""}
MAX_OWN_PLACES = 40


def load_places(home):
    """The UK list's places within NEARBY_KM of home, nearest first. Read again only if home moves."""
    key = (round(home["lat"], 3), round(home["lon"], 3))
    if PLACES_CACHE["key"] == key:
        return PLACES_CACHE["rows"]
    rows, built, error = [], "", ""
    dlat = NEARBY_KM / 111.0
    dlon = NEARBY_KM / (111.0 * max(0.2, math.cos(math.radians(home["lat"]))))
    try:
        with gzip.open(PLACES_FILE, "rt", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    m = re.search(r"Built (\d{4}-\d{2}-\d{2})", line)
                    built = m.group(1) if m else built
                    continue
                p = line.rstrip("\n").split("\t")
                if len(p) < 4 or p[2] not in KIND_BY_CODE:
                    continue
                lat, lon = float(p[0]), float(p[1])
                if abs(lat - home["lat"]) > dlat or abs(lon - home["lon"]) > dlon:
                    continue
                d = km_between(home["lat"], home["lon"], lat, lon)
                if d <= NEARBY_KM:
                    rows.append((d, lat, lon, KIND_BY_CODE[p[2]][1], p[3], p[4] if len(p) > 4 else ""))
    except (OSError, ValueError, EOFError) as e:
        error = "The list of places couldn't be read (%s)" % str(e)[:80]
    rows.sort()
    PLACES_CACHE.update(key=key, rows=rows, error=error, built=built)
    return rows


COORD_PATTERNS = [
    re.compile(r"mlat=(-?\d+(?:\.\d+)?)&mlon=(-?\d+(?:\.\d+)?)"),
    re.compile(r"#map=\d+/(-?\d+(?:\.\d+)?)/(-?\d+(?:\.\d+)?)"),
    re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)"),
    re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)"),
    re.compile(r"[?&](?:q|ll|query|daddr|destination)=(-?\d+(?:\.\d+)?)(?:,|%2C)\s*(-?\d+(?:\.\d+)?)"),
    re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$"),
]


def parse_where(text):
    """Coordinates from "54.48, -0.62" or a link from Google, Apple or OpenStreetMap maps."""
    t = (text or "").strip()
    for rx in COORD_PATTERNS:
        m = rx.search(t)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return round(lat, 5), round(lon, 5)
    raise ApiError(400, "Couldn't find a location in that. Paste a map link, or type it like 54.48, -0.62 "
                        "(long-press the place in your maps app to get it).")


def clean_places(body):
    rows = body.get("places")
    if not isinstance(rows, list):
        raise ApiError(400, "Places should be a list")
    if len(rows) > MAX_OWN_PLACES:
        raise ApiError(400, "That's too many places (%d at most)" % MAX_OWN_PLACES)
    out, n = [], 0
    for r in rows:
        if not isinstance(r, dict):
            raise ApiError(400, "Each place needs a name and where it is")
        name = clean_text(r.get("name"), 80)
        if not name:
            raise ApiError(400, "Give each place a name")
        if r.get("where"):
            lat, lon = parse_where(clean_text(r.get("where"), 600))
        else:
            if r.get("lat") in (None, "") or r.get("lon") in (None, ""):
                raise ApiError(400, "Where is %s? Paste a map link or the coordinates." % name)
            try:
                lat = clean_num(r.get("lat"), None, -90, 90, "Latitude", 5)
                lon = clean_num(r.get("lon"), None, -180, 180, "Longitude", 5)
            except ApiError:
                raise ApiError(400, "Those coordinates for %s aren't on the map" % name)
        kind = r.get("kind") if isinstance(r.get("kind"), str) and r.get("kind") in OWN_KINDS else "other"
        hazards = r.get("hazards") if isinstance(r.get("hazards"), list) else []
        hz = [h for h in hazards if isinstance(h, str) and h in HAZARD_KEYS]
        n += 1
        out.append({"id": n, "name": name, "lat": round(lat, 5), "lon": round(lon, 5), "kind": kind, "hazards": hz,
                    "notes": clean_text(r.get("notes"), 300)})
    return out


def own_places():
    raw = setting_raw("places", [])
    try:
        return clean_places({"places": raw if isinstance(raw, list) else []})
    except ApiError:
        return []


def _km_words(d):
    return ("%.1f km" % d) if d < 10 else ("%d km" % int(round(d)))


def _place(home, kind, name, lat, lon, own=None, ele=""):
    d = km_between(home["lat"], home["lon"], lat, lon)
    if own:
        what, emoji, icon = OWN_KINDS[own["kind"]]
    else:
        what, emoji, icon = KIND[kind][2], KIND[kind][3], KIND[kind][4]
        if kind == "high" and ele:
            what = "High ground, %s m" % ele
    p = {"kind": own["kind"] if own else kind, "what": what, "emoji": emoji, "icon": icon, "name": name,
         "lat": lat, "lon": lon, "km": round(d, 1), "dir": compass(home["lat"], home["lon"], lat, lon) if d >= 0.05 else "",
         "own": bool(own), "map": "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=16/%s/%s" % (lat, lon, lat, lon)}
    p["text"] = "%s · %s%s" % (what, _km_words(d), (" " + p["dir"]) if p["dir"] else "")
    p["short"] = (_km_words(d) + " " + DIR_SHORT[p["dir"]]).strip()
    if own:
        p["id"] = own["id"]
        p["hazards"] = own["hazards"]
        p["notes"] = own["notes"]
    return p


def active_hazards(s, items):
    """Which of the hazards are happening, from the warnings in force and the alert level's reasons."""
    keys = set(r["key"] for r in s["situation"]["reasons"])
    act = []
    for w in items:
        k, t = w.get("kind"), (w.get("title") or "").lower()
        if k == "flood" and (w.get("severity") or 0) >= 2:
            act.append("flood")
        if k == "river" and (w.get("severity") or 0) >= 2:   # a river higher than it's been for years
            act.append("flood")
        if k == "fire":
            act.append("fire")
        if k == "weather" and (w.get("severity") or 0) >= 2:
            if "wind" in t or "storm" in t:
                act.append("storm")
            if "heat" in t:
                act.append("heat")
            if "snow" in t or "ice" in t or "cold" in t:
                act.append("cold")
    if keys & {"hot_indoor", "hot_out"}:
        act.append("heat")
    if keys & {"cold_indoor", "freezing_out", "power_cut", "power_cut_long", "battery_low"}:
        act.append("cold")
    if keys & {"severe_flood", "emergency_alert"}:
        act.append("leave")
    return [h for h in HAZARD_KEYS if h in act]


def places_view(s):
    """Where to go for each hazard, what to put on the map, and what Dads Army knows."""
    cfg = warn_cfg()
    home = home_location(cfg)
    own = own_places()
    out = {"home": home, "own": [], "hazards": [], "help": [], "map": [], "active": [], "error": "",
           "built": PLACES_CACHE["built"], "count": 0}
    if not home:
        out["own"] = own
        return out
    rows = load_places(home)
    out["error"], out["built"] = PLACES_CACHE["error"], PLACES_CACHE["built"]
    items = warn_public()["items"]
    active = active_hazards(s, items)
    out["active"] = active
    fires = [(w["lat"], w["lon"]) for w in items if w.get("kind") == "fire" and w.get("lat") is not None]
    floods = [(w["lat"], w["lon"]) for w in items if w.get("kind") == "flood" and (w.get("severity") or 0) >= 2
              and w.get("lat") is not None]
    mine = [_place(home, None, o["name"], o["lat"], o["lon"], own=o) for o in own]
    mine.sort(key=lambda p: p["km"])
    out["own"] = mine

    def away(lat, lon, threats):
        """Further from every one of these than home is."""
        return all(km_between(lat, lon, a, b) >= km_between(home["lat"], home["lon"], a, b) + 1.0
                   for a, b in threats)

    def nearest(kind, n, threats=()):
        got = []
        for d, lat, lon, k, name, ele in rows:
            if k != kind or d > KIND[kind][5]:
                continue
            if threats and not away(lat, lon, threats):
                continue
            got.append(_place(home, kind, name, lat, lon, ele=ele))
            if len(got) >= n:
                break
        return got

    for key, what, emoji, kinds, advice in PLACE_HAZARDS:
        threats = fires if key == "fire" else floods if key in ("flood", "leave") else ()
        firsts, rest = [], []
        for kind in kinds:
            got = nearest(kind, 2, threats)
            firsts += got[:1]
            rest += got[1:]
        picks = [p for p in mine if key in p["hazards"]] + (firsts + sorted(rest, key=lambda p: p["km"]))[:3]
        out["hazards"].append({"key": key, "what": what, "emoji": emoji, "advice": advice, "active": key in active,
                               "avoiding": ("the fire" if key == "fire" and fires else
                                            "the flood" if key in ("flood", "leave") and floods else ""),
                               "places": picks})
    out["help"] = nearest("fire", 1) + nearest("police", 1) + nearest("hospital", 1)
    # The map: home, your own places, what's suggested, and help nearby. No repeats.
    seen, pts = set(), []
    for p in mine + [p for h in out["hazards"] for p in h["places"]] + out["help"]:
        k = (round(p["lat"], 4), round(p["lon"], 4))
        if k not in seen:
            seen.add(k)
            pts.append(p)
    out["map"] = pts[:30]
    out["count"] = len(out["map"])
    return out


@route("PUT", "/api/places")
def api_places(body, query):
    """Your own places: family, friends, meeting places. Replaces the list."""
    places = clean_places(body)
    with tx() as db:
        set_setting_raw(db, "places", places)
        add_log("plan", "", "Places to go updated (%d of your own)" % len(places))
    HA_WAKE.set()
    return {"places": places}


@route("POST", "/api/places/restore")
def api_places_restore(body, query):
    """Undo for places: put the list back as it was."""
    return api_places(body, query)


@route("POST", "/api/places/where")
def api_places_where(body, query):
    """Check a map link or coordinates as you type them in."""
    lat, lon = parse_where(clean_text(body.get("where"), 600))
    home = home_location(warn_cfg())
    out = {"lat": lat, "lon": lon}
    if home:
        out["km"] = round(km_between(home["lat"], home["lon"], lat, lon), 1)
        out["dir"] = compass(home["lat"], home["lon"], lat, lon)
    return out


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


# -- Live information (1.12.0) -------------------------------------------------------------
# The wider picture: rivers near home, power cuts nearby, the electricity grid, gas storage, air
# quality, space weather and the pound. Like the warnings, each feed is public and fetched whole
# (all of England's rivers, every power cut a network has): nothing about you is sent, and Dads Army
# picks out what's near home itself. Each turns into a reading for the app and, when something's
# up, a warning. Trend warnings ("emptying faster than last year") come from the feeds' own history.
LIVE_KEYS = ("rivers", "power", "grid", "gas", "air", "space", "pound")
LIVE_EVERY = {"rivers": 14 * 60, "power": 14 * 60, "grid": 14 * 60, "gas": 3 * 3600, "air": 55 * 60,
              "space": 29 * 60, "pound": 6 * 3600}     # seconds between fetches: no more often than they change
LIVE_CREDIT = {
    "rivers": "Environment Agency flood and river level data from the real-time data API (Beta), under the Open "
              "Government Licence",
    "power": "Live power cut data from UK Power Networks, National Grid Electricity Distribution, SSEN and Northern "
             "Powergrid, under their open data licences",
    "grid": "System warnings from Elexon's BMRS (Insights), issued by NESO",
    "gas": "GB gas storage from the National Gas data portal",
    "air": "Daily Air Quality Index from Defra's UK-AIR, under the Open Government Licence",
    "space": "Space weather scales from NOAA's Space Weather Prediction Center",
    "pound": "Exchange rates and Bank Rate from the Bank of England database, under the Open Government Licence",
}
RIVER_KM = 10          # rivers this close count as near home
RIVER_KEEP_KM = 30     # station details kept for this far, so a small move of home doesn't need a refetch
POWER_KM = 10          # power cuts listed this far away
POWER_NEAR_KM = 2      # ...and a warning this close
AIR_KM = 40
DAQI_BANDS = [(3, "Low"), (6, "Moderate"), (9, "High"), (10, "Very high")]
G_WORDS = {0: "Quiet", 1: "Minor storm (G1)", 2: "Moderate storm (G2)", 3: "Strong storm (G3)",
           4: "Severe storm (G4)", 5: "Extreme storm (G5)"}


def _f0(v):
    """A number from a feed, or None. Feeds send numbers, strings, '', null and lists."""
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, bool) or v in (None, ""):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _first(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def _iso_age_h(s, now):
    d = parse_when(s) if s else None
    return (now - d).total_seconds() / 3600.0 if d else None


def daqi_band(i):
    for top, name in DAQI_BANDS:
        if i <= top:
            return name
    return "Very high"


def dms(text):
    """'55&deg;47&acute;31.78&quot;N    3&deg;14&acute;34.44&quot;W' -> (55.792, -3.243)."""
    t = htmllib.unescape(text or "")
    found = re.findall(r"(\d+)\s*°\s*(\d+)\D{1,3}?([\d.]+)\D{0,3}?([NSEW])", t)
    if len(found) < 2:
        return None
    out = []
    for d, m, s, h in found[:2]:
        v = int(d) + int(m) / 60.0 + float(s) / 3600.0
        out.append(-v if h in "SW" else v)
    return out[0], out[1]


# -- Rivers ---------------------------------------------------------------------------------
def parse_river_stations(data, home):
    """Stations measuring river level within RIVER_KEEP_KM of home, with their usual range."""
    doc = json.loads(data.decode("utf-8"))
    out = []
    for s in doc.get("items") or []:
        if not isinstance(s, dict):
            continue
        lat, lon = _f0(s.get("lat")), _f0(s.get("long"))
        if lat is None or lon is None:
            continue
        d = km_between(home["lat"], home["lon"], lat, lon)
        if d > RIVER_KEEP_KM:
            continue
        ms = s.get("measures")
        ms = ms if isinstance(ms, list) else [ms] if isinstance(ms, dict) else []
        stage = [m for m in ms if isinstance(m, dict) and m.get("qualifier") == "Stage" and m.get("parameter") == "level"]
        if not stage:
            continue
        sc = s.get("stageScale") if isinstance(s.get("stageScale"), dict) else {}
        recent = sc.get("highestRecent") if isinstance(sc.get("highestRecent"), dict) else {}
        out.append({"id": plain(_first(s.get("notation")), 40), "name": plain(_first(s.get("label")), 80),
                    "river": plain(_first(s.get("riverName")), 80), "town": plain(_first(s.get("town")), 80),
                    "lat": round(lat, 5), "lon": round(lon, 5), "measure": str(stage[0].get("@id") or ""),
                    "unit": plain(stage[0].get("unitName"), 10), "high": _f0(sc.get("typicalRangeHigh")),
                    "low": _f0(sc.get("typicalRangeLow")), "recent_high": _f0(recent.get("value"))})
    return out


def parse_river_readings(data):
    """{measure id: (value, when)} for every level measure in England."""
    out = {}
    for r in json.loads(data.decode("utf-8")).get("items") or []:
        if isinstance(r, dict) and isinstance(r.get("measure"), str):
            v = _f0(r.get("value"))
            if v is not None:
                out[r["measure"]] = (v, r.get("dateTime") or "")
    return out


def river_state(st, v):
    hi, lo = st.get("high"), st.get("low")
    if hi is None:
        return "unknown"
    # A few stations measure from a different datum than their range: don't compare those.
    if abs(v - hi) > max(10.0, 5 * abs(hi)):
        return "unknown"
    if st.get("recent_high") is not None and v >= st["recent_high"]:
        return "very_high"
    if v > hi:
        return "high"
    if lo is not None and v < lo:
        return "low"
    return "normal"


RIVER_WORDS = {"very_high": "Higher than it's been for years", "high": "Above its normal range",
               "normal": "Normal", "low": "Below its normal range", "unknown": "No usual range to compare"}


def rivers_live(stations, levels, hist, home, now):
    """Readings for the rivers near home, and warnings when one's above its normal range."""
    t = time.time()
    rows, items = [], []
    for st in stations:
        d = km_between(home["lat"], home["lon"], st["lat"], st["lon"])
        lv = levels.get(st["measure"])
        if d > RIVER_KM or not lv:
            continue
        v, when = lv
        age = _iso_age_h(when, now)
        if age is None or age > 48:
            continue      # a gauge that's stopped reporting
        h = [p for p in hist.get(st["id"], []) if t - p[0] < 48 * 3600 and p[1] is not None]
        if not h or h[-1][0] < t - 300 or h[-1][1] != v:
            h.append([t, v])
        hist[st["id"]] = h[-200:]
        before = [p for p in h if 2 * 3600 <= t - p[0] <= 6 * 3600]
        trend = "steady"
        if before:
            change = v - before[-1][1]
            trend = "rising" if change >= 0.05 else "falling" if change <= -0.05 else "steady"
        state = river_state(st, v)
        pct = None
        if state != "unknown" and st.get("low") is not None and st["high"] > st["low"]:
            pct = int(round(100.0 * (v - st["low"]) / (st["high"] - st["low"])))
        place = st["river"] or st["name"]
        where = "%s at %s" % (st["river"], st["name"]) if st["river"] else st["name"]
        row = {"id": st["id"], "name": st["name"], "river": st["river"], "where": where, "km": round(d, 1),
               "dir": DIR_SHORT.get(compass(home["lat"], home["lon"], st["lat"], st["lon"]), ""),
               "level": round(v, 2), "unit": st["unit"], "high": st["high"], "low": st["low"], "pct": pct,
               "state": state, "trend": trend, "when": when, "lat": st["lat"], "lon": st["lon"],
               "url": "https://check-for-flooding.service.gov.uk/station/%s" % st["id"]}
        rows.append(row)
        if state in ("high", "very_high"):
            sev = 2 if state == "very_high" else 1
            items.append({"id": "river:%s:%s" % (st["id"], state), "source": "rivers", "kind": "river",
                          "severity": sev, "level": "River high",
                          "title": "%s: %s%s" % (where, RIVER_WORDS[state].lower(), ", and rising" if trend == "rising" else ""),
                          "text": "The %s is at %s m, against a usual top of %s m. %s" % (
                              place, fq(round(v, 2)), fq(st["high"]),
                              "Keep an eye on flood warnings, and know how you'd get out if it rises further."),
                          "area": st["town"] or st["name"], "distance_km": int(round(d)), "when": "",
                          "url": row["url"], "issued": iso_utc(parse_when(when) or now)})
    rows.sort(key=lambda r: r["km"])
    order = {"very_high": 0, "high": 1}
    top = sorted(rows, key=lambda r: (order.get(r["state"], 2), r["km"]))
    return items, {"stations": rows[:6], "high": sum(1 for r in rows if r["state"] in order),
                   "count": len(rows), "worst": top[0] if top else None}


# -- Power cuts -----------------------------------------------------------------------------
def _cut(dno, ref, lat, lon, customers, planned, etr, started, where):
    return {"dno": dno, "ref": plain(ref, 40), "lat": lat, "lon": lon, "customers": int(customers or 0),
            "planned": bool(planned), "etr": plain(etr, 30), "started": plain(started, 30), "where": plain(where, 80)}


def parse_ukpn(data):
    out = []
    for r in json.loads(data.decode("utf-8")) or []:
        if not isinstance(r, dict):
            continue
        kind = (r.get("powercuttype") or "").strip()
        if kind not in ("Planned", "Unplanned") or r.get("statusid") == 5:
            continue   # restored, or a roll-up of others
        g = r.get("geopoint") if isinstance(r.get("geopoint"), dict) else {}
        lat, lon = _f0(g.get("lat")), _f0(g.get("lon"))
        if lat is None or lon is None:
            continue
        out.append(_cut("UK Power Networks", r.get("incidentreference"), lat, lon,
                        r.get("nocustomeraffected") or r.get("noplannedcustomers"), kind == "Planned",
                        r.get("estimatedrestorationdate") or r.get("incidenttypetbcestimatedfriendlydescription"),
                        r.get("receiveddate") or r.get("planneddate"), r.get("postcodesaffected")))
    return out


def parse_nged(data, now):
    out = []
    for r in csv.DictReader(io.StringIO(data.decode("utf-8-sig", "replace"))):
        status = (r.get("Status") or "").lower()
        if "restor" in status or "complete" in status or (r.get("Resource Status") or "").upper() == "CANC":
            continue
        lat, lon = _f0(r.get("Location Latitude")), _f0(r.get("Location Longitude"))
        if lat is None or lon is None:
            continue
        planned = (r.get("Planned") or "").lower() == "true"
        age = _iso_age_h(r.get("Start Time"), now)
        if planned and age is not None and age > 48:
            continue   # an old planned job still listed
        n = (_f0(r.get("Confirmed Off")) or 0) + (_f0(r.get("Predicted Off")) or 0)
        out.append(_cut("National Grid", r.get("Incident ID"), lat, lon, n, planned, r.get("ETR"), r.get("Start Time"),
                        (r.get("Postcodes") or "").split(",")[0]))
    return out


def parse_ssen(data):
    out = []
    for r in (json.loads(data.decode("utf-8")) or {}).get("faults") or []:
        if not isinstance(r, dict):
            continue
        loc = r.get("location") if isinstance(r.get("location"), dict) else {}
        lat, lon = _f0(loc.get("latitude")), _f0(loc.get("longitude"))
        if lat is None or lon is None:
            continue
        areas = r.get("affectedAreas") if isinstance(r.get("affectedAreas"), list) else []
        out.append(_cut("SSEN", r.get("reference"), lat, lon, r.get("customerCount"), r.get("type") == "PSI",
                        r.get("estimatedRestorationTimeUtc"), r.get("loggedAtUtc"),
                        r.get("title") or (areas[0] if areas else "")))
    return out


def parse_npg(data):
    by = {}
    for r in json.loads(data.decode("utf-8")) or []:
        if not isinstance(r, dict) or not r.get("reference"):
            continue
        lat, lon = _f0(r.get("lat")), _f0(r.get("lng"))
        if lat is None or lon is None or r["reference"] in by:
            continue
        pc = r.get("postcode") if isinstance(r.get("postcode"), list) else []
        by[r["reference"]] = _cut("Northern Powergrid", r["reference"], lat, lon,
                                  (_f0(r.get("totalconfirmedpowercut")) or 0) + (_f0(r.get("totalpredictedpowercut")) or 0),
                                  "planned" in (r.get("natureofoutage") or "").lower(),
                                  r.get("estimatedtimetillresolution"), r.get("loggedtime"),
                                  re.sub(r"\s+", " ", pc[0]) if pc else "")
    return list(by.values())


POWER_FEEDS = (("power_ukpn", "ukpn"), ("power_nged", "nged"), ("power_ssen", "ssen"), ("power_npg", "npg"))


def when_words(s):
    """'2026-11-14T23:00:00' -> 'about 23:00' (today) or '15 Nov 03:30'."""
    try:   # times with no zone (UK Power Networks, National Grid) are UK local time already
        d = dt.datetime.fromisoformat((s or "").strip().replace("Z", "+00:00")[:25])
    except ValueError:
        return plain(s, 30)
    local = d.astimezone().replace(tzinfo=None) if d.tzinfo else d
    return local.strftime("%H:%M") if local.date() == dt.date.today() else "%d %s %s" % (
        local.day, local.strftime("%b"), local.strftime("%H:%M"))


def power_live(cuts, home):
    rows, items = [], []
    for c in cuts:
        d = km_between(home["lat"], home["lon"], c["lat"], c["lon"])
        if d > POWER_KM:
            continue
        c = dict(c, km=round(d, 1), dir=DIR_SHORT.get(compass(home["lat"], home["lon"], c["lat"], c["lon"]), ""))
        c["text"] = "%s%s, %s %s%s" % ("Planned: " if c["planned"] else "", c["where"] or c["dno"], _km_words(d), c["dir"],
                                       (" · back by " + when_words(c["etr"])) if c["etr"] and not c["planned"] else "")
        rows.append(c)
        if d <= POWER_NEAR_KM:
            homes = ("%d homes" % c["customers"]) if c["customers"] > 1 else "a home" if c["customers"] == 1 else ""
            if c["planned"]:
                title = "Planned power cut %s away" % _km_words(d)
                text = ("%s plans to switch the power off nearby%s. If it's your street, they'll have written to "
                        "you. Charge phones and power banks before it starts." % (c["dno"], (" (" + homes + ")") if homes else ""))
            else:
                title = "Power cut %s away" % _km_words(d)
                text = ("%s is working on a power cut %s %s%s%s. If your power's off, call 105 to report it or "
                        "check for updates." % (c["dno"], _km_words(d), c["dir"], (", affecting " + homes) if homes else "",
                                                (", and expects it back by " + when_words(c["etr"])) if c["etr"] else ""))
            items.append({"id": "power:%s:%s" % (c["dno"], c["ref"]), "source": "power", "kind": "power",
                          "severity": 1 if c["planned"] else 2, "level": "Planned" if c["planned"] else "Power cut",
                          "title": title, "text": text, "area": c["where"], "distance_km": int(round(d)),
                          "when": "", "url": "https://www.powercut105.com/", "issued": iso_utc(parse_when(c["started"]) or dt.datetime.now(dt.timezone.utc))})
    rows.sort(key=lambda r: r["km"])
    unplanned = [r for r in rows if not r["planned"]]
    return items, {"cuts": rows[:6], "count": len(unplanned), "planned": len(rows) - len(unplanned),
                   "homes": sum(r["customers"] for r in unplanned), "near": sum(1 for r in unplanned if r["km"] <= POWER_NEAR_KM)}


# -- The electricity grid -----------------------------------------------------------------------
GRID_PERIOD = re.compile(r"from\s+(\d{1,2})[:.]?(\d{2})\s*hrs?\s+(?:to|until)\s+(\d{1,2})[:.]?(\d{2})\s*hrs?\s+on\s+\w+\s+"
                         r"(\d{1,2})/(\d{1,2})/(\d{4})", re.I)


def grid_text(t):
    return re.sub(r"[ \t]+", " ", (t or "").replace("\r\\n", "\n").replace("\\n", "\n").replace("\r", "")).strip()


def parse_grid(data, now):
    """NESO's notices that matter to households: electricity margin notices, capacity market notices, and
    any warning of demand control (planned rota power cuts). Cancelled or finished ones drop out."""
    rows = json.loads(data.decode("utf-8"))
    rows = rows.get("data") if isinstance(rows, dict) else rows
    notices = []
    for r in sorted([r for r in rows or [] if isinstance(r, dict)], key=lambda r: r.get("publishTime") or ""):
        kind = (r.get("warningType") or "").upper()
        text = grid_text(r.get("warningText"))
        up = text.upper()
        when = parse_when(r.get("publishTime"))
        if not when or when > now + dt.timedelta(minutes=5):
            continue
        if "TEST" in up or "FLEXIBIL" in up:
            continue   # voltage reduction tests and the Demand Flexibility Service aren't warnings
        if "DEMAND CONTROL IMMINENT" in up or "HIGH RISK OF DEMAND REDUCTION" in up:
            key = "demand"
        elif kind == "ELECTRICITY MARGIN NOTICE" or "ELECTRICITY MARGIN NOTICE" in up:
            key = "emn"
        elif kind == "CAPACITY MARKET NOTICE" or "CAPACITY MARKET NOTICE" in up:
            key = "cmn"
        else:
            continue
        if "CANCEL" in up:
            notices = [n for n in notices if n["key"] != key]
            continue
        end = None
        m = GRID_PERIOD.search(text)
        if m:
            try:
                end = dt.datetime(int(m.group(7)), int(m.group(6)), int(m.group(5)), int(m.group(3)) % 24, int(m.group(4)))
                start = end.replace(hour=int(m.group(1)) % 24, minute=int(m.group(2)))
                if end <= start:
                    end += dt.timedelta(days=1)
            except ValueError:
                end = None
        notices.append({"key": key, "when": when, "end": end, "text": text, "period": m.group(0) if m else ""})
    local_now = now.astimezone().replace(tzinfo=None)   # the periods are in UK time
    items = []
    for n in notices:
        if (n["end"] and n["end"] < local_now) or (not n["end"] and now - n["when"] > dt.timedelta(hours=12)):
            continue
        if n["key"] == "demand":
            sev, title = 2, "Electricity grid: warning of possible planned power cuts"
            text = ("NESO, which runs Britain's electricity system, has warned that it may have to cut power to some "
                    "areas in turn (demand control). Charge phones and power banks, and keep torches handy.")
        elif n["key"] == "emn":
            sev, title = 1, "Electricity margin notice: the grid is short of spare power"
            text = ("NESO is asking power stations for more electricity %s. It's a call for more supply, not a power "
                    "cut, and they're usually met. A good time to charge power banks." % (n["period"] or "for a few hours"))
        else:
            sev, title = 1, "Capacity market notice: the grid expects to be tight"
            text = ("NESO expects less spare electricity than it likes in the next few hours. It's an early warning to "
                    "power stations, not a power cut.")
        items.append({"id": "grid:%s:%s" % (n["key"], iso_utc(n["when"])), "source": "grid", "kind": "grid",
                      "severity": sev, "level": "Grid notice", "title": title, "text": text, "area": "Great Britain",
                      "when": n["period"], "url": "https://bmrs.elexon.co.uk/system-warnings", "issued": iso_utc(n["when"])})
    status = "demand" if any(i["severity"] == 2 for i in items) else "notice" if items else "normal"
    return items, {"status": status, "notices": len(items),
                   "text": {"normal": "Normal: no notices", "notice": items[0]["title"] if items else "",
                            "demand": "Warning of possible planned power cuts"}[status]}


# -- Gas storage --------------------------------------------------------------------------------
GAS_ITEMS = {"stock level": "stock", "available capacity": "space", "inflows": "in", "outflows": "out"}


def parse_gas(data):
    """{date: {stock, space, in, out}} in GWh, from the National Gas data portal's CSV."""
    days = {}
    for r in csv.DictReader(io.StringIO(data.decode("utf-8-sig", "replace"))):
        name = (r.get("Data Item") or "").lower()
        key = next((v for k, v in GAS_ITEMS.items() if k in name), None)
        v = _f0(r.get("Value"))
        try:
            d, m, y = (r.get("Applicable For") or "").split("/")
            day = dt.date(int(y), int(m), int(d))
        except ValueError:
            continue
        if key and v is not None:
            days.setdefault(day, {})[key] = v / 1e6
    return days


def gas_stats(days):
    """How full, and the net draw a day over the last two weeks (positive = emptying)."""
    full = sorted(d for d, v in days.items() if "stock" in v and "space" in v)
    if not full:
        return None
    last = full[-1]
    stock, space = days[last]["stock"], days[last]["space"]
    pct = 100.0 * stock / (stock + space) if stock + space > 0 else 0.0
    back = [d for d in full if d <= last - dt.timedelta(days=14)]
    draw = (days[back[-1]]["stock"] - stock) / float((last - back[-1]).days) if back else None
    return {"day": last, "gwh": stock, "pct": pct, "draw": draw}


def gas_live(now_days, year_ago_days, today):
    s = gas_stats(now_days)
    if not s:
        raise ValueError("no storage figures in the feed")
    ly = gas_stats(year_ago_days) if year_ago_days else None
    items = []
    reading = {"pct": round(s["pct"], 1), "gwh": int(round(s["gwh"])), "date": s["day"].isoformat(),
               "draw_gwh_day": round(s["draw"], 1) if s["draw"] is not None else None,
               "year_ago_pct": round(ly["pct"], 1) if ly else None,
               "year_ago_draw": round(ly["draw"], 1) if ly and ly["draw"] is not None else None}
    trend = "steady"
    if s["draw"] is not None:
        trend = "emptying" if s["draw"] > 5 else "filling" if s["draw"] < -5 else "steady"
    reading["trend"] = trend
    winter = today.month in (11, 12, 1, 2, 3)
    if (s["draw"] is not None and ly and ly["draw"] is not None and s["draw"] > 20
            and s["draw"] > 1.5 * max(ly["draw"], 5) and s["pct"] < ly["pct"]):
        items.append({"id": "gas:faster:%s" % today.isoformat()[:7], "source": "gas", "kind": "gas", "severity": 1,
                      "level": "Two-week trend", "title": "Gas storage is emptying faster than this time last year",
                      "text": "Britain's gas storage is %d%% full, against %d%% a year ago, and over the last two weeks "
                              "it's been drawn down by about %d GWh a day, against %d a year ago. Storage is a small "
                              "part of Britain's gas supply, so it's a sign to watch rather than a worry on its own." % (
                                  round(s["pct"]), round(ly["pct"]), round(s["draw"]), round(max(ly["draw"], 0))),
                      "area": "Great Britain", "when": "", "url": "https://data.nationalgas.com/",
                      "issued": iso_utc(dt.datetime.now(dt.timezone.utc))})
    if winter and s["pct"] < 10:
        items.append({"id": "gas:low:%s" % today.isoformat()[:7], "source": "gas", "kind": "gas", "severity": 1,
                      "level": "Gas storage", "title": "Gas storage is low: %d%% full" % round(s["pct"]),
                      "text": "Britain's gas storage is nearly empty for the time of year. If the gas network asks "
                              "people to use less, keep the rooms you use warm and have blankets and warm clothes ready.",
                      "area": "Great Britain", "when": "", "url": "https://data.nationalgas.com/",
                      "issued": iso_utc(dt.datetime.now(dt.timezone.utc))})
    return items, reading


# -- Air quality ---------------------------------------------------------------------------------
def parse_air_sites(data):
    out = []
    for it in parse_xml(data).iter("item"):
        desc = it.findtext("description") or ""
        loc = dms(desc)
        m = re.search(r"index\s+(\d+)", desc, re.I)
        if loc and m:
            out.append({"name": plain(it.findtext("title"), 80), "lat": loc[0], "lon": loc[1], "index": int(m.group(1)),
                        "when": it.findtext("pubDate") or ""})
    return out


def parse_air_forecast(data, home):
    """The forecast for the nearest of Defra's forecast points: [(day, index), ...] from today."""
    best, best_d = None, None
    for it in parse_xml(data).iter("item"):
        desc = it.findtext("description") or ""
        loc = dms(desc)
        if not loc:
            continue
        d = km_between(home["lat"], home["lon"], loc[0], loc[1])
        if best_d is None or d < best_d:
            best, best_d = (plain(it.findtext("title"), 80), desc), d
    if not best or best_d > AIR_KM:
        return None
    days = [(day, int(n)) for day, n in re.findall(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*:\s*(\d+)", best[1])]
    return {"place": best[0].title(), "km": round(best_d, 1), "days": days}


def air_live(sites, forecast, home, now):
    near = sorted(((km_between(home["lat"], home["lon"], s["lat"], s["lon"]), s) for s in sites), key=lambda x: x[0])
    site = near[0] if near and near[0][0] <= AIR_KM else None
    reading = {"site": site[1]["name"] if site else "", "km": round(site[0], 1) if site else None,
               "index": site[1]["index"] if site else None, "band": daqi_band(site[1]["index"]) if site else "",
               "forecast": []}
    today_name = dt.date.today().strftime("%a")
    if forecast:
        days = forecast["days"]
        start = next((i for i, (d, _) in enumerate(days) if d == today_name), 0)
        reading["forecast"] = [{"day": d, "index": n, "band": daqi_band(n)} for d, n in days[start:start + 3]]
        reading["forecast_place"] = forecast["place"]
    items = []
    worst = None
    for label, n in ([("now", reading["index"])] if reading["index"] else []) + \
            [((f["day"] if i else "today"), f["index"]) for i, f in enumerate(reading["forecast"][:2])]:
        if n and n >= 7 and (worst is None or n > worst[1]):
            worst = (label, n)
    if worst:
        when = "now" if worst[0] == "now" else "today" if worst[0] == "today" else "on " + dict(
            Mon="Monday", Tue="Tuesday", Wed="Wednesday", Thu="Thursday", Fri="Friday", Sat="Saturday",
            Sun="Sunday").get(worst[0], worst[0])
        items.append({"id": "air:%s:%s" % (dt.date.today().isoformat(), daqi_band(worst[1])), "source": "air",
                      "kind": "air", "severity": 2 if worst[1] >= 10 else 1, "level": daqi_band(worst[1]) + " pollution",
                      "title": "%s air pollution %s (index %d)" % (daqi_band(worst[1]), when, worst[1]),
                      "text": "Adults and children with lung problems, and adults with heart problems, should do less "
                              "strenuous exercise outdoors, and anyone with asthma may need their inhaler more often. "
                              "Keep windows closed on busy roads.",
                      "area": reading["site"] or reading.get("forecast_place", ""), "when": "",
                      "url": "https://uk-air.defra.gov.uk/forecasting/", "issued": iso_utc(now)})
    return items, reading


# -- Space weather ------------------------------------------------------------------------------
def parse_space(data, now):
    doc = json.loads(data.decode("utf-8"))

    def g(k):
        try:
            return int((doc.get(k) or {}).get("G", {}).get("Scale") or 0)
        except (TypeError, ValueError, AttributeError):
            return 0
    g_now, g_next = g("0"), max(g("1"), g("2"), g("3"))
    reading = {"g_now": g_now, "g_next": g_next, "text": G_WORDS.get(g_now, "Storm"),
               "next_text": G_WORDS.get(g_next, "Storm")}
    items = []
    worst = max(g_now, g_next)
    if worst >= 4:
        items.append({"id": "space:G%d:%s" % (worst, now.date().isoformat()), "source": "space", "kind": "space",
                      "severity": 2 if worst >= 5 else 1, "level": "G%d" % worst,
                      "title": "%s %s" % (G_WORDS[worst], "now" if g_now == worst else "forecast"),
                      "text": "A severe solar storm can disrupt power grids, satellite navigation, radio and mobile "
                              "signals for a while. It's rare, and the grid is designed for it. Charge power banks "
                              "and torches, and have a battery or wind-up radio. You may see the northern lights.",
                      "area": "Worldwide", "when": "", "url": "https://www.swpc.noaa.gov/",
                      "issued": iso_utc(now)})
    return items, reading


# -- The pound and Bank Rate -------------------------------------------------------------------------
def parse_pound(data):
    rows = []
    for r in csv.DictReader(io.StringIO(data.decode("utf-8-sig", "replace"))):
        try:
            day = dt.datetime.strptime((r.get("DATE") or "").strip(), "%d %b %Y").date()
        except ValueError:
            continue
        rows.append({"day": day, "usd": _f0(r.get("XUDLUSS")), "eur": _f0(r.get("XUDLERS")), "rate": _f0(r.get("IUDBEDR"))})
    return sorted(rows, key=lambda r: r["day"])


def _pct(a, b):
    return 100.0 * (a - b) / b if a is not None and b else None


def pound_live(rows, now):
    rows = [r for r in rows if r["usd"] or r["eur"]]
    if not rows:
        raise ValueError("no exchange rates in the feed")
    last = rows[-1]
    wk = [r for r in rows if r["day"] <= last["day"] - dt.timedelta(days=7)]
    fn = [r for r in rows if r["day"] <= last["day"] - dt.timedelta(days=14)]
    wk, fn = (wk[-1] if wk else None), (fn[-1] if fn else None)
    rates = [r["rate"] for r in rows if r["rate"] is not None]
    reading = {"usd": last["usd"], "eur": last["eur"], "rate": rates[-1] if rates else None, "date": last["day"].isoformat(),
               "usd_week": round(_pct(last["usd"], wk["usd"]), 1) if wk and _pct(last["usd"], wk["usd"]) is not None else None,
               "eur_week": round(_pct(last["eur"], wk["eur"]), 1) if wk and _pct(last["eur"], wk["eur"]) is not None else None,
               "usd_fortnight": round(_pct(last["usd"], fn["usd"]), 1) if fn and _pct(last["usd"], fn["usd"]) is not None else None,
               "eur_fortnight": round(_pct(last["eur"], fn["eur"]), 1) if fn and _pct(last["eur"], fn["eur"]) is not None else None}
    items = []
    for cur, name in (("usd", "dollar"), ("eur", "euro")):
        w, f = reading[cur + "_week"], reading[cur + "_fortnight"]
        if w is not None and w <= -3:
            items.append({"id": "pound:week:%s:%s" % (cur, last["day"].isoformat()), "source": "pound", "kind": "money",
                          "severity": 1, "level": "The pound",
                          "title": "The pound has fallen %s%% against the %s in a week" % (fq(abs(w)), name),
                          "text": "A sharp fall in the pound makes imported food and fuel dearer over the following "
                                  "months. Nothing to do today, but it's a reason to keep the stores topped up.",
                          "area": "UK", "when": "", "url": "https://www.bankofengland.co.uk/boeapps/database/",
                          "issued": iso_utc(now)})
            break
        if f is not None and f <= -5:
            items.append({"id": "pound:fortnight:%s:%s" % (cur, last["day"].isoformat()), "source": "pound",
                          "kind": "money", "severity": 1, "level": "Two-week trend",
                          "title": "The pound is down %s%% against the %s over two weeks" % (fq(abs(f)), name),
                          "text": "A steady fall in the pound makes imported food and fuel dearer over the following "
                                  "months. A reason to keep the stores topped up.", "area": "UK", "when": "",
                          "url": "https://www.bankofengland.co.uk/boeapps/database/", "issued": iso_utc(now)})
            break
    changed = [(a, b) for a, b in zip(rows, rows[1:]) if a["rate"] is not None and b["rate"] is not None
               and a["rate"] != b["rate"] and b["day"] >= last["day"] - dt.timedelta(days=14)]
    if changed:
        a, b = changed[-1]
        items.append({"id": "pound:rate:%s" % b["day"].isoformat(), "source": "pound", "kind": "news", "severity": 0,
                      "level": "Bank Rate", "title": "Bank Rate %s to %s%% (from %s%%)" % (
                          "up" if b["rate"] > a["rate"] else "down", fq(b["rate"]), fq(a["rate"])),
                      "text": "", "area": "UK", "when": "", "url": "https://www.bankofengland.co.uk/monetary-policy",
                      "issued": iso_utc(dt.datetime.combine(b["day"], dt.time(12), dt.timezone.utc))})
    return items, reading


LIVE_LOOK = {"rivers": ("🏞️", "Rivers"), "power": ("🔌", "Power cuts"), "grid": ("⚡", "The grid"),
             "gas": ("🔥", "Gas storage"), "air": ("🌫️", "Air quality"), "space": ("☀️", "Space weather"),
             "pound": ("💷", "The pound")}
TREND_WORDS = {"rising": "rising", "falling": "falling", "steady": "steady"}


def _signed(x):
    return ("+" if x > 0 else "−" if x < 0 else "") + fq(abs(x))


def live_rows(live, items):
    """One line for each live source that's on: what it says now, and whether that's fine (good), worth
    watching (warn) or serious (bad). The app, the Home Assistant sensor and the dashboard all use these."""
    worst = {}
    for i in items:
        worst[i["source"]] = max(worst.get(i["source"], 0), i.get("severity") or 0)
    rows = []
    for key in LIVE_KEYS:
        r = live.get(key)
        if not r:
            continue
        emoji, name = LIVE_LOOK[key]
        text, state = "", "good"
        if key == "rivers":
            w = r.get("worst")
            if not w:
                text = "No river gauges within %d km" % RIVER_KM
            else:
                text = "%s: %s, %s" % (w["where"], RIVER_WORDS[w["state"]].lower(), TREND_WORDS.get(w["trend"], w["trend"]))
                if r.get("count", 0) > 1:
                    text += " · %d gauges nearby" % r["count"]
        elif key == "power":
            if r["count"]:
                c = [x for x in r["cuts"] if not x["planned"]][0] if any(not x["planned"] for x in r["cuts"]) else None
                text = "%d power cut%s within %d km%s" % (r["count"], "" if r["count"] == 1 else "s", POWER_KM,
                                                          (", nearest %s %s" % (_km_words(c["km"]), c["dir"])) if c else "")
                state = "warn"
            else:
                text = "None within %d km" % POWER_KM
            if r.get("planned"):
                text += " · %d planned" % r["planned"]
        elif key == "grid":
            text = r["text"]
            state = {"normal": "good", "notice": "warn", "demand": "bad"}.get(r["status"], "good")
        elif key == "gas":
            text = "%s%% full" % fq(round(r["pct"])) + ({"emptying": ", emptying", "filling": ", filling"}.get(r.get("trend"), ""))
            if r.get("year_ago_pct") is not None:
                text += " · %s%% a year ago" % fq(round(r["year_ago_pct"]))
        elif key == "air":
            if r.get("index"):
                text = "%s (%d) at %s" % (r["band"], r["index"], r["site"])
                state = "good" if r["index"] <= 6 else "bad" if r["index"] >= 10 else "warn"
            else:
                text = "No monitoring site within %d km" % AIR_KM
            if len(r.get("forecast") or []) > 1:
                f = r["forecast"][1]
                text += " · %s: %s" % (f["day"], f["band"].lower())
        elif key == "space":
            nxt = G_WORDS.get(r["g_next"], "Storm")
            text = r["text"] + ("" if r["g_next"] <= r["g_now"] else " · %s forecast" % (nxt[:1].lower() + nxt[1:]))
        elif key == "pound":
            bits = []
            if r.get("usd"):
                bits.append("$%.2f" % r["usd"])
            if r.get("eur"):
                bits.append("€%.2f" % r["eur"])
            if r.get("rate") is not None:
                bits.append("Bank Rate %s%%" % fq(r["rate"]))
            text = " · ".join(bits)
            if r.get("usd_week") is not None and abs(r["usd_week"]) >= 1:
                text += " · %s%% on the dollar this week" % _signed(r["usd_week"])
        if worst.get(key, 0) >= 2:
            state = "bad"
        elif worst.get(key, 0) == 1 and state == "good":
            state = "warn"
        rows.append({"key": key, "emoji": emoji, "name": name, "text": text, "state": state,
                     "dot": {"good": "🟢", "warn": "🟡", "bad": "🔴"}[state], "checked_at": r.get("checked_at"),
                     "credit": r.get("credit", "")})
    return rows


def fetch_live(key, cfg, home, mem, now):
    """(warnings, reading) for one live source."""
    if key == "space":
        return parse_space(http_get(FEED_URLS["space"]), now)
    if key == "grid":
        start = (now - dt.timedelta(hours=36)).strftime("%Y-%m-%dT%H:%MZ")
        end = (now + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%MZ")
        return parse_grid(http_get(FEED_URLS["grid"].format(start=start, end=end)), now)
    if key == "gas":
        today = now.date()
        url = FEED_URLS["gas"]
        this = parse_gas(http_get(url.format(start=(today - dt.timedelta(days=20)).isoformat(), end=today.isoformat())))
        try:
            ly = today.replace(year=today.year - 1)
        except ValueError:
            ly = today - dt.timedelta(days=365)
        last = parse_gas(http_get(url.format(start=(ly - dt.timedelta(days=20)).isoformat(), end=ly.isoformat())))
        return gas_live(this, last, today)
    if key == "pound":
        start = (now.date() - dt.timedelta(days=40)).strftime("%d/%b/%Y")
        return pound_live(parse_pound(http_get(FEED_URLS["pound"].format(start=start))), now)
    if not home:
        raise NeedLocation()
    if key == "rivers":
        cache = mem["river_stations"]
        spot = [round(home["lat"], 2), round(home["lon"], 2)]
        old = (time.time() - (cache.get("t") or 0)) > 7 * 86400
        if old or cache.get("home") != spot or not isinstance(cache.get("stations"), list):
            st = parse_river_stations(http_get(FEED_URLS["river_stations"], timeout=60), home)
            cache.clear()
            cache.update({"t": time.time(), "home": spot, "stations": st})
        return rivers_live(cache["stations"], parse_river_readings(http_get(FEED_URLS["rivers"], timeout=40)),
                           mem["river_history"], home, now)
    if key == "power":
        cuts, worked, err = [], 0, None
        for url_key, kind in POWER_FEEDS:
            if not FEED_URLS.get(url_key):
                continue
            try:
                data = http_get(FEED_URLS[url_key], timeout=30)
                cuts += {"ukpn": parse_ukpn, "ssen": parse_ssen, "npg": parse_npg}[kind](data) if kind != "nged" \
                    else parse_nged(data, now)
                worked += 1
            except Exception as e:   # one network's feed being down shouldn't hide the others
                err = e
        if not worked and err:
            raise err
        return power_live(cuts, home)
    if key == "air":
        sites = parse_air_sites(http_get(FEED_URLS["air"]))
        fc = mem["air_forecast"]
        if time.time() - (fc.get("t") or 0) > 6 * 3600 or fc.get("home") != [round(home["lat"], 2), round(home["lon"], 2)]:
            try:
                got = parse_air_forecast(http_get(FEED_URLS["air_forecast"], timeout=40), home)
                fc.clear()
                fc.update({"t": time.time(), "home": [round(home["lat"], 2), round(home["lon"], 2)], "fc": got})
            except Exception:
                pass   # the current readings are still worth having
        return air_live(sites, fc.get("fc"), home, now)
    raise ValueError("unknown source")


def fetch_source(key, cfg, home, region, mem, now):
    if key in LIVE_KEYS:
        items, reading = fetch_live(key, cfg, home, mem, now)
        mem["live"][key] = dict(reading, checked_at=now_iso(), credit=LIVE_CREDIT[key])
        return items
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
            r["lat"], r["lon"] = round(centre[0], 4), round(centre[1], 4)   # so Places can steer away from it
            out.append(r)
    return out


def home_key(home):
    """Roughly where home is (about 1 km), so a reading for the old home isn't shown for a new one."""
    return [round(home["lat"], 2), round(home["lon"], 2)] if home else None


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
               "fire_ignore": fire_ignore_list(), "river_stations": setting_raw("river_stations", {}) or {},
               "river_history": setting_raw("river_history", {}) or {}, "air_forecast": setting_raw("air_forecast", {}) or {}}
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
    mem["live"] = live = dict(prev.get("live") or {})
    for key, _, _ in WARN_SOURCES:
        if not cfg["sources"][key]:
            by_src.pop(key, None)
            live.pop(key, None)
            continue
        old = prev["sources"].get(key) or {}
        # Live feeds change slowly (gas storage once a day): don't fetch them more often than that.
        if key in LIVE_EVERY and old.get("ok") and key in live and time.time() - (old.get("t") or 0) < LIVE_EVERY[key] \
                and (old.get("home") == home_key(home)):
            statuses[key] = old
            any_ok = True
            continue
        try:
            got = fetch_source(key, cfg, home, region, mem, now)
            by_src[key] = got
            statuses[key] = {"ok": True, "error": "", "checked_at": now_iso(), "count": len(got), "t": time.time(),
                             "home": home_key(home)}
            any_ok = True
        except NeedLocation:
            by_src[key] = []
            live.pop(key, None)
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
             "checked_at": now_iso() if any_ok else prev["checked_at"], "region": region, "seen": seen,
             "live": live}
    areas = mem["areas"]
    if len(areas) > 3000:
        areas = dict(list(areas.items())[-2000:])
    with tx() as db:
        set_setting_raw(db, "warnings_cache", state)
        set_setting_raw(db, "flood_areas", areas)
        set_setting_raw(db, "fire_cells", mem["fire_cells"])
        set_setting_raw(db, "river_stations", mem["river_stations"])
        set_setting_raw(db, "river_history", mem["river_history"])
        set_setting_raw(db, "air_forecast", mem["air_forecast"])
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
    live = dict((k, v) for k, v in (st.get("live") or {}).items() if on and cfg["sources"].get(k))
    return {"config": cfg, "on": on, "live": live, "live_rows": live_rows(live, st["items"] if on else []),
            "items": st["items"] if on else [], "news": st["news"] if on else [],
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
            "checked_at": w["checked_at"],
            "live": [{k: r[k] for k in ("key", "emoji", "name", "text", "state", "dot")} for r in w["live_rows"]]}


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
# Credits: the people who built Dads Army, with thanks (Help -> Credits)
# --------------------------------------------------------------------------
# The words and names live in CREDITS.md in the GitHub repository, so they can be edited there.
# The app carries its own copy, so the page works with no internet. "Check GitHub for new names"
# fetches the latest copy and GitHub's list of code contributors: two fixed public addresses,
# asked only when someone taps the button, with nothing about the household sent.
CREDITS_REPO = "https://github.com/parkerveese-cloud/dads-army"
CREDITS_EDIT = CREDITS_REPO + "/blob/main/dadsarmy/CREDITS.md"
CREDITS_FILE = os.environ.get("DADSARMY_CREDITS", os.path.join(APP_DIR, "CREDITS.md"))
CREDITS_MAX = 64 * 1024
CREDITS_FALLBACK = "Thank you to everyone who has helped build Dads Army."
GH_LOGIN_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")
GH_HANDLE_RE = re.compile(r"(?<![\w.@])@(" + GH_LOGIN_RE.pattern + r")(?![\w-])")
MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https://[^)\s]+)\)")


def _md_plain(s):
    """Markdown down to plain words: links become their text, emphasis and code marks go."""
    s = MD_LINK_RE.sub(lambda m: m.group(1), s or "")
    s = re.sub(r"\*\*|__|`", "", s)
    s = re.sub(r"(?<![\w*])\*(?=\S)([^*]+?)\*(?!\w)", r"\1", s)
    s = re.sub(r"[\x00-\x1f\x7f]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _credit_entry(line):
    """'Name (@github-name): what they did' -> {name, handle, url, note}. Only the name is needed."""
    masked = MD_LINK_RE.sub(lambda m: "x" * len(m.group(0)), line)   # a colon inside a link isn't the split
    cut = re.search(r":\s|\s[—–-]\s", masked)
    who, note = (line[:cut.start()], line[cut.end():]) if cut else (line, "")
    handle = None
    h = GH_HANDLE_RE.search(who)
    if h:
        handle = h.group(1)
        who = re.sub(r"\(\s*\)", "", who[:h.start()] + who[h.end():])
    link = MD_LINK_RE.search(who)
    name = _md_plain(who)[:120] or ("@" + handle if handle else "")
    if not name:
        return None
    url = link.group(2) if link else ("https://github.com/" + handle if handle else None)
    return {"name": name, "handle": handle, "url": url, "note": _md_plain(note)[:200]}


def parse_credits(text):
    """CREDITS.md -> {title, message: [paragraphs], groups: [{title, about, people}]}.
    The paragraphs before the first '##' heading are the thank-you message."""
    text = re.sub(r"<!--.*?(?:-->|\Z)", "", text or "", flags=re.S)
    out = {"title": "Credits", "message": [], "groups": []}
    para = []
    cur = None

    def flush():
        if para:
            words = _md_plain(" ".join(para))[:1500]
            if words:
                (cur["about"] if cur is not None else out["message"]).append(words)
            del para[:]

    for raw in text.splitlines():
        line = raw.strip()
        if not line or re.fullmatch(r"([-*_])(\s*\1){2,}", line):   # a gap, or a --- rule
            flush()
        elif re.match(r"#\s", line):
            flush()
            out["title"] = _md_plain(line[1:])[:80] or "Credits"
        elif line.startswith("##"):
            flush()
            cur = {"title": _md_plain(line.lstrip("#"))[:80], "about": [], "people": []}
            out["groups"].append(cur)
        elif re.match(r"[-*+]\s+\S", line):
            flush()
            if cur is None:
                cur = {"title": "Contributors", "about": [], "people": []}
                out["groups"].append(cur)
            entry = _credit_entry(line[1:].strip())
            if entry and len(cur["people"]) < 300:
                cur["people"].append(entry)
        else:
            para.append(line)
    flush()
    out["message"] = out["message"][:8]
    out["groups"] = [g for g in out["groups"] if g["people"] or g["about"]][:20]
    return out


def parse_contributors(data):
    """GitHub's contributors list -> [{login, n}], people only (no bots), most changes first."""
    if not isinstance(data, list):
        raise ValueError("expected a list")
    out = []
    for c in data[:100]:
        if not isinstance(c, dict) or c.get("type") != "User":
            continue
        login, n = c.get("login"), c.get("contributions")
        if isinstance(login, str) and GH_LOGIN_RE.fullmatch(login) and isinstance(n, int) and not isinstance(n, bool) and n > 0:
            out.append({"login": login, "n": n})
    return out


def credits_merge(parsed, people):
    """Anyone with code on GitHub who isn't named in the file yet goes in a group of their own,
    after the last group that names people by their GitHub name."""
    known = set(p["handle"].lower() for g in parsed["groups"] for p in g["people"] if p["handle"])
    extra = [p for p in people if p["login"].lower() not in known]
    if not extra:
        return parsed
    at = 0
    for i, g in enumerate(parsed["groups"]):
        if any(p["handle"] for p in g["people"]):
            at = i + 1
    parsed["groups"].insert(at, {"title": "Code on GitHub", "about": [], "people": [
        {"name": "@" + p["login"], "handle": p["login"], "url": "https://github.com/" + p["login"],
         "note": "%d change%s" % (p["n"], "" if p["n"] == 1 else "s")} for p in extra]})
    return parsed


def credits_bundled():
    try:
        with open(CREDITS_FILE, "rb") as f:
            return f.read(CREDITS_MAX).decode("utf-8", "replace")
    except OSError:
        return ""


def credits_cache():
    cache = setting_raw("credits_cache", None)
    return dict(cache) if isinstance(cache, dict) else {}


def credits_view():
    """What Help -> Credits shows: GitHub's copy if it was checked on this version, else the app's own."""
    cache = credits_cache()
    text, source = credits_bundled(), "app"
    if isinstance(cache.get("text"), str) and cache.get("version") == VERSION:
        text, source = cache["text"], "github"
    parsed = parse_credits(text)
    people = cache.get("people") if isinstance(cache.get("people"), list) else []
    credits_merge(parsed, [p for p in people[:100] if isinstance(p, dict) and isinstance(p.get("login"), str)
                           and GH_LOGIN_RE.fullmatch(p["login"]) and isinstance(p.get("n"), int)])
    if not parsed["message"]:
        parsed["message"] = [CREDITS_FALLBACK]
    parsed.update(source=source, checked_at=cache.get("t"), check_error=cache.get("error"),
                  repo=CREDITS_REPO, edit_url=CREDITS_EDIT,
                  count=sum(len(g["people"]) for g in parsed["groups"]))
    return parsed


@route("GET", "/api/credits")
def api_credits(body, query):
    with LOCK:
        return {"credits": credits_view()}


@route("POST", "/api/credits/check")
def api_credits_check(body, query):
    """Fetch the latest credits list and GitHub's code contributors. Keeps what it has if either fails."""
    with LOCK:
        cache = credits_cache()
    problems = []
    try:
        text = http_get(FEED_URLS["credits"], timeout=15, limit=CREDITS_MAX).decode("utf-8")
        if re.search(r"<!doctype|<html", text[:2048], re.I):   # a Wi-Fi sign-in page or an error page
            raise ValueError("it was a web page, not the list")
        if not any(g["people"] for g in parse_credits(text)["groups"]):
            raise ValueError("there were no names in it")
        cache.update(text=text, version=VERSION)
    except Exception as e:
        problems.append("the credits list: " + why_failed(e))
    try:
        raw = http_get(FEED_URLS["contributors"], timeout=15, limit=1024 * 1024).decode("utf-8").strip()
        cache["people"] = parse_contributors(json.loads(raw) if raw else [])   # an empty repository says nothing
    except Exception as e:
        problems.append("the list of code contributors: " + why_failed(e))
    cache["t"] = now_iso()
    cache["error"] = "; ".join(problems) or None
    with tx() as db:
        set_setting_raw(db, "credits_cache", cache)
    with LOCK:
        return {"credits": credits_view(), "ok": not problems}



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
        say(GOV, "Be Ready", "Keep an emergency kit at home and build it up over time: water, food, a torch, a battery "
                             "or wind-up radio, spare batteries and a first aid kit."),
        say(SAS, "PLAN", "Work through PLAN before you need it: how you'd protect the household, how people would know "
                         "where you are, how you'd get water and food, and where you'd go."),
    ],
    "level2": [
        say(GOV, "Be Ready", "Keep up with the forecast and local news, and keep phones and power banks charged."),
        say(SAS, "PLAN: Protection", "Protection comes first: think through what would keep everyone warm, dry and "
                                     "safe if things got worse."),
    ],
    "level3": [
        say(GOV, "Be Ready", "Have enough drinking water for at least 3 days: 3 litres per person per day."),
        say(GOV, "Be Ready", "Check on neighbours and relatives who may need help, especially older people."),
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
        say(GOV, "Met Office", "Bring in or tie down anything that could blow about, and keep torches handy in case "
                               "the power goes."),
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
        say(GOV, "Be Ready", "Turn the water off at the stopcock, and keep away from any electrics near the water."),
    ],
    "power_cut_near": [
        say(NETWORKS, "105", "There's a power cut nearby. To check whether it's yours, or report one, call 105. It's "
                             "free from any phone."),
        say(TIP, "", "Charge phones and power banks now, in case it spreads, and find the torches."),
    ],
    "river_high": [
        say(GOV, "Environment Agency", "Check the flood warnings for your area, and sign up for free flood warnings "
                                       "by phone, text or email at gov.uk/sign-up-for-flood-warnings."),
        say(GOV, "Environment Agency", "If flooding is expected, move people, pets and valuables upstairs, and know "
                                       "how to turn off the gas, electricity and water."),
    ],
    "grid_demand": [
        say(NETWORKS, "Demand control", "If there are rota power cuts, your network operator will publish which areas "
                                        "are off and when. Charge things, and fill flasks, before your slot."),
        say(TIP, "", "Keep the fridge and freezer shut while the power's off, and use torches, not candles."),
    ],
    "space_storm": [
        say(TIP, "", "A severe solar storm can upset satellite navigation, radio and mobile signals, and sometimes "
                     "power. Charge power banks, keep a battery radio handy, and have a paper map."),
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
        say(GOV, "Be Ready", "Without the internet, use a battery or wind-up radio for local news and emergency "
                             "information."),
        say(TIP, "", "Warnings can't update without the internet, so the ones shown may be out of date."),
    ],
    "food_low": [
        say(GOV, "Be Ready", "Aim for enough food to last at least 3 days, and build it up over time."),
    ],
    "water_low": [
        say(GOV, "Be Ready", "Store at least 3 litres of drinking water per person per day, for at least 3 days."),
    ],
    "essentials": [
        say(GOV, "Be Ready", "Build your kit up over time: you don't need to buy everything at once. Start with a "
                             "torch, a battery or wind-up radio, a power bank and a first aid kit."),
        say(TIP, "", "Work through the essentials first. They're marked in each area under Resilience on the Sitrep."),
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
        # Live information (1.12.0). Gas storage and the pound are worth knowing, but don't change the level.
        elif src == "power" and sev >= 2:
            add(2, "power_cut_near", title)
        elif src == "rivers":
            add(3 if sev >= 2 else 2, "river_high", title)
        elif src == "grid" and sev >= 2:
            add(2, "grid_demand", title)
        elif src == "air":
            add(2, "poor_air", title)
        elif src == "space":
            add(2, "space_storm", title)

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
    weak = []
    if s["people"]:
        if s["food_days"] < 3:
            add(2, "food_low", "Food would last %s day%s" % (_f(s["food_days"]), "" if s["food_days"] == 1 else "s"))
        if s["water_days"] < 3:
            add(2, "water_low", "Water would last %s day%s" % (_f(s["water_days"]), "" if s["water_days"] == 1 else "s"))
        if s["food_days"] < 3 or s["water_days"] < 3:
            weak.append("the stores wouldn't last 3 days")
    # Resilience: an area without its essentials (food and water have their own rule above).
    gaps = [a for a in (s.get("resilience") or {}).get("areas", [])
            if [m for m in a["essentials_missing"] if m not in DAYS_IDS]]
    if gaps:
        add(2, "essentials", "Essentials missing: " + and_list([a["name"] for a in gaps]))
    # In a power cut or a cold home, missing kit for it makes things worse.
    missing = set(m for a in gaps for m in a["essentials_missing"])
    serious = set(f["key"] for f in factors if f["level"] >= 3)
    if serious & {"power_cut", "power_cut_long", "battery_low"} and missing & {"power_torch", "power_bank"}:
        weak.append("there's little backup power or light")
    if serious & {"cold_indoor", "freezing_out"} and missing & {"warm_bedding", "warm_clothes"}:
        weak.append("there's little to keep warm with")

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
            # Why it went up to SEVERE: "the stores wouldn't last 3 days", "there's little backup power or light"...
            "escalated_why": " and ".join(weak) if escalated else "",
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
            self.send_json(e.status, dict({"error": e.message}, **({"code": e.code} if e.code else {})))
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
    threading.Thread(target=history_loop, name="history", daemon=True).start()
    threading.Thread(target=offline_loop, name="offline-barcodes", daemon=True).start()
    sweep_scan_photos()
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
