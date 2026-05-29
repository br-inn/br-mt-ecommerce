from decimal import Decimal

from app.services.procurement.invoice_parser import _parse_invoice_text

SAMPLE = [
    "INVOICE",
    "2026002035 29/01/2026",
    "Page : 1 of 34",
    "Code Description Quantity Unit price Discount Amount",
    "Order No. : PE2545255 Customer reference : FONDO DE CUBA",
    "INCOTERMS : DAP",
    '310912015 THREE PIECES TANK BOTTOM VALVE AISI 316 1/2" 79 34.804 2,749.516',
    "Intrastat code : 84818081",
    "422401 CHROME HANDLE FOR LONG NECK VALVES 500 1.477 738.50",
    "Intrastat code : 84819000",
]


def test_parse_extracts_invoice_number_and_incoterm():
    r = _parse_invoice_text(SAMPLE)
    assert r.invoice_number == "2026002035"
    assert r.incoterms == "DAP"
    assert "PE2545255" in r.order_refs


def test_parse_extracts_item_lines_with_unit_price_and_hs():
    r = _parse_invoice_text(SAMPLE)
    by_code = {ln.code: ln for ln in r.lines}
    assert by_code["310912015"].quantity == Decimal("79")
    assert by_code["310912015"].unit_price == Decimal("34.804")
    assert by_code["310912015"].intrastat_code == "84818081"
    assert by_code["422401"].unit_price == Decimal("1.477")
    assert by_code["422401"].intrastat_code == "84819000"


def test_parse_ignores_non_item_lines():
    r = _parse_invoice_text(SAMPLE)
    assert len(r.lines) == 2
