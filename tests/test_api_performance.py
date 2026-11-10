"""Cache tests against the current /api/new request path."""
import pytest
from unittest.mock import AsyncMock, patch

from custom_components.handballnet.http_client import HandballNetHTTPError
from .api_test_helpers import mocked_handball_api


@pytest.fixture
def api():
    with mocked_handball_api() as api_client:
        yield api_client


@pytest.mark.asyncio
async def test_team_schedule_caching(api):
    raw = {"id": "match1", "local": {"id": "team123"}}
    api._make_new_api_request = AsyncMock(return_value={"data": [raw]})
    expected = [api._normalize_match(raw, "team123")]
    with patch("time.time", return_value=1000):
        assert await api.get_team_schedule("team123") == expected
    assert api._make_new_api_request.await_count == 1
    with patch("time.time", return_value=2800):
        assert await api.get_team_schedule("team123") == expected
    assert api._make_new_api_request.await_count == 1
    with patch("time.time", return_value=4601):
        assert await api.get_team_schedule("team123") == expected
    assert api._make_new_api_request.await_count == 2


@pytest.mark.asyncio
async def test_team_schedule_cache_limit(api):
    api._make_new_api_request = AsyncMock(return_value={"data": []})
    for i in range(20):
        await api.get_team_schedule(f"team{i}")
    assert len(api._team_schedule_cache) == 20
    assert api._make_new_api_request.await_count == 20
    await api.get_team_schedule("team20")
    assert len(api._team_schedule_cache) == 1
    assert api._make_new_api_request.await_count == 21
    assert "team20" in api._team_schedule_cache


@pytest.mark.asyncio
async def test_team_schedule_no_cache_on_error(api):
    api._make_new_api_request = AsyncMock(side_effect=HandballNetHTTPError(403, "matches", "denied"))
    with pytest.raises(HandballNetHTTPError):
        await api.get_team_schedule("team123")
    assert not api._team_schedule_cache
    raw = {"id": "match2"}
    api._make_new_api_request = AsyncMock(return_value={"data": [raw]})
    assert await api.get_team_schedule("team123") == [api._normalize_match(raw, "team123")]
    api._make_new_api_request.assert_awaited_once()
    assert len(api._team_schedule_cache) == 1


@pytest.mark.asyncio
async def test_team_info_caching(api):
    api._make_new_api_request = AsyncMock(return_value={"data": {"id": "team123"}})
    expected = {"id": "team123", "logo": None, "defaultTournament": None}
    with patch("time.time", return_value=2000):
        assert await api.get_team_info("team123") == expected
    assert api._make_new_api_request.await_count == 1
    with patch("time.time", return_value=5000):
        assert await api.get_team_info("team123") == expected
    assert api._make_new_api_request.await_count == 1
    with patch("time.time", return_value=23601):
        assert await api.get_team_info("team123") == expected
    assert api._make_new_api_request.await_count == 2


@pytest.mark.asyncio
async def test_team_info_no_cache_on_error(api):
    api._make_new_api_request = AsyncMock(side_effect=HandballNetHTTPError(403, "teams/team123", "denied"))
    with pytest.raises(HandballNetHTTPError):
        await api.get_team_info("team123")
    assert not api._team_info_cache
    api._make_new_api_request = AsyncMock(return_value={"data": {"id": "team123"}})
    assert await api.get_team_info("team123") == {"id": "team123", "logo": None, "defaultTournament": None}
    api._make_new_api_request.assert_awaited_once()
    assert len(api._team_info_cache) == 1
