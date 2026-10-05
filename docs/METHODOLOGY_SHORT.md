#### How to read this dashboard

- **Crew = the referee's crew.** The referee is the stable identifier, but the other six officials are reshuffled every off-season, so "crew history" mostly means "referee history".
- **Flags are parsed from play text.** nflverse's `penalty` column only tracks the enforced foul on each play, so it misses declined flags. Administrative kickoff fouls (2024+) are excluded because they are automatic, not judgment calls.
- **"Vs. expected" adjusts for the teams.** A crew that draws undisciplined teams will look flag-happy on raw counts. We subtract each team's season penalty average.
- **Shrinkage.** A crew works about 17 games a year. Every crew-level rate is pulled toward the league average in proportion to how noisy it is (empirical Bayes). *Reliability* is the share of a crew's raw deviation we believe is real.
- **Multiple testing.** With about 17 crews × 3 markets, a couple of "significant" ATS splits show up by chance every year. We report Benjamini–Hochberg q-values.
- **Betting lines are closing lines** from nflverse. ATS pushes are excluded. Breakeven at -110 is 52.38%.

**Bottom line (2015–present, regular season):** crews differ reliably in *how many* penalties they call (year-over-year r ≈ 0.4) and somewhat in *which* ones. Home-team ATS, over/under, and home win rates by crew show no persistence (r ≈ 0), and none survive the false-discovery correction. Treat crew betting splits as descriptive trivia unless a future model shows out-of-sample value.
