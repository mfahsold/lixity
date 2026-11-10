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
  video.muted = true;
  toggle.hidden = false;
  function update() {
    toggle.textContent = video.paused ? toggle.dataset.play : toggle.dataset.pause;
    const index = cues.findLastIndex(cue => video.currentTime >= Number(cue.dataset.start));
    if (index !== current && index >= 0) {
      current = index;
      line.textContent = cues[index].textContent;
    }
    caption.hidden = failed || video.readyState < 2;
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
  video.addEventListener('play', () => { attempted = true; update(); });
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
  motion.addEventListener('change', () => { if (motion.matches) video.pause(); });
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
