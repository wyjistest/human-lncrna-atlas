#!/usr/bin/env python3
"""
Database Migration Runner

A simple, lightweight migration system for managing schema changes.
Tracks applied migrations in a schema_migrations table.

Usage:
    python run_migrations.py              # Apply pending migrations
    python run_migrations.py --status     # Show migration status
    python run_migrations.py --dry-run    # Show what would be applied

Environment:
    Reads database connection from .env file or environment variables.
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def get_database_url() -> str:
    """Get database URL from environment."""
    # Try to load from .env file
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "amax")
    password = os.environ.get("DB_PASSWORD", "")
    dbname = os.environ.get("DB_NAME", "lncrna_production")

    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def ensure_migrations_table(engine) -> None:
    """Create schema_migrations table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                description TEXT
            )
        """))
        conn.commit()


def get_applied_migrations(engine) -> set:
    """Get set of already applied migration versions."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version FROM schema_migrations"))
        return {row[0] for row in result.fetchall()}


def get_migration_files(migrations_dir: Path) -> list:
    """Get sorted list of migration SQL files."""
    pattern = re.compile(r"^(\d{3})_.+\.sql$")
    migrations = []

    for file in sorted(migrations_dir.glob("*.sql")):
        match = pattern.match(file.name)
        if match:
            version = match.group(1)
            migrations.append((version, file))

    return migrations


def apply_migration(engine, version: str, sql_file: Path, dry_run: bool = False) -> bool:
    """Apply a single migration file."""
    # Extract description from first comment line
    description = ""
    with open(sql_file) as f:
        content = f.read()
        for line in content.split("\n"):
            if line.startswith("-- Description:"):
                description = line.replace("-- Description:", "").strip()
                break

    print(f"  Applying {sql_file.name}...")
    if description:
        print(f"    Description: {description}")

    if dry_run:
        print("    [DRY RUN] Would execute SQL")
        return True

    try:
        with engine.connect() as conn:
            # Execute migration SQL
            conn.execute(text(content))

            # Record migration as applied
            conn.execute(
                text("""
                    INSERT INTO schema_migrations (version, description)
                    VALUES (:version, :description)
                """),
                {"version": version, "description": description},
            )
            conn.commit()

        print(f"    Applied successfully")
        return True

    except SQLAlchemyError as e:
        print(f"    ERROR: {e}")
        return False


def show_status(engine, migrations: list, applied: set) -> None:
    """Show status of all migrations."""
    print("\nMigration Status:")
    print("-" * 60)
    print(f"{'Version':<10} {'File':<35} {'Status':<10}")
    print("-" * 60)

    for version, sql_file in migrations:
        status = "Applied" if version in applied else "Pending"
        print(f"{version:<10} {sql_file.name:<35} {status:<10}")

    print("-" * 60)
    print(f"Total: {len(migrations)} migrations, {len(applied)} applied, {len(migrations) - len(applied)} pending")


def main():
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be applied without executing")
    args = parser.parse_args()

    migrations_dir = Path(__file__).parent
    print(f"Migration directory: {migrations_dir}")

    # Get database connection
    db_url = get_database_url()
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else db_url}")

    try:
        engine = create_engine(db_url)

        # Ensure migrations table exists
        ensure_migrations_table(engine)

        # Get migrations
        migrations = get_migration_files(migrations_dir)
        applied = get_applied_migrations(engine)

        if args.status:
            show_status(engine, migrations, applied)
            return

        # Find pending migrations
        pending = [(v, f) for v, f in migrations if v not in applied]

        if not pending:
            print("\nNo pending migrations.")
            return

        print(f"\nFound {len(pending)} pending migration(s):")

        # Apply each pending migration
        success_count = 0
        for version, sql_file in pending:
            if apply_migration(engine, version, sql_file, dry_run=args.dry_run):
                success_count += 1
            else:
                print(f"\nMigration failed. Stopping.")
                break

        if not args.dry_run:
            print(f"\nApplied {success_count}/{len(pending)} migrations.")

    except SQLAlchemyError as e:
        print(f"Database error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
