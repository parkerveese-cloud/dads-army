/* Dads Army - small SVG charts. Plain ES5, no dependencies, no build step.
 *
 * window.DAChart.<name>(options) returns an SVG string (legend returns HTML).
 * Colour comes only from CSS custom properties (with fallbacks), so themes just work.
 * Styles and the draw-in animation live in charts.css. Pass noAnimate: true on background refreshes.
 */
(function (root) {
  'use strict';

  // ------------------------------------------------------------------
  // Colour
  // ------------------------------------------------------------------
  var STATE = {
    good: 'var(--good, #2f6a2b)',
    warn: 'var(--warn, #b77600)',
    bad: 'var(--bad, #b0342c)',
    info: 'var(--info, #5d84ad)'
  };
  var NAMED = {
    food: 'var(--c-food, #7c8a35)',
    water: 'var(--c-water, #5d84ad)',
    kit: 'var(--c-kit, #a8875a)',
    olive: 'var(--olive, #4b5320)',
    track: 'var(--c-track, rgba(128, 128, 100, .2))',
    grid: 'var(--c-grid, rgba(128, 128, 100, .2))',
    target: 'var(--c-target, var(--ink, currentColor))',
    ink: 'var(--ink, currentColor)',
    muted: 'var(--muted, #7d806f)',
    surface: 'var(--surface, #fff)'
  };
  var SERIES = [NAMED.olive, NAMED.water, NAMED.kit];
  var CATS = [NAMED.food, NAMED.water, NAMED.kit];

  // A colour option may be a state name, a palette name, any CSS colour or a var(...) string.
  // Anything that could break out of a style attribute is refused.
  function paint(color, state, fallback) {
    if (typeof color === 'string') {
      var c = color.replace(/^\s+|\s+$/g, '');
      if (STATE[c]) return STATE[c];
      if (NAMED[c]) return NAMED[c];
      if (c && c.length <= 160 && /^[#a-zA-Z0-9(),.%\s-]+$/.test(c)) return c;
    }
    if (typeof state === 'string' && STATE[state]) return STATE[state];
    return fallback || STATE.good;
  }

  // ------------------------------------------------------------------
  // Small helpers
  // ------------------------------------------------------------------
  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function str(s) { return s === null || s === undefined ? '' : String(s); }
  function trunc(s, n) {
    s = str(s).replace(/\s+/g, ' ').replace(/^\s+|\s+$/g, '');
    n = Math.max(2, Math.floor(n));
    return s.length > n ? s.slice(0, n - 1).replace(/\s+$/, '') + '…' : s;
  }
  function num(v) {
    if (typeof v === 'string' && v.replace(/\s/g, '') !== '') v = Number(v.replace(',', '.'));
    return typeof v === 'number' && isFinite(v) ? v : null;
  }
  function posNum(v, dflt) { v = num(v); return v !== null && v > 0 ? v : dflt; }
  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function r2(v) { return Math.round(v * 100) / 100; }
  function group(s) {
    var neg = s.charAt(0) === '-';
    if (neg) s = s.slice(1);
    var parts = s.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return (neg ? '-' : '') + parts.join('.');
  }
  // Plain number for labels: 13, 2.5, 1,250.
  function fmt(v) {
    v = num(v);
    if (v === null) return 'no data';
    var a = Math.abs(v), s;
    if (a >= 100 || v === Math.round(v)) s = String(Math.round(v));
    else if (a >= 10) s = v.toFixed(1);
    else s = v.toFixed(a < 1 ? 2 : 1);
    if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
    if (s === '-0') s = '0';
    return group(s);
  }
  // Short number for tight spaces: 950, 12k, 1.2M.
  function short(v) {
    v = num(v);
    if (v === null) return '–';
    var a = Math.abs(v);
    if (a >= 1e9) return trim1(v / 1e9) + 'bn';
    if (a >= 1e6) return trim1(v / 1e6) + 'M';
    if (a >= 1e4) return trim1(v / 1e3) + 'k';
    return fmt(v);
  }
  function trim1(v) { var s = (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toString(); return s; }
  function pct(f) { return Math.round(f * 100); }
  function unitText(u) { u = str(u); return u ? ' ' + u : ''; }
  // value/max as a 0..1 drawing fraction (clamped), or null when there's nothing to show.
  function frac(value, max) {
    if (value === null) return null;
    if (max === null || max <= 0) return value > 0 ? 1 : 0;
    return clamp(value / max, 0, 1);
  }
  function anim(o) { return o && o.noAnimate ? '' : ' dac-anim'; }
  function open(kind, o, label, attrs) {
    var cls = 'dac dac-' + kind + anim(o);
    if (o && typeof o.className === 'string' && /^[\w\s-]+$/.test(o.className)) cls += ' ' + o.className;
    return '<svg xmlns="http://www.w3.org/2000/svg" class="' + cls + '" role="img" focusable="false" aria-label="' +
      esc(o && o.ariaLabel ? o.ariaLabel : label) + '" ' + attrs + '>';
  }
  function named(o) { var t = trunc(str(o.title || o.name), 80); return t ? t + ': ' : ''; }
  // Centred text whose size fits a width (rough per-character estimate, good enough for numbers).
  function fitSize(text, width, maxSize, ratio) {
    var n = Math.max(1, str(text).length);
    return Math.min(maxSize, width / (n * (ratio || 0.6)));
  }

  // ------------------------------------------------------------------
  // Geometry
  // ------------------------------------------------------------------
  // Angle in degrees, 0 at the top, clockwise.
  function polar(cx, cy, r, a) {
    var t = (a - 90) * Math.PI / 180;
    return [cx + r * Math.cos(t), cy + r * Math.sin(t)];
  }
  function arc(cx, cy, r, a0, a1) {
    var sweep = a1 - a0;
    if (sweep >= 359.99) {
      var top = polar(cx, cy, r, a0), bot = polar(cx, cy, r, a0 + 180);
      return 'M' + r2(top[0]) + ' ' + r2(top[1]) +
        'A' + r2(r) + ' ' + r2(r) + ' 0 1 1 ' + r2(bot[0]) + ' ' + r2(bot[1]) +
        'A' + r2(r) + ' ' + r2(r) + ' 0 1 1 ' + r2(top[0]) + ' ' + r2(top[1]);
    }
    var p0 = polar(cx, cy, r, a0), p1 = polar(cx, cy, r, a1);
    return 'M' + r2(p0[0]) + ' ' + r2(p0[1]) + 'A' + r2(r) + ' ' + r2(r) + ' 0 ' + (sweep > 180 ? 1 : 0) +
      ' 1 ' + r2(p1[0]) + ' ' + r2(p1[1]);
  }
  // A progress stroke along a path, drawn to fraction f (0..1). pathLength=100 keeps the dash maths simple.
  function progress(d, f, color, width, cap) {
    if (!(f > 0)) return '';
    var off = r2(100 - f * 100);
    return '<path class="dac-arc" d="' + d + '" pathLength="100" style="fill:none;stroke:' + color +
      ';stroke-width:' + r2(width) + ';stroke-linecap:' + (cap || 'round') +
      ';stroke-dasharray:100 100;stroke-dashoffset:' + off + '"/>';
  }
  function track(d, width) {
    return '<path d="' + d + '" style="fill:none;stroke:' + NAMED.track + ';stroke-width:' + r2(width) + '"/>';
  }
  function text(x, y, s, cls, extra) {
    return '<text x="' + x + '" y="' + r2(y) + '" class="' + cls + '"' + (extra || '') + '>' + esc(s) + '</text>';
  }
  // A big number with a smaller line under it, centred as a block (cap-height based, so it looks centred).
  function centreText(cx, cy, big, small, width, bigMax) {
    var out = '';
    big = str(big); small = str(small);
    var bs = big ? fitSize(big, width * 0.92, bigMax, 0.58) : 0;
    var ss = small ? clamp(bs * 0.36, 9, 13) : 0;
    if (small && !big) ss = clamp(width / 8, 9, 13);
    if (small) small = trunc(small, Math.max(4, Math.floor(width * 1.1 / (ss * 0.52))));
    var cap = 0.71, gap = big && small ? Math.max(3, bs * 0.16) : 0;
    var h = bs * cap + gap + ss * cap;
    var topY = cy - h / 2;
    if (big) out += text(cx, topY + bs * cap, big, 'dac-big', ' text-anchor="middle" style="font-size:' + r2(bs) + 'px"');
    if (small) out += text(cx, topY + bs * cap + gap + ss * cap, small, 'dac-sub', ' text-anchor="middle" style="font-size:' + r2(ss) + 'px"');
    return out ? '<g class="dac-fade">' + out + '</g>' : '';
  }

  // ------------------------------------------------------------------
  // ring: one progress ring with a centred number
  // ------------------------------------------------------------------
  function ring(o) {
    o = o || {};
    var size = clamp(posNum(o.size, 120), 24, 2000);
    var th = clamp(posNum(o.thickness, size * 0.1), 2, size / 4);
    var value = num(o.value), max = num(o.max), target = num(o.target);
    var f = frac(value, max);
    var hasTarget = target !== null && max !== null && max > 0 && target > 0;
    var pad = hasTarget ? 3 : 1;
    var c = size / 2, r = c - th / 2 - pad;
    var color = paint(o.color, o.state, STATE.good);
    var p = value !== null && max !== null && max > 0 ? pct(value / max) : null;

    var label = named(o) + (value === null ? 'no data' :
      fmt(value) + (max !== null && max > 0 ? ' of ' + fmt(max) : '') + unitText(o.unit) + (p !== null ? ', ' + p + '%' : ''));
    if (hasTarget) label += ', target ' + fmt(target) + unitText(o.unit);

    var big = o.label !== undefined && o.label !== null ? str(o.label) : (value === null ? '–' : p !== null ? p + '%' : short(value));
    var s = open('ring', o, label, 'viewBox="0 0 ' + size + ' ' + size + '" style="width:100%;max-width:' + size + 'px;height:auto"');
    var d = arc(c, c, r, 0, 360);
    s += track(d, th);
    s += progress(d, f, color, th);
    if (hasTarget) {
      var ta = clamp(target / max, 0, 1) * 360;
      var a = polar(c, c, r - th / 2 - 2, ta), b = polar(c, c, r + th / 2 + 2, ta);
      s += '<line x1="' + r2(a[0]) + '" y1="' + r2(a[1]) + '" x2="' + r2(b[0]) + '" y2="' + r2(b[1]) +
        '" style="stroke:' + NAMED.target + ';stroke-width:' + r2(clamp(th / 4, 1.5, 3)) + ';stroke-linecap:round"/>';
    }
    s += centreText(c, c, big, o.sub, (r - th / 2) * 2 * 0.8, (r - th / 2) * 0.82);
    return s + '</svg>';
  }

  // ------------------------------------------------------------------
  // rings: concentric rings (food, water, kit)
  // ------------------------------------------------------------------
  function rings(o) {
    o = o || {};
    var list = o.rings && o.rings.length ? o.rings : [];
    var size = clamp(posNum(o.size, 160), 40, 2000);
    var th = clamp(posNum(o.thickness, size * 0.075), 3, size / 8);
    var gap = Math.max(2, th * 0.3);
    var c = size / 2, r0 = c - th / 2 - 1;
    var parts = [], body = '', inner = r0 + th / 2, i;
    for (i = 0; i < list.length; i++) {
      var g = list[i] || {}, r = r0 - i * (th + gap);
      var v = num(g.value), m = num(g.max), f = frac(v, m);
      var nm = trunc(str(g.label || g.name || ('Ring ' + (i + 1))), 40);
      var p = v !== null && m !== null && m > 0 ? pct(v / m) : null;
      parts.push(nm + ' ' + (v === null ? 'no data' : fmt(v) + (m !== null && m > 0 ? ' of ' + fmt(m) : '') + unitText(g.unit) + (p !== null ? ', ' + p + '%' : '')));
      if (r - th / 2 < size * 0.12) continue;     // no room left: keep it in the label, skip the drawing
      var d = arc(c, c, r, 0, 360);
      body += track(d, th) + progress(d, f, paint(g.color, g.state, CATS[i % 3]), th);
      inner = r - th / 2;
    }
    if (!list.length) body = track(arc(c, c, r0, 0, 360), th);
    var ce = o.centre || o.center || {};
    var label = named(o) + (parts.length ? parts.join('; ') : 'no data');
    var s = open('rings', o, label, 'viewBox="0 0 ' + size + ' ' + size + '" style="width:100%;max-width:' + size + 'px;height:auto"');
    s += body;
    s += centreText(c, c, ce.big, ce.small, (inner - gap) * 2 * 0.82, inner * 0.62);
    return s + '</svg>';
  }

  // ------------------------------------------------------------------
  // gauge: semi-circle with a target tick
  // ------------------------------------------------------------------
  function gauge(o) {
    o = o || {};
    var W = 220, cx = 110, r = 80, th = clamp(posNum(o.thickness, 14), 4, 30);
    var top = 26, cy = top + r + th / 2, H = cy + 24;
    var value = num(o.value), max = num(o.max), target = num(o.target);
    var f = frac(value, max);
    var color = paint(o.color, o.state, STATE.good);
    var unit = str(o.unit);
    var title = trunc(str(o.label || o.title), 60);
    var p = value !== null && max !== null && max > 0 ? pct(value / max) : null;
    var hasTarget = target !== null && max !== null && max > 0;

    var aria = (title ? title + ': ' : '') + (value === null ? 'no data' :
      fmt(value) + (max !== null && max > 0 ? ' of ' + fmt(max) : '') + unitText(unit) + (p !== null ? ', ' + p + '%' : ''));
    if (hasTarget) aria += ', target ' + fmt(target) + unitText(unit);

    var s = open('gauge', o, aria, 'viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;max-width:' + (o.size ? posNum(o.size, W) : 260) + 'px;height:auto"');
    var d = arc(cx, cy, r, -90, 90);
    s += track(d, th);
    s += progress(d, f, color, th);
    if (hasTarget) {
      var tf = clamp(target / max, 0, 1), ang = -90 + 180 * tf;
      var a = polar(cx, cy, r - th / 2 - 4, ang), b = polar(cx, cy, r + th / 2 + 4, ang);
      s += '<line class="dac-tick" x1="' + r2(a[0]) + '" y1="' + r2(a[1]) + '" x2="' + r2(b[0]) + '" y2="' + r2(b[1]) +
        '" style="stroke:' + NAMED.surface + ';stroke-width:6;stroke-linecap:round"/>';
      s += '<line class="dac-tick" x1="' + r2(a[0]) + '" y1="' + r2(a[1]) + '" x2="' + r2(b[0]) + '" y2="' + r2(b[1]) +
        '" style="stroke:' + NAMED.target + ';stroke-width:2.5;stroke-linecap:round"/>';
      var lp = polar(cx, cy, r + th / 2 + 9, ang);
      var anchor = ang < -25 ? 'end' : ang > 25 ? 'start' : 'middle';
      var ly = lp[1] + (anchor === 'middle' ? -1 : 4);
      s += text(r2(lp[0]), ly, short(target), 'dac-axis dac-target-label', ' text-anchor="' + anchor + '"');
    }
    // Number + unit on one baseline, label under it.
    var big = value === null ? '–' : short(value);
    var bs = fitSize(big + (unit ? '  ' + trunc(unit, 10) : ''), (r - th) * 1.7, 36, 0.52);
    var us = clamp(bs * 0.42, 10, 15);
    s += '<g class="dac-fade"><text x="' + cx + '" y="' + r2(cy - 4) + '" text-anchor="middle" class="dac-big" style="font-size:' + r2(bs) + 'px">' +
      esc(big) + (unit && value !== null ? '<tspan class="dac-unit" style="font-size:' + r2(us) + 'px" dx="3">' + esc(trunc(unit, 10)) + '</tspan>' : '') + '</text>';
    if (title) s += text(cx, cy + 17, trunc(title, 22), 'dac-sub', ' text-anchor="middle" style="font-size:12px"');
    var tEnd = hasTarget ? clamp(target / max, 0, 1) : -1;
    if (!(tEnd >= 0 && tEnd < 0.08)) s += text(r2(cx - r), cy + 17, '0', 'dac-axis', ' text-anchor="middle"');
    if (max !== null && max > 0 && !(tEnd > 0.92)) s += text(r2(cx + r), cy + 17, short(max), 'dac-axis', ' text-anchor="middle"');
    s += '</g>';
    return s + '</svg>';
  }

  // ------------------------------------------------------------------
  // Fluid plots (spark, trend): fixed pixel height, full container width.
  // Lines live in a nested SVG stretched to the width with non-scaling strokes, so
  // strokes and text stay crisp and true-size at any width. Dots and text use % x positions.
  // ------------------------------------------------------------------
  function lineSegments(pts, gapBreak) {
    // pts: [{x: 0..1, y: px, k: ordinal}] in order, with nulls for gaps
    var segs = [], cur = [], prev = null, i;
    for (i = 0; i < pts.length; i++) {
      var p = pts[i];
      if (!p) { if (cur.length) segs.push(cur); cur = []; prev = null; continue; }
      if (prev && gapBreak && gapBreak(prev, p)) { segs.push(cur); cur = []; }
      cur.push(p); prev = p;
    }
    if (cur.length) segs.push(cur);
    return segs;
  }
  function segPath(seg, vw) {
    var d = '', i;
    for (i = 0; i < seg.length; i++) d += (i ? 'L' : 'M') + r2(seg[i].x * vw) + ' ' + r2(seg[i].y);
    return d;
  }
  function areaPath(seg, vw, base) {
    return segPath(seg, vw) + 'L' + r2(seg[seg.length - 1].x * vw) + ' ' + r2(base) + 'L' + r2(seg[0].x * vw) + ' ' + r2(base) + 'Z';
  }
  function xp(f) { return r2(f * 100) + '%'; }
  function dot(f, y, color, rad, halo) {
    return '<circle cx="' + xp(f) + '" cy="' + r2(y) + '" r="' + rad + '" style="fill:' + color +
      (halo ? ';stroke:' + NAMED.surface + ';stroke-width:' + halo : '') + '"/>';
  }
  function plotOpen(H) {
    return '<svg x="0" y="0" width="100%" height="' + r2(H) + '" viewBox="0 0 1000 ' + r2(H) + '" preserveAspectRatio="none" style="overflow:visible">';
  }
  function lineAttrs(color, w) {
    return ' vector-effect="non-scaling-stroke" style="fill:none;stroke:' + color + ';stroke-width:' + w +
      ';stroke-linecap:round;stroke-linejoin:round"';
  }

  // ------------------------------------------------------------------
  // spark: sparkline or small area chart, gaps for null
  // ------------------------------------------------------------------
  function spark(o) {
    o = o || {};
    var raw = o.points && o.points.length ? o.points : [];
    var vals = [], i, lo = Infinity, hi = -Infinity, n = raw.length;
    for (i = 0; i < n; i++) {
      var v = num(raw[i] && typeof raw[i] === 'object' ? raw[i].y : raw[i]);
      vals.push(v);
      if (v !== null) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
    }
    var target = num(o.target);
    if (target !== null && lo !== Infinity) { lo = Math.min(lo, target); hi = Math.max(hi, target); }
    var labels = o.labels || null;
    var H = clamp(posNum(o.height, 36), 12, 400);
    var lab = labels && (labels.first || labels.last) ? 14 : 0;
    var pad = 4, plotH = H - lab, y0 = pad, y1 = plotH - pad;
    var color = paint(o.color, o.state, NAMED.olive);
    if (lo === Infinity) { lo = 0; hi = 1; }
    if (o.area && lo > 0 && o.zero !== false) lo = 0;
    if (hi === lo) { hi = lo + 1; lo = lo - 1; }
    function yOf(v) { return y1 - (v - lo) / (hi - lo) * (y1 - y0); }
    var pts = [], last = -1, count = 0;
    for (i = 0; i < n; i++) {
      if (vals[i] === null) { pts.push(null); continue; }
      pts.push({ x: n > 1 ? i / (n - 1) : 0.5, y: yOf(vals[i]) });
      last = i; count++;
    }
    var segs = lineSegments(pts);
    var first = -1;
    for (i = 0; i < n; i++) if (vals[i] !== null) { first = i; break; }

    var aria = named(o) + (count === 0 ? 'no data' :
      (count === 1 ? fmt(vals[last]) + unitText(o.unit) :
        'from ' + fmt(vals[first]) + ' to ' + fmt(vals[last]) + unitText(o.unit) + ', low ' + fmt(lowest(vals)) + ', high ' + fmt(highest(vals))));
    if (target !== null) aria += ', target ' + fmt(target);

    var s = open('spark', o, aria, 'width="100%" height="' + H + '" style="display:block;width:100%;height:' + H + 'px;overflow:visible"');
    if (target !== null) {
      var ty = r2(yOf(target)) + 0.5;
      s += '<line x1="0" x2="100%" y1="' + ty + '" y2="' + ty + '" style="stroke:' + NAMED.target +
        ';stroke-opacity:.55;stroke-width:1;stroke-dasharray:3 3"/>';
    }
    s += '<g class="dac-line">' + plotOpen(plotH);
    for (i = 0; i < segs.length; i++) {
      if (o.area && segs[i].length > 1) s += '<path d="' + areaPath(segs[i], 1000, y1 + pad) + '" style="fill:' + color + ';fill-opacity:.14;stroke:none"/>';
      if (segs[i].length > 1) s += '<path d="' + segPath(segs[i], 1000) + '"' + lineAttrs(color, posNum(o.strokeWidth, 1.75)) + '/>';
    }
    s += '</svg>';
    for (i = 0; i < segs.length; i++) {
      if (segs[i].length === 1 && segs[i][0] !== pts[last]) s += dot(segs[i][0].x, segs[i][0].y, color, 2);
    }
    s += '</g>';
    if (last >= 0) s += '<g class="dac-fade">' + dot(pts[last].x, pts[last].y, color, 2.75, 1.5) + '</g>';
    if (lab) {
      if (labels.first) s += text('0', H - 2, trunc(labels.first, 16), 'dac-axis');
      if (labels.last) s += text('100%', H - 2, trunc(labels.last, 16), 'dac-axis', ' text-anchor="end"');
    }
    if (count === 0) s += '<line x1="0" x2="100%" y1="' + r2(plotH / 2) + '" y2="' + r2(plotH / 2) + '" style="stroke:' + NAMED.track + ';stroke-width:1.5;stroke-dasharray:2 4;stroke-linecap:round"/>';
    return s + '</svg>';
  }
  function lowest(a) { var m = null, i; for (i = 0; i < a.length; i++) if (a[i] !== null && (m === null || a[i] < m)) m = a[i]; return m; }
  function highest(a) { var m = null, i; for (i = 0; i < a.length; i++) if (a[i] !== null && (m === null || a[i] > m)) m = a[i]; return m; }

  // ------------------------------------------------------------------
  // Dates and ticks
  // ------------------------------------------------------------------
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function dayNum(x) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(str(x));
    if (!m) return null;
    var t = Date.UTC(+m[1], +m[2] - 1, +m[3]);
    return isFinite(t) ? Math.round(t / 864e5) : null;
  }
  function dayLabel(d, long) {
    var t = new Date(d * 864e5);
    return long ? MON[t.getUTCMonth()] + ' ' + t.getUTCFullYear() : t.getUTCDate() + ' ' + MON[t.getUTCMonth()];
  }
  function niceStep(range, count) {
    var raw = range / Math.max(1, count);
    var p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
  }

  // ------------------------------------------------------------------
  // trend: line chart with grid, date labels, target line and last-value dots
  // ------------------------------------------------------------------
  function trend(o) {
    o = o || {};
    var input = o.series && o.series.length ? o.series.slice(0, 3) : [];
    var H = clamp(posNum(o.height, 200), 80, 1000);
    var target = num(o.target), yUnit = str(o.yUnit);
    var series = [], i, j, minD = Infinity, maxD = -Infinity, lo = Infinity, hi = -Infinity, diffs = [];
    for (i = 0; i < input.length; i++) {
      var sr = input[i] || {}, raw = sr.points && sr.points.length ? sr.points : [], pts = [];
      for (j = 0; j < raw.length; j++) {
        var p = raw[j], x, y;
        if (p && typeof p === 'object' && !(p instanceof Array)) { x = p.x !== undefined ? p.x : p.date; y = p.y; }
        else if (p instanceof Array) { x = p[0]; y = p[1]; }
        else continue;
        var d = dayNum(x);
        if (d === null) continue;
        pts.push({ d: d, v: num(y) });
      }
      pts.sort(function (a, b) { return a.d - b.d; });
      for (j = 0; j < pts.length; j++) {
        minD = Math.min(minD, pts[j].d); maxD = Math.max(maxD, pts[j].d);
        if (pts[j].v !== null) { lo = Math.min(lo, pts[j].v); hi = Math.max(hi, pts[j].v); }
        if (j) diffs.push(pts[j].d - pts[j - 1].d);
      }
      series.push({ name: trunc(str(sr.name || sr.label), 40), color: paint(sr.color, sr.state, SERIES[i]), pts: pts });
    }
    var hasData = lo !== Infinity;
    // Typical spacing between points: anything much wider than that is a gap.
    diffs.sort(function (a, b) { return a - b; });
    var step = posNum(o.gapDays, 0) || Math.max(1, diffs.length ? diffs[Math.floor(diffs.length / 2)] : 1) * 1.5;

    // Y scale: zero-based unless the data go negative, "nice" ticks, room for the target.
    if (!hasData) { lo = 0; hi = target !== null && target > 0 ? target : 10; }
    if (target !== null) { lo = Math.min(lo, target); hi = Math.max(hi, target); }
    var yMin = num(o.yMin), yMax = num(o.yMax);
    if (yMin !== null) lo = Math.min(lo, yMin); else if (lo > 0) lo = 0;
    if (yMax !== null) hi = Math.max(hi, yMax);
    if (hi === lo) hi = lo + (Math.abs(lo) || 1);
    var nTicks = clamp(Math.round(posNum(o.yTicks, 4)), 2, 8);
    var ys = niceStep(hi - lo, nTicks - 1);
    var yTop = Math.ceil(hi / ys - 1e-9) * ys, yBot = Math.floor(lo / ys + 1e-9) * ys;
    if (yTop === yBot) yTop = yBot + ys;
    var ticks = [];
    for (var t = yBot; t <= yTop + ys / 2; t += ys) ticks.push(Math.round(t / ys) * ys);

    var tickLabels = [], gutter = 0;
    for (i = 0; i < ticks.length; i++) { tickLabels.push(short(ticks[i])); gutter = Math.max(gutter, tickLabels[i].length); }
    gutter = Math.round(gutter * 6.6 + 12);
    var top = 16, bottom = H - 24, ph = bottom - top;
    function yOf(v) { return bottom - (v - yBot) / (yTop - yBot) * ph; }
    var span = maxD - minD;
    function xOf(d) { return span > 0 ? (d - minD) / span : 0.5; }

    // Accessible summary.
    var aria = named(o), bits = [];
    for (i = 0; i < series.length; i++) {
      var sp = series[i].pts, fv = null, lv = null;
      for (j = 0; j < sp.length; j++) if (sp[j].v !== null) { if (!fv) fv = sp[j]; lv = sp[j]; }
      if (!lv) { bits.push((series[i].name || 'Series ' + (i + 1)) + ': no data'); continue; }
      bits.push((series[i].name ? series[i].name + ': ' : '') + fmt(lv.v) + unitText(yUnit) + ' on ' + dayLabel(lv.d) +
        (fv !== lv ? ', from ' + fmt(fv.v) + ' on ' + dayLabel(fv.d) : ''));
    }
    aria += bits.length && hasData ? bits.join('; ') : 'no data yet';
    if (target !== null) aria += '. Target ' + fmt(target) + unitText(yUnit);

    var s = open('trend', o, aria, 'width="100%" height="' + H + '" style="display:block;width:100%;height:' + H +
      'px;overflow:visible;box-sizing:border-box;padding-left:' + gutter + 'px;padding-right:6px"');

    // Grid and y labels (labels sit in the left padding).
    s += '<g class="dac-grid">';
    for (i = 0; i < ticks.length; i++) {
      var gy = Math.round(yOf(ticks[i])) + 0.5;
      s += '<line x1="0" x2="100%" y1="' + gy + '" y2="' + gy + '" style="stroke:' + NAMED.grid + ';stroke-width:1' +
        (ticks[i] === yBot ? '' : ';stroke-dasharray:2 3') + '"/>';
      s += text(-8, gy + 3.5, tickLabels[i], 'dac-axis', ' text-anchor="end"');
    }
    s += '</g>';

    // X labels: a few evenly spaced dates.
    if (span >= 0 && minD !== Infinity) {
      var longFmt = span > 300, nx = clamp(Math.round(posNum(o.xTicks, longFmt ? 3 : 4)), 2, 8), seen = {};
      if (span === 0) s += text('50%', H - 6, dayLabel(minD, longFmt), 'dac-axis', ' text-anchor="middle"');
      else {
        nx = Math.min(nx, span + 1);
        for (i = 0; i < nx; i++) {
          var dd = Math.round(minD + span * i / (nx - 1));
          if (seen[dd]) continue; seen[dd] = 1;
          var anc = i === 0 ? 'start' : i === nx - 1 ? 'end' : 'middle';
          s += text(xp(xOf(dd)), H - 6, dayLabel(dd, longFmt), 'dac-axis', ' text-anchor="' + anc + '"');
        }
      }
    }

    // Target line with label at the right; the label hops below the line if a last dot is in the way.
    var lastDots = [];
    for (i = 0; i < series.length; i++) {
      var q = series[i].pts;
      for (j = q.length - 1; j >= 0; j--) if (q[j].v !== null) { lastDots.push({ x: xOf(q[j].d), y: yOf(q[j].v), c: series[i].color }); break; }
    }
    if (target !== null) {
      var tyy = Math.round(yOf(target)) + 0.5;
      s += '<line class="dac-target" x1="0" x2="100%" y1="' + tyy + '" y2="' + tyy + '" style="stroke:' + NAMED.target +
        ';stroke-width:1.5;stroke-dasharray:5 4;stroke-linecap:round;stroke-opacity:.8"/>';
      var tl = str(o.targetLabel) || ('Target ' + fmt(target) + unitText(yUnit));
      var above = tyy - 6, below = tyy + 14, ly = above;
      for (i = 0; i < lastDots.length; i++) if (lastDots[i].x > 0.6 && lastDots[i].y > tyy - 22 && lastDots[i].y < tyy + 2) ly = below;
      if (ly === above && above < 10) ly = below;
      if (ly === below) for (i = 0; i < lastDots.length; i++) if (lastDots[i].x > 0.6 && lastDots[i].y > tyy - 2 && lastDots[i].y < tyy + 22) ly = above;
      s += text('100%', ly, trunc(tl, 28), 'dac-axis dac-target-label', ' text-anchor="end" dx="-10"');
    }

    // Lines.
    s += '<g class="dac-line">' + plotOpen(H);
    var singles = [];
    for (i = 0; i < series.length; i++) {
      var ser = series[i], pp = [];
      for (j = 0; j < ser.pts.length; j++) pp.push(ser.pts[j].v === null ? null : { x: xOf(ser.pts[j].d), y: yOf(ser.pts[j].v), d: ser.pts[j].d });
      var segs = lineSegments(pp, function (a, b) { return b.d - a.d > step; });
      for (j = 0; j < segs.length; j++) {
        if (segs[j].length > 1) s += '<path d="' + segPath(segs[j], 1000) + '"' + lineAttrs(ser.color, series.length > 1 ? 2 : 2.25) + '/>';
        else singles.push({ x: segs[j][0].x, y: segs[j][0].y, c: ser.color });
      }
    }
    s += '</svg>';
    for (i = 0; i < singles.length; i++) s += dot(singles[i].x, singles[i].y, singles[i].c, 2);
    s += '</g><g class="dac-fade">';
    for (i = 0; i < lastDots.length; i++) s += dot(lastDots[i].x, lastDots[i].y, lastDots[i].c, 4, 2);
    s += '</g>';
    if (!hasData) s += text('50%', top + ph / 2 + 4, str(o.empty) ? trunc(o.empty, 40) : 'No data yet', 'dac-sub', ' text-anchor="middle"');
    return s + '</svg>';
  }

  // ------------------------------------------------------------------
  // bars: horizontal bars against targets (fluid width)
  // ------------------------------------------------------------------
  function bars(o) {
    o = o || {};
    var items = o.items && o.items.length ? o.items : [];
    var bh = clamp(posNum(o.barHeight, 8), 3, 24), maxLabel = posNum(o.maxLabel, 30);
    var y = 0, body = '', parts = [], i;
    for (i = 0; i < items.length; i++) {
      var it = items[i] || {}, v = num(it.value), m = num(it.max), f = frac(v, m);
      var unit = str(it.unit !== undefined ? it.unit : o.unit);
      var lbl = trunc(str(it.label), maxLabel);
      var p = v !== null && m !== null && m > 0 ? pct(v / m) : null;
      var vt = it.valueText !== undefined ? str(it.valueText) :
        v === null ? 'no data' : (m !== null && m > 0 ? fmt(v) + ' of ' + fmt(m) : fmt(v)) + unitText(unit);
      parts.push(trunc(str(it.label), 60) + ': ' + (v === null ? 'no data' : (m !== null && m > 0 ? fmt(v) + ' of ' + fmt(m) : fmt(v)) + unitText(unit) + (p !== null ? ', ' + p + '%' : '')));
      var color = paint(it.color, it.state || 'good');
      var by = y + 22;
      body += '<g class="dac-row"' + (it.key !== undefined ? ' data-key="' + esc(it.key) + '"' : '') + '>';
      body += text(0, y + 14, lbl, 'dac-label');
      body += text('100%', y + 14, trunc(vt, 24), 'dac-value', ' text-anchor="end"');
      body += '<rect x="0" y="' + by + '" width="100%" height="' + bh + '" rx="' + bh / 2 + '" style="fill:' + NAMED.track + '"/>';
      if (f > 0) body += '<rect class="dac-bar-fill" x="0" y="' + by + '" width="' + xp(f) + '" height="' + bh + '" rx="' + bh / 2 + '" style="fill:' + color + '"/>';
      var tg = num(it.target);
      if (tg !== null && m !== null && m > 0) {
        body += '<line x1="' + xp(clamp(tg / m, 0, 1)) + '" x2="' + xp(clamp(tg / m, 0, 1)) + '" y1="' + (by - 3) + '" y2="' + (by + bh + 3) +
          '" style="stroke:' + NAMED.target + ';stroke-width:2;stroke-linecap:round"/>';
      }
      y = by + bh;
      if (it.sub !== undefined && it.sub !== null && str(it.sub) !== '') { body += text(0, y + 15, trunc(str(it.sub), 48), 'dac-sub'); y += 19; }
      body += '</g>';
      y += 14;
    }
    if (!items.length) { body = text(0, 16, str(o.empty) || 'Nothing to show yet', 'dac-sub'); y = 24; }
    else y -= 14;
    var H = Math.max(1, Math.ceil(y + 2));
    return open('bars', o, named(o) + (parts.length ? parts.join('; ') : 'no data'),
      'width="100%" height="' + H + '" style="display:block;width:100%;height:' + H + 'px;overflow:visible"') + body + '</svg>';
  }

  // ------------------------------------------------------------------
  // columns: stacked columns (expiry timeline by month)
  // ------------------------------------------------------------------
  function columns(o) {
    o = o || {};
    var cols = o.columns && o.columns.length ? o.columns.slice(0, 60) : [];
    var n = cols.length, H = clamp(posNum(o.height, 180), 60, 1000);
    var top = 20, bottom = H - 22, ph = bottom - top, i, j;
    var totals = [], maxT = 0;
    for (i = 0; i < n; i++) {
      var st = (cols[i] && cols[i].stacks) || [], tot = 0;
      for (j = 0; j < st.length; j++) { var sv = num(st[j] && st[j].value); if (sv !== null && sv > 0) tot += sv; }
      if (!st.length) { var cv = num(cols[i] && cols[i].value); if (cv !== null && cv > 0) tot = cv; }
      totals.push(tot); maxT = Math.max(maxT, tot);
    }
    var scale = Math.max(maxT, posNum(o.max, 0)) || 1;
    var hl = o.highlight, slot = n ? 100 / n : 100;
    var bwf = Math.min(0.62, 0.62 * n / 9) || 0.62, bw = slot * bwf;
    var showVals = o.values !== false && n <= 16;
    var labelEvery = Math.max(1, Math.ceil(n / 12));
    var maxChars = Math.max(3, Math.floor(44 * labelEvery / Math.max(n, 1)));
    var parts = [], s = '';

    s += '<line x1="0" x2="100%" y1="' + (bottom + 0.5) + '" y2="' + (bottom + 0.5) + '" style="stroke:' + NAMED.grid + ';stroke-width:1"/>';
    for (i = 0; i < n; i++) {
      var c = cols[i] || {}, stacks = c.stacks && c.stacks.length ? c.stacks : [{ value: c.value, state: c.state, color: c.color }];
      var key = c.key !== undefined && c.key !== null ? str(c.key) : str(c.label);
      var isHl = hl !== undefined && hl !== null && (hl === i || str(hl) === key);
      var x0 = slot * i + (slot - bw) / 2, h = 0, y = bottom, bitsA = [];
      s += '<g class="dac-col' + (isHl ? ' is-highlight' : '') + '" data-key="' + esc(key) + '" data-index="' + i + '">';
      if (isHl) s += '<rect x="' + r2(slot * i + slot * 0.06) + '%" y="2" width="' + r2(slot * 0.88) + '%" height="' + (H - 2) + '" rx="8" style="fill:' + NAMED.grid + ';fill-opacity:.7"/>';
      s += '<g class="dac-grow">';
      if (totals[i] > 0) {
        for (j = 0; j < stacks.length; j++) {
          var sk = stacks[j] || {}, v = num(sk.value);
          if (v === null || v <= 0) continue;
          var sh = v / scale * ph, gap = j > 0 && h > 0 ? 2 : 0, dh = Math.max(1.5, sh - gap);
          y = bottom - h - sh;
          s += '<rect x="' + r2(x0) + '%" y="' + r2(y) + '" width="' + r2(bw) + '%" height="' + r2(dh) + '" rx="' + r2(Math.min(3, dh / 2)) +
            '" style="fill:' + paint(sk.color, sk.state || 'good') + '"/>';
          h += sh;
          bitsA.push(fmt(v) + (sk.label ? ' ' + trunc(str(sk.label), 30) : ''));
        }
      } else {
        s += '<rect x="' + r2(x0) + '%" y="' + (bottom - 2) + '" width="' + r2(bw) + '%" height="2" rx="1" style="fill:' + NAMED.track + '"/>';
      }
      s += '</g>';
      if (showVals && totals[i] > 0) s += text(r2(slot * (i + 0.5)) + '%', bottom - h - 6, short(totals[i]), 'dac-value dac-fade', ' text-anchor="middle"');
      if (i % labelEvery === 0 || isHl) s += text(r2(slot * (i + 0.5)) + '%', H - 6, trunc(str(c.label), maxChars), 'dac-axis' + (isHl ? ' dac-strong' : ''), ' text-anchor="middle"');
      s += '</g>';
      parts.push(trunc(str(c.label), 30) + ' ' + fmt(totals[i]) + (bitsA.length > 1 ? ' (' + bitsA.join(', ') + ')' : ''));
    }
    if (!n) s += text('50%', top + ph / 2, str(o.empty) || 'Nothing to show yet', 'dac-sub', ' text-anchor="middle"');
    return open('columns', o, named(o) + (parts.length ? parts.join('; ') : 'no data'),
      'width="100%" height="' + H + '" style="display:block;width:100%;height:' + H + 'px;overflow:visible"') + s + '</svg>';
  }

  // ------------------------------------------------------------------
  // donut: composition
  // ------------------------------------------------------------------
  function donut(o) {
    o = o || {};
    var segs = o.segments && o.segments.length ? o.segments : [];
    var size = clamp(posNum(o.size, 160), 40, 2000);
    var th = clamp(posNum(o.thickness, size * 0.13), 3, size / 4);
    var c = size / 2, r = c - th / 2 - 1, total = 0, i, live = 0;
    for (i = 0; i < segs.length; i++) { var v = num(segs[i] && segs[i].value); if (v !== null && v > 0) { total += v; live++; } }
    var gapA = live > 1 ? clamp(180 / (Math.PI * r) * 2.5, 0.8, 4) : 0;
    var s = '', a = 0, parts = [];
    s += track(arc(c, c, r, 0, 360), th);
    for (i = 0; i < segs.length; i++) {
      var sg = segs[i] || {}, sv = num(sg.value), nm = trunc(str(sg.label), 40);
      parts.push(nm + ' ' + (sv === null ? 'no data' : fmt(sv) + (total > 0 && sv > 0 ? ' (' + pct(sv / total) + '%)' : '')));
      if (!(sv > 0) || total <= 0) continue;
      var sweep = sv / total * 360, a1 = a + sweep - gapA;
      if (a1 - a > 0.2) {
        s += '<path class="dac-arc" d="' + arc(c, c, r, a, Math.min(a1, a + 359.99)) + '" pathLength="100" style="fill:none;stroke:' +
          paint(sg.color, sg.state, CATS[i % 3]) + ';stroke-width:' + r2(th) + ';stroke-dasharray:100 100;stroke-dashoffset:0"/>';
      }
      a += sweep;
    }
    var ce = o.centre || o.center || {};
    var label = named(o) + (parts.length ? parts.join('; ') : 'no data');
    s += centreText(c, c, ce.big, ce.small, (r - th / 2) * 2 * 0.8, (r - th / 2) * 0.62);
    return open('donut', o, label, 'viewBox="0 0 ' + size + ' ' + size + '" style="width:100%;max-width:' + size + 'px;height:auto"') + s + '</svg>';
  }

  // ------------------------------------------------------------------
  // meter: thin inline bar with a target tick
  // ------------------------------------------------------------------
  function meter(o) {
    o = o || {};
    var bh = clamp(posNum(o.height, 6), 2, 24);
    var value = num(o.value), max = num(o.max), target = num(o.target), f = frac(value, max);
    var hasT = target !== null && max !== null && max > 0;
    var pad = hasT ? 3 : 0, H = bh + pad * 2;
    var p = value !== null && max !== null && max > 0 ? pct(value / max) : null;
    var label = named(o) + (value === null ? 'no data' : fmt(value) + (max !== null && max > 0 ? ' of ' + fmt(max) : '') + unitText(o.unit) + (p !== null ? ', ' + p + '%' : ''));
    if (hasT) label += ', target ' + fmt(target) + unitText(o.unit);
    var s = open('meter', o, label, 'width="100%" height="' + H + '" style="display:block;width:100%;height:' + H + 'px;overflow:visible"');
    s += '<rect x="0" y="' + pad + '" width="100%" height="' + bh + '" rx="' + bh / 2 + '" style="fill:' + NAMED.track + '"/>';
    if (f > 0) s += '<rect class="dac-bar-fill" x="0" y="' + pad + '" width="' + xp(f) + '" height="' + bh + '" rx="' + bh / 2 + '" style="fill:' + paint(o.color, o.state, STATE.good) + '"/>';
    if (hasT) {
      var tx = xp(clamp(target / max, 0, 1));
      s += '<line x1="' + tx + '" x2="' + tx + '" y1="0.75" y2="' + (H - 0.75) + '" style="stroke:' + NAMED.surface + ';stroke-width:4;stroke-linecap:round"/>';
      s += '<line x1="' + tx + '" x2="' + tx + '" y1="1" y2="' + (H - 1) + '" style="stroke:' + NAMED.target + ';stroke-width:2;stroke-linecap:round"/>';
    }
    return s + '</svg>';
  }

  // ------------------------------------------------------------------
  // legend: HTML list that matches the chart colours
  // ------------------------------------------------------------------
  function legend(o) {
    o = o || {};
    var items = o.items && o.items.length ? o.items : [], s = '', i;
    for (i = 0; i < items.length; i++) {
      var it = items[i] || {}, v = it.value;
      var vt = v === undefined || v === null || v === '' ? '' : (num(v) !== null && typeof v !== 'string' ? fmt(v) : trunc(str(v), 24));
      s += '<li class="dac-legend-item"><span class="dac-swatch" aria-hidden="true" style="background:' +
        paint(it.color, it.state, i < 3 ? CATS[i] : NAMED.muted) + '"></span><span class="dac-legend-label">' + esc(trunc(str(it.label), 40)) + '</span>' +
        (vt ? '<span class="dac-legend-value">' + esc(vt) + '</span>' : '') + '</li>';
    }
    return '<ul class="dac-legend' + (o.vertical ? ' dac-legend-v' : '') + '">' + s + '</ul>';
  }

  root.DAChart = {
    ring: ring, rings: rings, gauge: gauge, spark: spark, trend: trend,
    bars: bars, columns: columns, donut: donut, meter: meter, legend: legend,
    esc: esc
  };
})(typeof window !== 'undefined' ? window : this);
