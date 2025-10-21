# LP Aggregation RFQ System

A standalone Request-for-Quote (RFQ) system that aggregates liquidity from multiple Liquidity Providers (LPs), selects the best quote, and streams live price improvements to clients.

## Overview

This system removes dependencies on centralized exchanges (like Binance) and focuses purely on LP aggregation:

1. **Operator Input**: Terminal interface for entering quote requests (side, amount, pair)
2. **Async LP Polling**: Concurrently pings multiple LPs for quotes
3. **Best Quote Selection**: Chooses optimal price (min for BUY, max for SELL)
4. **Markup Application**: Adds configurable markup to LP quotes
5. **Quote Streaming**: Continuously polls LPs and displays price improvements in real-time

## Features

- **Risk-Free Model**: No order book dependencies, purely aggregating LP quotes
- **Async Architecture**: Concurrent LP polling using Python asyncio
- **Quote Locking**: Smart locking system that freezes best LP quote and only polls competitors
- **Price Improvement Detection**: Automatically detects meaningful improvements (≥1 basis point)
- **Validity Management**: Client quotes have shorter validity than LP quotes (safety buffer)
- **Mock LP Support**: Built-in mock LPs for testing without real integrations
- **Real-time Monitor**: Tkinter GUI with Mario Kart-style leaderboard displaying LP competition
- **Configurable**: Settings via environment variables (.env file)
- **Clean Separation**: Pricing completely separated from execution

## Architecture

```
┌─────────────────┐
│  Operator Input │  (Terminal Interface)
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Quote Streamer  │  (Continuous polling + callbacks)
└────────┬────────┘
         │
         v
┌─────────────────┐
│  LP Aggregator  │  (Select best + apply markup)
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│  LP1    LP2    LP3    ...  LPn  │  (Async concurrent polling)
└─────────────────────────────────┘
```

## Project Structure

```
lp-rfq/
├── src/
│   ├── core/
│   │   ├── models.py           # Data models (QuoteRequest, LPQuote, AggregatedQuote)
│   │   ├── lp_aggregator.py    # Core aggregation logic
│   │   └── quote_streamer.py   # Live quote streaming
│   ├── lps/
│   │   ├── base_lp.py          # LP interface (ABC)
│   │   └── mock_lp.py          # Mock LP for testing
│   ├── ui/
│   │   └── terminal.py         # Terminal interface
│   ├── config/
│   │   └── settings.py         # Configuration management
│   └── main.py                 # Application entry point
├── .env.example                # Example configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Installation

1. **Clone or navigate to project directory**:
   ```bash
   cd lp-rfq
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure settings** (optional):
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

## Usage

### Running the Application

```bash
python -m src.main
```

### Operator Workflow

1. Application starts and displays banner
2. Operator enters quote request:
   - **Side**: `b` (buy) or `s` (sell)
   - **Amount**: Quantity to trade (e.g., 1.5)
   - **Pair**: Trading pair (e.g., BTCUSDT)
3. System streams quotes for configured duration (default: 30s)
4. Price improvements are highlighted automatically
5. Operator can request another quote or exit

### Example Session

```
==============================================================
  LP Aggregation RFQ System
==============================================================

LP Aggregation Mode - Mock LPs
Markup: 5.0 bps
LPs: 3 mock providers

Enter Quote Request:
  Side (b/buy or s/sell): b
  Amount: 1.5
  Pair (e.g., BTCUSDT): BTCUSDT

Request: BUY 1.5 BTC/USDT

Streaming quotes for 30s...
Press Ctrl+C to stop early

==============================================================
  Quote #Q20250119-143025-123
==============================================================
  LP Source: MockLP-1
  Client BUYS 1.50000000 BTC
  Client Price: 100,050.5000 USDT
  LP Price: 100,000.0000 USDT
  Markup: 5.0 bps

  Client Pays: 150,075.75000000 USDT
  Client Receives: 1.50000000 BTC

  Valid for: 8.0s
==============================================================

*** PRICE IMPROVEMENT ***
...
```

