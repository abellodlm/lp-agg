"""
LP Aggregation RFQ System - Main Application Entry Point

This application:
1. Accepts operator input for quote requests (terminal)
2. Pings multiple LPs asynchronously
3. Selects best quote and applies markup
4. Streams live quote updates showing price improvements
5. Displays LP leaderboard in Tkinter monitor
"""

import asyncio
import threading
from typing import List, Optional, Dict
from colorama import Fore, Style

import math
from .config.settings import settings
from .config.pairs import get_pair_config
from .core.models import QuoteRequest, AggregatedQuote, LPQuote
from .core.lp_aggregator import LPAggregator
from .core.quote_streamer import QuoteStreamer
from .lps.base_lp import LiquidityProvider
from .lps.mock_lp import MockLP
from .lps.sine_lp import SineLPProvider
from .ui.terminal import TerminalInterface
from .ui.monitor import get_monitor
from .execution import determine_hedge_params, calculate_pnl, execute_simulated_trade
from .execution.execution_manager import ExecutionManager


def create_mock_lps() -> List[LiquidityProvider]:
    """
    Create Sine Wave LP instances for realistic price competition.

    Creates LPs with phase-shifted sine wave pricing:
    - LP-1: phase=0 (starts mid, rising)
    - LP-2: phase=π/2 (starts at peak)
    - LP-3: phase=π (starts mid, falling)

    This creates realistic competition where different LPs win at different times.
    """
    # Sine wave parameters (increased frequency for faster competition)
    amplitude = 50
    frequency = 0.20  # Increased from 0.05 for faster oscillation (3x faster)
    trend = -1
    base_price = settings.mock_base_price

    # Phase offsets for 3 LPs (creates competition)
    phases = [0.0, math.pi / 2, math.pi]

    lps = []
    for i in range(min(settings.mock_lp_count, 3)):  # Max 3 LPs for clear phases
        lp = SineLPProvider(
            name=f"LP-{i+1}",
            base_price=base_price,
            amplitude=amplitude,
            frequency=frequency,
            phase=phases[i],
            trend=trend,
            spread_bps=settings.mock_spread_bps,
            response_delay=(settings.mock_min_delay, settings.mock_max_delay)
        )
        lps.append(lp)

    return lps


