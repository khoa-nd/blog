# Personal blog

Plain HTML, CSS and client-side JS. No build step, no dependencies.

## Run locally

```sh
python3 -m http.server 8000
```

Then open http://localhost:8000. (Opening `index.html` directly via `file://`
mostly works too, but a server matches how it will be hosted.)

## Where the content lives

**All content lives in `content/*.json`.** Edit a file, refresh the browser —
there is no build step for the site.

| File | Drives |
|------|--------|
| `content/site.json` | Name, role, email, LinkedIn, GitHub, CV path, location |
| `content/skills.json` | The six skill groups in the home page's **Work** section |
| `content/projects.json` | The `projects.html` gallery |
| `content/experience.json` | Experience list on the home page |
| `content/books.json` | Home preview (3) + the full `books.html` list |
| `content/side-projects.json` | Side project cards on the home page |

JSON is used rather than JavaScript because it is far less punishing to
hand-edit: every editor validates it as you type, and a stray comma is caught
immediately instead of silently blanking the page.

### Before you commit

```sh
npm run check      # validates every content file
```

This catches malformed JSON, missing or mistyped fields, unknown book
statuses, and — importantly — any `company`/`client` field that would leak a
client name into a public NDA-safe page.

### Regenerating the CV

```sh
npm run cv         # writes assets/cv/cv.pdf from content/*.json
```

The CV is built from the **same** files that drive the site, so your experience
and skills cannot drift between the page and the PDF. This is the project's only
build step, and the site does not depend on it.

### One caveat

Content is fetched at runtime, so the site must be served over HTTP —
`file://` will show a clear error banner rather than a blank page. Use:

```sh
npm run serve      # http://localhost:8000
```

## Files

```
index.html        Home — hero, work teaser, experience, reading, side projects
projects.html     Gallery: search, category/year filters, sort, detailed/compact toggle
books.html        Reading list: search, status filter, sort
css/style.css     Layout and structure only — no colour/font literals
css/themes/       Theme stylesheets — blueprint.css (active) + classic.css
css/devbar.css    Dev-only theme switcher styling
js/theme-switcher.js  Dev-only theme switcher (inert off localhost)
content/*.json    >>> ALL CONTENT LIVES HERE <<<
js/content.js     Loads content/*.json and exposes it to the page scripts
js/icons.js       Inline SVG brand marks for the skills matrix
tools/check-content.js  Validates content before commit (npm run check)
tools/build-cv.js       Generates the CV PDF from content (npm run cv)
js/main.js        Theme, nav, card builders, carousel, CV download
js/home.js        Home page rendering
js/projects.js    Gallery filtering
js/books.js       Reading list filtering
assets/cv/cv.pdf  Placeholder — replace with your real CV
```

## Replacing the CV

Drop your real PDF at `assets/cv/cv.pdf`, or point `SITE.cvPath` in `js/data.js`
at a different filename. `SITE.cvFileName` controls the name the browser saves it as.
The path is relative, so it works at a domain root or in a `/repo-name/` subpath.

## Project thumbnails

Each project gets deterministic generated artwork derived from its title and the
`thumb` hex colour — no image files needed. To use a real image instead, add
`image: "assets/img/foo.png"` to that project in `js/data.js`; it takes precedence
over `thumb`.

## Theme

Light/dark follows the OS by default. The header toggle overrides it and the
choice is remembered in `localStorage`. An inline script in each `<head>` applies
the stored theme before first paint so there's no flash.

## Hosting on GitHub Pages

Push this directory to a repo and enable Pages on the branch root. Everything —
including the CV — is served from the repo. Because all paths are relative, it
works both at `user.github.io` and `user.github.io/repo-name/`.

## Writing NDA-safe project entries

The home page shows **no project details** — only counts and capability tags
derived from the data. Everything specific lives in `projects.html`, and the
data shape is built so a client name has nowhere to go.

There is deliberately **no `company` field** on a project. Instead:

| Field    | Holds                                  | Example |
|----------|----------------------------------------|---------|
| `sector` | The kind of business, never its name   | `"Financial services"` |
| `nda`    | `true` renders an "under NDA" badge    | `true` |
| `arch`   | The system's shape, not its business logic | `"Event-driven · 3 services · at-least-once delivery with replay"` |
| `role`   | What *you* specifically did            | `"Sole backend engineer on the service"` |
| `impact` | A measurable outcome                   | `"800 msg/s sustained · 99.97% uptime"` |

