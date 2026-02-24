"""Genelec Smart IP Device API Client."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import aiohttp
from aiohttp import ClientSession, ClientResponseError

from .const import (
    API_BASE,
    ATTR_API_VER,
    ATTR_BARCODE,
    ATTR_BASS_LEVEL,
    ATTR_CPU_LOAD,
    ATTR_CPU_TEMP,
    ATTR_CATEGORY,
    ATTR_FW_ID,
    ATTR_HW_ID,
    ATTR_INPUT_LEVEL,
    ATTR_MAC,
    ATTR_MODEL,
    ATTR_NETWORK_TRAFFIC,
    ATTR_TWEETER_LEVEL,
    ATTR_UPTIME,
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    DEFAULT_API_VERSION,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    ENDPOINT_AUDIO_INPUTS,
    ENDPOINT_AUDIO_VOLUME,
    ENDPOINT_AOIP_DANTE_IDENTITY,
    ENDPOINT_AOIP_IPV4,
    ENDPOINT_DEVICE_ID,
    ENDPOINT_DEVICE_INFO,
    ENDPOINT_DEVICE_LED,
    ENDPOINT_DEVICE_PWR,
    ENDPOINT_EVENTS,
    ENDPOINT_NETWORK_IPV4,
    ENDPOINT_NETWORK_ZONE,
    ENDPOINT_PROFILE_LIST,
    ENDPOINT_PROFILE_RESTORE,
    LOGGER,
    POWER_STATE_ACTIVE,
    POWER_STATE_AOIPBOOT,
    POWER_STATE_BOOT,
    POWER_STATE_ISS_SLEEP,
    POWER_STATE_PWR_FAIL,
    POWER_STATE_STANDBY,
)

_LOGGER = logging.getLogger(__name__)


class GenelecSmartIPDevice:
    """Representation of a Genelec Smart IP device."""

    def __init__(
        self,
        host: str,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        port: int = DEFAULT_PORT,
        api_version: str = DEFAULT_API_VERSION,
        session: ClientSession | None = None,
        lock: asyncio.Lock | None = None,
    ) -> None:
        """Initialize the device."""
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._api_version = api_version
        self._session = session  # Use shared session
        self._lock = lock or asyncio.Lock()  # Lock to ensure only one request at a time
        self._base_url = f"http://{host}:{port}{API_BASE.format(version=api_version)}"
        self._auth_header = self._create_auth_header()
        self._device_info: dict[str, Any] = {}
        self._device_id: dict[str, Any] = {}

    def _create_auth_header(self) -> str:
        """Create Basic Auth header."""
        credentials = f"{self._username}:{self._password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def _request(
        self, method: str, endpoint: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a request to the device API."""
        url = f"{self._base_url}{endpoint}"
        headers = {
            "Accept": "application/json",
            "Authorization": self._auth_header,
        }

        if data is not None:
            headers["Content-Type"] = "application/json"

        _LOGGER.debug("%s %s (session: %s)", method, url, 
                      "shared" if self._session else "temporary")

        # Use lock to ensure only one request at a time
        async with self._lock:
            # Must use shared session - never create temporary sessions
            if self._session is None:
                raise RuntimeError("Shared session not initialized")
            
            session = self._session
            
            async with session.request(
                method, url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(
                    total=10)
            ) as response:
                if response.status == 503:
                    _LOGGER.warning("Device busy (503): %s", url)
                    raise ClientResponseError(
                        response.request_info,
                        response.history,
                        status=503,
                        message="Device busy - too many connections",
                    )
                
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error("Request failed %d: %s",
                                  response.status, error_text)
                    raise ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=error_text,
                    )
                text = await response.text()
                if not text:
                    return {}
                return json.loads(text)

    async def get_device_info(self) -> dict[str, Any]:
        """Get device information."""
        data = await self._request("GET", ENDPOINT_DEVICE_INFO)
        self._device_info = data
        return data

    async def get_device_id(self) -> dict[str, Any]:
        """Get device ID information."""
        data = await self._request("GET", ENDPOINT_DEVICE_ID)
        self._device_id = data
        return data

    async def get_power_state(self) -> dict[str, Any]:
        """Get power state."""
        return await self._request("GET", ENDPOINT_DEVICE_PWR)

    async def set_power_state(self, state: str) -> dict[str, Any]:
        """Set power state."""
        return await self._request("PUT", ENDPOINT_DEVICE_PWR, {"state": state})

    async def wake_up(self) -> dict[str, Any]:
        """Wake up the device."""
        return await self.set_power_state(POWER_STATE_ACTIVE)

    async def set_standby(self) -> dict[str, Any]:
        """Put device in standby."""
        return await self.set_power_state(POWER_STATE_STANDBY)

    async def boot_device(self) -> dict[str, Any]:
        """Boot the device."""
        return await self.set_power_state(POWER_STATE_BOOT)

    async def get_volume(self) -> dict[str, Any]:
        """Get volume level and mute state."""
        return await self._request("GET", ENDPOINT_AUDIO_VOLUME)

    async def set_volume(self, level: float | None = None,
                         mute: bool | None = None) -> dict[str, Any]:
        """Set volume level and/or mute state."""
        # Don't get current volume first to reduce requests - send only what's needed
        data: dict[str, Any] = {}
        if level is not None:
            data["level"] = level
        if mute is not None:
            data["mute"] = mute

        if not data:
            return {}

        return await self._request("PUT", ENDPOINT_AUDIO_VOLUME, data)

    async def get_inputs(self) -> dict[str, Any]:
        """Get selected audio inputs."""
        return await self._request("GET", ENDPOINT_AUDIO_INPUTS)

    async def set_inputs(self, inputs: list[str]) -> dict[str, Any]:
        """Set audio inputs."""
        return await self._request("PUT", ENDPOINT_AUDIO_INPUTS, {"input": inputs})

    async def get_led_settings(self) -> dict[str, Any]:
        """Get LED settings."""
        return await self._request("GET", ENDPOINT_DEVICE_LED)

    async def set_led_settings(
        self,
        led_intensity: int | None = None,
        rj45_leds: bool | None = None,
        hide_clip: bool | None = None,
    ) -> dict[str, Any]:
        """Set LED settings."""
        data: dict[str, Any] = {}
        if led_intensity is not None:
            data["ledIntensity"] = led_intensity
        if rj45_leds is not None:
            data["rj45Leds"] = rj45_leds
        if hide_clip is not None:
            data["hideClip"] = hide_clip
        
        if not data:
            return {}
            
        return await self._request("PUT", ENDPOINT_DEVICE_LED, data)

    async def get_events(self) -> dict[str, Any]:
        """Get device events and measurements."""
        return await self._request("GET", ENDPOINT_EVENTS)

    async def get_zone_info(self) -> dict[str, Any]:
        """Get zone information."""
        return await self._request("GET", ENDPOINT_NETWORK_ZONE)

    async def get_profile_list(self) -> dict[str, Any]:
        """Get list of profiles."""
        return await self._request("GET", ENDPOINT_PROFILE_LIST)

    async def restore_profile(self, profile_id: int,
                              startup: bool = False) -> dict[str, Any]:
        """Restore a profile."""
        return await self._request(
            "PUT", ENDPOINT_PROFILE_RESTORE, {"id": profile_id, "startup": startup}
        )

    async def get_network_config(self) -> dict[str, Any]:
        """Get network configuration."""
        return await self._request("GET", ENDPOINT_NETWORK_IPV4)

    async def get_aoip_identity(self) -> dict[str, Any]:
        """Get AoIP Dante identity."""
        return await self._request("GET", ENDPOINT_AOIP_DANTE_IDENTITY)

    async def get_aoip_ipv4(self) -> dict[str, Any]:
        """Get AoIP IPv4 settings."""
        return await self._request("GET", ENDPOINT_AOIP_IPV4)

    async def test_connection(self) -> bool:
        """Test connection to the device."""
        try:
            await self.get_device_info()
            return True
        except Exception:
            return False

    @property
    def name(self) -> str:
        """Return device name."""
        model = self._device_info.get(ATTR_MODEL, "Unknown")
        return f"Genelec {model}"

    @property
    def mac_address(self) -> str | None:
        """Return MAC address."""
        return self._device_id.get(ATTR_MAC)

    @property
    def model(self) -> str | None:
        """Return device model."""
        return self._device_info.get(ATTR_MODEL)

    @property
    def unique_id(self) -> str:
        """Return unique ID for the device."""
        # Use MAC address if available, otherwise use host IP
        mac = self.mac_address
        if mac:
            return f"genelec_{mac.replace(':', '_')}"
        # Fallback to host IP for consistency before MAC is fetched
        return f"genelec_{self._host.replace('.', '_')}"


def create_device_from_config_entry(
    config: dict[str, Any],
    session: aiohttp.ClientSession | None = None,
    lock: asyncio.Lock | None = None,
) -> GenelecSmartIPDevice:
    """Create a device instance from config entry data."""
    return GenelecSmartIPDevice(
        host=config[CONF_HOST],
        username=config.get(CONF_USERNAME, DEFAULT_USERNAME),
        password=config.get(CONF_PASSWORD, DEFAULT_PASSWORD),
        port=config.get(CONF_PORT, DEFAULT_PORT),
        api_version=config.get(CONF_API_VERSION, DEFAULT_API_VERSION),
        session=session,
        lock=lock,
    )
