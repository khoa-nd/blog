#!/usr/bin/env node
/* ============================================================
   Prerender content/*.json into the HTML files.

   Run:  npm run build   (a pre-commit hook does this for you)

   Why: the page scripts render from JSON at runtime, which leaves
   the HTML source empty. Crawlers that do not execute JS — and
   every social-media link preview — would see nothing. This bakes
   the rendered markup into the files so the content is in the
   source, while the client scripts still work exactly as before.

   Each managed region is delimited by comment markers. Everything
   between them is regenerated; everything outside is left alone,
   so hand edits elsewhere in the HTML are safe.
   ============================================================ */
"use strict";

const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");

const read = (n) => JSON.parse(fs.readFileSync(path.join(ROOT, "content", n + ".json"), "utf8"));
const SITE = read("site");
const SKILLS = read("skills");
const PROJECTS = read("projects");
const EXPERIENCE = read("experience");
const BOOKS = read("books");
const SIDE = read("side-projects");

const SITE_URL = (SITE.url || "https://nguyendangkhoa.info").replace(/\/$/, "");

/* ---------- helpers ---------- */
const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const rich = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
const plain = (s) => String(s == null ? "" : s).replace(/\*\*/g, "");

/* Mirrors thumbSVG() in js/main.js so prerendered and client-rendered
   cards show identical artwork. */
function thumbSVG(p) {
  if (p.image) return `<img src="${esc(p.image)}" alt="" loading="lazy">`;
  let seed = 0;
  for (let i = 0; i < p.title.length; i++) seed = (seed * 31 + p.title.charCodeAt(i)) >>> 0;
  const rand = () => { seed = (seed * 1103515245 + 12345) >>> 0; return seed / 4294967296; };
  const c = p.thumb || "#2f5ea8";
  const parts = [];
  for (let y = 0; y < 4; y++) {
    for (let x = 0; x < 7; x++) {
      const r = rand();
      if (r < 0.42) continue;
      const px = 8 + x * 12.5, py = 8 + y * 14;
      if (r > 0.88) {
        parts.push(`<circle cx="${px + 5}" cy="${py + 5.5}" r="4.4" fill="${c}" opacity="${(0.25 + r * 0.6).toFixed(2)}"/>`);
      } else {
        parts.push(`<rect x="${px}" y="${py}" width="${r > 0.66 ? 20 : 10}" height="9" rx="2.5" fill="${c}" opacity="${(0.16 + r * 0.5).toFixed(2)}"/>`);
      }
    }
  }
  return `<svg viewBox="0 0 100 72" preserveAspectRatio="xMidYMid slice" role="img" aria-label=""><rect width="100" height="72" fill="${c}" opacity="0.06"/>${parts.join("")}</svg>`;
}

/* ---------- fragment builders ---------- */
function projectCard(p) {
  /* Mirrors projectCard() in js/main.js, including the Present button and
     its wrapper, so prerendered and client-rendered markup match. */
  const specs = [["arch", p.arch], ["role", p.role], ["impact", p.impact]]
    .filter(([, v]) => v)
    .map(([k, v]) => `<div class="spec-row"><span class="spec-label">${k}</span><span class="spec-value">${esc(v)}</span></div>`)
    .join("");
  const tags = (p.stack || []).slice(0, 4).map(t => `<span class="tag">${esc(t)}</span>`).join("");
  const sector = p.sector
    ? `<p class="project-sector"><span>${esc(p.sector)}</span>${p.nda ? '<span class="nda-badge">under NDA</span>' : ""}</p>`
    : "";
  const hasSlides = p.slides && p.slides.length;
  const card = `<a class="project-card${hasSlides ? " has-present" : ""}" href="${esc(p.url || "#")}" data-title="${esc(p.title.toLowerCase())}" data-desc="${esc((p.desc || "").toLowerCase())}" data-category="${esc(p.category || "")}" data-year="${p.year}" data-stack="${esc((p.stack || []).join(" ").toLowerCase())}">
<div class="project-thumb">${thumbSVG(p)}</div>
<div class="project-body">
<div class="project-title-row"><h3>${esc(p.title)}</h3><span class="project-year">${p.year}</span></div>
${sector}
<p class="project-desc">${esc(p.desc)}</p>
<div class="project-specs">${specs}</div>
<div class="tags">${tags}</div>
</div></a>`;
  if (!hasSlides) return card;
  const attrs = `data-title="${esc(p.title.toLowerCase())}" data-desc="${esc((p.desc || "").toLowerCase())}" data-category="${esc(p.category || "")}" data-year="${p.year}" data-stack="${esc((p.stack || []).join(" ").toLowerCase())}"`;
  return `<div class="project-card-wrap" ${attrs}>${card}<button class="present-cta" type="button" data-present="${esc(p.title)}" aria-label="Present ${esc(p.title)}"><span class="present-cta-icon" aria-hidden="true">&#9654;</span><span>Present</span></button></div>`;
}

