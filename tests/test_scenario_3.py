"""Quick test for Scenario 3: Hail Mary"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_scenarios import scenario_3_hail_mary

if __name__ == "__main__":
    try:
        print("\n\nStarting Scenario 3: Hail Mary (Quote Improves at T-1s)")
        print("="*70)
        print("\nWatch for the dramatic price improvement in the last second!")
        print("LP-HailMary will suddenly become best right before expiry.\n")

        asyncio.run(scenario_3_hail_mary())

        print("\n\nScenario 3 complete! Did you see the last-second improvement?")
        input("\nPress ENTER to exit...")

    except KeyboardInterrupt:
        print("\n\nTest interrupted.\n")
