"""Shared limits for untrusted API lists and bounded async fan-out."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from itertools import chain
from typing import Any, TypeVar

from .http_client import HandballNetHTTPError

# Large enough for full season histories; never truncate an apparently valid list.
MAX_PAGES = 100
MAX_RECORDS = 10_000
MAX_FANOUT_WORKERS = 4
MAX_FIELD_BYTES = 16 * 1024
# Canonical compact UTF-8 JSON bytes, not CPython object/RSS estimates.
MAX_CACHE_ENTRY_BYTES = 8 * 1024 * 1024
MAX_CACHE_BYTES = 16 * 1024 * 1024
MAX_TOURNAMENT_RESULT_BYTES = 16 * 1024 * 1024
_T = TypeVar("_T")


def validate_fields(value: Any, endpoint: str) -> None:
    """Bound every retained UTF-8 string, including nested data and keys."""
    pending = [iter((value,))]
    while pending:
        try:
            item = next(pending[-1])
        except StopIteration:
            pending.pop()
            continue
        if isinstance(item, str):
            if len(item) > MAX_FIELD_BYTES:
                raise HandballNetHTTPError(200, endpoint, "field byte limit exceeded")
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError:
                raise HandballNetHTTPError(
                    200, endpoint, "invalid field encoding"
                ) from None
            if size > MAX_FIELD_BYTES:
                raise HandballNetHTTPError(200, endpoint, "field byte limit exceeded")
        elif isinstance(item, dict):
            pending.append(chain(item.keys(), item.values()))
        elif isinstance(item, list):
            pending.append(iter(item))


def payload_bytes(value: Any, endpoint: str, limit: int) -> int:
    """Measure without allocating a second complete serialized payload."""
    validate_fields(value, endpoint)
    size = 0
    try:
        for chunk in json.JSONEncoder(
            ensure_ascii=False, separators=(",", ":")
        ).iterencode(value):
            size += len(chunk.encode("utf-8"))
            if size > limit:
                raise HandballNetHTTPError(200, endpoint, "result byte limit exceeded")
    except (RecursionError, UnicodeError, ValueError):
        raise HandballNetHTTPError(200, endpoint, "invalid result encoding") from None
    return size


class MatchWorkBudget:
    """Count inspected schedules, not only unique/target tournament results."""

    def __init__(self) -> None:
        self.records = 0
        self.result_bytes = 0
        self.failure_reason: str | None = None

    def check_start(self) -> None:
        if self.failure_reason is not None:
            raise HandballNetHTTPError(200, "matches", self.failure_reason)
        if self.records >= MAX_RECORDS:
            raise HandballNetHTTPError(
                200, "matches", "Tournament match record limit exceeded"
            )
        if self.result_bytes >= MAX_TOURNAMENT_RESULT_BYTES:
            raise HandballNetHTTPError(
                200, "matches", "Tournament result byte limit exceeded"
            )

    def consume(self, count: int) -> None:
        if self.records + count > MAX_RECORDS:
            self.failure_reason = "Tournament match record limit exceeded"
            raise HandballNetHTTPError(200, "matches", self.failure_reason)
        self.records += count


_match_work: ContextVar[MatchWorkBudget | None] = ContextVar(
    "handballnet_match_work", default=None
)


@contextmanager
def match_work_budget():
    """Propagate one shared counter to all child workers; restore on failure."""
    budget = MatchWorkBudget()
    token = _match_work.set(budget)
    try:
        yield budget
    finally:
        _match_work.reset(token)


def charge_match_records(count: int) -> None:
    if (budget := _match_work.get()) is not None:
        budget.consume(count)


def check_match_work_start() -> None:
    """Reject further schedule pages after shared work has been exhausted."""
    if (budget := _match_work.get()) is not None:
        budget.check_start()


def charge_match_bytes(result: Any) -> None:
    """Count normalized schedules, including cache hits, before retention."""
    if (budget := _match_work.get()) is not None:
        try:
            budget.result_bytes += payload_bytes(
                result, "matches", MAX_TOURNAMENT_RESULT_BYTES - budget.result_bytes
            )
        except HandballNetHTTPError:
            budget.failure_reason = "Tournament result byte limit exceeded"
            raise


async def async_bounded_map(
    function: Callable[[_T], Awaitable[Any]],
    items: Sequence[_T],
    *,
    return_exceptions: bool = False,
) -> list[Any]:
    """Run ordered work with at most four tasks, never one task per item.

    Cancellation (including a self-cancelled child) is not an optional failure:
    propagate it and cancel/await every sibling before returning to the caller.
    """
    results: list[Any] = [None] * len(items)
    pending = iter(enumerate(items))

    async def worker() -> None:
        for index, item in pending:
            try:
                results[index] = await function(item)
            except Exception as err:
                if not return_exceptions:
                    raise
                results[index] = err

    tasks = [
        asyncio.create_task(worker())
        for _ in range(min(MAX_FANOUT_WORKERS, len(items)))
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return results


def validate_records(
    payload: dict, endpoint: str, *, count: int = 0
) -> list[dict[str, Any]]:
    """Require a bounded list of records before consumers iterate or cache it."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise HandballNetHTTPError(200, endpoint, "invalid record list")
    records = payload["data"]
    if len(records) + count > MAX_RECORDS:
        raise HandballNetHTTPError(200, endpoint, "record limit exceeded")
    if any(not isinstance(record, dict) for record in records):
        raise HandballNetHTTPError(200, endpoint, "invalid record type")
    validate_fields(records, endpoint)
    return records


def validate_last_page(
    payload: dict,
    endpoint: str,
    previous: int,
    *,
    metadata: str = "pagination",
    key: str = "last_page",
) -> int:
    """Accept only real positive integers, bounded and never decreasing.

    Missing pagination retains the prior bound (single-page endpoints omit it).
    Explicit null, bool, float and numeric strings are not valid page counts.
    """
    pagination = payload.get(metadata, {})
    if not isinstance(pagination, dict):
        raise HandballNetHTTPError(200, endpoint, "invalid pagination object")
    last_page = pagination.get(key, previous)
    if type(last_page) is not int or not previous <= last_page <= MAX_PAGES:
        raise HandballNetHTTPError(
            200, endpoint, "invalid page count or page limit exceeded"
        )
    return last_page
