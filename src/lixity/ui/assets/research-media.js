// One local viewer for retained images and generated diagram SVGs.
(function () {
  "use strict";
  var shell, viewer;
  function open(items, index, trigger, cleanup) {
    if (!items.length || !window.PhotoSwipe || viewer) return false;
    if (!shell) {
      shell = document.createElement("dialog");
      shell.id = "modal-dossier-image-enlarge";
      shell.className = "research-media-dialog";
      shell.addEventListener("cancel", function(event) {
        event.preventDefault();
        if (viewer) viewer.close();
      });
      document.body.appendChild(shell);
    }
    shell.setAttribute("aria-label", trigger.getAttribute("aria-label") || trigger.textContent.trim() || uiLabel("image_enlarge"));
    shell.showModal();
    viewer = new PhotoSwipe({
      dataSource: items, index: index, appendToEl: shell,
      showHideAnimationType: "none", bgOpacity: 1,
      maxZoomLevel: 4, secondaryZoomLevel: function(levels) { return Math.max(1, levels.initial * 2); },
      closeTitle: uiLabel("modal_close"), zoomTitle: uiLabel("media_zoom"),
      arrowPrevTitle: uiLabel("media_previous"), arrowNextTitle: uiLabel("media_next"),
      errorMsg: uiLabel("image_unavailable"), returnFocus: false,
    });
    var instance = viewer;
    viewer.on("loadComplete", function(event) {
      var content = event.content, item = items[content.index], element = content.element;
      if (event.isError || !item || item.width || !element || !element.naturalWidth) return;
      // Inline lazy images may not have dimensions yet. Let PhotoSwipe load its
      // bounded neighbouring slides, then rebuild only that slide at exact size.
      item.width = element.naturalWidth; item.height = element.naturalHeight;
      queueMicrotask(function() {
        if (viewer === instance && !instance.isDestroying && shell.open) instance.refreshSlideContent(content.index);
      });
    });
    viewer.on("uiRegister", function() {
      viewer.ui.registerElement({
        name: "caption", order: 9, isButton: false, appendTo: "root",
        onInit: function(element, instance) {
          element.setAttribute("aria-live", "polite");
          instance.on("change", function() { element.textContent = instance.currSlide.data.caption || ""; });
        },
      });
    });
    viewer.on("destroy", function() {
      viewer = null;
      shell.close();
      shell.replaceChildren();
      if (cleanup) cleanup();
      if (trigger.isConnected && trigger.getClientRects().length) trigger.focus();
    });
    viewer.init();
    return true;
  }
  window.LixityResearchMedia = {open: open};
})();
