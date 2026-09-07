"""Fetches league, roster, user, and weekly matchup data from Sleeper and caches raw JSON."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os
import random
from .sleeper_client import SleeperClient


def ensure_dirs(base_dir: Path) -> Path:
    """Ensure data/raw directory exists."""
    raw_dir = base_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def load_pairs_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load pairing configuration from config/pairs.json."""
    if config_path is None:
        config_path = Path("config/pairs.json")
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file_path: Path, data: Any) -> None:
    """Save serializable data to JSON file with indentation."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def fetch_league_data(
    client: SleeperClient,
    league_id: str,
    max_week: Optional[int] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Fetch league info, users, rosters, and matchup data for all available weeks."""
    if output_dir is None:
        output_dir = Path("data/raw")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching league metadata for league {league_id}...")
    league = client.get_league(league_id)
    save_json(output_dir / "league.json", league)

    print("Fetching users...")
    users = client.get_users(league_id)
    save_json(output_dir / "users.json", users)

    print("Fetching rosters...")
    rosters = client.get_rosters(league_id)
    save_json(output_dir / "rosters.json", rosters)

    if max_week is None:
        try:
            nfl_state = client.get_nfl_state()
            current_week = nfl_state.get("week", 1)
            # If current week hasn't finished, fetch up to current_week or week 1
            max_week = max(1, current_week)
        except Exception:
            max_week = 1

    matchups_by_week: Dict[int, List[Dict[str, Any]]] = {}
    for week in range(1, max_week + 1):
        try:
            print(f"Fetching matchups for Week {week}...")
            matchups = client.get_matchups(league_id, week)
            if matchups:
                save_json(output_dir / f"week_{week}.json", matchups)
                matchups_by_week[week] = matchups
            else:
                print(f"No matchup data returned for Week {week}.")
        except Exception as e:
            print(f"Could not fetch Week {week}: {e}")

    return {
        "league": league,
        "users": users,
        "rosters": rosters,
        "matchups_by_week": matchups_by_week,
    }


