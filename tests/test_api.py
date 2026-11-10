import pytest
from unittest.mock import patch, AsyncMock

from .api_test_helpers import mocked_handball_api

@pytest.fixture
def api():
    with mocked_handball_api() as api_client:
        yield api_client

@pytest.mark.asyncio
async def test_league_table_caching(api):
    row = {"round": 1, "position": 1, "team": {"id": 1, "name": "Team A"}}
    api._make_new_api_request = AsyncMock(return_value={"data": [row]})
    expected = api._normalize_standings([row])
    with patch("time.time", return_value=1000):
        assert await api.get_league_table("123") == expected
    assert api._make_new_api_request.await_count == 1
    with patch("time.time", return_value=2800):
        assert await api.get_league_table("123") == expected
    assert api._make_new_api_request.await_count == 1
    with patch("time.time", return_value=4601):
        assert await api.get_league_table("123") == expected
    assert api._make_new_api_request.await_count == 2


@pytest.mark.asyncio
async def test_league_table_no_cache_on_error(api):
    from custom_components.handballnet.http_client import HandballNetHTTPError

    api._make_new_api_request = AsyncMock(side_effect=HandballNetHTTPError(403, "standings", "denied"))
    with pytest.raises(HandballNetHTTPError):
        await api.get_league_table("123")
    assert "123" not in api._league_table_cache
    row = {"round": 1, "position": 2, "team": {"id": 2, "name": "Team B"}}
    api._make_new_api_request = AsyncMock(return_value={"data": [row]})
    assert await api.get_league_table("123") == api._normalize_standings([row])
    api._make_new_api_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_tournament_team_ids_filters_by_default_tournament(api):
    api._make_request = AsyncMock(
        return_value={
            "data": [
                {
                    "id": "team-a",
                    "defaultTournament": {"id": "sr.competition.57"},
                },
                {
                    "id": "team-b",
                    "defaultTournament": {"id": "sr.competition.57"},
                },
                {
                    "id": "team-c",
                    "defaultTournament": {"id": "sr.competition.123"},
                },
                {
                    "id": "team-a",
                    "defaultTournament": {"id": "sr.competition.57"},
                },
                {
                    "id": "team-d",
                    "defaultTournament": None,
                },
            ]
        }
    )

    result = await api.get_tournament_team_ids("sr.competition.57")

    assert result == ["team-a", "team-b"]
    api._make_request.assert_called_once()


@pytest.mark.asyncio
async def test_get_tournament_team_ids_reads_all_pages(api):
    api._make_request = AsyncMock(
        side_effect=[
            {
                "data": [
                    {
                        "id": "team-a",
                        "defaultTournament": {"id": "sr.competition.57"},
                    }
                ],
                "meta": {"pageCount": 2},
            },
            {
                "data": [
                    {
                        "id": "team-b",
                        "defaultTournament": {"id": "sr.competition.57"},
                    },
                    {
                        "id": "team-c",
                        "defaultTournament": {"id": "sr.competition.999"},
                    },
                ],
                "meta": {"pageCount": 2},
            },
        ]
    )

    result = await api.get_tournament_team_ids("sr.competition.57")

    assert result == ["team-a", "team-b"]
    assert api._make_request.await_args_list[0].args[0].endswith("page=1")
    assert api._make_request.await_args_list[1].args[0].endswith("page=2")
