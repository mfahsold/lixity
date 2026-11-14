// One quiet recording, localized by the visible page transcript.
(() => {
  const figure = document.querySelector('.product-tour');
  if (!figure) return;
  const video = figure.querySelector('video');
  const toggle = figure.querySelector('.tour-toggle');
  const caption = figure.querySelector('.tour-caption');
  const line = caption.querySelector('span');
  const error = figure.querySelector('.tour-error');
  const cues = [...figure.querySelectorAll('[data-start]')];
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  let attempted = false;
  let failed = false;
  let current = -1;
  let letters = [];
  let visibleLetters = -1;
  let frame = 0;
  video.muted = true;
  toggle.hidden = false;
  function update() {
    const label = video.paused ? toggle.dataset.play : toggle.dataset.pause;
    if (toggle.textContent !== label) toggle.textContent = label;
    const index = cues.findLastIndex(cue => video.currentTime >= Number(cue.dataset.start));
    if (index !== current && index >= 0) {
      current = index;
      letters = Array.from(cues[index].textContent, character => {
        const letter = document.createElement('span');
        letter.dataset.letter = '';
        letter.textContent = character;
        return letter;
      });
      line.replaceChildren(...letters);
      visibleLetters = -1;
    }
    const elapsed = index < 0 ? 0 : video.currentTime - Number(cues[index].dataset.start);
    const count = motion.matches || video.paused ? letters.length :
      Math.min(letters.length, Math.max(0, Math.ceil((elapsed - .08) / .55 * letters.length)));
    if (count !== visibleLetters) {
      letters.forEach((letter, position) => { letter.style.visibility = position < count ? 'visible' : 'hidden'; });
      visibleLetters = count;
    }
    caption.hidden = failed || video.readyState < 2;
  }
  function tick() {
    update();
    frame = video.paused || video.ended ? 0 : requestAnimationFrame(tick);
  }
  async function play() {
    attempted = true;
    try { await video.play(); } catch {
      // Autoplay rejection is normal. Keep the poster and explicit controls.
      update();
    }
  }
  toggle.addEventListener('click', () => {
    attempted = true;
    if (video.paused) void play();
    else video.pause();
  });
  // Native controls count as an intentional choice, too: never auto-resume.
  video.addEventListener('play', () => { attempted = true; if (!frame) tick(); });
  for (const event of ['pause', 'ended', 'timeupdate', 'loadeddata', 'seeked']) video.addEventListener(event, update);
  const reportFailure = () => {
    failed = true;
    error.hidden = false;
    toggle.hidden = true;
    caption.hidden = true;
  };
  video.addEventListener('error', reportFailure);
  const sources = [...video.querySelectorAll('source')].filter(source => video.canPlayType(source.type));
  const failedSources = new Set();
  for (const source of sources) source.addEventListener('error', () => {
    failedSources.add(source);
    if (failedSources.size === sources.length) reportFailure();
  });
  if (!sources.length) reportFailure();
  document.addEventListener('visibilitychange', () => { if (document.hidden) video.pause(); });
  motion.addEventListener('change', () => { if (motion.matches) video.pause(); update(); });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) video.pause();
        else if (entry.intersectionRatio >= .5 && !attempted && !motion.matches &&
                 !navigator.connection?.saveData && !document.hidden) void play();
      }
    }, {threshold: [0, .5]});
    observer.observe(video);
  }
  update();
})();
