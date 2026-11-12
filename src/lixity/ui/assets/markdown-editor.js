// Enhanced Markdown Editor for Dossiers and Authored Notes
// Provides formatting toolbar, keyboard shortcuts, smart list continuation,
// auto-closing pairs, and undo history while preserving the native textarea.
(function () {
  "use strict";

  function wrapSelection(textarea, before, after) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var value = textarea.value;
    var selected = value.slice(start, end);

    var replacement = before + selected + after;
    textarea.value = value.slice(0, start) + replacement + value.slice(end);

    // If no text was selected, place cursor between delimiters; otherwise select the wrapped text
    if (start === end) {
      textarea.selectionStart = textarea.selectionEnd = start + before.length;
    } else {
      textarea.selectionStart = start + before.length;
      textarea.selectionEnd = end + before.length;
    }
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.focus({preventScroll: true});
  }

  function prefixLines(textarea, prefix) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var value = textarea.value;

    var lineStart = value.lastIndexOf("\n", start - 1) + 1;
    var lineEnd = value.indexOf("\n", end);
    if (lineEnd === -1) lineEnd = value.length;

    var lines = value.slice(lineStart, lineEnd).split("\n");
    var modified = lines.map(function (line) {
      if (line.startsWith(prefix)) return line.slice(prefix.length);
      return prefix + line;
    }).join("\n");

    textarea.value = value.slice(0, lineStart) + modified + value.slice(lineEnd);
    textarea.selectionStart = lineStart;
    textarea.selectionEnd = lineStart + modified.length;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.focus({preventScroll: true});
  }

  function countWords(str) {
    var match = str.trim().match(/\S+/g);
    return match ? match.length : 0;
  }

  function label(key, fallback) {
    var translated = typeof uiLabel === "function" ? uiLabel("editor_" + key.replace(/-/g, "_")) : "";
    return translated && translated.indexOf("editor_") !== 0 ? translated : fallback;
  }

  function mount(textarea, options) {
    if (!textarea || textarea.__lixityEditor) return textarea.__lixityEditor;
    options = options || {};

    var wrap = document.createElement("div");
    wrap.className = "markdown-editor-wrap";
    textarea.parentNode.insertBefore(wrap, textarea);
    wrap.appendChild(textarea);
    textarea.classList.add("markdown-editor-area");

    // Toolbar
    var toolbar = document.createElement("div");
    toolbar.className = "markdown-editor-toolbar";
    toolbar.setAttribute("role", "toolbar");
    toolbar.setAttribute("aria-label", label("formatting", "Markdown formatting"));

    var tools = [
      { id: "bold", label: "Bold (Ctrl+B)", icon: "bold", action: function () { wrapSelection(textarea, "**", "**"); } },
      { id: "italic", label: "Italic (Ctrl+I)", icon: "italic", action: function () { wrapSelection(textarea, "*", "*"); } },
      { id: "heading", label: "Heading (Ctrl+H)", icon: "heading", action: function () { prefixLines(textarea, "### "); } },
      { id: "link", label: "Link (Ctrl+K)", icon: "link", action: function () { wrapSelection(textarea, "[", "](https://)"); } },
      { id: "wikilink", label: "Wikilink", icon: "book-open", action: function () { wrapSelection(textarea, "[[", "]]"); } },
      { id: "code", label: "Code", icon: "code", action: function () {
        var start = textarea.selectionStart, end = textarea.selectionEnd;
        if (textarea.value.slice(start, end).includes("\n")) {
          wrapSelection(textarea, "```\n", "\n```");
        } else {
          wrapSelection(textarea, "`", "`");
        }
      }},
      { id: "math", label: "Math ($)", icon: "sigma", action: function () { wrapSelection(textarea, "$", "$"); } },
      { id: "bullet-list", label: "Bullet list", icon: "list", action: function () { prefixLines(textarea, "- "); } },
      { id: "numbered-list", label: "Numbered list", icon: "list-ordered", action: function () { prefixLines(textarea, "1. "); } },
      { id: "task-list", label: "Task list", icon: "check-square", action: function () { prefixLines(textarea, "- [ ] "); } },
      { id: "callout", label: "Callout", icon: "info", action: function () { prefixLines(textarea, "> [!NOTE]\n> "); } }
    ];

    var components = window.LixityComponents;
    if (components && typeof components.html === "function" && typeof components.mount === "function") {
      var html = components.html;
      components.mount(
        toolbar,
        tools.map(function (tool) {
          var shortcut = tool.label.match(/ \(Ctrl\+[A-Z]\)/);
          var localized = label(tool.id, tool.label.replace(/ \(.*\)$/, "")) + (shortcut ? shortcut[0] : "");
          var iconMarkup = window.LixityIcons ? window.LixityIcons.svg(tool.icon, { size: 14 }) : localized.slice(0, 1);
          return html`
            <button
              key=${tool.id}
              type="button"
              class="editor-tool-btn"
              title=${localized}
              aria-label=${localized}
              onClick=${function (e) { e.preventDefault(); tool.action(); }}
              dangerouslySetInnerHTML=${{ __html: iconMarkup }}
            ></button>
          `;
        })
      );
    } else {
      tools.forEach(function (tool) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "editor-tool-btn";
        var shortcut = tool.label.match(/ \(Ctrl\+[A-Z]\)/);
        tool.label = label(tool.id, tool.label.replace(/ \(.*\)$/, "")) + (shortcut ? shortcut[0] : "");
        btn.title = tool.label;
        btn.setAttribute("aria-label", tool.label);
        if (window.LixityIcons) {
          btn.innerHTML = window.LixityIcons.svg(tool.icon, { size: 14 });
        } else {
          btn.textContent = tool.label.slice(0, 1);
        }
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          tool.action();
        });
        toolbar.appendChild(btn);
      });
    }

    wrap.insertBefore(toolbar, textarea);

    // Footer with stats
    var footer = document.createElement("div");
    footer.className = "markdown-editor-footer";
    var stats = document.createElement("span");
    stats.className = "editor-stats";
    footer.appendChild(stats);
    wrap.appendChild(footer);

    function updateStats() {
      var text = textarea.value || "";
      var words = countWords(text);
      var chars = text.length;
      stats.textContent = label("stats", "{words} words · {chars} chars")
        .replace("{words}", String(words)).replace("{chars}", String(chars));
    }
    textarea.addEventListener("input", updateStats);
    updateStats();

    // Auto-closing brackets and smart list continuation
    var PAIRS = { "(": ")", "[": "]", "{": "}", "\"": "\"", "'": "'", "`": "`", "$": "$" };
    textarea.addEventListener("keydown", function (e) {
      var start = textarea.selectionStart;
      var end = textarea.selectionEnd;
      var value = textarea.value;

      // Shortcuts: Ctrl/Cmd + B, I, K, H
      if ((e.ctrlKey || e.metaKey) && !e.altKey) {
        var key = e.key.toLowerCase();
        if (key === "b") { e.preventDefault(); wrapSelection(textarea, "**", "**"); return; }
        if (key === "i") { e.preventDefault(); wrapSelection(textarea, "*", "*"); return; }
        if (key === "k") { e.preventDefault(); wrapSelection(textarea, "[", "](https://)"); return; }
        if (key === "h") { e.preventDefault(); prefixLines(textarea, "### "); return; }
      }

      // Tab remains native focus navigation, including inside modal dialogs.

      // Auto-closing bracket wrapping or pair insertion
      if (PAIRS[e.key] && !e.ctrlKey && !e.metaKey && !e.altKey) {
        var closer = PAIRS[e.key];
        if (start !== end) {
          e.preventDefault();
          wrapSelection(textarea, e.key, closer);
          return;
        } else if (e.key === closer && value[start] === closer) {
          // Skip over closing char if already typed
          e.preventDefault();
          textarea.selectionStart = textarea.selectionEnd = start + 1;
          return;
        }
      }

      // Smart list continuation on Enter
      if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
        var lineStart = value.lastIndexOf("\n", start - 1) + 1;
        var currentLine = value.slice(lineStart, start);
        var match = currentLine.match(/^(\s*)(- \[[ xX]\]|[-*+]|\d+\.)\s+/);
        if (match) {
          var prefix = match[0];
          // If the list item is empty (user hit Enter on empty item), exit list
          if (currentLine.trim() === match[0].trim()) {
            e.preventDefault();
            textarea.value = value.slice(0, lineStart) + value.slice(start);
            textarea.selectionStart = textarea.selectionEnd = lineStart;
            textarea.dispatchEvent(new Event("input", { bubbles: true }));
            return;
          }
          e.preventDefault();
          var nextPrefix = prefix;
          var numMatch = prefix.match(/^(\s*)(\d+)\.\s+/);
          if (numMatch) {
            nextPrefix = numMatch[1] + (Number(numMatch[2]) + 1) + ". ";
          } else if (prefix.includes("- [")) {
            nextPrefix = match[1] + "- [ ] ";
          }
          textarea.value = value.slice(0, start) + "\n" + nextPrefix + value.slice(end);
          textarea.selectionStart = textarea.selectionEnd = start + 1 + nextPrefix.length;
          textarea.dispatchEvent(new Event("input", { bubbles: true }));
          return;
        }
      }
    });

    var editor = {
      wrap: wrap,
      textarea: textarea,
      read: function () { return textarea.value; },
      write: function (val) { textarea.value = val; updateStats(); },
      focus: function () { textarea.focus({preventScroll: true}); }
    };
    textarea.__lixityEditor = editor;
    return editor;
  }

  window.LixityMarkdownEditor = {
    mount: mount
  };
})();
