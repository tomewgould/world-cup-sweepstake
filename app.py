from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st


DATA_DIR = Path(__file__).parent / "data"


st.set_page_config(
    page_title="2026 World Cup Sweepstake",
    page_icon=":soccer:",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }
    div[data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 0.75rem;
    }
    .sweep-card {
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 0.85rem;
        margin-bottom: 0.75rem;
        background: #111827;
        color: #f8fafc;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.3);
    }
    .muted {
        color: #cbd5e1;
        font-size: 0.9rem;
    }
    .match-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0.2rem 0;
    }
    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.85rem;
            padding-right: 0.85rem;
        }
        h1 {
            font-size: 1.65rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_csv(filename: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / filename)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    owners = load_csv("team_owners.csv")
    fixtures = load_csv("fixtures.csv")
    results = load_csv("results.csv")
    standings = load_csv("standings.csv")
    return owners, fixtures, results, standings


def add_match_owners(matches: pd.DataFrame, owners: pd.DataFrame) -> pd.DataFrame:
    owner_lookup = owners[["team", "owner"]]

    matches = matches.merge(
        owner_lookup.rename(columns={"team": "home_team", "owner": "home_owner"}),
        on="home_team",
        how="left",
    )
    matches = matches.merge(
        owner_lookup.rename(columns={"team": "away_team", "owner": "away_owner"}),
        on="away_team",
        how="left",
    )
    matches[["home_owner", "away_owner"]] = matches[
        ["home_owner", "away_owner"]
    ].fillna("TBC")
    return matches


def add_standing_owners(standings: pd.DataFrame, owners: pd.DataFrame) -> pd.DataFrame:
    standings = standings.drop(columns=["owner"], errors="ignore")
    return standings.merge(owners[["team", "owner"]], on="team", how="left")


def format_group(value: object) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "-"
    return str(value)


def format_team_list(teams: list[str]) -> str:
    if not teams:
        return "None"
    return ", ".join(teams)


def upcoming_matches(fixtures: pd.DataFrame, owners: pd.DataFrame) -> pd.DataFrame:
    matches = fixtures.copy()
    matches["kickoff"] = pd.to_datetime(
        matches["date"] + " " + matches["kickoff_uk"], errors="coerce"
    )
    matches = matches[matches["status"].str.lower().eq("scheduled")]
    matches = matches.sort_values(["kickoff", "match_id"])
    return add_match_owners(matches, owners)


def completed_results(results: pd.DataFrame, fixtures: pd.DataFrame) -> pd.DataFrame:
    completed = results.copy()
    completed["home_goals"] = pd.to_numeric(completed["home_goals"], errors="coerce")
    completed["away_goals"] = pd.to_numeric(completed["away_goals"], errors="coerce")
    completed = completed.dropna(subset=["home_goals", "away_goals"])
    completed = completed[completed["result_status"].str.lower().eq("completed")]
    return completed.merge(
        fixtures[
            [
                "match_id",
                "date",
                "kickoff_uk",
                "stage",
                "group",
                "home_team",
                "away_team",
            ]
        ],
        on=["match_id", "home_team", "away_team"],
        how="left",
    )


def biggest_defeat(
    results: pd.DataFrame, fixtures: pd.DataFrame, owners: pd.DataFrame
) -> Optional[pd.Series]:
    completed = completed_results(results, fixtures)
    if completed.empty:
        return None

    completed["margin"] = (completed["home_goals"] - completed["away_goals"]).abs()
    completed = completed[completed["margin"] > 0].sort_values(
        ["margin", "match_id"], ascending=[False, True]
    )
    if completed.empty:
        return None

    row = completed.iloc[0].copy()
    losing_team = (
        row["away_team"] if row["home_goals"] > row["away_goals"] else row["home_team"]
    )
    owner = owners.loc[owners["team"].eq(losing_team), "owner"]
    row["losing_team"] = losing_team
    row["losing_owner"] = owner.iloc[0] if not owner.empty else "TBC"
    row["scoreline"] = f"{row['home_team']} {int(row['home_goals'])}-{int(row['away_goals'])} {row['away_team']}"
    row["match"] = f"{row['home_team']} vs {row['away_team']}"
    return row


def render_match_card(row: pd.Series) -> None:
    kickoff = f"{row['kickoff'].strftime('%a')} {row['kickoff'].day} {row['kickoff'].strftime('%b, %H:%M')}"

    st.markdown(
        f"""
        <div class="sweep-card">
            <div class="muted">{kickoff} UK - {row["stage"]} - Group {format_group(row["group"])}</div>
            <div class="match-title">{row["home_team"]} vs {row["away_team"]}</div>
            <div>{row["home_owner"]} vs {row["away_owner"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_match_cards(matches: pd.DataFrame) -> None:
    for _, row in matches.iterrows():
        render_match_card(row)


def today_page(fixtures: pd.DataFrame, owners: pd.DataFrame) -> None:
    st.subheader("Today")
    matches = upcoming_matches(fixtures, owners)

    if matches.empty:
        st.info("No upcoming matches found.")
        return

    next_date = matches["kickoff"].dt.date.min()
    todays_matches = matches[matches["kickoff"].dt.date.eq(next_date)]

    st.caption(f"Next matches: {next_date.strftime('%A %d %B %Y')}")
    render_match_cards(todays_matches)

    with st.expander("All upcoming matches"):
        matches_by_date = matches.assign(match_date=matches["kickoff"].dt.date)
        for match_date, date_matches in matches_by_date.groupby("match_date", sort=True):
            st.markdown(f"#### {match_date.strftime('%A %d %B %Y')}")
            render_match_cards(date_matches)


def groups_page(standings: pd.DataFrame, owners: pd.DataFrame) -> None:
    st.subheader("Groups")
    standings = add_standing_owners(standings, owners)
    standings = standings.sort_values(["group", "position"])

    for group_name, group_rows in standings.groupby("group", sort=True):
        st.markdown(f"#### Group {group_name}")
        st.dataframe(
            group_rows[
                [
                    "group",
                    "position",
                    "team",
                    "owner",
                    "played",
                    "wins",
                    "draws",
                    "losses",
                    "goal_difference",
                    "points",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )


def power_rankings(standings: pd.DataFrame, owners: pd.DataFrame) -> pd.DataFrame:
    ranked = add_standing_owners(standings, owners)
    ranked["owner"] = ranked["owner"].fillna("TBC")
    ranked["status"] = ranked["status"].fillna("")
    ranked["position"] = pd.to_numeric(ranked["position"], errors="coerce")
    ranked["is_eliminated"] = ranked["status"].str.lower().str.contains("eliminated")
    ranked["is_active"] = ~ranked["is_eliminated"]
    ranked["is_qualifying"] = ranked["position"].le(2) & ranked["is_active"]
    ranked["is_group_leader"] = ranked["position"].eq(1) & ranked["is_active"]

    rows = []
    for owner, owner_rows in ranked.groupby("owner", sort=True):
        rows.append(
            {
                "owner": owner,
                "active_count": int(owner_rows["is_active"].sum()),
                "qualifying_count": int(owner_rows["is_qualifying"].sum()),
                "group_leader_count": int(owner_rows["is_group_leader"].sum()),
                "eliminated_count": int(owner_rows["is_eliminated"].sum()),
                "qualifying_teams": owner_rows.loc[
                    owner_rows["is_qualifying"], "team"
                ].tolist(),
                "group_leaders": owner_rows.loc[
                    owner_rows["is_group_leader"], "team"
                ].tolist(),
                "eliminated_teams": owner_rows.loc[
                    owner_rows["is_eliminated"], "team"
                ].tolist(),
            }
        )

    return pd.DataFrame(rows).sort_values(
        [
            "group_leader_count",
            "qualifying_count",
            "active_count",
            "owner",
        ],
        ascending=[False, False, False, True],
    )


def render_power_card(row: pd.Series) -> None:
    st.markdown(
        f"""
        <div class="sweep-card">
            <div class="match-title">{row["owner"]}</div>
            <div><strong>Still active:</strong> {row["active_count"]}</div>
            <div><strong>Qualifying positions:</strong> {row["qualifying_count"]} - {format_team_list(row["qualifying_teams"])}</div>
            <div><strong>Group leaders:</strong> {row["group_leader_count"]} - {format_team_list(row["group_leaders"])}</div>
            <div><strong>Eliminated:</strong> {row["eliminated_count"]} - {format_team_list(row["eliminated_teams"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def power_rankings_page(standings: pd.DataFrame, owners: pd.DataFrame) -> None:
    st.subheader("Power Rankings")
    rankings = power_rankings(standings, owners)

    if rankings.empty:
        st.info("No ranking data found.")
        return

    for _, row in rankings.iterrows():
        render_power_card(row)


def awards_page(
    results: pd.DataFrame, fixtures: pd.DataFrame, owners: pd.DataFrame
) -> None:
    st.subheader("Awards")
    col1, col2, col3 = st.columns(3)
    col1.metric("Tournament winner", "TBC")
    col2.metric("Runner-up", "TBC")
    col3.metric("Third place", "TBC")

    st.markdown("#### Biggest defeat")
    defeat = biggest_defeat(results, fixtures, owners)
    if defeat is None:
        st.info("No completed matches yet.")
        return

    st.markdown(
        f"""
        <div class="sweep-card">
            <div class="muted">{defeat["stage"]} - Group {format_group(defeat["group"])}</div>
            <div class="match-title">{defeat["scoreline"]}</div>
            <div><strong>Losing team:</strong> {defeat["losing_team"]} ({defeat["losing_owner"]})</div>
            <div><strong>Match:</strong> {defeat["match"]}</div>
            <div><strong>Defeat margin:</strong> {int(defeat["margin"])} goals</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def teams_page(owners: pd.DataFrame) -> None:
    st.subheader("Teams")
    owners = owners.sort_values(["owner", "team"])

    for owner, rows in owners.groupby("owner", sort=True):
        teams = ", ".join(rows["team"].tolist())
        st.markdown(
            f"""
            <div class="sweep-card">
                <div class="match-title">{owner}</div>
                <div>{teams}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    st.title("2026 World Cup Sweepstake")
    owners, fixtures, results, standings = load_data()

    today, groups, rankings, awards, teams = st.tabs(
        ["Today", "Groups", "Power Rankings", "Awards", "Teams"]
    )
    with today:
        today_page(fixtures, owners)
    with groups:
        groups_page(standings, owners)
    with rankings:
        power_rankings_page(standings, owners)
    with awards:
        awards_page(results, fixtures, owners)
    with teams:
        teams_page(owners)


if __name__ == "__main__":
    main()