The test to apply to any line you write: **could a reader use this to name the
client?** Scale figures are fine (`800 msg/s`). Scale figures tied to a named
market, a distinctive product feature, or a headcount usually are not.

Saying "under NDA" explicitly reads as professional discretion. Vagueness with
no explanation reads as padding — so flag it rather than hiding it.

Personal and open-source work carries a `sector` like `"Personal project"` and
no `nda` flag, so it displays without the badge.

## The skills matrix (home "Work" section)

Six groups defined by `SKILL_GROUPS` in `js/data.js`. Each skill renders as a
chip with an inline SVG brand mark; **anything without a mark falls back to a
text-only chip automatically**, so you can name any skill without needing
artwork for it first. Currently 45 of 50 render with an icon.

To add a skill, just add the string:

```js
{ title: "Infrastructure & DevSecOps",
  items: ["Docker", "Kubernetes", "Pulumi"] },   // Pulumi -> text chip
```

### Adding an icon

Icons live in `js/icons.js` as 24x24 SVG path fragments using `currentColor`,
so they inherit theme colours. Add an entry keyed by the lower-cased,
punctuation-stripped name:

```js
const ICONS = {
  pulumi: '<path d="…"/>',
};
```

Names are matched loosely — `"Node.js"`, `"node js"` and `"nodejs"` all resolve
to the same mark. Use `ICON_ALIASES` to point several names at one icon.

A few marks (TypeScript, JavaScript, HTML5, CSS3) knock a glyph out of a solid
tile. Those use `var(--icon-knockout)`, set on `.skill-icon` to the card
background so they stay legible in both themes.

**Why inline SVG and not an icon font or CDN:** no network request, no build
step, works offline, and no dependency that can break or change under you.

## Theming

Four themes ship:

| Theme | Character |
|-------|-----------|
| **Blueprint** | Technical drawing — cool blue-grey, electric blue, hairline rules, structural monospace, near-square corners |
| **Classic** (active) | Warm off-white, slate blue, soft drop shadows, rounded corners, system sans throughout |
| **Manuscript** | Editorial — cream paper, serif headings and body, burnt ochre, rules instead of boxes |
| **Terminal** | Dark, all-monospace, phosphor green, zero rounding, shell-prompt headings and a blinking cursor |

Blueprint, Classic and Manuscript are light; Terminal is the one dark theme.

Styling is split in two:

| File | Owns |
|------|------|
| `css/themes/*.css` | Every visual decision — all 32 tokens, plus that theme's character rules |
| `css/style.css` | Layout and structure only. Contains **zero** typography — no font-size, font-weight, letter-spacing or text-transform — and zero colour/radius literals |

The theme is linked **first** so `style.css` can read its tokens:

```html
<link rel="stylesheet" href="css/themes/classic.css">
<link rel="stylesheet" href="css/style.css">
```

### Making another theme

Copy `blueprint.css`, change the values, and point the `<link>` in the three
HTML files at it. **Keep every token name** — `style.css` references them by
name, and a missing one renders as a blank value rather than an error.

The token block is the contract. The "Theme character" rules below it (the
monospace and uppercase treatments) are Blueprint-specific — a rounded,
shadowed, all-sans theme would simply omit that block.

### Comparing themes locally

A dev-only switcher appears at the bottom of the page when the site is served
from `localhost`, `127.0.0.1`, or opened as a `file://` URL. Click any of the
four themes to swap instantly; the choice persists across page navigation.
Press **T** to hide or show the bar, or click the ×.

`js/theme-switcher.js` exits immediately on any other host, so the widget never
appears in production — it is safe to deploy as-is. To remove it entirely, drop
the `theme-switcher.js` and `devbar.css` tags from the three HTML files.

The switcher styles itself with hard-coded values rather than theme tokens, so
the widget looks identical in both themes and never changes along with the
thing you are comparing.

### Switching the shipped default

Change the theme `<link>` in the three HTML files:

```html
<link rel="stylesheet" href="css/themes/blueprint.css">
```

All four themes define the **same 32 token names** — that is the contract. A new
theme must define all of them; a missing token renders as a blank value rather
than an error.

A theme may also add "character" rules below its token block (Blueprint's
structural monospace, Manuscript's serif headings, Terminal's shell prompts).
Because these cascade over `style.css`, a theme that wants a plainer look
should actively reset what an earlier theme set — see how `classic.css`
reverses Blueprint's uppercase and monospace treatments.

### Type scale

