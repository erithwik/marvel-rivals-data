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
    "lunatoemuncher": "LunaToeMuncher",
    "liquidussnake1": "LiquidusSnake1"
}
FILE_NAMES = {ign: os.path.join(DATA_DIR, f"{handle}.json") for handle, ign in IN_GAME_NAMES.items()}

# Friend list (adjust as needed)
FRIENDS = set(IN_GAME_NAMES.values())

# Relevant characters (adjust as needed)
RELEVANT_CHARACTERS_MAP = {
    "glacial_spark": ["Rocket Raccoon", "Doctor Strange", "Mister Fantastic", "Namor"],
    "LunaToeMuncher": ["Cloak & Dagger", "Scarlet Witch", "Peni Parker", "Mister Fantastic", "Squirrel Girl"]
}

MAP_NAME_TO_MAP_TYPE = {
    "Spider-Islands": "Convoy",
    "Krakoa": "Domination",
    "Yggdrasill Path": "Convoy",
    "Birnin T'Challa": "Domination",
    "Central Park": "Convergence",
    "Symbiotic Surface": "Convergence",
    "Hell's Heaven": "Domination",
    "Midtown": "Convoy",
    "Hall Of Djalia": "Convergence",
    "Arakko": "Convoy"
}

AVERAGE_HERO_PERFORMANCE_TEXT = "This next chart shows the average (per game) elo plus/minus for each hero you've played in competitive play. Only heroes played in at least 5 games are included."
AVERAGE_MATCHUP_SAME_TEAM_PERFORMANCE_TEXT = "This next chart shows the average (per game) elo plus/minus based on what heroes played with you. For example, when you play {player_hero}, if your team has a {teammate_hero}, you perform relatively well."
AVERAGE_MATCHUP_OPPONENT_PERFORMANCE_TEXT = "This next chart shows the average (per game) elo plus/minus based on what heroes played against you. For example, when you play {player_hero}, if the opposing team has a {opponent_hero}, you perform relatively poorly."
AVERAGE_MAP_PERFORMANCE_TEXT = "This next chart shows the average (per game) elo plus/minus for each map you've played in competitive play. For example, if you play {player_hero} on {map_name}, you perform relatively well."
AVERAGE_MAP_TYPE_PERFORMANCE_TEXT = "This next chart shows the average (per game) elo plus/minus for each map type you've played in competitive play. For example, if you play {player_hero} on {map_type}, you perform relatively well."

TOTAL_HERO_PERFORMANCE_TEXT = "This next chart shows the total elo plus/minus of each hero you've played in competitive play. Only heroes played in at least 5 games are included."
TOTAL_MATCHUP_SAME_TEAM_PERFORMANCE_TEXT = "This next chart shows the total elo plus/minus based on what heroes played with you. For example, when you play {player_hero}, if your team has a {teammate_hero}, you perform relatively well."
TOTAL_MATCHUP_OPPONENT_PERFORMANCE_TEXT = "This next chart shows the total elo plus/minus based on what heroes played against you. For example, when you play {player_hero}, if the opposing team has a {opponent_hero}, you perform relatively poorly."
TOTAL_MAP_PERFORMANCE_TEXT = "This next chart shows the total elo plus/minus for each map you've played in competitive play. For example, if you play {player_hero} on {map_name}, you perform relatively well."
TOTAL_MAP_TYPE_PERFORMANCE_TEXT = "This next chart shows the total elo plus/minus for each map type you've played in competitive play. For example, if you play {player_hero} on {map_type}, you perform relatively well."

AVERAGE_PERFORMANCE_BY_DAY_TEXT = "This next chart shows your average (per game) elo plus/minus for each day of the week."
TOTAL_PERFORMANCE_BY_DAY_TEXT = "This next chart shows your total elo plus/minus for each day of the week."

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
    hero_stats = defaultdict(lambda: {"total_plus_minus": 0, "num_games": 0})
    for _, match_data in filtered_matches.items():
        for player_data in match_data.get("match_details", []):
            if player_data.get("name") == player_ign:
                for hero in player_data.get("heroes", []):
                    hero_stats[hero]["total_plus_minus"] += player_data.get("rank_delta", 0)
                    hero_stats[hero]["num_games"] += 1
    # Only include heroes played more than 5 times
    filtered_hero_stats = {hero: stats["total_plus_minus"] for hero, stats in hero_stats.items() if stats["num_games"] >= 5}
    return dict(sorted(filtered_hero_stats.items(), key=lambda item: item[1], reverse=True))

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
        if stats["num_games"] >= 5:
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

