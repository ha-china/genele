"""The Genelec Smart IP integration."""
from __future__ import annotations

import asyncio
import aiohttp
from datetime import timedelta
from typing import TYPE_CHECKING
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_API_VERSION,
    DEFAULT_API_VERSION,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

if TYPE_CHECKING:
    from .device import GenelecSmartIPDevice

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(
                    CONF_USERNAME, default=DEFAULT_USERNAME
                ): cv.string,
                vol.Optional(
                    CONF_PASSWORD, default=DEFAULT_PASSWORD
                ): cv.string,
                vol.Optional(
                    CONF_API_VERSION, default=DEFAULT_API_VERSION
                ): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class GenelecSmartIPData:
    """Class to hold Genelec Smart IP data."""

    def __init__(self) -> None:
        """Initialize the data."""
        self.session: aiohttp.ClientSession | None = None
        self.coordinator: DataUpdateCoordinator | None = None
        self.device: GenelecSmartIPDevice | None = None  # Shared device instance
        self.volume_data: dict = {}
        self.power_data: dict = {}
        self.inputs_data: dict = {}
        self.events_data: dict = {}
        self.device_info: dict = {}
        self.device_id: dict = {}
        self.led_data: dict = {}
        self.led_initialized: bool = False  # Track if LED endpoint exists
        self.network_config: dict = {}
        self.aoip_ipv4: dict = {}
        self.aoip_identity: dict = {}
        self.zone_info: dict = {}
        self.profile_list: dict = {}
        self.lock = asyncio.Lock()  # Lock to ensure only one request at a time


