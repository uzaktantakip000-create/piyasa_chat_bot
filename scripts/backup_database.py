"""
Automated Database Backup Script

Creates compressed backups with rotation strategy:
- Daily backups: Keep last 7 days
- Weekly backups: Keep last 4 weeks
- Monthly backups: Keep last 12 months

Supports both SQLite and PostgreSQL databases.

Usage:
    python scripts/backup_database.py [--backup-dir PATH] [--dry-run]

Environment Variables:
    DATABASE_URL - Database connection string
    BACKUP_DIR - Backup directory (default: ./backups)
    BACKUP_RETENTION_DAYS - Daily backup retention (default: 7)
    BACKUP_RETENTION_WEEKS - Weekly backup retention (default: 4)
    BACKUP_RETENTION_MONTHS - Monthly backup retention (default: 12)
"""

import argparse
import gzip
import logging
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DatabaseBackup:
    """Handles database backup operations with rotation."""

    def __init__(
        self,
        backup_dir: str = "./backups",
        retention_days: int = 7,
        retention_weeks: int = 4,
        retention_months: int = 12,
    ):
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.retention_weeks = retention_weeks
        self.retention_months = retention_months

        # Create backup directories
        self.daily_dir = self.backup_dir / "daily"
        self.weekly_dir = self.backup_dir / "weekly"
        self.monthly_dir = self.backup_dir / "monthly"

        for dir_path in [self.daily_dir, self.weekly_dir, self.monthly_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Get database URL from environment
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        self.db_type = self._detect_db_type()

    def _detect_db_type(self) -> str:
        """Detect database type from URL."""
        if self.database_url.startswith("postgresql"):
            return "postgresql"
        elif self.database_url.startswith("sqlite"):
            return "sqlite"
        else:
            raise ValueError(f"Unsupported database type: {self.database_url}")

    def _get_backup_filename(self, backup_type: str = "daily") -> str:
        """Generate backup filename with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"backup_{backup_type}_{timestamp}.sql.gz"

    def _compress_file(self, source_path: Path, dest_path: Path) -> None:
        """Compress file with gzip."""
        with open(source_path, "rb") as f_in:
            with gzip.open(dest_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

    def backup_sqlite(self, output_path: Path) -> bool:
        """Backup SQLite database."""
        try:
            # Extract database file path from URL
            db_path = self.database_url.replace("sqlite:///", "")
            db_file = Path(db_path)

            if not db_file.exists():
                logger.error(f"SQLite database file not found: {db_file}")
                return False

            logger.info(f"Backing up SQLite database: {db_file}")

            # Use Python sqlite3 module to dump database
            import sqlite3

            dump_file = output_path.with_suffix("")  # Remove .gz

            # Connect to database
            conn = sqlite3.connect(str(db_file))

            # Perform SQL dump
            with open(dump_file, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")

            conn.close()

            # Compress the dump
            self._compress_file(dump_file, output_path)

            # Remove temporary dump file
            dump_file.unlink()

            logger.info(f"SQLite backup created: {output_path}")
            return True

        except sqlite3.Error as e:
            logger.error(f"SQLite backup failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during SQLite backup: {e}")
            return False

    def backup_postgresql(self, output_path: Path) -> bool:
        """Backup PostgreSQL database."""
        try:
            # Parse PostgreSQL connection string
            # Format: postgresql://user:password@host:port/dbname
            from urllib.parse import urlparse

            parsed = urlparse(self.database_url)

            logger.info(f"Backing up PostgreSQL database: {parsed.path[1:]}")

            # Use pg_dump command
            import subprocess

            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password

            dump_file = output_path.with_suffix("")  # Remove .gz

            cmd = [
                "pg_dump",
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres",
                "-d", parsed.path[1:],  # Remove leading /
                "-F", "p",  # Plain text format
                "-f", str(dump_file),
            ]

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            # Compress the dump
            self._compress_file(dump_file, output_path)

            # Remove temporary dump file
            dump_file.unlink()

            logger.info(f"PostgreSQL backup created: {output_path}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"PostgreSQL backup failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during PostgreSQL backup: {e}")
            return False

    def create_backup(self, backup_type: str = "daily") -> Optional[Path]:
        """Create database backup."""
        backup_dir = {
            "daily": self.daily_dir,
            "weekly": self.weekly_dir,
            "monthly": self.monthly_dir,
        }.get(backup_type, self.daily_dir)

        filename = self._get_backup_filename(backup_type)
        output_path = backup_dir / filename

        logger.info(f"Creating {backup_type} backup: {output_path}")

        if self.db_type == "sqlite":
            success = self.backup_sqlite(output_path)
        elif self.db_type == "postgresql":
            success = self.backup_postgresql(output_path)
        else:
            logger.error(f"Unsupported database type: {self.db_type}")
            return None

        if success:
            size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Backup completed: {output_path} ({size_mb:.2f} MB)")
            return output_path
        else:
            return None

    def _get_old_backups(self, backup_dir: Path, days: int) -> List[Path]:
        """Get list of backups older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        old_backups = []

        for backup_file in backup_dir.glob("backup_*.sql.gz"):
            # Parse timestamp from filename
            try:
                # Format: backup_daily_20231103_123456.sql.gz
                parts = backup_file.stem.split("_")
                date_str = parts[2]  # YYYYMMDD
                backup_date = datetime.strptime(date_str, "%Y%m%d")

                if backup_date < cutoff_date:
                    old_backups.append(backup_file)
            except (IndexError, ValueError):
                logger.warning(f"Could not parse date from filename: {backup_file}")
                continue

        return old_backups

    def rotate_backups(self, dry_run: bool = False) -> None:
        """Apply backup rotation policy."""
        logger.info("Running backup rotation...")

        rotations = [
            (self.daily_dir, self.retention_days, "daily"),
            (self.weekly_dir, self.retention_weeks * 7, "weekly"),
            (self.monthly_dir, self.retention_months * 30, "monthly"),
        ]

        total_deleted = 0
        total_size = 0

        for backup_dir, retention_days, backup_type in rotations:
            old_backups = self._get_old_backups(backup_dir, retention_days)

            if not old_backups:
                logger.info(f"No old {backup_type} backups to delete")
                continue

            logger.info(f"Found {len(old_backups)} old {backup_type} backups")

            for backup_file in old_backups:
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                total_size += size_mb

                if dry_run:
                    logger.info(f"[DRY RUN] Would delete: {backup_file} ({size_mb:.2f} MB)")
                else:
                    logger.info(f"Deleting old backup: {backup_file} ({size_mb:.2f} MB)")
                    backup_file.unlink()
                    total_deleted += 1

        if dry_run:
            logger.info(f"[DRY RUN] Would delete {len(old_backups)} backups ({total_size:.2f} MB total)")
        else:
            logger.info(f"Deleted {total_deleted} old backups ({total_size:.2f} MB freed)")

    def determine_backup_type(self) -> str:
        """Determine backup type based on current date."""
        now = datetime.now()

        # Monthly backup: First day of month
        if now.day == 1:
            return "monthly"

        # Weekly backup: Sunday (weekday 6)
        if now.weekday() == 6:
            return "weekly"

        # Daily backup: Default
        return "daily"

    def run(self, dry_run: bool = False, backup_type: Optional[str] = None) -> bool:
        """Run backup process with rotation."""
        if dry_run:
            logger.info("[DRY RUN MODE] No changes will be made")

        # Determine backup type if not specified
        if backup_type is None:
            backup_type = self.determine_backup_type()
            logger.info(f"Auto-detected backup type: {backup_type}")

        # Create backup
        if not dry_run:
            backup_path = self.create_backup(backup_type)
            if not backup_path:
                logger.error("Backup creation failed")
                return False
        else:
            logger.info(f"[DRY RUN] Would create {backup_type} backup")

        # Rotate old backups
        self.rotate_backups(dry_run=dry_run)

        logger.info("Backup process completed successfully")
        return True


def main():
    parser = argparse.ArgumentParser(description="Automated database backup")
    parser.add_argument(
        "--backup-dir",
        default=os.getenv("BACKUP_DIR", "./backups"),
        help="Backup directory (default: ./backups)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int(os.getenv("BACKUP_RETENTION_DAYS", "7")),
        help="Daily backup retention in days (default: 7)",
    )
    parser.add_argument(
        "--retention-weeks",
        type=int,
        default=int(os.getenv("BACKUP_RETENTION_WEEKS", "4")),
        help="Weekly backup retention in weeks (default: 4)",
    )
    parser.add_argument(
        "--retention-months",
        type=int,
        default=int(os.getenv("BACKUP_RETENTION_MONTHS", "12")),
        help="Monthly backup retention in months (default: 12)",
    )
    parser.add_argument(
        "--type",
        choices=["daily", "weekly", "monthly"],
        help="Force specific backup type (default: auto-detect)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate backup without making changes",
    )

    args = parser.parse_args()

    backup = DatabaseBackup(
        backup_dir=args.backup_dir,
        retention_days=args.retention_days,
        retention_weeks=args.retention_weeks,
        retention_months=args.retention_months,
    )

    success = backup.run(dry_run=args.dry_run, backup_type=args.type)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\nBackup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
