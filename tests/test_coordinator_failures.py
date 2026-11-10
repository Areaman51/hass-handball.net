"""Do not replace known team data with empty buckets on API failures."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.handballnet.coordinator import HandballDataUpdateCoordinator
from custom_components.handballnet.http_client import HandballNetHTTPError


@pytest.fixture
def coordinator():
    coordinator = HandballDataUpdateCoordinator.__new__(HandballDataUpdateCoordinator)
    coordinator.hass = SimpleNamespace(data={"handballnet": {"86229": {"matches": [{"id": "existing"}]}}})
    coordinator._api = SimpleNamespace(
        get_team_schedule=AsyncMock(side_effect=HandballNetHTTPError(403, "matches", "denied")),
        get_team_info=AsyncMock(return_value=None),
        extract_team_logo_url=MagicMock(return_value=None),
    )
    coordinator._standard_interval = 3600
    coordinator._live_interval = 15
    coordinator._perf_snapshot = {"phases_ms": {}, "team_bucket_ms": {}}
    coordinator._entity_type = "club"
    coordinator._team_items = [("86229", "Test team")]
    coordinator._store_team_bucket = MagicMock()
    return coordinator


@pytest.mark.asyncio
async def test_team_schedule_failure_reaches_coordinator(coordinator):
    with pytest.raises(UpdateFailed, match="schedule"):
        await coordinator._load_team_bucket("86229", "Test team")


@pytest.mark.asyncio
async def test_failed_team_update_does_not_overwrite_existing_bucket(coordinator):
    coordinator._load_team_bucket = AsyncMock(side_effect=HandballNetHTTPError(403, "matches", "denied"))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    coordinator._store_team_bucket.assert_not_called()
    assert coordinator.hass.data["handballnet"]["86229"]["matches"] == [{"id": "existing"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_first", [False, True])
async def test_one_failed_team_prevents_all_partial_bucket_writes(coordinator, failed_first):
    coordinator._team_items = [("86229", "Existing team"), ("other", "Other team")]
    success = {"is_live": False, "matches": [{"id": "new-match"}]}
    failure = HandballNetHTTPError(503, "matches", "denied")
    coordinator._load_team_bucket = AsyncMock(side_effect=[failure, success] if failed_first else [success, failure])
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    coordinator._store_team_bucket.assert_not_called()
    assert coordinator.hass.data["handballnet"] == {"86229": {"matches": [{"id": "existing"}]}}


@pytest.mark.asyncio
async def test_failed_tournament_update_is_an_update_failure(coordinator):
    coordinator._entity_type = "tournament"
    coordinator._async_update_tournament_data = AsyncMock(side_effect=HandballNetHTTPError(403, "standings", "denied"))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_failed_participant_schedule_does_not_publish_partial_tournament(coordinator):
    coordinator._tournament_id = "13541"
    with pytest.raises(UpdateFailed):
        await coordinator._fetch_tournament_matches([{"team_id": "86229"}])


@pytest.mark.asyncio
async def test_failed_team_table_fetch_is_not_silently_replaced_with_none(coordinator):
    coordinator._api.get_team_table_position = AsyncMock(side_effect=HandballNetHTTPError(403, "standings", "denied"))
    with pytest.raises(UpdateFailed):
        await coordinator._load_table_position("86229", "13541")
