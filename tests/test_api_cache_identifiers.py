"""HTTP-L2: retain original string/integer identifiers in every API cache.

Only the HA coordinator base initializer is doubled in the team/club test;
API, token bootstrap, loopback HTTP, normalization and bucket publication are real.
"""

import json
import time
from collections import deque
from types import SimpleNamespace

import pytest
from aiohttp import web
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.handballnet import api as api_module
from custom_components.handballnet import resource_limits
from custom_components.handballnet.api import HandballNetAPI
from custom_components.handballnet.coordinator import HandballDataUpdateCoordinator
from custom_components.handballnet.http_client import HandballNetHTTPError
from tests.test_http_client import bootstrap, transport  # noqa: F401

CACHE_CASES = [
    ("get_team_schedule", "_team_schedule_cache", "TEAM_SCHEDULE_CACHE_TTL"),
    ("get_team_info", "_team_info_cache", "TEAM_INFO_CACHE_TTL"),
    ("get_league_table", "_league_table_cache", "LEAGUE_TABLE_CACHE_TTL"),
]


def client_for(transport, monkeypatch):
    monkeypatch.setattr(
        api_module, "async_get_clientsession", lambda hass: transport.session
    )
    return HandballNetAPI(transport.hass)


def cache_bytes(key, result):
    """Independent oracle: UTF-8 identifier text plus compact JSON value."""
    return len(str(key).encode("utf-8")) + len(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def queue_reply(transport, method_name, identifier, marker):
    if method_name == "get_team_schedule":
        path = "/api/new/matches"
        data = [{"id": marker, "local": {"id": "test"}, "phase": {"id": 13541}}]
    elif method_name == "get_team_info":
        path = f"/api/new/teams/{identifier}"
        data = {"id": marker, "name": "Team"}
    else:
        path = "/api/new/standings"
        data = [{"round": 1, "position": marker, "team": {"id": "test"}}]
    transport.replies.setdefault(path, deque()).append(web.json_response({"data": data}))


@pytest.mark.asyncio
@pytest.mark.parametrize("entity_type", ["team", "club"])
async def test_numeric_phase_survives_two_coordinator_updates(
    transport, monkeypatch, entity_type
):
    client_for(transport, monkeypatch)
    bootstrap(transport)
    transport.replies["/api/new/matches"] = deque([
        web.json_response({"data": [{
            "id": "numeric-phase-game", "date": "2030-01-01T12:00:00+00:00",
            "local": {"id": "test", "name": "Team"}, "phase": {"id": 13541},
        }]})
    ])
    queue_reply(transport, "get_team_info", "test", "test")
    for _ in range(2):
        queue_reply(transport, "get_league_table", 13541, 1)

    def init_base(self, hass, logger, *, name, update_interval):
        self.hass = hass
        self.update_interval = update_interval

    monkeypatch.setattr(DataUpdateCoordinator, "__init__", init_base)
    entry = SimpleNamespace(
        entry_id="numeric-cache-regression", options={},
        data={"entity_type": entity_type, "team_id": "test", "team_mapping": {"Team": "test"}},
    )
    coordinator = HandballDataUpdateCoordinator(transport.hass, entry)
    first = await coordinator._async_update_data()
    first_requests = len(transport.requests)
    second = await coordinator._async_update_data()
    positions = [result["teams"]["test"]["table_position"] for result in (first, second)]
    print("NUMERIC_PHASE", entity_type, {
        "positions": positions,
        "cache_keys": list(coordinator._api._league_table_cache),
        "standings_requests": sum(p == "/api/new/standings" for p, _, _ in transport.requests),
    })
    assert positions[0] is not None
    assert positions[0]["position"] == positions[1]["position"] == 1
    assert all(result["teams"]["test"]["tournament_id"] == 13541 for result in (first, second))
    assert transport.hass.data["handballnet"]["test"]["table_position"] == positions[1]
    assert len(transport.requests) == first_requests
    assert sum(p == "/api/new/standings" for p, _, _ in transport.requests) == 1
    assert list(coordinator._api._league_table_cache) == [13541]
    assert ("_league_table_cache", 13541) in coordinator._api._cache_sizes


@pytest.mark.asyncio
@pytest.mark.parametrize(("method_name", "cache_name", "ttl_name"), CACHE_CASES)
async def test_mixed_identifiers_lookup_write_and_expiry(
    transport, monkeypatch, method_name, cache_name, ttl_name
):
    client = client_for(transport, monkeypatch)
    bootstrap(transport)
    method = getattr(client, method_name)
    cache = getattr(client, cache_name)
    keys = [13541, "13541", "ä-13541"]
    retained = {}
    for marker, key in enumerate(keys, 1):
        queue_reply(transport, method_name, key, marker)
        retained[key] = await method(key)
    assert retained[13541] != retained["13541"]
    assert list(cache) == keys
    assert client._cache_sizes == {
        (cache_name, key): cache_bytes(key, result) for key, result in retained.items()
    }
    request_count = len(transport.requests)
    for key in keys:
        assert await method(key) is retained[key]
    assert len(transport.requests) == request_count

    # Expiring one original key must neither hit nor overwrite its string sibling.
    cache[13541] = (time.time() - getattr(client, ttl_name) - 1, retained[13541])
    queue_reply(transport, method_name, 13541, 4)
    refreshed = await method(13541)
    assert refreshed != retained[13541]
    assert cache[13541][1] is refreshed
    assert await method("13541") is retained["13541"]
    assert len(transport.requests) == request_count + 1
    assert client._cache_sizes[(cache_name, 13541)] == cache_bytes(13541, refreshed)
    assert set(cache) == set(keys)


@pytest.mark.asyncio
@pytest.mark.parametrize(("method_name", "cache_name", "ttl_name"), CACHE_CASES)
@pytest.mark.parametrize("key", [13541, "13541", "ä-13541"])
async def test_identifier_entry_byte_boundary_is_exact(
    transport, monkeypatch, method_name, cache_name, ttl_name, key
):
    client = client_for(transport, monkeypatch)
    bootstrap(transport)
    method = getattr(client, method_name)
    queue_reply(transport, method_name, key, 1)
    result = await method(key)
    size = cache_bytes(key, result)
    cache = getattr(client, cache_name)
    cache.clear()
    client._cache_sizes.clear()
    monkeypatch.setattr(resource_limits, "MAX_CACHE_ENTRY_BYTES", size)
    monkeypatch.setattr(resource_limits, "MAX_CACHE_BYTES", size)
    queue_reply(transport, method_name, key, 1)
    assert await method(key) == result
    assert client._cache_sizes == {(cache_name, key): size}

    # One extra byte is rejected before either cache or accounting is mutated.
    cache[key] = (time.time() - getattr(client, ttl_name) - 1, result)
    before_cache = cache.copy()
    before_sizes = client._cache_sizes.copy()
    monkeypatch.setattr(resource_limits, "MAX_CACHE_ENTRY_BYTES", size - 1)
    queue_reply(transport, method_name, key, 1)
    with pytest.raises(HandballNetHTTPError, match="result byte limit"):
        await method(key)
    assert cache == before_cache
    assert client._cache_sizes == before_sizes


@pytest.mark.asyncio
async def test_mixed_identifiers_share_global_byte_budget_and_eviction(transport, monkeypatch):
    client = client_for(transport, monkeypatch)
    result = {"name": "ä"}
    entry_size = cache_bytes(13541, result)
    assert entry_size == cache_bytes("13541", result)
    monkeypatch.setattr(resource_limits, "MAX_CACHE_ENTRY_BYTES", entry_size)
    monkeypatch.setattr(resource_limits, "MAX_CACHE_BYTES", entry_size * 2)

    def put(cache_name, key, value=result, max_entries=20):
        client._cache_result(
            cache_name, key, value, 1000, max_entries=max_entries, endpoint="test"
        )

    def assert_accounting():
        expected = {
            (name, key): cache_bytes(key, value)
            for _, name, _ in CACHE_CASES
            for key, (_, value) in getattr(client, name).items()
        }
        assert client._cache_sizes == expected
        assert sum(expected.values()) <= resource_limits.MAX_CACHE_BYTES

    put("_team_info_cache", 13541)
    put("_team_info_cache", "13541")
    assert_accounting()
    assert sum(client._cache_sizes.values()) == resource_limits.MAX_CACHE_BYTES
    held = client._team_info_cache[13541][1]
    # Rewriting just the int key refreshes its accounting order, not the str key.
    replacement = {"name": "ö"}
    put("_team_info_cache", 13541, replacement)
    assert client._team_info_cache[13541][1] is replacement
    assert client._team_info_cache["13541"][1] is result
    assert_accounting()
    put("_league_table_cache", "13541")
    assert "13541" not in client._team_info_cache
    assert 13541 in client._team_info_cache
    assert_accounting()
    put("_team_schedule_cache", 13541, [])
    assert 13541 not in client._team_info_cache
    assert held is result and held == {"name": "ä"}
    assert_accounting()
    # The pre-existing per-kind count clear must remove both key types' sizes.
    monkeypatch.setattr(resource_limits, "MAX_CACHE_BYTES", entry_size * 10)
    put("_team_info_cache", 13541)
    put("_team_info_cache", "13541")
    put("_team_info_cache", "other", max_entries=2)
    assert list(client._team_info_cache) == ["other"]
    assert_accounting()


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["x" * 16385, "ä" * 8193, "\ud800"])
async def test_identifier_field_limits_still_reject_before_publication(transport, monkeypatch, key):
    client = client_for(transport, monkeypatch)
    with pytest.raises(HandballNetHTTPError, match="field byte limit|invalid field encoding"):
        client._cache_result("_team_info_cache", key, {}, 1000, max_entries=50, endpoint="test")
    assert not client._team_info_cache
    assert not client._cache_sizes
