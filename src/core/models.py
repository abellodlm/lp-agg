"""
Core data models for LP Aggregation RFQ System.

Defines the structure for quote requests, LP quotes, and aggregated quotes.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
from datetime import datetime
import time


@dataclass
class QuoteRequest:
    """Request sent to LPs for pricing"""
    side: str  # 'BUY' or 'SELL'
    amount: float
    base_asset: str  # e.g., 'BTC'
    quote_asset: str  # e.g., 'USDT'
    timestamp: float = field(default_factory=time.time)

    def __str__(self):
        return f"{self.side} {self.amount} {self.base_asset}/{self.quote_asset}"


@dataclass
class LPQuote:
    """Quote received from a single LP"""
    lp_name: str
    price: float
    quantity: float  # Max quantity LP can provide
    validity_seconds: float  # How long quote is valid
    timestamp: float
    side: str
    metadata: Optional[Dict] = None

    def is_expired(self) -> bool:
        """Check if quote has expired"""
        return (time.time() - self.timestamp) > self.validity_seconds

    def time_remaining(self) -> float:
        """Seconds remaining before expiry"""
        elapsed = time.time() - self.timestamp
        return max(0, self.validity_seconds - elapsed)


@dataclass
class AggregatedQuote:
    """Final quote shown to client (LP quote + markup)"""
    quote_id: str

    # Pricing
    client_price: float      # Price shown to client (after markup)
    lp_price: float          # Original LP price (before markup)
    lp_name: str             # Which LP provided this quote
    markup_bps: float        # Markup applied

    # Trade details
    side: str
    amount: float
    base_asset: str
    quote_asset: str

    # Client flows
    client_gives_amount: float
    client_gives_asset: str
    client_receives_amount: float
    client_receives_asset: str

    # Validity
    validity_seconds: float
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if client quote has expired"""
        return (time.time() - self.created_at) > self.validity_seconds

    def time_remaining(self) -> float:
        """Seconds remaining for client"""
        elapsed = time.time() - self.created_at
        return max(0, self.validity_seconds - elapsed)

    @staticmethod
    def generate_id() -> str:
        """Generate unique quote ID"""
        return f"Q{datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:19]}"
