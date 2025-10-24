"""
LP Aggregation Monitor - Mario Kart Style Leaderboard

Tkinter-based dashboard showing:
- Best aggregated quote (top section)
- LP leaderboard with dynamic sizing (1st larger, podium normal, rest smaller)
- Stream status and auto-refresh toggle
"""

import tkinter as tk
from tkinter import font
import threading
import time
from typing import Optional, List
from datetime import datetime

from ..core.models import LPQuote, AggregatedQuote


class LPAggregationMonitor:
    """
    LP Aggregation Monitor with Mario Kart style leaderboard.

    Features:
    - Best quote display (large, prominent)
    - LP rankings with visual hierarchy (winner > podium > others)
    - Auto-refresh toggle
    - Thread-safe updates
    """

    def __init__(self, db_path: Optional[str] = None):
        self.window: Optional[tk.Tk] = None
        self.running = False
        self.db_path = db_path

        # Current data
        self.best_quote: Optional[AggregatedQuote] = None
        self.all_lp_quotes: List[LPQuote] = []
        self.poll_count = 0

        # GUI elements
        self.quote_id_label = None
        self.operation_label = None
        self.client_price_label = None
        self.lp_source_label = None
        self.validity_label = None
        self.lp_row_frames = []  # List of (frame, name_label, price_label, info_label)
        self.status_label = None
        self.blotter = None  # ExecutionBlotter instance

        # State flags
        self.is_executed = False  # Track if trade was executed

        self.lock = threading.Lock()

    def start(self):
        """Start the monitor window in a separate daemon thread"""
        if not self.running:
            self.running = True
            monitor_thread = threading.Thread(target=self._run_gui, daemon=True)
            monitor_thread.start()
            time.sleep(0.5)  # Give it time to initialize

    def _run_gui(self):
        """Run the Tkinter GUI"""
        self.window = tk.Tk()
        self.window.title("LP Aggregation Monitor")

        # Window configuration
        self.window.geometry("1200x800")  # Increased width for two columns
        self.window.resizable(False, False)
        self.window.attributes('-topmost', True)  # Always on top

        # Colors
        bg_color = "#1e1e1e"
        fg_color = "#ffffff"
        accent_color = "#00d4aa"
        muted_color = "#888888"

        self.window.configure(bg=bg_color)

        # Fonts
        title_font = font.Font(family="Consolas", size=12, weight="bold")
        large_font = font.Font(family="Consolas", size=16, weight="bold")
        normal_font = font.Font(family="Consolas", size=12)
        small_font = font.Font(family="Consolas", size=10)
        tiny_font = font.Font(family="Consolas", size=9)

        # Main container with grid layout for two columns
        main_container = tk.Frame(self.window, bg=bg_color)
        main_container.pack(fill='both', expand=True, padx=15, pady=15)

        # Configure grid: 60% left column (monitor), 40% right column (blotter)
        main_container.columnconfigure(0, weight=6)
        main_container.columnconfigure(1, weight=4)
        main_container.rowconfigure(0, weight=1)

        # LEFT COLUMN: LP Monitor
        left_frame = tk.Frame(main_container, bg=bg_color)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))

        # RIGHT COLUMN: Execution Blotter
        right_frame = tk.Frame(main_container, bg=bg_color)
        right_frame.grid(row=0, column=1, sticky='nsew')

        # ==================================================
        # LEFT COLUMN CONTENT: LP MONITOR
        # ==================================================
        tk.Label(
            left_frame,
            text="LP AGGREGATION MONITOR",
            font=title_font,
            bg=bg_color,
            fg=accent_color
        ).pack(pady=(0, 15))

        # ==================================================
        # BEST QUOTE SECTION
        # ==================================================
        best_quote_frame = tk.Frame(left_frame, bg="#2a2a2a", relief='ridge', bd=2)
        best_quote_frame.pack(fill='x', pady=(0, 20))

        # Quote ID
        self.quote_id_label = tk.Label(
            best_quote_frame,
            text="Waiting for quote...",
            font=small_font,
            bg="#2a2a2a",
            fg=muted_color
        )
        self.quote_id_label.pack(pady=(10, 2))

        # Operation description
        self.operation_label = tk.Label(
            best_quote_frame,
            text="",
            font=normal_font,
            bg="#2a2a2a",
            fg=accent_color
        )
        self.operation_label.pack(pady=(0, 10))

        # Separator
        tk.Frame(best_quote_frame, height=1, bg="#444444").pack(fill='x', padx=20, pady=5)

        # Client price (large)
        client_price_container = tk.Frame(best_quote_frame, bg="#2a2a2a")
        client_price_container.pack(pady=5)

        tk.Label(
            client_price_container,
            text="CLIENT PRICE:",
            font=small_font,
            bg="#2a2a2a",
            fg=muted_color
        ).pack(side='left', padx=(0, 10))

        self.client_price_label = tk.Label(
            client_price_container,
            text="--",
            font=large_font,
            bg="#2a2a2a",
            fg=fg_color
        )
        self.client_price_label.pack(side='left')

        self.validity_label = tk.Label(
            client_price_container,
            text="",
            font=normal_font,
            bg="#2a2a2a",
            fg=accent_color
        )
        self.validity_label.pack(side='right', padx=(20, 0))

        # LP source + markup
        self.lp_source_label = tk.Label(
            best_quote_frame,
            text="",
            font=tiny_font,
            bg="#2a2a2a",
            fg=muted_color
        )
        self.lp_source_label.pack(pady=(5, 10))

        # ==================================================
        # LP LEADERBOARD SECTION
        # ==================================================
        tk.Label(
            left_frame,
            text="LP LEADERBOARD",
            font=title_font,
            bg=bg_color,
            fg=accent_color
        ).pack(pady=(10, 10))

        # Create scrollable frame for LPs
        lp_container = tk.Frame(left_frame, bg=bg_color)
        lp_container.pack(fill='both', expand=True)

        # Create up to 10 LP rows (dynamic display)
        for i in range(10):
            self._create_lp_row(lp_container, bg_color, fg_color, muted_color)

        # Status label removed (redundant - quote box shows status)
        self.status_label = None

        # ==================================================
        # RIGHT COLUMN CONTENT: EXECUTION BLOTTER
        # ==================================================
        if self.db_path:
            from .blotter import ExecutionBlotter
            self.blotter = ExecutionBlotter(right_frame, self.db_path)

        # Start update loop
        self.window.after(1000, self._update_loop)

        # Handle close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # Run
        self.window.mainloop()

    def _create_lp_row(self, parent, bg_color, fg_color, muted_color):
        """Create a single LP row in the leaderboard"""
        row_frame = tk.Frame(parent, bg=bg_color, height=60)
        row_frame.pack(fill='x', pady=2)
        row_frame.pack_propagate(False)

        # Inner frame for content
        content_frame = tk.Frame(row_frame, bg=bg_color)
        content_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # LP name + medal
        name_label = tk.Label(
            content_frame,
            text="",
            font=font.Font(family="Consolas", size=12),
            bg=bg_color,
            fg=fg_color,
            anchor='w'
        )
        name_label.pack(anchor='w')

        # Price
        price_label = tk.Label(
            content_frame,
            text="",
            font=font.Font(family="Consolas", size=14, weight="bold"),
            bg=bg_color,
            fg=fg_color,
            anchor='w'
        )
        price_label.pack(anchor='w')

        # Info (validity, latency)
        info_label = tk.Label(
            content_frame,
            text="",
            font=font.Font(family="Consolas", size=9),
            bg=bg_color,
            fg=muted_color,
            anchor='w'
        )
        info_label.pack(anchor='w')

        self.lp_row_frames.append((row_frame, content_frame, name_label, price_label, info_label))

    def _update_loop(self):
        """Update display periodically"""
        if not self.running:
            return

        try:
            with self.lock:
                # Update best quote section
                if self.best_quote:
                    self._update_best_quote_display()

                # Update LP leaderboard
                if self.all_lp_quotes:
                    self._update_leaderboard_display()

                # Update validity countdown (only if not executed)
                if self.best_quote and not self.is_executed:
                    self._update_validity_countdown()
        except Exception as e:
            print(f"Monitor update error: {e}")

        # Schedule next update
        self.window.after(1000, self._update_loop)

    def _update_best_quote_display(self):
        """Update the best quote section"""
        if not self.best_quote:
            return

        # Quote ID
        self.quote_id_label.config(text=f"Quote #{self.best_quote.quote_id}")

        # Operation description
        op_text = f"Client {self.best_quote.side}S {self.best_quote.client_receives_amount:,.4f} {self.best_quote.client_receives_asset}"
        op_text += f" for {self.best_quote.client_gives_amount:,.2f} {self.best_quote.client_gives_asset}"
        self.operation_label.config(text=op_text)

        # Client price
        price_text = f"{self.best_quote.client_price:,.2f} {self.best_quote.quote_asset}"
        self.client_price_label.config(text=price_text)

        # LP source + markup
        source_text = f"LP Source: {self.best_quote.lp_name} | Markup: {self.best_quote.markup_bps:.1f} bps"
        self.lp_source_label.config(text=source_text)

    def _update_validity_countdown(self):
        """Update the validity countdown timer"""
        if not self.best_quote:
            return

        remaining = self.best_quote.time_remaining()

        if remaining > 0:
            self.validity_label.config(
                text=f"⏱ {int(remaining)}s",
                fg="#00d4aa"
            )
        else:
            self.validity_label.config(
                text="EXPIRED",
                fg="#ff6b6b"
            )

    def _update_leaderboard_display(self):
        """Update LP leaderboard with Mario Kart style ranking"""
        if not self.all_lp_quotes:
            return

        # Sort LPs by price (best first)
        side = self.best_quote.side if self.best_quote else 'BUY'
        sorted_lps = sorted(
            self.all_lp_quotes,
            key=lambda q: q.price,
            reverse=(side == 'SELL')
        )

        # Update each row
        for i, (row_frame, content_frame, name_label, price_label, info_label) in enumerate(self.lp_row_frames):
            if i < len(sorted_lps):
                lp_quote = sorted_lps[i]

                # Determine style based on position
                if i == 0:  # Winner
                    self._style_lp_row_winner(row_frame, content_frame, name_label, price_label, info_label, lp_quote, sorted_lps[0].price)
                elif i < 3:  # Podium (2nd, 3rd)
                    self._style_lp_row_podium(row_frame, content_frame, name_label, price_label, info_label, lp_quote, sorted_lps[0].price, i)
                else:  # Others
                    self._style_lp_row_normal(row_frame, content_frame, name_label, price_label, info_label, lp_quote, sorted_lps[0].price)

                # Make visible
                row_frame.pack(fill='x', pady=2)
            else:
                # Hide unused rows
                row_frame.pack_forget()

    def _style_lp_row_winner(self, row_frame, content_frame, name_label, price_label, info_label, lp_quote, best_price):
        """Style the winner row (1st place)"""
        # Green background, larger font
        bg_color = "#1a3d2e"
        fg_color = "#00d4aa"

        row_frame.config(bg=bg_color, relief='solid', bd=2, height=70)
        content_frame.config(bg=bg_color)

        # Name with medal
        name_label.config(
            text=f"🥇 {lp_quote.lp_name.upper()} (BEST)",
            font=font.Font(family="Consolas", size=13, weight="bold"),
            bg=bg_color,
            fg=fg_color
        )

        # Price
        price_label.config(
            text=f"{lp_quote.price:,.2f} USDT",
            font=font.Font(family="Consolas", size=16, weight="bold"),
            bg=bg_color,
            fg="#ffffff"
        )

        # Info
        remaining = lp_quote.time_remaining()
        latency_ms = lp_quote.metadata.get('delay_ms', 0) if lp_quote.metadata else 0
        info_label.config(
            text=f"⏱ {int(remaining)}s left  |  📡 {int(latency_ms)}ms",
            bg=bg_color,
            fg="#888888"
        )

    def _style_lp_row_podium(self, row_frame, content_frame, name_label, price_label, info_label, lp_quote, best_price, position):
        """Style podium rows (2nd, 3rd)"""
        bg_color = "#1e1e1e"
        fg_color = "#ffffff"

        row_frame.config(bg=bg_color, relief='flat', bd=0, height=60)
        content_frame.config(bg=bg_color)

        # Medal
        medal = "🥈" if position == 1 else "🥉"

        # Calculate delta from best
        delta_pct = ((lp_quote.price - best_price) / best_price) * 100

        # Name with medal
        name_label.config(
            text=f"{medal} {lp_quote.lp_name}",
            font=font.Font(family="Consolas", size=12),
            bg=bg_color,
            fg=fg_color
        )

        # Price with delta
        price_label.config(
            text=f"{lp_quote.price:,.2f} USDT ({delta_pct:+.2f}%)",
            font=font.Font(family="Consolas", size=14, weight="bold"),
            bg=bg_color,
            fg=fg_color
        )

        # Info
        remaining = lp_quote.time_remaining()
        latency_ms = lp_quote.metadata.get('delay_ms', 0) if lp_quote.metadata else 0
        info_label.config(
            text=f"⏱ {int(remaining)}s left  |  📡 {int(latency_ms)}ms",
            bg=bg_color,
            fg="#888888"
        )

    def _style_lp_row_normal(self, row_frame, content_frame, name_label, price_label, info_label, lp_quote, best_price):
        """Style normal rows (4th+)"""
        bg_color = "#1e1e1e"
        fg_color = "#666666"

        row_frame.config(bg=bg_color, relief='flat', bd=0, height=50)
        content_frame.config(bg=bg_color)

        # Calculate delta from best
        delta_pct = ((lp_quote.price - best_price) / best_price) * 100

        # Name
        name_label.config(
            text=f"   {lp_quote.lp_name}",
            font=font.Font(family="Consolas", size=10),
            bg=bg_color,
            fg=fg_color
        )

        # Price with delta
        price_label.config(
            text=f"{lp_quote.price:,.2f} USDT ({delta_pct:+.2f}%)",
            font=font.Font(family="Consolas", size=12),
            bg=bg_color,
            fg=fg_color
        )

        # Info
        remaining = lp_quote.time_remaining()
        latency_ms = lp_quote.metadata.get('delay_ms', 0) if lp_quote.metadata else 0
        info_label.config(
            text=f"⏱ {int(remaining)}s  |  📡 {int(latency_ms)}ms",
            bg=bg_color,
            fg=fg_color
        )

    def update_display(self, all_lp_quotes: List[LPQuote], best_quote: AggregatedQuote, poll_count: int, locked_lp_name: Optional[str] = None):
        """
        Update monitor with new quote data.

        Thread-safe method to update display from streaming thread.

        Args:
            all_lp_quotes: All LP quotes received (includes frozen data for locked LP)
            best_quote: Best aggregated quote (locked quote if no improvement)
            poll_count: Current poll number
            locked_lp_name: Name of currently locked LP (if any)
        """
        with self.lock:
            # Deep copy to prevent shared state issues
            self.all_lp_quotes = list(all_lp_quotes) if all_lp_quotes else []
            self.best_quote = best_quote  # AggregatedQuote is immutable (dataclass)
            self.poll_count = poll_count

            # Reset executed flag on new quote (poll 1 means new quote request)
            if poll_count == 1:
                self.is_executed = False

            # Update status
            # Status label removed - no longer needed

    def show_expired(self):
        """Show expired status"""
        with self.lock:
            # Update the validity label in the quote box to show EXPIRED
            if self.validity_label:
                self.validity_label.config(
                    text="EXPIRED",
                    fg="#ff6b6b"
                )

    def show_executed(self):
        """Show executed status"""
        with self.lock:
            # Set flag to prevent timer from overwriting
            self.is_executed = True

            # Update the validity label in the quote box to show EXECUTED
            if self.validity_label:
                self.validity_label.config(
                    text="EXECUTED",
                    fg="#51cf66"
                )


    def _on_close(self):
        """Handle window close"""
        self.running = False
        if self.window:
            self.window.destroy()

    def stop(self):
        """Stop monitor"""
        self.running = False
        if self.window:
            try:
                self.window.destroy()
            except:
                pass


# Global singleton instance
_monitor_instance: Optional[LPAggregationMonitor] = None
_monitor_lock = threading.Lock()


def get_monitor(db_path: Optional[str] = None) -> LPAggregationMonitor:
    """
    Get or create the global monitor instance.

    Args:
        db_path: Optional path to database for blotter

    Returns:
        Global monitor instance
    """
    global _monitor_instance

    with _monitor_lock:
        if _monitor_instance is None:
            _monitor_instance = LPAggregationMonitor(db_path=db_path)
            _monitor_instance.start()
        elif db_path and not _monitor_instance.db_path:
            # Update db_path if monitor already exists but db_path wasn't set
            _monitor_instance.db_path = db_path

        return _monitor_instance
