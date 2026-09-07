"""Unit tests for the Fantasy Football Mentor League standings engine."""

import pytest
from src.standings import StandingsCalculator


@pytest.fixture
def sample_config():
    return {
        "league_id": "test_league",
        "upset_bonus_multiplier": 1.5,
        "weighted_score": {
            "beginner_weight": 0.7,
            "expert_weight": 0.3,
        },
        "playoff_qualifiers": 4,
        "pairs": [
            {
                "id": 1,
                "name": "Pair Alpha",
                "beginner": {"roster_id": 1, "name": "Beginner 1"},
                "expert": {"roster_id": 6, "name": "Expert 6"},
            },
            {
                "id": 2,
                "name": "Pair Beta",
                "beginner": {"roster_id": 2, "name": "Beginner 2"},
                "expert": {"roster_id": 7, "name": "Expert 7"},
            },
            {
                "id": 3,
                "name": "Pair Gamma",
                "beginner": {"roster_id": 3, "name": "Beginner 3"},
                "expert": {"roster_id": 8, "name": "Expert 8"},
            },
            {
                "id": 4,
                "name": "Pair Delta",
                "beginner": {"roster_id": 4, "name": "Beginner 4"},
                "expert": {"roster_id": 9, "name": "Expert 9"},
            },
            {
                "id": 5,
                "name": "Pair Epsilon",
                "beginner": {"roster_id": 5, "name": "Beginner 5"},
                "expert": {"roster_id": 10, "name": "Expert 10"},
            },
        ],
    }


@pytest.fixture
def sample_roster_meta():
    meta = {}
    for i in range(1, 11):
        role = "Beginner" if i <= 5 else "Expert"
        meta[i] = {
            "display_name": f"{role} {i}",
            "team_name": f"Team {i}",
            "avatar": "",
        }
    return meta


def test_standard_scoring_and_upset_bonus(sample_config, sample_roster_meta):
    """Test that beginner beating expert awards 1.5 wins, while expert beating beginner awards 1.0."""
    calc = StandingsCalculator(sample_config)

    # Week 1 Matchups:
    # Matchup 1: Beginner 1 (110.0) vs Expert 7 (90.0) -> UPSET! Beginner 1 gets 1.5 wins
    # Matchup 2: Expert 6 (100.0) vs Beginner 2 (95.0) -> Expert 6 gets 1.0 win
    # Matchup 3: Beginner 3 (105.0) vs Beginner 4 (92.0) -> Beginner 3 gets 1.0 win (no upset)
    # Matchup 4: Expert 8 (120.0) vs Expert 9 (115.0) -> Expert 8 gets 1.0 win (no upset)
    # Matchup 5: Beginner 5 (80.0) vs Expert 10 (85.0) -> Expert 10 gets 1.0 win
    matchups = [
        {"matchup_id": 1, "roster_id": 1, "points": 110.0},
        {"matchup_id": 1, "roster_id": 7, "points": 90.0},
        {"matchup_id": 2, "roster_id": 6, "points": 100.0},
        {"matchup_id": 2, "roster_id": 2, "points": 95.0},
        {"matchup_id": 3, "roster_id": 3, "points": 105.0},
        {"matchup_id": 3, "roster_id": 4, "points": 92.0},
        {"matchup_id": 4, "roster_id": 8, "points": 120.0},
        {"matchup_id": 4, "roster_id": 9, "points": 115.0},
        {"matchup_id": 5, "roster_id": 5, "points": 80.0},
        {"matchup_id": 5, "roster_id": 10, "points": 85.0},
    ]

    week_res = calc.process_week(1, matchups, sample_roster_meta)
    pair_map = {p["pair_id"]: p for p in week_res["pair_results"]}

    # Pair 1: Beginner 1 won with Upset (1.5) + Expert 6 won (1.0) = 2.5 wins!
    p1 = pair_map[1]
    assert p1["wins"] == 2.5
    assert p1["losses"] == 0.0
    assert p1["beginner_upset"] is True
    assert p1["combined_points"] == 210.0

    # Pair 2: Beginner 2 lost (0.0) + Expert 7 lost (0.0) = 0.0 wins, 2.0 losses
    p2 = pair_map[2]
    assert p2["wins"] == 0.0
    assert p2["losses"] == 2.0
    assert p2["combined_points"] == 185.0

    # Pair 3: Beginner 3 won vs beginner (1.0) + Expert 8 won vs expert (1.0) = 2.0 wins
    p3 = pair_map[3]
    assert p3["wins"] == 2.0
    assert p3["losses"] == 0.0
    assert p3["beginner_upset"] is False


