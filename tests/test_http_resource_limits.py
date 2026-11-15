"""Offline resource-boundary regressions using real local aiohttp sockets."""

import asyncio
import gzip
from collections import deque
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web

from custom_components.handballnet import http_client
from custom_components.handballnet.api import HandballNetAPI

from .test_http_client import TOKEN, api, bootstrap, fetch, transport  # noqa: F401 (fixture)


@pytest.mark.asyncio
async def test_new_and_legacy_requests_share_four_slots_per_hass(transport):
    bootstrap(transport)
    api(transport)
    await fetch(transport)
    release = asyncio.Event()
    saturated = asyncio.Event()
    active = peak = 0

    async def blocked(request):
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        if active >= 4:
            saturated.set()
        try:
            await release.wait()
            return web.json_response({"data": []})
        finally:
            active -= 1

    for _ in range(12):
        transport.replies["/api/new/teams/test"].append(blocked)
    tasks = [
        asyncio.create_task(
            fetch(transport)
            if i % 2
            else legacy_client(transport)._make_request("teams/test")
        )
        for i in range(12)
    ]
    try:
        await asyncio.wait_for(saturated.wait(), 1)
        await asyncio.sleep(0.03)
        assert peak == 4
    finally:
        release.set()
        results = await asyncio.gather(*tasks)
    assert all(result == {"data": []} for result in results)


@pytest.mark.asyncio
async def test_queued_cancellation_does_not_send_request_or_leak_slot(transport):
    bootstrap(transport)
    api(transport)
    await fetch(transport)
    release = asyncio.Event()
    saturated = asyncio.Event()
    entered = 0

    async def blocked(request):
        nonlocal entered
        entered += 1
        if entered >= 4:
            saturated.set()
        await release.wait()
        return web.json_response({"data": []})

    for _ in range(5):
        transport.replies["/api/new/teams/test"].append(blocked)
    tasks = [asyncio.create_task(fetch(transport)) for _ in range(4)]
    try:
        await asyncio.wait_for(saturated.wait(), 1)
        queued = asyncio.create_task(fetch(transport))
        await asyncio.sleep(0.02)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        assert entered == 4
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert await fetch(transport) == {"data": []}


@pytest.mark.asyncio
async def test_request_slots_are_isolated_between_hass_instances(transport):
    second_hass = SimpleNamespace(data={})
    for hass in (transport.hass, second_hass):
        bootstrap(transport)
        api(transport)
        await fetch(transport, hass=hass)
    release = asyncio.Event()
    saturated = asyncio.Event()
    entered = 0

    async def blocked(request):
        nonlocal entered
        entered += 1
        if entered == 8:
            saturated.set()
        await release.wait()
        return web.json_response({"data": []})

    for _ in range(8):
        transport.replies["/api/new/teams/test"].append(blocked)
    tasks = [
        asyncio.create_task(fetch(transport, hass=hass))
        for hass in (transport.hass, second_hass)
        for _ in range(4)
    ]
    try:
        await asyncio.wait_for(saturated.wait(), 1)
    finally:
        release.set()
        await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_bootstrap_uses_same_slots_and_cancellation_releases_token_lock(
    transport,
):
    release = asyncio.Event()
    saturated = asyncio.Event()
    entered = 0

    async def blocked(request):
        nonlocal entered
        entered += 1
        if entered == 4:
            saturated.set()
        await release.wait()
        return web.json_response({"data": []})

    for _ in range(4):
        transport.replies["/api/new/teams/test"].append(blocked)
    tasks = [
        asyncio.create_task(legacy_client(transport)._make_request("teams/test"))
        for _ in range(4)
    ]
    bootstrap(transport)
    api(transport)
    try:
        await asyncio.wait_for(saturated.wait(), 1)
        queued = asyncio.create_task(fetch(transport))
        await asyncio.sleep(0.02)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        assert all(path != "/" for path, _, _ in transport.requests)
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert await fetch(transport) == {"data": {"name": "Test"}}


def legacy_client(transport):
    client = HandballNetAPI.__new__(HandballNetAPI)
    client.hass = transport.hass
    client.session = transport.session
    client.base_url = http_client.HANDBALL_NET_NEW_API_BASE_URL
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["bootstrap", "api", "legacy"])
@pytest.mark.parametrize("compressed", [False, True])
async def test_rejects_oversized_decompressed_bodies(
    transport, monkeypatch, caplog, stage, compressed
):
    monkeypatch.setattr(http_client, "MAX_API_RESPONSE_BYTES", 256, raising=False)
    monkeypatch.setattr(http_client, "MAX_BOOTSTRAP_RESPONSE_BYTES", 256, raising=False)
    if stage != "bootstrap":
        bootstrap(transport)
    body = (
        (f'<meta name="client-token" content="{TOKEN}">' + " " * 300).encode()
        if stage == "bootstrap"
        else b'{"data": "' + b"x" * 300 + b'"}'
    )
    path = "/" if stage == "bootstrap" else "/api/new/teams/test"
    transport.replies[path].append(
        web.Response(
            body=gzip.compress(body) if compressed else body,
            headers={"Content-Encoding": "gzip"} if compressed else {},
            content_type="text/html" if stage == "bootstrap" else "application/json",
        )
    )
    if stage == "legacy":
        assert await legacy_client(transport)._make_request("teams/test") is None
    else:
        with pytest.raises(http_client.HandballNetHTTPError, match="limit"):
            await fetch(transport)
    assert TOKEN not in caplog.text
    if stage == "bootstrap":
        assert "token" not in transport.hass.data[http_client._TOKEN_DATA_KEY]
        assert len(transport.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["bootstrap", "api", "legacy"])
