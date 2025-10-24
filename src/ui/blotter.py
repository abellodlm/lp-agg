"""
Execution Blotter - Real-time trade log display.

Shows executed trades with:
- Execution details (ID, timestamp, status)
- Trade information (side, pair, amounts, LP)
- P&L metrics (net P&L, basis points)
"""

import tkinter as tk
from tkinter import font
import sqlite3
import threading
from typing import Optional, List, Dict
from datetime import datetime


class ExecutionBlotter:
    """
    Real-time execution blotter component.

    Features:
    - Displays last 10 executions (no scrolling)
    - Auto-refresh from database (2 second polling)
    - Color-coded status and P&L
    - Thread-safe updates
    - Smart caching to prevent blinking
    """

    def __init__(self, parent_frame: tk.Frame, db_path: Optional[str] = None):
        """
        Initialize blotter with parent Tkinter frame and database path.

        Args:
            parent_frame: Parent Tkinter frame to attach blotter to
            db_path: Path to SQLite database (None = disabled)
        """
        self.parent_frame = parent_frame
        self.db_path = db_path
        self.running = False
        self.lock = threading.Lock()

        # Colors (consistent with monitor)
        self.bg_color = "#1e1e1e"
        self.fg_color = "#ffffff"
        self.accent_color = "#00d4aa"
        self.muted_color = "#888888"
        self.success_color = "#51cf66"
        self.failed_color = "#ff6b6b"
        self.positive_pnl_color = "#00d4aa"
        self.negative_pnl_color = "#ff6b6b"

        # Fonts
        self.header_font = font.Font(family="Consolas", size=11, weight="bold")
        self.row_font = font.Font(family="Consolas", size=9)
        self.tiny_font = font.Font(family="Consolas", size=8)

        # UI elements
        self.execution_rows = []  # List of (frame, labels) tuples
        self.scrollable_frame = None
        self.canvas = None
        self.empty_state_label = None  # Track empty state label

        # Cache for preventing unnecessary updates
        self.last_execution_ids = []  # Track which executions are displayed

        # Build UI
        self._build_ui()

        # Start auto-refresh if database is available
        if self.db_path:
            self.running = True
            self.parent_frame.after(2000, self._update_loop)  # Start after 2 seconds

    def _build_ui(self):
        """Build the blotter UI"""
        # Header
        header = tk.Label(
            self.parent_frame,
            text="EXECUTION BLOTTER",
            font=self.header_font,
            bg=self.bg_color,
            fg=self.accent_color
        )
        header.pack(pady=(0, 10))

        if not self.db_path:
            # Database disabled message
            msg = tk.Label(
                self.parent_frame,
                text="Database logging disabled",
                font=self.row_font,
                bg=self.bg_color,
                fg=self.muted_color
            )
            msg.pack(pady=20)
            return

        # Create container frame (no scrolling, just last 10 executions)
        container = tk.Frame(self.parent_frame, bg=self.bg_color)
        container.pack(fill='both', expand=True)

        self.scrollable_frame = tk.Frame(container, bg=self.bg_color)
        self.scrollable_frame.pack(fill='both', expand=True)

        # Column headers
        self._create_headers()

        # Initial empty state
        self._show_empty_state()

    def _create_headers(self):
        """Create column headers"""
        header_frame = tk.Frame(
            self.scrollable_frame,
            bg="#2a2a2a",
            height=30
        )
        header_frame.pack(fill='x', pady=(0, 5))
        header_frame.pack_propagate(False)

        # Configure grid columns
        header_frame.columnconfigure(0, weight=1, minsize=60)   # Time
        header_frame.columnconfigure(1, weight=1, minsize=45)   # Side
        header_frame.columnconfigure(2, weight=1, minsize=70)   # Pair
        header_frame.columnconfigure(3, weight=2, minsize=90)   # Client Price
        header_frame.columnconfigure(4, weight=2, minsize=90)   # Hedge Price
        header_frame.columnconfigure(5, weight=1, minsize=45)   # LP
        header_frame.columnconfigure(6, weight=2, minsize=100)  # P&L

        # Define columns
        columns = ["Time", "Side", "Pair", "Client", "Hedge", "LP", "P&L"]

        for idx, col_name in enumerate(columns):
            label = tk.Label(
                header_frame,
                text=col_name,
                font=self.header_font,
                bg="#2a2a2a",
                fg=self.accent_color,
                anchor='w'
            )
            label.grid(row=0, column=idx, sticky='w', padx=2, pady=5)

    def _show_empty_state(self):
        """Show 'No executions yet' message"""
        if self.empty_state_label is None:
            self.empty_state_label = tk.Label(
                self.scrollable_frame,
                text="No executions yet",
                font=self.row_font,
                bg=self.bg_color,
                fg=self.muted_color
            )
            self.empty_state_label.pack(pady=20)

    def _hide_empty_state(self):
        """Hide the empty state message"""
        if self.empty_state_label:
            self.empty_state_label.destroy()
            self.empty_state_label = None

    def _create_row(self, execution: Dict, row_index: int):
        """
        Create a single execution row.

        Args:
            execution: Execution data dictionary
            row_index: Row index (for alternating colors)
        """
        # Alternating row colors
        row_bg = "#252525" if row_index % 2 == 0 else self.bg_color

        row_frame = tk.Frame(
            self.scrollable_frame,
            bg=row_bg,
            height=50
        )
        row_frame.pack(fill='x', pady=1)
        row_frame.pack_propagate(False)

        # Format timestamp
        executed_at = execution.get('executed_at', 0)
        time_str = datetime.fromtimestamp(executed_at).strftime('%H:%M:%S')

        # Format side (use client side from quotes table, not exchange_side)
        client_side = execution.get('side', execution.get('exchange_side', '--'))

        # Format pair from joined quotes table
        base_asset = execution.get('base_asset', '?')
        quote_asset = execution.get('quote_asset', '?')
        pair_str = f"{base_asset}/{quote_asset}"

        # Format client price
        client_price = execution.get('client_price')
        if client_price is not None:
            client_price_str = f"{client_price:,.2f}"
        else:
            client_price_str = "--"

        # Format hedge price (avg_price from execution)
        hedge_price = execution.get('avg_price')
        if hedge_price is not None:
            hedge_price_str = f"{hedge_price:,.2f}"
        else:
            hedge_price_str = "--"

        # Format LP
        lp_name = execution.get('lp_name', '--')

        # Format P&L (in asset, not bps)
        pnl_after_fees = execution.get('pnl_after_fees')
        pnl_asset = execution.get('pnl_asset', '')
        status = execution.get('status', 'UNKNOWN')

        if status == 'SUCCESS' and pnl_after_fees is not None:
            # Determine precision based on asset
            if pnl_asset == 'USDT' or pnl_asset.endswith('USDT'):
                pnl_str = f"{pnl_after_fees:+,.2f} {pnl_asset}"
            else:
                pnl_str = f"{pnl_after_fees:+,.6f} {pnl_asset}"

            if pnl_after_fees > 0:
                pnl_color = self.positive_pnl_color
            elif pnl_after_fees < 0:
                pnl_color = self.negative_pnl_color
            else:
                pnl_color = self.muted_color
        else:
            pnl_str = "FAILED" if status == 'FAILED' else "--"
            pnl_color = self.failed_color if status == 'FAILED' else self.muted_color

        # Configure grid columns (same as headers)
        row_frame.columnconfigure(0, weight=1, minsize=60)   # Time
        row_frame.columnconfigure(1, weight=1, minsize=45)   # Side
        row_frame.columnconfigure(2, weight=1, minsize=70)   # Pair
        row_frame.columnconfigure(3, weight=2, minsize=90)   # Client Price
        row_frame.columnconfigure(4, weight=2, minsize=90)   # Hedge Price
        row_frame.columnconfigure(5, weight=1, minsize=45)   # LP
        row_frame.columnconfigure(6, weight=2, minsize=100)  # P&L

        # Create labels for each column
        columns_data = [
            (time_str, self.fg_color),
            (client_side, self.accent_color),
            (pair_str, self.fg_color),
            (client_price_str, self.fg_color),
            (hedge_price_str, self.fg_color),
            (lp_name, self.accent_color),
            (pnl_str, pnl_color)
        ]

        labels = []
        for idx, (text, color) in enumerate(columns_data):
            label = tk.Label(
                row_frame,
                text=text,
                font=self.row_font,
                bg=row_bg,
                fg=color,
                anchor='w'
            )
            label.grid(row=0, column=idx, sticky='w', padx=2, pady=5)
            labels.append(label)

        # Store row reference
        self.execution_rows.append((row_frame, labels))

    def _fetch_recent_executions(self, limit: int = 50) -> List[Dict]:
        """
        Query database for recent executions.

        Args:
            limit: Maximum number of executions to fetch

        Returns:
            List of execution dictionaries (most recent first)
        """
        if not self.db_path:
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    e.execution_id,
                    e.quote_id,
                    e.status,
                    e.lp_name,
                    e.exchange_side,
                    e.executed_qty,
                    e.avg_price,
                    e.commission,
                    e.commission_asset,
                    e.pnl_after_fees,
                    e.pnl_bps,
                    e.pnl_asset,
                    e.error_message,
                    e.executed_at,
                    q.base_asset,
                    q.quote_asset,
                    q.client_price,
                    q.lp_price,
                    q.side
                FROM executions e
                LEFT JOIN quotes q ON e.quote_id = q.quote_id
                ORDER BY e.executed_at DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            # Convert to list of dicts
            return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"[Blotter] Database error: {e}")
            return []
        except Exception as e:
            print(f"[Blotter] Error fetching executions: {e}")
            return []

    def _update_display(self):
        """Update blotter display with latest executions"""
        with self.lock:
            # Fetch recent executions (last 10 only)
            executions = self._fetch_recent_executions(limit=10)

            # Get current execution IDs
            current_execution_ids = [e.get('execution_id') for e in executions]

            # Check if data has changed
            if current_execution_ids == self.last_execution_ids:
                # No changes, skip update to avoid blinking
                return

            # Data has changed, update the cache
            self.last_execution_ids = current_execution_ids

            # Clear existing rows
            for row_frame, labels in self.execution_rows:
                row_frame.destroy()
            self.execution_rows.clear()

            if not executions:
                # Show empty state
                self._show_empty_state()
            else:
                # Hide empty state if showing executions
                self._hide_empty_state()

                # Create rows for each execution
                for idx, execution in enumerate(executions):
                    self._create_row(execution, idx)

    def _update_loop(self):
        """Auto-update loop (called every 2 seconds)"""
        if not self.running:
            return

        try:
            self._update_display()
        except Exception as e:
            print(f"[Blotter] Update error: {e}")

        # Schedule next update
        if self.running:
            self.parent_frame.after(2000, self._update_loop)

    def refresh(self):
        """Manual refresh trigger"""
        self._update_display()

    def stop(self):
        """Stop auto-refresh"""
        self.running = False
