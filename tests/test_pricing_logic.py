"""
Unit tests for pricing logic migration.

Tests target_asset handling, amount calculations, and rounding rules.
"""

import sys
from pathlib import Path
import time

# Add parent to path to import src as a module
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import QuoteRequest, LPQuote, AggregatedQuote
from src.core.lp_aggregator import LPAggregator


def test_buy_base_asset():
    """Test BUY base asset (standard case)"""
    print("\n=== Test 1: BUY 1.5 BTC on BTCUSDT ===")

    request = QuoteRequest(
        side='BUY',
        amount=1.5,
        base_asset='BTC',
        quote_asset='USDT',
        target_asset='BTC'  # Buying BTC
    )

    # Mock LP quote: BTC price is 100,000 USDT
    lp_quote = LPQuote(
        lp_name='TestLP',
        price=100000.0,
        quantity=10.0,
        validity_seconds=10.0,
        timestamp=time.time(),
        side='BUY'
    )

    aggregator = LPAggregator(lps=[], markup_bps=5.0)  # 5 bps markup
    quote = aggregator._create_aggregated_quote(lp_quote, request)

    print(f"Request: {request}")
    print(f"LP Price: {lp_quote.price:,.2f}")
    print(f"Client Price: {quote.client_price:,.2f}")
    print(f"Client gives: {quote.client_gives_amount:,.2f} {quote.client_gives_asset}")
    print(f"Client receives: {quote.client_receives_amount:.5f} {quote.client_receives_asset}")

    # Verify logic
    # Client buys BTC, pays USDT
    assert quote.client_receives_asset == 'BTC'
    assert quote.client_gives_asset == 'USDT'
    assert quote.client_receives_amount == 1.5  # Exact amount requested

    # Client price should have 5bps markup (BUY = pay premium)
    expected_price = 100000.0 * (1 + 5.0 / 10000)  # 100050.0
    assert abs(quote.client_price - expected_price) < 0.01

    # Client pays = amount * price = 1.5 * 100050 = 150075
    # Rounded UP (protects market maker)
    assert quote.client_gives_amount == 150075.00

    print("[OK] Test passed!")


def test_buy_quote_asset():
    """Test BUY quote asset (inverted case)"""
    print("\n=== Test 2: BUY 50,000 USDT on BTCUSDT ===")

    request = QuoteRequest(
        side='BUY',
        amount=50000.0,
        base_asset='BTC',
        quote_asset='USDT',
        target_asset='USDT'  # Buying USDT (not BTC!)
    )

    # Mock LP quote: BTC price is 100,000 USDT
    lp_quote = LPQuote(
        lp_name='TestLP',
        price=100000.0,
        quantity=10.0,
        validity_seconds=10.0,
        timestamp=time.time(),
        side='BUY'
    )

    aggregator = LPAggregator(lps=[], markup_bps=5.0)
    quote = aggregator._create_aggregated_quote(lp_quote, request)

    print(f"Request: {request}")
    print(f"LP Price: {lp_quote.price:,.2f}")
    print(f"Client Price: {quote.client_price:,.2f}")
    print(f"Client gives: {quote.client_gives_amount:.5f} {quote.client_gives_asset}")
    print(f"Client receives: {quote.client_receives_amount:,.2f} {quote.client_receives_asset}")

    # Verify logic
    # Client buys USDT, pays BTC
    assert quote.client_receives_asset == 'USDT'
    assert quote.client_gives_asset == 'BTC'
    assert quote.client_receives_amount == 50000.0  # Exact amount requested

    # Client price should have INVERTED markup (BUY quote = discount on base price)
    expected_price = 100000.0 * (1 - 5.0 / 10000)  # 99950.0
    assert abs(quote.client_price - expected_price) < 0.01

    # Client pays = amount / price = 50000 / 99950 ≈ 0.50025 BTC
    # Rounded UP (protects market maker)
    expected_payment = 50000.0 / expected_price
    assert quote.client_gives_amount >= expected_payment

    print("[OK] Test passed!")