def get_map_performance_for_hero(filtered_matches: dict, player_ign: str, character: str):
    """Calculates total map performance for a specific hero."""
    map_data = defaultdict(int)
    map_games = defaultdict(int)
    for _, match_data in filtered_matches.items():
        map_name = match_data.get("map", "Unknown")
        player_list = [player for player in match_data.get("match_details", []) if player.get("name") == player_ign]
        if not player_list:
            continue
        player_data = player_list[0]
        if character in player_data.get("heroes", []):
            map_data[map_name] += player_data.get("rank_delta", 0)
            map_games[map_name] += 1
    return map_data, map_games


def get_map_type_performance_for_hero(filtered_matches: dict, player_ign: str, character: str):
    """Calculates total map performance for a specific hero."""
    map_data = defaultdict(int)
    map_games = defaultdict(int)
    for _, match_data in filtered_matches.items():
        map_type = MAP_NAME_TO_MAP_TYPE[match_data["map"]]
        player_list = [player for player in match_data.get("match_details", []) if player.get("name") == player_ign]
        if not player_list:
            continue
        player_data = player_list[0]
        if character in player_data.get("heroes", []):
            map_data[map_type] += player_data.get("rank_delta", 0)
            map_games[map_type] += 1
    return map_data, map_games

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

def create_map_performance_chart(map_data: dict, map_games: dict, player_ign: str, character: str, show_average: bool = False):
    """Generates a Plotly bar chart for map performance for a specific hero."""
    if not map_data:
        return None
    
    df_columns = ['Map', 'Rank Delta']
    df_map = pd.DataFrame(list(map_data.items()), columns=df_columns)
    
    if show_average:
        # Calculate average per map
        df_map['Games'] = [map_games.get(map_name, 1) for map_name in df_map['Map']]
        df_map['Average Delta'] = df_map['Rank Delta'] / df_map['Games']
        df_map = df_map.sort_values(by='Average Delta', ascending=False)
        y_values = df_map['Average Delta']
        title_text = f"Average Map Performance for {character} (Avg +/- per Game)"
        y_axis_title = "Average Rank Delta per Game"
    else:
        # Use total values
        df_map = df_map.sort_values(by='Rank Delta', ascending=False)
        y_values = df_map['Rank Delta']
        title_text = f"Total Map Performance for {character} (Cumulative +/-)"
        y_axis_title = "Total Cumulative Rank Delta"
    
    colors = ['blue' if delta >= 0 else 'red' for delta in y_values]
    
    fig = go.Figure()
    if not df_map.empty:
        fig.add_trace(
            go.Bar(
                x=df_map['Map'],
                y=y_values,
                name='Map Performance',
                marker_color=colors,
            )
        )
    
    fig.update_layout(
        title_text=title_text,
        showlegend=False,
        height=400
    )
    fig.update_xaxes(title_text="Map", tickangle=45, tickfont=dict(size=10))
    fig.update_yaxes(title_text=y_axis_title)
    
    return fig


def create_map_type_performance_chart(map_data: dict, map_games: dict, player_ign: str, character: str, show_average: bool = False):
    """Generates a Plotly bar chart for map performance for a specific hero."""
    if not map_data:
        return None
    
    df_columns = ['Map Type', 'Rank Delta']
    df_map = pd.DataFrame(list(map_data.items()), columns=df_columns)
    
    if show_average:
        # Calculate average per map
        df_map['Games'] = [map_games.get(map_type, 1) for map_type in df_map['Map Type']]
        df_map['Average Delta'] = df_map['Rank Delta'] / df_map['Games']
        df_map = df_map.sort_values(by='Average Delta', ascending=False)
        y_values = df_map['Average Delta']
        title_text = f"Average Map Type Performance for {character} (Avg +/- per Game)"
        y_axis_title = "Average Rank Delta per Game"
    else:
        # Use total values
        df_map = df_map.sort_values(by='Rank Delta', ascending=False)
        y_values = df_map['Rank Delta']
        title_text = f"Total Map Type Performance for {character} (Cumulative +/-)"
        y_axis_title = "Total Cumulative Rank Delta"
    
    colors = ['blue' if delta >= 0 else 'red' for delta in y_values]
    
    fig = go.Figure()
    if not df_map.empty:
        fig.add_trace(
            go.Bar(
                x=df_map['Map Type'],
                y=y_values,
                name='Map Performance',
                marker_color=colors,
            )
        )
    
    fig.update_layout(
        title_text=title_text,
        showlegend=False,
        height=400
    )
    fig.update_xaxes(title_text="Map Type", tickangle=45, tickfont=dict(size=10))
    fig.update_yaxes(title_text=y_axis_title)
    
    return fig

