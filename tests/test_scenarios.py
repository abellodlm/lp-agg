"""
Test scenarios for LP Aggregation System

Implements the three testing scenarios from README:
1. Competing: Offset descending sine wave - LPs compete with varying prices
2. Non-competition: Best bid stays #1, rest compete for 2nd place
3. Hail Mary: Quote improves dramatically 1 second before expiry
"""

import asyncio
import time
import math
from typing import Optional
from colorama import Fore, Style, init

from src.core.models import QuoteRequest, LPQuote
from src.lps.base_lp import LiquidityProvider
from src.core.lp_aggregator import LPAggregator
from src.core.quote_streamer import QuoteStreamer
from src.ui.monitor import get_monitor

init(autoreset=True)


class ScenarioLP(LiquidityProvider):
    """
    Configurable LP for testing scenarios.

    Supports different price generation strategies.
    """

    def __init__(self, name: str, strategy: str, **kwargs):
        """
        Args:
            name: LP identifier
            strategy: 'sine', 'fixed', 'hail_mary'
            **kwargs: Strategy-specific parameters
        """
        self.name = name
        self.strategy = strategy
        self.params = kwargs
        self.start_time = None
        self.poll_count = 0

    def get_name(self) -> str:
        """Return LP name"""
        return self.name

    async def execute_trade(self, quote, client_quote) -> bool:
        """Execute trade (not used in testing scenarios)"""
        # Simulate successful execution for testing
        await asyncio.sleep(0.1)
        return True

    async def request_quote(self, request: QuoteRequest) -> Optional[LPQuote]:
        """Generate quote based on strategy"""

        if self.start_time is None:
            self.start_time = time.time()

        self.poll_count += 1
        elapsed = time.time() - self.start_time

        # Simulate network delay
        await asyncio.sleep(self.params.get('delay', 0.2))

        # Generate price based on strategy
        if self.strategy == 'sine':
            price = self._sine_price(elapsed)
        elif self.strategy == 'fixed':
            price = self.params.get('base_price', 100000)
        elif self.strategy == 'hail_mary':
            price = self._hail_mary_price(elapsed)
        else:
            price = 100000

        return LPQuote(
            lp_name=self.name,
            price=price,
            quantity=request.amount,
            validity_seconds=10.0,
            timestamp=time.time(),
            side=request.side,
            metadata={
                'strategy': self.strategy,
                'poll_count': self.poll_count,
                'elapsed': elapsed,
                'delay_ms': self.params.get('delay', 0.2) * 1000
            }
        )

    def _sine_price(self, elapsed: float) -> float:
        """
        Offset descending sine wave.

        Creates oscillating prices that trend downward over time.
        """
        base_price = self.params.get('base_price', 100000)
        amplitude = self.params.get('amplitude', 200)
        frequency = self.params.get('frequency', 0.5)  # Hz
        offset = self.params.get('offset', 0)  # Phase offset
        trend = self.params.get('trend', -10)  # Price drift per second

        # Sine wave: A * sin(2π * f * t + φ)
        oscillation = amplitude * math.sin(2 * math.pi * frequency * elapsed + offset)

        # Descending trend
        drift = trend * elapsed

        return base_price + oscillation + drift + offset * 50  # Add offset spacing

    def _hail_mary_price(self, elapsed: float) -> float:
        """
        Hail Mary: Quote dramatically improves 1s before expiry.

        Quote stays mediocre until T-1s, then suddenly becomes best.
        """
        base_price = self.params.get('base_price', 100300)
        expiry_time = self.params.get('expiry_time', 10)  # seconds
        improvement_window = self.params.get('improvement_window', 1)  # seconds before expiry

        time_until_expiry = expiry_time - elapsed

        if time_until_expiry <= improvement_window:
            # Dramatically improve price (much better than base)
            return base_price - 500  # Becomes best quote
        else:
            # Stay mediocre (worst quote)
            return base_price


