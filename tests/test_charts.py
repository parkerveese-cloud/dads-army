"""Tests for static/charts.js, run through macOS JavaScriptCore (osascript -l JavaScript).

Skipped where osascript isn't available (Node isn't required anywhere in this project).
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARTS = os.path.join(ROOT, "dadsarmy", "static", "charts.js")

HARNESS = r"""
var EVIL = '<script>alert("x")</script>\'"&';
var out = { calls: [] };
function callChart(name, opts) {
  var r = { name: name };
  try {
    var s = DAChart[name](opts);
    r.type = typeof s;
    r.svg = s.indexOf('<svg') === 0;
    r.html = s;
  } catch (e) { r.error = String(e); }
  out.calls.push(r);
}
var d = '2026-11-12';
var cases = {
  ring: [{}, { value: 13, max: 30, title: 'Food', unit: 'days' }, { value: 0, max: 0 }, { value: -5, max: 30 },
         { value: NaN, max: null }, { value: 1e12, max: 30, target: 50 }, { value: 3, max: 30, title: EVIL, label: EVIL, sub: EVIL, color: EVIL }],
  rings: [{}, { rings: [] }, { rings: [null, { value: NaN }, { value: 99, max: 1, label: EVIL, color: 'water' }], centre: { big: EVIL, small: EVIL } }],
  gauge: [{}, { value: 9, max: 21, target: 14, unit: 'days', label: 'Water' }, { value: 99, max: 0, target: -1, unit: EVIL, label: EVIL }],
  spark: [{}, { points: [] }, { points: [4] }, { points: [null, null] }, { points: [1, null, 3, 'x', 5], area: true, target: 2, labels: { first: EVIL, last: EVIL }, title: EVIL }],
  trend: [{}, { series: [] }, { series: [{ points: [{ x: d, y: 3 }] }] },
          { series: [{ name: EVIL, color: 'red;}<', points: [{ x: 'bad', y: 1 }, { x: '2026-11-01', y: null }, ['2026-11-02', 4], { x: '2026-11-09', y: -2 }, { x: d, y: 1e9 }] },
                     { points: [] }, { points: [{ x: d, y: 5 }] }, { points: [] }], target: 30, targetLabel: EVIL, yUnit: EVIL, title: EVIL }],
  bars: [{}, { items: [] }, { items: [{ label: EVIL, value: 50, max: 5, sub: EVIL, key: EVIL }, { label: 'x', value: null, max: 0 }, null], unit: EVIL }],
  columns: [{}, { columns: [] }, { columns: [{ label: EVIL, key: EVIL, stacks: [{ value: 3, state: 'bad' }, { value: -1 }, { value: NaN }] }, null, { label: 'Zero', stacks: [] }], highlight: EVIL }],
  donut: [{}, { segments: [] }, { segments: [{ label: EVIL, value: 0 }, { label: 'b', value: null }] }, { segments: [{ label: 'a', value: 3, color: EVIL }], centre: { big: EVIL } }],
  meter: [{}, { value: 9, max: 15, target: 12 }, { value: 50, max: 0, target: 3, title: EVIL }, { value: NaN }]
};
for (var k in cases) for (var i = 0; i < cases[k].length; i++) callChart(k, cases[k][i]);
var leg = DAChart.legend({ items: [{ label: EVIL, value: EVIL, color: EVIL }, null, { label: 'x', value: 3 }] });


out.legend = leg;
out.ring = DAChart.ring({ value: 13, max: 30, title: 'Food', unit: 'days', noAnimate: true });
out.over = DAChart.ring({ value: 4500, max: 30, title: 'Food', unit: 'days' });
out.columns = DAChart.columns({ columns: [{ label: 'Jan', key: '2026-01', stacks: [{ value: 2 }] }] });
JSON.stringify(out);
"""


@unittest.skipUnless(shutil.which("osascript"), "needs macOS osascript (JavaScriptCore)")
class ChartsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CHARTS, encoding="utf-8") as f:
            src = f.read()
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
            t.write(src + "\n" + HARNESS)
            path = t.name
        try:
            p = subprocess.run(["osascript", "-l", "JavaScript", path], capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(path)
        if p.returncode != 0:
            raise AssertionError("osascript failed: " + p.stderr)
        cls.out = json.loads(p.stdout.strip())

    def test_every_call_returns_svg(self):
        for c in self.out["calls"]:
            with self.subTest(name=c["name"]):
                self.assertNotIn("error", c, c.get("error"))
                self.assertEqual(c["type"], "string")
                self.assertTrue(c["svg"], c["html"][:80])
                self.assertIn('role="img"', c["html"])
                self.assertRegex(c["html"], r'aria-label="[^"]+"')
                self.assertNotIn("NaN", c["html"])
                self.assertNotIn("Infinity", c["html"])
                self.assertNotIn("undefined", c["html"])

    def test_hostile_text_is_escaped(self):
        for c in self.out["calls"] + [{"html": self.out["legend"]}]:
            html = c["html"]
            self.assertNotIn("<script", html)
            self.assertNotIn('"x")', html)        # raw double quote never escapes an attribute
            self.assertNotIn(";}<", html)          # unsafe colour refused
        self.assertIn("&lt;script&gt;", self.out["legend"])

    def test_labels_say_the_value(self):
        self.assertIn('aria-label="Food: 13 of 30 days, 43%"', self.out["ring"])
        self.assertNotIn("dac-anim", self.out["ring"])
        self.assertIn("4,500 of 30 days, 15000%", self.out["over"])   # true number kept, drawing clamped
        self.assertIn('data-key="2026-01"', self.out["columns"])
        self.assertIn("dac-anim", self.out["columns"])


if __name__ == "__main__":
    unittest.main()
