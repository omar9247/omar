/* Local-only display preference; dark remains the mission-console default. */
'use strict';
function applyTheme(theme) {
  const light = theme === 'light';
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
  const button = document.getElementById('theme-toggle');
  if (button) {
    button.textContent = light ? 'Use dark mode' : 'Use light mode';
    button.setAttribute('aria-pressed', String(light));
  }
}
try { applyTheme(localStorage.getItem('aura-theme')); } catch { applyTheme('dark'); }
document.addEventListener('DOMContentLoaded', () => {
  applyTheme(document.documentElement.dataset.theme);
  document.getElementById('theme-toggle').addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    applyTheme(theme);
    try { localStorage.setItem('aura-theme', theme); } catch { /* display still works without storage */ }
    document.dispatchEvent(new Event('themechange'));
  });
});
