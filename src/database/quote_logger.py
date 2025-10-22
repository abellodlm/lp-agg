"""
Quote Logger - Database logging for LP Aggregation RFQ System.

Logs all quotes, LP responses, and performance metrics to SQLite database.
"""

import sqlite3
import json
import time
from typing import List, Optional, Dict, Any
from ..core.models import AggregatedQuote, LPQuote


class QuoteLogger:
    """
    Logs quote data to SQLite database.

    Provides methods for:
    - Logging aggregated quotes
    - Logging individual LP quotes
    - Tracking LP performance
    - Querying historical data
    """

    def __init__(self, db_path: str):
        """
        Initialize QuoteLogger.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries

    def log_quote(
        self,
        quote: AggregatedQuote,
        all_lp_quotes: List[LPQuote],
        poll_num: int,
        is_improvement: bool,
        locked_lp_name: Optional[str]
    ) -> None:
        """
        Log an aggregated quote to the database.

        Args:
            quote: Aggregated quote shown to client
            all_lp_quotes: All LP quotes received in this poll
            poll_num: Current poll number
            is_improvement: Whether this quote is an improvement
            locked_lp_name: Name of currently locked LP
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO quotes (
                    quote_id, side, base_asset, quote_asset, target_asset, amount,
                    client_price, lp_price, lp_name, markup_bps,
                    validity_seconds, is_improvement, locked_lp_name,
                    poll_number, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quote.quote_id,
                quote.side,
                quote.base_asset,
                quote.quote_asset,
                quote.target_asset,
                quote.amount,
                quote.client_price,
                quote.lp_price,
                quote.lp_name,
                quote.markup_bps,
                quote.validity_seconds,
                1 if is_improvement else 0,
                locked_lp_name,
                poll_num,
                quote.created_at
            ))

            self.conn.commit()

            # Log all LP quotes
            self.log_lp_quotes(quote.quote_id, all_lp_quotes)

            # Update LP performance for the winning LP
            self.update_lp_performance(quote.lp_name, won=True, price=quote.lp_price)

            # Update performance for losing LPs
            for lp_quote in all_lp_quotes:
                if lp_quote.lp_name != quote.lp_name:
                    self.update_lp_performance(lp_quote.lp_name, won=False, price=lp_quote.price)

        except sqlite3.IntegrityError as e:
            # Quote ID already exists (duplicate), skip
            pass
        except Exception as e:
            print(f"[QuoteLogger] Error logging quote: {e}")
            self.conn.rollback()

    def log_lp_quotes(self, quote_id: str, lp_quotes: List[LPQuote]) -> None:
        """
        Log individual LP quotes.

        Args:
            quote_id: ID of the parent aggregated quote
            lp_quotes: List of LP quotes to log
        """
        cursor = self.conn.cursor()

        for lp_quote in lp_quotes:
            try:
                # Calculate response time if available
                response_time_ms = None
                if lp_quote.metadata and 'delay_ms' in lp_quote.metadata:
                    response_time_ms = lp_quote.metadata['delay_ms']

                # Serialize metadata to JSON
                metadata_json = json.dumps(lp_quote.metadata) if lp_quote.metadata else None

                cursor.execute("""
                    INSERT INTO lp_quotes (
                        quote_id, lp_name, price, quantity,
                        validity_seconds, response_time_ms, timestamp,
                        side, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    quote_id,
                    lp_quote.lp_name,
                    lp_quote.price,
                    lp_quote.quantity,
                    lp_quote.validity_seconds,
                    response_time_ms,
                    lp_quote.timestamp,
                    lp_quote.side,
                    metadata_json
                ))

            except Exception as e:
                print(f"[QuoteLogger] Error logging LP quote for {lp_quote.lp_name}: {e}")

        self.conn.commit()

    def update_lp_performance(
        self,
        lp_name: str,
        won: bool,
        price: float,
        response_time_ms: Optional[float] = None
    ) -> None:
        """
        Update LP performance metrics.

        Args:
            lp_name: Name of the LP
            won: Whether this LP won the poll
            price: Price quoted by the LP
            response_time_ms: Response time in milliseconds (optional)
        """
        cursor = self.conn.cursor()

        try:
            # Check if LP exists
            cursor.execute("SELECT * FROM lp_performance WHERE lp_name = ?", (lp_name,))
            existing = cursor.fetchone()

            if existing:
                # Update existing record
                total_quotes = existing['total_quotes'] + 1
                total_wins = existing['total_wins'] + (1 if won else 0)
                win_rate = (total_wins / total_quotes) * 100

                # Update average response time
                if response_time_ms:
                    if existing['avg_response_time_ms']:
                        avg_response_time_ms = (
                            (existing['avg_response_time_ms'] * existing['total_quotes'] + response_time_ms) /
                            total_quotes
                        )
                    else:
                        avg_response_time_ms = response_time_ms
                else:
                    avg_response_time_ms = existing['avg_response_time_ms']

                # Update best/worst prices
                best_price = min(price, existing['best_price']) if existing['best_price'] else price
                worst_price = max(price, existing['worst_price']) if existing['worst_price'] else price

                cursor.execute("""
                    UPDATE lp_performance
                    SET total_quotes = ?,
                        total_wins = ?,
                        win_rate = ?,
                        avg_response_time_ms = ?,
                        best_price = ?,
                        worst_price = ?,
                        last_updated = ?
                    WHERE lp_name = ?
                """, (
                    total_quotes,
                    total_wins,
                    win_rate,
                    avg_response_time_ms,
                    best_price,
                    worst_price,
                    time.time(),
                    lp_name
                ))

            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO lp_performance (
                        lp_name, total_quotes, total_wins, win_rate,
                        avg_response_time_ms, best_price, worst_price, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lp_name,
                    1,
                    1 if won else 0,
                    100.0 if won else 0.0,
                    response_time_ms,
                    price,
                    price,
                    time.time()
                ))

            self.conn.commit()

        except Exception as e:
            print(f"[QuoteLogger] Error updating LP performance for {lp_name}: {e}")
            self.conn.rollback()

    def get_recent_quotes(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent aggregated quotes.

        Args:
            limit: Maximum number of quotes to return

        Returns:
            List of quote dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM quotes
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def get_lp_stats(self, lp_name: str) -> Optional[Dict[str, Any]]:
        """
        Get performance stats for a specific LP.

        Args:
            lp_name: Name of the LP

        Returns:
            Dictionary of performance metrics, or None if LP not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM lp_performance
            WHERE lp_name = ?
        """, (lp_name,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_lp_stats(self) -> List[Dict[str, Any]]:
        """
        Get performance stats for all LPs.

        Returns:
            List of LP performance dictionaries, sorted by win rate
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM lp_performance
            ORDER BY win_rate DESC
        """)

        return [dict(row) for row in cursor.fetchall()]

    def get_quote_history(
        self,
        lp_name: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get quote history with optional filters.

        Args:
            lp_name: Filter by LP name (optional)
            start_time: Filter by start timestamp (optional)
            end_time: Filter by end timestamp (optional)
            limit: Maximum number of results

        Returns:
            List of quote dictionaries
        """
        cursor = self.conn.cursor()

        query = "SELECT * FROM quotes WHERE 1=1"
        params = []

        if lp_name:
            query += " AND lp_name = ?"
            params.append(lp_name)

        if start_time:
            query += " AND created_at >= ?"
            params.append(start_time)

        if end_time:
            query += " AND created_at <= ?"
            params.append(end_time)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Ensure connection is closed on deletion."""
        self.close()
