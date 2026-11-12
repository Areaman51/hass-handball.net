from __future__ import annotations

from types import ModuleType
import sys


def _install_homeassistant_stubs() -> None:
    try:
        import homeassistant  # noqa: F401
        return
    except Exception:
        pass

    homeassistant = ModuleType("homeassistant")
    homeassistant.__path__ = []

    config_entries = ModuleType("homeassistant.config_entries")
    helpers = ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    config_validation = ModuleType("homeassistant.helpers.config_validation")
    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    core = ModuleType("homeassistant.core")

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            return None

        def async_show_form(self, *, step_id, data_schema, errors):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors,
            }

        def async_create_entry(self, *, title, data):
            return {
                "type": "create_entry",
                "title": title,
                "data": data,
            }

        def async_abort(self, *, reason):
            return {"type": "abort", "reason": reason}

        def _async_current_entries(self):
            return []

    class OptionsFlow:
        def __init__(self):
            self.config_entry = None

        def async_create_entry(self, *, title, data):
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(self, *, step_id, data_schema, errors, description_placeholders=None):
            return {
                "type": "form", "step_id": step_id, "data_schema": data_schema,
                "errors": errors, "description_placeholders": description_placeholders,
            }

        def async_show_menu(self, *, step_id, menu_options, description_placeholders=None):
            return {"type": "menu", "step_id": step_id, "menu_options": menu_options,
                    "description_placeholders": description_placeholders}

        def async_abort(self, *, reason):
            return {"type": "abort", "reason": reason}

    class ConfigEntry:
        pass

    class HomeAssistant:
        pass

    def callback(func):
        return func

    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
    config_entries.ConfigEntry = ConfigEntry

    config_validation.multi_select = lambda options: (lambda value: value)
    config_validation.config_entry_only_config_schema = lambda domain: domain

    aiohttp_client.async_get_clientsession = lambda hass: None

    core.HomeAssistant = HomeAssistant
    core.callback = callback

    homeassistant.config_entries = config_entries
    homeassistant.helpers = helpers
    homeassistant.core = core

    helpers.config_validation = config_validation
    helpers.aiohttp_client = aiohttp_client

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.config_validation"] = config_validation
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.core"] = core

    update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        def __class_getitem__(cls, item):
            return cls

    # Additional test doubles for the central logo manager; never production fallbacks.
    import copy

    storage = ModuleType("homeassistant.helpers.storage")

    class Store:
        def __init__(self, hass, version, key, **kwargs):
            self.hass, self.key = hass, key
            self.version, self.kwargs = version, kwargs

        @property
        def path(self):
            return self.hass.config.path("test-storage", self.key)

        async def async_load(self):
            return copy.deepcopy(self.hass.data.get("_test_stores", {}).get(self.key))

        async def async_save(self, data):
            self.hass.data.setdefault("_test_stores", {})[self.key] = copy.deepcopy(data)

    storage.Store = Store
    sys.modules["homeassistant.helpers.storage"] = storage

    components = ModuleType("homeassistant.components")
    components.__path__ = []
    file_upload = ModuleType("homeassistant.components.file_upload")

    def process_uploaded_file(hass, file_id):
        raise ValueError("File does not exist")

    file_upload.process_uploaded_file = process_uploaded_file
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.file_upload"] = file_upload

    selector = ModuleType("homeassistant.helpers.selector")

    class SelectSelector:
        def __init__(self, config):
            self.config = config

        def __call__(self, value):
            import probatio as p
            if not isinstance(value, str) or (
                not self.config.get("custom_value") and value not in self.config["options"]
            ):
                raise p.Invalid("Invalid selection")
            return value

        def serialize(self):
            return {"selector": {"select": self.config}}

    class TextSelector:
        def __init__(self, config=None):
            self.config = config or {}

        def __call__(self, value):
            import probatio as p
            return p.Schema(str)(value)

        def serialize(self):
            return {"selector": {"text": self.config}}

    class FileSelector(TextSelector):
        def __call__(self, value):
            from uuid import UUID
            value = super().__call__(value)
            UUID(value)
            return value

        def serialize(self):
            return {"selector": {"file": self.config}}

    class BooleanSelector(TextSelector):
        def __call__(self, value):
            import probatio as p
            return p.Schema(bool)(value)

        def serialize(self):
            return {"selector": {"boolean": self.config}}

    selector.SelectSelector = SelectSelector
    selector.TextSelector = TextSelector
    selector.FileSelector = FileSelector
    selector.BooleanSelector = BooleanSelector
    sys.modules["homeassistant.helpers.selector"] = selector

    update_coordinator.UpdateFailed = UpdateFailed
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator


_install_homeassistant_stubs()
