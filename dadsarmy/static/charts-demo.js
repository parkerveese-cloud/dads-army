/* Gallery for charts.js: every chart in several states, light and dark side by side. */
(function () {
  'use strict';
  var C = window.DAChart;
  var EVIL = '<script>alert("x")</script> \'quoted\' & "double"';
  var LONG = 'Long-life semi-skimmed UHT milk, one litre cartons from the big shop';

  function iso(d) { return new Date(d * 864e5).toISOString().slice(0, 10); }
  var today = Math.floor(Date.UTC(2026, 10, 12) / 864e5);

  // A deterministic wobbly series.
  function series(n, start, drift, wobble, seed, gaps) {
    var out = [], v = start, i;
    for (i = 0; i < n; i++) {
      v += drift + Math.sin((i + seed) * 1.7) * wobble;
      var d = today - (n - 1 - i);
      if (gaps && gaps.indexOf(i) >= 0) continue;          // missing day
      out.push({ x: iso(d), y: (gaps && gaps.indexOf(-i) >= 0) ? null : Math.round(v * 10) / 10 });
    }
    return out;
  }

  function card(title, body, wide) {
    return '<div class="card' + (wide ? ' wide' : '') + '"><h3>' + C.esc(title) + '</h3>' + body + '</div>';
  }
  function cell(svg, cap) { return '<div>' + svg + (cap ? '<p>' + C.esc(cap) + '</p>' : '') + '</div>'; }

  function gallery(noAnimate) {
    var A = { noAnimate: noAnimate };
    function o(x) { var k; for (k in A) x[k] = A[k]; return x; }
    var h = '';

    h += card('Ring: states', '<div class="row">' +
      cell(C.ring(o({ title: 'Food', value: 26, max: 30, state: 'good', unit: 'days', label: '26', sub: 'of 30 days' })), 'good') +
      cell(C.ring(o({ title: 'Food', value: 13, max: 30, state: 'warn', unit: 'days', label: '13', sub: 'of 30 days', target: 21 })), 'warn + target') +
      cell(C.ring(o({ title: 'Water', value: 3, max: 30, state: 'bad', unit: 'days' })), 'bad, default %') +
      '</div>');
    h += card('Ring: edge cases', '<div class="row">' +
      cell(C.ring(o({ title: 'Empty', value: null, max: 30 })), 'null') +
      cell(C.ring(o({ title: 'Zero', value: 0, max: 30, state: 'bad', label: '0', sub: 'days' })), 'zero') +
      cell(C.ring(o({ title: 'Overflow', value: 4500, max: 30, state: 'good', unit: 'days' })), 'value 4,500 of 30') +
      cell(C.ring(o({ title: EVIL, value: 7, max: 0, label: '7', sub: LONG })), 'max 0, long sub, hostile') +
      '</div>');

    h += card('Rings', '<div class="row">' +
      cell(C.rings(o({ rings: [
        { label: 'Food', value: 13, max: 30, color: 'food' },
        { label: 'Water', value: 9, max: 14, color: 'water' },
        { label: 'Kit', value: 72, max: 100, color: 'kit' }], centre: { big: '13', small: 'days' } }))) +
      cell(C.rings(o({ rings: [
        { label: 'Food', value: 45, max: 30, color: 'food' },
        { label: 'Water', value: 0, max: 14, color: 'water' },
        { label: EVIL, value: NaN, max: 100, color: 'kit' }], centre: { big: '999', small: LONG } })), 'overflow, zero, NaN') +
      cell(C.rings(o({ rings: [], centre: { big: '–', small: 'no data' } })), 'empty') +
      '</div>');

    h += card('Gauge', '<div class="row gauges">' +
      cell(C.gauge(o({ value: 9, max: 21, target: 14, unit: 'days', state: 'warn', label: 'Water' }))) +
      cell(C.gauge(o({ value: 31, max: 21, target: 21, unit: 'days', state: 'good', label: 'Food' })), 'overflow, target at max') +
      '</div><div class="row gauges" style="margin-top:12px">' +
      cell(C.gauge(o({ value: null, max: 21, target: 0, unit: 'days', label: LONG })), 'null, target at 0') +
      cell(C.gauge(o({ value: -4, max: 0, unit: EVIL, state: 'bad', label: EVIL })), 'negative, max 0, hostile') +
      '</div>');

    var sp = [12, 13, 13, 14, 12, 11, 12, 13, 15, 16, 15, 17];
    h += card('Spark', '<div class="stack">' +
      C.spark(o({ points: sp, state: 'good', title: 'Hold-out days' })) +
      C.spark(o({ points: [3, 4, null, 6, 5, null, null, 4, 3, 2, 2, 1], state: 'bad', area: true, target: 2, labels: { first: 'Aug', last: 'Today' }, title: 'Expired' })) +
      C.spark(o({ points: [5, 5, 5, 5, 5], state: 'info', area: true })) +
      C.spark(o({ points: [4], state: 'warn' })) +
      C.spark(o({ points: [], labels: { first: 'no data', last: EVIL } })) +
      C.spark(o({ points: [null, 2, null, 4, null, 3, null], state: 'warn', height: 28 })) +
      '<p class="cap">normal; gaps + area + target + labels; flat; single point; empty; isolated points</p></div>');

    h += card('Trend: 90 days, one series, gaps, target', C.trend(o({
      title: 'Hold-out days', yUnit: 'days', target: 30,
      series: [{ name: 'Hold-out', points: series(90, 8, 0.07, 0.6, 2, [20, 21, 22, 60, -45, -46]) }]
    })), true);
    h += card('Trend: three series', C.trend(o({
      height: 220, yUnit: 'days', target: 14,
      series: [
        { name: 'Food', color: 'food', points: series(60, 10, 0.05, 0.5, 1) },
        { name: 'Water', color: 'water', points: series(60, 5, 0.12, 0.6, 4, [30, 31]) },
        { name: 'Kit', color: 'kit', points: series(60, 16, -0.03, 0.4, 7) }]
    })) + '<div style="margin-top:12px">' + C.legend({ items: [
      { label: 'Food', color: 'food', value: '13 days' },
      { label: 'Water', color: 'water', value: '9 days' },
      { label: 'Kit', color: 'kit', value: '18 days' }] }) + '</div>', true);
    h += card('Trend: target near the last value', C.trend(o({
      yUnit: 'days', target: 20, height: 160,
      series: [{ name: 'Hold-out', state: 'good', points: series(30, 14, 0.2, 0.3, 3) }]
    })));
    h += card('Trend: gas storage, 400 days', C.trend(o({
      yUnit: 'TWh', height: 160,
      series: [{ name: 'Gas', color: 'info', points: (function () {
        var a = [], i; for (i = 0; i < 400; i += 7) a.push([iso(today - 400 + i), 2 + 9 * Math.abs(Math.sin(i / 120))]); return a;
      }()) }]
    })));
    h += card('Trend: single point, empty, negative', C.trend(o({ height: 120, target: 30, series: [{ name: 'One', points: [{ x: iso(today), y: 12 }] }] })) +
      C.trend(o({ height: 120, series: [] })) +
      C.trend(o({ height: 140, series: [{ name: 'Balance', state: 'bad', points: series(20, 2, -0.4, 1, 5) }] })));
    h += card('Trend: hostile and junk input', C.trend(o({
      title: EVIL, height: 140, target: 'x', targetLabel: EVIL, yUnit: EVIL,
      series: [{ name: EVIL, color: 'red;background:url(x)', points: [{ x: 'nope', y: 3 }, { x: iso(today - 3), y: 'NaN' }, { x: iso(today - 2), y: 4 }, { x: iso(today - 1), y: 1e9 }, { x: iso(today), y: 5 }] }]
    })));

    h += card('Bars: stock by category', C.bars(o({ unit: '', items: [
      { label: 'Food', value: 13, max: 30, state: 'warn', unit: 'days', sub: '42 items, 3 expiring' },
      { label: 'Water', value: 14, max: 14, state: 'good', unit: 'days' },
      { label: 'Medical', value: 2, max: 10, state: 'bad', unit: 'items', target: 6 },
      { label: 'Power & light', value: 40, max: 12, state: 'good', unit: 'items' },
      { label: LONG, value: 0, max: 5, state: 'bad' },
      { label: EVIL, value: null, max: 4 }
    ] })));
    h += card('Bars: empty', C.bars(o({ items: [] })));

    var months = ['Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov'];
    var cols = months.map(function (m, i) {
      return { label: m, key: '2026-' + (i + 1), stacks: [
        { value: i === 0 ? 3 : 0, state: 'bad', label: 'expired' },
        { value: i < 2 ? 4 - i : 0, state: 'warn', label: 'expiring' },
        { value: [2, 5, 3, 8, 14, 6, 0, 4, 9, 22, 3, 1][i], state: 'good', label: 'fine' }] };
    });
    h += card('Columns: expiry timeline, highlight Mar', C.columns(o({ title: 'Expiry by month', columns: cols, highlight: 3 })), true);
    h += card('Columns: few, zeros, overflow labels', C.columns(o({ height: 150, columns: [
      { label: LONG, key: 'a', stacks: [{ value: 1200, state: 'info' }] },
      { label: 'Zero', key: 'b', stacks: [{ value: 0 }] },
      { label: EVIL, key: EVIL, stacks: [{ value: 340, state: 'warn' }, { value: -5, state: 'bad' }] }], highlight: 'b' })));
    var many = []; for (var i = 0; i < 24; i++) many.push({ label: months[i % 12], stacks: [{ value: (i * 7) % 11, state: i % 5 ? 'good' : 'warn' }] });
    h += card('Columns: 24, no values, empty', C.columns(o({ height: 130, columns: many })) + C.columns(o({ height: 100, columns: [] })));

    h += card('Donut', '<div class="row">' +
      cell(C.donut(o({ title: 'Stock', segments: [
        { label: 'Food', value: 42, color: 'food' }, { label: 'Water', value: 18, color: 'water' }, { label: 'Kit', value: 25, color: 'kit' }],
        centre: { big: '85', small: 'items' } }))) +
      cell(C.donut(o({ segments: [{ label: 'All', value: 5, state: 'good' }], centre: { big: '100%', small: 'one segment' } })), 'single') +
      cell(C.donut(o({ segments: [{ label: EVIL, value: 0 }, { label: 'x', value: null }], centre: { big: '0', small: 'empty' } })), 'zero / null') +
      '</div><div style="margin-top:12px">' + C.legend({ vertical: true, items: [
        { label: 'Food', color: 'food', value: 42 }, { label: 'Water', color: 'water', value: 18 }, { label: LONG, color: 'kit', value: EVIL }] }) + '</div>');

    function mrow(name, v, m, t, st, txt) {
      return '<div class="meter-row"><span>' + C.esc(name) + '</span>' +
        C.meter(o({ title: name, value: v, max: m, target: t, state: st })) + '<b>' + C.esc(txt) + '</b></div>';
    }
    h += card('Meter (inside rows)', '<div class="stack">' +
      mrow('Baked beans', 9, 15, 12, 'warn', '9 of 15') +
      mrow('Bottled water', 24, 24, null, 'good', '24 of 24') +
      mrow('Batteries AA', 0, 16, 8, 'bad', '0 of 16') +
      mrow('Overflow', 40, 10, 10, 'good', '40 of 10') +
      mrow(LONG, null, 0, null, null, 'none') +
      '</div>');
    return h;
  }

  function render(noAnimate) {
    var gals = document.querySelectorAll('.gal'), i;
    var html = gallery(noAnimate);
    for (i = 0; i < gals.length; i++) gals[i].innerHTML = html;
  }
  render(false);
  document.getElementById('replay').addEventListener('click', function () {
    var gals = document.querySelectorAll('.gal'), i;
    for (i = 0; i < gals.length; i++) gals[i].innerHTML = '';
    window.requestAnimationFrame(function () { render(false); });
  });
}());
