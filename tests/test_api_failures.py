"""Regression tests: failed fetches must not look like empty schedules."""
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.handballnet.http_client import HandballNetHTTPError
from .api_test_helpers import mocked_handball_api


@pytest.mark.asyncio
async def test_failed_schedule_fetch_raises_and_does_not_poison_cache():
    with mocked_handball_api() as api:
        error = HandballNetHTTPError(403, "matches", "HTTP 403")
        with patch("custom_components.handballnet.api.async_get_json", AsyncMock(side_effect=error)):
            with pytest.raises(HandballNetHTTPError, match="HTTP 403"):
                await api.get_team_schedule("86229")
        assert "86229" not in api._team_schedule_cache


@pytest.mark.asyncio
async def test_reported_api_failure_is_not_cached_as_an_empty_table():
    with mocked_handball_api() as api:
        with patch("custom_components.handballnet.api.async_get_json", AsyncMock(return_value={"success": False})):
            with pytest.raises(HandballNetHTTPError):
                await api.get_league_table("13541")
        assert "13541" not in api._league_table_cache


@pytest.mark.asyncio
async def test_later_page_failure_does_not_cache_a_partial_schedule():
    with mocked_handball_api() as api:
        responses = [
            {"data": [{"id": "first-page-match"}], "pagination": {"last_page": 2}},
            HandballNetHTTPError(503, "matches", "HTTP 503"),
        ]
        with patch("custom_components.handballnet.api.async_get_json", AsyncMock(side_effect=responses)):
            with pytest.raises(HandballNetHTTPError, match="HTTP 503"):
                await api.get_team_schedule("86229")
        assert "86229" not in api._team_schedule_cache


@pytest.mark.asyncio
async def test_successful_empty_schedule_is_distinct_from_a_failed_request():
    with mocked_handball_api() as api:
        with patch("custom_components.handballnet.api.async_get_json", AsyncMock(return_value={"data": []})):
            assert await api.get_team_schedule("86229") == []
        assert api._team_schedule_cache["86229"][1] == []
