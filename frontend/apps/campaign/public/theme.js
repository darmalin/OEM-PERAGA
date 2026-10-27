// Follow the device's light or dark setting before first paint. A file, not an inline
// script: the form's Content-Security-Policy allows no inline scripts of our own.
try {
  document.documentElement.classList.toggle("dark", matchMedia("(prefers-color-scheme: dark)").matches);
} catch (e) {}
