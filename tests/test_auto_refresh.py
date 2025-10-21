"""
Test auto-refresh functionality with poll-based kill switch.

This test demonstrates auto-refresh working correctly:
- Quotes expire after 8s
- Auto-refresh requests fresh quotes when expired
- Runs until specified number of refreshes (not duration-based)
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
from colorama import Fore, Style, init

init()


async def test_auto_refresh_with_kill_switch():
    """Test auto-refresh with poll-count based kill switch"""
    print("\n" + "=" * 70)
    print("AUTO-REFRESH TEST (Poll-Based Kill Switch)")
    print("=" * 70)
    print("\nThis test will:")
    print("  - Enable auto-refresh")
    print("  - Stop after 3 quote refreshes (not duration-based)")
    print("  - Each quote has 8s validity")
    print("  - Expected runtime: ~24s (3 refreshes × 8s)")
    print("\n" + "-" * 70 + "\n")

    # Create competing LPs
    lps = [
        MockLP("LP-1", base_price=100000, spread_bps=5),
        MockLP("LP-2", base_price=100100, spread_bps=5),
        MockLP("LP-3", base_price=99900, spread_bps=5),
    ]

    aggregator = LPAggregator(lps=lps, markup_bps=5.0, validity_buffer_seconds=2.0)
    streamer = QuoteStreamer(aggregator=aggregator, poll_interval_ms=500, improvement_threshold_bps=1.0)

    request = QuoteRequest(side='BUY', amount=1.5, base_asset='BTC', quote_asset='USDT')

    # Kill switch: stop after N refreshes
    MAX_REFRESHES = 3
    refresh_count = 0
    poll_count = 0
    last_poll_num = 0
    improvement_count = 0

    def on_quote_update(all_lp_quotes: List[LPQuote], best_quote: AggregatedQuote,
                        poll_num: int, is_improvement: bool, locked_lp_name: Optional[str]):
        nonlocal refresh_count, poll_count, last_poll_num, improvement_count

        poll_count = poll_num

        # Detect refresh (poll count resets to 1)
        if poll_num == 1 and last_poll_num > 1:
            refresh_count += 1
            print(f"\n{Fore.MAGENTA}{'='*70}")
            print(f"REFRESH #{refresh_count} - Fresh quote requested")
            print(f"{'='*70}{Style.RESET_ALL}\n")

            # Kill switch: stop after MAX_REFRESHES
            if refresh_count >= MAX_REFRESHES:
                print(f"{Fore.YELLOW}Kill switch triggered! Stopping after {refresh_count} refreshes.{Style.RESET_ALL}\n")
                streamer.stop()

        last_poll_num = poll_num

        # Track improvements
        if is_improvement:
            improvement_count += 1

        # Display
        if poll_num == 1:
            print(f"{Fore.CYAN}[Poll {poll_num}] LOCKED: {locked_lp_name} @ {best_quote.client_price:,.2f} (validity: {best_quote.time_remaining():.1f}s){Style.RESET_ALL}")
        elif is_improvement:
            print(f"{Fore.GREEN}[Poll {poll_num}] IMPROVEMENT: {locked_lp_name} @ {best_quote.client_price:,.2f} (validity: {best_quote.time_remaining():.1f}s){Style.RESET_ALL}")
        elif poll_num % 5 == 0:  # Print every 5th poll to reduce noise
            print(f"{Fore.WHITE}[Poll {poll_num}] Locked: {locked_lp_name} @ {best_quote.client_price:,.2f} (validity: {best_quote.time_remaining():.1f}s){Style.RESET_ALL}")

    print(f"{Fore.CYAN}Starting stream with auto-refresh enabled...{Style.RESET_ALL}\n")

    start_time = asyncio.get_event_loop().time()

    await streamer.stream_quotes(
        request=request,
        on_quote_update=on_quote_update,
        duration_seconds=None,  # No duration limit - use kill switch instead
        auto_refresh=True
    )

    end_time = asyncio.get_event_loop().time()
    elapsed = end_time - start_time

    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"TEST COMPLETE")
    print(f"{'='*70}{Style.RESET_ALL}")
    print(f"\n  Total runtime: {elapsed:.1f}s")
    print(f"  Total refreshes: {refresh_count}")
    print(f"  Total polls: {poll_count}")
    print(f"  Price improvements: {improvement_count}")
    print(f"  Average time per refresh: {elapsed/refresh_count:.1f}s\n")

    # Verify
    if refresh_count == MAX_REFRESHES:
        print(f"{Fore.GREEN}[PASS] Auto-refresh worked correctly ({refresh_count} refreshes){Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}[FAIL] Expected {MAX_REFRESHES} refreshes, got {refresh_count}{Style.RESET_ALL}")

    if 20 <= elapsed <= 30:  # Should be ~24s (3 × 8s)
        print(f"{Fore.GREEN}[PASS] Runtime within expected range (~24s){Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}[WARNING] Runtime {elapsed:.1f}s outside expected range (20-30s){Style.RESET_ALL}")


async def main():
    """Run auto-refresh test"""
    try:
        await test_auto_refresh_with_kill_switch()
        print()

    except Exception as e:
        print(f"\n{Fore.RED}[ERROR] Test failed: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