def get_performance_by_day_of_week(filtered_matches: dict, player_ign: str):
    """Calculates total and average ELO +/- per day of the week."""
    day_stats = defaultdict(lambda: {"total_plus_minus": 0, "num_games": 0})
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for _, match_data in filtered_matches.items():
        match_timestamp_str = match_data.get("match_timestamp")
        if not match_timestamp_str:
            continue

        pst_time_obj = convert_datetime(match_timestamp_str)
        if not pst_time_obj:
            continue

        day_name = pst_time_obj.strftime('%A')

        for p_data in match_data.get("match_details", []):
            if p_data.get("name") == player_ign:
                day_stats[day_name]["total_plus_minus"] += p_data.get("rank_delta", 0)
                day_stats[day_name]["num_games"] += 1
                # Since we are looking at overall player performance per day,
                # we don't need to iterate through heroes here and can break
                # after finding the player.
                break 
                
    total_performance = {day: day_stats[day]["total_plus_minus"] for day in days_order if day in day_stats}
    average_performance = {
        day: day_stats[day]["total_plus_minus"] / day_stats[day]["num_games"]
        for day in days_order
        if day in day_stats and day_stats[day]["num_games"] > 0
    }
    
    # Ensure all days are present in the output, even if with 0 value, and maintain order
    ordered_total_performance = {day: total_performance.get(day, 0) for day in days_order}
    ordered_average_performance = {day: average_performance.get(day, 0.0) for day in days_order}

    return ordered_total_performance, ordered_average_performance

def create_performance_by_day_chart(performance_data: dict, player_ign: str, is_average: bool):
    """Generates a Plotly bar chart for performance by day of the week."""
    if not performance_data or all(value == 0 for value in performance_data.values()): # Check if all values are zero
        return None

    days = list(performance_data.keys())
    values = list(performance_data.values())

    y_axis_title = "Average Rank Delta per Game" if is_average else "Total Cumulative Rank Delta"
    title_suffix = "Average (+/- per Game)" if is_average else "Total (Cumulative +/-)"
    chart_title = f"Performance by Day of Week for {player_ign} - {title_suffix}"

    colors = ['blue' if delta >= 0 else 'red' for delta in values]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=days,
            y=values,
            name='Performance',
            marker_color=colors
        )
    )

    fig.update_layout(
        title_text=chart_title,
        showlegend=False,
        height=500
    )
    fig.update_xaxes(title_text="Day of the Week", tickangle=45, tickfont=dict(size=10))
    fig.update_yaxes(title_text=y_axis_title)

    return fig

# --- Plotting Helper Functions ---

def get_globally_latest_update_time(all_player_data_dict: dict) -> str:
    """
    Finds the most recent match timestamp from all player data,
    converts it to PST, and returns a formatted string.
    """
    latest_pst_time_obj = None

    for player_ign in all_player_data_dict:
        player_matches = all_player_data_dict.get(player_ign, {})
        # Ensure player_matches is a dictionary (it should be from json.load)
        if not isinstance(player_matches, dict):
            # This case should ideally not happen if load_all_player_data works as expected
            print(f"Warning: Data for player {player_ign} is not in the expected format. Skipping for latest time calculation.")
            continue

        for match_id, match_data in player_matches.items():
            # Ensure match_data is a dictionary
            if not isinstance(match_data, dict):
                print(f"Warning: Match data for {match_id} (player {player_ign}) is not a dictionary. Skipping for latest time calculation.")
                continue
            match_timestamp_str = match_data.get("match_timestamp")
            if match_timestamp_str:
                current_pst_time_obj = convert_datetime(match_timestamp_str) # convert_datetime returns PST or None
                if current_pst_time_obj:
                    if latest_pst_time_obj is None or current_pst_time_obj > latest_pst_time_obj:
                        latest_pst_time_obj = current_pst_time_obj

    if latest_pst_time_obj:
        # Format to YYYY-MM-DD hh:mm:ss AM/PM PST
        return f"Last data update: {latest_pst_time_obj.strftime('%Y-%m-%d %I:%M:%S %p PST')}"
    return "Last data update: N/A"

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
last_update_string = get_globally_latest_update_time(all_player_data)

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
st.sidebar.caption(last_update_string) # Display the last update time

