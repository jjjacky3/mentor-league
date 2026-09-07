"""Client for interacting with the public Sleeper Fantasy Football API."""

from typing import Any, Dict, List, Optional
import requests

SLEEPER_API_BASE = "https://api.sleeper.app/v1"


class SleeperClient:
    """Client for fetching public league and matchup data from Sleeper."""

    def __init__(self, base_url: str = SLEEPER_API_BASE, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MentorLeagueApp/1.0",
            "Accept": "application/json"
        })

    def _get(self, endpoint: str) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Error requesting Sleeper API endpoint '{url}': {e}") from e

    def get_league(self, league_id: str) -> Dict[str, Any]:
        """Fetch league metadata (settings, scoring rules, season, status)."""
        return self._get(f"league/{league_id}")

    def get_rosters(self, league_id: str) -> List[Dict[str, Any]]:
        """Fetch all rosters in the league (maps roster_id to owner_id and player stats)."""
        return self._get(f"league/{league_id}/rosters")

    def get_users(self, league_id: str) -> List[Dict[str, Any]]:
        """Fetch all user profiles in the league (display_name, team_name, avatar)."""
        return self._get(f"league/{league_id}/users")

    def get_matchups(self, league_id: str, week: int) -> List[Dict[str, Any]]:
        """Fetch individual matchup results for a specific week."""
        return self._get(f"league/{league_id}/matchups/{week}")

    def get_nfl_state(self, sport: str = "nfl") -> Dict[str, Any]:
        """Fetch current NFL calendar state (current week, season, season_type)."""
        return self._get(f"state/{sport}")

