(function initDim3D() {
  var canvas = document.getElementById("dim-3d-canvas");
  if (!canvas) return;

  var tooltip = document.getElementById("dim-3d-tooltip");
  var btnTraj = document.getElementById("dim-ctl-traj");
  var btnCorr = document.getElementById("dim-ctl-corr");
  var btnSpin = document.getElementById("dim-ctl-spin");
  var btnReset = document.getElementById("dim-ctl-reset");

  var raw = canvas.getAttribute("data-dim3d");
  if (!raw) return;
  var data;
  try {
    data = JSON.parse(raw);
  } catch (e) {
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
  var thresholdFormat = new Intl.NumberFormat(data.language || "en");
  if (!points.length) return;

  var ctx = canvas.getContext("2d");
  if (!ctx) return;

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

    var cs = getComputedStyle(document.documentElement);
    var fg = cs.getPropertyValue("--fg").trim() || "#1d2129";
    var line = cs.getPropertyValue("--line").trim() || "#e6e9ee";
    var muted = cs.getPropertyValue("--muted").trim() || "#656d78";
    var accent = cs.getPropertyValue("--accent").trim() || "#2b5c8f";
    var surface = cs.getPropertyValue("--surface").trim() || "#ffffff";
    var isDark = cs.getPropertyValue("--bg").trim().includes("0e1013") ||
                 window.matchMedia("(prefers-color-scheme: dark)").matches;

    var flagColor = isDark ? "#f59e0b" : "#d97706";
    var gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";

    // 1. Median house style plane (Y = 0)
    var gridStep = threshold;
    ctx.save();
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    for (var gx = -maxCoord; gx <= maxCoord + 0.01; gx += gridStep) {
      var pA = project(gx, 0, -maxCoord, cx, cy, radius);
      var pB = project(gx, 0, maxCoord, cx, cy, radius);
      ctx.beginPath();
      ctx.moveTo(pA.x, pA.y);
      ctx.lineTo(pB.x, pB.y);
      ctx.stroke();
    }
    for (var gz = -maxCoord; gz <= maxCoord + 0.01; gz += gridStep) {
      var pC = project(-maxCoord, 0, gz, cx, cy, radius);
      var pD = project(maxCoord, 0, gz, cx, cy, radius);
      ctx.beginPath();
      ctx.moveTo(pC.x, pC.y);
      ctx.lineTo(pD.x, pD.y);
      ctx.stroke();
    }
    ctx.restore();

    // 2. Coordinate Axes: Dim 1 (X), Dim 2 (Y), Dim 3 (Z)
    var axisLength = threshold * 1.15;
    var axisDefs = [
      { name: "D1", endPos: project(axisLength, 0, 0, cx, cy, radius), endNeg: project(-axisLength, 0, 0, cx, cy, radius), info: axes[0] },
      { name: "D2", endPos: project(0, axisLength, 0, cx, cy, radius), endNeg: project(0, -axisLength, 0, cx, cy, radius), info: axes[1] },
      { name: "D3", endPos: project(0, 0, axisLength, cx, cy, radius), endNeg: project(0, 0, -axisLength, cx, cy, radius), info: axes[2] }
    ];

    ctx.save();
    ctx.lineWidth = 1;
    ctx.font = "10px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
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
        if (ax.info.pos) {
          ctx.fillText("+" + ax.name + " (" + ax.info.pos + ")", ax.endPos.x, ax.endPos.y - 10);
        }
        if (ax.info.neg) {
          ctx.fillText("−" + ax.name + " (" + ax.info.neg + ")", ax.endNeg.x, ax.endNeg.y + 10);
        }
      }
    }
    ctx.restore();

    if (showCorridor) {
      ctx.save();
      ctx.strokeStyle = isDark ? "rgba(74, 138, 212, 0.28)" : "rgba(43, 92, 143, 0.22)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([3, 4]);
      var corners = [];
      for (var corner = 0; corner < 8; corner++) {
        corners.push(project(
          corner & 1 ? threshold : -threshold,
          corner & 2 ? threshold : -threshold,
          corner & 4 ? threshold : -threshold, cx, cy, radius
        ));
      }
      ctx.beginPath();
      for (var vertex = 0; vertex < corners.length; vertex++) {
        for (var axisBit = 1; axisBit <= 4; axisBit *= 2) {
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

    // 4. Project all points
    projectedPoints = [];
    for (var pIdx = 0; pIdx < points.length; pIdx++) {
      var pt = points[pIdx];
      var pr = project(pt.x, pt.y, pt.z, cx, cy, radius);
      projectedPoints.push({
        orig: pt,
        x: pr.x,
        y: pr.y,
        depth: pr.depth,
        scale: pr.scale,
        isHovered: (hoveredPoint && hoveredPoint.ch === pt.ch)
      });
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
      var nodeR = (orig.flagged ? 6.5 : 4.5) * (0.8 + spt.scale * 0.35);
      if (spt.isHovered) nodeR *= 1.4;

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
      } else if (spt.isHovered) {
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

      ctx.font = "bold 9px ui-monospace, SFMono-Regular, Menlo, monospace";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillStyle = spt.isHovered || orig.flagged ? fg : muted;
      ctx.fillText(String(orig.ch), spt.x + nodeR + 3, spt.y);

      ctx.restore();
    }
  }

  function getCanvasPos(e) {
    var rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  }

  canvas.addEventListener("pointerdown", function(e) {
    if (e.button !== 0) return;
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
      clearHover();

      yaw += dx * 0.009;
      pitch += dy * 0.009;
      pitch = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, pitch));
      draw();
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
    [point.x, point.y, point.z].forEach(function(value, index) {
      var row = appendText(tooltip, "div", "dim-tt-row", "");
      appendText(row, "span", "", (labels.dimension || "Dimension") + " " + (index + 1));
      appendText(row, "b", "", scoreFormat.format(value));
    });
    if (point.flagged) {
      appendText(tooltip, "div", "dim-tt-flag", (labels.flagged || "Flagged") + " (|score| ≥ " + thresholdFormat.format(threshold) + ")");
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
    var delta = e.deltaY < 0 ? 1.08 : 0.92;
    zoom = Math.max(0.6, Math.min(2.4, zoom * delta));
    clearHover();
    draw();
  }, { passive: false });

  canvas.addEventListener("click", function(e) {
    if (dragDistance > 4) return;
    var point = findPoint(e).point;
    if (point) {
      var chTarget = document.getElementById("ch-" + point.ch);
      if (chTarget) {
        scrollAndFlash(chTarget);
      }
    }
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
      scheduleAnimation();
      draw();
    });
  }

  function animate() {
    animationFrame = null;
    if (spin && !document.hidden) {
      yaw += spinSpeed;
      draw();
    }
    scheduleAnimation();
  }

  function scheduleAnimation() {
    if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    animationFrame = spin && !document.hidden ? requestAnimationFrame(animate) : null;
  }

  document.addEventListener("visibilitychange", scheduleAnimation);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  window.addEventListener("resize", function() {
    clearHover();
    draw();
  });
  draw();
})();
