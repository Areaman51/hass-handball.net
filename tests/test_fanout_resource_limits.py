"""Fan-out creates bounded tasks, not thousands of semaphore waiters."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.handballnet.config_flow import HandballNetConfigFlow

from .test_coordinator_failures import coordinator  # noqa: F401 (pytest fixture)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path", ["club", "tournament_logos", "tournament_schedules", "flow"]
)
async def test_fanout_has_at_most_four_workers(coordinator, path):
    # Real HA's interval setter requires timedelta; the legacy fixture is a stub.
    coordinator._standard_interval = timedelta(hours=1)
    coordinator._live_interval = timedelta(seconds=15)
    release = asyncio.Event()
    saturated = asyncio.Event()
    started = 0
    # Exercise the full accepted logo workload; 257+ participants must be
    # rejected before workers start (covered by the HTTP-R1 regression).
    count = {"tournament_schedules": 100, "tournament_logos": 256}.get(path, 1000)

    async def blocked(*args):
        nonlocal started
        started += 1
        if started >= 4:
            saturated.set()
        await release.wait()
        return {"is_live": False} if path == "club" else None

    if path == "club":
        coordinator._team_items = [(str(i), "Team") for i in range(count)]
        coordinator._load_team_bucket = blocked
        operation = coordinator._async_update_data()
    elif path == "tournament_logos":
        coordinator._api.get_team_info = blocked
        coordinator._utils = MagicMock()
        operation = coordinator._extract_table_rows_with_logos(
            [{"team": {"id": str(i)}} for i in range(count)]
        )
    elif path == "tournament_schedules":
        coordinator._tournament_id = "league"
        coordinator._api.get_team_schedule = blocked
        operation = coordinator._fetch_tournament_matches(
            [{"team_id": str(i)} for i in range(count)]
        )
    else:
        flow = HandballNetConfigFlow()
        flow._api_get_new_paginated = AsyncMock(
            return_value=[{"id": str(i), "name": f"Team {i}"} for i in range(count)]
        )
        flow._get_team_league_name = blocked
        operation = flow._get_teams_for_club("club")
    previous = asyncio.all_tasks()
    parent = asyncio.create_task(operation)
    try:
        await asyncio.wait_for(saturated.wait(), 1)
        await asyncio.sleep(0.02)
        created = asyncio.all_tasks() - previous
        assert started == 4
        assert len(created) <= 5  # parent + four workers, independent of input size
    finally:
        release.set()
        await parent
    assert started == count


@pytest.mark.asyncio
async def test_cancelled_club_update_awaits_children_and_never_publishes(coordinator):
    started = asyncio.Event()
    active = 0

    async def blocked(*args):
        nonlocal active
        active += 1
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1

    coordinator._team_items = [(str(i), "Team") for i in range(100)]
    coordinator._load_team_bucket = blocked
    previous = asyncio.all_tasks()
    parent = asyncio.create_task(coordinator._async_update_data())
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.sleep(0.01)
    children = asyncio.all_tasks() - previous - {parent}
    parent.cancel()
    with pytest.raises(asyncio.CancelledError):
        await parent
    assert active == 0
    assert all(task.done() for task in children)
    coordinator._store_team_bucket.assert_not_called()


@pytest.mark.asyncio
async def test_self_cancelled_team_propagates_cancellation_not_partial_success(
    coordinator,
):
    coordinator._load_team_bucket = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await coordinator._async_update_data()
    coordinator._store_team_bucket.assert_not_called()


@pytest.mark.asyncio
async def test_self_cancelled_schedule_propagates_cancellation(coordinator):
    coordinator._api.get_team_schedule = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await coordinator._load_team_bucket("id", "Team")


@pytest.mark.asyncio
async def test_tournament_discovery_limit_is_failure_not_truncated_success(coordinator):
    coordinator._tournament_id = "league"
    coordinator._api.get_team_schedule = AsyncMock(
        return_value=[
            {
                "id": "match",
                "tournament": {"id": "league"},
                "homeTeam": {"id": "256"},
                "awayTeam": {},
            }
        ]
    )
    coordinator._extract_essential_match_data = MagicMock(return_value=[])
    with pytest.raises(UpdateFailed, match="team limit"):
        await coordinator._fetch_tournament_matches(
            [{"team_id": str(i)} for i in range(256)]
        )


@pytest.mark.asyncio
async def test_tournament_initial_participants_cannot_bypass_team_limit(coordinator):
    coordinator._tournament_id = "league"
    coordinator._api.get_team_schedule = AsyncMock(return_value=[])
    coordinator._extract_essential_match_data = MagicMock(return_value=[])
    with pytest.raises(UpdateFailed, match="team limit"):
        await coordinator._fetch_tournament_matches(
            [{"team_id": str(i)} for i in range(257)]
        )
    coordinator._api.get_team_schedule.assert_not_called()


@pytest.mark.asyncio
async def test_tournament_aggregate_match_limit_is_failure(coordinator):
    coordinator._tournament_id = "league"
    coordinator._api.get_team_schedule = AsyncMock(
        return_value=[
            {
                "id": str(i),
                "tournament": {"id": "league"},
                "homeTeam": {},
                "awayTeam": {},
            }
            for i in range(10001)
        ]
    )
    coordinator._extract_essential_match_data = MagicMock(return_value=[])
    with pytest.raises(UpdateFailed, match="record limit"):
        await coordinator._fetch_tournament_matches([{"team_id": "team"}])
