"""Sensor platform for Genelec Smart IP integration."""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_BARCODE,
    ATTR_BASS_LEVEL,
    ATTR_CPU_LOAD,
    ATTR_CPU_TEMP,
    ATTR_FW_ID,
    ATTR_HW_ID,
    ATTR_INPUT_LEVEL,
    ATTR_MAC,
    ATTR_MODEL,
    ATTR_NETWORK_TRAFFIC,
    ATTR_TWEETER_LEVEL,
    ATTR_UPTIME,
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    SENSOR_KEYS_AOIP_IDENTITY,
    SENSOR_KEYS_AOIP_IPV4,
    SENSOR_KEYS_EVENTS,
    SENSOR_KEYS_NETWORK_IPV4,
    SENSOR_KEYS_PROFILE,
    SENSOR_KEYS_ZONE,
)
from .device import GenelecSmartIPDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Genelec Smart IP sensor entities."""
    # Get shared data from hass.data
    data = hass.data[DOMAIN].get(entry.entry_id)
    coordinator = data.coordinator if data else None

    # Use shared device instance
    device = data.device if data and data.device else None
    if not device:
        LOGGER.error("Shared device instance not found")
        return

    # Get device info from shared data
    device_info = data.device_info if data else {}
    device_id = data.device_id if data else {}

    # Get all other data from coordinator for initialization
    network_config = data.network_config if data else {}
    aoip_ipv4 = data.aoip_ipv4 if data else {}
    aoip_identity = data.aoip_identity if data else {}
    zone_info = data.zone_info if data else {}
    profile_list = data.profile_list if data else {}

    LOGGER.debug("Initial data - network_config: %s, aoip_ipv4: %s, aoip_identity: %s, zone_info: %s, profile_list: %s",
                 network_config, aoip_ipv4, aoip_identity, zone_info, profile_list)

    # Create sensors
    entities = [
        GenelecCPUTemperatureSensor(device, device_info, coordinator),
        GenelecCPULoadSensor(device, device_info, coordinator),
        GenelecUptimeSensor(device, device_info, coordinator),
        GenelecNetworkTrafficSensor(device, device_info, coordinator),
        GenelecBassLevelSensor(device, device_info, coordinator),
        GenelecTweeterLevelSensor(device, device_info, coordinator),
        GenelecInputLevelSensor(device, device_info, coordinator),
        GenelecFWSensor(device, device_info, coordinator),
        GenelecModelSensor(device, device_info, coordinator),
        GenelecMACSensor(device, device_info, coordinator, device_id),
        GenelecBarcodeSensor(device, device_info, coordinator, device_id),
        GenelecHWIDSensor(device, device_info, coordinator, device_id),
        GenelecHostIPSensor(device, device_info, coordinator),
        GenelecReceiverIPSensor(device, device_info, coordinator, aoip_ipv4),
        GenelecDanteNameSensor(device, device_info, coordinator, aoip_identity),
        GenelecDanteFriendlyNameSensor(device, device_info, coordinator, aoip_identity),
        GenelecHostnameSensor(device, device_info, coordinator, network_config),
        GenelecZoneNameSensor(device, device_info, coordinator, zone_info),
        GenelecZoneIDSensor(device, device_info, coordinator, zone_info),
        GenelecCurrentProfileSensor(device, device_info, coordinator, profile_list),
        GenelecStartupProfileSensor(device, device_info, coordinator, profile_list),
    ]

    async_add_entities(entities)


class GenelecBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Genelec sensors."""

    # All sensors are enabled by default and not in diagnostic category
    _attr_entity_registry_enabled_default = True
    _attr_entity_category = None

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device = device
        self._device_info = device_info
        self._coordinator = coordinator
        self._attr_unique_id = f"{device.unique_id}_{self._name_suffix}"
        self._attr_name = self._name_suffix
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.unique_id)},
            "name": device.name,
            "manufacturer": "Genelec",
            "model": device_info.get("model", "Unknown"),
            "sw_version": device_info.get("fwId", "Unknown"),
        }
        self._attr_has_entity_name = False  # Use custom name

        # Initialize value from coordinator data if available
        if coordinator and coordinator.data:
            self._init_from_coordinator_data(coordinator.data)

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize sensor value from coordinator data. Override in subclasses."""
        pass

    @property
    def should_poll(self) -> bool:
        """Return False as this entity is updated by the coordinator."""
        return not bool(self._coordinator)

    @property
    def _name_suffix(self) -> str:
        """Return the name suffix for this sensor."""
        raise NotImplementedError

    @property
    def _events_key(self) -> str | None:
        """Return the key in events data for this sensor."""
        return None

    @property
    def _coordinator_key(self) -> str | None:
        """Return the key in coordinator data for this sensor (non-events data)."""
        return None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._coordinator and self._coordinator.data:
            # Check for events key (for events-based sensors)
            events_key = self._events_key
            if events_key:
                events_data = self._coordinator.data.get("events", {})
                self._attr_native_value = events_data.get(events_key)
                _LOGGER.debug("Sensor %s: events_key=%s, value=%s", 
                              self._name_suffix, events_key, self._attr_native_value)
                self.async_write_ha_state()


class GenelecCPUTemperatureSensor(GenelecBaseSensor):
    """Sensor for CPU temperature."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "cpu_temperature"
    _attr_icon = "mdi:thermometer"

    @property
    def _name_suffix(self) -> str:
        return "cpu_temperature"

    @property
    def _events_key(self) -> str:
        return "cpuT"

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        events_data = data.get("events", {})
        self._attr_native_value = events_data.get("cpuT")


