"""Media Player platform for Genelec Smart IP integration."""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

if TYPE_CHECKING:
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    INPUT_AOIP_01,
    INPUT_AOIP_02,
    INPUT_ANALOG,
    INPUT_API_TO_DISPLAY,
    INPUT_DISPLAY_TO_API,
    INPUT_MIX,
    INPUT_NONE,
    LOGGER,
    POWER_STATE_ACTIVE,
    POWER_STATE_STANDBY,
)
from .device import GenelecSmartIPDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Genelec Smart IP media player entities."""
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

    async_add_entities([GenelecSmartIPMediaPlayer(device, device_info, coordinator)])


class GenelecSmartIPMediaPlayer(MediaPlayerEntity):
    """Representation of a Genelec Smart IP speaker."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )
    _attr_volume_level = 1.0
    _attr_media_title = None
    _attr_media_artist = None
    _attr_media_album_name = None
    _attr_media_image_url = None
    _attr_media_content_id = None
    _attr_media_content_type = None

    def __init__(self, device: GenelecSmartIPDevice, device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None) -> None:
        """Initialize the media player."""
        self._device = device
        self._device_info = device_info
        self._coordinator = coordinator
        self._attr_name = "Speaker"
        self._attr_unique_id = device.unique_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.unique_id)},
            "name": device.name,
            "manufacturer": "Genelec",
            "model": device_info.get("model", "Unknown"),
            "sw_version": device_info.get("fwId", "Unknown"),
        }
        self._volume = -5.0
        self._is_muted = False
        self._power_state = POWER_STATE_ACTIVE
        self._current_source = INPUT_ANALOG
        self._current_sources: list[str] = []  # Track all selected sources
        self._source_list = [
            INPUT_NONE,
            INPUT_ANALOG,
            INPUT_AOIP_01,
            INPUT_AOIP_02,
            INPUT_MIX,
        ]

        # Initialize from coordinator data if available
        if coordinator and coordinator.data:
            self._init_from_coordinator_data(coordinator.data)

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        volume_data = data.get("volume", {})
        power_data = data.get("power", {})
        inputs_data = data.get("inputs", {})

        if volume_data:
            self._volume = volume_data.get("level", -5.0)
            self._is_muted = volume_data.get("mute", False)
        
        if power_data:
            self._power_state = power_data.get("state", POWER_STATE_ACTIVE)
        
        inputs = inputs_data.get("input", [])
        self._current_sources = inputs
        self._current_source = self._sources_to_display(inputs)

        self._attr_state = (
            MediaPlayerState.ON
            if self._power_state == POWER_STATE_ACTIVE
            else MediaPlayerState.OFF
        )

    def _sources_to_display(self, api_sources: list[str]) -> str:
        """Convert API source list to display name."""
        if not api_sources:
            return INPUT_NONE
        if len(api_sources) > 1:
            return INPUT_MIX
        return INPUT_API_TO_DISPLAY.get(api_sources[0], api_sources[0])

    async def async_update(self) -> None:
        """Update the media player state."""
        if self._coordinator:
            # Use coordinator data
            coordinator_data = self._coordinator.data
            volume_data = coordinator_data.get("volume", {})
            power_data = coordinator_data.get("power", {})
            inputs_data = coordinator_data.get("inputs", {})

            self._volume = volume_data.get("level", -5.0)
            self._is_muted = volume_data.get("mute", False)
            self._power_state = power_data.get("state", POWER_STATE_STANDBY)

            inputs = inputs_data.get("input", [])
            self._current_sources = inputs
            self._current_source = self._sources_to_display(inputs)

            self._attr_state = (
                MediaPlayerState.ON
                if self._power_state == POWER_STATE_ACTIVE
                else MediaPlayerState.OFF
            )
        else:
            # Fallback to direct requests
            try:
                volume_data = await self._device.get_volume()
                self._volume = volume_data.get("level", -5.0)
                self._is_muted = volume_data.get("mute", False)

                power_data = await self._device.get_power_state()
                self._power_state = power_data.get("state", POWER_STATE_STANDBY)

                inputs_data = await self._device.get_inputs()
                inputs = inputs_data.get("input", [])
                self._current_sources = inputs
                self._current_source = self._sources_to_display(inputs)

                self._attr_state = (
                    MediaPlayerState.ON
                    if self._power_state == POWER_STATE_ACTIVE
                    else MediaPlayerState.OFF
                )
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.error("Error updating media player: %s", e)

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        return self._source_list

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return (self._volume + 130) / 130

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self._is_muted

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source == INPUT_NONE:
            # No input - empty array
            api_sources = []
        elif source == INPUT_MIX:
            # Mix - select all inputs
            api_sources = list(INPUT_DISPLAY_TO_API.values())
        else:
            # Single source
            api_source = INPUT_DISPLAY_TO_API.get(source, source)
            api_sources = [api_source]
        
        await self._device.set_inputs(api_sources)
        self._current_sources = api_sources
        self._current_source = source
        self.async_write_ha_state()
        # Immediately refresh coordinator data after control
        if self._coordinator:
            await self._coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute media player."""
        await self._device.set_volume(mute=mute)
        self._is_muted = mute
        self.async_write_ha_state()
        # Immediately refresh coordinator data after control
        if self._coordinator:
            await self._coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        level = (volume * 130) - 130
        await self._device.set_volume(level=level)
        self._volume = level
        self.async_write_ha_state()
        # Immediately refresh coordinator data after control
        if self._coordinator:
            await self._coordinator.async_request_refresh()

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        new_level = min(0, self._volume + 1.0)
        await self._device.set_volume(level=new_level)
        self._volume = new_level
        self.async_write_ha_state()
        # Immediately refresh coordinator data after control
        if self._coordinator:
            await self._coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        new_level = max(-130, self._volume - 1.0)
        await self._device.set_volume(level=new_level)
        self._volume = new_level
        self.async_write_ha_state()
        # Immediately refresh coordinator data after control
        if self._coordinator:
            await self._coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._device.wake_up()
        self._power_state = POWER_STATE_ACTIVE
        self.async_write_ha_state()
        # Immediately refresh coordinator data after control
        if self._coordinator:
            await self._coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._device.set_standby()
        self._power_state = POWER_STATE_STANDBY
        self.async_write_ha_state()
        # Immediately refresh coordinator data after control
        if self._coordinator:
            await self._coordinator.async_request_refresh()
