"""Click-based CLI for china-indices-watcher."""

import time
from typing import Optional

import click

from . import api
from . import display


@click.group()
@click.version_option(version="0.1.0", prog_name="cniw")
def main():
    """📈 China Indices Watcher (cniw) - A-Share Market CLI Tool

    Monitor major A-share indices, top gainers, 龙虎榜 (billboard),
    and set price alerts — all from your terminal.
    """


@main.command()
@click.option(
    "--interval", "-i",
    default=0,
    type=int,
    help="Watch interval in seconds (0=one-shot, default 0)",
)
@click.option(
    "--count", "-c",
    default=10,
    type=int,
    help="Number of refresh cycles (default 10, only with --interval)",
)
def watch(interval: int, count: int):
    """Watch major A-share indices live.

    Displays 上证指数, 深证成指, 创业板指, 上证50, 科创50
    with real-time price, change%, and up/down stock counts.
    """
    if interval <= 0:
        try:
            quotes = api.fetch_index_quotes()
        except RuntimeError as e:
            click.echo(f"❌ Error: {e}", err=True)
            return
        display.display_index_quotes(quotes)
        return

    cycles = 0
    try:
        while cycles < count:
            try:
                quotes = api.fetch_index_quotes()
            except RuntimeError as e:
                click.echo(f"❌ Error: {e}", err=True)
                time.sleep(interval)
                cycles += 1
                continue

            display.console.clear()
            display.display_index_quotes(quotes)
            display.console.print(
                f"\n[dim]Auto-refresh every {interval}s | "
                f"Cycle {cycles + 1}/{count}"
                f" | Ctrl+C to quit[/dim]"
            )
            time.sleep(interval)
            cycles += 1
    except KeyboardInterrupt:
        display.console.print("\n[yellow]👋 Stopped by user[/yellow]")


@main.command()
@click.option("--count", "-n", default=20, type=int, help="Number of gainers to show")
def gainers(count: int):
    """Show top gainers in the A-share market."""
    try:
        data = api.fetch_top_gainers(page_size=count)
    except RuntimeError as e:
        click.echo(f"❌ Error: {e}", err=True)
        return
    if not data:
        click.echo("No data available.", err=True)
        return
    display.display_gainers(data)


@main.command()
@click.option("--count", "-n", default=10, type=int, help="Number of 龙虎榜 items")
def lhb(count: int):
    """Show 龙虎榜 (dragon-tiger billboard) data."""
    try:
        data = api.fetch_longhubang(page_size=count)
    except RuntimeError as e:
        click.echo(f"❌ Error: {e}", err=True)
        return
    if not data:
        click.echo("No data available.", err=True)
        return
    display.display_longhubang(data)


@main.command()
@click.argument("price", type=float)
@click.option(
    "--index", "-i",
    default="上证指数",
    type=click.Choice(api.INDEX_NAMES),
    help="Index to monitor (default: 上证指数)",
)
@click.option(
    "--interval", "-t",
    default=10,
    type=int,
    help="Check interval in seconds (default: 10)",
)
def alert(price: float, index: str, interval: int):
    """Alert when an index crosses a price threshold.

    Continuously monitors and alerts when the index price
    goes above or below the target.
    """
    click.echo(
        f"🔔 Monitoring {index} for price alert at {price:.2f} "
        f"(checking every {interval}s)..."
    )

    try:
        while True:
            try:
                quotes = api.fetch_index_quotes()
            except RuntimeError as e:
                click.echo(f"❌ Error: {e}", err=True)
                time.sleep(interval)
                continue

            current = None
            for q in quotes:
                if q["name"] == index:
                    current = q["price"]
                    break

            if current is None:
                click.echo(f"⚠️ Could not find {index} in fetched data", err=True)
            else:
                crossed_above = current >= price
                crossed_below = current <= price
                if crossed_above or crossed_below:
                    display.display_alert(price, current, index)
                    break

            time.sleep(interval)
    except KeyboardInterrupt:
        display.console.print("\n[yellow]👋 Stopped by user[/yellow]")


if __name__ == "__main__":
    main()
