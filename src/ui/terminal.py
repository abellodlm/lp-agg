"""
Terminal interface for operator input and quote display.
"""

from colorama import Fore, Style, init
from typing import Optional
from ..core.models import QuoteRequest, AggregatedQuote

init(autoreset=True)


class TerminalInterface:
    """Simple terminal interface for operator input"""

    def display_banner(self):
        """Display startup banner"""
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"  LP Aggregation RFQ System")
        print(f"{'='*60}{Style.RESET_ALL}\n")

    def parse_input(self, user_input: str) -> Optional[QuoteRequest]:
        """
        Parse single-line quote request.

        Format: <side> <amount> <pair>
        Example: b 1.5 btcusdt

        Args:
            user_input: User input string

        Returns:
            QuoteRequest or None if invalid
        """
        try:
            parts = user_input.strip().split()
            if len(parts) != 3:
                return None

            # Parse side
            side_input = parts[0].lower()
            if side_input in ['b', 'buy']:
                side = 'BUY'
            elif side_input in ['s', 'sell']:
                side = 'SELL'
            else:
                return None

            # Parse amount
            amount = float(parts[1])
            if amount <= 0:
                return None

            # Parse pair
            pair_input = parts[2].upper()
            if 'USDT' in pair_input:
                base_asset = pair_input.replace('USDT', '')
                quote_asset = 'USDT'
            elif 'USDC' in pair_input:
                base_asset = pair_input.replace('USDC', '')
                quote_asset = 'USDC'
            else:
                return None

            return QuoteRequest(
                side=side,
                amount=amount,
                base_asset=base_asset,
                quote_asset=quote_asset
            )

        except (ValueError, IndexError):
            return None

    def get_quote_request(self) -> Optional[QuoteRequest]:
        """
        Prompt operator for quote request details.

        Returns:
            QuoteRequest or None if cancelled
        """
        print(f"\n{Fore.YELLOW}Enter Quote Request:{Style.RESET_ALL}")

        # Get side
        while True:
            side_input = input(f"  Side (b/buy or s/sell): ").strip().lower()
            if side_input in ['b', 'buy']:
                side = 'BUY'
                break
            elif side_input in ['s', 'sell']:
                side = 'SELL'
                break
            else:
                print(f"{Fore.RED}  Invalid side. Use 'b' or 's'{Style.RESET_ALL}")

        # Get amount
        while True:
            try:
                amount = float(input(f"  Amount: ").strip())
                if amount <= 0:
                    raise ValueError
                break
            except ValueError:
                print(f"{Fore.RED}  Invalid amount. Enter a positive number{Style.RESET_ALL}")

        # Get pair
        pair_input = input(f"  Pair (e.g., BTCUSDT): ").strip().upper()

        # Parse pair (simple parsing for now)
        if 'USDT' in pair_input:
            base_asset = pair_input.replace('USDT', '')
            quote_asset = 'USDT'
        elif 'USDC' in pair_input:
            base_asset = pair_input.replace('USDC', '')
            quote_asset = 'USDC'
        else:
            print(f"{Fore.RED}  Unsupported pair format{Style.RESET_ALL}")
            return None

        return QuoteRequest(
            side=side,
            amount=amount,
            base_asset=base_asset,
            quote_asset=quote_asset
        )

    def display_quote(self, quote: AggregatedQuote):
        """Display aggregated quote"""
        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"  Quote #{quote.quote_id}")
        print(f"{'='*60}{Style.RESET_ALL}")
        print(f"  LP Source: {Fore.CYAN}{quote.lp_name}{Style.RESET_ALL}")
        print(f"  Client {quote.side}S {quote.amount:,.8f} {quote.base_asset}")
        print(f"  Client Price: {Fore.YELLOW}{quote.client_price:,.4f} {quote.quote_asset}{Style.RESET_ALL}")
        print(f"  LP Price: {quote.lp_price:,.4f} {quote.quote_asset}")
        print(f"  Markup: {quote.markup_bps} bps")
        print(f"\n  Client Pays: {quote.client_gives_amount:,.8f} {quote.client_gives_asset}")
        print(f"  Client Receives: {quote.client_receives_amount:,.8f} {quote.client_receives_asset}")
        print(f"\n  Valid for: {Fore.YELLOW}{quote.validity_seconds:.1f}s{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")
