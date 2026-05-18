"""PDP (Product Detail Page) extractor for Amazon UAE.

Migrated from MT_Pricing_Run_Kit/src/extractor_pdp.py (BeautifulSoup) to
selectolax for faster parsing.

Amazon renders the same spec data in several different DOM layouts depending on
the listing template. We aggregate all of them and canonicalize via
``LABEL_TO_KEY``.

Public API::

    from app.services.matching.extractors.pdp_extractor import extract_pdp_specs

    specs = extract_pdp_specs(html)
    # → {"material_type": "Brass", "valve_type": "Ball Valve", ...}
"""

from __future__ import annotations

import re
from typing import Any

from selectolax.parser import HTMLParser, Node

# ---------------------------------------------------------------------------
# Canonical attribute keys → Amazon label aliases
# ---------------------------------------------------------------------------
ATTRIBUTE_LABELS: dict[str, list[str]] = {
    "material_type":            ["Material Type", "Material"],
    "valve_type":               ["Valve Type"],
    "maximum_pressure":         ["Maximum Pressure", "Maximum pressure", "Pressure Rating"],
    "pressure_rating":          ["Pressure Rating"],
    "thread_size":              ["Thread Size"],
    "thread_type":              ["Thread Type"],
    "inlet_connection":         ["Inlet Connection Type", "Inlet Connection"],
    "outlet_connection":        ["Outlet Connection Type", "Outlet Connection"],
    "connection_type":          ["Connection Type"],
    "exterior_finish":          ["Exterior Finish"],
    "number_of_ports":          ["Number of Ports"],
    "size":                     ["Size"],
    "specification_met":        ["Specification Met", "Compliance", "Certification"],
    "brand_name":               ["Brand Name", "Brand"],
    "manufacturer":             ["Manufacturer"],
    "model_number":             ["Model Number", "Item model number"],
    "manufacturer_part_number": ["Manufacturer Part Number"],
    "asin":                     ["ASIN"],
    "unit_count":               ["Unit Count"],
    "set_name":                 ["Set Name"],
    "number_of_items":          ["Number of Items", "Number of Pieces", "Item Package Quantity", "Quantity"],
    "package_dimensions":       ["Package Dimensions"],
    "item_weight":              ["Item Weight"],
    "date_first_available":     ["Date First Available"],
    "country_of_origin":        ["Country of Origin"],
}

# Reverse lookup: normalized label → canonical key (built once at import time).
LABEL_TO_KEY: dict[str, str] = {
    lbl.lower().strip(): key
    for key, labels in ATTRIBUTE_LABELS.items()
    for lbl in labels
}

_SECTION_KEYWORDS = frozenset(
    ["features", "specs", "item details", "measurements",
     "additional details", "user guide", "product details"]
)

_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")
_WHITESPACE_RE = re.compile(r"\s+")
_RTL_MARKS = str.maketrans("", "", "‎‏")

# Pack-size patterns in titles: "3 Pack", "Pack of 3", "Set of 3", "3 Pieces", "3 Pcs", etc.
_PACK_TITLE_RE = re.compile(
    r"(?:"
    r"(?:pack|set|lot|bundle|box)\s+of\s+(\d+)"   # "pack of 3", "set of 3"
    r"|(\d+)\s*[-–]?\s*(?:pack|pcs?|pieces?|units?|count|ct)\b"  # "3 pack", "3pcs", "3-piece"
    r"|(?:set|lot|bundle)\s+(\d+)\b"              # "set 3"
    r")",
    re.I,
)

