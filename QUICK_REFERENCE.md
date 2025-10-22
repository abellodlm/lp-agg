# Quick Reference - LP-RFQ System

## Running the Application

```bash
python -m src.main
```

## Workflow

1. **Enter quote request** (format below)
2. **System displays locked quote** with best LP price
3. **Choose action**:
   - `p` - Proceed with execution
   - `c` - Cancel and request new quote
   - `q` - Quit application
4. **If improved quote found**, system displays new quote automatically
5. **After execution**, returns to main menu

---

## Command Formats

### New Format (Recommended)
```
<side> <amount> <target_asset> <pair>
```

**Examples:**
```bash
b 1.5 btc btcusdt          # Buy 1.5 BTC
s 2.0 btc btcusdt          # Sell 2.0 BTC
b 50000 usdt btcusdt       # Buy 50,000 USDT (pays in BTC)
s 75000 usdt btcusdt       # Sell 75,000 USDT (receives BTC)
```

### Legacy Format (Still Works)
```
<side> <amount> <pair>
```

**Examples:**
```bash
b 1.5 btcusdt              # Defaults to base asset (BTC)
s 0.01 ethusdt             # Defaults to base asset (ETH)
```

---

## Understanding target_asset

### What is target_asset?
The asset that the `amount` refers to.

### Examples:

#### Scenario 1: Client wants to buy 1.5 BTC
```bash
> b 1.5 btc btcusdt
```
- **target_asset:** BTC (base)
- **Client receives:** 1.5 BTC
- **Client pays:** ~150,000 USDT (depends on price + markup)
- **Spread:** Premium on BTC price (standard)

#### Scenario 2: Client wants to buy 50,000 USDT
```bash
> b 50000 usdt btcusdt
```
- **target_asset:** USDT (quote)
- **Client receives:** 50,000 USDT
- **Client pays:** ~0.5 BTC (depends on price + markup)
- **Spread:** INVERTED (discount on BTC price)

---

## Spread Direction Logic

| Client Action | target_asset | Spread Direction | Why |
|--------------|--------------|------------------|-----|
| BUY | base | Premium | Buying base → pay more |
| SELL | base | Discount | Selling base → receive less |
| BUY | quote | **Discount** | Buying quote = selling base → inverted |
| SELL | quote | **Premium** | Selling quote = buying base → inverted |

---

## Pricing Formulas

### When target_asset = base (e.g., BTC on BTCUSDT)

**BUY (client buys base):**
```python
client_price = lp_price × (1 + markup_bps / 10000)
client_receives_amount = amount  # Exact amount requested
client_gives_amount = amount × client_price
```

**SELL (client sells base):**
```python
client_price = lp_price × (1 - markup_bps / 10000)
client_gives_amount = amount  # Exact amount given
client_receives_amount = amount × client_price
```

### When target_asset = quote (e.g., USDT on BTCUSDT)

**BUY (client buys quote, sells base):**
```python
client_price = lp_price × (1 - markup_bps / 10000)  # INVERTED!
client_receives_amount = amount  # Exact amount requested
client_gives_amount = amount / client_price  # DIVISION!
```

**SELL (client sells quote, buys base):**
```python
client_price = lp_price × (1 + markup_bps / 10000)  # INVERTED!
client_gives_amount = amount  # Exact amount given
client_receives_amount = amount / client_price  # DIVISION!
```

---

## Rounding Rules

- **Client pays:** Round UP (protects market maker)
- **Client receives:** Round DOWN (protects market maker)

**Decimal precision per pair:**
- BTCUSDT: 5 decimals (BTC), 2 decimals (USDT)
- ETHUSDT: 4 decimals (ETH), 2 decimals (USDT)
- USDCUSDT: 2 decimals (USDC), 4 decimals (USDT)

---

## Configuration

### Adding a New Pair

Edit [src/config/pairs.py](src/config/pairs.py):

