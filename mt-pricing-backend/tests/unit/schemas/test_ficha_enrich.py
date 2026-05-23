from app.schemas.ficha_enrich import (
    ExtractedScalars,
    ExtractedSpecs,
    FichaEnrichApplyRequest,
    FichaExtractionResult,
)


def test_extracted_scalars_partial():
    s = ExtractedScalars(pn="30", temp_min_c=-20, temp_max_c=120)
    assert s.pn == "30"
    assert s.temp_min_c == -20
    d = s.model_dump(exclude_none=True)
    assert "family" not in d


def test_ficha_extraction_result_defaults():
    r = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
    )
    assert r.materials == []
    assert r.dimensions == []
    assert r.page_classifications == []
    assert r.extracted_assets == []
    assert r.pt_curve_points == []
    assert r.confidence == 0.0


def test_apply_request_defaults():
    req = FichaEnrichApplyRequest(
        extraction=FichaExtractionResult(
            scalars=ExtractedScalars(),
            specs=ExtractedSpecs(),
        ),
        apply_to_skus=[],
    )
    assert req.apply_scalars is True
    assert req.apply_translations is False
    assert req.apply_assets is False
    assert req.apply_pt_curve is False
