"""
P&L Calculator

Calculates profit/loss from executed trades based on:
- What the client traded (target_asset)
- What we executed on exchange (hedge)
- Where we want to keep profit (profit_asset)

Ported from rfq/src/main.py:621-714
"""

from typing import Dict, Tuple
from ..core.models import AggregatedQuote
from ..config.pairs import TradingPairConfig


def calculate_pnl(
    quote: AggregatedQuote,
    side: str,
    target_asset: str,
    execution_result: Dict,
    pair_config: TradingPairConfig
) -> Tuple[float, str, float, float]:
    """
    Calculate P&L from the executed trade.

    P&L logic depends on:
    1. What client traded (target_asset)
    2. Client side (BUY/SELL)
    3. Where we keep profit (profit_asset)

    Args:
        quote: Aggregated quote with trade details
        side: Client side ('BUY' or 'SELL')
        target_asset: Asset the client is trading
        execution_result: Execution result from exchange with keys:
            - 'executed_qty': Base asset quantity executed
            - 'executed_quote_qty': Quote asset quantity executed
            - 'commission': Fee amount
            - 'avg_price': Average execution price
        pair_config: Trading pair configuration

    Returns:
        Tuple of (pnl_amount, pnl_asset, pnl_after_fees, pnl_bps)
        - pnl_amount: Gross P&L before fees
        - pnl_asset: Asset in which P&L is denominated
        - pnl_after_fees: Net P&L after fees
        - pnl_bps: P&L in basis points relative to notional

    Example:
        Client buys 1.5 BTC at 100,050, pays 150,075 USDT.
        We buy 1.5 BTC at 100,000, spend 150,000 USDT.
        P&L = 150,075 - 150,000 = 75 USDT (if profit_asset='quote')
    """
    base_asset = pair_config.base_asset
    quote_asset = pair_config.quote_asset
    profit_asset = pair_config.profit_asset

    # Extract client flows
    client_pays = quote.client_gives_amount
    client_receives = quote.client_receives_amount

    # Extract exchange execution results
    we_got_base = execution_result['executed_qty']
    we_spent_quote = execution_result['executed_quote_qty']
    commission = execution_result.get('commission', 0.0)

    # Market price (for P&L bps calculation)
    market_price = quote.lp_price

    # Determine P&L based on what the client traded and our profit asset preference
    if target_asset == base_asset:
        if side == 'BUY':
            # Client pays quote, receives base | We bought base with quote
            if profit_asset == 'base':
                # Profit in base: we bought more base than client receives
                pnl_amount = we_got_base - client_receives
                pnl_asset = base_asset
            else:
                # Profit in quote: client paid us more than we spent
                pnl_amount = client_pays - we_spent_quote
                pnl_asset = quote_asset
        else:  # SELL
            # Client pays base, receives quote | We sold base for quote
            if profit_asset == 'quote':
                # Profit in quote: we got more quote than client receives
                pnl_amount = we_spent_quote - client_receives
                pnl_asset = quote_asset
            else:
                # Profit in base: client gave us more base than we spent
                pnl_amount = client_pays - we_got_base
                pnl_asset = base_asset
    else:  # target_asset == quote_asset
        if side == 'BUY':
            # Client pays base, receives quote | We sold base for quote
            if profit_asset == 'quote':
                # Profit in quote: we got more quote than client receives
                pnl_amount = we_spent_quote - client_receives
                pnl_asset = quote_asset
            else:
                # Profit in base: client gave us more base than we spent
                pnl_amount = client_pays - we_got_base
                pnl_asset = base_asset
        else:  # SELL
            # Client pays quote, receives base | We bought base with quote
            if profit_asset == 'base':
                # Profit in base: we bought more base than client receives
                pnl_amount = we_got_base - client_receives
                pnl_asset = base_asset
            else:
                # Profit in quote: client paid us more than we spent
                pnl_amount = client_pays - we_spent_quote
                pnl_asset = quote_asset

    # Adjust for commission
    pnl_after_fees = pnl_amount - commission

    # Calculate P&L in bps relative to quote currency notional
    if quote.client_gives_asset == quote_asset:
        notional_quote = quote.client_gives_amount
    else:
        notional_quote = quote.client_receives_amount

    # Convert P&L to quote currency if needed for bps calculation
    if pnl_asset == base_asset and notional_quote > 0:
        # P&L is in base, convert to quote for bps
        pnl_in_quote = pnl_after_fees * market_price
        pnl_bps = (pnl_in_quote / notional_quote) * 10000 if notional_quote > 0 else 0
    else:
        # P&L already in quote
        pnl_bps = (pnl_after_fees / notional_quote) * 10000 if notional_quote > 0 else 0

    return pnl_amount, pnl_asset, pnl_after_fees, pnl_bps


def format_pnl(
    pnl_amount: float,
    pnl_asset: str,
    pnl_after_fees: float,
    pnl_bps: float
) -> str:
    """
    Format P&L for display.

    Args:
        pnl_amount: Gross P&L
        pnl_asset: P&L asset
        pnl_after_fees: Net P&L after fees
        pnl_bps: P&L in basis points

    Returns:
        Formatted string
    """
    sign = "+" if pnl_after_fees >= 0 else ""
    return f"{sign}{pnl_after_fees:.8f} {pnl_asset} ({sign}{pnl_bps:.2f} bps)"
