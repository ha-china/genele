"""Select platform for Genelec Smart IP integration."""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    LOGGER,
    POWER_STATE_ACTIVE,
    POWER_STATE_AOIPBOOT,
    POWER_STATE_BOOT,
    POWER_STATE_ISS_SLEEP,
    POWER_STATE_PWR_FAIL,
    POWER_STATE_STANDBY,
)
from .device import GenelecSmartIPDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Genelec Smart IP select entities."""
    # Get shared data from hass.data
    data = hass.data[DOMAIN].get(entry.entry_id)
    coordinator = data.coordinator if data else None

    # Use shared device instance
    device = data.device if data and data.device else None
    if not device:
        _LOGGER.error("Shared device instance not found")
        return

    # Get device info from shared data
    device_info = data.device_info if data else {}

    entities = [
        GenelecPowerStateSelect(device, device_info, coordinator),
    ]

    async_add_entities(entities)


class GenelecPowerStateSelect(CoordinatorEntity, SelectEntity):
    """Select entity for power state."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_options = [
        POWER_STATE_ACTIVE,
        POWER_STATE_STANDBY,
        POWER_STATE_BOOT,
        POWER_STATE_AOIPBOOT,
    ]
    _attr_translation_key = "power_state"
    _attr_icon = "mdi:power"

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._device = device
        self._device_info = device_info
        self._coordinator = coordinator
        self._attr_name = "Power State"
        self._attr_unique_id = f"{device.unique_id}_power_state"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.unique_id)},
            "name": device.name,
            "manufacturer": "Genelec",
            "model": device_info.get("model", "Unknown"),
            "sw_version": device_info.get("fwId", "Unknown"),
        }
        self._attr_has_entity_name = True
        self._current_option: str | None = POWER_STATE_ACTIVE

        # Initialize from coordinator data if available
        if coordinator and coordinator.data:
            self._init_from_coordinator_data(coordinator.data)

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        power_data = data.get("power", {})
        state = power_data.get("state", POWER_STATE_ACTIVE)
        if state in self._attr_options:
            self._current_option = state

    @property
    def should_poll(self) -> bool:
        """Return False as this entity is updated by the coordinator."""
        return not bool(self._coordinator)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._coordinator and self._coordinator.data:
            power_data = self._coordinator.data.get("power", {})
            state = power_data.get("state", POWER_STATE_ACTIVE)

            if state in self._attr_options:
                self._current_option = state
            else:
                self._current_option = None
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the select entity (fallback when no coordinator)."""
        if self._coordinator:
            return
        try:
            power_data = await self._device.get_power_state()
            state = power_data.get("state", POWER_STATE_ACTIVE)

            if state in self._attr_options:
                self._current_option = state
            else:
                self._current_option = None
        except Exception as e:
            _LOGGER.error("Error updating power state: %s", e)
            self._current_option = None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._device.set_power_state(option)
        self._current_option = option
        self.async_write_ha_state()
        # Immediately refresh coordinator data after control
        if self._coordinator:
            await self._coordinator.async_request_refresh()

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        return self._current_option
