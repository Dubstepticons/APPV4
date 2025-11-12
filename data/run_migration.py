#!/usr/bin/env python3
"""
Database migration runner - adds missing efficiency column.

Run this script to update your database schema:
    python -m data.run_migration
    OR
    python data/run_migration.py (from project root)
"""

import sys
from pathlib import Path

# Add project root to Python path if running directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data.db_engine import engine
from sqlalchemy import text

def run_migration():
    """Run the efficiency column migration."""
    migration_file = Path(__file__).parent / "migrations" / "add_efficiency_column.sql"

    print(f"[MIGRATION] Reading migration from: {migration_file}")

    if not migration_file.exists():
        print(f"[MIGRATION] ERROR: Migration file not found: {migration_file}")
        return False

    sql = migration_file.read_text()
    print(f"[MIGRATION] Executing SQL migration...")

    try:
        with engine.connect() as conn:
            # Execute the migration
            conn.execute(text(sql))
            conn.commit()
            print(f"[MIGRATION] [OK] Successfully added 'efficiency' column to traderecord table")
            return True
    except Exception as e:
        error_msg = str(e).lower()
        print(f"[MIGRATION] ERROR: {e}")

        # If column already exists, that's OK (SQLite error: "duplicate column name")
        if any(phrase in error_msg for phrase in [
            "already exists",
            "duplicate column",
            "duplicate column name"
        ]):
            print(f"[MIGRATION] Column already exists, migration skipped")
            return True

        return False

if __name__ == "__main__":
    print("\n" + "="*80)
    print("DATABASE MIGRATION: Add efficiency column")
    print("="*80 + "\n")

    success = run_migration()

    if success:
        print("\n[OK] Migration completed successfully!")
        print("You can now start the app.\n")
    else:
        print("\n[X] Migration failed!")
        print("Please check the error above and try again.\n")
