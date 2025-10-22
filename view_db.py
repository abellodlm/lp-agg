"""
Database Viewer - View LP quote logs and performance metrics.

Quick utility to inspect the quotes.db database.
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def view_quotes(db_path: str, limit: int = 20):
    """View recent aggregated quotes"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            quote_id,
            side,
            base_asset || quote_asset as pair,
            target_asset,
            amount,
            client_price,
            lp_price,
            lp_name,
            markup_bps,
            is_improvement,
            locked_lp_name,
            poll_number,
            datetime(created_at, 'unixepoch', 'localtime') as created
        FROM quotes
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\n[!] No quotes found in database\n")
        return

    # Convert to list of dicts for tabulate
    data = []
    for row in rows:
        data.append([
            row['quote_id'][:15] + '...',
            row['side'],
            row['pair'],
            row['target_asset'],
            f"{row['amount']:.4f}",
            f"{row['client_price']:.2f}",
            f"{row['lp_price']:.2f}",
            row['lp_name'],
            f"{row['markup_bps']:.1f}",
            'Y' if row['is_improvement'] else '',
            row['locked_lp_name'] or '-',
            row['poll_number'],
            row['created']
        ])

    print(f"\n{'='*120}")
    print(f"RECENT QUOTES (Last {limit})")
    print(f"{'='*120}\n")

    # Print header
    print(f"{'Quote ID':<18} {'Side':<5} {'Pair':<10} {'Tgt':<5} {'Amount':<10} {'Client $':<10} {'LP $':<10} {'LP':<10} {'Mkp':<6} {'Imp':<4} {'Locked':<10} {'Poll':<5} {'Created':<20}")
    print("-" * 120)

    # Print rows
    for row in data:
        print(f"{row[0]:<18} {row[1]:<5} {row[2]:<10} {row[3]:<5} {row[4]:<10} {row[5]:<10} {row[6]:<10} {row[7]:<10} {row[8]:<6} {row[9]:<4} {row[10]:<10} {row[11]:<5} {row[12]:<20}")
    print()


def view_lp_quotes(db_path: str, quote_id: str = None, limit: int = 50):
    """View LP quotes (individual LP responses)"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if quote_id:
        cursor.execute("""
            SELECT
                quote_id,
                lp_name,
                price,
                quantity,
                validity_seconds,
                response_time_ms,
                datetime(timestamp, 'unixepoch', 'localtime') as timestamp,
                side
            FROM lp_quotes
            WHERE quote_id = ?
            ORDER BY price ASC
        """, (quote_id,))
    else:
        cursor.execute("""
            SELECT
                quote_id,
                lp_name,
                price,
                quantity,
                validity_seconds,
                response_time_ms,
                datetime(timestamp, 'unixepoch', 'localtime') as timestamp,
                side
            FROM lp_quotes
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\n[!] No LP quotes found\n")
        return

    data = []
    for row in rows:
        data.append([
            row['quote_id'][:15] + '...' if not quote_id else row['quote_id'],
            row['lp_name'],
            f"{row['price']:.2f}",
            f"{row['quantity']:.4f}",
            f"{row['validity_seconds']:.1f}s",
            f"{row['response_time_ms']:.1f}ms" if row['response_time_ms'] else '-',
            row['side'],
            row['timestamp']
        ])

    print(f"\n{'='*120}")
    print(f"LP QUOTES" + (f" for {quote_id}" if quote_id else f" (Last {limit})"))
    print(f"{'='*120}\n")

    # Print header
    print(f"{'Quote ID':<35} {'LP':<10} {'Price':<12} {'Quantity':<12} {'Validity':<10} {'Response':<10} {'Side':<6} {'Timestamp':<20}")
    print("-" * 120)

    # Print rows
    for row in data:
        print(f"{row[0]:<35} {row[1]:<10} {row[2]:<12} {row[3]:<12} {row[4]:<10} {row[5]:<10} {row[6]:<6} {row[7]:<20}")
    print()


def view_lp_performance(db_path: str):
    """View LP performance metrics"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            lp_name,
            total_quotes,
            total_wins,
            win_rate,
            avg_response_time_ms,
            best_price,
            worst_price,
            datetime(last_updated, 'unixepoch', 'localtime') as last_updated
        FROM lp_performance
        ORDER BY win_rate DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\n[!] No LP performance data found\n")
        return

    data = []
    for row in rows:
        data.append([
            row['lp_name'],
            row['total_quotes'],
            row['total_wins'],
            f"{row['win_rate']:.2f}%",
            f"{row['avg_response_time_ms']:.1f}ms" if row['avg_response_time_ms'] else '-',
            f"{row['best_price']:.2f}" if row['best_price'] else '-',
            f"{row['worst_price']:.2f}" if row['worst_price'] else '-',
            row['last_updated']
        ])

    print(f"\n{'='*120}")
    print("LP PERFORMANCE METRICS")
    print(f"{'='*120}\n")

    # Print header
    print(f"{'LP Name':<15} {'Total':<8} {'Wins':<8} {'Win Rate':<12} {'Avg Resp':<12} {'Best $':<12} {'Worst $':<12} {'Last Updated':<20}")
    print("-" * 120)

    # Print rows
    for row in data:
        print(f"{row[0]:<15} {row[1]:<8} {row[2]:<8} {row[3]:<12} {row[4]:<12} {row[5]:<12} {row[6]:<12} {row[7]:<20}")
    print()


def view_executions(db_path: str, limit: int = 20):
    """View recent executions"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            execution_id,
            quote_id,
            status,
            lp_name,
            exchange_side,
            executed_qty,
            avg_price,
            pnl_after_fees,
            pnl_asset,
            pnl_bps,
            datetime(executed_at, 'unixepoch', 'localtime') as executed
        FROM executions
        ORDER BY executed_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\n[!] No executions found in database\n")
        return

    data = []
    for row in rows:
        data.append([
            row['execution_id'][:15] + '...',
            row['quote_id'][:15] + '...',
            row['status'],
            row['lp_name'],
            row['exchange_side'] or '-',
            f"{row['executed_qty']:.4f}" if row['executed_qty'] else '-',
            f"{row['avg_price']:.2f}" if row['avg_price'] else '-',
            f"{row['pnl_after_fees']:.4f}" if row['pnl_after_fees'] else '-',
            row['pnl_asset'] or '-',
            f"{row['pnl_bps']:.2f}" if row['pnl_bps'] else '-',
            row['executed']
        ])

    print(f"\n{'='*120}")
    print(f"RECENT EXECUTIONS (Last {limit})")
    print(f"{'='*120}\n")

    # Print header
    print(f"{'Execution ID':<18} {'Quote ID':<18} {'Status':<8} {'LP':<10} {'Side':<6} {'Qty':<10} {'Price':<10} {'P&L':<10} {'Asset':<6} {'bps':<8} {'Executed':<20}")
    print("-" * 120)

    # Print rows
    for row in data:
        print(f"{row[0]:<18} {row[1]:<18} {row[2]:<8} {row[3]:<10} {row[4]:<6} {row[5]:<10} {row[6]:<10} {row[7]:<10} {row[8]:<6} {row[9]:<8} {row[10]:<20}")
    print()


