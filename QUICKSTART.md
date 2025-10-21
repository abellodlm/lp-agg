# LP Aggregation RFQ System - Quick Start Guide

## What You Just Built

A complete LP aggregation system with:
- ✅ **Mario Kart style leaderboard** (Tkinter monitor)
- ✅ **Non-blocking terminal** (enter commands while streaming)
- ✅ **Auto-refresh toggle** (continuous quote updates)
- ✅ **Real-time LP ranking** (1st place green/large, 2nd-3rd normal, 4th+ gray/small)
- ✅ **Price improvement detection**
- ✅ **Async LP polling** (concurrent, efficient)

## Running the System

```bash
cd lp-rfq
python -m src.main
```

## How to Use

### 1. System Startup

When you run the application:
- Monitor window opens automatically (always-on-top)
- Terminal shows available commands
- 3 mock LPs are ready (MockLP-1, MockLP-2, MockLP-3)

### 2. Request a Quote

**Format:** `<side> <amount> <pair>`

**Examples:**
```
> b 1.5 btcusdt        # BUY 1.5 BTC/USDT
> s 2.0 ethusdt        # SELL 2.0 ETH/USDT
> buy 0.5 btcusdc      # BUY 0.5 BTC/USDC
```

### 3. Monitor Updates

The Tkinter window shows:

**Top Section - Best Quote:**
- Quote ID
- Client operation (e.g., "Client BUYS 1.5 BTC for 149,850.00 USDT")
- Client price (with markup applied)
- LP source + markup
- Validity countdown (⏱ 28s)

**Middle Section - LP Leaderboard:**
```
🥇 MOCKUP-A (BEST)               [Green background, large font]
   99,850.00 USDT  |  ⏱ 8s  |  📡 250ms

🥈 MockLP-B                      [White text, normal font]
   99,900.00 USDT (+0.05%)  |  ⏱ 7s  |  📡 320ms

🥉 MockLP-C                      [White text, normal font]
   99,970.00 USDT (+0.12%)  |  ⏱ 9s  |  📡 180ms
```

**Bottom Section - Status:**
- Poll count
- LP response rate (e.g., "3/3 LPs responded")
- Last update timestamp
- Auto-refresh checkbox

### 4. Terminal Commands

While streaming, you can:

| Command | Action |
|---------|--------|
| `b 1.5 btcusdt` | Start new quote request (auto-stops previous) |
| `x` | Stop current stream |
| `q` | Quit application |

**The terminal never blocks** - you can always enter commands!

### 5. Auto-Refresh Feature

In the monitor window, check/uncheck the "Auto-refresh" box:

- ☑ **Enabled**: When quote expires, automatically requests fresh quote
  - Continues streaming indefinitely
  - Monitor shows continuous updates

- ☐ **Disabled**: When quote expires, streaming stops
  - Monitor shows "Quote expired - waiting for new request"
  - Enter new request manually in terminal

## How It Works

### LP Aggregation Flow

```
Operator enters: b 1.5 btcusdt
         ↓
Quote Request Created (BUY 1.5 BTC/USDT)
         ↓
Ping 3 LPs concurrently (async)
    ├─> LP-A: 99,850.00 USDT (250ms)
    ├─> LP-B: 99,900.00 USDT (320ms)
    └─> LP-C: 99,970.00 USDT (180ms)
         ↓
Select Best: LP-A (lowest for BUY)
         ↓
Apply Markup: 99,850.00 × (1 + 5 bps) = 99,900.00
         ↓
Display to Client: 99,900.00 USDT
         ↓
Monitor Updates (every 500ms)
         ↓
Price Improvement Detection
    - New best < Current best (for BUY)
    - Flash green in terminal
    - Update monitor leaderboard
```

### Mario Kart Leaderboard Logic

LPs are ranked by price (best first):
- **For BUY**: Lowest ask price wins (client pays less)
- **For SELL**: Highest bid price wins (client receives more)

Visual hierarchy:
1. **🥇 1st Place**: Green background, 16pt font, "BEST" badge
2. **🥈 2nd Place**: White text, 14pt font, shows delta from best
3. **🥉 3rd Place**: White text, 14pt font, shows delta from best
4. **4th+**: Gray text, 12pt font, smaller display

