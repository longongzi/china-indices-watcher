"""Terminal display utilities using rich for beautiful table output."""

from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


def color_for_change(val: float | None) -> str:
    """Return rich color/style string for a change percentage."""
    if val is None:
        return "white"
    if val > 0:
        return "red"  # Chinese convention: red = up
    if val < 0:
        return "green"  # Chinese convention: green = down
    return "white"


def arrow_for_change(val: float | None) -> str:
    """Return arrow indicator for change."""
    if val is None:
        return "→"
    if val > 0:
        return "↑"
    if val < 0:
        return "↓"
    return "→"


def display_index_quotes(quotes: list[dict[str, Any]]) -> None:
    """Display index quotes in a rich table."""
    table = Table(
        title="📊 A-Share Major Indices / A股主要指数",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold yellow",
    )
    table.add_column("指数", style="bold", no_wrap=True)
    table.add_column("最新价", justify="right")
    table.add_column("涨跌幅", justify="right")
    table.add_column("涨跌额", justify="right")
    table.add_column("↑上涨", justify="right")
    table.add_column("↓下跌", justify="right")
    table.add_column("涨跌比", justify="right")

    for q in quotes:
        pct = q.get("change_pct")
        amt = q.get("change_amount")
        color = color_for_change(pct)
        arrow = arrow_for_change(pct)

        pct_str = f"{arrow} {pct:+.2f}%" if pct is not None else "N/A"
        amt_str = f"{amt:+.2f}" if amt is not None else "N/A"

        table.add_row(
            q.get("name", ""),
            f"{q.get('price', 0):.2f}",
            Text(pct_str, style=color),
            Text(amt_str, style=color),
            str(q.get("up_stocks", 0)),
            str(q.get("down_stocks", 0)),
            f"{q.get('ratio_up_down', 0):.2f}",
        )

    console.print(table)


def display_gainers(gainers: list[dict[str, Any]]) -> None:
    """Display top gainers in a rich table."""
    table = Table(
        title="🚀 Top Gainers / 涨幅榜",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold yellow",
    )
    table.add_column("#", style="dim", no_wrap=True)
    table.add_column("代码", no_wrap=True)
    table.add_column("名称", style="bold")
    table.add_column("最新价", justify="right")
    table.add_column("涨跌幅", justify="right")
    table.add_column("涨跌额", justify="right")
    table.add_column("换手率%", justify="right")

    for i, g in enumerate(gainers, 1):
        pct = g.get("change_pct")
        color = color_for_change(pct)
        arrow = arrow_for_change(pct)
        pct_str = f"{arrow} {pct:+.2f}%" if pct is not None else "N/A"

        table.add_row(
            str(i),
            g.get("code", ""),
            g.get("name", ""),
            f"{g.get('price', 0):.2f}",
            Text(pct_str, style=color),
            Text(f"{g.get('change_amount', 0):+.2f}", style=color),
            f"{g.get('turnover_pct', 0):.2f}" if g.get("turnover_pct") else "N/A",
        )

    console.print(table)


def display_longhubang(items: list[dict[str, Any]]) -> None:
    """Display 龙虎榜 data in a rich table."""
    table = Table(
        title="🐯 LongHuBang / 龙虎榜",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold yellow",
    )
    table.add_column("代码", no_wrap=True)
    table.add_column("名称", style="bold")
    table.add_column("日期")
    table.add_column("收盘价", justify="right")
    table.add_column("涨跌幅", justify="right")
    table.add_column("净买入(万)", justify="right")
    table.add_column("总买入(万)", justify="right")
    table.add_column("总卖出(万)", justify="right")
    table.add_column("上榜理由")

    for item in items:
        pct = item.get("change_pct")
        color = color_for_change(pct)
        arrow = arrow_for_change(pct)
        pct_str = f"{arrow} {pct:+.2f}%" if pct is not None else "N/A"

        def yuan_to_wan(val: float) -> str:
            """Convert yuan to 万元."""
            if val is None or val == 0:
                return "0.00"
            return f"{val / 10000:.2f}"

        table.add_row(
            item.get("code", ""),
            item.get("name", ""),
            str(item.get("trade_date", "")),
            f"{item.get('close_price', 0):.2f}",
            Text(pct_str, style=color),
            yuan_to_wan(item.get("net_buy", 0)),
            yuan_to_wan(item.get("total_buy", 0)),
            yuan_to_wan(item.get("total_sell", 0)),
            item.get("reason", ""),
        )

    console.print(table)


def display_alert(price: float, current: float, name: str) -> None:
    """Display an alert notification."""
    diff = current - price
    direction = "📈突破" if diff > 0 else "📉跌破"
    color = "red" if diff > 0 else "green"
    text = Text()
    text.append(f"\n🔔 价格提醒 | Price Alert\n", style="bold yellow")
    text.append(f"  指数: {name}\n", style="bold")
    text.append(f"  目标价: {price:.2f}\n")
    text.append(f"  现价: {current:.2f}\n")
    text.append(f"{direction} {abs(diff):.2f} 点\n", style=color)
    console.print(text)
