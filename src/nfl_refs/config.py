"""Project-wide constants: paths, analysis window, penalty taxonomy, betting math."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MANUAL_DIR = DATA_DIR / "manual"

# nflverse officials rosters start in 2015; it is also a sensible "modern rules" cutoff
# (2015 PAT move, 2018 roughing-the-passer emphasis, 2023+ crew mixing).
FIRST_SEASON = 2015

# Standard -110 juice: you must win 110/210 = 52.38% of ATS / O-U bets to break even.
BREAKEVEN_RATE = 110 / 210

# Columns pulled from play-by-play (it has ~370; we only need these).
PBP_COLUMNS = [
    "game_id", "play_id", "season", "week", "season_type", "qtr",
    "home_team", "away_team", "posteam", "defteam", "play_type",
    "penalty", "penalty_team", "penalty_type", "penalty_yards", "desc",
]

# Penalty taxonomy. Anything unmapped falls into "Other".
PENALTY_GROUPS = {
    "Pre-snap / procedural": [
        "False Start", "Defensive Offside", "Offside on Free Kick", "Encroachment",
        "Neutral Zone Infraction", "Delay of Game", "Illegal Formation", "Illegal Shift",
        "Illegal Motion", "Defensive Delay of Game", "Too Many Men on Field",
        "Defensive Too Many Men on Field", "Offensive Too Many Men on Field",
        "Illegal Substitution", "Delay of Kickoff", "Defensive 12 On-field",
        "Offensive 12 On-field",
    ],
    "Passing rules": [
        "Ineligible Downfield Pass", "Intentional Grounding", "Illegal Forward Pass",
        "Illegal Touch Pass",
    ],
    "Special teams": [
        "Player Out of Bounds on Kick", "Player Out of Bounds on Punt", "Fair Catch Interference",
        "Kick Catch Interference", "Illegal Touch Kick", "Ineligible Downfield Kick",
        "Invalid Fair Catch Signal", "Illegal Kick/Kicking Loose Ball",
    ],
    "Holding": ["Offensive Holding", "Defensive Holding"],
    "Pass interference / coverage": [
        "Defensive Pass Interference", "Offensive Pass Interference", "Illegal Contact",
        "Illegal Use of Hands",
    ],
    "Player safety / personal fouls": [
        "Unnecessary Roughness", "Roughing the Passer", "Face Mask", "Face Mask (15 Yards)",
        "Horse Collar Tackle", "Lowering the Head to Make Forcible Contact", "Hip Drop Tackle",
        "Lowering the Head to Initiate Contact", "Roughing the Kicker", "Running Into the Kicker",
        "Illegal Blindside Block", "Clipping", "Chop Block", "Tripping", "Lowering the Head to Make Contact",
        "Illegal Crackback", "Leverage", "Leaping", "Illegal Peelback",
    ],
    "Unsportsmanlike / taunting": [
        "Unsportsmanlike Conduct", "Taunting", "Disqualification", "Fighting",
        "Personal Foul",
    ],
    "Blocking (non-holding)": [
        "Illegal Block Above the Waist", "Offensive Offside", "Illegal Low Block",
        "Low Block", "Illegal Double-Team Block",
    ],
}
PENALTY_TO_GROUP = {p.lower(): g for g, ps in PENALTY_GROUPS.items() for p in ps}