class GenelecCPULoadSensor(GenelecBaseSensor):
    """Sensor for CPU load."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "cpu_load"
    _attr_icon = "mdi:cpu-64-bit"

    @property
    def _name_suffix(self) -> str:
        return "cpu_load"

    @property
    def _events_key(self) -> str:
        return "cpuLoad"

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        events_data = data.get("events", {})
        self._attr_native_value = events_data.get("cpuLoad")


class GenelecUptimeSensor(GenelecBaseSensor):
    """Sensor for device uptime."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "uptime"
    _attr_icon = "mdi:clock-outline"

    @property
    def _name_suffix(self) -> str:
        return "uptime"

    @property
    def _events_key(self) -> str:
        return "uptime"

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        events_data = data.get("events", {})
        self._attr_native_value = events_data.get("uptime")


class GenelecNetworkTrafficSensor(GenelecBaseSensor):
    """Sensor for network traffic."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_native_unit_of_measurement = "kbps"
    _attr_translation_key = "network_traffic"
    _attr_icon = "mdi:network"

    @property
    def _name_suffix(self) -> str:
        return "network_traffic"

    @property
    def _events_key(self) -> str:
        return "nwInKbps"

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        events_data = data.get("events", {})
        self._attr_native_value = events_data.get("nwInKbps")


class GenelecBassLevelSensor(GenelecBaseSensor):
    """Sensor for bass output level."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_native_unit_of_measurement = "dB"
    _attr_translation_key = "bass_level"
    _attr_icon = "mdi:waveform"

    @property
    def _name_suffix(self) -> str:
        return "bass_level"

    @property
    def _events_key(self) -> str:
        return "bsLevel"

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        events_data = data.get("events", {})
        self._attr_native_value = events_data.get("bsLevel")


class GenelecTweeterLevelSensor(GenelecBaseSensor):
    """Sensor for tweeter output level."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_native_unit_of_measurement = "dB"
    _attr_translation_key = "tweeter_level"
    _attr_icon = "mdi:waveform"

    @property
    def _name_suffix(self) -> str:
        return "tweeter_level"

    @property
    def _events_key(self) -> str:
        return "twLevel"

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        events_data = data.get("events", {})
        self._attr_native_value = events_data.get("twLevel")


class GenelecInputLevelSensor(GenelecBaseSensor):
    """Sensor for input level."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_native_unit_of_measurement = "dB"
    _attr_translation_key = "input_level"
    _attr_icon = "mdi:audio-input"

    @property
    def _name_suffix(self) -> str:
        return "input_level"

    @property
    def _events_key(self) -> str:
        return "inLevel"

    def _init_from_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initialize from coordinator data."""
        events_data = data.get("events", {})
        self._attr_native_value = events_data.get("inLevel")


class GenelecFWSensor(GenelecBaseSensor):
    """Sensor for firmware version."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "firmware_version"
    _attr_icon = "mdi:chip"

    @property
    def _name_suffix(self) -> str:
        return "firmware_version"

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        self._attr_native_value = device_info.get(ATTR_FW_ID)
        _LOGGER.debug("Firmware version sensor value: %s (device_info: %s)",
                      self._attr_native_value, device_info)

    def _handle_coordinator_update(self) -> None:
        """Firmware version doesn't change, no update needed."""
        pass