# Regex patterns for extracting specs from product titles (no-JS fallback).
_MATERIAL_RE = re.compile(
    r"\b(brass|stainless[\s-]steel|carbon[\s-]steel|cast[\s-]iron|pvc|cpvc|bronze|ss316|ss304|316l|304)\b",
    re.I,
)
_VALVE_TYPE_RE = re.compile(
    r"\b(ball[\s-]valve|gate[\s-]valve|check[\s-]valve|butterfly[\s-]valve|"
    r"globe[\s-]valve|needle[\s-]valve|solenoid[\s-]valve|strainer|filter)\b",
    re.I,
)
_PN_RE = re.compile(r"\bPN\s*(\d+)\b", re.I)
_DN_RE = re.compile(r"\bDN\s*(\d+)\b", re.I)
_INCH_SIZE_RE = re.compile(r'(\d+/\d+|\d+(?:\.\d+)?)\s*[″"\']\s*(?:inch)?', re.I)
_THREAD_TYPE_RE = re.compile(r"\b(BSP|BSPP|BSPT|NPT|NPTF|G\d|Rc\d?)\b", re.I)
_CONNECTION_RE = re.compile(
    r"\b(threaded|flanged|welded|socket[\s-]weld|butt[\s-]weld|"
    r"compression|push[\s-]fit|inner[\s-]thread|outer[\s-]thread|male|female)\b",
    re.I,
)


def _extract_specs_from_title(title: str, raw_pairs: list[dict[str, str]]) -> None:
    """Regex fallback: parse key specs from a product title string.

    Used when Amazon serves a no-JS shell and spec tables are absent.
    Appends to ``raw_pairs`` so the main canonicalization loop can process them.
    """
    if not title:
        return

    m = _VALVE_TYPE_RE.search(title)
    if m:
        raw_pairs.append({"label": "Valve Type", "value": m.group(0).title()})

    m = _MATERIAL_RE.search(title)
    if m:
        raw_pairs.append({"label": "Material Type", "value": m.group(0).title()})

    m = _PN_RE.search(title)
    if m:
        raw_pairs.append({"label": "Maximum Pressure", "value": f"PN{m.group(1)}"})

    m = _DN_RE.search(title)
    if m:
        raw_pairs.append({"label": "Size", "value": f"DN{m.group(1)}"})
    elif (m := _INCH_SIZE_RE.search(title)):
        raw_pairs.append({"label": "Thread Size", "value": m.group(0).strip()})

    m = _THREAD_TYPE_RE.search(title)
    if m:
        raw_pairs.append({"label": "Thread Type", "value": m.group(0).upper()})

    m = _CONNECTION_RE.search(title)
    if m:
        raw_pairs.append({"label": "Connection Type", "value": m.group(0).title()})


def _clean(s: str | None) -> str:
    if not s:
        return ""
    s = s.translate(_RTL_MARKS)
    return _WHITESPACE_RE.sub(" ", s).strip()


def _normalize_label(lbl: str) -> str:
    return _clean(lbl).rstrip(":").lower()


def _node_text(node: Node) -> str:
    return _clean(node.text())