def test_teammate_matchup_wash(sample_config, sample_roster_meta):
    """Test that if teammates in the same pair face each other, it washes to 1-1 without upset bonus."""
    calc = StandingsCalculator(sample_config)

    # Beginner 1 (roster 1) faces their own mentor Expert 6 (roster 6)
    matchups = [
        {"matchup_id": 1, "roster_id": 1, "points": 120.0},
        {"matchup_id": 1, "roster_id": 6, "points": 90.0},
        {"matchup_id": 2, "roster_id": 2, "points": 100.0},
        {"matchup_id": 2, "roster_id": 7, "points": 105.0},
        {"matchup_id": 3, "roster_id": 3, "points": 100.0},
        {"matchup_id": 3, "roster_id": 8, "points": 105.0},
        {"matchup_id": 4, "roster_id": 4, "points": 100.0},
        {"matchup_id": 4, "roster_id": 9, "points": 105.0},
        {"matchup_id": 5, "roster_id": 5, "points": 100.0},
        {"matchup_id": 5, "roster_id": 10, "points": 105.0},
    ]

    week_res = calc.process_week(1, matchups, sample_roster_meta)
    pair_map = {p["pair_id"]: p for p in week_res["pair_results"]}

    p1 = pair_map[1]
    # Beginner won against their own mentor, but internal matchups net to 1-1 wash (no upset bonus)
    assert p1["wins"] == 1.0
    assert p1["losses"] == 1.0
    assert p1["beginner_upset"] is False


def test_weighted_mentee_score(sample_config, sample_roster_meta):
    """Test that weighted score equals 0.7 * Beginner_pts + 0.3 * Expert_pts."""
    calc = StandingsCalculator(sample_config)

    # Beginner 1 scores 100.0, Expert 6 scores 50.0
    # Expected weighted score: 0.7 * 100 + 0.3 * 50 = 70 + 15 = 85.0
    matchups = [
        {"matchup_id": 1, "roster_id": 1, "points": 100.0},
        {"matchup_id": 1, "roster_id": 2, "points": 90.0},
        {"matchup_id": 2, "roster_id": 6, "points": 50.0},
        {"matchup_id": 2, "roster_id": 7, "points": 60.0},
        {"matchup_id": 3, "roster_id": 3, "points": 70.0},
        {"matchup_id": 3, "roster_id": 8, "points": 80.0},
        {"matchup_id": 4, "roster_id": 4, "points": 90.0},
        {"matchup_id": 4, "roster_id": 9, "points": 90.0},
        {"matchup_id": 5, "roster_id": 5, "points": 100.0},
        {"matchup_id": 5, "roster_id": 10, "points": 110.0},
    ]

    week_res = calc.process_week(1, matchups, sample_roster_meta)
    p1 = [p for p in week_res["pair_results"] if p["pair_id"] == 1][0]
    assert p1["weighted_score"] == 85.0


