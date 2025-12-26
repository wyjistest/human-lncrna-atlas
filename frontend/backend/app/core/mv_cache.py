"""
Thread-safe Materialized View Cache

Phase 9.24: Centralized thread-safe cache for materialized view availability checks.
Resolves:
- Code duplication between lncrna_chipseq_overlap.py and igv_overlap_track.py
- Thread-safety issues with module-level global dict (Codex review finding)

Usage:
    from app.core.mv_cache import mv_cache

    # Check if MV is available
    if mv_cache.is_available(db):
        # Use MV query
    else:
        # Use fallback query

    # Reset cache (e.g., after MV refresh)
    mv_cache.reset()
"""
import logging
import threading
import time

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MaterializedViewCache:
    """
    Thread-safe cache for materialized view availability status.

    Uses threading.RLock to protect read-modify-write operations on the cache state.
    Supports TTL-based expiration to detect MV creation/refresh during runtime.

    Attributes:
        mv_name: Name of the materialized view to check
        ttl_seconds: Cache TTL in seconds (default: 300 = 5 minutes)
    """

    def __init__(self, mv_name: str, ttl_seconds: int = 300):
        """
        Initialize the cache.

        Args:
            mv_name: Name of the materialized view (e.g., 'mv_lncrna_chipseq_overlaps')
            ttl_seconds: How long to cache the availability status
        """
        self._mv_name = mv_name
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._checked = False
        self._available = False
        self._checked_at = 0.0

    @property
    def mv_name(self) -> str:
        """Get the materialized view name."""
        return self._mv_name

    @property
    def ttl_seconds(self) -> int:
        """Get the cache TTL in seconds."""
        return self._ttl_seconds

    def reset(self) -> None:
        """
        Reset the cache, forcing a fresh check on next query.

        Thread-safe: uses lock to ensure atomic reset.
        Call this after creating/refreshing the MV.
        """
        with self._lock:
            self._checked = False
            self._available = False
            self._checked_at = 0.0
        logger.info(f"Materialized view cache reset for '{self._mv_name}'")

    def is_available(self, db: Session) -> bool:
        """
        Check if the materialized view exists and is populated.

        Thread-safe: uses lock to protect cache read/write.
        Uses TTL to periodically re-check, detecting MV creation during runtime.

        Args:
            db: Database session (must be PostgreSQL for MV support)

        Returns:
            True if MV exists and is populated, False otherwise
        """
        with self._lock:
            # Check if cached result is still valid
            if self._checked:
                elapsed = time.monotonic() - self._checked_at
                if elapsed < self._ttl_seconds:
                    return self._available
                # TTL expired, will re-check below
                logger.debug(f"MV cache TTL expired ({elapsed:.1f}s), re-checking...")

            # Perform the actual check
            available = self._check_mv_exists(db)

            # Update cache state (still under lock)
            self._checked = True
            self._available = available
            self._checked_at = time.monotonic()

            return available

    def _check_mv_exists(self, db: Session) -> bool:
        """
        Internal method to check if MV exists in PostgreSQL.

        Should only be called while holding the lock.

        Args:
            db: Database session

        Returns:
            True if MV exists and is populated
        """
        try:
            bind = db.get_bind()
            if not bind or bind.dialect.name != "postgresql":
                return False

            from sqlalchemy import text

            check_sql = text("""
                SELECT
                    c.relname,
                    c.relispopulated
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'm'  -- materialized view
                  AND n.nspname = 'public'
                  AND c.relname = :mv_name
            """)

            result = db.execute(check_sql, {"mv_name": self._mv_name}).fetchone()

            if result and result.relispopulated:
                logger.info(f"Materialized view '{self._mv_name}' is available and populated")
                return True
            else:
                if result:
                    logger.warning(f"Materialized view '{self._mv_name}' exists but is not populated")
                else:
                    logger.info(f"Materialized view '{self._mv_name}' does not exist")
                return False

        except Exception as e:
            logger.error(f"Error checking materialized view '{self._mv_name}': {e}")
            return False

    def get_status(self) -> dict:
        """
        Get current cache status (for debugging/monitoring).

        Thread-safe.

        Returns:
            Dict with 'checked', 'available', 'checked_at', 'ttl_seconds', 'mv_name'
        """
        with self._lock:
            return {
                "mv_name": self._mv_name,
                "checked": self._checked,
                "available": self._available,
                "checked_at": self._checked_at,
                "ttl_seconds": self._ttl_seconds,
                "age_seconds": time.monotonic() - self._checked_at if self._checked else None
            }


# Singleton instance for the lncRNA-ChIP-seq overlaps MV
# This is the only MV currently used in the project
mv_cache = MaterializedViewCache(
    mv_name="mv_lncrna_chipseq_overlaps",
    ttl_seconds=300  # 5 minutes
)


def is_mv_missing_error(exc: Exception) -> bool:
    """
    Check if an exception indicates that the MV does not exist.

    Phase 9.24: Used to detect when MV was dropped during TTL window,
    allowing automatic fallback to join query.

    Args:
        exc: The exception to check

    Returns:
        True if the error indicates MV is missing/unavailable
    """
    error_msg = str(exc).lower()
    # SECURITY/Correctness: be strict to avoid masking unrelated DB errors.
    # Only treat errors as "MV missing" if the MV name is explicitly present.
    mv_name = "mv_lncrna_chipseq_overlaps"
    if mv_name not in error_msg:
        return False

    # PostgreSQL common error patterns for missing relation
    return (
        "does not exist" in error_msg
        or "undefined_table" in error_msg
        or ("relation" in error_msg and "does not exist" in error_msg)
    )


__all__ = ["MaterializedViewCache", "mv_cache", "is_mv_missing_error"]
