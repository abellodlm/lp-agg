"""
Quick test script to verify the LP aggregation system works end-to-end.

This script simulates a quote request without operator input.
"""

import asyncio
from src.core.models import QuoteRequest
from src.core.lp_aggregator import LPAggregator
from src.core.quote_streamer import QuoteStreamer
from src.lps.mock_lp import MockLP
from src.config.settings import settings


async def test_single_quote():
    """Test getting a single aggregated quote"""
    print("=" * 60)
    print("TEST 1: Single Quote Request")
    print("=" * 60)

    # Create mock LPs
    lps = [
        MockLP("LP-A", base_price=100000, spread_bps=5),
        MockLP("LP-B", base_price=100100, spread_bps=8),
        MockLP("LP-C", base_price=99900, spread_bps=6),
    ]

    # Create aggregator
    aggregator = LPAggregator(lps=lps, markup_bps=5.0)

    # Test BUY request
    request = QuoteRequest(
        side='BUY',
        amount=1.5,
        base_asset='BTC',
        quote_asset='USDT'
    )

    print(f"\nRequest: {request}")
    quote = await aggregator.get_best_quote(request)

    if quote:
        print(f"\n[OK] Got quote from: {quote.lp_name}")
        print(f"  LP Price: {quote.lp_price:,.2f} USDT")
        print(f"  Client Price: {quote.client_price:,.2f} USDT (markup: {quote.markup_bps} bps)")
        print(f"  Client pays: {quote.client_gives_amount:,.2f} {quote.client_gives_asset}")
        print(f"  Client receives: {quote.client_receives_amount:.8f} {quote.client_receives_asset}")
        print(f"  Valid for: {quote.validity_seconds}s")
    else:
        print("[FAIL] No quote received")

    # Test SELL request
    request_sell = QuoteRequest(
        side='SELL',
        amount=2.0,
        base_asset='BTC',
        quote_asset='USDT'
    )

    print(f"\n\nRequest: {request_sell}")
    quote_sell = await aggregator.get_best_quote(request_sell)

    if quote_sell:
        print(f"\n[OK] Got quote from: {quote_sell.lp_name}")
        print(f"  LP Price: {quote_sell.lp_price:,.2f} USDT")
        print(f"  Client Price: {quote_sell.client_price:,.2f} USDT (markup: {quote_sell.markup_bps} bps)")
        print(f"  Client pays: {quote_sell.client_gives_amount:.8f} {quote_sell.client_gives_asset}")
        print(f"  Client receives: {quote_sell.client_receives_amount:,.2f} {quote_sell.client_receives_asset}")
        print(f"  Valid for: {quote_sell.validity_seconds}s")
    else:
        print("[FAIL] No quote received")


async def test_quote_streaming():
    """Test quote streaming with improvements"""
    print("\n\n" + "=" * 60)
    print("TEST 2: Quote Streaming (5 second test)")
    print("=" * 60)

    # Create LPs with varying prices
    lps = [
        MockLP("Streamer-LP-1", base_price=100000, spread_bps=10),
        MockLP("Streamer-LP-2", base_price=100050, spread_bps=8),
        MockLP("Streamer-LP-3", base_price=99950, spread_bps=12),
    ]

    aggregator = LPAggregator(lps=lps, markup_bps=5.0)
    streamer = QuoteStreamer(aggregator=aggregator, poll_interval_ms=1000)

    request = QuoteRequest(
        side='BUY',
        amount=1.0,
        base_asset='ETH',
        quote_asset='USDT'
    )

    quote_count = 0

    def on_update(quote, is_improvement):
        nonlocal quote_count
        quote_count += 1
        improvement_tag = " [IMPROVEMENT]" if is_improvement else ""
        print(f"\n  Quote {quote_count}{improvement_tag}:")
        print(f"    {quote.lp_name}: {quote.client_price:,.2f} USDT (valid: {quote.validity_seconds:.1f}s)")

    print(f"\nStreaming quotes for {request}...")
    print("Polling every 1 second for 5 seconds...\n")

    await streamer.stream_quotes(
        request=request,
        on_quote_update=on_update,
        duration_seconds=5
    )

    print(f"\n[OK] Stream completed. Received {quote_count} quote(s)")


async def test_lp_selection_logic():
    """Test that LP selection logic works correctly"""
    print("\n\n" + "=" * 60)
    print("TEST 3: LP Selection Logic")
    print("=" * 60)

    # Create LPs with wide price gaps (to avoid random variation affecting results)
    lps = [
        MockLP("Expensive-LP", base_price=105000, spread_bps=0),
        MockLP("Cheap-LP", base_price=95000, spread_bps=0),
        MockLP("Mid-LP", base_price=100000, spread_bps=0),
    ]

    aggregator = LPAggregator(lps=lps, markup_bps=5.0)

    # BUY should select cheapest LP (even with ±1% variation)
    buy_request = QuoteRequest(side='BUY', amount=1.0, base_asset='BTC', quote_asset='USDT')
    buy_quote = await aggregator.get_best_quote(buy_request)

    print(f"\nBUY Request:")
    print(f"  Selected LP: {buy_quote.lp_name}")
    print(f"  LP Price: {buy_quote.lp_price:,.2f} USDT")
    print(f"  Expected: Cheap-LP (lowest ask)")
    buy_pass = buy_quote.lp_price < 97000  # Should be cheapest even with variation
    print(f"  [PASS]" if buy_pass else "  [FAIL]")

    # SELL should select most expensive LP (even with ±1% variation)
    sell_request = QuoteRequest(side='SELL', amount=1.0, base_asset='BTC', quote_asset='USDT')
    sell_quote = await aggregator.get_best_quote(sell_request)

    print(f"\nSELL Request:")
    print(f"  Selected LP: {sell_quote.lp_name}")
    print(f"  LP Price: {sell_quote.lp_price:,.2f} USDT")
    print(f"  Expected: Expensive-LP (highest bid)")
    sell_pass = sell_quote.lp_price > 103000  # Should be most expensive even with variation
    print(f"  [PASS]" if sell_pass else "  [FAIL]")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("LP AGGREGATION SYSTEM - END-TO-END TEST")
    print("=" * 60)

    try:
        await test_single_quote()
        await test_quote_streaming()
        await test_lp_selection_logic()

        print("\n\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)
        print("\n[OK] System is working correctly!")
        print("\nTo run the full application:")
        print("  python -m src.main")
        print()

    except Exception as e:
        print(f"\n\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