def extract_pdp_specs(html: str) -> dict[str, Any]:
    """Extract structured specs from an Amazon UAE PDP.

    Args:
        html: Raw HTML of the product detail page.

    Returns:
        Dict with canonical spec keys plus ``title_pdp``, ``canonical_url``,
        and ``raw_pairs`` (list of raw label/value pairs for debugging).
        Returns minimal dict on empty/bad HTML.
    """
    if not html:
        return {"title_pdp": "", "canonical_url": "", "raw_pairs": []}

    try:
        tree = HTMLParser(html)
    except Exception:  # noqa: BLE001
        return {"title_pdp": "", "canonical_url": "", "raw_pairs": []}

    raw_pairs: list[dict[str, str]] = []

    # ── 1) Tech spec tables (most common template) ──────────────────────────
    for tbl in tree.css("table[id*='productDetails_techSpec'], table[id*='productDetails_detailBullets']"):
        for tr in tbl.css("tr"):
            th = tr.css_first("th")
            td = tr.css_first("td")
            if th and td:
                raw_pairs.append({"label": _node_text(th), "value": _node_text(td)})

    # ── 2) Section-based key/value layout (Amazon UAE 2024+) ────────────────
    # Pattern: <div class="a-section"><h3>Features & Specs</h3>
    #              <div><span>Label</span><span>Value</span></div> ...
    for sec in tree.css("div.a-section, section.a-section"):
        header = sec.css_first("h2, h3, h4")
        if header is None:
            continue
        htxt = _node_text(header).lower()
        if not any(kw in htxt for kw in _SECTION_KEYWORDS):
            continue
        for row in sec.css("div, tr, li"):
            spans = [s for s in row.iter() if s.tag == "span" and s.parent == row]
            if len(spans) >= 2:
                lbl = _clean(spans[0].text())
                val = _clean(" ".join(s.text() for s in spans[1:]))
                if lbl and val and len(lbl) < 60 and len(val) < 200:
                    raw_pairs.append({"label": lbl, "value": val})

    # ── 3) detailBullets list  (e.g. "Label  ‏ : ‎ Value") ─────────────────
    for ul in tree.css(
        "#detailBullets_feature_div ul, #detailBulletsWrapper_feature_div ul"
    ):
        for li in ul.css("li"):
            span = li.css_first("span.a-list-item")
            if span is None:
                continue
            txt = _node_text(span)
            if ":" in txt:
                lbl, _, val = txt.partition(":")
                raw_pairs.append({"label": _clean(lbl), "value": _clean(val)})

    # ── 4) Title ─────────────────────────────────────────────────────────────
    title_node = tree.css_first("span#productTitle") or tree.css_first("h1")
    title = _node_text(title_node) if title_node else ""

    # ── 4b) Description / "About this item" bullets ───────────────────────────
    # Collected from feature-bullets and productDescription sections.
    # This text is the richest source for LLM spec extraction.
    desc_parts: list[str] = []
    for bullets_ul in tree.css(
        "#feature-bullets ul.a-unordered-list, "
        "#feature-bullets ul"
    ):
        for li in bullets_ul.css("li"):
            span = li.css_first("span.a-list-item")
            txt = _node_text(span) if span else _node_text(li)
            if txt and len(txt) > 8:
                desc_parts.append(txt)
        if desc_parts:
            break  # stop at first populated bullets section

    # Fallback: productDescription prose
    if not desc_parts:
        desc_node = tree.css_first("#productDescription p, #productDescription")
        if desc_node:
            txt = _node_text(desc_node)
            if txt:
                desc_parts.append(txt[:1000])

    description_text = " | ".join(desc_parts[:12])  # cap at 12 bullets ~1 KB

    # ── 4c) Customer reviews ──────────────────────────────────────────────────
    review_rating: str | None = None
    review_count: int | None = None
    rating_node = (
        tree.css_first("span[data-hook='rating-out-of-text']")
        or tree.css_first("#averageCustomerReviews span[data-hook='rating-out-of-text']")
        or tree.css_first("i.a-icon-star span.a-icon-alt")
    )
    if rating_node:
        rt = _clean(rating_node.text())
        _m_r = re.match(r"(\d+(?:[.,]\d+)?)", rt)
        if _m_r:
            review_rating = _m_r.group(1).replace(",", ".")
    count_node = (
        tree.css_first("span[data-hook='total-review-count']")
        or tree.css_first("#acrCustomerReviewText")
    )
    if count_node:
        ct = _clean(count_node.text())
        _m_c = re.search(r"([\d,]+)", ct)
        if _m_c:
            try:
                review_count = int(_m_c.group(1).replace(",", ""))
            except ValueError:
                pass

    # ── 4d) Delivery text ─────────────────────────────────────────────────────
    delivery_text_pdp: str | None = None
    for _del_sel in (
        "#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE",
        "#deliveryBlockMessage",
        "#delivery-message",
        "#ddmDeliveryMessage",
    ):
        _del_node = tree.css_first(_del_sel)
        if _del_node:
            _del_txt = _clean(_del_node.text())
            if _del_txt and len(_del_txt) > 5:
                delivery_text_pdp = _del_txt
                break

    # ── 5) Canonical URL → ASIN fallback ─────────────────────────────────────
    canonical_url = ""
    link = tree.css_first("link[rel='canonical']")
    if link:
        canonical_url = link.attributes.get("href", "")
        m = _ASIN_RE.search(canonical_url)
        if m:
            raw_pairs.append({"label": "ASIN", "value": m.group(1)})

    # ── 6) Meta tag fallback (no-JS pages served by curl_cffi) ───────────────
    # Amazon's JS-shell still carries <meta name="title"> and <meta name="description">
    # with the full product title. Use these when the DOM-rendered nodes are absent.
    meta_title = ""
    for meta in tree.css("meta[name='title'], meta[property='og:title']"):
        content = _clean(meta.attributes.get("content", ""))
        if content:
            meta_title = content
            break

    if not title and meta_title:
        title = meta_title

    # ── 7) Regex spec extraction from title (no-JS fallback) ─────────────────
    # When spec tables are absent, parse material / valve type / PN / DN / thread
    # from the product title (which is always present via meta or productTitle).
    # Exclude administrative-only keys (asin, model_number, etc.) from the check
    # so they don't suppress the regex parser on JS-shell pages.
    _ADMIN_KEYS = frozenset({
        "asin", "manufacturer_part_number", "model_number",
        "date_first_available", "package_dimensions", "unit_count",
    })
    has_product_specs = any(
        (key := LABEL_TO_KEY.get(_normalize_label(p["label"]))) and key not in _ADMIN_KEYS
        for p in raw_pairs
    )
    if not has_product_specs and title:
        _extract_specs_from_title(title, raw_pairs)

    # ── Canonicalize ──────────────────────────────────────────────────────────
    out: dict[str, Any] = {
        "title_pdp": title,
        "canonical_url": canonical_url,
        "raw_pairs": raw_pairs,
        "description_text": description_text,
    }
    for pair in raw_pairs:
        nl = _normalize_label(pair["label"])
        key = LABEL_TO_KEY.get(nl)
        if key:
            # Keep first-seen value; some pages duplicate sections.
            out.setdefault(key, pair["value"])

    if review_rating is not None:
        out["review_rating"] = review_rating
    if review_count is not None:
        out["review_count"] = review_count
    if delivery_text_pdp:
        out["delivery_text"] = delivery_text_pdp

    return out


