// Apply the saved light/dark choice before first paint (avoids a flash).
try {
  var t = localStorage.getItem('da-theme');
  if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t;
} catch (e) { /* private mode: follow the system theme */ }
