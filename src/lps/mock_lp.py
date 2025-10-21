"""
Mock LP implementation for testing and development.

Returns simulated quotes with configurable behavior.
"""

import asyncio
import random
import time
from typing import Optional
from .base_lp import LiquidityProvider
from ..core.models import QuoteRequest, LPQuote, AggregatedQuote


class MockLP(LiquidityProvider):
    """
    Mock LP for testing and development.
    Returns random quotes with configurable behavior.
    """

    def __init__(
        self,
        name: str,
        base_price: float = 100000.0,
        spread_bps: float = 5.0,
        response_delay: tuple = (0.1, 0.5),
        failure_rate: float = 0.0
    ):
        """
        Args:
            name: LP identifier
            base_price: Base price to quote around
            spread_bps: Bid/ask spread in basis points
            response_delay: (min, max) response time in seconds
            failure_rate: Probability of failing to return quote (0.0-1.0)
        """
        self.name = name
        self.base_price = base_price
        self.spread_bps = spread_bps
        self.response_delay = response_delay
        self.failure_rate = failure_rate

    async def request_quote(self, request: QuoteRequest) -> Optional[LPQuote]:
        """Simulate LP quote request"""

        # Simulate network delay
        delay = random.uniform(*self.response_delay)
        await asyncio.sleep(delay)

        # Simulate occasional failures
        if random.random() < self.failure_rate:
            return None

        # Generate price with random variation
        variation = random.uniform(-0.01, 0.01)  # ±1%
        mid_price = self.base_price * (1 + variation)

        # Apply spread based on side
        if request.side == 'BUY':
            # Client buying = we sell = ask price
            price = mid_price * (1 + self.spread_bps / 10000)
        else:
            # Client selling = we buy = bid price
            price = mid_price * (1 - self.spread_bps / 10000)

        return LPQuote(
            lp_name=self.name,
            price=price,
            quantity=request.amount,
            validity_seconds=10.0,
            timestamp=time.time(),
            side=request.side,
            metadata={
                'variation_pct': variation * 100,
                'delay_ms': delay * 1000
            }
        )

    def get_name(self) -> str:
        return self.name

    async def execute_trade(self, quote: LPQuote, client_quote: AggregatedQuote) -> bool:
        """Simulate trade execution"""
        # Simulate execution delay
        await asyncio.sleep(random.uniform(0.2, 0.5))

        # Check if quote is still valid
        if quote.is_expired():
            print(f"[{self.name}] Quote expired, cannot execute")
            return False

        print(f"[{self.name}] Trade executed successfully")
        return True
