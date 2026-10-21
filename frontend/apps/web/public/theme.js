// Apply the saved theme before first paint, so dark mode never flashes light.
// A file, not an inline script, so the Content-Security-Policy can forbid inline scripts.
try {
  var t = localStorage.getItem("ems.theme") || "system";
  var dark = t === "dark" || (t === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
} catch (e) {}