## Configuration

Edit `.env` to customize settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `MARKUP_BPS` | 5.0 | Markup in basis points added to LP quotes |
| `VALIDITY_BUFFER_SECONDS` | 2.0 | Safety buffer (client validity = LP validity - buffer) |
| `POLL_INTERVAL_MS` | 500 | Milliseconds between LP polls during streaming |
| `DEFAULT_STREAM_DURATION_SECONDS` | 30 | How long to stream quotes before expiring |
| `MOCK_LP_COUNT` | 3 | Number of mock LPs to create |
| `MOCK_BASE_PRICE` | 100000.0 | Base price for mock LPs (BTCUSDT) |
| `MOCK_SPREAD_BPS` | 5.0 | Spread for mock LP quotes |
| `MOCK_MIN_DELAY` | 0.1 | Minimum response delay (seconds) |
| `MOCK_MAX_DELAY` | 0.5 | Maximum response delay (seconds) |
| `MOCK_FAILURE_RATE` | 0.0 | Percentage of failed LP responses (0.0-1.0) |

## Adding Real LP Integrations

To integrate a real LP, create a new class inheriting from `LiquidityProvider`:

```python
# src/lps/my_lp.py

from ..core.models import QuoteRequest, LPQuote
from .base_lp import LiquidityProvider
from typing import Optional
import time

class MyCustomLP(LiquidityProvider):
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(name="MyLP")
        self.api_key = api_key
        self.api_secret = api_secret

    async def request_quote(self, request: QuoteRequest) -> Optional[LPQuote]:
        """Request quote from LP API"""
        # Your custom API integration here
        response = await self._call_lp_api(request)

        return LPQuote(
            lp_name=self.name,
            price=response['price'],
            quantity=response['quantity'],
            validity_seconds=response['validity'],
            timestamp=time.time(),
            side=request.side,
            metadata=response.get('metadata')
        )

    async def _call_lp_api(self, request):
        # Implement your LP's API call
        pass
```

Then update `src/main.py` to use your LP instead of mocks:

```python
def create_lps() -> List[LiquidityProvider]:
    return [
        MyCustomLP(api_key="...", api_secret="..."),
        AnotherLP(endpoint="...", token="..."),
        # ...
    ]
```

## Key Concepts

### Quote Flow

1. **QuoteRequest**: Operator specifies side, amount, base/quote assets
2. **LP Polling**: All LPs polled concurrently with `asyncio.gather()`
3. **Best Selection**:
   - BUY: Minimum price (client pays less)
   - SELL: Maximum price (client receives more)
4. **Markup Application**:
   - BUY: `client_price = lp_price * (1 + markup_bps / 10000)`
   - SELL: `client_price = lp_price * (1 - markup_bps / 10000)`
5. **Validity Buffer**: Client quote valid for `LP_validity - 2s` (safety)

### Quote Locking System

The system implements intelligent quote locking to provide stable client pricing:

1. **First Poll**: Query ALL LPs and lock the winner
2. **Subsequent Polls**: Query only competing (non-locked) LPs
3. **Improvement Detection**: Switch lock only if competitor beats current by ≥1 basis point
4. **Competitive Re-polling**: Previously locked LPs can compete again after being beaten
5. **Frozen Display**: Locked LP shows frozen quote data (not re-polled)

**Benefits**:
- Stable client pricing (no continuous updates)
- Reduced LP polling (saves API calls)
- Only meaningful improvements shown (≥1bp threshold)
- Previous winners can come back to compete

**Example Flow**:
```
[Poll 1] LOCKED: LP-Alpha @ 99,850.00
[Poll 2-10] LP-Alpha stays locked (competitors don't beat by ≥1bp)
[Poll 11] IMPROVEMENT: LP-Beta @ 99,840.00 (unlocked LP-Alpha)
[Poll 12-20] LP-Beta stays locked
```

### Price Improvement Detection

During streaming, each competitor quote is compared to the locked quote:
- **BUY improvement**: New price ≤ (locked_price - 1bp threshold)
- **SELL improvement**: New price ≥ (locked_price + 1bp threshold)

