"""
Database Restore Script

Restores database from compressed backup files.

Usage:
    python scripts/restore_database.py <backup_file> [--dry-run]

Environment Variables:
    DATABASE_URL - Database connection string (target database)

WARNING: This will overwrite the existing database!
"""

import argparse
import gzip
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DatabaseRestore:
    """Handles database restore operations."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.db_type = self._detect_db_type()

    def _detect_db_type(self) -> str:
        """Detect database type from URL."""
        if self.database_url.startswith("postgresql"):
            return "postgresql"
        elif self.database_url.startswith("sqlite"):
            return "sqlite"
        else:
            raise ValueError(f"Unsupported database type: {self.database_url}")

    def _decompress_backup(self, backup_file: Path, output_file: Path) -> bool:
        """Decompress gzipped backup file."""
        try:
            logger.info(f"Decompressing backup: {backup_file}")
            with gzip.open(backup_file, "rb") as f_in:
                with open(output_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logger.info(f"Decompressed to: {output_file}")
            return True
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            return False

    def restore_sqlite(self, sql_file: Path, dry_run: bool = False) -> bool:
        """Restore SQLite database from SQL dump."""
        try:
            # Extract database file path from URL
            db_path = self.database_url.replace("sqlite:///", "")
            db_file = Path(db_path)

            logger.info(f"Restoring SQLite database: {db_file}")

            if dry_run:
                logger.info(f"[DRY RUN] Would restore from: {sql_file}")
                logger.info(f"[DRY RUN] Target database: {db_file}")
                return True

            # Backup existing database if it exists
            if db_file.exists():
                backup_path = db_file.with_suffix(".db.bak")
                logger.info(f"Backing up existing database to: {backup_path}")
                shutil.copy2(db_file, backup_path)

            # Read SQL dump
            sql_content = sql_file.read_text(encoding='utf-8')

            # Restore using Python sqlite3 module
            import sqlite3

            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            # Execute SQL statements
            cursor.executescript(sql_content)

            conn.commit()
            conn.close()

            logger.info(f"SQLite database restored successfully: {db_file}")
            return True

        except sqlite3.Error as e:
            logger.error(f"SQLite restore failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during SQLite restore: {e}")
            return False

    def restore_postgresql(self, sql_file: Path, dry_run: bool = False) -> bool:
        """Restore PostgreSQL database from SQL dump."""
        try:
            # Parse PostgreSQL connection string
            parsed = urlparse(self.database_url)
            db_name = parsed.path[1:]  # Remove leading /

            logger.info(f"Restoring PostgreSQL database: {db_name}")

            if dry_run:
                logger.info(f"[DRY RUN] Would restore from: {sql_file}")
                logger.info(f"[DRY RUN] Target database: {db_name}")
                return True

            # Set password environment variable
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password

            # Use psql command to restore
            cmd = [
                "psql",
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres",
                "-d", db_name,
                "-f", str(sql_file),
            ]

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"PostgreSQL database restored successfully: {db_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"PostgreSQL restore failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during PostgreSQL restore: {e}")
            return False

    def restore(self, backup_file: Path, dry_run: bool = False) -> bool:
        """Restore database from backup file."""
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False

        # Decompress backup
        sql_file = backup_file.with_suffix("")  # Remove .gz suffix
        if backup_file.suffix == ".gz":
            if not self._decompress_backup(backup_file, sql_file):
                return False
        else:
            sql_file = backup_file

        try:
            # Restore based on database type
            if self.db_type == "sqlite":
                success = self.restore_sqlite(sql_file, dry_run=dry_run)
            elif self.db_type == "postgresql":
                success = self.restore_postgresql(sql_file, dry_run=dry_run)
            else:
                logger.error(f"Unsupported database type: {self.db_type}")
                return False

            return success

        finally:
            # Cleanup temporary SQL file if we decompressed
            if backup_file.suffix == ".gz" and sql_file.exists():
                sql_file.unlink()
                logger.info(f"Cleaned up temporary file: {sql_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Restore database from backup",
        epilog="WARNING: This will overwrite the existing database!",
    )
    parser.add_argument(
        "backup_file",
        type=Path,
        help="Path to backup file (.sql.gz or .sql)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "sqlite:///./app.db"),
        help="Target database URL (default: from DATABASE_URL env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate restore without making changes",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    # Confirmation prompt
    if not args.dry_run and not args.yes:
        response = input(
            f"\n⚠️  WARNING: This will overwrite the database at:\n"
            f"   {args.database_url}\n\n"
            f"   From backup: {args.backup_file}\n\n"
            f"   Are you sure? Type 'yes' to continue: "
        )
        if response.lower() != "yes":
            logger.info("Restore cancelled by user")
            sys.exit(0)

    if args.dry_run:
        logger.info("[DRY RUN MODE] No changes will be made")

    restore = DatabaseRestore(args.database_url)
    success = restore.restore(args.backup_file, dry_run=args.dry_run)

    if success:
        logger.info("✅ Restore completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Restore failed")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\nRestore interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
