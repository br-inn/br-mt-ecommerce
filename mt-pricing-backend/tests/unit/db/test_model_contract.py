"""Documentación ejecutable del contrato del modelo Product.

Verifica invariantes de Python que deben mantenerse siempre:
- name_en y active son hybrid_property sin setter — read-only a nivel Python.
- lifecycle_status acepta sus valores definidos.
- active se deriva de lifecycle_status, no es un campo independiente.

Sin DB (unit) — fallan en tiempo de ejecución Python si alguien añade un setter
accidentalmente o intenta escribir campos prohibidos.
"""

from __future__ import annotations

import pytest

from app.db.models.product import Product


def test_product_name_en_is_read_only_hybrid() -> None:
    """name_en no tiene setter — intentar asignarlo lanza AttributeError."""
    p = Product(sku="CONTRACT-001", family="valves_ball")
    with pytest.raises(AttributeError):
        p.name_en = "Should fail"  # type: ignore[misc]


def test_product_active_is_read_only_hybrid() -> None:
    """active no tiene setter — cambiar el valor requires lifecycle_status."""
    p = Product(sku="CONTRACT-002", family="valves_ball")
    with pytest.raises(AttributeError):
        p.active = True  # type: ignore[misc]


def test_product_constructor_rejects_name_en() -> None:
    """Product(name_en=...) lanza AttributeError — documenta el bug silencioso."""
    with pytest.raises(AttributeError):
        Product(sku="CONTRACT-003", family="valves_ball", name_en="Foo")  # type: ignore[call-arg]


def test_product_constructor_rejects_active() -> None:
    """Product(active=...) lanza AttributeError — usa lifecycle_status en su lugar."""
    with pytest.raises(AttributeError):
        Product(sku="CONTRACT-004", family="valves_ball", active=True)  # type: ignore[call-arg]


def test_product_active_derives_from_lifecycle_status() -> None:
    """active es True solo cuando lifecycle_status == 'active'."""
    active_p = Product(sku="CONTRACT-ACT", family="valves_ball", lifecycle_status="active")
    assert active_p.active is True

    for inactive_status in ("deprecated", "draft", "blocked"):
        p = Product(
            sku=f"CONTRACT-{inactive_status}",
            family="valves_ball",
            lifecycle_status=inactive_status,
        )
        assert p.active is False, f"lifecycle_status='{inactive_status}' should give active=False"


def test_product_lifecycle_status_valid_values() -> None:
    """Documenta los valores válidos de lifecycle_status (sin DB — validación es PG CHECK)."""
    valid = ("active", "deprecated", "draft", "blocked", "in_review", "replaced", "discontinued")
    for status in valid:
        p = Product(sku=f"CONTRACT-LS-{status}", family="valves_ball", lifecycle_status=status)
        assert p.lifecycle_status == status


def test_product_erp_name_is_writable() -> None:
    """erp_name es un campo regular — sustituye al antiguo name_en para escritura."""
    p = Product(sku="CONTRACT-ERP", family="valves_ball", erp_name="ERP Name")
    assert p.erp_name == "ERP Name"
    p.erp_name = "Updated"
    assert p.erp_name == "Updated"
