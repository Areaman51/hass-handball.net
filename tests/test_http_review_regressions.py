"""Regressionen der unabhängig bestätigten HTTP-R1/R2/L1-Befunde.
Alle HTTP-Aufrufe verwenden ausschließlich den Loopback-Testserver.
"""

import asyncio
from collections import deque
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.handballnet import api as api_module
from custom_components.handballnet import http_client, resource_limits
from custom_components.handballnet.api import HandballNetAPI
from custom_components.handballnet.config_flow import HandballNetConfigFlow
from custom_components.handballnet.coordinator import HandballDataUpdateCoordinator
from custom_components.handballnet.http_client import HandballNetHTTPError
from custom_components.handballnet.resource_limits import async_bounded_map
from custom_components.handballnet.utils import HandballNetUtils
from tests.test_http_client import api, bootstrap, fetch, transport  # noqa: F401


def coordinator_for(client, entity_type="tournament"):
    result = HandballDataUpdateCoordinator.__new__(HandballDataUpdateCoordinator)
    result.hass = client.hass
    result._api = client
    result._utils = HandballNetUtils()
    result._entry = SimpleNamespace(data={"tournament_name": "League"})
    result._entity_type = entity_type
    result._tournament_id = "league"
    result._perf_snapshot = {}
    result._standard_interval = timedelta(hours=1)
    result._live_interval = timedelta(seconds=15)
    result._store_tournament_bucket = MagicMock()
    result._store_team_bucket = MagicMock()
    return result


@pytest.mark.asyncio
async def test_participant_guard_precedes_all_logo_requests(transport, monkeypatch):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    client = HandballNetAPI(transport.hass)
    info_ids = []

    async def reply(endpoint, params, referer):
        if endpoint == "standings":
            return {
                "data": [
                    {"round": 1, "position": i + 1, "team": {"id": i, "name": "Team"}}
                    for i in range(257)
                ]
            }
        if endpoint.startswith("teams/"):
            info_ids.append(endpoint)
            return {"data": {"id": endpoint.split("/")[1], "club": {}}}
        raise AssertionError(endpoint)

    client._make_new_api_request = AsyncMock(side_effect=reply)
    client.get_team_schedule = AsyncMock(return_value=[])
    coordinator = coordinator_for(client)
    with pytest.raises(UpdateFailed, match="participant team limit"):
        await coordinator._async_update_data()
    assert info_ids == []
    client.get_team_schedule.assert_not_awaited()
    coordinator._store_tournament_bucket.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [True, False])
async def test_tournament_work_guard_stops_before_full_schedule_wave(
    transport, monkeypatch, target
):
    """Count all inspected records, including duplicates/non-target matches."""
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    client = HandballNetAPI(transport.hass)
    schedule_ids = []

    async def reply(endpoint, params, referer):
        assert endpoint == "matches"
        team_id = params["team_id"]
        schedule_ids.append(team_id)
        return {
            "data": [
                {
                    "id": f"{team_id}-{i}",
                    "date": "2026-11-15T12:00:00+00:00",
                    "phase": {"id": "league" if target else "other"},
                }
                for i in range(2000)
            ]
        }

    client._make_new_api_request = AsyncMock(side_effect=reply)
    coordinator = coordinator_for(client)
    with pytest.raises(UpdateFailed, match="match record limit"):
        await coordinator._fetch_tournament_matches(
            [{"team_id": str(i)} for i in range(10)]
        )
    assert len(schedule_ids) <= 6  # no whole 10-schedule wave before checking
    retained = sum(len(matches) for _, matches in client._team_schedule_cache.values())
    assert retained <= 10000
    coordinator._store_tournament_bucket.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", ["api", "flow", "legacy"])
