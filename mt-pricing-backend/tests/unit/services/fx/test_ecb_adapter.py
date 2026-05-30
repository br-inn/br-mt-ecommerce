from decimal import Decimal

import pytest

from app.services.fx.ecb_adapter import EcbFxAdapter

_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
 xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
 <Cube><Cube time="2026-05-30">
  <Cube currency="USD" rate="1.0856"/>
  <Cube currency="GBP" rate="0.8512"/>
 </Cube></Cube></gesmes:Envelope>"""


@pytest.mark.asyncio
async def test_fetch_eur_aed_applies_peg(monkeypatch) -> None:  # noqa: ANN001
    async def _fake_get(self, url):  # noqa: ANN001, ANN202
        class R:
            content = _XML

            def raise_for_status(self) -> None: ...

        return R()

    monkeypatch.setattr("httpx.AsyncClient.get", _fake_get)
    q = await EcbFxAdapter().fetch_eur_aed()
    assert q.eur_usd == Decimal("1.0856")
    assert q.eur_aed == (Decimal("1.0856") * Decimal("3.6725"))
    assert q.ecb_date == "2026-05-30"


@pytest.mark.asyncio
async def test_fetch_raises_when_usd_missing(monkeypatch) -> None:  # noqa: ANN001
    bad = _XML.replace(b'currency="USD"', b'currency="ZZZ"')

    async def _fake_get(self, url):  # noqa: ANN001, ANN202
        class R:
            content = bad

            def raise_for_status(self) -> None: ...

        return R()

    monkeypatch.setattr("httpx.AsyncClient.get", _fake_get)
    with pytest.raises(ValueError, match="USD"):
        await EcbFxAdapter().fetch_eur_aed()