async def run_scenario(scenario_name: str, lps: list, duration: int = 15):
    """
    Run a testing scenario.

    Args:
        scenario_name: Name of the scenario
        lps: List of LPs to use
        duration: How long to run (seconds)
    """
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'='*70}{Style.RESET_ALL}\n")

    # Create aggregator
    aggregator = LPAggregator(lps=lps, markup_bps=5.0)

    # Start monitor
    monitor = get_monitor()
    time.sleep(0.5)

    # Initialize database for testing (optional)
    quote_logger = None
    try:
        from src.database.schema import init_database
        from src.database.quote_logger import QuoteLogger
        init_database("test_quotes.db")
        quote_logger = QuoteLogger("test_quotes.db")
        print(f"{Fore.GREEN}[Database logging enabled]{Style.RESET_ALL}\n")
    except Exception as e:
        print(f"{Fore.YELLOW}[Database logging disabled: {e}]{Style.RESET_ALL}\n")

    # Create request
    request = QuoteRequest(
        side='BUY',
        amount=1.5,
        base_asset='BTC',
        quote_asset='USDT'
    )

    print(f"{Fore.YELLOW}Request: {request}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Duration: {duration}s{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}LPs: {len(lps)}{Style.RESET_ALL}\n")

    # Create streamer
    streamer = QuoteStreamer(aggregator, poll_interval_ms=500, improvement_threshold_bps=1.0, quote_logger=quote_logger)

    poll_count = 0
    improvements = 0
    previous_locked_lp = None

    def on_quote_update(all_lp_quotes, best_quote, poll_num, is_improvement, locked_lp_name):
        nonlocal poll_count, improvements, previous_locked_lp
        poll_count = poll_num

        if is_improvement:
            improvements += 1

        # Update monitor
        monitor.update_display(all_lp_quotes, best_quote, poll_num, locked_lp_name)

        # Terminal output
        if poll_num == 1:
            # Initial lock
            print(f"{Fore.CYAN}[Poll {poll_num}] LOCKED: {locked_lp_name} @ {best_quote.client_price:,.2f}{Style.RESET_ALL}")
            previous_locked_lp = locked_lp_name
        elif is_improvement:
            # Improvement - lock switched
            print(f"{Fore.GREEN}[Poll {poll_num}] IMPROVEMENT: {locked_lp_name} @ {best_quote.client_price:,.2f} (unlocked {previous_locked_lp}){Style.RESET_ALL}")
            previous_locked_lp = locked_lp_name
        else:
            # Print every poll
            print(f"{Fore.WHITE}[Poll {poll_num}] Locked: {locked_lp_name} @ {best_quote.client_price:,.2f}{Style.RESET_ALL}")

    # Stream quotes
    try:
        await streamer.stream_quotes(
            request=request,
            on_quote_update=on_quote_update,
            duration_seconds=duration,
            auto_refresh=False
        )

        print(f"\n{Fore.CYAN}Scenario Complete:{Style.RESET_ALL}")
        print(f"  Total polls: {poll_count}")
        print(f"  Price improvements: {improvements}")
        print(f"  Improvement rate: {improvements/poll_count*100:.1f}%\n")

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Scenario interrupted{Style.RESET_ALL}\n")


async def scenario_1_competing():
    """
    Scenario 1: Competing LPs with offset descending sine waves.

    All LPs compete with oscillating prices that trend downward.
    Each LP has a different phase offset creating interesting dynamics.
    """
    lps = [
        ScenarioLP("LP-Alpha", "sine", base_price=100000, amplitude=150, frequency=0.3, offset=0, trend=-5),
        ScenarioLP("LP-Beta", "sine", base_price=100000, amplitude=180, frequency=0.4, offset=math.pi/2, trend=-8),
        ScenarioLP("LP-Gamma", "sine", base_price=100000, amplitude=120, frequency=0.5, offset=math.pi, trend=-6),
        ScenarioLP("LP-Delta", "sine", base_price=100000, amplitude=200, frequency=0.35, offset=3*math.pi/2, trend=-7),
    ]

    await run_scenario("Competing - Offset Descending Sine", lps, duration=20)


async def scenario_2_non_competition():
    """
    Scenario 2: Non-competition - Best bid stays #1, rest compete.

    One LP consistently provides the best quote (fixed low price).
    Other LPs compete for 2nd place with oscillating prices.
    """
    lps = [
        ScenarioLP("LP-BestBid", "fixed", base_price=99500),  # Always best
        ScenarioLP("LP-Comp1", "sine", base_price=100000, amplitude=100, frequency=0.4, offset=0),
        ScenarioLP("LP-Comp2", "sine", base_price=100100, amplitude=120, frequency=0.5, offset=math.pi/3),
        ScenarioLP("LP-Comp3", "sine", base_price=100200, amplitude=150, frequency=0.3, offset=2*math.pi/3),
    ]

    await run_scenario("Non-Competition - Best Stays #1", lps, duration=15)


async def scenario_3_hail_mary():
    """
    Scenario 3: Hail Mary - Quote improves 1 second before expiry.

    Most LPs provide normal quotes.
    One LP provides mediocre quotes until 1s before expiry, then dramatically improves.
    """
    lps = [
        ScenarioLP("LP-Normal1", "fixed", base_price=100000),
        ScenarioLP("LP-Normal2", "sine", base_price=100100, amplitude=100, frequency=0.4),
        ScenarioLP("LP-HailMary", "hail_mary", base_price=100300, expiry_time=10, improvement_window=1),
        ScenarioLP("LP-Normal3", "fixed", base_price=100200),
    ]

    print(f"{Fore.YELLOW}Watch for dramatic price improvement at T-1s!{Style.RESET_ALL}")

    await run_scenario("Hail Mary - Last Second Improvement", lps, duration=12)


async def run_all_scenarios():
    """Run all test scenarios sequentially"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"  LP AGGREGATION SYSTEM - TEST SCENARIOS")
    print(f"{'='*70}{Style.RESET_ALL}\n")

    print(f"{Fore.YELLOW}Running 3 test scenarios:{Style.RESET_ALL}")
    print(f"  1. Competing LPs (offset descending sine)")
    print(f"  2. Non-competition (best stays #1)")
    print(f"  3. Hail Mary (improvement at T-1s)\n")

    input(f"{Fore.GREEN}Press ENTER to start Scenario 1...{Style.RESET_ALL}")
    await scenario_1_competing()

    input(f"\n{Fore.GREEN}Press ENTER to start Scenario 2...{Style.RESET_ALL}")
    await scenario_2_non_competition()

    input(f"\n{Fore.GREEN}Press ENTER to start Scenario 3...{Style.RESET_ALL}")
    await scenario_3_hail_mary()

    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"  ALL SCENARIOS COMPLETE")
    print(f"{'='*70}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_all_scenarios())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Testing interrupted{Style.RESET_ALL}\n")
