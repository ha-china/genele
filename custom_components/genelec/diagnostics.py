"""Diagnostics support for Genelec Smart IP."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_PASSWORD, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # Redact sensitive data
    redacted_data = entry.data.copy()
    if CONF_PASSWORD in redacted_data:
        redacted_data[CONF_PASSWORD] = "******"

    diagnostics_data = {
        "entry": redacted_data,
        "devices": [],
    }

    # Get device info from data
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    for platform_name, platform_data in entry_data.items():
        if isinstance(platform_data, list):
            for entity in platform_data:
                if hasattr(entity, "_device") and hasattr(entity._device, "_device_info"):
                    device_info = entity._device._device_info
                    diagnostics_data["devices"].append({
                        "model": device_info.get("model"),
                        "fw_id": device_info.get("fwId"),
                        "api_ver": device_info.get("apiVer"),
                        "category": device_info.get("category"),
                        "hw_id": device_info.get("hwId"),
                    })

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    return await async_get_config_entry_diagnostics(hass, config_entry)
