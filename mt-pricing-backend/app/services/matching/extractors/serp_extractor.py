"""SERP extractor for Amazon UAE search-result pages.

Migrated from MT_Pricing_Run_Kit/src/extractor_v51.py (BeautifulSoup) to
selectolax for significantly faster parse times on large SERP pages.

Public API::

    from app.services.matching.extractors.serp_extractor import extract_top_results

    results = extract_top_results(html, top_n=3)
    # → [{"asin": ..., "title": ..., "price_aed": ..., "image_url": ..., "url": ...}, ...]
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from selectolax.parser import HTMLParser, Node

_BASE_URL = "https://www.amazon.ae"

# Sponsored cards contain a visually hidden label with this text.
_SPONSORED_RE = re.compile(r"Sponsored", re.IGNORECASE)

# Amazon price is in a visually-hidden <span class="a-offscreen"> like "AED 145.50"
_PRICE_RE = re.compile(r"[\d,]+\.?\d*")


def _is_sponsored(node: Node) -> bool:
    """True if any descendant span text matches 'Sponsored'."""
    for span in node.css("span"):
        txt = span.text(strip=True)
        if _SPONSORED_RE.search(txt):
            return True
    return False


def _extract_asin(node: Node) -> str | None:
    asin = node.attributes.get("data-asin", "").strip()
    return asin or None


def _extract_title(node: Node) -> str:
    h2 = node.css_first("h2")
    if h2 is None:
        return ""
    span = h2.css_first("span")
    if span:
        return span.text(strip=True)
    return h2.text(strip=True)


def _extract_price(node: Node) -> Decimal | None:
    """Extract price from the visually-hidden a-offscreen span."""
    offscreen = node.css_first("span.a-offscreen")
    if offscreen is None:
        return None
    txt = offscreen.text(strip=True).replace(",", "")
    m = _PRICE_RE.search(txt)
    if m:
        try:
            return Decimal(m.group(0))
        except InvalidOperation:
            pass
    return None


def _extract_image(node: Node) -> str:
    img = node.css_first("img.s-image") or node.css_first("img")
    if img is None:
        return ""
    return img.attributes.get("src", "")


def _extract_url(node: Node) -> str:
    h2 = node.css_first("h2")
    if h2:
        a = h2.css_first("a")
        if a:
            href = a.attributes.get("href", "")
            if href:
                return (_BASE_URL + href) if href.startswith("/") else href
    a = node.css_first("a.s-link-style") or node.css_first("a")
    if a:
        href = a.attributes.get("href", "")
        if href:
            return (_BASE_URL + href) if href.startswith("/") else href
    return ""


def extract_top_results(html: str, top_n: int = 3) -> list[dict[str, Any]]:
    """Extract top N non-sponsored products from an Amazon UAE SERP page.

    Args:
        html: Raw HTML of the Amazon search-results page.
        top_n: Maximum number of results to return.

    Returns:
        List of dicts with keys: ``asin``, ``title``, ``price_aed`` (Decimal
        or None), ``image_url``, ``url``. Empty list on bad/empty HTML.
    """
    if not html:
        return []

    try:
        tree = HTMLParser(html)
    except Exception:
        return []

    # Primary selector: data-component-type is the stable Amazon hook.
    cards = tree.css("div[data-component-type='s-search-result']")

    # Fallback: any div with data-asin (older layouts).
    if not cards:
        cards = [
            n for n in tree.css("div[data-asin]") if (n.attributes.get("data-asin") or "").strip()
        ]

    results: list[dict[str, Any]] = []
    for card in cards:
        if _is_sponsored(card):
            continue

        asin = _extract_asin(card)
        if not asin:
            # Skip incomplete fragments with no ASIN at all.
            continue

        price_aed = _extract_price(card)
        # Industrial products on Amazon often have no visible SERP price
        # (B2B listings, "click for price", sold-by-weight). Include them —
        # price_aed=None is valid and will be filled from the PDP if available.

        results.append(
            {
                "asin": asin,
                "title": _extract_title(card),
                "price_aed": price_aed,
                "image_url": _extract_image(card),
                "url": _extract_url(card),
            }
        )

        if len(results) >= top_n:
            break

    return results
