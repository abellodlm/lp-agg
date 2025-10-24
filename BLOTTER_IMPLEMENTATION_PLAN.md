# Trading Blotter Implementation Plan

## Overview

Add a trading blotter as a second column in the LP Aggregation Monitor window to display real-time execution history alongside the existing LP leaderboard.

## Current UI Structure

### Existing Components
1. **Tkinter Monitor Window** (`src/ui/monitor.py`)
   - Best aggregated quote (top section)
   - LP leaderboard (Mario Kart style rankings)
   - Auto-refresh toggle
   - Window size: 700x800px

2. **Terminal Interface** (`src/ui/terminal.py`)
   - Command line for operator input

## Trading Blotter Requirements

### Essential Elements

#### 1. Execution Details
- **Execution ID**: Unique identifier (e.g., `E20250122-143025-123`)
- **Timestamp**: Formatted datetime (e.g., `14:30:25`)
- **Status**: SUCCESS/FAILED with color coding
  - Green for SUCCESS
  - Red for FAILED
- **Quote ID**: Reference to original quote

#### 2. Trade Information
- **Side**: BUY/SELL
- **Asset Pair**: e.g., BTC/USDT
- **Client Gives**: Amount and asset (what client pays)
- **Client Receives**: Amount and asset (what client gets)
- **LP Used**: Which LP executed the trade

#### 3. Hedge Execution Details
- **Exchange Side**: The hedge side (opposite of client side)
- **Executed Quantity**: Actual executed amount on exchange
- **Average Price**: Execution price
- **Commission**: Fee paid (amount + asset)

#### 4. P&L Information
- **Gross P&L**: P&L before fees
- **Net P&L**: P&L after fees (most important)
- **P&L (bps)**: P&L in basis points
- **P&L Asset**: Asset denomination
- **Color Coding**:
  - Green for positive P&L
  - Red for negative P&L
  - Yellow for zero/near-zero P&L

