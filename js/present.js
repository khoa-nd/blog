/* ============================================================
   Project presentation viewer.

   Opens a fullscreen <dialog> containing a three-slide deck for a
   project: Overview, Architecture, Key Results. Plain HTML and CSS
   — no slideshow library.

   Slides come from the "slides" array on each project in
   content/projects.json, so decks are content, not code.

   Keyboard:  → / ← / Space  navigate      Esc  close
              Home / End     first / last  F    fullscreen
   ============================================================ */
(function () {
  "use strict";

  let dialog, deck, slides = [], index = 0, titleEl, counterEl, dotsEl;

  /* ---------- building ---------- */

  function el(tag, attrs, children) {
    const n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") n.className = attrs[k];
      else if (k === "text") n.textContent = attrs[k];
      else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }

  /* A simple left-to-right pipeline, drawn as boxes and arrows.
     Deliberately schematic — it should read at a glance from across
     a room, which rules out anything detailed. */
  function pipeline(nodes) {
    const row = el("div", { class: "slide-pipeline" });
    nodes.forEach(function (label, i) {
      row.appendChild(el("div", { class: "pipe-node" }, [
        el("span", { class: "pipe-index", text: String(i + 1).padStart(2, "0") }),
        el("span", { class: "pipe-label", text: label }),
      ]));
      if (i < nodes.length - 1) {
        row.appendChild(el("div", { class: "pipe-arrow", "aria-hidden": "true" }, [
          el("span", { text: "→" }),
        ]));
      }
    });
    return row;
  }

  function buildSlide(s, project) {
    const body = el("div", { class: "slide-body" });

    if (s.lead) body.appendChild(el("p", { class: "slide-lead", text: s.lead }));

    if (s.type === "overview") {
      if (s.points) {
        body.appendChild(el("ul", { class: "slide-list" },
          s.points.map(function (p) { return el("li", { text: p }); })));
      }
      if (s.facts) {
        body.appendChild(el("div", { class: "slide-facts" },
          s.facts.map(function (f) {
            return el("div", { class: "fact" }, [
              el("span", { class: "fact-label", text: f[0] }),
              el("span", { class: "fact-value", text: f[1] }),
            ]);
          })));
      }
    }

    if (s.type === "architecture") {
      if (s.nodes) body.appendChild(pipeline(s.nodes));
      if (s.notes) {
        body.appendChild(el("ul", { class: "slide-list slide-notes" },
          s.notes.map(function (n) { return el("li", { text: n }); })));
      }
    }

    if (s.type === "results") {
      if (s.metrics) {
        body.appendChild(el("div", { class: "slide-metrics" },
          s.metrics.map(function (m) {
            return el("div", { class: "metric" }, [
              el("span", { class: "metric-value", text: m[0] }),
              el("span", { class: "metric-label", text: m[1] }),
            ]);
          })));
      }
      if (s.points) {
        body.appendChild(el("ul", { class: "slide-list" },
          s.points.map(function (p) { return el("li", { text: p }); })));
      }
    }

    return el("section", { class: "slide", "data-type": s.type, "aria-hidden": "true" }, [
      el("header", { class: "slide-head" }, [
        el("span", { class: "slide-kicker", text: project.title }),
        el("h2", { text: s.title }),
      ]),
      body,
    ]);
  }

  /* ---------- dialog shell ---------- */

  function ensureDialog() {
    if (dialog) return dialog;

    titleEl   = el("span", { class: "present-title" });
    counterEl = el("span", { class: "present-counter" });
    dotsEl    = el("div", { class: "present-dots" });
    deck      = el("div", { class: "present-deck" });

    const prev = el("button", { class: "present-nav", type: "button",
                                "aria-label": "Previous slide", "data-dir": "-1", text: "‹" });
    const next = el("button", { class: "present-nav", type: "button",
                                "aria-label": "Next slide", "data-dir": "1", text: "›" });
    prev.addEventListener("click", function () { go(index - 1); });
    next.addEventListener("click", function () { go(index + 1); });

    const close = el("button", { class: "present-close", type: "button",
                                 "aria-label": "Close presentation", text: "✕" });
    close.addEventListener("click", function () { dialog.close(); });

    const fs = el("button", { class: "present-fs", type: "button",
                              "aria-label": "Toggle fullscreen", text: "⛶" });
    fs.addEventListener("click", toggleFullscreen);

    dialog = el("dialog", { class: "present", "aria-label": "Project presentation" }, [
      el("div", { class: "present-bar" }, [titleEl, counterEl, fs, close]),
      el("div", { class: "present-stage" }, [prev, deck, next]),
      dotsEl,
    ]);

    dialog.addEventListener("keydown", onKey);
    dialog.addEventListener("close", function () {
      document.documentElement.style.overflow = "";
    });
    /* Clicking the backdrop closes, but clicks inside must not. */
    dialog.addEventListener("click", function (e) {
      if (e.target === dialog) dialog.close();
    });

    document.body.appendChild(dialog);
    return dialog;
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) {
      document.exitFullscreen && document.exitFullscreen();
    } else if (dialog.requestFullscreen) {
      dialog.requestFullscreen().catch(function () { /* user gesture required */ });
    }
  }

  function onKey(e) {
    switch (e.key) {
      case "ArrowRight": case " ": case "PageDown":
        e.preventDefault(); go(index + 1); break;
      case "ArrowLeft": case "PageUp":
        e.preventDefault(); go(index - 1); break;
      case "Home": e.preventDefault(); go(0); break;
      case "End":  e.preventDefault(); go(slides.length - 1); break;
      case "f": case "F": toggleFullscreen(); break;
      /* Esc is handled natively by <dialog>. */
    }
  }

  function go(i) {
    if (i < 0 || i >= slides.length) return;
    index = i;
    slides.forEach(function (s, n) {
      const on = n === index;
      s.classList.toggle("is-active", on);
      s.setAttribute("aria-hidden", String(!on));
    });
    counterEl.textContent = (index + 1) + " / " + slides.length;
    Array.prototype.forEach.call(dotsEl.children, function (d, n) {
      d.setAttribute("aria-current", String(n === index));
    });
    deck.scrollTop = 0;
  }

  /* ---------- opening ---------- */

  function open(project) {
    ensureDialog();
    const data = (project.slides && project.slides.length)
      ? project.slides
      : [{ type: "overview", title: "Project Overview", lead: project.desc }];

    deck.textContent = "";
    dotsEl.textContent = "";
    slides = data.map(function (s) {
      const node = buildSlide(s, project);
      deck.appendChild(node);
      return node;
    });
    data.forEach(function (s, i) {
      const dot = el("button", { class: "present-dot", type: "button",
                                 title: s.title, "aria-label": "Go to " + s.title });
      dot.addEventListener("click", function () { go(i); });
      dotsEl.appendChild(dot);
    });

    titleEl.textContent = project.title;
    index = 0;
    go(0);

    document.documentElement.style.overflow = "hidden";
    dialog.showModal();
    dialog.focus();
  }

  /* ---------- wiring ---------- */

  function init() {
    /* Delegated so it also covers cards the gallery re-renders on filter. */
    document.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-present]");
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      const title = btn.getAttribute("data-present");
      const project = (window.PROJECTS || []).find(function (p) { return p.title === title; });
      if (project) open(project);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
