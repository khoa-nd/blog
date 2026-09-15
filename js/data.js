/* ============================================================
   Site content — edit everything here.
   All pages read from this file. No build step, no framework.
   ============================================================ */

const SITE = {
  name: "Your Name",
  role: "Software Engineer",
  email: "you@example.com",
  linkedin: "https://www.linkedin.com/in/your-handle",
  github: "https://github.com/your-handle",
  cvPath: "assets/cv/cv.pdf",       // relative on purpose: works on any host
  cvFileName: "Your-Name-CV.pdf",
  location: "Ho Chi Minh City, Vietnam",
};

/* ---------- Skills matrix (home "Work" section) ----------
   Six groups, in display order. Each entry is a skill name; if
   js/icons.js has a mark for it the icon renders, otherwise it
   falls back to a plain text tag automatically — so you can add
   anything here without needing artwork for it first.

   Check what has an icon: the ICONS + ICON_ALIASES keys in js/icons.js. */
const SKILL_GROUPS = [
  {
    title: "AI & Agentic Software Engineering",
    items: ["OpenAI API", "LangChain", "MCP", "RAG", "PyTorch",
            "Prompt Engineering", "Agent Orchestration", "Evals"],
  },
  {
    title: "Software Architecture & Design",
    items: ["System Design", "Microservices", "Design Patterns", "REST API",
            "GraphQL", "Kafka", "Domain-Driven Design", "Event Sourcing"],
  },
  {
    title: "Programming Frameworks & Skills",
    items: ["TypeScript", "JavaScript", "Python", "Java", "Go",
            "React", "Next.js", "Node.js", "Tailwind", "HTML5", "CSS3"],
  },
  {
    title: "Infrastructure & DevSecOps",
    items: ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD",
            "Git", "Linux", "DevSecOps", "Observability"],
  },
  {
    title: "Software Solutions & Packages",
    items: ["CMS", "Postgres", "MongoDB", "Redis", "Vector DB",
            "Cloud", "Mobile"],
  },
  {
    title: "Fundamental Skills",
    items: ["Data Structures", "Algorithms", "Testing", "Performance",
            "Accessibility", "Documentation", "Agile"],
  },
];

/* ---------- Projects ----------
   NDA-SAFE BY CONSTRUCTION. There is deliberately no client-name field.

     sector   what kind of business it was  ("Fintech scale-up")
     nda      true  -> card shows "· under NDA" after the sector
     arch     the shape of the system, not the business logic
     role     what YOU specifically did
     impact   a measurable outcome, no client-identifying numbers

   Rule of thumb: if a line would let a reader name the client, it belongs
   in your interview conversation, not on this page. Scale figures are fine
   ("800 msg/s"); scale figures tied to a named market are not.

   thumb: hex colour seeding the generated schematic artwork. Swap for
   `image: "assets/img/foo.png"` when you have a real (sanitised) diagram. */
