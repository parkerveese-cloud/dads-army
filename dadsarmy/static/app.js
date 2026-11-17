/* Dads Army - home front stores tracker. Plain JavaScript, no build step, no internet needed. */
'use strict';
(function () {

  // ------------------------------------------------------------------
  // Constants
  // ------------------------------------------------------------------
  var CATS = [
    { id: 'food', label: 'Food', icon: '🥫' },
    { id: 'water', label: 'Water', icon: '💧' },
    { id: 'drinks', label: 'Drinks', icon: '🧃' },
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
  // Days before its best-before that something counts as expiring soon: some categories (medicines, say) can warn earlier.
  function warnDays(catId) { return ((S.settings.warn_by_cat || {})[catId]) || S.settings.warn_days; }
  function expState(s, catId) {
    if (!s) return 'none';
    var n = daysUntil(s);
    if (n < 0) return 'bad';
    if (n <= warnDays(catId)) return 'warn';
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
  // Out-of-date stock doesn't count towards the target (it needs replacing), just as the Pi works it out.
  function info(it) {
    var tot = total(it), good = inDate(it), soonest = null;
    it.batches.forEach(function (b) {
      if (b.expiry && b.qty > 0 && (soonest === null || b.expiry < soonest)) soonest = b.expiry;
    });
    return {
      total: tot,
      good: good,
      old: Math.round((tot - good) * 1000) / 1000,
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

  function petsWater(st) {
    return (st.dogs || 0) * (st.water_per_dog || 0) + (st.cats || 0) * (st.water_per_cat || 0) +
      (st.other_pets || 0) * (st.water_per_other_pet || 0);
  }
  function petsCount(st) { return (st.dogs || 0) + (st.cats || 0) + (st.other_pets || 0); }
  function petsWords(st) {
    var bits = [];
    if (st.dogs) bits.push(st.dogs + ' dog' + (st.dogs === 1 ? '' : 's'));
    if (st.cats) bits.push(st.cats + ' cat' + (st.cats === 1 ? '' : 's'));
    if (st.other_pets) bits.push(st.other_pets + ' other pet' + (st.other_pets === 1 ? '' : 's'));
    return bits.length > 1 ? bits.slice(0, -1).join(', ') + ' and ' + bits[bits.length - 1] : bits.join('');
  }
  // Food and drinks feed the household (juice and milk count as food, not drinking water).
  function kcalCat(c) { return c === 'food' || c === 'drinks'; }
  // What's kept in a cupboard, fridge or freezer (as the Pi has it: storage is '' for everything else).
  function storedCat(c) { return kcalCat(c) || c === 'pets'; }
  // Drinkable litres in one: "litres per unit" if set, else the pack size (5000 g or ml of water is 5 L).
  function itemLitres(it) {
    if (it.category !== 'water' && it.category !== 'drinks') return 0;
    if (it.litres_per_unit > 0) return it.litres_per_unit;
    var u = (it.pack_unit || '').toLowerCase(), n = +it.pack_size || 0;
    var solid = it.category === 'water';   // a 5000 g bottle of water is 5 L; a 250 g "drink" is probably rice
    return u === 'ml' || (solid && u === 'g') ? n / 1000 : u === 'l' || (solid && u === 'kg') ? n : 0;
  }
  // Is an AI set up (an API key, or Home Assistant's AI Task)? Without one, the AI buttons are hidden
  // (html.no-ai in the CSS) and a hint says what adding one would do.
  function aiOn() { return !!(S && S.ai_ready); }
  function aiHint() {
    return aiOn() ? '' : '<p class="small muted ai-hint">💡 Add an AI in <b>HQ → Scanning</b> (an API key, or Home Assistant\'s AI Task) and Dads Army can also ' +
      'read labels, best before dates and calories from photos, and fill in what\'s missing.</p>';
  }
  function srN(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  // Under the calories box: what that is in a person's day, so a per-serving figure stands out.
  function kcalHint(k, unit) {
    var base = 'For the whole ' + esc(unit || 'thing') + ': kcal per 100 g × its weight ÷ 100. A 400 g tin at 80 kcal per 100 g is 320.';
    var adult = S && S.settings ? S.settings.kcal_adult : 2200;
    if (!(k > 0) || !adult) return base;
    var pct = Math.round(100 * k / adult);
    return '<b>' + nf0.format(k) + ' kcal</b> is ' + (pct >= 100 ? fmtDays(k / adult) + ' days' : pct + '% of a day') + ' for one adult. ' + base;
  }
  // How many days stock lasts, eating whatever goes off first (as the Pi works it out): each batch can be eaten
  // up to and including its date, and what's left of it then goes to waste. lots: [[amount, expiry or null]].
  function lastsDays(lots, perDay) {
    if (!(perDay > 0)) return { days: 0, wasted: 0 };
    var t = 0, wasted = 0;
    lots.slice().sort(function (a, b) { return (a[1] ? 0 : 1) - (b[1] ? 0 : 1) || String(a[1] || '').localeCompare(String(b[1] || '')); })
      .forEach(function (l) {
        if (!(l[0] > 0)) return;
        var days = l[0] / perDay;
        if (l[1]) {
          var room = daysUntil(l[1]) + 1 - t;
          if (room <= 0) { wasted += days; return; }
          if (days > room) { wasted += days - room; days = room; }
        }
        t += days;
      });
    return { days: t, wasted: wasted };
  }
  // Water: drinks can cover up to `cap` litres of each day (the drinking), plain water the rest (cooking, washing,
  // pets), using whatever goes off first. Days that go the same way are taken together: a run ends when a lot goes
  // off, the drinks drop below a day's share or the water runs out. Same as the Pi (water_lasts), step for step.
  var DRINK_CAP = 1.5, WATER_MAX_DAYS = 3660;
  function waterLasts(wLots, dLots, perDay, cap) {
    if (!(perDay > 0)) return { days: 0, wasted: 0 };
    cap = Math.min(cap, perDay);
    var lots = function (raw) {
      return raw.filter(function (l) { return l[0] > 0; }).map(function (l) { return [l[0], l[1] ? daysUntil(l[1]) : null]; })
        .sort(function (a, b) { return (a[1] === null) - (b[1] === null) || (a[1] || 0) - (b[1] || 0); });
    };
    var water = lots(wLots), drinks = lots(dLots), t = 0, wasted = 0, day = 0;
    var sum = function (pool) { return pool.reduce(function (a, l) { return a + l[0]; }, 0); };
    var take = function (pool, want) {
      var got = 0;
      pool.forEach(function (l) { if (got >= want) return; var n = Math.min(l[0], want - got); l[0] -= n; got += n; });
    };
    while (day < WATER_MAX_DAYS) {
      [water, drinks].forEach(function (pool) {
        pool.forEach(function (l) { if (l[1] !== null && l[1] < day && l[0] > 0) { if (pool === water) wasted += l[0]; l[0] = 0; } });
      });
      var wAv = sum(water), dAv = sum(drinks), dUse = Math.min(cap, dAv), need = perDay - dUse;
      if (wAv >= need - 1e-9) {
        var run = WATER_MAX_DAYS - day;
        water.concat(drinks).forEach(function (l) { if (l[1] !== null && l[0] > 0) run = Math.min(run, l[1] + 1 - day); });
        if (dAv > 0 && dAv < cap) run = 1;   // the last of the drinks goes today
        else if (cap > 0 && cap <= dAv) run = Math.min(run, Math.floor(dAv / cap));
        if (need > 0) run = Math.min(run, Math.floor((wAv + 1e-9) / need));
        run = Math.max(1, run);
        take(drinks, dUse * run);
        take(water, need * run);
        t += run;
        day += run;
        continue;
      }
      var f = (wAv + dUse) / perDay;
      if (perDay > cap && dAv >= cap) f = Math.min(f, wAv / (perDay - cap));
      t += Math.max(0, Math.min(1, f));
      break;
    }
    return { days: t, wasted: wasted / perDay };
  }
  function readiness() {
    var st = S.settings;
    var people = st.adults + st.children;
    var kcalDay = st.adults * st.kcal_adult + st.children * st.kcal_child;
    var petWater = petsWater(st);
    var waterDay = people * st.water_per_person + petWater;
    var r = { petWater: petWater, people: people, kcalDay: kcalDay, waterDay: waterDay, kcal: 0, kcalOld: 0, litres: 0, litresOld: 0, drinkLitres: 0, coldKcal: 0, noKcal: 0 };
    var kLots = [], wLots = [], dLots = [];
    S.items.forEach(function (it) {
      var food = kcalCat(it.category), lpu = itemLitres(it), water = lpu > 0;
      if (food && !(it.kcal_per_unit > 0)) food = false;
      if (!food && !water) return;
      it.batches.forEach(function (b) {
        var old = b.expiry && daysUntil(b.expiry) < 0;
        if (food) {
          if (old) r.kcalOld += b.qty * it.kcal_per_unit;
          else {
            r.kcal += b.qty * it.kcal_per_unit; kLots.push([b.qty * it.kcal_per_unit, b.expiry]);
            if (it.storage === 'chilled' || it.storage === 'frozen') r.coldKcal += b.qty * it.kcal_per_unit;   // eat it first in a power cut
          }
        }
        if (water) {
          if (old) { if (it.category === 'water') r.litresOld += b.qty * lpu; }   // old juice is past-date food, not water
          else if (it.category === 'water') { r.litres += b.qty * lpu; wLots.push([b.qty * lpu, b.expiry]); }
          else { r.drinkLitres += b.qty * lpu; dLots.push([b.qty * lpu, b.expiry]); }   // juice, milk: the drinking only
        }
      });
    });
    r.noKcal = S.items.filter(function (it) {
      return kcalCat(it.category) && !(it.kcal_per_unit > 0) && total(it) > 0 && !/tea|coffee|salt|stock|spice|herb|water/i.test(it.name);
    }).length;
    // Eaten in date order: what goes off before you'd get to it doesn't count.
    var fl = lastsDays(kLots, kcalDay), wl = waterLasts(wLots, dLots, waterDay, people * Math.min(DRINK_CAP, st.water_per_person));
    r.foodDays = fl.days; r.foodWaste = fl.wasted;
    r.waterDays = wl.days; r.waterWaste = wl.wasted;
    r.foodOldDays = kcalDay > 0 ? r.kcalOld / kcalDay : 0;
    r.waterOldDays = waterDay > 0 ? r.litresOld / waterDay : 0;
    var kit = S.items.filter(function (it) { return it.target_qty > 0 && !kcalCat(it.category) && it.category !== 'water'; });
    r.kit = kit.length;
    r.kitPct = kit.length ? kit.reduce(function (a, it) { return a + Math.min(1, inDate(it) / it.target_qty); }, 0) / kit.length : 0;
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
        if (!res.ok) { var err = new Error(data.error || ('Error ' + res.status)); err.code = data.code; err.status = res.status; throw err; }
        return data;
      });
    }, function () {
      setOnline(false);
      throw new Error("Can't reach HQ - check the Pi and your Wi-Fi.");
    });
  }
  // An opened pack keeps for the item's "once opened" days: its batch goes off then, or at its best before
  // if that's sooner. Opened packs are used first, as the Pi takes them.
  function openedDates(data) {
    (data.items || []).forEach(function (it) {
      (it.batches || []).forEach(function (b) {
        b.printed_expiry = b.expiry;
        if (!b.opened_at || !(it.open_days > 0)) return;
        var d = parseYmd(b.opened_at.slice(0, 10));
        d.setDate(d.getDate() + it.open_days);
        b.open_until = ymd(d);
        if (!b.expiry || b.open_until < b.expiry) b.expiry = b.open_until;
      });
      (it.batches || []).sort(function (a, b) {
        return (a.opened_at ? 0 : 1) - (b.opened_at ? 0 : 1) || (a.expiry ? 0 : 1) - (b.expiry ? 0 : 1) ||
          (a.expiry || '').localeCompare(b.expiry || '') || a.id - b.id;
      });
    });
  }
  function refresh() {
    return api('GET', 'api/state').then(function (data) {
      openedDates(data);
      S = data;
      document.documentElement.classList.toggle('no-ai', !data.ai_ready);
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
      '<button class="btn block" data-act="scan">📷 Scan what you have</button>' +
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

  // ------------------------------------------------------------------
  // Trends: how ready the household has been, day by day (from the Pi's daily history)
  // ------------------------------------------------------------------
  var HIST = { days: 90, metric: 'days', rows: null, at: 0, loadedDays: 0, loading: false };
  try {
    HIST.days = +localStorage.getItem('da-trend-days') || 90;
    HIST.metric = localStorage.getItem('da-trend-metric') || 'days';
  } catch (e) { /* defaults */ }
  var CHARTS = {};
  function loadHistory(force) {
    if (HIST.loading) return;
    if (!force && HIST.rows && HIST.loadedDays === HIST.days && Date.now() - HIST.at < 10 * 60000) return;
    HIST.loading = true;
    api('GET', 'api/history?days=' + HIST.days).then(function (res) {
      HIST.rows = res.rows; HIST.at = Date.now(); HIST.loadedDays = HIST.days; HIST.loading = false;
      var box = $('#trends');
      if (box) box.outerHTML = trendsCard();
    }, function () { HIST.loading = false; });
  }
  function niceMax(v) {
    if (!(v > 0)) return 1;
    var p = Math.pow(10, Math.floor(Math.log(v) / Math.LN10)), n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  }
  function shortDate(s) { return parseYmd(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }); }
  // A line chart in SVG: thin lines, a recessive grid, labels at the line ends, and a crosshair with the
  // values when you point at it (see chartHover). Values below zero are "not known" and leave a gap.
  function lineChart(id, rows, series, opt) {
    // Drawn at the size it's shown, so the text stays the size of the text around it.
    var W = opt.width || 640, H = Math.round(Math.max(190, Math.min(260, W * 0.42))), L = 36, R = 88, T = 14, B = 26;
    var pw = W - L - R, ph = H - T - B;
    var t0 = parseYmd(rows[0].day).getTime(), t1 = parseYmd(rows[rows.length - 1].day).getTime();
    var span = Math.max(1, t1 - t0);
    var xs = rows.map(function (r) { return L + pw * (parseYmd(r.day).getTime() - t0) / span; });
    var hi = opt.max || niceMax(Math.max.apply(null, [opt.target || 0].concat(rows.map(function (r) {
      return Math.max.apply(null, series.map(function (s) { return r[s.key] > 0 ? r[s.key] : 0; }));
    }))) * 1.08);
    if (opt.whole) hi = Math.max(4, Math.ceil(hi / 4) * 4);   // counts: whole numbers on every gridline
    var y = function (v) { return T + ph - ph * Math.min(v, hi) / hi; };
    var g = '<svg class="chart" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(opt.label) + '">';
    for (var k = 0; k <= 4; k++) {
      var v = hi * k / 4, yy = y(v);
      g += '<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + yy + '" y2="' + yy + '"/>' +
        '<text class="axis" x="' + (L - 6) + '" y="' + (yy + 4) + '" text-anchor="end">' + esc(fq(Math.round(v * 10) / 10)) + '</text>';
    }
    var ticks = rows.length > 2 ? [0, Math.floor((rows.length - 1) / 2), rows.length - 1] : [0, rows.length - 1];
    ticks.forEach(function (i, n) {
      g += '<text class="axis" x="' + xs[i] + '" y="' + (H - 8) + '" text-anchor="' + (n === 0 ? 'start' : n === ticks.length - 1 ? 'end' : 'middle') + '">' + esc(shortDate(rows[i].day)) + '</text>';
    });
    var ends = [];
    if (opt.target) {
      g += '<line class="target" x1="' + L + '" x2="' + (W - R) + '" y1="' + y(opt.target) + '" y2="' + y(opt.target) + '"/>';
      ends.push({ y: y(opt.target), x: W - R, text: (opt.targetLabel || 'Target') + ' ' + fq(opt.target), cls: 'axis tgt' });
    }
    series.forEach(function (s) {
      var d = '', pen = false, last = null;
      rows.forEach(function (r, i) {
        var v = r[s.key];
        if (v === null || v === undefined || v < 0) { pen = false; return; }
        d += (pen ? 'L' : 'M') + xs[i].toFixed(1) + ' ' + y(v).toFixed(1) + ' ';
        pen = true; last = { x: xs[i], y: y(v), v: v };
      });
      g += '<path class="line" style="stroke:var(' + s.color + ')" d="' + d + '"/>';
      if (rows.length < 40) {
        rows.forEach(function (r, i) {
          if (r[s.key] >= 0) g += '<circle class="pt" style="fill:var(' + s.color + ')" cx="' + xs[i].toFixed(1) + '" cy="' + y(r[s.key]).toFixed(1) + '" r="3"/>';
        });
      }
      if (last) ends.push({ y: last.y, x: last.x, text: s.name + ' ' + fq(Math.round(last.v * 10) / 10) + (opt.unit || ''), color: s.color });
    });
    // Labels at the right-hand end of each line (and the target), nudged apart so none overlap.
    ends.sort(function (a, b) { return a.y - b.y; });
    for (var e = 1; e < ends.length; e++) if (ends[e].y - ends[e - 1].y < 16) ends[e].y = ends[e - 1].y + 16;
    var over = ends.length ? ends[ends.length - 1].y - (T + ph + 4) : 0;
    if (over > 0) ends.forEach(function (en) { en.y -= over; });
    ends.forEach(function (en) {
      g += '<text class="' + (en.cls || 'end') + '" x="' + (W - R + 8) + '" y="' + (en.y + 4) + '">' + esc(en.text) + '</text>';
    });
    g += '<line class="xhair" x1="0" x2="0" y1="' + T + '" y2="' + (T + ph) + '" hidden/>' +
      '<rect class="chart-hit" data-chart="' + id + '" x="' + L + '" y="' + T + '" width="' + pw + '" height="' + ph + '"/></svg>';
    CHARTS[id] = { xs: xs, rows: rows, series: series, unit: opt.unit || '', W: W };
    return '<div class="chart-wrap" id="' + id + '">' + g + '<div class="chart-tip" hidden></div></div>';
  }
  // The width the chart will have: the card's, which on wide screens is one of the columns.
  function chartWidth() {
    var v = $('#view'), w = 360;
    if (v) { var cs = getComputedStyle(v); w = v.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight); }
    if (isWide()) {
      var n = Math.max(1, Math.min(3, Math.floor((w + 18) / 398)));
      w = (w - 18 * (n - 1)) / n;
    }
    return Math.max(260, Math.round(w - 34));   // the card's padding and border
  }
  var chartResize = null;
  window.addEventListener('resize', function () {
    clearTimeout(chartResize);
    chartResize = setTimeout(function () { var tb = $('#trends'); if (tb && HIST.rows) tb.outerHTML = trendsCard(); }, 250);
  });
  function chartHover(e) {
    var hit = e.target.closest && e.target.closest('.chart-hit');
    $$('.chart-wrap').forEach(function (w) {
      if (hit && w.contains(hit)) return;
      var t = $('.chart-tip', w); if (t) t.hidden = true;
      var x = $('.xhair', w); if (x) x.setAttribute('hidden', '');
    });
    if (!hit) return;
    var c = CHARTS[hit.dataset.chart], wrap = hit.closest('.chart-wrap'), svg = hit.ownerSVGElement;
    if (!c || !wrap || !svg) return;
    var box = svg.getBoundingClientRect(), sx = (e.clientX - box.left) * c.W / box.width;
    var best = 0;
    c.xs.forEach(function (x, i) { if (Math.abs(x - sx) < Math.abs(c.xs[best] - sx)) best = i; });
    var r = c.rows[best], line = $('.xhair', wrap), tip = $('.chart-tip', wrap);
    line.setAttribute('x1', c.xs[best]); line.setAttribute('x2', c.xs[best]); line.removeAttribute('hidden');
    tip.innerHTML = '<b>' + esc(fmtDate(r.day)) + '</b>' + c.series.map(function (s) {
      var v = r[s.key];
      return '<span><i style="background:var(' + s.color + ')"></i>' + esc(s.name) + ' <b>' + (v >= 0 ? esc(fq(Math.round(v * 10) / 10)) + esc(c.unit) : '–') + '</b></span>';
    }).join('');
    tip.hidden = false;
    var px = c.xs[best] * box.width / c.W;
    tip.style.left = Math.max(0, Math.min(box.width - tip.offsetWidth, px - tip.offsetWidth / 2)) + 'px';
  }
  function trendsCard() {
    loadHistory();
    var rows = HIST.rows, m = HIST.metric;
    var html = '<section class="card trends" id="trends"><div class="card-head"><h2>Trends</h2>' +
      '<div class="seg small" role="group" aria-label="What to show">' + [['days', 'Days you could last'], ['res', 'Resilience']].map(function (x) {
        return '<button data-act="trend-metric" data-val="' + x[0] + '" aria-pressed="' + (m === x[0]) + '">' + x[1] + '</button>';
      }).join('') + '</div></div>';
    if (!rows) return html + '<p class="small muted">Loading…</p></section>';
    var useful = rows.filter(function (r) { return m === 'res' ? r.resilience >= 0 : r.food_days >= 0 || r.water_days >= 0; });
    if (useful.length < 2) {
      return html + '<p class="small muted">The charts fill in a day at a time: there\'s ' + (useful.length ? 'one day' : 'nothing') +
        ' so far. Come back in a day or two.</p></section>';
    }
    var series = m === 'res'
      ? [{ key: 'resilience', name: 'Resilience', color: '--series-1' }]
      : [{ key: 'water_days', name: 'Water', color: '--series-1' }, { key: 'food_days', name: 'Food', color: '--series-2' }];
    if (m !== 'res') {
      html += '<div class="legend">' + series.map(function (s) { return '<span><i style="background:var(' + s.color + ')"></i>' + s.name + '</span>'; }).join('') +
        '<span><i class="dash"></i>Target</span></div>';
    }
    html += lineChart('chart-' + m, useful, series, m === 'res'
      ? { label: 'Resilience, per cent ready, by day', max: 100, unit: '%', width: chartWidth() }
      : { label: 'Days the food and water would last, by day', target: S.settings.target_days, unit: ' d', width: chartWidth() });
    html += '<div class="chips trend-range">' + [[30, '30 days'], [90, '90 days'], [365, '1 year'], [1830, 'All']].map(function (d) {
      return '<button class="chip" data-act="trend-days" data-val="' + d[0] + '" aria-pressed="' + (HIST.days === d[0]) + '">' + d[1] + '</button>';
    }).join('') + '</div>';
    html += '<details class="trend-table"><summary>Show as a table</summary><table class="live-table"><thead><tr><th>Day</th>' +
      series.map(function (s) { return '<th class="num">' + esc(s.name) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      useful.slice().reverse().map(function (r) {
        return '<tr><td>' + esc(fmtDate(r.day)) + '</td>' + series.map(function (s) {
          return '<td class="num">' + (r[s.key] >= 0 ? esc(fq(Math.round(r[s.key] * 10) / 10)) + (m === 'res' ? '%' : '') : '–') + '</td>';
        }).join('') + '</tr>';
      }).join('') + '</tbody></table></details>';
    return html + '</section>';
  }

  // Pets: their food lasts as long as the pet food with a daily use (their water is in the water meter).
  function petMeter(target) {
    var st = S.settings, p = S.pets;
    if (!petsCount(st) || !p) return '';
    if (p.food_days === null || p.food_days === undefined) {
      return '<div class="meter-plain"><span class="meter-label">🐾 Pet food</span> <span class="small muted">' + esc(petsWords(st)) +
        '. Set <b>Used a day</b> on their food to see how long it lasts' +
        (S.items.some(function (it) { return it.category === 'pets'; }) ? '' : ', or <button class="link" data-act="seed">add pet food from the starter list</button>') + '.</span></div>';
    }
    var who = S.items.filter(function (it) { return it.name === p.food_runs_out_first; })[0];
    return meter('🐾 Pet food', fmtDays(p.food_days) + ' of ' + target + ' days', p.food_days / target,
      esc(petsWords(st)) + (who ? ' · <button class="link" data-act="open" data-id="' + who.id + '">' + esc(who.name) + '</button> runs out first' : ''));
  }

  // A review suggestion already added (this visit), or already on the supply run: it isn't offered again.
  function onSupplyRun(g) {
    var want = String(g.add || '').trim().toLowerCase();
    return !!g.added || (S.shopping || []).some(function (x) { return !x.done && String(x.text || '').trim().toLowerCase() === want; });
  }
  // Is the food a balanced diet, and what's missing? Asked for with a button; the last answer is kept.
  function reviewCard() {
    if (!aiOn() || !S.items.some(function (it) { return total(it) > 0; })) return '';   // no AI set up: no review
    var v = S.stock_review, words = ['', 'Would not do', 'Big gaps', 'Some gaps', 'Good', 'Would feed you well'];
    var head = '<div class="card-head"><h2>Stores review</h2>' + (v && v.score ? pill(v.score >= 4 ? 'good' : v.score === 3 ? 'warn' : 'bad', words[v.score]) : '') + '</div>';
    if (!v) {
      return '<section class="card review-card">' + head + '<p class="small muted">The AI checks whether your food would feed the household with no mains water, power, gas or fridge: ' +
        'can it be eaten cold or with a little heat, will it keep once opened, and is it a balanced diet (not 100 tins of tuna)? Then, briefly, the rest of the stores. ' +
        'Only item names and amounts are sent. About 0.3p a go.</p>' +
        '<div class="btn-row"><button class="btn" data-act="stock-review">🤖 Review my stores</button></div></section>';
    }
    var when = v.made_at ? new Date(v.made_at) : null;
    return '<section class="card review-card">' + head + '<p class="small muted review-aim">Food with no mains water, power, gas or fridge</p>' +
      '<p class="review-text">' + esc(v.summary) + '</p>' +
      (v.wider ? '<p class="small"><b>The rest of the stores:</b> ' + esc(v.wider) + '</p>' : '') +
      (v.suggestions && v.suggestions.length ? '<ul class="review-list">' + v.suggestions.map(function (g, n) {
        return '<li><span class="review-ico" aria-hidden="true">' + cat(g.category).icon + '</span><span class="review-main"><b>' + esc(g.add) + '</b>' +
          (g.why ? '<span class="small muted"> ' + esc(g.why) + '</span>' : '') + '</span>' +
          (onSupplyRun(g) ? '<button class="btn small" disabled>✓ On the list</button>'
            : '<button class="btn small" data-act="review-add" data-n="' + n + '">+ Supply run</button>') + '</li>';
      }).join('') + '</ul>' : '') +
      '<div class="btn-row"><button class="btn small" data-act="stock-review">🤖 Review again</button>' +
      '<span class="small muted">' + (when ? 'Reviewed ' + esc(when.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })) + ' · ' : '') + srN(v.items || 0, 'item', 'items') + ' looked at</span></div></section>';
  }
  // ------------------------------------------------------------------
  // The daily briefing (1.15.0): one paragraph at 6am on what to be aware of, locally, across the UK and in the world.
  // ------------------------------------------------------------------
  var BRIEF_STATE = { 1: 'good', 2: 'good', 3: 'warn', 4: 'bad', 5: 'bad' };
  var briefTimer = null;
  function safeHref(u) { return /^https?:\/\/[^\s"'<>]+$/.test(u || '') ? u : ''; }
  function briefWhen(b) {
    var d = new Date(b.made_at), today = new Date().toISOString().slice(0, 10);
    var t = isNaN(d) ? '' : d.toLocaleTimeString('en-GB', { hour: 'numeric', minute: '2-digit' });
    return (b.day === today ? 'Today' : fmtDate(b.day)) + (t ? ', ' + t : '');
  }
  function briefChip(B, b, k, label) {
    var n = (b.levels || {})[k];
    if (!n) return '';
    var vs = (b.vs_usual || {})[k];
    return '<span class="brief-chip" data-state="' + (BRIEF_STATE[n] || 'good') + '"><b>' + esc(label) + '</b> ' + esc(B.levels[n] || n) +
      (vs && vs !== 'same' ? ' <span class="brief-vs">' + (vs === 'higher' ? '↑ above usual' : '↓ below usual') + '</span>' : '') + '</span>';
  }
  function briefCard() {
    var B = S.briefing;
    if (!B || !B.config.on || !B.available) return '';
    var b = B.latest;
    clearTimeout(briefTimer);
    if (B.busy) briefTimer = setTimeout(function () { refresh(); }, 8000);
    var head = '<div class="card-head"><h2>Daily briefing</h2>' + (b ? '<span class="small muted">' + esc(briefWhen(b)) + '</span>' : '') + '</div>';
    if (!b) {
      return '<section class="card brief-card">' + head + '<p class="small muted">' +
        (B.busy ? 'Writing your first briefing: searching the news. This takes a minute or two…' : B.error ? esc(B.error) : 'Your first briefing comes at ' + B.hour + 'am.') + '</p></section>';
    }
    var stale = b.day !== new Date().toISOString().slice(0, 10) && new Date().getHours() >= B.hour;
    var src = (b.sources || []).map(function (x) {
      var u = safeHref(x.url);
      return u ? '<li><a href="' + esc(u) + '" target="_blank" rel="noopener noreferrer">' + esc(x.title) + '</a></li>' : '';
    }).join('');
    return '<section class="card brief-card">' + head +
      '<div class="brief-chips">' + briefChip(B, b, 'local', 'Local') + briefChip(B, b, 'national', 'UK') + briefChip(B, b, 'global', 'World') + '</div>' +
      '<p class="brief-text">' + esc(b.text) + '</p>' +
      (B.busy ? '<p class="small muted">Writing a new one…</p>' : stale && B.error ? '<p class="small err">Today\'s didn\'t come through: ' + esc(B.error) + '</p>' : '') +
      (src ? '<details class="brief-src"><summary>Sources (' + (b.sources || []).length + ')' + (b.searched && b.searched.length ? ' and searches' : '') + '</summary><ul>' + src + '</ul>' +
        (b.searched && b.searched.length ? '<p class="small muted">Searched: ' + b.searched.map(esc).join(' · ') + '</p>' : '') + '</details>' : '') +
      '<p class="small muted brief-foot">Written by AI from the news and Dads Army\'s live data. Check anything important with the official source.</p></section>';
  }
  // HQ: switch it on, choose how thorough, and where "local" is.
  function briefHqCard() {
    var B = S.briefing;
    if (!B) return '';
    var c = B.config;
    var html = '<section class="card" id="briefCard"><div class="card-head"><h2>Daily briefing</h2>' + (c.on && B.available ? pill('good', 'On') : pill('plain', 'Off')) + '</div>' +
      '<p class="small muted">Every morning at ' + B.hour + 'am, Claude reads your warnings and the wider picture, searches the news, and writes one paragraph on threats and risks to be aware of: ' +
      'locally, across the UK and in the world (weather, conflict, cyber, health, power, supply and more), compared with what\'s been usual lately. It\'s shown at the top of the Sitrep.</p>';
    if (!B.available) {
      return html + '<p class="small">Needs an Anthropic API key: choose <b>Anthropic Claude</b> under Scanning above and paste your key. (The news search runs on Anthropic\'s side, so the other AIs can\'t do this.)</p></section>';
    }
    html += '<label class="opt"><input type="checkbox" data-brief="on"' + (c.on ? ' checked' : '') + '><span><b>Daily briefing</b>' +
      '<span class="small muted">Uses your Anthropic key and counts towards the monthly AI limit above.</span></span></label>' +
      '<label class="field"><span>How thorough</span><select data-brief="model">' +
      Object.keys(B.models).map(function (k) { return '<option value="' + k + '"' + (k === c.model ? ' selected' : '') + '>' + esc(B.models[k].name + ': ' + B.models[k].about) + '</option>'; }).join('') +
      '</select></label>' +
      '<label class="field"><span>Local news for</span><input type="text" data-brief="area" autocomplete="off" maxlength="60" value="' + esc(c.area) + '" placeholder="' + esc(B.area_auto) + '">' +
      '<div class="hint">A town or county. Left empty, it\'s ' + esc(B.area_auto) + ' (your Met Office region). This name, the day\'s warnings and wider picture, and how long your stores last are sent to Anthropic.</div></label>';
    if (c.on) {
      var b = B.latest;
      html += '<p class="small muted">' + (B.busy ? 'Writing one now…' : b ? 'Last one: ' + esc(briefWhen(b)) + ', ' + (b.searches || 0) + ' searches, ' + esc(usd(b.cost_usd)) + '.' : 'None yet.') + '</p>' +
        (B.error ? '<p class="small ha-error">' + esc(B.error) + '</p>' : '') +
        '<div class="btn-row"><button class="btn" data-act="brief-now"' + (B.busy ? ' disabled' : '') + '>Write one now</button></div>';
    }
    return html + '</section>';
  }
  function redrawBrief() { var el = $('#briefCard'); if (el) el.outerHTML = briefHqCard(); }
  document.addEventListener('change', function (e) {
    var t = e.target, k = t.dataset && t.dataset.brief;
    if (!k) return;
    var body = {};
    body[k] = k === 'on' ? t.checked : t.value;
    api('PUT', 'api/briefing', body).then(function (r) {
      S.briefing = r; redrawBrief();
      toast(k === 'on' ? (r.config.on ? (r.busy ? 'On: writing today\'s briefing now' : 'Daily briefing on') : 'Daily briefing off') : 'Saved');
      if (r.busy) setTimeout(refresh, 8000);
    }, function (err) { toast(err.message, { error: true }); if (k === 'on') t.checked = !t.checked; });
  });

  function renderSitrep(el) {
    if (!S.items.length) { el.innerHTML = watchCard() + briefCard() + levelCard() + warnCard(false) + liveCard() + emptyCard() + resilienceCard(); return; }
    var st = S.settings, r = readiness(), target = st.target_days;
    var html = watchCard() + briefCard() + levelCard() + dashNote() + warnCard(false) + liveCard() + resilienceCard();

    // Hero: how long could we hold out?
    if (r.people === 0) {
      html += '<section class="card hero"><div class="eyebrow">Situation report</div><p style="margin-top:10px">Tell HQ who you\'re feeding to see how long your stores will last.</p><button class="btn primary" data-tab="hq">Set up household</button></section>';
    } else {
      var hs = stateOf(r.hold / target);
      var limit = r.limit === 'food' ? 'Food runs out first' : r.limit === 'water' ? 'Water runs out first' : '';
      var foodNote = nf0.format(r.kcal) + ' kcal stored · ' + nf0.format(r.kcalDay) + ' needed a day';
      if (r.foodOldDays >= 0.1) foodNote += ' · +' + fmtDays(r.foodOldDays) + ' days in expired stock';
      if (r.foodWaste >= 0.5) foodNote += ' · ' + fmtDays(r.foodWaste) + ' days\' worth goes off before you\'d get to it';
      if (r.kcalDay > 0 && r.coldKcal / r.kcalDay >= 0.1) foodNote += ' · ' + fmtDays(r.coldKcal / r.kcalDay) + ' days of the food needs a fridge or freezer: eat it first in a power cut';
      if (r.noKcal) foodNote += ' · ' + r.noKcal + ' item' + (r.noKcal === 1 ? '' : 's') + ' with no calories set <button class="link" data-act="ai-fill">Fill in with AI</button>';
      var waterNote = fq(Math.round(r.litres * 10) / 10) + ' L stored · ' + fq(Math.round(r.waterDay * 10) / 10) + ' L needed a day' +
        (r.petWater > 0 ? ' (' + fq(Math.round(r.petWater * 10) / 10) + ' L for the pets)' : '');
      if (r.waterOldDays >= 0.1) waterNote += ' · +' + fmtDays(r.waterOldDays) + ' days past best-before';
      if (r.waterWaste >= 0.5) waterNote += ' · ' + fmtDays(r.waterWaste) + ' days\' worth passes its date first';
      if (r.drinkLitres >= 0.5) waterNote += ' · plus ' + fq(Math.round(r.drinkLitres * 10) / 10) + ' L of juice, milk and other drinks, counted for drinking only (up to ' + fq(DRINK_CAP) + ' L a person a day), not cooking or washing';
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
        petMeter(target) + '</div></section>';
    }
    html += trendsCard();

    // Alert tiles
    var cnt = { bad: 0, warn: 0, low: 0 };
    S.items.forEach(function (it) {
      var i = info(it);
      if (i.exp === 'bad') cnt.bad++; else if (i.exp === 'warn') cnt.warn++;
      if (i.low) cnt.low++;
    });
    html += '<div class="tiles">' +
      tile(cnt.bad, 'Expired', 'bad', 'expired') +
      tile(cnt.warn, Object.keys(st.warn_by_cat || {}).length ? 'Expiring soon' : 'Expiring in ' + st.warn_days + ' days', 'warn', 'soon') +
      tile(cnt.low, 'Below target', 'warn', 'low') + '</div>';

    // Use first
    var upcoming = [];
    S.items.forEach(function (it) {
      it.batches.forEach(function (b) { if (b.expiry && b.qty > 0) upcoming.push({ it: it, b: b }); });
    });
    upcoming.sort(function (a, b) { return a.b.expiry < b.b.expiry ? -1 : a.b.expiry > b.b.expiry ? 1 : 0; });
    var urgent = upcoming.filter(function (x) { return expState(x.b.expiry, x.it.category) !== 'ok'; });
    var showList = (urgent.length ? urgent : upcoming).slice(0, 6);
    if (showList.length) {
      html += '<section class="card flush"><div class="card-head"><h2>' + (urgent.length ? 'Use these first' : 'Next to expire') + '</h2>' +
        (upcoming.length > showList.length ? '<button class="link" data-act="go" data-show="all" data-sort="expiry">See all</button>' : '') + '</div><div class="list">';
      showList.forEach(function (x) {
        var es = expState(x.b.expiry, x.it.category);
        html += '<div class="li"><span class="li-ico">' + cat(x.it.category).icon + '</span>' +
          '<button class="li-main" data-act="open" data-id="' + x.it.id + '"><div class="li-title">' + esc(x.it.name) + '</div>' +
          '<div class="li-sub"><span class="badge ' + (es === 'ok' ? 'plain' : es) + '">' + esc(expiryWords(x.b.expiry)) + '</span>' +
          '<span>' + esc(qu(x.b.qty, x.it.unit)) + (x.b.location ? ' · ' + esc(x.b.location) : '') + '</span></div></button>' +
          '<button class="qbtn" data-act="use" data-id="' + x.it.id + '" aria-label="Use one ' + esc(x.it.name) + '">' + ICON.minus + '</button></div>';
      });
      html += '</div></section>';
    }

    html += timelineCard();
    html += reviewCard();

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
      var met = tg.filter(function (it) { return inDate(it) >= it.target_qty; }).length;
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

  // Expiry timeline: batches in stock by the month they go out of date, for a year, after a column for what
  // already has. Spots a month where a lot goes at once, in time to use it or swap it out.
  function timelineCard() {
    var now = new Date(), y = now.getFullYear(), m = now.getMonth(), cols = [], later = 0, k;
    cols.push({ label: 'Past', long: 'Already out of date', bad: 0, warn: 0, ok: 0, show: 'expired' });
    for (k = 0; k < 12; k++) {
      var md = new Date(y, m + k, 1);
      cols.push({ label: md.toLocaleDateString('en-GB', { month: 'short' }), long: md.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }),
        bad: 0, warn: 0, ok: 0, show: 'all' });
    }
    S.items.forEach(function (it) {
      it.batches.forEach(function (b) {
        if (!b.expiry || !(b.qty > 0)) return;
        var es = expState(b.expiry, it.category);
        if (es === 'bad') { cols[0].bad++; return; }
        var bd = parseYmd(b.expiry), idx = (bd.getFullYear() - y) * 12 + bd.getMonth() - m;
        if (idx >= 12) { later++; return; }
        cols[idx + 1][es]++;
      });
    });
    var sum = function (c) { return c.bad + c.warn + c.ok; };
    var most = Math.max.apply(null, cols.map(sum));
    if (!most) return '';   // nothing with a date in the next year: no chart to show
    var tot = { bad: 0, warn: 0, ok: 0 };
    var bars = cols.map(function (c) {
      var n = sum(c);
      tot.bad += c.bad; tot.warn += c.warn; tot.ok += c.ok;
      // Each part's height is its share of the busiest month, so the months can be compared by eye.
      var part = function (state, v) { return v ? '<i class="tl-' + state + '" style="height:' + (v / most * 100).toFixed(1) + '%"></i>' : ''; };
      var lab = c.long + ': ' + (n ? srN(n, 'batch', 'batches') + (c.warn && c.ok ? ', ' + c.warn + ' expiring soon' : '') : 'nothing') + '. Open the stores, soonest first';
      return '<button class="tl-col" data-act="go" data-show="' + c.show + '" data-sort="expiry" aria-label="' + esc(lab) + '">' +
        '<span class="tl-n">' + (n || '') + '</span><span class="tl-bar">' + part('ok', c.ok) + part('warn', c.warn) + part('bad', c.bad) + '</span>' +
        '<span class="tl-lab">' + esc(c.label) + '</span></button>';
    }).join('');
    return '<section class="card timeline-card"><div class="card-head"><h2>Expiry timeline</h2>' +
      '<button class="link" data-act="go" data-show="all" data-sort="expiry">Soonest first</button></div>' +
      '<p class="small muted">Batches in stock by the month they go out of date, to ' + esc(cols[12].long) + '.</p>' +
      '<div class="tl-cols">' + bars + '</div>' +
      '<div class="legend"><span><i class="tl-bad"></i>Out of date (' + tot.bad + ')</span><span><i class="tl-warn"></i>Expiring soon (' + tot.warn + ')</span>' +
      '<span><i class="tl-ok"></i>Fine (' + tot.ok + ')</span>' + (later ? '<span class="muted">+ ' + srN(later, 'batch', 'batches') + ' after that</span>' : '') +
      '</div></section>';
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
        '<div class="search-row"><div class="search">' + ICON.search + '<input type="search" id="q" placeholder="Search item, place or note" autocomplete="off" enterkeyhint="search" aria-label="Search stores"></div>' +
        '<button class="btn scan-btn" data-act="scan" aria-label="Scan a barcode">📷<span> Scan</span></button></div>' +
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
    if (i.out && it.target_qty > 0) badges += '<span class="badge bad">' + (i.none ? 'Out' : 'Replace') + '</span>';
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
    if (i.old > 0 && it.target_qty > 0) amount += ' <span class="old">(' + fq(i.old) + ' out of date)</span>';
    var left = daysLeft(it);
    var lasts = left > 0 ? '<span>· lasts ' + esc(lastsWords(left)) + '</span>' : '';
    var body = (showIcon ? '<span class="row-ico">' + cat(it.category).icon + '</span>' : '') +
      '<span class="row-text"><span class="row-name">' + esc(it.name) +
      (it.storage === 'chilled' || it.storage === 'frozen' ? ' <span class="st-cold" title="' + (it.storage === 'chilled' ? 'Kept in the fridge' : 'Kept in the freezer') + '">' + (it.storage === 'chilled' ? '❄️' : '🧊') + '</span>' : '') + '</span>' +
      '<span class="row-sub"><span>' + amount + '</span>' + (where ? '<span>· ' + esc(where) + '</span>' : '') + lasts + badges + '</span></span>';
    if (SEL) {   // picking items to delete: the whole row is a tick box
      var on = !!SEL[it.id];
      return '<div class="row' + (on ? ' picked' : '') + (i.none ? ' is-out' : '') + '">' +
        '<button class="row-main" role="checkbox" aria-checked="' + on + '" data-act="sel-toggle" data-id="' + it.id + '">' +
        '<span class="box">' + ICON.check + '</span>' + body + '</button></div>';
    }
    return '<div class="row' + (i.none ? ' is-out' : '') + '">' +
      '<button class="row-main" data-act="open" data-id="' + it.id + '">' + body + '</button>' +
      '<div class="row-ctl">' +
      '<button class="qbtn" data-act="use" data-id="' + it.id + '" aria-label="Use one ' + esc(it.name) + '"' + (i.none ? ' disabled' : '') + '>' + ICON.minus + '</button>' +
      '<button class="qbtn add" data-act="stock" data-id="' + it.id + '" aria-label="Add ' + esc(it.name) + '">' + ICON.plus + '</button>' +
      '</div></div>';
  }

  // Wall tablets and wide screens: the stores as a table, sortable by its column headings.
  var WIDE = window.matchMedia ? window.matchMedia('(min-width: 900px)') : { matches: false };
  function isWide() { return WIDE.matches; }
  function tableRow(it, i, showCat) {
    var badges = '';
    if (i.exp === 'bad') badges += '<span class="badge bad">Expired</span>';
    else if (i.exp === 'warn') badges += '<span class="badge warn">' + esc(shortLeft(i.soonest)) + '</span>';
    if (i.out && it.target_qty > 0) badges += '<span class="badge bad">' + (i.none ? 'Out' : 'Replace') + '</span>';
    else if (i.low) badges += '<span class="badge warn">Low</span>';
    if (!badges && it.target_qty > 0) badges = '<span class="badge ok">At target</span>';
    var locs = {};
    it.batches.forEach(function (b) { if (b.location) locs[b.location] = 1; });
    var lk = Object.keys(locs);
    var left = daysLeft(it), use = (S.usage || {})[String(it.id)];
    var lasts = left > 0 ? lastsWords(left) : left === 0 ? 'Run out' : use && use.lasts_days != null ? lastsWords(use.lasts_days) + ' at your rate' : '';
    var unit = isMoney(it.unit) ? '' : ' ' + plural(it.unit, i.total);
    var qty = (isMoney(it.unit) ? it.unit : '') + fq(i.total) + (it.unit && !isMoney(it.unit) ? unit : '');
    return '<tr class="' + (i.none ? 'is-out' : '') + '">' +
      '<td class="t-name"><button data-act="open" data-id="' + it.id + '">' + (showCat ? '' : '<span class="t-ico">' + cat(it.category).icon + '</span>') +
      esc(it.name) + '</button></td>' +
      (showCat ? '' : '<td class="t-cat">' + esc(cat(it.category).label) + '</td>') +
      '<td class="num"><b>' + esc(qty) + '</b>' + (i.old > 0 ? '<span class="old"> (' + fq(i.old) + ' old)</span>' : '') + '</td>' +
      '<td class="num">' + (it.target_qty > 0 ? esc(fq(it.target_qty)) : '–') + '</td>' +
      '<td>' + (i.soonest ? esc(fmtDate(i.soonest)) : '<span class="muted">–</span>') + '</td>' +
      '<td>' + (lk.length ? esc(lk.length === 1 ? lk[0] : lk.join(', ')) : '<span class="muted">–</span>') + '</td>' +
      '<td>' + (lasts ? esc(lasts) : '<span class="muted">–</span>') + '</td>' +
      '<td class="t-badges">' + badges + '</td>' +
      '<td class="t-ctl"><button class="qbtn" data-act="use" data-id="' + it.id + '" aria-label="Use one ' + esc(it.name) + '"' + (i.none ? ' disabled' : '') + '>' + ICON.minus + '</button>' +
      '<button class="qbtn add" data-act="stock" data-id="' + it.id + '" aria-label="Add ' + esc(it.name) + '">' + ICON.plus + '</button></td></tr>';
  }
  function tableHtml(list) {
    var grouped = F.sort === 'category';
    function head(key, label, cls) {
      var on = F.sort === key || (key === 'name' && grouped);
      return '<th' + (cls ? ' class="' + cls + '"' : '') + (key ? ' aria-sort="' + (F.sort === key ? 'ascending' : 'none') + '"' : '') + '>' +
        (key ? '<button data-act="sort" data-sort="' + key + '"' + (on ? ' class="on"' : '') + '>' + label + '</button>' : label) + '</th>';
    }
    var cols = grouped ? 8 : 9;
    var h = '<div class="table-wrap"><table class="stock-table"><thead><tr>' + head(grouped ? 'category' : 'name', 'Item') +
      (grouped ? '' : head('category', 'Category')) + head('', 'In stock', 'num') + head('', 'Target', 'num') +
      head('expiry', 'Best before') + head('', 'Where') + head('', 'Lasts') + head('short', 'Status') + '<th class="t-ctl"></th></tr></thead><tbody>';
    var cur = null;
    list.forEach(function (x) {
      if (grouped && x.it.category !== cur) {
        cur = x.it.category;
        var n = list.filter(function (y) { return y.it.category === cur; }).length;
        h += '<tr class="group"><td colspan="' + cols + '">' + cat(cur).icon + ' ' + esc(cat(cur).label) + ' <span class="n">' + n + '</span></td></tr>';
      }
      h += tableRow(x.it, x.i, grouped);
    });
    return h + '</tbody></table></div>';
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
    if (isWide() && !SEL) {
      html += tableHtml(list);
    } else if (F.sort === 'category') {
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
      '<p class="small muted">Everything below target, plus anything you add. Back from the shops? Tap <b>Got it</b> to put it in the stores ' +
      '(for something you added, that makes it a new item and takes it off the list).' +
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
          '<div class="need">Get <b>' + esc(qu(x.i.short, x.it.unit)) + '</b> · have ' + esc(fq(x.i.good)) + ' of ' + esc(fq(x.it.target_qty)) +
          (x.i.old > 0 ? ' · ' + esc(fq(x.i.old)) + ' out of date' : '') +
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
        (s.done ? '' : '<button class="btn small" data-act="shop-got" data-id="' + s.id + '" aria-label="Got it: add ' + esc(s.text) + ' to the stores">Got it</button>') +
        '<button class="icon-btn" data-act="shop-edit" data-id="' + s.id + '" aria-label="Change ' + esc(s.text) + '">' + ICON.edit + '</button>' +
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
    el.innerHTML = warnCard(true) + html + '</section>' + planCard() + placesCard();
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
  // Places to go: possible refuges near home (worked out on the Pi from a UK list that
  // ships with the app), plus your own places. Drawn here without any map service.
  // ------------------------------------------------------------------
  var OWN_KIND_OPTS = [['family', 'Family or friends', '🏠'], ['meet', 'Meeting place', '🚩'], ['other', 'Somewhere else', '📌']];
  function PL() { return S.places || { home: null, own: [], hazards: [], help: [], map: [], active: [] }; }
  function fmtKm(k) { return (k < 1 ? fq(k) : fq(Math.round(k))) + ' km'; }
  function placesPlot(p) {
    var home = p.home, pts = p.map.filter(function (x) { return x.km <= 20; });
    var far = Math.max.apply(null, [0.5].concat(pts.map(function (x) { return x.km; })));
    var R = [0.5, 1, 2, 3, 5, 7.5, 10, 15, 20].filter(function (r) { return r >= far; })[0] || 20;
    var k = 128 / R, cos = Math.cos(home.lat * Math.PI / 180);
    var svg = '<svg class="places-plot" viewBox="-150 -150 300 300" role="img" aria-label="Places near home, up to ' + fmtKm(R) + ' away">' +
      '<circle r="128" class="pp-ring"/><circle r="64" class="pp-ring"/>' +
      '<line x1="0" y1="-140" x2="0" y2="140" class="pp-axis"/><line x1="-140" y1="0" x2="140" y2="0" class="pp-axis"/>' +
      '<text x="0" y="-141" class="pp-n">N</text>' +
      '<text x="5" y="76" class="pp-km">' + fmtKm(R / 2) + '</text><text x="5" y="140" class="pp-km">' + fmtKm(R) + '</text>';
    pts.forEach(function (x) {
      var px = (x.lon - home.lon) * cos * 111.32 * k, py = -(x.lat - home.lat) * 110.57 * k;
      svg += '<text x="' + px.toFixed(1) + '" y="' + py.toFixed(1) + '" class="pp-pt"><title>' + esc(x.name + ' · ' + x.text) + '</title>' + x.emoji + '</text>';
    });
    return svg + '<text x="0" y="0" class="pp-pt pp-home"><title>Home</title>🏠</text></svg>';
  }
  function placeRow(x) {
    return '<div class="li place-row"><span class="li-ico">' + x.emoji + '</span><span class="li-main">' +
      '<span class="li-title wrap">' + (x.own ? '⭐ ' : '') + esc(x.name) + '</span>' +
      '<span class="li-sub">' + esc(x.text || '') + (x.notes ? ' · ' + esc(x.notes) : '') + '</span></span>' +
      (x.map ? '<a class="btn small" href="' + esc(x.map) + '" target="_blank" rel="noopener noreferrer">Map</a>' : '') + '</div>';
  }
  function hazardRow(h) {
    var top = h.places[0];
    return '<details class="hz' + (h.active ? ' now' : '') + '"' + (h.active ? ' open' : '') + '><summary>' +
      '<span class="hz-ico">' + h.emoji + '</span><span class="hz-main"><span class="hz-what">' + esc(h.what) +
      (h.active ? ' <span class="badge warn">Now</span>' : '') + '</span>' +
      '<span class="hz-top">' + (top ? (top.own ? '⭐ ' : '') + esc(top.name) + ' · ' + esc(top.short) : 'Stay indoors, or go to family or friends') + '</span></span>' +
      ICON.chev + '</summary><p class="small">' + esc(h.advice) + '</p>' +
      (h.avoiding ? '<p class="small muted">Leaving out places nearer ' + esc(h.avoiding) + ' than you are.</p>' : '') +
      (h.places.length ? '<div class="list">' + h.places.map(placeRow).join('') + '</div>' : '') + '</details>';
  }
  function placesCard() {
    var p = PL();
    var html = '<section class="card places-card"><div class="card-head"><h2>Places to go</h2>' +
      (p.home ? '<span class="small muted">if you have to leave home</span>' : '') + '</div>';
    if (!p.home) {
      return html + '<p class="small muted">Dads Army can suggest places near home to go in an emergency, such as high ground, leisure centres and community halls, ' +
        'and keep your own places like family and friends. First it needs to know where home is.' +
        (S.server.ha ? ' It uses Home Assistant\'s home location, or one you set in the warnings settings.' : '') + '</p>' +
        '<button class="btn block" data-act="warn-set">Set where home is</button>' + ownPlacesList(p) + '</section>';
    }
    return html + placesPlot(p) +
      '<p class="small muted center">Straight-line distances. Tap <b>Map</b> on a place for directions.</p>' +
      '<h3>If it\'s…</h3><div class="hz-list">' + p.hazards.map(hazardRow).join('') + '</div>' +
      (p.help.length ? '<h3>Help nearby</h3><div class="list">' + p.help.map(placeRow).join('') + '</div>' : '') +
      ownPlacesList(p) +
      '<p class="small muted" style="margin-top:12px">Suggestions come from a list of UK places that comes with Dads Army' + (p.built ? ' (' + esc(fmtDate(p.built)) + ')' : '') +
      ', so nothing is looked up online. They\'re possibilities, not official refuges: councils say where rest centres open at the time. ' +
      'Place data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>.' +
      (p.error ? ' <span class="err">' + esc(p.error) + '</span>' : '') + '</p></section>';
  }
  function ownPlacesList(p) {
    return '<h3>Your own places</h3>' + (p.own.length ? '<div class="list">' + p.own.map(function (x) {
      var k = OWN_KIND_OPTS.filter(function (o) { return o[0] === x.kind; })[0] || OWN_KIND_OPTS[2];
      var hz = (x.hazards || []).map(function (key) { var h = S.place_hazards.filter(function (y) { return y[0] === key; })[0]; return h ? h[2] : ''; }).join(' ');
      return '<button class="li" data-act="place-edit" data-id="' + x.id + '"><span class="li-ico">' + k[2] + '</span><span class="li-main">' +
        '<span class="li-title wrap">' + esc(x.name) + '</span><span class="li-sub">' + esc(x.text || k[1]) + (hz ? ' · for ' + hz : '') + '</span></span>' + ICON.chev + '</button>';
    }).join('') + '</div>' : '<p class="small muted">Family and friends you could stay with, and your meeting places. They\'re shown first, and on the Home Assistant map.</p>') +
      '<button class="btn block" style="margin-top:10px" data-act="place-new">' + ICON.plus + ' Add a place</button>';
  }
  function ownList() {
    return PL().own.map(function (o) { return { name: o.name, lat: o.lat, lon: o.lon, kind: o.kind, hazards: o.hazards || [], notes: o.notes || '' }; });
  }
  function sheetPlace(s) {
    var own = PL().own, x = s.id ? own.filter(function (o) { return o.id === s.id; })[0] : null;
    if (s.id && !x) return null;
    var v = x || { name: '', kind: 'family', hazards: ['leave', 'unrest'], notes: '' };
    return sheetHead(x ? 'Edit place' : 'Add a place', 'Somewhere you could go in an emergency', '📌') +
      '<form id="placeForm" data-id="' + (x ? x.id : '') + '" novalidate>' +
      '<label class="field"><span>Name</span><input type="text" name="name" value="' + esc(v.name) + '" maxlength="80" placeholder="e.g. Gran\'s house" autocomplete="off"' + (x ? '' : ' data-autofocus') + '></label>' +
      '<label class="field"><span>Where is it?</span><input type="text" name="where" value="' + (x ? esc(x.lat + ', ' + x.lon) : '') + '" maxlength="600" placeholder="Paste a map link, or 54.48, -0.62" autocomplete="off" inputmode="url">' +
      '<div class="hint" id="whereHint">' + (x && x.text ? esc(x.text) + ' from home' : 'In Google Maps or Apple Maps, long-press the place, then copy the coordinates or share the link, and paste it here.') + '</div></label>' +
      '<fieldset class="field"><legend>What is it?</legend><div class="opts">' + OWN_KIND_OPTS.map(function (o) {
        return '<label class="opt"><input type="radio" name="kind" value="' + o[0] + '"' + (v.kind === o[0] ? ' checked' : '') + '><span>' + o[2] + ' ' + esc(o[1]) + '</span></label>';
      }).join('') + '</div></fieldset>' +
      '<fieldset class="field"><legend>Somewhere to go for…</legend><div class="opts">' + S.place_hazards.map(function (h) {
        return '<label class="opt"><input type="checkbox" name="hz" value="' + h[0] + '"' + ((v.hazards || []).indexOf(h[0]) >= 0 ? ' checked' : '') + '><span>' + h[2] + ' ' + esc(h[1]) + '</span></label>';
      }).join('') + '</div></fieldset>' +
      '<label class="field"><span>Notes</span><input type="text" name="notes" value="' + esc(v.notes || '') + '" maxlength="300" placeholder="Optional, e.g. key under the pot"></label>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + (x ? 'Save' : 'Add the place') + '</button>' +
      (x ? '<button class="btn danger block" type="button" data-act="place-del" data-id="' + x.id + '">' + ICON.trash + ' Delete</button>' : '') + '</div></form>';
  }
  function checkWhere(input) {
    var hint = $('#whereHint');
    if (!hint || !input.value.trim()) return;
    api('POST', 'api/places/where', { where: input.value }).then(function (r) {
      hint.className = 'hint';
      hint.textContent = r.km != null ? 'Found it: ' + fmtKm(r.km) + ' ' + r.dir + ' of home.' : 'Found it: ' + r.lat + ', ' + r.lon + '.';
    }, function (e) { hint.className = 'hint err'; hint.textContent = e.message; });
  }

  // ------------------------------------------------------------------
  // Warnings: Met Office, floods, Emergency Alerts, GDACS, UKHSA, WHO
  // ------------------------------------------------------------------
  var WARN_ICON = { weather: '🌦️', flood: '🌊', alert: '📢', disaster: '🌍', fire: '🔥', news: '🩺',
    river: '🏞️', power: '🔌', grid: '⚡', gas: '🔥', air: '🌫️', space: '☀️', money: '💷',
    threat: '🛡️', cyber: '💻', drought: '💧', water: '🚰' };
  var SRC_NAME = { metoffice: 'Met Office', floods: 'Environment Agency', govalerts: 'GOV.UK', gdacs: 'GDACS', fires: 'NASA FIRMS',
    ukhsa: 'UKHSA', who: 'WHO', rivers: 'Environment Agency', power: 'Power networks', grid: 'NESO', gas: 'National Gas',
    air: 'Defra UK-AIR', space: 'NOAA', pound: 'Bank of England', threat: 'GOV.UK', cyber: 'NCSC', travel: 'FCDO',
    drought: 'Environment Agency', water: 'Your water company', floodrisk: 'Flood Forecasting Centre', rain: 'Environment Agency',
    ground: 'Environment Agency', gridnow: 'NESO / Elexon', gridstress: 'Elexon / NESO' };
  var LIVE_KEYS = ['rivers', 'power', 'grid', 'gas', 'air', 'space', 'pound'];
  var LIVE_MORE = 'threat';   // 1.15.0's sources start here in the settings
  function W() {
    return S.warnings || { on: false, items: [], news: [], sources: {}, config: { sources: {} }, regions: [], source_list: [] };
  }
  function sevClass(s) { return s >= 3 ? 'bad' : s === 2 ? 'warn' : 'yellow'; }
  function srcName(k) { return SRC_NAME[k] || k; }
  function whoFrom(w) { return w.by || srcName(w.source); }   // a regional provider says who it's from: "SEPA"
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
      '<span class="li-sub"><span class="badge ' + sevClass(w.severity) + '">' + esc(w.level) + '</span><span>' + esc(whoFrom(w)) +
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

  // The wider picture: one line for each live feed (worked out on the Pi), green, amber or red.
  function liveRow(r) {
    return '<button class="li live-row" data-state="' + r.state + '" data-act="live-open" data-key="' + r.key + '">' +
      '<span class="li-ico">' + r.emoji + '</span><span class="li-main"><span class="li-title">' + esc(r.name) + '</span>' +
      '<span class="li-sub">' + esc(r.text) + '</span></span><span class="live-dot" aria-label="' +
      ({ good: 'Fine', warn: 'Worth watching', bad: 'Serious' }[r.state] || '') + '"></span></button>';
  }
  // 1.18.0: what's affecting home comes first, item by item, then the lines that need attention (worst first), then
  // the rest under headings. What counts as yours, and the order, are worked out on the Pi (affecting, live_layout),
  // so "Affecting you" lists exactly the warnings that turn a line amber or red, and never disagrees with it.
  function liveCard() {
    var w = W(), rows = w.live_rows || [], aff = w.affecting || { yours: [], near: [], near_count: 0 };
    if (!w.on || (!rows.length && !aff.yours.length)) return '';
    var byKey = {};
    rows.forEach(function (r) { byKey[r.key] = r; });
    var lay = w.live_layout || { attention: [], groups: [{ name: '', keys: rows.map(function (r) { return r.key; }) }] };
    var html = '<section class="card flush live-card"><div class="card-head"><h2>The wider picture</h2>' +
      '<button class="link" data-act="live-open">More</button></div>' + (w.location ? affectHtml(aff) : '');
    html += lay.attention.length
      ? '<h3 class="group-head">Needs attention <span class="n">' + lay.attention.length + '</span></h3><div class="list">' +
        lay.attention.map(function (k) { return liveRow(byKey[k]); }).join('') + '</div>'
      : rows.length ? '<p class="li live-calm small"><span class="li-ico" aria-hidden="true">✅</span><span class="li-main"><b>Nothing needs attention</b>' +
        '<span class="li-sub">Every line is clear. Tap one for its details.</span></span></p>' : '';
    html += lay.groups.map(function (g) {
      return (g.name ? '<h3 class="group-head">' + esc(g.name) + '</h3>' : '') + '<div class="list">' +
        g.keys.map(function (k) { return liveRow(byKey[k]); }).join('') + '</div>';
    }).join('');
    return html + '</section>';
  }
  function affectHtml(aff) {
    var html = !aff.yours.length
      ? '<div class="affect calm"><span class="ia-ico" aria-hidden="true">✅</span><span class="ia-main"><b>Nothing affecting you</b>' +
        '<span class="ia-sub">No water, power, flood or weather problems in your area right now.</span></span></div>'
      : '<div class="affect"><h3 class="group-head">Affecting you <span class="n">' + aff.yours.length + '</span></h3>' +
        aff.yours.map(function (x) { return affectRow(x, false); }).join('') + '</div>';
    if (aff.near.length) {
      var more = Math.max(aff.near_count, aff.near.length) - Math.min(3, aff.near.length);
      html += '<div class="affect"><h3 class="group-head">Nearby, not in your area <span class="n">' + Math.max(aff.near_count, aff.near.length) + '</span></h3>' +
        aff.near.slice(0, 3).map(function (x) { return affectRow(x, true); }).join('') +
        (more > 0 ? '<button class="ia-more" data-act="live-open" data-key="' + esc(aff.near[0].key) + '">and ' + more + ' more</button>' : '') + '</div>';
    }
    return html;
  }
  // One thing affecting home: what it is, then how serious, how far, the postcodes (a power cut), when it started or
  // is expected back, and the first sentence of the details. Tapping it opens that source's details.
  function affectRow(x, near) {
    var lvl = x.level && x.title.toLowerCase().indexOf(x.level.toLowerCase()) !== 0 ? x.level : '';
    var km = x.distance_km == null ? '' : x.distance_km < 1 ? 'under 1 km away' : fq(x.distance_km) + ' km away';
    var when = x.back_by ? 'back by ' + x.back_by : x.started ? 'started ' + ago(x.started) : x.when;
    // The details' first sentence, unless it only repeats the distance or the time back (a power cut's text starts so).
    var detail = x.detail && !/\bkm\b/i.test(x.detail) && !(x.back_by && x.detail.indexOf(x.back_by) >= 0) ? x.detail : '';
    var bits = [near ? '' : lvl, km, x.postcodes, when, detail].filter(Boolean);
    var act = x.key ? 'data-act="live-open" data-key="' + esc(x.key) + '"' : 'data-act="warn-open" data-i="' + x.i + '"';
    return '<button class="ia-row' + (near ? ' near' : ' sev' + x.severity) + '" ' + act + '>' +
      '<span class="ia-ico" aria-hidden="true">' + (WARN_ICON[x.kind] || '⚠️') + '</span>' +
      '<span class="ia-main"><span class="ia-title">' + esc(x.title) + '</span><span class="ia-sub">' + esc(bits.join(' · ')) + '</span></span>' +
      ICON.chev + '</button>';
  }

  // Things to watch (1.17.0): counts from the live sources that are well up on the last two weeks, at the top of
  // the Sitrep. Each opens the wider picture at its source, where the chart shows the rise.
  function watchCard() {
    var w = W(), t = w.on ? (w.trends || []) : [];
    if (!t.length) return '';
    return '<section class="card flush watch-card" aria-label="Things to watch"><div class="card-head"><h2>Things to watch</h2></div><div class="list">' +
      t.map(function (x) {
        return '<button class="li live-row" data-state="warn" data-act="live-open" data-key="' + esc(x.source) + '">' +
          '<span class="li-ico">📈</span><span class="li-main"><span class="li-title wrap">' + esc(x.title) + '</span>' +
          '<span class="li-sub">' + esc(x.text) + '</span></span>' + ICON.chev + '</button>';
      }).join('') + '</div></section>';
  }
  // The counts behind the trends, fetched when the wider picture opens (and kept for a few minutes).
  var LIVEHIST = { data: null, at: 0, loading: false };
  function loadLiveHistory() {
    if (LIVEHIST.loading || (LIVEHIST.data && Date.now() - LIVEHIST.at < 5 * 60000)) return;
    LIVEHIST.loading = true;
    api('GET', 'api/live/history').then(function (res) {
      LIVEHIST.data = res; LIVEHIST.at = Date.now(); LIVEHIST.loading = false;
      var top = stack[stack.length - 1];
      if (top && top.type === 'live') renderSheet();
    }, function () { LIVEHIST.loading = false; });
  }
  function trendNotes(source) {
    return (W().trends || []).filter(function (t) { return t.source === source; }).map(function (t) {
      return '<p class="callout small">📈 <b>' + esc(t.title) + '</b>. ' + esc(t.text) + '</p>';
    }).join('');
  }
  // One chart for each count a source keeps: the same line chart as the Trends card, with the usual as a dashed line.
  function countCharts(metrics) {
    return metrics.map(function (m) {
      var have = m.rows.filter(function (r) { return r.value >= 0; });
      var h = '<h4 class="count-h">' + esc(m.name) + ', a day at a time</h4>';
      if (have.length < 2) return h + '<p class="small muted">This fills in a day at a time: come back in a day or two.</p>';
      var vals = have.map(function (r) { return r.value; }), last = have[have.length - 1];
      var label = m.name + ', the highest each day over the last ' + have.length + ' days: from ' + fq(Math.min.apply(null, vals)) +
        ' to ' + fq(Math.max.apply(null, vals)) + ', ' + fq(last.value) + ' on ' + fmtDate(last.day) +
        (m.usual != null ? ', usually ' + fq(m.usual) : '');
      return h + lineChart('count-' + m.key, m.rows, [{ key: 'value', name: 'Count', color: '--series-1' }],
        { label: label, target: m.usual || 0, targetLabel: 'Usual', whole: true, width: Math.min(chartWidth(), 600) });
    }).join('');
  }

  function liveDetail(key, r) {
    var h = '';
    if (key === 'rivers') {
      if (!r.stations.length) return '<p class="small muted">No river gauges within 10 km of home. The Environment Agency\'s gauges cover England (and a few over the Welsh border), and SEPA\'s Scotland.</p>';
      h += '<table class="live-table"><thead><tr><th>Gauge</th><th>Level</th><th>Usual</th><th>Now</th></tr></thead><tbody>' +
        r.stations.map(function (x) {
          return '<tr data-state="' + (x.state === 'very_high' ? 'bad' : x.state === 'high' ? 'warn' : 'good') + '"><td><a href="' + esc(x.url) +
            '" target="_blank" rel="noopener noreferrer">' + esc(x.where) + '</a><br><span class="small muted">' + esc(fq(x.km)) + ' km ' + esc(x.dir) + '</span></td>' +
            '<td class="num">' + esc(fq(x.level)) + ' m</td><td class="num">' + (x.high != null ? esc(fq(x.low != null ? x.low : 0)) + '–' + esc(fq(x.high)) + ' m' : '–') + '</td>' +
            '<td>' + esc({ very_high: 'Very high', high: 'High', normal: 'Normal', low: 'Low', unknown: '–' }[x.state]) +
            (x.trend !== 'steady' ? ', ' + esc(x.trend) : '') + '</td></tr>';
        }).join('') + '</tbody></table>' +
        '<p class="small muted">“Usual” is the range the river is in most of the time (for SEPA\'s gauges in Scotland, between its usual yearly low and high). Rising or falling compares the level with 2 to 6 hours ago.</p>';
    } else if (key === 'power') {
      h += r.cuts.length ? '<div class="list">' + r.cuts.map(function (c) {
        return '<div class="li"><span class="li-ico">' + (c.planned ? '🛠️' : '🔌') + '</span><span class="li-main"><span class="li-title wrap">' + esc(c.text) + '</span>' +
          '<span class="li-sub">' + esc(c.dno) + (c.customers ? ' · ' + c.customers + ' home' + (c.customers === 1 ? '' : 's') : '') + '</span></span></div>';
      }).join('') + '</div>' : '<p class="small muted">No power cuts reported within ' + (r.within_km || 10) + ' km.</p>';
      if (r.no_feed) {
        h += '<p class="callout info small">' + esc(r.no_feed) + ', your network, only publishes its live power cuts to registered users, so they can\'t be shown here. ' +
          (r.no_feed_url ? '<a href="' + esc(r.no_feed_url) + '" target="_blank" rel="noopener noreferrer">See its power cut map</a>, or call 105.' : 'Call 105.') + '</p>';
      }
      if ((r.failed || []).length) h += '<p class="small err">Couldn\'t check ' + esc(r.failed.join(', ')) + ' this time. The others are still shown.</p>';
      h += '<p class="small muted">Power cut? Call <b>105</b>, free from any phone, to report it or get updates. Covers UK Power Networks, National Grid, SSEN and Northern Powergrid everywhere, ' +
        'and Electricity North West and NIE Networks near their own networks. SP Energy Networks doesn\'t publish its live power cuts openly.</p>';
    } else if (key === 'grid') {
      h += (r.status === 'normal' ? '<p>' + esc(r.text) + '</p>' : '') + '<p class="small muted">NESO runs Britain\'s electricity system. A margin or capacity market notice asks power stations for more; ' +
        'a warning of demand control means planned rota power cuts may be needed. None of these have meant power cuts in recent years.</p>';
    } else if (key === 'gas') {
      h += '<p>Britain\'s gas storage is <b>' + esc(fq(r.pct)) + '% full</b> (' + esc(fq(r.gwh)) + ' GWh)' +
        (r.year_ago_pct != null ? ', against ' + esc(fq(r.year_ago_pct)) + '% this time last year' : '') + '.</p>' +
        (r.draw_gwh_day != null ? '<p>Over the last two weeks it has ' + (r.draw_gwh_day >= 0 ? 'gone down' : 'gone up') + ' by about ' + esc(fq(Math.abs(Math.round(r.draw_gwh_day)))) + ' GWh a day' +
          (r.year_ago_draw != null ? ', against ' + esc(fq(Math.round(r.year_ago_draw))) + ' a year ago' : '') + '.</p>' : '') +
        '<p class="small muted">Storage is a small part of Britain\'s gas: most comes from the North Sea, Norway and shipped-in LNG. Dads Army warns if it\'s emptying much faster than last year, or nearly empty in winter.</p>';
    } else if (key === 'air') {
      h += r.index ? '<p>Air pollution is <b>' + esc(r.band.toLowerCase()) + '</b> (index ' + r.index + ' of 10) at ' + esc(r.site) + ', ' + esc(fq(r.km)) + ' km away.</p>' : '';
      if ((r.forecast || []).length) {
        h += '<div class="chips">' + r.forecast.map(function (f, i) {
          return '<span class="chip static" data-band="' + esc(f.band) + '">' + esc(i ? f.day : 'Today') + ': ' + esc(f.band) + ' (' + f.index + ')</span>';
        }).join('') + '</div>';
      }
      h += '<p class="small muted">Defra\'s Daily Air Quality Index: 1–3 low, 4–6 moderate, 7–9 high, 10 very high. When it\'s high, people with heart or lung conditions should do less outdoors.</p>';
    } else if (key === 'space') {
      h += '<p>Now: <b>' + esc(r.text) + '</b>. Next three days: ' + esc(r.next_text.charAt(0).toLowerCase() + r.next_text.slice(1)) + '.</p>' +
        '<p class="small muted">Geomagnetic storms run from G1 (minor) to G5 (extreme). Severe ones (G4, G5) can upset satellite navigation, radio and, rarely, the power grid. Dads Army warns from G4.</p>';
    } else if (key === 'threat') {
      h += '<p>The UK national threat level is <b>' + esc(String(r.level || '').toLowerCase()) + '</b>: ' + esc(r.means || '') + '.' +
        (r.ni ? ' Northern Ireland-related terrorism in Northern Ireland: ' + esc(String(r.ni).toLowerCase()) + '.' : '') + '</p>' +
        '<p class="small muted">Set by the Joint Terrorism Analysis Centre and MI5. It\'s the same for everyone in Great Britain (Northern Ireland has its own as well), and isn\'t your household\'s alert level. ' +
        'Dads Army warns when it goes up, and at critical.</p>';
    } else if (key === 'cyber') {
      h += (r.news || []).length ? '<div class="list">' + r.news.map(function (n) {
        return '<a class="li news" href="' + esc(n.url) + '" target="_blank" rel="noopener noreferrer"><span class="li-main"><span class="li-title wrap">' + (n.urgent ? '⚠️ ' : '') + esc(n.title) + '</span>' +
          '<span class="li-sub">' + esc(whenText(n.issued)) + '</span></span>' + ICON.chev + '</a>';
      }).join('') + '</div>' : '<p class="small muted">Nothing from the NCSC in the last two weeks.</p>';
      h += '<p class="small muted">The National Cyber Security Centre\'s news. A critical flaw or live attack in the last three days is a warning: update your phones, computers and router.</p>';
    } else if (key === 'travel') {
      h += (r.changes || []).length ? '<div class="list">' + r.changes.map(function (c) {
        return '<a class="li news" href="' + esc(c.url) + '" target="_blank" rel="noopener noreferrer"><span class="li-main"><span class="li-title wrap">' + esc(c.country) + (c.against ? ' · against travel' : '') + '</span>' +
          '<span class="li-sub">' + esc(c.text) + '</span></span>' + ICON.chev + '</a>';
      }).join('') + '</div>' : '<p class="small muted">No travel advice changes in the last three days.</p>';
      h += '<p class="small muted">The Foreign Office\'s travel advice changes. One advising against travel is often the first sign something is going on there.</p>';
    } else if (key === 'drought') {
      h += r.storage != null ? '<p>England\'s reservoirs are <b>' + esc(fq(r.storage)) + '% full</b>' + (r.vs_average ? ', ' + esc(fq(Math.abs(r.vs_average))) + '% ' + (r.vs_average < 0 ? 'below' : 'above') + ' average for the time of year' : '') + ' (week to ' + esc(r.week) + ').</p>' : '';
      h += r.area ? '<p>' + esc(r.area) + ': <b>' + esc((r.stage || 'Normal').toLowerCase()) + '</b>.</p>' : '<p class="small muted">Choose your Environment Agency area in the warnings settings to see your own drought status.</p>';
      h += r.ban ? '<p><b>Hosepipe ban:</b> ' + esc(r.ban) + '</p>' : '';
      h += r.company_text ? '<p class="small">' + esc(r.company) + ': ' + esc(r.company_text) + '</p>' : '';
      h += '<p class="small muted">From the Environment Agency\'s weekly dry weather and drought report. ' + (r.url ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener noreferrer">Read it</a>.' : '') + '</p>';
    } else if (key === 'water') {
      h += (r.reports || []).length ? '<div class="list">' + r.reports.map(function (x) {
        return '<div class="li"><span class="li-ico">' + (x.yours ? '⚠️' : '🚰') + '</span><span class="li-main"><span class="li-title wrap">' + esc(x.kind) + (x.yours ? ' · may be yours' : '') + '</span>' +
          '<span class="li-sub">' + esc(fq(x.km)) + ' km away · ' + esc(x.group) + (x.where ? ' · ' + esc(x.where) : '') + (x.issued ? ' · ' + esc(whenText(x.issued)) : '') + '</span></span></div>';
      }).join('') + '</div>' : '<p class="small muted">Nothing reported within ' + (r.within_km || 10) + ' km.</p>';
      h += '<p class="small muted">From ' + esc(r.company) + '\'s <a href="' + esc(r.url) + '" target="_blank" rel="noopener noreferrer">in your area</a> page. A supply problem is counted as yours when ' +
        'the company says your area is affected, or two are reported within 3 km, or one within 1 km.</p>';
    } else if (key === 'floodrisk') {
      var scot = r.days === 3;
      h += (scot ? '<p>Flood risk for the next three days: <b>' + esc(String(r.word || r.risk || '').toLowerCase()) + '</b>.</p>'
        : '<p><b>' + esc(r.headline || 'Flood risk ' + String(r.risk || '').toLowerCase() + ' where you live') + '</b>' + (r.rising ? ' (higher than today)' : '') + '.</p>') +
        (r.text ? '<p class="small">' + esc(r.text) + '</p>' : '') +
        '<p class="small muted">' + (scot ? 'The Scottish Flood Forecast, from SEPA and the Met Office. '
          : 'The Flood Forecasting Centre\'s five-day outlook (Environment Agency and Met Office), from GOV.UK\'s Check for flooding. Home is checked against the areas at risk here, so it isn\'t sent. ') +
        (r.url ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener noreferrer">' + (scot ? 'The forecast' : 'Check for flooding') + '</a>.' : '') + '</p>';
    } else if (key === 'rain') {
      h += r.day_mm != null ? '<p><b>' + esc(fq(r.day_mm)) + ' mm</b> in the last 24 hours, ' + esc(fq(Math.round(r.week_mm))) + ' mm in 7 days.</p>' +
        '<p class="small muted">Averaged over the nearest ' + (r.gauges || []).map(function (g) { return esc(g.name) + ' (' + esc(fq(g.km)) + ' km)'; }).join(', ') +
        (r.by ? ', from ' + esc(r.by) : '') + '. Over 30 mm in a day is heavy: watch for surface water.' +
        (r.url ? ' <a href="' + esc(r.url) + '" target="_blank" rel="noopener noreferrer">The nearest gauge</a>.' : '') + '</p>'
        : '<p class="small muted">No rain gauge within 25 km of home.</p>';
    } else if (key === 'ground') {
      h += (r.boreholes || []).length ? '<table class="live-table"><thead><tr><th>Borehole</th><th>For the time of year</th></tr></thead><tbody>' + r.boreholes.map(function (b) {
        return '<tr><td><a href="' + esc(b.url) + '" target="_blank" rel="noopener noreferrer">' + esc(b.name) + '</a><br><span class="small muted">' + esc(fq(b.km)) + ' km · ' + esc(fmtDate(b.date)) +
          (b.level_m != null ? ' · ' + esc(fq(Math.abs(b.level_m))) + ' m ' + (b.level_m < 0 ? 'below' : 'above') + ' sea level' : '') + '</span></td><td>' + esc(b.band) +
          (b.deep ? '<br><span class="small muted">A deep borehole: it follows decades, not this year\'s rain</span>' : '') + '</td></tr>';
      }).join('') + '</tbody></table>' : '<p class="small muted">' + (r.any_near ? 'The boreholes within 30 km haven\'t been read lately.' : 'No Environment Agency borehole within 30 km of home.') + '</p>';
      h += '<p class="small muted">Groundwater feeds many springs, wells and rivers. Most boreholes are read by hand every few months, so each reading is compared with the same time of year since records began.</p>';
    } else if (key === 'gridnow') {
      h += '<p>Carbon intensity: <b>' + esc(String(r.ci)) + ' g CO2 per kWh</b> (' + esc(r.index || '') + ').' + (r.hz ? ' Frequency ' + esc(r.hz.toFixed(2)) + ' Hz (' + esc(r.hz_min.toFixed(2)) + '–' + esc(r.hz_max.toFixed(2)) + ' in 15 minutes).' : '') + '</p>' +
        ((r.mix || []).length ? '<div class="chips">' + r.mix.map(function (m) { return '<span class="chip static">' + esc(m.fuel) + ' ' + esc(fq(m.pct)) + '%</span>'; }).join('') + '</div>' : '') +
        '<p class="small muted">Britain\'s grid runs at 50 Hz. A dip below 49.8 usually means a large power station or link has tripped.</p>';
    } else if (key === 'gridstress') {
      h += '<p>Tightest in the next 14 hours: <b>' + esc(fq(Math.round(r.margin_mw / 100) / 10)) + ' GW spare</b>.' + (r.low_mw != null ? ' Lowest in the next two weeks: ' + esc(fq(Math.round(r.low_mw / 100) / 10)) + ' GW on ' + esc(fmtDate(r.low_on)) + '.' : '') + '</p>' +
        ((r.dfs || []).length ? '<p>Demand Flexibility Service: ' + r.dfs.map(function (e) { return esc(fmtDate(e.day) + ' ' + e.from + '–' + e.to); }).join(', ') + '. If your supplier takes part, you may be paid to use less then.</p>' : '') +
        '<p class="small muted">The de-rated margin is the spare generating capacity once likely breakdowns are allowed for. Above about 3 GW is comfortable.</p>';
    } else if (key === 'pound') {
      h += '<table class="live-table"><tbody>' +
        (r.usd ? '<tr><td>£1 in dollars</td><td class="num">$' + esc(r.usd.toFixed(2)) + '</td><td class="num">' + (r.usd_week != null ? esc((r.usd_week > 0 ? '+' : '') + fq(r.usd_week)) + '% in a week' : '') + '</td></tr>' : '') +
        (r.eur ? '<tr><td>£1 in euros</td><td class="num">€' + esc(r.eur.toFixed(2)) + '</td><td class="num">' + (r.eur_week != null ? esc((r.eur_week > 0 ? '+' : '') + fq(r.eur_week)) + '% in a week' : '') + '</td></tr>' : '') +
        (r.rate != null ? '<tr><td>Bank Rate</td><td class="num">' + esc(fq(r.rate)) + '%</td><td></td></tr>' : '') + '</tbody></table>' +
        '<p class="small muted">The Bank of England\'s figures for ' + esc(fmtDate(r.date)) + '. A big fall in the pound makes imported food and fuel dearer over the following months. Dads Army warns at 3% in a week, or 5% in two.</p>';
    }
    return h;
  }

  function sheetLive(s) {
    var w = W(), rows = w.live_rows || [];
    var html = sheetHead('The wider picture', 'Live, from public sources', '🌍');
    if (!rows.length) return html + '<p class="small muted">Nothing yet. These come with warnings, and are checked every 15 minutes or so.</p>';
    var order = s.key ? rows.filter(function (r) { return r.key === s.key; }).concat(rows.filter(function (r) { return r.key !== s.key; })) : rows;
    loadLiveHistory();
    var counts = (LIVEHIST.data && LIVEHIST.data.metrics) || [];
    var keys = rows.map(function (r) { return r.key; });
    html += order.map(function (r) {
      var its = w.items.filter(function (x) { return x.source === r.key; });
      return '<div class="live-block" data-state="' + r.state + '"><h3>' + r.emoji + ' ' + esc(r.name) + '</h3>' +
        trendNotes(r.key) +
        its.map(function (x) {
          return '<div class="li warn-row sev' + x.severity + '"><span class="li-ico">' + (WARN_ICON[x.kind] || '⚠️') + '</span>' +
            '<button class="li-main" data-act="warn-open" data-i="' + w.items.indexOf(x) + '"><span class="li-title wrap">' + esc(x.title) + '</span></button></div>';
        }).join('') +
        liveDetail(r.key, w.live[r.key] || {}) +
        countCharts(counts.filter(function (m) { return m.source === r.key; })) +
        '<p class="credit small muted">' + esc(r.credit) + (r.checked_at ? ' · checked ' + esc(ago(r.checked_at)) : '') + '</p></div>';
    }).join('');
    // Flood warnings and fires are warnings, not live lines, but their counts are kept too: they go at the end.
    var other = counts.filter(function (m) { return keys.indexOf(m.source) < 0; });
    if (other.length) {
      var srcs = other.map(function (m) { return m.source; }).filter(function (x, i, a) { return a.indexOf(x) === i; });
      var up = (w.trends || []).some(function (t) { return srcs.indexOf(t.source) >= 0; });
      html += '<div class="live-block" data-state="' + (up ? 'warn' : 'good') + '"><h3>📈 Warnings, counted</h3>' +
        srcs.map(trendNotes).join('') + countCharts(other) +
        '<p class="credit small muted">The day\'s highest, kept for two weeks. A count twice its usual or more is a trend to watch.</p></div>';
    }
    return html + '<button class="btn block" data-act="warn-set">Choose what to show</button>';
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
    if (w.kind === 'power') {
      return { plan: ['power_off'], tips: [
        'Power off? Call 105, free from any phone, to report it or get updates.',
        'Charge phones and power banks while you can, and find the torches.',
        'Keep the fridge and freezer shut: food stays cold for hours.'] };
    }
    if (w.kind === 'river') {
      return { plan: ['meet_near', 'power_off', 'gas_off', 'water_off'], tips: [
        'Check the flood warnings for where you live, and sign up for free ones at gov.uk/sign-up-for-flood-warnings.',
        'Keep documents and medicines somewhere high.',
        'Never walk or drive through flood water.'] };
    }
    if (w.kind === 'grid') {
      return { plan: [], tips: [
        'Nothing to do but be ready: charge phones and power banks, and know where the torches are.',
        'If planned rota cuts are announced, your network\'s website will show when your area is off.'] };
    }
    if (w.kind === 'air') {
      return { plan: [], tips: [
        'If you have a heart or lung condition, do less outdoors, and keep reliever inhalers handy.',
        'Keep windows shut on busy roads.'] };
    }
    if (w.kind === 'space') {
      return { plan: [], tips: [
        'Charge power banks and torches, and keep a battery or wind-up radio handy.',
        'Satellite navigation may be unreliable for a while: have a paper map.'] };
    }
    if (w.kind === 'gas' || w.kind === 'money') {
      return { plan: [], tips: ['Nothing to do today. It\'s a reason to keep the stores and the warm kit topped up.'] };
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
    return sheetHead(w.title, whoFrom(w) + (w.issued ? ' · ' + whenText(w.issued) : ''), WARN_ICON[w.kind] || '⚠️') +
      '<div class="warn-meta"><span class="badge ' + sevClass(w.severity) + '">' + esc(w.level) + '</span>' +
      (w.area ? '<span class="small muted">' + esc(w.area) + '</span>' : '') +
      (w.distance_km != null ? '<span class="small muted">' + w.distance_km + ' km away</span>' : '') + '</div>' +
      (w.when ? '<p class="small"><b>' + esc(w.when) + '</b></p>' : '') +
      (w.text ? '<div class="notes">' + esc(w.text) + '</div>' : '') +
      (w.url ? '<a class="btn block ext" href="' + esc(w.url) + '" target="_blank" rel="noopener noreferrer">' +
        (w.kind === 'fire' ? 'See it on NASA\'s fire map' : 'Full details from ' + esc(whoFrom(w))) + '</a>' : '') +
      (w.kind === 'fire' && w.lat != null ? '<button class="btn block ext" data-act="fire-ignore" data-lat="' + w.lat + '" data-lon="' + w.lon + '">' +
        'Not a wildfire: ignore this spot</button>' : '') +
      '<h3>What to do</h3><ul class="tips">' + tips.tips.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') +
      (r.people && w.kind !== 'disaster' ? '<li>Your stores would last about <b>' + esc(fmtDays(r.hold)) + ' days</b>' +
        (r.supplies[0] ? ', and ' + esc(r.supplies[0].it.name) + ' about ' + esc(fmtDays(r.supplies[0].days)) + ' days' : '') + '.</li>' : '') + '</ul>' +
      (bits.length ? '<h3>From your plan</h3>' + bits.map(function (k) {
        return '<div class="plan-bit"><span class="sub-label">' + esc(heads[k]) + '</span><div class="notes">' + esc(p[k]) + '</div></div>';
      }).join('') : '') +
      '<p class="small muted" style="margin-top:14px">From ' + esc(whoFrom(w)) + '. Always follow official advice and the emergency services.</p>';
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
        return (s[0] === LIVE_KEYS[0] ? '<h3>Live information</h3><p class="small muted">The wider picture: rivers and power cuts near home, the electricity grid, ' +
          'gas storage, air quality, space weather and the pound. Each is a public feed for the whole country (or a whole region or network), so nothing is sent about where you are. ' +
          'Where England\'s feeds don\'t reach, Scotland\'s, Wales\' and Northern Ireland\'s own take over, near home only.</p>' : '') +
          (s[0] === LIVE_MORE ? '<h3>More of the wider picture</h3><p class="small muted">The threat level, cyber security, travel advice, drought, the five-day flood risk, ' +
            'rain and groundwater near home, and the electricity grid. The daily briefing reads these too. Public feeds again: only the nearest rain gauges, asked for by name, say roughly where you are.</p>' : '') +
          (w.unavailable && w.unavailable[s[0]]
            ? '<label class="opt is-off"><input type="checkbox" name="src_' + s[0] + '" disabled' + (c.sources[s[0]] ? ' checked' : '') + '><span>' + esc(s[1]) +
              '<span class="small muted">' + (/^(Choose|Needs) /.test(w.unavailable[s[0]]) ? esc(w.unavailable[s[0]])   // something to set, not somewhere it can't go
                : 'Not for your area: ' + esc(w.unavailable[s[0]].charAt(0).toLowerCase() + w.unavailable[s[0]].slice(1))) + '</span></span></label>'
            : '<label class="opt"><input type="checkbox" name="src_' + s[0] + '"' + (c.sources[s[0]] ? ' checked' : '') + '><span>' + esc(s[1]) + '</span></label>');
      }).join('') +
      '<h3>Where you are</h3>' +
      '<div class="grid2"><label class="field"><span>Environment Agency area</span><select name="ea_area"><option value="">Not set (England\'s totals)</option>' +
      (w.ea_areas || []).map(function (a) { return '<option' + (c.ea_area === a ? ' selected' : '') + '>' + esc(a) + '</option>'; }).join('') + '</select>' +
      '<div class="hint">For your drought status. England only.</div></label>' +
      '<label class="field"><span>Water company</span><select name="water_co"><option value="">Not set</option>' +
      (w.water_cos || []).map(function (a) { return '<option' + (c.water_co === a ? ' selected' : '') + '>' + esc(a) + '</option>'; }).join('') + '</select>' +
      '<div class="hint">For hosepipe bans, and supply problems (Cambridge Water, South Staffs Water, Yorkshire Water, South West Water, Bournemouth Water and NI Water). It isn\'t guessed from where you live.</div></label></div>' +
      '<label class="field"><span>Met Office region</span><select name="region">' +
      '<option value="">' + (guess ? 'From my location: ' + esc(guess) : 'From my location') + '</option>' +
      '<option value="UK"' + (c.region === 'UK' ? ' selected' : '') + '>The whole UK</option>' +
      w.regions.map(function (r) { return '<option value="' + r[0] + '"' + (c.region === r[0] ? ' selected' : '') + '>' + esc(r[1]) + '</option>'; }).join('') +
      '</select></label>' +
      '<div class="field"><span>Location</span><div class="grid2">' +
      '<input type="number" name="lat" inputmode="decimal" step="any" placeholder="Latitude, e.g. 53.96" value="' + (c.lat != null ? c.lat : '') + '" aria-label="Latitude">' +
      '<input type="number" name="lon" inputmode="decimal" step="any" placeholder="Longitude, e.g. -1.08" value="' + (c.lon != null ? c.lon : '') + '" aria-label="Longitude"></div>' +
      '<div class="hint">' + esc(locLine) + ' Used for flood and disaster warnings, worked out here. With Emergency Alerts on, it\'s looked up once, rounded to about 100 m, to find your district (see the documentation). ' +
      (w.ha ? 'Leave empty to use your Home Assistant home location.' : 'Long-press your home in a maps app to find it.') + '</div></div>' +
      '<div class="grid2"><label class="field"><span>Floods within (km)</span><input type="number" name="flood_km" inputmode="numeric" min="1" max="200" value="' + c.flood_km + '"></label>' +
      '<label class="field"><span>Fires within (km)</span><input type="number" name="fire_km" inputmode="numeric" min="2" max="50" value="' + c.fire_km + '"></label></div>' +
      '<div class="grid2"><label class="field"><span>Disasters within (km)</span><input type="number" name="gdacs_km" inputmode="numeric" min="50" max="5000" value="' + c.gdacs_km + '"></label>' +
      '<label class="field"><span>Near you (km)</span><input type="number" name="near_km" inputmode="numeric" min="5" max="40" step="1" value="' + (c.near_km || 10) + '" aria-describedby="nearKmHint"></label></div>' +
      '<p class="small muted" id="nearKmHint" style="margin:-6px 0 12px">Near you, 5 to 40 km: how far power cuts and water supply reports are listed, under <b>Nearby, not in your area</b>. ' +
      'Only one in your own area (a power cut within 2 km, a supply problem the water company says is yours) is a warning, whatever this is.</p>' +
      '<p class="small muted" style="margin:-6px 0 12px">Disasters are orange and red alerts from GDACS, the UN and EU disaster alert system. ' +
      'Fires are hotspots NASA satellites saw in the last 24 hours: often controlled burns or farm fires, sometimes a wildfire. ' +
      'Places seen again and again over a week or more, like industrial flares, are left out, and you can tell it to ignore a spot.</p>' +
      (w.fire_ignored ? '<p class="small muted">Ignoring ' + w.fire_ignored + ' fire spot' + (w.fire_ignored === 1 ? '' : 's') +
        ' you\'ve marked as not a wildfire. <button type="button" class="link" data-act="fire-unignore">Show them again</button></p>' : '') +
      (status ? '<h3>Last check</h3>' + status : '') +
      '<p class="small muted" style="margin-top:12px">Sources: Met Office (weather warnings), Environment Agency (flood warnings and river levels, under the Open Government Licence), ' +
      'SEPA (Scotland\'s flood warnings, river levels, rain gauges and the Scottish Flood Forecast), Natural Resources Wales (Wales\' flood warnings and rain gauges), ' +
      'GOV.UK Emergency Alerts, GDACS, NASA FIRMS (fire detections), UK Health Security Agency, the World Health Organization, ' +
      'UK Power Networks, National Grid, SSEN, Northern Powergrid, Electricity North West and NIE Networks (power cuts), NESO and Elexon (grid notices), National Gas (gas storage), ' +
      'Defra UK-AIR (air quality), NOAA (space weather), the Bank of England (the pound and Bank Rate) and your water company. The DOCS list each one\'s licence.</p>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">Save and check now</button></div></form>';
  }

  // ------------------------------------------------------------------
  // Household alert level (worked out on the Pi: warnings + home sensors + stores)
  // ------------------------------------------------------------------
  var SRC_CLASS = { 'UK Government': 'gov', 'SAS Survival Handbook': 'sas', 'Fire & rescue services': 'fire',
    'Dads Army tip': 'tip', 'Electricity networks': 'net' };
  var LEVEL_RULES = {
    5: ['An Emergency Alert for your area', 'A severe flood warning', 'A gas, carbon monoxide or smoke alarm going off'],
    4: ['A red weather warning', 'A flood warning', 'A power cut over 12 hours, or with the backup battery under 20%',
      'The coldest room under 9°C, or the warmest 33°C or more', 'PM2.5 air pollution of 75 µg/m³ or more'],
    3: ['An amber weather warning', 'A possible fire within 3 km', 'A power cut', 'A water leak',
      'A river near you higher than it\'s been for years',
      'The coldest room under 12°C, or the warmest 30°C or more', '−10°C or colder, or 35°C or hotter, outside',
      'PM2.5 of 55 µg/m³ or more'],
    2: ['A yellow weather warning', 'A flood alert', 'A disaster in or near the UK (not one abroad that can\'t reach you, such as an earthquake in Norway; volcanic ash can)', 'A possible fire nearby',
      'A power cut within 2 km', 'A river near you above its normal range', 'High air pollution', 'A severe solar storm',
      'A warning of planned rota power cuts',
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
      PL().hazards.filter(function (h) { return h.active; }).map(function (h, i) {
        return (i ? '' : '<h3>Where to go</h3>') + '<p class="small"><b>' + h.emoji + ' ' + esc(h.what) + ':</b> ' + esc(h.advice) + '</p>' +
          (h.places.length ? '<div class="list">' + h.places.slice(0, 3).map(placeRow).join('') + '</div>' : '');
      }).join('') +
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
    try { if (localStorage.getItem('da-dash-note') === 'layout6') return ''; } catch (e) { /* show it */ }
    return '<div class="card tip-card"><p><b>New for the Home front dashboard:</b> the wider picture: rivers and power cuts near home, ' +
      'the electricity grid, gas storage, air quality, space weather and the pound. Also the map of places to go, if you haven\'t updated since. ' +
      'Update the dashboard to get them.</p>' +
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
      row('🗺️', 'Places to go', 'High ground, rest centres, warm spaces, and your own places, near home', 'help-go', ' data-view="plan"') +
      (ha ? row('🌡️', 'Choose home sensors', 'Temperatures, power, alarms and more can change the alert level', 'home-sensors') : '') +
      row('📢', 'Warnings for where you live', 'Met Office, floods, Emergency Alerts, fires', 'warn-set') +
      row('📋', 'Routine checks and your emergency plan', 'On the Plan tab', 'help-go', ' data-view="plan"') +
      row('🛒', 'Shopping for what\'s missing', 'The Supply run tab lists everything below target', 'help-go', ' data-view="supply"') +
      (S.items.length ? '' : row('📦', 'Load the starter list', 'About 95 essentials, sized for your household', 'seed')) +
      row('💛', 'Credits', 'The people who built Dads Army, with thanks', 'credits') +
      '</div>' +
      (ha ? '<h3>Phone alerts</h3><p class="small muted">Two ready-made automations send warnings, run-outs, checks that are due and a weekly round-up to your phone. ' +
        'In Home Assistant, open <b>Settings → Apps → Dads Army → Documentation</b> and follow <b>Phone alerts</b>.</p>' : '') +
      '<p class="small muted" style="margin-top:14px">Dads Army v' + esc(S.server.version) + '</p>';
  }

  // Credits: the thank-you and the names come from CREDITS.md (the app's own copy, or GitHub's once checked).
  function sheetCredits(s) {
    var head = sheetHead('Credits', 'The people behind Dads Army', '💛'), c = s.data;
    if (!c) return head + '<p class="small muted">Loading…</p>';
    if (c.failed) return head + '<p class="small ha-error">' + esc(c.failed) + '</p>';
    var html = head + '<div class="credits-thanks">' + c.message.map(function (p, i) {
      return '<p' + (i === 0 && p.length <= 40 ? ' class="credits-lead"' : '') + '>' + esc(p) + '</p>';
    }).join('') + '</div>';
    c.groups.forEach(function (g) {
      html += '<h3>' + esc(g.title) + '</h3>' + g.about.map(function (p) { return '<p class="small muted">' + esc(p) + '</p>'; }).join('');
      if (g.people.length) {
        html += '<ul class="credits-list">' + g.people.map(function (p) {
          var name = p.url ? '<a href="' + esc(p.url) + '" target="_blank" rel="noopener noreferrer">' + esc(p.name) + '</a>' : esc(p.name);
          var handle = p.handle && p.name.toLowerCase() !== '@' + p.handle.toLowerCase() ? ' <span class="credits-handle">@' + esc(p.handle) + '</span>' : '';
          return '<li><span class="credits-name">' + name + handle + '</span>' + (p.note ? '<span class="credits-note">' + esc(p.note) + '</span>' : '') + '</li>';
        }).join('') + '</ul>';
      }
    });
    var from = c.source === 'github' ? 'Checked with GitHub ' + ago(c.checked_at) + '.' :
      'This list came with Dads Army v' + S.server.version + (c.checked_at ? ', and GitHub was last asked ' + ago(c.checked_at) : '') + '.';
    return html + '<div class="credits-foot">' +
      '<p class="small muted">' + esc(from) + ' Checking asks GitHub for the latest list and the people who\'ve changed the code. Nothing about you is sent.</p>' +
      (c.check_error ? '<p class="small ha-error">The last check had a problem with ' + esc(c.check_error) + '.</p>' : '') +
      '<div class="btn-stack"><button class="btn block" type="button" data-act="credits-check">Check GitHub for new names</button>' +
      '<a class="btn block" href="' + esc(c.edit_url) + '" target="_blank" rel="noopener noreferrer">Add a name on GitHub</a></div></div>';
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

  // Earlier warnings for some categories: medicines you'd want to replace well before they run out of date, say.
  var WARN_CHOICES = [14, 30, 60, 90, 180];
  function warnByCat(st) {
    var by = st.warn_by_cat || {}, n = Object.keys(by).length;
    return '<details class="warncat"' + (n ? ' open' : '') + '><summary>Warn earlier (or later) for some categories' + (n ? ' · ' + n + ' set' : '') + '</summary>' +
      '<p class="small muted">For example, 90 days for medicines, so there\'s time to get a new prescription.</p>' +
      CATS.map(function (c) {
        var v = by[c.id] || 0;
        return '<label class="set-row"><span>' + c.icon + ' ' + esc(c.label) + '</span><select data-warncat="' + c.id + '" aria-label="Expiry warning for ' + esc(c.label) + '">' +
          '<option value="0"' + (v ? '' : ' selected') + '>As above (' + st.warn_days + ' days)</option>' +
          WARN_CHOICES.map(function (d) { return '<option value="' + d + '"' + (v === d ? ' selected' : '') + '>' + d + ' days</option>'; }).join('') +
          (v && WARN_CHOICES.indexOf(v) < 0 ? '<option value="' + v + '" selected>' + v + ' days</option>' : '') + '</select></label>';
      }).join('') + '</details>';
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
      '<h3 class="plan-h">Pets</h3>' +
      setRow('dogs', 'Dogs', '', st.dogs, 1) +
      (st.dogs ? setRow('water_per_dog', 'Water per dog', 'litres a day: about 50 ml per kg', st.water_per_dog, 0.25) : '') +
      setRow('cats', 'Cats', '', st.cats, 1) +
      (st.cats ? setRow('water_per_cat', 'Water per cat', 'litres a day', st.water_per_cat, 0.05) : '') +
      setRow('other_pets', 'Other pets', '', st.other_pets, 1) +
      (st.other_pets ? setRow('water_per_other_pet', 'Water per other pet', 'litres a day', st.water_per_other_pet, 0.05) : '') +
      '<div class="needs">Your household needs <b>' + nf0.format(r.kcalDay) + ' kcal</b> and <b>' + fq(Math.round(r.waterDay * 10) / 10) + ' L of water</b> a day' +
      (r.petWater > 0 ? ', including ' + fq(Math.round(r.petWater * 100) / 100) + ' L for the pets' : '') + '. ' +
      'For ' + target + ' days that\'s <b>' + nf0.format(r.kcalDay * target) + ' kcal</b> and <b>' + nf0.format(r.waterDay * target) + ' L</b>.' +
      (petsCount(st) ? ' Their food is counted from the pet food\'s <b>Used a day</b>.' : '') + '</div></section>';

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
      }).join('') + '</div>' + warnByCat(st) + '</section>';

    html += '<section class="card"><div class="card-head"><h2>Hard copy &amp; backups</h2></div>' +
      '<p class="small muted">If the power goes, so does the Pi. Keep a printed copy with the stores, and a backup somewhere other than the Pi.</p>' +
      '<div class="btn-stack">' +
      '<button class="btn block" data-act="print">' + ICON.print + ' Print full inventory</button>' +
      '<button class="btn block" data-act="print-plan">' + ICON.print + ' Print emergency plan &amp; checks</button>' +
      '<a class="btn block" href="api/backup.json" download>' + ICON.download + ' Download backup</a>' +
      '<a class="btn block" href="api/export.csv" download>' + ICON.download + ' Export spreadsheet (CSV)</a>' +
      '<button class="btn block" data-act="restore">' + ICON.upload + ' Restore from a backup…</button>' +
      '<button class="btn block" data-act="backups">' + ICON.upload + ' Restore an automatic copy…</button></div>' +
      '<p class="small muted" style="margin:10px 0 0">The Pi also saves its own copy every day' +
      (S.server.last_backup ? ' (last one ' + esc(ago(S.server.last_backup)) + ')' : '') + '.</p></section>';

    html += '<section class="card"><div class="card-head"><h2>Starter list</h2></div>' +
      '<p class="small muted">Adds about 95 suggested essentials at zero stock (and pet food, if you have pets), with targets sized for your household and ' + target + '-day goal. ' +
      'When the household or the goal changes, those targets change with it, unless you\'ve set one yourself. ' +
      'Anything you already have is skipped. To clear out what you don\'t need, use <b>Select to delete</b> in Stores.</p>' +
      '<button class="btn block" data-act="seed">Load starter list</button></section>';

    html += scanHqCard() + briefHqCard();
    html += warnHqCard() + homeCard() + haCard();

    html += '<section class="card"><div class="card-head"><h2>Appearance</h2></div><div class="seg" role="group" aria-label="Theme">' +
      [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (t) {
        return '<button data-act="theme" data-val="' + t[0] + '" aria-pressed="' + (theme === t[0]) + '">' + t[1] + '</button>';
      }).join('') + '</div></section>';

    html += '<section class="card"><div class="card-head"><h2>Activity log</h2><span class="small muted">last ' + S.log.length + '</span></div>' +
      (S.log.length ? logHtml(S.log) : '<p class="small muted">Nothing yet.</p>') + '</section>';
    html += '<p class="tagline">Dads Army v' + esc(S.server.version) + ' · Don\'t panic</p>' +
      '<p class="tagline-sub"><button class="link" type="button" data-act="credits">Credits</button>: with thanks to everyone who built it</p>';
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
        return api('PUT', 'api/settings', body).then(function (res) {
          return refresh().then(function () {
            toast(res.rescaled ? 'Saved. Targets for ' + res.rescaled + ' starter-list item' + (res.rescaled === 1 ? '' : 's') + ' changed to suit' : 'Saved',
              res.rescaled ? { ms: 4500 } : {});
          });
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
    // Straight after closing one (a result replacing the sheet you were on): reuse its step in history.
    if (backSoon) { clearTimeout(backSoon); backSoon = null; try { history.replaceState({ daSheet: stack.length }, ''); } catch (e) { /* ignore */ } }
    else { try { history.pushState({ daSheet: stack.length }, ''); } catch (e) { /* ignore */ } }
    showSheet(true);
  }
  // Going back in history is asynchronous, so a sheet opened straight after closing one would be popped by
  // the late popstate. Close the sheet now, step history back a moment later, and ignore that popstate.
  var ownPops = 0, ownPopAt = 0, backSoon = null;
  function stepBack(n) {
    ownPops++; ownPopAt = Date.now();
    try { if (n > 1) history.go(-n); else history.back(); } catch (e) { ownPops--; }
  }
  function closeSheet() {
    if (!stack.length) return;
    var hs = history.state && history.state.daSheet;
    stack.pop();
    showSheet(true);
    if (hs) backSoon = setTimeout(function () { backSoon = null; stepBack(1); }, 0);
  }
  // Close every open sheet at once (each was a step in history), then carry on.
  // Saved: back to where you were. After a scan, that's the stores, not the scan result you came from.
  var SCAN_SHEETS = ['livescan', 'scanned', 'scanhit', 'scanfail', 'scancode', 'scanpick'];
  function doneSheet() {
    if (stack.some(function (x) { return SCAN_SHEETS.indexOf(x.type) >= 0; })) closeAllSheets();
    else closeSheet();
  }
  function closeAllSheets(then) {
    var n = stack.length, hs = history.state && history.state.daSheet;
    if (!n) return then && then();
    stack.length = 0;
    showSheet(true);
    if (backSoon) { clearTimeout(backSoon); backSoon = null; n++; }
    if (hs) stepBack(Math.min(n, hs));
    if (then) setTimeout(then, hs ? 150 : 0);
  }
  window.addEventListener('popstate', function () {
    if (ownPops && Date.now() - ownPopAt < 1500) { ownPops--; return; }
    ownPops = 0;
    if (stack.length) { stack.pop(); showSheet(true); }
    else if (SEL) { endSelect(); renderStoreList(); }
  });
  function showSheet(resetScroll) {
    var root = $('#sheet-root');
    if (!stack.length) {
      stopLive();
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
    if (s.type === 'livescan' && LIVE && $('#liveVideo')) return;   // the camera is running: a refresh mustn't replace it
    if (s.type !== 'livescan') stopLive();
    var html = {
      item: sheetItem, edit: sheetEdit, stock: sheetStock, use: sheetUse, batch: sheetBatch, text: sheetText, halists: sheetHaLists,
      check: sheetCheck, plan: sheetPlan, warning: sheetWarning, warnset: sheetWarnSet, help: sheetHelp, dashwiz: sheetDashWiz,
      level: sheetLevel, levelhelp: sheetLevelHelp, homesensors: sheetHomeSensors, area: sheetArea, resall: sheetResAll,
      place: sheetPlace, live: sheetLive, scanned: sheetScanned, scancode: sheetScanCode, scanhit: sheetScanHit,
      livescan: sheetLiveScan, scanfail: sheetScanFail, scanpick: sheetScanPick, aifill: sheetAiFill,
      credits: sheetCredits, shoptext: sheetShopText, backups: sheetBackups
    }[s.type](s);
    if (html === null) {   // the item was deleted elsewhere
      closeSheet();
      return;
    }
    $('#sheet-body').innerHTML = html;
    if (s.type === 'edit') perDayHint($('#itemForm'));
    if (s.type === 'livescan') startLive();
  }
  // The AI fills in what's missing (calories for a whole pack, what one holds, how long it keeps once opened),
  // for you to check before anything is saved.
  function sheetAiFill(s) {
    if (!s.got && !s.asking) {
      s.asking = true;
      api('POST', 'api/ai/fill', {}).then(function (r) {
        s.got = r.suggestions; s.left = r.left; SCAN_AI = null;
        if (stack[stack.length - 1] === s) showSheet();
      }, function (e) { s.err = e.message; if (stack[stack.length - 1] === s) showSheet(); });
    }
    var head = sheetHead('Fill in missing details', 'Estimated by the AI: check them', '🤖');
    if (s.err) return head + '<p class="err">' + esc(s.err) + '</p>';
    if (!s.got) return head + '<p class="small muted">Asking the AI about the food, drinks and pet food that are missing calories, pack sizes or how long they keep once opened. Only the names go, no photos: well under a penny.</p>';
    if (!s.got.length) return head + '<p>Nothing to fill in: everything has what it needs.</p>';
    var words = function (x) {
      var f = x.fields, out = [];
      if (f.kcal_per_unit) out.push(nf0.format(f.kcal_per_unit) + ' kcal per ' + (x.unit || 'one'));
      if (f.pack_size) out.push('holds ' + fq(f.pack_size) + (f.pack_unit === 'each' ? ' items' : ' ' + f.pack_unit));
      if (f.open_days) out.push('use within ' + fq(f.open_days) + ' days once opened');
      if (f.storage) out.push(({ ambient: 'kept in the cupboard', chilled: 'kept in the fridge', frozen: 'kept in the freezer' })[f.storage]);
      return out.join(' · ');
    };
    return head + '<p class="small">Typical figures for each, from its name. Untick any that look wrong; you can change them later, and they show as "AI estimate" until you do.</p>' +
      '<div class="opts">' + s.got.map(function (x) {
        return '<label class="opt"><input type="checkbox" data-fill="' + x.id + '" checked><span><b>' + esc(x.name) + '</b><br><small>' + esc(words(x)) + '</small></span></label>';
      }).join('') + '</div>' +
      (s.left ? '<p class="small muted">' + srN(s.left, 'more item', 'more items') + ' after these: run it again once these are saved.</p>' : '') +
      '<div class="sheet-actions"><button class="btn primary block" data-act="ai-fill-save">Save the ticked ones</button></div>';
  }
  function sheetHead(title, sub, icon) {
    return '<div class="sheet-head">' + (icon ? '<span class="li-ico">' + icon + '</span>' : '') +
      '<div><h2 id="sheet-title">' + esc(title) + '</h2>' + (sub ? '<p>' + esc(sub) + '</p>' : '') + '</div>' +
      '<button class="icon-btn" type="button" data-act="close-sheet" aria-label="Close">' + ICON.close + '</button></div>';
  }
  function stat(value, label) {
    return '<div class="stat"><span class="stat-val">' + esc(value) + '</span><span class="stat-lbl">' + esc(label) + '</span></div>';
  }
  function expiryField(val, usual, dates) {
    return '<div class="field"><span>Best before / expiry</span>' +
      '<div class="date-row"><input type="date" name="expiry" value="' + esc(val || '') + '" aria-label="Best before date">' +
      '<button type="button" class="btn small" data-act="scan-date">📷 Read it from a photo</button></div>' +
      '<div class="hint" data-scan-hint hidden></div>' +
      (dates && dates.length ? '<div class="quick">' + dates.map(function (d) {
        return '<button type="button" class="chip" data-expdate="' + esc(d) + '">Same as ' + esc(fmtDate(d)) + '</button>';
      }).join('') + '</div>' : '') +
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
    if (it.target_qty > 0) stats.push(stat(fq(it.target_qty), (i.low ? 'target · short ' + fq(i.short) : 'target · met ✓') +
      (i.old > 0 ? ' · ' + fq(i.old) + ' out of date' : '') + (it.auto_target ? ' · follows the household' : '')));
    var guessed = function (f) { return (',' + (it.ai_guessed || '') + ',').indexOf(',' + f + ',') >= 0; };
    if (kcalCat(it.category) && it.kcal_per_unit > 0 && r.kcalDay > 0) stats.push(stat(fmtDays(i.total * it.kcal_per_unit / r.kcalDay), 'days of food'));
    if (it.kcal_per_unit > 0) stats.push(stat(nf0.format(it.kcal_per_unit), 'kcal per ' + (it.unit || 'one') + (guessed('kcal_per_unit') ? ' · AI estimate' : '')));
    if (it.open_days > 0 && guessed('open_days')) stats.push(stat(fq(it.open_days), 'days once opened · AI estimate'));
    if (it.storage && storedCat(it.category)) stats.push(stat(({ ambient: '🥫', chilled: '❄️', frozen: '🧊' })[it.storage],
      ({ ambient: 'stored in the cupboard', chilled: 'stored in the fridge', frozen: 'stored in the freezer' })[it.storage] + (guessed('storage') ? ' · AI estimate' : '')));
    if (itemLitres(it) > 0) {
      stats.push(stat(fq(Math.round(i.total * itemLitres(it) * 10) / 10) + ' L', it.category !== 'water' ? 'to drink' : r.waterDay > 0 ? fmtDays(i.total * itemLitres(it) / r.waterDay) + ' days of water' : 'of water'));
    }
    if (it.per_day > 0) stats.push(stat(fmtDays(daysLeft(it)), 'days at ' + fq(it.per_day) + ' a day'));
    if (it.price > 0) stats.push(stat(money(i.total * it.price), 'worth, at ' + money(it.price) + ' each'));
    var use = (S.usage || {})[String(it.id)];
    var batches = it.batches.map(function (b) {
      var es = expState(b.expiry, it.category);
      var exp = b.expiry
        ? '<span class="badge ' + (es === 'ok' ? 'ok' : es) + '">' + esc(expiryWords(b.expiry)) + '</span>' + esc(fmtDate(b.expiry))
        : '<span class="badge plain">No expiry</span>';
      return '<div class="batch"><button class="batch-main" data-act="batch" data-id="' + b.id + '" data-item="' + it.id + '">' +
        '<span class="batch-exp">' + exp + '</span><span class="batch-meta">' +
        (b.opened_at ? '<b>Opened ' + esc(fmtDate(b.opened_at.slice(0, 10))) + '</b>' + (b.open_until ? ' · keeps until ' + esc(fmtDate(b.open_until)) : '') + ' · ' : '') +
        (b.location ? esc(b.location) : 'No location set') +
        ' · added ' + esc(fmtDate(b.added_at)) + '</span></button>' +
        '<button class="link batch-more" data-act="stock-like" data-id="' + it.id + '" data-likeexp="' + esc(b.printed_expiry || '') + '" data-loc="' + esc(b.location || '') + '">More like this</button>' +
        '<div class="mini-step"><button class="qbtn" data-act="bstep" data-id="' + b.id + '" data-d="-1" aria-label="One less">' + ICON.minus + '</button>' +
        '<output>' + esc(fq(b.qty)) + '</output>' +
        '<button class="qbtn" data-act="bstep" data-id="' + b.id + '" data-d="1" aria-label="One more">' + ICON.plus + '</button></div></div>';
    }).join('');
    return sheetHead(it.name, c.label + (it.unit ? ' · per ' + it.unit : ''), c.icon) +
      '<div class="stats">' + stats.join('') + '</div>' +
      (packWords(it, i.total) ? '<p class="small muted">' + esc(packWords(it, i.total)) + '</p>' : '') +
      (use ? '<p class="usage">📈 You use ' + esc(use.text) + '. <span class="muted">From ' + use.uses + ' uses since ' + esc(fmtDate(use.since)) + '.</span></p>' : '') +
      '<div class="btn-row"><button class="btn" data-act="use-sheet" data-id="' + it.id + '"' + (i.none ? ' disabled' : '') + '>' + ICON.minus + ' Use</button>' +
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
    var pre = s.pre || {};
    var v = it || { name: pre.name || '', category: pre.category || s.cat || 'food', unit: pre.unit || '', kcal_per_unit: pre.kcal_per_unit || 0,
      litres_per_unit: pre.litres_per_unit || 0, target_qty: 0, per_day: 0, price: 0, notes: '',
      pack_size: pre.count > 1 ? pre.count : (pre.grams || 0),
      // what the scan or label says the size is in (a juice in ml, a jar of coffee in g), else by category
      pack_unit: pre.count > 1 ? 'each' : pre.grams ? (pre.pack_unit || (pre.category === 'water' || pre.category === 'drinks' ? 'ml' : 'g')) : '',
      open_days: pre.open_days || 0, storage: pre.storage || 'ambient' };   // new food: the cupboard, unless the scan or label says otherwise
    var cats = CATS.map(function (c) {
      return '<label class="cat-opt"><input type="radio" name="category" value="' + c.id + '"' + (c.id === v.category ? ' checked' : '') + '>' +
        '<span><i>' + c.icon + '</i>' + esc(c.short || c.label) + '</span></label>';
    }).join('');
    return sheetHead(it ? 'Edit item' : 'New item', it ? it.name : 'Add something to the stores') +
      '<form id="itemForm" data-cat="' + esc(v.category) + '" data-id="' + (it ? it.id : '') + '"' +
      (s.code ? ' data-barcode="' + esc(s.code) + '" data-product="' + esc(pre.name || '') + '"' : '') +
      (!it && s.shop ? ' data-shop="' + esc(s.shop) + '"' : '') + (!it && pre.ai_guessed ? ' data-guessed="' + esc(pre.ai_guessed) + '"' : '') + ' novalidate>' +
      (!it && !s.code && !pre.from_ai ? '<div class="btn-row add-ways"><button type="button" class="btn small" data-act="scan">📷 Scan a barcode</button>' +
        '<button type="button" class="btn small" data-act="scan-label">🤖 Read the label</button><span class="small muted">or type it in below</span></div>' + aiHint() : '') +
      (s.code ? '<p class="callout info small">Barcode ' + esc(s.code) + (pre.name ? ': details from Open Food Facts. Check them, then add.' : ': not in Open Food Facts, so fill it in once and it\'s remembered.') + '</p>'
        : pre.from_ai ? '<p class="callout info small">Read from the label by the AI. Check the details and the date, then add.</p>' : '') +
      '<label class="field"><span>Name</span><input type="text" name="name" value="' + esc(v.name) + '" maxlength="120" placeholder="e.g. Baked beans (415g)" autocomplete="off"' + (it ? '' : ' data-autofocus') + '>' +
      (it ? '' : '<div class="hint" data-dupe hidden></div>') + '</label>' +
      '<fieldset class="field"><legend>Category</legend><div class="cat-grid">' + cats + '</div></fieldset>' +
      '<div class="grid2"><label class="field"><span>Unit</span><input type="text" name="unit" value="' + esc(v.unit) + '" list="dl-units" placeholder="tin, pack, kg" maxlength="30" autocomplete="off"></label>' +
      '<label class="field"><span>Target stock</span><input type="number" name="target_qty" value="' + (v.target_qty || '') + '" inputmode="decimal" min="0" step="any" placeholder="0"></label></div>' +
      '<div class="field"><div class="grid2"><label><span class="sub-label">Used a day</span><input type="number" name="per_day" value="' + (v.per_day || '') + '" inputmode="decimal" min="0" step="any" placeholder="0"></label>' +
      '<label><span class="sub-label">Price each (£)</span><input type="number" name="price" value="' + (v.price || '') + '" inputmode="decimal" min="0" step="0.01" placeholder="Optional"></label></div>' +
      '<div class="hint" id="perDayHint"></div></div>' +
      '<div class="only-food"><label class="field"><span>Calories in one whole <span data-unitword>' + esc(v.unit || 'one') + '</span> (not per serving)</span><input type="number" name="kcal_per_unit" value="' + (v.kcal_per_unit || '') + '" inputmode="decimal" min="0" step="any" placeholder="e.g. 320 for a 400 g tin">' +
      '<div class="hint" data-kcalhint>' + kcalHint(v.kcal_per_unit, v.unit) + '</div></label>' +
      '<div class="date-row"><button type="button" class="btn small" data-act="scan-nutrition">📷 Read the nutrition label</button></div>' +
      '<div class="hint" data-nutri hidden></div>' +
      '<details class="calc"><summary>Work it out from the label</summary><div class="grid2">' +
      '<label class="field"><span>kcal per 100g</span><input type="number" data-calc="per100" inputmode="decimal" min="0" step="any"></label>' +
      '<label class="field"><span>Weight of the whole ' + esc(v.unit || 'pack') + ' (g or ml)</span><input type="number" data-calc="grams" inputmode="decimal" min="0" step="any"></label></div>' +
      '<p class="small muted">For a multipack, the whole pack: 6 × 330 ml is 1980.</p></details></div>' +
      '<div class="field"><span>Each one holds</span><div class="pack-row"><input type="number" name="pack_size" value="' + (v.pack_size || '') + '" inputmode="decimal" min="0" step="any" placeholder="Optional, e.g. 500">' +
      '<select name="pack_unit" aria-label="Pack size unit">' + [['g', 'g'], ['kg', 'kg'], ['ml', 'ml'], ['l', 'l'], ['oz', 'oz'], ['lb', 'lb'], ['each', 'items (a multipack)']].map(function (u) {
        return '<option value="' + u[0] + '"' + ((v.pack_unit || 'g') === u[0] ? ' selected' : '') + '>' + u[1] + '</option>';
      }).join('') + '</select></div><div class="hint">Lets you use part of one: 200 g of a 500 g bag, 1 can from a 6-pack, or say what\'s left in the open one.</div></div>' +
      '<fieldset class="field only-food"><legend>Kept before opening</legend><div class="use-mode" role="radiogroup" aria-label="Kept before opening">' +
      [['ambient', '🥫 Cupboard'], ['chilled', '❄️ Fridge'], ['frozen', '🧊 Freezer']].map(function (o) {
        return '<label class="seg-opt"><input type="radio" name="storage" value="' + o[0] + '"' + (v.storage === o[0] ? ' checked' : '') + '><span>' + o[1] + '</span></label>';
      }).join('') + '</div><div class="hint">Cupboard: tins, jars, dried and long-life food. Fridge and freezer food only lasts a day or two in a power cut.</div></fieldset>' +
      '<label class="field"><span>Once opened, use within (days)</span><input type="number" name="open_days" value="' + (v.open_days || '') + '" inputmode="numeric" min="0" step="1" placeholder="Optional, e.g. 3">' +
      '<div class="hint">An open tin of beans keeps about 3 days in the fridge. Once you\'ve used part of one, the rest goes off then, even if its best before is later.</div></label>' +
      '<label class="field only-water"><span>Litres in one</span><input type="number" name="litres_per_unit" value="' + (v.litres_per_unit || '') + '" inputmode="decimal" min="0" step="any" placeholder="e.g. 5">' +
      '<div class="hint">What you can drink. Left empty, it comes from "Each one holds" (5000 ml is 5 litres). Juice and milk count as food, and can stand in for drinking water (up to ' + fq(DRINK_CAP) + ' L a person a day), but not for cooking or washing.</div></label>' +
      (it ? '' : '<h3>Opening stock</h3><div class="field"><span>How many?</span>' + stepperHtml('qty', 1, 'Quantity') + '</div>' +
        expiryField(pre.expiry || '') + locationField(lastLocation(lastTouched()))) +
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
      expiryField(s.exp || '', usualLife(it), batchDates(it)) + locationField(s.loc ? s.loc : (lastLocation(it) || lastLocation(lastTouched()))) +
      '<p class="small muted">The same date and place as a batch you have adds to it. A different date starts a new batch.</p>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + ICON.plus + ' Add to stores</button></div></form>';
  }

  function sheetUse(s) {
    var it = byId(s.id);
    if (!it) return null;
    var i = info(it);
    var live = it.batches.filter(function (b) { return b.qty > 0; });
    var pick = live.length > 1 ? '<fieldset class="field use-batches"><legend>Which batch is it from?</legend><div class="opts">' + live.map(function (b, n) {
        return '<label class="opt"><input type="radio" name="batch_id" value="' + b.id + '"' + (n === 0 ? ' checked' : '') + ' data-exp="' + esc(b.printed_expiry || b.expiry || '') + '"><span>' +
          esc(b.expiry ? fmtDate(b.expiry) : 'No date') + ' · ' + esc(fq(b.qty)) + (b.location ? ' · ' + esc(b.location) : '') + (b.opened_at ? ' · opened' : '') +
          (n === 0 ? ' <small>(use first)</small>' : '') + '</span></label>';
      }).join('') + '</div><div class="date-row"><button type="button" class="btn small" data-act="scan-usebatch">📷 Match the date on it</button></div>' +
      '<div class="hint" data-scan-hint hidden></div></fieldset>' : '';
    var pk = it.pack_size > 0, pu = it.pack_unit || 'g', unitName = plural(it.unit || 'pack', 2);
    var modes = pk ? '<div class="use-mode" role="radiogroup" aria-label="How to say what you used">' +
      [['units', 'Whole ' + unitName], ['amount', pu === 'each' ? 'Single ones' : 'An amount (' + pu + ')'], ['left', 'What\'s left']].map(function (m, n) {
        return '<label class="seg-opt"><input type="radio" name="mode" value="' + m[0] + '"' + (n === 0 ? ' checked' : '') + '><span>' + esc(m[1]) + '</span></label>';
      }).join('') + '</div>' +
      '<div class="field use-amount" hidden><span>How much did you use?</span><div class="pack-row"><input type="text" name="amount" inputmode="decimal" autocomplete="off" placeholder="' + (pu === 'each' ? 'e.g. 1' : 'e.g. 200') + '">' +
      '<span class="pack-u">' + esc(pu === 'each' ? '' : pu) + '</span></div>' +
      '<div class="hint">' + esc(pu === 'each' ? fq(it.pack_size) + ' in each ' + (it.unit || 'pack') : 'Each holds ' + fq(it.pack_size) + ' ' + pu) + '.</div></div>' +
      '<div class="field use-left" hidden><span>How much is left in the open one?</span><div class="pack-row"><input type="text" name="left" inputmode="decimal" autocomplete="off" placeholder="' + (pu === 'each' ? 'e.g. 4' : 'e.g. 300') + '">' +
      '<span class="pack-u">' + esc(pu === 'each' ? '' : pu) + '</span></div>' +
      '<div class="hint">' + esc(packWords(it, i.total) ? 'Now: ' + packWords(it, i.total) + '.' : 'None open yet: this opens one.') + '</div></div>' : '';
    return sheetHead('Use stock', it.name, cat(it.category).icon) +
      '<form id="useForm" data-id="' + it.id + '" data-pack="' + (pk ? it.pack_size : 0) + '" novalidate>' + modes +
      '<div class="field use-units"><span>' + esc(howMany(it.unit)) + '</span>' + stepperHtml('qty', 1, 'Quantity') +
      '<div class="quick"><button type="button" class="chip" data-setqty="' + i.total + '">All of it (' + esc(fq(i.total)) + ')</button></div>' +
      '<div class="hint">You have ' + esc(qu(i.total, it.unit)) + (packWords(it, i.total) ? ' (' + esc(packWords(it, i.total)) + ')' : '') + '. ' +
      (live.length > 1 ? 'Pick the batch it\'s from below.' : 'The oldest expiry date is used first.') + '</div></div>' + pick +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">' + ICON.minus + ' Use it</button></div></form>';
  }

  function sheetBatch(s) {
    var it = byId(s.item);
    var b = it && it.batches.filter(function (x) { return x.id === s.id; })[0];
    if (!b) return null;
    return sheetHead('Edit batch', it.name, cat(it.category).icon) +
      '<form id="batchForm" data-id="' + b.id + '" novalidate>' +
      '<div class="field"><span>Quantity</span>' + stepperHtml('qty', fq(b.qty).replace(/,/g, ''), 'Quantity') + '</div>' +
      expiryField(b.printed_expiry !== undefined ? b.printed_expiry : b.expiry) + locationField(b.location) +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">Save batch</button>' +
      '<button class="btn danger block" type="button" data-act="del-batch" data-id="' + b.id + '">' + ICON.trash + ' Remove this batch</button></div></form>';
  }

  // ------------------------------------------------------------------
  // Scanning (1.13.0). Barcodes are read here on the phone, with the bundled ZXing library: from a live
  // camera where the browser allows it (https only), otherwise from a photo. A new barcode is looked up in
  // Open Food Facts on the Pi. Dates and labels are read from a photo by the AI chosen in HQ → Scanning.
  // ------------------------------------------------------------------
  // With a pack size: 1.6 bags of 500 g is "1 bag + 300 g in the open one".
  function packWords(it, q) {
    if (!(it.pack_size > 0)) return '';
    var whole = Math.floor(q + 1e-6), part = Math.round((q - whole) * it.pack_size * 10) / 10;
    if (part <= 0) return '';
    if (it.pack_unit === 'each') part = Math.round(part);
    var amt = it.pack_unit === 'each' ? fq(part) : fq(part) + ' ' + it.pack_unit;
    return (whole ? fq(whole) + ' ' + plural(it.unit || 'pack', whole) + ' + ' : '') + amt + (whole ? ' in the open one' : ' left in the open one');
  }
  // The best before dates of the batches you have, newest first: one tap to add more of the same.
  function batchDates(it) {
    var seen = {};
    return it.batches.filter(function (b) { var d = b.printed_expiry || b.expiry; return d && !b.opened_at && !seen[d] && (seen[d] = true); })
      .map(function (b) { return b.printed_expiry || b.expiry; }).sort().reverse().slice(0, 3);
  }

  var zxingLoad = null;
  function loadZXing() {
    if (window.ZXing) return Promise.resolve(window.ZXing);
    if (!zxingLoad) zxingLoad = new Promise(function (ok, no) {
      var sc = document.createElement('script');
      sc.src = 'zxing.min.js';
      sc.onload = function () { ok(window.ZXing); };
      sc.onerror = function () { zxingLoad = null; no(new Error('Couldn\'t load the barcode reader')); };
      document.head.appendChild(sc);
    });
    return zxingLoad;
  }
  function takePhoto() {
    return new Promise(function (ok) {
      var inp = document.createElement('input');
      inp.type = 'file'; inp.accept = 'image/*'; inp.setAttribute('capture', 'environment');
      inp.style.display = 'none';
      var done = function (f) { ok(f || null); if (inp.parentNode) inp.remove(); };
      inp.addEventListener('change', function () { done(inp.files && inp.files[0]); });
      inp.addEventListener('cancel', function () { done(null); });   // picker closed without a photo
      document.body.appendChild(inp);
      inp.click();
    });
  }
  // A photo, scaled down, as a JPEG data: URL. Read with FileReader (data:, which the page's security
  // policy allows; blob: isn't), as phones take far bigger photos than reading a label needs.
  function shrinkPhoto(file, max) {
    return new Promise(function (ok, no) {
      var fail = function () { no(new Error('That photo couldn\'t be opened. Try again, or take it with the camera rather than choosing a file.')); };
      if (!file || !file.size) { fail(); return; }
      var rd = new FileReader();
      rd.onerror = fail;
      rd.onload = function () {
        var img = new Image();
        img.onload = function () {
          var k = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
          var c = document.createElement('canvas');
          c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
          c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
          ok(c.toDataURL('image/jpeg', 0.85));
        };
        img.onerror = fail;
        img.src = rd.result;
      };
      rd.readAsDataURL(file);
    });
  }
  function barcodeHints(Z) {
    var hints = new Map();
    hints.set(Z.DecodeHintType.POSSIBLE_FORMATS, [Z.BarcodeFormat.EAN_13, Z.BarcodeFormat.EAN_8, Z.BarcodeFormat.UPC_A, Z.BarcodeFormat.UPC_E,
      Z.BarcodeFormat.RSS_14, Z.BarcodeFormat.RSS_EXPANDED, Z.BarcodeFormat.CODE_128, Z.BarcodeFormat.ITF]);
    hints.set(Z.DecodeHintType.TRY_HARDER, true);
    return hints;
  }
  // A photo, redrawn: cropped to the middle, shrunk, or turned, as ZXing often misses a barcode that's small,
  // large or sideways in a big photo.
  function photoVariant(img, crop, max, turn) {
    var w = img.naturalWidth * crop, h = img.naturalHeight * crop, k = Math.min(1, max / Math.max(w, h));
    var c = document.createElement('canvas'), x = c.getContext('2d');
    c.width = Math.round((turn ? h : w) * k); c.height = Math.round((turn ? w : h) * k);
    if (turn) { x.translate(c.width, 0); x.rotate(Math.PI / 2); }
    x.drawImage(img, (img.naturalWidth - w) / 2, (img.naturalHeight - h) / 2, w, h, 0, 0, Math.round(w * k), Math.round(h * k));
    return c.toDataURL('image/jpeg', 0.9);
  }
  function readCode(Z, dataUrl) {
    return new Promise(function (ok) {
      var img = new Image();
      img.onload = function () { ok(img); };
      img.onerror = function () { ok(null); };
      img.src = dataUrl;
    }).then(function (img) {
      if (!img) return null;
      // The phone's own reader first, where there is one (Android Chrome): it's quicker and copes with more.
      var native = window.BarcodeDetector ? new window.BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'itf'] })
        .detect(img).then(function (r) { return r && r[0] ? r[0].rawValue : null; }, function () { return null; }) : Promise.resolve(null);
      return native.then(function (code) {
        if (code) return code;
        var hints = barcodeHints(Z);
        var tries = [[1, 1600, false], [0.6, 1200, false], [1, 900, false], [1, 1600, true], [0.6, 1200, true], [0.4, 900, false]];
        var go = function (n) {
          if (n >= tries.length) return null;
          var t = tries[n];
          return new Z.BrowserMultiFormatReader(hints).decodeFromImageUrl(photoVariant(img, t[0], t[1], t[2]))   // 1,600 px first
            .then(function (res) { return res.getText(); }, function () { return go(n + 1); });
        };
        return go(0);
      });
    });
  }
  var LOOKING = 'Looking for the barcode…';
  function scanBarcode(btn) {
    return takePhoto().then(function (file) {
      if (!file) return;
      return run(function () {
        toast(LOOKING, { ms: 120000 });   // stays up while it looks (a photo with no barcode takes a few seconds)
        return Promise.all([loadZXing(), shrinkPhoto(file, 2000)]).then(function (r) {
          return readCode(r[0], r[1]).then(function (code) {
            untoast(LOOKING);
            if (code) return lookupBarcode(code, btn, r[1]);
            scanNote('photo-nobarcode');
            return openSheet({ type: 'scanfail', img: r[1] });
          });
        });
      }, btn).then(function () { untoast(LOOKING); });
    });
  }
  // DataBar and GS1-128 give "(01)05012345678900…": the product number is the 14 digits after 01.
  function productCode(raw) {
    var t = String(raw || '').replace(/[()\s]/g, '');
    var m = /^01(\d{14})/.exec(t);
    if (m) t = m[1];
    if (/^\d{14}$/.test(t) && t.charAt(0) === '0') t = t.slice(1);
    return t;
  }
  // Tell the Pi how a scan went, so its log says why one didn't work (camera refused, no barcode found...).
  function scanNote(what, detail) {
    try { api('POST', 'api/scan/note', { what: what, detail: detail || '' }).catch(function () { /* fine */ }); } catch (e) { /* fine */ }
  }
  // Not in Open Food Facts, or it doesn't know the calories or size: read the rest from the photo, if there is one.
  function needsLabel(p, code) {
    if (!p || !p.name || p.name === code) return true;
    return (p.category === 'food' || p.category === 'drinks') && (!p.kcal_per_unit || !p.grams);
  }
  function lookupBarcode(code, btn, img) {
    var raw = code;
    code = productCode(code);
    if (!/^[0-9]{6,14}$/.test(code || '')) { scanNote('not-product', String(raw || '').slice(0, 30)); toast('That isn\'t a product barcode. Try another, read the label, or choose from your stores.', { error: true }); return; }
    return run(function () {
      return api('GET', 'api/scan/barcode?code=' + encodeURIComponent(code)).then(function (r) {
        if (stack.length && stack[stack.length - 1].type === 'scancode') closeSheet();
        if (r.item_id && byId(r.item_id)) return openSheet({ type: 'scanhit', id: r.item_id });
        if (r.product && (!r.product.name || r.product.name === code)) r.product = null;   // known, but with no name
        if (img && aiOn() && needsLabel(r.product, code)) {
          toast(r.product ? 'Open Food Facts is missing some details: reading the rest from your photo…' : 'Not in Open Food Facts: reading the label in your photo…');
          return api('POST', 'api/scan/label', { image: img, known: Object.assign({ code: code }, r.product || {}) }).then(function (x) {
            SCAN_AI = null;
            return openSheet({ type: 'scanned', code: code, product: x.product, fromPhoto: true });
          }, function () {
            return openSheet({ type: 'scanned', code: code, product: r.product, lookupError: r.lookup_error });
          });
        }
        return openSheet({ type: 'scanned', code: code, product: r.product, lookupError: r.lookup_error });
      });
    }, btn);
  }
  function sheetScanCode() {
    return sheetHead('Type the barcode', 'The numbers under the bars', '🔢') +
      '<div class="field"><span>Barcode</span><input type="text" id="scanCode" inputmode="numeric" pattern="[0-9]*" maxlength="14" autocomplete="off" data-autofocus></div>' +
      '<div class="sheet-actions"><button class="btn primary block" data-act="scan-code">Look it up</button>' +
      '<button class="btn block" data-act="scan-photo">📷 Try another photo</button></div>';
  }
  // A barcode you've scanned before: putting one in, or taking one out?
  function sheetScanHit(s) {
    var it = byId(s.id);
    if (!it) return null;
    var i = info(it);
    return sheetHead(it.name, qu(i.total, it.unit) + ' in stock', cat(it.category).icon) +
      '<div class="scan-choice"><button class="btn primary block" data-act="stock" data-id="' + it.id + '">' + ICON.plus + ' Putting it in the stores</button>' +
      '<button class="btn block" data-act="use-sheet" data-id="' + it.id + '"' + (i.none ? ' disabled' : '') + '>' + ICON.minus + ' Taking it out to use</button></div>' +
      '<p class="small muted">Taking one out: if you have more than one batch, you can match the date on it, so the right batch goes down.</p>';
  }
  // A barcode we haven't seen: a new item, or another brand of something you already keep.
  function sheetScanned(s) {
    var p = s.product, words = ((p && p.name) || '').toLowerCase().replace(/[^a-z ]/g, ' ').split(/\s+/).filter(function (w) { return w.length > 2; });
    var scored = S.items.map(function (it) {
      var n = it.name.toLowerCase();
      return { it: it, score: words.filter(function (w) { return n.indexOf(w) >= 0; }).length };
    }).filter(function (x) { return x.score > 0; }).sort(function (a, b) { return b.score - a.score || a.it.name.localeCompare(b.it.name); }).slice(0, 6);
    var row = function (it) {
      return '<button class="li" data-act="scan-link" data-id="' + it.id + '"><span class="li-ico">' + cat(it.category).icon + '</span><span class="li-main">' +
        '<span class="li-title">' + esc(it.name) + '</span><span class="li-sub">' + esc(qu(info(it).total, it.unit)) + ' in stock</span></span>' + ICON.chev + '</button>';
    };
    return sheetHead(p && p.name ? p.name : 'New barcode', s.code ? 'Barcode ' + s.code : 'Read from the label by the AI: check it', s.code ? '📦' : '🤖') +
      (p ? '<p class="small">' + esc([p.unit && p.unit !== 'pack' ? 'A ' + p.unit : '', p.quantity, p.kcal_per_unit ? p.kcal_per_unit + ' kcal for the whole ' + (p.unit || 'pack') : '', p.brand,
            p.open_days ? 'once opened, ' + p.open_days + ' days' : '', p.storage === 'chilled' ? 'kept in the fridge' : p.storage === 'frozen' ? 'kept in the freezer' : '',
            p.expiry ? 'best before ' + fmtDate(p.expiry) : ''].filter(Boolean).join(' · ')) + '</p>' +
          (p.ai_guessed ? '<p class="small muted">' + esc((p.ai_guessed.indexOf('kcal') >= 0 ? 'No calories printed in the photo, so they\'re the AI\'s estimate for this kind of product' : 'The days once opened are the AI\'s estimate')) + ': marked "AI estimate" until you change them.</p>' : '') +
          '<button class="btn block" data-act="scan-label-more" style="margin-bottom:10px">📷 Add another photo (back, nutrition, date)</button>' +
          (p.how ? '<p class="small muted">From the label: ' + esc(p.how) + '</p>' : '') +
          ((p.category === 'food' || p.category === 'drinks' || p.category === 'pets') && !p.kcal_per_unit
            ? '<p class="small muted">No calories in Open Food Facts for this one.</p><button class="btn block" data-act="scan-nutrition" style="margin-bottom:10px">📷 Read the nutrition label</button>' : '')
        : '<p class="small muted">' + (s.lookupError ? 'Couldn\'t reach Open Food Facts just now.' : 'Not in Open Food Facts.') + (aiOn() ? ' The AI can read the label instead, or type it in.' : ' Add it as a new item and type in the details: they\'re remembered for next time.') + '</p>' + aiHint() +
          '<button class="btn block" data-act="scan-label" data-code="' + esc(s.code || '') + '" style="margin-bottom:10px">🤖 Read the label with AI</button>') +
      '<button class="btn primary block" data-act="scan-new">' + ICON.plus + ' Add as a new item</button>' +
      (S.items.length ? '<h3>Or add it to something you already keep</h3><p class="small muted">Another brand of the same thing goes on the same line, with its own batches.' +
        (s.code ? ' The barcode is remembered.' : '') + '</p>' +
        (scored.length ? '<div class="list">' + scored.map(function (x) { return row(x.it); }).join('') + '</div>' : '') +
        '<details class="scan-all"><summary>All items</summary><div class="list">' + S.items.slice().sort(byName).map(row).join('') + '</div></details>' : '');
  }
  // No barcode in the photo: the AI can read the label instead (name, size, calories, date).
  function sheetScanFail(s) {
    return sheetHead('No barcode found', 'In that photo', '🔍') +
      '<p class="small">The photo was read six ways (whole, middle, smaller, turned) and no barcode came out. Usually it\'s one of these:</p>' +
      '<ul class="small scan-why"><li><b>Too far away or blurred:</b> get close enough that the barcode fills most of the photo, and hold still.</li>' +
      '<li><b>Glare:</b> shiny wrappers and curved tins reflect the light. Tilt it a little, or turn the light off.</li>' +
      '<li><b>Creased, torn or wrapped round a corner:</b> flatten it, or type the numbers under the bars.</li>' +
      '<li><b>No barcode at all</b> (one can from a multipack): read the label or choose from your stores.</li></ul>' +
      (aiOn() ? '<p class="small">The AI can read the label instead: the name, size, what it\'s in, calories and best before date.</p>' : aiHint()) +
      '<div class="scan-choice"><button class="btn primary block" data-act="scan-label-same">🤖 Read the label from this photo</button>' +
      '<button class="btn block" data-act="scan-label">📷 Take a photo of the front of the pack</button>' +
      '<button class="btn block" data-act="scan-photo">Try the barcode again</button>' +
      '<button class="btn block" data-act="scan-type">🔢 Type the numbers</button>' +
      (S.items.length ? '<button class="btn block" data-act="scan-pick">📋 Choose from your stores</button>' : '') + '</div>';
  }
  // No barcode at all (a can from a multipack, say): pick the item, then put one in or take one out.
  function sheetScanPick() {
    return sheetHead('Choose from your stores', 'For things without a barcode', '📋') +
      '<div class="search">' + ICON.search + '<input type="search" id="pickQ" placeholder="Search" autocomplete="off" data-autofocus aria-label="Search your stores"></div>' +
      '<div class="list" id="pickList">' + pickRows('') + '</div>';
  }
  function pickRows(q) {
    q = q.trim().toLowerCase();
    return S.items.filter(function (it) { return !q || it.name.toLowerCase().indexOf(q) >= 0; }).sort(byName).slice(0, 60).map(function (it) {
      return '<button class="li" data-act="scan-picked" data-id="' + it.id + '"><span class="li-ico">' + cat(it.category).icon + '</span><span class="li-main">' +
        '<span class="li-title">' + esc(it.name) + '</span><span class="li-sub">' + esc(qu(info(it).total, it.unit)) + ' in stock</span></span>' + ICON.chev + '</button>';
    }).join('') || '<p class="small muted">Nothing matches. Close this and use Add item.</p>';
  }
  // A photo of the nutrition panel: calories for one whole unit (kcal per 100 g × what the whole pack weighs).
  function packGrams(size, unit) {
    var k = { g: 1, kg: 1000, ml: 1, l: 1000, oz: 28.35, lb: 453.6 }[unit];
    return size > 0 && k ? size * k : null;
  }
  function readNutrition(btn) {
    var f = btn.closest('form'), top = stack[stack.length - 1], p = top && top.type === 'scanned' ? top.product : null;
    var grams = f ? packGrams(num(f.elements.pack_size.value), f.elements.pack_unit.value) : p ? p.grams : null;
    var hint = f && $('[data-nutri]', f);
    return takePhoto().then(function (file) {
      if (!file) return;
      if (hint) { hint.hidden = false; hint.className = 'hint'; hint.textContent = 'Reading the nutrition label…'; }
      return run(function () {
        return shrinkPhoto(file, 1600).then(function (img) { return api('POST', 'api/scan/nutrition', { image: img, grams: grams }); }).then(function (r) {
          SCAN_AI = null;
          if (p && !f) {   // a scan result: carry the calories (and weight) on to Add as a new item
            p.how = r.how;
            if (r.kcal_per_unit) p.kcal_per_unit = r.kcal_per_unit;
            if (r.grams && !p.grams) p.grams = r.grams;
            return showSheet();
          }
          if (r.kcal_per_unit) {
            f.elements.kcal_per_unit.value = r.kcal_per_unit;
            f.elements.kcal_per_unit.dispatchEvent(new Event('input', { bubbles: true }));
          }
          if (r.grams && !(num(f.elements.pack_size.value) > 0)) {
            f.elements.pack_size.value = r.grams;
            f.elements.pack_unit.value = f.dataset.cat === 'drinks' ? 'ml' : 'g';
          }
          if (r.kcal_100g) { var c1 = $('[data-calc="per100"]', f), c2 = $('[data-calc="grams"]', f); if (c1) c1.value = r.kcal_100g; if (c2 && r.grams) c2.value = r.grams; }
          hint.className = 'hint' + (r.kcal_per_unit ? '' : ' err');
          hint.innerHTML = 'From the label: <b>' + esc(r.how) + '</b>.' + (r.kcal_serving ? ' (A serving is ' + esc(fq(r.kcal_serving)) + ' kcal: not used.)' : '') + ' Check it, then save.';
        });
      }, btn).then(function () { if (hint && hint.textContent === 'Reading the nutrition label…') hint.hidden = true; });
    });
  }
  function readLabel(img, btn, code, known) {
    return run(function () {
      toast(known ? 'Adding what this photo shows…' : 'Reading the label…');
      return api('POST', 'api/scan/label', { image: img, known: known || null }).then(function (r) {
        SCAN_AI = null;   // the spend figures have moved
        var top = stack.length && stack[stack.length - 1].type;
        if (top === 'scanfail' || (top === 'scanned' && (code || known))) closeSheet();
        return openSheet({ type: 'scanned', code: code || '', product: r.product });   // a barcode stays with it
      });
    }, btn);
  }
  function scanDate(btn) {
    var field = btn.closest('.field'), input = field.querySelector('input[type="date"]'), hint = field.querySelector('[data-scan-hint]');
    return takePhoto().then(function (file) {
      if (!file) return;
      hint.hidden = false; hint.className = 'hint'; hint.textContent = 'Reading the date…';
      return shrinkPhoto(file, 1280).then(function (img) { return api('POST', 'api/scan/date', { image: img }).then(function (r) { SCAN_AI = null; return r; }); }).then(function (r) {
        if (r.date) {
          input.value = r.date;
          hint.innerHTML = 'Read as <b>' + esc(fmtDate(r.date)) + '</b>. Check it\'s right before saving.';
        } else {
          hint.className = 'hint err';
          hint.textContent = 'Couldn\'t see a date in that photo. Try closer, with the date in the middle, or pick it.';
        }
      }, function (e) { hint.className = 'hint err'; hint.textContent = e.message; });
    });
  }
  // Taking one out: read the date on it and tick the batch with that date (or the nearest).
  function scanUseBatch(btn) {
    var fs = btn.closest('fieldset'), hint = fs.querySelector('[data-scan-hint]');
    return takePhoto().then(function (file) {
      if (!file) return;
      hint.hidden = false; hint.className = 'hint'; hint.textContent = 'Reading the date…';
      return shrinkPhoto(file, 1280).then(function (img) { return api('POST', 'api/scan/date', { image: img }).then(function (r) { SCAN_AI = null; return r; }); }).then(function (r) {
        var radios = $$('input[name="batch_id"]', fs);
        if (!r.date) { hint.className = 'hint err'; hint.textContent = 'Couldn\'t see a date. Pick the batch instead.'; return; }
        var t = parseYmd(r.date).getTime(), best = null, bestGap = Infinity;
        radios.forEach(function (x) {
          if (!x.dataset.exp) return;
          var gap = Math.abs(parseYmd(x.dataset.exp).getTime() - t);
          if (gap < bestGap) { best = x; bestGap = gap; }
        });
        if (best && bestGap <= 45 * 86400000) {
          best.checked = true;
          hint.innerHTML = 'Read as <b>' + esc(fmtDate(r.date)) + '</b>: that\'s the batch dated ' + esc(fmtDate(best.dataset.exp)) + '.';
        } else {
          hint.className = 'hint err';
          hint.textContent = 'Read as ' + fmtDate(r.date) + ', which doesn\'t match a batch you have. Pick one, or check its date.';
        }
      }, function (e) { hint.className = 'hint err'; hint.textContent = e.message; });
    });
  }
  // Typing a new item that's already in the stores: offer to add stock to it instead.
  function dupeHint(f) {
    var box = $('[data-dupe]', f);
    if (!box) return;
    var n = f.elements.name.value.trim().toLowerCase();
    var hit = n.length > 2 && S.items.filter(function (it) { return it.name.toLowerCase() === n || it.name.toLowerCase().indexOf(n) === 0; })[0];
    box.hidden = !hit;
    box.innerHTML = hit ? 'You already have <b>' + esc(hit.name) + '</b>. <button type="button" class="link" data-act="dupe-stock" data-id="' + hit.id + '">Add stock to it instead</button>' : '';
  }

  // Live scanning: a viewfinder that reads the barcode as soon as it's in the box. Browsers only allow the
  // camera on https; anywhere else (or if it's refused, or Home Assistant's page doesn't allow it) Scan takes a
  // photo instead, for the rest of the visit.
  var LIVE = null, LIVE_FAILED = false;
  function liveOk() {
    return !LIVE_FAILED && !!(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }
  function stopLive() {
    if (!LIVE) return;
    var l = LIVE;
    LIVE = null;
    try { if (l.reader) l.reader.reset(); } catch (e) { /* already stopped */ }
    try { if (l.stream) l.stream.getTracks().forEach(function (t) { t.stop(); }); } catch (e) { /* fine */ }
  }
  function sheetLiveScan() {
    return sheetHead('Scan a barcode', 'Hold it inside the box', '📷') +
      '<div class="live-wrap"><video id="liveVideo" playsinline muted autoplay></video><div class="live-box" aria-hidden="true"></div>' +
      '<button type="button" class="btn small live-torch" data-act="scan-torch" hidden>🔦 Torch</button></div>' +
      '<p class="small muted center" id="liveStatus" role="status">Starting the camera…</p>' +
      '<div class="live-alt"><button class="live-opt" data-act="scan-photo"><i aria-hidden="true">📷</i>Take a photo</button>' +
      '<button class="live-opt" data-act="scan-label"><i aria-hidden="true">🤖</i>Read the label</button>' +
      '<button class="live-opt" data-act="scan-type"><i aria-hidden="true">🔢</i>Type the number</button>' +
      (S.items.length ? '<button class="live-opt" data-act="scan-pick"><i aria-hidden="true">📋</i>Pick from stores</button>' : '') + '</div>';
  }
  function liveStatus(text, bad) {
    var el = $('#liveStatus');
    if (el) { el.textContent = text; el.className = 'small center ' + (bad ? 'err' : 'muted'); }
  }
  function startLive() {
    var v = $('#liveVideo');
    if (!v || LIVE) return;
    var token = {};
    LIVE = { token: token };
    var mine = function () { return LIVE && LIVE.token === token; };
    loadZXing().then(function (Z) {
      if (!mine()) return;
      var reader = new Z.BrowserMultiFormatReader(barcodeHints(Z), 200);
      LIVE.reader = reader;
      return reader.decodeFromConstraints({ audio: false, video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } } }, v,
        function (res) {
          if (!res || !mine()) return;
          var code = res.getText();
          try { if (navigator.vibrate) navigator.vibrate(60); } catch (e) { /* no buzz */ }
          stopLive();
          liveStatus('Got ' + code);
          // Opens on top: close it to scan the next one. Not a product barcode, or the lookup failed: keep scanning.
          Promise.resolve(lookupBarcode(code)).then(function () {
            if (!LIVE && stack.length && stack[stack.length - 1].type === 'livescan') setTimeout(startLive, 1200);
          });
        }).then(function () {
          if (!mine()) return;
          var st = v.srcObject, tr = st && st.getVideoTracks && st.getVideoTracks()[0];
          LIVE.stream = st;
          LIVE.track = tr;
          var caps = tr && tr.getCapabilities ? tr.getCapabilities() : {};
          if (caps && caps.torch) { var tb = $('.live-torch'); if (tb) tb.hidden = false; }
          liveStatus('Point the camera at the barcode');
          setTimeout(function () {   // still nothing: say why it might be
            if (mine()) liveStatus('Not reading it yet. Get closer so the barcode fills the box, keep it flat and out of glare, or take a photo instead.');
          }, 9000);
        });
    }).catch(function (e) {
      if (mine()) stopLive();
      LIVE_FAILED = true;
      var framed = false;
      try { framed = window.self !== window.top; } catch (x) { framed = true; }
      var name = e && e.name;
      liveStatus(name === 'NotAllowedError' ? (framed ? 'The live camera isn\'t allowed here: either camera permission was refused, or Home Assistant doesn\'t let add-ons use it. Scan will take a photo instead.'
          : 'The camera wasn\'t allowed. Allow the camera for this browser, or take a photo instead.')
        : name === 'NotFoundError' || name === 'OverconstrainedError' ? 'No camera found. Take a photo instead, or type the numbers.'
        : 'The live camera isn\'t available here. Take a photo instead.', true);
    });
  }
  function toggleTorch(btn) {
    if (!LIVE || !LIVE.track) return;
    LIVE.torch = !LIVE.torch;
    LIVE.track.applyConstraints({ advanced: [{ torch: LIVE.torch }] }).then(function () {
      btn.classList.toggle('primary', LIVE && LIVE.torch);
    }, function () { btn.hidden = true; });
  }

  // HQ → Scanning: which AI reads dates and labels. Keys stay on the Pi and are never shown back.
  var SCAN_AI = null;
  function scanHqCard() {
    if (!SCAN_AI) {
      api('GET', 'api/scan/ai').then(function (r) { SCAN_AI = r; var el = $('#scanAiCard'); if (el) el.outerHTML = scanHqCard(); }, function () { /* offline */ });
      return '<section class="card" id="scanAiCard"><div class="card-head"><h2>Scanning</h2></div><p class="small muted">Loading…</p></section>';
    }
    var c = SCAN_AI, P = c.providers, prov = c.provider;
    var keyBox = prov === 'ha' ? '<p class="small muted">' + (c.ha_entities.length ? 'Uses ' + esc(c.ha_entities[0]) + (c.ha_entities.length > 1 ? ', then the others if it fails' : '') + '. Add or change AIs in Home Assistant: Settings → Devices &amp; services.'
        : 'No AI Task set up in Home Assistant yet. Add Google Gemini, Anthropic or OpenAI there, or pick a provider here and add its key.') + '</p>'
      : '<div class="field"><span>' + esc(P[prov].name) + ' API key</span>' +
        '<input type="password" autocomplete="off" spellcheck="false" data-scanai="key_' + prov + '" placeholder="' + (c.keys_set.indexOf(prov) >= 0 ? 'Saved. Paste a new key to replace it' : 'Paste your key here') + '">' +
        (c.keys_set.indexOf(prov) >= 0 ? '<button type="button" class="link" data-act="scanai-forget" data-prov="' + prov + '">Remove the saved key</button>' : '') + '</div>' +
        '<div class="field"><span>Model</span><input type="text" autocomplete="off" data-scanai="model" value="' + esc(c.model) + '" placeholder="' + esc(P[prov].model) + '"></div>';
    return '<section class="card" id="scanAiCard"><div class="card-head"><h2>Scanning</h2></div>' +
      '<p class="small muted">Barcodes are read on this phone and looked up in Open Food Facts (only the barcode is sent). Best before dates, and labels without a barcode, are read from a photo by an AI: about 0.1p a photo.</p>' +
      '<div class="field"><span>Who reads the photos</span><select data-scanai="provider" aria-label="Who reads the photos">' +
      Object.keys(P).map(function (k) { return '<option value="' + k + '"' + (k === prov ? ' selected' : '') + '>' + esc(P[k].name) + (k !== 'ha' && c.keys_set.indexOf(k) >= 0 ? ' (key saved)' : '') + '</option>'; }).join('') +
      '</select></div>' + keyBox +
      '<h3>Missing details</h3><p class="small">The AI can estimate calories for a whole pack, what one holds, and how long things keep once opened, from their names, for you to check.</p>' +
      (aiOn() ? '<div class="btn-row"><button class="btn" data-act="ai-fill">🤖 Fill in missing details</button></div>' : '<p class="small muted">Set up an AI above to use this.</p>') +
      spendBox(c) + offlineBox() + '</section>';
  }
  // What the AI has cost: this month, today, what's left of the limit, and the last few calls.
  function usd(v) { return v == null ? 'not priced' : '$' + (v < 0.01 && v > 0 ? v.toFixed(4) : v.toFixed(2)); }
  function spendBox(c) {
    var st = c.stats, lim = c.limit_usd || 0;
    if (!st) return '';
    var pct = lim ? Math.min(100, Math.round(100 * st.cost_usd / lim)) : 0;
    var tile = function (val, label, state) {
      return '<div class="stat"' + (state ? ' data-state="' + state + '"' : '') + '><span class="stat-val">' + esc(val) + '</span><span class="stat-lbl">' + esc(label) + '</span></div>';
    };
    var rows = (c.recent || []).map(function (r) {
      return '<tr><td>' + esc(fmtDate(r.ts.slice(0, 10))) + ' ' + esc(r.ts.slice(11, 16)) + '</td><td>' + esc(r.task.replace('Dads Army ', '')) + '</td>' +
        '<td>' + esc(r.model || r.ai.replace('ai_task.', '')) + '</td><td>' + (r.tokens_in || r.tokens_out ? r.tokens_in + ' / ' + r.tokens_out : '–') + '</td>' +
        '<td>' + (r.ok ? esc(usd(r.cost_usd)) : '<span class="err" title="' + esc(r.note) + '">failed</span>') + '</td></tr>';
    }).join('');
    return '<h3>AI use and spending</h3><div class="stats">' +
      tile(usd(st.cost_usd), lim ? 'spent of $' + lim.toFixed(2) : 'spent this month', lim && st.cost_usd >= lim ? 'bad' : lim && pct >= 80 ? 'warn' : '') +
      tile(String(st.ok), 'AI answers this month') +
      tile(String(st.today.ok), 'today (' + usd(st.today.cost_usd) + ')') +
      (lim ? tile(usd(st.left_usd), 'left this month', st.left_usd <= 0 ? 'bad' : '') : tile(usd(st.last_month.cost_usd), 'last month')) +
      '</div>' + (lim ? '<div class="ai-meter"><span style="width:' + pct + '%"></span></div>' : '') +
      '<p class="small muted">' + [
        st.tasks.dates ? st.tasks.dates + ' best before date' + (st.tasks.dates === 1 ? '' : 's') : '',
        st.tasks.labels ? st.tasks.labels + ' label' + (st.tasks.labels === 1 ? '' : 's') : '',
        st.tasks.filled ? st.tasks.filled + ' fill-in' + (st.tasks.filled === 1 ? '' : 's') : '',
        st.tasks.review ? st.tasks.review + ' stores review' + (st.tasks.review === 1 ? '' : 's') : '',
        st.tasks.briefing ? st.tasks.briefing + ' briefing' + (st.tasks.briefing === 1 ? '' : 's') : '',
        st.tasks.other ? st.tasks.other + ' other (names translated)' : '',
        st.failed ? st.failed + ' failed' : '',
        st.avg_usd != null ? 'about ' + usd(st.avg_usd) + ' each' : '',
        (st.tokens_in + st.tokens_out) + ' tokens'
      ].filter(Boolean).join(' · ') + '. In Home Assistant: sensor.dads_army_ai_spend.' +
      (c.provider === 'ha' ? ' Through Home Assistant\'s AI Task the cost isn\'t known here: check your AI provider\'s own page.' : '') + '</p>' +
      '<div class="field"><span>Monthly limit (US dollars)</span>' +
      '<input type="text" inputmode="decimal" autocomplete="off" data-scanai="limit_usd" value="' + (lim || '') + '" placeholder="No limit, e.g. 1">' +
      '<div class="hint">Once this month\'s spend reaches it, nothing more is sent to Claude, Gemini or OpenAI with your API key until the 1st. ' +
      'Costs are worked out here from each call\'s tokens and the provider\'s list price (an unknown model is counted on the high side). ' +
      'The limit doesn\'t cover the Home Assistant AI Task route, which is billed there.</div></div>' +
      (rows ? '<details class="ai-calls"><summary>Recent AI calls</summary><div class="table-wrap"><table class="ai-table"><thead><tr><th>When</th><th>What</th><th>Model</th><th>Tokens in / out</th><th>Cost</th></tr></thead><tbody>' +
        rows + '</tbody></table></div></details>' : '');
  }
  // The offline barcode list: on/off, how it's doing, and Update now.
  var OFFLINE_ST = null, offlineTimer = null;
  function offlineBox() {
    if (!OFFLINE_ST) {
      api('GET', 'api/scan/offline').then(function (r) { OFFLINE_ST = r; redrawScanCard(); }, function () { /* offline */ });
      return '';
    }
    var o = OFFLINE_ST, state;
    if (o.building) {
      state = 'Updating: ' + (o.total_mb ? o.read_mb + ' of ' + o.total_mb + ' MB read' : 'starting') + (o.kept ? ', ' + nf0.format(o.kept) + ' UK products so far' : '') + '. This takes a while; you can carry on.';
      clearTimeout(offlineTimer);
      offlineTimer = setTimeout(function () { api('GET', 'api/scan/offline').then(function (r) { OFFLINE_ST = r; redrawScanCard(); }); }, 8000);
    } else if (o.built_at) {
      state = nf0.format(o.count) + ' UK products, updated ' + fmtDate(o.built_at.slice(0, 10)) + ' (' + o.size_mb + ' MB). It updates itself each month, overnight.';
    } else {
      state = o.enabled ? 'Not downloaded yet.' : 'Off: new barcodes are looked up online.';
    }
    return '<h3 class="plan-h">Offline barcode list</h3>' +
      '<label class="offline-toggle"><span class="offline-toggle-text"><span class="offline-toggle-title">Keep a list of UK products on the Pi</span>' +
      '<span class="offline-toggle-hint">So scanning works with the internet down. About 200,000 products from Open Food Facts, 25 MB on the Pi, and a 1.5 GB download each month.</span></span>' +
      '<span class="switch"><input type="checkbox" data-offline="1"' + (o.enabled ? ' checked' : '') + '></span></label>' +
      '<p class="small' + (o.error && !o.building ? ' err' : ' muted') + '">' + esc(state) + (o.error && !o.building ? ' Last try: ' + esc(o.error) + '.' : '') + '</p>' +
      (o.enabled && !o.building ? '<button type="button" class="btn small" data-act="offline-update">Update now</button>' : '') +
      '<p class="small muted">Product data © Open Food Facts contributors (Open Database Licence).</p>';
  }
  function redrawScanCard() { var el = $("#scanAiCard"); if (el) el.outerHTML = scanHqCard(); }
  document.addEventListener('change', function (e) {
    if (!e.target.dataset || !e.target.dataset.offline) return;
    api('PUT', 'api/scan/offline', { enabled: e.target.checked }).then(function (r) {
      OFFLINE_ST = r; redrawScanCard();
      toast(r.enabled ? (r.building ? 'Downloading the UK list: it takes a while' : 'Offline list on') : 'Offline list off');
    }, function (err) { toast(err.message, { error: true }); });
  });

  function saveScanAi(body) {
    return api('PUT', 'api/scan/ai', body).then(function (r) { SCAN_AI = r; var el = $('#scanAiCard'); if (el) el.outerHTML = scanHqCard(); toast('Saved'); },
      function (e) { toast(e.message, { error: true }); });
  }
  document.addEventListener('change', function (e) {
    var t = e.target, k = t.dataset && t.dataset.scanai;
    if (!k) return;
    var v = t.value.trim();
    if (k.indexOf('key_') === 0 && !v) return;   // an empty box never clears a saved key
    var b = {};
    b[k] = k === 'limit_usd' ? (parseFloat(v) || 0) : v;
    if (k === 'provider') b.model = '';         // each provider has its own default model
    saveScanAi(b);
  });


  function sheetText(s) {
    return sheetHead(s.title, 'Select all and copy') +
      '<textarea readonly rows="12" style="font-family:ui-monospace,monospace;font-size:14px">' + esc(s.text) + '</textarea>';
  }

  function sheetShopText(s) {
    var x = S.shopping.filter(function (r) { return r.id === s.id; })[0];
    if (!x) return null;
    return sheetHead('Change it', 'Also get on the supply run', '📝') +
      '<form id="shopEditForm" data-id="' + x.id + '" novalidate autocomplete="off">' +
      '<label class="field"><span>What to get</span><input type="text" name="text" value="' + esc(x.text) + '" maxlength="200" data-autofocus></label>' +
      '<div class="sheet-actions"><button class="btn primary block" type="submit">Save</button></div></form>';
  }

  // The Pi's own daily copies, newest first. A damaged one is listed so you know it's there, but can't be picked.
  function sheetBackups(s) {
    var d = s.data, body;
    if (!d) body = '<p class="small muted">Looking for them…</p>';
    else if (d.error) body = '<p class="err">' + esc(d.error) + '</p>';
    else if (!d.backups.length) body = '<p class="small muted">There aren\'t any yet. The Pi makes one each day.</p>';
    else {
      body = '<p class="small muted">The Pi keeps a copy from each of the last ' + esc(d.keep) + ' days, and one from just before each restore. ' +
        'Restoring one replaces everything in the stores, but a copy of what\'s there now is kept first.</p><div class="list">' +
        d.backups.map(function (b) {
          var when = new Date(String(b.at).replace(' ', 'T'));
          var label = isNaN(when) ? b.at : when.toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
          var what = b.items === null ? 'Damaged: can\'t be restored' : srN(b.items, 'item', 'items');
          return '<div class="li"><button class="li-main" data-act="backup-use" data-name="' + esc(b.name) + '" data-when="' + esc(label) + '"' +
            (b.items === null ? ' disabled' : '') + ' aria-label="' + esc('Restore the copy from ' + label + ', ' + what) + '">' +
            '<span class="li-title">' + esc(label) + '</span><span class="li-sub">' + esc(what) +
            (b.kind === 'pre-restore' ? ' · saved before a restore' : '') + '</span></button></div>';
        }).join('') + '</div>';
    }
    return sheetHead('Automatic copies', 'Saved on the Pi each day', '🗄️') + body;
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
  // A "working on it" message, put away when the work's done (unless another message has taken its place).
  function untoast(msg) {
    var t = $('#toast');
    if (t && !t.hidden && t.textContent === msg) { clearTimeout(toastTimer); t.hidden = true; }
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
      case 'stock-like':
        return openSheet({ type: 'stock', id: id, exp: a.dataset.likeexp || '', loc: a.dataset.loc || '' });
      case 'scan':
        return liveOk() ? openSheet({ type: 'livescan' }) : scanBarcode(a);
      case 'scan-photo':
        stopLive();
        return scanBarcode(a);
      case 'scan-type':
        stopLive();
        return openSheet({ type: 'scancode' });
      case 'scan-pick':
        stopLive();
        return openSheet({ type: 'scanpick' });
      case 'scan-picked':
        return openSheet({ type: 'scanhit', id: id });
      case 'scan-torch':
        return toggleTorch(a);
      case 'scan-code':
        return lookupBarcode((($('#scanCode') || {}).value || '').replace(/\s+/g, ''), a);
      case 'scan-new': {
        var top = stack[stack.length - 1];
        return openSheet({ type: 'edit', id: null, code: top.code, pre: top.product || {}, cat: (top.product || {}).category || 'food' });
      }
      case 'scan-link': {
        var sc = stack[stack.length - 1];
        if (!sc.code) {   // read from the label: nothing to remember, straight to adding stock
          closeSheet();
          return openSheet({ type: 'stock', id: id, exp: (sc.product || {}).expiry || '' });
        }
        return run(function () {
          return api('POST', 'api/scan/link', { code: sc.code, item_id: id, product: (sc.product || {}).name || '' }).then(function () {
            closeSheet();
            toast('Barcode added to ' + (byId(id) || {}).name + '. Next time it goes straight there.');
            return openSheet({ type: 'stock', id: id });
          });
        }, a);
      }
      case 'scan-label': {
        stopLive();
        var lcode = a.dataset.code || '';
        return takePhoto().then(function (file) {
          if (!file) return;
          return shrinkPhoto(file, 1600).then(function (img) { return readLabel(img, a, lcode); });
        });
      }
      case 'ai-fill':
        return openSheet({ type: 'aifill' });
      case 'ai-fill-save': {
        var fs = stack[stack.length - 1];
        var keep = (fs.got || []).filter(function (x) { var c = $('input[data-fill="' + x.id + '"]'); return c && c.checked; })
          .map(function (x) { return Object.assign({ id: x.id }, x.fields); });
        if (!keep.length) return closeSheet();
        return run(function () {
          return api('POST', 'api/ai/fill/apply', { items: keep }).then(function (r) {
            closeSheet(); toast('Filled in ' + srN(r.saved, 'item', 'items') + '. Marked "AI estimate" until you change them.'); return refresh();
          });
        }, a);
      }
      case 'scan-nutrition':
        return readNutrition(a);
      case 'scan-label-more': {
        var lm = stack[stack.length - 1];
        return takePhoto().then(function (file) {
          if (!file) return;
          return shrinkPhoto(file, 1600).then(function (img) { return readLabel(img, a, lm.code || '', Object.assign({}, lm.product || {})); });
        });
      }
      case 'stock-review':
        return run(function () {
          toast('Reviewing your stores…');
          return api('POST', 'api/ai/review', {}).then(function (r) { S.stock_review = r.review; SCAN_AI = null; render(); });
        }, a);
      case 'review-add': {
        var rv = (S.stock_review || {}).suggestions || [], one = rv[+a.dataset.n];
        if (!one || onSupplyRun(one)) return;
        return run(function () {
          return api('POST', 'api/shopping', { text: one.add }).then(function () { one.added = true; a.textContent = '✓ On the list'; toast(one.add + ' added to the supply run'); });
        }, a).then(function () { if (one.added) a.disabled = true; });   // run() turns the button back on: once is enough
      }
      case 'scan-label-same':
        return readLabel(stack[stack.length - 1].img, a);
      case 'scan-date':
        return scanDate(a);
      case 'scan-usebatch':
        return scanUseBatch(a);
      case 'dupe-stock':
        closeSheet();
        return openSheet({ type: 'stock', id: id });
      case 'offline-update':
        return run(function () {
          return api('POST', 'api/scan/offline/update').then(function (r) { OFFLINE_ST = r; redrawScanCard(); toast('Updating the UK list: it takes a while'); });
        }, a);
      case 'scanai-forget': {
        var fb = {};
        fb['key_' + a.dataset.prov] = null;
        return saveScanAi(fb);
      }
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
          return api('POST', path, snap).then(function (res) {
            return refresh().then(function () {
              var sk = (res && res.skipped) || [];
              toast(sk.length ? 'Undone, except ' + nameList(sk, 3) + ': changed since' : 'Undone', sk.length ? { ms: 5000 } : {});
            });
          });
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
      case 'brief-now':
        a.disabled = true;
        return api('POST', 'api/briefing/now', {}).then(function (r) { S.briefing = r; redrawBrief(); toast('Writing a briefing: it takes a minute or two'); setTimeout(refresh, 8000); },
          function (err) { a.disabled = false; toast(err.message, { error: true }); });
      case 'warn-set':
        return openSheet({ type: 'warnset' });
      case 'trend-metric':
        HIST.metric = a.dataset.val;
        try { localStorage.setItem('da-trend-metric', HIST.metric); } catch (e) { /* fine */ }
        var tb = $('#trends'); if (tb) tb.outerHTML = trendsCard();
        return;
      case 'trend-days':
        HIST.days = +a.dataset.val;
        try { localStorage.setItem('da-trend-days', String(HIST.days)); } catch (e) { /* fine */ }
        loadHistory(true);
        return;
      case 'sort':
        F.sort = a.dataset.sort;
        try { localStorage.setItem('da-sort', F.sort); } catch (e) { /* fine */ }
        if ($('#fSort')) $('#fSort').value = F.sort;
        return renderStoreList();
      case 'live-open':
        return openSheet({ type: 'live', key: a.dataset.key || '' });
      case 'warn-check':
        return checkWarnings(a);
      case 'help':
        return openSheet({ type: 'help' });
      case 'credits': {
        var cr = { type: 'credits', data: null };
        openSheet(cr);
        return api('GET', 'api/credits').then(function (d) { cr.data = d.credits; }, function (e) {
          cr.data = { failed: e.message };
        }).then(function () { if (stack[stack.length - 1] === cr) renderSheet(); });
      }
      case 'credits-check': {
        var cs = stack[stack.length - 1];
        if (!cs || cs.type !== 'credits' || !cs.data) return;
        var before = cs.data.count || 0;
        a.textContent = 'Asking GitHub…';
        return run(function () {
          return api('POST', 'api/credits/check').then(function (res) {
            cs.data = res.credits;
            if (stack[stack.length - 1] === cs) renderSheet();
            var more = res.credits.count - before;
            if (!res.ok) toast('Not everything could be checked with GitHub. There\'s a note at the bottom.', { error: true });
            else toast(more > 0 ? more + ' new name' + (more === 1 ? '' : 's') + ' from GitHub' : 'Up to date: no new names');
          });
        }, a);
      }
      case 'place-new':
        return openSheet({ type: 'place', id: null });
      case 'place-edit':
        return openSheet({ type: 'place', id: id });
      case 'place-del': {
        var prevPlaces = ownList(), gone = PL().own.filter(function (o) { return o.id === id; })[0];
        var keepPlaces = prevPlaces.filter(function (o, i) { return PL().own[i].id !== id; });
        return run(function () {
          return api('PUT', 'api/places', { places: keepPlaces }).then(function () {
            closeSheet();
            return refresh().then(function () {
              toast('Deleted ' + (gone ? gone.name : 'the place'), { undo: { places: prevPlaces }, undoPath: 'api/places/restore' });
            });
          });
        }, a);
      }
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
        try { localStorage.setItem('da-dash-note', 'layout6'); } catch (e) { /* fine */ }
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
      case 'shop-edit':
        return openSheet({ type: 'shoptext', id: id });
      case 'shop-got': {
        // A new item with the extra's words as its name; saving it takes the extra off the list.
        var x = S.shopping.filter(function (r) { return r.id === id; })[0];
        if (!x) return;
        return openSheet({ type: 'edit', id: null, cat: 'other', pre: { name: x.text }, shop: x.id });
      }
      case 'backups': {
        var bs = { type: 'backups', data: null };
        openSheet(bs);
        return api('GET', 'api/backups').then(function (d) { bs.data = d; }, function (e) {
          bs.data = { error: e.message, backups: [] };
        }).then(function () { if (stack[stack.length - 1] === bs) renderSheet(); });
      }
      case 'backup-use': {
        var label = a.dataset.when, name = a.dataset.name;
        if (!confirm('Restore the copy from ' + label + '?\n\nThis REPLACES everything currently in the stores. The Pi keeps a copy of the current data first, just in case.')) return;
        // The same as restoring a file: an empty copy is only restored once you've said so.
        return run(function () {
          return api('POST', 'api/backups/restore', { name: name }).catch(function (err) {
            if (err.code !== 'empty_backup') throw err;
            if (!confirm(err.message + '\n\nRestore it anyway?')) return null;
            return api('POST', 'api/backups/restore', { name: name, confirm_empty: true });
          }).then(function (res) {
            if (!res) return;
            closeSheet();
            return refresh().then(function () { toast('Restored ' + srN(res.items, 'item', 'items') + ' from ' + label); });
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
        per_day: num(d.per_day), price: num(d.price),
        pack_size: num(d.pack_size), pack_unit: num(d.pack_size) ? (d.pack_unit || 'g') : '', open_days: num(d.open_days),
        // Cupboard, fridge or freezer is only asked about food, drinks and pet food (the choice is hidden for the rest).
        storage: storedCat(d.category) ? (d.storage || '') : ''
      };
      var id = f.dataset.id, shop = f.dataset.shop;
      if (!id) { body.qty = num(d.qty); body.expiry = d.expiry || null; body.location = d.location || ''; }
      if (!id && f.dataset.barcode) { body.barcode = f.dataset.barcode; body.product = f.dataset.product || ''; }
      if (!id && f.dataset.guessed) body.ai_guessed = f.dataset.guessed;
      return run(function () {
        return api(id ? 'PUT' : 'POST', id ? 'api/items/' + id : 'api/items', body).then(function () {
          // Bought from the "Also get" list: it's in the stores now, so it comes off the list.
          return shop ? api('DELETE', 'api/shopping/' + shop).catch(function () { /* already gone */ }) : null;
        }).then(function () {
          doneSheet();
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
          doneSheet();
          return refresh().then(function () { toast('Added ' + qu(qty, it ? it.unit : '') + (it ? ' · ' + it.name : '')); });
        });
      }, btn);
    }
    if (f.id === 'useForm') {
      var uq = num(d.qty), pack = +f.dataset.pack || 0, uit = byId(+f.dataset.id);
      if (pack && d.mode === 'amount') {
        if (!(num(d.amount) > 0)) { toast('How much did you use?', { error: true }); return; }
        uq = Math.round(num(d.amount) / pack * 1000) / 1000;
      } else if (pack && d.mode === 'left') {
        var left = num(d.left);
        if (d.left === '' || left < 0) { toast('How much is left in it?', { error: true }); return; }
        // The open one is the batch picked (or the first): its part-used amount, or a whole one if none is open.
        var bsel = uit && uit.batches.filter(function (b) { return b.qty > 0 && (!d.batch_id || b.id === +d.batch_id); })[0];
        var frac = bsel ? bsel.qty - Math.floor(bsel.qty + 1e-6) : 0, open = frac > 1e-6 ? frac : 1;
        uq = Math.round((open - left / pack) * 1000) / 1000;
        if (!(uq > 0)) { toast('That\'s as much as was in it, so nothing\'s been used', { error: true }); return; }
      }
      if (uq <= 0) { toast('How many are you using?', { error: true }); return; }
      var ub = { qty: uq };
      if (d.batch_id) ub.batch_id = +d.batch_id;
      return run(function () {
        return api('POST', 'api/items/' + f.dataset.id + '/use', ub).then(function (res) {
          var it = byId(+f.dataset.id);
          doneSheet();
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
    if (f.id === 'placeForm') {
      if (!d.name) { toast('Give the place a name', { error: true }); f.elements.name.focus(); return; }
      if (!d.where) { toast('Where is it? Paste a map link or the coordinates', { error: true }); f.elements.where.focus(); return; }
      var pid = f.dataset.id ? +f.dataset.id : null;
      var entry = { name: d.name, where: d.where, kind: d.kind || 'other', notes: d.notes || '',
        hazards: $$('input[name="hz"]:checked', f).map(function (i) { return i.value; }) };
      var list = ownList();
      if (pid) list = list.map(function (o, i) { return PL().own[i].id === pid ? entry : o; });
      else list.push(entry);
      return run(function () {
        return api('PUT', 'api/places', { places: list }).then(function () {
          closeSheet();
          return refresh().then(function () { toast(pid ? 'Saved' : d.name + ' added to your places'); });
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
        flood_km: num(d.flood_km), gdacs_km: num(d.gdacs_km), fire_km: num(d.fire_km), near_km: num(d.near_km), sources: {},
        ea_area: d.ea_area || '', water_co: d.water_co || '' };
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
    if (f.id === 'shopEditForm') {
      if (!d.text) { toast('Type what to get, or remove it from the list instead', { error: true }); f.elements.text.focus(); return; }
      return run(function () {
        return api('PUT', 'api/shopping/' + f.dataset.id, { text: d.text }).then(function () {
          closeSheet();
          return refresh().then(function () { toast('Saved'); });
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
    var expDate = t.closest('[data-expdate]');
    if (expDate) { expDate.closest('.field').querySelector('input[type="date"]').value = expDate.dataset.expdate; return; }
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
  // A place's map link or coordinates: check them as soon as they're pasted in.
  document.addEventListener('change', function (e) {
    var t = e.target;
    if (t.name === 'where' && t.form && t.form.id === 'placeForm') checkWhere(t);
  });

  document.addEventListener('input', function (e) {
    var t = e.target;
    if (t.id === 'q') { F.q = t.value; renderStoreList(); return; }
    if (t.id === 'pickQ') { var pl = $('#pickList'); if (pl) pl.innerHTML = pickRows(t.value); return; }
    if (t.dataset.calc) {
      var f = t.form;
      var per = num($('[data-calc="per100"]', f).value), g = num($('[data-calc="grams"]', f).value);
      if (per > 0 && g > 0) f.elements.kcal_per_unit.value = Math.round(per * g / 100);
    }
    if (t.form && t.form.id === 'itemForm' && (t.dataset.calc || t.name === 'kcal_per_unit' || t.name === 'unit')) {
      var kh = $('[data-kcalhint]', t.form), uw = $('[data-unitword]', t.form);
      if (uw) uw.textContent = t.form.elements.unit.value.trim() || 'one';
      if (kh) kh.innerHTML = kcalHint(num(t.form.elements.kcal_per_unit.value), t.form.elements.unit.value.trim());
    }
    if ((t.name === 'per_day' || t.name === 'target_qty') && t.form && t.form.id === 'itemForm') perDayHint(t.form);
    if (t.name === 'name' && t.form && t.form.id === 'itemForm' && !t.form.dataset.id) dupeHint(t.form);
    if (t.name === 'mode' && t.form && t.form.id === 'useForm') {
      var uf = t.form;
      $('.use-units', uf).hidden = t.value !== 'units';
      $('.use-amount', uf).hidden = t.value !== 'amount';
      $('.use-left', uf).hidden = t.value !== 'left';
      var focusEl = t.value === 'amount' ? uf.elements.amount : t.value === 'left' ? uf.elements.left : null;
      if (focusEl) focusEl.focus();
    }
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
    if (t.dataset.warncat) {
      var by = {};
      Object.keys(S.settings.warn_by_cat || {}).forEach(function (k) { by[k] = S.settings.warn_by_cat[k]; });
      if (+t.value) by[t.dataset.warncat] = +t.value; else delete by[t.dataset.warncat];
      queueSetting('warn_by_cat', by);
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
        if (!confirm('Restore ' + n + ' items from "' + file.name + '"?\n\nThis REPLACES everything currently in the stores. The Pi keeps a copy of the current data first, just in case.')) return;
        run(function () {
          return api('POST', 'api/restore', data).catch(function (err) {
            if (err.code !== 'empty_backup') throw err;
            if (!confirm(err.message + '\n\nRestore it anyway?')) return null;
            data.confirm_empty = true;
            return api('POST', 'api/restore', data);
          }).then(function (res) {
            if (!res) return;
            return refresh().then(function () { toast('Restored ' + n + ' items'); });
          });
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

  // Charts: point at one (or touch it) to see the day's values.
  document.addEventListener('pointermove', chartHover);
  document.addEventListener('pointerdown', chartHover);
  // Turning a tablet round, or resizing the window: the Stores switch between the table and the list.
  if (WIDE.addEventListener) WIDE.addEventListener('change', function () { if (S && view === 'stores') renderStoreList(); });

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
