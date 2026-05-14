"""East Money (东方财富) API client for A-share market data.

Uses multiple free data sources:
  - Tencent Finance (qt.gtimg.cn) for index quotes
  - East Money datacenter for 龙虎榜
  - East Money push2 for index quotes & gainers (when accessible)
"""

from typing import Any

import requests

# ── Index mappings ─────────────────────────────────────────────
# Tencent codes: sh=上海, sz=深圳
TENCENT_INDEX_CODES = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
    "上证50":   "sh000016",
    "科创50":   "sh000688",
}

# East Money sec IDs
EM_INDEX_SECIDS = {
    "上证指数": "1.000001",
    "深证成指": "0.399001",
    "创业板指": "0.399006",
    "上证50":   "1.000016",
    "科创50":   "1.000688",
}

INDEX_NAMES = list(TENCENT_INDEX_CODES.keys())

# ── API endpoints ──────────────────────────────────────────────
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
EASTMONEY_CLIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_LHB_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="

TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://quote.eastmoney.com/",
}


def _get(url: str, params: dict | None = None) -> requests.Response:
    """Make a GET request with browser-like headers."""
    return requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)


# ── Index Quotes ───────────────────────────────────────────────

def fetch_index_quotes() -> list[dict[str, Any]]:
    """Fetch major A-share index quotes.

    Primary: East Money push2 API.
    Fallback: Tencent Finance API.

    Returns a list of dicts with keys:
        code, name, price, change_pct, change_amount, up_stocks, down_stocks
    """
    try:
        return _fetch_em_quotes()
    except Exception:
        try:
            return _fetch_tencent_quotes()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to fetch index quotes (both East Money and Tencent failed): {exc}"
            ) from exc


def _fetch_em_quotes() -> list[dict[str, Any]]:
    """Fetch index quotes from East Money push2 API."""
    secids = ",".join(EM_INDEX_SECIDS.values())
    params = {
        "secids": secids,
        "fields": "f2,f3,f4,f12,f14,f169,f170",
        "fltt": "2",
    }
    resp = _get(EASTMONEY_QUOTE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    raw_list = (data.get("data") or {}).get("diff", [])
    if not raw_list:
        raise RuntimeError("Empty response from East Money index API")

    items = []
    for item in raw_list:
        code = item.get("f12", "")
        items.append({
            "code": code,
            "name": item.get("f14", ""),
            "price": item.get("f2", 0.0),
            "change_pct": item.get("f3", 0.0),
            "change_amount": item.get("f4", 0.0),
            "up_stocks": _parse_f169(item.get("f169"), 0),
            "down_stocks": _parse_f169(item.get("f169"), 1),
            "source": "eastmoney",
        })
    return items


def _parse_f169(val: Any, idx: int) -> int:
    """Parse f169 field (up/down stock counts)."""
    if isinstance(val, list) and len(val) > idx:
        return val[idx]
    return 0


def _fetch_tencent_quotes() -> list[dict[str, Any]]:
    """Fetch index quotes from Tencent Finance API."""
    codes = ",".join(TENCENT_INDEX_CODES.values())
    url = TENCENT_QUOTE_URL + codes
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    items = []
    for line in resp.text.strip().split(";\n"):
        line = line.strip()
        if not line:
            continue
        # Parse: v_sh000001="...~...~..."
        eq_idx = line.find("=")
        if eq_idx == -1:
            continue
        raw = line[eq_idx + 1:]
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        parts = raw.split("~")
        if len(parts) < 40:
            continue

        code_raw = parts[0]  # e.g. "1" for SH, "51" for SZ
        name = parts[1]
        code = parts[2]
        price = _safe_float(parts[3])
        change_pct = _safe_float(parts[32])  # 涨跌幅
        change_amount = _safe_float(parts[31])  # 涨跌额

        items.append({
            "code": code,
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "change_amount": change_amount,
            "up_stocks": 0,
            "down_stocks": 0,
            "source": "tencent",
        })
    return items


def _safe_float(val: str) -> float:
    """Convert string to float, returning 0.0 on failure."""
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0


# ── Top Gainers ────────────────────────────────────────────────

def fetch_top_gainers(page_size: int = 20) -> list[dict[str, Any]]:
    """Fetch top gainers from East Money.

    Returns a list of dicts with keys:
        code, name, price, change_pct, change_amount, turnover_pct
    """
    params = {
        "pn": "1",
        "pz": str(page_size),
        "po": "1",
        "fields": "f2,f3,f4,f12,f14,f9",
        "fid": "f3",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "fltt": "2",
    }
    try:
        resp = _get(EASTMONEY_CLIST_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch top gainers: {exc}") from exc

    raw_list = (data.get("data") or {}).get("diff", [])
    items = []
    for item in raw_list:
        items.append({
            "code": item.get("f12", ""),
            "name": item.get("f14", ""),
            "price": item.get("f2", 0.0),
            "change_pct": item.get("f3", 0.0),
            "change_amount": item.get("f4", 0.0),
            "turnover_pct": item.get("f9", 0.0),
        })
    return items


# ── 龙虎榜 (Dragon-Tiger Billboard) ───────────────────────────

def fetch_longhubang(page_size: int = 10) -> list[dict[str, Any]]:
    """Fetch 龙虎榜 (billboard/dragon-tiger) data from East Money datacenter.

    Returns a list of dicts with keys:
        code, name, trade_date, close_price, change_pct,
        net_buy, total_buy, total_sell, reason
    """
    params = {
        "reportName": "RPT_DAILYBILLBOARD_PROFILE",
        "columns": "ALL",
        "pageSize": str(page_size),
        "sortTypes": "-1",
        "sortColumns": "TRADE_DATE",
        "source": "WEB",
        "client": "WEBB",
    }
    try:
        resp = _get(EASTMONEY_LHB_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch 龙虎榜 data: {exc}") from exc

    raw_list = (data.get("result") or {}).get("data", [])
    items = []
    for item in raw_list:
        items.append({
            "code": item.get("SECURITY_CODE", ""),
            "name": item.get("SECURITY_NAME_ABBR", ""),
            "trade_date": item.get("TRADE_DATE", ""),
            "close_price": item.get("CLOSE_PRICE", 0.0),
            "change_pct": item.get("CHANGE_RATE", 0.0),
            "net_buy": item.get("NET_BUY_AMOUNT", 0.0),
            "total_buy": item.get("BUY_AMOUNT", 0.0),
            "total_sell": item.get("SELL_AMOUNT", 0.0),
            "reason": item.get("BILLBOARD_REASON", ""),
        })
    return items


# ── Single stock quote (Tencent fallback) ─────────────────────

def fetch_tencent_quote(code: str) -> dict[str, Any]:
    """Fetch a single stock quote from Tencent.

    Args:
        code: e.g. "sh600519" or "sz000001"

    Returns dict with code, name, price, change_pct, change_amount.
    """
    url = TENCENT_QUOTE_URL + code
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        parts = text.split("~")
        if len(parts) < 32:
            raise ValueError(f"Unexpected Tencent response format: {text[:100]}")
        return {
            "code": code,
            "name": parts[1],
            "price": _safe_float(parts[3]),
            "change_pct": _safe_float(parts[32]),
            "change_amount": _safe_float(parts[31]),
        }
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch Tencent quote for {code}: {exc}") from exc
