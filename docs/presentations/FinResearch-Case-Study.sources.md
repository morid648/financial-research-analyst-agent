# Deck sources — FinResearch Case Study

> Companion to `FinResearch-Case-Study.pptx`. Every number or claim on a slide traces to one of the sources below.

**Audience**: Recruiter / hiring panel
**Narrative spine**: Context → Tension → Insight → Implication → Decision → Action (user-specified custom framework)
**Design profile**: Ported directly from the live product's own design system (`static/css/style.css`, light theme) — Georgia (serif display, substituting `Newsreader`), Arial (body, substituting `IBM Plex Sans`), Courier New (data/tickers, substituting `IBM Plex Mono`); background `#f7f6f3`, accent `#2f5586`, semantic gain/loss/caution `#1f7a4c` / `#b3412c` / `#92620f`. Font substitutions were required because `html2pptx` only supports web-safe fonts.

## Source map

| ID | Source | Used on |
|---|---|---|
| S1 | `docs/ROOT_CAUSE_ANALYSIS.md` — 17-finding severity table, root-cause themes | Slides 4, 6, 7 |
| S2 | `docs/ROOT_CAUSE_ANALYSIS.md` finding #7 — Utique Enterprises D/E (1.41 → 0.01), cross-checked against Screener.in | Slide 5 |
| S3 | `docs/ROOT_CAUSE_ANALYSIS.md` findings #2–#5 — Altman Z-Score, ROCE, Interest Coverage, Cash Conversion Cycle were hardcoded placeholder strings | Slide 6 |
| S4 | This session's ponytail repo-wide audit and its execution (frontend/, scratch/, `persistence.py`, `security.py`, `rag_mixin.py` deleted; `sqlalchemy`, `psycopg2-binary`, `alembic`, `redis`, `streamlit` dropped; `db`/`redis` Docker services retired) — exact line counts re-derived via `wc -l` for this deck (10,044 + 697 + 281 + 192 + 246 = 11,460) rather than reused from an earlier rough estimate | Slide 8 |
| S5 | `README.md` — product capability list (ratios/DCF/risk/sentiment), zero-paid-API-key claim, NSE/BSE/US coverage | Slide 2 |
| S6 | Live redesign of `static/*` this session — before: 3 accent colors + glassmorphism/glow; after: 1 accent color, hairline borders, no gradients | Slide 8 |

## Deliberate omissions

- **No specific market prices are cited anywhere in the deck.** Numbers pulled from this session's live testing (e.g. a specific AAPL price) came from a sandboxed data feed tied to the environment's simulated date and are not verifiable real-world facts. Only *structural* correctness claims (a ratio was 100x off; a formula was hardcoded) are used, since those are true regardless of what the market is doing on any given day.
- **No fabricated URLs.** The live-demo link, GitHub link, and presenter name are left as bracketed placeholders (`[ live demo URL ]`, `[ GitHub URL ]`, `[ Your Name ]`) for you to fill in — none were invented.

## Known limitation in this build

LibreOffice/Poppler aren't installed on the machine this was built on, so slides 1–3, 5–8, and 10 were verified with pixel-accurate Playwright screenshots of the source HTML (the same render `html2pptx` measures from), but slides 4 (bar chart) and 9 (table) could only be verified structurally — via `python-pptx`, confirming correct categories/values/colors and correct table contents/position — not by an actual rendered screenshot. Worth a 10-second glance in PowerPoint before you present.
