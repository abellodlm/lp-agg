"""Quick test for Scenario 2: Non-Competition"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_scenarios import scenario_2_non_competition

if __name__ == "__main__":
    try:
        print("\n\nStarting Scenario 2: Non-Competition (Best Stays #1)")
        print("="*70)
        print("\nThe monitor window will show LP-BestBid always winning.")
        print("Other LPs compete for 2nd-4th place.\n")

        asyncio.run(scenario_2_non_competition())

        print("\n\nScenario 2 complete! Check the monitor window.")
        input("\nPress ENTER to exit...")

    except KeyboardInterrupt:
        print("\n\nTest interrupted.\n")
