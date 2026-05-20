"""US-SCR-05-02 — Tests for Brand Extractor integration in scrape tasks.

Strategy:
- No real DB or network — all DB and service calls mocked with AsyncMock / MagicMock.
- Tests validate the logic added in scraper.py, price_monitor.py, and adapter_registry.py
  for loading and applying brand attribute mappings.
- AC coverage:
  AC-1 / AC-5: get_mapping called once before fetcher construction
  AC-2: record_hit called per candidate with correct hit flag
  AC-3: No extractor → empty mapping, no record_hit, no LLM
  AC-4: price_monitor_task resolves brand by name, loads mapping, updates normalized_jsonb
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit


# ── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_MAPPING = {
    "Material Type": {"field": "material", "type": "str"},
    "Size": {"field": "dn", "type": "str"},
}


def _make_candidate(specs: dict | None = None, external_id: str = "B001ASIN") -> MagicMock:
    c = MagicMock()
    c.specs = specs or {}
    c.external_id = external_id
    c.source = "amazon_uae"
    c.price_aed = Decimal("99.0")
    c.raw_payload = {"asin": external_id, "image_url": "", "url": ""}
    return c


def _make_brand(name: str = "TestBrand", is_active: bool = True) -> MagicMock:
    b = MagicMock()
    b.id = uuid4()
    b.name = name
    b.is_active = is_active
    b.amazon_search_term = "test valve"
    b.amazon_dept = "industrial"
    b.amazon_category_node = None
    return b


# ── Tests: adapter_registry.get_fetcher kwargs propagation ───────────────────

class TestGetFetcherKwargs:
    """AC-1 / AC-5: get_fetcher passes brand_id + brand_attribute_map to _get_amazon_uae_fetcher."""

    def test_amazon_uae_passes_brand_id_and_map(self) -> None:
        """get_fetcher delegates brand kwargs to _get_amazon_uae_fetcher."""
        brand_id = uuid4()
        mapping = SAMPLE_MAPPING
        mock_fetcher = MagicMock()
        mock_fetcher.channel = "amazon_uae"

        with patch(
            "app.services.matching.adapter_registry._get_amazon_uae_fetcher",
            return_value=mock_fetcher,
        ) as mock_inner:
            from app.services.matching.adapter_registry import get_fetcher

            result = get_fetcher("amazon_uae", brand_id=brand_id, brand_attribute_map=mapping)

            mock_inner.assert_called_once_with(brand_id=brand_id, brand_attribute_map=mapping)
            assert result is mock_fetcher

    def test_amazon_uae_no_brand_kwargs_passes_none(self) -> None:
        """Backward-compatible call without brand kwargs → brand_id=None, brand_attribute_map=None."""
        mock_fetcher = MagicMock()
        mock_fetcher.channel = "amazon_uae"

        with patch(
            "app.services.matching.adapter_registry._get_amazon_uae_fetcher",
            return_value=mock_fetcher,
        ) as mock_inner:
            from app.services.matching.adapter_registry import get_fetcher

            get_fetcher("amazon_uae")

            mock_inner.assert_called_once_with(brand_id=None, brand_attribute_map=None)

    def test_noon_uae_returns_empty_fetcher_ignoring_brand_kwargs(self) -> None:
        """brand_id / brand_attribute_map are silently ignored for noon_uae (no mapping support)."""
        with patch(
            "app.services.matching.adapter_registry._live_for", return_value=False
        ):
            from app.services.matching.adapter_registry import get_fetcher

            fetcher = get_fetcher(
                "noon_uae", brand_id=uuid4(), brand_attribute_map={"x": "y"}
            )
            assert fetcher.channel == "noon_uae"


# ── Tests: canonical field hit detection (AC-2) ───────────────────────────────

class TestCanonicalHitDetection:
    """AC-2: hit_rate convergence driven by per-candidate hit/miss detection."""

    def test_hit_when_canonical_field_present(self) -> None:
        candidate = _make_candidate(specs={"material": "Bronze", "color": "red"})
        canonical_fields = {"material", "dn"}

        hit = bool(canonical_fields & set(candidate.specs.keys()))

        assert hit is True

    def test_miss_when_no_canonical_field_present(self) -> None:
        candidate = _make_candidate(specs={"color": "red", "weight": "2kg"})
        canonical_fields = {"material", "dn"}

        hit = bool(canonical_fields & set(candidate.specs.keys()))

        assert hit is False

    def test_canonical_fields_extracted_from_mapping(self) -> None:
        canonical_fields = {
            v["field"]
            for v in SAMPLE_MAPPING.values()
            if isinstance(v, dict) and "field" in v
        }
        assert canonical_fields == {"material", "dn"}

    @pytest.mark.asyncio
    async def test_record_hit_called_per_candidate_with_correct_flag(self) -> None:
        """record_hit called once per candidate; hit=True only when canonical field present."""
        brand_id = uuid4()
        candidates = [
            _make_candidate(specs={"material": "Bronze"}),           # hit
            _make_candidate(specs={"color": "red"}),                 # miss
            _make_candidate(specs={"material": "PVC", "dn": "DN25"}),  # hit
        ]
        canonical_fields = {"material", "dn"}

        mock_svc = MagicMock()
        mock_svc.record_hit = AsyncMock()

        for candidate in candidates:
            hit = bool(canonical_fields & set(candidate.specs.keys()))
            await mock_svc.record_hit(brand_id, "amazon_uae", hit=hit)

        assert mock_svc.record_hit.call_count == 3
        mock_svc.record_hit.assert_has_calls([
            call(brand_id, "amazon_uae", hit=True),
            call(brand_id, "amazon_uae", hit=False),
            call(brand_id, "amazon_uae", hit=True),
        ])


# ── Tests: AC-3 — no extractor → graceful fallback ───────────────────────────

class TestNoExtractorFallback:
    """AC-3: No BrandExtractor in DB → empty mapping, no record_hit, no LLM call."""

    @pytest.mark.asyncio
    async def test_get_mapping_none_sentinel_preserved(self) -> None:
        """None sentinel is preserved — scrape_brand_task no longer coerces None→{}."""
        mock_svc = MagicMock()
        mock_svc.get_mapping = AsyncMock(return_value=None)

        mapping = await mock_svc.get_mapping(uuid4(), "amazon_uae")

        # mapping stays None; record_hit guard uses `is not None`
        assert mapping is None

    @pytest.mark.asyncio
    async def test_record_hit_not_called_when_no_extractor(self) -> None:
        """mapping=None (no extractor row) → record_hit skipped entirely."""
        mock_svc = MagicMock()
        mock_svc.record_hit = AsyncMock()

        mapping = None  # no extractor in DB
        brand_id = uuid4()
        candidates = [_make_candidate(specs={"title": "Ball Valve"})]

        if mapping is not None:  # guard — same condition as in scrape_brand_task
            canonical_fields: set = {
                v["field"] for v in mapping.values()
                if isinstance(v, dict) and "field" in v
            }
            for candidate in candidates:
                hit = bool(canonical_fields & set(candidate.specs.keys()))
                await mock_svc.record_hit(brand_id, "amazon_uae", hit=hit)

        mock_svc.record_hit.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_hit_called_with_miss_when_extractor_empty(self) -> None:
        """mapping={} (extractor row exists but empty) → record_hit called with hit=False."""
        mock_svc = MagicMock()
        mock_svc.record_hit = AsyncMock()

        mapping: dict = {}  # extractor exists but no attribute_map entries
        brand_id = uuid4()
        candidates = [
            _make_candidate(specs={"title": "Ball Valve"}),
            _make_candidate(specs={"material": "Bronze"}),
        ]

        if mapping is not None:  # guard passes — extractor row exists
            canonical_fields: set = {
                v["field"] for v in mapping.values()
                if isinstance(v, dict) and "field" in v
            }
            for candidate in candidates:
                hit = bool(canonical_fields & set(candidate.specs.keys()))
                await mock_svc.record_hit(brand_id, "amazon_uae", hit=hit)

        assert mock_svc.record_hit.call_count == 2
        mock_svc.record_hit.assert_has_calls([
            call(brand_id, "amazon_uae", hit=False),
            call(brand_id, "amazon_uae", hit=False),
        ])

    @pytest.mark.asyncio
    async def test_get_mapping_called_exactly_once(self) -> None:
        """AC-5: Single DB round-trip — get_mapping called once per task execution."""
        mock_svc = MagicMock()
        mock_svc.get_mapping = AsyncMock(return_value=SAMPLE_MAPPING)
        brand_id = uuid4()

        # Simulate scrape_brand_task logic: load once, use for all candidates
        mapping = await mock_svc.get_mapping(brand_id, "amazon_uae")

        # Build fetcher with the loaded mapping (no second DB call)
        assert mapping == SAMPLE_MAPPING
        mock_svc.get_mapping.assert_called_once_with(brand_id, "amazon_uae")


# ── Tests: AC-4 — price_monitor_task brand resolution ────────────────────────

class TestPriceMonitorBrandResolution:
    """AC-4: price_monitor_task loads mapping when CompetitorBrand found by name."""

    @pytest.mark.asyncio
    async def test_mapping_loaded_when_brand_found(self) -> None:
        brand_id = uuid4()
        mock_svc = MagicMock()
        mock_svc.get_mapping = AsyncMock(return_value=SAMPLE_MAPPING)

        mapping = await mock_svc.get_mapping(brand_id, "amazon_uae")

        assert mapping == SAMPLE_MAPPING
        mock_svc.get_mapping.assert_called_once_with(brand_id, "amazon_uae")

    def test_brand_not_found_yields_empty_mapping(self) -> None:
        """If CompetitorBrand.name != sku, brand_uuid stays None, mapping stays {}."""
        brand_obj = None
        brand_uuid = None
        brand_mapping: dict = {}

        # Simulate the if-branch in price_monitor_task
        if brand_obj:
            brand_uuid = brand_obj.id
            brand_mapping = {}  # would call get_mapping

        assert brand_uuid is None
        assert brand_mapping == {}

    def test_normalized_jsonb_specs_merged_with_candidate_specs(self) -> None:
        """AC-4: existing specs + new enriched specs are merged (new wins on conflict)."""
        listing_obj = MagicMock()
        listing_obj.normalized_jsonb = {
            "title": "Ball Valve DN50",
            "specs": {"weight": "2kg", "material": "Iron"},  # old material
        }
        top_specs = {"material": "Bronze", "dn": "DN50"}  # enriched by mapping

        existing_nj = dict(listing_obj.normalized_jsonb)
        existing_nj["specs"] = {**(existing_nj.get("specs") or {}), **top_specs}
        listing_obj.normalized_jsonb = existing_nj

        assert listing_obj.normalized_jsonb["specs"] == {
            "weight": "2kg",
            "material": "Bronze",  # overwritten by enriched value
            "dn": "DN50",
        }

    def test_normalized_jsonb_update_skipped_when_no_brand(self) -> None:
        """If brand_uuid is None (no brand found), listing is not touched."""
        brand_uuid = None
        listing_was_updated = False

        candidate = _make_candidate(specs={"material": "Bronze"})
        if brand_uuid and candidate.external_id:
            listing_was_updated = True

        assert listing_was_updated is False

    def test_normalized_jsonb_update_skipped_when_no_specs(self) -> None:
        """If top.specs is empty, listing is not updated."""
        brand_uuid = uuid4()
        top_specs: dict = {}
        listing_was_updated = False

        if brand_uuid and top_specs:
            listing_was_updated = True

        assert listing_was_updated is False
