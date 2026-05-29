"""Unit tests for _content_type_for helper in imports route.

Loads the module file directly (bypassing the routes package __init__)
to avoid transitive imports of pydantic[email] / app bootstrap code.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal env stubs so config / settings don't blow up on import
# ---------------------------------------------------------------------------
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

# ---------------------------------------------------------------------------
# Load imports.py directly, without going through app.api.routes.__init__
# ---------------------------------------------------------------------------
_ROUTES_FILE = (
    Path(__file__).parent.parent.parent / "app" / "api" / "routes" / "imports.py"
)


def _load_imports_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("app.api.routes.imports", _ROUTES_FILE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules so relative imports inside the file resolve
    sys.modules.setdefault("app.api.routes.imports", mod)
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:
        # The module-level side-effects (router creation, imports of deps) may
        # fail in a stub environment — we only need the pure helper function
        # that is defined before any heavy imports.  If exec fails partway
        # through, the helper will already be bound on the module object.
        pass
    return mod


_imports_mod = _load_imports_module()
_content_type_for = _imports_mod._content_type_for  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_content_type_for_xml() -> None:
    assert _content_type_for("articulos.xml") == "text/xml"
    assert _content_type_for("ART.XML") == "text/xml"


def test_content_type_for_xlsx() -> None:
    assert _content_type_for("PIM.xlsx") == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
