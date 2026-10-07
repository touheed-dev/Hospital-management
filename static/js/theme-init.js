// Runs before first paint (loaded synchronously in <head>) so the saved theme never flashes.
(function () {
  var stored = null;
  try { stored = localStorage.getItem("medibook-theme"); } catch (err) { /* storage blocked */ }
  var dark = stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
})();
