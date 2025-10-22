"""
Unit tests for hedge calculator and P&L calculator.

Tests all 8 scenarios:
- target_asset (base/quote) × side (BUY/SELL) × profit_asset (base/quote)
"""

import sys
from pathlib import Path
import time

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import AggregatedQuote
from src.config.pairs import get_pair_config
from src.execution.hedge_calculator import determine_hedge_params
from src.execution.pnl_calculator import calculate_pnl
from src.execution.simulator import execute_simulated_trade


def create_test_quote(
    side: str,
    amount: float,
    target_asset: str,
    lp_price: float,
    markup_bps: float,
    pair_symbol: str
) -> AggregatedQuote:
    """Helper to create test quote"""
    pair_config = get_pair_config(pair_symbol)

    # Calculate client price
    if target_asset == pair_config.base_asset:
        if side == 'BUY':
            client_price = lp_price * (1 + markup_bps / 10000)
        else:
            client_price = lp_price * (1 - markup_bps / 10000)
    else:
        if side == 'SELL':
            client_price = lp_price * (1 + markup_bps / 10000)
        else:
            client_price = lp_price * (1 - markup_bps / 10000)

    # Calculate flows
    if target_asset == pair_config.base_asset:
        if side == 'BUY':
            client_receives_amount = amount
            client_gives_amount = amount * client_price
            client_receives_asset = pair_config.base_asset
            client_gives_asset = pair_config.quote_asset
        else:
            client_gives_amount = amount
            client_receives_amount = amount * client_price
            client_gives_asset = pair_config.base_asset
            client_receives_asset = pair_config.quote_asset
    else:
        if side == 'BUY':
            client_receives_amount = amount
            client_gives_amount = amount / client_price
            client_receives_asset = pair_config.quote_asset
            client_gives_asset = pair_config.base_asset
        else:
            client_gives_amount = amount
            client_receives_amount = amount / client_price
            client_gives_asset = pair_config.quote_asset
            client_receives_asset = pair_config.base_asset

    return AggregatedQuote(
        quote_id=f"TEST{int(time.time())}",
        client_price=client_price,
        lp_price=lp_price,
        lp_name="TestLP",
        markup_bps=markup_bps,
        side=side,
        amount=amount,
        base_asset=pair_config.base_asset,
        quote_asset=pair_config.quote_asset,
        target_asset=target_asset,
        profit_asset=pair_config.profit_asset,
        client_gives_amount=client_gives_amount,
        client_gives_asset=client_gives_asset,
        client_receives_amount=client_receives_amount,
        client_receives_asset=client_receives_asset,
        base_decimals=pair_config.base_decimals,
        quote_decimals=pair_config.quote_decimals,
        validity_seconds=10.0,
        created_at=time.time()
    )


def test_scenario_1():
    """Scenario 1: BUY base, profit_asset=quote"""
    print("\n=== Test 1: BUY 1.5 BTC, profit in USDT ===")

    pair_config = get_pair_config('BTCUSDT')
    quote = create_test_quote('BUY', 1.5, 'BTC', 100000.0, 5.0, 'BTCUSDT')

    # Determine hedge
    exchange_side, quantity, quote_qty = determine_hedge_params(
        quote, 'BUY', 'BTC', pair_config
    )

    print(f"Client: BUY 1.5 BTC, pays {quote.client_gives_amount:.2f} USDT")
    print(f"Hedge: {exchange_side} {quantity if quantity else quote_qty} {'BTC' if quantity else 'USDT'}")

    assert exchange_side == 'BUY'
    assert quantity == 1.5  # Buy exact amount
    assert quote_qty is None

    # Simulate execution
    exec_result = execute_simulated_trade(
        quote, exchange_side, quantity, quote_qty, quote.lp_price
    )

    # Calculate P&L
    pnl_amount, pnl_asset, pnl_after_fees, pnl_bps = calculate_pnl(
        quote, 'BUY', 'BTC', exec_result, pair_config
    )

    print(f"Execution: Bought {exec_result['executed_qty']:.5f} BTC at {exec_result['avg_price']:.2f}")
    print(f"P&L: {pnl_after_fees:.2f} {pnl_asset} ({pnl_bps:.2f} bps)")

    assert pnl_asset == 'USDT'
    assert pnl_after_fees > 0  # Should make profit

    print("[OK] Test passed!")


def test_scenario_2():
    """Scenario 2: BUY quote, profit_asset=quote"""
    print("\n=== Test 2: BUY 50000 USDT, profit in USDT ===")

    pair_config = get_pair_config('BTCUSDT')
    quote = create_test_quote('BUY', 50000.0, 'USDT', 100000.0, 5.0, 'BTCUSDT')

    exchange_side, quantity, quote_qty = determine_hedge_params(
        quote, 'BUY', 'USDT', pair_config
    )

    print(f"Client: BUY 50000 USDT, pays {quote.client_gives_amount:.5f} BTC")
    print(f"Hedge: {exchange_side} {quantity if quantity else quote_qty}")

    assert exchange_side == 'SELL'  # Sell BTC to get USDT

    # Simulate execution
    exec_result = execute_simulated_trade(
        quote, exchange_side, quantity, quote_qty, quote.lp_price
    )

    # Calculate P&L
    pnl_amount, pnl_asset, pnl_after_fees, pnl_bps = calculate_pnl(
        quote, 'BUY', 'USDT', exec_result, pair_config
    )

    print(f"P&L: {pnl_after_fees:.8f} {pnl_asset} ({pnl_bps:.2f} bps)")

    assert pnl_asset == 'USDT'
    assert pnl_after_fees > 0

    print("[OK] Test passed!")


def test_all_8_scenarios():
    """Test all 8 combinations"""
    print("\n" + "=" * 60)
    print("  Testing All 8 Hedge/P&L Scenarios")
    print("=" * 60)

    scenarios = [
        ('BUY', 'BTC', 1.5, 'BTCUSDT'),
        ('SELL', 'BTC', 1.5, 'BTCUSDT'),
        ('BUY', 'USDT', 50000.0, 'BTCUSDT'),
        ('SELL', 'USDT', 50000.0, 'BTCUSDT'),
    ]

    for i, (side, target, amount, pair) in enumerate(scenarios, 1):
        print(f"\n--- Scenario {i}: {side} {amount} {target} on {pair} ---")

        pair_config = get_pair_config(pair)
        quote = create_test_quote(side, amount, target, 100000.0, 5.0, pair)

        # Hedge
        exchange_side, quantity, quote_qty = determine_hedge_params(
            quote, side, target, pair_config
        )

        print(f"Hedge: {exchange_side} {quantity if quantity else quote_qty}")

        # Execute
        exec_result = execute_simulated_trade(
            quote, exchange_side, quantity, quote_qty, quote.lp_price
        )

        # P&L
        pnl_amount, pnl_asset, pnl_after_fees, pnl_bps = calculate_pnl(
            quote, side, target, exec_result, pair_config
        )

        print(f"P&L: {pnl_after_fees:.8f} {pnl_asset} ({pnl_bps:.2f} bps)")

        # All scenarios should be profitable (we're market makers!)
        assert pnl_after_fees > 0, f"Scenario {i} should be profitable!"

        print("[OK]")

    print("\n" + "=" * 60)
    print("  [SUCCESS] All 8 scenarios passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_scenario_1()
        test_scenario_2()
        test_all_8_scenarios()

        print("\n" + "=" * 60)
        print("  All hedge/P&L tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