def generate_mock_data(weeks: int = 3, output_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Generate realistic mock data for 10 teams across specified weeks for testing."""
    if output_dir is None:
        output_dir = Path("data/raw")
    output_dir.mkdir(parents=True, exist_ok=True)

    users = [
        {"user_id": f"u{i}", "display_name": name, "metadata": {"team_name": team}}
        for i, (name, team) in enumerate(
            [
                ("Alice Chen", "Championship Chasers"),
                ("Bob Smith", "Rookie Rollers"),
                ("Charlie Day", "Wildcard Wonders"),
                ("Dave Miller", "Touchdown Dynasty"),
                ("Eve Adams", "Gridiron Newbies"),
                ("Frank Vance", "Vance Refrigeration"),
                ("Grace Hopper", "Debuggers"),
                ("Hank Hill", "Propane & Points"),
                ("Ivy Taylor", "Endzone Initiates"),
                ("Jack Bauer", "24hr Blitz"),
            ],
            start=1,
        )
    ]

    rosters = [
        {
            "roster_id": i,
            "owner_id": f"u{i}",
            "settings": {
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "fpts": 0,
                "fpts_decimal": 0,
                "fpts_against": 0,
            },
        }
        for i in range(1, 11)
    ]

    league = {
        "league_id": "mock_mentor_league",
        "name": "The Mentor League (Mock Demo)",
        "total_rosters": 10,
        "season": "2024",
        "status": "in_season",
        "settings": {"playoff_week_start": 15},
    }

    save_json(output_dir / "league.json", league)
    save_json(output_dir / "users.json", users)
    save_json(output_dir / "rosters.json", rosters)

    # 5 matchups per week for 10 teams (pairings 1-5 matchups)
    # Week schedules with fixed seed for determinism in testing
    rng = random.Random(42)
    matchups_by_week: Dict[int, List[Dict[str, Any]]] = {}

    # Pre-crafted schedules to ensure testing diverse scenarios:
    # Beginner beats Expert (upset), Expert beats Beginner, Beginner beats Beginner, etc.
    schedules = [
        # Week 1: Beginner (1) vs Expert (6) -> Partner vs partner (edge case wash!)
        # Beginner (2) vs Expert (8), Beginner (3) vs Beginner (4), etc.
        [(1, 6), (2, 8), (3, 4), (5, 7), (9, 10)],
        # Week 2:
        [(1, 7), (2, 6), (3, 8), (4, 9), (5, 10)],
        # Week 3:
        [(1, 8), (2, 9), (3, 10), (4, 6), (5, 7)],
    ]

    # Score templates per week to create realistic upset scenarios
    # Beginners are 1, 2, 3, 4, 5. Experts are 6, 7, 8, 9, 10.
    week_score_presets = [
        # Week 1
        {
            1: 115.4, 6: 102.1,  # Pair 1 teammates face off! 1-1 wash
            2: 128.6, 8: 95.2,   # Beginner 2 beats Expert 8 -> UPSET BONUS!
            3: 88.4,  4: 104.2,  # Beginner 4 beats Beginner 3 -> Normal win
            5: 79.8,  7: 122.5,  # Expert 7 beats Beginner 5 -> Normal win
            9: 135.0, 10: 110.8  # Expert 9 beats Expert 10 -> Normal win
        },
        # Week 2
        {
            1: 108.2, 7: 114.6,  # Expert 7 beats Beginner 1 -> Normal win
            2: 99.4,  6: 94.0,   # Beginner 2 beats Expert 6 -> UPSET BONUS!
            3: 121.8, 8: 105.3,  # Beginner 3 beats Expert 8 -> UPSET BONUS!
            4: 112.5, 9: 130.2,  # Expert 9 beats Beginner 4 -> Normal win
            5: 95.6,  10: 92.1   # Beginner 5 beats Expert 10 -> UPSET BONUS!
        },
        # Week 3
        {
            1: 125.0, 8: 118.4,  # Beginner 1 beats Expert 8 -> UPSET BONUS!
            2: 110.2, 9: 115.6,  # Expert 9 beats Beginner 2 -> Normal win
            3: 101.4, 10: 103.2, # Expert 10 beats Beginner 3 -> Closest match (1.8 pt margin)
            4: 142.6, 6: 89.2,   # Beginner 4 beats Expert 6 -> UPSET BONUS + Blowout (53.4 pt margin)
            5: 119.5, 7: 112.3   # Beginner 5 beats Expert 7 -> UPSET BONUS!
        }
    ]

    for week_num in range(1, min(weeks, len(schedules)) + 1):
        matchup_pairs = schedules[week_num - 1]
        scores = week_score_presets[week_num - 1]
        matchups: List[Dict[str, Any]] = []

        for m_id, (team_a, team_b) in enumerate(matchup_pairs, start=1):
            score_a = scores[team_a]
            score_b = scores[team_b]
            matchups.append({
                "roster_id": team_a,
                "matchup_id": m_id,
                "points": score_a
            })
            matchups.append({
                "roster_id": team_b,
                "matchup_id": m_id,
                "points": score_b
            })

        save_json(output_dir / f"week_{week_num}.json", matchups)
        matchups_by_week[week_num] = matchups

    return {
        "league": league,
        "users": users,
        "rosters": rosters,
        "matchups_by_week": matchups_by_week,
    }


def load_cached_data(raw_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load cached raw JSON files from data/raw/."""
    if raw_dir is None:
        raw_dir = Path("data/raw")
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory does not exist: {raw_dir}")

    league_file = raw_dir / "league.json"
    users_file = raw_dir / "users.json"
    rosters_file = raw_dir / "rosters.json"

    if not (league_file.exists() and users_file.exists() and rosters_file.exists()):
        raise FileNotFoundError("Missing league.json, users.json, or rosters.json in data/raw/")

    with open(league_file, "r", encoding="utf-8") as f:
        league = json.load(f)
    with open(users_file, "r", encoding="utf-8") as f:
        users = json.load(f)
    with open(rosters_file, "r", encoding="utf-8") as f:
        rosters = json.load(f)

    matchups_by_week: Dict[int, List[Dict[str, Any]]] = {}
    for file in sorted(raw_dir.glob("week_*.json")):
        try:
            week_num = int(file.stem.split("_")[1])
            with open(file, "r", encoding="utf-8") as f:
                matchups_by_week[week_num] = json.load(f)
        except (IndexError, ValueError) as e:
            print(f"Skipping malformed filename {file}: {e}")

    return {
        "league": league,
        "users": users,
        "rosters": rosters,
        "matchups_by_week": matchups_by_week,
    }