function bookCard(b) {
  const initials = b.title.split(/\s+/).slice(0, 2).map(w => w[0]).join("");
  const tags = (b.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join("");
  const rating = b.rating ? `<span class="book-rating">${"★".repeat(b.rating)}${"☆".repeat(5 - b.rating)}</span>` : "";
  return `<article class="book-card" data-title="${esc(b.title.toLowerCase())}" data-author="${esc((b.author || "").toLowerCase())}" data-desc="${esc((b.desc || "").toLowerCase())}" data-status="${esc(b.status)}" data-tags="${esc((b.tags || []).join(" ").toLowerCase())}">
<div class="book-cover">${esc(initials)}</div>
<div class="book-main">
<h3 class="book-title">${esc(b.title)}</h3>
<p class="book-author">${esc(b.author)} · ${esc(b.year)}</p>
<p class="book-desc">${esc(b.desc)}</p>
<div class="tags">${tags}</div>
</div>
<div class="book-side"><span class="book-status" data-status="${esc(b.status)}">${esc(b.status)}</span>${rating}</div>
</article>`;
}

/* ---------- regions ---------- */
const STATUS_ORDER = { reading: 0, finished: 1, queued: 2 };

const regions = {
  "skill-matrix": SKILLS.map(g => {
    const chips = g.items.map(i => `<span class="skill-chip" title="${esc(i)}"><span class="skill-name">${esc(i)}</span></span>`).join("");
    return `<div class="skill-group"><h3 class="skill-group-title">${esc(g.title)}</h3><div class="skill-chips">${chips}</div></div>`;
  }).join("\n"),

  "experience-list": EXPERIENCE.map(x => {
    const tags = (x.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join("");
    return `<article class="xp-item"><div class="xp-period">${esc(x.period)}</div><div>
<h3 class="xp-role">${esc(x.role)}</h3>
<p class="xp-company"><b>${esc(x.company)}</b></p>
<p class="xp-desc">${esc(x.desc)}</p>
<div class="tags">${tags}</div></div></article>`;
  }).join("\n"),

  "books-preview": BOOKS.slice()
    .sort((a, b) => (STATUS_ORDER[a.status] ?? 3) - (STATUS_ORDER[b.status] ?? 3))
    .slice(0, 3).map(bookCard).join("\n"),

  "hobby-grid": SIDE.map(h =>
    `<article class="hobby-card"><div class="hobby-icon">${esc(h.icon || "")}</div>
<h3>${esc(h.title)}</h3><p>${esc(h.desc)}</p>
<span class="hobby-status" data-status="${esc(h.status)}">${esc(h.status)}</span></article>`).join("\n"),

  "gallery": PROJECTS.slice().sort((a, b) => b.year - a.year).map(projectCard).join("\n"),

  "book-list": BOOKS.slice()
    .sort((a, b) => (STATUS_ORDER[a.status] ?? 3) - (STATUS_ORDER[b.status] ?? 3) || a.title.localeCompare(b.title))
    .map(bookCard).join("\n"),

  "hero-intro": rich(SITE.intro || ""),
  "site-name": esc(SITE.name),
};

/* ---------- head metadata ---------- */
function headFor(page) {
  const meta = {
    "index.html": {
      title: `${SITE.name} — ${SITE.role}`,
      desc: plain(SITE.intro || "").slice(0, 160),
      url: SITE_URL + "/",
    },
    "projects.html": {
      title: `Projects — ${SITE.name}`,
      desc: `${PROJECTS.length} selected projects: architecture, role and measurable outcomes. Client names withheld.`,
      url: SITE_URL + "/projects.html",
    },
    "books.html": {
      title: `Reading — ${SITE.name}`,
      desc: `Books I've read, am reading, and have queued up — ${BOOKS.length} titles with notes.`,
      url: SITE_URL + "/books.html",
    },
  }[page];

  const ld = page === "index.html" ? {
    "@context": "https://schema.org",
    "@type": "Person",
    name: SITE.name,
    jobTitle: SITE.role,
    email: "mailto:" + SITE.email,
    url: SITE_URL + "/",
    address: { "@type": "PostalAddress", addressLocality: SITE.location },
    sameAs: [SITE.linkedin, SITE.github].filter(u => u && !/your-handle/.test(u)),
    knowsAbout: SKILLS.flatMap(g => g.items).slice(0, 30),
  } : null;

  return `<title>${esc(meta.title)}</title>
<meta name="description" content="${esc(meta.desc)}">
<link rel="canonical" href="${esc(meta.url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="${esc(SITE.name)}">
<meta property="og:title" content="${esc(meta.title)}">
<meta property="og:description" content="${esc(meta.desc)}">
<meta property="og:url" content="${esc(meta.url)}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="${esc(meta.title)}">
<meta name="twitter:description" content="${esc(meta.desc)}">${
  ld ? `\n<script type="application/ld+json">\n${JSON.stringify(ld, null, 2)}\n</script>` : ""}`;
}

/* ---------- apply ---------- */
function replaceRegion(html, id, content) {
  const open = `<!-- build:${id} -->`, close = `<!-- /build:${id} -->`;
  const i = html.indexOf(open), j = html.indexOf(close);
  if (i === -1 || j === -1) return { html, found: false };
  return {
    html: html.slice(0, i + open.length) + "\n" + content + "\n" + html.slice(j),
    found: true,
  };
}

let changed = 0;
["index.html", "projects.html", "books.html"].forEach(function (page) {
  const file = path.join(ROOT, page);
  const before = fs.readFileSync(file, "utf8");
  let html = before;

  const r = replaceRegion(html, "head", headFor(page));
  html = r.html;

  Object.keys(regions).forEach(function (id) {
    html = replaceRegion(html, id, regions[id]).html;
  });

  if (html !== before) { fs.writeFileSync(file, html); changed++; console.log("  rebuilt " + page); }
  else console.log("  unchanged " + page);
});

/* ---------- sitemap + robots ---------- */
const today = new Date().toISOString().slice(0, 10);
fs.writeFileSync(path.join(ROOT, "sitemap.xml"),
`<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${["/", "/projects.html", "/books.html"].map(u =>
`  <url><loc>${SITE_URL}${u}</loc><lastmod>${today}</lastmod></url>`).join("\n")}
</urlset>
`);
fs.writeFileSync(path.join(ROOT, "robots.txt"),
`User-agent: *
Allow: /

Sitemap: ${SITE_URL}/sitemap.xml
`);
console.log("  wrote sitemap.xml, robots.txt");
console.log(`\nPrerendered ${changed} page(s) from content/*.json`);
