"""Shared HTTP helper for the new handball.net API (/api/new).

Every failure is logged with enough context (endpoint, params, HTTP status,
Cloudflare ray id, response excerpt) to be pasted directly into a GitHub issue.
Repeated identical failures are logged only once at WARNING (then DEBUG) so the
log is not flooded by coordinator polling; recovery is logged at INFO.
"""
from __future__ import annotations

import asyncio
from html.parser import HTMLParser
import logging
from time import monotonic
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import HANDBALL_NET_NEW_API_BASE_URL, HANDBALL_NET_WEB_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
_BODY_EXCERPT = 300
_TOKEN_TTL = 15 * 60
_TOKEN_DATA_KEY = "handballnet_client_token"
# The HTML site redirects the bare host to www; the API Referer stays bare.
_TOKEN_BOOTSTRAP_URL = "https://www.handball.net/"
# handball.net rejects Python/HA user agents; scope this to our requests only.
_USER_AGENT = "Mozilla/5.0"

# endpoint -> signature of the last logged failure
_failures: dict[str, str] = {}

_STATUS_HINTS = {
    401: "authentication required",
    403: "request rejected by handball.net/Cloudflare - check the client token "
    "and that the Referer matches the API origin (https://handball.net/...)",
    404: "resource not found - team/club/competition id may be invalid or outdated",
    429: "rate limited by handball.net - increase the update interval",
}


class HandballNetHTTPError(Exception):
    """Raised when handball.net cannot be reached or does not answer with usable JSON."""

    def __init__(self, status: int | None, endpoint: str, reason: str) -> None:
        super().__init__(f"{endpoint}: {reason}")
        self.status = status
        self.endpoint = endpoint
        self.reason = reason


def _excerpt(text: str, tokens: tuple[str, ...] | list[str] = ()) -> str:
    # Redact before truncating so excerpts cannot expose partial tokens.
    for token in tokens:
        text = text.replace(token, "[redacted]")
    text = " ".join(text.split())
    return text if len(text) <= _BODY_EXCERPT else text[:_BODY_EXCERPT] + "..."


def _log_failure(endpoint: str, signature: str, message: str, *args: Any) -> None:
    if _failures.get(endpoint) == signature:
        _LOGGER.debug(message + " (repeated)", *args)
        return
    _failures[endpoint] = signature
    _LOGGER.warning(message, *args)


def _log_success(endpoint: str) -> None:
    if _failures.pop(endpoint, None) is not None:
        _LOGGER.info("handball.net API reachable again: %s", endpoint)


class _ClientTokenParser(HTMLParser):
    """Extract the public client token without logging bootstrap HTML."""

    token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("name") == "client-token":
            self.token = attributes.get("content")


async def _async_get_token(
    hass: HomeAssistant, session: aiohttp.ClientSession, endpoint: str,
    *, rejected_token: str | None = None,
) -> str:
    """Return a per-HA cached token, serializing public HTML bootstraps."""
    state = hass.data.setdefault(_TOKEN_DATA_KEY, {"lock": asyncio.Lock()})
    async with state["lock"]:
        token = state.get("token")
        # A different coordinator may already have replaced this rejected token.
        if (rejected_token is not None and token == rejected_token) or token is None or monotonic() >= state["expires_at"]:
            async with session.get(
                _TOKEN_BOOTSTRAP_URL, headers={"User-Agent": _USER_AGENT},
                timeout=REQUEST_TIMEOUT, allow_redirects=False
            ) as response:
                if response.status != 200:
                    _log_failure(
                        endpoint, f"bootstrap-http-{response.status}",
                        "handball.net client-token bootstrap failed for %s: HTTP %s",
                        endpoint, response.status,
                    )
                    raise HandballNetHTTPError(response.status, endpoint, "client-token bootstrap failed")
                parser = _ClientTokenParser()
                try:
                    html = await response.text()
                except UnicodeDecodeError:
                    _log_failure(
                        endpoint, "bootstrap-decode",
                        "handball.net client-token bootstrap failed for %s: response text decoding failed",
                        endpoint,
                    )
                    raise HandballNetHTTPError(
                        response.status, endpoint, "client-token bootstrap response text decoding failed"
                    ) from None
                parser.feed(html)
                token = parser.token
                if not token or not token.strip() or any(ord(char) < 32 or ord(char) == 127 for char in token):
                    _log_failure(
                        endpoint, "bootstrap-no-token",
                        "handball.net client-token bootstrap failed for %s: missing client-token meta tag",
                        endpoint,
                    )
                    raise HandballNetHTTPError(200, endpoint, "missing client-token meta tag")
                state["token"] = token
                state["expires_at"] = monotonic() + _TOKEN_TTL
        return token


