# Alexandria

An autonomous personalized book curator: it crawls the bookstores you track, shortlists books against your
taste, checks what readers and critics say, publishes one pick a day as a page on your blog, and learns from
your reactions.

- Design: https://nguyendangkhoa.info/blogs/autonomous-book-curator-system-design.html
- Build guide: https://nguyendangkhoa.info/blogs/autonomous-book-curator-hands-on.html

## Run it locally in five minutes (no keys, $0)

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt
eval "$(python -m alexandria dev-db)"        # local Postgres, prints DATABASE_URL
python -m alexandria db-init
python -m alexandria owner-key               # keep the printed key
python -m alexandria seed
python -m alexandria sites                   # robots.txt decides crawl or link-only
python -m alexandria discover --cap 6        # polite crawl, ~7 minutes
python -m alexandria nightly --fake --no-crawl
python -m alexandria publish --blog-dir ./out
python -m unittest discover -s tests -t .    # 33 tests
```

## Commands

| Command | When |
|---|---|
| `db-init` | once, and after pulling schema changes (safe to rerun) |
| `owner-key` | once; again to rotate the key |
| `seed` | once |
| `sites` | after adding a site, or any time |
| `discover [--cap N] [--llm]` | part of `nightly`; run alone to test a site |
| `nightly [--fake] [--no-crawl] [--date D]` | 00:00 ICT by GitHub Actions |
| `publish [--blog-dir DIR] [--date D]` | 07:00 ICT by GitHub Actions |
| `learn [--weekly]` | part of `nightly` |
| `status` | any time |

## Layout

```text
alexandria/       pipeline: crawl, extract, discover, shortlist, review, publish, learn, gateway, tasks
alexandria/templates/  daily page, index, console, CSS
config/           seeds.yaml (starting tastes and sites), routes.yaml (AI gateway)
db/schema.sql     tables, row level security, owner-only functions
.github/workflows/alexandria.yml   the two daily runs
tests/            33 offline tests (fixtures are real pages saved on Nov 2, 2026)
```
