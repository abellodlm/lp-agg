"""
Trade Execution Simulator

Simulates exchange execution for demonstration purposes.
Uses LP's quoted price as the "exchange execution price".
"""

from typing import Dict, Optional
from ..core.models import AggregatedQuote, LPQuote


def execute_simulated_trade(
    quote: AggregatedQuote,
    exchange_side: str,
    quantity: Optional[float],
    quote_qty: Optional[float],
    lp_price: float,
    commission_bps: float = 0.1
) -> Dict:
    """
    Simulate trade execution on an exchange.

    Uses the LP's quoted price as the execution price (no slippage simulation).

    Args:
        quote: Aggregated quote with trade details
        exchange_side: 'BUY' or 'SELL' on exchange
        quantity: Base asset quantity (if specified)
        quote_qty: Quote asset quantity (if specified)
        lp_price: LP's price (used as execution price)
        commission_bps: Commission in basis points (default 0.1 bps = 0.001%)

    Returns:
        Execution result dictionary with keys:
        - 'executed_qty': Base asset quantity executed
        - 'executed_quote_qty': Quote asset quantity executed
        - 'avg_price': Average execution price
        - 'commission': Commission paid
        - 'status': 'FILLED'
        - 'order_id': Simulated order ID
    """
    # Calculate executed quantities
    if quantity is not None:
        # Quantity specified -> calculate quote_qty
        executed_qty = quantity
        executed_quote_qty = quantity * lp_price
    else:
        # Quote qty specified -> calculate quantity
        executed_quote_qty = quote_qty
        executed_qty = quote_qty / lp_price

    # Calculate commission
    # Commission is typically charged on the asset we receive
    if exchange_side == 'BUY':
        # We receive base asset -> commission in base
        commission = executed_qty * (commission_bps / 10000)
        executed_qty -= commission  # Reduce received amount by commission
    else:  # SELL
        # We receive quote asset -> commission in quote
        commission = executed_quote_qty * (commission_bps / 10000)
        executed_quote_qty -= commission  # Reduce received amount by commission

    # Create execution result (matches Binance API response format)
    return {
        'order_id': f"SIM{quote.quote_id}",  # Simulated order ID
        'status': 'FILLED',
        'side': exchange_side,
        'executed_qty': executed_qty,
        'executed_quote_qty': executed_quote_qty,
        'avg_price': lp_price,
        'commission': commission,
        'commission_bps': commission_bps
    }


def format_execution_result(result: Dict, base_asset: str, quote_asset: str) -> str:
    """
    Format execution result for display.

    Args:
        result: Execution result dictionary
        base_asset: Base asset symbol
        quote_asset: Quote asset symbol

    Returns:
        Formatted string
    """
    lines = []
    lines.append(f"Order ID: {result['order_id']}")
    lines.append(f"Status: {result['status']}")
    lines.append(f"Side: {result['side']}")
    lines.append(f"Executed Qty: {result['executed_qty']:.8f} {base_asset}")
    lines.append(f"Executed Value: {result['executed_quote_qty']:.2f} {quote_asset}")
    lines.append(f"Avg Price: {result['avg_price']:.2f}")
    lines.append(f"Commission: {result['commission']:.8f} ({result['commission_bps']} bps)")

    return "\n".join(lines)
