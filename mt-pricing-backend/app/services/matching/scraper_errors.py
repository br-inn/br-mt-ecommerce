"""Shared scraper exception types.

Centralised here so that all scraper tiers (Tier 1 curl_cffi, Tier 2
patchright, etc.) raise the same exception class and the adapter_registry
can catch a single type regardless of which tier is active.
"""

from __future__ import annotations


class ScraperBlockedError(Exception):
    """Raised when a live scraper is blocked by the target (CAPTCHA or 403).

    The adapter_registry catches this to trigger an automatic fallback to the
    next tier in the chain (or the stub fetcher as last resort).
    """
