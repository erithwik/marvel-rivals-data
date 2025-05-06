import streamlit as st
import json
from collections import defaultdict
import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- Configuration and Data Loading ---

DATA_DIR = "data"
IN_GAME_NAMES = {
    "glacial_spark": "glacial_spark",
    "tenisstar2000": "Tenisstar2000",
    "massive_bao": "massive bao",
    "liquidussnake1": "LiquidusSnake1",
    "necros_cnf": "necros_cnf"
}
FILE_NAMES = {ign: os.path.join(DATA_DIR, f"{handle}.json") for handle, ign in IN_GAME_NAMES.items()}

# Friend list (adjust as needed)
FRIENDS = set(IN_GAME_NAMES.values())

# Relevant characters (adjust as needed)
RELEVANT_CHARACTERS_MAP = {
    "glacial_spark": ["Emma Frost", "Doctor Strange", "Mister Fantastic"],
    "massive bao": ["Invisible Woman", "Iron Fist", "The Thing", "Psylocke", "Rocket Raccoon"],
    "Tenisstar2000": ["Cloak & Dagger", "Scarlet Witch", "Groot"],
    "LiquidusSnake1": ["Loki", "Magneto", "Iron Man", "Thor", "Rocket Raccoon"],
    "necros_cnf": ["Iron Fist", "Cloak & Dagger"]
}

@st.cache_data # Cache data loading
def load_all_player_data():
    all_data = {}
    available_players = []
    for ign, file_path in FILE_NAMES.items():
        try:
            with open(file_path, 'r') as f:
                all_data[ign] = json.load(f)
                available_players.append(ign)
        except FileNotFoundError:
            st.warning(f"Data file not found for {ign}: {file_path}. Skipping player.")
        except json.JSONDecodeError:
            st.error(f"Error decoding JSON for {ign} from {file_path}. Skipping player.")
    return all_data, available_players

# --- Helper Functions (Adapted from Notebook) ---

def convert_datetime(match_timestamp):
    try:
        utc_time = datetime.datetime.strptime(match_timestamp, "%Y-%m-%dT%H:%M:%S%z")
        # Assuming PST, adjust if needed
        pst_offset = datetime.timezone(datetime.timedelta(hours=-8))
        return utc_time.astimezone(pst_offset)
    except ValueError:
        st.warning(f"Could not parse timestamp: {match_timestamp}")
        return None # Handle potential parsing errors

def _check_if_friend_game(match_data: dict, player_ign: str):
    """Check if the game has a friend in it (excluding the player themselves)."""
    # Correctly handle cases where match_details might be missing or empty
    match_details = match_data.get("match_details", [])
    if not match_details:
        return False
    teammates = {player_data["name"] for player_data in match_details if player_data.get("is_same_team")}
    friends_in_game = teammates.intersection(FRIENDS)
    # Ensure the friend is not the player themselves if player_ign is also in FRIENDS
    return any(friend != player_ign for friend in friends_in_game)


def filter_matches(matches: dict, only_friend_games: bool, player_ign: str):
    if not only_friend_games:
        return matches
    return {
        match_id: match_data
        for match_id, match_data in matches.items()
        if _check_if_friend_game(match_data, player_ign)
    }

def get_overall_plus_minus(filtered_matches: dict, player_ign: str):
    hero_stats = defaultdict(int)
    for _, match_data in filtered_matches.items():
        for player_data in match_data.get("match_details", []):
            if player_data.get("name") == player_ign:
                for hero in player_data.get("heroes", []):
                    hero_stats[hero] += player_data.get("rank_delta", 0)
    return dict(sorted(hero_stats.items(), key=lambda item: item[1], reverse=True))

def get_average_plus_minus(filtered_matches: dict, player_ign: str):
    hero_stats = defaultdict(lambda: {"total_plus_minus": 0, "num_games": 0})
    for _, match_data in filtered_matches.items():
        for player_data in match_data.get("match_details", []):
            if player_data.get("name") == player_ign:
                for hero in player_data.get("heroes", []):
                    hero_stats[hero]["total_plus_minus"] += player_data.get("rank_delta", 0)
                    hero_stats[hero]["num_games"] += 1
    results = {}
    for hero, stats in hero_stats.items():
        if stats["num_games"] > 0:
            results[hero] = stats["total_plus_minus"] / stats["num_games"]
    return dict(sorted(results.items(), key=lambda item: item[1], reverse=True))


