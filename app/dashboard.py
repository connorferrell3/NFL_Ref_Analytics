"""NFL Referee Crew dashboard.  Run:  streamlit run app/dashboard.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from nfl_refs import metrics as M
from nfl_refs.config import BREAKEVEN_RATE, MANUAL_DIR

st.set_page_config(page_title="NFL Referee Crews", page_icon="🏈", layout="wide")


@st.cache_data
def load_all():
    return {n: M.load(n) for n in ["games", "team_games", "flags", "officials", "upcoming"]}


D = load_all()
games_all, team_games_all, flags_all = D["games"], D["team_games"], D["flags"]
min_s, max_s = int(games_all["season"].min()), int(games_all["season"].max())

# ---------------- Sidebar filters ----------------
st.sidebar.title("Filters")
seasons = st.sidebar.slider("Seasons", min_s, max_s, (max(min_s, max_s - 4), max_s))
game_types = st.sidebar.multiselect("Game types", ["REG", "WC", "DIV", "CON", "SB"], default=["REG"])
min_games = st.sidebar.number_input("Min games for a crew", 1, 200, 15)
active_only = st.sidebar.checkbox("Only crews active this season", True)

games = M.filter_games(games_all, seasons, game_types)
team_games = M.filter_games(team_games_all, seasons, game_types)
flags = flags_all[flags_all["game_id"].isin(games["game_id"])]
summary = M.crew_summary(games, team_games, min_games=min_games)
if active_only:  # judged on all data, so a past-seasons window still shows today's crews
    summary = summary[summary["referee"].isin(games_all.loc[games_all["season"] == max_s, "referee"])]

st.title("🏈 NFL Referee Crew Analytics")
st.caption(f"{len(games):,} games · {seasons[0]}–{seasons[1]} · {', '.join(game_types)} · "
           f"crew = referee's crew (nflverse). League avg: {games['penalties'].mean():.1f} accepted penalties/game, "
           f"home ATS {games['home_cover'].mean():.1%}, overs {games['over'].mean():.1%}.")

tabs = st.tabs(["Leaderboard", "Crew Profile", "Team × Crew", "Betting", "This Week", "Methodology"])

pct = lambda s: s.map(lambda v: f"{v:.1%}" if pd.notna(v) else "—")

# ---------------- Leaderboard ----------------
with tabs[0]:
    st.subheader("Crew leaderboard")
    st.markdown("**Penalty tendencies are persistent and real; betting splits mostly are not** — see *Methodology*. "
                "`vs expected` adjusts for the teams a crew happened to work, and is shrunk toward league average.")
    view = summary.assign(
        **{"Flags/g": summary["flags_pg"].round(1), "Pens/g": summary["penalties_pg"].round(1),
           "Pen yds/g": summary["pen_yards_pg"].round(0),
           "Pens vs expected": summary["pen_resid_eb"].round(2),
           "Home−away pens": summary["home_pen_diff_pg"].round(2),
           "Home win%": pct(summary["home_win_pct"]),
           "Home ATS": summary["home_ats_record"], "O/U": summary["over_record"],
           "Over%": pct(summary["over_rate"]), "Avg total": summary["avg_total"].round(1)})
    cols = ["referee", "games", "Flags/g", "Pens/g", "Pen yds/g", "Pens vs expected", "Home−away pens",
            "Home win%", "Home ATS", "O/U", "Over%", "Avg total"]
    st.dataframe(view[cols].sort_values("Pens vs expected", ascending=False), hide_index=True, width="stretch")

    s = summary.sort_values("pen_resid_eb")
    fig = px.bar(s, x="pen_resid_eb", y="referee", orientation="h",
                 color="pen_resid_eb", color_continuous_scale="RdBu_r", color_continuous_midpoint=0,
                 labels={"pen_resid_eb": "Accepted penalties/game vs. team-expected (shrunk)", "referee": ""},
                 hover_data={"games": True, "pen_resid_rel": ":.2f"})
    fig.update_layout(height=max(400, 22 * len(s)), coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")

# ---------------- Crew profile ----------------
with tabs[1]:
    refs = summary.sort_values("games", ascending=False)["referee"].tolist()
    if not refs:
        st.info("No crews match the filters.")
    else:
        ref = st.selectbox("Referee", refs)
        row = summary.set_index("referee").loc[ref]
        lg = games["penalties"].mean()
        c = st.columns(5)
        c[0].metric("Games", int(row["games"]))
        c[1].metric("Penalties / game", f"{row['penalties_pg']:.1f}", f"{row['penalties_pg'] - lg:+.1f} vs lg", delta_color="off")
        c[2].metric("Vs. team-expected", f"{row['pen_resid_eb']:+.2f}", f"reliability {row['pen_resid_rel']:.0%}", delta_color="off")
        c[3].metric("Home ATS", row["home_ats_record"], f"{row['home_ats_rate']:.1%}", delta_color="off")
        c[4].metric("Over / Under", row["over_record"], f"{row['over_rate']:.1%}", delta_color="off")

        left, right = st.columns(2)
        mix = M.penalty_mix(flags, games)
        mix = mix[mix["referee"] == ref].assign(diff=lambda d: d["index"] - 100).sort_values("diff")
        fig = px.bar(mix, x="diff", y="group", orientation="h", color="diff",
                     color_continuous_scale="RdBu_r", color_continuous_midpoint=0,
                     labels={"diff": "% above/below league rate", "group": ""},
                     hover_data={"per_game": ":.2f", "index": True}, title="Penalty mix vs. league")
        fig.update_layout(coloraxis_showscale=False)
        left.plotly_chart(fig, width="stretch")

        trend = games.groupby(["season", games["referee"] == ref])["penalties"].agg(["mean", "size"]).unstack()
        trend = pd.DataFrame({"season": trend.index, ref: trend[("mean", True)],
                              "League (others)": trend[("mean", False)], "n": trend[("size", True)]})
        fig = px.line(trend, x="season", y=[ref, "League (others)"], markers=True, hover_data=["n"],
                      title="Accepted penalties / game by season (hover for crew games)",
                      labels={"value": "", "variable": ""})
        right.plotly_chart(fig, width="stretch")

        left, right = st.columns(2)
        left.markdown("**Most-called penalties** (index 100 = league rate)")
        left.dataframe(M.top_penalty_types(flags, games, ref).round(2), hide_index=True, width="stretch")

        off = D["officials"]
        latest = off[off["game_id"].isin(games_all.loc[games_all["referee"] == ref, "game_id"])]
        latest = latest[latest["season"] == latest["season"].max()]
        roster = (latest.groupby(["position", "official_name"]).size().rename("games").reset_index()
                  .sort_values(["position", "games"], ascending=[True, False]).groupby("position").head(1))
        right.markdown(f"**Most frequent crew, {latest['season'].max() if len(latest) else '—'}** "
                       "(crews are reshuffled every off-season)")
        right.dataframe(roster, hide_index=True, width="stretch")

        st.markdown("**Game log**")
        log = games[games["referee"] == ref].sort_values(["season", "week"], ascending=False)
        st.dataframe(log[["season", "week", "away_team", "home_team", "away_score", "home_score",
                          "spread_line", "total_line", "home_cover", "over", "penalties",
                          "home_penalties", "away_penalties", "penalty_yards"]], hide_index=True, width="stretch")

# ---------------- Team x Crew ----------------
with tabs[2]:
    team = st.selectbox("Team", sorted(team_games["team"].unique()))
    tvc = M.team_vs_crew(team_games, team)
    st.warning("Most team–crew pairs have fewer than 10 games. A 4-1 ATS record is entirely consistent with a coin "
               "flip. Treat this tab as context, not a signal — the 95% intervals show why.")
    st.dataframe(tvc.assign(**{"Win%": pct(tvc["win_pct"]), "ATS%": pct(tvc["ats_pct"]), "Over%": pct(tvc["over_pct"]),
                               "Pen diff/g": tvc["pen_diff"].round(2)})[
        ["referee", "games", "su_record", "Win%", "ats_record", "ATS%", "Over%", "Pen diff/g", "last_season"]],
        hide_index=True, width="stretch")
    t = tvc[tvc["ats_n"] >= 3].sort_values("ats_pct")
    fig = go.Figure(go.Scatter(
        x=t["ats_pct"], y=t["referee"], mode="markers",
        error_x=dict(type="data", symmetric=False, array=t["ats_hi"] - t["ats_pct"], arrayminus=t["ats_pct"] - t["ats_lo"]),
        text=t["ats_record"], hovertemplate="%{y}: %{text} ATS<extra></extra>"))
    fig.add_vline(x=0.5, line_dash="dash")
    fig.update_layout(title=f"{team} ATS by referee (95% CI, ≥3 games)", xaxis_tickformat=".0%",
                      height=max(350, 24 * len(t)))
    st.plotly_chart(fig, width="stretch")

# ---------------- Betting ----------------
with tabs[3]:
    st.subheader("Against the spread & totals by crew")
    st.markdown(f"Dashed line = 50%. Dotted = **{BREAKEVEN_RATE:.2%} breakeven at -110**. "
                "Hollow diamond = empirical-Bayes estimate (how much of the split we actually believe). "
                "`q` = false-discovery-adjusted p-value across all crews; q < 0.10 would be worth a look.")
    market = st.radio("Market", ["Home team ATS", "Over", "Favorite ATS"], horizontal=True)
    pref = {"Home team ATS": "home_ats", "Over": "over", "Favorite ATS": "fav_ats"}[market]
    s = summary.sort_values(f"{pref}_rate")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s[f"{pref}_rate"], y=s["referee"], mode="markers", name="Observed",
        error_x=dict(type="data", symmetric=False, array=s[f"{pref}_hi"] - s[f"{pref}_rate"],
                     arrayminus=s[f"{pref}_rate"] - s[f"{pref}_lo"]),
        text=s[f"{pref}_record"], hovertemplate="%{y}: %{text}<extra></extra>"))
    fig.add_trace(go.Scatter(x=s[f"{pref}_eb"], y=s["referee"], mode="markers", name="Shrunk estimate",
                             marker=dict(symbol="diamond-open", size=10)))
    fig.add_vline(x=0.5, line_dash="dash")
    for x in (BREAKEVEN_RATE, 1 - BREAKEVEN_RATE):
        fig.add_vline(x=x, line_dash="dot", line_color="gray")
    fig.update_layout(xaxis_tickformat=".0%", height=max(400, 24 * len(s)))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(s[["referee", "games", f"{pref}_record", f"{pref}_rate", f"{pref}_eb", f"{pref}_q",
                    "avg_ats_margin", "avg_ou_margin"]].round(3), hide_index=True, width="stretch")

# ---------------- This week ----------------
with tabs[4]:
    up = D["upcoming"]
    manual = MANUAL_DIR / "assignments.csv"
    if manual.exists():  # game_id,referee — fill in from Football Zebras when nflverse lags
        up = up.drop(columns="referee").merge(pd.read_csv(manual), on="game_id", how="left")
    if up.empty:
        st.info("No upcoming games in the data.")
    else:
        wk = up[up["week"] == up["week"].min()]
        st.subheader(f"{int(wk['season'].iloc[0])} week {int(wk['week'].iloc[0])}")
        st.caption("Crew assignments are typically published mid-week. Unassigned games show TBA; you can add them in "
                   "`data/manual/assignments.csv`.")
        allsum = M.crew_summary(M.filter_games(games_all, (max_s - 4, max_s), ["REG"]), team_games_all, min_games=1)
        wk = wk.merge(allsum[["referee", "penalties_pg", "pen_resid_eb", "home_ats_record", "over_record"]],
                      on="referee", how="left")
        wk["referee"] = wk["referee"].fillna("TBA")
        st.dataframe(wk[["gameday", "away_team", "home_team", "spread_line", "total_line", "referee",
                         "penalties_pg", "pen_resid_eb", "home_ats_record", "over_record"]].round(2),
                     hide_index=True, width="stretch")

# ---------------- Methodology ----------------
with tabs[5]:
    st.subheader("Is it signal or noise? Year-over-year persistence")
    st.markdown("For each metric we correlate a crew's value in season *t* with the same crew in season *t+1*. "
                "A real crew tendency persists (r clearly > 0). If r ≈ 0, last year's split tells you nothing "
                "about this year's — no matter how extreme it looked.")
    stab = M.stability_table(games_all[games_all["game_type"] == "REG"], team_games_all)
    fig = go.Figure(go.Bar(
        x=stab["r"], y=stab["label"], orientation="h",
        error_x=dict(type="data", symmetric=False, array=stab["hi"] - stab["r"], arrayminus=stab["r"] - stab["lo"]),
        marker_color=["#2b8cbe" if lo > 0 else "#bdbdbd" for lo in stab["lo"]]))
    fig.add_vline(x=0)
    fig.update_layout(xaxis_title="Year-over-year correlation (95% CI)", height=420)
    st.plotly_chart(fig, width="stretch")
    st.markdown(Path(__file__).resolve().parents[1].joinpath("docs", "METHODOLOGY_SHORT.md").read_text())
