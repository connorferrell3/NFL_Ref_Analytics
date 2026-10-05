# NFL Referee Crew Analytics — Project Plan

## 1. Goal
A dashboard that answers, for any NFL referee crew:
1. **What do they call?** Volume, yardage and mix of penalties, adjusted for the teams they officiate.
2. **How do teams fare with them?** Straight-up and against-the-spread records by team × crew.
3. **Is there a betting angle?** ATS and over/under tendencies, with honest uncertainty.
4. **What's coming this week?** Upcoming assignments joined to each crew's profile.

The analytical stance throughout: **separate persistent tendencies from noise.** Most published "referee betting trends" are small-sample artifacts. The dashboard's job is to show that difference clearly, not to hide it.

## 2. Data sources

| Need | Source | Notes |
|---|---|---|
| Games, scores, referee, closing spread/total/moneyline | nflverse `load_schedules` | Referee filled 1999+. One table covers results and betting. |
| Full 7-person crews | nflverse `load_officials` | 2015+ only, keyed by old GSIS game id → mapped to `game_id`. |
| Penalties (type, team, yards, status) | nflverse `load_pbp` → parsed from `desc` | See §4.1. |
| Weekly assignments (before nflverse has them) | Football Zebras (manual CSV for now) | `data/manual/assignments.csv` |
| *(future)* Opening lines, line movement, public % | Paid odds feed (e.g. The Odds API, SportsDataIO) | Needed to evaluate "ref news moves the line" ideas. |

**Analysis window:** 2015 onward by default (officials data begins then; modern rules era). The dashboard lets you widen or narrow it.

## 3. Architecture

```
nflverse ──► ingest.py ──► data/raw/*.parquet
                              │
                              ▼
                       transform.py  ──► data/processed/
                       (marts)            flags, games, team_games, officials, upcoming
                              │
                              ▼
           metrics.py + stats.py (aggregation, shrinkage, FDR, stability)
                              │
                              ▼
                   app/dashboard.py (Streamlit + Plotly)
```

- Parquet files plus pandas are enough at this scale (~3k games, ~46k flags). Move to DuckDB or Postgres only if we add play-level modeling or multi-user hosting.
- Refresh: run `make refresh` (or the two module commands) weekly on Tuesday, after Monday Night Football. A scheduled job can do it later.

## 4. Data science methodology

### 4.1 Measuring penalties correctly
- nflverse's `penalty == 1` marks **only the enforced foul** on each play. Declined and offsetting flags (about 12% of all flags) are invisible there, so we regex-parse every flag from the play description. Validated: parsed accepted counts match `penalty == 1` within about 0.3% per season.
- 2024+ kickoff administrative fouls ("short of landing zone") are excluded on purpose because they are not judgment calls.
- Penalty types are mapped to 8 categories (`config.PENALTY_GROUPS`). About 0.1% of flags are left in "Other".
- Metrics: flags thrown, accepted penalties, penalty yards, home-minus-away penalties, and category mix indexed to the league (100 = average).

### 4.2 Controlling for opponents
Raw crew penalty rates are confounded by which teams a crew draws.
- **v1 (built):** residual = game penalties − (home team-season avg + away team-season avg).
- **v2:** Poisson/negative-binomial GLMM: `penalties ~ offense_team_season + defense_team_season + home + (1 | referee) + (1 | official)`. This also separates individual officials (e.g. a back judge who calls a lot of DPI) from the referee.

### 4.3 Small samples → shrinkage
About 17 games per crew-season. All crew rates go through empirical-Bayes shrinkage:
- Binary outcomes (ATS, O/U, win): beta-binomial, method-of-moments prior.
- Continuous outcomes (penalties/game): normal-normal with pooled within-crew variance.
- We report the **reliability** weight so users can see how much of a split is believed.

### 4.4 Multiple comparisons
17 crews × 3 markets × N seasons × 32 teams adds up to thousands of implicit tests. We report Wilson 95% intervals plus Benjamini–Hochberg q-values. Team × crew splits get a standing warning.

