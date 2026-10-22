// Feedback follows committed state; it never owns navigation, focus or data.
(function() {
  "use strict";
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var animations = new Map(), layers = new Map(), viewRevision = 0;
  var passage = null, passageTimer = null, passageRevision = 0;
  function cancel(node) {
    var animation = animations.get(node);
    if (animation) { animation.cancel(); animations.delete(node); }
  }
  function reveal(node) {
    if (!node) return;
    var previous = animations.get(node);
    var opacity = previous ? Number(getComputedStyle(node).opacity) : .85;
    cancel(node);
    if (reduced.matches || !node.animate || !node.getClientRects().length) return;
    // Opacity preserves the rectangles used by passage/selection restoration.
    var animation = node.animate([{opacity: opacity}, {opacity: 1}], {
      duration: 180, easing: "cubic-bezier(.2,.7,.3,1)", id: "lixity-reveal"
    });
    animations.set(node, animation);
    animation.onfinish = function() { if (animations.get(node) === animation) animations.delete(node); };
  }
  function visible(root, selector) {
    var nodes = [], chapters = new Map();
    Array.prototype.some.call(root.querySelectorAll(selector), function(node) {
      var chapter = node.closest(".chapter");
      if (chapter) {
        // One chapter bound avoids measuring every paragraph in offscreen chapters.
        if (!chapters.has(chapter)) chapters.set(chapter, chapter.getBoundingClientRect());
        var bounds = chapters.get(chapter);
        if (bounds.bottom <= 0 || bounds.top >= innerHeight) return false;
      }
      var rect = node.getBoundingClientRect();
      if (rect.height > 0 && rect.height <= innerHeight * 2 && rect.bottom > 0 && rect.top < innerHeight) nodes.push(node);
      return nodes.length === 8;
    });
    return nodes;
  }
  function markPassage(node) {
    ++passageRevision;
    clearTimeout(passageTimer);
    if (passage) passage.classList.remove("reader-return-target");
    passage = node;
    if (!node || !node.isConnected) return;
    // A static gutter remains useful when motion is disabled.
    node.classList.add("reader-return-target");
    passageTimer = setTimeout(function() { node.classList.remove("reader-return-target"); passage = null; }, 1400);
  }
  function view(pane) {
    var revision = ++viewRevision;
    var initialPassageRevision = passageRevision;
    animations.forEach(function(_, node) { cancel(node); });
    // Relation routes and Reader.restore finish their own scroll in this frame.
    requestAnimationFrame(function() { requestAnimationFrame(function() {
      if (revision !== viewRevision || !pane || !pane.getClientRects().length) return;
      visible(pane, ".chapter-head, .reader-structural, .ptext, .panel > h2, .research-navigation, .research-tab-pane > .ctl-note").forEach(reveal);
      // An explicit destination owns its settled cue, including while scrolling.
      if (passageRevision === initialPassageRevision && pane.id === "view-pane-analysis" && window.LixityReader) {
        var anchor = window.LixityReader.capture();
        if (anchor) markPassage(anchor.panel);
      }
    }); });
  }
  function analysis(chapters) {
    if (reduced.matches) return;
    visible(chapters, ".ptext, .strip, .chapter-head .meta").forEach(function(node) {
      if (!node.matches(".ptext")) { reveal(node); return; }
      clearTimeout(layers.get(node));
      node.classList.add("reader-layer-enter");
      layers.set(node, setTimeout(function() { node.classList.remove("reader-layer-enter"); layers.delete(node); }, 220));
    });
  }
  reduced.addEventListener("change", function() {
    if (!reduced.matches) return;
    animations.forEach(function(_, node) { cancel(node); });
    layers.forEach(function(timer, node) { clearTimeout(timer); node.classList.remove("reader-layer-enter"); });
    layers.clear();
  });
  window.LixityMotion = {reveal: reveal, view: view, analysis: analysis, passage: markPassage};
})();