async def test_chunked_overflow_stops_reading_before_end(transport, monkeypatch, stage):
    monkeypatch.setattr(http_client, "MAX_API_RESPONSE_BYTES", 128, raising=False)
    monkeypatch.setattr(http_client, "MAX_BOOTSTRAP_RESPONSE_BYTES", 128, raising=False)
    disconnected = asyncio.Event()
    if stage == "api":
        bootstrap(transport)

    async def streaming(request):
        response = web.StreamResponse(headers={"Content-Type": "application/json"})
        await response.prepare(request)
        prefix = (
            f'<meta name="client-token" content="{TOKEN}">'.encode()
            if stage == "bootstrap"
            else b'{"data": "'
        )
        await response.write(prefix + b" " * 129)
        try:
            for _ in range(20):
                await asyncio.sleep(0.005)
                await response.write(b" " * 64)
            await response.write(b'"}' if stage != "bootstrap" else b" ")
            await response.write_eof()
        except (ConnectionResetError, aiohttp.ClientConnectionError):
            disconnected.set()
        return response

    path = "/" if stage == "bootstrap" else "/api/new/teams/test"
    transport.replies[path].append(streaming)
    if stage == "legacy":
        assert await legacy_client(transport)._make_request("teams/test") is None
    else:
        with pytest.raises(http_client.HandballNetHTTPError, match="limit"):
            await fetch(transport)
    await asyncio.wait_for(disconnected.wait(), 1)


@pytest.mark.asyncio
async def test_api_exact_byte_limit_is_accepted(transport, monkeypatch):
    body = b'{"data": []}'
    monkeypatch.setattr(http_client, "MAX_API_RESPONSE_BYTES", len(body), raising=False)
    bootstrap(transport)
    transport.replies["/api/new/teams/test"].append(web.Response(body=body))
    assert await fetch(transport) == {"data": []}


@pytest.mark.asyncio
async def test_legacy_request_has_fixed_timeout_and_no_redirects(
    transport, monkeypatch
):
    original_get = transport.session.get
    seen = []

    def get(url, **kwargs):
        seen.append(kwargs)
        return original_get(url, **kwargs)

    monkeypatch.setattr(transport.session, "get", get)
    api(transport)
    assert await legacy_client(transport)._make_request("teams/test") is not None
    assert seen[0].get("allow_redirects") is False
    assert seen[0].get("timeout") == http_client.REQUEST_TIMEOUT


@pytest.mark.asyncio
async def test_legacy_timeout_preserves_none_contract(transport, monkeypatch):
    monkeypatch.setattr(
        http_client, "REQUEST_TIMEOUT", aiohttp.ClientTimeout(total=0.01)
    )

    async def delayed(request):
        await asyncio.sleep(0.04)
        return web.json_response({"data": []})

    transport.replies["/api/new/teams/test"].append(delayed)
    assert await legacy_client(transport)._make_request("teams/test") is None


@pytest.mark.asyncio
async def test_legacy_redirect_is_not_followed(transport):
    transport.replies["/api/new/teams/test"].append(
        web.Response(status=302, headers={"Location": "/untrusted"})
    )
    transport.replies["/untrusted"] = deque([web.json_response({"data": []})])
    assert await legacy_client(transport)._make_request("teams/test") is None
    assert [path for path, _, _ in transport.requests] == ["/api/new/teams/test"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["bootstrap", "api", "legacy"])
async def test_unknown_charset_retains_aiohttp_utf8_fallback(transport, stage):
    if stage != "bootstrap":
        bootstrap(transport)
    body = (
        f'<meta name="client-token" content="{TOKEN}">'.encode()
        if stage == "bootstrap"
        else b'{"data": []}'
    )
    path = "/" if stage == "bootstrap" else "/api/new/teams/test"
    transport.replies[path].append(
        web.Response(
            body=body,
            headers={"Content-Type": "application/json; charset=unknown-encoding"},
        )
    )
    if stage == "bootstrap":
        api(transport, {"data": []})
    result = (
        await legacy_client(transport)._make_request("teams/test")
        if stage == "legacy"
        else await fetch(transport)
    )
    assert result == {"data": []}


@pytest.mark.asyncio
async def test_deep_json_preserves_http_error_contract(transport):
    # CPython's C JSON parser has a separate depth budget on newer Python.
    depth = 100_000
    bootstrap(transport)
    transport.replies["/api/new/teams/test"].append(
        web.Response(
            body=b'{"data":' + b"[" * depth + b"0" + b"]" * depth + b"}",
        )
    )
    with pytest.raises(http_client.HandballNetHTTPError):
        await fetch(transport)