def get_matchups(filtered_matches: dict, player_ign: str, character: str, target_teammates: bool, filter_teammates_to_friends: bool = False):
    """Calculates average matchup stats (teammates or opponents)."""
    matchups = defaultdict(lambda: {"total_plus_minus": 0, "num_games": 0})
    for _, match_data in filtered_matches.items():
        details = match_data.get("match_details", [])
        current_player_list = [pd for pd in details if pd.get("name") == player_ign]

        if not current_player_list:
            continue

        current_player = current_player_list[0]
        if character not in current_player.get("heroes", []):
            continue

        target_players = [
            pd for pd in details
            if pd.get("name") != player_ign and pd.get("is_same_team") == target_teammates
        ]

        if target_teammates and filter_teammates_to_friends:
            target_players = [p for p in target_players if p.get("name") in FRIENDS]

        for target in target_players:
            for hero in target.get("heroes", []):
                matchups[hero]["total_plus_minus"] += current_player.get("rank_delta", 0)
                matchups[hero]["num_games"] += 1

    results = {}
    for hero, stats in matchups.items():
        if stats["num_games"] > 0:
            results[hero] = stats["total_plus_minus"] / stats["num_games"]
    return dict(sorted(results.items(), key=lambda item: item[1], reverse=True))

def get_total_matchups(filtered_matches: dict, player_ign: str, character: str, target_teammates: bool, filter_teammates_to_friends: bool = False):
    """Calculates TOTAL cumulative matchup stats (teammates or opponents)."""
    matchups = defaultdict(int) # Simpler defaultdict to just sum totals
    for _, match_data in filtered_matches.items():
        details = match_data.get("match_details", [])
        current_player_list = [pd for pd in details if pd.get("name") == player_ign]

        if not current_player_list:
            continue

        current_player = current_player_list[0]
        if character not in current_player.get("heroes", []):
            continue

        target_players = [
            pd for pd in details
            if pd.get("name") != player_ign and pd.get("is_same_team") == target_teammates
        ]

        if target_teammates and filter_teammates_to_friends:
            target_players = [p for p in target_players if p.get("name") in FRIENDS]

        for target in target_players:
            for hero in target.get("heroes", []):
                # Just add the rank delta for the current game to the total for that matchup hero
                matchups[hero] += current_player.get("rank_delta", 0)

    return dict(sorted(matchups.items(), key=lambda item: item[1], reverse=True))

def get_latest_games(filtered_matches: dict, num_games: int = 10):
    matches_list = list(filtered_matches.values())
    # Sort by timestamp, handling potential None values from parsing errors
    sorted_matches = sorted(
        matches_list,
        key=lambda x: convert_datetime(x.get("match_timestamp", "1970-01-01T00:00:00+00:00")) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
        reverse=True
    )
    relevant_data_keys = ["match_timestamp", "map", "is_win", "match_details"]
    latest_games_data = []
    for match in sorted_matches[:num_games]:
        game_info = {k: match.get(k) for k in relevant_data_keys if k in match}
        if game_info.get("match_timestamp"):
             game_info["match_timestamp_pst"] = convert_datetime(game_info["match_timestamp"]).strftime('%Y-%m-%d %H:%M:%S %Z') # Format for display
        latest_games_data.append(game_info)
    return latest_games_data

# --- Plotting Helper Functions ---

def create_hero_average_chart(avg_pm: dict, player_ign: str):
    """Generates a Plotly bar chart for average hero performance."""
    if not avg_pm:
        return None

    df_average = pd.DataFrame(list(avg_pm.items()), columns=['Hero', 'Average Rank Delta'])
    df_average = df_average.sort_values(by='Average Rank Delta', ascending=False)
    colors_average = ['blue' if delta >= 0 else 'red' for delta in df_average['Average Rank Delta']]

    fig = go.Figure()
    if not df_average.empty:
        fig.add_trace(
            go.Bar(
                x=df_average['Hero'],
                y=df_average['Average Rank Delta'],
                name='Average Delta',
                marker_color=colors_average
            )
        )

    fig.update_layout(
        title_text=f"Average Hero Performance for {player_ign} (+/- per Game)",
        showlegend=False,
        height=500
    )
    fig.update_xaxes(tickangle=45, tickfont=dict(size=10))
    fig.update_yaxes(title_text="Average Rank Delta per Game")
    return fig

def create_hero_total_chart(overall_pm: dict, player_ign: str):
    """Generates a Plotly bar chart for total hero performance."""
    if not overall_pm:
        return None

    df_overall = pd.DataFrame(list(overall_pm.items()), columns=['Hero', 'Total Rank Delta'])
    df_overall = df_overall.sort_values(by='Total Rank Delta', ascending=False)
    colors_overall = ['blue' if delta >= 0 else 'red' for delta in df_overall['Total Rank Delta']]

    fig = go.Figure()
    if not df_overall.empty:
        fig.add_trace(
            go.Bar(
                x=df_overall['Hero'],
                y=df_overall['Total Rank Delta'],
                name='Total Delta',
                marker_color=colors_overall
            )
        )

    fig.update_layout(
        title_text=f"Total Hero Performance for {player_ign} (Cumulative +/-)",
        showlegend=False,
        height=500
    )
    fig.update_xaxes(tickangle=45, tickfont=dict(size=10))
    fig.update_yaxes(title_text="Total Cumulative Rank Delta")
    return fig

