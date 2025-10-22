"""
Execution module for LP Aggregation RFQ System.

Provides hedge calculation, P&L calculation, and trade execution simulation.
"""

from .hedge_calculator import determine_hedge_params
from .pnl_calculator import calculate_pnl
from .simulator import execute_simulated_trade

__all__ = [
    'determine_hedge_params',
    'calculate_pnl',
    'execute_simulated_trade'
]
