"""
LP Aggregator - Core quote aggregation logic.

Pings multiple LPs concurrently, selects best quote, and applies markup.
"""

import asyncio
from typing import List, Optional
from .models import QuoteRequest, LPQuote, AggregatedQuote
from ..lps.base_lp import LiquidityProvider


class LPAggregator:
    """
    Core aggregation engine.

    Responsibilities:
    - Ping multiple LPs concurrently
    - Select best quote
    - Apply markup
    - Return aggregated quote for client
    """

    def __init__(
        self,
        lps: List[LiquidityProvider],
        markup_bps: float = 5.0,
        validity_buffer_seconds: float = 2.0
    ):
        """
        Args:
            lps: List of LP instances
            markup_bps: Markup to add on top of LP quotes
            validity_buffer_seconds: Buffer to reduce LP validity for client
        """
        self.lps = lps
        self.markup_bps = markup_bps
        self.validity_buffer = validity_buffer_seconds

    async def get_all_quotes(self, request: QuoteRequest) -> tuple[List[LPQuote], Optional[AggregatedQuote]]:
        """
        Request quotes from all LPs and return both all quotes and best aggregated quote.

        Args:
            request: Quote request

        Returns:
            Tuple of (all_lp_quotes, best_aggregated_quote)
            Returns ([], None) if no valid quotes received
        """
        # Request quotes from all LPs concurrently
        tasks = [lp.request_quote(request) for lp in self.lps]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter valid quotes (ignore errors and None)
        valid_quotes = []
        for result in results:
            if isinstance(result, LPQuote) and result is not None:
                valid_quotes.append(result)
            elif isinstance(result, Exception):
                print(f"LP error: {result}")

        if not valid_quotes:
            return [], None

        # Select best quote based on side
        best_lp_quote = self._select_best(valid_quotes, request.side)

        # Apply markup and create aggregated quote
        best_aggregated = self._create_aggregated_quote(best_lp_quote, request)

        return valid_quotes, best_aggregated

    async def get_quotes_excluding(
        self,
        excluded_lp_name: str,
        request: QuoteRequest
    ) -> tuple[List[LPQuote], Optional[AggregatedQuote]]:
        """
        Request quotes from all LPs EXCEPT the excluded one.

        Used for quote locking: poll competitors while keeping locked LP's quote.

        Args:
            excluded_lp_name: LP name to exclude from polling
            request: Quote request

        Returns:
            Tuple of (competitor_lp_quotes, best_competitor_quote)
            Returns ([], None) if no valid quotes received
        """
        # Get LPs excluding the locked one
        competitor_lps = [lp for lp in self.lps if lp.get_name() != excluded_lp_name]

        if not competitor_lps:
            return [], None

        # Request quotes from competitors only
        tasks = [lp.request_quote(request) for lp in competitor_lps]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter valid quotes
        valid_quotes = []
        for result in results:
            if isinstance(result, LPQuote) and result is not None:
                valid_quotes.append(result)
            elif isinstance(result, Exception):
                print(f"LP error: {result}")

        if not valid_quotes:
            return [], None

        # Select best from competitors
        best_lp_quote = self._select_best(valid_quotes, request.side)

        # Apply markup and create aggregated quote
        best_aggregated = self._create_aggregated_quote(best_lp_quote, request)

        return valid_quotes, best_aggregated

    async def get_best_quote(self, request: QuoteRequest) -> Optional[AggregatedQuote]:
        """
        Request quotes from all LPs and return best with markup.

        Args:
            request: Quote request

        Returns:
            AggregatedQuote with best LP price + markup, or None if no quotes
        """
        _, best_quote = await self.get_all_quotes(request)
        return best_quote

    def _select_best(self, quotes: List[LPQuote], side: str) -> LPQuote:
        """
        Select best quote from list.

        For BUY: lowest ask (client pays less)
        For SELL: highest bid (client receives more)
        """
        if side == 'BUY':
            return min(quotes, key=lambda q: q.price)
        else:  # SELL
            return max(quotes, key=lambda q: q.price)

    def _create_aggregated_quote(
        self,
        lp_quote: LPQuote,
        request: QuoteRequest
    ) -> AggregatedQuote:
        """
        Apply markup to LP quote and create client quote.
        """
        # Apply markup
        if request.side == 'BUY':
            # Client buying: add markup to price
            client_price = lp_quote.price * (1 + self.markup_bps / 10000)
        else:  # SELL
            # Client selling: subtract markup from price
            client_price = lp_quote.price * (1 - self.markup_bps / 10000)

        # Calculate client flows
        if request.side == 'BUY':
            # Client buys base, pays quote
            client_gives_amount = request.amount * client_price
            client_gives_asset = request.quote_asset
            client_receives_amount = request.amount
            client_receives_asset = request.base_asset
        else:  # SELL
            # Client sells base, receives quote
            client_gives_amount = request.amount
            client_gives_asset = request.base_asset
            client_receives_amount = request.amount * client_price
            client_receives_asset = request.quote_asset

        # Reduce validity for client (safety buffer)
        client_validity = max(
            lp_quote.validity_seconds - self.validity_buffer,
            3.0  # Minimum 3 seconds
        )

        return AggregatedQuote(
            quote_id=AggregatedQuote.generate_id(),
            client_price=client_price,
            lp_price=lp_quote.price,
            lp_name=lp_quote.lp_name,
            markup_bps=self.markup_bps,
            side=request.side,
            amount=request.amount,
            base_asset=request.base_asset,
            quote_asset=request.quote_asset,
            client_gives_amount=client_gives_amount,
            client_gives_asset=client_gives_asset,
            client_receives_amount=client_receives_amount,
            client_receives_asset=client_receives_asset,
            validity_seconds=client_validity
        )