def test_sell_base_asset():
    """Test SELL base asset (standard case)"""
    print("\n=== Test 3: SELL 2.0 BTC on BTCUSDT ===")

    request = QuoteRequest(
        side='SELL',
        amount=2.0,
        base_asset='BTC',
        quote_asset='USDT',
        target_asset='BTC'  # Selling BTC
    )

    lp_quote = LPQuote(
        lp_name='TestLP',
        price=100000.0,
        quantity=10.0,
        validity_seconds=10.0,
        timestamp=time.time(),
        side='SELL'
    )

    aggregator = LPAggregator(lps=[], markup_bps=5.0)
    quote = aggregator._create_aggregated_quote(lp_quote, request)

    print(f"Request: {request}")
    print(f"LP Price: {lp_quote.price:,.2f}")
    print(f"Client Price: {quote.client_price:,.2f}")
    print(f"Client gives: {quote.client_gives_amount:.5f} {quote.client_gives_asset}")
    print(f"Client receives: {quote.client_receives_amount:,.2f} {quote.client_receives_asset}")

    # Verify logic
    # Client sells BTC, receives USDT
    assert quote.client_gives_asset == 'BTC'
    assert quote.client_receives_asset == 'USDT'
    assert quote.client_gives_amount == 2.0

    # Client price should have 5bps discount (SELL = receive less)
    expected_price = 100000.0 * (1 - 5.0 / 10000)  # 99950.0
    assert abs(quote.client_price - expected_price) < 0.01

    # Client receives = amount * price = 2.0 * 99950 = 199900
    # Rounded DOWN (protects market maker)
    assert quote.client_receives_amount == 199900.00

    print("[OK] Test passed!")


def test_sell_quote_asset():
    """Test SELL quote asset (inverted case)"""
    print("\n=== Test 4: SELL 75,000 USDT on BTCUSDT ===")

    request = QuoteRequest(
        side='SELL',
        amount=75000.0,
        base_asset='BTC',
        quote_asset='USDT',
        target_asset='USDT'  # Selling USDT (not BTC!)
    )

    lp_quote = LPQuote(
        lp_name='TestLP',
        price=100000.0,
        quantity=10.0,
        validity_seconds=10.0,
        timestamp=time.time(),
        side='SELL'
    )

    aggregator = LPAggregator(lps=[], markup_bps=5.0)
    quote = aggregator._create_aggregated_quote(lp_quote, request)

    print(f"Request: {request}")
    print(f"LP Price: {lp_quote.price:,.2f}")
    print(f"Client Price: {quote.client_price:,.2f}")
    print(f"Client gives: {quote.client_gives_amount:,.2f} {quote.client_gives_asset}")
    print(f"Client receives: {quote.client_receives_amount:.5f} {quote.client_receives_asset}")

    # Verify logic
    # Client sells USDT, receives BTC
    assert quote.client_gives_asset == 'USDT'
    assert quote.client_receives_asset == 'BTC'
    assert quote.client_gives_amount == 75000.0

    # Client price should have INVERTED markup (SELL quote = premium on base price)
    expected_price = 100000.0 * (1 + 5.0 / 10000)  # 100050.0
    assert abs(quote.client_price - expected_price) < 0.01

    # Client receives = amount / price = 75000 / 100050 ≈ 0.74962 BTC
    # Rounded DOWN (protects market maker)
    expected_receives = 75000.0 / expected_price
    assert quote.client_receives_amount <= expected_receives

    print("[OK] Test passed!")


def test_rounding():
    """Test rounding rules"""
    print("\n=== Test 5: Rounding Rules ===")

    # Case that creates fractional amounts
    request = QuoteRequest(
        side='BUY',
        amount=1.23456789,
        base_asset='BTC',
        quote_asset='USDT',
        target_asset='BTC'
    )

    lp_quote = LPQuote(
        lp_name='TestLP',
        price=99999.99,
        quantity=10.0,
        validity_seconds=10.0,
        timestamp=time.time(),
        side='BUY'
    )

    aggregator = LPAggregator(lps=[], markup_bps=7.5)
    quote = aggregator._create_aggregated_quote(lp_quote, request)

    print(f"Client receives (BTC): {quote.client_receives_amount}")
    print(f"Client gives (USDT): {quote.client_gives_amount}")

    # BTC has 5 decimals, USDT has 2 decimals (per config)
    # Client receives should be rounded DOWN to 5 decimals
    assert quote.client_receives_amount == 1.23456  # Rounded down from 1.23456789

    # Client gives should be rounded UP to 2 decimals
    # This protects the market maker

    print("[OK] Test passed!")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("  Pricing Logic Migration Tests")
    print("=" * 60)

    try:
        test_buy_base_asset()
        test_buy_quote_asset()
        test_sell_base_asset()
        test_sell_quote_asset()
        test_rounding()

        print("\n" + "=" * 60)
        print("  [SUCCESS] All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
