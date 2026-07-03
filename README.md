# Paul the Agent 🐙

A slick, self-grading dashboard for 2026 FIFA World Cup predictions — the
spiritual successor to Paul the Octopus, only this one shows its work. An
ensemble model (Dixon–Coles + Elo + momentum) locks a scoreline **before**
kickoff, then grades itself against real results — no hindsight, no edits.

**Live site:** https://nakashon.github.io/paul-the-agent/

## What it shows

- **Live scorecard** — points captured, outcome accuracy, exact-scoreline rate.
- **Predictions & results** — every locked pick vs. the actual score, colour
  coded as `Exact` / `Outcome` / `Miss`, filterable by round.
- **Futures** — long bets (champion, golden boot) locked at the start.
- **Title race** — live championship probability from tournament simulations.

## How it works

1. Predictions and results live in `data/wc2026.db` (SQLite), maintained by the
   scripts in `scripts/`.
2. `scripts/export_site.py` joins predictions against results, applies the
   stage-based scoring rules (`scoring` table), and writes `docs/data.json`.
3. `docs/` is a static site (no build step) that renders that JSON.

## Update the site after new results

```bash
python scripts/add_result.py "Home" 2 1 "Away" 4   # record a played match
python scripts/export_site.py                       # regenerate docs/data.json
```

Commit and push — the GitHub Actions workflow (`.github/workflows/deploy.yml`)
regenerates the data and deploys to GitHub Pages automatically.

## Local preview

```bash
cd docs && python -m http.server 8000
# open http://localhost:8000
```

## Scoring

| Stage | Correct outcome | Exact score |
|-------|-----------------|-------------|
| Group | 1 | 3 |
| Round of 32 | 2 | 5 |
| Round of 16 | 2 | 5 |
| Quarter-final | 4 | 8 |
| Semi-final | 5 | 10 |
| Final | 8 | 15 |

Futures: champion and golden boot worth 12 pts each.