def view_stats(db_path: str):
    """View database statistics"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Count quotes
    cursor.execute("SELECT COUNT(*) FROM quotes")
    total_quotes = cursor.fetchone()[0]

    # Count improvements
    cursor.execute("SELECT COUNT(*) FROM quotes WHERE is_improvement = 1")
    total_improvements = cursor.fetchone()[0]

    # Count LP quotes
    cursor.execute("SELECT COUNT(*) FROM lp_quotes")
    total_lp_quotes = cursor.fetchone()[0]

    # Count executions
    cursor.execute("SELECT COUNT(*) FROM executions")
    total_executions = cursor.fetchone()[0]

    # Successful executions
    cursor.execute("SELECT COUNT(*) FROM executions WHERE status = 'SUCCESS'")
    successful_executions = cursor.fetchone()[0]

    # Total P&L
    cursor.execute("SELECT SUM(pnl_after_fees) FROM executions WHERE status = 'SUCCESS' AND pnl_asset = 'USDT'")
    total_pnl_usdt = cursor.fetchone()[0] or 0.0

    # Average markup
    cursor.execute("SELECT AVG(markup_bps) FROM quotes")
    avg_markup = cursor.fetchone()[0]

    # Most active LP
    cursor.execute("""
        SELECT lp_name, COUNT(*) as count
        FROM quotes
        GROUP BY lp_name
        ORDER BY count DESC
        LIMIT 1
    """)
    most_active = cursor.fetchone()

    conn.close()

    print(f"\n{'='*60}")
    print("DATABASE STATISTICS")
    print(f"{'='*60}")
    print(f"Total Quotes:        {total_quotes}")
    print(f"Improvements:        {total_improvements} ({total_improvements/total_quotes*100:.1f}%)" if total_quotes > 0 else "Improvements:        0")
    print(f"Total LP Quotes:     {total_lp_quotes}")
    print(f"Total Executions:    {total_executions}")
    print(f"Successful:          {successful_executions} ({successful_executions/total_executions*100:.1f}%)" if total_executions > 0 else "Successful:          0")
    print(f"Total P&L (USDT):    {total_pnl_usdt:,.2f}")
    print(f"Average Markup:      {avg_markup:.2f} bps" if avg_markup else "Average Markup:      N/A")
    print(f"Most Active LP:      {most_active[0]} ({most_active[1]} wins)" if most_active else "Most Active LP:      N/A")
    print(f"{'='*60}\n")


def main():
    """Main CLI"""
    db_path = "quotes.db"

    if not Path(db_path).exists():
        print(f"\n[!] Database not found: {db_path}")
        print("[!] Run the application first to generate quotes\n")
        return

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == 'stats':
            view_stats(db_path)
        elif command == 'quotes':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            view_quotes(db_path, limit)
        elif command == 'lp-quotes':
            if len(sys.argv) > 2:
                # Specific quote ID
                view_lp_quotes(db_path, quote_id=sys.argv[2])
            else:
                view_lp_quotes(db_path)
        elif command == 'performance':
            view_lp_performance(db_path)
        elif command == 'executions':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            view_executions(db_path, limit)
        elif command == 'all':
            view_stats(db_path)
            view_lp_performance(db_path)
            view_executions(db_path, limit=5)
            view_quotes(db_path, limit=10)
        else:
            print(f"\n[!] Unknown command: {command}\n")
            print_help()
    else:
        # Default: show all
        view_stats(db_path)
        view_lp_performance(db_path)
        view_executions(db_path, limit=5)
        view_quotes(db_path, limit=10)


def print_help():
    print("\nUSAGE:")
    print("  python view_db.py [command] [args]")
    print("\nCOMMANDS:")
    print("  (none)           Show stats, performance, executions, and recent quotes")
    print("  all              Show all data")
    print("  stats            Show database statistics")
    print("  quotes [N]       Show last N quotes (default: 20)")
    print("  lp-quotes [ID]   Show LP quotes (all or for specific quote ID)")
    print("  performance      Show LP performance metrics")
    print("  executions [N]   Show last N executions (default: 20)")
    print("\nEXAMPLES:")
    print("  python view_db.py")
    print("  python view_db.py stats")
    print("  python view_db.py quotes 50")
    print("  python view_db.py executions 10")
    print("  python view_db.py lp-quotes Q20250119-143025-123")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted\n")
