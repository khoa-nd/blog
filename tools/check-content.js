#!/usr/bin/env node
/* ============================================================
   Validate content/*.json before you commit.

   Run:  node tools/check-content.js   (or: npm run check)

   Catches the mistakes JSON allows but the site cannot use:
   missing required fields, wrong types, unknown status values,
   and — importantly — any field that could leak a client name.
   ============================================================ */
"use strict";

const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");

let errors = 0, warnings = 0;
const err  = (f, m) => { console.error(`  ERROR  ${f}: ${m}`); errors++; };
const warn = (f, m) => { console.warn (`  WARN   ${f}: ${m}`); warnings++; };

function load(name) {
  const file = path.join(ROOT, "content", name + ".json");
  if (!fs.existsSync(file)) { err(name + ".json", "file is missing"); return null; }
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    err(name + ".json", "invalid JSON — " + e.message);
    return null;
  }
}

const need = (file, obj, i, fields) => fields.forEach(function (f) {
  const v = obj[f];
  if (v === undefined || v === null || v === "") err(file, `entry ${i} ("${obj.title || obj.role || i}") is missing "${f}"`);
});

/* ---------- site ---------- */
const site = load("site");
if (site) {
  ["name", "role", "intro", "email", "cvPath", "cvFileName"].forEach(function (k) {
    if (!site[k]) err("site.json", `missing "${k}"`);
  });
  if (site.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(site.email)) err("site.json", `"${site.email}" is not a valid email`);
  if (site.cvPath && site.cvPath.startsWith("/")) err("site.json", "cvPath must be relative (no leading slash) or it breaks under /repo-name/");
  if (site.cvPath && !fs.existsSync(path.join(ROOT, site.cvPath))) warn("site.json", `cvPath "${site.cvPath}" does not exist — run: npm run cv`);
  if (site.name === "Your Name") warn("site.json", 'name is still the placeholder "Your Name"');
  if (site.intro) {
    const unclosed = (site.intro.match(/\*\*/g) || []).length % 2;
    if (unclosed) err("site.json", '"intro" has an unclosed ** bold marker');
    if (/<[a-z/]/i.test(site.intro)) warn("site.json", '"intro" contains HTML — it will be escaped and shown literally; use **bold** instead');
  }
}

/* ---------- projects ---------- */
const projects = load("projects");
if (Array.isArray(projects)) {
  projects.forEach(function (p, i) {
    need("projects.json", p, i, ["title", "year", "sector", "category", "desc"]);
    if (typeof p.year !== "number") err("projects.json", `entry ${i} "year" must be a number, not "${typeof p.year}"`);
    if (p.stack && !Array.isArray(p.stack)) err("projects.json", `entry ${i} "stack" must be an array`);
    /* The NDA contract: no client-name field may exist at all. */
    ["company", "client", "employer", "customer"].forEach(function (banned) {
      if (banned in p) err("projects.json", `entry ${i} has a "${banned}" field — client names must not appear; use "sector"`);
    });
    if (p.nda !== undefined && typeof p.nda !== "boolean") err("projects.json", `entry ${i} "nda" must be true or false`);

    /* Presentation deck, if present. */
    if (p.slides !== undefined) {
      if (!Array.isArray(p.slides)) {
        err("projects.json", `entry ${i} "slides" must be an array`);
      } else {
        const TYPES = ["overview", "architecture", "results"];
        p.slides.forEach(function (s, j) {
          const where = `entry ${i} ("${p.title}") slide ${j}`;
          if (!s.title) err("projects.json", `${where} is missing "title"`);
          if (!s.type)  err("projects.json", `${where} is missing "type"`);
          else if (TYPES.indexOf(s.type) === -1) {
            err("projects.json", `${where} type "${s.type}" must be one of: ${TYPES.join(", ")}`);
          }
          ["points", "notes", "nodes"].forEach(function (k) {
            if (s[k] !== undefined && !Array.isArray(s[k])) err("projects.json", `${where} "${k}" must be an array`);
          });
          ["facts", "metrics"].forEach(function (k) {
            if (s[k] === undefined) return;
            if (!Array.isArray(s[k])) { err("projects.json", `${where} "${k}" must be an array`); return; }
            s[k].forEach(function (pair, n) {
              if (!Array.isArray(pair) || pair.length !== 2) {
                err("projects.json", `${where} ${k}[${n}] must be a [label, value] pair`);
              }
            });
          });
          if (s.type === "architecture" && s.nodes && s.nodes.length > 7) {
            warn("projects.json", `${where} has ${s.nodes.length} pipeline nodes — more than ~6 is hard to read on a slide`);
          }
        });
      }
    }
  });
}

/* ---------- experience ---------- */
const experience = load("experience");
if (Array.isArray(experience)) {
  experience.forEach(function (x, i) {
    need("experience.json", x, i, ["role", "company", "period", "desc"]);
    if (x.tags && !Array.isArray(x.tags)) err("experience.json", `entry ${i} "tags" must be an array`);
  });
}

/* ---------- books ---------- */
const STATUSES = ["reading", "finished", "queued"];
const books = load("books");
if (Array.isArray(books)) {
  books.forEach(function (b, i) {
    need("books.json", b, i, ["title", "author", "status", "desc"]);
    if (b.status && STATUSES.indexOf(b.status) === -1) {
      err("books.json", `entry ${i} status "${b.status}" must be one of: ${STATUSES.join(", ")}`);
    }
    if (b.rating !== undefined && (typeof b.rating !== "number" || b.rating < 0 || b.rating > 5)) {
      err("books.json", `entry ${i} "rating" must be a number 0-5`);
    }
  });
}

/* ---------- skills ---------- */
const skills = load("skills");
if (Array.isArray(skills)) {
  skills.forEach(function (g, i) {
    if (!g.title) err("skills.json", `group ${i} is missing "title"`);
    if (!Array.isArray(g.items) || !g.items.length) err("skills.json", `group ${i} ("${g.title}") needs a non-empty "items" array`);
  });
  /* Which skills will render as plain text because no icon exists. */
  const iconsSrc = fs.readFileSync(path.join(ROOT, "js", "icons.js"), "utf8");
  const known = new Set();
  const block = iconsSrc.slice(iconsSrc.indexOf("const ICONS"), iconsSrc.indexOf("const ICON_ALIASES"));
  (block.match(/^\s{2}([a-z0-9]+):/gm) || []).forEach(m => known.add(m.trim().replace(":", "")));
  (iconsSrc.slice(iconsSrc.indexOf("const ICON_ALIASES")).match(/"([^"]+)":/g) || [])
    .forEach(m => known.add(m.replace(/[":]/g, "")));
  const noIcon = [];
  skills.forEach(g => (g.items || []).forEach(function (item) {
    const key = String(item).toLowerCase().trim();
    if (!known.has(key) && !known.has(key.replace(/[\s.\-_/]+/g, ""))) noIcon.push(item);
  }));
  if (noIcon.length) {
    console.log(`  INFO   ${noIcon.length} skill(s) render as text (no icon): ${noIcon.join(", ")}`);
  }
}

/* ---------- side projects ---------- */
const side = load("side-projects");
if (Array.isArray(side)) {
  side.forEach(function (h, i) { need("side-projects.json", h, i, ["title", "desc", "status"]); });
}

console.log("");
if (errors)      { console.error(`${errors} error(s), ${warnings} warning(s). Fix the errors before committing.`); process.exit(1); }
if (warnings)    { console.log(`No errors, ${warnings} warning(s).`); process.exit(0); }
console.log("All content valid.");
