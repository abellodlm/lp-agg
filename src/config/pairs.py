"""
Trading pair configurations for LP Aggregation RFQ System.

Defines all supported trading pairs with their specific parameters,
including profit asset preferences and decimal precision.
"""

from dataclasses import dataclass
from typing import Dict, Literal


@dataclass
class TradingPairConfig:
    """Configuration for a trading pair."""
    symbol: str  # e.g., 'BTCUSDT'
    base_asset: str  # e.g., 'BTC'
    quote_asset: str  # e.g., 'USDT'
    default_markup_bps: float
    base_decimals: int  # Decimal places for base asset
    quote_decimals: int  # Decimal places for quote asset
    min_amount: float  # Minimum order amount
    profit_asset: Literal['base', 'quote']  # Which asset to keep spread profit in

    def format_base_amount(self, amount: float) -> str:
        """Format base asset amount with correct decimals."""
        return f"{amount:,.{self.base_decimals}f}"

    def format_quote_amount(self, amount: float) -> str:
        """Format quote asset amount with correct decimals."""
        return f"{amount:,.{self.quote_decimals}f}"

    def round_base_quantity(self, amount: float) -> str:
        """
        Round base asset quantity to correct precision.

        Args:
            amount: Raw quantity amount

        Returns:
            Formatted string with correct decimals, trailing zeros removed
        """
        rounded = round(amount, self.base_decimals)
        formatted = f"{rounded:.{self.base_decimals}f}".rstrip('0').rstrip('.')
        return formatted

    def round_quote_quantity(self, amount: float) -> str:
        """
        Round quote asset quantity to correct precision.

        Args:
            amount: Raw quantity amount

        Returns:
            Formatted string with correct decimals, trailing zeros removed
        """
        rounded = round(amount, self.quote_decimals)
        formatted = f"{rounded:.{self.quote_decimals}f}".rstrip('0').rstrip('.')
        return formatted


# Supported trading pairs
SUPPORTED_PAIRS: Dict[str, TradingPairConfig] = {
    'BTCUSDT': TradingPairConfig(
        symbol='BTCUSDT',
        base_asset='BTC',
        quote_asset='USDT',
        default_markup_bps=5.0,
        base_decimals=5,
        quote_decimals=2,
        min_amount=0.001,
        profit_asset='quote'  # Keep profit in USDT
    ),
    'ETHUSDT': TradingPairConfig(
        symbol='ETHUSDT',
        base_asset='ETH',
        quote_asset='USDT',
        default_markup_bps=5.0,
        base_decimals=4,
        quote_decimals=2,
        min_amount=0.01,
        profit_asset='quote'  # Keep profit in USDT
    ),
    'USDCUSDT': TradingPairConfig(
        symbol='USDCUSDT',
        base_asset='USDC',
        quote_asset='USDT',
        default_markup_bps=3.0,  # Lower markup for stablecoin pair
        base_decimals=2,
        quote_decimals=4,
        min_amount=10.0,
        profit_asset='quote'  # Keep profit in USDT
    ),
}


def get_pair_config(symbol: str) -> TradingPairConfig:
    """
    Get configuration for a trading pair.

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')

    Returns:
        TradingPairConfig for the pair

    Raises:
        ValueError: If pair is not supported
    """
    symbol_upper = symbol.upper()
    if symbol_upper not in SUPPORTED_PAIRS:
        raise ValueError(
            f"Unsupported trading pair: {symbol}. "
            f"Supported: {list(SUPPORTED_PAIRS.keys())}"
        )

    return SUPPORTED_PAIRS[symbol_upper]


def parse_pair(pair_str: str) -> tuple[str, str]:
    """
    Parse a pair string into base and quote assets.

    Args:
        pair_str: Pair string like 'BTCUSDT' or 'btcusdt'

    Returns:
        Tuple of (base_asset, quote_asset)

    Raises:
        ValueError: If pair format is invalid or unsupported
    """
    config = get_pair_config(pair_str)
    return config.base_asset, config.quote_asset
