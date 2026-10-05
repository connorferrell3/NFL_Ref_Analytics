import numpy as np
import pandas as pd

from nfl_refs.stats import bh_qvalues, eb_proportion, wilson_ci
from nfl_refs.transform import parse_flags


def _pbp(desc):
    return pd.DataFrame([{
        "game_id": "g", "play_id": 1, "season": 2025, "week": 1, "qtr": 1,
        "home_team": "DAL", "away_team": "PHI", "posteam": "DAL", "desc": desc}])


def test_parse_flags_accepted_and_declined():
    f = parse_flags(_pbp("PENALTY on DAL-35-M.Liufau, Unnecessary Roughness, 12 yards, enforced at DAL 24. "
                         "Penalty on DAL-14-M.Bell, Unnecessary Roughness, declined."))
    assert list(f["status"]) == ["accepted", "declined"]
    assert f["yards"].tolist() == [12, 0]
    assert f["is_home_team"].all() and (f["side"] == "offense").all()


def test_parse_flags_team_only_and_offsetting():
    f = parse_flags(_pbp("PENALTY on PHI, Defensive Offside, 5 yards. Penalty on DAL-70-Z.Martin, Offensive Holding, offsetting."))
    assert f["penalty_team"].tolist() == ["PHI", "DAL"]
    assert f["status"].tolist() == ["accepted", "offsetting"]
    assert f["group"].tolist() == ["Pre-snap / procedural", "Holding"]


def test_kickoff_admin_fouls_excluded():
    f = parse_flags(_pbp("PENALTY on BAL-33-T.Loop, Kickoff Short of Landing Zone, placed at BUF 40."))
    assert f.empty or len(f) == 0


def test_wilson_contains_point_estimate():
    lo, hi = wilson_ci(np.array([7]), np.array([10]))
    assert lo[0] < 0.7 < hi[0]


def test_eb_shrinks_pure_noise_to_mean():
    rng = np.random.default_rng(0)
    n = np.full(20, 150)
    k = rng.binomial(n, 0.5)
    shrunk, rel = eb_proportion(k, n)
    assert np.ptp(shrunk) < np.ptp(k / n) / 2  # strong shrinkage when there's no real spread


def test_bh_monotone_and_bounded():
    q = bh_qvalues([0.01, 0.04, 0.03, 0.5])
    assert (q >= np.array([0.01, 0.04, 0.03, 0.5])).all() and (q <= 1).all()