only_friend_games = st.sidebar.checkbox("Filter games to only include games containing friends?", value=False)
only_friend_teammates_matchups = st.sidebar.checkbox("Update same-team matchups charts to only include heroes played by friends?", value=False)

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
        total_perf_by_day, avg_perf_by_day = get_performance_by_day_of_week(filtered_player_matches, selected_player_ign)

        with avg_tab:
            st.subheader("Average Hero Performance (+/- per Game)")
            st.text(AVERAGE_HERO_PERFORMANCE_TEXT)
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
                         player_hero = char_to_analyze
                         teammate_hero = list(team_matchups.keys())[0]
                         st.text(AVERAGE_MATCHUP_SAME_TEAM_PERFORMANCE_TEXT.format(player_hero=player_hero, teammate_hero=teammate_hero))
                         st.plotly_chart(fig_team, use_container_width=True)
                     else:
                         st.info(f"No teammate matchup data available for {char_to_analyze} with the selected filters.")

                     fig_opp = create_matchup_chart(opp_matchups, player_readable_name, char_to_analyze, is_teammate_chart=False)
                     if fig_opp:
                         player_hero = char_to_analyze
                         opponent_hero = list(opp_matchups.keys())[-1]
                         st.text(AVERAGE_MATCHUP_OPPONENT_PERFORMANCE_TEXT.format(player_hero=player_hero, opponent_hero=opponent_hero))
                         st.plotly_chart(fig_opp, use_container_width=True)
                     else:
                         st.info(f"No opponent matchup data available for {char_to_analyze} with the selected filters.")
                     
                     # Add Average Map Performance
                     map_data, map_games = get_map_performance_for_hero(
                         filtered_matches=filtered_player_matches,
                         player_ign=selected_player_ign,
                         character=char_to_analyze
                     )
                     fig_map_avg = create_map_performance_chart(
                         map_data=map_data,
                         map_games=map_games,
                         player_ign=player_readable_name,
                         character=char_to_analyze,
                         show_average=True
                     )
                     if fig_map_avg:
                         player_hero = char_to_analyze
                         # Get the best performing map by sorting based on average performance
                         best_map_name = max(map_data.items(), key=lambda x: x[1]/map_games[x[0]] if map_games[x[0]] > 0 else float('-inf'))[0]
                         st.text(AVERAGE_MAP_PERFORMANCE_TEXT.format(player_hero=player_hero, map_name=best_map_name))
                         st.plotly_chart(fig_map_avg, use_container_width=True)
                     else:
                         st.info(f"No map performance data available for {char_to_analyze} with the selected filters.")
                        
                     # Add Average Map Type Performance
                     map_type_data, map_type_games = get_map_type_performance_for_hero(
                         filtered_matches=filtered_player_matches,
                         player_ign=selected_player_ign,
                         character=char_to_analyze
                     )
                     fig_map_type_avg = create_map_type_performance_chart(
                         map_data=map_type_data,
                         map_games=map_type_games,
                         player_ign=player_readable_name,
                         character=char_to_analyze,
                         show_average=True
                     )
                     if fig_map_type_avg:
                         player_hero = char_to_analyze
                         # Get the best performing map type by sorting based on average performance
                         best_map_type = max(map_type_data.items(), key=lambda x: x[1]/map_type_games[x[0]] if map_type_games[x[0]] > 0 else float('-inf'))[0]
                         st.text(AVERAGE_MAP_TYPE_PERFORMANCE_TEXT.format(player_hero=player_hero, map_type=best_map_type))
                         st.plotly_chart(fig_map_type_avg, use_container_width=True)
                     else:
                         st.info(f"No map performance data available for {char_to_analyze} with the selected filters.")

                     st.markdown("---")

            st.markdown("***")
            st.subheader("Average Performance by Day of Week")
            st.text(AVERAGE_PERFORMANCE_BY_DAY_TEXT)
            fig_avg_perf_by_day = create_performance_by_day_chart(avg_perf_by_day, player_readable_name, is_average=True)
            if fig_avg_perf_by_day:
                st.plotly_chart(fig_avg_perf_by_day, use_container_width=True)
            else:
                st.info("No average performance data by day of week available for the selected filters.")

        with total_tab:
            st.subheader("Total Hero Performance (Cumulative +/-)")
            st.text(TOTAL_HERO_PERFORMANCE_TEXT)
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
                         player_hero = char_to_analyze
                         teammate_hero = list(total_team_matchups.keys())[0]
                         st.text(TOTAL_MATCHUP_SAME_TEAM_PERFORMANCE_TEXT.format(player_hero=player_hero, teammate_hero=teammate_hero))
                         st.plotly_chart(fig_total_team, use_container_width=True)
                     else:
                         st.info(f"No total teammate matchup data available for {char_to_analyze} with the selected filters.")

                     # Display Total Opponent Matchup Chart
                     fig_total_opp = create_total_matchup_chart(total_opp_matchups, player_readable_name, char_to_analyze, is_teammate_chart=False)
                     if fig_total_opp:
                         player_hero = char_to_analyze
                         opponent_hero = list(total_opp_matchups.keys())[-1]
                         st.text(TOTAL_MATCHUP_OPPONENT_PERFORMANCE_TEXT.format(player_hero=player_hero, opponent_hero=opponent_hero))
                         st.plotly_chart(fig_total_opp, use_container_width=True)
                     else:
                         st.info(f"No total opponent matchup data available for {char_to_analyze} with the selected filters.")
                     
                     # Add Total Map Performance
                     map_data, map_games = get_map_performance_for_hero(
                         filtered_matches=filtered_player_matches,
                         player_ign=selected_player_ign,
                         character=char_to_analyze
                     )
                     fig_map_total = create_map_performance_chart(
                         map_data=map_data,
                         map_games=map_games,
                         player_ign=player_readable_name,
                         character=char_to_analyze,
                         show_average=False
                     )
                     if fig_map_total:
                         player_hero = char_to_analyze
                         # Get the best performing map by total performance
                         best_map_name = max(map_data.items(), key=lambda x: x[1])[0]
                         st.text(TOTAL_MAP_PERFORMANCE_TEXT.format(player_hero=player_hero, map_name=best_map_name))
                         st.plotly_chart(fig_map_total, use_container_width=True)
                     else:
                         st.info(f"No map performance data available for {char_to_analyze} with the selected filters.")
                     
                     # Add Total Map Type Performance
                     map_type_data, map_type_games = get_map_type_performance_for_hero(
                         filtered_matches=filtered_player_matches,
                         player_ign=selected_player_ign,
                         character=char_to_analyze
                     )
                     fig_map_type_total = create_map_type_performance_chart(
                         map_data=map_type_data,
                         map_games=map_type_games,
                         player_ign=player_readable_name,
                         character=char_to_analyze,
                         show_average=False
                     )
                     if fig_map_type_total:
                         player_hero = char_to_analyze
                         # Get the best performing map type by total performance
                         best_map_type = max(map_type_data.items(), key=lambda x: x[1])[0]
                         st.text(TOTAL_MAP_TYPE_PERFORMANCE_TEXT.format(player_hero=player_hero, map_type=best_map_type))
                         st.plotly_chart(fig_map_type_total, use_container_width=True)
                     else:
                         st.info(f"No map performance data available for {char_to_analyze} with the selected filters.")

                     st.markdown("---")
            # ----> END ADDED TOTAL MATCHUP SECTION <----
            
            st.markdown("***")
            st.subheader("Total Performance by Day of Week")
            st.text(TOTAL_PERFORMANCE_BY_DAY_TEXT)
            fig_total_perf_by_day = create_performance_by_day_chart(total_perf_by_day, player_readable_name, is_average=False)
            if fig_total_perf_by_day:
                st.plotly_chart(fig_total_perf_by_day, use_container_width=True)
            else:
                st.info("No total performance data by day of week available for the selected filters.")

else:
    st.info("Select a player from the sidebar to view their stats.")