"""
Data migration script: SQLite → PostgreSQL
Zero-downtime migration with progress tracking
"""

import sqlite3
import psycopg
from datetime import datetime
import sys

# Database connections
SQLITE_DB = "app.db"
POSTGRES_URL = "postgresql://app:app@db:5432/app"

# Tables to migrate (order matters for foreign keys)
TABLES_ORDER = [
    'settings',
    'api_users',
    'bots',
    'chats',
    'bot_stances',
    'bot_holdings',
    'bot_memories',
    'messages',
    'api_sessions',
    'system_checks',
]

def get_column_names(sqlite_cursor, table):
    """Get column names from SQLite table"""
    sqlite_cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in sqlite_cursor.fetchall()]

def get_boolean_columns(pg_cursor, table_name):
    """Get list of boolean column names in PostgreSQL table"""
    pg_cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND data_type = 'boolean'
    """, (table_name,))
    return [row[0] for row in pg_cursor.fetchall()]

def get_json_columns(pg_cursor, table_name):
    """Get list of JSON column names in PostgreSQL table"""
    pg_cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND (data_type = 'json' OR data_type = 'jsonb')
    """, (table_name,))
    return [row[0] for row in pg_cursor.fetchall()]

def convert_row_types(row, columns, boolean_columns, json_columns):
    """Convert SQLite types to PostgreSQL types"""
    import json
    converted = []
    for i, value in enumerate(row):
        col_name = columns[i]

        if value is None:
            converted.append(None)
        # Convert SQLite boolean (0/1) to PostgreSQL boolean (False/True)
        elif col_name in boolean_columns:
            converted.append(bool(value))
        # Convert to JSON - handle numbers, strings, and already-JSON strings
        elif col_name in json_columns:
            if isinstance(value, str):
                # Try to parse as JSON first (might already be JSON string)
                try:
                    parsed = json.loads(value)
                    converted.append(json.dumps(parsed))
                except:
                    # If not valid JSON, treat as plain string and encode
                    converted.append(json.dumps(value))
            else:
                # Numbers, booleans, etc. - encode to JSON
                converted.append(json.dumps(value))
        else:
            converted.append(value)
    return tuple(converted)

def migrate_table(sqlite_conn, pg_conn, table_name):
    """Migrate a single table from SQLite to PostgreSQL"""
    print(f"\n[{table_name}]", end=" ", flush=True)

    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()

    # Get column names
    columns = get_column_names(sqlite_cur, table_name)

    # Get boolean columns for type conversion
    boolean_columns = get_boolean_columns(pg_cur, table_name)

    # Get JSON columns for type conversion
    json_columns = get_json_columns(pg_cur, table_name)

    # Count rows
    sqlite_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = sqlite_cur.fetchone()[0]

    if total_rows == 0:
        print(f"0 rows (empty table)")
        return 0

    print(f"{total_rows} rows...", end=" ", flush=True)

    # Fetch all rows from SQLite
    sqlite_cur.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cur.fetchall()

    # Prepare INSERT statement
    placeholders = ', '.join(['%s'] * len(columns))
    columns_str = ', '.join(columns)
    insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

    # Insert into PostgreSQL
    migrated = 0
    for row in rows:
        try:
            # Convert types (booleans, JSON, etc.)
            converted_row = convert_row_types(row, columns, boolean_columns, json_columns)
            pg_cur.execute(insert_sql, converted_row)
            migrated += 1
        except Exception as e:
            print(f"\n  ERROR on row: {e}")
            print(f"  Data: {row}")
            # Continue with other rows

    pg_conn.commit()
    print(f"[OK] {migrated} migrated")
    return migrated

def main():
    print("="*60)
    print("SQLite to PostgreSQL Migration")
    print("="*60)
    print(f"Source: {SQLITE_DB}")
    print(f"Target: {POSTGRES_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    try:
        # Connect to databases
        print("\n[1] Connecting to databases...")
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        pg_conn = psycopg.connect(POSTGRES_URL)
        print("  [OK] Connected to both databases")

        # Migrate tables
        print("\n[2] Migrating tables:")
        total_migrated = 0

        for table in TABLES_ORDER:
            count = migrate_table(sqlite_conn, pg_conn, table)
            total_migrated += count

        # Final summary
        print("\n" + "="*60)
        print("[DONE] Migration completed successfully!")
        print(f"Total rows migrated: {total_migrated}")
        print("="*60)

        # Close connections
        sqlite_conn.close()
        pg_conn.close()

        return 0

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