async def async_get_json(
    hass: HomeAssistant, endpoint: str, params: dict[str, Any], referer: str
) -> dict[str, Any]:
    """GET an /api/new endpoint using a cached public client token and Referer.

    Refresh the token and retry exactly once after HTTP 403. Raise
    HandballNetHTTPError on network, HTTP and JSON decoding failures.
    """
    session = async_get_clientsession(hass)
    url = f"{HANDBALL_NET_NEW_API_BASE_URL}/{endpoint}"
    tokens: list[str] = []

    try:
        token = await _async_get_token(hass, session, endpoint)
        tokens.append(token)
        for attempt in range(2):
            async with session.get(
                url, params=params,
                headers={"Referer": referer, "x-client-token": token, "User-Agent": _USER_AGENT},
                timeout=REQUEST_TIMEOUT, allow_redirects=False,
            ) as resp:
                ray = _excerpt(resp.headers.get("cf-ray", "-"), tokens)
                try:
                    text = await resp.text()
                except UnicodeDecodeError:
                    _log_failure(
                        endpoint, f"decode-{resp.status}",
                        "handball.net API error: HTTP %s for %s: response text decoding failed",
                        resp.status, endpoint,
                    )
                    raise HandballNetHTTPError(
                        resp.status, endpoint, "response text decoding failed"
                    ) from None
                if resp.status == 403 and attempt == 0:
                    pass  # Release the failed response before refreshing the token.
                else:
                    if resp.status != 200:
                        hint = _STATUS_HINTS.get(resp.status, "unexpected status")
                        _log_failure(
                            endpoint,
                            f"http-{resp.status}",
                            "handball.net API error: HTTP %s for %s (%s) | params=%s | "
                            "referer=%s | cf-ray=%s | response: %s",
                            resp.status,
                            endpoint,
                            hint,
                            params,
                            referer,
                            ray,
                            _excerpt(text, tokens),
                        )
                        raise HandballNetHTTPError(resp.status, endpoint, f"HTTP {resp.status}: {hint}")

                    try:
                        payload = await resp.json(content_type=None)
                    except ValueError:
                        _log_failure(
                            endpoint,
                            "no-json",
                            "handball.net API error: HTTP 200 but no valid JSON for %s "
                            "(content-type=%s, cf-ray=%s, possibly a Cloudflare challenge page) | "
                            "response: %s",
                            endpoint,
                            _excerpt(resp.headers.get("content-type", "-"), tokens),
                            ray,
                            _excerpt(text, tokens),
                        )
                        raise HandballNetHTTPError(200, endpoint, "response is not JSON") from None
                    break
            token = await _async_get_token(hass, session, endpoint, rejected_token=token)
            tokens.append(token)

    except HandballNetHTTPError:
        raise
    except asyncio.TimeoutError:
        _log_failure(
            endpoint,
            "timeout",
            "handball.net API error: timeout after %ss for %s",
            REQUEST_TIMEOUT.total,
            endpoint,
        )
        raise HandballNetHTTPError(None, endpoint, "timeout") from None
    except aiohttp.ClientError as err:
        reason = _excerpt(str(err), tokens)
        _log_failure(
            endpoint,
            f"client-{type(err).__name__}",
            "handball.net API error: connection problem for %s: %s: %s",
            endpoint,
            type(err).__name__,
            reason,
        )
        raise HandballNetHTTPError(None, endpoint, reason) from None

    if not isinstance(payload, dict):
        _log_failure(
            endpoint, "nonobject-json",
            "handball.net API error: expected JSON object for %s | response: %s",
            endpoint, _excerpt(text, tokens),
        )
        raise HandballNetHTTPError(200, endpoint, "response is not a JSON object")

    if payload.get("success") is False:
        detail = payload.get("error") or payload.get("message") or payload.get("errors")
        detail = _excerpt(str(detail), tokens)
        _log_failure(
            endpoint,
            f"success-false-{detail}",
            "handball.net API reported an error for %s | params=%s | error=%s | response: %s",
            endpoint,
            params,
            detail,
            _excerpt(str(payload), tokens),
        )
        raise HandballNetHTTPError(200, endpoint, f"API reported an error: {detail}")

    _log_success(endpoint)
    return payload
