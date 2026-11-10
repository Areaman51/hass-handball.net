"""Regression: browser-compatible UA on both requests, never session-global."""
from aiohttp import web
import pytest
from .test_http_client import transport, fetch, TOKEN


@pytest.mark.asyncio
async def test_user_agent_is_request_scoped_on_bootstrap_and_api(transport):
    transport.session.headers['User-Agent'] = 'HomeAssistant/test Python/aiohttp'
    defaults_before = dict(transport.session.headers)

    async def gated_bootstrap(request):
        if request.headers.get('User-Agent') != 'Mozilla/5.0':
            return web.Response(status=403, text='Forbidden')
        return web.Response(text=f'<meta name="client-token" content="{TOKEN}">')

    async def gated_api(request):
        if request.headers.get('User-Agent') != 'Mozilla/5.0':
            return web.Response(status=403, text='Forbidden')
        return web.json_response({'data': {'name': 'Test'}})

    transport.replies['/'].append(gated_bootstrap)
    transport.replies['/api/new/teams/test'].append(gated_api)
    assert await fetch(transport) == {'data': {'name': 'Test'}}
    assert [p for p, _, _ in transport.requests] == ['/', '/api/new/teams/test']
    assert all(h['User-Agent'] == 'Mozilla/5.0' for _, h, _ in transport.requests)
    assert dict(transport.session.headers) == defaults_before