def test_tiebreaker_points_for(sample_config, sample_roster_meta):
    """Test that when pairs have equal wins, total points for acts as the tiebreaker."""
    calc = StandingsCalculator(sample_config)

    # Week 1: Pair 1 and Pair 2 both go 2-0, but Pair 2 has more points
    matchups = [
        # Pair 1: B1 (100) vs B3 (80), E6 (100) vs E8 (80) -> 2-0, 200 pts
        {"matchup_id": 1, "roster_id": 1, "points": 100.0},
        {"matchup_id": 1, "roster_id": 3, "points": 80.0},
        {"matchup_id": 2, "roster_id": 6, "points": 100.0},
        {"matchup_id": 2, "roster_id": 8, "points": 80.0},
        # Pair 2: B2 (120) vs B4 (80), E7 (120) vs E9 (80) -> 2-0, 240 pts
        {"matchup_id": 3, "roster_id": 2, "points": 120.0},
        {"matchup_id": 3, "roster_id": 4, "points": 80.0},
        {"matchup_id": 4, "roster_id": 7, "points": 120.0},
        {"matchup_id": 4, "roster_id": 9, "points": 80.0},
        # Pair 5:
        {"matchup_id": 5, "roster_id": 5, "points": 50.0},
        {"matchup_id": 5, "roster_id": 10, "points": 60.0},
    ]

    league = {"name": "Test League", "season": "2024"}
    users = [{"user_id": f"u{i}", "display_name": f"User {i}"} for i in range(1, 11)]
    rosters = [{"roster_id": i, "owner_id": f"u{i}"} for i in range(1, 11)]
    matchups_by_week = {1: matchups}

    standings = calc.calculate_season_standings(league, users, rosters, matchups_by_week)
    pairs = standings["pair_standings"]

    # Rank 1 must be Pair 2 because it has 240.0 pts vs Pair 1's 200.0 pts despite equal wins
    assert pairs[0]["pair_name"] == "Pair Beta"
    assert pairs[0]["rank"] == 1
    assert pairs[0]["points_for"] == 240.0

    assert pairs[1]["pair_name"] == "Pair Alpha"
    assert pairs[1]["rank"] == 2
    assert pairs[1]["points_for"] == 200.0

    # Top 4 qualify for playoffs, 5th eliminated
    assert pairs[0]["is_playoff_seed"] is True
    assert pairs[1]["is_playoff_seed"] is True
    assert pairs[4]["is_playoff_seed"] is False
    assert pairs[4]["seed"] is None


def test_unplayed_week_handling(sample_config, sample_roster_meta):
    """Test that a scheduled week with 0.0 scores is treated as unplayed without assigning 0.5 ties."""
    calc = StandingsCalculator(sample_config)

    matchups = [
        {"matchup_id": 1, "roster_id": 1, "points": 0.0},
        {"matchup_id": 1, "roster_id": 6, "points": 0.0},
        {"matchup_id": 2, "roster_id": 2, "points": 0.0},
        {"matchup_id": 2, "roster_id": 7, "points": 0.0},
        {"matchup_id": 3, "roster_id": 3, "points": 0.0},
        {"matchup_id": 3, "roster_id": 8, "points": 0.0},
        {"matchup_id": 4, "roster_id": 4, "points": 0.0},
        {"matchup_id": 4, "roster_id": 9, "points": 0.0},
        {"matchup_id": 5, "roster_id": 5, "points": 0.0},
        {"matchup_id": 5, "roster_id": 10, "points": 0.0},
    ]

    week_res = calc.process_week(1, matchups, sample_roster_meta)
    assert week_res["is_unplayed"] is True
    assert week_res["awards"] == {}

    league = {"name": "chuzzez", "season": "2026"}
    users = [{"user_id": f"u{i}", "display_name": f"User {i}"} for i in range(1, 11)]
    rosters = [{"roster_id": i, "owner_id": f"u{i}"} for i in range(1, 11)]
    standings = calc.calculate_season_standings(league, users, rosters, {1: matchups})

    assert standings["is_preseason"] is True
    assert standings["current_week"] == 0
    for p in standings["pair_standings"]:
        assert p["wins"] == 0.0
        assert p["losses"] == 0.0
        assert p["ties"] == 0.0