**1 basis point = 0.01% = 0.0001**
- For $99,850 quote: 1bp = $9.985
- Improvement requires: new_price ≤ $99,840.015 (for BUY)

Improvements are automatically highlighted in the terminal output and monitor GUI.

## Testing

### Manual Testing with Monitor GUI

Test with mock LPs and monitor GUI:
```bash
python test_monitor_manual.py
```

This will:
- Open the Tkinter monitor GUI (Mario Kart-style leaderboard)
- Stream quotes for 15 seconds
- Display real-time LP rankings with price updates
- Show quote locking behavior

### Testing Scenarios

Three pre-built scenarios to test different LP behaviors:

**Scenario 1: Competing LPs (Offset Descending Sine)**
```bash
python test_scenario_1.py
```
- 4 LPs with sine wave prices (different phases)
- All LPs actively compete
- Demonstrates dynamic lock switching

**Scenario 2: Non-Competition (Best Stays #1)**
```bash
python test_scenario_2.py
```
- 1 LP consistently provides best quote (fixed low price)
- Other LPs compete for 2nd-4th place
- Demonstrates stable locking (no improvements)

**Scenario 3: Hail Mary (Last-Second Improvement)**
```bash
python test_scenario_3.py
```
- Most LPs provide normal quotes
- 1 LP dramatically improves at T-1s before expiry
- Demonstrates last-second lock switching

### Run Pytest

```bash
pytest tests/
```

### Main Application

Test with default configuration:
```bash
python -m src.main
```

## Differences from Original RFQ System

This LP aggregation system differs from the Binance-based RFQ system:

| Feature | Original RFQ | LP Aggregation |
|---------|--------------|----------------|
| **Price Source** | Binance order book | Multiple LP APIs |
| **Execution** | Direct Binance trade | LP handles execution |
| **Risk** | Market risk (slippage) | No market risk (firm quotes) |
| **Dependencies** | Binance API, WebSocket | LP integrations only |
| **Quote Validity** | Based on market depth | LP-specific validity |
| **Monitoring** | Tkinter GUI (advanced) | Tkinter GUI (Mario Kart leaderboard) |
| **Quote Locking** | N/A | Smart locking with 1bp threshold |

## Future Enhancements

- [x] Tkinter GUI for quote display (Mario Kart-style leaderboard) ✅
- [x] Quote locking system with improvement threshold ✅
- [x] Testing scenarios (Competing, Non-competition, Hail Mary) ✅
- [x] Make improvement threshold configurable ✅
- [x] Database logging (quote blotter) ✅
- [ ] Quote analytics and reporting
- [ ] Quote execution integration

## Nice to have (if we go live)

- [ ] Advanced LP selection logic (weighted, tiered) 
- [ ] LP performance tracking (fill rates, latency)
- [ ] Chat-based interaction 
    - For this one im thinking the terminal asks to click on the client chat to provide initial quote so the timer is in-sync.
- [ ] Flow Orchestration (Order matching)
- [ ] LP parameter awareness (Rate limits, etc.)


## Development Status

**Current Phase**: Phase 1 Complete ✅

Core functionality implemented:
- ✅ Async LP aggregation
- ✅ Quote streaming with price improvements
- ✅ Terminal operator interface
- ✅ Mock LP for testing
- ✅ Configurable settings
- ✅ Tkinter monitor GUI (Mario Kart-style leaderboard)
- ✅ Quote locking system with configurable improvement threshold
- ✅ Testing scenarios (Competing, Non-competition, Hail Mary)
- ✅ SQLite database logging (quotes, LP responses, performance tracking)

**Next Steps**:
1. ✅ Make improvement threshold configurable - COMPLETE
2. ✅ Add database logging for quote blotter - COMPLETE
3. Implement quote execution integration with LPs
4. Add LP performance analytics (fill rates, latency tracking)
5. Consider chat-based interaction for client quotes 
  

## License

Internal project - no license specified.

## Contact

For questions or issues, contact the development team.