const PROJECTS = [
  {
    title: "Component Library & Design Tokens",
    year: 2025,
    sector: "B2B SaaS", nda: true,
    category: "Design Systems",
    stack: ["TypeScript", "Web Components", "Storybook"],
    arch: "Framework-agnostic web components · tokens compiled from one JSON source to CSS/iOS/Android",
    role: "Lead engineer · set the API conventions and the adoption path",
    impact: "48 components · adopted by 6 product teams",
    desc: "A themeable component library that let independent teams ship consistent UI without coordinating releases.",
    thumb: "#2f5ea8",
    url: "#",
  },
  {
    title: "CI Telemetry Pipeline",
    year: 2025,
    sector: "Personal project",
    category: "Infrastructure",
    stack: ["Go", "ClickHouse", "Grafana"],
    arch: "Event ingest → columnar store → rollup queries · flake detection over rolling windows",
    role: "Sole author, design through operation",
    impact: "2M events/day · surfaced flaky tests that cut build time 38%",
    desc: "Real-time build telemetry that finds slow and unreliable steps before they block a release.",
    thumb: "#8a5cf0",
    url: "#",
  },
  {
    title: "Payments Reconciliation Engine",
    year: 2024,
    sector: "Financial services", nda: true,
    category: "Backend",
    stack: ["Python", "Postgres", "Airflow"],
    arch: "Scheduled DAG · idempotent matching across multiple provider feeds · exception queue for human review",
    role: "Designed the matching model and owned the rollout",
    impact: "1.4M transactions/cycle · 3 days of manual work → 20 minutes",
    desc: "Automated a month-end reconciliation process that previously occupied two analysts for three days.",
    thumb: "#0f9b8e",
    url: "#",
  },
  {
    title: "Headless Content Platform",
    year: 2024,
    sector: "B2B SaaS", nda: true,
    category: "Full-stack",
    stack: ["Java", "Magnolia", "React"],
    arch: "Headless CMS · one editorial workspace fanning out to many regional front-ends · per-market publishing rules",
    role: "Platform lead · content model, publishing rules, front-end integration",
    impact: "12 regional sites · 4 languages from a single workspace",
    desc: "Let one editorial team serve a dozen markets without a separate CMS per region.",
    thumb: "#d9743f",
    url: "#",
  },
  {
    title: "Local-First Analytics Notebook",
    year: 2023,
    sector: "Personal project",
    category: "Data",
    stack: ["Rust", "DuckDB", "Svelte"],
    arch: "In-process OLAP engine compiled to WASM · query execution entirely client-side, no server round-trip",
    role: "Sole author",
    impact: "10GB local datasets · zero network calls by design",
    desc: "Query CSV and Parquet files in the browser without uploading anything anywhere.",
    thumb: "#c2417a",
    url: "#",
  },
  {
    title: "Offline-First Field Data Capture",
    year: 2023,
    sector: "Non-profit",
    category: "Mobile",
    stack: ["React Native", "Expo", "SQLite"],
    arch: "Local SQLite as source of truth · opportunistic sync with conflict resolution on reconnect",
    role: "Sole mobile engineer",
    impact: "200+ field users · fully functional with no connectivity",
    desc: "Data collection for volunteers working in places where a network connection is not a given.",
    thumb: "#3fa85f",
    url: "#",
  },
  {
    title: "Event Router",
    year: 2022,
    sector: "Financial services", nda: true,
    category: "Backend",
    stack: ["Kotlin", "Kafka", "Kubernetes"],
    arch: "Event-driven · 3 services · at-least-once delivery with replay from offset",
    role: "Sole backend engineer on the service",
    impact: "800 msg/s sustained · 99.97% uptime over 14 months",
    desc: "Fans internal state changes out to downstream consumers with replay when a consumer falls behind.",
    thumb: "#5566c4",
    url: "#",
  },
  {
    title: "Contrast-Checking Palette Tool",
    year: 2022,
    sector: "Open source",
    category: "Design Systems",
    stack: ["JavaScript", "Canvas", "WASM"],
    arch: "Pairwise WCAG contrast computed on every drag · no build step, runs entirely in the browser",
    role: "Sole author",
    impact: "Checks every colour pair against AA and AAA in real time",
    desc: "Builds a palette while continuously verifying every foreground/background pair stays accessible.",
    thumb: "#e0a33e",
    url: "#",
  },
  {
    title: "Risk Exposure Dashboard",
    year: 2021,
    sector: "Financial services", nda: true,
    category: "Data",
    stack: ["Python", "pandas", "FastAPI"],
    arch: "Streaming aggregation replacing a nightly batch · incremental recompute on position change",
    role: "Backend and data modelling",
    impact: "Nightly report → live view · used daily by 12 desks",
    desc: "Replaced an overnight batch report with a live view that traders actually kept open all day.",
    thumb: "#4a9ed4",
    url: "#",
  },
];

