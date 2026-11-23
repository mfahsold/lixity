// Website preferences are used only for the language of public pages.
(() => {
  const key = 'lixity-site-language';

  function preferred(supported) {
    let saved;
    try { saved = localStorage.getItem(key); } catch { /* Use browser preferences. */ }
    if (supported.includes(saved)) return saved;
    return (navigator.languages || [navigator.language]).map(language =>
      language.toLowerCase().split('-')[0]).find(language => supported.includes(language));
  }

  function remember(language) {
    try { localStorage.setItem(key, language); } catch { /* Navigation still works. */ }
  }

  window.LixitySiteLanguage = {preferred, remember};
})();
