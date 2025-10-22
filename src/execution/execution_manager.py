"""
Execution Manager - Coordinates trade execution with LPs.

Handles:
- LP execution
- Hedge calculation
- P&L tracking
- Database logging
"""

import time
from typing import Dict, Optional, TYPE_CHECKING
from datetime import datetime
from ..core.models import AggregatedQuote, LPQuote
from ..config.pairs import get_pair_config
from .hedge_calculator import determine_hedge_params
from .pnl_calculator import calculate_pnl
from .simulator import execute_simulated_trade

if TYPE_CHECKING:
    from ..lps.base_lp import LiquidityProvider
    from ..database.quote_logger import QuoteLogger


class ExecutionManager:
    """
    Manages trade execution flow.

    Flow:
    1. Receive confirmed quote from operator
    2. Calculate hedge parameters
    3. Execute with LP
    4. Simulate hedge execution (or execute real hedge)
    5. Calculate P&L
    6. Log to database
    """

    def __init__(self, lps: Dict[str, 'LiquidityProvider'], quote_logger: Optional['QuoteLogger'] = None):
        """
        Initialize execution manager.

        Args:
            lps: Dictionary of LP name -> LP instance
            quote_logger: Optional database logger
        """
        self.lps = lps
        self.quote_logger = quote_logger

    async def execute_quote(
        self,
        quote: AggregatedQuote,
        lp_quote: LPQuote
    ) -> Dict:
        """
        Execute a confirmed quote.

        Args:
            quote: Aggregated client quote
            lp_quote: Original LP quote

        Returns:
            Execution result dictionary with:
            - execution_id: Unique execution ID
            - status: 'SUCCESS' or 'FAILED'
            - lp_name: LP name
            - exchange_side: Hedge side
            - quantity/quote_qty: Hedge parameters
            - executed_qty/executed_quote_qty: Execution results
            - avg_price: Execution price
            - commission: Commission paid
            - pnl_amount: Gross P&L
            - pnl_asset: P&L asset
            - pnl_after_fees: Net P&L
            - pnl_bps: P&L in basis points
            - error_message: Error if failed
            - executed_at: Timestamp
        """
        execution_id = self._generate_execution_id()
        executed_at = time.time()

        try:
            # Get LP instance
            lp = self.lps.get(quote.lp_name)
            if not lp:
                raise ValueError(f"LP not found: {quote.lp_name}")

            # Get pair config
            pair_config = get_pair_config(f"{quote.base_asset}{quote.quote_asset}")

            # Calculate hedge parameters
            exchange_side, quantity, quote_qty = determine_hedge_params(
                quote,
                quote.side,
                quote.target_asset,
                pair_config
            )

            # Execute with LP (client side trade)
            lp_success = await lp.execute_trade(lp_quote, quote)

            if not lp_success:
                # LP execution failed
                result = {
                    'execution_id': execution_id,
                    'status': 'FAILED',
                    'quote_id': quote.quote_id,
                    'lp_name': quote.lp_name,
                    'exchange_side': exchange_side,
                    'quantity': quantity,
                    'quote_qty': quote_qty,
                    'error_message': 'LP execution failed',
                    'executed_at': executed_at
                }

                # Log to database
                if self.quote_logger:
                    self._log_execution(result)

                return result

            # Simulate hedge execution (in production, this would be a real exchange trade)
            exec_result = execute_simulated_trade(
                quote, exchange_side, quantity, quote_qty, quote.lp_price
            )

            # Calculate P&L
            pnl_amount, pnl_asset, pnl_after_fees, pnl_bps = calculate_pnl(
                quote, quote.side, quote.target_asset, exec_result, pair_config
            )

            # Build execution result
            result = {
                'execution_id': execution_id,
                'status': 'SUCCESS',
                'quote_id': quote.quote_id,
                'lp_name': quote.lp_name,
                'exchange_side': exchange_side,
                'quantity': quantity,
                'quote_qty': quote_qty,
                'executed_qty': exec_result['executed_qty'],
                'executed_quote_qty': exec_result['executed_quote_qty'],
                'avg_price': exec_result['avg_price'],
                'commission': exec_result['commission'],
                'commission_asset': quote.base_asset if exchange_side == 'BUY' else quote.quote_asset,
                'pnl_amount': pnl_amount,
                'pnl_asset': pnl_asset,
                'pnl_after_fees': pnl_after_fees,
                'pnl_bps': pnl_bps,
                'error_message': None,
                'executed_at': executed_at
            }

            # Log to database
            if self.quote_logger:
                self._log_execution(result)

            return result

        except Exception as e:
            # Execution error
            result = {
                'execution_id': execution_id,
                'status': 'FAILED',
                'quote_id': quote.quote_id,
                'lp_name': quote.lp_name,
                'exchange_side': None,
                'quantity': None,
                'quote_qty': None,
                'error_message': str(e),
                'executed_at': executed_at
            }

            # Log to database
            if self.quote_logger:
                self._log_execution(result)

            return result

    def _generate_execution_id(self) -> str:
        """Generate unique execution ID"""
        return f"E{datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:19]}"

    def _log_execution(self, result: Dict) -> None:
        """
        Log execution to database.

        Args:
            result: Execution result dictionary
        """
        if not self.quote_logger:
            return

        try:
            conn = self.quote_logger.conn
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO executions (
                    execution_id, quote_id, status, lp_name, exchange_side,
                    quantity, quote_qty, executed_qty, executed_quote_qty,
                    avg_price, commission, commission_asset,
                    pnl_amount, pnl_asset, pnl_after_fees, pnl_bps,
                    error_message, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['execution_id'],
                result['quote_id'],
                result['status'],
                result['lp_name'],
                result.get('exchange_side'),
                result.get('quantity'),
                result.get('quote_qty'),
                result.get('executed_qty'),
                result.get('executed_quote_qty'),
                result.get('avg_price'),
                result.get('commission'),
                result.get('commission_asset'),
                result.get('pnl_amount'),
                result.get('pnl_asset'),
                result.get('pnl_after_fees'),
                result.get('pnl_bps'),
                result.get('error_message'),
                result['executed_at']
            ))

            conn.commit()

        except Exception as e:
            print(f"[ExecutionManager] Error logging execution: {e}")
            conn.rollback()