async def test_gzip_page_sequence_has_cumulative_decompressed_budget(
    transport, monkeypatch, consumer
):
    import gzip
    import json

    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    monkeypatch.setattr(
        api_module, "HANDBALL_NET_BASE_URL", http_client.HANDBALL_NET_NEW_API_BASE_URL
    )
    client = HandballNetAPI(transport.hass)
    bootstrap(transport)
    calls = []

    async def page(request):
        calls.append(int(request.query["page"]))
        payload = {
            "success": True,
            "data": [{"id": "test"}],
            "pagination": {"last_page": 20},
            "meta": {"pageCount": 20},
        }
        # Whitespace is real decompressed input, without oversized scalar fields.
        raw = json.dumps(payload).encode() + b" " * (512 * 1024)
        return web.Response(
            body=gzip.compress(raw),
            content_type="application/json",
            headers={"Content-Encoding": "gzip"},
        )

    path = "/api/new/teams/search" if consumer == "legacy" else "/api/new/matches"
    transport.replies[path] = deque([page] * 20)
    if consumer == "flow":
        flow = HandballNetConfigFlow()
        flow.hass = transport.hass
        assert await flow._api_get_new_paginated("matches", {}, "ref") == []
        assert flow._lookup_error("not_found") == "api_blocked"
    else:
        with pytest.raises(HandballNetHTTPError, match="byte limit"):
            if consumer == "legacy":
                await client.get_tournament_team_ids("league")
            else:
                await client.get_team_schedule("test")
    assert 1 < len(calls) <= 16
    assert not client._team_schedule_cache


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "consumer", ["schedule", "table", "info", "events", "flow", "legacy"]
)
async def test_oversized_utf8_scalar_never_enters_results_or_caches(
    transport, monkeypatch, consumer
):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    client = HandballNetAPI(transport.hass)
    # 8193 characters, but 16386 UTF-8 bytes: enforce bytes, not code points.
    record = {"id": "test", "name": "é" * 8193}
    payload = {"success": True, "data": record if consumer == "info" else [record]}
    bootstrap(transport)
    path = {
        "schedule": "matches",
        "table": "standings",
        "info": "teams/test",
        "events": "matches/test/events",
        "flow": "teams",
        "legacy": "teams/search",
    }[consumer]
    transport.replies[f"/api/new/{path}"] = deque([web.json_response(payload)])
    if consumer == "flow":
        flow = HandballNetConfigFlow()
        flow.hass = transport.hass
        assert await flow._api_get_new_paginated(path, {}, "ref") == []
        assert flow._lookup_error("not_found") == "api_blocked"
    else:
        if consumer == "legacy":
            client.base_url = http_client.HANDBALL_NET_NEW_API_BASE_URL
        with pytest.raises(HandballNetHTTPError, match="field byte limit"):
            await {
                "schedule": client.get_team_schedule,
                "table": client.get_league_table,
                "info": client.get_team_info,
                "events": client.get_live_ticker,
                "legacy": client.get_tournament_team_ids,
            }[consumer]("test")
    assert not client._team_schedule_cache
    assert not client._league_table_cache
    assert not client._team_info_cache


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", ["schedule", "table", "info"])
async def test_normalized_cache_entry_byte_limit_is_all_or_nothing(
    transport, monkeypatch, consumer
):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    monkeypatch.setattr(resource_limits, "MAX_CACHE_ENTRY_BYTES", 1000, raising=False)
    client = HandballNetAPI(transport.hass)
    record = {
        "id": "test",
        "round": 1,
        "local": {"name": "x" * 250},
        "team": {"name": "x" * 250},
    }
    data = (
        {"id": "test", "extra": ["x" * 250] * 5} if consumer == "info" else [record] * 5
    )
    client._make_new_api_request = AsyncMock(return_value={"data": data})
    with pytest.raises(HandballNetHTTPError, match="byte limit"):
        await {
            "schedule": client.get_team_schedule,
            "table": client.get_league_table,
            "info": client.get_team_info,
        }[consumer]("test")
    assert not client._team_schedule_cache
    assert not client._league_table_cache
    assert not client._team_info_cache