#### 5. UI Features
- **Scrollable view**: Handle 50-100+ executions
- **Most recent first**: New executions appear at top
- **Auto-updates**: Poll database every 1-2 seconds
- **Alternating row colors**: For readability
- **Fixed-width font**: Consolas for alignment
- **Dark theme**: Consistent with existing monitor (#1e1e1e)
- **Compact rows**: Show more data in less space

## Data Source

### Database Schema
The blotter reads from the **executions** table in the database (`src/database/schema.py:108-148`):

```sql
CREATE TABLE executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT UNIQUE NOT NULL,
    quote_id TEXT NOT NULL,
    status TEXT NOT NULL,              -- 'SUCCESS' or 'FAILED'
    lp_name TEXT NOT NULL,
    exchange_side TEXT NOT NULL,       -- 'BUY' or 'SELL'
    quantity REAL,
    quote_qty REAL,
    executed_qty REAL,
    executed_quote_qty REAL,
    avg_price REAL,
    commission REAL,
    commission_asset TEXT,
    pnl_amount REAL,
    pnl_asset TEXT,
    pnl_after_fees REAL,              -- Net P&L (most important)
    pnl_bps REAL,                     -- P&L in basis points
    error_message TEXT,
    executed_at REAL NOT NULL,        -- Unix timestamp
    FOREIGN KEY (quote_id) REFERENCES quotes(quote_id)
)
```

### Query Strategy
```sql
SELECT * FROM executions
ORDER BY executed_at DESC
LIMIT 50
```

## Architecture Changes

### 1. New File: `src/ui/blotter.py`

Create `ExecutionBlotter` class with:

```python
class ExecutionBlotter:
    """
    Real-time execution blotter component.

    Features:
    - Scrollable table of recent executions
    - Auto-refresh from database
    - Color-coded status and P&L
    - Thread-safe updates
    """

    def __init__(self, parent_frame, db_path: str):
        """Initialize blotter with parent Tkinter frame and database path"""

    def _create_header(self):
        """Create column headers"""
        # Columns: Time | Status | Side | Pair | Client Pays | Client Gets | LP | Net P&L | bps

    def _create_row(self, execution: Dict):
        """Create a single execution row"""

    def _fetch_recent_executions(self, limit: int = 50) -> List[Dict]:
        """Query database for recent executions"""

    def _update_loop(self):
        """Auto-update loop (called every 1-2 seconds)"""

    def refresh(self):
        """Manual refresh trigger"""
```

### 2. Modify `src/ui/monitor.py`

Update `LPAggregationMonitor` class:

```python
class LPAggregationMonitor:
    def __init__(self, db_path: Optional[str] = None):
        # ... existing fields ...
        self.db_path = db_path
        self.blotter = None  # ExecutionBlotter instance

    def _run_gui(self):
        # Window configuration
        self.window.geometry("1200x800")  # Increased from 700x800

        # Create main container with 2-column grid
        main_container = tk.Frame(self.window, bg=bg_color)
        main_container.pack(fill='both', expand=True, padx=15, pady=15)

        # Configure grid columns (60/40 split)
        main_container.columnconfigure(0, weight=6)  # Left: LP Monitor
        main_container.columnconfigure(1, weight=4)  # Right: Blotter
        main_container.rowconfigure(0, weight=1)

        # LEFT COLUMN: Existing LP Monitor
        left_frame = tk.Frame(main_container, bg=bg_color)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))

        # ... move all existing content to left_frame ...

        # RIGHT COLUMN: Execution Blotter
        right_frame = tk.Frame(main_container, bg=bg_color)
        right_frame.grid(row=0, column=1, sticky='nsew')

        # Initialize blotter
        if self.db_path:
            from .blotter import ExecutionBlotter
            self.blotter = ExecutionBlotter(right_frame, self.db_path)
```

### 3. Update `src/main.py`

Pass database path to monitor:

```python
# In main_loop()
monitor = get_monitor()

# If database logging is enabled, update monitor with db_path
if settings.enable_database_logging:
    # ... existing database init ...
    monitor.db_path = settings.database_path
    monitor._initialize_blotter()  # New method to lazy-init blotter
```

Alternatively, modify the singleton `get_monitor()` function to accept optional db_path.

## Implementation Steps

### Phase 1: Create Blotter Component

1. **Create `src/ui/blotter.py`**
   - [ ] Define `ExecutionBlotter` class
   - [ ] Create scrollable frame with Canvas + Scrollbar
   - [ ] Implement column headers (fixed at top)
   - [ ] Implement row creation with proper styling
   - [ ] Add color coding logic for status and P&L
   - [ ] Implement database query method
   - [ ] Add auto-update loop (1-2 second interval)

2. **Design Blotter Layout**
   ```
   ┌─────────────────────────────────────────────────┐
   │ EXECUTION BLOTTER                               │
   ├────────┬────────┬──────┬───────┬──────┬─────────┤
   │ Time   │ Status │ Side │ Pair  │ LP   │ P&L(bps)│
   ├────────┼────────┼──────┼───────┼──────┼─────────┤
   │ 14:30  │ ✓ SUCC │ BUY  │ BTC/  │ LP-1 │ +12.5   │
   │        │        │      │ USDT  │      │         │
   ├────────┼────────┼──────┼───────┼──────┼─────────┤
   │ 14:28  │ ✗ FAIL │ SELL │ ETH/  │ LP-2 │ --      │
   │        │        │      │ USDT  │      │         │
   ├────────┼────────┼──────┼───────┼──────┼─────────┤
   │ ...    │        │      │       │      │         │
   └────────┴────────┴──────┴───────┴──────┴─────────┘
   ```

### Phase 2: Modify Monitor Window

3. **Update `src/ui/monitor.py`**
   - [ ] Change window geometry to 1200x800
   - [ ] Create two-column grid layout
   - [ ] Move existing content to left frame
   - [ ] Add blotter to right frame
   - [ ] Pass database path to monitor initialization
   - [ ] Handle case when database is disabled

### Phase 3: Integration

4. **Update Monitor Initialization**
   - [ ] Modify `get_monitor()` to accept optional db_path
   - [ ] Update `main.py` to pass database path
   - [ ] Add method to lazy-initialize blotter when db_path is set
   - [ ] Ensure thread-safe access to database

5. **Testing**
   - [ ] Test with database logging enabled
   - [ ] Test with database logging disabled (blotter should hide or show "N/A")
   - [ ] Test blotter updates after executions
   - [ ] Test scrolling with 50+ executions
   - [ ] Test color coding for different statuses/P&L

## Key Design Decisions

### Layout
- **Window Size**: 1200x800px (from 700x800)
- **Split**: 60% monitor / 40% blotter
- **Left Column**: Existing LP aggregation + leaderboard
- **Right Column**: Execution blotter

### Data & Performance
- **Data Source**: Read-only queries from `executions` table
- **Update Frequency**: 1-2 seconds (lighter than quote streaming)
- **Display Limit**: Last 50-100 trades (configurable)
- **Query Optimization**: Use indexed `executed_at` column

### Styling
- **Theme**: Dark mode consistent with monitor (#1e1e1e background)
- **Font**: Consolas (same as monitor)
- **Colors**:
  - Success: #51cf66 (green)
  - Failed: #ff6b6b (red)
  - Positive P&L: #00d4aa (cyan-green)
  - Negative P&L: #ff6b6b (red)
  - Neutral: #888888 (gray)

### Edge Cases
- **No executions**: Show "No executions yet" message
- **Database disabled**: Show "Database logging disabled" message
- **Database error**: Log error, show last known data
- **Large P&L values**: Format with K/M suffixes

## Example Row Data Rendering

```
Time    Status  Side  Pair     Client→LP         LP    Net P&L      bps
────────────────────────────────────────────────────────────────────────
14:30   ✓ SUCC  BUY   BTC/USDT 75000→1.5 BTC    LP-1  +0.0012 BTC  +12.5
14:28   ✗ FAIL  SELL  ETH/USDT 2.5 ETH→failed   LP-2  --           --
14:25   ✓ SUCC  BUY   BTC/USDT 50000→1.0 BTC    LP-3  +0.0008 BTC  +8.2
```

## Future Enhancements (Optional)

1. **Filters**
   - Filter by status (SUCCESS only, FAILED only, ALL)
   - Filter by LP
   - Filter by asset pair
   - Date/time range filter

2. **Metrics Panel**
   - Total executions today
   - Success rate
   - Total P&L (aggregated)
   - Best/worst execution

3. **Export**
   - Export to CSV
   - Copy selected row to clipboard

4. **Click Actions**
   - Click row to see full execution details
   - Right-click menu for actions

## Dependencies

### Existing
- tkinter (already used in monitor.py)
- sqlite3 (already used for database)
- threading (already used for thread-safety)

### New
- None (uses existing dependencies)

## Testing Checklist

- [ ] Blotter appears correctly in right column
- [ ] Executions display with correct formatting
- [ ] Color coding works for status and P&L
- [ ] Auto-refresh updates blotter every 1-2 seconds
- [ ] Scrolling works with 50+ executions
- [ ] Window resizing maintains layout
- [ ] Works when database logging is disabled
- [ ] Thread-safe updates (no race conditions)
- [ ] Performance is acceptable with 100+ executions

## Rollback Plan

If issues arise:
1. Blotter component is isolated in separate file (`blotter.py`)
2. Monitor can run without blotter (conditional initialization)
3. Simply remove blotter initialization to revert to original layout
4. No database schema changes required
