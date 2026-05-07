"""SchemaMapper — Postgres rows → graph operations.

Mapea las entidades core del PIM a nodos y edges del knowledge graph.

Tabla de mapeo (Fase 1 scaffold — extensible):

| entity_type        | Nodo principal              | Edges generados                                 |
|--------------------|-----------------------------|--------------------------------------------------|
| product            | (:Product {sku})            | (:Product)-[:MADE_OF]->(:Material) si payload tiene `material`        |
|                    |                             | (:Product)-[:BRANDED]->(:Manufacturer) si `brand`                        |
|                    |                             | (:Product)-[:BELONGS_TO]->(:Family) si `family`                          |
| supplier           | (:Supplier {code})          | (:Supplier)-[:USES_CURRENCY]->(:Currency) si `contract_currency`         |
| cost               | (:Cost {id})                | (:Product)-[:HAS_COST]->(:Cost), (:Cost)-[:FROM_SUPPLIER]->(:Supplier)   |
| match_candidate    | (:MatchCandidate {id})      | (:Product)-[:HAS_MATCH]->(:MatchCandidate)                              |
|                    |                             | (:MatchCandidate)-[:LISTED_ON]->(:Channel)                              |

Diseño:
- Función pura: input ``(entity_type, action, payload)`` → output
  ``(nodes, edges)``. NO interactúa con BD ni con el graph store.
- ``action='delete'`` no produce edges; el caller dispara
  ``delete_subgraph`` sobre el nodo principal y los edges incidentes
  desaparecen automáticamente.
- Si el ``entity_type`` no está soportado, devuelve ``([], [])`` y
  registra warning vía structlog (no rompe el dispatcher).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.services.graphrag.ports import GraphEdge, GraphNode

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Etiquetas canónicas — fuente de verdad para queries Cypher futuros.
# ---------------------------------------------------------------------------
LABEL_PRODUCT = "Product"
LABEL_SUPPLIER = "Supplier"
LABEL_COST = "Cost"
LABEL_MATCH_CANDIDATE = "MatchCandidate"
LABEL_MANUFACTURER = "Manufacturer"
LABEL_MATERIAL = "Material"
LABEL_FAMILY = "Family"
LABEL_CHANNEL = "Channel"
LABEL_CURRENCY = "Currency"

EDGE_MADE_OF = "MADE_OF"
EDGE_BRANDED = "BRANDED"
EDGE_BELONGS_TO = "BELONGS_TO"
EDGE_USES_CURRENCY = "USES_CURRENCY"
EDGE_HAS_COST = "HAS_COST"
EDGE_FROM_SUPPLIER = "FROM_SUPPLIER"
EDGE_HAS_MATCH = "HAS_MATCH"
EDGE_LISTED_ON = "LISTED_ON"


class SchemaMapper:
    """Traductor stateless. Métodos clase para ser triviales de testear."""

    # ------------------------------------------------------------------ public
    @classmethod
    def map_event(
        cls,
        *,
        entity_type: str,
        action: str,
        payload: dict[str, Any],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Devuelve `(nodes, edges)` que el dispatcher debe MERGE-ear.

        Para ``action='delete'`` el dispatcher debe llamar
        ``delete_subgraph(primary_label, primary_pk)``; este método devuelve
        ``([], [])`` en ese caso (no hay nodos a hacer merge).
        """
        if action == "delete":
            return [], []

        method = getattr(cls, f"_map_{entity_type}", None)
        if method is None:
            logger.warning(
                "graphrag.schema_mapper.unsupported_entity",
                entity_type=entity_type,
                action=action,
            )
            return [], []
        nodes, edges = method(payload)
        return nodes, edges

    @classmethod
    def primary_label(cls, entity_type: str) -> str | None:
        """Etiqueta del nodo principal para `delete_subgraph`."""
        return {
            "product": LABEL_PRODUCT,
            "supplier": LABEL_SUPPLIER,
            "cost": LABEL_COST,
            "match_candidate": LABEL_MATCH_CANDIDATE,
        }.get(entity_type)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _str_or_none(v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @staticmethod
    def _filter_props(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
        """Subselección de claves serializables — evita meter blobs grandes."""
        out: dict[str, Any] = {}
        for k in keys:
            v = payload.get(k)
            if v is None:
                continue
            # Pasamos los Decimal/UUID/datetime a str para JSON-safety.
            if isinstance(v, (str, int, float, bool, list, dict)):
                out[k] = v
            else:
                out[k] = str(v)
        return out

    # ------------------------------------------------------------------ mappers
    @classmethod
    def _map_product(
        cls, payload: dict[str, Any]
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        sku = cls._str_or_none(payload.get("sku"))
        if sku is None:
            return [], []

        nodes: list[GraphNode] = [
            GraphNode(
                label=LABEL_PRODUCT,
                primary_key=sku,
                properties=cls._filter_props(
                    payload,
                    [
                        "name_en",
                        "family",
                        "subfamily",
                        "type",
                        "material",
                        "dn",
                        "pn",
                        "connection",
                        "brand",
                        "active",
                    ],
                ),
            )
        ]
        edges: list[GraphEdge] = []

        material = cls._str_or_none(payload.get("material"))
        if material:
            edges.append(
                GraphEdge(
                    src_label=LABEL_PRODUCT,
                    src_pk=sku,
                    type=EDGE_MADE_OF,
                    dst_label=LABEL_MATERIAL,
                    dst_pk=material,
                )
            )

        brand = cls._str_or_none(payload.get("brand"))
        if brand:
            edges.append(
                GraphEdge(
                    src_label=LABEL_PRODUCT,
                    src_pk=sku,
                    type=EDGE_BRANDED,
                    dst_label=LABEL_MANUFACTURER,
                    dst_pk=brand,
                )
            )

        family = cls._str_or_none(payload.get("family"))
        if family:
            edges.append(
                GraphEdge(
                    src_label=LABEL_PRODUCT,
                    src_pk=sku,
                    type=EDGE_BELONGS_TO,
                    dst_label=LABEL_FAMILY,
                    dst_pk=family,
                )
            )
        return nodes, edges

    @classmethod
    def _map_supplier(
        cls, payload: dict[str, Any]
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        code = cls._str_or_none(payload.get("code"))
        if code is None:
            return [], []
        nodes: list[GraphNode] = [
            GraphNode(
                label=LABEL_SUPPLIER,
                primary_key=code,
                properties=cls._filter_props(
                    payload,
                    [
                        "name",
                        "contract_currency",
                        "lead_time_days",
                        "active",
                    ],
                ),
            )
        ]
        edges: list[GraphEdge] = []
        currency = cls._str_or_none(payload.get("contract_currency"))
        if currency:
            edges.append(
                GraphEdge(
                    src_label=LABEL_SUPPLIER,
                    src_pk=code,
                    type=EDGE_USES_CURRENCY,
                    dst_label=LABEL_CURRENCY,
                    dst_pk=currency,
                )
            )
        return nodes, edges

    @classmethod
    def _map_cost(
        cls, payload: dict[str, Any]
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        cost_id = cls._str_or_none(payload.get("id"))
        sku = cls._str_or_none(payload.get("sku"))
        if cost_id is None:
            return [], []
        nodes: list[GraphNode] = [
            GraphNode(
                label=LABEL_COST,
                primary_key=cost_id,
                properties=cls._filter_props(
                    payload,
                    [
                        "scheme_code",
                        "currency_origin",
                        "scheme_landed_aed",
                        "status",
                        "version",
                        "effective_at",
                    ],
                ),
            )
        ]
        edges: list[GraphEdge] = []
        if sku:
            edges.append(
                GraphEdge(
                    src_label=LABEL_PRODUCT,
                    src_pk=sku,
                    type=EDGE_HAS_COST,
                    dst_label=LABEL_COST,
                    dst_pk=cost_id,
                )
            )
        supplier_code = cls._str_or_none(payload.get("supplier_code"))
        if supplier_code:
            edges.append(
                GraphEdge(
                    src_label=LABEL_COST,
                    src_pk=cost_id,
                    type=EDGE_FROM_SUPPLIER,
                    dst_label=LABEL_SUPPLIER,
                    dst_pk=supplier_code,
                )
            )
        return nodes, edges

    @classmethod
    def _map_match_candidate(
        cls, payload: dict[str, Any]
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        match_id = cls._str_or_none(payload.get("id"))
        sku = cls._str_or_none(payload.get("product_sku"))
        if match_id is None:
            return [], []
        nodes: list[GraphNode] = [
            GraphNode(
                label=LABEL_MATCH_CANDIDATE,
                primary_key=match_id,
                properties=cls._filter_props(
                    payload,
                    [
                        "channel",
                        "external_id",
                        "title",
                        "brand",
                        "score",
                        "kind",
                        "status",
                    ],
                ),
            )
        ]
        edges: list[GraphEdge] = []
        if sku:
            edges.append(
                GraphEdge(
                    src_label=LABEL_PRODUCT,
                    src_pk=sku,
                    type=EDGE_HAS_MATCH,
                    dst_label=LABEL_MATCH_CANDIDATE,
                    dst_pk=match_id,
                )
            )
        channel = cls._str_or_none(payload.get("channel"))
        if channel:
            edges.append(
                GraphEdge(
                    src_label=LABEL_MATCH_CANDIDATE,
                    src_pk=match_id,
                    type=EDGE_LISTED_ON,
                    dst_label=LABEL_CHANNEL,
                    dst_pk=channel,
                )
            )
        return nodes, edges


__all__ = ["SchemaMapper"]