@pytest.mark.asyncio
async def test_one_byte_budget_covers_all_three_api_caches(transport, monkeypatch):
    import json

    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    monkeypatch.setattr(resource_limits, "MAX_CACHE_BYTES", 2048, raising=False)
    client = HandballNetAPI(transport.hass)
    caches = [
        client._team_schedule_cache,
        client._league_table_cache,
        client._team_info_cache,
    ]
    for index in range(12):
        key = str(index)
        method = [
            client.get_team_schedule,
            client.get_league_table,
            client.get_team_info,
        ][index % 3]
        record = {
            "id": key,
            "round": 1,
            "team": {"name": "x" * 250},
            "local": {"name": "x" * 250},
            "name": "x" * 250,
        }
        client._make_new_api_request = AsyncMock(
            return_value={"data": record if index % 3 == 2 else [record]}
        )
        result = await method(key)
        assert result
        # Count payload JSON plus UTF-8 cache identifiers, across cache types.
        retained = sum(
            len(k.encode())
            + len(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode())
            for cache in caches
            for k, (_, v) in cache.items()
        )
        assert retained <= 2048
        assert caches[index % 3][key][1] == result
    assert sum(len(cache) for cache in caches) < 12


@pytest.mark.asyncio
async def test_undated_match_survives_coordinator_and_cached_second_update(
    transport, monkeypatch
):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    client = HandballNetAPI(transport.hass)
    bootstrap(transport)
    transport.replies["/api/new/matches"] = deque(
        [
            web.json_response(
                {"data": [{"id": "undated", "date": None, "local": {"id": "test"}}]}
            )
        ]
    )
    transport.replies["/api/new/teams/test"].append(
        web.json_response({"data": {"id": "test", "name": "Team"}})
    )
    coordinator = coordinator_for(client, entity_type="team")
    coordinator._team_items = [("test", "Team")]
    result = await coordinator._async_update_data()
    assert result["teams"]["test"]["matches"][0]["startsAt"] is None
    assert result["teams"]["test"]["live_matches"] == []
    assert not result["is_live"]
    assert client._team_schedule_cache["test"][1][0]["startsAt"] is None
    requests_before = len(transport.requests)
    assert (await coordinator._async_update_data())["teams"]["test"][
        "matches"
    ] == result["teams"]["test"]["matches"]
    assert len(transport.requests) == requests_before
    assert coordinator._store_team_bucket.call_count == 2


@pytest.mark.asyncio
async def test_tournament_sort_accepts_mixed_missing_and_known_dates(
    transport, monkeypatch
):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    client = HandballNetAPI(transport.hass)
    client._make_new_api_request = AsyncMock(
        return_value={
            "data": [
                {
                    "id": "dated",
                    "date": "2026-11-15T12:00:00+00:00",
                    "phase": {"id": "league"},
                },
                {"id": "undated", "date": None, "phase": {"id": "league"}},
            ]
        }
    )
    coordinator = coordinator_for(client)
    result = await coordinator._fetch_tournament_matches([{"team_id": "test"}])
    assert [match["id"] for match in result] == ["undated", "dated"]
    assert result[0]["startsAt"] is None


@pytest.mark.asyncio
async def test_exact_shared_response_budget_stops_before_next_http_request(transport):
    bootstrap(transport)
    api(transport)
    await fetch(transport)
    transport.requests.clear()
    body = b'{"data": []}'
    for _ in range(4):
        transport.replies["/api/new/teams/test"].append(web.Response(body=body))
    with http_client.response_budget(len(body) * 2):
        assert await fetch(transport) == {"data": []}
        assert await fetch(transport) == {"data": []}
        with pytest.raises(HandballNetHTTPError, match="byte limit"):
            await fetch(transport)
    assert len(transport.requests) == 2
    assert await fetch(transport) == {"data": []}