### 4.5 The key validation: persistence
For each metric, correlate crew value in season *t* with season *t+1* (2015–2025, 156 crew-season pairs):

| Metric | YoY r | 95% CI | Verdict |
|---|---|---|---|
| Penalty yards / game | 0.45 | 0.31–0.57 | **Real tendency** |
| Flags thrown / game | 0.39 | 0.25–0.52 | **Real tendency** |
| Accepted penalties / game | 0.37 | 0.22–0.49 | **Real tendency** |
| Penalties vs. team-expected | 0.24 | 0.09–0.38 | **Real, smaller** |
| Home − away penalties | −0.08 | −0.23–0.08 | Noise |
| Home win % | 0.07 | −0.09–0.23 | Noise |
| Home ATS % | −0.03 | −0.18–0.13 | Noise |
| Over % | −0.09 | −0.24–0.07 | Noise |
| Total vs. closing line | −0.11 | −0.27–0.04 | Noise |

The empirical-Bayes fit agrees: the spread between crews in ATS and over/under rates is no bigger than coin-flip noise would produce, so every crew shrinks to the league rate. Even Bill Vinovich's 69–100 home ATS record (40.8%) has q = 0.51.

**Implication:** the strongest product is the *penalty* profile. Betting views are framed as descriptive, with uncertainty always visible.

### 4.6 Where a real betting edge could exist (research backlog)
These are testable hypotheses, evaluated only **out-of-sample** (train ≤ season *t*, test season *t+1*, compared to closing-line value):
1. **Penalty volume → totals.** Do high-flag crews lower or raise scoring once team pace is controlled for? Mechanism: penalties stop the clock and extend drives, but also kill drives.
2. **Crew × team-style interaction.** For example, a crew heavy on DPI calls paired with a deep-passing offense, or a crew heavy on holding calls paired with a weak offensive line.
3. **Market reaction.** Does the line move when assignments are announced (Wed/Thu)? This needs opening and mid-week line data. If the market already prices crews, there's no edge.
4. **Penalty props** (team total penalties, first-half flags) are the most direct use of a persistent tendency, and the market there is likely less efficient.

### 4.7 Known caveats
- Neutral-site and international games are recorded with a nominal "home" team.
- Crews are reshuffled each off-season. Since 2023 the league mixes officials more aggressively, which weakens "crew" as a unit and makes the official-level model (v2) more important.
- Closing lines only; no line-shopping or vig variation is modeled.
- Postseason crews are all-star crews, so they are excluded by default.

## 5. Dashboard (built in v1)
| Tab | Content |
|---|---|
| Leaderboard | All crews: flags, penalties, yards, team-adjusted (shrunk), home bias, SU/ATS/O-U |
| Crew Profile | KPIs, penalty mix vs. league, season trend, top penalties, current crew roster, game log |
| Team × Crew | Pick a team: SU/ATS/O-U and penalty differential with every referee, CI plot |
| Betting | ATS / over / favorite-cover caterpillar plots: observed + CI + shrunk, breakeven lines, q-values |
| This Week | Upcoming games + assigned crew + crew profile (manual override CSV) |
| Methodology | Year-over-year persistence chart + reading guide |

## 6. Roadmap
- **Phase 1 — Foundation (done):** ingestion, flag parser, marts, shrinkage, dashboard v1.
- **Phase 2 — Better attribution:** GLMM with team-season and per-official effects; credit the individual official who threw the flag (where play text and officials data allow it).
- **Phase 3 — Assignments automation:** scrape Football Zebras weekly crew assignments; scheduled Tuesday/Thursday refresh.
- **Phase 4 — Betting research:** acquire opening lines; run the out-of-sample tests in §4.6; only surface a "signal" badge for things that pass.
- **Phase 5 — Deployment:** Streamlit Community Cloud or a container; cache processed parquet in object storage.
