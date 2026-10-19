// One geography field shared by dossier creation, revisions and saved readers.
// Coordinates are author-supplied data; the sketch uses no tiles or network API.
(function () {
  "use strict";
  var types = ["Point", "LineString", "Polygon", "unknown"];
  var transports = ["walking", "driving", "cycling", "rail", "boat", "other"];
  var maxFeatures = 200, maxCoordinates = 10000, maxImportBytes = 4 * 1024 * 1024;
  function label(key) { return uiLabel("geography_" + key); }
  function safe(value) { return escapeHtml(String(value == null ? "" : value)).replace(/"/g, "&quot;"); }
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function length(value) { return Array.from(value).length; }
  function invalid() { return new Error(label("invalid")); }
  function position(value) {
    return Array.isArray(value) && value.length === 2 && value.every(function(n) { return typeof n === "number" && Number.isFinite(n); }) &&
      Math.abs(value[0]) <= 180 && Math.abs(value[1]) <= 90;
  }
  function validate(value) {
    if (value === null) return null;
    if (!value || value.type !== "FeatureCollection" || !Array.isArray(value.features) || value.features.length > maxFeatures ||
        Object.keys(value).some(function(key) { return !["type", "features"].includes(key); })) throw invalid();
    var count = 0;
    value.features.forEach(function(feature) {
      if (!feature || feature.type !== "Feature" || !Object.prototype.hasOwnProperty.call(feature, "geometry") ||
          Object.keys(feature).some(function(key) { return !["type", "geometry", "properties"].includes(key); })) throw invalid();
      var props = feature.properties;
      if (!props || typeof props !== "object" || Array.isArray(props) || typeof props.label !== "string" || !props.label.trim() ||
          Object.keys(props).some(function(key) { return !["label", "description", "time_period", "actors", "transport", "feature_type", "waypoint_labels"].includes(key); })) throw invalid();
      ["label", "description", "time_period", "feature_type"].forEach(function(key) {
        if (props[key] != null && (typeof props[key] !== "string" || !props[key].trim() || length(props[key]) > (key === "description" ? 4000 : 500))) throw invalid();
      });
      ["actors", "waypoint_labels"].forEach(function(key) {
        if (Object.prototype.hasOwnProperty.call(props, key) && (!Array.isArray(props[key]) || props[key].some(function(item) { return typeof item !== "string" || !length(item) || length(item) > (key === "actors" ? 100 : 500); }))) throw invalid();
      });
      if (props.actors && props.actors.length > 100) throw invalid();
      if (props.transport != null && !transports.includes(props.transport)) throw invalid();
      var geometry = feature.geometry, points = [];
      if (geometry !== null) {
        if (!geometry || !types.slice(0, 3).includes(geometry.type) || Object.keys(geometry).some(function(key) { return !["type", "coordinates"].includes(key); })) throw invalid();
        var coords = geometry.coordinates;
        if (geometry.type === "Point") points = [coords];
        else if (geometry.type === "LineString") {
          if (!Array.isArray(coords) || coords.length < 2) throw invalid();
          points = coords;
        } else {
          if (!Array.isArray(coords) || !coords.length) throw invalid();
          coords.forEach(function(ring) {
            if (!Array.isArray(ring) || ring.length < 4 || JSON.stringify(ring[0]) !== JSON.stringify(ring[ring.length - 1])) throw invalid();
            points = points.concat(ring);
          });
        }
        if (points.some(function(point) { return !position(point); })) throw invalid();
      }
      if (props.waypoint_labels && props.waypoint_labels.length &&
          (!geometry || geometry.type !== "LineString" || props.waypoint_labels.length !== geometry.coordinates.length)) throw invalid();
      count += points.length;
      if (count > maxCoordinates) throw invalid();
    });
    return clone(value);
  }
  function geometryPoints(geometry) {
    if (!geometry) return [];
    return geometry.type === "Point" ? [geometry.coordinates] : geometry.type === "LineString" ? geometry.coordinates : geometry.coordinates.flat();
  }
  function coordinateText(geometry) {
    if (!geometry) return "";
    function lines(points) { return points.map(function(point) { return point.join(", "); }).join("\n"); }
    return geometry.type === "Point" ? geometry.coordinates.join(", ") :
      geometry.type === "LineString" ? lines(geometry.coordinates) : geometry.coordinates.map(lines).join("\n\n");
  }
  function coordinateFrame(value) {
    var points = value.features.flatMap(function(feature) { return geometryPoints(feature.geometry); });
    if (!points.length) return null;
    // Place the longitude seam in the largest empty gap, so a local dateline
    // crossing stays local. This flat coordinate sketch is not a projection.
    var longitudes = points.map(function(point) { return (point[0] + 360) % 360; }).sort(function(a, b) { return a - b; });
    var start = longitudes[0], gap = -1;
    longitudes.forEach(function(lon, index) {
      var next = index + 1 < longitudes.length ? longitudes[index + 1] : longitudes[0] + 360;
      if (next - lon > gap) { gap = next - lon; start = next % 360; }
    });
    return {points: points, start: start, longitude: function(lon) { return ((lon + 360) % 360 - start + 360) % 360 + start; }};
  }
  function sketch(value, interactive) {
    var frame = coordinateFrame(value);
    if (!frame) return "";
    var points = frame.points;
    function longitude(lon) { return frame.longitude(lon) - frame.start; }
    var xs = points.map(function(point) { return longitude(point[0]); }), ys = points.map(function(point) { return point[1]; });
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs), minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
    var spanX = Math.max(maxX - minX, .01), spanY = Math.max(maxY - minY, .01), scale = Math.min(560 / spanX, 250 / spanY);
    function xy(point) { return [(300 + (longitude(point[0]) - (minX + maxX) / 2) * scale).toFixed(2),
      (155 - (point[1] - (minY + maxY) / 2) * scale).toFixed(2)]; }
    var ordered = value.features.map(function(feature, index) { return {feature: feature, index: index}; });
    // A route can end at a point. Paint points last so their controls remain
    // reachable instead of being covered by the route's endpoint.
    ordered.sort(function(a, b) {
      return Number(a.feature.geometry && a.feature.geometry.type === "Point") - Number(b.feature.geometry && b.feature.geometry.type === "Point");
    });
    var shapes = ordered.map(function(entry) {
      var feature = entry.feature, index = entry.index;
      var geometry = feature.geometry;
      if (!geometry) return "";
      var name = safe((index + 1) + ". " + feature.properties.label);
      var title = '<title>' + name + '</title>';
      var attributes = interactive ? ' data-geo-select="' + index + '" tabindex="0" role="button" aria-pressed="false" aria-label="' + name + '"' : '';
      if (geometry.type === "Point") {
        var point = xy(geometry.coordinates);
        return '<g' + attributes + '>' + title + '<circle cx="' + point[0] + '" cy="' + point[1] + '" r="5"/><text x="' + (Number(point[0]) + 9) + '" y="' + (Number(point[1]) - 8) + '">' + (index + 1) + '</text></g>';
      }
      var rings = geometry.type === "Polygon" ? geometry.coordinates : [geometry.coordinates];
      var paths = rings.map(function(ring) { return ring.map(function(point, i) { return (i ? "L" : "M") + xy(point).join(" "); }).join(" ") + (geometry.type === "Polygon" ? " Z" : ""); }).join(" ");
      var anchor = xy(geometry.type === "LineString" ? geometry.coordinates[Math.floor(geometry.coordinates.length / 2)] : rings[0][0]);
      return '<g' + attributes + '>' + title + '<path class="geography-' + (geometry.type === "Polygon" ? "area" : "route") + '" d="' + paths + '" fill-rule="evenodd"/>' +
        '<text x="' + (Number(anchor[0]) + 9) + '" y="' + (Number(anchor[1]) - 8) + '">' + (index + 1) + '</text></g>';
    }).join("");
    return '<svg class="geography-sketch" viewBox="0 0 600 310" role="' + (interactive ? 'group' : 'img') + '" aria-label="' + safe(label("sketch")) + '"><title>' + safe(label("sketch")) + '</title>' + shapes + '</svg>';
  }
  function html(value) {
    if (!value) return "";
    try { value = validate(value); } catch (_) { return '<p class="ctl-note">' + safe(label("invalid")) + '</p>'; }
    if (!value.features.length) return "";
    var canMap = Boolean(coordinateFrame(value));
    var mapControls = canMap ? '<button type="button" class="ctl ctl-sm" data-geo-map aria-expanded="false">' + safe(label("map")) + '</button>' +
      '<div class="geography-map-tools" hidden><button type="button" class="ctl ctl-sm" data-geo-fit>' + safe(label("fit")) + '</button>' +
      '<label class="form-checkbox"><input type="checkbox" data-geo-basemap/><span>' + safe(label("basemap")) + '</span></label>' +
      '<p class="ctl-note geography-basemap-hint">' + safe(label("basemap_hint")) + '</p></div>' +
      '<div class="geography-map" hidden role="group" aria-label="' + safe(label("map_label")) + '"></div><p class="ctl-status geography-map-status" role="status"></p>' : '';
    return '<section class="dossier-geography" data-geo-geometries="' + safe(JSON.stringify(value.features.map(function(feature) { return feature.geometry; }))) + '"><h4>' + safe(label("title")) + '</h4><p class="ctl-note">' + safe(label("hint")) + '</p>' +
      '<p class="ctl-note geography-navigation-hint">' + safe(label("navigation_hint")) + '</p>' + mapControls + sketch(value, true) +
      '<ol class="geography-feature-list">' + value.features.map(function(feature, index) {
        var props = feature.properties, geometry = feature.geometry;
        var meta = [label(geometry ? geometry.type : "unknown"), props.time_period, (props.actors || []).join(", "),
          props.transport ? label(props.transport) : "", props.feature_type].filter(Boolean);
        return '<li data-geo-feature-index="' + index + '"><button type="button" class="ctl ctl-link geography-feature-select" data-geo-select="' + index + '" aria-pressed="false"><strong>' + safe(props.label) + '</strong></button><p class="ctl-note">' + meta.map(safe).join(" · ") + '</p>' +
          (props.description ? '<p>' + safe(props.description) + '</p>' : '') +
          (props.waypoint_labels && props.waypoint_labels.length ? '<p>' + props.waypoint_labels.map(safe).join(" → ") + '</p>' : '') +
          (geometry ? '<details><summary>' + safe(label("coordinates")) + '</summary><pre>' + safe(coordinateText(geometry)) + '</pre></details>' : '') + '</li>';
      }).join("") + '</ol></section>';
  }
  function selectFeature(control) {
    var root = control.closest(".dossier-geography");
    if (!root) return;
    var index = control.dataset.geoSelect;
    if (!/^(0|[1-9]\d*)$/.test(index || "")) return;
    var entry = root.querySelector('li[data-geo-feature-index="' + index + '"]');
    if (!entry) return;
    // Selection belongs only to this rendered view; repeated history/companion
    // hosts share no state, and replacing the HTML discards the old selection.
    root.querySelectorAll("[data-geo-select]").forEach(function(node) {
      var selected = node.dataset.geoSelect === index;
      node.classList.toggle("is-selected", selected);
      node.setAttribute("aria-pressed", selected ? "true" : "false");
    });
    root.querySelectorAll("li[data-geo-feature-index]").forEach(function(node) {
      node.classList.toggle("is-selected", node === entry);
    });
    var coordinates = entry.querySelector("details");
    if (coordinates) coordinates.open = true;
    if (control.closest("svg")) {
      entry.querySelector("button[data-geo-select]").focus({preventScroll: true});
      entry.scrollIntoView({block: "nearest"});
    }
  }
  var maps = new Map();
  function mapContext() {
    return [typeof researchContextToken === "function" ? researchContextToken() : "",
      typeof researchSelectionProjectId === "undefined" ? "" : researchSelectionProjectId].join("\n");
  }
  function visible(root) { return root.isConnected && root.getClientRects().length > 0; }
  function stopTiles(state) {
    var tiles = state.tiles;
    state.tiles = null;
    if (tiles) state.map.removeLayer(tiles);
    var checkbox = state.root.querySelector("[data-geo-basemap]");
    if (checkbox) checkbox.checked = false;
  }
  function stopMap(state) {
    stopTiles(state);
    state.map.remove();
    delete state.host._geographyMap;
    state.host.replaceChildren(); state.host.hidden = true;
    state.root.classList.remove("geography-map-active");
    var tools = state.root.querySelector(".geography-map-tools");
    if (tools) tools.hidden = true;
    var toggle = state.root.querySelector("[data-geo-map]");
    if (toggle) { toggle.setAttribute("aria-expanded", "false"); toggle.textContent = label("map"); }
    maps.delete(state.root);
  }
  function fit(state) {
    var bounds = state.layers.getBounds();
    if (bounds.isValid()) state.map.fitBounds(bounds, {padding: [24, 24], maxZoom: 15, animate: false});
  }
  function startMap(root) {
    var status = root.querySelector(".geography-map-status"), host = root.querySelector(".geography-map");
    var state;
    try {
      if (!window.L || !visible(root)) throw invalid();
      var value = validate({type: "FeatureCollection", features: JSON.parse(root.dataset.geoGeometries).map(function(geometry, index) {
        return {type: "Feature", geometry: geometry, properties: {label: root.querySelector('button[data-geo-select="' + index + '"]').textContent}};
      })});
      var frame = coordinateFrame(value);
      if (!frame) throw invalid();
      host.hidden = false; root.classList.add("geography-map-active");
      var map = window.L.map(host, {zoomControl: false, scrollWheelZoom: false, minZoom: 0, maxZoom: 19,
        zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false, inertia: false});
      host._geographyMap = map;
      state = {root: root, host: host, map: map, tiles: null, context: mapContext(), layers: null};
      maps.set(root, state);
      map.setView([frame.points[0][1], frame.longitude(frame.points[0][0])], 5, {animate: false});
      window.L.control.zoom({zoomInTitle: label("zoom_in"), zoomOutTitle: label("zoom_out")}).addTo(map);
      state.layers = window.L.geoJSON(value, {
        coordsToLatLng: function(coords) { return window.L.latLng(coords[1], frame.longitude(coords[0])); },
        pointToLayer: function(feature, point) { return window.L.circleMarker(point, {radius: 7}); },
        style: {color: "var(--accent)", weight: 3, fillOpacity: .12},
      }).addTo(map);
      state.layers.eachLayer(function(layer) {
        var index = value.features.indexOf(layer.feature), node = layer.getElement();
        node.dataset.geoSelect = String(index); node.setAttribute("tabindex", "0");
        node.setAttribute("role", "button"); node.setAttribute("aria-pressed", "false");
        node.setAttribute("aria-label", (index + 1) + ". " + layer.feature.properties.label);
        layer.on("click", function() { selectFeature(node); });
        layer.bindTooltip(String(index + 1), {permanent: true, direction: "top", className: "geography-map-number"});
        if (layer.feature.geometry.type === "Point") layer.bringToFront();
      });
      var drawing = host.querySelector(".leaflet-overlay-pane > svg");
      if (drawing) { drawing.setAttribute("role", "group"); drawing.setAttribute("aria-label", label("map_label")); }
      fit(state);
      root.querySelector(".geography-map-tools").hidden = false;
      var toggle = root.querySelector("[data-geo-map]");
      toggle.setAttribute("aria-expanded", "true"); toggle.textContent = label("show_sketch");
      status.textContent = "";
      var selected = root.querySelector('button[data-geo-select][aria-pressed="true"]');
      if (selected) selectFeature(selected);
    } catch (_) {
      if (state) stopMap(state);
      else { host.hidden = true; root.classList.remove("geography-map-active"); }
      status.textContent = label("map_failed");
    }
  }
  document.addEventListener("click", function(event) {
    var toggle = event.target.closest("[data-geo-map], [data-geo-fit]");
    if (toggle) {
      var root = toggle.closest(".dossier-geography"), state = maps.get(root);
      if (state && (!state.host.isConnected || state.host !== root.querySelector(".geography-map"))) { stopMap(state); state = null; }
      if (toggle.hasAttribute("data-geo-fit")) { if (state) fit(state); }
      else if (state) stopMap(state);
      else startMap(root);
      return;
    }
    var control = event.target.closest("[data-geo-select]");
    if (control) selectFeature(control);
  });
  document.addEventListener("keydown", function(event) {
    var control = event.target.closest("svg [data-geo-select]");
    if (!control || !["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    selectFeature(control);
  });
  document.addEventListener("change", function(event) {
    if (!event.target.matches("[data-geo-basemap]")) return;
    var root = event.target.closest(".dossier-geography"), state = maps.get(root);
    if (!state || state.context !== mapContext() || !visible(root)) { event.target.checked = false; return; }
    if (!event.target.checked) { stopTiles(state); return; }
    root.querySelector(".geography-map-status").textContent = "";
    var tiles = window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, keepBuffer: 0, updateWhenIdle: true, referrerPolicy: "origin",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    });
    state.tiles = tiles;
    tiles.on("tileerror", function() {
      if (state.tiles !== tiles) return;
      stopTiles(state); root.querySelector(".geography-map-status").textContent = label("basemap_failed");
    });
    tiles.addTo(state.map);
  });
  document.addEventListener("click", function(event) {
    // End online approval before a navigation handler can resize a hidden map.
    if (event.target.closest("[data-view], [data-switch-view], [data-rtab]")) maps.forEach(stopTiles);
  }, true);
  var checkingMaps = false;
  new MutationObserver(function() {
    if (!maps.size || checkingMaps) return;
    checkingMaps = true;
    queueMicrotask(function() {
      checkingMaps = false;
      maps.forEach(function(state) {
        if (!visible(state.root) || !state.host.isConnected || state.context !== mapContext()) stopMap(state);
      });
    });
  }).observe(document.documentElement, {subtree: true, childList: true, attributes: true,
    attributeFilter: ["class", "style", "hidden", "open", "data-research-token"]});
  window.addEventListener("pagehide", function() { maps.forEach(stopMap); });
  function mount(host, identifier, value) {
    var root = document.createElement("details"); root.id = identifier + "-editor"; root.className = "geography-editor research-details";
    var summary = document.createElement("summary"); summary.textContent = label("title"); root.appendChild(summary);
    var hint = document.createElement("p"); hint.className = "ctl-note"; hint.textContent = label("edit_hint"); root.appendChild(hint);
    var input = document.createElement("input"); input.type = "hidden"; input.id = identifier; root.appendChild(input);
    var list = document.createElement("div"); list.className = "geography-editor-features"; root.appendChild(list);
    var actions = document.createElement("div"); actions.className = "row";
    var add = document.createElement("button"); add.type = "button"; add.className = "ctl ctl-sm"; add.dataset.geoAdd = ""; add.textContent = label("add"); actions.appendChild(add);
    var importLabel = document.createElement("label"); importLabel.className = "form-label"; importLabel.htmlFor = identifier + "-import"; importLabel.textContent = label("import");
    var file = document.createElement("input"); file.type = "file"; file.id = importLabel.htmlFor; file.className = "ctl"; file.accept = ".geojson,.json,application/geo+json,application/json"; file.dataset.geoImport = "";
    root.append(actions, importLabel, file);
    var status = document.createElement("p"); status.className = "ctl-status"; status.setAttribute("role", "status"); status.dataset.geoStatus = ""; root.appendChild(status);
    var preview = document.createElement("div"); preview.className = "geography-editor-preview"; root.appendChild(preview);
    host.appendChild(root);
    var sequence = 0, generation = 0, importing = false;
    function field(card, name) { return card.querySelector('[data-geo-field="' + name + '"]'); }
    function drafts() {
      return Array.from(list.children).map(function(card) {
        var raw = {};
        card.querySelectorAll("[data-geo-field]").forEach(function(control) { raw[control.dataset.geoField] = control.value; });
        return raw;
      });
    }
    function read(quiet) {
      if (importing) {
        if (!quiet) status.textContent = label("import_pending");
        throw new Error(label("import_pending"));
      }
      try {
        var features = drafts().map(function(raw, index) {
          var geometry = null;
          if (raw.type !== "unknown") {
            var rings = raw.coordinates.trim().split(/\n\s*\n/).map(function(ring) {
              return ring.split(/\r?\n/).map(function(line) {
                var pair = line.trim().split(/\s*,\s*|\s+/);
                if (pair.length !== 2 || pair.some(function(item) { return !item || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(item); })) throw invalid();
                return pair.map(Number);
              });
            });
            if (raw.type === "Point" && (rings.length !== 1 || rings[0].length !== 1)) throw invalid();
            if (raw.type === "LineString" && rings.length !== 1) throw invalid();
            geometry = {type: raw.type, coordinates: raw.type === "Point" ? rings[0][0] : raw.type === "LineString" ? rings[0] : rings};
          }
          var card = list.children[index], original = card._originalLists;
          function names(key) {
            // Newlines are valid inside imported labels. Keep the exact saved
            // array until its displayed list is edited by the author.
            return raw[key] === card._originalDisplays[key] ? original[key].slice() : raw[key] ? raw[key].split(/\r?\n/) : [];
          }
          function text(key) {
            return Object.prototype.hasOwnProperty.call(card._originalProperties, key) && raw[key] === card._originalDisplays[key] ?
              card._originalProperties[key] : raw[key];
          }
          var props = {label: text("label"), actors: names("actors")};
          ["description", "time_period", "transport", "feature_type"].forEach(function(key) { var value = text(key); if (value !== "") props[key] = value; });
          var waypoints = names("waypoint_labels");
          if (waypoints.length) props.waypoint_labels = waypoints;
          return {type: "Feature", geometry: geometry, properties: props};
        });
        var result = validate(features.length ? {type: "FeatureCollection", features: features} : null);
        status.textContent = "";
        return result;
      } catch (error) { if (!quiet) status.textContent = label("invalid"); throw error; }
    }
    function sync(notify) {
      generation++; importing = false;
      input.value = JSON.stringify(drafts());
      add.disabled = list.children.length >= maxFeatures || input.disabled;
      try { preview.innerHTML = sketch(read(true) || {features: []}); } catch (_) { preview.replaceChildren(); }
      if (notify) input.dispatchEvent(new Event("input", {bubbles: true}));
    }
    function appendFeature(feature) {
      var props = feature.properties || {}, card = document.createElement("fieldset"); card.className = "geography-editor-feature"; card.dataset.geoFeature = "";
      card._originalLists = {actors: (props.actors || []).slice(), waypoint_labels: (props.waypoint_labels || []).slice()};
      card._originalProperties = clone(props);
      var legend = document.createElement("legend"); legend.textContent = label("feature"); card.appendChild(legend);
      var index = ++sequence;
      function control(name, text, type, content, choices) {
        var group = document.createElement("div"); group.className = "form-group";
        var labelNode = document.createElement("label"); labelNode.className = "form-label"; labelNode.htmlFor = identifier + "-" + index + "-" + name; labelNode.textContent = text;
        var node = document.createElement(type === "select" ? "select" : type === "textarea" ? "textarea" : "input");
        node.className = "ctl"; node.id = labelNode.htmlFor; node.dataset.geoField = name;
        if (type === "select") choices.forEach(function(choice) { node.add(new Option(choice[1], choice[0])); });
        else if (type === "textarea") node.rows = name === "coordinates" ? 4 : 2;
        else node.type = "text";
        node.value = content || ""; group.append(labelNode, node); return group;
      }
      card.appendChild(control("label", label("name"), "text", props.label));
      card.appendChild(control("type", label("type"), "select", feature.geometry ? feature.geometry.type : "unknown", types.map(function(type) { return [type, label(type)]; })));
      var coordinates = control("coordinates", label("coordinates"), "textarea", coordinateText(feature.geometry));
      var note = document.createElement("p"); note.className = "ctl-note"; note.textContent = label("coordinate_hint"); coordinates.appendChild(note); card.appendChild(coordinates);
      var options = document.createElement("details"); options.className = "research-details"; var title = document.createElement("summary"); title.textContent = uiLabel("optional_details"); options.appendChild(title);
      options.appendChild(control("actors", label("actors"), "textarea", (props.actors || []).join("\n")));
      options.appendChild(control("transport", label("transport"), "select", props.transport, [["", "—"]].concat(transports.map(function(mode) { return [mode, label(mode)]; }))));
      options.appendChild(control("time_period", uiLabel("research_claim_time"), "text", props.time_period));
      options.appendChild(control("description", label("description"), "textarea", props.description));
      options.appendChild(control("feature_type", label("feature_type"), "text", props.feature_type));
      options.appendChild(control("waypoint_labels", label("waypoints"), "textarea", (props.waypoint_labels || []).join("\n")));
      card.appendChild(options);
      card._originalDisplays = {};
      card.querySelectorAll("[data-geo-field]").forEach(function(control) { card._originalDisplays[control.dataset.geoField] = control.value; });
      var remove = document.createElement("button"); remove.type = "button"; remove.className = "ctl ctl-sm"; remove.dataset.geoRemove = ""; remove.textContent = uiLabel("remove_recent_project"); card.appendChild(remove);
      function updateType() { coordinates.hidden = field(card, "type").value === "unknown"; }
      field(card, "type").addEventListener("change", updateType); updateType(); list.appendChild(card);
      return card;
    }
    function set(next, notify) {
      list.replaceChildren();
      (next && next.features || []).forEach(appendFeature);
      file.value = ""; sync(notify);
    }
    add.addEventListener("click", function() {
      if (input.disabled || list.children.length >= maxFeatures) return;
      var card = appendFeature({geometry: {type: "Point", coordinates: []}, properties: {label: ""}});
      sync(true); field(card, "label").focus();
    });
    list.addEventListener("input", function() { sync(true); });
    list.addEventListener("change", function() { sync(true); });
    list.addEventListener("click", function(event) {
      var remove = event.target.closest("[data-geo-remove]");
      if (!remove || input.disabled) return;
      remove.closest("[data-geo-feature]").remove(); sync(true); add.focus();
    });
    file.addEventListener("change", async function() {
      var selected = file.files[0], request = ++generation, before = input.value;
      if (!selected || input.disabled) return;
      importing = true;
      // Register the new draft immediately: a save response must not clear a
      // file selection whose asynchronous read has not completed yet.
      input.value = JSON.stringify({draft: drafts(), importing: request});
      input.dispatchEvent(new Event("input", {bubbles: true}));
      before = input.value;
      try {
        if (selected.size > maxImportBytes) throw invalid();
        var imported = validate(JSON.parse(await selected.text()));
        if (!imported) throw invalid();
        if (!root.isConnected || request !== generation || before !== input.value || input.disabled) return;
        importing = false;
        set(imported, true);
      } catch (_) {
        if (request === generation && root.isConnected) { importing = false; status.textContent = label("import_failed"); }
      }
    });
    input._geographyEditor = {read: read, set: function(next) { set(next, false); }, reset: function() { set(null, false); }};
    set(value || null, false);
    return input;
  }
  window.LixityDossierGeography = {mount: mount, html: html};
  var create = document.getElementById("r-dos-geography-host");
  if (create) mount(create, "r-dos-geography", null);
})();
