"""
Shared utility functions for the application.
Consolidates common functionality to avoid code duplication.
"""
import re


def escape_like_pattern(value: str) -> str:
    """Escape LIKE pattern special characters (%, _, \\)"""
    return re.sub(r'([%_\\])', r'\\\1', value)
