import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import http_client, resource_limits
from .const import (
    HANDBALL_NET_BASE_URL,
    HANDBALL_NET_NEW_API_BASE_URL,
    HANDBALL_NET_WEB_URL,
)
from .http_client import HandballNetHTTPError, async_get_json
from .resource_limits import (
    charge_match_records,
    validate_fields,
    validate_last_page,
    validate_records,
)
from .utils import HandballNetUtils

_LOGGER = logging.getLogger(__name__)

class HandballNetAPI:
    """API client for handball.net"""

    LEAGUE_TABLE_CACHE_TTL = 3600  # 1 hour
    TEAM_SCHEDULE_CACHE_TTL = 3600  # 1 hour
    TEAM_INFO_CACHE_TTL = 21600  # 6 hours

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.base_url = HANDBALL_NET_BASE_URL
        self.utils = HandballNetUtils()
        self.session = async_get_clientsession(hass)
        self._league_table_cache: dict[str | int, tuple[float, List[Dict[str, Any]]]] = {}
        self._team_schedule_cache: dict[str | int, tuple[float, List[Dict[str, Any]]]] = {}
        self._team_info_cache: dict[str | int, tuple[float, Dict[str, Any]]] = {}
        self._cache_sizes: dict[tuple[str, str | int], int] = {}

    def _cache_result(
        self, cache_name: str, key: str | int, result: Any, now: float,
        *, max_entries: int, endpoint: str,
    ) -> None:
        """
        Validate before publication; evict oldest inserts across all caches.

        Byte accounting covers compact UTF-8 JSON values and UTF-8 key text;
        original string/integer identifiers remain unchanged as cache keys.
        The synchronous admission/eviction section cannot race between workers.
        """
        key_text = str(key)
        validate_fields(key_text, endpoint)
        key_bytes = len(key_text.encode("utf-8"))
        size = key_bytes + resource_limits.payload_bytes(
            result, endpoint,
            min(resource_limits.MAX_CACHE_ENTRY_BYTES, resource_limits.MAX_CACHE_BYTES)
            - key_bytes,
        )
        if cache_name == "_team_schedule_cache":
            resource_limits.charge_match_bytes(result)
        cache = getattr(self, cache_name)
        if len(cache) >= max_entries:
            cache.clear()
            for identity in list(self._cache_sizes):
                if identity[0] == cache_name:
                    del self._cache_sizes[identity]
        identity = (cache_name, key)
        self._cache_sizes.pop(identity, None)
        while sum(self._cache_sizes.values()) + size > resource_limits.MAX_CACHE_BYTES:
            (old_cache, old_key) = next(iter(self._cache_sizes))
            getattr(self, old_cache).pop(old_key, None)
            del self._cache_sizes[(old_cache, old_key)]
        self._cache_sizes[identity] = size
        cache[key] = (now, result)

    async def _make_request(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make HTTP request to handball.net API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            async with http_client.budgeted_request_slot(self.hass, endpoint), self.session.get(
                url, timeout=http_client.REQUEST_TIMEOUT, allow_redirects=False
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("HTTP error %s for endpoint %s", resp.status, endpoint)
                    return None
                body = await http_client.async_read_limited(
                    resp, http_client.MAX_API_RESPONSE_BYTES, endpoint
                )
                if resp.content_type != "application/json" and not resp.content_type.endswith("+json"):
                    return None
                payload = json.loads(http_client.decode_body(resp, body))
                return payload if isinstance(payload, dict) else None
        except Exception as e:
            _LOGGER.error("Request failed for endpoint %s: %s", endpoint, e)
            return None

    async def _make_new_api_request(
        self, endpoint: str, params: Dict[str, Any], referer: str
    ) -> Dict[str, Any]:
        """Fetch new-API data without disguising failures as empty results."""
        payload = await async_get_json(self.hass, endpoint, params, referer)

        if not payload or payload.get("success") is False:
            # Events and standings may omit "success" on valid responses.
            raise HandballNetHTTPError(None, endpoint, "API reported failure or empty response")

        return payload

    @http_client.sequence_limited
    async def _fetch_new_api_paginated(
        self, endpoint: str, params: Dict[str, Any], referer: str
    ) -> List[Dict[str, Any]]:
        """Fetch all pages of a paginated new-API list endpoint"""
        results: List[Dict[str, Any]] = []
        page = 1
        last_page = 1

        while page <= last_page:
            if endpoint == "matches":
                resource_limits.check_match_work_start()
            payload = await self._make_new_api_request(
                endpoint, {**params, "page": page}, referer
            )
            records = validate_records(payload, endpoint, count=len(results))
            last_page = validate_last_page(payload, endpoint, last_page)
            if endpoint == "matches":
                charge_match_records(len(records))
            results.extend(records)
            page += 1

        return results

    @staticmethod
    def _parse_match_date_to_ms(date_str: Optional[str]) -> Optional[int]:
        """Parse an ISO 8601 match date into epoch milliseconds"""
        if not date_str:
            return None
        try:
            return int(datetime.fromisoformat(date_str).timestamp() * 1000)
        except ValueError:
            return None

    _round_keys_logged = False

    def _extract_round(self, match: Dict[str, Any]) -> Optional[int]:
        """Matchday number of a match, if the API provides one.

        The standings endpoint exposes "round" as int; for matches the exact
        shape is not documented, so a few candidates are accepted (int or
        object with number/order/name).
        """
        for key in ("round", "matchday", "round_number", "jornada", "journey"):
            value = match.get(key)
            if isinstance(value, dict):
                value = value.get("number") or value.get("order") or value.get("name")
            if isinstance(value, str):
                digits = "".join(ch for ch in value if ch.isdigit())
                value = int(digits) if digits else None
            if isinstance(value, int) and value > 0:
                return value
        if not HandballNetAPI._round_keys_logged:
            HandballNetAPI._round_keys_logged = True
            _LOGGER.debug(
                "No matchday field found in match data (keys: %s); "
                "falling back to calendar-week grouping",
                sorted(match.keys()),
            )
        return None

    def _normalize_match(self, match: Dict[str, Any], team_id: str | int) -> Dict[str, Any]:
        """Normalize a new-API match into the schedule shape the rest of the integration expects"""
        local = match.get("local") or {}
        visitor = match.get("visitor") or {}
        status = match.get("status") or {}
        result = match.get("result") or {}
        phase = match.get("phase") or {}
        competition = phase.get("competition") or {}

        local_id = local.get("id")
        visitor_id = visitor.get("id")
        local_logo = (local.get("club") or {}).get("logo")
        visitor_logo = (visitor.get("club") or {}).get("logo")

        return {
            "id": match.get("id"),
            "startsAt": self._parse_match_date_to_ms(match.get("date")),
            "state": "Post" if status.get("is_finished") else status.get("short_name"),
            "homeTeam": {
                "id": str(local_id) if local_id is not None else None,
                "name": local.get("name"),
                "logo": self.utils.normalize_logo_url(local_logo) if local_logo else None,
            },
            "awayTeam": {
                "id": str(visitor_id) if visitor_id is not None else None,
                "name": visitor.get("name"),
                "logo": self.utils.normalize_logo_url(visitor_logo) if visitor_logo else None,
            },
            "field": {"name": (match.get("field") or {}).get("name")},
            "homeGoals": result.get("local"),
            "awayGoals": result.get("visitor"),
            "tournament": {
                "id": phase.get("id"),
                "name": competition.get("name"),
            },
            "isHomeMatch": str(local_id) == str(team_id) if local_id is not None else False,
            "isAway": str(visitor_id) == str(team_id) if visitor_id is not None else False,
            "lastUpdated": None,
            "round": self._extract_round(match),
            "status": status.get("short_name"),
            "error": None,
        }

    async def get_team_schedule(self, team_id: str | int) -> Optional[List[Dict[str, Any]]]:
        """Get team schedule/matches"""
        now = time.time()

        if team_id in self._team_schedule_cache:
            timestamp, cached_data = self._team_schedule_cache[team_id]
            if now - timestamp < self.TEAM_SCHEDULE_CACHE_TTL:
                charge_match_records(len(cached_data))
                resource_limits.charge_match_bytes(cached_data)
                return cached_data

        matches = await self._fetch_new_api_paginated(
            "matches",
            {"team_id": team_id},
            referer=f"{HANDBALL_NET_WEB_URL}team/{team_id}",
        )
        result = [self._normalize_match(match, team_id) for match in matches]

        if result is not None:
            self._cache_result(
                "_team_schedule_cache", team_id, result, now,
                max_entries=20, endpoint="matches",
            )

        return result

    async def get_team_info(self, team_id: str | int) -> Optional[Dict[str, Any]]:
        """Get team information including logo"""
        now = time.time()

        if team_id in self._team_info_cache:
            timestamp, cached_data = self._team_info_cache[team_id]
            if now - timestamp < self.TEAM_INFO_CACHE_TTL:
                return cached_data

        payload = await self._make_new_api_request(
            f"teams/{team_id}", {}, referer=f"{HANDBALL_NET_WEB_URL}team/{team_id}"
        )
        team_data = payload.get("data") if payload else None
        if team_data is not None and not isinstance(team_data, dict):
            raise HandballNetHTTPError(200, f"teams/{team_id}", "invalid team record")
        if not team_data:
            return None

        validate_fields(team_data, f"teams/{team_id}")

        club_logo = (team_data.get("club") or {}).get("logo")
        team_data["logo"] = self.utils.normalize_logo_url(club_logo) if club_logo else None

        # Not returned by the new API; schedule matches carry a fallback tournament id.
        team_data.setdefault("defaultTournament", None)

        self._cache_result(
            "_team_info_cache", team_id, team_data, now,
            max_entries=50, endpoint=f"teams/{team_id}",
        )

        return team_data

    def _normalize_standings(
        self, standings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Normalize new-API standings rows into the legacy table-row shape.

        The new `standings` endpoint returns one row per team *per round*
        (i.e. the full table history for the season), not just the current
        table. We take the rows for the highest round number present, which
        should be the most recently played/current matchday.
        """
        if not standings:
            return []

        max_round = max((row.get("round") or 0) for row in standings)
        current_rows = [row for row in standings if row.get("round") == max_round]

        rows: List[Dict[str, Any]] = []
        for row in current_rows:
            team = row.get("team") or {}
            club = team.get("club") or {}
            team_id = team.get("id")

            rows.append(
                {
                    "rank": row.get("position"),
                    "team": {
                        "id": str(team_id) if team_id is not None else None,
                        "name": team.get("name"),
                        "acronym": "",
                        "logo": club.get("logo"),
                    },
                    "points": row.get("points"),
                    "games": row.get("played", 0),
                    "wins": row.get("won", 0),
                    "draws": row.get("drawn", 0),
                    "losses": row.get("lost", 0),
                    "goals": row.get("goals_for", 0),
                    "goalsAgainst": row.get("goals_against", 0),
                    "goalDifference": row.get("goals_diff", 0),
                    "promoted": None,
                    "relegated": None,
                }
            )

        rows.sort(key=lambda r: r.get("rank") or 0)
        return rows

    async def get_league_table(self, league_id: str | int) -> Optional[List[Dict[str, Any]]]:
        """Get league table"""
        now = time.time()

        if league_id in self._league_table_cache:
            timestamp, cached_data = self._league_table_cache[league_id]
            if now - timestamp < self.LEAGUE_TABLE_CACHE_TTL:
                return cached_data

        payload = await self._make_new_api_request(
            "standings",
            {"phase_id": league_id},
            referer=f"{HANDBALL_NET_WEB_URL}ligen/{league_id}",
        )
        standings = validate_records(payload, "standings")
        result = self._normalize_standings(standings)

        if result is not None:
            self._cache_result(
                "_league_table_cache", league_id, result, now,
                max_entries=20, endpoint="standings",
            )

        return result

    async def get_live_ticker(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Get live ticker events for a game"""
        payload = await self._make_new_api_request(
            f"matches/{game_id}/events",
            {},
            referer=f"{HANDBALL_NET_WEB_URL}match/{game_id}",
        )
        return {"events": validate_records(payload, f"matches/{game_id}/events")}

    @http_client.sequence_limited
    async def get_tournament_team_ids(self, tournament_id: str) -> list[str]:
        """Resolve tournament participants using team search fallback."""
        query = quote_plus(tournament_id)

        team_ids: list[str] = []
        seen: set[str] = set()

        page = 1
        page_count = 1
        record_count = 0
        while page <= page_count:
            data = await self._make_request(f"teams/search?query={query}&page={page}")
            if data is None:
                http_client.check_response_budget("teams/search")
                raise HandballNetHTTPError(None, "teams/search", "participant search failed")
            teams = validate_records(data, "teams/search", count=record_count)
            record_count += len(teams)
            page_count = validate_last_page(
                data, "teams/search", page_count, metadata="meta", key="pageCount"
            )

            for team in teams:
                if not isinstance(team, dict):
                    continue

                default_tournament = team.get("defaultTournament")
                if not isinstance(default_tournament, dict):
                    continue

                if default_tournament.get("id") != tournament_id:
                    continue

                team_id = team.get("id")
                if not team_id or team_id in seen:
                    continue

                seen.add(team_id)
                team_ids.append(team_id)

            page += 1

        return team_ids

    def extract_team_logo_url(self, matches: List[Dict[str, Any]], team_id: str) -> Optional[str]:
        """Extract team logo URL from matches data"""
        if not matches:
            return None

        for match in matches:
            for team_key in ["homeTeam", "awayTeam"]:
                team = match.get(team_key, {})
                if team.get("id") == team_id:
                    logo_url = team.get("logo")
                    if logo_url:
                        return self.utils.normalize_logo_url(logo_url)
        return None

    async def get_team_table_position(self, team_id: str, tournament_id: str | int) -> Optional[Dict[str, Any]]:
        """Get team position in league table"""
        table_data = await self.get_league_table(tournament_id)
        if not table_data:
            _LOGGER.debug("No table data received for tournament %s", tournament_id)
            return None

        return self._find_team_in_table(table_data, team_id, tournament_id)

    def _find_team_in_table(self, table_data: Any, team_id: str, tournament_id: str | int) -> Optional[Dict[str, Any]]:
        """Find team in league table data"""
        rows = self._extract_table_rows(table_data)
        if not rows:
            return None

        for team_entry in rows:
            if not isinstance(team_entry, dict):
                continue

            team_info = team_entry.get("team")
            if not isinstance(team_info, dict):
                continue

            if team_info.get("id") == team_id:
                return self._create_table_position_dict(team_entry, team_info)

        _LOGGER.debug("Team %s not found in table for tournament %s", team_id, tournament_id)
        return None

    def _extract_table_rows(self, table_data: Any) -> Optional[List[Dict[str, Any]]]:
        """Extract rows from table data structure"""
        if isinstance(table_data, dict):
            return table_data.get("rows", [])
        elif isinstance(table_data, list):
            return table_data
        else:
            _LOGGER.warning("Unexpected table data format: %s", type(table_data))
            return None

    def _create_table_position_dict(self, team_entry: Dict[str, Any], team_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create standardized table position dictionary"""
        return {
            "position": team_entry.get("rank"),
            "team_name": team_info.get("name", ""),
            "points": team_entry.get("points", "0:0"),
            "games_played": team_entry.get("games", 0),
            "wins": team_entry.get("wins", 0),
            "draws": team_entry.get("draws", 0),
            "losses": team_entry.get("losses", 0),
            "goals_scored": team_entry.get("goals", 0),
            "goals_conceded": team_entry.get("goalsAgainst", 0),
            "goal_difference": team_entry.get("goalDifference", 0)
        }