def parse_pack_units(title: str, specs: dict[str, Any]) -> int | None:
    """Extract pack/set size from Amazon specs and title.

    Priority order:
    1. ``unit_count`` spec field  (e.g. "3.0 Count", "3 Count", "3")
    2. ``number_of_items`` spec  (e.g. "3", "3 Pieces")
    3. ``set_name`` spec          (e.g. "Set of 3")
    4. Title regex                (e.g. "3 Pack", "Pack of 3", "Set of 3")

    Returns None if no pack info found or pack size is 1 (individual item).
    """
    def _to_int(val: Any) -> int | None:
        if val is None:
            return None
        s = str(val).strip()
        # "3.0 Count" → "3", "Set of 3" → handled below, "3" → 3
        m = re.match(r"^(\d+)(?:[.,]\d+)?", s)
        return int(m.group(1)) if m else None

    def _set_of(val: Any) -> int | None:
        """Parse 'Set of N' or 'N pieces' patterns from a string value."""
        if val is None:
            return None
        s = str(val)
        m = re.search(r"(?:set|pack|lot|bundle)\s+of\s+(\d+)", s, re.I)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)\s*(?:pcs?|pieces?|units?|count|ct)\b", s, re.I)
        if m:
            return int(m.group(1))
        return _to_int(val)

    for field_name, parser in [
        ("unit_count", _to_int),
        ("number_of_items", _set_of),
        ("set_name", _set_of),
    ]:
        val = specs.get(field_name)
        if val is not None:
            n = parser(val)
            if n is not None and n > 1:
                return n

    if title:
        m = _PACK_TITLE_RE.search(title)
        if m:
            raw = m.group(1) or m.group(2) or m.group(3)
            if raw:
                n = int(raw)
                if n > 1:
                    return n

    return None
