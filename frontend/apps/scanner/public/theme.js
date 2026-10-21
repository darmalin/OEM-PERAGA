// Follow the system theme before first paint. A file, not an inline script, for the CSP.
try {
  var m = matchMedia("(prefers-color-scheme: dark)");
  var apply = function () {
    document.documentElement.classList.toggle("dark", m.matches);
  };
  apply();
  m.addEventListener("change", apply);
} catch (e) {}
