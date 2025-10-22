"""
Quick test of execution flow.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.models import QuoteRequest, AggregatedQuote, LPQuote
from src.lps.sine_lp import SineLPProvider
from src.core.lp_aggregator import LPAggregator
from src.execution.execution_manager import ExecutionManager
from src.config.settings import settings
from src.database.schema import init_database
from src.database.quote_logger import QuoteLogger
from src.config.pairs import get_pair_config
import time


async def test_execution():
    """Test the execution flow"""
    print("\n" + "="*70)
    print("EXECUTION FLOW TEST")
    print("="*70 + "\n")

    # Initialize database
    db_path = "test_quotes.db"
    init_database(db_path)
    quote_logger = QuoteLogger(db_path)

    # Create LPs
    lps = [
        SineLPProvider(name="LP-1", base_price=100000.0, phase=0.0),
        SineLPProvider(name="LP-2", base_price=100000.0, phase=1.57),
        SineLPProvider(name="LP-3", base_price=100000.0, phase=3.14),
    ]

    # Create aggregator
    aggregator = LPAggregator(
        lps=lps,
        markup_bps=5.0,
        validity_buffer_seconds=2.0
    )

    # Create execution manager
    lp_dict = {lp.get_name(): lp for lp in lps}
    execution_manager = ExecutionManager(lp_dict, quote_logger)

    # Create quote request
    pair_config = get_pair_config('BTCUSDT')
    request = QuoteRequest(
        side='BUY',
        amount=1.5,
        base_asset='BTC',
        quote_asset='USDT',
        target_asset='BTC'
    )

    print(f"Request: {request}\n")

    # Get quotes
    all_lp_quotes, best_quote = await aggregator.get_all_quotes(request)

    if not best_quote:
        print("[FAIL] No quotes received")
        return

    print(f"Best Quote:")
    print(f"  LP:              {best_quote.lp_name}")
    print(f"  Client Price:    {best_quote.client_price:,.2f}")
    print(f"  LP Price:        {best_quote.lp_price:,.2f}")
    print(f"  Client Pays:     {best_quote.client_gives_amount:,.2f} {best_quote.client_gives_asset}")
    print(f"  Client Receives: {best_quote.client_receives_amount:,.8f} {best_quote.client_receives_asset}")
    print()

    # Find the LP quote for this winner
    lp_quote = next((q for q in all_lp_quotes if q.lp_name == best_quote.lp_name), None)

    if not lp_quote:
        print("[FAIL] LP quote not found")
        return

    # Execute the trade
    print("Executing trade...\n")
    exec_result = await execution_manager.execute_quote(best_quote, lp_quote)

    # Display results
    if exec_result['status'] == 'SUCCESS':
        print("="*70)
        print("EXECUTION SUCCESSFUL")
        print("="*70)
        print(f"Execution ID:    {exec_result['execution_id']}")
        print(f"Quote ID:        {exec_result['quote_id']}")
        print(f"LP:              {exec_result['lp_name']}")
        print(f"Exchange Side:   {exec_result['exchange_side']}")
        print(f"Executed Qty:    {exec_result['executed_qty']:,.8f} BTC")
        print(f"Avg Price:       {exec_result['avg_price']:,.2f}")
        print(f"Commission:      {exec_result['commission']:,.8f} {exec_result['commission_asset']}")
        print()
        print("P&L:")
        print(f"  Gross:         {exec_result['pnl_amount']:,.8f} {exec_result['pnl_asset']}")
        print(f"  Net:           {exec_result['pnl_after_fees']:,.8f} {exec_result['pnl_asset']}")
        print(f"  bps:           {exec_result['pnl_bps']:,.2f}")
        print("="*70)
        print()
        print("[OK] Test passed!")
    else:
        print("="*70)
        print("EXECUTION FAILED")
        print("="*70)
        print(f"Error: {exec_result.get('error_message')}")
        print("="*70)
        print()
        print("[FAIL] Test failed")

    # Close logger
    quote_logger.close()


if __name__ == "__main__":
    asyncio.run(test_execution())
