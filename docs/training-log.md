# Training Log — MT Pricing Backup Operator

**Historia**: US-1B-05-03
**Sprint**: Sprint 8
**Fecha de creación**: 2026-05-12
**Champion / Supervisor**: psierra@br-innovation.com

---

## Información del Backup Operator

| Campo | Valor |
|-------|-------|
| Nombre | [PENDIENTE — rellenar] |
| Email | [PENDIENTE] |
| Rol | Backup Operator |
| Training Champion | psierra |
| Status | pending |

---

## Criterio de completado

El Backup Operator está listo para el cutover cuando:

- [ ] ≥ 2 sesiones hands-on completadas y grabadas
- [ ] 1 import ejecutado sin errores (documentado abajo)
- [ ] 1 aprobación de precio ejecutada sin errores (documentado abajo)
- [ ] Firma en este documento

> **Riesgo mitigado**: R-02 (single-point-of-failure del operador primario). El Backup Operator debe poder ejecutar de forma autónoma cualquier tarea de operación diaria definida en `docs/handbook-es.md`.

---

## Sesión 1

**Fecha**: [PENDIENTE]
**Duración**: [h]
**Modalidad**: [presencial / videoconferencia]
**Grabación**: [link o "n/a"]

### Ejercicios realizados

- [ ] Login y navegación del dashboard (`http://localhost:3000` en local / `app.mtme.ae` en prod)
- [ ] Revisión de cola de aprobación (`/admin/approvals`)
- [ ] Revisión de precios pendientes
- [ ] Simulación de aprobación individual

### Observaciones

[Rellenar post-sesión]

---

## Sesión 2

**Fecha**: [PENDIENTE]
**Duración**: [h]
**Modalidad**: [presencial / videoconferencia]
**Grabación**: [link o "n/a"]

### Ejercicios realizados

- [ ] Import completo de Excel v5.1 via `/admin/imports`
- [ ] Revisión del diff report `parallel-run-diff-YYYY-MM-DD.csv`
- [ ] Bulk-approve de lote de prueba
- [ ] Revisión del digest diario in-app

### Observaciones

[Rellenar post-sesión]

---

## Ejecución supervisada — Import

**Fecha**: [PENDIENTE]
**Archivo importado**: [nombre del Excel]
**Resultado**: [ ] Sin errores  [ ] Con errores (documentar)
**Observaciones**: [rellenar]

---

## Ejecución supervisada — Aprobación

**Fecha**: [PENDIENTE]
**Precios revisados**: [N]
**Acción**: [ ] Aprobación individual  [ ] Bulk-approve
**Resultado**: [ ] Completado sin errores  [ ] Con errores
**Observaciones**: [rellenar]

---

## Firma de completado

| Rol | Nombre | Fecha | Firma |
|-----|--------|-------|-------|
| Backup Operator | [PENDIENTE] | [PENDIENTE] | _____ |
| Champion / Supervisor | psierra | [PENDIENTE] | _____ |

---

*Generado: 2026-05-12 — Sprint 8 — US-1B-05-03*
