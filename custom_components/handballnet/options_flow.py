"""Native HA 2026.11 options: intervals and the shared logo registry."""
from __future__ import annotations

from collections import deque

import probatio as p
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL_LIVE,
    DEFAULT_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_LIVE,
    DOMAIN,
)
from .logo_manager import (
    LogoStorageError, LogoValidationError, async_get_logo_manager, normalize_team_name,
)


class HandballNetOptionsFlowHandler(config_entries.OptionsFlow):
    """Logo changes are global and do not change config-entry options or reload."""

    def __init__(self, config_entry):
        super().__init__()
        self._team_name: str | None = None

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["intervals", "logos"])

    async def async_step_intervals(self, user_input=None):
        errors = {}
        if user_input is not None:
            values = {}
            for key in (CONF_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL_LIVE):
                value = user_input.get(key)
                if type(value) is not int or value < 1:
                    errors["base"] = "invalid_interval"
                    break
                values[key] = value
            if not errors:
                return self.async_create_entry(title="", data={**self.config_entry.options, **values})
        fields = {}
        for key, default in (
            (CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            (CONF_UPDATE_INTERVAL_LIVE, DEFAULT_UPDATE_INTERVAL_LIVE),
        ):
            fields[p.Optional(key, default=self.config_entry.options.get(
                key, self.config_entry.data.get(key, default)
            ))] = p.All(int, p.Range(min=1))
        return self.async_show_form(step_id="intervals", data_schema=p.Schema(fields), errors=errors)

    def _known_team_names(self, manager) -> list[str]:
        """Use coordinator facts from every entry, not entry titles or API images."""
        names: dict[str, str] = {}

        def add(name):
            try:
                key = normalize_team_name(name)
            except LogoValidationError:
                return
            names.setdefault(key, name.strip())

        stack = deque(getattr(getattr(entry, "runtime_data", None), "data", None)
                      for entry in self.hass.config_entries.async_entries(DOMAIN))
        seen = set()
        while stack:
            data = stack.popleft()
            if not isinstance(data, (dict, list)) or id(data) in seen:
                continue
            seen.add(id(data))
            if isinstance(data, list):
                stack.extend(data)
                continue
            for key in ("team_name", "configured_team_name"):
                if key in data:
                    add(data[key])
            for key in ("homeTeam", "awayTeam", "home_team", "away_team", "opponent", "team_info"):
                if isinstance(team := data.get(key), dict):
                    add(team.get("name"))
            stack.extend(data.values())
        for name in manager.as_attributes()["handballnet_logo_overrides"]:
            add(name)
        return sorted(names.values(), key=normalize_team_name)

    async def async_step_logos(self, user_input=None):
        errors = {}
        try:
            manager = await async_get_logo_manager(self.hass)
        except LogoStorageError:
            return self.async_abort(reason="storage_error")
        if user_input is not None:
            try:
                self._team_name = normalize_team_name(user_input.get("team_name"))
                return await self.async_step_logo_action()
            except LogoValidationError as err:
                errors["team_name"] = err.code
        return self.async_show_form(
            step_id="logos", errors=errors,
            data_schema=p.Schema({p.Required("team_name"): selector.SelectSelector({
                "options": self._known_team_names(manager), "custom_value": True,
                "mode": "dropdown",
            })}),
        )

    async def async_step_logo_action(self, user_input=None):
        if self._team_name is None:
            return await self.async_step_logos()
        return self.async_show_menu(
            step_id="logo_action", menu_options=["logo_url", "logo_upload", "logo_restore"],
            description_placeholders={"team_name": self._team_name},
        )

    async def async_step_logo_url(self, user_input=None):
        if self._team_name is None:
            return await self.async_step_logos()
        errors = {}
        current = ""
        try:
            manager = await async_get_logo_manager(self.hass)
            current = manager.as_attributes()["handballnet_logo_overrides"].get(self._team_name, "")
            if user_input is not None:
                await manager.async_set_url(self._team_name, user_input.get("url"), retry=True)
                return self.async_abort(reason="logo_saved")
        except LogoValidationError as err:
            errors["url"] = err.code
        except LogoStorageError:
            errors["base"] = "storage_error"
        return self.async_show_form(
            step_id="logo_url", errors=errors,
            description_placeholders={"team_name": self._team_name},
            data_schema=p.Schema({p.Required("url", default=current): selector.TextSelector()}),
        )

    async def async_step_logo_upload(self, user_input=None):
        if self._team_name is None:
            return await self.async_step_logos()
        errors = {}
        if user_input is not None:
            try:
                manager = await async_get_logo_manager(self.hass)
                await manager.async_set_upload(self._team_name, user_input.get("file_id"), retry=True)
                return self.async_abort(reason="logo_saved")
            except LogoValidationError as err:
                errors["file_id"] = err.code
            except LogoStorageError:
                errors["base"] = "storage_error"
        return self.async_show_form(
            step_id="logo_upload", errors=errors,
            description_placeholders={"team_name": self._team_name},
            data_schema=p.Schema({p.Required("file_id"): selector.FileSelector({
                "accept": "image/png,image/jpeg,image/webp",
            })}),
        )

    async def async_step_logo_restore(self, user_input=None):
        if self._team_name is None:
            return await self.async_step_logos()
        errors = {}
        if user_input is not None:
            if user_input.get("confirm") is not True:
                errors["confirm"] = "confirmation_required"
            else:
                try:
                    manager = await async_get_logo_manager(self.hass)
                    await manager.async_remove(self._team_name)
                    return self.async_abort(reason="logo_restored")
                except LogoStorageError:
                    errors["base"] = "storage_error"
        return self.async_show_form(
            step_id="logo_restore", errors=errors,
            description_placeholders={"team_name": self._team_name},
            data_schema=p.Schema({p.Required("confirm", default=False): selector.BooleanSelector()}),
        )


@callback
def async_get_options_flow(config_entry):
    return HandballNetOptionsFlowHandler(config_entry)
