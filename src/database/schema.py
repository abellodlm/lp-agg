"""
Database schema for LP Aggregation RFQ System.

Defines tables for:
- quotes: Aggregated quotes shown to client
- lp_quotes: Individual LP responses
- lp_performance: LP performance metrics
"""

import sqlite3
from pathlib import Path


def init_database(db_path: str) -> None:
    """
    Initialize database and create tables if they don't exist.

    Args:
        db_path: Path to SQLite database file
    """
    # Create directory if it doesn't exist
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create quotes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id TEXT UNIQUE NOT NULL,
            side TEXT NOT NULL,
            base_asset TEXT NOT NULL,
            quote_asset TEXT NOT NULL,
            amount REAL NOT NULL,
            client_price REAL NOT NULL,
            lp_price REAL NOT NULL,
            lp_name TEXT NOT NULL,
            markup_bps REAL NOT NULL,
            validity_seconds REAL NOT NULL,
            is_improvement INTEGER NOT NULL,
            locked_lp_name TEXT,
            poll_number INTEGER NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    # Create indexes for quotes table
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_quotes_created_at
        ON quotes(created_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_quotes_lp_name
        ON quotes(lp_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_quotes_quote_id
        ON quotes(quote_id)
    """)

    # Create lp_quotes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lp_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id TEXT NOT NULL,
            lp_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity REAL NOT NULL,
            validity_seconds REAL NOT NULL,
            response_time_ms REAL,
            timestamp REAL NOT NULL,
            side TEXT NOT NULL,
            metadata TEXT,
            FOREIGN KEY (quote_id) REFERENCES quotes(quote_id)
        )
    """)

    # Create indexes for lp_quotes table
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_lp_quotes_quote_id
        ON lp_quotes(quote_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_lp_quotes_lp_name
        ON lp_quotes(lp_name)
    """)

    # Create lp_performance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lp_performance (
            lp_name TEXT PRIMARY KEY,
            total_quotes INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            avg_response_time_ms REAL,
            best_price REAL,
            worst_price REAL,
            last_updated REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    print(f"[Database] Initialized at {db_path}")
