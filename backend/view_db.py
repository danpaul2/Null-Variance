"""
view_db.py - Interactive CLI tool to view database contents
Usage:
    python view_db.py               (shows all tables summary)
    python view_db.py instruments   (views instruments table)
    python view_db.py sessions      (views test_sessions table)
    python view_db.py users         (views users table)
    python view_db.py activity      (views activity_log table)
"""
import sys
import json
import sqlite3
import pandas as pd

DB_FILE = "nawidb.sqlite"

def main():
    con = sqlite3.connect(DB_FILE)
    table_arg = sys.argv[1].lower() if len(sys.argv) > 1 else None

    if not table_arg:
        print("\n" + "="*55)
        print("  NAWI OIML R-76 DATABASE OVERVIEW")
        print("="*55)
        cur = con.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        data_tables = [t for t in tables if not t.startswith("sqlite_") and not t.startswith("alembic_")]
        
        for t in data_tables:
            count = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"  • {t.ljust(15)} : {count} records")
        
        print("\nTo view any table in detail, run:")
        print("  python view_db.py instruments")
        print("  python view_db.py sessions")
        print("  python view_db.py users")
        print("  python view_db.py activity")
        print("="*55 + "\n")
        return

    table_map = {
        "instruments": "instruments",
        "sessions": "test_sessions",
        "test_sessions": "test_sessions",
        "users": "users",
        "activity": "activity_log",
        "attachments": "attachments"
    }

    target = table_map.get(table_arg, table_arg)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)

    try:
        df = pd.read_sql_query(f"SELECT * FROM {target}", con)
        print(f"\n--- TABLE: {target} ({len(df)} rows) ---")
        if target == "users":
            # Mask sensitive hash in preview
            df["hashed_password"] = df["hashed_password"].apply(lambda x: x[:10] + "..." if isinstance(x, str) else x)
        elif target == "test_sessions":
            # Shorten JSON previews for readability
            for col in ["eccentricity_data", "repeatability_data", "discrimination_data", "linearity_data"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: str(x)[:30] + "..." if x else "")
        print(df.to_string(index=False))
        print()
    except Exception as e:
        print(f"Error querying table {target}: {e}")

if __name__ == "__main__":
    main()