class GenelecModelSensor(GenelecBaseSensor):
    """Sensor for device model."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "model"
    _attr_icon = "mdi:speaker"

    @property
    def _name_suffix(self) -> str:
        return "model"

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        self._attr_native_value = device_info.get(ATTR_MODEL)

    def _handle_coordinator_update(self) -> None:
        """Model doesn't change, no update needed."""
        pass


class GenelecMACSensor(GenelecBaseSensor):
    """Sensor for MAC address."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "mac_address"
    _attr_icon = "mdi:lan"

    @property
    def _name_suffix(self) -> str:
        return "mac_address"

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None, device_id: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # MAC address is in device_id
        if device_id:
            self._attr_native_value = device_id.get(ATTR_MAC)

    def _handle_coordinator_update(self) -> None:
        """MAC address doesn't change, no update needed."""
        pass


class GenelecBarcodeSensor(GenelecBaseSensor):
    """Sensor for device barcode."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "barcode"
    _attr_icon = "mdi:barcode"

    @property
    def _name_suffix(self) -> str:
        return "barcode"

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None, device_id: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Barcode is in device_id
        if device_id:
            self._attr_native_value = device_id.get(ATTR_BARCODE)

    def _handle_coordinator_update(self) -> None:
        """Barcode doesn't change, no update needed."""
        pass


class GenelecHWIDSensor(GenelecBaseSensor):
    """Sensor for hardware ID."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "hardware_id"
    _attr_icon = "mdi:identifier"

    @property
    def _name_suffix(self) -> str:
        return "hardware_id"

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None, device_id: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Hardware ID is in device_id, show N/A if empty
        hw_id = device_id.get(ATTR_HW_ID) if device_id else None
        self._attr_native_value = hw_id if hw_id else "N/A"
        _LOGGER.debug("Hardware ID sensor value: %s", self._attr_native_value)

    def _handle_coordinator_update(self) -> None:
        """Hardware ID doesn't change, no update needed."""
        pass


class GenelecHostIPSensor(GenelecBaseSensor):
    """Sensor for device host IP (control IP)."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "host_ip"
    _attr_icon = "mdi:server-network"

    @property
    def _name_suffix(self) -> str:
        return "host_ip"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_NETWORK_IPV4

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Host IP is the configured IP
        self._attr_native_value = device._host

    def _handle_coordinator_update(self) -> None:
        """Host IP is static, no update needed."""
        pass


class GenelecReceiverIPSensor(GenelecBaseSensor):
    """Sensor for AoIP receiver IP (audio stream IP)."""

    _attr_entity_registry_enabled_default = True
    _attr_entity_category = None
    _attr_translation_key = "receiver_ip"
    _attr_icon = "mdi:ethernet"

    @property
    def _name_suffix(self) -> str:
        return "receiver_ip"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_AOIP_IPV4

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None,
                 initial_data: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Initialize with initial data if available, otherwise N/A
        if initial_data and "ip" in initial_data:
            self._attr_native_value = initial_data.get("ip")
            _LOGGER.debug("Receiver IP sensor initialized with: %s", self._attr_native_value)
        else:
            self._attr_native_value = "N/A"

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator data."""
        if self._coordinator and self._coordinator.data:
            aoip_ipv4 = self._coordinator.data.get(SENSOR_KEYS_AOIP_IPV4, {})
            _LOGGER.debug("AoIP IPv4 data: %s", aoip_ipv4)
            # Only set value if data is available (device has AoIP module)
            if aoip_ipv4 and "ip" in aoip_ipv4:
                self._attr_native_value = aoip_ipv4.get("ip")
            else:
                self._attr_native_value = "N/A"
            self.async_write_ha_state()


