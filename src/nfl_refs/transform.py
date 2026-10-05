"""Build analysis-ready tables ("marts") from raw nflverse data.

Outputs (data/processed/):
  flags.parquet       one row per flag thrown (accepted, declined, offsetting)
  games.parquet       one row per completed game: crew, result, betting outcomes, flag counts
  team_games.parquet  two rows per game (one per team): team-perspective outcomes
  officials.parquet   crew rosters keyed to nflverse game_id
"""
import re

import numpy as np
import pandas as pd

from .config import PENALTY_TO_GROUP, PROCESSED_DIR, RAW_DIR

# nflverse's `penalty` column only marks the single enforced foul on a play, so declined and
# offsetting flags are invisible there (~450 declined flags in 2025 alone). We parse every flag
# from the play description instead. Example fragments:
#   "PENALTY on NO, Illegal Shift, 5 yards, enforced at ..."
#   "Penalty on DAL-14-M.Bell, Unnecessary Roughness, declined."
# Deliberately NOT matched: 2024+ kickoff administrative fouls ("..., Kickoff Short of Landing
# Zone, placed at BUF 40"). They are automatic spot fouls, not officiating judgment calls.
FLAG_RE = re.compile(
    r"PENALTY on (?P<team>[A-Z]{2,3})(?:-[^,]*)?,\s*(?P<type>[^,]+?),\s*"
    r"(?P<outcome>declined|offsetting|-?\d+ yards?)",
    re.IGNORECASE,
)


def parse_flags(pbp: pd.DataFrame) -> pd.DataFrame:
    plays = pbp[pbp["desc"].str.contains("penalty on", case=False, na=False)]
    rows = []
    for play in plays.itertuples(index=False):
        for m in FLAG_RE.finditer(play.desc):
            outcome = m["outcome"].lower()
            status = "declined" if outcome == "declined" else "offsetting" if outcome == "offsetting" else "accepted"
            rows.append({
                "game_id": play.game_id, "play_id": play.play_id, "season": play.season,
                "week": play.week, "qtr": play.qtr, "home_team": play.home_team,
                "away_team": play.away_team, "posteam": play.posteam,
                "penalty_team": m["team"].upper(), "penalty_type": m["type"].strip(),
                "status": status,
                "yards": int(outcome.split()[0]) if status == "accepted" else 0,
            })
    flags = pd.DataFrame(rows, columns=[
        "game_id", "play_id", "season", "week", "qtr", "home_team", "away_team", "posteam",
        "penalty_team", "penalty_type", "status", "yards"])
    # Team abbreviations in play text can differ from nflverse codes for relocated teams (e.g. JAC/JAX).
    flags["penalty_team"] = flags["penalty_team"].replace({"JAC": "JAX", "SD": "LAC", "STL": "LA", "OAK": "LV", "LAR": "LA"})
    flags["is_home_team"] = flags["penalty_team"] == flags["home_team"]
    flags["side"] = np.where(flags["penalty_team"] == flags["posteam"], "offense", "defense")
    flags["group"] = flags["penalty_type"].str.lower().map(PENALTY_TO_GROUP).fillna("Other")
    return flags


