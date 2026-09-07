"""Main CLI entrypoint for the Fantasy Football Mentor League Application."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from .fetch_data import (
    fetch_league_data,
    generate_mock_data,
    load_cached_data,
    load_pairs_config,
    save_json,
)
from .generate_report import generate_reports
from .sleeper_client import SleeperClient
from .standings import StandingsCalculator


def run_init_pairs(client: SleeperClient, league_id: str, config_path: Path) -> None:
    """Helper tool to inspect a real Sleeper league and display all teams/owners to easily assign pairs."""
    print(f"\n--- Sleeper League Inspector ({league_id}) ---")
    try:
        league = client.get_league(league_id)
        users = client.get_users(league_id)
        rosters = client.get_rosters(league_id)
    except Exception as e:
        print(f"Failed to fetch league data from Sleeper: {e}")
        return

    user_map = {u.get("user_id"): u for u in users}
    print(f"League: {league.get('name')} (Season {league.get('season')}, {len(rosters)} Teams)\n")
    print(f"{'Roster ID':<10} {'Owner Display Name':<25} {'Team Name':<30}")
    print("-" * 65)

    team_catalog = []
    for r in rosters:
        r_id = r.get("roster_id")
        owner_id = r.get("owner_id")
        user = user_map.get(owner_id, {})
        display_name = user.get("display_name", "Unknown")
        team_name = (user.get("metadata") or {}).get("team_name", f"Team {r_id}")
        print(f"{r_id:<10} {display_name:<25} {team_name:<30}")
        team_catalog.append({
            "roster_id": r_id,
            "display_name": display_name,
            "team_name": team_name
        })

    print("-" * 65)
    print("\nTo assign pairs, edit config/pairs.json with the corresponding roster_id values,")
    print("or provide your desired pairings to this assistant and we will update it for you!\n")


def run_pipeline(
    fetch: bool = False,
    mock: bool = False,
    week: int = None,
    config_path: Path = Path("config/pairs.json"),
    data_dir: Path = Path("data"),
    docs_dir: Path = Path("docs"),
    templates_dir: Path = Path("templates"),
) -> None:
    """Execute the full data fetch -> standings calculation -> report generation workflow."""
    config = load_pairs_config(config_path)
    league_id = str(config.get("league_id", "")).strip()

    is_placeholder = (not league_id or "REPLACE" in league_id.upper() or league_id == "123456789")

    # Determine whether to use mock data or live fetch
    raw_dir = data_dir / "raw"
    if mock or (is_placeholder and not raw_dir.exists()):
        print("\n[INFO] Running with mock data (demo mode)...")
        raw_data = generate_mock_data(weeks=week or 3, output_dir=raw_dir)
    elif fetch:
        if is_placeholder:
            print("[ERROR] Please specify a valid Sleeper league_id in config/pairs.json before fetching live data.")
            sys.exit(1)
        client = SleeperClient()
        raw_data = fetch_league_data(client, league_id, max_week=week, output_dir=raw_dir)
    else:
        # Try loading existing cached data, fallback to mock if empty
        try:
            raw_data = load_cached_data(raw_dir)
        except Exception:
            print("\n[INFO] No cached data found. Generating mock data for instant preview...")
            raw_data = generate_mock_data(weeks=week or 3, output_dir=raw_dir)

    print("\nCalculating Mentor League standings and awards...")
    calculator = StandingsCalculator(config)
    standings = calculator.calculate_season_standings(
        league=raw_data["league"],
        users=raw_data["users"],
        rosters=raw_data["rosters"],
        matchups_by_week=raw_data["matchups_by_week"],
    )

    standings_json_path = data_dir / "standings.json"
    save_json(standings_json_path, standings)
    print(f"Standings saved to {standings_json_path}")

    # Generate Reports
    generate_reports(
        standings_json_path=standings_json_path,
        template_dir=templates_dir,
        docs_dir=docs_dir,
    )

    # Print summary to console
    print("\n" + "=" * 70)
    print(f"🏆 {standings['league_name']} — OFFICIAL PAIR STANDINGS (Week {standings['current_week']})")
    print("=" * 70)
    print(f"{'Rank':<5} {'Pair Name':<22} {'Record':<10} {'Win %':<8} {'Pts For':<10} {'Upsets':<8}")
    print("-" * 70)
    for p in standings["pair_standings"]:
        record = f"{p['wins']}-{p['losses']}"
        seed_label = f"(Seed #{p['seed']})" if p['is_playoff_seed'] else "(Elim)"
        print(f"#{p['rank']:<4} {p['pair_name']:<22} {record:<10} {p['win_pct']:<8.3f} {p['points_for']:<10.2f} {p['upsets_total']:<8} {seed_label}")
    print("=" * 70)
    print(f"\n✨ Dashboard compiled: {docs_dir / 'index.html'}")
    print(f"📄 CSV export created: {docs_dir / 'standings.csv'}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fantasy Football Mentor League Manager")
    parser.add_argument("--fetch", action="store_true", help="Fetch live data from Sleeper API")
    parser.add_argument("--mock", action="store_true", help="Generate/use mock data for testing/demo")
    parser.add_argument("--week", type=int, default=None, help="Target week number")
    parser.add_argument("--init-pairs", action="store_true", help="Inspect Sleeper league and help assign pairs")
    parser.add_argument("--serve", action="store_true", help="Host dashboard locally on HTTP server")
    parser.add_argument("--port", type=int, default=8000, help="Port to host locally (default: 8000)")
    parser.add_argument("--config", type=str, default="config/pairs.json", help="Path to config file")

    args = parser.parse_args()
    config_path = Path(args.config)

    if args.init_pairs:
        config = load_pairs_config(config_path)
        league_id = str(config.get("league_id", "")).strip()
        if not league_id or "REPLACE" in league_id.upper():
            league_id = input("Enter Sleeper League ID: ").strip()
        client = SleeperClient()
        run_init_pairs(client, league_id, config_path)
        return

    if args.serve:
        import http.server
        import socketserver
        import webbrowser
        docs_dir = Path("docs")

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(docs_dir), **kw)

        with socketserver.TCPServer(("", args.port), Handler) as httpd:
            url = f"http://localhost:{args.port}"
            print(f"\n🚀 Local Mentor League Dashboard running at: {url}")
            print("Press Ctrl+C to stop the server.\n")
            try:
                webbrowser.open(url)
            except Exception:
                pass
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
        return

    run_pipeline(
        fetch=args.fetch,
        mock=args.mock,
        week=args.week,
        config_path=config_path,
    )


if __name__ == "__main__":
    main()

