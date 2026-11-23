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
if (languageLinks.length && window.LixitySiteLanguage) {
  const available = new Map(languageLinks.map(link => [link.hreflang, link]));
  const {preferred, remember} = window.LixitySiteLanguage;
  document.querySelectorAll('.language-picker a[hreflang], .language-list a[hreflang]').forEach(link => {
    link.addEventListener('click', () => remember(link.hreflang));
  });
  const language = preferred([...available.keys()]);
  const suggestion = document.getElementById('language-suggestion');
  if (suggestion && language && language !== root.lang) {
    const target = available.get(language);
    const link = suggestion.querySelector('a');
    link.href = target.getAttribute('href');
    link.hreflang = language;
    link.lang = language;
    link.textContent = target.dataset.languageAction;
    link.addEventListener('click', () => remember(language));
    suggestion.hidden = false;
    suggestion.querySelector('button').addEventListener('click', () => {
      remember(root.lang);
      suggestion.hidden = true;
      document.querySelector('.language-picker summary').focus();
    });
  }
}