```python
'SOLUSDT': TradingPairConfig(
    symbol='SOLUSDT',
    base_asset='SOL',
    quote_asset='USDT',
    default_markup_bps=5.0,
    base_decimals=4,
    quote_decimals=2,
    min_amount=0.1,
    profit_asset='quote'  # Keep profit in USDT
),
```

### profit_asset Setting

Determines which asset accumulates spread profit:

- **`profit_asset='quote'`** (most common)
  - Accumulate profit in USDT
  - Easier to track P&L in fiat terms

- **`profit_asset='base'`**
  - Accumulate profit in BTC/ETH/etc
  - Builds inventory in the base asset

---

## Viewing Database

```bash
# View summary stats
python view_db.py stats

# View recent executions
python view_db.py executions 10

# View all data
python view_db.py all

# View LP performance
python view_db.py performance

# View LP quotes for specific quote ID
python view_db.py lp-quotes Q20251022-120530-123
```

---

## Testing

Run unit tests:
```bash
cd C:\Users\andre\OneDrive\Escritorio\Quoter\lp-rfq
python tests/test_pricing_logic.py
python tests/test_hedge_pnl.py
```

Expected: All tests pass

---

## Troubleshooting

### Error: "target_asset must be either BTC or USDT"
**Cause:** You specified a target_asset that's not part of the pair.

**Fix:** Use either the base or quote asset of the pair.
```bash
# Wrong:
b 1.5 eth btcusdt  ❌

# Right:
b 1.5 btc btcusdt  ✅
b 1.5 usdt btcusdt ✅
```

### Error: "Unsupported trading pair"
**Cause:** Pair not defined in config.

**Fix:** Add the pair to `SUPPORTED_PAIRS` in [src/config/pairs.py](src/config/pairs.py).

### Unexpected spread direction
**Check:** Are you trading the quote asset?

If `target_asset = quote_asset`, spread direction is **inverted**.

---

## Real-World Examples

### Example 1: Market Maker Quoted BTC at 100,000 USDT

**Client Request:** Buy 50,000 USDT
```bash
> b 50000 usdt btcusdt
```

**System Processing:**
1. Identifies: target_asset = USDT (quote)
2. Applies INVERTED spread: 100,000 × (1 - 5/10000) = 99,950
3. Calculates: 50,000 / 99,950 = 0.50025 BTC
4. Rounds UP (client pays): 0.50026 BTC

**Result:**
- Client gives: 0.50026 BTC
- Client receives: 50,000 USDT
- Effective BTC price: 99,950 (client got a discount)

### Example 2: Same Market Price

**Client Request:** Buy 0.5 BTC
```bash
> b 0.5 btc btcusdt
```

**System Processing:**
1. Identifies: target_asset = BTC (base)
2. Applies STANDARD spread: 100,000 × (1 + 5/10000) = 100,050
3. Calculates: 0.5 × 100,050 = 50,025
4. Rounds UP (client pays): 50,025.00 USDT

**Result:**
- Client gives: 50,025.00 USDT
- Client receives: 0.5 BTC
- Effective BTC price: 100,050 (client paid a premium)

### Comparison

Both clients received ~50,000 USDT worth of value, but:
- Example 1: Client paid 0.50026 BTC for 50,000 USDT
- Example 2: Client paid 50,025 USDT for 0.5 BTC

The spreads are **inverted** because one is trading the quote asset!

---

## Summary

✅ **target_asset** determines which asset the amount refers to
✅ **Spread direction** inverts when trading quote asset
✅ **Amount calculations** use division for quote asset trades
✅ **Rounding** protects market maker (up for pays, down for receives)
✅ **Backwards compatible** with legacy 3-part format

---

## Further Reading

- **Migration Details:** [MIGRATION_COMPLETE.md](MIGRATION_COMPLETE.md)
- **Full Roadmap:** [BUSINESS_LOGIC_MIGRATION.md](BUSINESS_LOGIC_MIGRATION.md)
- **Test Suite:** [tests/test_pricing_logic.py](tests/test_pricing_logic.py)
