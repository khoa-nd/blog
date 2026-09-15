/* ============================================================
   Theme switcher — LOCALHOST ONLY.

   A development aid for comparing themes side by side. It exits
   immediately on any non-local host, so shipping this file to
   production is harmless: the widget simply never appears.

   Remove the <script> tag from the three HTML files when you no
   longer want it, or leave it — it costs nothing in production.
   ============================================================ */
(function () {
  "use strict";

  const DEV_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "::1", ""];
  const isDev = DEV_HOSTS.indexOf(location.hostname) !== -1 ||
                location.protocol === "file:" ||
                /\.local$/.test(location.hostname);
  if (!isDev) return;

  const THEMES = [
    { id: "classic",    label: "Classic",    hint: "Warm off-white, rounded, soft shadows, slate blue" },
    { id: "blueprint",  label: "Blueprint",  hint: "Technical drawing — mono labels, hairlines, electric blue" },
    { id: "manuscript", label: "Manuscript", hint: "Editorial — cream paper, serif headings, burnt ochre" },
    { id: "terminal",   label: "Terminal",   hint: "Dark, all-mono, phosphor green, zero rounding" },
  ];
  const STORAGE_KEY = "dev:theme";

  /* The <link> the themes swap through. */
  const link = document.querySelector('link[href*="css/themes/"]');
  if (!link) return;

  function currentId() {
    const m = link.getAttribute("href").match(/themes\/([a-z0-9-]+)\.css/);
    return m ? m[1] : THEMES[0].id;
  }

  function apply(id) {
    /* Resolve relative to the existing href so this works from any page depth. */
    link.setAttribute("href", link.getAttribute("href").replace(/[a-z0-9-]+\.css$/, id + ".css"));
    try { localStorage.setItem(STORAGE_KEY, id); } catch (e) { /* private mode */ }
    render();
  }

  /* Restore the last choice before the widget is built, so the page
     does not flash the default theme on every navigation. */
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && saved !== currentId() && THEMES.some(function (t) { return t.id === saved; })) {
      link.setAttribute("href", link.getAttribute("href").replace(/[a-z0-9-]+\.css$/, saved + ".css"));
    }
  } catch (e) {}

  let panel;
  function render() {
    if (!panel) return;
    const active = currentId();
    panel.querySelectorAll("[data-theme-id]").forEach(function (btn) {
      const on = btn.getAttribute("data-theme-id") === active;
      btn.setAttribute("aria-pressed", String(on));
    });
  }

  function build() {
    panel = document.createElement("div");
    panel.className = "devbar";
    panel.setAttribute("role", "group");
    panel.setAttribute("aria-label", "Theme switcher (development only)");

    const tag = document.createElement("span");
    tag.className = "devbar-tag";
    tag.textContent = "DEV";
    panel.appendChild(tag);

    THEMES.forEach(function (t) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "devbar-btn";
      btn.textContent = t.label;
      btn.title = t.hint;
      btn.setAttribute("data-theme-id", t.id);
      btn.addEventListener("click", function () { apply(t.id); });
      panel.appendChild(btn);
    });

    const hide = document.createElement("button");
    hide.type = "button";
    hide.className = "devbar-hide";
    hide.textContent = "×";
    hide.title = "Hide (press T to bring it back)";
    hide.setAttribute("aria-label", "Hide theme switcher");
    hide.addEventListener("click", function () { panel.hidden = true; });
    panel.appendChild(hide);

    document.body.appendChild(panel);
    render();
  }

  /* T toggles the bar; handy when it covers something you want to see. */
  document.addEventListener("keydown", function (e) {
    if (e.key !== "t" && e.key !== "T") return;
    const el = e.target;
    if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (panel) panel.hidden = !panel.hidden;
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();
