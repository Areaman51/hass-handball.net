"""Protocol tests using real aiohttp sockets; only HA/session URLs substituted."""
import asyncio
from collections import deque
from types import SimpleNamespace

import aiohttp
from aiohttp import web
import pytest
import pytest_asyncio

from custom_components.handballnet import http_client

REFERER = "https://handball.net/teams/test"
TOKEN = "public-meta-token-SECRET"


def test_bootstrap_uses_canonical_www_origin():
    from urllib.parse import urlsplit

    bootstrap_url = getattr(http_client, "_TOKEN_BOOTSTRAP_URL", http_client.HANDBALL_NET_WEB_URL)
    assert urlsplit(bootstrap_url).hostname == "www.handball.net"


@pytest_asyncio.fixture
async def transport(monkeypatch):
    http_client._failures.clear()
    requests = []
    replies = {"/": deque(), "/api/new/teams/test": deque()}

    async def handler(request):
        requests.append((request.path, dict(request.headers), dict(request.query)))
        if not replies[request.path]:
            return web.Response(status=500, text="unexpected request")
        reply = replies[request.path].popleft()
        if callable(reply):
            return await reply(request)
        return reply

    app = web.Application()
    app.router.add_get("/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    root = f"http://127.0.0.1:{port}/"
    monkeypatch.setattr(http_client, "HANDBALL_NET_WEB_URL", root, raising=False)
    monkeypatch.setattr(http_client, "_TOKEN_BOOTSTRAP_URL", root)
    monkeypatch.setattr(http_client, "HANDBALL_NET_NEW_API_BASE_URL", root + "api/new")
    try:
        async with aiohttp.ClientSession() as session:
            monkeypatch.setattr(http_client, "async_get_clientsession", lambda hass: session)
            yield SimpleNamespace(
                hass=SimpleNamespace(data={}), replies=replies, requests=requests, session=session
            )
    finally:
        await runner.cleanup()
        http_client._failures.clear()


def bootstrap(transport, token=TOKEN, **kwargs):
    transport.replies["/"].append(web.Response(
        text=f'<html><head><meta content="{token}" name="client-token"></head></html>',
        **kwargs,
    ))


def api(transport, payload=None, **kwargs):
    transport.replies["/api/new/teams/test"].append(
        web.json_response({"data": {"name": "Test"}} if payload is None else payload, **kwargs)
    )


async def fetch(transport, **kwargs):
    return await http_client.async_get_json(
        kwargs.pop("hass", transport.hass), "teams/test", kwargs.pop("params", {}), REFERER
    )


@pytest.mark.asyncio
async def test_bootstraps_public_meta_token_before_api_request(transport):
    bootstrap(transport)
    api(transport)

    assert await fetch(transport) == {"data": {"name": "Test"}}
    assert [path for path, _, _ in transport.requests] == ["/", "/api/new/teams/test"]
    assert "x-client-token" not in transport.requests[0][1]
    assert transport.requests[1][1]["Referer"] == REFERER
    assert transport.requests[1][1]["x-client-token"] == TOKEN


@pytest.mark.asyncio
async def test_reuses_token_for_same_hass(transport):
    bootstrap(transport)
    api(transport)
    api(transport)
    await fetch(transport)
    await fetch(transport)
    assert [path for path, _, _ in transport.requests].count("/") == 1


@pytest.mark.asyncio
async def test_refreshes_token_after_monotonic_ttl(transport, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(http_client, "monotonic", lambda: now[0], raising=False)
    bootstrap(transport)
    api(transport)
    await fetch(transport)
    now[0] += 901
    bootstrap(transport, token="refreshed")
    api(transport)
    await fetch(transport)
    assert [path for path, _, _ in transport.requests].count("/") == 2
    assert transport.requests[-1][1]["x-client-token"] == "refreshed"


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
async def test_concurrent_bootstrap_is_single_flight(transport, monkeypatch, expired):
    now = [100.0]
    monkeypatch.setattr(http_client, "monotonic", lambda: now[0], raising=False)
    if expired:
        bootstrap(transport, token="old")
        api(transport)
        await fetch(transport)
        now[0] += 901
        transport.requests.clear()
    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_bootstrap(request):
        started.set()
        await release.wait()
        return web.Response(text=f'<META NAME="client-token" CONTENT="{TOKEN}">')

    transport.replies["/"].append(delayed_bootstrap)
    for _ in range(6):
        api(transport)
    tasks = [asyncio.create_task(fetch(transport)) for _ in range(6)]
    await asyncio.wait_for(started.wait(), timeout=2)
    await asyncio.sleep(0.02)
    release.set()
    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=2)
    assert all(result == {"data": {"name": "Test"}} for result in results), results
    assert [path for path, _, _ in transport.requests].count("/") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status,html", [
    (200, "<html>private-bootstrap-body</html>"),
    (200, '<meta name="client-token" content="">private-bootstrap-body'),
    (200, '<meta name="client-token" content="   ">private-bootstrap-body'),
    (200, '<meta name="client-token" content="bad&#10;header">private-bootstrap-body'),
    (503, f'<meta name="client-token" content="{TOKEN}">private-bootstrap-body'),
    (302, "private-bootstrap-body"),
])
async def test_rejects_unusable_bootstrap_without_logging_html(transport, caplog, status, html):
    transport.replies["/"].append(web.Response(status=status, text=html))
    with pytest.raises(http_client.HandballNetHTTPError) as caught:
        await fetch(transport)
    assert caught.value.status == status
    assert [path for path, _, _ in transport.requests] == ["/"]
    assert "private-bootstrap-body" not in caplog.text
    assert TOKEN not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("expired_json", [False, True])
