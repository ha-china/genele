# Genelec Smart IP

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/ha-china/genele.svg)](https://github.com/ha-china/genele/releases)
[![License](https://img.shields.io/github/license/ha-china/genele.svg)](LICENSE)

Home Assistant 自定义集成，用于控制 Genelec Smart IP 系列监听音箱。

## 安装

### 通过 HACS 安装（推荐）

1. 打开 HACS
2. 点击 "集成"
3. 点击右上角的 "+" 按钮
4. 搜索 "Genelec Smart IP"
5. 点击 "下载"

### 手动安装

1. 下载此仓库
2. 将 `custom_components/genelec` 文件夹复制到你的 Home Assistant 配置目录下的 `custom_components` 文件夹中
3. 重启 Home Assistant

## 配置

1. 在 Home Assistant 中，进入 "设置" -> "设备与服务"
2. 点击右下角的 "+" 按钮
3. 搜索 "Genelec Smart IP"
4. 按照提示完成配置

## 支持的功能

- 媒体播放器控制（音量、静音、输入源切换）
- 电源状态监控和远程控制
- 设备信息传感器（温度、CPU 负载、运行时间等）
- LED 亮度控制
- 配置文件管理
- Dante/AoIP 设置

## 支持的设备

- Genelec Smart IP 系列监听音箱（需要固件支持 API）

## 服务

### wake_up
唤醒设备

### set_standby
设置设备进入待机模式

### boot_device
启动设备

### set_volume_level
设置音量（dB）

### set_led_intensity
设置 LED 亮度

### restore_profile
恢复保存的配置文件

## 许可证

MIT License
