"""Smoke test — verify the /imports/invoice route is registered (F0.5)."""

from __future__ import annotations


def test_invoice_route_registered() -> None:
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert any(p.endswith("/imports/invoice") for p in paths)
