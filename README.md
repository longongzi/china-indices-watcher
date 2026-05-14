
# 📈 China Indices Watcher (cniw)

[![PyPI](https://img.shields.io/pypi/v/china-indices-watcher)](https://pypi.org/project/china-indices-watcher/)
[![Python Version](https://img.shields.io/pypi/pyversions/china-indices-watcher)](https://pypi.org/project/china-indices-watcher/)
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

```bash
pip install china-indices-watcher
```

Or install from source:

```bash
git clone https://github.com/longongzi/china-indices-watcher.git
cd china-indices-watcher
pip install -e .
```

## Usage / 使用

### Watch Indices / 查看指数

One-shot display of all major indices:

```bash
cniw watch
```

Live refresh every 5 seconds:

```bash
cniw watch --interval 5
```

```
╭──────────────────── A-Share Major Indices / A股主要指数 ────────────────────╮
│ 指数        │ 最新价    │ 涨跌幅    │ 涨跌额    │ ↑上涨 │ ↓下跌 │ 涨跌比 │
├─────────────┼───────────┼───────────┼───────────┼───────┼───────┼────────┤
│ 上证指数    │ 3154.55   │ ↑ +1.01% │ +31.63   │ 1523  │ 677   │ 2.25   │
│ 深证成指    │ 9712.53   │ ↑ +1.10% │ +105.70  │ 1936  │ 796   │ 2.43   │
│ 创业板指    │ 1878.48   │ ↑ +1.12% │ +20.77   │ 753   │ 424   │ 1.78   │
│ 上证50      │ 2487.89   │ ↑ +0.82% │ +20.18   │ 28    │ 17    │ 1.65   │
│ 科创50      │ 768.51    │ ↑ +1.88% │ +14.17   │ 344   │ 225   │ 1.53   │
╰────────────────────────────────────────────────────────────────────────────╯
```

### Top Gainers / 涨幅榜

```bash
cniw gainers --count 20
```

### LongHuBang / 龙虎榜

```bash
cniw lhb --count 10
```

### Price Alert / 价格提醒

Alert when 上证指数 crosses 3200:

```bash
cniw alert 3200
```

Alert on a specific index:

```bash
cniw alert 2500 --index 上证50 --interval 15
```

## Commands Overview / 命令概览

| Command / 命令 | Description / 说明 |
|---------------|-------------------|
| `cniw watch` | Watch major indices (实时指数) |
| `cniw gainers` | Top gainers list (涨幅榜) |
| `cniw lhb` | 龙虎榜 data |
| `cniw alert <price>` | Price alert (价格提醒) |

## API Sources / 数据来源

- **Primary**: [East Money (东方财富)](https://www.eastmoney.com/) free APIs
- **Fallback**: Tencent Finance (腾讯财经) `qt.gtimg.cn` API

No API key or registration required. Data is for reference only.

## Development / 开发

```bash
# Install dev dependencies
pip install -e .

# Run tests
python -m pytest
```

## License / 许可证

[MIT](LICENSE) © 2026 longongzi

---

<div align="center">
  <sub>Built with ❤️ for the Chinese investment community | 为中国投资者社区倾心打造</sub>
</div>