/* ---------- Experience ---------- */
const EXPERIENCE = [
  {
    role: "Senior Software Engineer",
    company: "B2B SaaS company",
    period: "2023 — Present",
    desc: "Lead engineer on the platform team. Own the design system and the content infrastructure powering twelve regional sites. Mentor three engineers.",
    tags: ["TypeScript", "Java", "Design Systems", "Leadership"],
  },
  {
    role: "Software Engineer",
    company: "Financial services company",
    period: "2021 — 2023",
    desc: "Built and operated backend services for payments reconciliation and risk reporting. Took the reconciliation process from three days of manual work to twenty minutes.",
    tags: ["Python", "Kotlin", "Kafka", "Postgres"],
  },
  {
    role: "Full-stack Developer",
    company: "Digital agency",
    period: "2019 — 2021",
    desc: "Agency work across a dozen client projects — e-commerce, editorial sites, internal tools. Learned to ship fast and read someone else's codebase without complaining.",
    tags: ["JavaScript", "PHP", "React", "AWS"],
  },
  {
    role: "Junior Developer",
    company: "Software consultancy",
    period: "2018 — 2019",
    desc: "First engineering role. Maintained an internal reporting tool and wrote the integration tests nobody else wanted to write.",
    tags: ["Java", "Selenium", "MySQL"],
  },
];

/* ---------- Books ---------- */
const BOOKS = [
  {
    title: "Designing Data-Intensive Applications",
    author: "Martin Kleppmann",
    year: 2017,
    status: "finished",
    rating: 5,
    tags: ["Systems", "Distributed"],
    desc: "The reference I keep returning to. The chapter on consistency models finally made replication lag feel intuitive rather than terrifying.",
  },
  {
    title: "The Pragmatic Programmer",
    author: "Andrew Hunt & David Thomas",
    year: 1999,
    status: "finished",
    rating: 4,
    tags: ["Craft"],
    desc: "Dated in its examples, durable in its advice. Worth rereading every few years to see which parts you have quietly stopped doing.",
  },
  {
    title: "Thinking, Fast and Slow",
    author: "Daniel Kahneman",
    year: 2011,
    status: "reading",
    rating: 4,
    tags: ["Psychology", "Decisions"],
    desc: "Slow going but rewarding. Changed how I write postmortems — most of what looks like a bad decision was a decision made under a bad frame.",
  },
  {
    title: "A Philosophy of Software Design",
    author: "John Ousterhout",
    year: 2018,
    status: "finished",
    rating: 5,
    tags: ["Craft", "Architecture"],
    desc: "Short, opinionated, and the clearest argument I have read for deep modules over thin ones. Disagree with parts of it and you will still think better.",
  },
  {
    title: "Shape Up",
    author: "Ryan Singer",
    year: 2019,
    status: "finished",
    rating: 4,
    tags: ["Process", "Product"],
    desc: "Free online and worth more than most paid books on process. The appetite-over-estimate framing stuck with me.",
  },
  {
    title: "Crafting Interpreters",
    author: "Robert Nystrom",
    year: 2021,
    status: "reading",
    rating: 5,
    tags: ["Languages", "Compilers"],
    desc: "Working through the second half slowly. Writing a bytecode VM by hand demystifies a lot of things you otherwise take on faith.",
  },
  {
    title: "The Design of Everyday Things",
    author: "Don Norman",
    year: 1988,
    status: "finished",
    rating: 4,
    tags: ["Design"],
    desc: "Affordances and signifiers, applied to doors and then to everything else. I think about this book every time an error message says only 'invalid input'.",
  },
  {
    title: "Staff Engineer",
    author: "Will Larson",
    year: 2021,
    status: "queued",
    rating: 0,
    tags: ["Career", "Leadership"],
    desc: "On the shelf. Picked it up after a conversation about what the next step looks like when it is no longer about writing more code.",
  },
];

/* ---------- Hobby projects (skeleton — design later) ---------- */
const HOBBIES = [
  { icon: "◈", title: "Placeholder One",   status: "active", desc: "Short description goes here. Replace when the real content is ready." },
  { icon: "◐", title: "Placeholder Two",   status: "paused", desc: "Short description goes here. Replace when the real content is ready." },
  { icon: "▲", title: "Placeholder Three", status: "active", desc: "Short description goes here. Replace when the real content is ready." },
  { icon: "◇", title: "Placeholder Four",  status: "idea",   desc: "Short description goes here. Replace when the real content is ready." },
];