async def test_refreshes_once_after_forbidden(transport, expired_json):
    bootstrap(transport, token="stale")
    bootstrap(transport, token="fresh")
    if expired_json:
        api(transport, {"success": False, "code": "CLIENT_TOKEN_EXPIRED"}, status=403)
    else:
        transport.replies["/api/new/teams/test"].append(web.Response(status=403, text="Forbidden"))
    api(transport)
    assert await fetch(transport) == {"data": {"name": "Test"}}
    assert [path for path, _, _ in transport.requests] == [
        "/", "/api/new/teams/test", "/", "/api/new/teams/test"
    ]
    assert [headers["x-client-token"] for path, headers, _ in transport.requests if path != "/"] == ["stale", "fresh"]


@pytest.mark.asyncio
async def test_concurrent_stale_rejections_share_refresh_even_when_late(transport):
    bootstrap(transport, token="stale")
    api(transport)
    await fetch(transport)
    transport.requests.clear()
    bootstrap(transport, token="fresh")
    all_stale = asyncio.Event()
    fresh_seen = asyncio.Event()
    count = 0

    async def reject_stale(request):
        nonlocal count
        assert request.headers["x-client-token"] == "stale"
        count += 1
        index = count
        if count == 6:
            all_stale.set()
        await all_stale.wait()
        if index == 6:
            await fresh_seen.wait()
        return web.json_response({"code": "CLIENT_TOKEN_EXPIRED"}, status=403)

    async def accept_fresh(request):
        assert request.headers["x-client-token"] == "fresh"
        fresh_seen.set()
        return web.json_response({"data": {"name": "Test"}})

    for _ in range(6):
        transport.replies["/api/new/teams/test"].append(reject_stale)
    for _ in range(6):
        transport.replies["/api/new/teams/test"].append(accept_fresh)
    results = await asyncio.wait_for(
        asyncio.gather(*(fetch(transport) for _ in range(6)), return_exceptions=True), timeout=3
    )
    assert all(result == {"data": {"name": "Test"}} for result in results), results
    assert [path for path, _, _ in transport.requests].count("/") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["[]", "null", "7", '"hello"'])
