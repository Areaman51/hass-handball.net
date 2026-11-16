"""Bounded, typed, all-or-nothing list ingestion (no external requests)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.handballnet.config_flow import HandballNetConfigFlow
from custom_components.handballnet.http_client import HandballNetHTTPError

from .api_test_helpers import mocked_handball_api


@pytest.mark.asyncio
@pytest.mark.parametrize("last_page", [101, True, False, 0, -1, "2", 2.0, None, [], {}])
async def test_api_rejects_unsafe_page_count_without_caching(last_page):
    with mocked_handball_api() as api:
        response = {"data": [{"id": "partial"}], "pagination": {"last_page": last_page}}
        api._make_new_api_request = AsyncMock(return_value=response)
        with pytest.raises(HandballNetHTTPError):
            await api.get_team_schedule("team")
        assert api._make_new_api_request.await_count == 1
        assert not api._team_schedule_cache


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [None, {}, "text", [None], [7], ["record"]])
async def test_api_rejects_invalid_record_types(data):
    with mocked_handball_api() as api:
        api._make_new_api_request = AsyncMock(return_value={"data": data})
        with pytest.raises(HandballNetHTTPError):
            await api.get_team_schedule("team")
        assert not api._team_schedule_cache


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["schedule", "table", "events"])
async def test_api_bounds_nonpaginated_and_paginated_records(target):
    with mocked_handball_api() as api:
        api._make_new_api_request = AsyncMock(return_value={"data": [{}] * 10001})
        with pytest.raises(HandballNetHTTPError, match="record"):
            await {
                "schedule": api.get_team_schedule,
                "table": api.get_league_table,
                "events": api.get_live_ticker,
            }[target]("id")
        assert not api._league_table_cache
        assert not api._team_schedule_cache


@pytest.mark.asyncio
async def test_api_bounds_aggregate_records_across_pages():
    with mocked_handball_api() as api:
        api._make_new_api_request = AsyncMock(
            side_effect=[
                {"data": [{}] * 6000, "pagination": {"last_page": 2}},
                {"data": [{}] * 4001},
            ]
        )
        with pytest.raises(HandballNetHTTPError, match="record"):
            await api.get_team_schedule("team")
        assert not api._team_schedule_cache


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_page",
    [{}, {"data": [], "pagination": []}, {"data": [], "pagination": {"last_page": 1}}],
)
async def test_api_later_malformed_page_never_returns_partial(bad_page):
    with mocked_handball_api() as api:
        api._make_new_api_request = AsyncMock(
            side_effect=[
                {"data": [{}], "pagination": {"last_page": 2}},
                bad_page,
            ]
        )
        with pytest.raises(HandballNetHTTPError):
            await api.get_team_schedule("team")
        assert not api._team_schedule_cache


@pytest.mark.asyncio
@pytest.mark.parametrize("last_page", [101, True, 0, "2", 2.0, None])
async def test_flow_rejects_unsafe_pagination_as_blocked(last_page):
    flow = HandballNetConfigFlow()
    flow._api_get_new = AsyncMock(
        return_value={
            "success": True,
            "data": [{"id": "partial"}],
            "pagination": {"last_page": last_page},
        }
    )
    assert await flow._api_get_new_paginated("teams", {}, "ref") == []
    assert flow._lookup_error("no_teams_found") == "api_blocked"
    assert flow._api_get_new.await_count == 1


@pytest.mark.asyncio
async def test_flow_later_failure_discards_previous_pages():
    flow = HandballNetConfigFlow()
    flow.hass = SimpleNamespace(data={})
    with patch(
        "custom_components.handballnet.config_flow.async_get_json",
        AsyncMock(
            side_effect=[
                {
                    "success": True,
                    "data": [{"id": "partial"}],
                    "pagination": {"last_page": 2},
                },
                HandballNetHTTPError(503, "teams", "failed"),
            ]
        ),
    ):
        assert await flow._api_get_new_paginated("teams", {}, "ref") == []
    assert flow._last_http_status == 503


@pytest.mark.asyncio
async def test_flow_later_empty_object_is_a_failed_lookup_not_not_found():
    flow = HandballNetConfigFlow()
    flow.hass = SimpleNamespace(data={})
    with patch(
        "custom_components.handballnet.config_flow.async_get_json",
        AsyncMock(
            side_effect=[
                {
                    "success": True,
                    "data": [{"id": "partial"}],
                    "pagination": {"last_page": 2},
                },
                {},
            ]
        ),
    ):
        assert await flow._api_get_new_paginated("teams", {}, "ref") == []
    assert flow._lookup_error("no_teams_found") == "api_blocked"


@pytest.mark.asyncio
async def test_flow_counts_all_records_across_pages_before_publishing():
    flow = HandballNetConfigFlow()
    flow._api_get_new = AsyncMock(
        side_effect=[
            {"success": True, "data": [{}] * 6000, "pagination": {"last_page": 2}},
            {"success": True, "data": [{}] * 4001},
        ]
    )
    assert await flow._api_get_new_paginated("teams", {}, "ref") == []
    assert flow._lookup_error("no_teams_found") == "api_blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [[{}] * 10001, None, "invalid", [None], {}])
@pytest.mark.parametrize(
    "method,args",
    [
        ("_search_clubs", ("query",)),
        ("_search_competitions", ("query",)),
        ("_get_phases_for_competition", ("competition",)),
        ("_get_teams_for_club", ("club",)),
        ("_get_team_phase", ("team",)),
    ],
)
async def test_flow_bounds_and_validates_all_list_endpoints(data, method, args):
    flow = HandballNetConfigFlow()
    flow.hass = SimpleNamespace(data={})
    with patch(
        "custom_components.handballnet.config_flow.async_get_json",
        AsyncMock(return_value={"success": True, "data": data}),
    ):
        assert not await getattr(flow, method)(*args)
    assert flow._lookup_error("not_found") == "api_blocked"


@pytest.mark.asyncio
@pytest.mark.parametrize("page_count", [101, True, 0, "2", 2.0, None])
async def test_legacy_search_pagination_is_bounded_and_typed(page_count):
    with mocked_handball_api() as api:
        api._make_request = AsyncMock(
            return_value={"data": [], "meta": {"pageCount": page_count}}
        )
        with pytest.raises(HandballNetHTTPError):
            await api.get_tournament_team_ids("tournament")
        assert api._make_request.await_count == 1


@pytest.mark.asyncio
async def test_legacy_later_failure_never_returns_partial_participants():
    with mocked_handball_api() as api:
        api._make_request = AsyncMock(
            side_effect=[
                {
                    "data": [
                        {"id": "partial", "defaultTournament": {"id": "tournament"}}
                    ],
                    "meta": {"pageCount": 2},
                },
                None,
            ]
        )
        with pytest.raises(HandballNetHTTPError):
            await api.get_tournament_team_ids("tournament")


@pytest.mark.asyncio
async def test_exact_record_and_page_limits_are_accepted():
    with mocked_handball_api() as api:
        api._make_new_api_request = AsyncMock(
            return_value={"data": [{}] * 100, "pagination": {"last_page": 100}}
        )
        assert len(await api._fetch_new_api_paginated("matches", {}, "ref")) == 10000
        assert api._make_new_api_request.await_count == 100
