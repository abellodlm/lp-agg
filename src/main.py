"""
LP Aggregation RFQ System - Main Application Entry Point

This application:
1. Accepts operator input for quote requests (terminal)
2. Pings multiple LPs asynchronously
3. Selects best quote and applies markup
4. Streams live quote updates showing price improvements
5. Displays LP leaderboard in Tkinter monitor (Mario Kart style)
"""

import asyncio
from typing import List, Optional
from colorama import Fore, Style

from .config.settings import settings
from .core.models import QuoteRequest, AggregatedQuote, LPQuote
from .core.lp_aggregator import LPAggregator
from .core.quote_streamer import QuoteStreamer
from .lps.base_lp import LiquidityProvider
from .lps.mock_lp import MockLP
from .ui.terminal import TerminalInterface
from .ui.monitor import get_monitor


def create_mock_lps() -> List[LiquidityProvider]:
    """
    Create mock LP instances for testing.

    In production, replace with real LP integrations.
    """
    lps = []

    for i in range(settings.mock_lp_count):
        # Vary prices slightly for each LP
        price_offset = i * 100  # LP1: 100000, LP2: 100100, LP3: 100200

        lp = MockLP(
            name=f"MockLP-{i+1}",
            base_price=settings.mock_base_price + price_offset,
            spread_bps=settings.mock_spread_bps,
            response_delay=(settings.mock_min_delay, settings.mock_max_delay),
            failure_rate=settings.mock_failure_rate
        )
        lps.append(lp)

    return lps


async def handle_quote_stream(
    request: QuoteRequest,
    aggregator: LPAggregator,
    streamer: QuoteStreamer,
    monitor
):
    """
    Stream quotes for a given request and update monitor.

    Args:
        request: Quote request from operator
        aggregator: LP aggregator instance
        streamer: Quote streamer instance
        monitor: Monitor GUI instance
    """
    # Track previous locked LP to detect lock changes
    previous_locked_lp = None

    # Callback for quote updates
    def on_quote_update(all_lp_quotes: List[LPQuote], best_quote: AggregatedQuote, poll_count: int, is_improvement: bool, locked_lp_name: Optional[str]):
        nonlocal previous_locked_lp

        # Update monitor with all LP data
        monitor.update_display(all_lp_quotes, best_quote, poll_count, locked_lp_name)

        # Terminal feedback on lock changes and improvements
        if poll_count == 1:
            # Initial lock
            print(f"{Fore.CYAN}[Poll {poll_count}] LOCKED: {locked_lp_name} @ {best_quote.client_price:,.4f} {best_quote.quote_asset}{Style.RESET_ALL}")
            previous_locked_lp = locked_lp_name
        elif is_improvement:
            # Improvement - lock switched
            print(f"{Fore.GREEN}[Poll {poll_count}] IMPROVEMENT: {locked_lp_name} @ {best_quote.client_price:,.4f} {best_quote.quote_asset} (unlocked {previous_locked_lp}){Style.RESET_ALL}")
            previous_locked_lp = locked_lp_name

    # Get auto-refresh setting from monitor
    auto_refresh = monitor.is_auto_refresh_enabled()

    # Stream quotes (indefinitely if auto-refresh, otherwise until expiry)
    print(f"{Fore.CYAN}[OK] Streaming started. Monitor window updated.{Style.RESET_ALL}")
    if auto_refresh:
        print(f"{Fore.CYAN}[OK] Auto-refresh enabled - will continue until stopped{Style.RESET_ALL}")

    try:
        await streamer.stream_quotes(
            request=request,
            on_quote_update=on_quote_update,
            duration_seconds=None,  # Stream until expiry or manual stop
            auto_refresh=auto_refresh
        )

        # Stream ended (quote expired and no auto-refresh)
        print(f"\n{Fore.YELLOW}[!] Quote expired{Style.RESET_ALL}")
        monitor.show_expired()

    except asyncio.CancelledError:
        # Stream was manually cancelled (new request or 'x' command)
        print(f"{Fore.YELLOW}[!] Stream stopped{Style.RESET_ALL}")
        streamer.stop()


async def main_loop():
    """Main application loop with non-blocking terminal"""
    terminal = TerminalInterface()
    terminal.display_banner()

    print(f"{Fore.CYAN}LP Aggregation Mode - Mock LPs{Style.RESET_ALL}")
    print(f"Markup: {settings.markup_bps} bps")
    print(f"LPs: {settings.mock_lp_count} mock providers\n")

    # Start monitor in background
    monitor = get_monitor()
    print(f"{Fore.GREEN}[OK] Monitor window opened{Style.RESET_ALL}\n")

    # Initialize database if logging is enabled
    quote_logger = None
    if settings.enable_database_logging:
        from .database.schema import init_database
        from .database.quote_logger import QuoteLogger
        init_database(settings.database_path)
        quote_logger = QuoteLogger(settings.database_path)
        print(f"{Fore.GREEN}[OK] Database logging enabled: {settings.database_path}{Style.RESET_ALL}\n")

    # Create LP aggregator and streamer (reused across requests)
    lps = create_mock_lps()
    aggregator = LPAggregator(
        lps=lps,
        markup_bps=settings.markup_bps,
        validity_buffer_seconds=settings.validity_buffer_seconds
    )
    streamer = QuoteStreamer(
        aggregator=aggregator,
        poll_interval_ms=settings.poll_interval_ms,
        improvement_threshold_bps=settings.improvement_threshold_bps,
        quote_logger=quote_logger
    )

    # Track current streaming task
    current_task: Optional[asyncio.Task] = None

    print(f"{Fore.YELLOW}Commands:{Style.RESET_ALL}")
    print(f"  - Enter quote request (e.g., 'b 1.5 btcusdt' or 's 2.0 ethusdt')")
    print(f"  - Type 'x' to stop current stream")
    print(f"  - Type 'q' to quit\n")

    while True:
        # Get input from operator (blocking but that's OK)
        user_input = input(f"{Fore.CYAN}>{Style.RESET_ALL} ").strip().lower()

        if user_input == 'q':
            # Quit application
            if current_task and not current_task.done():
                current_task.cancel()
                try:
                    await current_task
                except asyncio.CancelledError:
                    pass
            print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}\n")
            break

        if user_input == 'x':
            # Stop current stream
            if current_task and not current_task.done():
                current_task.cancel()
                try:
                    await current_task
                except asyncio.CancelledError:
                    pass
                print(f"{Fore.YELLOW}[!] Stream stopped{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[!] No active stream{Style.RESET_ALL}")
            continue

        # Parse as quote request
        request = terminal.parse_input(user_input)

        if request is None:
            print(f"{Fore.RED}[X] Invalid request. Format: <side> <amount> <pair>{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}    Example: b 1.5 btcusdt{Style.RESET_ALL}")
            continue

        print(f"{Fore.CYAN}Request: {request}{Style.RESET_ALL}")

        # Cancel previous stream if exists
        if current_task and not current_task.done():
            print(f"{Fore.YELLOW}[!] Stopping previous stream...{Style.RESET_ALL}")
            current_task.cancel()
            try:
                await current_task
            except asyncio.CancelledError:
                pass

        # Start new stream in background
        current_task = asyncio.create_task(
            handle_quote_stream(request, aggregator, streamer, monitor)
        )

        print(f"{Fore.GREEN}[OK] Enter new request or 'x' to stop, 'q' to quit{Style.RESET_ALL}\n")


def main():
    """Entry point"""
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Application stopped by operator{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
