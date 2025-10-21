"""
Manual test script for the LP Aggregation Monitor.

Run this to verify the monitor displays correctly with live LP quotes.
"""

import asyncio
import time
from colorama import Fore, Style, init

from src.core.models import QuoteRequest
from src.core.lp_aggregator import LPAggregator
from src.core.quote_streamer import QuoteStreamer
from src.lps.mock_lp import MockLP
from src.ui.monitor import get_monitor

init(autoreset=True)


async def test_monitor():
    """Test monitor with live streaming quotes"""

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"LP Aggregation Monitor - Manual Test")
    print(f"{'='*60}{Style.RESET_ALL}\n")

    # Create mock LPs with varying prices
    print(f"{Fore.YELLOW}Creating mock LPs...{Style.RESET_ALL}")
    lps = [
        MockLP("LP-Alpha", base_price=99900, spread_bps=5),
        MockLP("LP-Beta", base_price=100000, spread_bps=8),
        MockLP("LP-Gamma", base_price=100100, spread_bps=6),
        MockLP("LP-Delta", base_price=100200, spread_bps=10),
        MockLP("LP-Epsilon", base_price=100300, spread_bps=7),
    ]

    # Create aggregator
    aggregator = LPAggregator(lps=lps, markup_bps=5.0)

    # Start monitor
    print(f"{Fore.YELLOW}Starting monitor window...{Style.RESET_ALL}")
    monitor = get_monitor()
    time.sleep(1)  # Give monitor time to initialize
    print(f"{Fore.GREEN}[OK] Monitor window opened{Style.RESET_ALL}\n")

    # Create quote request
    request = QuoteRequest(
        side='BUY',
        amount=1.5,
        base_asset='BTC',
        quote_asset='USDT'
    )

    print(f"{Fore.CYAN}Request: {request}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Streaming quotes for 15 seconds...{Style.RESET_ALL}\n")

    # Create streamer
    streamer = QuoteStreamer(aggregator, poll_interval_ms=500, improvement_threshold_bps=1.0)

    poll_count = 0
    previous_locked_lp = None

    def on_quote_update(all_lp_quotes, best_quote, poll_num, is_improvement, locked_lp_name):
        nonlocal poll_count, previous_locked_lp
        poll_count = poll_num

        # Update monitor
        monitor.update_display(all_lp_quotes, best_quote, poll_num, locked_lp_name)

        # Terminal feedback
        if poll_num == 1:
            # Initial lock
            print(f"{Fore.CYAN}[Poll {poll_num}] LOCKED: {locked_lp_name} @ {best_quote.client_price:,.2f}{Style.RESET_ALL}")
            previous_locked_lp = locked_lp_name
        elif is_improvement:
            # Improvement - lock switched
            print(f"{Fore.GREEN}[Poll {poll_num}] IMPROVEMENT: {locked_lp_name} @ {best_quote.client_price:,.2f} (unlocked {previous_locked_lp}){Style.RESET_ALL}")
            previous_locked_lp = locked_lp_name
        else:
            print(f"{Fore.WHITE}[Poll {poll_num}] Locked: {locked_lp_name} @ {best_quote.client_price:,.2f} ({len(all_lp_quotes)} LPs){Style.RESET_ALL}")

    # Stream quotes
    try:
        await streamer.stream_quotes(
            request=request,
            on_quote_update=on_quote_update,
            duration_seconds=15,
            auto_refresh=False
        )

        print(f"\n{Fore.YELLOW}[!] Stream completed ({poll_count} polls){Style.RESET_ALL}")
        print(f"{Fore.CYAN}Monitor window should show:{Style.RESET_ALL}")
        print(f"  - Best quote at top")
        print(f"  - LP leaderboard with 5 LPs ranked by price")
        print(f"  - 1st place highlighted in green")
        print(f"  - Stream status at bottom\n")

        print(f"{Fore.YELLOW}Keeping monitor open for 30 seconds...{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Check the monitor window to verify display{Style.RESET_ALL}\n")

        # Keep alive so you can see the monitor
        await asyncio.sleep(30)

        print(f"\n{Fore.GREEN}[OK] Test complete!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}If you saw the monitor with LP leaderboard, everything is working!{Style.RESET_ALL}\n")

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Test interrupted by user{Style.RESET_ALL}\n")


if __name__ == "__main__":
    try:
        asyncio.run(test_monitor())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}\n")
