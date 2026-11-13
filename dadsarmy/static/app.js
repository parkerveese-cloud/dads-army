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
  var lastStateJson = '';       // the last /api/state seen, to skip redrawing when nothing changed
  var reqSeq = 0, reqApplied = 0;   // refreshes can overlap: only the newest answer counts
  var shopBusy = {};            // supply run extras with a tick on its way to HQ
  var searchTimer = null;
  var UNREACHABLE = "Can't reach Dads Army. Check Home Assistant is running and you're connected.";

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
  // A typed number, allowing a comma for the decimal point ("1,5"). NaN if it isn't a number.
  function parseQty(v) {
    v = String(v == null ? '' : v).replace(/\s+/g, '');
    if (/^[+-]?\d*,\d+$/.test(v)) v = v.replace(',', '.');
    if (!/^[+-]?(\d+\.?\d*|\.\d+)$/.test(v)) return NaN;
    return parseFloat(v);
  }
  function num(v) { var n = parseQty(v); return isFinite(n) ? n : 0; }
  var nf = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 3 });
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
  function warnDays(category) {
    return (S.settings.category_warn_days || {})[category] || S.settings.warn_days;
  }
  function expState(s, category) {
    if (!s) return 'none';
    var n = daysUntil(s);
    if (n < 0) return 'bad';
    if (n <= warnDays(category)) return 'warn';
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
  function dateAdd(s, n) { var d = parseYmd(s); d.setDate(d.getDate() + n); return ymd(d); }
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
  // In-date stock: what counts towards the target (expired stock needs replacing).
  function fresh(it) {
    return it.batches.reduce(function (a, b) { return a + (b.expiry && daysUntil(b.expiry) < 0 ? 0 : b.qty); }, 0);
  }
  function info(it) {
    var tot = total(it), good = fresh(it), soonest = null;
    it.batches.forEach(function (b) {
      if (b.expiry && b.qty > 0 && (soonest === null || b.expiry < soonest)) soonest = b.expiry;
    });
    return {
      total: tot,
      fresh: good,
      expired: Math.round((tot - good) * 1000) / 1000,
      soonest: soonest,
      exp: soonest ? expState(soonest, it.category) : 'none',
      low: it.target_qty > 0 && good < it.target_qty,
      out: good <= 0,
      none: tot <= 0,
      short: Math.max(0, Math.round((it.target_qty - good) * 1000) / 1000)
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
    var due = dateAdd(c.last_done, c.every_days), d = daysUntil(due);
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
    var people = st.adults + st.children, pets = st.pets || 0;
    var kcalDay = st.adults * st.kcal_adult + st.children * st.kcal_child + pets * (st.kcal_per_pet || 0);
    var waterDay = people * st.water_per_person + pets * (st.water_per_pet || 0);
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
    r.kitPct = kit.length ? kit.reduce(function (a, it) { return a + Math.min(1, fresh(it) / it.target_qty); }, 0) / kit.length : 0;
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
    if (method !== 'GET') dropUndo();   // a later change: an older Undo could now wipe it out
    return fetch(path, opt).then(function (res) {
      // Signed out of Home Assistant, or a proxy saying Dads Army isn't there: not an answer from HQ.
      var ours = !!res.headers.get('X-Dads-Army');
      var json = /application\/json/i.test(res.headers.get('Content-Type') || '');
      if (!json || (!ours && [401, 502, 503, 504].indexOf(res.status) >= 0)) {
        setOnline(false);
        throw new Error(UNREACHABLE);
      }
      setOnline(true);
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) throw new Error(data.error || ('Error ' + res.status));
        return data;
      });
    }, function () {
      setOnline(false);
      throw new Error(UNREACHABLE);
    });
  }
  function refresh() {
    var n = ++reqSeq;
    return api('GET', 'api/state').then(function (data) {
      if (n < reqApplied) return;   // an older request answering late
      reqApplied = n;
      var server = data.server || {};
      var json = JSON.stringify(data, function (k, v) { return this === server && k === 'time' ? undefined : v; });
      if (json === lastStateJson && S) return;   // nothing changed: don't redraw (or re-announce) anything
      lastStateJson = json;
      S = data;
      updateDatalists();
      if (hqTyping()) updateHQ();   // don't wipe out a setting that's being typed
      else render();
      maybeOfferDashboard();
    });
  }
  // Something in HQ has focus: a field being typed in, or about to be.
  function hqTyping() {
    var a = document.activeElement;
    return view === 'hq' && !stack.length && a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) && !!a.closest('#view');
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
  // A selector for an element that survives a redraw (same id, name or action), to keep focus on it.
  function focusKey(el) {
    if (!el || el === document.body || !el.getAttribute) return null;
    var sel = el.tagName.toLowerCase(), any = false;
    ['id', 'name', 'data-act', 'data-id', 'data-setting', 'data-step', 'data-d', 'data-key', 'data-val', 'data-cat', 'data-tab', 'data-catwarn'].forEach(function (a) {
      var v = el.getAttribute(a);
      if (v === null) return;
      any = true;
      sel += '[' + a + '="' + String(v).replace(/["\\]/g, '\\$&') + '"]';
    });
    return any ? sel : null;
  }
  function refocus(key, within) {
    if (!key) return false;
    var el = $(key, within);
    if (!el) return false;
    if (el !== document.activeElement) {
      try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); }
    }
    return true;
  }

  function render() {
    var a = document.activeElement;
    var keep = a && a.closest && a.closest('#view') ? focusKey(a) : null;
    $$('.tab').forEach(function (t) { t.setAttribute('aria-current', t.dataset.tab === view ? 'page' : 'false'); });
    var el = $('#view');
    if (!S) {
      el.dataset.view = '';
      el.innerHTML = offline
        ? '<div class="card empty"><div class="crate">📡</div><h2>No signal from HQ</h2><p>The app couldn\'t reach Dads Army. Check Home Assistant is running and you\'re connected.</p><button class="btn primary" data-act="retry">Try again</button></div>'
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
    mountIntelMap();   // the live alerts map lives on the Sitrep (and is tidied away elsewhere)
    if (stack.length && /^(item|area|resall)$/.test(stack[stack.length - 1].type)) renderSheet();
    if (keep && !stack.length) refocus(keep, el);
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

  // ------------------------------------------------------------------
  // First run: nothing in the stores yet (also shown by Stores when it's empty)
  // ------------------------------------------------------------------
  function emptyCard() {
    var st = S.settings, who = srHousehold(st);
    var steps = [
      ['Who you\'re feeding',
        who ? 'Set for <b>' + esc(who) + '</b>. Targets are sized from this and keep up if it changes.'
          : 'Tell HQ who lives with you, so the targets fit your household.',
        '<button class="btn small" data-tab="hq">' + (who ? 'Change household' : 'Set up household') + '</button>'],
      ['Your target',
        'Enough food and water to last <b>' + esc(st.target_days) + ' days</b>. You can change it at any time.',
        '<button class="btn small" data-tab="hq">Change target</button>'],
      ['Fill the stores',
        'Load about 95 suggested essentials at zero stock, then add what you already have. Or start from scratch.',
        '<button class="btn small primary" data-act="seed">Load starter list</button>' +
        '<button class="btn small" data-act="new">' + ICON.plus + ' Add an item</button>']
    ];
    return '<section class="card sr-first">' +
      '<div class="sr-first-head"><div class="card-kicker">Getting started</div>' +
      '<h2 class="sr-first-title">Let\'s get the stores in order</h2>' +
      '<p class="card-sub">Three steps, and the Sitrep fills in: how long you could hold out, what to use first and what to buy.</p></div>' +
      '<ol class="sr-steps">' + steps.map(function (s, i) {
        return '<li class="sr-step"><span class="sr-step-n" aria-hidden="true">' + (i + 1) + '</span>' +
          '<div class="sr-step-body"><h3 class="sr-step-title">' + s[0] + '</h3><p>' + s[1] + '</p>' +
          '<div class="sr-step-btns">' + s[2] + '</div></div></li>';
      }).join('') + '</ol></section>';
  }

  // ------------------------------------------------------------------
  // Sitrep
  // ------------------------------------------------------------------
  var SR_GRID = null;   // the Sitrep grid last drawn: while it's still on screen, a redraw is a refresh (charts don't animate)
  var SR_ICO = {
    clock: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 8v4.5l3 2"/></svg>',
    swap: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 10a7 7 0 0 1 12.2-3.6M19 14a7 7 0 0 1-12.2 3.6M17.5 3v3.6h-3.6M6.5 21v-3.6h3.6"/></svg>',
    cart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4.5h2.2l2.1 10a1.5 1.5 0 0 0 1.5 1.2h8.3a1.5 1.5 0 0 0 1.5-1.1L20 8.5H6"/><circle cx="9.5" cy="19.5" r="1.2"/><circle cx="17" cy="19.5" r="1.2"/></svg>',
    alert: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4.5l8.5 15h-17z"/><path d="M12 10.5v4M12 17.2v.01"/></svg>',
    bell: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 16v-5a5.5 5.5 0 0 1 11 0v5l1.5 2h-14z"/><path d="M10 20.5a2 2 0 0 0 4 0"/></svg>',
    people: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="3"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><circle cx="17" cy="9" r="2.2"/><path d="M15.8 14.1a4.5 4.5 0 0 1 4.7 4.4"/></svg>',
    trend: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 17l5-5 3.5 3.5L20 8"/><path d="M15 8h5v5"/></svg>'
  };
  // Units that read well as "3 tins of chopped tomatoes".
  var SR_OF = { tin: 1, jar: 1, pack: 1, bag: 1, bottle: 1, box: 1, carton: 1, bar: 1, roll: 1, tube: 1, tub: 1, canister: 1, kg: 1, g: 1, litre: 1 };

  function srHousehold(st) {
    var bits = [];
    if (st.adults) bits.push(st.adults + ' adult' + (st.adults === 1 ? '' : 's'));
    if (st.children) bits.push(st.children + (st.children === 1 ? ' child' : ' children'));
    if (st.pets) bits.push(st.pets + ' pet' + (st.pets === 1 ? '' : 's'));
    return bits.length > 1 ? bits.slice(0, -1).join(', ') + ' and ' + bits[bits.length - 1] : bits.join('');
  }
  function srDate(s) {   // "24 Nov", with the year when it isn't this year
    var d = parseYmd(s), o = { day: 'numeric', month: 'short' };
    if (d.getFullYear() !== new Date().getFullYear()) o.year = 'numeric';
    return d.toLocaleDateString('en-GB', o);
  }
  function srName(it) {   // "chopped tomatoes" from "Chopped tomatoes (400g)", "AA batteries" left alone
    var n = it.name.replace(/\s*\([^)]*\)\s*$/, '') || it.name;
    return /^[A-Z][a-z]/.test(n) ? n.charAt(0).toLowerCase() + n.slice(1) : n;
  }
  function srThing(it, qty) {   // "3 tins of chopped tomatoes", "the first aid kit", "2 × head torch"
    var u = (it.unit || '').toLowerCase(), n = srName(it);
    if (SR_OF[u]) return qu(qty, it.unit) + ' of ' + n;
    if (isMoney(it.unit)) return n + ' (' + qu(qty, it.unit) + ')';
    return qty === 1 ? 'the ' + n : fq(qty) + ' × ' + n;
  }
  function srNames(list, max) {   // "Rice, tinned fish and 6 more"
    var names = list.slice(0, max).map(function (it) { return it.name.replace(/\s*\([^)]*\)\s*$/, ''); });
    var more = list.length - names.length;
    if (more > 0) return names.join(', ') + ' and ' + more + ' more';
    return names.length > 1 ? names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1] : names.join('');
  }
  function srN(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function srGap(a, b) { return Math.round((parseYmd(b) - parseYmd(a)) / 864e5); }

  // History, oldest first with today last, and the entry to compare today against: a week back if we have it.
  function srHist() { return (S.history || []).filter(function (h) { return h && h.date; }); }
  function srBack(hist) {
    if (hist.length < 2) return null;
    var last = hist[hist.length - 1], i, gap;
    for (i = hist.length - 2; i >= 0; i--) {
      gap = srGap(hist[i].date, last.date);
      if (gap >= 7) return gap <= 10 ? { h: hist[i], when: 'this week', vs: 'on last week' } : null;
    }
    gap = srGap(hist[0].date, last.date);
    if (gap < 1) return null;
    var since = 'since ' + (gap === 1 ? 'yesterday' : parseYmd(hist[0].date).toLocaleDateString('en-GB', { weekday: 'long' }));
    return { h: hist[0], when: since, vs: since };
  }
  // A trend arrow with words. more: 'good' when going up is good, 'bad' when it's worse (expired and the like).
  function srDelta(diff, text, more) {
    var dir = Math.abs(diff) < 1e-9 ? 'flat' : diff > 0 ? 'up' : 'down';
    return '<span class="delta ' + dir + (more === 'bad' ? ' invert' : '') + '">' + esc(text) + '</span>';
  }

  function srCounts() {
    var c = { expired: 0, soon: 0, low: 0, out: 0 };
    S.items.forEach(function (it) {
      var i = info(it);
      if (i.exp === 'bad') c.expired++; else if (i.exp === 'warn') c.soon++;
      if (i.low) c.low++;
      if (i.out) c.out++;
    });
    return c;
  }

  // Hero: how long could we hold out, against what target, and which way it's heading.
  function srHero(r, hist, anim) {
    var st = S.settings, target = st.target_days;
    if (r.people === 0) {
      return '<section class="card col-8 sr-hero sr-hero-setup"><div class="card-kicker">Situation report</div>' +
        '<h2 class="sr-setup-title">Who are you feeding?</h2>' +
        '<p class="card-sub">Tell HQ who lives with you to see how long your food and water would last.</p>' +
        '<div class="sr-step-btns"><button class="btn primary" data-tab="hq">Set up household</button></div></section>';
    }
    var hs = stateOf(r.hold / target), days = fmtDays(r.hold);
    var limit = r.limit === 'food' ? 'Food runs out first' : r.limit === 'water' ? 'Water runs out first' : '';
    var notes = [];
    if (r.foodOldDays >= 0.1) notes.push(fmtDays(r.foodOldDays) + ' more days of food are past their date');
    if (r.waterOldDays >= 0.1) notes.push(fmtDays(r.waterOldDays) + ' more days of water are past best-before');
    if (r.noKcal) notes.push(srN(r.noKcal, 'food has', 'foods have') + ' no calories set, so don\'t count');

    var html = '<section class="card col-8 sr-hero"><div class="sr-hero-top"><div class="sr-hero-main">' +
      '<div class="card-kicker">Situation report</div>' +
      '<h2 class="sr-hold"><span class="sr-hold-lead">You could hold out for</span> ' +
      '<span class="sr-hold-num"><b>' + days + '</b> <span>' + (days === '1' ? 'day' : 'days') + '</span></span></h2>' +
      '<div class="sr-hero-sub">' + pill(hs, hs === 'good' ? target + '-day target met' : 'Target ' + target + ' days') +
      (limit ? '<span>' + limit + '</span>' : '') + '</div>' +
      (notes.length ? '<p class="sr-hero-note">' + esc(notes.join(' · ')) + '</p>' : '') + '</div>';

    var rings = [
      { value: Math.round(r.foodDays * 10) / 10, max: target, color: 'food', label: 'Food', unit: 'days' },
      { value: Math.round(r.waterDays * 10) / 10, max: target, color: 'water', label: 'Water', unit: 'days' }
    ];
    var legend = [
      { label: 'Food', color: 'food', value: fmtDays(r.foodDays) + ' of ' + target + ' days' },
      { label: 'Water', color: 'water', value: fmtDays(r.waterDays) + ' of ' + target + ' days' }
    ];
    if (r.kit) {
      rings.push({ value: Math.round(r.kitPct * 100), max: 100, color: 'kit', label: 'Kit and supplies', unit: '%' });
      legend.push({ label: 'Kit', color: 'kit', value: Math.round(r.kitPct * 100) + '% stocked' });
    }
    html += '<div class="sr-rings"><div class="sr-rings-chart">' + DAChart.rings({
      rings: rings, size: 168, title: 'Against your ' + target + '-day target', noAnimate: !anim,
      centre: { big: Math.min(999, Math.round(r.hold / target * 100)) + '%', small: 'of target' }
    }) + '</div>' + DAChart.legend({ items: legend, vertical: true }) + '</div></div>';

    // The trend: hold-out days a day at a time, against the target.
    var back = srBack(hist), head = '';
    if (back) {
      var d = r.hold - (+back.h.hold_out_days || 0), ad = Math.abs(d);
      var dt = ad < 0.05 ? 'No change ' + back.when : (d > 0 ? 'Up ' : 'Down ') + fmtDays(ad) + (fmtDays(ad) === '1' ? ' day ' : ' days ') + back.when;
      head = srDelta(ad < 0.05 ? 0 : d, dt, 'good');
    }
    var span90 = hist.length ? srGap(hist[0].date, hist[hist.length - 1].date) + 1 : 0;
    html += '<div class="sr-trend"><div class="sr-trend-head"><span class="sr-label">Hold-out days' +
      (hist.length >= 3 ? ', last ' + srN(Math.min(span90, 120), 'day', 'days') : '') + '</span>' + head + '</div>';
    if (hist.length >= 3) {
      var top = 0;
      hist.forEach(function (h) { top = Math.max(top, +h.hold_out_days || 0); });
      html += '<div class="sr-trend-chart">' + DAChart.trend({
        series: [{ name: 'Hold-out days', color: 'olive', points: hist.slice(-90).map(function (h) { return { x: h.date, y: h.hold_out_days }; }) }],
        height: 150, target: target, targetLabel: 'Target ' + target + ' days', yUnit: 'days', title: 'Hold-out days',
        yMax: Math.max(top, target) * 1.12, noAnimate: !anim
      }) + '</div>';
    } else {
      html += '<div class="sr-trend-empty">' + SR_ICO.trend + '<div><b>Your trend builds up as the days go by.</b>' +
        '<span>Dads Army notes how long you could hold out each day. In a few days you\'ll see which way it\'s heading.</span></div></div>';
    }
    return html + '</div></section>';
  }

  // Next actions: the few most useful things to do now, most pressing first.
  function srActions(r) {
    var st = S.settings, I = S.intel, acts = [], late = [];
    if (r.people === 0) acts.push({ state: 'info', ico: SR_ICO.people, title: 'Tell HQ who you\'re feeding', sub: 'So Dads Army can work out how long your stores last', attrs: 'data-tab="hq"' });

    // A live alert near you: the worst one goes to the top if it's serious.
    if (I && I.enabled) {
      var worst = null;
      I.sources.forEach(function (s) {
        if (!s.enabled) return;
        s.items.forEach(function (i) {
          if (scopeOf(i) === 'yours' && isAlert(i) && (!worst || LEVEL_RANK[i.level] > LEVEL_RANK[worst.i.level])) worst = { s: s, i: i };
        });
      });
      if (worst) {
        var al = { state: LEVEL_STATE[worst.i.level] || 'warn', ico: SR_ICO.alert, title: worst.i.title,
          sub: LEVEL_WORD[worst.i.level] + ' · ' + worst.s.name + (worst.i.area ? ' · ' + worst.i.area : ''),
          attrs: 'data-act="sr-alert" data-src="' + esc(worst.s.id) + '"' };
        if (LEVEL_RANK[worst.i.level] >= LEVEL_RANK.moderate) acts.push(al); else late.push(al);
      }
    }

    // Use what expires first: the soonest in-date batch inside its warning window.
    var soon = [];
    S.items.forEach(function (it) {
      it.batches.forEach(function (b) { if (b.qty > 0 && expState(b.expiry, it.category) === 'warn') soon.push({ it: it, b: b }); });
    });
    soon.sort(function (a, b) { return a.b.expiry < b.b.expiry ? -1 : a.b.expiry > b.b.expiry ? 1 : 0; });
    if (soon.length) {
      var f = soon[0], others = {};
      soon.forEach(function (x) { if (x.it.id !== f.it.id) others[x.it.id] = 1; });
      var no = Object.keys(others).length;
      acts.push({ state: 'warn', ico: SR_ICO.clock, title: 'Use ' + srThing(f.it, f.b.qty) + ' by ' + srDate(f.b.expiry),
        sub: [expiryWords(f.b.expiry), f.b.location, no ? srN(no, 'more thing', 'more things') + ' expiring soon' : ''].filter(Boolean).join(' · '),
        attrs: 'data-act="open" data-id="' + f.it.id + '"' });
    }

    // Replace what's expired.
    var old = S.items.filter(function (it) { return info(it).expired > 0; }).map(function (it) {
      var first = null;
      it.batches.forEach(function (b) { if (b.qty > 0 && b.expiry && daysUntil(b.expiry) < 0 && (!first || b.expiry < first)) first = b.expiry; });
      return { it: it, d: first };
    }).sort(function (a, b) { return a.d < b.d ? -1 : a.d > b.d ? 1 : 0; });
    if (old.length === 1) {
      acts.push({ state: 'bad', ico: SR_ICO.swap, title: 'Replace ' + srThing(old[0].it, info(old[0].it).expired),
        sub: 'Went out of date on ' + srDate(old[0].d), attrs: 'data-act="open" data-id="' + old[0].it.id + '"' });
    } else if (old.length > 1) {
      acts.push({ state: 'bad', ico: SR_ICO.swap, title: 'Replace ' + old.length + ' things that are out of date',
        sub: srNames(old.map(function (x) { return x.it; }), 3), attrs: 'data-act="go" data-show="expired"' });
    }

    // Buy what's out, or runs out soonest at the rate you're using it.
    var buy = S.items.map(function (it) { return { it: it, i: info(it) }; }).filter(function (x) { return x.i.low; });
    if (buy.length) {
      buy.forEach(function (x) {
        var ro = x.it.usage && x.it.usage.runs_out_in_days;
        x.d = x.i.out ? 0 : ro !== null && ro !== undefined && isFinite(ro) ? +ro : Infinity;
        x.w = x.it.category === r.limit ? 0 : x.it.category === 'water' ? 1 : x.it.category === 'food' ? 2 : 3;
      });
      buy.sort(function (a, b) {
        return a.d - b.d || a.w - b.w || (a.i.fresh / a.it.target_qty) - (b.i.fresh / b.it.target_qty) || byName(a.it, b.it);
      });
      var x = buy[0], t;
      if (x.i.out) t = 'Buy ' + srName(x.it) + (x.i.none ? ': none in stock' : ': none in date');
      else if (x.d !== Infinity) t = 'Buy more ' + srName(x.it) + ': runs out in about ' + span(Math.max(1, Math.round(x.d)));
      else t = 'Top up ' + srName(x.it) + ': ' + fq(x.i.fresh) + ' of ' + qu(x.it.target_qty, x.it.unit);
      acts.push({ state: x.i.out ? 'bad' : 'warn', ico: SR_ICO.cart, title: t,
        sub: 'Get ' + qu(x.i.short, x.it.unit) + (buy.length > 1 ? ' · ' + srN(buy.length - 1, 'more thing', 'more things') + ' on the supply run' : ''),
        attrs: 'data-tab="supply"' });
    }
    acts = acts.concat(late);

    // Setting up.
    if (I && !I.enabled) acts.push({ state: 'info', ico: SR_ICO.bell, title: 'Switch on live alerts', sub: 'Floods, severe weather and power cuts near you', attrs: 'data-act="go-hq-intel"' });
    var starter = S.items.some(function (it) { return it.target_rule; }) || S.log.some(function (l) { return l.action === 'starter'; });
    if (!starter && S.items.length < 25) acts.push({ state: 'info', ico: ICON.list, title: 'Load the starter list', sub: 'About 95 suggested essentials, sized for your household', attrs: 'data-act="seed"' });
    return acts.slice(0, 5);
  }
  function srNext(r) {
    var acts = srActions(r);
    var html = '<section class="card col-4 sr-next"><div class="card-head"><h2>Next actions</h2>' +
      (acts.length ? '<span class="small muted">most pressing first</span>' : '') + '</div>';
    if (!acts.length) {
      return html + '<div class="sr-clear"><span class="sr-clear-ico">' + ICON.check + '</span><b>Nothing needs doing</b>' +
        '<span>Everything\'s in date and at target. Carry on.</span></div></section>';
    }
    return html + '<ol class="sr-acts">' + acts.map(function (a) {
      return '<li><button class="sr-act" data-state="' + a.state + '" ' + a.attrs + '><span class="sr-act-ico">' + a.ico + '</span>' +
        '<span class="sr-act-text"><span class="sr-act-title">' + esc(a.title) + '</span>' +
        (a.sub ? '<span class="sr-act-sub">' + esc(a.sub) + '</span>' : '') + '</span>' + ICON.chev + '</button></li>';
    }).join('') + '</ol></section>';
  }

  // The four counts, each with a small trend and a way into the list.
  function srKpis(c, hist, anim) {
    var back = srBack(hist), st = S.settings;
    var defs = [
      { label: 'Expired', n: c.expired, state: 'bad', show: 'expired', h: 'expired' },
      { label: Object.keys(st.category_warn_days || {}).length ? 'Expiring soon' : 'Expiring in ' + st.warn_days + ' days', n: c.soon, state: 'warn', show: 'soon', h: 'expiring' },
      { label: 'Below target', n: c.low, state: 'warn', show: 'low', h: 'below_target' },
      { label: 'Out of stock', n: c.out, state: 'bad', show: 'out', h: null }
    ];
    return '<div class="col-12 kpi-row sr-kpis">' + defs.map(function (k) {
      var state = k.n ? k.state : 'good', foot = '', spark = '';
      if (k.h && back) {
        var d = k.n - (+back.h[k.h] || 0);
        foot = srDelta(d, d === 0 ? (back.vs === 'on last week' ? 'Same as last week' : 'No change ' + back.vs) : (d > 0 ? '+' : '−') + Math.abs(d) + ' ' + back.vs, 'bad');
      } else if (!k.h) {
        foot = '<span class="sr-kpi-note">of ' + srN(S.items.length, 'item', 'items') + '</span>';
      }
      if (k.h && hist.length >= 3) {
        spark = DAChart.spark({ points: hist.slice(-30).map(function (h) { return h[k.h]; }), height: 28, color: k.n ? k.state : 'muted', area: true,
          title: k.label + ', last 30 days', unit: 'items', noAnimate: !anim });
      }
      return '<button class="stat sr-kpi" data-state="' + state + '" data-act="go" data-show="' + k.show + '">' +
        '<span class="stat-label">' + esc(k.label) + '</span>' +
        '<span class="stat-val">' + k.n + ' <span class="stat-unit">' + (k.n === 1 ? 'item' : 'items') + '</span></span>' +
        '<span class="stat-foot">' + foot + '</span>' +
        '<span class="stat-spark" aria-hidden="' + (spark ? 'false' : 'true') + '">' + spark + '</span></button>';
    }).join('') + '</div>';
  }

  // Expiry timeline: batches with stock, by the month they go out of date, after a column of what already has.
  function srTimeline(anim) {
    var now = new Date(), y = now.getFullYear(), m = now.getMonth(), k;
    var cols = [{ label: 'Expired', short: 'Past', long: 'Already expired', bad: 0, warn: 0, ok: 0, show: 'expired' }];
    for (k = 0; k < 12; k++) {
      var md = new Date(y, m + k, 1);
      cols.push({ label: md.toLocaleDateString('en-GB', { month: 'short' }), long: md.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }), bad: 0, warn: 0, ok: 0, show: 'all' });
    }
    var later = 0, tot = { bad: 0, warn: 0, ok: 0 };
    S.items.forEach(function (it) {
      it.batches.forEach(function (b) {
        if (!b.expiry || !(b.qty > 0)) return;
        var s = expState(b.expiry, it.category);
        if (s === 'bad') { cols[0].bad++; tot.bad++; return; }
        var bd = parseYmd(b.expiry), idx = (bd.getFullYear() - y) * 12 + bd.getMonth() - m;
        if (idx >= 12) { later++; return; }
        cols[idx + 1][s === 'warn' ? 'warn' : 'ok']++;
        tot[s === 'warn' ? 'warn' : 'ok']++;
      });
    });
    var chart = DAChart.columns({
      columns: cols.map(function (c) {
        return { label: '', key: c.long, stacks: [{ value: c.bad, state: 'bad', label: 'expired' }, { value: c.warn, state: 'warn', label: 'expiring soon' }, { value: c.ok, state: 'good', label: 'later' }] };
      }),
      height: 220, title: 'Batches by expiry month', noAnimate: !anim
    });
    var hits = cols.map(function (c) {
      var n = c.bad + c.warn + c.ok;
      var lab = c.long + ': ' + (n ? srN(n, 'batch', 'batches') + (c.warn && c.ok ? ', ' + c.warn + ' expiring soon' : '') : 'nothing') + '. Open Stores, soonest first';
      return '<button class="sr-col-hit" data-act="go" data-show="' + c.show + '" data-sort="expiry" aria-label="' + esc(lab) + '">' +
        (c.short ? '<span class="sr-col-l"><span class="sr-wide">' + c.label + '</span><span class="sr-narrow">' + c.short + '</span></span>' : '<span class="sr-col-l">' + c.label + '</span>') + '</button>';
    }).join('');
    var lastMonth = cols[12].long;
    return '<section class="card col-7 sr-timeline"><div class="card-head"><h2>Expiry timeline</h2>' +
      '<button class="link" data-act="go" data-show="all" data-sort="expiry">Soonest first</button></div>' +
      '<p class="card-sub sr-sub">Batches in stock by the month they go out of date, to ' + esc(lastMonth) + '</p>' +
      '<div class="sr-cols"><div class="sr-cols-chart">' + chart + '</div><div class="sr-cols-hits">' + hits + '</div></div>' +
      '<div class="sr-foot">' + DAChart.legend({ items: [
        { label: 'Expired', state: 'bad', value: tot.bad }, { label: 'Expiring soon', state: 'warn', value: tot.warn }, { label: 'Fine', state: 'good', value: tot.ok }
      ] }) + (later ? '<span class="small muted">+ ' + srN(later, 'batch', 'batches') + ' after that</span>' : '') + '</div></section>';
  }

  // Stock by category: how complete each one is against its targets.
  function srCats(anim) {
    var rows = '';
    CATS.forEach(function (c) {
      var its = S.items.filter(function (it) { return it.category === c.id; });
      if (!its.length) return;
      var tg = its.filter(function (it) { return it.target_qty > 0; });
      var met = tg.filter(function (it) { return fresh(it) >= it.target_qty; }).length;
      var p = tg.length ? tg.reduce(function (a, it) { return a + Math.min(1, fresh(it) / it.target_qty); }, 0) / tg.length : null;
      var pc = p === null ? null : Math.floor(p * 100);
      rows += '<button class="sr-cat" data-act="cat-go" data-cat="' + c.id + '" aria-label="' + esc(c.label + ': ' +
        (p === null ? srN(its.length, 'item', 'items') + ', no targets' : pc + '% stocked, ' + met + ' of ' + tg.length + ' at target')) + '">' +
        '<span class="sr-cat-top"><span class="sr-cat-name"><span aria-hidden="true">' + c.icon + '</span> ' + esc(c.short || c.label) + '</span>' +
        '<span class="sr-cat-pct"><span class="sr-cat-n">' + (p === null ? srN(its.length, 'item', 'items') : met + '/' + tg.length) + '</span>' +
        (p === null ? '–' : pc + '%') + '</span></span>' +
        DAChart.meter({ value: pc === null ? 0 : pc, max: 100, state: p === null ? 'info' : stateOf(p), height: 6, noAnimate: !anim }) + '</button>';
    });
    return '<section class="card col-5 sr-catcard"><div class="card-head"><h2>Stock by category</h2>' +
      '<span class="small muted">items at target · stocked</span></div><div class="sr-cats">' + rows + '</div></section>';
  }

  function srUseFirst() {
    var upcoming = [];
    S.items.forEach(function (it) {
      it.batches.forEach(function (b) { if (b.expiry && b.qty > 0) upcoming.push({ it: it, b: b }); });
    });
    upcoming.sort(function (a, b) { return a.b.expiry < b.b.expiry ? -1 : a.b.expiry > b.b.expiry ? 1 : 0; });
    var urgent = upcoming.filter(function (x) { return expState(x.b.expiry, x.it.category) !== 'ok'; });
    var list = (urgent.length ? urgent : upcoming).slice(0, 5);
    if (!list.length) return '';
    return '<section class="card flush sr-use"><div class="card-head"><h2>' + (urgent.length ? 'Use these first' : 'Next to expire') + '</h2>' +
      (upcoming.length > list.length ? '<button class="link" data-act="go" data-show="all" data-sort="expiry">See all</button>' : '') + '</div><div class="list">' +
      list.map(function (x) {
        var es = expState(x.b.expiry, x.it.category);
        return '<div class="li"><span class="li-ico" aria-hidden="true">' + cat(x.it.category).icon + '</span>' +
          '<button class="li-main" data-act="open" data-id="' + x.it.id + '"><span class="li-title">' + esc(x.it.name) + '</span>' +
          '<span class="li-sub"><span class="badge ' + (es === 'ok' ? 'plain' : es) + '">' + esc(expiryWords(x.b.expiry)) + '</span>' +
          '<span>' + esc(qu(x.b.qty, x.it.unit)) + (x.b.location ? ' · ' + esc(x.b.location) : '') + '</span></span></button>' +
          '<button class="qbtn" data-act="use" data-id="' + x.it.id + '" aria-label="Use one ' + esc(x.it.name) + '">' + ICON.minus + '</button></div>';
      }).join('') + '</div></section>';
  }

  // Routine checks that are due (or due this week), and the things with a daily use that run out first.
  function srPlan(r) {
    var due = sortedChecks().filter(function (x) { return x.i.days === null || x.i.days <= 7; });
    var target = S.settings.target_days, sup = r.supplies;
    var priced = S.items.filter(function (it) { return it.price > 0; }).length;
    var checks = '', daily = '';
    if (due.length) {
      checks = '<section class="card flush sr-checks"><div class="card-head"><h2>Checks due</h2><button class="link" data-tab="plan">All checks</button></div><div class="list">' +
        due.slice(0, 4).map(checkRow).join('') + '</div>' +
        (due.length > 4 ? '<button class="li more" data-tab="plan">' + esc(due.length - 4) + ' more ' + ICON.chev + '</button>' : '') + '</section>';
    }
    if (sup.length || priced) {
      daily = '<section class="card flush sr-daily"><div class="card-head"><h2>Daily supplies</h2>' +
        (sup.length ? '<span class="small muted">' + esc(sup.length) + ' tracked</span>' : '') + '</div><div class="list">' +
        sup.slice(0, 4).map(function (x) {
          var f = target > 0 ? Math.min(1, x.days / target) : 1, st = x.days <= 0 ? 'bad' : stateOf(f);
          return '<button class="li" data-act="open" data-id="' + x.it.id + '"><span class="li-ico" aria-hidden="true">' + cat(x.it.category).icon + '</span>' +
            '<span class="li-main"><span class="li-title">' + esc(x.it.name) + '</span>' +
            '<span class="li-sub">' + esc(qu(inDate(x.it), x.it.unit)) + ' left · ' + esc(fq(x.it.per_day)) + ' a day</span>' +
            '<span class="row-meter" data-state="' + st + '" style="--pct:' + (f * 100).toFixed(1) + '%" aria-hidden="true"><i></i></span></span>' +
            pill(st, x.days <= 0 ? 'Run out' : 'Lasts ' + lastsWords(x.days)) + '</button>';
        }).join('') +
        (priced ? '<div class="li"><span class="li-ico" aria-hidden="true">💷</span><span class="li-main"><span class="li-title">Stores worth about ' + esc(money(stockValue())) + '</span>' +
          '<span class="li-sub">From the prices on ' + esc(priced) + ' of ' + esc(S.items.length) + ' items</span></span></div>' : '') +
        '</div></section>';
    }
    var half = checks && daily ? 'col-6 ' : 'col-12 ';
    return checks.replace('class="card ', 'class="' + half + 'card ') + daily.replace('class="card ', 'class="' + half + 'card ');
  }

  // The household alert level, the dashboard note and the official warnings lead the Sitrep, full width.
  // Side by side on a wall tablet or desktop, stacked on a phone.
  function srTop() {
    var res = resilienceCard();
    return levelCard().replace('class="card ', 'class="' + (res ? 'col-5 ' : 'col-12 ') + 'card ') +
      res.replace('class="card ', 'class="col-7 card ') +
      (dashNote() + warnCard(false)).replace(/class="card /g, 'class="col-12 card ');
  }
  // With live alerts on, weather, flood and fire warnings are already on the live map and in Things to watch,
  // so the Sitrep's warnings card leaves them out. The Plan tab still lists every warning.
  var WARN_ON_MAP = { metoffice: 'weather', floods: 'floods', fires: 'fires' };
  function warnOnMap(w) {
    var I = S.intel, id = WARN_ON_MAP[w.source];
    if (!id || !I || !I.enabled) return false;
    return (I.sources || []).some(function (x) { return x.id === id && x.ok; });
  }

  function renderSitrep(el) {
    var anim = !(SR_GRID && el.contains(SR_GRID));   // first draw since load or since coming back to the Sitrep
    if (!S.items.length) {
      el.innerHTML = '<div class="grid sr-grid">' + srTop() + intelBanner() + emptyCard().replace('class="card sr-first"', 'class="card col-12 sr-first"') + intelSitrep(anim) + '</div>';
      SR_GRID = el.firstChild;
      return;
    }
    var r = readiness(), hist = srHist();
    var html = '<div class="grid stretch sr-grid">' + srTop() + intelBanner() + srHero(r, hist, anim) + srNext(r) + srKpis(srCounts(), hist, anim) +
      srPlan(r) + srTimeline(anim) + srCats(anim) + intelSitrep(anim);
    var use = srUseFirst();
    var log = S.log.length ? '<section class="card sr-log"><div class="card-head"><h2>Latest orders</h2><button class="link" data-tab="hq">Full log</button></div>' +
      logHtml(S.log.slice(0, 5)) + '</section>' : '';
    var half = use && log ? 'col-6 ' : 'col-12 ';
    html += use.replace('class="card ', 'class="' + half + 'card ') + log.replace('class="card ', 'class="' + half + 'card ');
    el.innerHTML = html + '</div><p class="tagline">Don\'t panic · stay supplied</p>';
    SR_GRID = el.firstChild;
  }

  // ------------------------------------------------------------------
  // Live alerts (server: intel.py)
  // ------------------------------------------------------------------
  var LEVEL_RANK = { none: 0, info: 1, minor: 2, moderate: 3, severe: 4 };
  var LEVEL_STATE = { none: 'good', info: 'good', minor: 'warn', moderate: 'bad', severe: 'bad' };
  var LEVEL_WORD = { none: 'All clear', info: 'For info', minor: 'Be aware', moderate: 'Be prepared', severe: 'Take action' };
  var INTEL_ICON = { floods: '🌊', rivers: '🏞️', weather: '🌧️', power: '⚡', fires: '🔥', gas: '🏭', fx: '💷', markets: '📈', grid: '🔌', air: '💨', space: '☀️' };

  function safeUrl(u) { return /^https:\/\//i.test(String(u || '')) ? String(u) : ''; }

  function intelItemHtml(src, i) {
    var url = safeUrl(i.url);
    var sub = [i.area, i.time && /^\d{4}-\d\d-\d\dT/.test(i.time) ? ago(i.time) : i.time].filter(Boolean).join(' · ');
    return '<div class="li intel-item"><span class="li-ico" aria-hidden="true">' + (INTEL_ICON[src.id] || '⚠️') + '</span>' +
      '<div class="li-main"><span class="li-title">' + esc(i.title) + '</span>' +
      (sub ? '<span class="li-sub">' + esc(sub) + '</span>' : '') +
      (i.detail ? '<span class="li-sub intel-detail">' + esc(i.detail) + '</span>' : '') +
      (url ? '<a class="link small" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">Official details</a>' : '') +
      '</div>' + pill(LEVEL_STATE[i.level] || 'warn', LEVEL_WORD[i.level] || i.level) + '</div>';
  }

  // The card on the Sitrep: a map of what's happening (near you and across the UK), colour-coded summaries,
  // and anything active near you.
  var INTEL_OPEN = null;         // the summary tile whose details are showing
  var MAPI = null, MAP_VIEW = null, LEAFLET = null;
  var LEVEL_COLOUR = { severe: '#d63b30', moderate: '#ef7d1a', minor: '#f2b705', info: '#2f7fd1', none: '#2fa85a' };
  var FIRE_COLOUR = '#ff4d1a';

  function scopeOf(i) { return i.scope || 'yours'; }
  function isAlert(i) { return LEVEL_RANK[i.level] >= LEVEL_RANK.minor; }

  function trendsFor(id) {
    return ((S.intel && S.intel.trends) || []).filter(function (t) { return t.source === id; })
      .sort(function (a, b) { return LEVEL_RANK[b.level] - LEVEL_RANK[a.level]; });
  }
  function intelStatus(s) {
    if (s.ok === null || s.ok === undefined) return { level: 'info', word: 'Checking…' };
    var mine = s.items.filter(function (i) { return scopeOf(i) === 'yours' && isAlert(i); });
    var tr = trendsFor(s.id);
    if (tr.length && LEVEL_RANK[tr[0].level] >= LEVEL_RANK[mine.length ? s.level : 'none']) {
      return { level: tr[0].level, word: LEVEL_WORD[tr[0].level], trend: tr[0], more: tr.length - 1 + mine.filter(function (i) { return !i.watch; }).length };
    }
    if (mine.length) return { level: s.level, word: LEVEL_WORD[s.level], n: mine.length };
    if (s.ok === false && !s.items.length) return { level: 'info', word: 'Not reachable' };
    // Country-wide measures aren't "near you": they're either normal or not.
    if (['gas', 'grid', 'space'].indexOf(s.id) >= 0) return { level: 'none', word: 'Normal' };
    if (s.id === 'fx' || s.id === 'markets') return { level: 'none', word: 'Steady' };
    if (s.id === 'air') return { level: 'none', word: 'Good' };
    if (s.id === 'rivers') return { level: 'none', word: s.items.some(function (i) { return scopeOf(i) === 'near'; }) ? 'Normal near you' : 'All clear near you' };
    return { level: 'none', word: 'All clear near you' };
  }
  function intelTileSub(s, st) {
    if (st.trend) return st.trend.title + (st.more > 0 ? ' · +' + st.more + ' more' : '');
    if (s.id === 'gas' && s.items.length) return s.items[0].title.replace('Gas storage ', '') + (s.items[0].days_left ? ' · ~' + s.items[0].days_left + ' days' : '');
    var parts = [];
    if (s.id === 'fx' && s.items.length) {
      return s.items.slice(0, 2).map(function (i) { return i.code + ' ' + i.value.toFixed(i.value >= 20 ? 2 : 4) + ' ' + pctTxt(i.changes.w1) + ' wk'; }).join(' · ');
    }
    if (s.id === 'markets' && s.items.length) {
      return s.items.slice(0, 1).concat(s.items.filter(function (i) { return i.code === '^GSPC'; })).map(function (i) {
        return i.name.replace(/ \(.*\)/, '') + ' ' + pctTxt(i.changes.w1) + ' wk';
      }).join(' · ');
    }
    if (s.id === 'rivers') {
      var gauges = s.items.filter(function (i) { return scopeOf(i) !== 'uk'; }).length;
      var highUk = s.items.filter(function (i) { return scopeOf(i) === 'uk'; }).length;
      if (st.n) parts.push(st.n + ' of ' + gauges + ' gauges high');
      else if (gauges) parts.push(gauges + ' gauge' + (gauges === 1 ? '' : 's') + ' nearby');
      if (highUk) parts.push(highUk + ' high elsewhere');
      if (parts.length) return parts.join(' · ');
    }
    if (st.n) parts.push(st.n + ' near you');
    var near = s.items.filter(function (i) { return scopeOf(i) === 'near'; }).length;
    var uk = s.items.filter(function (i) { return scopeOf(i) === 'uk'; }).length;
    if (near) parts.push(near + ' nearby');
    if (uk) parts.push(uk + ' elsewhere in the UK');
    if (parts.length) return parts.join(' · ');
    var quiet = s.items.filter(function (i) { return i.level === 'none' || i.level === 'info'; });
    if (quiet.length && (s.id === 'air' || s.id === 'space' || s.id === 'gas')) return quiet[0].title;
    return s.checked_at ? 'checked ' + ago(s.checked_at) : 'every ' + s.refresh_minutes + ' min';
  }

  // Gas storage: the stock level over time, from the National Gas feed ([[date, TWh], ...]).
  function srGasSeries(s) {
    var g = s && s.id === 'gas' && s.items[0];
    return g && g.series && g.series.length >= 2 ? g.series : null;
  }
  // Money: the pound and the markets. A row per currency or index with its recent path and how far it has moved.
  function pctTxt(v) { return v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1) + '%'; }
  function pctCell(v, neutral) {
    var cls = v == null || neutral || Math.abs(v) < 0.05 ? '' : v > 0 ? ' up' : ' down';
    return '<span class="mn-pct' + cls + '">' + pctTxt(v) + '</span>';
  }
  function moneyRow(i, anim) {
    var neutral = i.money === 'commodity';
    var state = i.level === 'moderate' ? 'bad' : i.level === 'minor' ? 'warn' : '';
    var val = i.money === 'fx' ? i.value.toFixed(i.value >= 20 ? 2 : 4) : i.value.toLocaleString('en-GB', { maximumFractionDigits: i.value >= 1000 ? 0 : 2 });
    var url = safeUrl(i.url);
    return '<div class="mn-row"' + (state ? ' data-state="' + state + '"' : '') + '>' +
      '<div class="mn-main"><span class="mn-name">' + (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(i.name) + '</a>' : esc(i.name)) + '</span>' +
      '<span class="mn-sub">' + esc(i.money === 'fx' ? i.code + ' per £1' : (i.currency || '')) + (i.watch ? ' · ' + esc(i.watch) : '') + '</span></div>' +
      '<span class="mn-spark">' + DAChart.spark({ points: i.series.map(function (p) { return p[1]; }), height: 26, color: state || 'info', area: true, zero: false,
        title: i.name + ', last three months', noAnimate: !anim }) + '</span>' +
      '<b class="mn-val">' + esc(val) + '</b>' + pctCell(i.changes.d1, neutral) + pctCell(i.changes.w1, neutral) + pctCell(i.changes.m1, neutral) + '</div>';
  }
  function moneyList(src, anim) {
    var head = '<div class="mn-row mn-head"><span></span><span></span><span class="mn-val">Now</span><span class="mn-pct">Day</span><span class="mn-pct">Week</span><span class="mn-pct">Month</span></div>';
    var groups = src.id === 'fx' ? [['fx', 'The pound buys']] : [['index', 'Stock markets'], ['commodity', 'Commodities']];
    return groups.map(function (g) {
      var list = src.items.filter(function (i) { return i.money === g[0]; });
      if (!list.length) return '';
      return '<h3 class="intel-group">' + esc(g[1]) + '</h3><div class="mn-list">' + head + list.map(function (i) { return moneyRow(i, anim); }).join('') + '</div>';
    }).join('') + '<p class="small muted">' + (src.id === 'fx' ? 'A falling line means a weaker pound. Daily reference rates.' : 'Prices can be delayed. Updated every three hours.') + ' Context only, not financial advice.</p>';
  }
  // What a source has looked like over the last two weeks (kept by the server at every check).
  function historyCharts(src, anim) {
    var H = (S.intel && S.intel.history) || {};
    return Object.keys(H).filter(function (m) { return H[m].source === src.id && H[m].points.length >= 3; }).map(function (m) {
      var days = Math.max(1, Math.round((new Date(H[m].points[H[m].points.length - 1][0]) - new Date(H[m].points[0][0])) / 864e5));
      return '<div class="sr-gas"><div class="sr-label">' + esc(H[m].label) + ' · last ' + (days <= 1 ? 'day' : days + ' days') + '</div>' + DAChart.trend({
        series: [{ name: H[m].label, color: 'info', points: H[m].points }], height: 130, title: H[m].label, noAnimate: !anim
      }) + '</div>';
    }).join('');
  }
  // The banner at the very top of the Sitrep: trends to watch and anything active near you. Tap one for its details.
  function intelBanner() {
    var I = S.intel;
    if (!I || !I.enabled) return '';
    var rows = (I.trends || []).map(function (t) { return { src: t.source, level: t.level, title: t.title, detail: t.detail, tag: 'Trend' }; });
    I.sources.forEach(function (s) {
      if (!s.enabled) return;
      s.items.forEach(function (i) {
        if (scopeOf(i) === 'yours' && isAlert(i) && !i.watch) rows.push({ src: s.id, level: i.level, title: i.title, detail: i.detail, tag: s.name });
      });
    });
    if (!rows.length) return '';
    rows.sort(function (a, b) { return LEVEL_RANK[b.level] - LEVEL_RANK[a.level]; });
    var more = rows.length - 4;
    return '<section class="col-12 tr-strip" data-level="' + esc(rows[0].level) + '" aria-label="Things to watch">' +
      '<div class="tr-head"><span class="sr-label">Things to watch</span><span class="small muted">' + rows.length + ' now</span></div>' +
      rows.slice(0, 4).map(function (t) {
        return '<button class="tr-item" data-act="intel-jump" data-src="' + esc(t.src) + '" data-level="' + esc(t.level) + '">' +
          '<span class="tr-ico" aria-hidden="true">' + (INTEL_ICON[t.src] || '📈') + '</span>' +
          '<span class="tr-main"><b>' + esc(t.title) + '</b><span>' + esc(t.tag) + (t.detail ? ' · ' + esc(t.detail.length > 150 ? t.detail.slice(0, 150) + '…' : t.detail) : '') + '</span></span>' +
          pill(LEVEL_STATE[t.level] || 'warn', LEVEL_WORD[t.level] || 'Be aware') + '</button>';
      }).join('') +
      (more > 0 ? '<button class="link small" data-act="intel-jump" data-src="">and ' + more + ' more in Live alerts</button>' : '') + '</section>';
  }

  // River gauges near you: where the level sits between the lowest and highest it has been, with the normal range shaded.
  function riverRow(i, anim) {
    var lo = Math.min(i.low, i.value), hi = Math.max(i.max == null ? i.high : i.max, i.value, i.high);
    var span = (hi - lo) || 1;
    function pc(v) { return Math.max(0, Math.min(100, (v - lo) / span * 100)).toFixed(1); }
    var state = i.state === 'high' ? (i.level === 'moderate' ? 'bad' : 'warn') : 'good';
    var word = i.state === 'high' ? 'Above normal' : i.state === 'low' ? 'Below normal' : 'Normal';
    var arrow = i.trend === 'rising' ? ' ↑' : i.trend === 'falling' ? ' ↓' : '';
    var url = safeUrl(i.url);
    var sub = [i.area, i.time ? ago(i.time) : '', i.trend ? i.trend.charAt(0).toUpperCase() + i.trend.slice(1) : ''].filter(Boolean).join(' · ');
    return '<div class="rv-row" data-state="' + state + '">' +
      '<div class="rv-main"><span class="rv-name">' + (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(i.name) + '</a>' : esc(i.name)) + '</span>' +
      '<span class="rv-sub">' + esc(sub) + '</span></div>' +
      '<div class="rv-bar" role="img" aria-label="' + esc(i.value.toFixed(2) + ' m. Normal range ' + i.low.toFixed(2) + ' to ' + i.high.toFixed(2) + ' m.') + '">' +
        '<span class="rv-norm" style="left:' + pc(i.low) + '%;width:' + (pc(i.high) - pc(i.low)).toFixed(1) + '%"></span>' +
        '<span class="rv-dot" style="left:' + pc(i.value) + '%"></span></div>' +
      (i.series ? '<span class="rv-spark">' + DAChart.spark({ points: i.series.map(function (p) { return p[1]; }), height: 22, color: state === 'good' ? 'info' : state, zero: false,
        title: i.name + ', recent levels', unit: 'm', noAnimate: !anim }) + '</span>' : '<span class="rv-spark"></span>') +
      '<span class="rv-val"><b>' + esc(i.value.toFixed(2)) + ' m' + arrow + '</b>' + pill(state, word) + '</span></div>';
  }
  function riverList(src, anim) {
    var near = src.items.filter(function (i) { return i.river && scopeOf(i) !== 'uk'; });
    if (!near.length) return '';
    return '<h3 class="intel-group">Gauges near you <span class="muted">' + near.length + '</span></h3>' +
      '<div class="rv-list">' + near.map(function (i) { return riverRow(i, anim); }).join('') + '</div>' +
      '<p class="small muted rv-key"><i class="rv-key-norm"></i>Shaded: the normal range. The bar runs from the lowest level up to the highest on record.</p>';
  }

  // The pill on the Live alerts card: name the thing when there's only one.
  function intelHeadline(I, on) {
    if (!I.active) return 'All clear near you';
    var hit = on.filter(function (s) { return LEVEL_RANK[intelStatus(s).level] >= LEVEL_RANK.minor; });
    if (hit.length === 1) return hit[0].name + ': ' + (LEVEL_WORD[intelStatus(hit[0]).level] || '').toLowerCase();
    return I.active + ' to be aware of';
  }

  function intelSitrep(anim) {
    var I = S.intel;
    if (!I) return '';
    if (!I.enabled) {
      return '<section class="card col-12 intel-off sr-intel-off"><div class="card-head"><h2>Live alerts</h2>' +
        '<button class="link" data-act="go-hq-intel">Switch on</button></div>' +
        '<p class="small muted">A live map of floods, river levels, severe weather, power cuts and wildfires, near you and across the UK, from the official sources.</p></section>';
    }
    var on = I.sources.filter(function (s) { return s.enabled; });
    var active = [];
    on.forEach(function (s) {
      s.items.forEach(function (i) { if (scopeOf(i) === 'yours' && isAlert(i)) active.push({ s: s, i: i }); });
    });
    active.sort(function (a, b) { return LEVEL_RANK[b.i.level] - LEVEL_RANK[a.i.level]; });
    var hasMap = I.map && I.map.on;
    var html = '<section class="card col-12 intel sr-intel" data-level="' + esc(I.level) + '"><div class="card-head"><h2>Live alerts</h2>' +
      pill(LEVEL_STATE[I.level] || 'good', intelHeadline(I, on)) + '</div>' +
      '<div class="sr-intel-body' + (hasMap ? ' has-map' : '') + '">';
    if (hasMap) {
      html += '<div class="intel-map-wrap"><div id="intelMap" class="intel-map" role="region" aria-label="Map of live alerts"></div>' +
        '<div class="intel-legend" aria-hidden="true">' + ['severe', 'moderate', 'minor', 'info'].map(function (l) {
          return '<span><i style="background:' + LEVEL_COLOUR[l] + '"></i>' + esc(l === 'info' ? 'For info' : LEVEL_WORD[l]) + '</span>';
        }).join('') + '<span><i style="background:' + FIRE_COLOUR + '"></i>Heat detection</span>' +
        '<span><i class="faint"></i>Elsewhere in the UK</span></div></div>';
    }
    // Anything that needs attention comes first, worst first; the quiet ones keep their usual order.
    var tiles = on.map(function (s, n) { return { s: s, st: intelStatus(s), n: n }; });
    tiles.sort(function (a, b) {
      var ra = LEVEL_RANK[a.st.level] >= LEVEL_RANK.minor ? LEVEL_RANK[a.st.level] : 0, rb = LEVEL_RANK[b.st.level] >= LEVEL_RANK.minor ? LEVEL_RANK[b.st.level] : 0;
      return rb - ra || a.n - b.n;
    });
    html += '<div class="intel-tiles">' + tiles.map(function (x) {
      var s = x.s, st = x.st, gs = srGasSeries(s);
      if (!gs && (s.id === 'fx' || s.id === 'markets') && s.items.length && s.items[0].series) gs = s.items[0].series;
      return '<button class="intel-tile" data-act="intel-src" data-src="' + esc(s.id) + '" data-level="' + esc(st.level) + '" aria-expanded="' + (INTEL_OPEN === s.id) + '">' +
        '<span class="it-ico" aria-hidden="true">' + (INTEL_ICON[s.id] || '⚠️') + '</span>' +
        '<span class="it-name">' + esc(s.name) + '</span>' +
        '<span class="it-word">' + esc(st.word) + '</span>' +
        '<span class="it-sub">' + esc(intelTileSub(s, st)) + '</span>' +
        (gs ? '<span class="it-spark">' + DAChart.spark({ points: gs.slice(-60).map(function (p) { return p[1]; }), height: 22, color: 'info', area: true, zero: false,
          title: s.id === 'gas' ? 'Gas in storage, last ' + Math.min(60, gs.length) + ' days' : s.items[0].name + ', last three months', unit: s.id === 'gas' ? 'TWh' : '', noAnimate: !anim }) + '</span>' : '') + '</button>';
    }).join('') + '</div></div>';
    var open = INTEL_OPEN && on.filter(function (s) { return s.id === INTEL_OPEN; })[0];
    if (open) {
      var groups = [['yours', 'Near you'], ['near', 'Nearby'], ['uk', 'Elsewhere in the UK']];
      html += '<div class="intel-open"><div class="small muted">' + esc(open.attribution) +
        (open.error ? ' · <span class="ha-error">' + esc(open.error) + '</span>' : '') + '</div>';
      var gser = srGasSeries(open);
      if (gser) {
        html += '<div class="sr-gas"><div class="sr-label">Gas in storage</div>' + DAChart.trend({
          series: [{ name: 'Gas in storage', color: 'info', points: gser }], height: 160, yUnit: 'TWh', title: 'Gas in storage', noAnimate: !anim
        }) + '</div>';
      }
      trendsFor(open.id).forEach(function (t) {
        html += '<div class="callout ' + (LEVEL_STATE[t.level] === 'bad' ? 'bad' : 'warn') + ' tr-callout"><b>' + esc(t.title) + '</b><br>' + esc(t.detail) + '</div>';
      });
      var any = false;
      var hc = historyCharts(open, anim);
      if (hc) { html += hc; }
      if (open.id === 'fx' || open.id === 'markets') {
        html += moneyList(open, anim); any = true; groups = [];
      }
      if (open.id === 'rivers') {
        var rl = riverList(open, anim);
        if (rl) { html += rl; any = true; }
        groups = [['uk', 'Running high elsewhere in England']];
      }
      groups.forEach(function (g) {
        var list = open.items.filter(function (i) { return scopeOf(i) === g[0]; });
        if (!list.length) return;
        any = true;
        html += '<h3 class="intel-group">' + esc(g[1]) + ' <span class="muted">' + list.length + '</span></h3><div class="list">' +
          list.slice(0, 25).map(function (i) { return intelItemHtml(open, i); }).join('') + '</div>' +
          (list.length > 25 ? '<p class="small muted">and ' + (list.length - 25) + ' more on the map</p>' : '');
      });
      if (!any) html += '<p class="small muted">Nothing to report.</p>';
      html += (safeUrl(open.link) ? '<a class="link small" href="' + esc(safeUrl(open.link)) + '" target="_blank" rel="noopener noreferrer">Official source</a>' : '') + '</div>';
    } else if (active.length) {
      html += '<div class="list sr-intel-active">' + active.slice(0, 6).map(function (x) { return intelItemHtml(x.s, x.i); }).join('') + '</div>' +
        (active.length > 6 ? '<button class="link" data-act="go-hq-intel">See all ' + active.length + '</button>' : '');
    }
    return html + '</section>';
  }

  // Leaflet is bundled (static/vendor/leaflet); load it the first time the map is shown.
  function ensureLeaflet() {
    if (window.L) return Promise.resolve(window.L);
    if (LEAFLET) return LEAFLET;
    LEAFLET = new Promise(function (ok, fail) {
      var css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = 'vendor/leaflet/leaflet.css';
      document.head.appendChild(css);
      var js = document.createElement('script');
      js.src = 'vendor/leaflet/leaflet.js';
      js.onload = function () { ok(window.L); };
      js.onerror = function () { LEAFLET = null; fail(new Error('map library')); };
      document.head.appendChild(js);
    });
    return LEAFLET;
  }

  function popupHtml(src, i) {
    var url = safeUrl(i.url);
    var when = i.time && /^\d{4}-\d\d-\d\dT/.test(i.time) ? ago(i.time) : i.time;
    var where = scopeOf(i) === 'yours' ? 'Near you' : scopeOf(i) === 'near' ? 'Nearby' : 'Elsewhere in the UK';
    return '<div class="map-pop"><b>' + (INTEL_ICON[src.id] || '') + ' ' + esc(i.title) + '</b>' +
      '<div class="muted">' + esc(where) + (i.network ? ' · ' + esc(i.network) : '') + '</div>' +
      (i.area ? '<div>' + esc(i.area) + '</div>' : '') + (when ? '<div class="muted">' + esc(when) + '</div>' : '') +
      (i.detail ? '<p>' + esc(i.detail.length > 220 ? i.detail.slice(0, 220) + '…' : i.detail) + '</p>' : '') +
      (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">Official details</a>' : '') + '</div>';
  }

  var UK_BOUNDS = [[49.9, -8.2], [60.9, 1.8]];

  function mountIntelMap() {
    var el = document.getElementById('intelMap');
    if (!el) {
      if (MAPI) { MAP_VIEW = { c: MAPI.getCenter(), z: MAPI.getZoom() }; MAPI.remove(); MAPI = null; }
      return;
    }
    ensureLeaflet().then(function (L) {
      if (!document.body.contains(el)) return;   // redrawn while loading
      if (MAPI) { MAP_VIEW = { c: MAPI.getCenter(), z: MAPI.getZoom() }; MAPI.remove(); MAPI = null; }
      var I = S.intel, M = I.map || {};
      var map = MAPI = L.map(el, { scrollWheelZoom: false, zoomControl: true, attributionControl: true });
      if (window.ResizeObserver) {   // the card changes size (rotation, sidebar): keep the tiles filling it
        var ro = new ResizeObserver(function () { if (MAPI === map) map.invalidateSize(); });
        ro.observe(el);
        map.on('unload', function () { ro.disconnect(); });
      }
      map.setView(M.home || [52.4, -1.5], M.home ? 10 : 6);   // a starting view: circles can't measure themselves without one
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18, attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> · EA, Met Office, UKPN, NGED, NASA FIRMS'
      }).addTo(map);

      // Weather warnings cover regions: shade each region a warning covers.
      var weather = I.sources.filter(function (s) { return s.id === 'weather' && s.enabled; })[0];
      if (weather) {
        weather.items.forEach(function (i) {
          var c = LEVEL_COLOUR[i.level] || LEVEL_COLOUR.info;
          (i.regions || []).forEach(function (code) {
            var at = (M.met_centres || {})[code];
            if (!at) return;
            L.circle(at, { radius: 75000, color: c, weight: scopeOf(i) === 'yours' ? 2 : 1, fillColor: c,
              fillOpacity: scopeOf(i) === 'yours' ? 0.22 : 0.12, dashArray: '4 6' }).bindPopup(popupHtml(weather, i)).addTo(map);
          });
        });
      }
      // Points: floods, power cuts, fires. Near you: bold; elsewhere: smaller and fainter.
      I.sources.forEach(function (s) {
        if (!s.enabled || s.id === 'weather') return;
        s.items.forEach(function (i) {
          if (i.lat == null || i.lon == null) return;
          if (i.river && !isAlert(i)) return;   // normal rivers stay off the map
          var sc = scopeOf(i), c = i.fire ? FIRE_COLOUR : (LEVEL_COLOUR[i.level] || LEVEL_COLOUR.info);
          (i.rings || []).forEach(function (ring) {
            L.polygon(ring, { color: c, weight: 2, fillColor: c, fillOpacity: sc === 'uk' ? 0.15 : 0.28 }).bindPopup(popupHtml(s, i)).addTo(map);
          });
          var big = sc === 'yours' && isAlert(i);
          L.circleMarker([i.lat, i.lon], {
            radius: i.fire ? (sc === 'uk' ? 3.5 : 6) : big ? 9 : sc === 'near' ? 6 : 4.5,
            color: i.fire ? '#7a1d00' : '#fff', weight: big ? 2 : 1, fillColor: c,
            fillOpacity: sc === 'uk' ? 0.55 : 0.95, opacity: sc === 'uk' ? 0.6 : 1
          }).bindPopup(popupHtml(s, i)).addTo(map);
        });
      });

      var ring = null;
      if (M.home) {
        L.marker(M.home, { title: 'Home', keyboard: false,
          icon: L.divIcon({ className: 'map-home', html: '<span>🏠</span>', iconSize: [30, 30], iconAnchor: [15, 15] }) })
          .bindTooltip('Home').addTo(map);
        ring = L.circle(M.home, { radius: (M.radius_km || 15) * 1000, color: '#23803d', weight: 1.5, dashArray: '6 6',
          fill: true, fillOpacity: 0.04, interactive: false }).addTo(map);
      }
      function goHome() {
        if (ring) map.fitBounds(ring.getBounds(), { padding: [16, 16], maxZoom: 12 });
        else map.fitBounds(UK_BOUNDS);
      }
      // Two buttons: back to home, or the whole of the UK.
      var Views = L.Control.extend({
        options: { position: 'topright' },
        onAdd: function () {
          var box = L.DomUtil.create('div', 'leaflet-bar map-views');
          box.innerHTML = '<a href="#" role="button" data-v="home" title="Back to home" aria-label="Back to home">🏠</a>' +
            '<a href="#" role="button" data-v="uk" title="Whole of the UK" aria-label="Whole of the UK">UK</a>';
          L.DomEvent.disableClickPropagation(box);
          L.DomEvent.on(box, 'click', function (e) {
            L.DomEvent.preventDefault(e);
            var v = e.target.closest('[data-v]');
            if (!v) return;
            if (v.dataset.v === 'uk') map.fitBounds(UK_BOUNDS); else goHome();
          });
          return box;
        }
      });
      map.addControl(new Views());
      // Fit once the card has its final size (fitting a map that hasn't been laid out zooms right in).
      var saved = MAP_VIEW;
      requestAnimationFrame(function () {
        if (MAPI !== map) return;
        map.invalidateSize();
        if (saved) map.setView(saved.c, saved.z); else goHome();
      });
    }).catch(function () {
      el.innerHTML = '<p class="small muted" style="padding:16px">The map couldn\'t load. The summaries below are still live.</p>';
    });
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
  // Desktop gets the dense table; phones and tablets the two-line rows. Redrawn when the width crosses over.
  var ST_WIDE = window.matchMedia ? window.matchMedia('(min-width: 1100px)') : { matches: false };
  function stWideChanged() { if (view === 'stores' && S && S.items.length) renderStoreList(); }
  if (ST_WIDE.addEventListener) ST_WIDE.addEventListener('change', stWideChanged);
  else if (ST_WIDE.addListener) ST_WIDE.addListener(stWideChanged);
  // Category groups folded away on the desktop table, for this session.
  var ST_FOLD = {};
  try { ST_FOLD = JSON.parse(sessionStorage.getItem('da-fold') || '{}') || {}; } catch (e) { ST_FOLD = {}; }
  function stSaveFold() { try { sessionStorage.setItem('da-fold', JSON.stringify(ST_FOLD)); } catch (e) { /* ignore */ } }
  var ST_CHEV = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';

  function renderStores(el) {
    if (!S.items.length) { endSelect(); el.dataset.view = ''; el.innerHTML = emptyCard(); return; }
    if (el.dataset.view !== 'stores' || !$('#q', el)) {
      el.dataset.view = 'stores';
      el.innerHTML =
        '<div class="toolbar st-toolbar" role="search" aria-label="Find in the stores">' +
        '<div class="st-tools">' +
        '<div class="search st-search">' + ICON.search + '<input type="search" id="q" placeholder="Search the stores" autocomplete="off" enterkeyhint="search" aria-label="Search stores"></div>' +
        '<div class="select st-show"><select id="fShow" aria-label="Show">' + SHOW_OPTS.map(opt).join('') + '</select></div>' +
        '<div class="select st-sort"><select id="fSort" aria-label="Sort by">' + SORT_OPTS.map(opt).join('') + '</select></div>' +
        '<button class="btn primary st-add" data-act="new">' + ICON.plus + '<span>Add item</span></button></div>' +
        '<div class="st-chiprow"><div class="chips st-chips" id="catChips"></div><div class="st-meta" id="stMeta"></div></div>' +
        '</div>' +
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
        return '<button class="chip" data-act="cat" data-cat="' + c.id + '" aria-pressed="' + (F.cat === c.id) + '"><span aria-hidden="true">' + c.icon + '</span> ' + esc(c.short || c.label) + ' <span class="n">' + counts[c.id] + '</span></button>';
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

  // ---- Row pieces, shared by the desktop table, the phone rows and the item sheet ----
  // An amount in the item's own unit: "£12", "9 tins", "1,5 kg".
  function stAmt(q, unit) { return isMoney(unit) ? unit + fq(q) : fq(q); }
  // The stock meter: in-date stock against the target (expired stock doesn't count).
  function stStock(it, i) {
    var t = it.target_qty > 0 ? it.target_qty : 0;
    var unitWord = isMoney(it.unit) ? '' : (it.unit ? ' ' + esc(plural(it.unit, t || i.fresh)) : '');
    var cap = '<b>' + esc(stAmt(i.fresh, it.unit)) + '</b>' + (t ? ' of ' + esc(stAmt(t, it.unit)) : '') + unitWord;
    if (!t) return '<div class="st-stock"><div class="row-meter st-blank" title="No target set" aria-hidden="true"></div><span class="row-meter-cap st-cap">' + cap + '</span></div>';
    var top = Math.max(t, i.fresh), state = stateOf(i.fresh / t);
    var style = '--pct:' + (i.fresh / top * 100).toFixed(1) + '%' + (i.fresh > t ? ';--target:' + (t / top * 100).toFixed(1) + '%' : '');
    return '<div class="st-stock"><div class="row-meter" data-state="' + state + '" style="' + style + '" role="img" aria-label="' +
      esc(fq(i.fresh) + ' of ' + fq(t) + ' in date') + '"><i></i></div><span class="row-meter-cap st-cap">' + cap + '</span></div>';
  }
  // How far off a date is, in words: "12 days", "3 weeks", "Expired 2 months ago".
  function stWhen(s, short) {
    var n = daysUntil(s);
    if (n < 0) return short ? 'Expired' : 'Expired ' + span(-n) + ' ago';
    if (n === 0) return 'Today';
    return span(n);
  }
  function stExpChip(it, i, short) {
    if (!i.soonest) return '<span class="st-none" aria-label="No expiry date">–</span>';
    var cls = i.exp === 'bad' ? 'bad' : i.exp === 'warn' ? 'warn' : 'plain';
    return '<span class="badge st-exp ' + cls + '" title="' + esc((i.exp === 'bad' ? 'Expired ' : 'Best before ') + fmtDate(i.soonest)) + '">' +
      esc(stWhen(i.soonest, short)) + '</span>';
  }
  function stPlaces(it) {
    var locs = {};
    it.batches.forEach(function (b) { if (b.location && b.qty > 0) locs[b.location] = 1; });
    return Object.keys(locs).sort();
  }
  function stWhere(it) {
    var lk = stPlaces(it);
    return lk.length === 1 ? lk[0] : lk.length > 1 ? lk.length + ' places' : '';
  }
  function stNice(n) { return n >= 3 ? nf0.format(Math.round(n)) : fq(Math.round(n * 2) / 2); }
  // "about 2 a week", or '' when there's nothing to go on.
  // Days until it runs out: from the daily use you've set, or else from how fast it has been going. null if unknown.
  function stDays(it) {
    if (it.per_day > 0) return Math.floor(daysLeft(it) + 1e-9);
    var d = it.usage ? it.usage.runs_out_in_days : null;
    return d === null || d === undefined ? null : d;
  }
  function stRate(it) {
    if (it.per_day > 0) return (isMoney(it.unit) ? it.unit : '') + fq(it.per_day) + ' a day';
    var u = it.usage, pw = u && u.per_week;
    if (!(pw > 0)) return '';
    var m = isMoney(it.unit) ? it.unit : '';
    if (pw >= 0.95) return 'about ' + m + stNice(pw) + ' a week';
    var pm = pw * 30.44 / 7;
    if (pm >= 0.95) return 'about ' + m + stNice(pm) + ' a month';
    return 'now and then';
  }
  // "lasts 6 weeks", or ''.
  function stLasts(it) {
    var d = stDays(it);
    if (d === null) return '';
    if (d < 1) return 'runs out today';
    if (d >= 3650) return 'lasts years';
    return 'lasts ' + span(d);
  }
  function stUsage(it) {
    var r = stRate(it), l = stLasts(it), d = stDays(it);
    if (!r) return '';
    return esc(r) + (l ? ' · <span class="' + (d !== null && d <= 14 ? 'warn-ink' : '') + '">' + esc(l) + '</span>' : '');
  }
  function stQuick(it, i) {
    return '<button class="qbtn" data-act="use" data-id="' + it.id + '" aria-label="Use one ' + esc(it.name) + '"' + (i.none ? ' disabled' : '') + '>' + ICON.minus + '</button>' +
      '<button class="qbtn add" data-act="stock" data-id="' + it.id + '" aria-label="Add ' + esc(it.name) + '">' + ICON.plus + '</button>';
  }
  function stNameBits(it, i) {
    var b = '';
    if (i.out && it.target_qty > 0) b = '<span class="badge bad st-flag">Out</span>';
    return b;
  }

  // Phones and tablets: a two-line row. Line 1 name and expiry; line 2 the meter, where it's kept and usage.
  function rowHtml(it, i, showIcon) {
    var where = stWhere(it), use = stUsage(it);
    var sub = [where ? esc(where) : '', use].filter(Boolean).join(' · ');
    var body = (showIcon ? '<span class="row-ico" aria-hidden="true">' + cat(it.category).icon + '</span>' : '') +
      '<span class="row-text"><span class="st-l1"><span class="row-name">' + esc(it.name) + '</span>' + stNameBits(it, i) + '</span>' +
      '<span class="st-l2">' + stStock(it, i) + (i.soonest ? stExpChip(it, i, true) : '') + (sub ? '<span class="st-sub">' + sub + '</span>' : '') + '</span></span>';
    if (SEL) {   // picking items to delete: the whole row is a tick box
      var on = !!SEL[it.id];
      return '<div class="row st-row' + (on ? ' picked' : '') + (i.out ? ' is-out' : '') + '">' +
        '<button class="row-main" role="checkbox" aria-checked="' + on + '" data-act="sel-toggle" data-id="' + it.id + '">' +
        '<span class="box">' + ICON.check + '</span>' + body + '</button></div>';
    }
    return '<div class="row st-row' + (i.out ? ' is-out' : '') + '">' +
      '<button class="row-main" data-act="open" data-id="' + it.id + '">' + body + '</button>' +
      '<div class="row-ctl">' + stQuick(it, i) + '</div></div>';
  }

  // Desktop: one table row.
  function stTr(it, i, showIcon) {
    var where = stWhere(it), places = stPlaces(it);
    var name = (showIcon ? '<span class="st-ico" aria-hidden="true">' + cat(it.category).icon + '</span>' : '') +
      '<span class="st-nm">' + esc(it.name) + '</span>' + stNameBits(it, i);
    var on = SEL && !!SEL[it.id];
    var first = SEL
      ? '<button class="st-open" role="checkbox" aria-checked="' + on + '" data-act="sel-toggle" data-id="' + it.id + '"><span class="box">' + ICON.check + '</span>' + name + '</button>'
      : '<button class="st-open" data-act="open" data-id="' + it.id + '">' + name + '</button>';
    return '<tr class="is-clickable' + (on ? ' picked' : '') + (i.out ? ' is-out' : '') + '" data-act="' + (SEL ? 'sel-toggle' : 'open') + '" data-id="' + it.id + '">' +
      '<td class="t-name">' + first + '</td>' +
      '<td class="st-c-stock">' + stStock(it, i) + '</td>' +
      '<td class="st-c-exp">' + stExpChip(it, i, false) + '</td>' +
      '<td class="st-c-where"><span class="truncate"' + (places.length > 1 ? ' title="' + esc(places.join(', ')) + '"' : '') + '>' + (where ? esc(where) : '<span class="st-none">–</span>') + '</span></td>' +
      '<td class="st-c-use"><span class="truncate">' + (stUsage(it) || '<span class="st-none">–</span>') + '</span></td>' +
      '<td class="t-ctl">' + (SEL ? '' : stQuick(it, i)) + '</td></tr>';
  }
  // A group's header: name, count, and what needs doing in it (so a folded group still tells you).
  function stGroupNote(xs) {
    var exp = 0, low = 0;
    xs.forEach(function (x) { if (x.i.exp === 'bad') exp++; if (x.i.low) low++; });
    var bits = [];
    if (exp) bits.push('<span class="bad-ink">' + exp + ' expired</span>');
    if (low) bits.push('<span class="warn-ink">' + low + ' below target</span>');
    return bits.join(' · ');
  }
  function stTable(list) {
    var groups = [];
    if (F.sort === 'category') {
      list.forEach(function (x) {
        var g = groups[groups.length - 1];
        if (!g || g.cat !== x.it.category) groups.push(g = { cat: x.it.category, xs: [] });
        g.xs.push(x);
      });
    } else groups.push({ cat: null, xs: list });
    var html = '<div class="card flush st-card"><table class="table st-table"><colgroup><col class="st-w-name"><col class="st-w-stock">' +
      '<col class="st-w-exp"><col class="st-w-where"><col class="st-w-use"><col class="st-w-ctl"></colgroup>' +
      '<thead><tr><th scope="col">Item</th><th scope="col">In date</th><th scope="col">Expires</th><th scope="col">Kept</th>' +
      '<th scope="col">Usage</th><th scope="col"><span class="sr-only">Use or add</span></th></tr></thead>';
    groups.forEach(function (g) {
      var folded = g.cat && ST_FOLD[g.cat] && !F.q.trim();
      html += '<tbody>';
      if (g.cat) {
        var c = cat(g.cat), note = stGroupNote(g.xs);
        html += '<tr class="table-group"><th colspan="6" scope="colgroup"><div class="st-gh">' +
          '<button type="button" data-act="st-fold" data-cat="' + esc(g.cat) + '" aria-expanded="' + !folded + '">' + ST_CHEV +
          '<span aria-hidden="true">' + c.icon + '</span> ' + esc(c.label) + ' <span class="n">' + g.xs.length + '</span></button>' +
          (note ? '<span class="st-gnote">' + note + '</span>' : '') + '</div></th></tr>';
      }
      if (!folded) g.xs.forEach(function (x) { html += stTr(x.it, x.i, !g.cat); });
      html += '</tbody>';
    });
    return html + '</table></div>';
  }

  function stMeta(n) {
    return '<span class="result-count" aria-live="polite">' +
      (SEL ? 'Tap the items to delete' : '<b>' + n + '</b> item' + (n === 1 ? '' : 's')) + '</span>' +
      (SEL ? '<button class="link" id="selAll" data-act="sel-all"></button>'
        : '<button class="link" data-act="sel-start">' + ICON.trash + ' Select to delete</button>');
  }

  function renderStoreList() {
    var box = $('#storeList');
    if (!box) return;
    var list = filtered();
    if (SEL) Object.keys(SEL).forEach(function (k) { if (!byId(+k)) delete SEL[k]; });   // deleted on another phone
    var meta = $('#stMeta');
    if (meta) meta.innerHTML = list.length || SEL ? stMeta(list.length) : '<span class="result-count"><b>0</b> items</span>';
    var bar = SEL ? '<div class="selbar" role="region" aria-label="Delete items"><span class="selbar-n" id="selCount" aria-live="polite"></span>' +
      '<button class="btn small" data-act="sel-cancel">Cancel</button>' +
      '<button class="btn small del" id="selDelete" data-act="sel-delete"></button></div>' : '';
    if (!list.length) {
      var what = F.q.trim() ? 'Nothing matches “' + esc(F.q.trim()) + '”' + (F.cat !== 'all' || F.show !== 'all' ? ' with these filters' : '') + '.'
        : 'No items match these filters.';
      box.innerHTML = '<div class="card empty st-empty"><div class="empty-ico">' + ICON.search + '</div><h2 class="empty-title">Nothing here</h2>' +
        '<p>' + what + ' Try fewer words, or clear the filters.</p>' +
        '<div class="btn-group st-empty-acts"><button class="btn" data-act="clear-filters">Clear filters</button>' +
        (F.q.trim() ? '<button class="btn primary" data-act="st-new" data-name="' + esc(F.q.trim()) + '">' + ICON.plus + ' Add “' + esc(F.q.trim()) + '”</button>' : '') +
        '</div></div>' + bar;
      syncSel(list);
      return;
    }
    var html;
    if (ST_WIDE.matches) html = stTable(list);
    else {
      html = '<div class="card flush st-list">';
      if (F.sort === 'category') {
        var cur = null;
        list.forEach(function (x) {
          if (x.it.category !== cur) {
            cur = x.it.category;
            var n = list.filter(function (y) { return y.it.category === cur; }).length;
            html += '<div class="group-head"><span aria-hidden="true">' + cat(cur).icon + '</span> ' + esc(cat(cur).label) + ' <span class="n">' + n + '</span></div>';
          }
          html += rowHtml(x.it, x.i, false);
        });
      } else {
        list.forEach(function (x) { html += rowHtml(x.it, x.i, true); });
      }
      html += '</div>';
    }
    box.innerHTML = html + bar;
    syncSel(list);
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
  function syncSel(shown) {
    if (!SEL) return;
    $$('button[data-act="sel-toggle"]').forEach(function (b) {
      var on = !!SEL[b.dataset.id];
      b.setAttribute('aria-checked', String(on));
      var row = b.closest('tr, .row');
      if (row) row.classList.toggle('picked', on);
    });
    shown = shown || filtered();
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

  var supplyDrawn = false;   // the summary charts draw in once, not on every 30-second refresh

  function runsOut(it) {
    var d = stDays(it);
    return typeof d === 'number' && isFinite(d) ? d : null;
  }
  // What to get first: out of stock essentials (in category order, so food and water lead), then whatever
  // runs out soonest at the recent rate of use, then whatever is furthest below target.
  function supplyUrgent(short) {
    function rank(x) { return x.i.out ? 0 : runsOut(x.it) !== null ? 1 : 2; }
    return short.slice().sort(function (a, b) {
      var ra = rank(a), rb = rank(b);
      if (ra !== rb) return ra - rb;
      if (ra === 1 && runsOut(a.it) !== runsOut(b.it)) return runsOut(a.it) - runsOut(b.it);
      if (ra === 2) {
        var fa = a.i.fresh / a.it.target_qty, fb = b.i.fresh / b.it.target_qty;
        if (fa !== fb) return fa - fb;
      }
      return catIndex(a.it.category) - catIndex(b.it.category) || byName(a.it, b.it);
    });
  }
  function needWords(x) {
    return 'Get <b>' + esc(qu(x.i.short, x.it.unit)) + '</b> · have ' + esc(fq(x.i.fresh)) + ' of ' + esc(fq(x.it.target_qty)) +
      (x.it.price > 0 ? ' · <span class="nowrap">' + esc(money(x.i.short * x.it.price)) + '</span>' : '') +
      (x.i.expired > 0 ? ' · <span class="bad-ink nowrap">' + esc(fq(x.i.expired)) + ' expired</span>' : '');
  }
  function supplyUrgentRow(x) {
    var ro = runsOut(x.it);
    var why = x.i.out ? pill('bad', 'Out of stock')
      : ro !== null ? pill('warn', ro < 1 ? 'Runs out today' : 'Runs out in ' + span(Math.round(ro)))
      : '<span class="pill plain">' + esc(Math.round(x.i.fresh / x.it.target_qty * 100)) + '% of target</span>';
    return '<button class="li su-urgent" data-act="open" data-id="' + x.it.id + '">' +
      '<span class="li-ico" aria-hidden="true">' + cat(x.it.category).icon + '</span>' +
      '<span class="li-main"><span class="li-title">' + esc(x.it.name) + '</span>' +
      '<span class="li-sub">Get ' + esc(qu(x.i.short, x.it.unit)) + '</span></span>' + why + '</button>';
  }

  function supplySummary(short, extras, anim) {
    var targeted = S.items.filter(function (it) { return it.target_qty > 0; });
    var met = targeted.length - short.length;
    var ticked = extras.filter(function (s) { return s.done; }).length;
    var todo = extras.length - ticked;
    var ha = S.server.ha && S.server.ha.todo ? S.server.ha : null;
    var frac = targeted.length ? met / targeted.length : 1;
    var cost = supplyCost(short);

    var html = '<section class="card sr-summary"><div class="card-kicker">Supply run</div>' +
      '<div class="su-head">' +
      (targeted.length ? '<div class="su-ring">' + DAChart.ring({
        value: met, max: targeted.length, size: 112, thickness: 11, state: stateOf(frac),
        label: Math.round(frac * 100) + '%', sub: 'at target', title: 'Items at target', noAnimate: !anim
      }) + '</div>' : '') +
      '<div class="su-counts"><p class="su-big"><b class="num">' + esc(short.length + todo) + '</b> to get</p>' +
      '<p class="small muted">' + esc(short.length) + ' below target · ' + esc(todo) + ' extra' + (todo === 1 ? '' : 's') +
      (ticked ? ' · ' + esc(ticked) + ' ticked' : '') + '</p>' +
      (targeted.length ? '<p class="small muted">' + esc(met) + ' of ' + esc(targeted.length) + ' items at target</p>' : '') +
      (cost.priced ? '<p class="small muted">About <b>' + esc(money(cost.sum)) + '</b>' + (cost.priced < short.length ? ' for the ' + esc(cost.priced) + ' with a price' : '') + '</p>' : '') +
      '</div></div>' +
      '<p class="small muted su-hint">Back from the shops? Tap <b>Got it</b> to put things in the stores.' +
      (ha ? ' The list is also on your Home Assistant list <b>' + esc(ha.todo_name) + '</b>.' : '') + '</p>' +
      '<div class="btn-row"><button class="btn" data-act="copy-list">' + ICON.copy + ' Copy list</button>' +
      '<button class="btn" data-act="print-list">' + ICON.print + ' Print</button></div></section>';

    if (short.length) {
      html += '<section class="card su-urgent-card"><div class="card-head"><h2>Most urgent</h2></div><div class="list">' +
        supplyUrgent(short).slice(0, 5).map(supplyUrgentRow).join('') + '</div></section>';

      var cats = CATS.map(function (c) {
        var tg = targeted.filter(function (it) { return it.category === c.id; });
        var need = short.filter(function (x) { return x.it.category === c.id; }).length;
        return { c: c, tg: tg.length, need: need };
      }).filter(function (r) { return r.need > 0; });
      html += '<section class="card su-cats"><div class="card-head"><h2>By category</h2><span class="small muted">at target</span></div>' +
        DAChart.bars({
          title: 'Items at target by category', noAnimate: !anim,
          items: cats.map(function (r) {
            var f = r.tg ? (r.tg - r.need) / r.tg : 0;
            return { label: r.c.label, value: r.tg - r.need, max: r.tg, state: stateOf(f), valueText: r.need + ' to get', key: r.c.id };
          })
        }) + '</section>';
    }
    return html;
  }

  function supplyRow(x, ticked) {
    var f = x.it.target_qty > 0 ? Math.min(1, x.i.fresh / x.it.target_qty) : 0;
    return '<div class="li su-row"><button class="li-main" data-act="open" data-id="' + x.it.id + '">' +
      '<span class="li-title">' + esc(x.it.name) + '</span>' +
      '<span class="need">' + needWords(x) + '</span>' +
      '<span class="row-meter" data-state="' + stateOf(f) + '" style="--pct:' + (f * 100).toFixed(1) + '%" aria-hidden="true"><i></i></span>' +
      (ticked.indexOf(x.it.id) >= 0 ? '<span class="badge ok ha-tick">' + ICON.check + ' Ticked off in Home Assistant</span>' : '') + '</button>' +
      '<button class="btn primary small su-got" data-act="stock" data-id="' + x.it.id + '" data-qty="' + esc(x.i.short) + '" aria-label="Got it: put ' + esc(x.it.name) + ' in the stores">' +
      ICON.check + '<span>Got it</span></button></div>';
  }

  function supplyExtras(extras) {
    var done = extras.filter(function (s) { return s.done; }).length;
    var html = '<section class="card su-extras"><div class="card-head"><h2>Also get</h2>' +
      (done ? '<button class="link" data-act="shop-clear">Clear ticked (' + esc(done) + ')</button>' : '<span class="small muted">' + esc(extras.length) + '</span>') + '</div>' +
      '<form class="add-row" id="shopForm" autocomplete="off"><input type="text" name="text" placeholder="e.g. Spare fuses" maxlength="200" enterkeyhint="done" aria-label="Add to the list">' +
      '<button class="btn primary" type="submit">' + ICON.plus + ' Add</button></form>';
    if (!extras.length) {
      html += '<p class="small muted su-extras-empty">Anything else for the trip that isn\'t in the stores: fuses, a spare lighter, the dog\'s biscuits.</p>';
    } else {
      html += '<div class="list">';
      extras.forEach(function (s) {
        html += '<div class="li su-extra"><button class="check" role="checkbox" aria-checked="' + (s.done ? 'true' : 'false') + '" data-act="shop-toggle" data-id="' + s.id + '">' +
          '<span class="box">' + ICON.check + '</span><span class="li-title">' + esc(s.text) + '</span></button>' +
          (s.done ? '' : '<button class="btn small" data-act="shop-got" data-id="' + s.id + '" aria-label="Got it: add ' + esc(s.text) + ' to the stores">Got it</button>') +
          '<button class="icon-btn" data-act="shop-edit" data-id="' + s.id + '" aria-label="Change ' + esc(s.text) + '">' + ICON.edit + '</button>' +
          '<button class="icon-btn" data-act="shop-del" data-id="' + s.id + '" aria-label="Remove ' + esc(s.text) + '">' + ICON.close + '</button></div>';
      });
      html += '</div>';
    }
    return html + '</section>';
  }

  function renderSupply(el) {
    var short = shortList(), extras = S.shopping;
    var todo = extras.filter(function (s) { return !s.done; }).length;
    var ha = S.server.ha && S.server.ha.todo ? S.server.ha : null;
    var ticked = ha ? ha.ticked || [] : [];
    var anim = !supplyDrawn;
    supplyDrawn = true;

    var list;
    if (!short.length && !todo) {
      list = '<section class="card empty sr-empty"><div class="empty-ico good">' + ICON.check + '</div>' +
        '<h2 class="empty-title">' + (S.items.length ? 'All squared away' : 'Nothing on the list yet') + '</h2>' +
        (S.items.length
          ? '<p>Nothing is below target and there are no extras to get. Add anything else you need below.</p><button class="btn primary" data-tab="stores">Look over the stores</button>'
          : '<p>The supply run fills itself from the stores: anything below its target turns up here. Start with the starter list.</p><button class="btn primary" data-act="seed">Load starter list</button>') +
        '</section>';
    } else if (!short.length) {
      list = '<section class="card su-allmet"><p class="small muted" style="margin:0">' + ICON.check + ' Nothing in the stores is below target. Just the extras below.</p></section>';
    } else {
      list = '<section class="card flush su-list"><div class="card-head"><h2>Below target</h2><span class="small muted">' + esc(short.length) + ' item' + (short.length === 1 ? '' : 's') + '</span></div>';
      var cur = null;
      short.forEach(function (x) {
        if (x.it.category !== cur) {
          cur = x.it.category;
          var n = short.filter(function (y) { return y.it.category === cur; }).length;
          list += '<div class="group-head"><span aria-hidden="true">' + cat(cur).icon + '</span> ' + esc(cat(cur).label) + ' <span class="n">' + n + '</span></div>';
        }
        list += supplyRow(x, ticked);
      });
      list += '</section>';
    }

    el.innerHTML = '<div class="grid su-grid">' +
      '<div class="col-4 stack su-side">' + supplySummary(short, extras, anim) + '</div>' +
      '<div class="col-8 stack su-main">' + list + supplyExtras(extras) + '</div></div>';
  }

  function supplyText() {
    var lines = ['DADS ARMY - Supply run, ' + new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }), ''];
    var short = shortList();
    if (short.length) {
      lines.push('Below target:');
      short.forEach(function (x) {
        lines.push('- ' + x.it.name + ': ' + qu(x.i.short, x.it.unit) + (x.i.expired > 0 ? ' (replace ' + fq(x.i.expired) + ' expired)' : ''));
      });
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
    el.innerHTML = warnCard(true) + '<div class="pl-grid">' + html + '</section>' + planCard() + '</div>';
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
      return full || !(p[0].source === 'govalerts' && p[0].severity < 2) && !warnOnMap(p[0]);
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
  var COUNTED = { adults: 1, children: 1, pets: 1 };
  function stepperHtml(name, value, label, step, isSetting) {
    step = step || 1;
    var lc = label.toLowerCase();
    var less = COUNTED[name] ? 'Fewer ' + lc : 'Less (' + lc + ')', more = COUNTED[name] ? 'More ' + lc : 'More (' + lc + ')';
    // A text box rather than type=number, so "1,5" works as well as "1.5".
    return '<div class="stepper"><button type="button" data-step="-' + step + '" aria-label="' + esc(less) + '">' + ICON.minus + '</button>' +
      '<input type="text" ' + (isSetting ? 'data-setting="' + name + '" id="set-' + name + '"' : 'name="' + name + '"') +
      ' value="' + esc(value) + '" inputmode="decimal" autocomplete="off" aria-label="' + esc(label) + '">' +
      '<button type="button" data-step="' + step + '" aria-label="' + esc(more) + '">' + ICON.plus + '</button></div>';
  }
  function setRow(key, label, hint, value, step) {
    return '<div class="set-row"><label for="set-' + key + '">' + esc(label) + (hint ? '<span class="hint">' + esc(hint) + '</span>' : '') + '</label>' +
      stepperHtml(key, value, label, step, true) + '</div>';
  }

  // What the household needs a day, and what the target adds up to, against what's in the stores.
  function needsHtml() {
    var r = readiness(), target = S.settings.target_days;
    var kcalT = r.kcalDay * target, waterT = r.waterDay * target;
    var html = '<div class="hq-needs-stats">' +
      '<div class="stat plain"><span class="stat-label">Food a day</span><span class="stat-val">' + esc(nf0.format(r.kcalDay)) + '<span class="stat-unit"> kcal</span></span></div>' +
      '<div class="stat plain"><span class="stat-label">Water a day</span><span class="stat-val">' + esc(fq(r.waterDay)) + '<span class="stat-unit"> litres</span></span></div>' +
      '</div>' +
      '<p class="hq-needs-total">For <b>' + esc(daysWords(target)) + '</b> that\'s <b class="nowrap">' + esc(nf0.format(kcalT)) + ' kcal</b> and <b class="nowrap">' +
      esc(nf0.format(waterT)) + ' litres</b> of water.</p>';
    if (kcalT > 0 || waterT > 0) {
      html += DAChart.bars({
        title: 'In the stores against the target', noAnimate: true,
        items: [
          { label: 'Food in date', value: Math.round(r.kcal), max: Math.round(kcalT), state: stateOf(kcalT > 0 ? r.kcal / kcalT : 0),
            valueText: fmtDays(r.foodDays) + ' of ' + target + ' days' },
          { label: 'Water in date', value: Math.round(r.litres), max: Math.round(waterT), state: stateOf(waterT > 0 ? r.litres / waterT : 0),
            valueText: fmtDays(r.waterDays) + ' of ' + target + ' days' }
        ]
      });
    }
    if (scalingCount()) html += '<p class="small muted hq-needs-note">Starter list targets that you haven\'t changed keep up with this.</p>';
    return html;
  }
  function scalingCount() { return S.items.filter(function (it) { return it.target_rule; }).length; }

  function daysWords(d) {
    d = +d;
    if (d === 365) return '1 year';
    if (d === 730) return '2 years';
    if (d === 7) return '1 week';
    return fq(d) + (d === 1 ? ' day' : ' days');
  }

  // Sliders for a number of days. The track is a list of sensible stops (so dragging lands on round numbers and
  // the arrow keys take useful steps); anything else is typed into the box beside it.
  var SLIDERS = {
    target_days: { label: 'Readiness target', stops: [1, 2, 3, 4, 5, 7, 10, 14, 21, 30, 45, 60, 90, 120, 180, 270, 365] },
    warn_days: { label: 'Expiry warning', stops: [1, 3, 7, 10, 14, 21, 30, 45, 60, 90, 120, 180, 270, 365] }
  };
  function sliderIndex(key, v) {
    var stops = SLIDERS[key].stops, best = 0;
    for (var i = 0; i < stops.length; i++) {
      if (Math.abs(Math.log(stops[i] / v)) < Math.abs(Math.log(stops[best] / v))) best = i;
    }
    return best;
  }
  function sliderHtml(key, value) {
    var sl = SLIDERS[key], i = sliderIndex(key, value), p = i / (sl.stops.length - 1);
    return '<div class="slider hq-slider" style="--p:' + p.toFixed(3) + '">' +
      '<input type="range" id="rng-' + key + '" data-slider="' + key + '" min="0" max="' + (sl.stops.length - 1) + '" step="1" value="' + i + '"' +
      ' aria-label="' + esc(sl.label) + '" aria-valuetext="' + esc(daysWords(value)) + '">' +
      '<output class="slider-val" for="rng-' + key + '">' + esc(daysWords(value)) + '</output></div>' +
      '<div class="slider-scale" aria-hidden="true"><span>' + esc(daysWords(sl.stops[0])) + '</span><span>' + esc(daysWords(sl.stops[sl.stops.length - 1])) + '</span></div>';
  }
  // Show a value on a slider (bubble, fill), and on the preset chips and the box that go with it.
  function syncDays(key, v, except) {
    if (!SLIDERS[key] || !(v > 0)) return;
    var r = $('#rng-' + key);
    if (r && r !== except) r.value = sliderIndex(key, v);
    if (r) {
      r.parentNode.style.setProperty('--p', (r.value / (SLIDERS[key].stops.length - 1)).toFixed(3));
      r.setAttribute('aria-valuetext', daysWords(v));
      var out = r.parentNode.querySelector('output');
      if (out) out.textContent = daysWords(v);
    }
    $$('[data-setting="' + key + '"]').forEach(function (i) { if (i !== except && i !== document.activeElement) i.value = v; });
    $$('[data-act="set"][data-key="' + key + '"]').forEach(function (b) { b.setAttribute('aria-pressed', String(+b.dataset.val === v)); });
  }
  function sliderMoved(t) {
    var key = t.dataset.slider, v = SLIDERS[key].stops[+t.value];
    syncDays(key, v, t);
    return v;
  }
  function sliderSave(t) { queueSetting(t.dataset.slider, sliderMoved(t)); }
  // Live feedback while dragging or typing; saving happens in the change handler (sliderSave, queueSetting).
  function hqLive(e) {
    var t = e.target;
    if (!t || !t.dataset || view !== 'hq') return;
    if (t.dataset.slider) { sliderMoved(t); return; }
    if (SLIDERS[t.dataset.setting]) { var v = parseQty(t.value); if (v > 0) syncDays(t.dataset.setting, v, t); }
  }
  document.addEventListener('input', hqLive);
  document.addEventListener('change', hqLive);
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-act="set"]');
    if (b && view === 'hq' && SLIDERS[b.dataset.key]) syncDays(b.dataset.key, +b.dataset.val);
  });

  // HQ was saved while a field has focus: update what's shown around it without redrawing.
  function updateHQ() {
    if (view !== 'hq') return;
    var st = S.settings, a = document.activeElement;
    var needs = $('#hqNeeds');
    if (needs) needs.innerHTML = needsHtml();
    $$('[data-setting]').forEach(function (i) { if (i !== a && st[i.dataset.setting] !== undefined) i.value = st[i.dataset.setting]; });
    $$('[data-catwarn]').forEach(function (i) { if (i !== a) i.value = (st.category_warn_days || {})[i.dataset.catwarn] || ''; });
    $$('[data-catwarn]').forEach(function (i) { i.placeholder = st.warn_days; });
    $$('[data-act="set"]').forEach(function (b) { b.setAttribute('aria-pressed', String(st[b.dataset.key] === +b.dataset.val)); });
    Object.keys(SLIDERS).forEach(function (k) {
      var r = $('#rng-' + k);
      if (r && r !== a) syncDays(k, st[k]);
    });
  }

  // Sections. Desktop and tablet show one at a time beside the list; phones stack them all and the chips jump.
  var HQ_SEC = 'household';
  var HQ_ICON = {
    household: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11l8-7 8 7M6 9.5V20h12V9.5M10 20v-6h4v6"/></svg>',
    targets: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 12h.01"/></svg>',
    alerts: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5h4"/></svg>',
    backups: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4" width="17" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/></svg>',
    ha: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 11.5L12 4l8.5 7.5M6 10v10h12V10"/><circle cx="12" cy="14" r="2"/></svg>',
    appearance: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 0 0 16z" style="fill:currentColor"/></svg>',
    activity: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l3-7 4 14 3-7h4"/></svg>'
  };
  function hqSections() {
    var s = [['household', 'Household'], ['targets', 'Targets and warnings'], ['alerts', 'Warnings and alerts'], ['backups', 'Backups']];
    if (S.server.ha) s.push(['ha', 'Home Assistant']);
    s.push(['appearance', 'Appearance'], ['activity', 'Activity']);
    return s;
  }
  function hqPhone() { return window.matchMedia ? window.matchMedia('(max-width: 699px)').matches : window.innerWidth < 700; }
  function hqShow(sec, jump) {
    if (!$('#hq-' + sec)) sec = 'household';
    HQ_SEC = sec;
    $$('.hq-sec').forEach(function (s) { s.classList.toggle('is-on', s.dataset.sec === sec); });
    $$('[data-act="hq-sec"]').forEach(function (b) { b.setAttribute('aria-current', String(b.dataset.sec === sec)); });
    if (!jump) return;
    var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    var nav = $('#hq-nav-' + sec);
    if (nav && nav.parentNode.scrollTo) nav.parentNode.scrollTo({ left: nav.offsetLeft - nav.parentNode.offsetLeft - 16, behavior: calm });
    if (hqPhone()) { var el = $('#hq-' + sec); if (el) el.scrollIntoView({ block: 'start', behavior: calm }); }
    else window.scrollTo(0, 0);
  }
  function hqSec(id, title, sub, body) {
    return '<section class="hq-sec' + (id === HQ_SEC ? ' is-on' : '') + '" id="hq-' + id + '" data-sec="' + id + '" aria-labelledby="hq-h-' + id + '">' +
      '<header class="hq-sec-head"><h2 class="hq-sec-title" id="hq-h-' + id + '">' + esc(title) + '</h2>' +
      (sub ? '<p class="hq-sec-sub">' + sub + '</p>' : '') + '</header>' + body + '</section>';
  }

  function hqHousehold() {
    var st = S.settings;
    return '<div class="hq-two">' +
      '<section class="card"><div class="card-head"><h2>People</h2></div>' +
      setRow('adults', 'Adults', '', st.adults, 1) +
      setRow('children', 'Children', '', st.children, 1) +
      setRow('kcal_adult', 'Calories per adult', 'kcal a day', st.kcal_adult, 100) +
      setRow('kcal_child', 'Calories per child', 'kcal a day', st.kcal_child, 100) +
      setRow('water_per_person', 'Water per person', 'litres a day (drinking & cooking)', st.water_per_person, 0.5) +
      '<h3 class="hq-sub">Pets</h3>' +
      setRow('pets', 'Pets', '', st.pets || 0, 1) +
      setRow('kcal_per_pet', 'Calories per pet', 'kcal a day, if their food is in Food', st.kcal_per_pet || 0, 50) +
      setRow('water_per_pet', 'Water per pet', 'litres a day', st.water_per_pet || 0, 0.5) + '</section>' +
      '<div class="stack"><section class="card hq-needs"><div class="card-head"><h2>Daily needs</h2></div><div id="hqNeeds">' + needsHtml() + '</div></section>' +
      '<section class="card"><div class="card-head"><h2>Starter list</h2></div>' +
      '<p class="small muted">Adds about 95 suggested essentials at zero stock, with targets sized for your household and a goal of ' + esc(daysWords(st.target_days)) + '. ' +
      'Those targets keep up when your household or goal changes, until you set one yourself. ' +
      'Anything you already have is skipped. To clear out what you don\'t need, use <b>Select to delete</b> in Stores.</p>' +
      '<button class="btn block" data-act="seed">Load starter list</button></section></div></div>';
  }

  function hqTargets() {
    var st = S.settings, cw = st.category_warn_days || {};
    var chips = function (key, list) {
      return '<div class="chips hq-presets" role="group" aria-label="Quick choices">' + list.map(function (d) {
        return '<button class="chip" data-act="set" data-key="' + key + '" data-val="' + d + '" aria-pressed="' + (st[key] === d) + '">' + esc(daysWords(d)) + '</button>';
      }).join('') + '</div>';
    };
    var overrides = Object.keys(cw).filter(function (k) { return cw[k]; }).length;
    return '<section class="card"><div class="card-head"><h2>Readiness target</h2></div>' +
      '<p class="small muted">How long should your stores last? The Sitrep measures everything against this.</p>' +
      sliderHtml('target_days', st.target_days) + chips('target_days', [3, 7, 14, 30, 90, 180, 365]) +
      setRow('target_days', 'Exactly', 'days, up to 10 years', st.target_days, 1) + '</section>' +
      '<section class="card"><div class="card-head"><h2>Expiry warning</h2></div>' +
      '<p class="small muted">Flag stock this long before its best-before date, so there\'s time to use it up.</p>' +
      sliderHtml('warn_days', st.warn_days) + chips('warn_days', [7, 14, 30, 60, 90]) +
      setRow('warn_days', 'Exactly', 'days, up to a year', st.warn_days, 1) + '</section>' +
      '<section class="card"><div class="card-head"><h2>By category</h2>' + (overrides ? '<span class="small muted">' + overrides + ' set</span>' : '') + '</div>' +
      '<p class="small muted">Leave a box empty to use the warning above. Handy for medicines or batteries you want to know about sooner.</p>' +
      '<div class="hq-catwarn">' + CATS.map(function (c) {
        return '<label class="hq-cw' + (cw[c.id] ? ' is-set' : '') + '"><span class="hq-cw-name"><span aria-hidden="true">' + c.icon + '</span> ' + esc(c.short || c.label) + '</span>' +
          '<span class="hq-cw-box"><input type="text" inputmode="numeric" autocomplete="off" data-catwarn="' + c.id + '" value="' + esc(cw[c.id] || '') + '" placeholder="' + esc(st.warn_days) + '" aria-label="' + esc(c.label) + ': days before best-before to warn"><span aria-hidden="true">days</span></span></label>';
      }).join('') + '</div></section>';
  }

  // One on/off row: title, a line of explanation, and a switch.
  function hqToggle(key, on, title, hint, extra) {
    return '<label class="hq-toggle" for="intel-' + key + '"><span class="hq-toggle-text"><span class="hq-toggle-title">' + title + '</span>' +
      (hint ? '<span class="hq-toggle-hint">' + hint + '</span>' : '') + '</span>' + (extra || '') +
      '<span class="switch"><input type="checkbox" id="intel-' + key + '" data-intel="' + esc(key) + '"' + (on ? ' checked' : '') + '></span></label>';
  }
  function intelField(key, label, control) {
    return '<div class="field"><label class="field-label" for="intel-' + key + '">' + esc(label) + '</label>' + control + '</div>';
  }

  // The live alerts section: where you are, what to show, and how each source is doing.
  function intelHQ() {
    var I = S.intel;
    if (!I) return '<section class="card"><p class="small muted" style="margin:0">Live alerts aren\'t available on this copy of Dads Army.</p></section>';
    var c = I.settings;
    var html = '<section class="card" id="intelCard">' +
      hqToggle('intel_enabled', c.intel_enabled, 'Check live alerts', 'Flood, weather, power cut and other warnings from the official feeds.') +
      '<p class="callout info hq-privacy">Dads Army checks the official feeds itself. Each feed is a national list filtered here, ' +
      'so nothing about where you live is sent to them. Your county, region and postcode districts decide what counts as “near you”.</p>' +
      (c.intel_enabled ? '' : '<p class="callout warn">Live alerts are off. Nothing is checked until you turn them on.</p>') + '</section>';

    html += '<section class="card"><div class="card-head"><h2>Where you are</h2></div><div class="intel-fields hq-fields">' +
      intelField('intel_county', 'County (flood warnings near you)',
        '<input type="text" id="intel-intel_county" autocomplete="off" data-intel="intel_county" value="' + esc(c.intel_county) + '" placeholder="e.g. Cambridgeshire">') +
      intelField('intel_met_region', 'Met Office region',
        '<div class="select"><select id="intel-intel_met_region" data-intel="intel_met_region"><option value="">Choose…</option>' +
        Object.keys(I.met_regions).map(function (k) {
          return '<option value="' + esc(k) + '"' + (c.intel_met_region === k ? ' selected' : '') + '>' + esc(I.met_regions[k]) + '</option>';
        }).join('') + '</select></div>') +
      intelField('intel_postcodes', 'Postcode districts (power cuts near you)',
        '<input type="text" id="intel-intel_postcodes" autocomplete="off" autocapitalize="characters" data-intel="intel_postcodes" value="' + esc(c.intel_postcodes) + '" placeholder="e.g. AB12 AB3">') +
      intelField('intel_air_region', 'Air quality region',
        '<div class="select"><select id="intel-intel_air_region" data-intel="intel_air_region"><option value="">Choose…</option>' +
        I.air_regions.map(function (r) {
          return '<option' + (c.intel_air_region === r ? ' selected' : '') + '>' + esc(r) + '</option>';
        }).join('') + '</select></div>') +
      intelField('intel_map_postcode', 'Centre the map on (postcode)',
        '<input type="text" id="intel-intel_map_postcode" autocomplete="postal-code" autocapitalize="characters" data-intel="intel_map_postcode" value="' + esc(c.intel_map_postcode) + '" placeholder="Home Assistant\'s home">') +
      intelField('intel_radius_km', '“Near you” distance',
        '<div class="select"><select id="intel-intel_radius_km" data-intel="intel_radius_km">' +
        [5, 10, 15, 25, 40].map(function (k) {
          return '<option value="' + k + '"' + (+c.intel_radius_km === k ? ' selected' : '') + '>' + k + ' km</option>';
        }).join('') + '</select></div>') +
      '</div><p class="small muted hq-foot">A map postcode is looked up once at postcodes.io when you save it' +
      (I.map && I.map.home_from ? '; the map is centred on ' + esc(I.map.home_from === 'postcode' ? 'your postcode' : 'Home Assistant\'s home') : '') + '.</p></section>';

    html += '<section class="card"><div class="card-head"><h2>What to show</h2></div>' +
      hqToggle('intel_map', c.intel_map, 'Map on the Sitrep', 'Map tiles come from OpenStreetMap.') +
      hqToggle('intel_uk', c.intel_uk, 'Across the UK', 'Show alerts elsewhere on the map, for context.') +
      hqToggle('intel_trends', c.intel_trends, 'Watch for trends', 'Flag a worrying direction of travel: rivers rising, power cuts or flood warnings climbing, gas emptying faster, sharp moves in the pound or markets.') +
      '<p class="small muted hq-foot">Only alerts near you raise the alert level and the Home Assistant sensors; the rest are on the map for context.</p></section>';

    html += '<section class="card hq-sources"><div class="card-head"><h2>Sources</h2>' +
      '<button class="btn small" data-act="intel-refresh"' + (c.intel_enabled ? '' : ' disabled') + '>Check now</button></div>' +
      I.sources.map(function (s) {
        var key = 'intel_' + s.id;
        var status = !s.enabled ? '<span class="pill plain">Off</span>' : s.ok === null || s.ok === undefined ? pill('warn', 'Not checked yet')
          : s.ok ? pill(LEVEL_STATE[s.level] || 'good', s.items.some(function (i) { return LEVEL_RANK[i.level] >= LEVEL_RANK.minor; }) ? LEVEL_WORD[s.level] : 'OK')
          : pill('bad', 'Failing');
        var sub = (s.checked_at ? 'Checked ' + esc(ago(s.checked_at)) + ' · ' : '') + 'every ' + esc(s.refresh_minutes) + ' min';
        var alerts = s.enabled ? s.items.filter(function (i) { return LEVEL_RANK[i.level] >= LEVEL_RANK.minor; }) : [];
        return '<div class="hq-src">' +
          hqToggle(key, c[key], '<span aria-hidden="true">' + (INTEL_ICON[s.id] || '') + '</span> ' + esc(s.name),
            sub + '<span class="hq-attr">' + esc(s.attribution) + '</span>', '<span class="hq-src-status">' + status + '</span>') +
          (s.error ? '<p class="small ha-error">' + esc(s.error) + '</p>' : '') +
          (alerts.length ? '<div class="list hq-src-items">' + alerts.map(function (i) { return intelItemHtml(s, i); }).join('') + '</div>' : '') +
          '</div>';
      }).join('') + '</section>';

    html += '<p class="callout hq-safety">These feeds help you get ready; they don\'t replace official warnings. In an emergency, call 999.</p>';
    return html;
  }

  function hqBackups() {
    return '<div class="hq-two">' +
      '<section class="card"><div class="card-head"><h2>Hard copy</h2></div>' +
      '<p class="small muted">A printed list to keep with the stores, with a box to tick for each batch.</p>' +
      '<div class="btn-stack"><button class="btn block" data-act="print">' + ICON.print + ' Print full inventory</button>' +
      '<button class="btn block" data-act="print-plan">' + ICON.print + ' Print emergency plan &amp; checks</button></div></section>' +
      '<section class="card"><div class="card-head"><h2>Take a copy</h2></div>' +
      '<p class="small muted">Keep a backup somewhere other than the Pi: a laptop, a USB stick, your email.</p>' +
      '<div class="btn-stack"><a class="btn block" href="api/backup.json" download>' + ICON.download + ' Download backup</a>' +
      '<a class="btn block" href="api/export.csv" download>' + ICON.download + ' Export spreadsheet (CSV)</a></div></section></div>' +
      '<section class="card"><div class="card-head"><h2>Restore</h2></div>' +
      '<div class="hq-backup-stat"><span class="stat plain"><span class="stat-label">Last automatic copy</span><span class="stat-val">' +
      esc(S.server.last_backup ? ago(S.server.last_backup) : 'Not yet') + '</span></span>' +
      '<p class="small muted">Dads Army saves its own copy every day.</p></div>' +
      '<p class="callout warn">Restoring replaces everything in the stores. Dads Army keeps a copy of what\'s there now first, just in case.</p>' +
      '<div class="btn-group hq-restore"><button class="btn" data-act="restore">' + ICON.upload + ' Restore from a file…</button>' +
      '<button class="btn" data-act="backups">' + ICON.upload + ' Restore an automatic copy…</button></div></section>';
  }

  // Only shown when Dads Army runs as a Home Assistant app.
  function haCard() {
    var ha = S.server.ha;
    if (!ha) return '';
    var html = '<section class="card"><div class="card-head"><h2>Dashboard</h2></div>' + dashPart(ha) + '</section>' +
      '<section class="card"><div class="card-head"><h2>Today\'s checklist</h2></div>' + checksPart(ha) + '</section>' +
      '<section class="card"><div class="card-head"><h2>Supply run list</h2></div>';
    if (!ha.todo) {
      html += '<p class="small muted">Put the supply run on a Home Assistant to-do list. Tick things off there, and add to it from anywhere, ' +
        'including by voice: <i>“Add matches to the supply run list”</i>.</p>' +
        '<div class="btn-group"><button class="btn primary" data-act="ha-make">' + ICON.list + ' Make a “Supply run” list</button>' +
        '<button class="btn" data-act="ha-pick">Use a list I already have…</button></div>';
    } else {
      var state = ha.ok === false ? pill('bad', 'Not syncing') : ha.ok ? pill('good', 'In step') : pill('warn', 'Starting');
      html += '<div class="ha-link"><div class="li-main"><span class="li-title">' + esc(ha.todo_name) + '</span>' +
        '<span class="small muted">' + esc(ha.todo) + (ha.synced_at ? ' · checked ' + esc(ago(ha.synced_at)) : '') + '</span></div>' + state + '</div>' +
        (ha.ok === false && ha.error ? '<p class="small ha-error">' + esc(ha.error) + '</p>' : '') +
        '<p class="small muted">Everything on the supply run is on that list. Tick extras off on either side. ' +
        'Tick off a below-target item there and it\'s marked here, ready to put away with <b>Got it</b>.</p>' +
        '<div class="btn-group"><button class="btn" data-act="ha-pick">Change list</button><button class="btn danger" data-act="ha-stop">Stop syncing</button></div>';
    }
    return html + '</section><p class="callout info">For dashboard cards and phone alerts, open the app\'s <b>Documentation</b> tab in Home Assistant.</p>';
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

  function hqAppearance() {
    var theme = document.documentElement.dataset.theme || 'auto';
    return '<section class="card"><div class="card-head"><h2>Theme</h2></div>' +
      '<div class="seg hq-theme" role="group" aria-label="Theme">' +
      [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (t) {
        return '<button data-act="theme" data-val="' + t[0] + '" aria-pressed="' + (theme === t[0]) + '">' + t[1] + '</button>';
      }).join('') + '</div>' +
      '<p class="small muted hq-foot">Auto follows this device\'s light or dark setting. The choice is kept on this device only.</p></section>';
  }

  // The activity log, a day at a time.
  function hqLogHtml(entries) {
    var day = null, html = '', t0 = today();
    entries.forEach(function (l) {
      var d = String(l.ts || '').slice(0, 10);
      if (d !== day) {
        day = d;
        var n = d ? -daysUntil(d) : null;
        var label = !d ? 'Earlier' : n === 0 ? 'Today' : n === 1 ? 'Yesterday' : parseYmd(d).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
        html += (html ? '</div>' : '') + '<h3 class="hq-log-day">' + esc(label) + '</h3><div class="hq-log">';
      }
      var time = String(l.ts || '').slice(11, 16);
      html += '<div class="hq-log-item"><span class="log-dot ' + esc(l.action) + '" aria-hidden="true"></span>' +
        '<div class="log-text"><b>' + esc(LOG_VERB[l.action] || l.action) + '</b>' + (l.item ? ' ' + esc(l.item) : '') +
        (l.detail ? '<span class="hq-log-detail">' + esc(l.detail) + '</span>' : '') + '</div>' +
        '<time class="log-when" datetime="' + esc(l.ts) + '" title="' + esc(ago(l.ts)) + '">' + esc(d === t0 ? ago(l.ts) : time) + '</time></div>';
    });
    return html ? html + '</div>' : '';
  }

  function renderHQ(el) {
    var secs = hqSections();
    if (!secs.some(function (s) { return s[0] === HQ_SEC; })) HQ_SEC = 'household';
    var html = '<div class="split hq">' +
      '<nav class="subnav hq-nav" aria-label="HQ sections">' + secs.map(function (s) {
        return '<button type="button" id="hq-nav-' + s[0] + '" data-act="hq-sec" data-sec="' + s[0] + '" aria-current="' + (s[0] === HQ_SEC) + '">' +
          HQ_ICON[s[0]] + '<span>' + esc(s[1]) + '</span></button>';
      }).join('') + '</nav><div class="hq-body">';

    html += hqSec('household', 'Household', 'Who the stores are for. Food, water and the starter list are all worked out from this.', hqHousehold());
    html += hqSec('targets', 'Targets and warnings', 'How long the stores should last, and how much notice you get before things go out of date.', hqTargets());
    html += hqSec('alerts', 'Warnings and live alerts', 'Official warnings, your home\'s sensors and live information for where you are.', warnHqCard() + homeCard() + intelHQ());
    html += hqSec('backups', 'Backups', 'If the power goes, so does the Pi. Keep a printed copy with the stores, and a backup somewhere else.', hqBackups());
    if (S.server.ha) html += hqSec('ha', 'Home Assistant', 'The Home front dashboard, today\'s checklist and the supply run list.', haCard());
    html += hqSec('appearance', 'Appearance', '', hqAppearance());
    html += hqSec('activity', 'Activity', S.log.length ? 'The last ' + esc(S.log.length) + ' changes, newest first.' : '',
      '<section class="card hq-activity">' + (S.log.length ? hqLogHtml(S.log) : '<p class="small muted" style="margin:0">Nothing yet. Changes to the stores and settings show up here.</p>') + '</section>');

    html += '<p class="tagline">Dads Army v' + esc(S.server.version) + ' · Don\'t panic</p></div></div>';
    el.innerHTML = html;
  }

  function queueSetting(key, value) {
    // Per-category warnings go one category at a time: gather them up.
    settingsQueue[key] = key === 'category_warn_days' ? Object.assign({}, settingsQueue[key], value) : value;
    clearTimeout(settingsTimer);
    settingsTimer = setTimeout(function () {
      var body = settingsQueue;
      settingsQueue = {};
      run(function () {
        return api('PUT', 'api/settings', body).then(function (res) {
          return refresh().then(function () {
            toast(res.rescaled ? 'Saved · ' + res.rescaled + ' starter target' + (res.rescaled === 1 ? '' : 's') + ' updated' : 'Saved');
          });
        }, function (e) {
          updateHQ();   // put back what's really saved
          throw e;
        });
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
      ' · ' + esc(st.adults) + ' adults, ' + esc(st.children) + ' children' + (st.pets ? ', ' + esc(st.pets) + ' pets' : '') +
      ' · Food ≈ ' + esc(fmtDays(r.foodDays)) + ' days · Water ≈ ' + esc(fmtDays(r.waterDays)) + ' days</p>';
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
    var a = document.activeElement;
    s.trigger = a && a !== document.body ? a : null;   // focus goes back here when it closes
    s.triggerKey = focusKey(s.trigger);
    stack.push(s);
    try { history.pushState({ daSheet: stack.length }, ''); } catch (e) { /* ignore */ }
    showSheet(true);
  }
  function closeSheet() {
    if (!stack.length) return;
    if (history.state && history.state.daSheet) history.back();
    else popSheet();
  }
  function popSheet() {
    var gone = stack.pop();
    showSheet(true);
    // Back to whatever opened it (or the same control, if it has been redrawn since).
    var t = gone && gone.trigger;
    if (t && document.contains(t) && !t.closest('[inert]')) t.focus();
    else if (gone) refocus(gone.triggerKey, stack.length ? $('#sheet-body') : document);
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
    if (stack.length) popSheet();
    else if (SEL) { endSelect(); renderStoreList(); }
  });
  // While a sheet is open, everything behind it is out of reach (screen readers and the Tab key).
  function setInert(on) {
    $$('body > header, #offline, main, nav.tabs').forEach(function (el) {
      el.inert = on;
      if (on) el.setAttribute('inert', ''); else el.removeAttribute('inert');
    });
  }
  function showSheet(resetScroll) {
    var root = $('#sheet-root');
    if (!stack.length) {
      root.hidden = true;
      document.body.classList.remove('sheet-open');
      setInert(false);
      $('#sheet-body').innerHTML = '';
      return;
    }
    var appearing = root.hidden;
    root.classList.toggle('anim', appearing);
    root.hidden = false;
    document.body.classList.add('sheet-open');
    setInert(true);
    var top = stack[stack.length - 1];
    var isNew = !top.shown;
    top.shown = true;
    renderSheet();
    if (resetScroll) $('.sheet', root).scrollTop = 0;
    if (isNew && stack[stack.length - 1] === top) {
      // Into the sheet: its first field if it asks for that, otherwise its heading.
      var auto = $('[data-autofocus]', root) || $('#sheet-title', root);
      if (auto) {
        try { auto.focus({ preventScroll: true }); } catch (e) { auto.focus(); }
        if (appearing && auto.matches('input, textarea')) setTimeout(function () { if (document.activeElement === auto) auto.focus(); }, 280);
      }
    }
  }
  function renderSheet() {
    var s = stack[stack.length - 1];
    if (!s) return;
    var html = {
      item: sheetItem, edit: sheetEdit, stock: sheetStock, use: sheetUse, batch: sheetBatch, text: sheetText, halists: sheetHaLists,
      backups: sheetBackups, shoptext: sheetShopText,
      check: sheetCheck, plan: sheetPlan, warning: sheetWarning, warnset: sheetWarnSet, help: sheetHelp, dashwiz: sheetDashWiz,
      level: sheetLevel, levelhelp: sheetLevelHelp, homesensors: sheetHomeSensors, area: sheetArea, resall: sheetResAll
    }[s.type](s);
    if (html === null) {   // the item was deleted elsewhere
      closeSheet();
      return;
    }
    var body = $('#sheet-body'), a = document.activeElement;
    var keep = a && body.contains(a) ? focusKey(a) : null;
    body.innerHTML = html;
    if (keep && !refocus(keep, body)) { var h = $('#sheet-title', body); if (h) h.focus(); }
    if (s.type === 'edit') perDayHint($('#itemForm'));
  }
  function sheetHead(title, sub, icon) {
    return '<div class="sheet-head">' + (icon ? '<span class="li-ico">' + icon + '</span>' : '') +
      '<div><h2 id="sheet-title" tabindex="-1">' + esc(title) + '</h2>' + (sub ? '<p>' + esc(sub) + '</p>' : '') + '</div>' +
      '<button class="icon-btn" type="button" data-act="close-sheet" aria-label="Close">' + ICON.close + '</button></div>';
  }
  function stat(value, label) {
    return '<div class="stat"><span class="stat-val">' + esc(value) + '</span><span class="stat-lbl">' + esc(label) + '</span></div>';
  }
  function expiryField(val, usual) {
    return '<div class="field st-date"><span>Best before / expiry</span>' +
      '<input type="date" name="expiry" value="' + esc(val || '') + '" aria-label="Best before date">' +
      '<div class="quick" role="group" aria-label="Quick dates">' + (usual ? '<button type="button" class="chip" data-exp="' + usual + '">Like last time (+' + monthsWords(usual) + ')</button>' : '') +
      [[6, '6 months'], [12, '1 year'], [24, '2 years'], [60, '5 years'], [300, '25 years']].map(function (m) {
        return '<button type="button" class="chip" data-exp="' + m[0] + '">+' + m[1] + '</button>';
      }).join('') + '<button type="button" class="chip" data-exp="">No date</button></div>' +
      '<div class="hint">Leave it empty for things that don\'t go off.</div></div>';
  }
  function locationField(val) {
    return '<label class="field"><span>Where is it kept?</span><input type="text" name="location" list="dl-locations" value="' + esc(val || '') +
      '" placeholder="e.g. Garage shelf B" maxlength="80" autocomplete="off"></label>';
  }
  // A labelled quantity stepper, with optional quick chips and a hint under it.
  function stQtyField(label, value, chips, hint, err) {
    return '<div class="field st-qty"><span>' + esc(label) + '</span>' + stepperHtml('qty', value, 'Quantity') +
      (chips ? '<div class="quick">' + chips + '</div>' : '') +
      (hint ? '<div class="hint">' + hint + '</div>' : '') +
      (err ? '<p class="form-error" role="alert" hidden></p>' : '') + '</div>';
  }
  function stSetChip(q, text) { return '<button type="button" class="chip" data-setqty="' + esc(q) + '">' + esc(text) + '</button>'; }
  // "9 of 15 tins in date", for sheet subtitles.
  function stHave(it, i) {
    return stAmt(i.fresh, it.unit) + (it.target_qty > 0 ? ' of ' + stAmt(it.target_qty, it.unit) : '') +
      (isMoney(it.unit) || !it.unit ? '' : ' ' + plural(it.unit, it.target_qty > 0 ? it.target_qty : i.fresh)) + ' in date';
  }

  function sheetItem(s) {
    var it = byId(s.id);
    if (!it) return null;
    var i = info(it), c = cat(it.category), r = readiness();
    var animate = !s.drawn;   // charts draw in the first time only, not on every refresh
    s.drawn = true;
    var t = it.target_qty > 0 ? it.target_qty : 0;
    var state = t ? stateOf(i.fresh / t) : 'info';
    var unitOf = function (q) { return isMoney(it.unit) || !it.unit ? '' : ' ' + plural(it.unit, q); };
    var ring = window.DAChart ? DAChart.ring({
      value: i.fresh, max: t || Math.max(i.fresh, 1), size: 112, thickness: 11, state: state,
      label: stAmt(i.fresh, it.unit), sub: t ? 'of ' + stAmt(t, it.unit) : (it.unit && !isMoney(it.unit) ? plural(it.unit, i.fresh) : 'in stock'),
      title: it.name + ' in date', noAnimate: !animate
    }) : '';
    var verdict = !t ? '<span class="pill plain">No target set</span>'
      : !i.low ? pill('good', 'Target met')
      : pill(state, i.out ? 'None in date' : fq(i.short) + unitOf(i.short) + ' short');
    var big = '<b>' + esc(stAmt(i.fresh, it.unit)) + '</b>' + (t ? ' of ' + esc(stAmt(t, it.unit)) : '') + esc(unitOf(t || i.fresh)) + ' in date';

    var facts = [];
    function fact(k, v, cls) { facts.push('<div class="st-fact"><dt>' + esc(k) + '</dt><dd' + (cls ? ' class="' + cls + '"' : '') + '>' + v + '</dd></div>'); }
    fact('Target', t ? esc(stAmt(t, it.unit) + unitOf(t)) + (it.target_rule ? ' <span class="muted">· scales with your household</span>' : '')
      : '<span class="muted">None. Set one in Edit details.</span>');
    var rate = stRate(it), lasts = stLasts(it), d = stDays(it);
    if (rate) {
      var until = d !== null && d >= 1 && d < 3650 ? ' <span class="muted">(about ' + esc(fmtDate(addDays(d))) + ')</span>' : '';
      fact('Usage', esc(rate) + (lasts ? ' · <span class="' + (d <= 14 ? 'warn-ink' : '') + '">' + esc(lasts) + '</span>' + until : ''));
    } else fact('Usage', '<span class="muted">Nothing used yet, so no forecast</span>');
    if (it.price > 0) fact('Worth', esc(money(i.total * it.price)) + ' <span class="muted">· ' + esc(money(it.price)) + ' each</span>');
    if (it.category === 'food' && it.kcal_per_unit > 0 && r.kcalDay > 0) fact('Food', esc(fmtDays(i.fresh * it.kcal_per_unit / r.kcalDay)) + ' days for the household <span class="muted">· ' + esc(nf0.format(it.kcal_per_unit)) + ' kcal each</span>');
    if (it.category === 'water' && it.litres_per_unit > 0) {
      var litres = Math.round(i.fresh * it.litres_per_unit * 10) / 10;
      fact('Water', esc(fq(litres)) + ' L' + (r.waterDay > 0 ? ' · ' + esc(fmtDays(litres / r.waterDay)) + ' days for the household' : ''));
    }
    var places = stPlaces(it);
    fact('Kept', places.length ? esc(places.join(', ')) : '<span class="muted">Nowhere set</span>');
    if (i.expired > 0) fact('Replace', esc(stAmt(i.expired, it.unit) + unitOf(i.expired)) + ' past best before', 'bad-ink');
    if (it.notes) fact('Notes', '<span class="st-notes">' + esc(it.notes) + '</span>');

    var live = it.batches.filter(function (b) { return b.qty > 0; });
    var batches = it.batches.map(function (b, n) {
      var es = expState(b.expiry, it.category);
      var next = n === 0 && live.length > 1 && b.qty > 0;
      var when = b.expiry
        ? '<span class="st-b-date">' + esc(fmtDate(b.expiry)) + '</span><span class="badge ' + (es === 'ok' ? 'plain' : es) + '">' + esc(expiryWords(b.expiry)) + '</span>'
        : '<span class="st-b-date">No expiry date</span>';
      var label = b.expiry ? fmtDate(b.expiry) : 'no date';
      return '<li class="st-b" data-state="' + es + '"' + (next ? ' data-next' : '') + '><span class="st-dot" aria-hidden="true"></span>' +
        '<button class="st-b-main" data-act="batch" data-id="' + b.id + '" data-item="' + it.id + '" aria-label="Edit the batch: ' + esc(fq(b.qty) + unitOf(b.qty) + ', ' + label) + '">' +
        (next ? '<span class="st-next">Use first</span>' : '') +
        '<span class="st-b-l1">' + when + '</span>' +
        '<span class="st-b-l2">' + (b.location ? esc(b.location) : 'No place set') + ' · added ' + esc(fmtDate(b.added_at)) + '</span></button>' +
        '<div class="mini-step st-step"><button class="qbtn" data-act="bstep" data-id="' + b.id + '" data-d="-1" aria-label="One less in the batch from ' + esc(label) + '">' + ICON.minus + '</button>' +
        '<output aria-label="' + esc(fq(b.qty) + unitOf(b.qty)) + '">' + esc(fq(b.qty)) + '</output>' +
        '<button class="qbtn" data-act="bstep" data-id="' + b.id + '" data-d="1" aria-label="One more in the batch from ' + esc(label) + '">' + ICON.plus + '</button></div></li>';
    }).join('');

    return sheetHead(it.name, c.label + (it.unit ? ' · counted in ' + plural(it.unit, 2) : ''), c.icon) +
      '<div class="st-hero"><div class="st-ring">' + ring + '</div><div class="st-hero-txt"><div class="st-big">' + big + '</div>' + verdict +
      (i.soonest ? '<div class="st-soon">' + (i.exp === 'bad' ? 'Some has expired' : 'Next best before ' + esc(fmtDate(i.soonest))) + '</div>' : '') + '</div></div>' +
      '<dl class="st-facts">' + facts.join('') + '</dl>' +
      '<h3>Batches' + (it.batches.length > 1 ? ' <small>used in this order</small>' : '') + '</h3>' +
      (batches ? '<ol class="st-tl">' + batches + '</ol>'
        : '<div class="empty compact st-nobatch"><p>None in stock. Add some when you next stock up.</p></div>') +
      '<div class="btn-row st-more"><button class="btn" data-act="edit" data-id="' + it.id + '">' + ICON.edit + ' Edit details</button>' +
      '<button class="btn danger" data-act="del-item" data-id="' + it.id + '">' + ICON.trash + ' Delete</button></div>' +
      '<div class="sheet-actions st-acts"><button class="btn" data-act="use-sheet" data-id="' + it.id + '"' + (i.none ? ' disabled' : '') + '>' + ICON.minus + ' Use</button>' +
      '<button class="btn primary" data-act="stock" data-id="' + it.id + '">' + ICON.plus + ' Add stock</button></div>';
  }
  function addDays(n) { var x = new Date(); x.setDate(x.getDate() + n); return ymd(x); }

  function sheetEdit(s) {
    var it = s.id ? byId(s.id) : null;
    if (s.id && !it) return null;
    var v = it || { name: s.name || '', category: s.cat || 'food', unit: '', kcal_per_unit: 0, litres_per_unit: 0, target_qty: 0, per_day: 0, price: 0, notes: '' };
    var cats = CATS.map(function (c) {
      return '<label class="cat-opt"><input type="radio" name="category" value="' + c.id + '"' + (c.id === v.category ? ' checked' : '') + '>' +
        '<span><i aria-hidden="true">' + c.icon + '</i>' + esc(c.short || c.label) + '</span></label>';
    }).join('');
    return sheetHead(it ? 'Edit item' : 'New item', it ? it.name : 'Add something to the stores') +
      '<form id="itemForm" class="st-form" data-cat="' + esc(v.category) + '" data-id="' + (it ? it.id : '') + '"' + (s.shop ? ' data-shop="' + esc(s.shop) + '"' : '') + ' novalidate>' +
      '<label class="field"><span>Name</span><input type="text" name="name" value="' + esc(v.name) + '" maxlength="120" placeholder="e.g. Baked beans (415g)" autocomplete="off"' + (it ? '' : ' data-autofocus') + '></label>' +
      '<p class="form-error" role="alert" hidden></p>' +
      '<fieldset class="field"><legend>Category</legend><div class="cat-grid">' + cats + '</div></fieldset>' +
      '<h3>Counting it</h3>' +
      '<div class="grid2"><label class="field"><span>Unit</span><input type="text" name="unit" value="' + esc(v.unit) + '" list="dl-units" placeholder="tin, pack, kg" maxlength="30" autocomplete="off">' +
      '<div class="hint">What you count it in.</div></label>' +
      '<div class="field"><span>Target stock</span>' + stepperHtml('target_qty', v.target_qty || 0, 'Target stock') +
      '<div class="hint">' + (it && it.target_rule ? 'Scales with your household. Change it to set your own.' : 'How many you want in. 0 for no target.') + '</div></div></div>' +
      '<div class="grid2"><label class="field"><span>Used a day</span><input type="text" name="per_day" value="' + esc(v.per_day || '') + '" inputmode="decimal" autocomplete="off" placeholder="Optional"></label>' +
      '<label class="field"><span>Price each (£)</span><input type="text" name="price" value="' + esc(v.price || '') + '" inputmode="decimal" autocomplete="off" placeholder="Optional"></label></div>' +
      '<div class="hint st-perday" id="perDayHint"></div>' +
      '<div class="only-food"><label class="field"><span>Calories per unit</span><input type="text" name="kcal_per_unit" value="' + esc(v.kcal_per_unit || '') + '" inputmode="decimal" autocomplete="off" placeholder="e.g. 340">' +
      '<div class="hint">Used to work out how many days your food will last.</div></label>' +
      '<details class="calc"><summary>Work it out from the label</summary><div class="grid2">' +
      '<label class="field"><span>kcal per 100g</span><input type="number" data-calc="per100" inputmode="decimal" min="0" step="any"></label>' +
      '<label class="field"><span>Weight (g)</span><input type="number" data-calc="grams" inputmode="decimal" min="0" step="any"></label></div></details></div>' +
      '<label class="field only-water"><span>Litres per unit</span><input type="text" name="litres_per_unit" value="' + esc(v.litres_per_unit || '') + '" inputmode="decimal" autocomplete="off" placeholder="e.g. 5">' +
      '<div class="hint">Drinkable water only. Leave empty for filters, tablets and containers.</div></label>' +
      (it ? '' : '<h3>Opening stock</h3>' + stQtyField('How many have you got?', 1, '', 'Put 0 if you haven\'t any yet.') +
        expiryField('') + locationField(lastLocation(lastTouched()))) +
      '<h3>Anything else</h3>' +
      '<label class="field"><span>Notes</span><textarea name="notes" rows="2" maxlength="2000" placeholder="Optional: brand, size, where to buy">' + esc(v.notes) + '</textarea></label>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + (it ? 'Save changes' : ICON.plus + ' Add to stores') + '</button></div></form>';
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
    var i = info(it);
    var chips = i.short > 0 ? stSetChip(i.short, 'Up to target (' + stAmt(i.short, it.unit) + ')') : '';
    return sheetHead('Add stock', it.name + ' · ' + stHave(it, i), cat(it.category).icon) +
      '<form id="stockForm" class="st-form" data-id="' + it.id + '" novalidate>' +
      stQtyField(howMany(it.unit), s.qty || 1, chips, '', true) +
      expiryField('', usualLife(it)) + locationField(lastLocation(it) || lastLocation(lastTouched())) +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + ICON.plus + ' Add to stores</button></div></form>';
  }

  function sheetUse(s) {
    var it = byId(s.id);
    if (!it) return null;
    var i = info(it);
    var first = it.batches.filter(function (b) { return b.qty > 0; })[0];
    var from = first ? (first.expiry
      ? 'It comes out of the batch that ' + (daysUntil(first.expiry) < 0 ? 'expired on ' : 'goes off first, ') + esc(fmtDate(first.expiry)) + (first.location ? ' (' + esc(first.location) + ')' : '') + '.'
      : 'It comes out of the oldest batch' + (first.location ? ' (' + esc(first.location) + ')' : '') + '.') : '';
    return sheetHead('Use stock', it.name + ' · ' + qu(i.total, it.unit) + ' in all', cat(it.category).icon) +
      '<form id="useForm" class="st-form" data-id="' + it.id + '" novalidate>' +
      stQtyField(howMany(it.unit), 1, stSetChip(i.total, 'All of it (' + fq(i.total) + ')'), from, true) +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + ICON.minus + ' Use it</button></div></form>';
  }

  function sheetBatch(s) {
    var it = byId(s.item);
    var b = it && it.batches.filter(function (x) { return x.id === s.id; })[0];
    if (!b) return null;
    return sheetHead('Edit batch', it.name + ' · added ' + fmtDate(b.added_at), cat(it.category).icon) +
      '<form id="batchForm" class="st-form" data-id="' + b.id + '" novalidate>' +
      stQtyField('How many are in this batch?', b.qty, '', '', true) +
      expiryField(b.expiry) + locationField(b.location) +
      '<div class="sheet-actions st-acts st-acts-b"><button class="btn danger" type="button" data-act="del-batch" data-id="' + b.id + '">' + ICON.trash + ' Remove this batch</button>' +
      '<button class="btn primary" type="submit">Save batch</button></div></form>';
  }

  function sheetText(s) {
    return sheetHead(s.title, 'Select all and copy') +
      '<textarea readonly rows="12" style="font-family:ui-monospace,monospace;font-size:14px">' + esc(s.text) + '</textarea>';
  }

  function sheetShopText(s) {
    var x = S.shopping.filter(function (r) { return r.id === s.id; })[0];
    if (!x) return null;
    return sheetHead('Change it', 'Also get', '📝') +
      '<form id="shopEditForm" data-id="' + x.id + '" novalidate autocomplete="off">' +
      '<label class="field"><span>What to get</span><input type="text" name="text" value="' + esc(x.text) + '" maxlength="200" data-autofocus></label>' +
      '<p class="form-error" role="alert" hidden></p>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">Save</button></div></form>';
  }

  function sheetBackups(s) {
    var d = s.data, body;
    if (!d) body = '<p class="small muted">Looking for them…</p>';
    else if (d.error) body = '<p class="small ha-error">' + esc(d.error) + '</p>';
    else if (!d.backups.length) body = '<p class="small muted">There aren\'t any yet. Dads Army makes one each day.</p>';
    else {
      body = '<p class="small muted">Dads Army keeps a copy from each of the last ' + esc(d.keep) + ' days, plus a copy from just before each restore. ' +
        'Restoring one replaces everything in the stores, but a copy of what\'s there now is kept first.</p><div class="list">' +
        d.backups.map(function (b) {
          var when = new Date(String(b.at).replace(' ', 'T'));
          var label = isNaN(when) ? b.at : when.toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
          var what = b.items === null ? 'Can\'t be read' : b.items + ' item' + (b.items === 1 ? '' : 's');
          return '<div class="li"><button class="li-main" data-act="backup-use" data-name="' + esc(b.name) + '"' + (b.items === null ? ' disabled' : '') + '>' +
            '<span class="li-title">' + esc(label) + '</span><span class="small muted">' + esc(what) +
            (b.kind === 'pre-restore' ? ' · saved before a restore' : '') + '</span></button></div>';
        }).join('') + '</div>';
    }
    return sheetHead('Automatic copies', 'Saved by Dads Army', '🗄️') + body;
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
  // Something else has changed since: an old Undo would wipe it out, so take the offer away.
  function dropUndo() {
    var t = $('#toast');
    if (t && t._undo) { t.hidden = true; t._undo = null; }
  }
  function formError(f, msg, field) {
    var e = $('.form-error', f);
    if (e) { e.textContent = msg; e.hidden = !msg; } else if (msg) toast(msg, { error: true });
    if (msg && field) field.focus();
  }

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
      // [sitrep actions: add new cases here]
      case 'sr-alert':   // a live alert from Next actions: open its source's details and bring the card into view
        INTEL_OPEN = a.dataset.src;
        render();
        setTimeout(function () { var c = $('#view .intel'); if (c) c.scrollIntoView({ block: 'start' }); }, 30);
        return;
      case 'retry':
        return run(refresh, a);
      case 'intel-jump':
        if (a.dataset.src) INTEL_OPEN = a.dataset.src;
        render();
        setTimeout(function () {
          var t = document.querySelector('.intel-open') || document.querySelector('.sr-intel');
          if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 60);
        return;
      case 'intel-src':
        INTEL_OPEN = INTEL_OPEN === a.dataset.src ? null : a.dataset.src;
        render();
        return;
      // [supply and hq actions: add new cases here]
      case 'hq-sec':
        return hqShow(a.dataset.sec, true);
      case 'go-hq-intel':
        HQ_SEC = 'alerts';
        go('hq');
        setTimeout(function () { hqShow('alerts', true); }, 50);
        return;
      case 'intel-refresh':
        return run(function () {
          return api('POST', 'api/intel/refresh').then(function () {
            toast('Checking the feeds…');
            return new Promise(function (ok) { setTimeout(ok, 9000); }).then(refresh);
          });
        }, a);
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
      // [stores actions: add new cases here]
      case 'st-fold':
        if (ST_FOLD[a.dataset.cat]) delete ST_FOLD[a.dataset.cat]; else ST_FOLD[a.dataset.cat] = 1;
        stSaveFold();
        renderStoreList();
        return refocus('button[data-act="st-fold"][data-cat="' + a.dataset.cat + '"]', $('#storeList'));
      case 'st-new':
        return openSheet({ type: 'edit', id: null, cat: F.cat !== 'all' ? F.cat : 'food', name: a.dataset.name || '' });
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
        t._undo = null;
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
        if (!s || shopBusy[id]) return;   // one tap at a time per line
        var was = s.done;
        shopBusy[id] = true;
        s.done = was ? 0 : 1;   // instant feedback
        a.setAttribute('aria-checked', s.done ? 'true' : 'false');
        return api('PUT', 'api/shopping/' + id, { done: !!s.done }).then(function () {
          delete shopBusy[id];
          return refresh();
        }, function (e) {
          delete shopBusy[id];
          s.done = was;   // it didn't happen: put the tick back as it was
          $$('[data-act="shop-toggle"][data-id="' + id + '"]').forEach(function (b) { b.setAttribute('aria-checked', was ? 'true' : 'false'); });
          toast(e.message || 'Something went wrong', { error: true });
        }).catch(function (e) { toast(e.message || 'Something went wrong', { error: true }); });
      }
      case 'shop-edit':
        return openSheet({ type: 'shoptext', id: id });
      case 'shop-got': {
        var x = S.shopping.filter(function (r) { return r.id === id; })[0];
        if (!x) return;
        return openSheet({ type: 'edit', id: null, cat: 'other', name: x.text, shop: x.id });
      }
      case 'backups': {
        var bs = { type: 'backups', data: null };
        openSheet(bs);
        return api('GET', 'api/backups').then(function (d) { bs.data = d; }, function (e) {
          bs.data = { error: e.message, backups: [] };
        }).then(function () { if (stack[stack.length - 1] === bs) renderSheet(); });
      }
      case 'backup-use': {
        var top = stack[stack.length - 1];
        var b = top && top.data && top.data.backups.filter(function (x) { return x.name === a.dataset.name; })[0];
        if (!b) return;
        var label = $('.li-title', a).textContent;
        if (!b.items) {
          if (!confirm('The copy from ' + label + ' has NO items in it.\n\nRestoring it EMPTIES the stores. Dads Army keeps a copy of the current data first, just in case.\n\nEmpty the stores?')) return;
        } else if (!confirm('Restore the copy from ' + label + ' (' + b.items + ' items)?\n\nThis REPLACES everything currently in the stores. Dads Army keeps a copy of the current data first, just in case.')) return;
        return run(function () {
          return api('POST', 'api/backups/restore', { name: b.name, confirm_empty: !b.items }).then(function (res) {
            closeSheet();
            return refresh().then(function () { toast('Restored ' + res.items + ' items from ' + label); });
          });
        }, a);
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
    if (input.dataset.setting === 'adults' || input.dataset.setting === 'children') {
      var other = $('[data-setting="' + (input.dataset.setting === 'adults' ? 'children' : 'adults') + '"]');
      if (v === 0 && other && num(other.value) === 0) { toast('The household needs at least one person in it', { error: true }); return; }
    }
    input.value = v;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function submitForm(f) {
    var fd = new FormData(f), d = {};
    fd.forEach(function (v, k) { d[k] = typeof v === 'string' ? v.trim() : v; });
    var btn = $('[type="submit"]', f);
    formError(f, '');
    if (f.id === 'itemForm') {
      if (!d.name) { formError(f, 'Give the item a name', f.elements.name); return; }
      var bad = ['target_qty', 'kcal_per_unit', 'litres_per_unit', 'qty'].filter(function (k) {
        return d[k] !== undefined && d[k] !== '' && !(parseQty(d[k]) >= 0);
      })[0];
      if (bad) { formError(f, 'That isn\'t a number: ' + d[bad], f.elements[bad]); return; }
      var body = {
        name: d.name, category: d.category || 'other', unit: d.unit || '', notes: d.notes || '',
        target_qty: num(d.target_qty), kcal_per_unit: num(d.kcal_per_unit), litres_per_unit: num(d.litres_per_unit),
        per_day: num(d.per_day), price: num(d.price)
      };
      var id = f.dataset.id, shop = f.dataset.shop;
      if (!id) { body.qty = num(d.qty); body.expiry = d.expiry || null; body.location = d.location || ''; }
      return run(function () {
        return api(id ? 'PUT' : 'POST', id ? 'api/items/' + id : 'api/items', body).then(function () {
          // Bought from the "Also get" list: it's in the stores now, so it comes off the list.
          return shop ? api('DELETE', 'api/shopping/' + shop).catch(function () { /* already gone */ }) : null;
        }).then(function () {
          closeSheet();
          return refresh().then(function () { toast(id ? 'Saved' : body.name + ' added to the stores'); });
        });
      }, btn);
    }
    if (f.id === 'stockForm') {
      var qty = parseQty(d.qty);
      if (!(qty > 0)) { formError(f, 'How many are you adding?', f.elements.qty); return; }
      return run(function () {
        return api('POST', 'api/items/' + f.dataset.id + '/stock', { qty: qty, expiry: d.expiry || null, location: d.location || '' }).then(function (res) {
          var it = byId(+f.dataset.id);
          closeSheet();
          return refresh().then(function () { toast('Added ' + qu(qty, it ? it.unit : '') + (it ? ' · ' + it.name : ''), { undo: res.undo }); });
        });
      }, btn);
    }
    if (f.id === 'useForm') {
      var uq = parseQty(d.qty);
      if (!(uq > 0)) { formError(f, 'How many are you using?', f.elements.qty); return; }
      return run(function () {
        return api('POST', 'api/items/' + f.dataset.id + '/use', { qty: uq }).then(function (res) {
          var it = byId(+f.dataset.id);
          closeSheet();
          return refresh().then(function () { toast('Used ' + qu(res.used, it ? it.unit : ''), { undo: res.undo }); });
        });
      }, btn);
    }
    if (f.id === 'batchForm') {
      var bq = parseQty(d.qty);
      if (!(bq >= 0)) {   // empty or not a number: never send 0 (that removes the batch)
        formError(f, d.qty ? 'That isn\'t a number: ' + d.qty : 'How many are in this batch?', f.elements.qty);
        return;
      }
      if (bq === 0 && !confirm('Set this batch to 0?\n\nThat removes it from the stores.')) return;
      return run(function () {
        return api('PUT', 'api/batches/' + f.dataset.id, { qty: bq, expiry: d.expiry || null, location: d.location || '' }).then(function (res) {
          closeSheet();
          return refresh().then(function () { toast(res.removed ? 'Batch removed' : 'Batch saved', res.removed ? { undo: res.undo } : {}); });
        });
      }, btn);
    }
    if (f.id === 'shopEditForm') {
      if (!d.text) { formError(f, 'Type what to get, or remove it from the list instead', f.elements.text); return; }
      return run(function () {
        return api('PUT', 'api/shopping/' + f.dataset.id, { text: d.text }).then(function () {
          closeSheet();
          return refresh().then(function () { toast('Saved'); });
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
    if (t.id === 'q') {
      F.q = t.value;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(renderStoreList, 120);
      return;
    }
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
    // [stores change handlers: add here]
    if (t.id === 'fShow') { F.show = t.value; renderStoreList(); return; }
    if (t.id === 'fSort') {
      F.sort = t.value;
      try { localStorage.setItem('da-sort', F.sort); } catch (err) { /* ignore */ }
      renderStoreList();
      return;
    }
    if (t.dataset.setting) {
      var sv = parseQty(t.value);
      if (!(sv >= 0)) { toast('That isn\'t a number: ' + t.value, { error: true }); updateHQ(); return; }
      queueSetting(t.dataset.setting, sv);
      return;
    }
    // [hq change handlers: add here]
    if (t.dataset.slider) { sliderSave(t); return; }
    if (t.dataset.intel) {
      var iv = {};
      iv[t.dataset.intel] = t.type === 'checkbox' ? t.checked : t.value.trim();
      run(function () {
        return api('PUT', 'api/intel', iv).then(function () {
          toast('Saved · checking the feeds');
          return new Promise(function (ok) { setTimeout(ok, 4000); }).then(refresh);
        }, function (e) { render(); throw e; });   // put back what's really saved
      });
      return;
    }
    if (t.dataset.catwarn) {
      var cv = {};
      if (t.value.trim() && !(parseQty(t.value) > 0)) { toast('That isn\'t a number of days: ' + t.value, { error: true }); return; }
      cv[t.dataset.catwarn] = t.value.trim() ? Math.round(parseQty(t.value)) : null;
      queueSetting('category_warn_days', cv);
      return;
    }
    if (t.name === 'every_days') { syncEvery(t.closest('.field')); return; }
    if (t.name === 'category' && t.form) { t.form.dataset.cat = t.value; return; }
    if (t.id === 'restoreFile' && t.files && t.files[0]) {
      var file = t.files[0];
      var reader = new FileReader();
      reader.onload = function () {
        var data;
        try { data = JSON.parse(reader.result); } catch (err) { toast('That file isn\'t a Dads Army backup', { error: true }); return; }
        var n = data && data.items ? data.items.length : 0;
        if (data && data.items && !n) {
          if (!confirm('"' + file.name + '" has NO items in it.\n\nRestoring it EMPTIES the stores. Dads Army keeps a copy of the current data first, just in case.\n\nEmpty the stores?')) return;
          data.confirm_empty = true;
        } else if (!confirm('Restore ' + n + ' items from "' + file.name + '"?\n\nThis REPLACES everything currently in the stores. Dads Army keeps a copy of the current data first, just in case.')) return;
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
