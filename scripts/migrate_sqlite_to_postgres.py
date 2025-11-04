"""
SQLite to PostgreSQL Data Migration Script

Migrates data from SQLite (app.db) to PostgreSQL while preserving:
- All table data
- Foreign key relationships
- Timestamps and metadata
- Encrypted tokens

Usage:
    # 1. Ensure PostgreSQL is running and DATABASE_URL is set
    export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname"

    # 2. Run migration (dry-run first)
    python scripts/migrate_sqlite_to_postgres.py --dry-run

    # 3. Execute migration
    python scripts/migrate_sqlite_to_postgres.py

    # 4. Verify data
    python scripts/migrate_sqlite_to_postgres.py --verify-only

Environment Variables:
    SQLITE_DB_PATH - Source SQLite database (default: ./app.db)
    DATABASE_URL - Target PostgreSQL connection string (required)
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import (
    Base,
    Bot,
    Chat,
    Message,
    Setting,
    BotStance,
    BotHolding,
    BotMemory,
    SystemCheck,
    ApiUser,
    ApiSession,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class DatabaseMigration:
    """Handles SQLite to PostgreSQL data migration."""

    # Table migration order (respects foreign keys)
    MIGRATION_ORDER = [
        "settings",
        "api_users",
        "api_sessions",
        "bots",
        "chats",
        "messages",
        "bot_stances",
        "bot_holdings",
        "bot_memories",
        "system_checks",
    ]

    # Table model mapping
    TABLE_MODELS = {
        "settings": Setting,
        "api_users": ApiUser,
        "api_sessions": ApiSession,
        "bots": Bot,
        "chats": Chat,
        "messages": Message,
        "bot_stances": BotStance,
        "bot_holdings": BotHolding,
        "bot_memories": BotMemory,
        "system_checks": SystemCheck,
    }

    def __init__(
        self,
        sqlite_path: str = "./app.db",
        postgres_url: str = None,
        dry_run: bool = False,
    ):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url or os.getenv("DATABASE_URL")
        self.dry_run = dry_run

        if not self.postgres_url:
            raise ValueError("DATABASE_URL environment variable not set")

        if not self.postgres_url.startswith("postgresql"):
            raise ValueError(f"DATABASE_URL must be PostgreSQL, got: {self.postgres_url}")

        # Create engines
        self.sqlite_engine = create_engine(f"sqlite:///{self.sqlite_path}")
        self.postgres_engine = create_engine(self.postgres_url)

        # Create sessions
        self.sqlite_session = sessionmaker(bind=self.sqlite_engine)()
        self.postgres_session = sessionmaker(bind=self.postgres_engine)()

    def verify_prerequisites(self) -> bool:
        """Verify migration prerequisites."""
        logger.info("=== Verifying Prerequisites ===")

        # Check SQLite database exists
        if not Path(self.sqlite_path).exists():
            logger.error(f"SQLite database not found: {self.sqlite_path}")
            return False
        logger.info(f"✅ SQLite database found: {self.sqlite_path}")

        # Check PostgreSQL connection
        try:
            self.postgres_engine.connect()
            logger.info("✅ PostgreSQL connection successful")
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            return False

        # Check PostgreSQL is empty (safety check)
        inspector = inspect(self.postgres_engine)
        existing_tables = inspector.get_table_names()
        if existing_tables:
            logger.warning(f"⚠️  PostgreSQL has existing tables: {existing_tables}")
            logger.warning("   Migration will OVERWRITE existing data!")
            if not self.dry_run:
                confirm = input("   Continue? (yes/no): ")
                if confirm.lower() != "yes":
                    logger.info("   Migration aborted by user")
                    return False

        return True

    def get_table_counts(self, session: Session) -> Dict[str, int]:
        """Get record counts for all tables."""
        counts = {}
        for table_name in self.MIGRATION_ORDER:
            model = self.TABLE_MODELS[table_name]
            count = session.query(model).count()
            counts[table_name] = count
        return counts

    def migrate_table(self, table_name: str) -> Dict[str, Any]:
        """Migrate a single table."""
        logger.info(f"--- Migrating table: {table_name} ---")

        model = self.TABLE_MODELS[table_name]

        # Count source records
        source_count = self.sqlite_session.query(model).count()
        logger.info(f"  Source records: {source_count}")

        if source_count == 0:
            logger.info(f"  Skipping (empty table)")
            return {"table": table_name, "migrated": 0, "skipped": True}

        if self.dry_run:
            logger.info(f"  DRY RUN: Would migrate {source_count} records")
            return {"table": table_name, "migrated": 0, "dry_run": True}

        # Fetch all records from SQLite
        records = self.sqlite_session.query(model).all()

        # Insert into PostgreSQL
        migrated_count = 0
        for record in records:
            # Create dict from record (excluding relationship attributes)
            record_dict = {}
            for column in model.__table__.columns:
                record_dict[column.name] = getattr(record, column.name)

            # Create new record in PostgreSQL
            new_record = model(**record_dict)
            self.postgres_session.add(new_record)
            migrated_count += 1

            # Commit in batches of 100
            if migrated_count % 100 == 0:
                self.postgres_session.commit()
                logger.info(f"  Migrated {migrated_count}/{source_count} records...")

        # Final commit
        self.postgres_session.commit()
        logger.info(f"  ✅ Migrated {migrated_count} records successfully")

        return {"table": table_name, "migrated": migrated_count, "success": True}

    def verify_migration(self) -> bool:
        """Verify migration completed successfully."""
        logger.info("=== Verifying Migration ===")

        sqlite_counts = self.get_table_counts(self.sqlite_session)
        postgres_counts = self.get_table_counts(self.postgres_session)

        all_match = True
        for table_name in self.MIGRATION_ORDER:
            sqlite_count = sqlite_counts[table_name]
            postgres_count = postgres_counts[table_name]

            if sqlite_count == postgres_count:
                logger.info(f"✅ {table_name}: {postgres_count} records (matched)")
            else:
                logger.error(
                    f"❌ {table_name}: SQLite={sqlite_count}, PostgreSQL={postgres_count} (MISMATCH!)"
                )
                all_match = False

        return all_match

    def run_migration(self) -> bool:
        """Execute full migration."""
        logger.info("\n" + "=" * 60)
        logger.info("SQLite to PostgreSQL Migration")
        logger.info("=" * 60)
        logger.info(f"Source: {self.sqlite_path}")
        logger.info(f"Target: {self.postgres_url}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("=" * 60 + "\n")

        # Verify prerequisites
        if not self.verify_prerequisites():
            logger.error("❌ Prerequisites check failed")
            return False

        # Get source counts
        logger.info("=== Source Database Summary ===")
        source_counts = self.get_table_counts(self.sqlite_session)
        total_records = 0
        for table_name, count in source_counts.items():
            logger.info(f"  {table_name}: {count} records")
            total_records += count
        logger.info(f"  TOTAL: {total_records} records\n")

        if self.dry_run:
            logger.info("=== DRY RUN MODE ===")
            logger.info("No data will be written to PostgreSQL\n")

        # Migrate tables in order
        logger.info("=== Starting Migration ===")
        results = []
        for table_name in self.MIGRATION_ORDER:
            result = self.migrate_table(table_name)
            results.append(result)

        # Verify migration
        if not self.dry_run:
            logger.info("")
            if self.verify_migration():
                logger.info("\n✅ Migration completed successfully!")
                return True
            else:
                logger.error("\n❌ Migration verification failed!")
                return False
        else:
            logger.info("\n✅ Dry run completed")
            return True

    def cleanup(self):
        """Close database connections."""
        self.sqlite_session.close()
        self.postgres_session.close()
        self.sqlite_engine.dispose()
        self.postgres_engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-db",
        default="./app.db",
        help="Path to SQLite database (default: ./app.db)",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without writing to PostgreSQL",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify migration (no data transfer)",
    )

    args = parser.parse_args()

    # Create migration instance
    migration = DatabaseMigration(
        sqlite_path=args.sqlite_db,
        postgres_url=args.postgres_url,
        dry_run=args.dry_run,
    )

    try:
        if args.verify_only:
            logger.info("=== Verification Mode ===")
            if migration.verify_migration():
                logger.info("✅ Verification passed")
                sys.exit(0)
            else:
                logger.error("❌ Verification failed")
                sys.exit(1)
        else:
            # Run migration
            success = migration.run_migration()
            sys.exit(0 if success else 1)

    except Exception as e:
        logger.exception(f"Migration failed with error: {e}")
        sys.exit(1)

    finally:
        migration.cleanup()


if __name__ == "__main__":
    main()
