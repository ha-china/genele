# Genelec Smart IP

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/ha-china/genele.svg)](https://github.com/ha-china/genele/releases)
[![License](https://img.shields.io/github/license/ha-china/genele.svg)](LICENSE)

A custom integration for Home Assistant to control Genelec Smart IP series studio monitors.

## Installation

### Via HACS (Recommended)

1. Open HACS
2. Go to "Integrations"
3. Click the "+" button in the top right corner
4. Search for "Genelec Smart IP"
5. Click "Download"

### Manual Installation

1. Download this repository
2. Copy the `custom_components/genelec` folder to your Home Assistant configuration directory under `custom_components`
3. Restart Home Assistant

## Configuration

1. In Home Assistant, go to "Settings" -> "Devices & Services"
2. Click the "+" button in the bottom right corner
3. Search for "Genelec Smart IP"
4. Follow the setup instructions

## Features

- Media player control (volume, mute, input source switching)
- Power state monitoring and remote control
- Device information sensors (temperature, CPU load, uptime, etc.)
- LED brightness control
- Profile management
- Dante/AoIP settings

## Supported Devices

- Genelec Smart IP series studio monitors (requires firmware with API support)

## Services

### wake_up
Wake up the device from standby/sleep mode.

### set_standby
Put the device in standby mode.

### boot_device
Boot the device.

### set_volume_level
Set volume level in dB.

### set_led_intensity
Set the front panel LED intensity.

### restore_profile
Restore a saved profile from device memory.

## License

MIT License