"""
Quote Streamer - Continuously polls LPs for price improvements with quote locking.

Streams quote updates to callback when better prices are found.
Implements quote locking: once an LP wins, they're not polled again until beaten.
"""

import asyncio
from typing import Callable, Optional, List, TYPE_CHECKING
from .lp_aggregator import LPAggregator
from .models import QuoteRequest, AggregatedQuote, LPQuote

if TYPE_CHECKING:
    from ..database.quote_logger import QuoteLogger


class QuoteStreamer:
    """
    Continuously polls LPs and streams quote improvements.

    Quote Locking Flow:
    1. Initial poll: Get quotes from ALL LPs
    2. Lock winner: Best LP's quote is "locked" (frozen)
    3. Poll competitors: Only poll non-locked LPs
    4. On improvement: If competitor beats locked by ≥1bp, switch winner
    5. Competitive re-polling: Previous winners can compete again (Option A)
    """

    def __init__(self, aggregator: LPAggregator, poll_interval_ms: int = 500,
                 improvement_threshold_bps: float = 1.0,
                 quote_logger: Optional['QuoteLogger'] = None):
        """
        Args:
            aggregator: LP aggregator instance
            poll_interval_ms: How often to poll LPs (milliseconds)
            improvement_threshold_bps: Minimum improvement to switch quotes (basis points)
            quote_logger: Optional database logger for quotes
        """
        self.aggregator = aggregator
        self.poll_interval_ms = poll_interval_ms
        self.improvement_threshold_bps = improvement_threshold_bps
        self.quote_logger = quote_logger
        self.streaming = False

        # Quote locking state
        self.locked_lp_name: Optional[str] = None  # Currently locked LP
        self.locked_quote: Optional[AggregatedQuote] = None  # Frozen locked quote
        self.locked_lp_quote: Optional[LPQuote] = None  # Original LP quote (for display)

    async def stream_quotes(
        self,
        request: QuoteRequest,
        on_quote_update: Callable[[List[LPQuote], AggregatedQuote, int, bool, Optional[str]], None],
        duration_seconds: float = None,
        auto_refresh: bool = False
    ):
        """
        Stream quotes with locking logic.

        Args:
            request: Quote request to stream
            on_quote_update: Callback(all_lp_quotes, best_quote, poll_count, is_improvement, locked_lp_name)
            duration_seconds: How long to stream (None = until quote expires or manual stop)
            auto_refresh: If True, automatically request new quote when expired
        """
        self.streaming = True
        self.locked_lp_name = None
        self.locked_quote = None
        self.locked_lp_quote = None

        poll_count = 0
        start_time = asyncio.get_event_loop().time()

        # FIRST POLL: Get quotes from ALL LPs
        poll_count += 1
        all_lp_quotes, best_quote = await self.aggregator.get_all_quotes(request)

        if not best_quote:
            print("[!] No quotes received from LPs")
            self.streaming = False
            return

        # LOCK THE WINNER
        self.locked_lp_name = best_quote.lp_name
        self.locked_quote = best_quote
        # Find the original LP quote for this winner
        self.locked_lp_quote = next((q for q in all_lp_quotes if q.lp_name == best_quote.lp_name), None)

        # Callback with initial locked quote
        on_quote_update(all_lp_quotes, best_quote, poll_count, True, self.locked_lp_name)

        # Log to database if logger is available
        if self.quote_logger:
            self.quote_logger.log_quote(best_quote, all_lp_quotes, poll_count, True, self.locked_lp_name)

        # SUBSEQUENT POLLS: Poll only competitors
        loop_count = 0
        while self.streaming:
            loop_count += 1

            # Wait before next poll
            await asyncio.sleep(self.poll_interval_ms / 1000)

            # Check expiry before polling (use time_remaining to match monitor display)
            if self.locked_quote.time_remaining() <= 0:
                if auto_refresh:
                    # Auto-refresh: Request fresh quote from ALL LPs
                    poll_count = 0  # Reset poll count
                    poll_count += 1
                    all_lp_quotes, best_quote = await self.aggregator.get_all_quotes(request)

                    if not best_quote:
                        print("[!] No quotes received from LPs on auto-refresh")
                        break

                    # Lock the new winner
                    self.locked_lp_name = best_quote.lp_name
                    self.locked_quote = best_quote
                    self.locked_lp_quote = next((q for q in all_lp_quotes if q.lp_name == best_quote.lp_name), None)

                    # Callback with new locked quote
                    on_quote_update(all_lp_quotes, best_quote, poll_count, True, self.locked_lp_name)

                    # Log to database if logger is available
                    if self.quote_logger:
                        self.quote_logger.log_quote(best_quote, all_lp_quotes, poll_count, True, self.locked_lp_name)

                    continue
                else:
                    # Stop streaming if quote expired
                    break

            poll_count += 1

            # Poll only non-locked LPs
            competitor_quotes, best_competitor = await self.aggregator.get_quotes_excluding(
                self.locked_lp_name, request
            )

            # Re-check expiry AFTER polling (locked quote may have expired during poll)
            if self.locked_quote.time_remaining() <= 0:
                if auto_refresh:
                    # Auto-refresh: Request fresh quote from ALL LPs
                    poll_count = 0  # Reset poll count
                    poll_count += 1
                    all_lp_quotes, best_quote = await self.aggregator.get_all_quotes(request)

                    if not best_quote:
                        print("[!] No quotes received from LPs on auto-refresh")
                        break

                    # Lock the new winner
                    self.locked_lp_name = best_quote.lp_name
                    self.locked_quote = best_quote
                    self.locked_lp_quote = next((q for q in all_lp_quotes if q.lp_name == best_quote.lp_name), None)

                    # Callback with new locked quote
                    on_quote_update(all_lp_quotes, best_quote, poll_count, True, self.locked_lp_name)

                    # Log to database if logger is available
                    if self.quote_logger:
                        self.quote_logger.log_quote(best_quote, all_lp_quotes, poll_count, True, self.locked_lp_name)

                    continue
                else:
                    # Stop streaming if quote expired
                    break

            # Check if any competitor beats the locked quote
            is_improvement = False
            if best_competitor and self._is_meaningful_improvement(best_competitor, request.side):
                # IMPROVEMENT! Switch to new winner
                old_locked_lp = self.locked_lp_name
                old_locked_lp_quote = self.locked_lp_quote  # Save old LP quote for display

                # Lock new winner
                self.locked_lp_name = best_competitor.lp_name
                self.locked_quote = best_competitor
                self.locked_lp_quote = next((q for q in competitor_quotes if q.lp_name == best_competitor.lp_name), None)

                is_improvement = True

                # For display: include old locked LP's frozen quote in all_quotes
                # (so it appears in leaderboard as available for re-polling)
                if old_locked_lp_quote:
                    all_display_quotes = competitor_quotes + [old_locked_lp_quote]
                else:
                    all_display_quotes = competitor_quotes

                on_quote_update(all_display_quotes, best_competitor, poll_count, is_improvement, self.locked_lp_name)

                # Log to database if logger is available
                if self.quote_logger:
                    self.quote_logger.log_quote(best_competitor, all_display_quotes, poll_count, is_improvement, self.locked_lp_name)
            else:
                # No improvement, keep locked quote
                # Display competitors + frozen locked LP quote
                if self.locked_lp_quote:
                    all_display_quotes = competitor_quotes + [self.locked_lp_quote]
                else:
                    all_display_quotes = competitor_quotes

                on_quote_update(all_display_quotes, self.locked_quote, poll_count, False, self.locked_lp_name)

                # Log to database if logger is available (non-improvement polls also logged)
                if self.quote_logger:
                    self.quote_logger.log_quote(self.locked_quote, all_display_quotes, poll_count, False, self.locked_lp_name)

            # Check duration limit if specified
            if duration_seconds is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= duration_seconds:
                    break

        self.streaming = False

    def _is_meaningful_improvement(self, new_quote: AggregatedQuote, side: str) -> bool:
        """
        Check if new quote beats locked quote by at least IMPROVEMENT_THRESHOLD_BPS.

        For BUY: new_price <= locked_price - threshold
        For SELL: new_price >= locked_price + threshold

        Args:
            new_quote: New quote from competitor
            side: 'BUY' or 'SELL'

        Returns:
            True if improvement is meaningful (≥1bp)
        """
        if not self.locked_quote:
            return True

        # Calculate threshold in price terms
        threshold = self.locked_quote.client_price * (self.improvement_threshold_bps / 10000)

        if side == 'BUY':
            # For BUY, lower price is better
            return new_quote.client_price <= (self.locked_quote.client_price - threshold)
        else:  # SELL
            # For SELL, higher price is better
            return new_quote.client_price >= (self.locked_quote.client_price + threshold)

    def stop(self):
        """Stop streaming"""
        self.streaming = False

    def get_locked_quote(self) -> Optional[AggregatedQuote]:
        """Get currently locked quote"""
        return self.locked_quote

    def get_locked_lp_name(self) -> Optional[str]:
        """Get currently locked LP name"""
        return self.locked_lp_name
