// The exhibitor portal is light only (owner request 2026-11-09): drop any dark class early.
// A file, not an inline script: the portal's Content-Security-Policy allows no inline scripts.
try {
  document.documentElement.classList.remove("dark");
} catch (e) {}
