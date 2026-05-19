---
tags: [sprint, dashboard]
---

# Sprint Dashboard — MT ERP

> [!tip] Requiere plugin **Dataview** (instalar desde Community Plugins)

## Stories en Backlog — ERP Best Practices (S13+)

```dataview
TABLE rows.file.link as Stories, length(rows) as Total
FROM "_bmad-output/planning-artifacts"
WHERE contains(file.name, "epics-and-stories-ep-erp")
FLATTEN file.link as story
GROUP BY file.name
SORT file.mtime DESC
```

## Planes de implementación activos

```dataview
TABLE file.mtime as "Última edición", file.size as "Bytes"
FROM "docs/superpowers/plans"
SORT file.mtime DESC
LIMIT 10
```

## ADRs recientes

```dataview
TABLE file.mtime as "Fecha"
FROM "_bmad-output/planning-artifacts/adr" OR "docs/adr"
SORT file.mtime DESC
LIMIT 15
```

## Chat docs (sesiones de trabajo)

```dataview
TABLE file.mtime as "Fecha"
FROM "docs/chat-docs"
SORT file.mtime DESC
LIMIT 10
```

---

## Navegación rápida

### Épicas activas S13+
- [EP-ERP-01 UX Producto](../_bmad-output/planning-artifacts/epics-and-stories-ep-erp-best-practices.md)
- [EP-ERP-02 Inventario v2](../_bmad-output/planning-artifacts/epics-and-stories-ep-erp-best-practices.md)
- [EP-ERP-03 Compras P2P](../_bmad-output/planning-artifacts/epics-and-stories-ep-erp-best-practices.md)
- [EP-ERP-06 Finanzas](../_bmad-output/planning-artifacts/epics-and-stories-ep-erp-best-practices.md)

### Artefactos clave
- [Sprint Status](../_bmad-output/implementation-artifacts/sprint-status.yaml)
- [PRD](../_bmad-output/planning-artifacts/prd-mt-pricing-mdm-phase1.md)
- [Arquitectura](../_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md)
- [Handbook operativo](handbook-es.md)
- [CLAUDE.md](../CLAUDE.md)
