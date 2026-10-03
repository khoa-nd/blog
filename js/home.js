/* ============================================================
   Home page rendering.
   ============================================================ */
(function () {
  "use strict";

  /* Content arrives asynchronously from content/*.json, so the render
     pass waits on it. ContentReady is defined in js/content.js. */

  /* Highlight card. Mirrored in tools/build.js — keep the two identical. */
  function highlightArt(kind) {
    if (kind !== "graph") return "";
    const L = [[60, 120, 180], [36, 92, 148, 204], [60, 120, 180], [90, 150]];
    const Y = [14, 52, 90, 128];
    const E = [[0,0,0],[0,0,1],[0,1,1],[0,1,2],[0,2,2],[0,2,3],[1,0,0],[1,1,0],[1,1,1],[1,2,1],[1,2,2],[1,3,2],[2,0,0],[2,1,0],[2,1,1],[2,2,1]];
    const HOT = ["0-1-1", "1-1-1", "2-1-1"], ON = ["0-1", "1-1", "2-1", "3-1"];
    const edges = E.map(function (e) {
      const x1 = L[e[0]][e[1]], x2 = L[e[0] + 1][e[2]], y1 = Y[e[0]] + 14, y2 = Y[e[0] + 1], ym = (y1 + y2) / 2;
      const hot = HOT.indexOf(e.join("-")) !== -1 ? " hot l" + e[0] : "";
      return '<path class="hl-edge' + hot + '" d="M' + x1 + "," + y1 + " C" + x1 + "," + ym + " " + x2 + "," + ym + " " + x2 + "," + y2 + '"/>';
    }).join("");
    const nodes = L.map(function (row, r) {
      return row.map(function (x, c) {
        const on = ON.indexOf(r + "-" + c) !== -1 ? " on" : "";
        return '<rect class="hl-node l' + r + on + '" x="' + (x - 20) + '" y="' + Y[r] + '" width="40" height="14" rx="3"/>';
      }).join("");
    }).join("");
    return '<svg viewBox="0 0 240 156" role="img" aria-label="">' + edges + nodes + "</svg>";
  }
  function highlightCard(h, i, esc) {
    const art = highlightArt(h.art);
    const meta = [h.kicker, h.date].filter(Boolean).map(esc).join(" · ");
    return '<a class="highlight-card' + (i === 0 ? " is-featured" : "") + (art ? "" : " no-art") + '" href="' + esc(h.url) + '">' +
      (art ? '<div class="highlight-art" aria-hidden="true">' + art + "</div>" : "") +
      '<div class="highlight-body">' +
      '<p class="highlight-kicker">' + (h.badge ? '<span class="highlight-badge">' + esc(h.badge) + "</span>" : "") + "<span>" + meta + "</span></p>" +
      '<h3 class="highlight-title">' + esc(h.title) + "</h3>" +
      (h.desc ? '<p class="highlight-desc">' + esc(h.desc) + "</p>" : "") +
      '<span class="highlight-cta">' + esc(h.cta || "Read more") +
      ' <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>' +
      "</div></a>";
  }

  function renderHome() {
  const el = Site.el;

  /* ---------- Highlights (content/highlights.json) ----------
     The first entry is featured full-width; later ones flow into a grid. */
  const hlList = document.getElementById("highlight-list");
  if (hlList && typeof HIGHLIGHTS !== "undefined") {
    hlList.innerHTML = HIGHLIGHTS.map(function (h, i) { return highlightCard(h, i, Site.esc); }).join("");
    const hlSection = document.getElementById("highlights");
    if (hlSection) hlSection.hidden = HIGHLIGHTS.length === 0;
  }

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
            x.desc ? el("p", { class: "xp-desc", text: x.desc }) : null,
            x.tags && x.tags.length ? el("div", { class: "tags" }, x.tags.map(function (t) {
              return el("span", { class: "tag", text: t });
            })) : null,
          ].filter(Boolean)),
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
