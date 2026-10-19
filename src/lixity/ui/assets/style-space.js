(function initDim3D() {
  var canvas = document.getElementById("dim-3d-canvas");
  if (!canvas) return;

  var tooltip = document.getElementById("dim-3d-tooltip");
  var btnTraj = document.getElementById("dim-ctl-traj");
  var btnCorr = document.getElementById("dim-ctl-corr");
  var btnSpin = document.getElementById("dim-ctl-spin");
  var btnReset = document.getElementById("dim-ctl-reset");
  var chapterSelect = document.getElementById("dim-chapter-select");
  var selection = document.getElementById("dim-selection");
  var readChapter = document.getElementById("dim-read-chapter");
  var projectionSelect = document.getElementById("dim-projection");
  var retained = document.getElementById("dim-retained");

  var raw = canvas.getAttribute("data-dim3d");
  if (!raw) return;
  var data;
  try {
    data = JSON.parse(raw);
  } catch (e) {
    if (window.LixityLog) window.LixityLog.warn("style-space: failed to parse data-dim3d JSON:", e);
    return;
  }

  var points = Array.isArray(data.points) ? data.points.filter(function(point) {
    return point && [point.x, point.y, point.z].every(Number.isFinite);
  }) : [];
  var threshold = Number.isFinite(data.threshold) && data.threshold > 0 ? data.threshold : 2.5;
  var axes = data.axes || [];
  var labels = data.labels || {};
  var scoreFormat = new Intl.NumberFormat(data.language || "en", {
    minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: "exceptZero"
  });
  var thresholdFormat = new Intl.NumberFormat(data.language || "en", {maximumSignificantDigits:21});
  var thresholdLabel = typeof data.threshold_label === "string" ? data.threshold_label : thresholdFormat.format(threshold);
  var varianceFormat = new Intl.NumberFormat(data.language || "en", {
    minimumFractionDigits: 1, maximumFractionDigits: 1
  });
  if (!points.length) {
    if (window.LixityLog) window.LixityLog.debug("style-space: no 3D points to render");
    return;
  }

  var ctx = canvas.getContext("2d");
  if (!ctx) {
    if (window.LixityLog) window.LixityLog.error("style-space: failed to obtain canvas 2D context");
    return;
  }
  if (window.LixityLog) {
    window.LixityLog.debug("style-space: initialized with " + points.length + " points, threshold " + threshold);
  }

  var yaw = 0.55;
  var pitch = 0.35;
  var zoom = 1.0;
  var showTrajectory = true;
  var showCorridor = true;
  var spin = false;
  var hoveredPoint = null;
  var isDragging = false;
  var lastX = 0, lastY = 0;
  var spinSpeed = 0.005;
  var animationFrame = null;
  var dragDistance = 0;
  var projectedPoints = [];
  var selectedPoint = points[0];
  var projection = "3d";
  var palette = null;
  var colorProbe = document.createElement("span");
  colorProbe.hidden = true;
  document.body.appendChild(colorProbe);

  function canvasPalette() {
    if (palette) return palette;
    palette = {};
    // Resolve light-dark() and other CSS color functions to canvas-ready values.
    // Cache them: drag/spin frames must not repeat DOM writes and style reads.
    ["fg", "line", "muted", "accent", "surface"].forEach(function(role) {
      colorProbe.style.color = "var(--" + role + ")";
      palette[role] = getComputedStyle(colorProbe).color;
    });
    var scheme = getComputedStyle(document.documentElement).colorScheme;
    palette.dark = scheme === "dark" || (scheme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    return palette;
  }

  function refreshPalette() {
    palette = null;
    draw();
  }

  function displayedAxes() {
    if (projection === "3d") return axes.map(function(_, index) { return index; });
    return projection.split("-").map(function(axis) { return Number(axis.slice(1)) - 1; });
  }

  function renderSelection() {
    if (!selection || !selectedPoint) return;
    selection.replaceChildren();
    selection.setAttribute("data-chapter", String(selectedPoint.ch));
    appendText(selection, "strong", "", selectedPoint.ch + ". " + selectedPoint.title);
    var scores = appendText(selection, "dl", "dim-selected-scores", "");
    axes.forEach(function(axis, index) {
      var row = appendText(scores, "div", "", "");
      var name = appendText(row, "dt", "", "D" + axis.idx);
      var meaning = [];
      if (axis.pos) meaning.push("+ " + axis.pos);
      if (axis.neg) meaning.push("− " + axis.neg);
      appendText(name, "span", "dim-axis-meaning", meaning.join(" / "));
      appendText(row, "dd", "", scoreFormat.format(selectedPoint[["x", "y", "z"][index]]));
    });
    appendText(selection, "p", "", selectedPoint.flagged ? labels.status_flagged : labels.not_flagged);
    if (chapterSelect) chapterSelect.value = String(selectedPoint.ch);
    if (readChapter) {
      readChapter.setAttribute("href", "#ch-" + selectedPoint.ch);
      readChapter.setAttribute("data-jump", "#ch-" + selectedPoint.ch);
    }
  }

  function selectChapter(point) {
    selectedPoint = point;
    renderSelection();
    draw();
  }

  if (chapterSelect) {
    chapterSelect.disabled = false;
    chapterSelect.addEventListener("change", function() {
      var point = points.find(function(candidate) { return String(candidate.ch) === chapterSelect.value; });
      if (point) selectChapter(point);
    });
  }

  function setProjection(value) {
    projection = value;
    canvas.setAttribute("data-projection", projection);
    if (projectionSelect) projectionSelect.value = value;
    if (retained && labels.retained) {
      var share = displayedAxes().reduce(function(total, index) { return total + axes[index].variance; }, 0);
      retained.textContent = labels.retained.replace("{variance}", varianceFormat.format(share * 100));
    }
    [btnSpin, document.getElementById("dim-ctl-left"), document.getElementById("dim-ctl-right"),
      document.getElementById("dim-ctl-up"), document.getElementById("dim-ctl-down")].forEach(function(button) {
      if (button) button.disabled = projection !== "3d";
    });
    if (projection !== "3d") {
      spin = false;
      setPressed(btnSpin, false);
    }
    clearHover();
    scheduleAnimation();
    draw();
  }

  if (projectionSelect) {
    projectionSelect.disabled = false;
    projectionSelect.addEventListener("change", function() { setProjection(projectionSelect.value); });
  }

  function setPressed(button, pressed) {
    if (!button) return;
    button.classList.toggle("active", pressed);
    button.setAttribute("aria-pressed", String(pressed));
  }

  setPressed(btnTraj, showTrajectory);
  setPressed(btnCorr, showCorridor);
  setPressed(btnSpin, spin);

  function clearHover() {
    hoveredPoint = null;
    if (tooltip) tooltip.style.display = "none";
  }

  var maxCoord = threshold * 1.35;
  for (var i = 0; i < points.length; i++) {
    var p = points[i];
    maxCoord = Math.max(maxCoord, Math.abs(p.x), Math.abs(p.y), Math.abs(p.z));
  }

  function resize() {
    var dpr = window.devicePixelRatio || 1;
    var w = canvas.clientWidth || canvas.offsetWidth || (canvas.parentElement ? canvas.parentElement.clientWidth : 800) || 800;
    var h = canvas.clientHeight || canvas.offsetHeight || 440;
    if (w < 10) w = 800;
    if (h < 10) h = 440;
    if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
    }
  }

  function project(x, y, z, cx, cy, radius) {
    if (projection !== "3d") {
      var indices = displayedAxes();
      var values = [x, y, z];
      return { x: cx + values[indices[0]] / maxCoord * radius * zoom,
        y: cy - values[indices[1]] / maxCoord * radius * zoom, depth: 0, scale: 1 };
    }
    var normX = x / maxCoord;
    var normY = y / maxCoord;
    var normZ = z / maxCoord;

    var sx = normX * radius * zoom;
    var sy = normY * radius * zoom;
    var sz = normZ * radius * zoom;

    var cosY = Math.cos(yaw), sinY = Math.sin(yaw);
    var x1 = sx * cosY + sz * sinY;
    var z1 = -sx * sinY + sz * cosY;

    var cosP = Math.cos(pitch), sinP = Math.sin(pitch);
    var y1 = sy * cosP - z1 * sinP;
    var z2 = sy * sinP + z1 * cosP;

    var fov = 520;
    var camDist = Math.max(700, radius * zoom * 2);
    var scale = fov / (camDist + z2);

    return {
      x: cx + x1 * scale,
      y: cy - y1 * scale,
      depth: z2,
      scale: scale
    };
  }

  function draw() {
    resize();
    var dpr = window.devicePixelRatio || 1;
    var w = canvas.width / dpr;
    var h = canvas.height / dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    var cx = w / 2;
    var cy = h / 2;
    var radius = Math.min(w, h) * 0.40;

    var colors = canvasPalette();
    var fg = colors.fg, line = colors.line, muted = colors.muted;
    var accent = colors.accent, surface = colors.surface, isDark = colors.dark;

    var flagColor = isDark ? "#f59e0b" : "#d97706";
    var gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";

    // Rank-space reference grid; planar views use their selected axes.
    var gridStep = Math.max(threshold, maxCoord / 4);
    var gridLines = Math.min(8, Math.floor(2 * (maxCoord / gridStep)));
    ctx.save();
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    for (var gridX = 0; gridX <= gridLines; gridX++) {
      var gx = -maxCoord + gridX * gridStep;
      var gridAxes = projection === "3d" ? [0, 2] : displayedAxes();
      var start = [0, 0, 0], end = [0, 0, 0];
      start[gridAxes[0]] = end[gridAxes[0]] = gx;
      start[gridAxes[1]] = -maxCoord;
      end[gridAxes[1]] = maxCoord;
      var pA = project(start[0], start[1], start[2], cx, cy, radius);
      var pB = project(end[0], end[1], end[2], cx, cy, radius);
      ctx.beginPath();
      ctx.moveTo(pA.x, pA.y);
      ctx.lineTo(pB.x, pB.y);
      ctx.stroke();
    }
    for (var gridZ = 0; gridZ <= gridLines; gridZ++) {
      var gz = -maxCoord + gridZ * gridStep;
      var gridIndices = projection === "3d" ? [0, 2] : displayedAxes();
      var gridStart = [0, 0, 0], gridEnd = [0, 0, 0];
      gridStart[gridIndices[0]] = -maxCoord;
      gridEnd[gridIndices[0]] = maxCoord;
      gridStart[gridIndices[1]] = gridEnd[gridIndices[1]] = gz;
      var pC = project(gridStart[0], gridStart[1], gridStart[2], cx, cy, radius);
      var pD = project(gridEnd[0], gridEnd[1], gridEnd[2], cx, cy, radius);
      ctx.beginPath();
      ctx.moveTo(pC.x, pC.y);
      ctx.lineTo(pD.x, pD.y);
      ctx.stroke();
    }
    ctx.restore();

    projectedPoints = points.map(function(point) {
      var projected = project(point.x, point.y, point.z, cx, cy, radius);
      return {orig: point, x: projected.x, y: projected.y, depth: projected.depth,
        scale: projected.scale, isHovered: hoveredPoint && hoveredPoint.ch === point.ch,
        isSelected: selectedPoint && selectedPoint.ch === point.ch};
    });
    var pointBoxes = projectedPoints.map(function(point) {
      var size = nodeRadius(point) + (point.orig.flagged ? 5 : 2);
      return {left: point.x - size, right: point.x + size, top: point.y - size, bottom: point.y + size};
    });
    var labelBoxes = [];
    function overlaps(a, b) {
      return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
    }
    function labelPositions(x, y, gap, halfWidth) {
      return [[x + gap + halfWidth, y], [x - gap - halfWidth, y], [x, y - gap - 8], [x, y + gap + 8],
        [x + gap + halfWidth, y - gap], [x - gap - halfWidth, y - gap],
        [x + gap + halfWidth, y + gap], [x - gap - halfWidth, y + gap]];
    }
    function paintLabel(text, positions) {
      var metrics = ctx.measureText(text);
      for (var candidate = 0; candidate < positions.length; candidate++) {
        var x = Math.max(metrics.actualBoundingBoxLeft + 4, Math.min(w - metrics.actualBoundingBoxRight - 4, positions[candidate][0]));
        var y = Math.max(metrics.actualBoundingBoxAscent + 4, Math.min(h - metrics.actualBoundingBoxDescent - 4, positions[candidate][1]));
        var box = {left: x - metrics.actualBoundingBoxLeft - 2, right: x + metrics.actualBoundingBoxRight + 2,
          top: y - metrics.actualBoundingBoxAscent - 2, bottom: y + metrics.actualBoundingBoxDescent + 2};
        if (labelBoxes.some(function(other) { return overlaps(box, other); }) ||
            pointBoxes.some(function(other) { return overlaps(box, other); })) continue;
        labelBoxes.push(box);
        ctx.fillText(text, x, y);
        return;
      }
      // Dense projections can exhaust these bounded positions. The point,
      // tooltip, chapter selector and score table remain available.
    }

    // 2. Coordinate Axes: Dim 1 (X), Dim 2 (Y), Dim 3 (Z)
    var axisLength = threshold * 1.15;
    var axisDefs = [
      { name: "D1", endPos: project(axisLength, 0, 0, cx, cy, radius), endNeg: project(-axisLength, 0, 0, cx, cy, radius), info: axes[0] },
      { name: "D2", endPos: project(0, axisLength, 0, cx, cy, radius), endNeg: project(0, -axisLength, 0, cx, cy, radius), info: axes[1] },
      { name: "D3", endPos: project(0, 0, axisLength, cx, cy, radius), endNeg: project(0, 0, -axisLength, cx, cy, radius), info: axes[2] }
    ].filter(function(_, index) { return displayedAxes().includes(index); });

    ctx.save();
    ctx.lineWidth = 1;
    ctx.font = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    for (var a = 0; a < axisDefs.length; a++) {
      var ax = axisDefs[a];
      ctx.strokeStyle = line;
      ctx.beginPath();
      ctx.moveTo(ax.endNeg.x, ax.endNeg.y);
      ctx.lineTo(ax.endPos.x, ax.endPos.y);
      ctx.stroke();

      if (ax.info) {
        ctx.fillStyle = muted;
        // Full signed feature meanings stay in the persistent inspector.
        [["+", ax.endPos], ["−", ax.endNeg]].forEach(function(side) {
          var text = side[0] + ax.name, end = side[1];
          var distance = Math.hypot(end.x - cx, end.y - cy) || 1;
          var positions = labelPositions(end.x, end.y, 8, ctx.measureText(text).width / 2);
          positions.unshift([end.x + (end.x - cx) / distance * 18, end.y + (end.y - cy) / distance * 18]);
          paintLabel(text, positions);
        });
      }
    }
    ctx.restore();

    if (showCorridor) {
      ctx.save();
      ctx.strokeStyle = isDark ? "rgba(74, 138, 212, 0.28)" : "rgba(43, 92, 143, 0.22)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([3, 4]);
      var corners = [];
      var corridorAxes = displayedAxes();
      for (var corner = 0; corner < Math.pow(2, corridorAxes.length); corner++) {
        var coordinates = [0, 0, 0];
        corridorAxes.forEach(function(axis, index) {
          coordinates[axis] = corner & Math.pow(2, index) ? threshold : -threshold;
        });
        corners.push(project(coordinates[0], coordinates[1], coordinates[2], cx, cy, radius));
      }
      ctx.beginPath();
      for (var vertex = 0; vertex < corners.length; vertex++) {
        for (var axisBit = 1; axisBit < corners.length; axisBit *= 2) {
          var neighbor = vertex ^ axisBit;
          if (neighbor > vertex) {
            ctx.moveTo(corners[vertex].x, corners[vertex].y);
            ctx.lineTo(corners[neighbor].x, corners[neighbor].y);
          }
        }
      }
      ctx.stroke();
      ctx.restore();
    }

    // 5. Draw Narrative Trajectory Line
    if (showTrajectory && projectedPoints.length > 1) {
      ctx.save();
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = isDark ? "rgba(74, 138, 212, 0.45)" : "rgba(43, 92, 143, 0.4)";
      ctx.beginPath();
      for (var t = 0; t < projectedPoints.length; t++) {
        var tp = projectedPoints[t];
        if (t === 0) ctx.moveTo(tp.x, tp.y);
        else ctx.lineTo(tp.x, tp.y);
      }
      ctx.stroke();
      ctx.restore();
    }

    // 6. Draw Chapter Nodes (sorted by depth)
    var sortedPoints = projectedPoints.slice().sort(function(a, b) {
      return b.depth - a.depth;
    });

    for (var s = 0; s < sortedPoints.length; s++) {
      var spt = sortedPoints[s];
      var orig = spt.orig;
      var nodeR = nodeRadius(spt);

      if (spt.isHovered) {
        var floorProj = project(orig.x, 0, orig.z, cx, cy, radius);
        ctx.save();
        ctx.strokeStyle = isDark ? "rgba(255, 255, 255, 0.3)" : "rgba(0, 0, 0, 0.25)";
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(spt.x, spt.y);
        ctx.lineTo(floorProj.x, floorProj.y);
        ctx.stroke();

        ctx.fillStyle = isDark ? "rgba(255, 255, 255, 0.3)" : "rgba(0, 0, 0, 0.25)";
        ctx.beginPath();
        ctx.arc(floorProj.x, floorProj.y, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      ctx.save();
      ctx.beginPath();
      ctx.arc(spt.x, spt.y, nodeR, 0, Math.PI * 2);

      if (orig.flagged) {
        ctx.fillStyle = flagColor;
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = surface;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(spt.x, spt.y, nodeR + 3, 0, Math.PI * 2);
        ctx.strokeStyle = flagColor;
        ctx.lineWidth = 1;
        ctx.stroke();
      } else if (spt.isHovered || spt.isSelected) {
        ctx.fillStyle = accent;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = surface;
        ctx.stroke();
      } else {
        ctx.fillStyle = surface;
        ctx.fill();
        ctx.lineWidth = 1.8;
        ctx.strokeStyle = accent;
        ctx.stroke();
      }

      ctx.restore();
    }
    ctx.save();
    ctx.font = "bold 12px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    // Keep the selected chapter's numeral when nearby points compete for space.
    sortedPoints.sort(function(a, b) { return Number(b.isSelected || b.isHovered) - Number(a.isSelected || a.isHovered); });
    sortedPoints.forEach(function(point) {
      if (point.x < 0 || point.x > w || point.y < 0 || point.y > h) return;
      ctx.fillStyle = point.isHovered || point.orig.flagged ? fg : muted;
      var text = String(point.orig.ch);
      paintLabel(text, labelPositions(point.x, point.y, nodeRadius(point) + 8, ctx.measureText(text).width / 2));
    });
    ctx.restore();
  }

  function nodeRadius(point) {
    return (point.orig.flagged ? 6.5 : 4.5) * (0.8 + point.scale * 0.35) *
      (point.isHovered ? 1.4 : point.isSelected ? 1.2 : 1);
  }

  function getCanvasPos(e) {
    var rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  function rotate(deltaYaw, deltaPitch) {
    if (projection !== "3d") return;
    yaw += deltaYaw;
    pitch = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, pitch + deltaPitch));
    clearHover();
    draw();
  }

  function changeZoom(factor) {
    zoom = Math.max(0.6, Math.min(2.4, zoom * factor));
    clearHover();
    draw();
  }

  [
    ["dim-ctl-left", -0.15, 0],
    ["dim-ctl-right", 0.15, 0],
    ["dim-ctl-up", 0, -0.15],
    ["dim-ctl-down", 0, 0.15]
  ].forEach(function(control) {
    var button = document.getElementById(control[0]);
    if (button) button.addEventListener("click", function() { rotate(control[1], control[2]); });
  });
  [
    ["dim-ctl-zoom-in", 1.08],
    ["dim-ctl-zoom-out", 0.92]
  ].forEach(function(control) {
    var button = document.getElementById(control[0]);
    if (button) button.addEventListener("click", function() { changeZoom(control[1]); });
  });

  canvas.addEventListener("pointerdown", function(e) {
    if (e.button !== 0) return;
    dragDistance = 0;
    if (projection !== "3d") return;
    isDragging = true;
    dragDistance = 0;
    lastX = e.clientX;
    lastY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
  });

  window.addEventListener("pointerup", function(e) {
    if (isDragging) {
      isDragging = false;
      try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
    }
  });

  canvas.addEventListener("pointermove", function(e) {
    if (isDragging) {
      var dx = e.clientX - lastX;
      var dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      dragDistance += Math.hypot(dx, dy);
      rotate(dx * 0.009, dy * 0.009);
      return;
    }

    updateHover(e);
  });

  function findPoint(e) {
    var pos = getCanvasPos(e);

    var bestDist = 14;
    var closest = null;
    var closestScreen = null;

    for (var index = 0; index < projectedPoints.length; index++) {
      var pr = projectedPoints[index];
      var dist = Math.hypot(pr.x - pos.x, pr.y - pos.y);
      if (dist < bestDist) {
        bestDist = dist;
        closest = pr.orig;
        closestScreen = pr;
      }
    }
    return { point: closest, screen: closestScreen };
  }

  function appendText(parent, tag, className, text) {
    var element = document.createElement(tag);
    element.className = className;
    element.textContent = text;
    parent.appendChild(element);
    return element;
  }

  function renderTooltip(point) {
    tooltip.replaceChildren();
    appendText(tooltip, "div", "dim-tt-title", point.title || String(point.ch));
    axes.forEach(function(axis, index) {
      var value = point[["x", "y", "z"][index]];
      var row = appendText(tooltip, "div", "dim-tt-row", "");
      appendText(row, "span", "", "D" + axis.idx);
      appendText(row, "b", "", scoreFormat.format(value));
    });
    if (point.flagged) {
      appendText(tooltip, "div", "dim-tt-flag", (labels.flagged || "Flagged") + " (|score| ≥ " + thresholdLabel + ")");
    }
  }

  function updateHover(e) {
    var hit = findPoint(e);
    var closest = hit.point;
    var closestScreen = hit.screen;

    if (closest !== hoveredPoint) {
      hoveredPoint = closest;
      draw();
    }

    if (closest && closestScreen && tooltip) {
      renderTooltip(closest);
      tooltip.style.display = "block";
      var halfWidth = tooltip.offsetWidth / 2;
      tooltip.style.left = Math.max(halfWidth, Math.min(canvas.clientWidth - halfWidth, closestScreen.x)) + "px";
      tooltip.style.top = Math.max(tooltip.offsetHeight + 10, closestScreen.y) + "px";
    } else if (tooltip) {
      tooltip.style.display = "none";
    }
  }

  canvas.addEventListener("lostpointercapture", function() {
    isDragging = false;
  });

  canvas.addEventListener("pointercancel", function() {
    isDragging = false;
    dragDistance = 5;
    clearHover();
    draw();
  });

  canvas.addEventListener("pointerleave", function() {
    if (!isDragging && hoveredPoint) {
      hoveredPoint = null;
      if (tooltip) tooltip.style.display = "none";
      draw();
    }
  });

  canvas.addEventListener("wheel", function(e) {
    e.preventDefault();
    changeZoom(e.deltaY < 0 ? 1.08 : 0.92);
  }, { passive: false });

  canvas.addEventListener("click", function(e) {
    if (dragDistance > 4) return;
    var point = findPoint(e).point;
    if (point) selectChapter(point);
  });

  if (btnTraj) {
    btnTraj.addEventListener("click", function() {
      showTrajectory = !showTrajectory;
      setPressed(btnTraj, showTrajectory);
      draw();
    });
  }
  if (btnCorr) {
    btnCorr.addEventListener("click", function() {
      showCorridor = !showCorridor;
      setPressed(btnCorr, showCorridor);
      draw();
    });
  }
  if (btnSpin) {
    btnSpin.addEventListener("click", function() {
      spin = !spin;
      setPressed(btnSpin, spin);
      clearHover();
      scheduleAnimation();
    });
  }
  if (btnReset) {
    btnReset.addEventListener("click", function() {
      yaw = 0.55;
      pitch = 0.35;
      zoom = 1.0;
      spin = false;
      setPressed(btnSpin, spin);
      clearHover();
      setProjection("3d");
    });
  }

  function animate() {
    animationFrame = null;
    if (spin && !document.hidden && canvas.getClientRects().length) {
      yaw += spinSpeed;
      draw();
    }
    scheduleAnimation();
  }

  function scheduleAnimation() {
    if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    animationFrame = spin && !document.hidden && canvas.getClientRects().length
      ? requestAnimationFrame(animate) : null;
  }

  document.addEventListener("visibilitychange", scheduleAnimation);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", refreshPalette);
  new MutationObserver(refreshPalette).observe(document.documentElement, {
    attributes:true, attributeFilter:["data-theme", "class", "style"]
  });
  window.addEventListener("resize", function() {
    clearHover();
    draw();
    scheduleAnimation();
  });
  canvas.setAttribute("data-projection", projection);
  renderSelection();
  draw();
})();