type GenelecSmartIPConfigEntry = ConfigEntry[GenelecSmartIPData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Genelec Smart IP component."""
    hass.data.setdefault(DOMAIN, {})
    LOGGER.info("Genelec Smart IP component loaded")
    return True


async def async_setup_entry(hass: HomeAssistant,
                            entry: GenelecSmartIPConfigEntry) -> bool:
    """Set up Genelec Smart IP from a config entry."""
    LOGGER.info("Setting up Genelec Smart IP integration")

    hass.data.setdefault(DOMAIN, {})

    # Create a shared aiohttp session for this integration entry
    # Device supports max 4 connections, but we only need 1
    # Keep connections alive for reuse to avoid reconnect overhead
    connector = aiohttp.TCPConnector(
        limit=1,
        limit_per_host=1,
        force_close=False,  # Keep connections alive for reuse
        enable_cleanup_closed=True,
        ttl_dns_cache=300,  # Cache DNS for 5 minutes
    )
    timeout = aiohttp.ClientTimeout(total=10)
    session = aiohttp.ClientSession(connector=connector, timeout=timeout)

    # Store session in data
    data = GenelecSmartIPData()
    data.session = session
    hass.data[DOMAIN][entry.entry_id] = data

    # Create device instance with shared lock
    from .device import create_device_from_config_entry
    device = create_device_from_config_entry(
        entry.data, session=session, lock=data.lock
    )
    data.device = device  # Store shared device instance

    # Fetch device_id early to ensure consistent unique_id
    try:
        device_id_data = await device.get_device_id()
        data.device_id = device_id_data
        device._device_id = device_id_data  # Update device's cached device_id
    except Exception as e:
        LOGGER.warning("Failed to get device_id during setup: %s", e)

    # Fetch device_info early
    try:
        device_info_data = await device.get_device_info()
        data.device_info = device_info_data
        device._device_info = device_info_data
    except Exception as e:
        LOGGER.warning("Failed to get device_info during setup: %s", e)

    # Create coordinator for centralized updates
    async def async_update_data():
        """Fetch data from device."""
        try:
            # Fetch all data in sequence to avoid overwhelming the device
            volume_data = await device.get_volume()
            power_data = await device.get_power_state()
            inputs_data = await device.get_inputs()
            events_data = await device.get_events()

            # Update cached data
            data.volume_data = volume_data
            data.power_data = power_data
            data.inputs_data = inputs_data
            data.events_data = events_data

            # Only fetch these once (they don't change often)
            # These endpoints are required and should work on all devices
            if not data.device_info:
                try:
                    data.device_info = await device.get_device_info()
                    LOGGER.debug("Device info: %s", data.device_info)
                except Exception as e:
                    LOGGER.warning("Failed to get device info: %s", e)
            if not data.device_id:
                try:
                    data.device_id = await device.get_device_id()
                    LOGGER.debug("Device ID: %s", data.device_id)
                except Exception as e:
                    LOGGER.debug("Failed to get device ID: %s", e)
            
            # Fetch LED settings once to check if endpoint exists
            if not data.led_initialized:
                try:
                    data.led_data = await device.get_led_settings()
                    data.led_initialized = True
                    LOGGER.debug("LED data: %s", data.led_data)
                except Exception as e:
                    LOGGER.debug("LED settings not available: %s", e)
                    data.led_initialized = True  # Mark as checked, even if failed

            # These endpoints may not exist on all device models
            # 404 errors are expected for devices without these features
            if not data.network_config:
                try:
                    data.network_config = await device.get_network_config()
                    LOGGER.debug("Network config: %s", data.network_config)
                except Exception as e:
                    # 404 is expected for devices without network config endpoint
                    LOGGER.debug("Network config not available: %s", e)
                    data.network_config = {}  # Set empty dict to prevent repeated attempts
            if not data.aoip_ipv4:
                try:
                    data.aoip_ipv4 = await device.get_aoip_ipv4()
                    LOGGER.debug("AoIP IPv4: %s", data.aoip_ipv4)
                except Exception as e:
                    # 404 is expected for devices without AoIP/Dante module
                    LOGGER.debug("AoIP IPv4 not available (device may not have Dante): %s", e)
                    data.aoip_ipv4 = {}  # Set empty dict to prevent repeated attempts
            if not data.aoip_identity:
                try:
                    data.aoip_identity = await device.get_aoip_identity()
                    LOGGER.debug("AoIP identity: %s", data.aoip_identity)
                except Exception as e:
                    # 404 is expected for devices without AoIP/Dante module
                    LOGGER.debug("AoIP identity not available (device may not have Dante): %s", e)
                    data.aoip_identity = {}  # Set empty dict to prevent repeated attempts
            if not data.zone_info:
                try:
                    data.zone_info = await device.get_zone_info()
                    LOGGER.debug("Zone info: %s", data.zone_info)
                except Exception as e:
                    LOGGER.debug("Zone info not available: %s", e)
                    data.zone_info = {}  # Set empty dict to prevent repeated attempts
            if not data.profile_list:
                try:
                    data.profile_list = await device.get_profile_list()
                    LOGGER.debug("Profile list: %s", data.profile_list)
                except Exception as e:
                    LOGGER.debug("Profile list not available: %s", e)
                    data.profile_list = {}  # Set empty dict to prevent repeated attempts

            return {
                "volume": volume_data,
                "power": power_data,
                "inputs": inputs_data,
                "events": events_data,
                "device_info": data.device_info,
                "device_id": data.device_id,
                "led": data.led_data,
                "network_ipv4": data.network_config,
                "aoip_ipv4": data.aoip_ipv4,
                "aoip_identity": data.aoip_identity,
                "zone_info": data.zone_info,
                "profile_list": data.profile_list,
            }
        except Exception as e:
            LOGGER.error("Error updating coordinator data: %s", e)
            # Return last known data if available
            return {
                "volume": data.volume_data,
                "power": data.power_data,
                "inputs": data.inputs_data,
                "events": data.events_data,
                "device_info": data.device_info,
                "device_id": data.device_id,
                "led": data.led_data,
                "network_ipv4": data.network_config,
                "aoip_ipv4": data.aoip_ipv4,
                "aoip_identity": data.aoip_identity,
                "zone_info": data.zone_info,
                "profile_list": data.profile_list,
            }

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    data.coordinator = coordinator
    await coordinator.async_config_entry_first_refresh()

    async def handle_wake_up(call):
        """Handle wake up service."""
        entity_ids = call.data.get("entity_id", [])
        for entity_id in entity_ids:
            entity = hass.states.get(entity_id)
            if entity:
                service_call = hass.services.async_call(
                    "media_player",
                    "turn_on",
                    {"entity_id": entity_id}
                )
                await service_call

    async def handle_set_standby(call):
        """Handle set standby service."""
        entity_ids = call.data.get("entity_id", [])
        for entity_id in entity_ids:
            service_call = hass.services.async_call(
                "media_player",
                "turn_off",
                {"entity_id": entity_id}
            )
            await service_call

    async def handle_boot_device(call):
        """Handle boot device service."""
        entity_ids = call.data.get("entity_id", [])
        for entity_id in entity_ids:
            service_call = hass.services.async_call(
                "media_player",
                "turn_on",
                {"entity_id": entity_id}
            )
            await service_call

    async def handle_set_volume_level(call):
        """Handle set volume level service."""
        entity_ids = call.data.get("entity_id", [])
        level = call.data.get("level")
        if level is None:
            return
        volume_percent = (level + 130) / 130
        for entity_id in entity_ids:
            service_call = hass.services.async_call(
                "media_player",
                "volume_set",
                {"entity_id": entity_id, "volume_level": volume_percent}
            )
            await service_call

    async def handle_set_led_intensity(call):
        """Handle set LED intensity service."""
        entity_ids = call.data.get("entity_id", [])
        intensity = call.data.get("intensity")
        if intensity is None:
            return

        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state:
                for platform in PLATFORMS:
                    for entry in hass.config_entries.async_entries(DOMAIN):
                        entities = hass.data[DOMAIN].get(
                            entry.entry_id, {}).get(platform, [])
                        for entity in entities:
                            if entity.entity_id == entity_id and hasattr(
                                    entity, '_device'):
                                await entity._device.set_led_settings(led_intensity=intensity)
                                break

    async def handle_restore_profile(call):
        """Handle restore profile service."""
        profile_id = call.data.get("profile_id")
        startup = call.data.get("startup", False)
        if profile_id is None:
            return

        entity_ids = call.data.get("entity_id", [])
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state:
                for platform in PLATFORMS:
                    for entry in hass.config_entries.async_entries(DOMAIN):
                        entities = hass.data[DOMAIN].get(
                            entry.entry_id, {}).get(platform, [])
                        for entity in entities:
                            if entity.entity_id == entity_id and hasattr(
                                    entity, '_device'):
                                await entity._device.restore_profile(profile_id, startup)
                                break

    hass.services.async_register(DOMAIN, "wake_up", handle_wake_up)
    hass.services.async_register(DOMAIN, "set_standby", handle_set_standby)
    hass.services.async_register(DOMAIN, "boot_device", handle_boot_device)
    hass.services.async_register(DOMAIN, "set_volume_level", handle_set_volume_level)
    hass.services.async_register(DOMAIN, "set_led_intensity", handle_set_led_intensity)
    hass.services.async_register(DOMAIN, "restore_profile", handle_restore_profile)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant,
                             entry: GenelecSmartIPConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.info("Unloading Genelec Smart IP integration")

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data and hasattr(data, 'session') and data.session:
            await data.session.close()

    return True


async def async_reload_entry(hass: HomeAssistant,
                             entry: GenelecSmartIPConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
