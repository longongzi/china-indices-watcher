# 📈 China Indices Watcher (cniw)

[![Release](https://img.shields.io/github/v/release/longongzi/china-indices-watcher)](https://github.com/longongzi/china-indices-watcher/releases/latest)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.9-blue)](https://python.org)
[![License](https://img.shields.io/github/license/longongzi/china-indices-watcher)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/longongzi/china-indices-watcher?style=social)](https://github.com/longongzi/china-indices-watcher)

> **Watch A-share market indices directly from your terminal.**
>
> **在终端中实时观测A股市场指数。**

A command-line tool for monitoring China A-share market indices using free public APIs from East Money (东方财富). Built with Python, Click, Rich, and Requests.

---

## Features / 功能

- 📊 **Index Watch** — Real-time display of major indices (上证指数, 深证成指, 创业板指, 上证50, 科创50)
- 🚀 **Top Gainers** — List the biggest gainers in the market
- 🐯 **LongHuBang (龙虎榜)** — View billboard data (dragon-tiger rankings)
- 🔔 **Price Alert** — Get notified when an index crosses a threshold
- 🎨 **Beautiful Terminal Output** — Color-coded tables with Rich (red for up, green for down, Chinese convention)
- 🔄 **Live Refresh** — Auto-refresh at custom intervals
- 🆓 **Free & Open Source** — Uses East Money free APIs, no API key required

## Installation / 安装

### pip install from GitHub (recommended)

```bash
pip install https://github.com/longongzi/china-indices-watcher/releases/latest/download/china_indices_watcher-0.1.0-py3-none-any.whl
```

### Install from source

```bash
git clone https://github.com/longongzi/china-indices-watcher.git
cd china-indices-watcher
pip install .
```

## Quick Start / 快速开始

```bash
# Watch major indices live
cniw watch

# Show top gainers
cniw gainers

# Show 龙虎榜 (dragon-tiger billboard)
cniw lhb

# Set a price alert (trigger when SSE Composite crosses 3200)
cniw alert --index sh000001 --threshold 3200
```

### Batch mode (auto-refresh)

```bash
# Refresh every 10 seconds
cniw watch --interval 10
```

## Usage / 使用说明

```
Usage: cniw [OPTIONS] COMMAND [ARGS]...

  📈 China Indices Watcher (cniw) - A-Share Market CLI Tool

Commands:
  watch     Watch major A-share indices live
  gainers   Show top gainers in the A-share market
  lhb       Show 龙虎榜 (dragon-tiger billboard) data
  alert     Alert when an index crosses a price threshold
```

### Color Convention / 颜色说明

Chinese market convention (inverted from Western):
- 📈 **Red** = price **up** (上涨)
- 📉 **Green** = price **down** (下跌)

## Data Source / 数据来源

All data is fetched from **East Money (东方财富)** public APIs. No authentication or API key required.

## Contributing / 贡献

Contributions are welcome! Feel free to open issues or submit pull requests.

## License / 许可证

MIT
