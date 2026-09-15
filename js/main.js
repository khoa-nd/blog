/* ============================================================
   Shared behaviour. Loaded on every page after data.js.
   ============================================================ */
(function () {
  "use strict";

  /* ---------- Mobile nav ---------- */
  function initNav() {
    const toggle = document.querySelector(".nav-toggle");
    const nav = document.getElementById("primary-nav");
    if (!toggle || !nav) return;

    const mq = matchMedia("(max-width: 720px)");
    const sync = function () {
      if (mq.matches) {
        nav.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
      } else {
        nav.hidden = false;
      }
    };
    sync();
    mq.addEventListener("change", sync);

    toggle.addEventListener("click", function () {
      const open = nav.hidden;
      nav.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && mq.matches && !nav.hidden) {
        nav.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  /* ---------- Helpers ---------- */
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "class") node.className = attrs[k];
        else if (k === "text") node.textContent = attrs[k];
        else if (k === "html") node.innerHTML = attrs[k];
        else if (attrs[k] != null) node.setAttribute(k, attrs[k]);
      });
    }
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  /* Deterministic placeholder artwork derived from the project title,
     so each card gets stable, distinct geometry without any image files. */
  function thumbSVG(project) {
    if (project.image) {
      return el("img", { src: project.image, alt: "", loading: "lazy" });
    }
    let seed = 0;
    for (let i = 0; i < project.title.length; i++) seed = (seed * 31 + project.title.charCodeAt(i)) >>> 0;
    const rand = function () {
      seed = (seed * 1103515245 + 12345) >>> 0;
      return seed / 4294967296;
    };
    const c = project.thumb || "#2f5ea8";
    const parts = [];
    const cols = 7, rows = 4;
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const r = rand();
        if (r < 0.42) continue;
        const px = 8 + x * 12.5, py = 8 + y * 14;
        if (r > 0.88) {
          parts.push('<circle cx="' + (px + 5) + '" cy="' + (py + 5.5) + '" r="4.4" fill="' + c + '" opacity="' + (0.25 + r * 0.6).toFixed(2) + '"/>');
        } else {
          parts.push('<rect x="' + px + '" y="' + py + '" width="' + (r > 0.66 ? 20 : 10) + '" height="9" rx="2.5" fill="' + c + '" opacity="' + (0.16 + r * 0.5).toFixed(2) + '"/>');
        }
      }
    }
    const svg = '<svg viewBox="0 0 100 72" preserveAspectRatio="xMidYMid slice" role="img" aria-label="">' +
                '<rect width="100" height="72" fill="' + c + '" opacity="0.06"/>' + parts.join("") + '</svg>';
    const wrap = document.createElement("div");
    wrap.style.cssText = "width:100%;height:100%";
    wrap.innerHTML = svg;
    return wrap.firstChild;
  }

  /* ---------- Project card ----------
     Renders sector (never a client name) plus the architecture / role /
     impact rows. `nda: true` shows an explicit "under NDA" marker, which
     reads as discretion rather than vagueness. */
  function projectCard(p) {
    const thumb = el("div", { class: "project-thumb" }, [thumbSVG(p)]);

    const titleRow = el("div", { class: "project-title-row" }, [
      el("h3", { text: p.title }),
      el("span", { class: "project-year", text: String(p.year) }),
    ]);

    const sectorLine = p.sector
      ? el("p", { class: "project-sector" }, [
          el("span", { text: p.sector }),
          p.nda ? el("span", { class: "nda-badge", text: "under NDA" }) : null,
        ])
      : null;

    function specRow(label, value) {
      if (!value) return null;
      return el("div", { class: "spec-row" }, [
        el("span", { class: "spec-label", text: label }),
        el("span", { class: "spec-value", text: value }),
      ]);
    }

    const specs = el("div", { class: "project-specs" }, [
      specRow("arch", p.arch),
      specRow("role", p.role),
      specRow("impact", p.impact),
    ]);

    const tags = el("div", { class: "tags" },
      (p.stack || []).slice(0, 4).map(function (s) {
        return el("span", { class: "tag", text: s });
      }));

    const body = el("div", { class: "project-body" }, [
      titleRow,
      sectorLine,
      el("p", { class: "project-desc", text: p.desc }),
      specs,
      tags,
    ]);

    /* A "Present" action lives alongside the card rather than inside it:
       a <button> nested in an <a> is invalid HTML and swallows clicks. */
    const present = p.slides && p.slides.length
      ? el("button", {
          class: "present-cta",
          type: "button",
          "data-present": p.title,
          "aria-label": "Present " + p.title,
        }, [
          el("span", { class: "present-cta-icon", "aria-hidden": "true", text: "▶" }),
          el("span", { text: "Present" }),
        ])
      : null;

    const card = el("a", {
      class: "project-card" + (present ? " has-present" : ""),
      href: p.url || "#",
      "data-title": p.title.toLowerCase(),
      "data-desc": (p.desc || "").toLowerCase(),
      "data-category": p.category || "",
      "data-year": String(p.year),
      "data-stack": (p.stack || []).join(" ").toLowerCase(),
    }, [thumb, body]);

    if (!present) return card;

    /* The wrapper carries the filter attributes too, because projects.js
       queries them on the grid's direct children. */
    return el("div", {
      class: "project-card-wrap",
      "data-title": card.getAttribute("data-title"),
      "data-desc": card.getAttribute("data-desc"),
      "data-category": card.getAttribute("data-category"),
      "data-year": card.getAttribute("data-year"),
      "data-stack": card.getAttribute("data-stack"),
    }, [card, present]);
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (m) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m];
    });
  }

  /* ---------- CV download ---------- */
  function initCV() {
    document.querySelectorAll("[data-cv-download]").forEach(function (link) {
      link.setAttribute("href", SITE.cvPath);
      link.setAttribute("download", SITE.cvFileName);
      link.addEventListener("click", function () { toast("Downloading CV…"); });
    });
  }

  let toastTimer;
  function toast(msg) {
    let node = document.querySelector(".toast");
    if (!node) {
      node = el("div", { class: "toast", role: "status", "aria-live": "polite" });
      document.body.appendChild(node);
    }
    node.textContent = msg;
    requestAnimationFrame(function () { node.classList.add("is-visible"); });
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { node.classList.remove("is-visible"); }, 2600);
  }

  /* ---------- Copy email to clipboard ----------
     The button shows the address on hover and confirms on click.
     Falls back to a hidden textarea + execCommand where the async
     Clipboard API is unavailable (non-secure origins, older Safari). */
  function initCopyEmail() {
    const btn = document.getElementById("copy-email");
    if (!btn) return;

    const address = SITE.email;
    btn.setAttribute("data-tip", address);

    let resetTimer;
    function confirm(msg) {
      btn.classList.add("is-copied");
      btn.setAttribute("data-tip", msg);
      clearTimeout(resetTimer);
      resetTimer = setTimeout(function () {
        btn.classList.remove("is-copied");
        btn.setAttribute("data-tip", address);
      }, 1800);
    }

    function fallbackCopy() {
      const ta = document.createElement("textarea");
      ta.value = address;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      let done = false;
      try { done = document.execCommand("copy"); } catch (e) { done = false; }
      document.body.removeChild(ta);
      return done;
    }

    btn.addEventListener("click", function () {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(address).then(
          function () { confirm("Copied!"); },
          function () { confirm(fallbackCopy() ? "Copied!" : address); }
        );
      } else {
        confirm(fallbackCopy() ? "Copied!" : address);
      }
    });
  }

  /* Render a short content string that may contain **bold** spans.
     Everything is escaped first, so the JSON can never inject markup —
     only the bold markers are honoured. */
  function richText(str) {
    return esc(str).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  /* ---------- Shared identity fill-in ---------- */
  function initIdentity() {
    document.querySelectorAll("[data-site]").forEach(function (n) {
      const v = SITE[n.getAttribute("data-site")];
      if (v != null) n.textContent = v;
    });
    /* Fields that may carry **bold** markup, rendered rather than escaped flat. */
    document.querySelectorAll("[data-site-rich]").forEach(function (n) {
      const v = SITE[n.getAttribute("data-site-rich")];
      if (v != null) n.innerHTML = richText(v);
    });
    document.querySelectorAll("[data-site-href]").forEach(function (n) {
      const key = n.getAttribute("data-site-href");
      const v = SITE[key];
      if (!v) return;
      n.setAttribute("href", key === "email" ? "mailto:" + v : v);
    });
    document.querySelectorAll("[data-year-now]").forEach(function (n) {
      n.textContent = String(new Date().getFullYear());
    });
  }

  /* ---------- Book card (used by home + books page) ---------- */
  function bookCard(b) {
    const initials = b.title.split(/\s+/).slice(0, 2).map(function (w) { return w[0]; }).join("");
    return el("article", {
      class: "book-card",
      "data-title": b.title.toLowerCase(),
      "data-author": (b.author || "").toLowerCase(),
      "data-desc": (b.desc || "").toLowerCase(),
      "data-status": b.status,
      "data-tags": (b.tags || []).join(" ").toLowerCase(),
    }, [
      el("div", { class: "book-cover", text: initials }),
      el("div", { class: "book-main" }, [
        el("h3", { class: "book-title", text: b.title }),
        el("p", { class: "book-author", text: b.author + " \u00b7 " + b.year }),
        el("p", { class: "book-desc", text: b.desc }),
        el("div", { class: "tags" }, (b.tags || []).map(function (t) {
          return el("span", { class: "tag", text: t });
        })),
      ]),
      el("div", { class: "book-side" }, [
        el("span", { class: "book-status", "data-status": b.status, text: b.status }),
        b.rating ? el("span", { class: "book-rating", text: "\u2605".repeat(b.rating) + "\u2606".repeat(5 - b.rating) }) : null,
      ]),
    ]);
  }

  /* ---------- Expose ---------- */
  window.Site = { el: el, esc: esc, projectCard: projectCard,
                  bookCard: bookCard, toast: toast };

  document.addEventListener("DOMContentLoaded", function () {
    /* Nav needs no content, so it works even if the JSON fails to load. */
    initNav();

    /* These three read SITE, which arrives from content/site.json. */
    function initContentBound() {
      initIdentity();
      initCV();
      initCopyEmail();
    }
    if (window.ContentReady) {
      window.ContentReady.then(initContentBound)
        .catch(function () { /* content.js already surfaced the error */ });
    } else {
      initContentBound();
    }
  });
})();
