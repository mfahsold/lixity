// Project inspection is explicit and read-only; settled responses are never cached.
(function () {
  "use strict";
  var overview = document.getElementById("project-overview");
  if (!overview || window.LixitySite.readOnly) return;
  var pane = document.getElementById("view-pane-project");
  var body = document.getElementById("project-overview-body");
  var status = document.getElementById("project-overview-status");
  var refresh = document.getElementById("project-overview-refresh");
  var keys = JSON.parse(document.getElementById("project-overview-label-keys").textContent);
  var revision = 0, pending = null;

  function text(key) { return uiLabel(key); }
  function node(tag, className, value) {
    var element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== undefined) element.textContent = value;
    return element;
  }
  function mapped(mapping, value, fallback) {
    return Object.prototype.hasOwnProperty.call(mapping, value) ? mapping[value] : fallback;
  }
  function active() { return pane.classList.contains("active"); }
  function sameContext(form, token) {
    return active() && form.isConnected && document.getElementById("settings-form") === form &&
      form.dataset.projectToken === token;
  }
  function message(key, failed) {
    status.textContent = key ? text(key) : "";
    status.hidden = !key;
    status.className = "ctl-status" + (failed ? " err" : "");
  }
  function clear() { body.replaceChildren(); body.hidden = true; }
  function idle() {
    overview.removeAttribute("aria-busy");
    refresh.disabled = false;
  }
  function invalidate() {
    revision++;
    if (pending) pending.abort();
    pending = null;
    clear(); idle(); message("project_structure_not_checked");
  }
  function validPath(value) { return value === null || typeof value === "string"; }
  function valid(data) {
    if (!data || data.ok !== true || data.schema_version !== "lixity-project-structure/1" ||
        typeof data.root !== "string" || typeof data.has_errors !== "boolean" || typeof data.truncated !== "boolean" ||
        !Array.isArray(data.roles) || !Array.isArray(data.artifacts) || !Array.isArray(data.issues)) return false;
    var roles = new Set();
    if (!data.roles.every(function (role) {
      if (!role || !Object.prototype.hasOwnProperty.call(keys.roles, role.role) || roles.has(role.role) ||
          typeof role.state !== "string" || !validPath(role.path)) return false;
      roles.add(role.role); return true;
    }) || roles.size !== Object.keys(keys.roles).length) return false;
    return data.artifacts.every(function (artifact) {
      return artifact && typeof artifact.name === "string" && typeof artifact.path === "string" &&
        typeof artifact.downloadable === "boolean" && artifact.provenance === "unknown" &&
        (artifact.size_bytes === null || Number.isSafeInteger(artifact.size_bytes) && artifact.size_bytes >= 0);
    }) && data.issues.every(function (issue) {
      return issue && typeof issue.code === "string" && ["error", "warning", "info"].includes(issue.severity) && validPath(issue.path);
    });
  }
  function roleRow(role) {
    var row = node("li", "project-overview-row");
    row.dataset.projectRole = role.role;
    var heading = node("div", "project-overview-row-heading");
    heading.append(node("strong", "", text(keys.roles[role.role])),
      node("span", "project-overview-state", text(mapped(keys.states, role.state, "project_structure_state_unknown"))));
    row.append(heading);
    if (role.path !== null) row.append(node("code", "", role.path));
    if (role.state === "available" && ["manuscript", "research"].includes(role.role)) {
      var button = node("button", "ctl", text("project_structure_open_" + (role.role === "manuscript" ? "manuscript" : "research")));
      button.type = "button";
      if (role.role === "research" && overview.dataset.researchNavigation !== "true") {
        button.disabled = true;
        row.append(node("p", "ctl-note", text("project_structure_research_context")));
      } else {
        button.dataset.switchView = role.role === "manuscript" ? "analysis" : "research";
        if (role.role === "research") button.dataset.projectResearch = "true";
      }
      row.append(button);
    }
    return row;
  }
  function outputRow(artifact, token) {
    var row = node("li", "project-overview-row"), heading = node("div", "project-overview-row-heading");
    heading.append(node("strong", "", artifact.name));
    if (artifact.size_bytes !== null) heading.append(node("span", "project-overview-state",
      new Intl.NumberFormat(document.documentElement.lang || "en").format(artifact.size_bytes) + " B"));
    row.append(heading, node("code", "", artifact.path));
    var name = artifact.name;
    if (artifact.downloadable && name && name !== "." && name !== ".." && !/[\\/\u0000-\u001f\u007f]/.test(name) && artifact.path === "exports/" + name) {
      var link = node("a", "ctl", text("project_structure_open_output"));
      link.href = API.replace(/\/api$/, "") + "/artifact/" + encodeURIComponent(name) + "?project_token=" + encodeURIComponent(token);
      link.target = "_blank"; link.rel = "noopener";
      row.append(link);
    }
    return row;
  }
  function render(data, token) {
    var folder = node("p", "project-overview-root");
    folder.append(node("span", "", text("project_structure_folder")), node("code", "", data.root));
    var columns = node("div", "project-overview-columns"), roles = Object.create(null);
    data.roles.forEach(function (role) { roles[role.role] = role; });
    ["sources", "outputs"].forEach(function (group) {
      var section = node("section", "project-overview-group"), list = node("ul", "project-overview-list");
      section.append(node("h4", "", text("project_structure_" + group)));
      (group === "sources" ? ["manuscript", "research"] : ["outputs", "output_archive"]).forEach(function (role) {
        list.append(roleRow(roles[role]));
      });
      section.append(list);
      if (group === "outputs") {
        if (data.artifacts.length) {
          section.append(node("p", "ctl-note", text("project_structure_provenance_unknown")));
          var outputs = node("ul", "project-overview-list project-overview-artifacts");
          data.artifacts.forEach(function (artifact) { outputs.append(outputRow(artifact, token)); });
          section.append(outputs);
        } else section.append(node("p", "ctl-note", text("project_structure_no_outputs")));
      }
      columns.append(section);
    });
    var submissions = node("ul", "project-overview-list");
    submissions.append(roleRow(roles.submissions));
    var findings = node("section", "project-overview-findings");
    findings.append(node("h4", "", text("project_structure_issues")));
    if (data.issues.length) {
      var issues = node("ul", "project-overview-issues");
      data.issues.forEach(function (issue) {
        var item = node("li", "");
        item.append(node("strong", "", text("project_structure_issue_" + issue.severity)),
          node("span", "", text(mapped(keys.issues, issue.code, "project_structure_issue_unknown"))));
        if (issue.path !== null) item.append(node("code", "", issue.path));
        issues.append(item);
      });
      findings.append(issues);
    } else findings.append(node("p", "ctl-note", text("project_structure_no_issues")));
    if (data.truncated && !data.issues.some(function (issue) { return keys.issues[issue.code] === "project_structure_issue_limited"; })) {
      findings.append(node("p", "ctl-note", text("project_structure_issue_limited")));
    }
    body.replaceChildren(folder, columns, submissions, findings);
    body.hidden = false;
  }
  async function load() {
    if (!active()) return;
    var form = document.getElementById("settings-form"), token = form && form.dataset.projectToken;
    if (!form || !/^[a-f0-9]{64}$/.test(token || "")) {
      invalidate(); message("project_structure_context_unavailable"); return;
    }
    var request = ++revision;
    if (pending) pending.abort();
    var controller = new AbortController(); pending = controller;
    clear(); overview.setAttribute("aria-busy", "true"); refresh.disabled = true;
    message("project_structure_loading");
    try {
      var api = (document.body.dataset.api || "/api").replace(/\/$/, "");
      var response = await fetch(api + "/project-structure?project_token=" + encodeURIComponent(token),
        {method: "GET", credentials: "same-origin", cache: "no-store", signal: controller.signal});
      var data = await response.json();
      if (request !== revision || !sameContext(form, token)) return;
      if (!response.ok || !valid(data)) throw new Error("Project inspection unavailable");
      render(data, token); message("");
    } catch (_) {
      if (request === revision && sameContext(form, token)) { clear(); message("project_structure_failed", true); }
    } finally {
      if (request === revision) {
        pending = null; idle();
        if (!sameContext(form, token)) { clear(); message("project_structure_not_checked"); }
      }
    }
  }
  refresh.addEventListener("click", load);
  document.addEventListener("lixity:viewchange", function () { if (active()) load(); else invalidate(); });
  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-project-research]")) {
      var tab = document.querySelector('#research-tabs [data-rtab="dossiers"]');
      if (tab) tab.click();
    }
  });
})();
