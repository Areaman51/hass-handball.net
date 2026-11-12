from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN
from ..device_helpers import via_device_fields

class HandballBaseSensor(CoordinatorEntity):
    """Base class for all handball sensors"""
    
    def __init__(self, coordinator, entry, entity_id, category=None):
        super().__init__(coordinator)
        self._entity_id = entity_id
        self._category = category
        self._attr_config_entry_id = entry.entry_id
        
        # Set entity_category for better grouping
        if category:
            self._attr_entity_category = category

    async def async_added_to_hass(self):
        """Publish explicit logo changes without polling the external API."""
        await super().async_added_to_hass()
        if not getattr(self, "_supports_central_logos", False):
            return
        from ..logo_manager import get_logo_manager

        manager = get_logo_manager(self.coordinator.hass)
        if manager is not None:
            self.async_on_remove(manager.async_listen(self.async_write_ha_state))
        else:
            from ..logo_manager import async_listen_logo_changes

            self.async_on_remove(async_listen_logo_changes(self.coordinator.hass, self.async_write_ha_state))

    @property
    def central_logo_attributes(self):
        """Expose a copy of the shared registry without changing API data."""
        from ..logo_manager import get_logo_manager

        manager = get_logo_manager(self.coordinator.hass)
        if manager is None:
            return {"handballnet_logo_overrides": {}, "handballnet_logo_revision": 0}
        return manager.as_attributes()

    def _create_device_info(self, identifiers, name, model, via_device=None):
        """Create device info dictionary"""
        device_info = {
            "identifiers": identifiers,
            "name": name,
            "manufacturer": "handball.net",
            "model": model,
            "entry_type": "service"
        }

        if via_device is not None:
            device_info.update(
                via_device_fields(self._attr_config_entry_id, via_device)
            )

        return device_info

    def update_device_name(self, new_name: str) -> None:
        """Update device name - to be overridden if needed"""
        pass
