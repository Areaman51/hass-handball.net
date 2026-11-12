"""Unit boundaries for publishing registry changes to sensor states."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/handballnet"


@pytest.fixture
def bridge(monkeypatch):
    import homeassistant.helpers.update_coordinator as uc

    class HostEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator
            self.hass = coordinator.hass
            self.remove_callbacks = []
            self.writes = 0
            self.parent_added = False

        async def async_added_to_hass(self):
            self.parent_added = True

        def async_on_remove(self, callback):
            self.remove_callbacks.append(callback)

        def async_write_ha_state(self):
            self.writes += 1

    monkeypatch.setattr(uc, "CoordinatorEntity", HostEntity, raising=False)
    devices = ModuleType("custom_components.handballnet.device_helpers")
    devices.via_device_fields = lambda *args: {}
    monkeypatch.setitem(sys.modules, devices.__name__, devices)
    manager_module = ModuleType("custom_components.handballnet.logo_manager")
    manager_module.get_logo_manager = lambda hass: hass.data.get("handballnet", {}).get("_logo_manager")
    manager_module.LogoStorageError = type("LogoStorageError", (RuntimeError,), {})
    monkeypatch.setitem(sys.modules, manager_module.__name__, manager_module)
    spec = importlib.util.spec_from_file_location(
        "custom_components.handballnet.sensors._bridge_test_base", ROOT / "sensors/base_sensor.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules, "custom_components.handballnet.sensors.base_sensor", module)
    manager = SimpleNamespace()
    manager.callbacks = []
    manager.as_attributes = lambda: {
        "handballnet_logo_overrides": {"SG Beispielstadt": "/local/own.png"},
        "handballnet_logo_revision": 2,
    }

    def listen(callback):
        manager.callbacks.append(callback)
        return lambda: manager.callbacks.remove(callback)

    manager.async_listen = listen
    hass = SimpleNamespace(data={"handballnet": {"_logo_manager": manager}})
    coordinator = SimpleNamespace(hass=hass)
    entry = SimpleNamespace(entry_id="example-entry")
    return module.HandballBaseSensor, coordinator, entry, manager


def test_sensor_bridge_exposes_central_snapshot_without_mutating_api(bridge):
    cls, coordinator, entry, _ = bridge
    entity = cls(coordinator, entry, "example-team")
    assert entity.central_logo_attributes == {
        "handballnet_logo_overrides": {"SG Beispielstadt": "/local/own.png"},
        "handballnet_logo_revision": 2,
    }


@pytest.mark.asyncio
async def test_registry_changes_push_sensor_state_without_api_refresh(bridge):
    cls, coordinator, entry, manager = bridge
    entity = cls(coordinator, entry, "example-team")
    entity._supports_central_logos = True
    await entity.async_added_to_hass()
    assert entity.parent_added
    assert len(manager.callbacks) == 1
    manager.callbacks[0]()
    assert entity.writes == 1
    assert len(entity.remove_callbacks) == 1
    entity.remove_callbacks[0]()
    assert manager.callbacks == []


@pytest.mark.parametrize("module_name,class_name,args", [
    ("team.next_match_sensor", "HandballNextMatchSensor", ("T", "SG Beispielstadt")),
    ("team.live_ticker_sensor", "HandballLiveTickerSensor", ("T", "SG Beispielstadt")),
    ("tournament.tournament_table_sensor", "HandballTournamentTableSensor", ("Q",)),
    ("tournament.tournament_schedule_sensor", "HandballTournamentScheduleSensor", ("Q",)),
])
@pytest.mark.parametrize("has_api_data", [False, True])
def test_every_card_source_exposes_registry_even_without_matches(bridge, module_name, class_name, args, has_api_data):
    import copy
    import importlib

    _, coordinator, _, _ = bridge
    coordinator.data = {"teams": {}, "tournament": {}}
    if has_api_data:
        home = {"name": "SG Beispielstadt", "logo": "https://api.example/logo.png"}
        coordinator.data = {
            "teams": {"T": {"next_match": {"home_team": home, "away_team": {"name": "Gast"}}, "live_matches": [{"homeTeam": home, "awayTeam": {"name": "Gast"}}]}},
            "tournament": {"table_rows": [{"team_name": home["name"], "team_logo": home["logo"], "points": 1}], "matches": []},
        }
    before = copy.deepcopy(coordinator.data)
    entry = SimpleNamespace(entry_id="example-entry", data={})
    module = importlib.import_module("custom_components.handballnet.sensors." + module_name)
    entity = getattr(module, class_name)(coordinator, entry, *args)
    attrs = entity.extra_state_attributes
    assert attrs.get("handballnet_logo_overrides") == {"SG Beispielstadt": "/local/own.png"}
    assert attrs["handballnet_logo_revision"] == 2
    assert entity._supports_central_logos is True
    assert coordinator.data == before


@pytest.mark.asyncio
async def test_entry_loads_shared_registry_before_entities_are_created(bridge, monkeypatch):
    import importlib

    integration = importlib.import_module("custom_components.handballnet")
    _, coordinator, _, manager = bridge
    events = []

    async def load(hass):
        events.append("registry")
        return manager

    sys.modules["custom_components.handballnet.logo_manager"].async_get_logo_manager = load

    class Coordinator:
        def __init__(self, hass, entry):
            self.hass = hass

        async def async_config_entry_first_refresh(self):
            events.append("refresh")

    async def forward(entry, platforms):
        events.append("entities")

    monkeypatch.setitem(sys.modules, "custom_components.handballnet.coordinator", SimpleNamespace(HandballDataUpdateCoordinator=Coordinator))
    hass = coordinator.hass
    hass.config_entries = SimpleNamespace(async_forward_entry_setups=forward)
    entry = SimpleNamespace(entry_id="test", data={"entity_type": "tournament", "tournament_id": "Q"})
    assert await integration.async_setup_entry(hass, entry) is True
    assert events == ["registry", "refresh", "entities"]


@pytest.mark.asyncio
async def test_damaged_optional_logo_store_does_not_disable_sports_data(bridge, monkeypatch, caplog):
    import importlib

    integration = importlib.import_module("custom_components.handballnet")
    _, coordinator, _, _ = bridge
    events = []
    module = sys.modules["custom_components.handballnet.logo_manager"]

    async def load(hass):
        raise module.LogoStorageError("storage_error")

    module.async_get_logo_manager = load

    class Coordinator:
        def __init__(self, hass, entry):
            self.hass = hass

        async def async_config_entry_first_refresh(self):
            events.append("refresh")

    async def forward(entry, platforms):
        events.append("entities")

    monkeypatch.setitem(sys.modules, "custom_components.handballnet.coordinator", SimpleNamespace(HandballDataUpdateCoordinator=Coordinator))
    hass = coordinator.hass
    hass.data['handballnet'].pop('_logo_manager')
    hass.config_entries = SimpleNamespace(async_forward_entry_setups=forward)
    entry = SimpleNamespace(entry_id="test", data={"entity_type": "tournament", "tournament_id": "Q"})
    assert await integration.async_setup_entry(hass, entry) is True
    assert events == ['refresh', 'entities']
    assert 'logo' in caplog.text.lower()
    assert module.get_logo_manager(hass) is None


def test_manifest_enables_native_upload_runtime():
    import json

    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert "file_upload" in manifest["dependencies"]
