/* ============================================================
   Projects gallery: search, filter, sort, density toggle.
   Filter state lives in the URL so a filtered view is linkable.
   ============================================================ */
(function () {
  "use strict";
  const el = Site.el;

  const grid    = document.getElementById("gallery");
  const count   = document.getElementById("result-count");
  const fSearch = document.getElementById("f-search");
  const fCat    = document.getElementById("f-category");
  const fYear   = document.getElementById("f-year");
  const fSort   = document.getElementById("f-sort");
  if (!grid) return;

  /* ---------- Populate filter options from the data ---------- */
  const categories = [...new Set(PROJECTS.map(function (p) { return p.category; }))].sort();
  categories.forEach(function (c) { fCat.appendChild(el("option", { value: c, text: c })); });

  const years = [...new Set(PROJECTS.map(function (p) { return p.year; }))].sort(function (a, b) { return b - a; });
  years.forEach(function (y) { fYear.appendChild(el("option", { value: String(y), text: String(y) })); });

  /* ---------- Restore state from the URL ---------- */
  const params = new URLSearchParams(location.search);
  if (params.get("q"))    fSearch.value = params.get("q");
  if (params.get("cat"))  fCat.value    = params.get("cat");
  if (params.get("year")) fYear.value   = params.get("year");
  if (params.get("sort")) fSort.value   = params.get("sort");
  let view = params.get("view") === "compact" ? "compact" : "detailed";

  function syncURL() {
    const p = new URLSearchParams();
    if (fSearch.value.trim()) p.set("q", fSearch.value.trim());
    if (fCat.value)  p.set("cat", fCat.value);
    if (fYear.value) p.set("year", fYear.value);
    if (fSort.value !== "year-desc") p.set("sort", fSort.value);
    if (view === "compact") p.set("view", "compact");
    const qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }

  /* ---------- Render ---------- */
  function render() {
    const q = fSearch.value.trim().toLowerCase();
    const cat = fCat.value;
    const year = fYear.value;

    let list = PROJECTS.filter(function (p) {
      if (cat && p.category !== cat) return false;
      if (year && String(p.year) !== year) return false;
      if (!q) return true;
      const hay = [p.title, p.desc, p.category, p.sector,
                   p.arch, p.role, p.impact, (p.stack || []).join(" ")]
        .join(" ").toLowerCase();
      return hay.includes(q);
    });

    const [key, dir] = fSort.value.split("-");
    list.sort(function (a, b) {
      let cmp;
      if (key === "year") cmp = a.year - b.year;
      else cmp = a.title.localeCompare(b.title);
      return dir === "desc" ? -cmp : cmp;
    });

    grid.textContent = "";
    grid.classList.toggle("is-compact", view === "compact");

    if (!list.length) {
      grid.appendChild(
        el("div", { class: "empty-state" }, [
          el("p", { text: "No projects match those filters." }),
          el("p", { text: "Try clearing the search or widening the category." }),
        ])
      );
    } else {
      list.forEach(function (p) { grid.appendChild(Site.projectCard(p)); });
    }

    count.textContent = list.length + " of " + PROJECTS.length + " project" +
                        (PROJECTS.length === 1 ? "" : "s");
    syncURL();
  }

  /* ---------- Wiring ---------- */
  let debounce;
  fSearch.addEventListener("input", function () {
    clearTimeout(debounce);
    debounce = setTimeout(render, 120);
  });
  [fCat, fYear, fSort].forEach(function (n) { n.addEventListener("change", render); });

  document.querySelectorAll(".view-switch button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      view = btn.getAttribute("data-view");
      document.querySelectorAll(".view-switch button").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      render();
    });
  });

  /* Reflect a restored compact view in the toggle before first render. */
  document.querySelectorAll(".view-switch button").forEach(function (b) {
    b.setAttribute("aria-pressed", String(b.getAttribute("data-view") === view));
  });

  render();
})();
