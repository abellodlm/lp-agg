# LP Aggregation System - Testing Scenarios

This document describes the three testing scenarios implemented to validate the LP aggregation and monitor system.

## Running the Tests

```bash
cd lp-rfq
python test_scenarios.py
```

The script will run all three scenarios sequentially. Press ENTER between scenarios to proceed.

---

## Scenario 1: Competing LPs (Offset Descending Sine)

### Purpose
Test system behavior when all LPs actively compete with dynamic, oscillating prices.

### Setup
- **4 LPs** with sine wave price strategies
- Each LP has different:
  - Amplitude (price oscillation range)
  - Frequency (how fast prices change)
  - Phase offset (timing of price cycles)
  - Trend (downward price drift)

### Price Formula
```
price = base_price + amplitude × sin(2π × frequency × time + offset) + trend × time
```

### Expected Behavior
- **Winner changes frequently** as sine waves intersect
- **Price improvements** occur regularly (multiple times per cycle)
- **Leaderboard shuffles** - different LPs take 1st place
- **Downward trend** - overall prices decrease over time

### Example Output
```
[Poll 1] ⬆ IMPROVEMENT: 99,850.00 from LP-Alpha
[Poll 3] ⬆ IMPROVEMENT: 99,720.00 from LP-Beta
[Poll 7] ⬆ IMPROVEMENT: 99,650.00 from LP-Gamma
...
Total polls: 40
Price improvements: 12
Improvement rate: 30%
```

### What to Observe in Monitor
- Winner badge (🥇) moves between LPs
- Green highlight switches as new LP takes 1st place
- Smooth price transitions
- All LPs visible in leaderboard

### Key Insights
- Tests **price improvement detection** accuracy
- Validates **leaderboard re-ranking** logic
- Verifies **concurrent LP polling** works correctly

---

## Scenario 2: Non-Competition (Best Stays #1)

### Purpose
Test system behavior when one LP consistently provides best quote while others compete for 2nd place.

### Setup
- **1 Fixed LP** ("LP-BestBid") - always provides lowest price (99,500)
- **3 Competing LPs** - oscillating prices around 100,000-100,200

### Expected Behavior
- **LP-BestBid always wins** (stays in 1st place)
- **2nd-4th positions shuffle** as other LPs compete
- **Fewer price improvements** (only on initial quote)
- **Stable top quote** for client

### Example Output
```
[Poll 1] ⬆ IMPROVEMENT: 99,548.73 from LP-BestBid
[Poll 5] Best: 99,548.73 from LP-BestBid
[Poll 10] Best: 99,548.73 from LP-BestBid
...
Total polls: 30
Price improvements: 1
Improvement rate: 3.3%
```

### What to Observe in Monitor
- **LP-BestBid stays in 1st** (green highlight, "BEST" badge)
- **2nd-4th positions change** as other LPs oscillate
- Client price **remains stable** (good for execution)
- Delta percentages update for 2nd-4th place

### Key Insights
- Tests **stable best quote** scenario (common in real markets)
- Validates **partial leaderboard updates** (only 2nd-4th change)
- Demonstrates **low volatility** quoting environment

---

## Scenario 3: Hail Mary (Last Second Improvement)

### Purpose
Test system behavior when a dramatic price improvement occurs just before quote expiry.

### Setup
- **3 Normal LPs** - stable prices around 100,000-100,200
- **1 Hail Mary LP** - mediocre price (100,300) until T-1s, then drops to 99,800

### Quote Validity
- LPs provide 10s validity
- Client sees 8s validity (2s buffer)
- Improvement window: Last 1 second

### Expected Behavior
- **First 9 seconds**: Normal LPs provide best quotes (LP-Normal1 wins)
- **Last 1 second**: Hail Mary LP suddenly becomes best
- **Late price improvement** triggers alert
- **Monitor updates** to show new winner

### Timeline
```
T=0s:   LP-Normal1 wins @ 100,000
T=5s:   LP-Normal1 still best @ 100,000
T=9s:   LP-HailMary improves to 99,800 (NEW BEST!)
T=10s:  Quote expires
```

