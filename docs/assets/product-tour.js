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
  const portrait = matchMedia('(orientation: portrait)');
  const landscapePoster = video.getAttribute('poster');
  const applyPoster = () => {
    const target = portrait.matches && video.dataset.portraitPoster
      ? video.dataset.portraitPoster : landscapePoster;
    if (video.getAttribute('poster') !== target) video.setAttribute('poster', target);
  };
  applyPoster();
  if (portrait.addEventListener) portrait.addEventListener('change', applyPoster);
  video.addEventListener('loadedmetadata', () => {
    if (video.videoWidth && video.videoHeight) {
      video.style.setProperty('--tour-aspect', `${video.videoWidth} / ${video.videoHeight}`);
    }
  });
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  let reducedMotion = motion.matches;
  let attempted = false;
  let failed = false;
  let current = -1;
  let frame = 0;
  video.muted = true;
  toggle.hidden = false;
  function update() {
    const label = video.paused ? toggle.dataset.play : toggle.dataset.pause;
    if (toggle.textContent !== label) toggle.textContent = label;
    const index = cues.findLastIndex(cue => video.currentTime >= Number(cue.dataset.start));
    if (index !== current && index >= 0) {
      current = index;
      // Read the whole sentence while the recording demonstrates one action.
      line.textContent = cues[index].textContent;
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
  const exhaustedSources = () => sources
    .filter(source => !source.media || matchMedia(source.media).matches)
    .every(source => failedSources.has(source));
  for (const source of sources) source.addEventListener('error', () => {
    failedSources.add(source);
    if (exhaustedSources()) reportFailure();
  });
  if (exhaustedSources()) reportFailure();
  document.addEventListener('visibilitychange', () => { if (document.hidden) video.pause(); });
  motion.addEventListener('change', event => {
    reducedMotion = event.matches;
    if (reducedMotion) video.pause();
    update();
  });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) video.pause();
        else if (entry.intersectionRatio >= .5 && !attempted && !reducedMotion &&
                 !navigator.connection?.saveData && !document.hidden) void play();
      }
    }, {threshold: [0, .5]});
    observer.observe(video);
  }
  update();
})();
