from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedProduct:
    """Producto parseado de una fila Excel, listo para persistencia."""

    sku: str
    scalars: dict[str, Any] = field(default_factory=dict)
    jsonb: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {"dimensions": {}, "packaging": {}, "specs": {}}
    )
    translations: dict[str, str] = field(default_factory=dict)
    certifications: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_error_row(self) -> bool:
        return not self.sku or not self.sku.strip()

    @property
    def has_translations(self) -> bool:
        return bool(self.translations)

    @property
    def has_certifications(self) -> bool:
        return bool(self.certifications)
