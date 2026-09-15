#!/usr/bin/env node
/* ============================================================
   Generate assets/cv/cv.pdf from the same content/*.json files
   that drive the site, so the CV can never drift from the page.

   Run:  node tools/build-cv.js

   This is the ONLY build step in the project, and the site does
   not depend on it — it exists purely to produce the PDF.

   No dependencies: the PDF is written by hand. That keeps the
   repo install-free, at the cost of a deliberately plain layout.
   ============================================================ */
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const read = (name) =>
  JSON.parse(fs.readFileSync(path.join(ROOT, "content", name + ".json"), "utf8"));

const SITE = read("site");
const EXPERIENCE = read("experience");
const SKILLS = read("skills");
const PROJECTS = read("projects");

/* ---------- PDF primitives ----------
   Helvetica only, so no font embedding is needed. */
const PAGE_W = 595.28, PAGE_H = 841.89;          // A4 points
const M = 56;                                     // margin
/* WinAnsi has no slot for several characters we use, so map them to
   equivalents that Helvetica can actually draw. Without this they
   silently vanish from the PDF. */
const CHAR_MAP = {
  "\u2014": "\u2013",  // em dash  -> en dash (WinAnsi 0x96)
  "\u2022": "\u00b7",  // bullet   -> middot
  "\u2018": "'", "\u2019": "'",
  "\u201c": '"', "\u201d": '"',
  "\u2026": "...",
  "\u2192": "->",
  "\u2605": "*", "\u2606": "-",
};
const esc = (s) => {
  let out = "";
  for (const ch of String(s)) {
    const mapped = CHAR_MAP[ch] !== undefined ? CHAR_MAP[ch] : ch;
    for (const c of mapped) {
      const code = c.charCodeAt(0);
      if (c === "\\") out += "\\\\";
      else if (c === "(") out += "\\(";
      else if (c === ")") out += "\\)";
      else if (code < 32) out += " ";
      else if (code < 127) out += c;
      else if (code === 0x2013) out += "\\226";       // en dash, WinAnsi octal
      else if (code === 0x00b7) out += "\\267";       // middle dot
      else if (code < 256) out += "\\" + code.toString(8).padStart(3, "0");
      else {
        /* Helvetica/WinAnsi cannot encode Vietnamese (and similar) diacritics.
           Decompose to the base letter rather than emitting "?" — "Nguyen"
           is a far better fallback than "Nguy?n". */
        /* NFD does not decompose these — the stroke/bar is part of the
           letterform, not a combining mark. Map them explicitly. */
        const STROKE = { "\u0110": "D", "\u0111": "d", "\u00d8": "O", "\u00f8": "o",
                         "\u0141": "L", "\u0142": "l", "\u0126": "H", "\u0127": "h" };
        const pre = STROKE[c] || c;
        const folded = pre.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        const cp = folded.charCodeAt(0);
        if (folded && cp < 127) out += folded;
        else if (folded && cp < 256) out += "\\" + cp.toString(8).padStart(3, "0");
        else out += "?";
      }
    }
  }
  return out;
};

/* Helvetica advance widths (per 1000 units) for the printable ASCII range,
   so we can wrap text without a font library. */
const W = [278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584];
function widthOf(text, size, bold) {
  let w = 0;
  for (const ch of String(text)) {
    const c = ch.charCodeAt(0);
    let u = (c >= 32 && c <= 126) ? W[c - 32] : 556;
    if (bold) u *= 1.06;              // rough Helvetica-Bold allowance
    w += u;
  }
  return w * size / 1000;
}
function wrap(text, size, bold, maxW) {
  const words = String(text).split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (const word of words) {
    const trial = line ? line + " " + word : word;
    if (widthOf(trial, size, bold) <= maxW) { line = trial; }
    else { if (line) lines.push(line); line = word; }
  }
  if (line) lines.push(line);
  return lines;
}

/* ---------- Document builder ---------- */
const pages = [];
let ops = [], y = 0;

function newPage() {
  if (ops.length) pages.push(ops.join("\n"));
  ops = [];
  y = PAGE_H - M;
}
function space(n) { y -= n; }
function need(n) { if (y - n < M) newPage(); }

function text(str, { size = 10, bold = false, color = "0 0 0", x = M, gap = 0 } = {}) {
  need(size + gap);
  ops.push("BT", `/F${bold ? 2 : 1} ${size} Tf`, `${color} rg`,
           `1 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)} Tm`, `(${esc(str)}) Tj`, "ET");
  y -= size + gap;
}
function paragraph(str, { size = 9.5, color = ".28 .28 .32", x = M, width = PAGE_W - M * 2, lead = 3.4 } = {}) {
  for (const line of wrap(str, size, false, width)) {
    need(size + lead);
    ops.push("BT", `/F1 ${size} Tf`, `${color} rg`,
             `1 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)} Tm`, `(${esc(line)}) Tj`, "ET");
    y -= size + lead;
  }
}
function rule(color = ".78 .78 .75") {
  need(10);
  ops.push(`${color} RG`, "0.7 w", `${M} ${y.toFixed(2)} m ${(PAGE_W - M).toFixed(2)} ${y.toFixed(2)} l S`);
  y -= 12;
}
function heading(str) {
  space(8);
  need(30);
  text(str.toUpperCase(), { size: 8.5, bold: true, color: ".18 .37 .65", gap: 5 });
  rule();
}

/* ---------- Content ---------- */
newPage();

