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
        "device": {},
        "coordinator": {},
    }

    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is None:
        return diagnostics_data

    device_info = getattr(entry_data, "device_info", {}) or {}
    device_id = getattr(entry_data, "device_id", {}) or {}
    diagnostics_data["device"] = {
        "model": device_info.get("model"),
        "fw_id": device_info.get("fwId"),
        "api_ver": device_info.get("apiVer"),
        "category": device_info.get("category"),
        "hw_id": device_info.get("hwId"),
        "mac": device_id.get("mac"),
        "barcode": device_id.get("barcode"),
    }

    coordinator_data = getattr(entry_data, "coordinator", None)
    coordinator_payload = getattr(coordinator_data, "data", {}) if coordinator_data else {}
    diagnostics_data["coordinator"] = {
        "volume": coordinator_payload.get("volume", {}),
        "power": coordinator_payload.get("power", {}),
        "inputs": coordinator_payload.get("inputs", {}),
        "events": coordinator_payload.get("events", {}),
        "network_ipv4": coordinator_payload.get("network_ipv4", {}),
        "aoip_ipv4": coordinator_payload.get("aoip_ipv4", {}),
        "aoip_identity": coordinator_payload.get("aoip_identity", {}),
        "zone_info": coordinator_payload.get("zone_info", {}),
        "profile_list": coordinator_payload.get("profile_list", {}),
    }

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    return await async_get_config_entry_diagnostics(hass, config_entry)