async def handle_quote_stream(
    request: QuoteRequest,
    aggregator: LPAggregator,
    streamer: QuoteStreamer,
    monitor,
    state: Dict,
    state_lock
):
    """
    Stream quotes for a given request and update monitor.

    Args:
        request: Quote request from operator
        aggregator: LP aggregator instance
        streamer: Quote streamer instance
        monitor: Monitor GUI instance
        state: Shared state dictionary with keys:
            - locked_quote: Current locked AggregatedQuote
            - locked_lp_quote: Current locked LPQuote
            - stop_stream: Set to True to stop streaming
    """
    # Track previous locked LP to detect lock changes
    previous_locked_lp = None

    # Callback for quote updates
    def on_quote_update(all_lp_quotes: List[LPQuote], best_quote: AggregatedQuote, poll_count: int, is_improvement: bool, locked_lp_name: Optional[str]):
        nonlocal previous_locked_lp

        # Check if stream should stop
        with state_lock:
            should_stop = state.get('stop_stream', False)
        
        if should_stop:
            streamer.stop()
            return

        try:
            # Update shared state with locked quote (protected by lock)
            with state_lock:
                state['locked_quote'] = best_quote
                state['locked_lp_quote'] = next((q for q in all_lp_quotes if q.lp_name == locked_lp_name), None)

            # Update monitor with all LP data
            monitor.update_display(all_lp_quotes, best_quote, poll_count, locked_lp_name)

            # Terminal feedback - only show initial lock and improvements
            if poll_count == 1:
                # Initial lock - show quote
                print(f"\n{Fore.CYAN}{'='*70}")
                print(f"QUOTE LOCKED")
                print(f"{'='*70}{Style.RESET_ALL}\n")
                print(f"  LP:             {locked_lp_name}")
                print(f"  Side:           {best_quote.side} {best_quote.amount} {best_quote.target_asset}")
                print(f"  Client Pays:    {best_quote.client_gives_amount:,.8f} {best_quote.client_gives_asset}")
                print(f"  Client Gets:    {best_quote.client_receives_amount:,.8f} {best_quote.client_receives_asset}")
                print(f"  Price:          {best_quote.client_price:,.4f} {best_quote.quote_asset}")
                print(f"  Valid for:      {best_quote.time_remaining():.1f}s")
                print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
                print(f"{Fore.YELLOW}Commands: [p] proceed  [c] cancel  [q] quit{Style.RESET_ALL}\n")

                previous_locked_lp = locked_lp_name
            elif is_improvement:
                # Improvement - lock switched
                print(f"\n{Fore.GREEN}{'='*70}")
                print(f"IMPROVED QUOTE")
                print(f"{'='*70}{Style.RESET_ALL}\n")
                print(f"  LP:             {locked_lp_name}")
                print(f"  Side:           {best_quote.side} {best_quote.amount} {best_quote.target_asset}")
                print(f"  Client Pays:    {best_quote.client_gives_amount:,.8f} {best_quote.client_gives_asset}")
                print(f"  Client Gets:    {best_quote.client_receives_amount:,.8f} {best_quote.client_receives_asset}")
                print(f"  Price:          {best_quote.client_price:,.4f} {best_quote.quote_asset}")
                print(f"  Valid for:      {best_quote.time_remaining():.1f}s")
                print(f"\n{Fore.GREEN}{'='*70}{Style.RESET_ALL}\n")
                print(f"{Fore.YELLOW}Commands: [p] proceed  [c] cancel  [q] quit{Style.RESET_ALL}\n")
                previous_locked_lp = locked_lp_name

        except Exception as e:
            print(f"{Fore.RED}[ERROR] in quote callback: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()

    # Get auto-refresh setting from monitor (force to True for continuous polling)
    auto_refresh = True  # Force enabled for continuous price updates

    # Stream quotes (indefinitely if auto-refresh, otherwise until expiry)
    try:
        await streamer.stream_quotes(
            request=request,
            on_quote_update=on_quote_update,
            duration_seconds=None,  # Stream until expiry or manual stop
            auto_refresh=auto_refresh
        )

        # Stream ended
        if state.get('stop_stream', False):
            # Stopped intentionally (execution completed)
            pass
        else:
            # Quote expired
            print(f"\n{Fore.YELLOW}Quote expired{Style.RESET_ALL}\n")
            monitor.show_expired()

    except asyncio.CancelledError:
        # Stream was manually cancelled
        streamer.stop()


async def main_loop():
    """Main application loop with non-blocking terminal"""
    terminal = TerminalInterface()

    # Initialize database if logging is enabled
    quote_logger = None
    db_path = None
    if settings.enable_database_logging:
        from .database.schema import init_database
        from .database.quote_logger import QuoteLogger
        init_database(settings.database_path)
        quote_logger = QuoteLogger(settings.database_path)
        db_path = settings.database_path

    # Start monitor in background with database path
    monitor = get_monitor(db_path=db_path)

    # Create LP aggregator and streamer (reused across requests)
    lps = create_mock_lps()
    aggregator = LPAggregator(
        lps=lps,
        markup_bps=settings.markup_bps,
        validity_buffer_seconds=settings.validity_buffer_seconds
    )
    streamer = QuoteStreamer(
        aggregator=aggregator,
        poll_interval_ms=settings.poll_interval_ms,
        improvement_threshold_bps=settings.improvement_threshold_bps,
        quote_logger=quote_logger
    )

    # Create execution manager
    lp_dict = {lp.get_name(): lp for lp in lps}
    execution_manager = ExecutionManager(lp_dict, quote_logger)

    # Track current streaming task and locked quote (shared state)
    current_task: Optional[asyncio.Task] = None
    state = {
        'locked_quote': None,
        'locked_lp_quote': None,
        'stop_stream': False
    }
    state_lock = threading.Lock()  # Protect shared state (threading.Lock for sync callback)

    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"LP AGGREGATION RFQ SYSTEM")
    print(f"{'='*70}{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}Enter Quote Request:{Style.RESET_ALL}")
    print(f"  Format: <side> <amount> <target_asset> <pair>")
    print(f"  Example: b 1.5 btc btcusdt")
    print(f"  Example: s 50000 usdt btcusdt\n")

    # Get event loop for async input
    loop = asyncio.get_event_loop()

    while True:
        # Get input from operator asynchronously (non-blocking)
        user_input = await loop.run_in_executor(
            None,
            lambda: input(f"{Fore.CYAN}> {Style.RESET_ALL}")
        )
        user_input = user_input.strip().lower()

        # Handle commands based on context
        if user_input == 'q':
            # Quit application
            if current_task and not current_task.done():
                with state_lock:
                    state['stop_stream'] = True
                current_task.cancel()
                try:
                    await current_task
                except asyncio.CancelledError:
                    pass
            print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}\n")
            break

        # Check if we're in streaming mode
        if current_task and not current_task.done():
            # Streaming active - handle p/c commands
            if user_input == 'p':
                # Proceed with execution
                if state['locked_quote'] is None or state['locked_lp_quote'] is None:
                    print(f"{Fore.RED}No locked quote available{Style.RESET_ALL}\n")
                    continue

                locked_quote = state['locked_quote']
                locked_lp_quote = state['locked_lp_quote']

                # Check if quote is still valid
                if locked_quote.is_expired():
                    print(f"{Fore.RED}Quote expired. Cannot execute.{Style.RESET_ALL}\n")
                    continue

                # Stop the stream FIRST (before execution)
                with state_lock:
                    state['stop_stream'] = True
                current_task.cancel()
                try:
                    await current_task
                except asyncio.CancelledError:
                    pass

                # Execute the trade
                print(f"\n{Fore.CYAN}Executing trade...{Style.RESET_ALL}\n")

                exec_result = await execution_manager.execute_quote(locked_quote, locked_lp_quote)

                # Display results
                if exec_result['status'] == 'SUCCESS':
                    print(f"{Fore.GREEN}{'='*70}")
                    print(f"EXECUTION SUCCESSFUL")
                    print(f"{'='*70}{Style.RESET_ALL}\n")
                    print(f"  Execution ID:   {exec_result['execution_id']}")
                    print(f"  Hedge:          {exec_result['exchange_side']} {exec_result['executed_qty']:,.8f} {locked_quote.base_asset}")
                    print(f"  Avg Price:      {exec_result['avg_price']:,.2f}")
                    print(f"  Net P&L:        {Fore.GREEN}{exec_result['pnl_after_fees']:,.8f} {exec_result['pnl_asset']} ({exec_result['pnl_bps']:,.2f} bps){Style.RESET_ALL}")
                    print(f"\n{Fore.GREEN}{'='*70}{Style.RESET_ALL}\n")

                    # Update monitor to show executed status
                    monitor.show_executed()
                else:
                    print(f"{Fore.RED}{'='*70}")
                    print(f"EXECUTION FAILED: {exec_result.get('error_message', 'Unknown error')}")
                    print(f"{'='*70}{Style.RESET_ALL}\n")

                # Reset state
                with state_lock:
                    state['locked_quote'] = None
                    state['locked_lp_quote'] = None
                    state['stop_stream'] = False
                current_task = None

                print(f"{Fore.YELLOW}Enter new quote request:{Style.RESET_ALL}\n")
                continue

            elif user_input == 'c':
                # Cancel stream
                with state_lock:
                    state['stop_stream'] = True
                current_task.cancel()
                try:
                    await current_task
                except asyncio.CancelledError:
                    pass

                # Reset state
                with state_lock:
                    state['locked_quote'] = None
                    state['locked_lp_quote'] = None
                    state['stop_stream'] = False
                current_task = None

                print(f"\n{Fore.YELLOW}Cancelled. Enter new quote request:{Style.RESET_ALL}\n")
                continue

            else:
                # Invalid command during streaming
                print(f"{Fore.YELLOW}Commands: [p] proceed  [c] cancel  [q] quit{Style.RESET_ALL}\n")
                continue

        else:
            # Not streaming - parse as quote request
            request = terminal.parse_input(user_input)

            if request is None:
                print(f"{Fore.RED}Invalid request{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Format: <side> <amount> <target_asset> <pair>{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Example: b 1.5 btc btcusdt{Style.RESET_ALL}\n")
                continue

            # Reset state
            state['locked_quote'] = None
            state['locked_lp_quote'] = None
            state['stop_stream'] = False

            # Start new stream in background
            current_task = asyncio.create_task(
                handle_quote_stream(request, aggregator, streamer, monitor, state, state_lock)
            )

            # Give the task a moment to start and fetch quotes
            await asyncio.sleep(0.5)


def main():
    """Entry point"""
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Application stopped by operator{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
