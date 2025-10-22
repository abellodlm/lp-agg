"""
Terminal interface for operator input and quote display.
"""

from colorama import Fore, Style, init
from typing import Optional
from ..core.models import QuoteRequest, AggregatedQuote
from ..config.pairs import get_pair_config

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

        Format: <side> <amount> <target_asset> <pair>
        Example: b 1.5 btc btcusdt  (buy 1.5 BTC)
        Example: b 50000 usdt btcusdt  (buy 50000 USDT worth of BTC)

        Legacy format (3 parts): <side> <amount> <pair>
        Example: b 1.5 btcusdt  (defaults to base asset)

        Args:
            user_input: User input string

        Returns:
            QuoteRequest or None if invalid
        """
        try:
            parts = user_input.strip().split()

            # Support both 3-part (legacy) and 4-part (new) formats
            if len(parts) == 3:
                # Legacy format: side, amount, pair (assume target_asset = base_asset)
                side_input, amount_str, pair_input = parts
                target_asset_input = None  # Will default to base
            elif len(parts) == 4:
                # New format: side, amount, target_asset, pair
                side_input, amount_str, target_asset_input, pair_input = parts
            else:
                return None

            # Parse side
            side_input = side_input.lower()
            if side_input in ['b', 'buy']:
                side = 'BUY'
            elif side_input in ['s', 'sell']:
                side = 'SELL'
            else:
                return None

            # Parse amount
            amount = float(amount_str)
            if amount <= 0:
                return None

            # Parse pair using pair config
            pair_input = pair_input.upper()
            try:
                pair_config = get_pair_config(pair_input)
                base_asset = pair_config.base_asset
                quote_asset = pair_config.quote_asset
            except ValueError:
                return None

            # Determine target_asset
            if target_asset_input is None:
                # Legacy mode: default to base asset
                target_asset = base_asset
            else:
                target_asset_input = target_asset_input.upper()
                if target_asset_input == base_asset:
                    target_asset = base_asset
                elif target_asset_input == quote_asset:
                    target_asset = quote_asset
                else:
                    return None

            return QuoteRequest(
                side=side,
                amount=amount,
                base_asset=base_asset,
                quote_asset=quote_asset,
                target_asset=target_asset
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
        while True:
            pair_input = input(f"  Pair (e.g., BTCUSDT): ").strip().upper()
            try:
                pair_config = get_pair_config(pair_input)
                base_asset = pair_config.base_asset
                quote_asset = pair_config.quote_asset
                break
            except ValueError:
                print(f"{Fore.RED}  Unsupported pair. Supported: BTCUSDT, ETHUSDT, USDCUSDT{Style.RESET_ALL}")

        # Get target asset
        while True:
            target_input = input(
                f"  Target asset ({base_asset} or {quote_asset}, default={base_asset}): "
            ).strip().upper()

            if not target_input:
                # Default to base asset
                target_asset = base_asset
                break
            elif target_input == base_asset:
                target_asset = base_asset
                break
            elif target_input == quote_asset:
                target_asset = quote_asset
                break
            else:
                print(f"{Fore.RED}  Invalid target asset. Choose {base_asset} or {quote_asset}{Style.RESET_ALL}")

        return QuoteRequest(
            side=side,
            amount=amount,
            base_asset=base_asset,
            quote_asset=quote_asset,
            target_asset=target_asset
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
