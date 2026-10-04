// Share the chosen theme between the overview and reading guides.
const root = document.documentElement;
const themeButton = document.getElementById('themeToggle');
const themes = ['auto', 'light', 'dark'];
let theme = 'auto';
try { theme = localStorage.getItem('lixity-theme') || 'auto'; } catch { /* Use system preference. */ }
if (!themes.includes(theme)) theme = 'auto';

function applyTheme() {
  root.dataset.theme = theme;
  if (themeButton) themeButton.textContent = `Theme: ${theme === 'auto' ? 'system' : theme}`;
}
applyTheme();
if (themeButton) themeButton.addEventListener('click', () => {
  theme = themes[(themes.indexOf(theme) + 1) % themes.length];
  applyTheme();
  try { localStorage.setItem('lixity-theme', theme); } catch { /* Keep the session choice. */ }
});