text(SITE.name, { size: 23, bold: true, gap: 4 });
text(SITE.role, { size: 11.5, color: ".28 .28 .32", gap: 7 });

const contact = [SITE.email, SITE.location,
                 (SITE.linkedin || "").replace(/^https?:\/\/(www\.)?/, ""),
                 (SITE.github   || "").replace(/^https?:\/\/(www\.)?/, "")]
                .filter(Boolean).join("   ·   ");
text(contact, { size: 8.5, color: ".42 .42 .48", gap: 10 });
rule(".65 .65 .62");

/* The site intro doubles as the CV summary. ** markers are for the web,
   so strip them — weight is carried by the layout here. */
if (SITE.intro) {
  space(2);
  paragraph(SITE.intro.replace(/\*\*/g, ""), { size: 9.5, lead: 3.8 });
  space(4);
}

heading("Experience");
EXPERIENCE.forEach(function (job, i) {
  if (i) space(6);
  need(46);
  const period = job.period || "";
  const pw = widthOf(period, 8.5, false);
  ops.push("BT", "/F1 8.5 Tf", ".42 .42 .48 rg",
           `1 0 0 1 ${(PAGE_W - M - pw).toFixed(2)} ${y.toFixed(2)} Tm`,
           `(${esc(period)}) Tj`, "ET");
  text(job.role, { size: 11, bold: true, gap: 1.5 });
  text(job.company, { size: 9.5, color: ".28 .28 .32", gap: 3.5 });
  if (job.desc) paragraph(job.desc);
  if (job.tags && job.tags.length) {
    space(1.5);
    paragraph(job.tags.join("  ·  "), { size: 8.5, color: ".45 .45 .5" });
  }
});

heading("Skills");
SKILLS.forEach(function (group, i) {
  if (i) space(4);
  need(26);
  text(group.title, { size: 9.5, bold: true, gap: 2 });
  paragraph((group.items || []).join("  ·  "), { size: 9, color: ".3 .3 .35" });
});

heading("Selected projects");
PROJECTS.slice()
  .sort(function (a, b) { return b.year - a.year; })
  .slice(0, 5)
  .forEach(function (p, i) {
    if (i) space(5);
    need(40);
    const yr = String(p.year);
    const yw = widthOf(yr, 8.5, false);
    ops.push("BT", "/F1 8.5 Tf", ".42 .42 .48 rg",
             `1 0 0 1 ${(PAGE_W - M - yw).toFixed(2)} ${y.toFixed(2)} Tm`,
             `(${esc(yr)}) Tj`, "ET");
    text(p.title, { size: 10.5, bold: true, gap: 1.5 });
    const sector = p.sector + (p.nda ? "  (under NDA)" : "");
    text(sector, { size: 8.5, color: ".45 .45 .5", gap: 3 });
    if (p.arch)   paragraph("Architecture:  " + p.arch, { size: 8.8 });
    if (p.role)   paragraph("Role:  " + p.role,         { size: 8.8 });
    if (p.impact) paragraph("Impact:  " + p.impact,     { size: 8.8 });
    if (p.stack && p.stack.length) {
      paragraph(p.stack.join("  ·  "), { size: 8.5, color: ".45 .45 .5" });
    }
  });

newPage();   // flush the last page

/* ---------- Assemble ---------- */
const objects = [];
const add = (body) => { objects.push(body); return objects.length; };

const fontRegular = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
const fontBold    = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>");

const pagesId = objects.length + 1 + pages.length * 2 + 1;
const pageIds = [];
pages.forEach(function (content) {
  const streamId = add("<< /Length " + Buffer.byteLength(content, "latin1") + " >>\nstream\n" + content + "\nendstream");
  pageIds.push(add(
    "<< /Type /Page /Parent " + pagesId + " 0 R " +
    "/MediaBox [0 0 " + PAGE_W + " " + PAGE_H + "] " +
    "/Resources << /Font << /F1 " + fontRegular + " 0 R /F2 " + fontBold + " 0 R >> >> " +
    "/Contents " + streamId + " 0 R >>"));
});
const pagesObj   = add("<< /Type /Pages /Kids [" + pageIds.map(i => i + " 0 R").join(" ") + "] /Count " + pageIds.length + " >>");
const catalogObj = add("<< /Type /Catalog /Pages " + pagesObj + " 0 R >>");

let out = Buffer.from("%PDF-1.4\n", "latin1");
const offsets = [];
objects.forEach(function (body, i) {
  offsets.push(out.length);
  out = Buffer.concat([out, Buffer.from((i + 1) + " 0 obj\n" + body + "\nendobj\n", "latin1")]);
});
const xref = out.length;
let tail = "xref\n0 " + (objects.length + 1) + "\n0000000000 65535 f \n";
offsets.forEach(o => { tail += String(o).padStart(10, "0") + " 00000 n \n"; });
tail += "trailer\n<< /Size " + (objects.length + 1) + " /Root " + catalogObj + " 0 R >>\n" +
        "startxref\n" + xref + "\n%%EOF\n";
out = Buffer.concat([out, Buffer.from(tail, "latin1")]);

const dest = path.join(ROOT, SITE.cvPath || "assets/cv/cv.pdf");
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.writeFileSync(dest, out);

console.log("Wrote " + path.relative(ROOT, dest) +
            "  (" + pageIds.length + " page" + (pageIds.length === 1 ? "" : "s") +
            ", " + (out.length / 1024).toFixed(1) + " KB)");
console.log("Source: content/{site,experience,skills,projects}.json");
