/* ============================================================
   Home page rendering.
   ============================================================ */
(function () {
  "use strict";

  /* Content arrives asynchronously from content/*.json, so the render
     pass waits on it. ContentReady is defined in js/content.js. */
  function renderHome() {
  const el = Site.el;

  /* ---------- Skills matrix (Work section) ----------
     Groups render as labelled rows of icon chips. A skill with no mark in
     js/icons.js degrades to a text-only chip, so the data can name anything. */
  const matrix = document.getElementById("skill-matrix");
  if (matrix && typeof SKILL_GROUPS !== "undefined") {
    /* The build step prerenders this markup for crawlers; clear it before
       re-rendering or every entry would appear twice. */
    matrix.textContent = "";
    SKILL_GROUPS.forEach(function (group) {
      const chips = group.items.map(function (name) {
        const icon = skillIcon(name);
        const chip = el("span", {
          class: "skill-chip" + (icon ? "" : " is-textonly"),
          title: name,
        }, [icon, el("span", { class: "skill-name", text: name })]);
        return chip;
      });

      matrix.appendChild(
        el("div", { class: "skill-group" }, [
          el("h3", { class: "skill-group-title", text: group.title }),
          el("div", { class: "skill-chips" }, chips),
        ])
      );
    });
  }

  /* ---------- Experience ---------- */
  const xpList = document.getElementById("experience-list");
  if (xpList) {
    xpList.textContent = "";
    EXPERIENCE.forEach(function (x) {
      xpList.appendChild(
        el("article", { class: "xp-item" }, [
          el("div", { class: "xp-period", text: x.period }),
          el("div", {}, [
            el("h3", { class: "xp-role", text: x.role }),
            el("p", { class: "xp-company", html: "<b>" + Site.esc(x.company) + "</b>" }),
            el("p", { class: "xp-desc", text: x.desc }),
            el("div", { class: "tags" }, x.tags.map(function (t) {
              return el("span", { class: "tag", text: t });
            })),
          ]),
        ])
      );
    });
  }

  /* ---------- Books preview: 3 most relevant ---------- */
  const booksPreview = document.getElementById("books-preview");
  if (booksPreview) {
    booksPreview.textContent = "";
    const order = { reading: 0, finished: 1, queued: 2 };
    BOOKS.slice()
      .sort(function (a, b) { return (order[a.status] ?? 3) - (order[b.status] ?? 3); })
      .slice(0, 3)
      .forEach(function (b) { booksPreview.appendChild(Site.bookCard(b)); });
  }

  /* ---------- Hobby skeleton cards ---------- */
  const hobbyGrid = document.getElementById("hobby-grid");
  if (hobbyGrid) {
    hobbyGrid.textContent = "";
    HOBBIES.forEach(function (h) {
      hobbyGrid.appendChild(
        el("article", { class: "hobby-card" }, [
          el("div", { class: "hobby-icon", text: h.icon }),
          el("h3", { text: h.title }),
          el("p", { text: h.desc }),
          el("span", { class: "hobby-status", "data-status": h.status, text: h.status }),
        ])
      );
    });
  }

  }

  if (window.ContentReady) {
    window.ContentReady.then(renderHome).catch(function () { /* banner already shown */ });
  } else {
    renderHome();
  }
})();
