// Shared light/dark theme. Loaded in <head> so the theme is applied before first paint.
(function () {
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem('theme'); } catch (_) {}
  var prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
  root.dataset.theme = stored || (prefersLight ? 'light' : 'dark');

  window.cssVar = function (name) {
    return getComputedStyle(root).getPropertyValue(name).trim();
  };

  function syncButtons() {
    var isLight = root.dataset.theme === 'light';
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-label', isLight ? 'Switch to dark theme' : 'Switch to light theme');
      btn.setAttribute('aria-pressed', String(isLight));
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    syncButtons();
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
        try { localStorage.setItem('theme', root.dataset.theme); } catch (_) {}
        syncButtons();
        window.dispatchEvent(new CustomEvent('themechange'));
      });
    });
  });
})();