def build_games(sched: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    g = sched[sched["result"].notna() & sched["referee"].notna()].copy()

    # nflverse conventions: result = home - away; spread_line > 0 means home favored by that many.
    g["home_win"] = np.where(g["result"] > 0, 1.0, np.where(g["result"] < 0, 0.0, 0.5))
    ats_margin = g["result"] - g["spread_line"]
    g["home_cover"] = np.where(ats_margin > 0, 1.0, np.where(ats_margin < 0, 0.0, np.nan))  # push -> NaN
    g["fav_is_home"] = g["spread_line"] > 0
    g["fav_cover"] = np.where(g["spread_line"] == 0, np.nan,
                              np.where(g["fav_is_home"], g["home_cover"], 1 - g["home_cover"]))
    ou_margin = g["total"] - g["total_line"]
    g["over"] = np.where(ou_margin > 0, 1.0, np.where(ou_margin < 0, 0.0, np.nan))
    g["ats_margin"], g["ou_margin"] = ats_margin, ou_margin

    acc = flags[flags["status"] == "accepted"]
    agg = flags.groupby("game_id").agg(
        flags_thrown=("status", "size"),
        flags_declined=("status", lambda s: (s == "declined").sum()),
    ).join(acc.groupby("game_id").agg(
        penalties=("status", "size"),
        penalty_yards=("yards", "sum"),
        home_penalties=("is_home_team", "sum"),
    ))
    agg["away_penalties"] = agg["penalties"] - agg["home_penalties"]
    by_group = acc.pivot_table(index="game_id", columns="group", values="play_id", aggfunc="size", fill_value=0)
    by_group.columns = [f"pen_{c}" for c in by_group.columns]

    g = g.merge(agg, on="game_id", how="left").merge(by_group, on="game_id", how="left")
    count_cols = [c for c in g.columns if c.startswith("pen_")] + [
        "flags_thrown", "flags_declined", "penalties", "penalty_yards", "home_penalties", "away_penalties"]
    g[count_cols] = g[count_cols].fillna(0)
    # Positive = home team penalized more than the away team.
    g["home_pen_diff"] = g["home_penalties"] - g["away_penalties"]
    keep = ["game_id", "season", "game_type", "week", "gameday", "home_team", "away_team",
            "home_score", "away_score", "result", "total", "overtime", "spread_line", "total_line",
            "home_moneyline", "away_moneyline", "div_game", "roof", "referee", "home_win",
            "home_cover", "fav_is_home", "fav_cover", "over", "ats_margin", "ou_margin", "old_game_id"]
    return g[keep + count_cols + ["home_pen_diff"]]


def build_team_games(games: pd.DataFrame) -> pd.DataFrame:
    """Long format: each game appears twice, once from each team's perspective."""
    base = ["game_id", "season", "game_type", "week", "referee", "total", "total_line", "over"]
    home = games[base].assign(
        team=games["home_team"], opponent=games["away_team"], is_home=True,
        points_for=games["home_score"], points_against=games["away_score"],
        win=games["home_win"], cover=games["home_cover"], spread=-games["spread_line"],
        penalties=games["home_penalties"], opp_penalties=games["away_penalties"])
    away = games[base].assign(
        team=games["away_team"], opponent=games["home_team"], is_home=False,
        points_for=games["away_score"], points_against=games["home_score"],
        win=1 - games["home_win"], cover=1 - games["home_cover"], spread=games["spread_line"],
        penalties=games["away_penalties"], opp_penalties=games["home_penalties"])
    # `spread` is from the team's perspective in betting notation: negative = team favored.
    return pd.concat([home, away], ignore_index=True)


def build_officials(officials: pd.DataFrame, sched: pd.DataFrame) -> pd.DataFrame:
    """Officials use the old 10-digit GSIS game id; map it to the nflverse game_id."""
    key = sched[["game_id", "old_game_id"]].dropna().astype({"old_game_id": str})
    off = officials.astype({"game_id": str}).rename(columns={"game_id": "old_game_id"})
    return off.merge(key, on="old_game_id", how="inner")


def run() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    sched = pd.read_parquet(RAW_DIR / "schedules.parquet")
    pbp = pd.read_parquet(RAW_DIR / "pbp.parquet")
    officials = pd.read_parquet(RAW_DIR / "officials.parquet")

    flags = parse_flags(pbp)
    games = build_games(sched, flags)
    flags = flags.merge(games[["game_id", "referee", "game_type"]], on="game_id", how="inner")

    flags.to_parquet(PROCESSED_DIR / "flags.parquet", index=False)
    games.to_parquet(PROCESSED_DIR / "games.parquet", index=False)
    build_team_games(games).to_parquet(PROCESSED_DIR / "team_games.parquet", index=False)
    build_officials(officials, sched).to_parquet(PROCESSED_DIR / "officials.parquet", index=False)
    # Upcoming games (no result yet) power the "This Week" view.
    upcoming = sched[sched["result"].isna()]
    upcoming.to_parquet(PROCESSED_DIR / "upcoming.parquet", index=False)
    print(f"{len(games):,} games, {len(flags):,} flags written to {PROCESSED_DIR}")


if __name__ == "__main__":
    run()
