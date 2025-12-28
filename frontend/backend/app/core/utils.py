"""
Shared utility functions for the application.
Consolidates common functionality to avoid code duplication.
"""
import re
from typing import Dict, Iterable, Iterator, List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Species IDs for conservation calculations
# Human=1, Chimp=2, Macaque=3, Marmoset=4
SPECIES_IDS: List[int] = [1, 2, 3, 4]


def escape_like_pattern(value: str, *, escape_char: str = "\\") -> str:
    """
    Escape user input for SQL LIKE/ILIKE pattern matching.

    Escapes:
    - '%' and '_' (wildcards)
    - the escape character itself

    Notes:
    - Callers MUST also provide the same `escape_char` to the SQLAlchemy
      `.like()` / `.ilike()` `escape=` parameter to ensure consistent behavior.
    """
    if len(escape_char) != 1:
        raise ValueError("escape_char must be a single character")

    # Escape the escape character first to avoid double-escaping.
    escaped = value.replace(escape_char, escape_char + escape_char)
    escaped = escaped.replace("%", escape_char + "%").replace("_", escape_char + "_")
    return escaped


_LOG_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")
_LOG_URL_USERINFO_RE = re.compile(r"(\b[a-zA-Z][a-zA-Z0-9+.\-]*://)([^@\s]+)@")
_LOG_KV_SECRET_RE = re.compile(
    r"(?i)(\b(?:password|passwd|pwd|secret|token|api_key|apikey|authorization|x-admin-api-key)\b\s*[:=]\s*)([^\s,;&]+)"
)
_LOG_BEARER_TOKEN_RE = re.compile(r"(?i)\bbearer\s+([a-z0-9\-._~+/]+=*)")


def _redact_url_userinfo(text: str) -> str:
    """
    Redact credentials in URL-like strings (e.g. postgresql://user:pass@host/db).

    Notes:
    - Best-effort: only targets common "scheme://userinfo@host" patterns.
    - We avoid parsing as URL to keep this utility lightweight and dependency-free.
    """

    def _replace(match: re.Match) -> str:
        scheme = match.group(1)
        userinfo = match.group(2)
        if ":" not in userinfo:
            return match.group(0)
        username, _password = userinfo.split(":", 1)
        return f"{scheme}{username}:***@"

    return _LOG_URL_USERINFO_RE.sub(_replace, text)


def _redact_kv_secrets(text: str) -> str:
    """Redact common key/value secret patterns (e.g. token=..., password: ...)."""

    def _replace(match: re.Match) -> str:
        return f"{match.group(1)}***"

    return _LOG_KV_SECRET_RE.sub(_replace, text)


def _redact_bearer_tokens(text: str) -> str:
    """Redact Authorization Bearer tokens when they appear inline in log messages."""

    def _replace(match: re.Match) -> str:
        return "Bearer ***"

    return _LOG_BEARER_TOKEN_RE.sub(_replace, text)


def _redact_secrets(text: str) -> str:
    # Order matters: redact structured patterns before truncation.
    text = _redact_url_userinfo(text)
    text = _redact_kv_secrets(text)
    text = _redact_bearer_tokens(text)
    return text


def sanitize_for_log(value: object, *, max_length: int = 200) -> str:
    """
    Sanitize potentially user-controlled values for safe logging.

    Security goals:
    - Prevent log injection / log forging (strip control characters like CR/LF/TAB/ESC).
    - Bound log size to avoid unbounded growth from large inputs.
    - Best-effort redact common secrets (tokens/passwords) and URL credentials.

    Args:
        value: Any value to be logged.
        max_length: Maximum length of the sanitized string (<=0 means no limit).

    Returns:
        A sanitized string safe for log lines.
    """
    if value is None:
        return ""

    text = str(value)
    text = _redact_secrets(text)
    text = _LOG_CONTROL_CHARS_RE.sub(" ", text).strip()

    if max_length <= 0 or len(text) <= max_length:
        return text

    suffix = "...[TRUNC]"
    if max_length <= len(suffix):
        return text[:max_length]
    return text[: max_length - len(suffix)] + suffix


def _unique_preserve_order(values: Iterable[int]) -> List[int]:
    """Deduplicate values while preserving the first-seen order."""
    seen: Set[int] = set()
    unique: List[int] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        unique.append(v)
    return unique


def _iter_chunks(values: List[int], *, chunk_size: int) -> Iterator[List[int]]:
    """Yield fixed-size chunks from a list (last chunk may be smaller)."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    for idx in range(0, len(values), chunk_size):
        yield values[idx : idx + chunk_size]


def compute_conservation_map(core_ids: List[int], db: "Session") -> Dict[int, tuple]:
    """
    Compute conservation data for a list of core_ids.

    This function determines the cross-species conservation status of genes
    by checking which species have the gene present.

    Args:
        core_ids: List of core gene IDs to check conservation for
        db: Database session

    Returns:
        Dict mapping core_id to (conservation_label, conservation_count)
        - conservation_label: Binary string like "1110" (present in human, chimp, macaque)
        - conservation_count: Number of species where the gene is present

    Example:
        >>> conservation_map = compute_conservation_map([123, 456], db)
        >>> conservation_map[123]
        ('1111', 4)  # Present in all 4 species
    """
    # Import here to avoid circular imports
    from app.models import Gene

    if not core_ids:
        return {}

    # Deduplicate while preserving order to reduce IN-clause size.
    unique_core_ids = _unique_preserve_order(core_ids)

    # Build a map: core_id -> set of species_ids
    species_map: Dict[int, Set[int]] = {}
    # SECURITY/PERF: chunk large IN lists to avoid DB/driver parameter limits and reduce worst-case parsing cost.
    for chunk in _iter_chunks(unique_core_ids, chunk_size=1000):
        rows = (
            db.query(Gene.core_id, Gene.species_id)
            .filter(Gene.core_id.in_(chunk))
            .distinct()
            .all()
        )
        for core_id, species_id in rows:
            if core_id not in species_map:
                species_map[core_id] = set()
            species_map[core_id].add(species_id)

    # Convert to conservation labels
    result: Dict[int, tuple] = {}
    for core_id in unique_core_ids:
        present_species = species_map.get(core_id, set())
        conservation_label = "".join(
            "1" if sid in present_species else "0"
            for sid in SPECIES_IDS
        )
        conservation_count = len(present_species)
        result[core_id] = (conservation_label, conservation_count)

    return result
