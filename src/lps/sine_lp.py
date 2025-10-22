"""
Sine Wave LP Implementation - Realistic Price Competition

Provides quotes that oscillate according to a sine wave pattern,
creating realistic price competition between multiple LPs.

Based on _sine_price.py reference implementation.
"""

import asyncio
import math
import time
from typing import Optional
from .base_lp import LiquidityProvider
from ..core.models import QuoteRequest, LPQuote, AggregatedQuote


class SineLPProvider(LiquidityProvider):
    """
    LP that provides quotes following a sine wave price pattern.

    This creates realistic price competition where different LPs
    have the best price at different times.

    Price formula:
        price(t) = base_price + amplitude * sin(2π * frequency * t + phase) + trend * t

    Example with 3 LPs:
        LP-1: phase = 0.0      (starts at mid-point, rising)
        LP-2: phase = π/2      (starts at peak)
        LP-3: phase = π        (starts at mid-point, falling)
    """

    def __init__(
        self,
        name: str,
        base_price: float = 100000.0,
        amplitude: float = 100.0,
        frequency: float = 0.05,
        phase: float = 0.0,
        trend: float = -10.0,
        spread_bps: float = 5.0,
        response_delay: tuple = (0.1, 0.3)
    ):
        """
        Args:
            name: LP identifier
            base_price: Base price around which to oscillate
            amplitude: Peak deviation from base price
            frequency: Oscillation frequency (Hz)
            phase: Phase offset in radians (0, π/2, π for 3 LPs)
            trend: Linear price trend per second
            spread_bps: Bid/ask spread in basis points
            response_delay: (min, max) response time in seconds
        """
        self.name = name
        self.base_price = base_price
        self.amplitude = amplitude
        self.frequency = frequency
        self.phase = phase
        self.trend = trend
        self.spread_bps = spread_bps
        self.response_delay = response_delay
        self.start_time = time.time()

    def _calculate_mid_price(self) -> float:
        """
        Calculate current mid price based on sine wave.

        Returns:
            Current mid price
        """
        elapsed = time.time() - self.start_time
        price = (
            self.base_price
            + self.amplitude * math.sin(2 * math.pi * self.frequency * elapsed + self.phase)
            + self.trend * elapsed
        )
        return price

    async def request_quote(self, request: QuoteRequest) -> Optional[LPQuote]:
        """
        Generate quote based on sine wave price pattern.

        Args:
            request: Quote request from client

        Returns:
            LP quote or None if unable to provide
        """
        # Simulate network delay
        import random
        delay = random.uniform(*self.response_delay)
        await asyncio.sleep(delay)

        # Get current mid price from sine wave
        mid_price = self._calculate_mid_price()

        # Apply spread based on side
        if request.side == 'BUY':
            # Client buying = we sell = ask price (add spread)
            price = mid_price * (1 + self.spread_bps / 10000)
        else:  # SELL
            # Client selling = we buy = bid price (subtract spread)
            price = mid_price * (1 - self.spread_bps / 10000)

        return LPQuote(
            lp_name=self.name,
            price=price,
            quantity=request.amount * 2,  # Can handle 2x the request size
            validity_seconds=10.0,
            timestamp=time.time(),
            side=request.side,
            metadata={
                'mid_price': mid_price,
                'spread_bps': self.spread_bps,
                'delay_ms': delay * 1000,
                'phase': self.phase,
                'elapsed': time.time() - self.start_time
            }
        )

    def get_name(self) -> str:
        """Get LP name"""
        return self.name

    async def execute_trade(self, quote: LPQuote, client_quote: AggregatedQuote) -> bool:
        """
        Simulate trade execution.

        Args:
            quote: LP quote
            client_quote: Aggregated client quote

        Returns:
            True if execution succeeds
        """
        # Simulate execution delay
        import random
        await asyncio.sleep(random.uniform(0.2, 0.5))

        # Check if quote is still valid
        if quote.is_expired():
            print(f"[{self.name}] Quote expired, cannot execute")
            return False

        print(f"[{self.name}] Trade executed at {quote.price:.2f}")
        return True