@pytest.mark.asyncio
async def test_tournament_update_shares_input_budget_across_schedules(
    transport, monkeypatch
):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    monkeypatch.setattr(http_client, "MAX_OPERATION_BYTES", 1000)
    client = HandballNetAPI(transport.hass)
    bootstrap(transport)
    transport.replies["/api/new/standings"] = deque(
        [
            web.json_response(
                {"data": [{"round": 1, "team": {"id": str(i)}} for i in range(3)]}
            )
        ]
    )
    for index in range(3):
        transport.replies[f"/api/new/teams/{index}"] = deque(
            [web.json_response({"data": {"id": str(index)}})]
        )
        transport.replies.setdefault("/api/new/matches", deque()).append(
            web.Response(
                body=b'{"data": []}' + b" " * 450,
                content_type="application/json",
            )
        )
    coordinator = coordinator_for(client)
    with pytest.raises(UpdateFailed, match="byte limit"):
        await coordinator._async_update_data()
    coordinator._store_tournament_bucket.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("cached", [False, True])
async def test_tournament_result_bytes_bound_fresh_and_cached_schedules(
    transport, monkeypatch, cached
):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    monkeypatch.setattr(
        resource_limits, "MAX_TOURNAMENT_RESULT_BYTES", 2000, raising=False
    )
    client = HandballNetAPI(transport.hass)
    client._make_new_api_request = AsyncMock(
        side_effect=lambda endpoint, params, referer: {
            "data": [
                {
                    "id": params["team_id"],
                    "phase": {"id": "league"},
                    "local": {"name": "x" * 900},
                }
            ]
        }
    )
    if cached:
        for team_id in ["a", "b", "c", "d"]:
            await client.get_team_schedule(team_id)
        client._make_new_api_request.reset_mock()
    coordinator = coordinator_for(client)
    with pytest.raises(UpdateFailed, match="byte limit"):
        await coordinator._fetch_tournament_matches(
            [{"team_id": team} for team in ["a", "b", "c", "d"]]
        )
    assert client._make_new_api_request.await_count <= (0 if cached else 2)
    if not cached:
        assert len(client._team_schedule_cache) == 1
    # The operation counter must not leak into a later unrelated lookup.
    assert await client.get_team_schedule("after")


@pytest.mark.asyncio
async def test_tournament_record_budget_checked_before_another_page(
    transport, monkeypatch
):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    monkeypatch.setattr(resource_limits, "MAX_RECORDS", 2)
    client = HandballNetAPI(transport.hass)
    client._make_new_api_request = AsyncMock(
        side_effect=[
            {"data": [{"id": "1"}, {"id": "2"}], "pagination": {"last_page": 2}},
            {"data": []},
        ]
    )
    coordinator = coordinator_for(client)
    with pytest.raises(UpdateFailed, match="match record limit"):
        await coordinator._fetch_tournament_matches([{"team_id": "team"}])
    assert client._make_new_api_request.await_count == 1
    assert not client._team_schedule_cache


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", ["info", "flow"])
async def test_invalid_unicode_field_keeps_safe_http_error_contract(
    transport, monkeypatch, caplog, consumer
):
    import traceback

    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    client = HandballNetAPI(transport.hass)
    bootstrap(transport)
    transport.replies["/api/new/teams/test"].append(
        web.Response(
            body=b'{"success": true, "data": {"id": "test", "name": "PRIVATE-BODY-\\ud800"}}',
            content_type="application/json",
        )
    )
    if consumer == "flow":
        flow = HandballNetConfigFlow()
        flow.hass = transport.hass
        assert await flow._api_get_new("teams/test", {}, "ref") is None
        assert flow._lookup_error("not_found") == "api_blocked"
    else:
        with pytest.raises(HandballNetHTTPError) as caught:
            await client.get_team_info("test")
        assert "PRIVATE-BODY" not in "".join(traceback.format_exception(caught.value))
        assert caught.value.__suppress_context__
    assert "PRIVATE-BODY" not in caplog.text
    assert not client._team_info_cache