def create_matchup_chart(matchup_data: dict, player_ign: str, character: str, is_teammate_chart: bool):
    if not matchup_data:
        return None

    col_name = 'Teammate Hero' if is_teammate_chart else 'Opponent Hero'
    title_part = "With Teammate" if is_teammate_chart else "Against Opponent"

    df_matchup = pd.DataFrame(list(matchup_data.items()), columns=[col_name, 'Average Rank Delta'])
    df_matchup = df_matchup.sort_values(by='Average Rank Delta', ascending=False)

    colors = ['blue' if delta >= 0 else 'red' for delta in df_matchup['Average Rank Delta']]

    fig = go.Figure()

    if not df_matchup.empty:
         fig.add_trace(
            go.Bar(
                x=df_matchup[col_name],
                y=df_matchup['Average Rank Delta'],
                name='Average Delta',
                marker_color=colors
            )
        )

    fig.update_layout(
        title_text=f"Average Rank Delta {title_part} (When Playing {character})",
        showlegend=False,
        height=500 # Adjust height as needed
    )
    fig.update_xaxes(title_text=col_name, tickangle=45, tickfont=dict(size=10))
    fig.update_yaxes(title_text="Average Rank Delta per Game")

    return fig

def create_total_matchup_chart(matchup_data: dict, player_ign: str, character: str, is_teammate_chart: bool):
    """Generates a Plotly bar chart for TOTAL cumulative matchup performance."""
    if not matchup_data:
        return None

    col_name = 'Teammate Hero' if is_teammate_chart else 'Opponent Hero'
    title_part = "With Teammate" if is_teammate_chart else "Against Opponent"

    df_matchup = pd.DataFrame(list(matchup_data.items()), columns=[col_name, 'Total Rank Delta'])
    df_matchup = df_matchup.sort_values(by='Total Rank Delta', ascending=False)

    colors = ['blue' if delta >= 0 else 'red' for delta in df_matchup['Total Rank Delta']]

    fig = go.Figure()
    if not df_matchup.empty:
         fig.add_trace(
            go.Bar(
                x=df_matchup[col_name],
                y=df_matchup['Total Rank Delta'],
                name='Total Delta',
                marker_color=colors
            )
        )

    fig.update_layout(
        title_text=f"Total Cumulative Rank Delta {title_part} (When Playing {character})",
        showlegend=False,
        height=500
    )
    fig.update_xaxes(title_text=col_name, tickangle=45, tickfont=dict(size=10))
    fig.update_yaxes(title_text="Total Cumulative Rank Delta") # Update Y-axis label

    return fig

# --- Streamlit App Layout ---

st.set_page_config(layout="wide")
st.title("Marvel Rivals Data Explorer")

# Load data
all_player_data, available_players = load_all_player_data()

if not available_players:
    st.error("No player data could be loaded. Please check the `data` directory and file names.")
    st.stop() # Stop execution if no data

# --- Sidebar Controls ---
st.sidebar.header("Filters")
selected_player_ign = st.sidebar.selectbox(
    "Select Player:",
    options=available_players,
    index=0,
    format_func=lambda x: IN_GAME_NAMES.get(x, x) # Show readable names
)

only_friend_games = st.sidebar.checkbox("Filter games to only include games containing any friend?", value=False)
only_friend_teammates_matchups = st.sidebar.checkbox("Filter same-team matchups to only include teammates considered friends?", value=False)

