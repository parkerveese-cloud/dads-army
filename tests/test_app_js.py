"""The phone app works out how long the water lasts itself (waterLasts in static/app.js), and must agree with the Pi
(water_lasts), step for step. This runs the app's own functions in a JavaScript engine (Node, or JavaScriptCore on a
Mac) over a few hundred made-up stores, and skips if there's neither."""
import datetime as dt
import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest

from support import APP_DIR, AppTest, server

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def engine():
    if shutil.which("node"):
        return [shutil.which("node")], "console.log"
    if os.path.exists(JSC):
        return [JSC], "print"
    return None, None


def app_functions():
    with open(os.path.join(APP_DIR, "static", "app.js"), encoding="utf-8") as f:
        src = f.read()

    def grab(name, end):
        i = src.index("function " + name + "(")
        return src[i:src.index(end, i)]
    return "\n".join([grab("pad", "\n  function ymd"), grab("ymd", "\n  function today"),
                      grab("today", "\n  function parseYmd"), grab("parseYmd", "\n  function daysUntil"),
                      grab("daysUntil", "\n  function addMonths"), grab("itemLitres", "\n  // Is an AI set up"),
                      "var DRINK_CAP = 1.5, WATER_MAX_DAYS = 3660;", grab("waterLasts", "\n  function readiness")])


@unittest.skipIf(engine()[0] is None, "no JavaScript engine here (Node or JavaScriptCore)")
class WaterSumsAgreeTest(AppTest):
    def test_the_app_and_the_pi_agree(self):
        rnd = random.Random(1500)
        today = dt.date.today()

        def lot():
            exp = rnd.choice([None, None, -3, -1, 0, 1, 2, 5, 10, 40, 400, 4000])
            return [rnd.choice([0, 0.5, 2, 5, 12, 37.5, 100, 3000]),
                    None if exp is None else (today + dt.timedelta(days=exp)).isoformat()]
        cases = [{"w": [lot() for _ in range(rnd.randint(0, 6))], "d": [lot() for _ in range(rnd.randint(0, 4))],
                  "perDay": rnd.choice([0, 1.5, 3, 7, 10, 13]), "cap": rnd.choice([0, 1.5, 3, 4.5, 20])} for _ in range(400)]
        items = [{"category": rnd.choice(["water", "drinks", "food"]), "litres_per_unit": rnd.choice([0, 0, 1.5]),
                  "pack_size": rnd.choice([0, 330, 1000, 5000, 2]), "pack_unit": rnd.choice(["", "g", "kg", "ml", "l", "each"])}
                 for _ in range(200)]
        cmd, out = engine()
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(app_functions() + "\nvar cases = %s, items = %s;\n%s(JSON.stringify({w: cases.map(function (c) {"
                    " var r = waterLasts(c.w, c.d, c.perDay, c.cap); return [r.days, r.wasted]; }), l: items.map(itemLitres)}));"
                    % (json.dumps(cases), json.dumps(items), out))
        try:
            got = json.loads(subprocess.run(cmd + [f.name], capture_output=True, text=True, check=True, timeout=60).stdout)
        finally:
            os.unlink(f.name)
        for c, (days, wasted) in zip(cases, got["w"]):
            py = server.water_lasts([tuple(x) for x in c["w"]], [tuple(x) for x in c["d"]], c["perDay"], c["cap"], today)
            self.assertAlmostEqual(py[0], days, places=6, msg=c)
            self.assertAlmostEqual(py[1], wasted, places=6, msg=c)
        for it, litres in zip(items, got["l"]):
            self.assertAlmostEqual(server.item_litres(it), litres, places=9, msg=it)


class WaterInRunsTest(AppTest):
    def test_ten_years_of_water_is_quick(self):
        """Worked out a run at a time (between a lot going off, the drinks running low and the water running out),
        not a day at a time: ten years of water in a moment."""
        today = dt.date(2026, 1, 1)
        days, wasted = server.water_lasts([(36600, None)], [(1000, "2027-01-01")], 10, 3, today)
        self.assertAlmostEqual(days, 3660)
        days, wasted = server.water_lasts([(30, "2026-01-02"), (100, None)], [(9, None)], 10, 3, today)
        # 2 days use 14 L of the 30 (drinks cover 3 L a day), the rest (16 L) goes off; then 100 L at 7 L a day
        # while the last 3 L of drinks last (1 day), then 10 L a day: 2 + 1 + 9.3 days.
        self.assertAlmostEqual(days, 12.3)
        self.assertAlmostEqual(wasted, 1.6)
