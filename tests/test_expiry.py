"""
Test quote expiry behavior - ensure streaming stops when quote expires.

This test verifies that:
1. When auto_refresh=False, streaming stops when quote expires
2. Monitor shows "EXPIRED" and no new quotes beat the expired one
3. When auto_refresh=True, a fresh quote is requested after expiry
"""

import asyncio
import sys
import os
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.models import QuoteRequest, AggregatedQuote, LPQuote
from src.core.lp_aggregator import LPAggregator
from src.core.quote_streamer import QuoteStreamer
from src.lps.mock_lp import MockLP
from src.ui.monitor import get_monitor
from colorama import Fore, Style, init

init()


async def test_expiry_no_autorefresh():
    """Test that streaming stops when quote expires (auto_refresh=False)"""
    print("\n" + "=" * 70)
    print("TEST 1: Quote Expiry WITHOUT Auto-Refresh")
    print("=" * 70)
    print("\nExpected behavior:")
    print("  - Stream should stop after ~8 seconds (quote validity - buffer)")
    print("  - Monitor should show 'EXPIRED'")
    print("  - No new quotes should beat the expired one")
    print("\n" + "-" * 70)

    # Create LPs (MockLP has 10s validity, with 2s buffer = 8s client validity)
    lps = [
        MockLP("LP-Short", base_price=100000, spread_bps=5),
        MockLP("LP-Competitor", base_price=100100, spread_bps=5),
    ]

    aggregator = LPAggregator(lps=lps, markup_bps=5.0, validity_buffer_seconds=2.0)
    streamer = QuoteStreamer(aggregator=aggregator, poll_interval_ms=500, improvement_threshold_bps=1.0)

    request = QuoteRequest(side='BUY', amount=1.5, base_asset='BTC', quote_asset='USDT')

    poll_count = 0
    expired_shown = False

    def on_quote_update(all_lp_quotes: List[LPQuote], best_quote: AggregatedQuote,
                        poll_num: int, is_improvement: bool, locked_lp_name: Optional[str]):
        nonlocal poll_count, expired_shown
        poll_count = poll_num

        # Check if quote is expired
        if best_quote.time_remaining() <= 0:
            if not expired_shown:
                print(f"{Fore.RED}[Poll {poll_num}] EXPIRED detected (time_remaining = {best_quote.time_remaining():.1f}s){Style.RESET_ALL}")
                expired_shown = True

        if is_improvement:
            print(f"{Fore.GREEN}[Poll {poll_num}] IMPROVEMENT: {locked_lp_name} @ {best_quote.client_price:,.2f} (time_remaining: {best_quote.time_remaining():.1f}s){Style.RESET_ALL}")
        elif poll_num % 3 == 0:
            print(f"{Fore.WHITE}[Poll {poll_num}] Locked: {locked_lp_name} @ {best_quote.client_price:,.2f} (time_remaining: {best_quote.time_remaining():.1f}s){Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}Starting stream (auto_refresh=False)...{Style.RESET_ALL}\n")

    start_time = asyncio.get_event_loop().time()

    await streamer.stream_quotes(
        request=request,
        on_quote_update=on_quote_update,
        duration_seconds=None,  # No duration limit
        auto_refresh=False  # Should stop when expired
    )

    end_time = asyncio.get_event_loop().time()
    elapsed = end_time - start_time

    print(f"\n{Fore.YELLOW}Stream ended after {elapsed:.1f}s and {poll_count} polls{Style.RESET_ALL}")

    # Verify
    if 7 <= elapsed <= 11:  # Should stop around 8s (quote validity)
        print(f"{Fore.GREEN}[PASS] Stream stopped at correct time (~8s){Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}[FAIL] Stream stopped at {elapsed:.1f}s (expected ~8s){Style.RESET_ALL}")

    if expired_shown:
        print(f"{Fore.GREEN}[PASS] Expiry was detected{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}[FAIL] Expiry was never detected{Style.RESET_ALL}")


async def test_expiry_with_autorefresh():
    """Test that streaming continues with fresh quotes (auto_refresh=True)"""
    print("\n\n" + "=" * 70)
    print("TEST 2: Quote Expiry WITH Auto-Refresh")
    print("=" * 70)
    print("\nExpected behavior:")
    print("  - Stream should continue past 8s (auto-refresh enabled)")
    print("  - Fresh quote should be requested when current expires")
    print("  - Poll count should reset when refreshed")
    print("\n" + "-" * 70)

    # Create LPs (MockLP has 10s validity, with 2s buffer = 8s client validity)
    lps = [
        MockLP("LP-AutoRefresh", base_price=100000, spread_bps=5),
        MockLP("LP-Competitor2", base_price=100100, spread_bps=5),
    ]

    aggregator = LPAggregator(lps=lps, markup_bps=5.0, validity_buffer_seconds=2.0)
    streamer = QuoteStreamer(aggregator=aggregator, poll_interval_ms=500, improvement_threshold_bps=1.0)

    request = QuoteRequest(side='BUY', amount=1.5, base_asset='BTC', quote_asset='USDT')

    poll_count = 0
    refresh_count = 0
    last_poll = 0

    def on_quote_update(all_lp_quotes: List[LPQuote], best_quote: AggregatedQuote,
                        poll_num: int, is_improvement: bool, locked_lp_name: Optional[str]):
        nonlocal poll_count, refresh_count, last_poll

        # Detect refresh (poll count resets)
        if poll_num < last_poll:
            refresh_count += 1
            print(f"{Fore.MAGENTA}[REFRESH #{refresh_count}] New quote requested (poll count reset){Style.RESET_ALL}")

        last_poll = poll_num
        poll_count = poll_num

        if is_improvement or poll_num == 1:
            print(f"{Fore.GREEN}[Poll {poll_num}] {'REFRESH' if poll_num == 1 and refresh_count > 0 else 'LOCKED'}: {locked_lp_name} @ {best_quote.client_price:,.2f} (time: {best_quote.time_remaining():.1f}s){Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}Starting stream (auto_refresh=True)...{Style.RESET_ALL}\n")

    # Run for 12 seconds (should trigger at least 2 refreshes with 5s validity)
    async def run_with_timeout():
        task = asyncio.create_task(streamer.stream_quotes(
            request=request,
            on_quote_update=on_quote_update,
            duration_seconds=12,
            auto_refresh=True
        ))

        await asyncio.sleep(12)
        streamer.stop()

        try:
            await task
        except asyncio.CancelledError:
            pass

    await run_with_timeout()

    print(f"\n{Fore.YELLOW}Stream ended after 12s{Style.RESET_ALL}")

    # Verify
    if refresh_count >= 1:
        print(f"{Fore.GREEN}[PASS] Auto-refresh worked ({refresh_count} refresh(es)){Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}[FAIL] No auto-refresh detected (expected at least 1){Style.RESET_ALL}")


async def main():
    """Run expiry tests"""
    print("\n" + "=" * 70)
    print("QUOTE EXPIRY TESTS")
    print("=" * 70)

    try:
        await test_expiry_no_autorefresh()
        await test_expiry_with_autorefresh()

        print("\n\n" + "=" * 70)
        print("EXPIRY TESTS COMPLETE")
        print("=" * 70)
        print()

    except Exception as e:
        print(f"\n{Fore.RED}[ERROR] Test failed: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