async def test_rejects_nonobject_json(transport, body):
    bootstrap(transport)
    transport.replies["/api/new/teams/test"].append(web.Response(text=body))
    with pytest.raises(http_client.HandballNetHTTPError, match="JSON object") as caught:
        await fetch(transport)
    assert caught.value.status == 200


@pytest.mark.asyncio
async def test_success_false_raises_instead_of_returning_payload(transport):
    bootstrap(transport)
    api(transport, {"success": False, "error": "upstream rejected request"})
    with pytest.raises(http_client.HandballNetHTTPError, match="upstream rejected request") as caught:
        await fetch(transport)
    assert caught.value.status == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["http", "final403", "invalid-json", "nonobject", "success-false"])
async def test_api_error_diagnostics_never_expose_any_attempt_token(transport, caplog, kind):
    caplog.set_level("DEBUG", logger=http_client.__name__)
    bootstrap(transport)
    if kind == "final403":
        bootstrap(transport, token="refreshed-secret")
        api(transport, {"code": "CLIENT_TOKEN_EXPIRED", "echo": TOKEN}, status=403)
        api(transport, {"echo": TOKEN + " refreshed-secret"}, status=403)
    elif kind == "http":
        api(transport, {"echo": TOKEN}, status=500)
    elif kind == "invalid-json":
        transport.replies["/api/new/teams/test"].append(web.Response(text=f"invalid {TOKEN}"))
    elif kind == "nonobject":
        api(transport, [TOKEN])
    else:
        api(transport, {"success": False, "error": TOKEN})
    with pytest.raises(http_client.HandballNetHTTPError) as caught:
        await fetch(transport)
    assert TOKEN not in caplog.text
    assert "refreshed-secret" not in caplog.text
    assert TOKEN not in str(caught.value)
    assert TOKEN not in str(http_client._failures)
    assert "[redacted]" in caplog.text
    if kind == "final403":
        assert caught.value.status == 403
        assert [path for path, _, _ in transport.requests].count("/") == 2
        assert [path for path, _, _ in transport.requests].count("/api/new/teams/test") == 2


@pytest.mark.asyncio
async def test_rate_limit_hint_increases_interval_without_retry(transport, caplog):
    bootstrap(transport)
    api(transport, {"error": "rate limited"}, status=429)
    with pytest.raises(http_client.HandballNetHTTPError) as caught:
        await fetch(transport)
    assert caught.value.status == 429
    assert "increase the update interval" in caplog.text
    assert len(transport.requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["bootstrap", "api"])
async def test_does_not_follow_redirects_outside_fixed_urls(transport, stage):
    if stage == "api":
        bootstrap(transport)
    path = "/" if stage == "bootstrap" else "/api/new/teams/test"
    transport.replies[path].append(web.Response(status=302, headers={"Location": "/untrusted"}))
    with pytest.raises(http_client.HandballNetHTTPError) as caught:
        await fetch(transport)
    assert caught.value.status == 302
    assert all(path != "/untrusted" for path, _, _ in transport.requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["cf-ray", "Content-Type"])
async def test_error_response_headers_cannot_leak_token(transport, caplog, header):
    bootstrap(transport)
    response = web.Response(status=200, body=b"not JSON", headers={header: TOKEN})
    assert response.headers[header] == TOKEN
    transport.replies["/api/new/teams/test"].append(response)
    with pytest.raises(http_client.HandballNetHTTPError):
        await fetch(transport)
    assert TOKEN not in caplog.text


@pytest.mark.asyncio
async def test_bootstrap_refresh_failure_headers_cannot_leak_cached_token(transport, caplog):
    caplog.set_level("DEBUG", logger=http_client.__name__)
    bootstrap(transport)
    api(transport)
    await fetch(transport)
    api(transport, status=403)
    response = web.Response(status=503, headers={"cf-ray": TOKEN})
    assert response.headers["cf-ray"] == TOKEN
    transport.replies["/"].append(response)

    with pytest.raises(http_client.HandballNetHTTPError) as caught:
        await fetch(transport)

    assert caught.value.status == 503
    assert [path for path, _, _ in transport.requests] == [
        "/", "/api/new/teams/test", "/api/new/teams/test", "/"
    ]
    assert TOKEN not in caplog.text
    assert TOKEN not in str(caught.value)
    assert TOKEN not in str(http_client._failures)
    assert "bootstrap failed" in caplog.text


