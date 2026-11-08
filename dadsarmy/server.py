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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

VERSION = "1.1.1"
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


def all_items():
    items = [dict(r) for r in DB.execute("SELECT * FROM items ORDER BY name COLLATE NOCASE")]
    by_item = {}
    for b in DB.execute("SELECT * FROM batches ORDER BY expiry IS NULL, expiry, id"):
        by_item.setdefault(b["item_id"], []).append(dict(b))
    for it in items:
        it["batches"] = by_item.get(it["id"], [])
    return items


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
                       "backup_dir": BACKUP_DIR},
        }


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
    """Undo: put an item and its batches back exactly as they were."""
    item = body.get("item")
    batches = body.get("batches")
    if not isinstance(item, dict) or not isinstance(batches, list):
        raise ApiError(400, "Nothing to restore")
    item_id = as_int_id(item.get("id"))
    data = clean_item(item)
    created = clean_text(item.get("created_at"), 30) or now_iso()
    with tx() as db:
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
        add_log("undo", data["name"], "Change undone")
    return {"ok": True}


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
        with LOCK:
            DB.close()
        print("Dismissed.", flush=True)


if __name__ == "__main__":
    main()
