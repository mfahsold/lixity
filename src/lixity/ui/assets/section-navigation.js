// Presentation for real document links; activation remains with scrollAndFlash.
(function() {
  "use strict";
  var instances = new Set(), lifecycle = null, listening = false;
  var motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  function refreshAll() { instances.forEach(function(instance) { instance.refresh(); }); }
  function listen() {
    if (listening) return;
    listening = true;
    document.addEventListener("scroll", refreshAll, {capture: true, passive: true});
    window.addEventListener("resize", refreshAll);
    document.addEventListener("toggle", refreshAll, true);
    document.addEventListener("lixity:viewchange", refreshAll);
    motion.addEventListener("change", refreshAll);
    lifecycle = new MutationObserver(refreshAll);
    lifecycle.observe(document.body, {subtree: true, childList: true, attributes: true,
      attributeFilter: ["hidden", "open", "class"]});
  }
  function unlisten() {
    if (instances.size || !listening) return;
    listening = false; lifecycle.disconnect(); lifecycle = null;
    document.removeEventListener("scroll", refreshAll, true);
    window.removeEventListener("resize", refreshAll);
    document.removeEventListener("toggle", refreshAll, true);
    document.removeEventListener("lixity:viewchange", refreshAll);
    motion.removeEventListener("change", refreshAll);
  }
  function scrollRoot(host) {
    for (var node = host; node && node !== document.body; node = node.parentElement) {
      if (/(auto|scroll)/.test(getComputedStyle(node).overflowY) && node.scrollHeight > node.clientHeight) return node;
    }
    return document.scrollingElement;
  }
  function svgNode(name, attributes) {
    var node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.keys(attributes).forEach(function(key) { node.setAttribute(key, attributes[key]); });
    return node;
  }
  function mount(nav, options) {
    if (!nav) return null;
    if (nav._sectionNavigation) { nav._sectionNavigation.refresh(); return nav._sectionNavigation; }
    options = options || {};
    var host = options.host || nav.parentElement, horizontal = Boolean(options.horizontal);
    var entries = Array.from(nav.querySelectorAll("[data-section-link]")).map(function(link) {
      return {link: link, target: document.getElementById(link.dataset.sectionLink)};
    }).filter(function(entry) { return entry.target && host.contains(entry.target); });
    if (!entries.length) return null;
    var svg = svgNode("svg", {"aria-hidden": "true", focusable: "false", "data-section-track": ""});
    var track = svgNode("path", {"class": "section-track"}), progress = svgNode("path", {"class": "section-progress", pathLength: "1"});
    var dot = svgNode("circle", {r: "3", "data-section-indicator": "", "class": "section-dot"});
    svg.append(track, progress, dot); nav.prepend(svg);
    var frame = 0, disposed = false, current = null, geometry = "", observing = false, observedRoot = null;
    var resize = typeof ResizeObserver === "function" ? new ResizeObserver(schedule) : null;
    function schedule() { if (!disposed && !frame) frame = requestAnimationFrame(update); }
    function visible(node) { return node.isConnected && node.getClientRects().length > 0; }
    function paint(entry) {
      if (!visible(nav)) {
        dot.style.transition = progress.style.transition = "none";
        svg.style.display = "none"; geometry = ""; return;
      }
      svg.style.display = "";
      var box = nav.getBoundingClientRect();
      var points = entries.map(function(item) {
        var rect = item.link.getBoundingClientRect();
        return horizontal ? [rect.left - box.left + nav.scrollLeft + rect.width / 2, rect.bottom - box.top + nav.scrollTop - 2] :
          [rect.left - box.left + nav.scrollLeft - 9, rect.top - box.top + nav.scrollTop + rect.height / 2];
      });
      var path = points.map(function(point, index) { return (index ? "L" : "M") + point.join(","); }).join(" ");
      var changedGeometry = path !== geometry; geometry = path;
      // Repeated scroll frames must not cancel an in-flight indicator transition.
      var animate = !changedGeometry && !motion.matches;
      dot.style.transition = animate ? "transform 200ms ease-out" : "none";
      progress.style.transition = animate ? "stroke-dasharray 200ms ease-out" : "none";
      // CSS owns the viewport size; copying scrollWidth here would let the
      // decoration's previous width prevent its parent from shrinking.
      track.setAttribute("d", path); progress.setAttribute("d", path);
      var lengths = [0];
      for (var i = 1; i < points.length; i++) lengths.push(lengths[i - 1] + Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]));
      var index = entries.indexOf(entry), point = points[index];
      dot.style.display = progress.style.display = point ? "" : "none";
      if (point) {
        dot.style.transform = "translate(" + point[0] + "px," + point[1] + "px)";
        progress.style.strokeDasharray = (lengths[index] / (lengths[lengths.length - 1] || 1)) + " 1";
      }
    }
    function update() {
      frame = 0;
      if (!nav.isConnected || !host.isConnected) { dispose(); return; }
      var shown = visible(host) && (visible(nav) || options.location && visible(options.location));
      var root = horizontal ? document.scrollingElement : scrollRoot(host);
      if (resize && (shown !== observing || shown && root !== observedRoot)) {
        resize.disconnect(); observing = shown; observedRoot = root;
        if (shown) {
          resize.observe(host); resize.observe(nav);
          if (root !== document.scrollingElement) resize.observe(root);
          entries.forEach(function(entry) { resize.observe(entry.target); });
        }
      }
      var available = entries.filter(function(entry) { return visible(entry.target); });
      var selected = null;
      if (available.length && visible(host)) {
        var windowRoot = root === document.scrollingElement;
        var bounds = windowRoot ? {top: 0, bottom: innerHeight, height: innerHeight} : root.getBoundingClientRect();
        var top = Math.max(0, bounds.top), bottom = Math.min(innerHeight, bounds.bottom);
        // A stacked companion can be partly above the viewport. Keep only its
        // compact orientation link inside the visible portion of that scrollport.
        if (options.location) {
          var inset = Math.max(0, -bounds.top) + "px";
          if (options.location.style.top !== inset) options.location.style.top = inset;
        }
        var marker = top + (bottom - top) * .3;
        selected = available[0];
        available.forEach(function(entry) {
          // The shared jump helper clears sticky controls with scroll-margin.
          // On short screens that arrival can be below the usual 30% marker.
          var clearance = parseFloat(getComputedStyle(entry.target).scrollMarginTop) || 0;
          var arrival = Math.min(bottom - 1, Math.max(marker, top + clearance));
          if (entry.target.getBoundingClientRect().top <= arrival + 1) selected = entry;
        });
        var last = available[available.length - 1];
        if (Math.ceil(root.scrollTop + root.clientHeight) >= root.scrollHeight - 1 && last.target.getBoundingClientRect().top < bottom) selected = last;
      }
      entries.forEach(function(entry) {
        if (entry === selected) entry.link.setAttribute("aria-current", "true");
        else entry.link.removeAttribute("aria-current");
      });
      if (current !== selected) {
        current = selected;
        if (options.onCurrent) options.onCurrent(selected && selected.link);
      }
      paint(selected);
    }
    function keyboard(event) {
      if (!horizontal || !["ArrowRight", "ArrowLeft"].includes(event.key)) return;
      var index = entries.findIndex(function(entry) { return entry.link === document.activeElement; });
      var next = index + (event.key === "ArrowRight" ? 1 : -1);
      if (index < 0 || next < 0 || next >= entries.length) return;
      event.preventDefault(); entries[next].link.click(); entries[next].link.focus({preventScroll: true});
      var bounds = nav.getBoundingClientRect(), focused = entries[next].link.getBoundingClientRect();
      if (focused.left < bounds.left) nav.scrollLeft += focused.left - bounds.left;
      else if (focused.right > bounds.right) nav.scrollLeft += focused.right - bounds.right;
    }
    function dispose() {
      if (disposed) return;
      disposed = true; cancelAnimationFrame(frame); if (resize) resize.disconnect();
      nav.removeEventListener("keydown", keyboard); nav.removeEventListener("click", schedule);
      if (options.onCurrent) options.onCurrent(null);
      svg.remove(); delete nav._sectionNavigation; instances.delete(instance); unlisten();
    }
    var instance = {refresh: schedule, dispose: dispose};
    nav._sectionNavigation = instance; nav.addEventListener("keydown", keyboard); nav.addEventListener("click", schedule);
    instances.add(instance); listen(); schedule(); return instance;
  }
  window.LixitySectionNavigation = {mount: mount};
})();
