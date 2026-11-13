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
  var VIEWS = ['sitrep', 'stores', 'supply', 'plan', 'hq'];

  // Household emergency plan: [field, heading, prompt, max length]. Same fields as the server's PLAN_TEXT.
  var PLAN_PARTS = [
    ['meet_near', 'Meeting place near home', 'If you can\'t get home or have to leave in a hurry, e.g. the church car park on Mill Lane', 300],
    ['meet_far', 'Meeting place further away', 'If the whole area has to leave, e.g. Gran\'s house in Harrogate', 300],
    ['water_off', 'Water stopcock', 'Where it is and how to turn it off, e.g. under the kitchen sink, turn clockwise', 600],
    ['gas_off', 'Gas', 'Usually a lever next to the gas meter: turn it so it points across the pipe', 600],
    ['power_off', 'Electricity', 'Where the fuse box is, e.g. cupboard under the stairs, main switch on the left', 600],
    ['medical', 'Medical needs', 'Allergies, medicines and doses, equipment that needs power. Is anyone on the Priority Services Register?', 2000],
    ['pets', 'Pets', 'Food, medicines, carriers, and where they can go if you have to leave', 1000],
    ['documents', 'Important documents', 'Where the passports, insurance papers and deeds are kept', 600],
    ['radio', 'Local radio', 'The station for local emergency news, and its frequency', 200],
    ['notes', 'Anything else', 'Who collects the children, a neighbour who needs checking on…', 3000]
  ];
  // Offered in the plan's contacts. All free to call in the UK.
  var UK_NUMBERS = [
    ['Emergency services', 'Police, fire, ambulance, coastguard', '999'],
    ['NHS 111', 'Urgent medical help that isn\'t a 999 emergency', '111'],
    ['Power cut', 'Any electricity network in the UK', '105'],
    ['Gas emergency', 'If you smell gas or suspect carbon monoxide (Great Britain)', '0800 111 999'],
    ['Floodline', 'Flood warnings for England, Scotland and Wales', '0345 988 1188'],
    ['Police (not an emergency)', '', '101']
  ];

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
    list: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/></svg>',
    phone: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 3.5h3l1.5 4.5-2 1.3a11 11 0 0 0 5.7 5.7l1.3-2 4.5 1.5v3a2 2 0 0 1-2 2A16.5 16.5 0 0 1 4.5 5.5a2 2 0 0 1 2-2z"/></svg>'
  };

  // ------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------
  var S = null;                 // everything from /api/state
  var view = 'sitrep';
  var offline = false;
  var F = { q: '', cat: 'all', show: 'all', sort: 'category' };   // Stores filters
  var SEL = null;               // Stores: ids picked for deleting ({id: 1}), or null when not picking
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
  function addDays(s, n) { var d = parseYmd(s); d.setDate(d.getDate() + n); return ymd(d); }
  var nf2 = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  function money(v) { return '£' + (v >= 100 ? nf0.format(Math.round(v)) : nf2.format(v)); }
  function lastsWords(d) { return d <= 0 ? 'run out' : d < 1 ? 'less than a day' : span(Math.floor(d)); }
  // How often a check comes round. Same wording as the server's every_words.
  function everyWords(n) {
    if (n === 1) return 'every day';
    if (n % 7 === 0 && n < 28) return n === 7 ? 'every week' : 'every ' + (n / 7) + ' weeks';
    var months = n / 30.44, m = Math.round(months);
    if (m >= 1 && Math.abs(months - m) <= 0.08 * m + 0.05) {
      if (m % 12 === 0) return m === 12 ? 'every year' : 'every ' + (m / 12) + ' years';
      return m === 1 ? 'every month' : 'every ' + m + ' months';
    }
    return 'every ' + n + ' days';
  }
  function monthsWords(m) { return m === 1 ? '1 month' : m < 24 || m % 12 ? m + ' months' : (m / 12) + ' years'; }
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
  // Stock that's still in date: what daily supplies count, as for food and water.
  function inDate(it) {
    return it.batches.reduce(function (a, b) { return a + (b.expiry && daysUntil(b.expiry) < 0 ? 0 : b.qty); }, 0);
  }
  function daysLeft(it) { return it.per_day > 0 ? inDate(it) / it.per_day : null; }
  // How long the last dated batch was kept for, in months: offered as "Like last time" when adding stock.
  function usualLife(it) {
    var best = null;
    it.batches.forEach(function (b) { if (b.expiry && b.added_at && (!best || b.id > best.id)) best = b; });
    if (!best) return 0;
    var m = Math.round((parseYmd(best.expiry) - parseYmd(best.added_at)) / 864e5 / 30.44);
    return m >= 1 ? m : 0;
  }
  function stockValue() {
    return S.items.reduce(function (a, it) { return a + (it.price > 0 ? total(it) * it.price : 0); }, 0);
  }

  // Routine checks
  function checkInfo(c) {
    if (!c.last_done) return { due: null, days: null, state: 'never', text: 'Not done yet' };
    var due = addDays(c.last_done, c.every_days), d = daysUntil(due);
    if (d < 0) return { due: due, days: d, state: 'bad', text: 'Overdue by ' + span(-d) };
    if (d === 0) return { due: due, days: 0, state: 'bad', text: 'Due today' };
    return { due: due, days: d, state: d <= 7 ? 'warn' : 'ok', text: 'Due in ' + span(d) };
  }
  function isDue(i) { return i.days === null || i.days <= 0; }
  function sortedChecks() {
    return (S.checks || []).map(function (c) { return { c: c, i: checkInfo(c) }; }).sort(function (a, b) {
      var da = a.i.days === null ? 0 : a.i.days, db = b.i.days === null ? 0 : b.i.days;
      return da - db || byName(a.c, b.c);
    });
  }
  function checksDue() { return sortedChecks().filter(function (x) { return isDue(x.i); }).length; }

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
    // Things with a daily use, shortest-lasting first.
    r.supplies = S.items.filter(function (it) { return it.per_day > 0; }).map(function (it) {
      return { it: it, days: daysLeft(it) };
    }).sort(function (a, b) { return a.days - b.days || byName(a.it, b.it); });
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
      maybeOfferDashboard();
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
      else if (view === 'plan') renderPlan(el);
      else if (view === 'hq') renderHQ(el);
      else renderSitrep(el);
    }
    if (stack.length && /^(item|area|resall)$/.test(stack[stack.length - 1].type)) renderSheet();
  }

  function updateBadge() {
    var n = S.items.filter(function (it) { return info(it).low; }).length +
      S.shopping.filter(function (s) { return !s.done; }).length;
    var b = $('#supplyBadge');
    b.hidden = n === 0;
    b.textContent = n > 99 ? '99+' : String(n);
    var due = checksDue(), pb = $('#planBadge');
    pb.hidden = due === 0;
    pb.textContent = String(due);
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
    if (!S.items.length) { el.innerHTML = levelCard() + warnCard(false) + emptyCard() + resilienceCard(); return; }
    var st = S.settings, r = readiness(), target = st.target_days;
    var html = levelCard() + dashNote() + warnCard(false) + resilienceCard();

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
      var sup = r.supplies[0], supNote = '';
      if (sup) {
        supNote = '<button class="link" data-act="open" data-id="' + sup.it.id + '">' + esc(sup.it.name) + '</button> ' +
          (sup.days > 0 ? 'runs out first' : 'has run out') +
          (r.supplies.length > 1 ? ' · ' + r.supplies.length + ' things with a daily use' : '');
      }
      html += '<section class="card hero">' +
        '<div class="eyebrow">You could hold out for</div>' +
        '<div class="hero-num">' + fmtDays(r.hold) + '<small>' + (fmtDays(r.hold) === '1' ? 'day' : 'days') + '</small></div>' +
        '<div class="hero-sub">' + pill(hs, hs === 'good' ? target + '-day target met' : 'Target ' + target + ' days') +
        (limit ? '<span>' + limit + '</span>' : '') + '</div>' +
        '<div class="meters">' +
        meter('🥫 Food', fmtDays(r.foodDays) + ' of ' + target + ' days', r.foodDays / target, foodNote) +
        meter('💧 Water', fmtDays(r.waterDays) + ' of ' + target + ' days', r.waterDays / target, waterNote) +
        (sup ? meter('⏳ Daily supplies', fmtDays(sup.days) + ' of ' + target + ' days', sup.days / target, supNote) : '') +
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

    // Routine checks that are due, or due within a week
    var due = sortedChecks().filter(function (x) { return x.i.days === null || x.i.days <= 7; });
    if (due.length) {
      html += '<section class="card flush"><div class="card-head"><h2>Checks due</h2><button class="link" data-tab="plan">All checks</button></div><div class="list">' +
        due.slice(0, 4).map(checkRow).join('') + '</div>' +
        (due.length > 4 ? '<button class="li more" data-tab="plan">' + (due.length - 4) + ' more ' + ICON.chev + '</button>' : '') + '</section>';
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
    html += '</div>';
    var priced = S.items.filter(function (it) { return it.price > 0; }).length;
    if (priced) {
      html += '<div class="li worth"><span class="li-main"><span class="li-title">Worth about ' + esc(money(stockValue())) + '</span>' +
        '<span class="li-sub">From the prices on ' + priced + ' of ' + S.items.length + ' items</span></span></div>';
    }
    html += '</section>';

    // Recent activity
    if (S.log.length) {
      html += '<section class="card"><div class="card-head"><h2>Latest orders</h2><button class="link" data-tab="hq">Full log</button></div>' +
        logHtml(S.log.slice(0, 4)) + '</section>';
    }
    html += '<p class="tagline">Don\'t panic · stay supplied</p>';
    el.innerHTML = html;
  }

  var LOG_VERB = { added: 'Added', stocked: 'Stocked', used: 'Used', adjusted: 'Adjusted', edited: 'Edited', removed: 'Deleted',
    undo: 'Undone', starter: 'Starter list', restored: 'Restored', settings: 'Settings', supply: 'Supply run', checked: 'Checked',
    plan: 'Emergency plan', resilience: 'Resilience' };
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
    if (!S.items.length) { endSelect(); el.dataset.view = ''; el.innerHTML = emptyCard(); return; }
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
    var left = daysLeft(it);
    var lasts = left > 0 ? '<span>· lasts ' + esc(lastsWords(left)) + '</span>' : '';
    var body = (showIcon ? '<span class="row-ico">' + cat(it.category).icon + '</span>' : '') +
      '<span class="row-text"><span class="row-name">' + esc(it.name) + '</span>' +
      '<span class="row-sub"><span>' + amount + '</span>' + (where ? '<span>· ' + esc(where) + '</span>' : '') + lasts + badges + '</span></span>';
    if (SEL) {   // picking items to delete: the whole row is a tick box
      var on = !!SEL[it.id];
      return '<div class="row' + (on ? ' picked' : '') + (i.out ? ' is-out' : '') + '">' +
        '<button class="row-main" role="checkbox" aria-checked="' + on + '" data-act="sel-toggle" data-id="' + it.id + '">' +
        '<span class="box">' + ICON.check + '</span>' + body + '</button></div>';
    }
    return '<div class="row' + (i.out ? ' is-out' : '') + '">' +
      '<button class="row-main" data-act="open" data-id="' + it.id + '">' + body + '</button>' +
      '<div class="row-ctl">' +
      '<button class="qbtn" data-act="use" data-id="' + it.id + '" aria-label="Use one ' + esc(it.name) + '"' + (i.out ? ' disabled' : '') + '>' + ICON.minus + '</button>' +
      '<button class="qbtn add" data-act="stock" data-id="' + it.id + '" aria-label="Add ' + esc(it.name) + '">' + ICON.plus + '</button>' +
      '</div></div>';
  }

  function renderStoreList() {
    var box = $('#storeList');
    if (!box) return;
    var list = filtered();
    if (SEL) Object.keys(SEL).forEach(function (k) { if (!byId(+k)) delete SEL[k]; });   // deleted on another phone
    var bar = SEL ? '<div class="selbar" role="region" aria-label="Delete items"><span class="selbar-n" id="selCount" aria-live="polite"></span>' +
      '<button class="btn small" data-act="sel-cancel">Cancel</button>' +
      '<button class="btn small del" id="selDelete" data-act="sel-delete"></button></div>' : '';
    if (!list.length) {
      box.innerHTML = '<div class="card empty"><div class="crate">🔍</div><h2>Nothing here</h2><p>No items match that search or filter.</p><button class="btn" data-act="clear-filters">Clear filters</button></div>' + bar;
      syncSel();
      return;
    }
    var html = '<div class="list-bar"><span class="result-count">' +
      (SEL ? 'Tap the items to delete' : list.length + ' item' + (list.length === 1 ? '' : 's')) + '</span>' +
      (SEL ? '<button class="link" id="selAll" data-act="sel-all"></button>'
        : '<button class="link" data-act="sel-start">' + ICON.trash + ' Select to delete</button>') +
      '</div><div class="card flush">';
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
    box.innerHTML = html + '</div>' + bar;
    syncSel();
  }

  // Picking several items to delete at once.
  function startSelect() {
    SEL = {};
    document.body.classList.add('selecting');
    try { history.pushState({ daSel: 1 }, ''); } catch (e) { /* ignore */ }   // Back leaves picking
  }
  function endSelect() {
    if (!SEL) return;
    SEL = null;
    document.body.classList.remove('selecting');
    if (history.state && history.state.daSel) history.back();
  }
  function syncSel() {
    if (!SEL) return;
    $$('[data-act="sel-toggle"]').forEach(function (b) {
      var on = !!SEL[b.dataset.id];
      b.setAttribute('aria-checked', String(on));
      b.parentNode.classList.toggle('picked', on);
    });
    var shown = filtered();
    var all = shown.length && shown.every(function (x) { return SEL[x.it.id]; });
    var sa = $('#selAll');
    if (sa) sa.textContent = (all ? 'Unselect all ' : 'Select all ') + shown.length;
    var n = Object.keys(SEL).length;
    $('#selCount').innerHTML = n ? '<b>' + n + '</b> picked' : 'None picked';
    var del = $('#selDelete');
    del.disabled = !n;
    del.innerHTML = ICON.trash + ' Delete' + (n ? ' ' + n : '');
  }
  function nameList(names, limit) {
    var more = names.length - limit;
    if (more > 0) return names.slice(0, limit).join(', ') + ' and ' + more + ' more';
    return names.length < 2 ? names.join('') : names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1];
  }
  function deletePicked(btn) {
    var picked = S.items.filter(function (it) { return SEL && SEL[it.id]; }).sort(byName);
    if (!picked.length) return;
    var stocked = picked.filter(function (it) { return total(it) > 0; });
    var msg = picked.length === 1 ? 'Delete ' + picked[0].name + ' from the stores?'
      : 'Delete these ' + picked.length + ' items from the stores?\n\n' + nameList(picked.map(function (it) { return it.name; }), 12) + '.';
    if (stocked.length) {
      msg += '\n\n' + (picked.length === 1 ? 'Its stock is deleted too: ' : 'Their stock is deleted too: ') +
        nameList(stocked.map(function (it) { return it.name + ' (' + qu(total(it), it.unit) + ')'; }), 6) + '.';
    }
    if (!confirm(msg + '\n\nYou can undo this straight afterwards.')) return;
    return run(function () {
      return api('POST', 'api/items/delete', { ids: picked.map(function (it) { return it.id; }) }).then(function (res) {
        endSelect();
        return refresh().then(function () {
          toast(res.deleted === 1 ? 'Deleted ' + res.name : 'Deleted ' + res.deleted + ' items', { undo: res.undo, ms: 10000 });
        });
      });
    }, btn);
  }

  // ------------------------------------------------------------------
  // Supply run
  // ------------------------------------------------------------------
  function shortList() {
    return S.items.map(function (it) { return { it: it, i: info(it) }; })
      .filter(function (x) { return x.i.low; })
      .sort(function (a, b) { return catIndex(a.it.category) - catIndex(b.it.category) || byName(a.it, b.it); });
  }

  // What the below-target items should cost, from the prices set on them.
  function supplyCost(short) {
    var c = { sum: 0, priced: 0 };
    short.forEach(function (x) { if (x.it.price > 0) { c.sum += x.i.short * x.it.price; c.priced++; } });
    return c;
  }

  function renderSupply(el) {
    var short = shortList();
    var todo = S.shopping.filter(function (s) { return !s.done; }).length;
    var done = S.shopping.length - todo;
    var ha = S.server.ha && S.server.ha.todo ? S.server.ha : null;
    var ticked = ha ? ha.ticked || [] : [];
    var cost = supplyCost(short);
    var html = '<section class="card"><div class="card-head"><h2>Supply run</h2><span class="small muted">' + (short.length + todo) + ' to get' +
      (cost.priced ? ' · about ' + esc(money(cost.sum)) : '') + '</span></div>' +
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
          '<div class="need">Get <b>' + esc(qu(x.i.short, x.it.unit)) + '</b> · have ' + esc(fq(x.i.total)) + ' of ' + esc(fq(x.it.target_qty)) +
          (x.it.price > 0 ? ' · ' + esc(money(x.i.short * x.it.price)) : '') + '</div>' +
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
    var cost = supplyCost(short);
    if (cost.priced) lines.push('', 'About ' + money(cost.sum) + (cost.priced < short.length ? ' for the ' + cost.priced + ' with a price' : ''));
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
  // Plan: routine checks and the household emergency plan
  // ------------------------------------------------------------------
  function checkRow(x) {
    var c = x.c, cls = x.i.state === 'never' ? 'warn' : x.i.state === 'ok' ? 'plain' : x.i.state;
    return '<div class="li check-row"><span class="li-ico">📋</span>' +
      '<button class="li-main" data-act="check-open" data-id="' + c.id + '"><span class="li-title wrap">' + esc(c.name) + '</span>' +
      '<span class="li-sub"><span class="badge ' + cls + '">' + esc(x.i.text) + '</span><span>' + esc(everyWords(c.every_days)) + '</span></span></button>' +
      '<button class="btn small" data-act="check-done" data-id="' + c.id + '" aria-label="' + esc(c.name) + ': done">' + ICON.check + ' Done</button></div>';
  }

  function missingSuggestions() {
    var have = {};
    (S.checks || []).forEach(function (c) { have[c.name.toLowerCase()] = 1; });
    return (S.check_suggestions || []).filter(function (n) { return !have[n.toLowerCase()]; });
  }

  function renderPlan(el) {
    var list = sortedChecks();
    var due = list.filter(function (x) { return isDue(x.i); }).length;
    var missing = missingSuggestions();
    var html = '<section class="card' + (list.length ? ' flush' : '') + '"><div class="card-head"><h2>Routine checks</h2>' +
      (list.length ? '<span class="small muted">' + (due ? due + ' due' : 'All done') + '</span>' : '') + '</div>';
    if (!list.length) {
      html += '<p class="small muted">Stores only help if the kit works when you need it. Keep a list of the jobs that come round regularly, ' +
        'like testing the smoke alarms or charging the power banks. Tick each one off when you\'ve done it and Dads Army works out when it\'s next due.</p>' +
        '<div class="btn-stack"><button class="btn primary block" data-act="checks-seed">Add suggested checks</button>' +
        '<button class="btn block" data-act="check-new">' + ICON.plus + ' Add your own</button></div>';
    } else {
      html += '<p class="small muted pad">Tick each one off when you\'ve done it. Dads Army works out when it\'s next due.</p>' +
        '<div class="list">' + list.map(checkRow).join('') + '</div>' +
        '<div class="card-foot btn-row"><button class="btn" data-act="check-new">' + ICON.plus + ' Add a check</button>' +
        (missing.length ? '<button class="btn" data-act="checks-seed">Suggestions (' + missing.length + ')</button>' : '') + '</div>';
    }
    el.innerHTML = warnCard(true) + html + '</section>' + planCard();
  }

  function planEmpty(p) {
    return !p.contacts.length && PLAN_PARTS.every(function (x) { return !p[x[0]]; });
  }
  function telHref(phone) {
    var d = String(phone || '').replace(/[^0-9+]/g, '');
    return d.length >= 3 ? 'tel:' + d : '';
  }
  function planCard() {
    var p = S.plan;
    var html = '<section class="card"><div class="card-head"><h2>Emergency plan</h2>' +
      (p.updated_at ? '<span class="small muted">updated ' + esc(ago(p.updated_at)) + '</span>' : '') + '</div>';
    if (planEmpty(p)) {
      return html + '<p class="small muted">Write down what everyone needs to know if something happens: who to call, where to meet, ' +
        'and how to turn off the water, gas and electricity. It\'s kept here with the stores, works with the internet down, and prints on a page for the grab bag.</p>' +
        '<button class="btn primary block" data-act="plan-edit">Make your plan</button></section>';
    }
    if (p.contacts.length) {
      html += '<h3 class="plan-h">Contacts</h3><div class="list contacts">' + p.contacts.map(function (c) {
        var tel = telHref(c.phone);
        return '<div class="li"><span class="li-main"><span class="li-title">' + esc(c.name || c.phone) + '</span>' +
          (c.role ? '<span class="li-sub">' + esc(c.role) + '</span>' : '') + '</span>' +
          (tel ? '<a class="btn small call" href="' + esc(tel) + '" aria-label="Call ' + esc(c.name || c.phone) + '">' + ICON.phone + esc(c.phone) + '</a>'
            : c.phone ? '<span class="small">' + esc(c.phone) + '</span>' : '') + '</div>';
      }).join('') + '</div>';
    }
    PLAN_PARTS.forEach(function (x) {
      if (p[x[0]]) html += '<h3 class="plan-h">' + esc(x[1]) + '</h3><div class="notes">' + esc(p[x[0]]) + '</div>';
    });
    return html + '<div class="btn-row" style="margin-top:16px"><button class="btn" data-act="plan-edit">' + ICON.edit + ' Edit plan</button>' +
      '<button class="btn" data-act="print-plan">' + ICON.print + ' Print</button></div></section>';
  }

  // ------------------------------------------------------------------
  // Warnings: Met Office, floods, Emergency Alerts, GDACS, UKHSA, WHO
  // ------------------------------------------------------------------
  var WARN_ICON = { weather: '🌦️', flood: '🌊', alert: '📢', disaster: '🌍', fire: '🔥', news: '🩺' };
  var SRC_NAME = { metoffice: 'Met Office', floods: 'Environment Agency', govalerts: 'GOV.UK', gdacs: 'GDACS', fires: 'NASA FIRMS',
    ukhsa: 'UKHSA', who: 'WHO' };
  function W() {
    return S.warnings || { on: false, items: [], news: [], sources: {}, config: { sources: {} }, regions: [], source_list: [] };
  }
  function sevClass(s) { return s >= 3 ? 'bad' : s === 2 ? 'warn' : 'yellow'; }
  function srcName(k) { return SRC_NAME[k] || k; }
  function regionName(code) {
    if (code === 'UK' || !code) return 'the whole UK';
    var r = W().regions.filter(function (x) { return x[0] === code; })[0];
    return r ? r[1] : code;
  }
  function whenText(iso) {
    var d = new Date(iso);
    return isNaN(d) ? '' : d.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  }
  function hoursSince(ts) {
    if (!ts) return null;
    var t = new Date(String(ts).replace(' ', 'T')).getTime();
    return isNaN(t) ? null : (Date.now() - t) / 36e5;
  }
  function warnRow(w, i) {
    return '<div class="li warn-row sev' + w.severity + '"><span class="li-ico">' + (WARN_ICON[w.kind] || '⚠️') + '</span>' +
      '<button class="li-main" data-act="warn-open" data-i="' + i + '"><span class="li-title wrap">' + esc(w.title) + '</span>' +
      '<span class="li-sub"><span class="badge ' + sevClass(w.severity) + '">' + esc(w.level) + '</span><span>' + esc(srcName(w.source)) +
      (w.distance_km != null ? ' · ' + w.distance_km + ' km away' : '') + '</span></span></button>' + ICON.chev + '</div>';
  }
  // A line on how fresh the warnings are, and which sources aren't working.
  function warnHealth(w) {
    var bits = [], h = hoursSince(w.checked_at);
    if (h === null) bits.push('Not checked yet');
    else bits.push('Checked ' + ago(w.checked_at) + (h >= 1 ? ': these may be out of date' : ''));
    Object.keys(w.sources).forEach(function (k) {
      var s = w.sources[k];
      if (!s.ok) bits.push(srcName(k) + ': ' + s.error);
    });
    return bits;
  }

  // Sitrep: only when something's in force. Plan tab (full): always, with health news and the settings.
  function warnCard(full) {
    var w = W();
    if (!w.on) {
      if (!full) return '';
      return '<section class="card"><div class="card-head"><h2>Warnings</h2></div>' +
        '<p class="small muted">See official warnings for where you live, alongside your stores and plan: Met Office weather warnings, ' +
        'flood warnings, UK Emergency Alerts and major disasters near the UK, with optional fire detections from NASA satellites and health news from UKHSA and the WHO.</p>' +
        '<button class="btn primary block" data-act="warn-set">Set up warnings</button></section>';
    }
    // The Sitrep keeps it short: no test or finished Emergency Alerts, and the three most serious.
    var shown = w.items.map(function (x, i) { return [x, i]; }).filter(function (p) {
      return full || !(p[0].source === 'govalerts' && p[0].severity < 2);
    });
    if (!full && !shown.length) return '';
    var more = full ? 0 : Math.max(0, shown.length - 3);
    if (more) shown = shown.slice(0, 3);
    var top = shown.reduce(function (a, p) { return Math.max(a, p[0].severity); }, 0);
    var html = '<section class="card flush warn-card' + (top >= 2 ? ' sev' + top : '') + '"><div class="card-head"><h2>Warnings' +
      (w.items.length ? ' in force' : '') + '</h2>' + (full ? '<button class="link" data-act="warn-check">Check now</button>' : '<button class="link" data-tab="plan">All warnings</button>') + '</div>';
    if (shown.length) {
      html += '<div class="list">' + shown.map(function (p) { return warnRow(p[0], p[1]); }).join('') + '</div>' +
        (more ? '<button class="li more" data-tab="plan">' + more + ' more ' + ICON.chev + '</button>' : '');
    } else {
      html += '<p class="li muted small">No warnings for ' + esc(regionName(w.region)) +
        (w.location ? ', and no floods within ' + w.config.flood_km + ' km' : '') + '.</p>';
    }
    var health = warnHealth(w);
    var h = hoursSince(w.checked_at);
    if (full || h === null || h >= 1) html += '<p class="warn-health small muted">' + health.map(esc).join('<br>') + '</p>';
    if (full && w.news.length) {
      html += '<div class="group-head">🩺 Health news</div><div class="list">' + w.news.map(function (n) {
        return '<a class="li news" href="' + esc(n.url) + '" target="_blank" rel="noopener noreferrer"><span class="li-main"><span class="li-title wrap">' + esc(n.title) + '</span>' +
          '<span class="li-sub">' + esc(srcName(n.source)) + (n.issued ? ' · ' + esc(whenText(n.issued)) : '') + '</span></span>' + ICON.chev + '</a>';
      }).join('') + '</div>';
    }
    if (full) html += '<div class="card-foot"><button class="btn block" data-act="warn-set">Warnings settings</button></div>';
    return html + '</section>';
  }

  function warnHqCard() {
    var w = W();
    var html = '<section class="card"><div class="card-head"><h2>Warnings</h2>' + (w.on ? pill('good', 'On') : pill('plain', 'Off')) + '</div>';
    if (!w.on) {
      html += '<p class="small muted">Met Office, flood, Emergency Alert and disaster warnings for where you live, on the Sitrep and on your phone.</p>';
    } else {
      html += '<p class="small muted">Met Office region: <b>' + esc(regionName(w.region)) + '</b>' + (w.region_guessed && w.location ? ' (from your location)' : '') + '. ' +
        (w.location ? 'Location ' + (w.location.from === 'homeassistant' ? 'from Home Assistant' : 'set by hand') + '.' : 'No location set, so no flood or disaster warnings.') + '</p>' +
        '<p class="small muted">' + warnHealth(w).map(esc).join('<br>') + '</p>';
    }
    return html + '<button class="btn block" data-act="warn-set">' + (w.on ? 'Warnings settings' : 'Set up warnings') + '</button></section>';
  }

  // What to do, by kind of warning. General UK advice; the official message comes first.
  function warnTips(w) {
    var t = (w.title + ' ' + w.text).toLowerCase();
    if (w.kind === 'flood') {
      return { plan: ['meet_near', 'meet_far', 'power_off', 'gas_off', 'water_off'], tips: [
        'Move valuables, documents and medicines upstairs or somewhere high.',
        'Be ready to turn off the gas, electricity and water.',
        'Pack the grab bag and charge phones and power banks.',
        'Never walk or drive through flood water: 30cm of flowing water can float a car.'] };
    }
    if (w.kind === 'alert') {
      return { plan: ['meet_near', 'meet_far'], tips: [
        'Do what the alert tells you. Emergency Alerts are only sent when there\'s a danger to life nearby.',
        'Check that the people you live with, and neighbours, have seen it.'] };
    }
    if (w.kind === 'fire') {
      return { plan: ['meet_near', 'meet_far'], tips: [
        'If you can see flames, or smoke from a fire that looks out of control, call 999. Don\'t assume someone else has.',
        'Don\'t go to look, and keep away from the smoke.',
        'Close windows and doors to keep smoke out.',
        'If it\'s heading your way, get ready to leave: grab bag, medicines, pets, and know where you\'ll meet.'] };
    }
    if (w.kind === 'disaster') {
      return { plan: [], tips: [
        'Unless it\'s in the UK, the main thing is to keep up with the news.',
        'If you have family there or plan to travel, check the Foreign Office travel advice.'] };
    }
    if (/snow|ice/.test(t)) {
      return { plan: ['power_off'], tips: [
        'Make sure you could stay at home for a few days: food, water and medicines.',
        'Charge phones and power banks, and keep torches handy in case the power goes. Power cut: call 105.',
        'Check on older neighbours.'] };
    }
    if (/heat/.test(t)) {
      return { plan: [], tips: [
        'Keep extra drinking water, and drink plenty.',
        'Stay out of the sun between 11am and 3pm, and close curtains on rooms that get the sun.',
        'Check on older neighbours and anyone unwell.'] };
    }
    if (/wind|storm|thunder|lightning/.test(t)) {
      return { plan: ['power_off'], tips: [
        'Bring in or tie down garden furniture, bins and anything that could blow about.',
        'Charge phones and power banks, and keep torches handy. Power cut: call 105.',
        'Avoid travelling during the worst of it.'] };
    }
    if (/rain|flood/.test(t)) {
      return { plan: ['power_off', 'gas_off', 'water_off'], tips: [
        'Check the flood warnings for where you live.',
        'Keep documents and medicines somewhere high.',
        'Avoid driving through flood water.'] };
    }
    return { plan: [], tips: ['Allow extra time for journeys, or put them off.'] };
  }

  function sheetWarning(s) {
    var w = s.w, tips = warnTips(w), p = S.plan, r = readiness();
    var bits = tips.plan.filter(function (k) { return p[k]; });
    var heads = {};
    PLAN_PARTS.forEach(function (x) { heads[x[0]] = x[1]; });
    return sheetHead(w.title, srcName(w.source) + (w.issued ? ' · ' + whenText(w.issued) : ''), WARN_ICON[w.kind] || '⚠️') +
      '<div class="warn-meta"><span class="badge ' + sevClass(w.severity) + '">' + esc(w.level) + '</span>' +
      (w.area ? '<span class="small muted">' + esc(w.area) + '</span>' : '') +
      (w.distance_km != null ? '<span class="small muted">' + w.distance_km + ' km away</span>' : '') + '</div>' +
      (w.when ? '<p class="small"><b>' + esc(w.when) + '</b></p>' : '') +
      (w.text ? '<div class="notes">' + esc(w.text) + '</div>' : '') +
      (w.url ? '<a class="btn block ext" href="' + esc(w.url) + '" target="_blank" rel="noopener noreferrer">' +
        (w.kind === 'fire' ? 'See it on NASA\'s fire map' : 'Full details from ' + esc(srcName(w.source))) + '</a>' : '') +
      (w.kind === 'fire' && w.lat != null ? '<button class="btn block ext" data-act="fire-ignore" data-lat="' + w.lat + '" data-lon="' + w.lon + '">' +
        'Not a wildfire: ignore this spot</button>' : '') +
      '<h3>What to do</h3><ul class="tips">' + tips.tips.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') +
      (r.people && w.kind !== 'disaster' ? '<li>Your stores would last about <b>' + esc(fmtDays(r.hold)) + ' days</b>' +
        (r.supplies[0] ? ', and ' + esc(r.supplies[0].it.name) + ' about ' + esc(fmtDays(r.supplies[0].days)) + ' days' : '') + '.</li>' : '') + '</ul>' +
      (bits.length ? '<h3>From your plan</h3>' + bits.map(function (k) {
        return '<div class="plan-bit"><span class="sub-label">' + esc(heads[k]) + '</span><div class="notes">' + esc(p[k]) + '</div></div>';
      }).join('') : '') +
      '<p class="small muted" style="margin-top:14px">From ' + esc(srcName(w.source)) + '. Always follow official advice and the emergency services.</p>';
  }

  function sheetWarnSet() {
    var w = W(), c = w.config, loc = w.location;
    var guess = w.region_guessed && loc ? regionName(w.region) : '';
    var locLine = !loc ? 'Not set.' : loc.from === 'homeassistant'
      ? 'Using your Home Assistant home location (' + loc.lat.toFixed(3) + ', ' + loc.lon.toFixed(3) + ').'
      : 'Set by hand (' + loc.lat.toFixed(3) + ', ' + loc.lon.toFixed(3) + ').';
    var status = Object.keys(w.sources).map(function (k) {
      var s = w.sources[k];
      return '<div class="src-status"><span>' + esc(srcName(k)) + '</span><span class="small ' + (s.ok ? 'muted' : 'err') + '">' +
        (s.ok ? s.count + ' · checked ' + esc(ago(s.checked_at)) : esc(s.error)) + '</span></div>';
    }).join('');
    return sheetHead('Warnings', 'Official warnings for where you live', '📢') +
      '<form id="warnForm" novalidate>' +
      '<label class="opt big"><input type="checkbox" name="on"' + (c.on ? ' checked' : '') + '><span><b>Show warnings</b>' +
      '<span class="small muted">Checked every 15 minutes while the internet is up</span></span></label>' +
      '<p class="small muted">Dads Army downloads the public warning feeds (the same files for everyone) and works out here which are near you. ' +
      'Nothing about you is sent. If the internet goes down, everything else carries on and the last warnings stay on show.</p>' +
      '<h3>Sources</h3>' + w.source_list.map(function (s) {
        return '<label class="opt"><input type="checkbox" name="src_' + s[0] + '"' + (c.sources[s[0]] ? ' checked' : '') + '><span>' + esc(s[1]) + '</span></label>';
      }).join('') +
      '<h3>Where you are</h3>' +
      '<label class="field"><span>Met Office region</span><select name="region">' +
      '<option value="">' + (guess ? 'From my location: ' + esc(guess) : 'From my location') + '</option>' +
      '<option value="UK"' + (c.region === 'UK' ? ' selected' : '') + '>The whole UK</option>' +
      w.regions.map(function (r) { return '<option value="' + r[0] + '"' + (c.region === r[0] ? ' selected' : '') + '>' + esc(r[1]) + '</option>'; }).join('') +
      '</select></label>' +
      '<div class="field"><span>Location</span><div class="grid2">' +
      '<input type="number" name="lat" inputmode="decimal" step="any" placeholder="Latitude, e.g. 53.96" value="' + (c.lat != null ? c.lat : '') + '" aria-label="Latitude">' +
      '<input type="number" name="lon" inputmode="decimal" step="any" placeholder="Longitude, e.g. -1.08" value="' + (c.lon != null ? c.lon : '') + '" aria-label="Longitude"></div>' +
      '<div class="hint">' + esc(locLine) + ' Used for flood and disaster warnings, and never leaves your network. ' +
      (w.ha ? 'Leave empty to use your Home Assistant home location.' : 'Long-press your home in a maps app to find it.') + '</div></div>' +
      '<div class="grid2"><label class="field"><span>Floods within (km)</span><input type="number" name="flood_km" inputmode="numeric" min="1" max="200" value="' + c.flood_km + '"></label>' +
      '<label class="field"><span>Fires within (km)</span><input type="number" name="fire_km" inputmode="numeric" min="2" max="50" value="' + c.fire_km + '"></label></div>' +
      '<div class="grid2"><label class="field"><span>Disasters within (km)</span><input type="number" name="gdacs_km" inputmode="numeric" min="50" max="5000" value="' + c.gdacs_km + '"></label></div>' +
      '<p class="small muted" style="margin:-6px 0 12px">Disasters are orange and red alerts from GDACS, the UN and EU disaster alert system. ' +
      'Fires are hotspots NASA satellites saw in the last 24 hours: often controlled burns or farm fires, sometimes a wildfire. ' +
      'Places seen again and again over a week or more, like industrial flares, are left out, and you can tell it to ignore a spot.</p>' +
      (w.fire_ignored ? '<p class="small muted">Ignoring ' + w.fire_ignored + ' fire spot' + (w.fire_ignored === 1 ? '' : 's') +
        ' you\'ve marked as not a wildfire. <button type="button" class="link" data-act="fire-unignore">Show them again</button></p>' : '') +
      (status ? '<h3>Last check</h3>' + status : '') +
      '<p class="small muted" style="margin-top:12px">Sources: Met Office (weather warnings), Environment Agency (flood warnings, under the Open Government Licence), ' +
      'GOV.UK Emergency Alerts, GDACS, NASA FIRMS (fire detections), UK Health Security Agency and the World Health Organization.</p>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">Save and check now</button></div></form>';
  }

  // ------------------------------------------------------------------
  // Household alert level (worked out on the Pi: warnings + home sensors + stores)
  // ------------------------------------------------------------------
  var SRC_CLASS = { 'UK Government': 'gov', 'SAS Survival Handbook': 'sas', 'Fire & rescue services': 'fire',
    'Dads Army tip': 'tip', 'Electricity networks': 'net' };
  var LEVEL_RULES = {
    5: ['An Emergency Alert', 'A severe flood warning', 'A gas, carbon monoxide or smoke alarm going off'],
    4: ['A red weather warning', 'A flood warning', 'A power cut over 12 hours, or with the backup battery under 20%',
      'The coldest room under 9°C, or the warmest 33°C or more', 'PM2.5 air pollution of 75 µg/m³ or more'],
    3: ['An amber weather warning', 'A possible fire within 3 km', 'A power cut', 'A water leak',
      'The coldest room under 12°C, or the warmest 30°C or more', '−10°C or colder, or 35°C or hotter, outside',
      'PM2.5 of 55 µg/m³ or more'],
    2: ['A yellow weather warning', 'A flood alert', 'A disaster near the UK', 'A possible fire nearby',
      'The coldest room under 16°C, or the warmest 27°C or more', '−5°C or colder, or 30°C or hotter, outside',
      'Humidity of 80% or more indoors', 'The internet down', 'PM2.5 of 35 µg/m³ or more',
      'Food or water that wouldn\'t last 3 days', 'An area of resilience missing its essentials'],
    1: ['None of the above']
  };

  function levelScale(sit) {
    return '<div class="level-scale" role="img" aria-label="' + esc(sit.name + ', level ' + sit.level + ' of 5') + '">' +
      sit.scale.map(function (x) {
        return '<span class="ls lv' + x.level + (x.level === sit.level ? ' on' : '') + '"><i></i><b>' + esc(x.name) + '</b></span>';
      }).join('') + '</div>';
  }
  function levelCard() {
    var sit = S.situation;
    if (!sit) return '';
    var why = sit.reasons.slice(0, 3).map(function (r) { return r.title; });
    var more = sit.reasons.length - why.length;
    return '<section class="card level-card lv' + sit.level + '">' +
      '<div class="level-top"><span class="eyebrow">Household alert level</span>' +
      '<button class="info-btn" data-act="level-help" aria-label="What the alert levels mean">i</button></div>' +
      '<button class="level-main" data-act="level-open"><span class="level-name">' + esc(sit.name) + '</span>' +
      '<span class="level-meaning">' + esc(sit.meaning) + '</span></button>' +
      levelScale(sit) +
      '<p class="level-why">' + (why.length ? '<b>Why:</b> ' + esc(why.join(' · ')) + (more > 0 ? ' and ' + more + ' more' : '') +
        (sit.escalated ? '. Raised to SEVERE because ' + esc(sit.escalated_why || 'the stores wouldn\'t last 3 days') + '.' : '')
        : 'Nothing is raising the level.') + '</p>' +
      '<button class="btn block" data-act="level-open">What to do now</button></section>';
  }
  // ------------------------------------------------------------------
  // Resilience: ten areas, of which food and water are two (worked out on the Pi)
  // ------------------------------------------------------------------
  function RS() { return S.resilience || { pct: 0, done: 0, total: 0, areas: [], next: [], items: [] }; }
  function resById(id) { return RS().items.filter(function (m) { return m.id === id; })[0] || null; }
  function areaById(id) { return RS().areas.filter(function (a) { return a.id === id; })[0] || null; }
  var RES_MARK = { done: '✓', partly: '◐', todo: '○', na: '–' };

  function resilienceCard() {
    var r = RS();
    if (!r.areas.length) return '';
    var next = r.next.slice(0, 3).map(resById).filter(Boolean);
    return '<section class="card res-card">' +
      '<div class="level-top"><span class="eyebrow">Resilience</span>' +
      '<button class="info-btn" data-act="res-all" aria-label="About resilience, and every recommendation">i</button></div>' +
      '<div class="res-top"><span class="res-pct">' + r.pct + '<small>%</small></span>' +
      '<span class="res-sub">ready across ' + r.areas.length + ' areas<br>' + r.done + ' of ' + r.total + ' recommendations done</span></div>' +
      '<div class="res-grid">' + r.areas.map(areaButton).join('') + '</div>' +
      (next.length ? '<h3 class="res-h">Next steps</h3><div class="list res-next">' + next.map(nextRow).join('') + '</div>'
        : '<p class="small muted">Everything is done, or not for you. Well done.</p>') +
      '<button class="btn block" data-act="res-all">All recommendations</button></section>';
  }
  function areaButton(a) {
    var miss = a.essentials_missing.length;
    return '<button class="res-area ' + a.state + '" data-act="res-area" data-area="' + a.id + '">' +
      '<span class="ra-top"><span class="ra-ico">' + a.emoji + '</span><span class="ra-name">' + esc(a.name) + '</span>' +
      '<span class="ra-pct">' + a.pct + '%</span></span>' +
      '<span class="ra-bar"><i style="width:' + a.pct + '%"></i></span>' +
      '<span class="ra-sub">' + (miss ? miss + ' essential' + (miss === 1 ? '' : 's') + ' to do' : a.done + ' of ' + a.total + ' done') + '</span></button>';
  }
  function nextRow(m) {
    var a = areaById(m.area);
    return '<button class="li" data-act="res-area" data-area="' + m.area + '"><span class="li-ico">' + (a ? a.emoji : '') + '</span>' +
      '<span class="li-main"><span class="li-title wrap">' + esc(m.title) + '</span>' +
      '<span class="li-sub"><span class="badge ' + (m.priority === 3 ? 'bad' : m.priority === 2 ? 'warn' : 'plain') + '">' + esc(m.priority_word) + '</span>' +
      (m.detail ? '<span>' + esc(m.detail) + '</span>' : '') + '</span></span>' + ICON.chev + '</button>';
  }
  // One recommendation, with whatever would move it on.
  function resItem(m) {
    var act = m.act || {}, btns = [];
    if (act.kind === 'add') btns.push('<button class="btn small primary" data-act="res-add" data-rid="' + m.id + '">' + ICON.plus + ' Add to stores</button>');
    else if (act.kind === 'addcheck') btns.push('<button class="btn small primary" data-act="res-add" data-rid="' + m.id + '">' + ICON.plus + ' Add the check</button>');
    else if (act.kind === 'open') btns.push('<button class="btn small" data-act="open" data-id="' + act.item + '">Open in stores</button>');
    else if (act.kind === 'cat') btns.push('<button class="btn small" data-act="res-go" data-cat="' + act.cat + '">See the ' + esc(cat(act.cat).label.toLowerCase()) + ' stores</button>');
    else if (act.kind === 'expired') btns.push('<button class="btn small" data-act="res-go" data-show="expired">See what\'s out of date</button>');
    else if (act.kind === 'plan') btns.push('<button class="btn small" data-act="plan-edit">Fill in the plan</button>');
    else if (act.kind === 'check') btns.push('<button class="btn small" data-act="check-done" data-id="' + act.check + '">' + ICON.check + ' Done today</button>');
    else if (act.kind === 'sensors') btns.push('<button class="btn small" data-act="home-sensors">Choose home sensors</button>');
    else if (act.kind === 'warnings') btns.push('<button class="btn small" data-act="warn-set">Switch on warnings</button>');
    if (m.status === 'todo' || m.status === 'partly') {
      btns.push('<button class="btn small' + (m.manual ? ' primary' : '') + '" data-act="res-answer" data-rid="' + m.id + '" data-status="yes">' +
        ICON.check + (m.manual ? ' Done' : ' We have this') + '</button>');
      btns.push('<button class="btn small quiet" data-act="res-answer" data-rid="' + m.id + '" data-status="na">Not for us</button>');
    } else if (m.answer) {
      btns.push('<span class="small muted">' + (m.answer === 'na' ? 'You said it\'s not for you.' : 'You ticked this off.') + '</span>' +
        '<button class="link" data-act="res-answer" data-rid="' + m.id + '" data-status="">Undo</button>');
    }
    return '<div class="res-item ' + m.status + '"><span class="ri-mark" aria-hidden="true">' + RES_MARK[m.status] + '</span><div class="ri-main">' +
      '<div class="ri-title">' + esc(m.title) + (m.priority === 3 && m.status !== 'done' && m.status !== 'na' ? ' <span class="badge bad">Essential</span>' : '') + '</div>' +
      (m.why && m.status !== 'done' && m.status !== 'na' ? '<p class="ri-why">' + esc(m.why) + '</p>' : '') +
      '<div class="ri-meta"><span class="src src-' + (SRC_CLASS[m.source] || 'tip') + '">' + esc(m.label) + '</span>' +
      (m.detail && !m.answer ? '<span>' + esc(m.detail) + '</span>' : '') + '</div>' +
      (btns.length ? '<div class="ri-acts">' + btns.join('') + '</div>' : '') + '</div></div>';
  }
  function sheetArea(s) {
    var a = areaById(s.area);
    if (!a) return null;
    var ms = RS().items.filter(function (m) { return m.area === a.id; });
    var rank = { todo: 0, partly: 0, done: 1, na: 2 };
    ms.sort(function (x, y) { return rank[x.status] - rank[y.status] || y.priority - x.priority; });
    var todo = ms.filter(function (m) { return rank[m.status] === 0; }),
      done = ms.filter(function (m) { return m.status === 'done'; }), na = ms.filter(function (m) { return m.status === 'na'; });
    return sheetHead(a.name, a.pct + '% ready · ' + a.done + ' of ' + a.total + ' done', a.emoji) +
      '<div class="ra-bar big ' + a.state + '"><i style="width:' + a.pct + '%"></i></div>' +
      (todo.length ? '<h3>To do</h3>' + todo.map(resItem).join('') : '<p class="small">All done here.</p>') +
      (done.length ? '<h3>Done</h3>' + done.map(resItem).join('') : '') +
      (na.length ? '<details class="res-na"><summary>Not for you (' + na.length + ')</summary>' + na.map(resItem).join('') + '</details>' : '') +
      '<p class="small muted" style="margin-top:14px">Dads Army ticks off what it can see in your stores, plan, checks and home sensors. ' +
      '<button type="button" class="link" data-act="res-all">How it works</button></p>';
  }
  function sheetResAll() {
    var r = RS();
    return sheetHead('Resilience', r.pct + '% ready across ' + r.areas.length + ' areas', '🛡️') +
      '<p>Being ready isn\'t just food and water. Dads Army looks at ten areas, each with things to have, know or do. ' +
      'Most come from the UK Government\'s <b>Be Ready</b> checklist, Ofcom and the Fire Kills campaign.</p>' +
      '<div class="list">' + r.areas.map(function (a) {
        return '<button class="li" data-act="res-area" data-area="' + a.id + '"><span class="li-ico">' + a.emoji + '</span>' +
          '<span class="li-main"><span class="li-title">' + esc(a.name) + '</span>' +
          '<span class="li-sub">' + a.done + ' of ' + a.total + ' done' + (a.essentials_missing.length ? ' · ' + a.essentials_missing.length + ' essential' +
            (a.essentials_missing.length === 1 ? '' : 's') + ' to do' : '') + '</span>' +
          '<span class="ra-bar ' + a.state + '"><i style="width:' + a.pct + '%"></i></span></span>' +
          '<span class="cat-pct">' + a.pct + '%</span>' + ICON.chev + '</button>';
      }).join('') + '</div>' +
      '<h3>How it works</h3>' +
      '<p class="small">Dads Army ticks off what it can see for itself: your stores, the emergency plan, routine checks, warnings and home sensors. ' +
      'Tick the rest off yourself, or say they\'re not for you, like a gas tap if you have no gas.</p>' +
      '<p class="small">Each area\'s score is how much of it is done. Essentials count three times as much as extras, and recommended things twice as much. ' +
      'Something partly done counts in part, and anything not for you is left out. The overall figure is the average of the ten areas.</p>' +
      '<p class="small">An area missing an essential keeps the household alert level at MODERATE or higher. In a power cut with no torches or power bank, ' +
      'or a cold home with no blankets or warm clothes, SUBSTANTIAL goes up to SEVERE, because you\'d be less able to cope.</p>' +
      '<h3>Where the recommendations come from</h3><ul class="guidance">' +
      '<li><span class="src src-gov">UK Government</span>The Be Ready checklist (gov.uk), Ofcom on staying connected in a power cut, the Fire Kills campaign, and Emergency Alerts. Put into plain statements, not quoted word for word.</li>' +
      '<li><span class="src src-fire">Fire &amp; rescue services</span>Free home fire safety visits.</li>' +
      '<li><span class="src src-sas">SAS Survival Handbook</span>PLAN: Protection, applied to a home: keeping one room warm.</li>' +
      '<li><span class="src src-tip">Dads Army tip</span>Practical extras, like a camping stove, water containers or walkie-talkies.</li></ul>';
  }

  function guidanceList(items) {
    return '<ul class="guidance">' + items.map(function (g) {
      return '<li><span class="src src-' + (SRC_CLASS[g.source] || 'tip') + '">' + esc(g.label) + '</span>' + esc(g.text) + '</li>';
    }).join('') + '</ul>';
  }
  function readingText(r) {
    if (!r.ok) return r.state === 'missing' ? 'not found' : 'unavailable';
    var v = parseFloat(r.value);
    return isFinite(v) && r.unit ? fq(Math.round(v * 10) / 10) + (r.unit === '%' ? '%' : ' ' + r.unit) : String(r.state);
  }
  function homeReadings() {
    var h = S.home, roles = HOME_ROLES, rows = [];
    if (!h) return '';
    roles.forEach(function (role) {
      (h.readings[role[0]] || []).forEach(function (r) {
        rows.push('<div class="src-status"><span>' + esc(r.name) + '<span class="small muted"> · ' + esc(role[1]) + '</span></span>' +
          '<span class="small' + (r.ok ? ' muted' : ' err') + '">' + esc(readingText(r)) + '</span></div>');
      });
    });
    return rows.join('');
  }
  var HOME_ROLES = [['indoor_temp', 'Indoor temperature'], ['outdoor_temp', 'Outdoor temperature'], ['humidity', 'Humidity'],
    ['power', 'Mains power'], ['battery', 'Backup battery'], ['gas_alarm', 'Gas or CO alarm'], ['smoke_alarm', 'Smoke alarm'],
    ['leak', 'Leak sensor'], ['internet', 'Internet'], ['air', 'Air quality']];

  function sheetLevel() {
    var sit = S.situation;
    if (!sit) return null;
    var h = S.home, readings = homeReadings();
    return sheetHead('Household alert level', 'Where the household stands, and what to do', '🛡️') +
      '<div class="level-card lv' + sit.level + ' in-sheet"><span class="level-name">' + esc(sit.name) + '</span>' +
      '<span class="level-meaning">' + esc(sit.meaning) + '</span>' + levelScale(sit) + '</div>' +
      '<h3>Why</h3>' + (sit.reasons.length ? '<ul class="why">' + sit.reasons.map(function (r) {
        return '<li><span class="ls-chip lv' + r.level + '">' + esc(r.name) + '</span>' + esc(r.title) + '</li>';
      }).join('') + '</ul>' : '<p class="small muted">Nothing is raising the level.</p>') +
      (sit.escalated ? '<p class="small">Raised to SEVERE because ' + esc(sit.escalated_why || 'the stores wouldn\'t last 3 days') +
        ', so you\'d be less able to cope.</p>' : '') +
      (sit.notes.length ? '<p class="small muted">Also worth knowing: ' + esc(sit.notes.join(' · ')) + '</p>' : '') +
      '<h3>What to do now</h3>' + guidanceList(sit.guidance) +
      '<p class="small muted">UK Government advice is put into plain words, not quoted. SAS statements apply the SAS Survival Handbook\'s PLAN priorities to a home. ' +
      '<button type="button" class="link" data-act="level-help">More about the levels and sources</button></p>' +
      (h ? '<h3>Home sensors</h3>' + (readings || '<p class="small muted">No home sensors chosen yet. Temperatures, power, alarms and more can raise or lower the level.</p>') +
        '<button class="btn block" style="margin-top:10px" data-act="home-sensors">' + (readings ? 'Change home sensors' : 'Choose home sensors') + '</button>' : '') +
      '<p class="small muted" style="margin-top:14px">Always follow official advice and the emergency services. In an emergency, call 999.</p>';
  }

  function sheetLevelHelp() {
    var sit = S.situation, scale = sit ? sit.scale.slice().reverse() : [];
    return sheetHead('What the levels mean', 'The household alert level, explained', 'ℹ️') +
      '<p>Dads Army works out a <b>household alert level</b> from the warnings in force where you live, your home\'s own sensors, ' +
      'and how long your stores would last. It shows where the household should consider itself, and what to do about it.</p>' +
      '<div class="level-defs">' + scale.map(function (x) {
        return '<div class="level-def"><span class="ls-chip lv' + x.level + '">' + esc(x.name) + '</span><p>' + esc(x.meaning) + '</p>' +
          '<p class="small muted"><b>Raised to ' + esc(x.name) + ' by:</b> ' + esc(LEVEL_RULES[x.level].join('; ')) + '.</p></div>';
      }).join('') + '</div>' +
      '<p class="small">The level is the most serious of these. If it\'s SUBSTANTIAL and you\'d be less able to cope, it goes up to SEVERE: ' +
      'when your food or water wouldn\'t last 3 days, when there\'s a power cut and you have no torches or power bank, ' +
      'or when the home is cold and you have no blankets or warm clothes. Only real danger makes it CRITICAL. UKHSA advises heating the rooms you use to at least 18°C, so below that you get cold-weather advice even at LOW.</p>' +
      '<h3>The UK\'s own levels</h3>' +
      '<p class="small">The names are the UK\'s five national threat levels, the nearest British equivalent to America\'s DEFCON. They\'re set by MI5\'s Joint Terrorism Analysis Centre: ' +
      esc(scale.slice().reverse().map(function (x) { return x.name + ' (' + x.mi5 + ')'; }).join('; ')) + '. ' +
      'This is the household\'s own level, not the national one. <a href="https://www.mi5.gov.uk/threat-levels" target="_blank" rel="noopener noreferrer">See the national threat level</a>.</p>' +
      '<h3>Where the advice comes from</h3><ul class="guidance">' +
      '<li><span class="src src-gov">UK Government</span>Be Ready (gov.uk), Ofcom, the NHS, UKHSA, the Met Office, the Environment Agency, DEFRA, Ofgem, the Foreign Office and the Fire Kills campaign. Put into plain statements, not quoted word for word.</li>' +
      '<li><span class="src src-sas">SAS Survival Handbook</span>John “Lofty” Wiseman\'s PLAN priorities: Protection, Location, Acquisition (of water and food) and Navigation, applied to a household. Paraphrased, not quoted.</li>' +
      '<li><span class="src src-fire">Fire &amp; rescue services</span>Their standard advice on wildfires and smoke.</li>' +
      '<li><span class="src src-net">Electricity networks</span>The national power cut number, 105.</li>' +
      '<li><span class="src src-tip">Dads Army tip</span>Practical hints from the app itself.</li></ul>' +
      '<p class="small muted">Always follow official advice and the emergency services. In an emergency, call 999.</p>';
  }

  function sheetHomeSensors(s) {
    var d = s.data;
    if (!d) return sheetHead('Home sensors', 'From Home Assistant', '🌡️') + '<p class="small muted">Asking Home Assistant…</p>';
    if (d.error) return sheetHead('Home sensors', 'From Home Assistant', '🌡️') + '<p class="small ha-error">' + esc(d.error) + '</p>';
    var cfg = s.pick || d.config;
    var html = sheetHead('Home sensors', 'Sensors that change the alert level', '🌡️') +
      '<p class="small muted">Choose the Home Assistant sensors Dads Army should watch. Temperatures, humidity, power, alarms, leaks, the internet and air quality ' +
      'can raise the household alert level, and bring advice for the situation. Nothing is used until you save.</p>' +
      '<button type="button" class="btn block" data-act="hs-suggest" style="margin-bottom:12px">Suggest sensors for me</button>' +
      '<form id="homeSensorsForm" novalidate>';
    d.roles.forEach(function (role) {
      var c = d.candidates[role.key] || [], chosen = cfg[role.key];
      var picked = role.multiple ? (chosen || []) : (chosen ? [chosen] : []);
      html += '<details class="hs-role"' + (picked.length ? ' open' : '') + '><summary><b>' + esc(role.label) + '</b>' +
        '<span class="small muted">' + (picked.length ? picked.length + ' chosen' : c.length ? c.length + ' found' : 'none found') + '</span></summary>' +
        (role.hint ? '<p class="small muted">' + esc(role.hint) + '</p>' : '');
      if (!c.length) {
        html += '<p class="small muted">Home Assistant has nothing of this kind.</p>';
      } else if (role.multiple) {
        html += c.map(function (x) {
          return '<label class="opt"><input type="checkbox" name="hs_' + role.key + '" value="' + esc(x.entity_id) + '"' + (picked.indexOf(x.entity_id) >= 0 ? ' checked' : '') + '>' +
            '<span>' + esc(x.name) + '<span class="small muted">' + esc(x.state + (x.unit ? ' ' + x.unit : '')) + ' · ' + esc(x.entity_id) + '</span></span></label>';
        }).join('');
      } else {
        html += '<select name="hs_' + role.key + '" aria-label="' + esc(role.label) + '"><option value="">Not used</option>' + c.map(function (x) {
          return '<option value="' + esc(x.entity_id) + '"' + (picked[0] === x.entity_id ? ' selected' : '') + '>' + esc(x.name + ' (' + x.state + (x.unit ? ' ' + x.unit : '') + ')') + '</option>';
        }).join('') + '</select>';
      }
      html += '</details>';
    });
    return html + '<div class="sheet-actions"><button class="btn primary block" type="submit">Save</button></div></form>';
  }
  function homeSensorsForm(f, roles) {
    var out = {};
    roles.forEach(function (role) {
      if (role.multiple) out[role.key] = $$('input[name="hs_' + role.key + '"]:checked', f).map(function (i) { return i.value; });
      else out[role.key] = f.elements['hs_' + role.key] ? f.elements['hs_' + role.key].value : '';
    });
    return out;
  }
  function homeCard() {
    var h = S.home;
    if (!h) return '';
    var readings = homeReadings();
    return '<section class="card"><div class="card-head"><h2>Home sensors</h2></div>' +
      (readings ? readings : '<p class="small muted">Let your Home Assistant sensors (temperatures, humidity, power, gas and smoke alarms, leaks, the internet, ' +
        'air quality) raise or lower the household alert level, and bring advice for the situation.</p>') +
      '<button class="btn block" style="margin-top:10px" data-act="home-sensors">' + (readings ? 'Change home sensors' : 'Choose home sensors') + '</button></section>';
  }
  function dashNote() {
    var ha = S.server.ha;
    if (!ha || !ha.dash_outdated) return '';
    try { if (localStorage.getItem('da-dash-note') === 'layout4') return ''; } catch (e) { /* show it */ }
    return '<div class="card tip-card"><p><b>New for the Home front dashboard:</b> resilience across ten areas, from water and power to communications and safety, ' +
      'with every recommendation on its own page. Update the dashboard to get it.</p>' +
      '<div class="btn-row"><button class="btn small" data-act="ha-dash" data-again="1">Update the dashboard</button>' +
      '<button class="btn small" data-act="dash-note-hide">Not now</button></div></div>';
  }

  // ------------------------------------------------------------------
  // Help, and the guided set-up of the Home front dashboard
  // ------------------------------------------------------------------
  var dashOffered = false;   // offered once per visit at most (and the Pi remembers "not now")

  function maybeOfferDashboard() {
    var ha = S && S.server.ha;
    if (dashOffered || !ha || !ha.dash_prompt || !S.items.length) return;
    dashOffered = true;
    setTimeout(function () {
      if (stack.length || SEL) return;
      openSheet({ type: 'dashwiz', auto: true });
      api('PUT', 'api/homeassistant/prompt', { snooze_days: 3 }).catch(function () { /* asked again next time */ });
    }, 800);
  }

  function sheetHelp() {
    var ha = S.server.ha;
    function row(icon, title, sub, act, extra) {
      return '<button class="li" data-act="' + act + '"' + (extra || '') + '><span class="li-ico">' + icon + '</span>' +
        '<span class="li-main"><span class="li-title wrap">' + title + '</span><span class="li-sub">' + sub + '</span></span>' + ICON.chev + '</button>';
    }
    return sheetHead('Help', 'Getting the most from Dads Army', '❔') +
      '<div class="list help-list">' +
      (ha ? row('📊', 'Put Dads Army on your Home Assistant dashboard', 'Tiles for warnings, today\'s checklist, resilience and the stores', 'dash-wizard') : '') +
      row('🛡️', 'What the household alert level means', 'LOW to CRITICAL, and how it\'s worked out', 'level-help') +
      row('🔋', 'Resilience: what to do next', 'Ten areas, from water and power to communications and safety', 'res-all') +
      (ha ? row('🌡️', 'Choose home sensors', 'Temperatures, power, alarms and more can change the alert level', 'home-sensors') : '') +
      row('📢', 'Warnings for where you live', 'Met Office, floods, Emergency Alerts, fires', 'warn-set') +
      row('📋', 'Routine checks and your emergency plan', 'On the Plan tab', 'help-go', ' data-view="plan"') +
      row('🛒', 'Shopping for what\'s missing', 'The Supply run tab lists everything below target', 'help-go', ' data-view="supply"') +
      (S.items.length ? '' : row('📦', 'Load the starter list', 'About 95 essentials, sized for your household', 'seed')) +
      '</div>' +
      (ha ? '<h3>Phone alerts</h3><p class="small muted">Two ready-made automations send warnings, run-outs, checks that are due and a weekly round-up to your phone. ' +
        'In Home Assistant, open <b>Settings → Apps → Dads Army → Documentation</b> and follow <b>Phone alerts</b>.</p>' : '') +
      '<p class="small muted" style="margin-top:14px">Dads Army v' + esc(S.server.version) + '</p>';
  }

  // What the dashboard will look like, with today's numbers.
  function dashPreview() {
    var r = readiness(), w = W(), due = checksDue(), short = shortList().length + S.shopping.filter(function (x) { return !x.done; }).length;
    var pct = RS().pct;
    var soon = S.items.filter(function (it) { var i = info(it); return i.exp === 'bad' || i.exp === 'warn'; }).length;
    function t(icon, name, val, cls) {
      return '<div class="dp-tile' + (cls ? ' ' + cls : '') + '"><span class="dp-ico">' + icon + '</span><span class="dp-name">' + name + '</span><b>' + val + '</b></div>';
    }
    return '<div class="dash-preview" aria-hidden="true"><div class="dp-bar">Home front</div><div class="dp-grid">' +
      t('⚠️', 'Warnings', w.on ? w.items.length + ' in force' : 'off', w.items.length ? 'red' : '') +
      t('📋', 'Today\'s checklist', due + ' due', due ? 'purple' : '') +
      t('🛡️', 'Resilience', pct + '%', pct >= 80 ? 'green' : pct >= 50 ? 'amber' : 'red') +
      t('⏳', 'Hold out', fmtDays(r.hold) + ' days', '') +
      t('📅', 'Use first', soon + (soon === 1 ? ' item' : ' items'), soon ? 'amber' : '') +
      t('🛒', 'Supply run', short + ' to get', '') +
      '</div></div>';
  }

  function sheetDashWiz(s) {
    var ha = S.server.ha || {};
    var head = sheetHead('Dads Army on your Home Assistant dashboard', 'A ready-made Home front dashboard', '📊');
    if (s.steps) {
      var icon = { wait: '○', run: '…', ok: ICON.check, bad: ICON.cross };
      var html = head + '<ol class="wiz-steps">' + s.steps.map(function (st) {
        return '<li class="' + st.state + '"><span class="wiz-ico">' + icon[st.state] + '</span><span>' + esc(st.label) +
          (st.error ? '<span class="small ha-error">' + esc(st.error) + '</span>' : '') + '</span></li>';
      }).join('') + '</ol>';
      if (s.done) {
        return html + '<div class="wiz-done"><b>Done.</b> <b>Home front</b> is now in your Home Assistant sidebar and in the Companion app.' +
          (s.steps.some(function (st) { return st.key === 'checks'; }) ? ' Tick checks off there and they\'re marked done here.' : '') + '</div>' +
          '<div class="sheet-actions">' + (inHomeAssistant() && ha.dashboard ? '<a class="btn primary block" href="' + esc(ha.dashboard.url) + '" target="_top">Open Home front</a>' : '') +
          '<button class="btn block" data-act="close-sheet">Close</button></div>';
      }
      if (s.failed) {
        return html + '<p class="small muted">If it keeps failing, you can still add Dads Army by hand: the app\'s <b>Documentation</b> tab in Home Assistant has a card to paste into any dashboard.</p>' +
          '<div class="sheet-actions"><button class="btn primary block" data-act="dash-run">Try again</button><button class="btn block" data-act="close-sheet">Close</button></div>';
      }
      return html + '<p class="small muted">This takes a few seconds.</p>';
    }
    if (ha.dashboard) {
      return head + dashPreview() +
        '<p>The <b>Home front</b> dashboard is already in your Home Assistant sidebar (made ' + esc(ago(ha.dashboard.made_at)) + ').</p>' +
        '<p class="small muted">Rebuild it if you\'ve linked a list since, so the list shows on it. Rebuilding replaces any changes you\'ve made to that dashboard.</p>' +
        '<div class="sheet-actions">' + (inHomeAssistant() ? '<a class="btn primary block" href="' + esc(ha.dashboard.url) + '" target="_top">Open Home front</a>' : '') +
        '<button class="btn block" data-act="ha-dash" data-again="1">Rebuild it</button></div>';
    }
    function opt(name, have, title, sub) {
      if (have) return '<div class="opt done"><span class="wiz-ico ok">' + ICON.check + '</span><span><b>' + title + '</b><span class="small muted">Already on “' + esc(have) + '”</span></span></div>';
      return '<label class="opt"><input type="checkbox" name="' + name + '" checked><span><b>' + title + '</b><span class="small muted">' + sub + '</span></span></label>';
    }
    return head +
      '<p>Add a <b>Home front</b> dashboard to Home Assistant, so you can see how you\'re doing at a glance, on the wall tablet or in the Companion app.</p>' +
      dashPreview() +
      '<form id="dashWizForm" novalidate><h3>Also set up</h3>' +
      opt('wiz_checks', ha.checks && ha.checks_name, 'Today\'s checklist', 'Routine checks that are due go on a Home Assistant to-do list. Tick them off on the dashboard.') +
      opt('wiz_supply', ha.todo && ha.todo_name, 'Supply run list', 'The shopping list goes on a Home Assistant to-do list too, and you can add to it by voice.') +
      '<p class="small muted" style="margin-top:12px">It\'s a dashboard of its own: your other dashboards aren\'t changed. It uses Home Assistant\'s own cards, so there\'s nothing else to install.</p>' +
      '<div class="sheet-actions"><button class="btn primary block" type="button" data-act="dash-run">Make the dashboard</button>' +
      (s.auto ? '<div class="btn-row"><button class="btn" type="button" data-act="dash-later">Not now</button><button class="btn" type="button" data-act="dash-never">Don\'t ask again</button></div>' : '') +
      '</div></form>';
  }

  function runDashWizard(s) {
    var f = $('#dashWizForm');
    if (!s.steps) {
      s.steps = [];
      if (f && f.elements.wiz_checks && f.elements.wiz_checks.checked) {
        s.steps.push({ key: 'checks', label: 'Making the “Dads Army checks” list', path: 'api/homeassistant/checks-list', state: 'wait' });
      }
      if (f && f.elements.wiz_supply && f.elements.wiz_supply.checked) {
        s.steps.push({ key: 'supply', label: 'Making the “Supply run” list', path: 'api/homeassistant/todo-list', state: 'wait' });
      }
      s.steps.push({ key: 'dash', label: 'Building the Home front dashboard', path: 'api/homeassistant/dashboard', state: 'wait' });
    }
    s.failed = false;
    function show() { if (stack[stack.length - 1] === s) renderSheet(); }
    var chain = Promise.resolve();
    s.steps.forEach(function (st) {
      chain = chain.then(function () {
        if (st.state === 'ok') return;
        st.state = 'run';
        st.error = '';
        show();
        return api('POST', st.path, {}).then(function () { st.state = 'ok'; show(); }, function (e) {
          st.state = 'bad';
          st.error = e.message;
          throw e;
        });
      });
    });
    show();
    return chain.then(function () { s.done = true; }, function () { s.failed = true; })
      .then(function () { return refresh().catch(function () { /* shown anyway */ }); })
      .then(show);
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
      '<button class="btn block" data-act="print-plan">' + ICON.print + ' Print emergency plan &amp; checks</button>' +
      '<a class="btn block" href="api/backup.json" download>' + ICON.download + ' Download backup</a>' +
      '<a class="btn block" href="api/export.csv" download>' + ICON.download + ' Export spreadsheet (CSV)</a>' +
      '<button class="btn block" data-act="restore">' + ICON.upload + ' Restore from a backup…</button></div>' +
      '<p class="small muted" style="margin:10px 0 0">The Pi also saves its own copy every day' +
      (S.server.last_backup ? ' (last one ' + esc(ago(S.server.last_backup)) + ')' : '') + '.</p></section>';

    html += '<section class="card"><div class="card-head"><h2>Starter list</h2></div>' +
      '<p class="small muted">Adds about 95 suggested essentials at zero stock, with targets sized for your household and ' + target + '-day goal. ' +
      'Anything you already have is skipped. To clear out what you don\'t need, use <b>Select to delete</b> in Stores.</p>' +
      '<button class="btn block" data-act="seed">Load starter list</button></section>';

    html += warnHqCard() + homeCard() + haCard();

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
    var html = '<section class="card"><div class="card-head"><h2>Home Assistant</h2></div>' +
      '<h3 class="plan-h">Dashboard</h3>' + dashPart(ha) +
      '<h3 class="plan-h">Today\'s checklist</h3>' + checksPart(ha) +
      '<h3 class="plan-h">Supply run list</h3>';
    if (!ha.todo) {
      html += '<p class="small muted">Put the supply run on a Home Assistant to-do list. Tick things off there, and add to it from anywhere, ' +
        'including by voice: <i>“Add matches to the supply run list”</i>.</p>' +
        '<div class="btn-stack"><button class="btn block" data-act="ha-make">' + ICON.list + ' Make a “Supply run” list</button>' +
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
    return html + '<p class="small muted" style="margin:12px 0 0">For phone alerts and cards for your own dashboards, open the app\'s <b>Documentation</b> tab in Home Assistant.</p></section>';
  }
  function inHomeAssistant() {
    try { return window.top !== window.self; } catch (e) { return true; }
  }
  function dashPart(ha) {
    var d = ha.dashboard;
    if (!d) {
      return '<p class="small muted">Add a <b>Home front</b> dashboard to the Home Assistant sidebar, made of tiles: warnings, today\'s checklist, ' +
        'readiness, what to use first, the stores and the supply run. It also works in the Companion app.</p>' +
        '<button class="btn primary block" data-act="dash-wizard">Make the dashboard…</button>';
    }
    return '<p class="small muted">The <b>Home front</b> dashboard is in the Home Assistant sidebar (made ' + esc(ago(d.made_at)) + '). ' +
      'Rebuild it after linking a list below, so the list shows on it.</p>' +
      '<div class="btn-row">' + (inHomeAssistant() ? '<a class="btn" href="' + esc(d.url) + '" target="_top">Open it</a>' : '') +
      '<button class="btn" data-act="ha-dash" data-again="1">Rebuild it</button></div>';
  }
  function checksPart(ha) {
    if (!ha.checks) {
      return '<p class="small muted">Put the checks that are due on a Home Assistant to-do list. Tick one off on the dashboard or in the Companion app ' +
        'and it\'s marked done here, with the next one worked out.</p>' +
        '<div class="btn-stack"><button class="btn block" data-act="ha-checks-make">' + ICON.list + ' Make a “Dads Army checks” list</button>' +
        '<button class="btn block" data-act="ha-pick" data-target="checks">Use a list I already have…</button></div>';
    }
    var state = ha.checks_ok === false ? pill('bad', 'Not syncing') : ha.checks_ok ? pill('good', 'In step') : pill('warn', 'Starting');
    return '<div class="ha-link"><div class="li-main"><span class="li-title">' + esc(ha.checks_name) + '</span>' +
      '<span class="small muted">' + esc(ha.checks) + (ha.checks_synced_at ? ' · checked ' + esc(ago(ha.checks_synced_at)) : '') + '</span></div>' + state + '</div>' +
      (ha.checks_ok === false && ha.checks_error ? '<p class="small ha-error">' + esc(ha.checks_error) + '</p>' : '') +
      '<p class="small muted">Checks that are due, or not done yet, are on that list with their due dates. Tick one off there and it\'s marked done here.</p>' +
      '<div class="btn-row"><button class="btn" data-act="ha-pick" data-target="checks">Change list</button><button class="btn" data-act="ha-checks-stop">Stop</button></div>';
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
    var cost = supplyCost(short);
    if (cost.priced) html += '<p class="p-meta" style="margin-top:4mm">About ' + esc(money(cost.sum)) + (cost.priced < short.length ? ' for the ' + cost.priced + ' with a price' : '') + '</p>';
    $('#print-root').innerHTML = html;
    window.print();
  }

  function printPlan() {
    var p = S.plan;
    var html = '<h1>Dads Army · Emergency plan</h1><p class="p-meta">Printed ' + esc(new Date().toLocaleDateString('en-GB', { dateStyle: 'medium' })) +
      (p.updated_at ? ' · plan last updated ' + esc(fmtDate(p.updated_at)) : '') + '</p>';
    if (p.contacts.length) {
      html += '<h2>Contacts</h2><table><thead><tr><th>Who</th><th></th><th class="num">Number</th></tr></thead><tbody>';
      p.contacts.forEach(function (c) {
        html += '<tr><td><b>' + esc(c.name) + '</b></td><td>' + esc(c.role) + '</td><td class="num"><b>' + esc(c.phone) + '</b></td></tr>';
      });
      html += '</tbody></table>';
    }
    PLAN_PARTS.forEach(function (x) {
      if (p[x[0]]) html += '<h2>' + esc(x[1]) + '</h2><p class="p-text">' + esc(p[x[0]]) + '</p>';
    });
    var checks = sortedChecks();
    if (checks.length) {
      html += '<h2>Routine checks</h2><table><thead><tr><th>Check</th><th>How often</th><th>Last done</th><th>Next due</th><th>Done</th></tr></thead><tbody>';
      checks.forEach(function (x) {
        html += '<tr><td>' + esc(x.c.name) + '</td><td>' + esc(everyWords(x.c.every_days).replace(/^every /, 'Every ')) + '</td>' +
          '<td>' + (x.c.last_done ? esc(fmtDate(x.c.last_done)) : 'Not yet') + '</td>' +
          '<td class="p-exp">' + (x.i.due ? esc(fmtDate(x.i.due)) : 'Now') + '</td><td class="tick"></td></tr>';
      });
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
  // Close every open sheet at once (each was a step in history), then carry on.
  function closeAllSheets(then) {
    var n = stack.length, hs = history.state && history.state.daSheet;
    if (!n) return then && then();
    stack.length = 0;
    showSheet(true);
    if (hs) { try { history.go(-Math.min(n, hs)); } catch (e) { /* fine */ } }
    if (then) setTimeout(then, hs ? 150 : 0);
  }
  window.addEventListener('popstate', function () {
    if (stack.length) { stack.pop(); showSheet(true); }
    else if (SEL) { endSelect(); renderStoreList(); }
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
      item: sheetItem, edit: sheetEdit, stock: sheetStock, use: sheetUse, batch: sheetBatch, text: sheetText, halists: sheetHaLists,
      check: sheetCheck, plan: sheetPlan, warning: sheetWarning, warnset: sheetWarnSet, help: sheetHelp, dashwiz: sheetDashWiz,
      level: sheetLevel, levelhelp: sheetLevelHelp, homesensors: sheetHomeSensors, area: sheetArea, resall: sheetResAll
    }[s.type](s);
    if (html === null) {   // the item was deleted elsewhere
      closeSheet();
      return;
    }
    $('#sheet-body').innerHTML = html;
    if (s.type === 'edit') perDayHint($('#itemForm'));
  }
  function sheetHead(title, sub, icon) {
    return '<div class="sheet-head">' + (icon ? '<span class="li-ico">' + icon + '</span>' : '') +
      '<div><h2 id="sheet-title">' + esc(title) + '</h2>' + (sub ? '<p>' + esc(sub) + '</p>' : '') + '</div>' +
      '<button class="icon-btn" type="button" data-act="close-sheet" aria-label="Close">' + ICON.close + '</button></div>';
  }
  function stat(value, label) {
    return '<div class="stat"><span class="stat-val">' + esc(value) + '</span><span class="stat-lbl">' + esc(label) + '</span></div>';
  }
  function expiryField(val, usual) {
    return '<div class="field"><span>Best before / expiry</span>' +
      '<input type="date" name="expiry" value="' + esc(val || '') + '" aria-label="Best before date">' +
      '<div class="quick">' + (usual ? '<button type="button" class="chip" data-exp="' + usual + '">Like last time (+' + monthsWords(usual) + ')</button>' : '') +
      [[6, '6 months'], [12, '1 year'], [24, '2 years'], [60, '5 years'], [300, '25 years']].map(function (m) {
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
    if (it.per_day > 0) stats.push(stat(fmtDays(daysLeft(it)), 'days at ' + fq(it.per_day) + ' a day'));
    if (it.price > 0) stats.push(stat(money(i.total * it.price), 'worth, at ' + money(it.price) + ' each'));
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
    var v = it || { name: '', category: s.cat || 'food', unit: '', kcal_per_unit: 0, litres_per_unit: 0, target_qty: 0, per_day: 0, price: 0, notes: '' };
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
      '<div class="field"><div class="grid2"><label><span class="sub-label">Used a day</span><input type="number" name="per_day" value="' + (v.per_day || '') + '" inputmode="decimal" min="0" step="any" placeholder="0"></label>' +
      '<label><span class="sub-label">Price each (£)</span><input type="number" name="price" value="' + (v.price || '') + '" inputmode="decimal" min="0" step="0.01" placeholder="Optional"></label></div>' +
      '<div class="hint" id="perDayHint"></div></div>' +
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
  // Under "Used a day": what that means for the target, with a one-tap way to use it.
  function perDayHint(f) {
    var box = f && $('#perDayHint', f);
    if (!box) return;
    var pd = num(f.elements.per_day.value), days = S.settings.target_days;
    if (pd > 0) {
      var need = Math.ceil(pd * days - 1e-9);
      box.innerHTML = 'For your ' + days + '-day target that\'s <b>' + esc(fq(need)) + '</b>.' +
        (num(f.elements.target_qty.value) === need ? '' : ' <button type="button" class="link" data-act="use-target" data-val="' + need + '">Make that the target</button>');
    } else {
      box.textContent = 'For things you get through every day, like tablets, nappies or toilet roll: shows how long they\'ll last. A price adds up what the stores are worth.';
    }
  }

  function sheetStock(s) {
    var it = byId(s.id);
    if (!it) return null;
    return sheetHead('Add stock', it.name, cat(it.category).icon) +
      '<form id="stockForm" data-id="' + it.id + '" novalidate>' +
      '<div class="field"><span>' + esc(howMany(it.unit)) + '</span>' + stepperHtml('qty', s.qty || 1, 'Quantity') + '</div>' +
      expiryField('', usualLife(it)) + locationField(lastLocation(it) || lastLocation(lastTouched())) +
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
    var d = s.data, body, checks = s.target === 'checks';
    var ha = S.server.ha || {};
    var current = checks ? ha.checks : ha.todo, other = checks ? ha.todo : ha.checks;
    if (!d) body = '<p class="small muted">Asking Home Assistant…</p>';
    else if (d.error) body = '<p class="small ha-error">' + esc(d.error) + '</p>';
    else if (!d.lists.length) body = '<p class="small muted">Home Assistant hasn\'t got any to-do lists yet. Close this and use <b>Make a “' + (checks ? 'Dads Army checks' : 'Supply run') + '” list</b> instead.</p>';
    else {
      body = '<p class="small muted">' + (checks
        ? 'Best to pick a list just for the checks. Whatever is on it now is left alone.'
        : 'Best to pick a list just for Dads Army. Whatever is on it now is left alone. Anything added to it later goes on the supply run.') + '</p><div class="list">' +
        d.lists.filter(function (l) { return l.entity_id !== other; }).map(function (l) {
          var on = l.entity_id === current;
          return '<div class="li"><button class="li-main" data-act="ha-use" data-target="' + (checks ? 'checks' : 'supply') + '" data-entity="' + esc(l.entity_id) + '" data-name="' + esc(l.name) + '">' +
            '<span class="li-title">' + esc(l.name) + '</span><span class="small muted">' + esc(l.entity_id) + '</span></button>' +
            (on ? '<span class="badge ok">' + ICON.check + ' In use</span>' : '') + '</div>';
        }).join('') + '</div>';
    }
    return sheetHead('Choose a to-do list', 'From Home Assistant', '📋') + body;
  }

  var EVERY = [[7, 'Weekly'], [30, 'Monthly'], [91, '3 months'], [182, '6 months'], [365, 'Yearly']];
  function sheetCheck(s) {
    var c = s.id ? (S.checks || []).filter(function (x) { return x.id === s.id; })[0] : null;
    if (s.id && !c) return null;
    var v = c || { name: '', every_days: 30, last_done: null, notes: '' };
    var sub = c ? checkInfo(c).text + ' · ' + everyWords(c.every_days) : 'Something that needs doing regularly';
    return sheetHead(c ? c.name : 'New check', sub, '📋') +
      '<form id="checkForm" data-id="' + (c ? c.id : '') + '" novalidate>' +
      (c ? '<div class="btn-row" style="margin-bottom:16px"><button class="btn primary" type="button" data-act="check-done" data-id="' + c.id + '">' + ICON.check + ' Done today</button></div>' : '') +
      '<label class="field"><span>What needs doing?</span><input type="text" name="name" value="' + esc(v.name) + '" maxlength="120" placeholder="e.g. Run the generator" autocomplete="off"' + (c ? '' : ' data-autofocus') + '></label>' +
      '<div class="field every"><span>How often (days)</span>' + stepperHtml('every_days', v.every_days, 'Days between checks') +
      '<div class="quick">' + EVERY.map(function (e) {
        return '<button type="button" class="chip" data-every="' + e[0] + '" aria-pressed="' + (v.every_days === e[0]) + '">' + e[1] + '</button>';
      }).join('') + '</div></div>' +
      '<div class="field"><span>Last done</span><input type="date" name="last_done" value="' + esc(v.last_done || '') + '" max="' + today() + '" aria-label="Last done">' +
      '<div class="quick"><button type="button" class="chip" data-setdate="today">Today</button><button type="button" class="chip" data-setdate="">Not done yet</button></div></div>' +
      '<label class="field"><span>Notes</span><textarea name="notes" rows="2" maxlength="1000" placeholder="Optional: how to do it, what to look out for">' + esc(v.notes) + '</textarea></label>' +
      '<div class="sheet-actions"><button class="btn ' + (c ? '' : 'primary ') + 'block" type="submit">' + (c ? 'Save changes' : 'Add check') + '</button>' +
      (c ? '<button class="btn danger block" type="button" data-act="check-del" data-id="' + c.id + '">' + ICON.trash + ' Delete this check</button>' : '') + '</div></form>';
  }
  function syncEvery(field) {
    var v = num($('input', field).value);
    $$('[data-every]', field).forEach(function (b) { b.setAttribute('aria-pressed', String(+b.dataset.every === v)); });
  }

  function contactRow(c) {
    c = c || {};
    return '<div class="contact-row" data-contact>' +
      '<input type="text" data-c="name" value="' + esc(c.name) + '" placeholder="Name" maxlength="80" aria-label="Name" autocomplete="off">' +
      '<input type="tel" data-c="phone" value="' + esc(c.phone) + '" placeholder="Number" maxlength="40" aria-label="Phone number" autocomplete="off">' +
      '<button type="button" class="icon-btn" data-act="contact-del" aria-label="Remove this contact">' + ICON.close + '</button>' +
      '<input type="text" data-c="role" value="' + esc(c.role) + '" placeholder="Who they are, e.g. out-of-area contact" maxlength="80" aria-label="Who they are" autocomplete="off"></div>';
  }
  function sheetPlan() {
    var p = S.plan;
    var heads = { meet_near: 'Where to meet', water_off: 'Turning things off', medical: 'People, pets and papers' };
    return sheetHead('Emergency plan', 'What everyone needs to know', '🗺️') +
      '<form id="planForm" novalidate>' +
      '<h3>Contacts</h3><p class="small muted">Family, an out-of-area contact everyone can ring, neighbours, the GP, work and school.</p>' +
      '<div id="contacts">' + (p.contacts.length ? p.contacts.map(contactRow).join('') : contactRow()) + '</div>' +
      '<div class="quick" style="margin-bottom:6px"><button type="button" class="chip" data-act="contact-add">' + ICON.plus + ' Add a contact</button>' +
      '<button type="button" class="chip" data-act="contact-uk">Add UK emergency numbers</button></div>' +
      PLAN_PARTS.map(function (x) {
        return (heads[x[0]] ? '<h3>' + heads[x[0]] + '</h3>' : '') +
          '<label class="field"><span>' + esc(x[1]) + '</span><textarea name="' + x[0] + '" rows="2" maxlength="' + x[3] + '" placeholder="' + esc(x[2]) + '">' + esc(p[x[0]]) + '</textarea></label>';
      }).join('') +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">Save plan</button></div></form>';
  }
  function addUkNumbers(btn) {
    var box = $('#contacts'), have = {};
    $$('[data-contact]', box).forEach(function (row) {
      var d = $('[data-c="phone"]', row).value.replace(/\D/g, '');
      if (d) have[d] = 1;
      // Drop the empty row the form starts with
      if (!d && !$('[data-c="name"]', row).value.trim() && !$('[data-c="role"]', row).value.trim()) row.remove();
    });
    var added = 0;
    UK_NUMBERS.forEach(function (n) {
      if (have[n[2].replace(/\D/g, '')]) return;
      box.insertAdjacentHTML('beforeend', contactRow({ name: n[0], role: n[1], phone: n[2] }));
      added++;
    });
    toast(added ? 'Added ' + added + ' numbers. Save the plan to keep them.' : 'They\'re already on your plan');
    if (btn) btn.blur();
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
    t._undoPath = opts.undoPath || 'api/restore-item';
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; t._undo = null; },
      opts.ms || (opts.undo ? 6500 : opts.error ? Math.max(5000, msg.length * 60) : 2600));
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

  function checkWarnings(btn) {
    toast('Checking the warning feeds…', { ms: 45000 });
    return run(function () {
      return api('POST', 'api/warnings/check', {}).then(refresh).then(function () {
        var w = W(), bad = Object.keys(w.sources).filter(function (k) { return !w.sources[k].ok; });
        var n = w.items.length;
        toast((n ? n + ' warning' + (n === 1 ? '' : 's') + ' in force' : 'No warnings for where you are') +
          (bad.length ? '. Couldn\'t check ' + bad.map(srcName).join(', ') : ''), bad.length ? { ms: 6000 } : {});
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
      case 'sel-start':
        startSelect();
        return renderStoreList();
      case 'sel-cancel':
        endSelect();
        return renderStoreList();
      case 'sel-toggle':
        if (!SEL) return;
        if (SEL[id]) delete SEL[id]; else SEL[id] = 1;
        return syncSel();
      case 'sel-all': {
        if (!SEL) return;
        var shown = filtered();
        var every = shown.every(function (x) { return SEL[x.it.id]; });
        shown.forEach(function (x) { if (every) delete SEL[x.it.id]; else SEL[x.it.id] = 1; });
        return syncSel();
      }
      case 'sel-delete':
        return deletePicked(a);
      case 'del-batch':
        return run(function () {
          return api('DELETE', 'api/batches/' + id).then(function (res) {
            closeSheet();
            return refresh().then(function () { toast('Batch removed', { undo: res.undo }); });
          });
        }, a);
      case 'undo': {
        var t = $('#toast'), snap = t._undo, path = t._undoPath || 'api/restore-item';
        t.hidden = true;
        if (!snap) return;
        return run(function () {
          return api('POST', path, snap).then(refresh).then(function () { toast('Undone'); });
        });
      }
      case 'check-new':
        return openSheet({ type: 'check', id: null });
      case 'check-open':
        return openSheet({ type: 'check', id: id });
      case 'check-done': {
        var ck = (S.checks || []).filter(function (x) { return x.id === id; })[0];
        return run(function () {
          return api('POST', 'api/checks/' + id + '/done', {}).then(function (res) {
            if (stack.length && stack[stack.length - 1].type === 'check') closeSheet();
            return refresh().then(function () {
              toast((ck ? ck.name + ': done. ' : 'Done. ') + 'Next due ' + fmtDate(res.next_due) + '.', { undo: res.undo, undoPath: 'api/checks/restore' });
            });
          });
        }, a);
      }
      case 'check-del':
        return run(function () {
          return api('DELETE', 'api/checks/' + id).then(function (res) {
            closeSheet();
            return refresh().then(function () { toast('Deleted ' + res.undo.check.name, { undo: res.undo, undoPath: 'api/checks/restore' }); });
          });
        }, a);
      case 'checks-seed': {
        var miss = missingSuggestions();
        if (!miss.length) return toast('You already have all the suggested checks');
        if (!confirm('Add ' + miss.length + ' suggested check' + (miss.length === 1 ? '' : 's') + '?\n\n• ' + miss.join('\n• ') +
          '\n\nThey start as not done yet. Tap Done on each one as you do it, and delete any you don\'t need.')) return;
        return run(function () {
          return api('POST', 'api/checks/seed', {}).then(function (res) {
            return refresh().then(function () { toast('Added ' + res.added + ' check' + (res.added === 1 ? '' : 's')); });
          });
        }, a);
      }
      case 'warn-open': {
        var wi = W().items[+a.dataset.i];
        return wi ? openSheet({ type: 'warning', w: wi }) : null;
      }
      case 'warn-set':
        return openSheet({ type: 'warnset' });
      case 'warn-check':
        return checkWarnings(a);
      case 'help':
        return openSheet({ type: 'help' });
      case 'res-all':
        return openSheet({ type: 'resall' });
      case 'res-area':
        return openSheet({ type: 'area', area: a.dataset.area });
      case 'res-go': {
        var to = a.dataset.cat ? { cat: a.dataset.cat } : { show: a.dataset.show };
        return closeAllSheets(function () { goStores(to); });
      }
      case 'res-add':
        return run(function () {
          return api('POST', 'api/resilience/add', { id: a.dataset.rid }).then(function (res) {
            return refresh().then(function () {
              var bits = res.added.concat(res.checks);
              toast((res.added.length ? 'On the supply run: ' : 'Added to your checks: ') + bits.join(', '),
                res.undo ? { undo: res.undo, undoPath: 'api/items/delete' } : {});
            });
          });
        }, a);
      case 'res-answer': {
        var rq = resById(a.dataset.rid), stt = a.dataset.status;
        return run(function () {
          return api('POST', 'api/resilience/answer', { id: a.dataset.rid, status: stt }).then(function (res) {
            return refresh().then(function () {
              toast((rq ? rq.brief + ': ' : '') + (stt === 'yes' ? 'ticked off' : stt === 'na' ? 'not for you' : 'back on the list'),
                { undo: res.undo, undoPath: 'api/resilience/answer' });
            });
          });
        }, a);
      }
      case 'level-open':
        return openSheet({ type: 'level' });
      case 'level-help':
        return openSheet({ type: 'levelhelp' });
      case 'home-sensors': {
        var hs = { type: 'homesensors', data: null };
        openSheet(hs);
        return api('GET', 'api/homeassistant/sensors').then(function (d) { hs.data = d; }, function (e) {
          hs.data = { error: e.message };
        }).then(function () { if (stack[stack.length - 1] === hs) renderSheet(); });
      }
      case 'hs-suggest': {
        var top2 = stack[stack.length - 1];
        if (!top2 || top2.type !== 'homesensors' || !top2.data || !top2.data.suggested) return;
        top2.pick = top2.data.suggested;
        renderSheet();
        return toast('Suggestions ticked. Check them, then Save.');
      }
      case 'dash-note-hide':
        try { localStorage.setItem('da-dash-note', 'layout4'); } catch (e) { /* fine */ }
        return render();
      case 'help-go': {
        var dest = a.dataset.view;
        closeSheet();
        return setTimeout(function () { go(dest); }, 60);
      }
      case 'dash-wizard':
        return openSheet({ type: 'dashwiz' });
      case 'dash-run': {
        var top = stack[stack.length - 1];
        if (!top || top.type !== 'dashwiz') return;
        a.disabled = true;
        return runDashWizard(top);
      }
      case 'dash-later':
      case 'dash-never':
        closeSheet();
        return api('PUT', 'api/homeassistant/prompt', act === 'dash-never' ? { never: true } : { snooze_days: 14 }).then(function () {
          toast(act === 'dash-never' ? 'You can still make it any time: tap ? at the top' : 'Asking again in a couple of weeks. Or tap ? at the top any time.');
        }, function () { /* fine */ });
      case 'fire-ignore': {
        var spot = [+a.dataset.lat, +a.dataset.lon];
        if (!confirm('Ignore fires at this spot from now on?\n\nUse this for places like a refinery flare or a regular bonfire site. ' +
          'You can undo it straight away, or later in the warnings settings.')) return;
        return run(function () {
          return api('POST', 'api/warnings/ignore-fire', { lat: spot[0], lon: spot[1] }).then(function () {
            closeSheet();
            return refresh().then(function () {
              toast('You won\'t see fires at that spot again', { undo: { remove: spot }, undoPath: 'api/warnings/ignore-fire', ms: 8000 });
            });
          });
        }, a);
      }
      case 'fire-unignore':
        return run(function () {
          return api('POST', 'api/warnings/ignore-fire', { clear: true }).then(function () {
            closeSheet();
            return refresh().then(function () { toast('Ignored fire spots will show again at the next check'); });
          });
        }, a);
      case 'plan-edit':
        return openSheet({ type: 'plan' });
      case 'print-plan':
        if (planEmpty(S.plan) && !(S.checks || []).length) return toast('Nothing to print yet: fill in the plan on the Plan tab', { error: true });
        return printPlan();
      case 'contact-add': {
        var box = $('#contacts');
        box.insertAdjacentHTML('beforeend', contactRow());
        return $('[data-contact]:last-child [data-c="name"]', box).focus();
      }
      case 'contact-del': {
        var row = a.closest('[data-contact]');
        if (row) row.remove();
        if (!$('#contacts [data-contact]')) $('#contacts').insertAdjacentHTML('beforeend', contactRow());
        return;
      }
      case 'contact-uk':
        return addUkNumbers(a);
      case 'use-target': {
        var form = a.closest('form');
        form.elements.target_qty.value = a.dataset.val;
        return perDayHint(form);
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
        if (!confirm('Load the starter list?\n\nAbout 95 suggested essentials are added at zero stock, with targets sized for your household. To clear out anything you don\'t need, use Select to delete in Stores.')) return;
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
      case 'ha-checks-make':
        return run(function () {
          toast('Making the list in Home Assistant…');
          return api('POST', 'api/homeassistant/checks-list', {}).then(refresh).then(function () {
            toast('Checks that are due now go on “' + S.server.ha.checks_name + '”' + (S.server.ha.dashboard ? '. Rebuild the dashboard to show it there.' : ''));
          });
        }, a);
      case 'ha-checks-stop':
        if (!confirm('Stop putting the checks on “' + S.server.ha.checks_name + '”?\n\nDads Army takes its checks off that list. Anything else on it stays.')) return;
        return run(function () {
          return api('PUT', 'api/homeassistant', { checks_list: '' }).then(refresh).then(function () { toast('Stopped'); });
        }, a);
      case 'ha-dash':
        if (a.dataset.again && !confirm('Rebuild the Home front dashboard?\n\nAny changes you\'ve made to it in Home Assistant are replaced.')) return;
        return run(function () {
          toast('Making the dashboard in Home Assistant…', { ms: 20000 });
          return api('POST', 'api/homeassistant/dashboard', {}).then(function (res) {
            return refresh().then(function () {
              toast(res.made ? 'Done: Home front is in the Home Assistant sidebar' : 'The Home front dashboard is up to date');
            });
          });
        }, a);
      case 'ha-pick': {
        var sh = { type: 'halists', data: null, target: a.dataset.target || 'supply' };
        openSheet(sh);
        return api('GET', 'api/homeassistant').then(function (d) { sh.data = d; }, function (e) {
          sh.data = { error: e.message, lists: [] };
        }).then(function () { if (stack[stack.length - 1] === sh) renderSheet(); });
      }
      case 'ha-use': {
        var name = a.dataset.name, forChecks = a.dataset.target === 'checks';
        if (S.server.ha && S.server.ha[forChecks ? 'checks' : 'todo'] === a.dataset.entity) return closeSheet();
        return run(function () {
          return api('PUT', 'api/homeassistant', forChecks ? { checks_list: a.dataset.entity } : { todo_list: a.dataset.entity }).then(function () {
            closeSheet();
            return refresh().then(function () {
              toast(forChecks ? 'Checks that are due now go on “' + name + '”' : 'The supply run is now on “' + name + '”');
            });
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
        target_qty: num(d.target_qty), kcal_per_unit: num(d.kcal_per_unit), litres_per_unit: num(d.litres_per_unit),
        per_day: num(d.per_day), price: num(d.price)
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
    if (f.id === 'checkForm') {
      if (!d.name) { toast('Say what needs doing', { error: true }); f.elements.name.focus(); return; }
      var every = Math.round(num(d.every_days));
      if (every < 1) { toast('How many days between checks?', { error: true }); return; }
      var cid = f.dataset.id;
      var cbody = { name: d.name, every_days: every, last_done: d.last_done || null, notes: d.notes || '' };
      return run(function () {
        return api(cid ? 'PUT' : 'POST', cid ? 'api/checks/' + cid : 'api/checks', cbody).then(function () {
          closeSheet();
          return refresh().then(function () { toast(cid ? 'Saved' : 'Check added'); });
        });
      }, btn);
    }
    if (f.id === 'planForm') {
      var plan = { contacts: [] };
      $$('[data-contact]', f).forEach(function (row) {
        var c = {};
        ['name', 'role', 'phone'].forEach(function (k) { c[k] = $('[data-c="' + k + '"]', row).value.trim(); });
        if (c.name || c.role || c.phone) plan.contacts.push(c);
      });
      PLAN_PARTS.forEach(function (x) { plan[x[0]] = d[x[0]] || ''; });
      return run(function () {
        return api('PUT', 'api/plan', plan).then(function () {
          closeSheet();
          return refresh().then(function () { toast('Plan saved'); });
        });
      }, btn);
    }
    if (f.id === 'homeSensorsForm') {
      var hsTop = stack[stack.length - 1];
      var picks = homeSensorsForm(f, hsTop.data.roles);
      var n = Object.keys(picks).reduce(function (a, k) { return a + (Array.isArray(picks[k]) ? picks[k].length : picks[k] ? 1 : 0); }, 0);
      return run(function () {
        return api('PUT', 'api/homeassistant/sensors', picks).then(function () {
          closeSheet();
          toast('Saved. Reading ' + n + ' sensor' + (n === 1 ? '' : 's') + '…');
          return new Promise(function (ok) { setTimeout(ok, 2500); }).then(refresh).then(function () {
            toast(n ? 'Watching ' + n + ' home sensor' + (n === 1 ? '' : 's') + '. Alert level: ' + S.situation.name : 'Not watching any home sensors');
          });
        });
      }, btn);
    }
    if (f.id === 'warnForm') {
      var wbody = { on: f.elements.on.checked, region: d.region || '', lat: d.lat, lon: d.lon,
        flood_km: num(d.flood_km), gdacs_km: num(d.gdacs_km), fire_km: num(d.fire_km), sources: {} };
      W().source_list.forEach(function (s) { wbody.sources[s[0]] = f.elements['src_' + s[0]].checked; });
      if ((d.lat === '') !== (d.lon === '')) { toast('Give both a latitude and a longitude, or leave both empty', { error: true }); return; }
      return run(function () {
        return api('PUT', 'api/warnings', wbody).then(function () {
          closeSheet();
          if (!wbody.on) return refresh().then(function () { toast('Warnings switched off'); });
          return checkWarnings(null);
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
    if (v !== 'stores') endSelect();
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
    var every = t.closest('[data-every]');
    if (every) {
      every.closest('.field').querySelector('input').value = every.dataset.every;
      syncEvery(every.closest('.field'));
      return;
    }
    var setDate = t.closest('[data-setdate]');
    if (setDate) {
      setDate.closest('.field').querySelector('input[type="date"]').value = setDate.dataset.setdate === 'today' ? today() : '';
      return;
    }
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
    if ((t.name === 'per_day' || t.name === 'target_qty') && t.form && t.form.id === 'itemForm') perDayHint(t.form);
    if (t.name === 'every_days') syncEvery(t.closest('.field'));
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
    if (t.name === 'every_days') { syncEvery(t.closest('.field')); return; }
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
    if (e.key !== 'Escape') return;
    if (stack.length) closeSheet();
    else if (SEL) { endSelect(); renderStoreList(); }
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
