"""Generates HTML dashboard (docs/index.html) and CSV export (docs/standings.csv) from computed standings."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape


def export_csv(standings_data: Dict[str, Any], output_path: Path) -> None:
    """Export the official pair standings to a clean CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pair_standings = standings_data.get("pair_standings", [])

    fieldnames = [
        "Rank",
        "Seed",
        "Pair Name",
        "Beginner",
        "Mentor",
        "Wins",
        "Losses",
        "Ties",
        "Win Pct",
        "Points For",
        "Points Against",
        "Avg Points",
        "Upset Bonus Wins",
        "Weighted Score Total",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in pair_standings:
            writer.writerow({
                "Rank": p.get("rank"),
                "Seed": p.get("seed") or "Eliminated",
                "Pair Name": p.get("pair_name"),
                "Beginner": p.get("beginner_name"),
                "Mentor": p.get("expert_name"),
                "Wins": p.get("wins"),
                "Losses": p.get("losses"),
                "Ties": p.get("ties"),
                "Win Pct": p.get("win_pct"),
                "Points For": p.get("points_for"),
                "Points Against": p.get("points_against"),
                "Avg Points": p.get("avg_points"),
                "Upset Bonus Wins": p.get("upsets_total"),
                "Weighted Score Total": p.get("weighted_score_total"),
            })


def render_html_dashboard(
    standings_data: Dict[str, Any],
    template_dir: Path,
    output_html_path: Path,
) -> None:
    """Render HTML dashboard with Jinja2."""
    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    template = env.get_template("standings.html.j2")
    rendered_html = template.render(
        data=standings_data,
        league_name=standings_data.get("league_name", "Mentor League"),
        season=standings_data.get("season", "2024"),
        total_weeks=standings_data.get("total_weeks", 0),
        current_week=standings_data.get("current_week", 0),
        active_week=standings_data.get("active_week", 1),
        is_preseason=standings_data.get("is_preseason", False),
        pair_standings=standings_data.get("pair_standings", []),
        mentee_standings=standings_data.get("mentee_standings", []),
        beginner_leaderboard=standings_data.get("beginner_leaderboard", []),
        mentor_leaderboard=standings_data.get("mentor_leaderboard", []),
        playoffs_preview=standings_data.get("playoffs_preview"),
        weekly_snapshots=standings_data.get("weekly_snapshots", []),
    )

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)


def generate_reports(
    standings_json_path: Optional[Path] = None,
    template_dir: Optional[Path] = None,
    docs_dir: Optional[Path] = None,
) -> None:
    """Generate all reports (HTML and CSV) from data/standings.json."""
    if standings_json_path is None:
        standings_json_path = Path("data/standings.json")
    if template_dir is None:
        template_dir = Path("templates")
    if docs_dir is None:
        docs_dir = Path("docs")

    if not standings_json_path.exists():
        raise FileNotFoundError(f"Standings file not found: {standings_json_path}")

    with open(standings_json_path, "r", encoding="utf-8") as f:
        standings_data = json.load(f)

    html_out = docs_dir / "index.html"
    csv_out = docs_dir / "standings.csv"

    print(f"Rendering HTML dashboard to {html_out}...")
    render_html_dashboard(standings_data, template_dir, html_out)

    print(f"Exporting standings CSV to {csv_out}...")
    export_csv(standings_data, csv_out)

    print("Reports generated successfully!")