class GenelecDanteNameSensor(GenelecBaseSensor):
    """Sensor for Dante name."""

    _attr_entity_registry_enabled_default = True
    _attr_entity_category = None
    _attr_translation_key = "dante_name"
    _attr_icon = "mdi:headphones-audio"

    @property
    def _name_suffix(self) -> str:
        return "dante_name"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_AOIP_IDENTITY

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None,
                 initial_data: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Initialize with initial data if available, otherwise N/A
        if initial_data and "name" in initial_data:
            self._attr_native_value = initial_data.get("name")
            _LOGGER.debug("Dante name sensor initialized with: %s", self._attr_native_value)
        else:
            self._attr_native_value = "N/A"

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator data."""
        if self._coordinator and self._coordinator.data:
            aoip_identity = self._coordinator.data.get(SENSOR_KEYS_AOIP_IDENTITY, {})
            _LOGGER.debug("AoIP identity data for Dante name: %s", aoip_identity)
            # Only set value if data is available (device has Dante module)
            if aoip_identity and "name" in aoip_identity:
                dante_name = aoip_identity.get("name")
                self._attr_native_value = dante_name
                _LOGGER.debug("Dante name sensor value: %s", dante_name)
            else:
                self._attr_native_value = "N/A"
            self.async_write_ha_state()


class GenelecDanteFriendlyNameSensor(GenelecBaseSensor):
    """Sensor for Dante friendly name."""

    _attr_entity_registry_enabled_default = True
    _attr_entity_category = None
    _attr_translation_key = "dante_friendly_name"
    _attr_icon = "mdi:tag"

    @property
    def _name_suffix(self) -> str:
        return "dante_friendly_name"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_AOIP_IDENTITY

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None,
                 initial_data: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Initialize with initial data if available, otherwise N/A
        if initial_data and "fname" in initial_data:
            self._attr_native_value = initial_data.get("fname")
            _LOGGER.debug("Dante friendly name sensor initialized with: %s", self._attr_native_value)
        else:
            self._attr_native_value = "N/A"

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator data."""
        if self._coordinator and self._coordinator.data:
            aoip_identity = self._coordinator.data.get(SENSOR_KEYS_AOIP_IDENTITY, {})
            _LOGGER.debug(
                "AoIP identity data for Dante friendly name: %s", aoip_identity)
            # Only set value if data is available (device has Dante module)
            if aoip_identity and "fname" in aoip_identity:
                dante_fname = aoip_identity.get("fname")
                self._attr_native_value = dante_fname
                _LOGGER.debug("Dante friendly name sensor value: %s", dante_fname)
            else:
                self._attr_native_value = "N/A"
            self.async_write_ha_state()


class GenelecHostnameSensor(GenelecBaseSensor):
    """Sensor for device hostname."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "hostname"
    _attr_icon = "mdi:lan"

    @property
    def _name_suffix(self) -> str:
        return "hostname"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_NETWORK_IPV4

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None,
                 initial_data: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Initialize with initial data if available
        if initial_data and "hostname" in initial_data:
            self._attr_native_value = initial_data.get("hostname")
            _LOGGER.debug("Hostname sensor initialized with: %s", self._attr_native_value)
        else:
            self._attr_native_value = None

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator data."""
        if self._coordinator and self._coordinator.data:
            network_config = self._coordinator.data.get(SENSOR_KEYS_NETWORK_IPV4, {})
            _LOGGER.debug("Network config data for hostname: %s", network_config)
            # Only set value if data is available
            if network_config and "hostname" in network_config:
                hostname = network_config.get("hostname")
                self._attr_native_value = hostname
                _LOGGER.debug("Hostname sensor value: %s", hostname)
            else:
                self._attr_native_value = None
            self.async_write_ha_state()


