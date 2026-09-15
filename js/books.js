/* ============================================================
   Reading list: search, status filter, sort.
   ============================================================ */
(function () {
  "use strict";

  /* Content arrives asynchronously from content/*.json, so the render
     pass waits on it. ContentReady is defined in js/content.js. */
  function renderBooks() {
  const el = Site.el;

  const list   = document.getElementById("book-list");
  const count  = document.getElementById("b-count");
  const search = document.getElementById("b-search");
  const status = document.getElementById("b-status");
  const sort   = document.getElementById("b-sort");
  if (!list) return;

  const STATUS_ORDER = { reading: 0, finished: 1, queued: 2 };

  function render() {
    const q = search.value.trim().toLowerCase();
    const st = status.value;

    let items = BOOKS.filter(function (b) {
      if (st && b.status !== st) return false;
      if (!q) return true;
      const hay = [b.title, b.author, b.desc, (b.tags || []).join(" ")].join(" ").toLowerCase();
      return hay.includes(q);
    });

    items.sort(function (a, b) {
      switch (sort.value) {
        case "title-asc":   return a.title.localeCompare(b.title);
        case "year-desc":   return b.year - a.year;
        case "rating-desc": return (b.rating || 0) - (a.rating || 0);
        default:
          return (STATUS_ORDER[a.status] ?? 3) - (STATUS_ORDER[b.status] ?? 3) ||
                 a.title.localeCompare(b.title);
      }
    });

    list.textContent = "";
    if (!items.length) {
      list.appendChild(
        el("div", { class: "empty-state" }, [
          el("p", { text: "No books match that." }),
          el("p", { text: "Try a different search term or status." }),
        ])
      );
    } else {
      items.forEach(function (b) { list.appendChild(Site.bookCard(b)); });
    }

    count.textContent = items.length + " of " + BOOKS.length + " book" +
                        (BOOKS.length === 1 ? "" : "s");
  }

  let debounce;
  search.addEventListener("input", function () {
    clearTimeout(debounce);
    debounce = setTimeout(render, 120);
  });
  [status, sort].forEach(function (n) { n.addEventListener("change", render); });

  render();
  }

  if (window.ContentReady) {
    window.ContentReady.then(renderBooks).catch(function () { /* banner already shown */ });
  } else {
    renderBooks();
  }
})();
