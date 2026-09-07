"""Standings and scoring engine for the Fantasy Football Mentor League.

Implements the official ruleset:
- Combined pair W/L records
- Upset Bonus (1.5x wins when a Beginner beats an Expert)
- Pair-vs-pair 1-1 wash handling
- Total points-for tiebreaker
- Weighted Mentee scores (0.7 beginner + 0.3 expert)
- Individual peer leaderboards (Beginners vs Beginners, Mentors vs Mentors)
- Weekly awards calculation
"""

from typing import Any, Dict, List, Optional, Tuple
import json
from pathlib import Path


class StandingsCalculator:
    """Calculates pair and individual standings from Sleeper league data."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.upset_multiplier = float(config.get("upset_bonus_multiplier", 1.5))
        self.weighted_config = config.get("weighted_score", {"beginner_weight": 0.7, "expert_weight": 0.3})
        self.beginner_weight = float(self.weighted_config.get("beginner_weight", 0.7))
        self.expert_weight = float(self.weighted_config.get("expert_weight", 0.3))
        self.playoff_qualifiers = int(config.get("playoff_qualifiers", 4))

        # Build mappings
        self.pairs_raw = config.get("pairs", [])
        self.roster_to_pair: Dict[int, Dict[str, Any]] = {}
        self.roster_to_role: Dict[int, str] = {}
        self._init_pair_mappings()

    def _init_pair_mappings(self) -> None:
        """Parse pair configuration into fast lookup dictionaries."""
        for p in self.pairs_raw:
            pair_id = p.get("id", p.get("name"))
            pair_name = p.get("name", f"Pair {pair_id}")

            # Support both nested {"beginner": {"roster_id": 1}} and flat {"beginner_roster_id": 1}
            beg_data = p.get("beginner", {})
            if isinstance(beg_data, dict):
                beg_id = beg_data.get("roster_id")
                beg_name = beg_data.get("name", "")
            else:
                beg_id = beg_data
                beg_name = ""

            if beg_id is None:
                beg_id = p.get("beginner_roster_id")

            exp_data = p.get("expert", {})
            if isinstance(exp_data, dict):
                exp_id = exp_data.get("roster_id")
                exp_name = exp_data.get("name", "")
            else:
                exp_id = exp_data
                exp_name = ""

            if exp_id is None:
                exp_id = p.get("expert_roster_id")

            pair_info = {
                "pair_id": pair_id,
                "pair_name": pair_name,
                "beginner_roster_id": int(beg_id) if beg_id is not None else None,
                "beginner_name": beg_name,
                "expert_roster_id": int(exp_id) if exp_id is not None else None,
                "expert_name": exp_name,
            }

            if pair_info["beginner_roster_id"] is not None:
                self.roster_to_pair[pair_info["beginner_roster_id"]] = pair_info
                self.roster_to_role[pair_info["beginner_roster_id"]] = "beginner"

            if pair_info["expert_roster_id"] is not None:
                self.roster_to_pair[pair_info["expert_roster_id"]] = pair_info
                self.roster_to_role[pair_info["expert_roster_id"]] = "expert"

    def enrich_roster_metadata(self, users: List[Dict[str, Any]], rosters: List[Dict[str, Any]]) -> Dict[int, Dict[str, str]]:
        """Map roster_id -> display_name, team_name, and avatar."""
        user_map = {u.get("user_id"): u for u in users}
        roster_meta: Dict[int, Dict[str, str]] = {}

        for r in rosters:
            r_id = r.get("roster_id")
            if r_id is None:
                continue
            owner_id = r.get("owner_id")
            user = user_map.get(owner_id, {})
            metadata = user.get("metadata", {}) or {}

            team_name = metadata.get("team_name") or f"Team {r_id}"
            display_name = user.get("display_name") or f"Owner {r_id}"
            avatar = user.get("avatar") or ""

            roster_meta[int(r_id)] = {
                "team_name": team_name,
                "display_name": display_name,
                "avatar": avatar,
            }

        return roster_meta

    def process_week(
        self,
        week_num: int,
        matchups: List[Dict[str, Any]],
        roster_meta: Dict[int, Dict[str, str]],
    ) -> Dict[str, Any]:
        """Compute all scoring and results for a single week."""
        # Group matchups by matchup_id
        matchups_by_id: Dict[int, List[Dict[str, Any]]] = {}
        for m in matchups:
            m_id = m.get("matchup_id")
            if m_id is not None:
                matchups_by_id.setdefault(m_id, []).append(m)

        # Map roster_id -> individual game stats
        individual_results: Dict[int, Dict[str, Any]] = {}
        matchup_games: List[Dict[str, Any]] = []

        # Check if week is unplayed (all scores 0.0)
        total_week_points = sum(float(m.get("points") or 0.0) for m in matchups)
        is_unplayed = (total_week_points == 0.0)

        for m_id, teams in matchups_by_id.items():
            if len(teams) == 2:
                t1, t2 = teams[0], teams[1]
                r1_id = int(t1["roster_id"])
                r2_id = int(t2["roster_id"])
                pts1 = round(float(t1.get("points") or 0.0), 2)
                pts2 = round(float(t2.get("points") or 0.0), 2)

                role1 = self.roster_to_role.get(r1_id, "unknown")
                role2 = self.roster_to_role.get(r2_id, "unknown")
                pair1_id = self.roster_to_pair.get(r1_id, {}).get("pair_id")
                pair2_id = self.roster_to_pair.get(r2_id, {}).get("pair_id")
                is_internal_pair_matchup = (pair1_id is not None and pair1_id == pair2_id)

                # Determine winners
                if is_unplayed:
                    t1_win, t2_win = 0.0, 0.0
                    t1_loss, t2_loss = 0.0, 0.0
                    t1_tie, t2_tie = 0.0, 0.0
                    t1_points_award = 0.0
                    t2_points_award = 0.0
                    t1_upset = False
                    t2_upset = False
                    margin = 0.0
                elif pts1 > pts2:
                    t1_win, t2_win = 1.0, 0.0
                    t1_loss, t2_loss = 0.0, 1.0
                    t1_tie, t2_tie = 0.0, 0.0
                    t1_points_award = t1_win
                    t2_points_award = t2_win
                    t1_upset = False
                    t2_upset = False
                    if not is_internal_pair_matchup and role1 == "beginner" and role2 == "expert":
                        t1_upset = True
                        t1_points_award = self.upset_multiplier
                    margin = round(abs(pts1 - pts2), 2)
                elif pts2 > pts1:
                    t1_win, t2_win = 0.0, 1.0
                    t1_loss, t2_loss = 1.0, 0.0
                    t1_tie, t2_tie = 0.0, 0.0
                    t1_points_award = t1_win
                    t2_points_award = t2_win
                    t1_upset = False
                    t2_upset = False
                    if not is_internal_pair_matchup and role2 == "beginner" and role1 == "expert":
                        t2_upset = True
                        t2_points_award = self.upset_multiplier
                    margin = round(abs(pts1 - pts2), 2)
                else:
                    t1_win, t2_win = 0.5, 0.5
                    t1_loss, t2_loss = 0.0, 0.0
                    t1_tie, t2_tie = 1.0, 1.0
                    t1_points_award = 0.5
                    t2_points_award = 0.5
                    t1_upset = False
                    t2_upset = False
                    margin = 0.0

                game_data = {
                    "matchup_id": m_id,
                    "team1": {
                        "roster_id": r1_id,
                        "name": roster_meta.get(r1_id, {}).get("display_name", f"Team {r1_id}"),
                        "role": role1,
                        "points": pts1,
                        "win": t1_win,
                        "win_credited": t1_points_award,
                        "upset": t1_upset,
                    },
                    "team2": {
                        "roster_id": r2_id,
                        "name": roster_meta.get(r2_id, {}).get("display_name", f"Team {r2_id}"),
                        "role": role2,
                        "points": pts2,
                        "win": t2_win,
                        "win_credited": t2_points_award,
                        "upset": t2_upset,
                    },
                    "margin": margin,
                    "is_upset": t1_upset or t2_upset,
                    "upset_winner": r1_id if t1_upset else (r2_id if t2_upset else None),
                }
                matchup_games.append(game_data)

                individual_results[r1_id] = {
                    "points": pts1,
                    "opponent_roster_id": r2_id,
                    "opponent_points": pts2,
                    "opponent_role": role2,
                    "win": t1_win,
                    "loss": t1_loss,
                    "tie": t1_tie,
                    "win_credited": t1_points_award,
                    "upset": t1_upset,
                    "margin": margin,
                }
                individual_results[r2_id] = {
                    "points": pts2,
                    "opponent_roster_id": r1_id,
                    "opponent_points": pts1,
                    "opponent_role": role1,
                    "win": t2_win,
                    "loss": t2_loss,
                    "tie": t2_tie,
                    "win_credited": t2_points_award,
                    "upset": t2_upset,
                    "margin": margin,
                }
            elif len(teams) == 1:
                # Bye week or unmatched team (rare in regular 10-team)
                t = teams[0]
                r_id = int(t["roster_id"])
                pts = round(float(t.get("points") or 0.0), 2)
                individual_results[r_id] = {
                    "points": pts,
                    "opponent_roster_id": None,
                    "opponent_points": 0.0,
                    "opponent_role": None,
                    "win": 1.0,
                    "loss": 0.0,
                    "tie": 0.0,
                    "win_credited": 1.0,
                    "upset": False,
                    "margin": pts,
                }

        # Compute pair results for the week
        pair_weekly_results: List[Dict[str, Any]] = []
        for p in self.pairs_raw:
            pair_id = p.get("id", p.get("name"))
            pair_name = p.get("name", f"Pair {pair_id}")

            beg_id = p.get("beginner_roster_id") or (p.get("beginner", {}) if isinstance(p.get("beginner"), dict) else {}).get("roster_id")
            exp_id = p.get("expert_roster_id") or (p.get("expert", {}) if isinstance(p.get("expert"), dict) else {}).get("roster_id")

            beg_id = int(beg_id) if beg_id is not None else None
            exp_id = int(exp_id) if exp_id is not None else None

            beg_res = individual_results.get(beg_id, {"points": 0.0, "win_credited": 0.0, "win": 0.0, "loss": 0.0, "tie": 0.0, "upset": False, "opponent_points": 0.0})
            exp_res = individual_results.get(exp_id, {"points": 0.0, "win_credited": 0.0, "win": 0.0, "loss": 0.0, "tie": 0.0, "upset": False, "opponent_points": 0.0})

            beg_pts = beg_res["points"]
            exp_pts = exp_res["points"]
            total_pair_pts = round(beg_pts + exp_pts, 2)
            total_opp_pts = round(beg_res.get("opponent_points", 0.0) + exp_res.get("opponent_points", 0.0), 2)

            # Pair wins with upset multiplier
            pair_wins = round(beg_res["win_credited"] + exp_res["win_credited"], 2)
            pair_losses = round(beg_res["loss"] + exp_res["loss"], 2)
            pair_ties = round(beg_res["tie"] + exp_res["tie"], 2)

            # Weighted Mentee score: 0.7 * B + 0.3 * E
            weighted_score = round((self.beginner_weight * beg_pts) + (self.expert_weight * exp_pts), 2)

            upsets_count = (1 if beg_res.get("upset") else 0)

            pair_weekly_results.append({
                "pair_id": pair_id,
                "pair_name": pair_name,
                "beginner_roster_id": beg_id,
                "expert_roster_id": exp_id,
                "beginner_name": roster_meta.get(beg_id, {}).get("display_name", f"Team {beg_id}"),
                "expert_name": roster_meta.get(exp_id, {}).get("display_name", f"Team {exp_id}"),
                "beginner_points": beg_pts,
                "expert_points": exp_pts,
                "beginner_upset": beg_res.get("upset", False),
                "combined_points": total_pair_pts,
                "opponent_points": total_opp_pts,
                "wins": pair_wins,
                "losses": pair_losses,
                "ties": pair_ties,
                "weighted_score": weighted_score,
                "upsets_count": upsets_count,
            })

        # Calculate Weekly Awards (§2: Highest Combined Score, Biggest Blowout, Closest Match, Best Upset)
        awards = self._calculate_weekly_awards(matchup_games, pair_weekly_results, roster_meta) if not is_unplayed else {}

        return {
            "week": week_num,
            "is_unplayed": is_unplayed,
            "matchup_games": matchup_games,
            "individual_results": individual_results,
            "pair_results": pair_weekly_results,
            "awards": awards,
        }

    def _calculate_weekly_awards(
        self,
        matchup_games: List[Dict[str, Any]],
        pair_results: List[Dict[str, Any]],
        roster_meta: Dict[int, Dict[str, str]],
    ) -> Dict[str, Any]:
        """Compute the official weekly awards."""
        awards: Dict[str, Any] = {}

        # 1. Highest Combined Score
        if pair_results:
            top_pair = max(pair_results, key=lambda x: x["combined_points"])
            awards["highest_combined_score"] = {
                "title": "Highest Combined Score",
                "winner": top_pair["pair_name"],
                "score": top_pair["combined_points"],
                "detail": f"{top_pair['beginner_name']} ({top_pair['beginner_points']} pts) + {top_pair['expert_name']} ({top_pair['expert_points']} pts)"
            }

        # 2. Biggest Blowout (individual matchup with largest margin)
        if matchup_games:
            blowout = max(matchup_games, key=lambda x: x["margin"])
            w = blowout["team1"] if blowout["team1"]["points"] > blowout["team2"]["points"] else blowout["team2"]
            l = blowout["team2"] if blowout["team1"]["points"] > blowout["team2"]["points"] else blowout["team1"]
            awards["biggest_blowout"] = {
                "title": "Biggest Blowout",
                "winner": w["name"],
                "loser": l["name"],
                "margin": blowout["margin"],
                "detail": f"{w['points']} to {l['points']} (+{blowout['margin']} margin)"
            }

            # 3. Closest Match (individual matchup with smallest margin)
            closest = min(matchup_games, key=lambda x: x["margin"])
            cw = closest["team1"] if closest["team1"]["points"] >= closest["team2"]["points"] else closest["team2"]
            cl = closest["team2"] if closest["team1"]["points"] >= closest["team2"]["points"] else closest["team1"]
            awards["closest_match"] = {
                "title": "Closest Match",
                "winner": cw["name"],
                "loser": cl["name"],
                "margin": closest["margin"],
                "detail": f"{cw['points']} to {cl['points']} (separated by only {closest['margin']} pts!)"
            }

            # 4. Best Upset (Beginner beating Expert with largest margin)
            upset_games = [g for g in matchup_games if g["is_upset"]]
            if upset_games:
                best_upset_game = max(upset_games, key=lambda x: x["margin"])
                u_win = best_upset_game["team1"] if best_upset_game["team1"]["upset"] else best_upset_game["team2"]
                u_lose = best_upset_game["team2"] if best_upset_game["team1"]["upset"] else best_upset_game["team1"]
                awards["best_upset"] = {
                    "title": "Best Upset",
                    "winner": u_win["name"],
                    "defeated": u_lose["name"],
                    "margin": best_upset_game["margin"],
                    "detail": f"Beginner {u_win['name']} ({u_win['points']} pts) toppled Expert {u_lose['name']} ({u_lose['points']} pts) earning a +1.5 win bonus!"
                }
            else:
                awards["best_upset"] = {
                    "title": "Best Upset",
                    "winner": "None",
                    "detail": "No beginner upsets occurred this week."
                }

        return awards

    def calculate_season_standings(
        self,
        league: Dict[str, Any],
        users: List[Dict[str, Any]],
        rosters: List[Dict[str, Any]],
        matchups_by_week: Dict[int, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Compile cumulative pair standings, peer leaderboards, and historical snapshots."""
        roster_meta = self.enrich_roster_metadata(users, rosters)

        # Process each week in sequence
        weekly_snapshots: List[Dict[str, Any]] = []
        cumulative_pairs: Dict[Any, Dict[str, Any]] = {}

        for p in self.pairs_raw:
            pair_id = p.get("id", p.get("name"))
            pair_name = p.get("name", f"Pair {pair_id}")
            beg_id = p.get("beginner_roster_id") or (p.get("beginner", {}) if isinstance(p.get("beginner"), dict) else {}).get("roster_id")
            exp_id = p.get("expert_roster_id") or (p.get("expert", {}) if isinstance(p.get("expert"), dict) else {}).get("roster_id")
            beg_id = int(beg_id) if beg_id is not None else None
            exp_id = int(exp_id) if exp_id is not None else None

            cumulative_pairs[pair_id] = {
                "pair_id": pair_id,
                "pair_name": pair_name,
                "beginner_roster_id": beg_id,
                "expert_roster_id": exp_id,
                "beginner_name": roster_meta.get(beg_id, {}).get("display_name", f"Team {beg_id}"),
                "expert_name": roster_meta.get(exp_id, {}).get("display_name", f"Team {exp_id}"),
                "wins": 0.0,
                "losses": 0.0,
                "ties": 0.0,
                "points_for": 0.0,
                "points_against": 0.0,
                "weighted_score_total": 0.0,
                "upsets_total": 0,
                "weeks_played": 0,
                "weekly_history": [],
            }

        # Track individual stats for peer leaderboards
        individual_peer_stats: Dict[int, Dict[str, Any]] = {}
        for r_id, role in self.roster_to_role.items():
            individual_peer_stats[r_id] = {
                "roster_id": r_id,
                "role": role,
                "name": roster_meta.get(r_id, {}).get("display_name", f"Team {r_id}"),
                "team_name": roster_meta.get(r_id, {}).get("team_name", ""),
                "wins": 0.0,
                "losses": 0.0,
                "ties": 0.0,
                "points_for": 0.0,
                "points_against": 0.0,
            }

        sorted_weeks = sorted(matchups_by_week.keys())
        for w_num in sorted_weeks:
            m_list = matchups_by_week[w_num]
            week_result = self.process_week(w_num, m_list, roster_meta)
            weekly_snapshots.append(week_result)

            if not week_result["is_unplayed"]:
                # Accumulate pair stats
                for p_res in week_result["pair_results"]:
                    p_id = p_res["pair_id"]
                    cum = cumulative_pairs[p_id]
                    cum["wins"] = round(cum["wins"] + p_res["wins"], 2)
                    cum["losses"] = round(cum["losses"] + p_res["losses"], 2)
                    cum["ties"] = round(cum["ties"] + p_res["ties"], 2)
                    cum["points_for"] = round(cum["points_for"] + p_res["combined_points"], 2)
                    cum["points_against"] = round(cum["points_against"] + p_res["opponent_points"], 2)
                    cum["weighted_score_total"] = round(cum["weighted_score_total"] + p_res["weighted_score"], 2)
                    cum["upsets_total"] += p_res["upsets_count"]
                    cum["weeks_played"] += 1
                    cum["weekly_history"].append({
                        "week": w_num,
                        "wins": p_res["wins"],
                        "losses": p_res["losses"],
                        "points": p_res["combined_points"],
                        "weighted_score": p_res["weighted_score"],
                        "upset": p_res["beginner_upset"],
                    })

                # Accumulate individual stats (unmodified wins, no upset bonus for peer leaderboards)
                for r_id, ind_res in week_result["individual_results"].items():
                    if r_id in individual_peer_stats:
                        ind = individual_peer_stats[r_id]
                        ind["wins"] += ind_res["win"]
                        ind["losses"] += ind_res["loss"]
                        ind["ties"] += ind_res["tie"]
                        ind["points_for"] = round(ind["points_for"] + ind_res["points"], 2)
                        ind["points_against"] = round(ind["points_against"] + ind_res.get("opponent_points", 0.0), 2)

        # Sort Official Pair Standings (§2): Ranked by wins desc, tiebreaker points_for desc
        pair_standings_list = list(cumulative_pairs.values())
        pair_standings_list.sort(key=lambda x: (x["wins"], x["points_for"]), reverse=True)

        # Assign ranks and playoff seeding status
        for idx, item in enumerate(pair_standings_list, start=1):
            item["rank"] = idx
            item["win_pct"] = round(item["wins"] / max(1, item["wins"] + item["losses"]), 3)
            item["avg_points"] = round(item["points_for"] / max(1, item["weeks_played"]), 2)
            item["avg_weighted_score"] = round(item["weighted_score_total"] / max(1, item["weeks_played"]), 2)
            # Playoff qualifier status: Top 4 qualify, 5th eliminated
            item["is_playoff_seed"] = (idx <= self.playoff_qualifiers)
            item["seed"] = idx if idx <= self.playoff_qualifiers else None

        # Build Playoff Virtual Matchups preview
        playoffs_preview = None
        if len(pair_standings_list) >= 4:
            s1, s2, s3, s4 = pair_standings_list[0], pair_standings_list[1], pair_standings_list[2], pair_standings_list[3]
            playoffs_preview = {
                "semifinal_1": {"seed_high": s1, "seed_low": s4},
                "semifinal_2": {"seed_high": s2, "seed_low": s3},
            }

        # Mentee Performance Leaderboard (Ranked by average/total weighted score)
        mentee_standings = sorted(
            pair_standings_list,
            key=lambda x: x["weighted_score_total"],
            reverse=True
        )

        # Peer Leaderboards (Beginners vs Beginners, Mentors vs Mentors)
        beginners = [
            ind for ind in individual_peer_stats.values() if ind["role"] == "beginner"
        ]
        beginners.sort(key=lambda x: (x["wins"], x["points_for"]), reverse=True)
        for i, b in enumerate(beginners, start=1):
            b["rank"] = i
            total_g = b["wins"] + b["losses"] + b["ties"]
            b["win_pct"] = round(b["wins"] / max(1, total_g), 3)

        mentors = [
            ind for ind in individual_peer_stats.values() if ind["role"] == "expert"
        ]
        mentors.sort(key=lambda x: (x["wins"], x["points_for"]), reverse=True)
        for i, m in enumerate(mentors, start=1):
            m["rank"] = i
            total_g = m["wins"] + m["losses"] + m["ties"]
            m["win_pct"] = round(m["wins"] / max(1, total_g), 3)

        played_weeks = [w["week"] for w in weekly_snapshots if not w.get("is_unplayed")]
        is_preseason = (len(played_weeks) == 0)
        current_completed_week = played_weeks[-1] if played_weeks else 0
        active_display_week = sorted_weeks[0] if (is_preseason and sorted_weeks) else (played_weeks[-1] if played_weeks else 1)

        return {
            "league_name": league.get("name", "Fantasy Mentor League"),
            "season": league.get("season", "2024"),
            "total_weeks": len(sorted_weeks),
            "current_week": current_completed_week,
            "active_week": active_display_week,
            "is_preseason": is_preseason,
            "pair_standings": pair_standings_list,
            "mentee_standings": mentee_standings,
            "beginner_leaderboard": beginners,
            "mentor_leaderboard": mentors,
            "playoffs_preview": playoffs_preview,
            "weekly_snapshots": weekly_snapshots,
        }

