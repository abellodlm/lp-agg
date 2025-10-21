# Database Schema Documentation

## Overview

The LP Aggregation RFQ System uses SQLite for logging all quotes, LP responses, and performance metrics. This provides a complete audit trail and enables analytics.

## Configuration

Database logging is controlled via environment variables:

```ini
# .env
DATABASE_PATH=quotes.db
ENABLE_DATABASE_LOGGING=true
```

- **DATABASE_PATH**: Path to SQLite database file (default: `quotes.db`)
- **ENABLE_DATABASE_LOGGING**: Enable/disable logging (default: `true`)

## Database Schema

### Table: `quotes`

Stores all aggregated quotes shown to the client.

```sql
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id TEXT UNIQUE NOT NULL,
    side TEXT NOT NULL,
    base_asset TEXT NOT NULL,
    quote_asset TEXT NOT NULL,
    amount REAL NOT NULL,
    client_price REAL NOT NULL,
    lp_price REAL NOT NULL,
    lp_name TEXT NOT NULL,
    markup_bps REAL NOT NULL,
    validity_seconds REAL NOT NULL,
    is_improvement INTEGER NOT NULL,
    locked_lp_name TEXT,
    poll_number INTEGER NOT NULL,
    created_at REAL NOT NULL
);
```

**Columns:**
- `quote_id`: Unique identifier for the quote
- `side`: BUY or SELL
- `base_asset`, `quote_asset`: Trading pair (e.g., BTC/USDT)
- `amount`: Quantity being traded
- `client_price`: Price shown to client (after markup)
- `lp_price`: Original LP price (before markup)
- `lp_name`: Which LP provided this quote
- `markup_bps`: Markup applied in basis points
- `validity_seconds`: How long quote is valid
- `is_improvement`: 1 if this was an improvement, 0 if not
- `locked_lp_name`: Name of currently locked LP
- `poll_number`: Sequential poll number in the stream
- `created_at`: Unix timestamp

**Indexes:**
- `idx_quotes_created_at` on `created_at`
- `idx_quotes_lp_name` on `lp_name`
- `idx_quotes_quote_id` on `quote_id`

---

### Table: `lp_quotes`

Stores all individual LP responses (every quote from every LP).

```sql
CREATE TABLE lp_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id TEXT NOT NULL,
    lp_name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    validity_seconds REAL NOT NULL,
    response_time_ms REAL,
    timestamp REAL NOT NULL,
    side TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (quote_id) REFERENCES quotes(quote_id)
);
```

**Columns:**
- `quote_id`: Links to parent aggregated quote
- `lp_name`: Name of the LP
- `price`: Price quoted by this LP
- `quantity`: Maximum quantity available
- `validity_seconds`: LP quote validity
- `response_time_ms`: Response time in milliseconds
- `timestamp`: Unix timestamp
- `side`: BUY or SELL
- `metadata`: JSON string with additional data

**Indexes:**
- `idx_lp_quotes_quote_id` on `quote_id`
- `idx_lp_quotes_lp_name` on `lp_name`

---

### Table: `lp_performance`

Aggregated LP performance metrics.

```sql
CREATE TABLE lp_performance (
    lp_name TEXT PRIMARY KEY,
    total_quotes INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    avg_response_time_ms REAL,
    best_price REAL,
    worst_price REAL,
    last_updated REAL NOT NULL
);
```

**Columns:**
- `lp_name`: Name of the LP
- `total_quotes`: Total number of quotes provided
- `total_wins`: Number of times LP had best quote
- `win_rate`: Percentage win rate (0-100)
- `avg_response_time_ms`: Average response time
- `best_price`: Best (lowest for BUY) price ever quoted
- `worst_price`: Worst (highest for BUY) price ever quoted
- `last_updated`: Last update timestamp

---

## Example Queries

### Get Recent Quotes

```sql
SELECT
    poll_number,
    lp_name,
    client_price,
    is_improvement,
    created_at
FROM quotes
ORDER BY created_at DESC
LIMIT 100;
```

### Get LP Performance Leaderboard

```sql
SELECT
    lp_name,
    total_quotes,
    total_wins,
    win_rate,
    avg_response_time_ms
FROM lp_performance
ORDER BY win_rate DESC;
```

