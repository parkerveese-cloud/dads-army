/* Dads Army - home front stores tracker. Plain JavaScript, no build step, no internet needed. */
'use strict';
(function () {

  // ------------------------------------------------------------------
  // Constants
  // ------------------------------------------------------------------
  var CATS = [
    { id: 'food', label: 'Food', icon: '🥫' },
    { id: 'water', label: 'Water', icon: '💧' },
    { id: 'medical', label: 'Medical', icon: '🩹' },
    { id: 'power', label: 'Power & light', short: 'Power', icon: '🔦' },
    { id: 'cooking', label: 'Fuel & cooking', short: 'Cooking', icon: '🔥' },
    { id: 'hygiene', label: 'Hygiene', icon: '🧻' },
    { id: 'tools', label: 'Tools & safety', short: 'Tools', icon: '🛠️' },
    { id: 'comms', label: 'Comms', icon: '📻' },
    { id: 'shelter', label: 'Shelter & clothing', short: 'Shelter', icon: '⛺' },
    { id: 'docs', label: 'Docs & cash', icon: '💷' },
    { id: 'pets', label: 'Pets', icon: '🐾' },
    { id: 'other', label: 'Other', icon: '📦' }
  ];
  var CAT = {};
  CATS.forEach(function (c) { CAT[c.id] = c; });
  var UNITS = ['tin', 'jar', 'pack', 'bag', 'bottle', 'box', 'carton', 'bar', 'roll', 'kg', 'g', 'litre',
    'each', 'pair', 'set', 'kit', 'tube', 'tub', 'canister', '£'];
  var VIEWS = ['sitrep', 'stores', 'supply', 'hq'];

  var ICON = {
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
    minus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    alert: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6.5v7M12 17.5v.01"/></svg>',
    cross: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7L7 17"/></svg>',
    chev: '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>',
    print: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 9V4h10v5M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="7" y="14" width="10" height="6" rx="1"/></svg>',
    download: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11M7 10.5l5 5 5-5M5 20h14"/></svg>',
    upload: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V5M7 9.5l5-5 5 5M5 20h14"/></svg>',
    copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
    trash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
    edit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4z"/></svg>',
    list: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/></svg>'
  };

  // ------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------
  var S = null;                 // everything from /api/state
  var view = 'sitrep';
  var offline = false;
  var F = { q: '', cat: 'all', show: 'all', sort: 'category' };   // Stores filters
  var stack = [];               // open bottom sheets
  var toastTimer = null;
  var settingsQueue = {};
  var settingsTimer = null;

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  function $(sel, el) { return (el || document).querySelector(sel); }
  function $$(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function num(v) { var n = parseFloat(v); return isFinite(n) ? n : 0; }
  var nf = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 });
  var nf0 = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
  function fq(q) { return nf.format(Math.round(q * 1000) / 1000); }

  var NO_PLURAL = { each: 1, kg: 1, g: 1, ml: 1, l: 1, kcal: 1, oz: 1, lb: 1, lbs: 1, cl: 1 };
  function isMoney(unit) { return /^[£$€]$/.test(unit || ''); }
  function plural(unit, q) {
    if (!unit || q === 1 || NO_PLURAL[unit.toLowerCase()] || !/^[a-z]+$/i.test(unit) || unit.length < 3 || /s$/i.test(unit)) return unit;
    if (/(x|ch|sh)$/i.test(unit)) return unit + 'es';
    if (/[^aeiou]y$/i.test(unit)) return unit.slice(0, -1) + 'ies';
    return unit + 's';
  }
  function qu(q, unit) {
    if (isMoney(unit)) return unit + fq(q);
    return unit ? fq(q) + ' ' + plural(unit, q) : fq(q);
  }
  function howMany(unit) {
    if (isMoney(unit)) return 'How much (' + unit + ')?';
    return unit ? 'How many ' + plural(unit, 2) + '?' : 'How many?';
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function ymd(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function today() { return ymd(new Date()); }
  function parseYmd(s) { var p = String(s).slice(0, 10).split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function daysUntil(s) { return Math.round((parseYmd(s) - parseYmd(today())) / 864e5); }
  function addMonths(n) {
    var d = new Date(), day = d.getDate();
    d.setDate(1); d.setMonth(d.getMonth() + n);
    var last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
    d.setDate(Math.min(day, last));
    return ymd(d);
  }
  function fmtDate(s) { return parseYmd(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }); }
  function span(n) {
    if (n < 14) return n + (n === 1 ? ' day' : ' days');
    if (n < 60) return Math.round(n / 7) + ' weeks';
    if (n < 730) return Math.round(n / 30.44) + ' months';
    return (Math.round(n / 365.25 * 10) / 10) + ' years';
  }
  function expiryWords(s) {
    var n = daysUntil(s);
    if (n < 0) return 'Expired ' + span(-n) + ' ago';
    if (n === 0) return 'Expires today';
    return span(n) + ' left';
  }
  function shortLeft(s) {
    var n = daysUntil(s);
    if (n < 0) return 'Expired';
    if (n === 0) return 'Today';
    if (n < 14) return n + 'd left';
    if (n < 60) return Math.round(n / 7) + 'w left';
    return Math.round(n / 30.44) + 'mo left';
  }
  function expState(s) {
    if (!s) return 'none';
    var n = daysUntil(s);
    if (n < 0) return 'bad';
    if (n <= S.settings.warn_days) return 'warn';
    return 'ok';
  }
  function ago(ts) {
    if (!ts) return '';
    var t = new Date(String(ts).replace(' ', 'T'));
    var s = (Date.now() - t.getTime()) / 1000;
    if (isNaN(s)) return '';
    if (s < 60) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    if (s < 86400) return Math.floor(s / 3600) + 'h ago';
    if (s < 7 * 86400) return Math.floor(s / 86400) + 'd ago';
    return t.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  }
  function fmtDays(d) {
    if (d >= 1000) return '999+';
    if (d >= 10) return nf0.format(Math.floor(d));
    return String(Math.floor(d * 10) / 10);
  }
  function stateOf(frac) { return frac >= 1 ? 'good' : frac >= 0.5 ? 'warn' : 'bad'; }
  function statusIcon(state) { return state === 'good' ? ICON.check : state === 'warn' ? ICON.alert : ICON.cross; }
  function pill(state, text) {
    return '<span class="pill ' + (state === 'good' ? '' : state) + '">' + statusIcon(state) + esc(text) + '</span>';
  }
  function byName(a, b) { return a.name.localeCompare(b.name, 'en-GB', { sensitivity: 'base' }); }
  function catIndex(id) { for (var i = 0; i < CATS.length; i++) if (CATS[i].id === id) return i; return 99; }
  function cat(id) { return CAT[id] || CAT.other; }

  // ------------------------------------------------------------------
  // Derived data
  // ------------------------------------------------------------------
  function byId(id) {
    for (var i = 0; i < S.items.length; i++) if (S.items[i].id === id) return S.items[i];
    return null;
  }
  function total(it) { return it.batches.reduce(function (a, b) { return a + b.qty; }, 0); }
  function info(it) {
    var tot = total(it), soonest = null;
    it.batches.forEach(function (b) {
      if (b.expiry && b.qty > 0 && (soonest === null || b.expiry < soonest)) soonest = b.expiry;
    });
    return {
      total: tot,
      soonest: soonest,
      exp: soonest ? expState(soonest) : 'none',
      low: it.target_qty > 0 && tot < it.target_qty,
      out: tot <= 0,
      short: Math.max(0, Math.round((it.target_qty - tot) * 1000) / 1000)
    };
  }
  function locations() {
    var seen = {};
    S.items.forEach(function (it) { it.batches.forEach(function (b) { if (b.location) seen[b.location] = 1; }); });
    return Object.keys(seen).sort();
  }
  function lastLocation(it) {
    var best = null;
    (it ? it.batches : []).forEach(function (b) { if (!best || b.id > best.id) best = b; });
    return best ? best.location : '';
  }

  function readiness() {
    var st = S.settings;
    var people = st.adults + st.children;
    var kcalDay = st.adults * st.kcal_adult + st.children * st.kcal_child;
    var waterDay = people * st.water_per_person;
    var r = { people: people, kcalDay: kcalDay, waterDay: waterDay, kcal: 0, kcalOld: 0, litres: 0, litresOld: 0, noKcal: 0 };
    S.items.forEach(function (it) {
      var food = it.category === 'food', water = it.category === 'water' && it.litres_per_unit > 0;
      if (food && !(it.kcal_per_unit > 0)) return;
      if (!food && !water) return;
      it.batches.forEach(function (b) {
        var old = b.expiry && daysUntil(b.expiry) < 0;
        if (food) { if (old) r.kcalOld += b.qty * it.kcal_per_unit; else r.kcal += b.qty * it.kcal_per_unit; }
        if (water) { if (old) r.litresOld += b.qty * it.litres_per_unit; else r.litres += b.qty * it.litres_per_unit; }
      });
    });
    r.noKcal = S.items.filter(function (it) {
      return it.category === 'food' && !(it.kcal_per_unit > 0) && total(it) > 0 && !/tea|coffee|salt|stock|spice|herb/i.test(it.name);
    }).length;
    r.foodDays = kcalDay > 0 ? r.kcal / kcalDay : 0;
    r.waterDays = waterDay > 0 ? r.litres / waterDay : 0;
    r.foodOldDays = kcalDay > 0 ? r.kcalOld / kcalDay : 0;
    r.waterOldDays = waterDay > 0 ? r.litresOld / waterDay : 0;
    var kit = S.items.filter(function (it) { return it.target_qty > 0 && it.category !== 'food' && it.category !== 'water'; });
    r.kit = kit.length;
    r.kitPct = kit.length ? kit.reduce(function (a, it) { return a + Math.min(1, total(it) / it.target_qty); }, 0) / kit.length : 0;
    r.hold = Math.min(r.foodDays, r.waterDays);
    r.limit = r.foodDays < r.waterDays ? 'food' : r.waterDays < r.foodDays ? 'water' : '';
    return r;
  }

  // ------------------------------------------------------------------
  // API
  // ------------------------------------------------------------------
  function setOnline(ok) {
    offline = !ok;
    var c = $('#conn');
    c.classList.toggle('down', !ok);
    $('.conn-label', c).textContent = ok ? 'HQ' : 'Offline';
    $('#offline').hidden = ok;
  }
  function api(method, path, body) {
    var opt = { method: method, headers: { 'Content-Type': 'application/json' }, cache: 'no-store' };
    if (body !== undefined) opt.body = JSON.stringify(body);
    return fetch(path, opt).then(function (res) {
      setOnline(true);
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) throw new Error(data.error || ('Error ' + res.status));
        return data;
      });
    }, function () {
      setOnline(false);
      throw new Error("Can't reach HQ - check the Pi and your Wi-Fi.");
    });
  }
  function refresh() {
    return api('GET', 'api/state').then(function (data) {
      S = data;
      updateDatalists();
      render();
    });
  }
  function run(fn, btn) {
    if (btn) btn.disabled = true;
    return Promise.resolve().then(fn).catch(function (e) {
      toast(e.message || 'Something went wrong', { error: true });
    }).then(function () { if (btn) btn.disabled = false; });
  }

  // ------------------------------------------------------------------
  // Rendering: shell
  // ------------------------------------------------------------------
  function render() {
    $$('.tab').forEach(function (t) { t.setAttribute('aria-current', t.dataset.tab === view ? 'page' : 'false'); });
    var el = $('#view');
    if (!S) {
      el.dataset.view = '';
      el.innerHTML = offline
        ? '<div class="card empty"><div class="crate">📡</div><h2>No signal from HQ</h2><p>The app couldn\'t reach the Pi. Check it\'s switched on and this phone is on the home Wi-Fi.</p><button class="btn primary" data-act="retry">Try again</button></div>'
        : '<div class="loading">Mustering the troops…</div>';
      return;
    }
    updateBadge();
    if (view === 'stores') renderStores(el);
    else {
      el.dataset.view = view;
      if (view === 'supply') renderSupply(el);
      else if (view === 'hq') renderHQ(el);
      else renderSitrep(el);
    }
    if (stack.length && stack[stack.length - 1].type === 'item') renderSheet();
  }

  function updateBadge() {
    var n = S.items.filter(function (it) { return info(it).low; }).length +
      S.shopping.filter(function (s) { return !s.done; }).length;
    var b = $('#supplyBadge');
    b.hidden = n === 0;
    b.textContent = n > 99 ? '99+' : String(n);
  }

  function updateDatalists() {
    var units = {};
    UNITS.forEach(function (u) { units[u] = 1; });
    S.items.forEach(function (it) { if (it.unit) units[it.unit] = 1; });
    $('#dl-units').innerHTML = Object.keys(units).map(function (u) { return '<option value="' + esc(u) + '">'; }).join('');
    $('#dl-locations').innerHTML = locations().map(function (l) { return '<option value="' + esc(l) + '">'; }).join('');
  }

  function emptyCard() {
    var st = S.settings;
    return '<div class="card empty"><div class="crate">📦</div><h2>Stores are empty</h2>' +
      '<p>Load a starter list of essentials sized for your household, or add your own items one at a time.</p>' +
      '<div class="btn-stack"><button class="btn primary block" data-act="seed">Load starter list</button>' +
      '<button class="btn block" data-act="new">' + ICON.plus + ' Add an item</button></div></div>' +
      '<div class="card"><p class="small muted" style="margin:0">Starter targets will be sized for <b>' +
      st.adults + ' adult' + (st.adults === 1 ? '' : 's') + '</b> and <b>' + st.children + ' child' + (st.children === 1 ? '' : 'ren') +
      '</b> over <b>' + st.target_days + ' days</b>. <button class="link" data-tab="hq">Change household</button></p></div>';
  }

  // ------------------------------------------------------------------
  // Sitrep
  // ------------------------------------------------------------------
  function meter(label, value, frac, note) {
    var state = stateOf(frac);
    var pct = Math.max(0, Math.min(100, frac * 100));
    return '<div class="meter" data-state="' + state + '">' +
      '<div class="meter-head"><span class="meter-label">' + label + '</span><span class="meter-val">' + value + '</span></div>' +
      '<div class="meter-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round(pct) + '"><div class="meter-fill" style="width:' + pct.toFixed(1) + '%"></div></div>' +
      (note ? '<div class="meter-note">' + note + '</div>' : '') + '</div>';
  }
  function tile(n, label, state, show) {
    var s = n === 0 ? 'good' : state;
    return '<button class="tile" data-state="' + s + '" data-act="go" data-show="' + show + '">' +
      '<span class="tile-top"><span class="tile-num">' + n + '</span><span class="tile-ico">' + statusIcon(s) + '</span></span>' +
      '<span class="tile-label">' + label + '</span></button>';
  }

  function renderSitrep(el) {
    if (!S.items.length) { el.innerHTML = emptyCard(); return; }
    var st = S.settings, r = readiness(), target = st.target_days;
    var html = '';

    // Hero: how long could we hold out?
    if (r.people === 0) {
      html += '<section class="card hero"><div class="eyebrow">Situation report</div><p style="margin-top:10px">Tell HQ who you\'re feeding to see how long your stores will last.</p><button class="btn primary" data-tab="hq">Set up household</button></section>';
    } else {
      var hs = stateOf(r.hold / target);
      var limit = r.limit === 'food' ? 'Food runs out first' : r.limit === 'water' ? 'Water runs out first' : '';
      var foodNote = nf0.format(r.kcal) + ' kcal stored · ' + nf0.format(r.kcalDay) + ' needed a day';
      if (r.foodOldDays >= 0.1) foodNote += ' · +' + fmtDays(r.foodOldDays) + ' days in expired stock';
      if (r.noKcal) foodNote += ' · ' + r.noKcal + ' item' + (r.noKcal === 1 ? '' : 's') + ' with no calories set';
      var waterNote = fq(Math.round(r.litres * 10) / 10) + ' L stored · ' + fq(r.waterDay) + ' L needed a day';
      if (r.waterOldDays >= 0.1) waterNote += ' · +' + fmtDays(r.waterOldDays) + ' days past best-before';
      html += '<section class="card hero">' +
        '<div class="eyebrow">You could hold out for</div>' +
        '<div class="hero-num">' + fmtDays(r.hold) + '<small>' + (fmtDays(r.hold) === '1' ? 'day' : 'days') + '</small></div>' +
        '<div class="hero-sub">' + pill(hs, hs === 'good' ? target + '-day target met' : 'Target ' + target + ' days') +
        (limit ? '<span>' + limit + '</span>' : '') + '</div>' +
        '<div class="meters">' +
        meter('🥫 Food', fmtDays(r.foodDays) + ' of ' + target + ' days', r.foodDays / target, foodNote) +
        meter('💧 Water', fmtDays(r.waterDays) + ' of ' + target + ' days', r.waterDays / target, waterNote) +
        (r.kit ? meter('🧰 Kit &amp; supplies', Math.round(r.kitPct * 100) + '% stocked', r.kitPct, 'Medical, power, hygiene, tools and the rest against their targets') : '') +
        '</div></section>';
    }

    // Alert tiles
    var cnt = { bad: 0, warn: 0, low: 0 };
    S.items.forEach(function (it) {
      var i = info(it);
      if (i.exp === 'bad') cnt.bad++; else if (i.exp === 'warn') cnt.warn++;
      if (i.low) cnt.low++;
    });
    html += '<div class="tiles">' +
      tile(cnt.bad, 'Expired', 'bad', 'expired') +
      tile(cnt.warn, 'Expiring in ' + st.warn_days + ' days', 'warn', 'soon') +
      tile(cnt.low, 'Below target', 'warn', 'low') + '</div>';

    // Use first
    var upcoming = [];
    S.items.forEach(function (it) {
      it.batches.forEach(function (b) { if (b.expiry && b.qty > 0) upcoming.push({ it: it, b: b }); });
    });
    upcoming.sort(function (a, b) { return a.b.expiry < b.b.expiry ? -1 : a.b.expiry > b.b.expiry ? 1 : 0; });
    var urgent = upcoming.filter(function (x) { return expState(x.b.expiry) !== 'ok'; });
    var showList = (urgent.length ? urgent : upcoming).slice(0, 6);
    if (showList.length) {
      html += '<section class="card flush"><div class="card-head"><h2>' + (urgent.length ? 'Use these first' : 'Next to expire') + '</h2>' +
        (upcoming.length > showList.length ? '<button class="link" data-act="go" data-show="all" data-sort="expiry">See all</button>' : '') + '</div><div class="list">';
      showList.forEach(function (x) {
        var es = expState(x.b.expiry);
        html += '<div class="li"><span class="li-ico">' + cat(x.it.category).icon + '</span>' +
          '<button class="li-main" data-act="open" data-id="' + x.it.id + '"><div class="li-title">' + esc(x.it.name) + '</div>' +
          '<div class="li-sub"><span class="badge ' + (es === 'ok' ? 'plain' : es) + '">' + esc(expiryWords(x.b.expiry)) + '</span>' +
          '<span>' + esc(qu(x.b.qty, x.it.unit)) + (x.b.location ? ' · ' + esc(x.b.location) : '') + '</span></div></button>' +
          '<button class="qbtn" data-act="use" data-id="' + x.it.id + '" aria-label="Use one ' + esc(x.it.name) + '">' + ICON.minus + '</button></div>';
      });
      html += '</div></section>';
    }

    // Categories
    html += '<section class="card flush"><div class="card-head"><h2>Stores by category</h2><span class="small muted">at target</span></div><div class="list">';
    CATS.forEach(function (c) {
      var its = S.items.filter(function (it) { return it.category === c.id; });
      if (!its.length) return;
      var tg = its.filter(function (it) { return it.target_qty > 0; });
      var met = tg.filter(function (it) { return total(it) >= it.target_qty; }).length;
      var pct = tg.length ? met / tg.length : null;
      html += '<button class="li" data-act="cat-go" data-cat="' + c.id + '"><span class="li-ico">' + c.icon + '</span>' +
        '<span class="li-main"><span class="li-title">' + esc(c.label) + '</span>' +
        '<span class="li-sub">' + its.length + ' item' + (its.length === 1 ? '' : 's') + (tg.length ? ' · ' + met + ' of ' + tg.length + ' at target' : '') + '</span>' +
        (pct !== null ? '<span class="catbar"><i style="width:' + (pct * 100).toFixed(1) + '%"></i></span>' : '') + '</span>' +
        '<span class="cat-pct">' + (pct !== null ? Math.round(pct * 100) + '%' : '') + '</span>' + ICON.chev + '</button>';
    });
    html += '</div></section>';

    // Recent activity
    if (S.log.length) {
      html += '<section class="card"><div class="card-head"><h2>Latest orders</h2><button class="link" data-tab="hq">Full log</button></div>' +
        logHtml(S.log.slice(0, 4)) + '</section>';
    }
    html += '<p class="tagline">Don\'t panic · stay supplied</p>';
    el.innerHTML = html;
  }

  var LOG_VERB = { added: 'Added', stocked: 'Stocked', used: 'Used', adjusted: 'Adjusted', edited: 'Edited', removed: 'Deleted',
    undo: 'Undone', starter: 'Starter list', restored: 'Restored', settings: 'Settings', supply: 'Supply run' };
  function logHtml(entries) {
    return entries.map(function (l) {
      return '<div class="log-item"><span class="log-dot ' + esc(l.action) + '"></span><div class="log-text"><b>' +
        esc(LOG_VERB[l.action] || l.action) + '</b>' + (l.item ? ' ' + esc(l.item) : '') +
        (l.detail ? '<div class="small muted">' + esc(l.detail) + '</div>' : '') + '</div><span class="log-when">' + esc(ago(l.ts)) + '</span></div>';
    }).join('');
  }

  // ------------------------------------------------------------------
  // Stores
  // ------------------------------------------------------------------
  var SHOW_OPTS = [['all', 'Show: everything'], ['expired', 'Expired'], ['soon', 'Expiring soon'], ['low', 'Below target'],
    ['out', 'Out of stock'], ['stocked', 'In stock']];
  var SORT_OPTS = [['category', 'Sort: category'], ['name', 'Sort: A–Z'], ['expiry', 'Sort: soonest expiry'],
    ['short', 'Sort: most needed'], ['recent', 'Sort: recently changed']];

  function renderStores(el) {
    if (!S.items.length) { el.dataset.view = ''; el.innerHTML = emptyCard(); return; }
    if (el.dataset.view !== 'stores' || !$('#q', el)) {
      el.dataset.view = 'stores';
      el.innerHTML =
        '<div class="search">' + ICON.search + '<input type="search" id="q" placeholder="Search item, place or note" autocomplete="off" enterkeyhint="search" aria-label="Search stores"></div>' +
        '<div class="chips scroll-x" id="catChips"></div>' +
        '<div class="filters"><select id="fShow" aria-label="Show">' + SHOW_OPTS.map(opt).join('') + '</select>' +
        '<select id="fSort" aria-label="Sort by">' + SORT_OPTS.map(opt).join('') + '</select></div>' +
        '<div id="storeList"></div>';
    }
    var q = $('#q');
    if (q.value !== F.q) q.value = F.q;
    $('#fShow').value = F.show;
    $('#fSort').value = F.sort;
    var counts = {};
    S.items.forEach(function (it) { counts[it.category] = (counts[it.category] || 0) + 1; });
    $('#catChips').innerHTML = '<button class="chip" data-act="cat" data-cat="all" aria-pressed="' + (F.cat === 'all') + '">All <span class="n">' + S.items.length + '</span></button>' +
      CATS.filter(function (c) { return counts[c.id]; }).map(function (c) {
        return '<button class="chip" data-act="cat" data-cat="' + c.id + '" aria-pressed="' + (F.cat === c.id) + '">' + c.icon + ' ' + esc(c.short || c.label) + ' <span class="n">' + counts[c.id] + '</span></button>';
      }).join('');
    renderStoreList();
  }
  function opt(o) { return '<option value="' + o[0] + '">' + esc(o[1]) + '</option>'; }

  function filtered() {
    var q = F.q.trim().toLowerCase();
    var list = S.items.map(function (it) { return { it: it, i: info(it) }; });
    if (F.cat !== 'all') list = list.filter(function (x) { return x.it.category === F.cat; });
    if (q) {
      list = list.filter(function (x) {
        var hay = [x.it.name, x.it.notes, x.it.unit, cat(x.it.category).label]
          .concat(x.it.batches.map(function (b) { return b.location; })).join(' ').toLowerCase();
        return q.split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
      });
    }
    var show = {
      expired: function (x) { return x.i.exp === 'bad'; },
      soon: function (x) { return x.i.exp === 'warn'; },
      low: function (x) { return x.i.low; },
      out: function (x) { return x.i.out; },
      stocked: function (x) { return !x.i.out; }
    }[F.show];
    if (show) list = list.filter(show);
    var sorters = {
      name: function (a, b) { return byName(a.it, b.it); },
      category: function (a, b) { return catIndex(a.it.category) - catIndex(b.it.category) || byName(a.it, b.it); },
      expiry: function (a, b) {
        if (a.i.soonest && b.i.soonest) return a.i.soonest < b.i.soonest ? -1 : a.i.soonest > b.i.soonest ? 1 : byName(a.it, b.it);
        return a.i.soonest ? -1 : b.i.soonest ? 1 : byName(a.it, b.it);
      },
      short: function (a, b) {
        var fa = a.it.target_qty > 0 ? a.i.short / a.it.target_qty : -1;
        var fb = b.it.target_qty > 0 ? b.i.short / b.it.target_qty : -1;
        return fb - fa || b.i.short - a.i.short || byName(a.it, b.it);
      },
      recent: function (a, b) { return a.it.updated_at < b.it.updated_at ? 1 : a.it.updated_at > b.it.updated_at ? -1 : 0; }
    };
    list.sort(sorters[F.sort] || sorters.category);
    return list;
  }

  function rowHtml(it, i, showIcon) {
    var badges = '';
    if (i.exp === 'bad') badges += '<span class="badge bad">Expired</span>';
    else if (i.exp === 'warn') badges += '<span class="badge warn">' + esc(shortLeft(i.soonest)) + '</span>';
    if (i.out && it.target_qty > 0) badges += '<span class="badge bad">Out</span>';
    else if (i.low) badges += '<span class="badge warn">Low</span>';
    var locs = {};
    it.batches.forEach(function (b) { if (b.location) locs[b.location] = 1; });
    var lk = Object.keys(locs);
    var where = lk.length === 1 ? lk[0] : lk.length > 1 ? lk.length + ' places' : '';
    var amount;
    if (isMoney(it.unit)) {
      amount = '<b>' + esc(it.unit + fq(i.total)) + '</b>' + (it.target_qty > 0 ? ' of ' + esc(it.unit + fq(it.target_qty)) : '');
    } else {
      amount = '<b>' + fq(i.total) + '</b>' + (it.target_qty > 0 ? ' of ' + fq(it.target_qty) : '') +
        (it.unit ? ' ' + esc(plural(it.unit, it.target_qty > 0 ? it.target_qty : i.total)) : '');
    }
    return '<div class="row' + (i.out ? ' is-out' : '') + '">' +
      '<button class="row-main" data-act="open" data-id="' + it.id + '">' +
      (showIcon ? '<span class="row-ico">' + cat(it.category).icon + '</span>' : '') +
      '<span class="row-text"><span class="row-name">' + esc(it.name) + '</span>' +
      '<span class="row-sub"><span>' + amount + '</span>' + (where ? '<span>· ' + esc(where) + '</span>' : '') + badges + '</span></span></button>' +
      '<div class="row-ctl">' +
      '<button class="qbtn" data-act="use" data-id="' + it.id + '" aria-label="Use one ' + esc(it.name) + '"' + (i.out ? ' disabled' : '') + '>' + ICON.minus + '</button>' +
      '<button class="qbtn add" data-act="stock" data-id="' + it.id + '" aria-label="Add ' + esc(it.name) + '">' + ICON.plus + '</button>' +
      '</div></div>';
  }

  function renderStoreList() {
    var box = $('#storeList');
    if (!box) return;
    var list = filtered();
    if (!list.length) {
      box.innerHTML = '<div class="card empty"><div class="crate">🔍</div><h2>Nothing here</h2><p>No items match that search or filter.</p><button class="btn" data-act="clear-filters">Clear filters</button></div>';
      return;
    }
    var html = '<div class="result-count">' + list.length + ' item' + (list.length === 1 ? '' : 's') + '</div><div class="card flush">';
    if (F.sort === 'category') {
      var cur = null;
      list.forEach(function (x) {
        if (x.it.category !== cur) {
          cur = x.it.category;
          var n = list.filter(function (y) { return y.it.category === cur; }).length;
          html += '<div class="group-head">' + cat(cur).icon + ' ' + esc(cat(cur).label) + ' <span class="n">' + n + '</span></div>';
        }
        html += rowHtml(x.it, x.i, false);
      });
    } else {
      list.forEach(function (x) { html += rowHtml(x.it, x.i, true); });
    }
    box.innerHTML = html + '</div>';
  }

  // ------------------------------------------------------------------
  // Supply run
  // ------------------------------------------------------------------
  function shortList() {
    return S.items.map(function (it) { return { it: it, i: info(it) }; })
      .filter(function (x) { return x.i.low; })
      .sort(function (a, b) { return catIndex(a.it.category) - catIndex(b.it.category) || byName(a.it, b.it); });
  }

  function renderSupply(el) {
    var short = shortList();
    var todo = S.shopping.filter(function (s) { return !s.done; }).length;
    var done = S.shopping.length - todo;
    var ha = S.server.ha && S.server.ha.todo ? S.server.ha : null;
    var ticked = ha ? ha.ticked || [] : [];
    var html = '<section class="card"><div class="card-head"><h2>Supply run</h2><span class="small muted">' + (short.length + todo) + ' to get</span></div>' +
      '<p class="small muted">Everything below target, plus anything you add. Back from the shops? Tap <b>Got it</b> to put it in the stores.' +
      (ha ? ' It\'s also on your Home Assistant list <b>' + esc(ha.todo_name) + '</b>.' : '') + '</p>' +
      '<div class="btn-row"><button class="btn" data-act="copy-list">' + ICON.copy + ' Copy list</button>' +
      '<button class="btn" data-act="print-list">' + ICON.print + ' Print</button></div></section>';

    html += '<section class="card flush"><div class="card-head"><h2>Below target</h2><span class="small muted">' + short.length + '</span></div>';
    if (!short.length) {
      html += '<p class="li muted">Nothing below target. All squared away.</p>';
    } else {
      var cur = null;
      short.forEach(function (x) {
        if (x.it.category !== cur) {
          cur = x.it.category;
          html += '<div class="group-head">' + cat(cur).icon + ' ' + esc(cat(cur).label) + '</div>';
        }
        html += '<div class="li"><button class="li-main" data-act="open" data-id="' + x.it.id + '"><div class="li-title">' + esc(x.it.name) + '</div>' +
          '<div class="need">Get <b>' + esc(qu(x.i.short, x.it.unit)) + '</b> · have ' + esc(fq(x.i.total)) + ' of ' + esc(fq(x.it.target_qty)) + '</div>' +
          (ticked.indexOf(x.it.id) >= 0 ? '<span class="badge ok ha-tick">' + ICON.check + ' Ticked off in Home Assistant</span>' : '') + '</button>' +
          '<button class="btn small" data-act="stock" data-id="' + x.it.id + '" data-qty="' + x.i.short + '">Got it</button></div>';
      });
    }
    html += '</section>';

    html += '<section class="card"><div class="card-head"><h2>Also get</h2>' +
      (done ? '<button class="link" data-act="shop-clear">Clear ticked (' + done + ')</button>' : '') + '</div>' +
      '<form class="add-row" id="shopForm" autocomplete="off"><input type="text" name="text" placeholder="e.g. Spare fuses" maxlength="200" enterkeyhint="done" aria-label="Add to the list">' +
      '<button class="btn primary" type="submit">Add</button></form><div class="list">';
    S.shopping.forEach(function (s) {
      html += '<div class="li"><button class="check" role="checkbox" aria-checked="' + (s.done ? 'true' : 'false') + '" data-act="shop-toggle" data-id="' + s.id + '">' +
        '<span class="box">' + ICON.check + '</span><span class="li-title">' + esc(s.text) + '</span></button>' +
        '<button class="icon-btn" data-act="shop-del" data-id="' + s.id + '" aria-label="Remove ' + esc(s.text) + '">' + ICON.close + '</button></div>';
    });
    html += '</div></section>';
    el.innerHTML = html;
  }

  function supplyText() {
    var lines = ['DADS ARMY - Supply run, ' + new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }), ''];
    var short = shortList();
    if (short.length) {
      lines.push('Below target:');
      short.forEach(function (x) { lines.push('- ' + x.it.name + ': ' + qu(x.i.short, x.it.unit)); });
    }
    var extra = S.shopping.filter(function (s) { return !s.done; });
    if (extra.length) {
      if (short.length) lines.push('');
      lines.push('Also get:');
      extra.forEach(function (s) { lines.push('- ' + s.text); });
    }
    if (!short.length && !extra.length) lines.push('Nothing needed. All squared away.');
    return lines.join('\n');
  }

  function copyText(text) {
    var fallback = function () {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '0';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      return ok;
    };
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return fallback(); });
    }
    return Promise.resolve(fallback());
  }

  // ------------------------------------------------------------------
  // HQ (settings)
  // ------------------------------------------------------------------
  function stepperHtml(name, value, label, step, isSetting) {
    step = step || 1;
    return '<div class="stepper"><button type="button" data-step="-' + step + '" aria-label="Less">' + ICON.minus + '</button>' +
      '<input type="number" ' + (isSetting ? 'data-setting="' + name + '" id="set-' + name + '"' : 'name="' + name + '"') +
      ' value="' + esc(value) + '" inputmode="decimal" min="0" step="any" aria-label="' + esc(label) + '">' +
      '<button type="button" data-step="' + step + '" aria-label="More">' + ICON.plus + '</button></div>';
  }
  function setRow(key, label, hint, value, step) {
    return '<div class="set-row"><label for="set-' + key + '">' + esc(label) + (hint ? '<span class="hint">' + esc(hint) + '</span>' : '') + '</label>' +
      stepperHtml(key, value, label, step, true) + '</div>';
  }

  function renderHQ(el) {
    var st = S.settings, r = readiness(), target = st.target_days;
    var theme = document.documentElement.dataset.theme || 'auto';
    var html = '<section class="card"><div class="card-head"><h2>Household</h2></div>' +
      setRow('adults', 'Adults', '', st.adults, 1) +
      setRow('children', 'Children', '', st.children, 1) +
      setRow('kcal_adult', 'Calories per adult', 'kcal a day', st.kcal_adult, 100) +
      setRow('kcal_child', 'Calories per child', 'kcal a day', st.kcal_child, 100) +
      setRow('water_per_person', 'Water per person', 'litres a day (drinking & cooking)', st.water_per_person, 0.5) +
      '<div class="needs">Your household needs <b>' + nf0.format(r.kcalDay) + ' kcal</b> and <b>' + fq(r.waterDay) + ' L of water</b> a day. ' +
      'For ' + target + ' days that\'s <b>' + nf0.format(r.kcalDay * target) + ' kcal</b> and <b>' + nf0.format(r.waterDay * target) + ' L</b>.</div></section>';

    html += '<section class="card"><div class="card-head"><h2>Readiness target</h2></div>' +
      '<p class="small muted">How many days should your stores last?</p><div class="chips">' +
      [3, 7, 14, 30, 90, 180, 365].map(function (d) {
        return '<button class="chip" data-act="set" data-key="target_days" data-val="' + d + '" aria-pressed="' + (st.target_days === d) + '">' + (d === 365 ? '1 year' : d + ' days') + '</button>';
      }).join('') + '</div>' +
      setRow('target_days', 'Custom', 'days', st.target_days, 1) +
      '<div class="card-head" style="margin-top:12px"><h2>Expiry warning</h2></div>' +
      '<p class="small muted">Flag stock this many days before it expires.</p><div class="chips">' +
      [14, 30, 60, 90].map(function (d) {
        return '<button class="chip" data-act="set" data-key="warn_days" data-val="' + d + '" aria-pressed="' + (st.warn_days === d) + '">' + d + ' days</button>';
      }).join('') + '</div></section>';

    html += '<section class="card"><div class="card-head"><h2>Hard copy &amp; backups</h2></div>' +
      '<p class="small muted">If the power goes, so does the Pi. Keep a printed copy with the stores, and a backup somewhere other than the Pi.</p>' +
      '<div class="btn-stack">' +
      '<button class="btn block" data-act="print">' + ICON.print + ' Print full inventory</button>' +
      '<a class="btn block" href="api/backup.json" download>' + ICON.download + ' Download backup</a>' +
      '<a class="btn block" href="api/export.csv" download>' + ICON.download + ' Export spreadsheet (CSV)</a>' +
      '<button class="btn block" data-act="restore">' + ICON.upload + ' Restore from a backup…</button></div>' +
      '<p class="small muted" style="margin:10px 0 0">The Pi also saves its own copy every day' +
      (S.server.last_backup ? ' (last one ' + esc(ago(S.server.last_backup)) + ')' : '') + '.</p></section>';

    html += '<section class="card"><div class="card-head"><h2>Starter list</h2></div>' +
      '<p class="small muted">Adds about 95 suggested essentials at zero stock, with targets sized for your household and ' + target + '-day goal. ' +
      'Anything you already have is skipped, and you can delete what you don\'t need.</p>' +
      '<button class="btn block" data-act="seed">Load starter list</button></section>';

    html += haCard();

    html += '<section class="card"><div class="card-head"><h2>Appearance</h2></div><div class="seg" role="group" aria-label="Theme">' +
      [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (t) {
        return '<button data-act="theme" data-val="' + t[0] + '" aria-pressed="' + (theme === t[0]) + '">' + t[1] + '</button>';
      }).join('') + '</div></section>';

    html += '<section class="card"><div class="card-head"><h2>Activity log</h2><span class="small muted">last ' + S.log.length + '</span></div>' +
      (S.log.length ? logHtml(S.log) : '<p class="small muted">Nothing yet.</p>') + '</section>';
    html += '<p class="tagline">Dads Army v' + esc(S.server.version) + ' · Don\'t panic</p>';
    el.innerHTML = html;
  }

  // Only shown when Dads Army runs as a Home Assistant app.
  function haCard() {
    var ha = S.server.ha;
    if (!ha) return '';
    var html = '<section class="card"><div class="card-head"><h2>Home Assistant</h2></div>';
    if (!ha.todo) {
      html += '<p class="small muted">Put the supply run on a Home Assistant to-do list. Tick things off there, and add to it from anywhere, ' +
        'including by voice: <i>“Add matches to the supply run list”</i>.</p>' +
        '<div class="btn-stack"><button class="btn primary block" data-act="ha-make">' + ICON.list + ' Make a “Supply run” list</button>' +
        '<button class="btn block" data-act="ha-pick">Use a list I already have…</button></div>';
    } else {
      var state = ha.ok === false ? pill('bad', 'Not syncing') : ha.ok ? pill('good', 'In step') : pill('warn', 'Starting');
      html += '<div class="ha-link"><div class="li-main"><span class="li-title">' + esc(ha.todo_name) + '</span>' +
        '<span class="small muted">' + esc(ha.todo) + (ha.synced_at ? ' · checked ' + esc(ago(ha.synced_at)) : '') + '</span></div>' + state + '</div>' +
        (ha.ok === false && ha.error ? '<p class="small ha-error">' + esc(ha.error) + '</p>' : '') +
        '<p class="small muted">Everything on the supply run is on that list. Tick extras off on either side. ' +
        'Tick off a below-target item there and it\'s marked here, ready to put away with <b>Got it</b>.</p>' +
        '<div class="btn-row"><button class="btn" data-act="ha-pick">Change list</button><button class="btn" data-act="ha-stop">Stop syncing</button></div>';
    }
    return html + '<p class="small muted" style="margin:12px 0 0">For dashboard cards and phone alerts, open the app\'s <b>Documentation</b> tab in Home Assistant.</p></section>';
  }

  function queueSetting(key, value) {
    settingsQueue[key] = value;
    clearTimeout(settingsTimer);
    settingsTimer = setTimeout(function () {
      var body = settingsQueue;
      settingsQueue = {};
      run(function () {
        return api('PUT', 'api/settings', body).then(refresh).then(function () { toast('Saved'); });
      });
    }, 450);
  }

  function setTheme(t) {
    try {
      if (t === 'auto') localStorage.removeItem('da-theme'); else localStorage.setItem('da-theme', t);
    } catch (e) { /* not saved, still applied */ }
    if (t === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = t;
    render();
  }

  // ------------------------------------------------------------------
  // Printing
  // ------------------------------------------------------------------
  function printInventory() {
    var st = S.settings, r = readiness();
    var html = '<h1>Dads Army · Stores</h1><p class="p-meta">Printed ' + esc(new Date().toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })) +
      ' · ' + st.adults + ' adults, ' + st.children + ' children · Food ≈ ' + fmtDays(r.foodDays) + ' days · Water ≈ ' + fmtDays(r.waterDays) + ' days</p>';
    CATS.forEach(function (c) {
      var its = S.items.filter(function (it) { return it.category === c.id; }).sort(byName);
      if (!its.length) return;
      html += '<h2>' + esc(c.label) + '</h2><table><thead><tr><th>Item</th><th class="num">Qty</th><th>Best before</th><th>Location</th><th class="num">Target</th><th>Check</th></tr></thead><tbody>';
      its.forEach(function (it) {
        var rows = it.batches.length ? it.batches : [null];
        rows.forEach(function (b, idx) {
          html += '<tr><td>' + (idx === 0 ? esc(it.name) : '') + '</td>' +
            '<td class="num">' + (b ? esc(qu(b.qty, it.unit)) : '-') + '</td>' +
            '<td class="p-exp">' + (b && b.expiry ? esc(fmtDate(b.expiry)) + (daysUntil(b.expiry) < 0 ? ' (expired)' : '') : '') + '</td>' +
            '<td>' + (b ? esc(b.location) : '') + '</td>' +
            '<td class="num">' + (idx === 0 && it.target_qty ? esc(fq(it.target_qty)) : '') + '</td><td class="tick"></td></tr>';
        });
      });
      html += '</tbody></table>';
    });
    $('#print-root').innerHTML = html;
    window.print();
  }
  function printSupply() {
    var html = '<h1>Dads Army · Supply run</h1><p class="p-meta">' + esc(new Date().toLocaleDateString('en-GB', { dateStyle: 'full' })) + '</p>';
    var short = shortList();
    if (short.length) {
      html += '<h2>Below target</h2><table><thead><tr><th>Got</th><th>Item</th><th class="num">Get</th></tr></thead><tbody>';
      short.forEach(function (x) {
        html += '<tr><td class="tick">☐</td><td>' + esc(x.it.name) + '</td><td class="num">' + esc(qu(x.i.short, x.it.unit)) + '</td></tr>';
      });
      html += '</tbody></table>';
    }
    var extra = S.shopping.filter(function (s) { return !s.done; });
    if (extra.length) {
      html += '<h2>Also get</h2><table><tbody>';
      extra.forEach(function (s) { html += '<tr><td class="tick">☐</td><td>' + esc(s.text) + '</td></tr>'; });
      html += '</tbody></table>';
    }
    $('#print-root').innerHTML = html;
    window.print();
  }

  // ------------------------------------------------------------------
  // Bottom sheets
  // ------------------------------------------------------------------
  function openSheet(s) {
    stack.push(s);
    try { history.pushState({ daSheet: stack.length }, ''); } catch (e) { /* ignore */ }
    showSheet(true);
  }
  function closeSheet() {
    if (!stack.length) return;
    if (history.state && history.state.daSheet) history.back();
    else { stack.pop(); showSheet(true); }
  }
  window.addEventListener('popstate', function () {
    if (stack.length) { stack.pop(); showSheet(true); }
  });
  function showSheet(resetScroll) {
    var root = $('#sheet-root');
    if (!stack.length) {
      root.hidden = true;
      document.body.classList.remove('sheet-open');
      $('#sheet-body').innerHTML = '';
      return;
    }
    var appearing = root.hidden;
    root.classList.toggle('anim', appearing);
    root.hidden = false;
    document.body.classList.add('sheet-open');
    renderSheet();
    if (resetScroll) $('.sheet', root).scrollTop = 0;
    var auto = $('[data-autofocus]', root);
    if (auto && appearing) setTimeout(function () { auto.focus(); }, 280);
  }
  function renderSheet() {
    var s = stack[stack.length - 1];
    if (!s) return;
    var html = {
      item: sheetItem, edit: sheetEdit, stock: sheetStock, use: sheetUse, batch: sheetBatch, text: sheetText, halists: sheetHaLists
    }[s.type](s);
    if (html === null) {   // the item was deleted elsewhere
      closeSheet();
      return;
    }
    $('#sheet-body').innerHTML = html;
  }
  function sheetHead(title, sub, icon) {
    return '<div class="sheet-head">' + (icon ? '<span class="li-ico">' + icon + '</span>' : '') +
      '<div><h2 id="sheet-title">' + esc(title) + '</h2>' + (sub ? '<p>' + esc(sub) + '</p>' : '') + '</div>' +
      '<button class="icon-btn" type="button" data-act="close-sheet" aria-label="Close">' + ICON.close + '</button></div>';
  }
  function stat(value, label) {
    return '<div class="stat"><span class="stat-val">' + esc(value) + '</span><span class="stat-lbl">' + esc(label) + '</span></div>';
  }
  function expiryField(val) {
    return '<div class="field"><span>Best before / expiry</span>' +
      '<input type="date" name="expiry" value="' + esc(val || '') + '" aria-label="Best before date">' +
      '<div class="quick">' + [[6, '6 months'], [12, '1 year'], [24, '2 years'], [60, '5 years'], [300, '25 years']].map(function (m) {
        return '<button type="button" class="chip" data-exp="' + m[0] + '">+' + m[1] + '</button>';
      }).join('') + '<button type="button" class="chip" data-exp="">No expiry</button></div></div>';
  }
  function locationField(val) {
    return '<label class="field"><span>Where is it kept?</span><input type="text" name="location" list="dl-locations" value="' + esc(val || '') +
      '" placeholder="e.g. Garage shelf B" maxlength="80" autocomplete="off"></label>';
  }

  function sheetItem(s) {
    var it = byId(s.id);
    if (!it) return null;
    var i = info(it), c = cat(it.category), r = readiness();
    var unitWord = isMoney(it.unit) ? '' : plural(it.unit, i.total);
    var stats = [stat(isMoney(it.unit) ? it.unit + fq(i.total) : fq(i.total), (unitWord ? unitWord + ' ' : '') + 'in stock')];
    if (it.target_qty > 0) stats.push(stat(fq(it.target_qty), i.low ? 'target · short ' + fq(i.short) : 'target · met ✓'));
    if (it.category === 'food' && it.kcal_per_unit > 0 && r.kcalDay > 0) stats.push(stat(fmtDays(i.total * it.kcal_per_unit / r.kcalDay), 'days of food'));
    if (it.category === 'water' && it.litres_per_unit > 0) {
      stats.push(stat(fq(Math.round(i.total * it.litres_per_unit * 10) / 10) + ' L', r.waterDay > 0 ? fmtDays(i.total * it.litres_per_unit / r.waterDay) + ' days of water' : 'of water'));
    }
    var batches = it.batches.map(function (b) {
      var es = expState(b.expiry);
      var exp = b.expiry
        ? '<span class="badge ' + (es === 'ok' ? 'ok' : es) + '">' + esc(expiryWords(b.expiry)) + '</span>' + esc(fmtDate(b.expiry))
        : '<span class="badge plain">No expiry</span>';
      return '<div class="batch"><button class="batch-main" data-act="batch" data-id="' + b.id + '" data-item="' + it.id + '">' +
        '<span class="batch-exp">' + exp + '</span><span class="batch-meta">' + (b.location ? esc(b.location) : 'No location set') +
        ' · added ' + esc(fmtDate(b.added_at)) + '</span></button>' +
        '<div class="mini-step"><button class="qbtn" data-act="bstep" data-id="' + b.id + '" data-d="-1" aria-label="One less">' + ICON.minus + '</button>' +
        '<output>' + esc(fq(b.qty)) + '</output>' +
        '<button class="qbtn" data-act="bstep" data-id="' + b.id + '" data-d="1" aria-label="One more">' + ICON.plus + '</button></div></div>';
    }).join('');
    return sheetHead(it.name, c.label + (it.unit ? ' · per ' + it.unit : ''), c.icon) +
      '<div class="stats">' + stats.join('') + '</div>' +
      '<div class="btn-row"><button class="btn" data-act="use-sheet" data-id="' + it.id + '"' + (i.out ? ' disabled' : '') + '>' + ICON.minus + ' Use</button>' +
      '<button class="btn primary" data-act="stock" data-id="' + it.id + '">' + ICON.plus + ' Add stock</button></div>' +
      '<h3>Batches' + (it.batches.length > 1 ? ' <small>oldest is used first</small>' : '') + '</h3>' +
      (batches || '<p class="small muted">None in stock.</p>') +
      (it.notes ? '<h3>Notes</h3><div class="notes">' + esc(it.notes) + '</div>' : '') +
      '<div class="btn-row" style="margin-top:20px"><button class="btn" data-act="edit" data-id="' + it.id + '">' + ICON.edit + ' Edit details</button>' +
      '<button class="btn danger" data-act="del-item" data-id="' + it.id + '">' + ICON.trash + ' Delete</button></div>';
  }

  function sheetEdit(s) {
    var it = s.id ? byId(s.id) : null;
    if (s.id && !it) return null;
    var v = it || { name: '', category: s.cat || 'food', unit: '', kcal_per_unit: 0, litres_per_unit: 0, target_qty: 0, notes: '' };
    var cats = CATS.map(function (c) {
      return '<label class="cat-opt"><input type="radio" name="category" value="' + c.id + '"' + (c.id === v.category ? ' checked' : '') + '>' +
        '<span><i>' + c.icon + '</i>' + esc(c.short || c.label) + '</span></label>';
    }).join('');
    return sheetHead(it ? 'Edit item' : 'New item', it ? it.name : 'Add something to the stores') +
      '<form id="itemForm" data-cat="' + esc(v.category) + '" data-id="' + (it ? it.id : '') + '" novalidate>' +
      '<label class="field"><span>Name</span><input type="text" name="name" value="' + esc(v.name) + '" maxlength="120" placeholder="e.g. Baked beans (415g)" autocomplete="off"' + (it ? '' : ' data-autofocus') + '></label>' +
      '<fieldset class="field"><legend>Category</legend><div class="cat-grid">' + cats + '</div></fieldset>' +
      '<div class="grid2"><label class="field"><span>Unit</span><input type="text" name="unit" value="' + esc(v.unit) + '" list="dl-units" placeholder="tin, pack, kg" maxlength="30" autocomplete="off"></label>' +
      '<label class="field"><span>Target stock</span><input type="number" name="target_qty" value="' + (v.target_qty || '') + '" inputmode="decimal" min="0" step="any" placeholder="0"></label></div>' +
      '<div class="only-food"><label class="field"><span>Calories per unit</span><input type="number" name="kcal_per_unit" value="' + (v.kcal_per_unit || '') + '" inputmode="decimal" min="0" step="any" placeholder="e.g. 340">' +
      '<div class="hint">Used to work out how many days your food will last.</div></label>' +
      '<details class="calc"><summary>Work it out from the label</summary><div class="grid2">' +
      '<label class="field"><span>kcal per 100g</span><input type="number" data-calc="per100" inputmode="decimal" min="0" step="any"></label>' +
      '<label class="field"><span>Weight (g)</span><input type="number" data-calc="grams" inputmode="decimal" min="0" step="any"></label></div></details></div>' +
      '<label class="field only-water"><span>Litres per unit</span><input type="number" name="litres_per_unit" value="' + (v.litres_per_unit || '') + '" inputmode="decimal" min="0" step="any" placeholder="e.g. 5">' +
      '<div class="hint">Drinkable water only. Leave empty for filters, tablets and containers.</div></label>' +
      (it ? '' : '<h3>Opening stock</h3><div class="field"><span>How many?</span>' + stepperHtml('qty', 1, 'Quantity') + '</div>' +
        expiryField('') + locationField(lastLocation(lastTouched()))) +
      '<label class="field"><span>Notes</span><textarea name="notes" rows="2" maxlength="2000" placeholder="Optional">' + esc(v.notes) + '</textarea></label>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + (it ? 'Save changes' : 'Add to stores') + '</button></div></form>';
  }
  function lastTouched() {
    var best = null;
    S.items.forEach(function (it) { if (it.batches.length && (!best || it.updated_at > best.updated_at)) best = it; });
    return best;
  }

  function sheetStock(s) {
    var it = byId(s.id);
    if (!it) return null;
    return sheetHead('Add stock', it.name, cat(it.category).icon) +
      '<form id="stockForm" data-id="' + it.id + '" novalidate>' +
      '<div class="field"><span>' + esc(howMany(it.unit)) + '</span>' + stepperHtml('qty', s.qty || 1, 'Quantity') + '</div>' +
      expiryField('') + locationField(lastLocation(it) || lastLocation(lastTouched())) +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + ICON.plus + ' Add to stores</button></div></form>';
  }

  function sheetUse(s) {
    var it = byId(s.id);
    if (!it) return null;
    var i = info(it);
    return sheetHead('Use stock', it.name, cat(it.category).icon) +
      '<form id="useForm" data-id="' + it.id + '" novalidate>' +
      '<div class="field"><span>' + esc(howMany(it.unit)) + '</span>' + stepperHtml('qty', 1, 'Quantity') +
      '<div class="quick"><button type="button" class="chip" data-setqty="' + i.total + '">All of it (' + esc(fq(i.total)) + ')</button></div>' +
      '<div class="hint">You have ' + esc(qu(i.total, it.unit)) + '. The oldest expiry date is used first.</div></div>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + ICON.minus + ' Use it</button></div></form>';
  }

  function sheetBatch(s) {
    var it = byId(s.item);
    var b = it && it.batches.filter(function (x) { return x.id === s.id; })[0];
    if (!b) return null;
    return sheetHead('Edit batch', it.name, cat(it.category).icon) +
      '<form id="batchForm" data-id="' + b.id + '" novalidate>' +
      '<div class="field"><span>Quantity</span>' + stepperHtml('qty', fq(b.qty).replace(/,/g, ''), 'Quantity') + '</div>' +
      expiryField(b.expiry) + locationField(b.location) +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">Save batch</button>' +
      '<button class="btn danger block" type="button" data-act="del-batch" data-id="' + b.id + '">' + ICON.trash + ' Remove this batch</button></div></form>';
  }

  function sheetText(s) {
    return sheetHead(s.title, 'Select all and copy') +
      '<textarea readonly rows="12" style="font-family:ui-monospace,monospace;font-size:14px">' + esc(s.text) + '</textarea>';
  }

  function sheetHaLists(s) {
    var d = s.data, body;
    var current = S.server.ha ? S.server.ha.todo : '';
    if (!d) body = '<p class="small muted">Asking Home Assistant…</p>';
    else if (d.error) body = '<p class="small ha-error">' + esc(d.error) + '</p>';
    else if (!d.lists.length) body = '<p class="small muted">Home Assistant hasn\'t got any to-do lists yet. Close this and use <b>Make a “Supply run” list</b> instead.</p>';
    else {
      body = '<p class="small muted">Best to pick a list just for Dads Army. Whatever is on it now is left alone. Anything added to it later goes on the supply run.</p><div class="list">' +
        d.lists.map(function (l) {
          var on = l.entity_id === current;
          return '<div class="li"><button class="li-main" data-act="ha-use" data-entity="' + esc(l.entity_id) + '" data-name="' + esc(l.name) + '">' +
            '<span class="li-title">' + esc(l.name) + '</span><span class="small muted">' + esc(l.entity_id) + '</span></button>' +
            (on ? '<span class="badge ok">' + ICON.check + ' In use</span>' : '') + '</div>';
        }).join('') + '</div>';
    }
    return sheetHead('Choose a to-do list', 'From Home Assistant', '📋') + body;
  }

  // ------------------------------------------------------------------
  // Toast + undo
  // ------------------------------------------------------------------
  function toast(msg, opts) {
    opts = opts || {};
    var t = $('#toast');
    t.className = 'toast' + (opts.error ? ' error' : '');
    t.innerHTML = '<span>' + esc(msg) + '</span>' + (opts.undo ? '<button type="button" data-act="undo">Undo</button>' : '');
    t._undo = opts.undo || null;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; t._undo = null; },
      opts.undo ? 6500 : opts.error ? Math.max(5000, msg.length * 60) : 2600);
  }

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------
  function useOne(id, btn) {
    var it = byId(id);
    if (!it) return;
    return run(function () {
      return api('POST', 'api/items/' + id + '/use', { qty: 1 }).then(function (res) {
        return refresh().then(function () {
          var now = byId(id);
          toast(it.name + ': used ' + qu(res.used, it.unit) + ', ' + fq(now ? total(now) : 0) + ' left', { undo: res.undo });
        });
      });
    }, btn);
  }

  function goStores(patch) {
    F.q = ''; F.cat = 'all'; F.show = 'all';
    Object.keys(patch).forEach(function (k) { F[k] = patch[k]; });
    var el = $('#view');
    el.dataset.view = '';   // force a full redraw of the toolbar
    go('stores');
  }

  function handleAct(a) {
    var act = a.dataset.act;
    var id = a.dataset.id ? +a.dataset.id : null;
    switch (act) {
      case 'retry':
        return run(refresh, a);
      case 'new':
        return openSheet({ type: 'edit', id: null, cat: F.cat !== 'all' && view === 'stores' ? F.cat : 'food' });
      case 'open':
        return openSheet({ type: 'item', id: id });
      case 'edit':
        return openSheet({ type: 'edit', id: id });
      case 'stock':
        return openSheet({ type: 'stock', id: id, qty: a.dataset.qty ? +a.dataset.qty : 1 });
      case 'use-sheet':
        return openSheet({ type: 'use', id: id });
      case 'batch':
        return openSheet({ type: 'batch', id: id, item: +a.dataset.item });
      case 'use':
        return useOne(id, a);
      case 'close-sheet':
        return closeSheet();
      case 'bstep':
        return run(function () {
          return api('PUT', 'api/batches/' + id, { delta: +a.dataset.d }).then(function (res) {
            return refresh().then(function () { if (res.removed) toast('Batch used up', { undo: res.undo }); });
          });
        }, a);
      case 'del-item': {
        var it = byId(id);
        return run(function () {
          return api('DELETE', 'api/items/' + id).then(function (res) {
            closeSheet();
            return refresh().then(function () { toast('Deleted ' + (it ? it.name : 'item'), { undo: res.undo }); });
          });
        }, a);
      }
      case 'del-batch':
        return run(function () {
          return api('DELETE', 'api/batches/' + id).then(function (res) {
            closeSheet();
            return refresh().then(function () { toast('Batch removed', { undo: res.undo }); });
          });
        }, a);
      case 'undo': {
        var t = $('#toast'), snap = t._undo;
        t.hidden = true;
        if (!snap) return;
        return run(function () {
          return api('POST', 'api/restore-item', snap).then(refresh).then(function () { toast('Undone'); });
        });
      }
      case 'go':
        return goStores(a.dataset.sort ? { show: a.dataset.show, sort: a.dataset.sort } : { show: a.dataset.show });
      case 'cat-go':
        return goStores({ cat: a.dataset.cat });
      case 'cat':
        F.cat = a.dataset.cat;
        return renderStores($('#view'));
      case 'clear-filters':
        F.q = ''; F.cat = 'all'; F.show = 'all';
        return renderStores($('#view'));
      case 'seed':
        if (!confirm('Load the starter list?\n\nAbout 95 suggested essentials are added at zero stock, with targets sized for your household. You can delete anything you don\'t need.')) return;
        return run(function () {
          return api('POST', 'api/seed', {}).then(function (res) {
            return refresh().then(function () {
              toast(res.added ? 'Added ' + res.added + ' items. Check the supply run.' : 'You already have everything on the starter list');
              if (res.added) goStores({});
            });
          });
        }, a);
      case 'set':
        queueSetting(a.dataset.key, +a.dataset.val);
        $$('[data-key="' + a.dataset.key + '"]').forEach(function (b) { b.setAttribute('aria-pressed', String(b === a)); });
        return;
      case 'theme':
        return setTheme(a.dataset.val);
      case 'print':
        return printInventory();
      case 'print-list':
        return printSupply();
      case 'copy-list': {
        var text = supplyText();
        return copyText(text).then(function (ok) {
          if (ok) toast('Supply list copied');
          else openSheet({ type: 'text', title: 'Supply run', text: text });
        });
      }
      case 'restore':
        $('#restoreFile').value = '';
        return $('#restoreFile').click();
      case 'shop-toggle': {
        var s = S.shopping.filter(function (x) { return x.id === id; })[0];
        if (!s) return;
        s.done = s.done ? 0 : 1;   // instant feedback
        a.setAttribute('aria-checked', s.done ? 'true' : 'false');
        return run(function () { return api('PUT', 'api/shopping/' + id, { done: !!s.done }).then(refresh); });
      }
      case 'shop-del':
        return run(function () { return api('DELETE', 'api/shopping/' + id).then(refresh); }, a);
      case 'shop-clear':
        return run(function () { return api('POST', 'api/shopping/clear-done', {}).then(refresh); }, a);
      case 'ha-make':
        return run(function () {
          toast('Making the list in Home Assistant…');
          return api('POST', 'api/homeassistant/todo-list', {}).then(refresh).then(function () {
            toast('The supply run is now on your Home Assistant list “' + S.server.ha.todo_name + '”');
          });
        }, a);
      case 'ha-pick': {
        var sh = { type: 'halists', data: null };
        openSheet(sh);
        return api('GET', 'api/homeassistant').then(function (d) { sh.data = d; }, function (e) {
          sh.data = { error: e.message, lists: [] };
        }).then(function () { if (stack[stack.length - 1] === sh) renderSheet(); });
      }
      case 'ha-use': {
        var name = a.dataset.name;
        if (S.server.ha && S.server.ha.todo === a.dataset.entity) return closeSheet();
        return run(function () {
          return api('PUT', 'api/homeassistant', { todo_list: a.dataset.entity }).then(function () {
            closeSheet();
            return refresh().then(function () { toast('The supply run is now on “' + name + '”'); });
          });
        }, a);
      }
      case 'ha-stop':
        if (!confirm('Stop putting the supply run on “' + S.server.ha.todo_name + '”?\n\nDads Army takes its below-target items off that list. Your extras stay on it.')) return;
        return run(function () {
          return api('PUT', 'api/homeassistant', { todo_list: '' }).then(refresh).then(function () { toast('Stopped syncing'); });
        }, a);
    }
  }

  function step(btn) {
    var input = btn.parentNode.querySelector('input');
    if (!input) return;
    var d = parseFloat(btn.dataset.step);
    var v = Math.max(0, Math.round((num(input.value) + d) * 1000) / 1000);
    input.value = v;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function submitForm(f) {
    var fd = new FormData(f), d = {};
    fd.forEach(function (v, k) { d[k] = typeof v === 'string' ? v.trim() : v; });
    var btn = $('[type="submit"]', f);
    if (f.id === 'itemForm') {
      if (!d.name) { toast('Give the item a name', { error: true }); f.elements.name.focus(); return; }
      var body = {
        name: d.name, category: d.category || 'other', unit: d.unit || '', notes: d.notes || '',
        target_qty: num(d.target_qty), kcal_per_unit: num(d.kcal_per_unit), litres_per_unit: num(d.litres_per_unit)
      };
      var id = f.dataset.id;
      if (!id) { body.qty = num(d.qty); body.expiry = d.expiry || null; body.location = d.location || ''; }
      return run(function () {
        return api(id ? 'PUT' : 'POST', id ? 'api/items/' + id : 'api/items', body).then(function () {
          closeSheet();
          return refresh().then(function () { toast(id ? 'Saved' : body.name + ' added to the stores'); });
        });
      }, btn);
    }
    if (f.id === 'stockForm') {
      var qty = num(d.qty);
      if (qty <= 0) { toast('How many are you adding?', { error: true }); return; }
      return run(function () {
        return api('POST', 'api/items/' + f.dataset.id + '/stock', { qty: qty, expiry: d.expiry || null, location: d.location || '' }).then(function () {
          var it = byId(+f.dataset.id);
          closeSheet();
          return refresh().then(function () { toast('Added ' + qu(qty, it ? it.unit : '') + (it ? ' · ' + it.name : '')); });
        });
      }, btn);
    }
    if (f.id === 'useForm') {
      var uq = num(d.qty);
      if (uq <= 0) { toast('How many are you using?', { error: true }); return; }
      return run(function () {
        return api('POST', 'api/items/' + f.dataset.id + '/use', { qty: uq }).then(function (res) {
          var it = byId(+f.dataset.id);
          closeSheet();
          return refresh().then(function () { toast('Used ' + qu(res.used, it ? it.unit : ''), { undo: res.undo }); });
        });
      }, btn);
    }
    if (f.id === 'batchForm') {
      return run(function () {
        return api('PUT', 'api/batches/' + f.dataset.id, { qty: num(d.qty), expiry: d.expiry || null, location: d.location || '' }).then(function (res) {
          closeSheet();
          return refresh().then(function () { toast(res.removed ? 'Batch removed' : 'Batch saved', res.removed ? { undo: res.undo } : {}); });
        });
      }, btn);
    }
    if (f.id === 'shopForm') {
      if (!d.text) return;
      return run(function () {
        return api('POST', 'api/shopping', { text: d.text }).then(refresh).then(function () {
          var input = $('#shopForm input');
          if (input) input.focus();
        });
      }, btn);
    }
  }

  // ------------------------------------------------------------------
  // Navigation
  // ------------------------------------------------------------------
  function go(v) {
    if (VIEWS.indexOf(v) < 0) v = 'sitrep';
    if (location.hash !== '#' + v) location.hash = v;
    else setView(v);
  }
  function setView(v) {
    if (VIEWS.indexOf(v) < 0) v = 'sitrep';
    var changed = view !== v;
    view = v;
    document.body.dataset.view = v;
    render();
    if (changed) window.scrollTo(0, 0);
  }

  // ------------------------------------------------------------------
  // Events
  // ------------------------------------------------------------------
  document.addEventListener('click', function (e) {
    var t = e.target;
    var stepBtn = t.closest('[data-step]');
    if (stepBtn) { step(stepBtn); return; }
    var expBtn = t.closest('[data-exp]');
    if (expBtn) {
      var input = expBtn.closest('.field').querySelector('input[type="date"]');
      input.value = expBtn.dataset.exp ? addMonths(+expBtn.dataset.exp) : '';
      return;
    }
    var setQty = t.closest('[data-setqty]');
    if (setQty) { setQty.closest('.field').querySelector('input').value = setQty.dataset.setqty; return; }
    var tab = t.closest('[data-tab]');
    if (tab) { if (stack.length) return; go(tab.dataset.tab); return; }
    var a = t.closest('[data-act]');
    if (a && !a.disabled) handleAct(a);
  });

  document.addEventListener('submit', function (e) {
    e.preventDefault();
    submitForm(e.target);
  });

  document.addEventListener('input', function (e) {
    var t = e.target;
    if (t.id === 'q') { F.q = t.value; renderStoreList(); return; }
    if (t.dataset.calc) {
      var f = t.form;
      var per = num($('[data-calc="per100"]', f).value), g = num($('[data-calc="grams"]', f).value);
      if (per > 0 && g > 0) f.elements.kcal_per_unit.value = Math.round(per * g / 100);
    }
  });

  document.addEventListener('change', function (e) {
    var t = e.target;
    if (t.id === 'fShow') { F.show = t.value; renderStoreList(); return; }
    if (t.id === 'fSort') {
      F.sort = t.value;
      try { localStorage.setItem('da-sort', F.sort); } catch (err) { /* ignore */ }
      renderStoreList();
      return;
    }
    if (t.dataset.setting) { queueSetting(t.dataset.setting, num(t.value)); return; }
    if (t.name === 'category' && t.form) { t.form.dataset.cat = t.value; return; }
    if (t.id === 'restoreFile' && t.files && t.files[0]) {
      var file = t.files[0];
      var reader = new FileReader();
      reader.onload = function () {
        var data;
        try { data = JSON.parse(reader.result); } catch (err) { toast('That file isn\'t a Dads Army backup', { error: true }); return; }
        var n = data && data.items ? data.items.length : 0;
        if (!confirm('Restore ' + n + ' items from "' + file.name + '"?\n\nThis REPLACES everything currently in the stores. The Pi keeps a copy of the current data first, just in case.')) return;
        run(function () {
          return api('POST', 'api/restore', data).then(refresh).then(function () { toast('Restored ' + n + ' items'); });
        });
      };
      reader.readAsText(file);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && stack.length) closeSheet();
  });

  window.addEventListener('hashchange', function () { setView(location.hash.slice(1)); });

  function poll() {
    if (document.hidden || stack.length) return;
    var a = document.activeElement;
    if (a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return;
    refresh().catch(function () { if (!S) render(); });
  }
  document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
  setInterval(poll, 30000);

  // ------------------------------------------------------------------
  // Start
  // ------------------------------------------------------------------
  try { history.replaceState(null, ''); } catch (e) { /* ignore */ }
  try { F.sort = localStorage.getItem('da-sort') || 'category'; } catch (e) { /* ignore */ }
  setView(location.hash.slice(1) || 'sitrep');
  refresh().catch(function () { render(); });

  // Small hook for testing and tinkering from the browser console.
  window.DA = { open: openSheet, state: function () { return S; }, refresh: refresh };
})();
