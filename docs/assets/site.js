// The public-site adapter does not run in the local application or its exports.
if (location.origin === 'https://mfahsold.github.io' && location.pathname.startsWith('/lixity/')) {
  const analytics = document.createElement('script');
  analytics.src = new URL('analytics.js', document.currentScript.src).href;
  analytics.defer = true;
  document.head.appendChild(analytics);
}

// Share the chosen theme between the overview and reading guides.
const root = document.documentElement;
const themeButton = document.getElementById('themeToggle');
const themes = ['auto', 'light', 'dark'];
let theme = 'auto';
try { theme = localStorage.getItem('lixity-theme') || 'auto'; } catch { /* Use system preference. */ }
if (!themes.includes(theme)) theme = 'auto';

function applyTheme() {
  root.dataset.theme = theme;
  const labels = {
    en: ['Theme', 'system', 'light', 'dark'], de: ['Darstellung', 'System', 'Hell', 'Dunkel'],
    fr: ['Thème', 'système', 'clair', 'sombre'], es: ['Tema', 'sistema', 'claro', 'oscuro'],
    it: ['Tema', 'sistema', 'chiaro', 'scuro'], pt: ['Tema', 'sistema', 'claro', 'escuro'],
    nl: ['Thema', 'systeem', 'licht', 'donker'],
  };
  const names = labels[root.lang] || labels.en;
  if (themeButton) themeButton.textContent = `${names[0]}: ${names[themes.indexOf(theme) + 1]}`;
}
applyTheme();
if (themeButton) themeButton.hidden = false;
if (themeButton) themeButton.addEventListener('click', () => {
  theme = themes[(themes.indexOf(theme) + 1) % themes.length];
  applyTheme();
  try { localStorage.setItem('lixity-theme', theme); } catch { /* Keep the session choice. */ }
});

// Website language is a browsing preference, never an analysis setting.
const languageLinks = [...document.querySelectorAll('.language-picker a[hreflang]')];
if (languageLinks.length) {
  const available = new Map(languageLinks.map(link => [link.hreflang, link]));
  const preferenceKey = 'lixity-site-language';
  function rememberLanguage(language) {
    try { localStorage.setItem(preferenceKey, language); } catch { /* Navigation still works. */ }
  }
  document.querySelectorAll('.language-picker a[hreflang], .language-list a[hreflang]').forEach(link => {
    link.addEventListener('click', () => rememberLanguage(link.hreflang));
  });
  let preferred;
  try { preferred = localStorage.getItem(preferenceKey); } catch { /* Use browser preferences. */ }
  if (!available.has(preferred)) {
    preferred = (navigator.languages || [navigator.language]).map(language =>
      language.toLowerCase().split('-')[0]).find(language => available.has(language));
  }
  const suggestion = document.getElementById('language-suggestion');
  if (suggestion && preferred && preferred !== root.lang) {
    const target = available.get(preferred);
    const link = suggestion.querySelector('a');
    link.href = target.getAttribute('href');
    link.hreflang = preferred;
    link.lang = preferred;
    link.textContent = target.dataset.languageAction;
    link.addEventListener('click', () => rememberLanguage(preferred));
    suggestion.hidden = false;
    suggestion.querySelector('button').addEventListener('click', () => {
      rememberLanguage(root.lang);
      suggestion.hidden = true;
      document.querySelector('.language-picker summary').focus();
    });
  }
}