# --- Main Content ---
if selected_player_ign and selected_player_ign in all_player_data:
    player_matches = all_player_data[selected_player_ign]
    player_readable_name = IN_GAME_NAMES.get(selected_player_ign, selected_player_ign)
    st.header(f"Player: {player_readable_name}")

    # Apply filters
    filtered_player_matches = filter_matches(player_matches, only_friend_games, selected_player_ign)
    num_total_games = len(player_matches)
    num_filtered_games = len(filtered_player_matches)

    st.metric(label="Total Games Analyzed", value=num_filtered_games, delta=f"{num_filtered_games} / {num_total_games} (Filter applied)" if only_friend_games else f"{num_total_games} (No filter)")

    if num_filtered_games == 0:
        st.warning("No games match the current filter settings.")
    else:
        # Change tabs
        avg_tab, total_tab = st.tabs(["Averages", "Totals"])

        # Calculate data needed for both tabs
        overall_pm = get_overall_plus_minus(filtered_player_matches, selected_player_ign)
        avg_pm = get_average_plus_minus(filtered_player_matches, selected_player_ign)

        with avg_tab:
            st.subheader("Average Hero Performance (+/- per Game)")
            fig_hero_avg = create_hero_average_chart(avg_pm, player_readable_name)
            if fig_hero_avg:
                st.plotly_chart(fig_hero_avg, use_container_width=True)
            else:
                st.info("No average hero performance data available for the selected filters.")

            st.markdown("***") # Separator
            st.subheader("Average Matchup Performance (+/- per Game)")
            all_heroes_played = list(avg_pm.keys()) # Use keys from already calculated avg_pm
            relevant_chars = RELEVANT_CHARACTERS_MAP.get(selected_player_ign, all_heroes_played)

            if not relevant_chars:
                 st.warning("No relevant characters found for matchup analysis with current filters.")
            else:
                 for char_to_analyze in relevant_chars:
                     st.markdown(f"#### Matchups When Playing: {char_to_analyze}")

                     team_matchups = get_matchups(
                         filtered_matches=filtered_player_matches,
                         player_ign=selected_player_ign,
                         character=char_to_analyze,
                         target_teammates=True,
                         filter_teammates_to_friends=only_friend_teammates_matchups
                     )
                     opp_matchups = get_matchups(
                         filtered_matches=filtered_player_matches,
                         player_ign=selected_player_ign,
                         character=char_to_analyze,
                         target_teammates=False
                     )

                     fig_team = create_matchup_chart(team_matchups, player_readable_name, char_to_analyze, is_teammate_chart=True)
                     if fig_team:
                         st.plotly_chart(fig_team, use_container_width=True)
                     else:
                         st.info(f"No teammate matchup data available for {char_to_analyze} with the selected filters.")

                     fig_opp = create_matchup_chart(opp_matchups, player_readable_name, char_to_analyze, is_teammate_chart=False)
                     if fig_opp:
                         st.plotly_chart(fig_opp, use_container_width=True)
                     else:
                         st.info(f"No opponent matchup data available for {char_to_analyze} with the selected filters.")

                     st.markdown("---")

        with total_tab:
            st.subheader("Total Hero Performance (Cumulative +/-)")
            fig_hero_total = create_hero_total_chart(overall_pm, player_readable_name)
            if fig_hero_total:
                st.plotly_chart(fig_hero_total, use_container_width=True)
            else:
                st.info("No total hero performance data available for the selected filters.")

            # ----> ADDED TOTAL MATCHUP SECTION <----
            st.markdown("***") # Separator
            st.subheader("Total Matchup Performance (Cumulative +/-)")
            # Need relevant characters again, calculated from avg_pm like in the averages tab
            all_heroes_played_total = list(avg_pm.keys()) # Reuse avg_pm keys to know which heroes player used
            relevant_chars_total = RELEVANT_CHARACTERS_MAP.get(selected_player_ign, all_heroes_played_total)

            if not relevant_chars_total:
                 st.warning("No relevant characters found for matchup analysis with current filters.")
            else:
                 for char_to_analyze in relevant_chars_total:
                     st.markdown(f"#### Matchups When Playing: {char_to_analyze}")

                     # Calculate Total Matchups
                     total_team_matchups = get_total_matchups(
                         filtered_matches=filtered_player_matches,
                         player_ign=selected_player_ign,
                         character=char_to_analyze,
                         target_teammates=True,
                         filter_teammates_to_friends=only_friend_teammates_matchups # Apply friend filter
                     )
                     total_opp_matchups = get_total_matchups(
                         filtered_matches=filtered_player_matches,
                         player_ign=selected_player_ign,
                         character=char_to_analyze,
                         target_teammates=False
                     )

                     # Display Total Teammate Matchup Chart
                     fig_total_team = create_total_matchup_chart(total_team_matchups, player_readable_name, char_to_analyze, is_teammate_chart=True)
                     if fig_total_team:
                         st.plotly_chart(fig_total_team, use_container_width=True)
                     else:
                         st.info(f"No total teammate matchup data available for {char_to_analyze} with the selected filters.")

                     # Display Total Opponent Matchup Chart
                     fig_total_opp = create_total_matchup_chart(total_opp_matchups, player_readable_name, char_to_analyze, is_teammate_chart=False)
                     if fig_total_opp:
                         st.plotly_chart(fig_total_opp, use_container_width=True)
                     else:
                         st.info(f"No total opponent matchup data available for {char_to_analyze} with the selected filters.")

                     st.markdown("---")
            # ----> END ADDED TOTAL MATCHUP SECTION <----

else:
    st.info("Select a player from the sidebar to view their stats.")