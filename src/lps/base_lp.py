"""
Base interface for Liquidity Provider integrations.

All LP implementations must inherit from LiquidityProvider.
"""

from abc import ABC, abstractmethod
from typing import Optional
from ..core.models import QuoteRequest, LPQuote, AggregatedQuote


class LiquidityProvider(ABC):
    """Base class for all LP integrations"""

    @abstractmethod
    async def request_quote(self, request: QuoteRequest) -> Optional[LPQuote]:
        """
        Request a quote from this LP.

        Args:
            request: Quote request with side, amount, pair

        Returns:
            LPQuote if successful, None if LP cannot quote
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return unique LP identifier"""
        pass

    @abstractmethod
    async def execute_trade(self, quote: LPQuote, client_quote: AggregatedQuote) -> bool:
        """
        Execute trade with this LP.

        Args:
            quote: Original LP quote
            client_quote: Aggregated quote shown to client

        Returns:
            True if execution successful
        """
        pass