Each LP shows:
- Price
- Delta from best (e.g., "+0.05%")
- Validity remaining
- Response latency

## Configuration

Edit `.env` to customize:

```ini
# Markup applied to LP quotes
MARKUP_BPS=5.0

# Client quote validity = LP validity - buffer
VALIDITY_BUFFER_SECONDS=2.0

# How often to poll LPs during streaming
POLL_INTERVAL_MS=500

# Number of mock LPs to create
MOCK_LP_COUNT=3

# Mock LP base price (BTCUSDT)
MOCK_BASE_PRICE=100000.0
```

## Adding Real LPs

To integrate a real LP:

1. Create new file: `src/lps/my_custom_lp.py`

```python
from ..lps.base_lp import LiquidityProvider
from ..core.models import QuoteRequest, LPQuote
import time

class MyCustomLP(LiquidityProvider):
    def __init__(self, name: str, api_key: str):
        self.name = name
        self.api_key = api_key

    async def request_quote(self, request: QuoteRequest) -> Optional[LPQuote]:
        # Call your LP's API
        response = await self._call_lp_api(request)

        return LPQuote(
            lp_name=self.name,
            price=response['price'],
            quantity=response['quantity'],
            validity_seconds=response['validity'],
            timestamp=time.time(),
            side=request.side,
            metadata={'custom_field': response.get('extra_data')}
        )

    async def _call_lp_api(self, request):
        # Implement your LP's specific API call
        pass
```

2. Update `src/main.py`:

```python
def create_lps() -> List[LiquidityProvider]:
    return [
        MyCustomLP("LP-Alpha", api_key="..."),
        MyCustomLP("LP-Beta", api_key="..."),
        AnotherLP("LP-Gamma", endpoint="..."),
    ]
```

## Troubleshooting

### Monitor doesn't open
- Check if another instance is running
- Try restarting the application

### Terminal input blocked
- This shouldn't happen! If it does, press Ctrl+C and restart

### No LP responses
- Check network connection (for real LPs)
- Verify LP API credentials
- Check mock LP configuration in `.env`

### Quote expired immediately
- Increase `VALIDITY_BUFFER_SECONDS` in `.env`
- Check LP validity times (mock LPs default to 10s)

## Key Features

### Non-Blocking Terminal
Unlike traditional RFQ systems, you can:
- Enter new quote request while current one streams
- Stop stream without killing application
- Switch pairs mid-stream

The secret: Background async tasks + simple blocking input()

### Price Improvement Detection
The system continuously polls LPs and detects when a better price is found:
- **BUY improvement**: New price < Current best
- **SELL improvement**: New price > Current best

Terminal shows:
```
[!] Price improvement: 99,850.00 USDT from LP-A
```

Monitor highlights winner in green with larger font.

### Thread-Safe Updates
- Monitor runs in daemon thread
- Quotes stream in async tasks
- Terminal input in main thread
- All updates are thread-safe with locks

## Next Steps

1. **Test with different pairs**: Try ETH, other assets
2. **Enable auto-refresh**: Test continuous streaming
3. **Adjust markup**: Modify `MARKUP_BPS` in `.env`
4. **Add real LPs**: Follow "Adding Real LPs" guide above
5. **Monitor multiple requests**: Enter new requests while streaming

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  Terminal (Main Thread)                         │
│  - Blocking input() loop                        │
│  - Command parsing                              │
│  - Task management                              │
└─────────────────────────────────────────────────┘
                    │
                    ├─> Launches
                    ↓
┌─────────────────────────────────────────────────┐
│  Quote Streamer (Async Task)                    │
│  - Polls LPs every 500ms                        │
│  - Detects price improvements                   │
│  - Calls monitor update callback                │
└─────────────────────────────────────────────────┘
                    │
                    ├─> Updates
                    ↓
┌─────────────────────────────────────────────────┐
│  Monitor GUI (Daemon Thread)                    │
│  - Tkinter window                               │
│  - Thread-safe updates                          │
│  - Auto-refresh toggle                          │
└─────────────────────────────────────────────────┘
```

## Success!

You now have a fully functional LP aggregation RFQ system with:
- Real-time quote streaming
- Mario Kart style leaderboard
- Non-blocking terminal
- Auto-refresh capability
- Price improvement detection

**Run it:** `python -m src.main`

Enjoy! 🚀
