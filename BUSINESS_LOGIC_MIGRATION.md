# Business Logic Migration Roadmap
## From RFQ (Market Orders) to LP-RFQ (LP Aggregation)

**Created:** 2025-10-21
**Purpose:** Port critical business logic from the `rfq` system to the `lp-rfq` system

---

## Executive Summary

The **rfq** system is a mature market-making platform that executes risk trades via market orders on exchanges (e.g., Binance). The **lp-rfq** system is an LP aggregator that sources quotes from multiple liquidity providers. While lp-rfq has the core aggregation logic, it's missing several critical business logic components that exist in rfq.

This document maps the relationship between all trading variables and provides a concrete roadmap to port the missing logic.

---

## 1. Key Variable Interrelationships

### 1.1 Core Trading Variables

| Variable | Description | Source | Used In |
|----------|-------------|--------|---------|
| **pair** (symbol) | Trading pair (e.g., `BTCUSDT`, `USDCUSDT`) | User selection | Both systems |
| **base_asset** | Base currency of pair (e.g., `BTC`, `USDC`) | Pair config | Both systems |
| **quote_asset** | Quote currency of pair (e.g., `USDT`) | Pair config | Both systems |
| **side** | `BUY` or `SELL` (from client's perspective) | User input | Both systems |
| **amount** | Quantity being traded | User input | Both systems |
| **target_asset** | **Which asset the client is trading** | User input | **RFQ ONLY** |
| **profit_asset** | **Which asset to keep spread profit in** | Pair config | **RFQ ONLY** |
| **spread_bps** / **markup_bps** | Spread applied to market price | Config | Both (different names) |
| **market_price** | Current mid price (base/quote) | Market data / LP quote | Both systems |

### 1.2 Critical Missing Variables in lp-rfq

1. **`target_asset`** - Determines WHAT the client is actually trading
   - Is the client trading BTC or USDT on BTCUSDT?
   - This affects spread direction, amount calculations, and flows

2. **`profit_asset`** - Determines WHERE the market maker keeps profit
   - Keep profit in base (e.g., BTC) or quote (e.g., USDT)?
   - Affects hedge execution strategy and P&L calculations

---

## 2. Business Logic Comparison

### 2.1 RFQ System (Market Orders)

**Flow:**
1. Client specifies: `side`, `amount`, `target_asset`, `pair`
2. System fetches market price from exchange websocket
3. Pricing engine calculates quote with spread
4. **Balance check**: Validates market maker has funds to hedge
5. **VWAP calculation**: Accounts for order book slippage
6. Client accepts quote
7. **Hedge execution**: Determines which side to trade on exchange based on `target_asset` and `profit_asset`
8. **P&L calculation**: Calculates realized profit in the specified `profit_asset`

**Key Files:**
- [src/main.py](../rfq/src/main.py) - Lines 545-714 (hedge params, P&L calc)
- [src/config/pairs.py](../rfq/src/config/pairs.py) - Lines 12-23 (`TradingPairConfig` with `profit_asset`)
- [src/pricing/engine.py](../rfq/src/pricing/engine.py) - Lines 58-166 (`calculate_quote` with `target_asset`)
- [src/utils/input_handler.py](../rfq/src/utils/input_handler.py) - Gets `target_asset` from user

### 2.2 LP-RFQ System (LP Aggregation)

**Flow:**
1. Client specifies: `side`, `amount`, `pair`
2. System pings multiple LPs asynchronously
3. Aggregator selects best LP quote
4. Applies markup to LP price
5. Streams live updates with price improvements
6. (Execution logic not yet implemented)

**Key Files:**
- [src/main.py](src/main.py) - Main loop
- [src/core/models.py](src/core/models.py) - Lines 48-87 (`AggregatedQuote`)
- [src/core/lp_aggregator.py](src/core/lp_aggregator.py) - Lines 146-197 (`_create_aggregated_quote`)

**What's Missing:**
- No `target_asset` concept
- No `profit_asset` configuration - this is set internally. 
- No balance validation - we dont need it here. 
- No hedge parameter logic
- No P&L calculation
- Simplified flow calculation (assumes `amount` is always in base asset)

---

## 3. Critical Logic to Port

### 3.1 Target Asset Logic

**In RFQ:**
```python
# From pricing/engine.py:92-109
if target_asset == base_asset:
    # Client trading base - use side directly
    if side == 'BUY':
        effective_price = market_price * (1 + spread / 10000)
    else:  # SELL
        effective_price = market_price * (1 - spread / 10000)
else:
    # Client trading quote - invert spread direction
    if side == 'SELL':
        effective_price = market_price * (1 + spread / 10000)
    else:  # BUY
        effective_price = market_price * (1 - spread / 10000)
```

**Why It Matters:**
- When client trades quote asset instead of base, spread direction must be inverted
- Current lp-rfq assumes client always trades base asset

### 3.2 Profit Asset Logic

**In RFQ:**
```python
# From config/pairs.py:22
profit_asset: Literal['base', 'quote']  # Which asset to keep spread profit in
```

**In Hedge Execution (main.py:545-619):**
```python
def _determine_hedge_params(self, quote, side, target_asset, pair_config):
    profit_asset = pair_config.profit_asset

    if target_asset == base_asset:
        if side == 'BUY':
            if profit_asset == 'quote':
                # Keep profit in USDT - buy exact amount client receives
                quantity = quote.client_receives_amount
            else:
                # Keep profit in BTC - spend all USDT to buy more BTC
                quote_qty = quote.client_gives_amount
```

**Why It Matters:**
- Determines whether to use `quantity` or `quote_qty` in market orders
- Affects which asset accumulates spread profit over time
- Critical for risk management and treasury optimization

### 3.3 Amount Calculation Logic

**In RFQ (pricing/engine.py:111-144):**
```python
if target_asset == base_asset:
    if side == 'BUY':
        client_receives_amount = amount
        client_gives_amount = amount * effective_price
    else:  # SELL
        client_gives_amount = amount
        client_receives_amount = amount * effective_price
else:  # target_asset == quote_asset
    if side == 'BUY':
        client_receives_amount = amount
        client_gives_amount = amount / effective_price
    else:  # SELL
        client_gives_amount = amount
        client_receives_amount = amount / effective_price
```

**In LP-RFQ (lp_aggregator.py:163-174):**
```python
# SIMPLIFIED - always assumes amount is in base
if request.side == 'BUY':
    client_gives_amount = request.amount * client_price
    client_receives_amount = request.amount
else:  # SELL
    client_gives_amount = request.amount
    client_receives_amount = request.amount * client_price
```

**Problem:** LP-RFQ doesn't consider which asset the `amount` refers to.

### 3.4 Rounding Rules

**In RFQ:**
- Uses pair-specific decimals (`base_decimals`, `quote_decimals`)
- Rounds UP when client pays (protects market maker)
- Rounds DOWN when client receives (protects market maker)

**In LP-RFQ:**
- No rounding logic currently implemented
- Could lead to precision issues and profit leakage

### 3.5 Balance Validation

**In RFQ (main.py:979-1064):**
- Checks BOTH assets before quoting
- Considers `profit_asset` setting to determine capital requirements
- Validates market maker can hedge on exchange BEFORE client trade arrives

**In LP-RFQ:**
- No balance validation (assumes LP provides liquidity)

---

## 4. Variable Relationship Matrix

This matrix shows how each variable affects others:

| If You Change... | It Affects... | Because... |
|------------------|---------------|------------|
| **pair** | `base_asset`, `quote_asset`, `profit_asset`, decimals | Pair config defines these |
| **target_asset** | Spread direction, amount calculations, flow logic | Changes which asset is the "subject" |
| **side** + **target_asset** | Effective price calculation | Combined they determine spread application |
| **profit_asset** | Hedge quantity, exchange order type | Determines `quantity` vs `quote_qty` |
| **amount** + **target_asset** | `client_gives_amount`, `client_receives_amount` | Amount could be in base OR quote |
| **base_decimals** / **quote_decimals** | Rounding of all amounts | Each asset has different precision |

---

## 5. Migration Roadmap

### Phase 1: Data Model Enhancements

**Goal:** Add missing fields to support full business logic

#### Task 1.1: Enhance TradingPairConfig
- [ ] Create `src/config/pairs.py` (similar to rfq)
- [ ] Add `profit_asset` field to pair configuration
- [ ] Add `base_decimals` and `quote_decimals` fields
- [ ] Define supported pairs with their configs

**Files to Create/Modify:**
- NEW: `src/config/pairs.py`
- MODIFY: `src/config/settings.py` (import pair configs)

#### Task 1.2: Add target_asset to QuoteRequest
- [ ] Add `target_asset` field to `QuoteRequest` model
- [ ] Update terminal parser to accept target asset from input
- [ ] Default to `base_asset` if not specified (backwards compatibility)

**Files to Modify:**
- `src/core/models.py` - Line 14 (QuoteRequest)
- `src/ui/terminal.py` - Input parsing logic

#### Task 1.3: Enhance AggregatedQuote Model
- [ ] Add `target_asset` field
- [ ] Add `profit_asset` field (from pair config)
- [ ] Add decimal precision fields

**Files to Modify:**
- `src/core/models.py` - Line 48 (AggregatedQuote)

---

### Phase 2: Pricing Logic Enhancement

**Goal:** Implement full pricing logic with target_asset and spread inversion

#### Task 2.1: Refactor _create_aggregated_quote
- [ ] Import pricing logic from rfq's `PricingEngine.calculate_quote`
- [ ] Implement spread direction logic based on `target_asset`
- [ ] Fix amount calculations to handle quote-asset amounts
- [ ] Add rounding rules (round up for client pays, down for client receives)

**Files to Modify:**
- `src/core/lp_aggregator.py` - Lines 146-197

**Reference Implementation:**
- `../rfq/src/pricing/engine.py` - Lines 58-166

#### Task 2.2: Create Standalone Pricing Module (Optional)
- [ ] Extract pricing logic to `src/core/pricing_engine.py`
- [ ] Share code between aggregator and any future direct execution

**Files to Create:**
- NEW: `src/core/pricing_engine.py`

---

### Phase 3: Balance & Risk Validation

**Goal:** Add pre-trade balance checks

#### Task 3.1: Implement Balance Checker
- [ ] Create `src/core/balance_validator.py`
- [ ] Port `_check_balance_for_trade` logic from rfq
- [ ] Account for `profit_asset` setting in capital calculations
- [ ] Integrate with LP aggregator workflow

**Files to Create:**
- NEW: `src/core/balance_validator.py`

**Reference Implementation:**
- `../rfq/src/main.py` - Lines 979-1064

---

### Phase 4: Execution & Hedging (Future)

**Goal:** When LP-RFQ adds execution capability, support profit_asset hedging

#### Task 4.1: Hedge Parameter Logic
- [ ] Port `_determine_hedge_params` from rfq
- [ ] Calculate correct `quantity` vs `quote_qty` based on `profit_asset`

**Files to Create:**
- NEW: `src/execution/hedge_calculator.py`

**Reference Implementation:**
- `../rfq/src/main.py` - Lines 545-619

#### Task 4.2: P&L Calculation
- [ ] Port `_calculate_pnl` from rfq
- [ ] Calculate profit in the configured `profit_asset`
- [ ] Return P&L in bps for monitoring

**Files to Create:**
- NEW: `src/execution/pnl_calculator.py`

**Reference Implementation:**
- `../rfq/src/main.py` - Lines 621-714

---

### Phase 5: Testing & Validation

**Goal:** Ensure ported logic matches rfq behavior

#### Task 5.1: Unit Tests
- [ ] Test target_asset logic (base vs quote)
- [ ] Test profit_asset scenarios
- [ ] Test rounding rules
- [ ] Test balance validation

**Files to Create:**
- NEW: `tests/test_pricing_logic.py`
- NEW: `tests/test_balance_validation.py`
- NEW: `tests/test_target_asset.py`

#### Task 5.2: Integration Tests
- [ ] Compare lp-rfq quotes against rfq quotes for same inputs
- [ ] Verify amount calculations match
- [ ] Validate spread direction logic

**Files to Create:**
- NEW: `tests/test_rfq_parity.py`

---

## 6. Implementation Priority

### Must-Have (Critical for Correctness)
1. **target_asset logic** - Without this, spread direction can be wrong
2. **Amount calculations** - Current logic breaks if amount is in quote asset
3. **Rounding rules** - Prevents profit leakage

### Should-Have (Important for Production)
4. **profit_asset configuration** - Needed for proper treasury management
5. **Balance validation** - Risk management requirement
6. **Decimal precision per pair** - Professional quality

### Nice-to-Have (For Future Execution)
7. **Hedge parameter logic** - Only needed when adding execution
8. **P&L calculation** - Only needed when executing trades

---

## 7. Quick Reference: Variable Flow Example

**Example Scenario:** Client wants to BUY 50,000 USDT on BTCUSDT pair

### With target_asset Support (RFQ):
```
Input:
  pair = BTCUSDT
  base_asset = BTC
  quote_asset = USDT
  side = BUY
  amount = 50000
  target_asset = USDT  ← Client is trading USDT, not BTC!

Logic:
  Since target_asset == quote_asset AND side == BUY:
    → Client buys USDT, pays BTC
    → Spread direction: INVERTED (discount on base price)
    → effective_price = market_price * (1 - spread/10000)

  client_gives_asset = BTC
  client_receives_asset = USDT
  client_receives_amount = 50000
  client_gives_amount = 50000 / effective_price  ← Division, not multiplication!
```

### Without target_asset Support (Current LP-RFQ):
```
Input:
  pair = BTCUSDT
  base_asset = BTC
  quote_asset = USDT
  side = BUY
  amount = 50000
  target_asset = ??? ← NOT CAPTURED

Logic (BROKEN):
  Assumes: amount is always in base_asset
    → Treats 50000 as 50000 BTC (absurd!)
    → client_gives_amount = 50000 * price ← Wrong calculation
    → Spread direction: may be wrong
```

---

## 8. Code Examples

### 8.1 Enhanced QuoteRequest Model

```python
# src/core/models.py
@dataclass
class QuoteRequest:
    """Request sent to LPs for pricing"""
    side: str  # 'BUY' or 'SELL'
    amount: float
    base_asset: str
    quote_asset: str
    target_asset: str  # NEW: which asset is the amount in?
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        """Validate target_asset is either base or quote"""
        if self.target_asset not in [self.base_asset, self.quote_asset]:
            raise ValueError(f"target_asset must be {self.base_asset} or {self.quote_asset}")
```

### 8.2 Enhanced TradingPairConfig

```python
# src/config/pairs.py (NEW FILE)
from dataclasses import dataclass
from typing import Literal

@dataclass
class TradingPairConfig:
    symbol: str
    base_asset: str
    quote_asset: str
    default_markup_bps: float
    base_decimals: int
    quote_decimals: int
    profit_asset: Literal['base', 'quote']  # NEW: where to keep profit
    min_amount: float

SUPPORTED_PAIRS = {
    'BTCUSDT': TradingPairConfig(
        symbol='BTCUSDT',
        base_asset='BTC',
        quote_asset='USDT',
        default_markup_bps=5.0,
        base_decimals=5,
        quote_decimals=2,
        profit_asset='quote',  # Keep profit in USDT
        min_amount=0.001
    ),
    # ... more pairs
}
```

### 8.3 Fixed Amount Calculation Logic

```python
# src/core/lp_aggregator.py - _create_aggregated_quote
def _create_aggregated_quote(self, lp_quote: LPQuote, request: QuoteRequest) -> AggregatedQuote:
    # Apply markup
    if request.side == 'BUY':
        client_price = lp_quote.price * (1 + self.markup_bps / 10000)
    else:
        client_price = lp_quote.price * (1 - self.markup_bps / 10000)

    # Calculate flows based on target_asset (FIXED LOGIC)
    if request.target_asset == request.base_asset:
        # Client trading base asset
        if request.side == 'BUY':
            client_receives_amount = request.amount
            client_gives_amount = request.amount * client_price
            client_receives_asset = request.base_asset
            client_gives_asset = request.quote_asset
        else:  # SELL
            client_gives_amount = request.amount
            client_receives_amount = request.amount * client_price
            client_gives_asset = request.base_asset
            client_receives_asset = request.quote_asset
    else:
        # Client trading quote asset (INVERTED LOGIC)
        if request.side == 'BUY':
            client_receives_amount = request.amount
            client_gives_amount = request.amount / client_price  # DIVISION!
            client_receives_asset = request.quote_asset
            client_gives_asset = request.base_asset
        else:  # SELL
            client_gives_amount = request.amount
            client_receives_amount = request.amount / client_price  # DIVISION!
            client_gives_asset = request.quote_asset
            client_receives_asset = request.base_asset

    # Apply rounding (NEW)
    client_gives_amount = self._round_amount(
        client_gives_amount,
        client_gives_asset,
        round_up=True  # Protect market maker
    )
    client_receives_amount = self._round_amount(
        client_receives_amount,
        client_receives_asset,
        round_up=False  # Protect market maker
    )

    return AggregatedQuote(...)
```

---

## 9. Testing Strategy

### 9.1 Test Cases to Cover

| Test Case | Inputs | Expected Behavior |
|-----------|--------|-------------------|
| BUY base (BTC) | side=BUY, amount=1.5, target=BTC | Standard buy logic |
| SELL base (BTC) | side=SELL, amount=1.5, target=BTC | Standard sell logic |
| BUY quote (USDT) | side=BUY, amount=50000, target=USDT | Inverted spread, division |
| SELL quote (USDT) | side=SELL, amount=50000, target=USDT | Inverted spread, division |
| Rounding (pays) | client_gives_amount=10000.12345 | Round UP (10000.13) |
| Rounding (receives) | client_receives_amount=10000.98765 | Round DOWN (10000.98) |

### 9.2 Validation Against RFQ

Create a comparison test that runs the same inputs through both systems:

```python
# tests/test_rfq_parity.py
def test_quote_parity():
    """Ensure lp-rfq produces same results as rfq for same inputs"""

    # Setup both engines
    rfq_engine = RFQPricingEngine(spread_bps=10)
    lp_aggregator = LPAggregator(markup_bps=10, ...)

    # Test case
    inputs = {
        'side': 'BUY',
        'amount': 50000,
        'target_asset': 'USDT',
        'market_price': 100000,
        'base_asset': 'BTC',
        'quote_asset': 'USDT'
    }

    # Get results
    rfq_quote = rfq_engine.calculate_quote(**inputs)
    lp_quote = ... # create mock LP quote
    lp_aggregated = lp_aggregator._create_aggregated_quote(lp_quote, ...)

    # Compare
    assert rfq_quote.client_gives_amount == lp_aggregated.client_gives_amount
    assert rfq_quote.client_receives_amount == lp_aggregated.client_receives_amount
    assert rfq_quote.effective_price == lp_aggregated.client_price
```

---

## 10. Migration Checklist

### Phase 1: Foundation
- [ ] Create `src/config/pairs.py` with `TradingPairConfig` including `profit_asset`
- [ ] Add `target_asset` field to `QuoteRequest` model
- [ ] Add `target_asset` parsing to terminal input handler
- [ ] Update `AggregatedQuote` to include `target_asset` and decimals

### Phase 2: Core Logic
- [ ] Refactor `_create_aggregated_quote` to handle `target_asset` correctly
- [ ] Implement spread direction inversion for quote-asset trades
- [ ] Fix amount calculations (use division when appropriate)
- [ ] Add rounding logic (round up for pays, down for receives)

### Phase 3: Validation
- [ ] Create balance validator module
- [ ] Port balance check logic from rfq
- [ ] Integrate balance checks into quote flow

### Phase 4: Testing
- [ ] Write unit tests for target_asset logic
- [ ] Write unit tests for rounding
- [ ] Create parity tests comparing rfq and lp-rfq outputs
- [ ] Manual testing with all pairs and scenarios

### Phase 5: Future (Execution)
- [ ] Port hedge parameter calculation
- [ ] Port P&L calculation
- [ ] Integrate with execution workflow

---

## 11. Glossary

| Term | Definition |
|------|------------|
| **Base Asset** | The asset being quoted (e.g., BTC in BTCUSDT) |
| **Quote Asset** | The asset used to price the base (e.g., USDT in BTCUSDT) |
| **Target Asset** | The specific asset the client wants to buy/sell (can be base OR quote) |
| **Profit Asset** | The asset in which the market maker keeps spread profit |
| **Spread** | Market maker's margin (rfq terminology) |
| **Markup** | Market maker's margin on top of LP quote (lp-rfq terminology) |
| **VWAP** | Volume-weighted average price from order book |
| **Hedge** | Offsetting trade to manage risk |

---

## 12. References

### RFQ System Files
- [rfq/src/main.py:545-714](../rfq/src/main.py) - Hedge params and P&L calculation
- [rfq/src/config/pairs.py](../rfq/src/config/pairs.py) - Pair config with profit_asset
- [rfq/src/pricing/engine.py:58-166](../rfq/src/pricing/engine.py) - Full pricing logic with target_asset
- [rfq/src/utils/input_handler.py](../rfq/src/utils/input_handler.py) - Terminal input parsing

### LP-RFQ System Files
- [lp-rfq/src/core/models.py](src/core/models.py) - Data models
- [lp-rfq/src/core/lp_aggregator.py:146-197](src/core/lp_aggregator.py) - Quote aggregation logic
- [lp-rfq/src/ui/terminal.py](src/ui/terminal.py) - Input parsing

---

## Document History

| Date | Author | Change |
|------|--------|--------|
| 2025-10-21 | Initial | Created comprehensive migration roadmap |
