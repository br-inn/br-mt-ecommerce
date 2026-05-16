# Story Artifact: US-ERP-04-03 — Credit check automático + auto-release

**Epic:** EP-ERP-04 — Ventas O2C  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Sistema de gestión de crédito de clientes: bloqueo automático de SOs que excedan el límite,
endpoint de liberación manual con razón obligatoria, y auto-release por Celery al registrar pago.

## Implementación verificada

### Migración
- `20260524_112_credit_management.py` — crea tablas:
  - `customer_credit_limits` (customer_id, credit_limit, currency, credit_horizon_days, is_blocked, block_reason)
  - `customer_open_items` (customer_id, so_id, invoice_id, document_type, amount, due_date)
  - Unique constraint en `customer_id`

### Modelos (`app/db/models/sales.py`)
- `CustomerCreditLimit` — `__tablename__ = "customer_credit_limits"`
- `CustomerOpenItem` — `__tablename__ = "customer_open_items"`

### API (`app/api/routes/sales.py`)
- `POST /api/v1/sales/orders/{id}/credit-check` — evalúa crédito del cliente
- `POST /api/v1/sales/credit-limits` — crear límite
- `PATCH /api/v1/sales/credit-limits/{id}` — actualizar límite
- `POST /api/v1/sales/orders/{id}/release-credit-block` — liberar bloqueo (solo gerente/ti, razón obligatoria)

### Worker (`app/workers/tasks/sales.py`)
- Task de re-evaluación automática de crédito al registrar pago

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Campo `credit_limit` en customers/tabla dedicada | ✅ `customer_credit_limits` |
| Al crear/modificar SO: evaluar crédito. Si falla: `status = 'credit_hold'` | ✅ lógica en SO creation |
| Endpoint `release-credit-hold` solo gerente/ti con razón obligatoria | ✅ `release-credit-block` con `require_role` |
| Job Celery re-evalúa crédito al registrar pago | ✅ task en `sales.py` |
| Órdenes < $500 exentas (configurable) | ✅ campo configurable |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260524_112_credit_management.py`
- `mt-pricing-backend/app/db/models/sales.py` (CustomerCreditLimit, CustomerOpenItem)
- `mt-pricing-backend/app/api/routes/sales.py` (endpoints credit_check, create_credit_limit, release_credit_block)
- `mt-pricing-backend/app/workers/tasks/sales.py`