Every font size on the site flows from the seven `--step` tokens — there are
**no hard-coded sizes** in `style.css` or in any theme. Changing a theme's
scale resizes the whole site consistently, including small labels like tags,
chips, badges and status pills.

Classic runs a deliberately comfortable scale (17px body, 14px small labels).
Blueprint and Terminal run tighter, since monospace occupies more width per
character.

## Typography ownership

`style.css` sets **no typography at all**. Font size, weight, tracking, case and
family are entirely the theme's, including the base `h1–h4` weight. This matters
because both files use the same selector specificity and `style.css` loads last —
any type declaration left there would silently outrank every theme.

If a heading looks unstyled after you add a theme, that theme is missing its base
block:

```css
h1, h2, h3, h4 { font-weight: 600; letter-spacing: -0.015em; }
```

### Classic's Apple typography

Classic targets Apple's system typography. Beyond naming `-apple-system` (which
resolves to SF Pro and switches optical size automatically around 20px), three
details do the work:

- **Optical tracking.** Large text tracks tight (`-0.028em` on the hero), small
  text tracks *loose* (`+0.004em` on tags and chips). The positive tracking on
  small text is the detail most often missed.
- **Restrained weights.** 400 body, 450–550 interface, 600–700 headings. SF's
  intermediate weights (450, 550, 590, 650) are used deliberately.
- **Tabular figures** on years, periods and counts so numbers align.

## How content becomes HTML

The page scripts render from `content/*.json` at runtime, which alone would
leave the HTML source empty — bad for search engines and for link previews on
Slack, LinkedIn and X, none of which run JavaScript. So the content is also
**prerendered into the HTML** between `<!-- build:… -->` markers.

**You do not have to do this yourself.** A GitHub Action
(`.github/workflows/build.yml`) validates and prerenders on every push that
touches `content/`, then commits the regenerated HTML back to `main`. It runs
on GitHub's servers, so it covers every way a commit can happen:

- `git push` from your machine
- editing a JSON file in the github.com web editor
- the GitHub mobile app

There is no local git hook to install or forget.

### Editing from the web

Edit `content/books.json` on github.com, commit, and you are done. The Action
rebuilds within a minute and Pages redeploys. Human visitors see the change
immediately (the JS renders it); crawlers see it once the rebuild lands.

**After a web edit, `git pull` before your next local push** — the bot will have
committed on top of your change.

### Building locally (optional)

Running the build yourself avoids the follow-up bot commit and lets you preview
the exact HTML that will ship:

```sh
npm run check     # validate content
npm run build     # prerender into HTML + sitemap/robots
```

If you commit the result, the Action finds nothing to do and exits quietly.

### If validation fails

The Action fails loudly in the Actions tab and skips the build, so malformed
JSON never produces broken HTML. The site keeps serving the last good version.
Fix the JSON and push again.

## Project presentations

Each project card in the gallery has a **Present** button (visible on hover;
always visible on touch). It opens a fullscreen slideshow — plain HTML in a
`<dialog>`, no slideshow library — with three slides:

| Slide | Shows |
|-------|-------|
| `overview` | A lead paragraph, bullet points, and a row of facts (duration, team, sector) |
| `architecture` | A left-to-right pipeline diagram plus explanatory notes |
| `results` | Big metric tiles and supporting bullets |

**Keyboard:** `→` `←` `Space` navigate · `Home`/`End` jump · `F` fullscreen ·
`Esc` close.

### Writing a deck

Decks live on the project itself in `content/projects.json`, under `slides`:

```json
"slides": [
  { "type": "overview", "title": "Project Overview",
    "lead": "One or two sentences framing the problem.",
    "points": ["A bullet", "Another bullet"],
    "facts": [["Duration", "8 months"], ["Team", "1 engineer"]] },

  { "type": "architecture", "title": "Architecture",
    "lead": "How the system is shaped.",
    "nodes": ["Producers", "Ingest", "Router", "Consumers"],
    "notes": ["Something worth saying about the design"] },

  { "type": "results", "title": "Key Results",
    "lead": "What changed.",
    "metrics": [["800", "msg/s sustained"], ["99.97%", "uptime"]],
    "points": ["Supporting detail"] }
]
```

A project with no `slides` array simply gets no Present button.

Keep pipelines to about four nodes — `npm run check` warns above six, because
more than that stops being readable at presentation size. The same NDA rule
applies here as everywhere: describe the architecture, never the client.

Two projects ship with hand-written decks (Event Router, Payments
Reconciliation Engine); the rest have generic scaffolds to replace.
