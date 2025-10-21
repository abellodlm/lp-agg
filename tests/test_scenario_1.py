"""Quick test for Scenario 1: Competing LPs"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_scenarios import scenario_1_competing

if __name__ == "__main__":
    try:
        print("\n\nStarting Scenario 1: Competing LPs (Offset Descending Sine)")
        print("="*70)
        print("\nThe monitor window will open and show live LP competition.")
        print("Watch as different LPs take turns winning with sine wave prices.\n")

        asyncio.run(scenario_1_competing())

        print("\n\nScenario 1 complete! Check the monitor window.")
        input("\nPress ENTER to exit...")

    except KeyboardInterrupt:
        print("\n\nTest interrupted.\n")