@pytest.mark.asyncio
async def test_per_hass_cache_is_isolated(transport):
    bootstrap(transport, token="first-instance")
    api(transport)
    await fetch(transport)
    bootstrap(transport, token="second-instance")
    api(transport)
    await fetch(transport, hass=SimpleNamespace(data={}))
    assert [headers["x-client-token"] for path, headers, _ in transport.requests if path != "/"] == [
        "first-instance", "second-instance"
    ]


@pytest.mark.asyncio
async def test_repeated_failures_are_deduplicated_then_recovery_logged(transport, caplog):
    caplog.set_level("DEBUG", logger=http_client.__name__)
    bootstrap(transport)
    for _ in range(2):
        api(transport, {"error": "unavailable"}, status=503, headers={"cf-ray": "test-ray"})
        with pytest.raises(http_client.HandballNetHTTPError):
            await fetch(transport, params={"limit": 50})
    records = [record for record in caplog.records if record.name == http_client.__name__]
    assert [record.levelname for record in records] == ["WARNING", "DEBUG"]
    assert "test-ray" in caplog.text
    assert "'limit': 50" in caplog.text
    assert "referer=" in caplog.text
    api(transport)
    await fetch(transport)
    assert "reachable again" in caplog.text
    assert "teams/test" not in http_client._failures


@pytest.mark.asyncio
@pytest.mark.parametrize("stage,status", [("bootstrap", 200), ("api", 200), ("api", 500), ("api", 403)])
async def test_invalid_utf8_is_wrapped_without_body_or_token_leak(transport, caplog, stage, status):
    import traceback

    caplog.set_level("DEBUG", logger=http_client.__name__)
    if stage == "api":
        bootstrap(transport)
        if status == 403:
            api(transport, status=403)
            bootstrap(transport, token="refreshed-secret")
    path = "/" if stage == "bootstrap" else "/api/new/teams/test"
    transport.replies[path].append(web.Response(
        status=status,
        body=f"private-undecodable-body {TOKEN} refreshed-secret ".encode() + b"\xff",
        content_type="text/html" if stage == "bootstrap" else "application/json",
        charset="utf-8",
    ))

    with pytest.raises(http_client.HandballNetHTTPError) as caught:
        await fetch(transport)

    assert caught.value.status == status
    assert caught.value.endpoint == "teams/test"
    assert "decod" in caught.value.reason.lower()
    assert ("bootstrap" in caught.value.reason.lower()) == (stage == "bootstrap")
    assert caught.value.__cause__ is None
    diagnostics = caplog.text + str(caught.value) + str(http_client._failures)
    diagnostics += "".join(traceback.format_exception(caught.value))
    for secret in (TOKEN, "refreshed-secret", "private-undecodable-body"):
        assert secret not in diagnostics
    expected = ["/"] if stage == "bootstrap" else ["/", "/api/new/teams/test"]
    if status == 403:
        expected += ["/", "/api/new/teams/test"]
    assert [path for path, _, _ in transport.requests] == expected


@pytest.mark.asyncio
async def test_connection_errors_are_wrapped_without_token_leak(transport, monkeypatch, caplog):
    bootstrap(transport)
    original_get = transport.session.get

    def get(url, **kwargs):
        if "/api/new/" in url:
            raise aiohttp.ClientConnectionError(f"connection failed: {TOKEN}")
        return original_get(url, **kwargs)

    monkeypatch.setattr(transport.session, "get", get)
    with pytest.raises(http_client.HandballNetHTTPError) as caught:
        await fetch(transport)
    assert caught.value.status is None
    assert TOKEN not in caplog.text
    assert TOKEN not in str(caught.value)
    assert caught.value.__cause__ is None
