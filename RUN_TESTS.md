# How to Run Tests

## Monitor is Working! ✅

The LP Aggregation Monitor with Mario Kart leaderboard is fully functional.

## Quick Tests

### Option 1: Manual Test (15 seconds)
```bash
python tests/test_monitor_manual.py
```
- Opens monitor window
- Shows 5 mock LPs
- Streams for 15 seconds
- Good for verifying monitor displays correctly

### Option 2: Scenario Tests (Individual)

**Scenario 1: Competing LPs**
```bash
python tests/test_scenario_1.py
```
- 4 LPs with sine wave prices
- Dynamic competition
- Winner changes frequently
- Duration: 20 seconds

**Scenario 2: Non-Competition**
```bash
python tests/test_scenario_2.py
```
- 1 LP always wins (best price)
- Other LPs compete for 2nd-4th
- Stable winner scenario
- Duration: 15 seconds

**Scenario 3: Hail Mary**
```bash
python tests/test_scenario_3.py
```
- Dramatic price improvement at T-1s
- Tests late-breaking changes
- Watch for last-second switch!
- Duration: 12 seconds

### Option 3: All Scenarios (Sequential)
```bash
python tests/test_scenarios.py
```
- Runs all 3 scenarios
- Press ENTER between each
- Total time: ~50 seconds

## What to Look For

When running any test, the Tkinter monitor window should show:

### Best Quote Section (Top)
- Quote ID
- Client operation (e.g., "Client BUYS 1.5 BTC for 149,850 USDT")
- Large client price
- LP source + markup
- Countdown timer (⏱ 8s)

### LP Leaderboard (Middle)
```
🥇 LP-NAME (BEST)           [Green background, large font]
   99,850.00 USDT | ⏱ 8s | 📡 250ms

🥈 LP-NAME                  [White text, normal font]
   99,900.00 (+0.05%) | ⏱ 7s | 📡 320ms

🥉 LP-NAME                  [White text, normal font]
   99,970.00 (+0.12%) | ⏱ 9s | 📡 180ms

   LP-NAME                  [Gray text, smaller font]
   100,020.00 (+0.17%) | ⏱ 6s | 📡 420ms
```

### Status Bar (Bottom)
- Poll count
- LP response rate (e.g., "5/5 LPs responded")
- Auto-refresh checkbox
- Last update timestamp

## Terminal Output

You'll also see terminal output like:

```
[Poll 1] ^ IMPROVEMENT: 99,548.73 from LP-Gamma
[Poll 5] Best: 99,610.69 from LP-Alpha (5 LPs)
[Poll 8] ^ IMPROVEMENT: 99,073.10 from LP-Alpha
...
```

Green = Price improvement
White = Regular update

## Expected Results

### Scenario 1 (Competing)
- 10-40% improvement rate
- Multiple LPs win at different times
- Leaderboard constantly shuffles

### Scenario 2 (Non-Competition)
- <5% improvement rate
- Same LP wins every time (LP-BestBid)
- 2nd-4th places shuffle

### Scenario 3 (Hail Mary)
- Exactly 2 improvements
- Late improvement at ~T-1s
- Dramatic price drop visible

## Troubleshooting

**Monitor doesn't open:**
- Wait a few seconds (initialization takes ~0.5s)
- Check if another instance is running
- Try closing other Python processes

**No terminal output:**
- This is normal! Monitor updates in background
- Terminal only shows improvements and periodic updates

**Unicode errors:**
- Fixed! Using ASCII characters (^, |, etc.)
- If you see encoding errors, report them

**Monitor empty/not updating:**
- Check if LPs are responding (terminal should show polls)
- Verify quote streaming started
- Try running manual test first

## Running the Main Application

To run the full application (not just tests):

```bash
python -m src.main
```

Then enter commands:
```
> b 1.5 btcusdt    # BUY 1.5 BTC/USDT
> s 2.0 ethusdt    # SELL 2.0 ETH/USDT
> x                # Stop stream
> q                # Quit
```

## Success Criteria

✅ **Monitor window opens** (always-on-top)
✅ **Best quote displays** at top
✅ **LP leaderboard shows** with proper styling
✅ **1st place highlighted** in green with larger font
✅ **Rankings update** as prices change
✅ **Countdown timer** works
✅ **Status bar** shows poll count
✅ **Terminal not blocked** (for main app)

If all these work, your system is ready! 🎉

## Next Steps

After validating with tests:
1. Integrate real LP APIs
2. Add database logging
3. Implement execution flow
4. Add performance tracking
5. Deploy to production

## Files Reference

| File | Purpose |
|------|---------|
| `tests/test_monitor_manual.py` | Quick 15s test |
| `tests/test_scenario_1.py` | Competing LPs test |
| `tests/test_scenario_2.py` | Non-competition test |
| `tests/test_scenario_3.py` | Hail Mary test |
| `tests/test_scenarios.py` | All scenarios (with prompts) |
| `TESTING_SCENARIOS.md` | Detailed scenario docs |
| `QUICKSTART.md` | User guide |

Happy testing! 🚀