### Get All Quotes for a Specific LP

```sql
SELECT
    poll_number,
    client_price,
    lp_price,
    is_improvement,
    created_at
FROM quotes
WHERE lp_name = 'LP-Alpha'
ORDER BY created_at DESC;
```

### Get Quote History for Time Range

```sql
SELECT
    poll_number,
    lp_name,
    client_price,
    is_improvement
FROM quotes
WHERE created_at BETWEEN 1234567890 AND 1234567999
ORDER BY created_at ASC;
```

### Get LP Response Details for a Quote

```sql
SELECT
    lq.lp_name,
    lq.price,
    lq.response_time_ms,
    q.lp_name AS winner
FROM lp_quotes lq
JOIN quotes q ON lq.quote_id = q.quote_id
WHERE lq.quote_id = 'Q20250121-143025-123'
ORDER BY lq.price ASC;
```

### Calculate Improvement Rate

```sql
SELECT
    COUNT(*) AS total_polls,
    SUM(is_improvement) AS improvements,
    (SUM(is_improvement) * 100.0 / COUNT(*)) AS improvement_rate
FROM quotes;
```

### Average Price by LP

```sql
SELECT
    lp_name,
    AVG(lp_price) AS avg_price,
    MIN(lp_price) AS best_price,
    MAX(lp_price) AS worst_price,
    COUNT(*) AS quote_count
FROM quotes
GROUP BY lp_name
ORDER BY avg_price ASC;
```

---

## Using the QuoteLogger API

### Initialization

```python
from src.database.schema import init_database
from src.database.quote_logger import QuoteLogger

# Initialize database
init_database("quotes.db")

# Create logger
logger = QuoteLogger("quotes.db")
```

### Querying Data

```python
# Get recent quotes
recent_quotes = logger.get_recent_quotes(limit=100)

# Get LP statistics
lp_stats = logger.get_lp_stats("LP-Alpha")
print(f"Win rate: {lp_stats['win_rate']:.1f}%")

# Get all LP stats
all_stats = logger.get_all_lp_stats()
for stats in all_stats:
    print(f"{stats['lp_name']}: {stats['win_rate']:.1f}% win rate")

# Get quote history with filters
history = logger.get_quote_history(
    lp_name="LP-Alpha",
    start_time=time.time() - 3600,  # Last hour
    limit=1000
)
```

### Cleanup

```python
# Close connection when done
logger.close()
```

---

## Database Maintenance

### Backup

```bash
# Create backup
cp quotes.db quotes_backup_$(date +%Y%m%d).db
```

### Vacuum (Optimize)

```bash
sqlite3 quotes.db "VACUUM;"
```

### Check Database Size

```bash
ls -lh quotes.db
```

### Delete Old Data (Future Enhancement)

```sql
-- Delete quotes older than 30 days
DELETE FROM quotes
WHERE created_at < unixepoch('now', '-30 days');

-- Delete orphaned LP quotes
DELETE FROM lp_quotes
WHERE quote_id NOT IN (SELECT quote_id FROM quotes);

-- Vacuum to reclaim space
VACUUM;
```

---

## Performance Considerations

1. **Indexes**: Already created on frequently queried columns
2. **Batch Inserts**: Logger uses transactions for better performance
3. **Connection Pooling**: Single connection per logger instance
4. **File Size**: Typical rate ~1MB per 1000 quotes (with all LP responses)

---

## Troubleshooting

### Database Locked Error

If you see "database is locked" errors:
1. Ensure only one process is writing at a time
2. Check for long-running queries
3. Close all connections when done

### Missing Data

If quotes aren't being logged:
1. Check `ENABLE_DATABASE_LOGGING=true` in .env
2. Verify database file permissions
3. Check logs for errors

### Corrupt Database

If database becomes corrupt:
1. Stop all processes
2. Restore from backup
3. Run `sqlite3 quotes.db ".recover" > recovered.sql`

---

## Future Enhancements

Potential improvements:
- [ ] Auto-cleanup of old data (configurable retention)
- [ ] Database migrations system
- [ ] PostgreSQL support for production
- [ ] Real-time analytics dashboard
- [ ] Export to CSV/JSON
- [ ] Data visualization tools