### Example Output
```
[Poll 1] ⬆ IMPROVEMENT: 100,050.00 from LP-Normal1
[Poll 5] Best: 100,050.00 from LP-Normal1
[Poll 10] Best: 100,050.00 from LP-Normal1
[Poll 18] ⬆ IMPROVEMENT: 99,848.73 from LP-HailMary  <-- Hail Mary!
...
Total polls: 24
Price improvements: 2
Improvement rate: 8.3%
```

### What to Observe in Monitor
- **Stable winner** for first ~9s
- **Sudden switch** to LP-HailMary at end
- **Green highlight** moves to new winner
- **Price drop** clearly visible in client price

### Key Insights
- Tests **late price improvements** (edge case)
- Validates **last-second updates** work correctly
- Demonstrates **quote validity management**
- Real-world scenario: LP adjusts quote before expiry

---

## Interpreting Results

### Healthy System Behavior

**Scenario 1 (Competing):**
- ✅ 10-40% improvement rate (dynamic competition)
- ✅ Multiple different winners
- ✅ Smooth leaderboard transitions

**Scenario 2 (Non-Competition):**
- ✅ <5% improvement rate (stable market)
- ✅ Same LP wins consistently
- ✅ Lower rankings change frequently

**Scenario 3 (Hail Mary):**
- ✅ Exactly 2 improvements (initial + last second)
- ✅ Late improvement detected
- ✅ Monitor updates correctly at T-1s

### Red Flags

❌ **No price improvements** - Detection logic broken
❌ **Wrong LP wins** - Selection logic incorrect
❌ **Monitor doesn't update** - Callback not working
❌ **Leaderboard out of order** - Sorting broken
❌ **Late improvements missed** - Timing issue

---

## Technical Details

### ScenarioLP Class

Custom LP implementation for testing scenarios:

```python
class ScenarioLP(LiquidityProvider):
    def __init__(self, name: str, strategy: str, **kwargs):
        self.strategy = strategy  # 'sine', 'fixed', 'hail_mary'
        self.params = kwargs

    async def request_quote(self, request: QuoteRequest) -> LPQuote:
        # Generate price based on strategy
        if self.strategy == 'sine':
            price = self._sine_price(elapsed)
        elif self.strategy == 'fixed':
            price = self.params['base_price']
        elif self.strategy == 'hail_mary':
            price = self._hail_mary_price(elapsed)

        return LPQuote(...)
```

### Sine Wave Strategy

Creates oscillating prices:
- **Amplitude**: How much price varies (±)
- **Frequency**: How fast it oscillates (Hz)
- **Offset**: Phase shift (creates competition)
- **Trend**: Long-term price direction

### Hail Mary Strategy

Time-based price change:
```python
def _hail_mary_price(self, elapsed):
    if time_until_expiry <= 1.0:
        return base_price - 500  # Dramatic improvement
    else:
        return base_price  # Mediocre price
```

---

## Extending Scenarios

### Add Custom Scenario

```python
async def scenario_4_custom():
    """Your custom test scenario"""
    lps = [
        ScenarioLP("LP-1", "sine", base_price=100000, amplitude=300),
        ScenarioLP("LP-2", "fixed", base_price=99000),
        # ... more LPs
    ]

    await run_scenario("Custom Scenario Name", lps, duration=20)
```

### Modify Parameters

Edit the scenario functions in `test_scenarios.py`:

```python
# Increase volatility
amplitude=300  # instead of 150

# Faster price changes
frequency=1.0  # instead of 0.4

# Longer test duration
duration=60  # instead of 15
```

---

## Manual Testing

For quick manual tests without scenarios:

```bash
python test_monitor_manual.py
```

This runs a simple 15-second test with 5 mock LPs.

---

## Next Steps

After running these scenarios, you should have validated:
- ✅ Monitor displays correctly
- ✅ LP leaderboard ranks properly
- ✅ Price improvements detected
- ✅ Quote streaming works
- ✅ Edge cases handled (late improvements)

You're now ready to integrate real LP APIs!
