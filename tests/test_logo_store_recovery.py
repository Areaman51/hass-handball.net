"""Recover a genuinely rejected logo store with already-added sports sensors."""
from __future__ import annotations

import asyncio
import copy
import importlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/handballnet"
SOURCES = (
    ("team.next_match_sensor", "HandballNextMatchSensor", ("T", "SG Beispielstadt")),
    ("team.live_ticker_sensor", "HandballLiveTickerSensor", ("T", "SG Beispielstadt")),
    ("tournament.tournament_table_sensor", "HandballTournamentTableSensor", ("Q",)),
    ("tournament.tournament_schedule_sensor", "HandballTournamentScheduleSensor", ("Q",)),
)
SPORTS = {
    "teams": {"T": {
        "next_match": {
            "opponent": {"name": "Gast"},
            "home_team": {"name": "SG Beispielstadt", "logo": "/api-original.png"},
        },
        "live_matches": [{"id": "live-fixture"}],
    }},
    "tournament": {
        "table_rows": [{"team_name": "SG Beispielstadt", "points": 2}],
        "matches": [],
    },
}


@pytest.fixture
def recovery(monkeypatch, tmp_path):
    """Only HA lifecycle/storage boundaries are doubles; load real integration code."""
    import homeassistant.helpers.update_coordinator as uc

    lm = importlib.import_module("custom_components.handballnet.logo_manager")

    class HostEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator
            self.hass = coordinator.hass
            self.remove_callbacks = []
            self.writes = []
            self.added = 0

        async def async_added_to_hass(self):
            self.added += 1

        def async_on_remove(self, callback):
            self.remove_callbacks.append(callback)

        def async_write_ha_state(self):
            self.writes.append(copy.deepcopy((
                self.state, self.extra_state_attributes,
                self.hass.data.get("_test_stores", {}).get(lm.STORAGE_KEY),
            )))

        def remove(self):
            for callback in self.remove_callbacks:
                callback()
            self.remove_callbacks.clear()

    monkeypatch.setattr(uc, "CoordinatorEntity", HostEntity, raising=False)
    devices = ModuleType("custom_components.handballnet.device_helpers")
    devices.via_device_fields = lambda *args: {}
    monkeypatch.setitem(sys.modules, devices.__name__, devices)
    modules = {}
    for suffix in ("base_sensor", "team.base_sensor", "tournament.base_sensor",
                   *(source[0] for source in SOURCES)):
        name = "custom_components.handballnet.sensors." + suffix
        spec = importlib.util.spec_from_file_location(
            name, ROOT / "sensors" / (suffix.replace(".", "/") + ".py")
        )
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[suffix] = module

    async def executor(func, *args):
        return await asyncio.to_thread(func, *args)

    # Malformed real payload: _async_load itself raises LogoStorageError.
    hass = SimpleNamespace(
        data={"_test_stores": {lm.STORAGE_KEY: {"revision": "broken"}}},
        config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts))),
        async_add_executor_job=executor,
    )
    entry = SimpleNamespace(
        entry_id="recovery-fixture",
        data={"entity_type": "tournament", "tournament_id": "Q"},
        options={"update_interval": 7200, "update_interval_live": 20, "keep": "unchanged"},
    )
    entities = []
    api = SimpleNamespace(get_team_schedule=AsyncMock(), get_tournament_schedule=AsyncMock())

    class Coordinator:
        def __init__(self, hass, entry):
            self.hass = hass
            self.data = copy.deepcopy(SPORTS)
            self.api = api
            self.async_config_entry_first_refresh = AsyncMock()
            self.async_request_refresh = AsyncMock()

    async def forward(entry, platforms):
        for suffix, class_name, args in SOURCES:
            entity = getattr(modules[suffix], class_name)(entry.runtime_data, entry, *args)
            entities.append(entity)
            await entity.async_added_to_hass()

    hass.config_entries = SimpleNamespace(
        async_forward_entry_setups=AsyncMock(side_effect=forward),
        async_entries=lambda domain: [entry],
        async_reload=AsyncMock(),
    )
    monkeypatch.setitem(sys.modules, "custom_components.handballnet.coordinator",
                        SimpleNamespace(HandballDataUpdateCoordinator=Coordinator))
    return SimpleNamespace(hass=hass, entry=entry, entities=entities, lm=lm, api=api)


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_attempts", [1, 3])
async def test_repaired_store_save_pushes_each_existing_source_once(recovery, monkeypatch, caplog, failed_attempts):
    r = recovery
    integration = importlib.import_module("custom_components.handballnet")
    before_options = copy.deepcopy(r.entry.options)
    assert await integration.async_setup_entry(r.hass, r.entry)
    assert any(record.exc_info and isinstance(record.exc_info[1], r.lm.LogoStorageError)
               for record in caplog.records)
    assert r.lm.get_logo_manager(r.hass) is None
    assert r.hass.data["_test_stores"][r.lm.STORAGE_KEY] == {"revision": "broken"}
    assert len(r.entities) == 4
    initial = [copy.deepcopy((entity.state, entity.extra_state_attributes)) for entity in r.entities]
    assert [state for state, _ in initial] == ["Gast", "Live", "SG Beispielstadt führt mit 2 Punkten", 0]
    assert all(attrs["handballnet_logo_overrides"] == {} for _, attrs in initial)

    # Failed retries after entity subscription must not lose or duplicate it.
    for _ in range(failed_attempts - 1):
        with pytest.raises(r.lm.LogoStorageError):
            await r.lm.async_get_logo_manager(r.hass)

    # Synthetic repair; the options flow performs the first successful load.
    r.hass.data["_test_stores"][r.lm.STORAGE_KEY] = {
        "overrides": {"restored": "/local/retained.png"}, "revision": 7,
    }
    of = importlib.import_module("custom_components.handballnet.options_flow")
    flow = of.HandballNetOptionsFlowHandler(r.entry)
    flow.hass, flow.config_entry = r.hass, r.entry
    assert (await flow.async_step_logos({"team_name": "SG Beispielstadt"}))["step_id"] == "logo_action"
    manager, same = await asyncio.gather(
        r.lm.async_get_logo_manager(r.hass), r.lm.async_get_logo_manager(r.hass),
    )
    assert manager is same is r.lm.get_logo_manager(r.hass)
    assert all(not entity.writes for entity in r.entities)

    # Recovery listeners must retain failure isolation and wait for persistence.
    def broken_listener():
        raise RuntimeError("synthetic listener failure")

    unsubscribe_broken = manager.async_listen(broken_listener)
    started, release = asyncio.Event(), asyncio.Event()
    original_save = manager._store.async_save

    async def gated_save(payload):
        started.set()
        await release.wait()
        await original_save(payload)

    monkeypatch.setattr(manager._store, "async_save", gated_save)
    save = asyncio.create_task(flow.async_step_logo_url({"url": "/local/recovered.png"}))
    await started.wait()
    assert all(not entity.writes for entity in r.entities)
    release.set()
    assert await save == {"type": "abort", "reason": "logo_saved"}
    expected_overrides = {"restored": "/local/retained.png", "sg beispielstadt": "/local/recovered.png"}
    payload = {"overrides": expected_overrides, "revision": 8}
    for entity, (state, attrs) in zip(r.entities, initial):
        attrs.update(handballnet_logo_overrides=expected_overrides, handballnet_logo_revision=8)
        assert entity.writes == [(state, attrs, payload)], type(entity).__name__
        assert entity.added == 1
    assert "synthetic listener failure" in caplog.text
    assert r.entry.runtime_data.data == SPORTS
    assert r.entry.options == before_options
    r.entry.runtime_data.async_config_entry_first_refresh.assert_awaited_once()
    r.entry.runtime_data.async_request_refresh.assert_not_called()
    r.api.get_team_schedule.assert_not_called()
    r.api.get_tournament_schedule.assert_not_called()
    r.hass.config_entries.async_reload.assert_not_called()
    r.hass.config_entries.async_forward_entry_setups.assert_awaited_once()

    unsubscribe_broken()
    for entity in r.entities:
        entity.remove()
    await manager.async_set_url("SG Beispielstadt", "/local/after-removal.png")
    assert all(len(entity.writes) == 1 for entity in r.entities)


@pytest.mark.asyncio
async def test_unsubscribe_before_store_recovery_remains_effective(recovery):
    r = recovery
    integration = importlib.import_module("custom_components.handballnet")
    assert await integration.async_setup_entry(r.hass, r.entry)
    assert r.lm.get_logo_manager(r.hass) is None
    for entity in r.entities:
        assert len(entity.remove_callbacks) == 1
        entity.remove()
    with pytest.raises(r.lm.LogoStorageError):
        await r.lm.async_get_logo_manager(r.hass)
    r.hass.data["_test_stores"][r.lm.STORAGE_KEY] = {"overrides": {}, "revision": 0}
    manager = await r.lm.async_get_logo_manager(r.hass)
    await manager.async_set_url("SG Beispielstadt", "/local/removed-before-repair.png")
    assert all(not entity.writes for entity in r.entities)