@pytest.mark.asyncio
async def test_shared_budget_cancellation_awaits_children_and_restores_context(
    transport,
):
    bootstrap(transport)
    api(transport)
    await fetch(transport)
    started = asyncio.Event()
    release = asyncio.Event()
    count = 0
    workers = set()

    async def partial(request):
        nonlocal count
        response = web.StreamResponse(headers={"Content-Type": "application/json"})
        await response.prepare(request)
        await response.write(b'{"data":')
        count += 1
        if count == 4:
            started.set()
        await release.wait()
        return response

    transport.replies["/api/new/teams/test"].extend([partial] * 4)

    async def child(_):
        workers.add(asyncio.current_task())
        return await fetch(transport)

    async def operation():
        try:
            with http_client.response_budget(64), resource_limits.match_work_budget():
                await async_bounded_map(child, list(range(20)))
        finally:
            assert http_client._response_budgets.get() == ()
            assert resource_limits._match_work.get() is None

    parent = asyncio.create_task(operation())
    try:
        await asyncio.wait_for(started.wait(), 1)
        parent.cancel()
        with pytest.raises(asyncio.CancelledError):
            await parent
        assert len(workers) == 4
        assert all(task.done() for task in workers)
        assert http_client.request_slots(transport.hass)._value == 4
        assert http_client._response_budgets.get() == ()
        api(transport, {"data": "x" * 128})
        assert await fetch(transport) == {"data": "x" * 128}
    finally:
        release.set()
        if not parent.done():
            parent.cancel()
        await asyncio.gather(parent, return_exceptions=True)


@pytest.mark.asyncio
async def test_exact_utf8_field_and_cache_entry_budgets_are_accepted(
    transport, monkeypatch
):
    import json

    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    client = HandballNetAPI(transport.hass)
    expected = {
        "id": "test",
        "name": "é" * 8192,
        "logo": None,
        "defaultTournament": None,
    }
    size = len("test".encode()) + len(
        json.dumps(expected, ensure_ascii=False, separators=(",", ":")).encode()
    )
    monkeypatch.setattr(resource_limits, "MAX_CACHE_ENTRY_BYTES", size)
    monkeypatch.setattr(resource_limits, "MAX_CACHE_BYTES", size)
    client._make_new_api_request = AsyncMock(
        return_value={"data": {"id": "test", "name": "é" * 8192}}
    )
    assert await client.get_team_info("test") == expected
    assert sum(client._cache_sizes.values()) == size


@pytest.mark.asyncio
async def test_real_http_tournament_guard_limits_started_and_cached_work(
    transport, monkeypatch
):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    client = HandballNetAPI(transport.hass)
    bootstrap(transport)
    first_four = asyncio.Event()
    calls = []

    async def page(request):
        team_id = request.query["team_id"]
        calls.append(team_id)
        if len(calls) == 4:
            first_four.set()
        await first_four.wait()
        return web.json_response(
            {
                "data": [
                    {"id": f"{team_id}-{i}", "phase": {"id": "other"}}
                    for i in range(2000)
                ]
            }
        )

    transport.replies["/api/new/matches"] = deque([page] * 10)
    coordinator = coordinator_for(client)
    with pytest.raises(UpdateFailed, match="match record limit"):
        await coordinator._fetch_tournament_matches(
            [{"team_id": str(i)} for i in range(10)]
        )
    # Five accepted schedules plus at most three already in-flight siblings;
    # never the whole ten-team wave, even when none belongs to the target league.
    assert 4 <= len(calls) <= 8
    assert (
        sum(len(matches) for _, matches in client._team_schedule_cache.values())
        <= 10000
    )
    assert sum(client._cache_sizes.values()) <= resource_limits.MAX_CACHE_BYTES
    coordinator._store_tournament_bucket.assert_not_called()
