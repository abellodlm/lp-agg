"""
Hedge Parameter Calculator

Determines how to hedge client trades on an exchange based on:
- Client side (BUY/SELL)
- Target asset (which asset they're trading)
- Profit asset (which asset to accumulate profit in)

Ported from rfq/src/main.py:545-619
"""

from typing import Optional, Tuple
from ..core.models import AggregatedQuote
from ..config.pairs import TradingPairConfig


def determine_hedge_params(
    quote: AggregatedQuote,
    side: str,
    target_asset: str,
    pair_config: TradingPairConfig
) -> Tuple[str, Optional[float], Optional[float]]:
    """
    Determine exchange side and quantities for hedging the client trade.

    The hedge logic depends on THREE factors:
    1. Client side (BUY/SELL)
    2. Target asset (base or quote)
    3. Profit asset preference (base or quote)

    This creates 2 × 2 × 2 = 8 different scenarios.

    Args:
        quote: Aggregated quote with trade details
        side: Client side ('BUY' or 'SELL')
        target_asset: Asset the client is trading
        pair_config: Trading pair configuration

    Returns:
        Tuple of (exchange_side, quantity, quote_qty)
        - exchange_side: 'BUY' or 'SELL' on exchange
        - quantity: Base asset quantity (None if using quote_qty)
        - quote_qty: Quote asset quantity (None if using quantity)

    Example:
        Client buys 1.5 BTC, we need to buy BTC on exchange to hedge.
        If profit_asset='quote', buy exact 1.5 BTC (keep profit in USDT).
        If profit_asset='base', spend all USDT to buy more BTC (keep profit in BTC).
    """
    base_asset = pair_config.base_asset
    quote_asset = pair_config.quote_asset
    profit_asset = pair_config.profit_asset

    # Calculate client_price (price shown to client after markup)
    # This is already in the quote, but we need market_price for some calculations
    # For LP aggregator, we use lp_price as the "market price"
    market_price = quote.lp_price

    if target_asset == base_asset:
        # Client is trading base asset (e.g., BTC on BTCUSDT)
        if side == 'BUY':
            # Client buys base from us -> we buy base on market
            exchange_side = 'BUY'

            if profit_asset == 'quote':
                # Keep profit in USDT - buy exact amount client receives
                quantity = quote.client_receives_amount
                quote_qty = None
            else:
                # Keep profit in BTC - spend all USDT client gave us to buy more BTC
                quantity = None
                quote_qty = quote.client_gives_amount
        else:
            # Client sells base to us -> we sell base on market
            exchange_side = 'SELL'

            if profit_asset == 'base':
                # Keep profit in BTC - sell only enough base to get USDT for client
                quantity = quote.client_receives_amount / market_price
                quote_qty = None
            else:
                # Keep profit in USDT - sell all BTC client gave us
                quantity = quote.client_gives_amount
                quote_qty = None

    else:  # target_asset == quote_asset
        # Client is trading quote asset (e.g., USDT on BTCUSDT)
        if side == 'BUY':
            # Client buys quote from us -> we sell base to get quote
            exchange_side = 'SELL'

            if profit_asset == 'base':
                # Keep profit in BTC - sell only enough base to get exact USDT for client
                quantity = quote.client_receives_amount / market_price
                quote_qty = None
            else:
                # Keep profit in USDT - sell all base to get more USDT
                quantity = quote.client_gives_amount
                quote_qty = None
        else:
            # Client sells quote to us -> we buy base with quote
            exchange_side = 'BUY'

            if profit_asset == 'base':
                # Keep profit in BTC - spend all USDT to buy more BTC
                quantity = None
                quote_qty = quote.client_gives_amount
            else:
                # Keep profit in USDT - buy only exact BTC needed for client
                quantity = quote.client_receives_amount
                quote_qty = None

    return exchange_side, quantity, quote_qty


def format_hedge_params(
    exchange_side: str,
    quantity: Optional[float],
    quote_qty: Optional[float],
    base_asset: str,
    quote_asset: str
) -> str:
    """
    Format hedge parameters for display.

    Args:
        exchange_side: Exchange order side
        quantity: Base asset quantity
        quote_qty: Quote asset quantity
        base_asset: Base asset symbol
        quote_asset: Quote asset symbol

    Returns:
        Formatted string
    """
    if quantity is not None:
        return f"{exchange_side} {quantity:.8f} {base_asset}"
    else:
        return f"{exchange_side} {quote_qty:.8f} {quote_asset} worth of {base_asset}"
