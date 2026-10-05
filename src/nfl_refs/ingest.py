"""Pull raw data from nflverse and cache it as parquet in data/raw/."""
import nflreadpy as nfl
import pandas as pd

from .config import FIRST_SEASON, PBP_COLUMNS, RAW_DIR


def _seasons(first: int = FIRST_SEASON) -> list[int]:
    return list(range(first, nfl.get_current_season() + 1))


def pull_schedules(seasons: list[int]) -> pd.DataFrame:
    """One row per game: teams, scores, referee, closing spread/total/moneylines."""
    return nfl.load_schedules(seasons).to_pandas()


def pull_officials(seasons: list[int]) -> pd.DataFrame:
    """One row per official per game (7 on-field officials + replay/alternates). 2015+ only."""
    return nfl.load_officials(seasons).to_pandas()


def pull_pbp(seasons: list[int]) -> pd.DataFrame:
    """Play-by-play, trimmed to the columns we need for penalty analysis."""
    frames = []
    for s in seasons:
        df = nfl.load_pbp([s]).select(PBP_COLUMNS).to_pandas()
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def run(first_season: int = FIRST_SEASON) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seasons = _seasons(first_season)
    print(f"Pulling seasons {seasons[0]}-{seasons[-1]}")
    pull_schedules(seasons).to_parquet(RAW_DIR / "schedules.parquet", index=False)
    pull_officials(seasons).to_parquet(RAW_DIR / "officials.parquet", index=False)
    pull_pbp(seasons).to_parquet(RAW_DIR / "pbp.parquet", index=False)
    print(f"Raw data written to {RAW_DIR}")


if __name__ == "__main__":
    run()
