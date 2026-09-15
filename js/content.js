/* ============================================================
   Content loader.

   Reads the JSON files in content/ and exposes them as the same
   globals the page scripts already use (SITE, PROJECTS, ...).

   Why JSON rather than a .js file: JSON is far less punishing to
   hand-edit. A trailing comma or a missing quote is flagged by
   every editor, and cannot take the whole page down the way a
   syntax error in a script tag does.

   There is no build step. Edit a file in content/, refresh.
   ============================================================ */
(function () {
  "use strict";

  const FILES = {
    SITE:         "site",
    SKILL_GROUPS: "skills",
    PROJECTS:     "projects",
    EXPERIENCE:   "experience",
    BOOKS:        "books",
    HOBBIES:      "side-projects",
  };

  /* Pages live at the site root, so content/ is always one level down.
     Relative on purpose: works at a domain root and under /repo-name/. */
  const BASE = "content/";

  function fail(message, detail) {
    console.error("[content] " + message, detail || "");
    const banner = document.createElement("div");
    banner.setAttribute("role", "alert");
    banner.style.cssText =
      "position:fixed;left:0;right:0;top:0;z-index:9999;padding:14px 18px;" +
      "background:#8c1d18;color:#fff;font:13px/1.5 ui-monospace,Menlo,monospace";
    banner.textContent = "Content failed to load — " + message +
      (detail ? " (" + detail + ")" : "");
    (document.body || document.documentElement).appendChild(banner);
  }

  function loadAll() {
    const names = Object.keys(FILES);
    return Promise.all(names.map(function (key) {
      const url = BASE + FILES[key] + ".json";
      return fetch(url)
        .then(function (res) {
          if (!res.ok) throw new Error(res.status + " " + res.statusText);
          return res.text();
        })
        .then(function (text) {
          try {
            return JSON.parse(text);
          } catch (e) {
            /* Point at the file, since that is what the author must fix. */
            throw new Error("invalid JSON in " + url + " — " + e.message);
          }
        });
    })).then(function (results) {
      names.forEach(function (key, i) { window[key] = results[i]; });
    });
  }

  /* Page scripts run against the globals, so they wait on this promise. */
  window.ContentReady = loadAll().catch(function (err) {
    /* file:// blocks fetch in every browser; say so plainly rather than
       leaving a blank page and a CORS message in the console. */
    if (location.protocol === "file:") {
      fail("open the site over http, not file://",
           "run: python3 -m http.server 8000");
    } else {
      fail(err.message);
    }
    throw err;
  });
})();
