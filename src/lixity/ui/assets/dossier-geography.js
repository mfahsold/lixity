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
  function sketch(value) {
    var points = value.features.flatMap(function(feature) { return geometryPoints(feature.geometry); });
    if (!points.length) return "";
    // Place the longitude seam in the largest empty gap, so a local dateline
    // crossing stays local. This flat coordinate sketch is not a projection.
    var longitudes = points.map(function(point) { return (point[0] + 360) % 360; }).sort(function(a, b) { return a - b; });
    var start = longitudes[0], gap = -1;
    longitudes.forEach(function(lon, index) {
      var next = index + 1 < longitudes.length ? longitudes[index + 1] : longitudes[0] + 360;
      if (next - lon > gap) { gap = next - lon; start = next % 360; }
    });
    function longitude(lon) { return ((lon + 360) % 360 - start + 360) % 360; }
    var xs = points.map(function(point) { return longitude(point[0]); }), ys = points.map(function(point) { return point[1]; });
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs), minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
    var spanX = Math.max(maxX - minX, .01), spanY = Math.max(maxY - minY, .01), scale = Math.min(560 / spanX, 250 / spanY);
    function xy(point) { return [(300 + (longitude(point[0]) - (minX + maxX) / 2) * scale).toFixed(2),
      (155 - (point[1] - (minY + maxY) / 2) * scale).toFixed(2)]; }
    var shapes = value.features.map(function(feature, index) {
      var geometry = feature.geometry;
      if (!geometry) return "";
      var title = '<title>' + safe((index + 1) + ". " + feature.properties.label) + '</title>';
      if (geometry.type === "Point") {
        var point = xy(geometry.coordinates);
        return '<g>' + title + '<circle cx="' + point[0] + '" cy="' + point[1] + '" r="5"/><text x="' + (Number(point[0]) + 9) + '" y="' + (Number(point[1]) - 8) + '">' + (index + 1) + '</text></g>';
      }
      var rings = geometry.type === "Polygon" ? geometry.coordinates : [geometry.coordinates];
      var paths = rings.map(function(ring) { return ring.map(function(point, i) { return (i ? "L" : "M") + xy(point).join(" "); }).join(" ") + (geometry.type === "Polygon" ? " Z" : ""); }).join(" ");
      var anchor = xy(geometry.type === "LineString" ? geometry.coordinates[Math.floor(geometry.coordinates.length / 2)] : rings[0][0]);
      return '<g>' + title + '<path class="geography-' + (geometry.type === "Polygon" ? "area" : "route") + '" d="' + paths + '" fill-rule="evenodd"/>' +
        '<text x="' + (Number(anchor[0]) + 9) + '" y="' + (Number(anchor[1]) - 8) + '">' + (index + 1) + '</text></g>';
    }).join("");
    return '<svg class="geography-sketch" viewBox="0 0 600 310" role="img" aria-label="' + safe(label("sketch")) + '"><title>' + safe(label("sketch")) + '</title>' + shapes + '</svg>';
  }
  function html(value) {
    if (!value) return "";
    try { value = validate(value); } catch (_) { return '<p class="ctl-note">' + safe(label("invalid")) + '</p>'; }
    if (!value.features.length) return "";
    return '<section class="dossier-geography"><h4>' + safe(label("title")) + '</h4><p class="ctl-note">' + safe(label("hint")) + '</p>' + sketch(value) +
      '<ol class="geography-feature-list">' + value.features.map(function(feature) {
        var props = feature.properties, geometry = feature.geometry;
        var meta = [label(geometry ? geometry.type : "unknown"), props.time_period, (props.actors || []).join(", "),
          props.transport ? label(props.transport) : "", props.feature_type].filter(Boolean);
        return '<li><strong>' + safe(props.label) + '</strong><p class="ctl-note">' + meta.map(safe).join(" · ") + '</p>' +
          (props.description ? '<p>' + safe(props.description) + '</p>' : '') +
          (props.waypoint_labels && props.waypoint_labels.length ? '<p>' + props.waypoint_labels.map(safe).join(" → ") + '</p>' : '') +
          (geometry ? '<details><summary>' + safe(label("coordinates")) + '</summary><pre>' + safe(coordinateText(geometry)) + '</pre></details>' : '') + '</li>';
      }).join("") + '</ol></section>';
  }
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
