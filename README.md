# NFL Referee Crew Analytics

A dashboard covering NFL referee crews: what penalties they call, how teams fare with them, and their against-the-spread (ATS) and over/under history. The statistics are built to separate real crew tendencies from small-sample noise.

See **[docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)** for data sources, methodology, findings and the roadmap.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make refresh        # pull nflverse data (2015 to now) and build tables, about 2 min
make app            # open the dashboard at http://localhost:8501
```

## Layout

```
src/nfl_refs/
  config.py      paths, analysis window, penalty taxonomy
  ingest.py      nflverse → data/raw/*.parquet
  transform.py   flag parser + marts → data/processed/*.parquet
  stats.py       Wilson CIs, empirical-Bayes shrinkage, BH q-values, year-over-year stability
  metrics.py     crew/team aggregations used by the app
app/dashboard.py Streamlit dashboard
docs/            project plan & methodology
data/manual/     assignments.csv override for this week's crews (game_id,referee)
tests/           unit tests (flag parser, stats)
```

## Headline finding so far
Crews differ reliably in **how many penalties they call**: a crew's penalty rate one season correlates with the next season's at r ≈ 0.4. Crew ATS, over/under and home-win splits **do not carry over from year to year** (r ≈ 0), and none hold up after correcting for testing many crews at once. The dashboard shows both, with uncertainty always visible.