class GenelecZoneNameSensor(GenelecBaseSensor):
    """Sensor for zone name."""

    _attr_entity_registry_enabled_default = True
    _attr_entity_category = None
    _attr_translation_key = "zone_name"
    _attr_icon = "mdi:map-marker"

    @property
    def _name_suffix(self) -> str:
        return "zone_name"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_ZONE

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None,
                 initial_data: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Initialize with initial data if available, show N/A if not configured
        zone_name = initial_data.get("name", "") if initial_data else ""
        self._attr_native_value = zone_name if zone_name else "N/A"
        _LOGGER.debug("Zone name sensor initialized with: %s", self._attr_native_value)

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator data."""
        if self._coordinator and self._coordinator.data:
            zone_info = self._coordinator.data.get(SENSOR_KEYS_ZONE, {})
            _LOGGER.debug("Zone info data for zone name: %s", zone_info)
            zone_name = zone_info.get("name", "") if zone_info else ""
            self._attr_native_value = zone_name if zone_name else "N/A"
            self.async_write_ha_state()


class GenelecZoneIDSensor(GenelecBaseSensor):
    """Sensor for zone ID."""

    _attr_entity_registry_enabled_default = True
    _attr_entity_category = None
    _attr_translation_key = "zone_id"
    _attr_icon = "mdi:identifier"

    @property
    def _name_suffix(self) -> str:
        return "zone_id"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_ZONE

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None,
                 initial_data: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Initialize with initial data if available, show N/A if zone is 0 (not configured)
        zone_id = initial_data.get("zone") if initial_data else None
        self._attr_native_value = zone_id if zone_id else "N/A"
        _LOGGER.debug("Zone ID sensor initialized with: %s", self._attr_native_value)

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator data."""
        if self._coordinator and self._coordinator.data:
            zone_info = self._coordinator.data.get(SENSOR_KEYS_ZONE, {})
            _LOGGER.debug("Zone info data: %s", zone_info)
            zone_id = zone_info.get("zone") if zone_info else None
            self._attr_native_value = zone_id if zone_id else "N/A"
            _LOGGER.debug("Zone ID sensor value: %s", self._attr_native_value)
            self.async_write_ha_state()


class GenelecCurrentProfileSensor(GenelecBaseSensor):
    """Sensor for current profile ID."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "current_profile"
    _attr_icon = "mdi:playlist-play"

    @property
    def _name_suffix(self) -> str:
        return "current_profile"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_PROFILE

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None,
                 initial_data: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Initialize with initial data if available
        if initial_data and "selected" in initial_data:
            self._attr_native_value = initial_data.get("selected")
            _LOGGER.debug("Current profile sensor initialized with: %s", self._attr_native_value)
        else:
            self._attr_native_value = None

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator data."""
        if self._coordinator and self._coordinator.data:
            profile_list = self._coordinator.data.get(SENSOR_KEYS_PROFILE, {})
            _LOGGER.debug("Profile list data for current profile: %s", profile_list)
            # Only set value if data is available
            if profile_list and "selected" in profile_list:
                current_profile = profile_list.get("selected")
                self._attr_native_value = current_profile
                _LOGGER.debug("Current profile sensor value: %s", current_profile)
            else:
                self._attr_native_value = None
            self.async_write_ha_state()


class GenelecStartupProfileSensor(GenelecBaseSensor):
    """Sensor for startup profile ID."""

    # Entity is enabled by default
    _attr_entity_registry_enabled_default = True

    _attr_translation_key = "startup_profile"
    _attr_icon = "mdi:restart"

    @property
    def _name_suffix(self) -> str:
        return "startup_profile"

    @property
    def _coordinator_key(self) -> str:
        """Return the key in coordinator data for this sensor."""
        return SENSOR_KEYS_PROFILE

    def __init__(self, device: GenelecSmartIPDevice,
                 device_info: dict[str, Any], coordinator: DataUpdateCoordinator | None = None,
                 initial_data: dict[str, Any] | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(device, device_info, coordinator)
        # Initialize with initial data if available
        if initial_data and "startup" in initial_data:
            self._attr_native_value = initial_data.get("startup")
            _LOGGER.debug("Startup profile sensor initialized with: %s", self._attr_native_value)
        else:
            self._attr_native_value = None

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator data."""
        if self._coordinator and self._coordinator.data:
            profile_list = self._coordinator.data.get(SENSOR_KEYS_PROFILE, {})
            _LOGGER.debug("Profile list data for startup profile: %s", profile_list)
            # Only set value if data is available
            if profile_list and "startup" in profile_list:
                startup_profile = profile_list.get("startup")
                self._attr_native_value = startup_profile
                _LOGGER.debug("Startup profile sensor value: %s", startup_profile)
            else:
                self._attr_native_value = None
            self.async_write_ha_state()
