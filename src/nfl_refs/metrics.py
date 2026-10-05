"""Crew-level metrics consumed by the dashboard."""
import numpy as np
import pandas as pd

from .config import PROCESSED_DIR
from .stats import bh_qvalues, binom_pvalue, eb_mean, eb_proportion, wilson_ci, year_over_year


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / f"{name}.parquet")


def filter_games(df: pd.DataFrame, seasons: tuple[int, int], game_types: list[str]) -> pd.DataFrame:
    return df[df["season"].between(*seasons) & df["game_type"].isin(game_types)]


def _rate_block(g: pd.DataFrame, col: str, prefix: str) -> pd.DataFrame:
    """Wins/n, raw rate, Wilson CI, EB-shrunk rate, and FDR q-value for a binary outcome column."""
    out = g.groupby("referee")[col].agg(k="sum", n="count")
    out[f"{prefix}_rate"] = out["k"] / out["n"]
    out[f"{prefix}_lo"], out[f"{prefix}_hi"] = wilson_ci(out["k"], out["n"])
    out[f"{prefix}_eb"], out[f"{prefix}_rel"] = eb_proportion(out["k"], out["n"])
    out[f"{prefix}_q"] = bh_qvalues(binom_pvalue(out["k"], out["n"], 0.5))
    out[f"{prefix}_record"] = (out["k"].astype(int).astype(str) + "-" +
                               (out["n"] - out["k"]).astype(int).astype(str))
    return out.drop(columns=["k", "n"])


def team_adjusted_penalties(games: pd.DataFrame, team_games: pd.DataFrame) -> pd.Series:
    """Penalties per game relative to what the two teams involved normally commit.

    A crew that happens to draw undisciplined teams will look flag-happy on raw counts.
    Expected penalties for a game = sum of each team's season average; the residual is what
    we attribute to the crew. (v1 approach; v2 = mixed model with team-season fixed effects.)"""
    tg = team_games[team_games["game_id"].isin(games["game_id"])]
    team_avg = tg.groupby(["team", "season"])["penalties"].transform("mean")
    expected = tg.assign(exp=team_avg).groupby("game_id")["exp"].sum()
    resid = games.set_index("game_id")["penalties"] - expected
    return resid.rename("pen_resid")


def crew_summary(games: pd.DataFrame, team_games: pd.DataFrame, min_games: int = 10) -> pd.DataFrame:
    g = games.copy()
    g = g.join(team_adjusted_penalties(g, team_games), on="game_id")

    base = g.groupby("referee").agg(
        games=("game_id", "size"),
        seasons=("season", "nunique"),
        last_season=("season", "max"),
        flags_pg=("flags_thrown", "mean"),
        penalties_pg=("penalties", "mean"),
        pen_yards_pg=("penalty_yards", "mean"),
        pen_resid_pg=("pen_resid", "mean"),
        home_pen_diff_pg=("home_pen_diff", "mean"),
        avg_total=("total", "mean"),
        avg_ou_margin=("ou_margin", "mean"),
        avg_ats_margin=("ats_margin", "mean"),
    )
    base["home_win_pct"] = g.groupby("referee")["home_win"].mean()
    base = base.join(_rate_block(g, "home_cover", "home_ats"))
    base = base.join(_rate_block(g, "over", "over"))
    base = base.join(_rate_block(g, "fav_cover", "fav_ats"))

    within = g["pen_resid"].var()
    base["pen_resid_eb"], base["pen_resid_rel"] = eb_mean(base["pen_resid_pg"], base["games"], within)
    base = base[base["games"] >= min_games]
    return base.sort_values("penalties_pg", ascending=False).reset_index()


def penalty_mix(flags: pd.DataFrame, games: pd.DataFrame, min_league_rate: float = 0.25) -> pd.DataFrame:
    """Accepted penalties per game by category, per crew, indexed to league average (100 = avg).

    Rare categories (< min_league_rate per game league-wide) are dropped: with ~2 flags a season
    their index swings by hundreds of percent on pure noise."""
    f = flags[(flags["status"] == "accepted") & flags["game_id"].isin(games["game_id"])]
    league = f.groupby("group").size() / len(games)
    league = league[(league >= min_league_rate) & (league.index != "Other")]
    f = f[f["group"].isin(league.index)]
    n_games = games.groupby("referee").size()
    per_game = f.groupby(["referee", "group"]).size().unstack(fill_value=0).div(n_games, axis=0)
    index = (per_game / league * 100).round(0)
    out = per_game.stack().rename("per_game").to_frame().join(index.stack().rename("index"))
    return out.reset_index()


def top_penalty_types(flags: pd.DataFrame, games: pd.DataFrame, referee: str, n: int = 12) -> pd.DataFrame:
    f = flags[(flags["status"] == "accepted") & flags["game_id"].isin(games["game_id"])]
    ref_games = (games["referee"] == referee).sum()
    ref = f[f["referee"] == referee]["penalty_type"].value_counts() / ref_games
    league = f["penalty_type"].value_counts() / len(games)
    out = pd.DataFrame({"crew_per_game": ref, "league_per_game": league}).dropna()
    out["index"] = (out["crew_per_game"] / out["league_per_game"] * 100).round(0)
    return out.sort_values("crew_per_game", ascending=False).head(n).reset_index(names="penalty_type")


def team_vs_crew(team_games: pd.DataFrame, team: str) -> pd.DataFrame:
    t = team_games[team_games["team"] == team]
    out = t.groupby("referee").agg(
        games=("game_id", "size"), wins=("win", "sum"), covers=("cover", "sum"),
        ats_n=("cover", "count"), overs=("over", "sum"), ou_n=("over", "count"),
        pen_for=("penalties", "mean"), pen_against=("opp_penalties", "mean"),
        last_season=("season", "max"),
    )
    out["su_record"] = out["wins"].astype(int).astype(str) + "-" + (out["games"] - out["wins"]).astype(int).astype(str)
    out["ats_record"] = out["covers"].astype(int).astype(str) + "-" + (out["ats_n"] - out["covers"]).astype(int).astype(str)
    out["win_pct"] = out["wins"] / out["games"]
    out["ats_pct"] = out["covers"] / out["ats_n"]
    out["ats_lo"], out["ats_hi"] = wilson_ci(out["covers"], out["ats_n"])
    out["over_pct"] = out["overs"] / out["ou_n"]
    out["pen_diff"] = out["pen_for"] - out["pen_against"]
    return out.sort_values("games", ascending=False).reset_index()


STABILITY_METRICS = {
    "flags_thrown": "Flags thrown / game",
    "penalties": "Accepted penalties / game",
    "penalty_yards": "Penalty yards / game",
    "pen_resid": "Penalties vs. team-expected",
    "home_pen_diff": "Home - away penalties",
    "home_win": "Home win %",
    "home_cover": "Home ATS %",
    "over": "Over %",
    "ou_margin": "Total vs. closing line (pts)",
}


def stability_table(games: pd.DataFrame, team_games: pd.DataFrame) -> pd.DataFrame:
    g = games.join(team_adjusted_penalties(games, team_games), on="game_id")
    rows = [year_over_year(g, m) | {"label": lbl} for m, lbl in STABILITY_METRICS.items()]
    return pd.DataFrame(rows)
