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

const desktopTestExpiry = document.getElementById('desktop-test-expiry');
if (desktopTestExpiry && Date.now() >= Date.parse(desktopTestExpiry.dateTime)) {
  document.getElementById('desktop-test-downloads').hidden = true;
  document.querySelectorAll('.desktop-test-archive').forEach(link => { link.hidden = true; });
  document.getElementById('desktop-test-expired').hidden = false;
}

const installerCheck = document.getElementById('installer-check');
if (installerCheck && window.crypto?.subtle) {
  const input = document.getElementById('installer-check-file');
  const status = document.getElementById('installer-check-status');
  const installers = JSON.parse(document.getElementById('installer-check-digests').textContent);
  const maximumBytes = 256 * 1024 * 1024;
  let selection = 0;
  installerCheck.hidden = false;
  input.addEventListener('change', async () => {
    const current = ++selection;
    const file = input.files[0];
    status.textContent = '';
    if (!file) return;
    if (file.size > maximumBytes) {
      status.textContent = 'For this file size, use the SHA-256 checksum list and verification instructions.';
      return;
    }
    const candidates = installers.filter(item => file.size === item.bytes);
    if (!candidates.length) {
      status.textContent = 'This file does not match the expected installer sizes. Extract the ZIP and select its installer.';
      return;
    }
    status.textContent = 'Checking the installer…';
    try {
      const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
      if (current !== selection) return;
      const hex = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
      const match = candidates.find(item => item.sha256 === hex);
      status.textContent = match
        ? `Checksum matches ${match.filename}. Continue with its setup steps.`
        : 'Checksum differs. Download the installer again from this page before opening it.';
    } catch {
      if (current === selection) status.textContent = 'Could not read the installer. Try again or use the SHA-256 instructions.';
    }
  });
}
