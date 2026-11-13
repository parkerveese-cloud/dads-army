#!/usr/bin/env python3
"""Fill a local Dads Army with realistic demo stock. Usage: seed_demo.py http://127.0.0.1:PORT"""
import datetime as dt
import json
import random
import sys
import urllib.request

B = sys.argv[1].rstrip("/")


def call(m, p, b=None):
    r = urllib.request.Request(B + p, method=m, data=None if b is None else json.dumps(b).encode(),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=20).read() or b"{}")


call("PUT", "/api/settings", {"adults": 2, "children": 2, "pets": 1, "water_per_pet": 0.5})
call("POST", "/api/seed", {})
random.seed(7)
today = dt.date.today()
for it in call("GET", "/api/state")["items"]:
    if random.random() < 0.18:
        continue
    qty = max(1, round((it["target_qty"] or 2) * random.choice([0.3, 0.6, 1.0, 1.0, 1.2])))
    for q in ([qty] if qty < 4 or random.random() < 0.5 else [qty // 2, qty - qty // 2]):
        days = random.choice([-20, 5, 12, 25, 60, 120, 300, 500, 900])
        no_date = it["category"] in ("tools", "power", "shelter", "docs", "comms") and random.random() < 0.6
        call("POST", "/api/items/%d/stock" % it["id"], {
            "qty": q, "expiry": None if no_date else (today + dt.timedelta(days=days)).isoformat(),
            "location": random.choice(["Garage shelf A", "Garage shelf B", "Pantry", "Loft", "Under stairs"])})
for t in ("Matches", "Spare gas canister", "Dog treats"):
    call("POST", "/api/shopping", {"text": t})
print("seeded", B)
