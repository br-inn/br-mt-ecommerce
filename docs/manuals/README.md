# Manuales de Usuario — MT Middle East MDM + Pricing

**Sistema:** MT Middle East MDM + Pricing — Fase 1  
**Audiencia:** Usuarios MT internos y clientes MT  
**Idioma:** Español  
**Última actualización:** 2026-05-12

---

## Manuales disponibles

| # | Manual | Roles | Estado |
|---|--------|-------|--------|
| [00](00-acceso-primeros-pasos.md) | Acceso y Primeros Pasos | Todos | ✅ Listo |
| [01](01-gestion-catalogo-pim.md) | Gestión de Catálogo (PIM) | Comercial, Gerente | ✅ Listo |
| [08](08-workflow-aprobacion-precios.md) | Workflow de Aprobación de Precios | Comercial, Gerente | ✅ Listo |

### Próximos manuales (backlog)

| # | Manual | Roles |
|---|--------|-------|
| 02 | Maestro de Proveedores | Comercial, Gerente |
| 03 | Maestro de Costes por SKU | Comercial, Gerente |
| 04 | Importadores y Datasheets PDF | Comercial |
| 05 | Monedas y Tipos de Cambio (FX) | Gerente |
| 06 | Motor de Pricing Multi-Canal | Gerente |
| 07 | Simulador de Precios por Canal | Gerente |
| 09 | RBAC y Gestión de Usuarios | TI |
| 10 | Scheduler y Panel de Jobs | TI |
| 11 | Connectors y Shadow Publish | TI |

---

## Capturas de pantalla

Las imágenes de cada manual se almacenan en [`assets/screenshots/`](assets/screenshots/).

### Capturas requeridas — Manual 00

| Archivo | Pantalla | URL |
|---------|----------|-----|
| `00-login.png` | Pantalla de login | `/login` |
| `00-dashboard.png` | Dashboard principal tras login | `/` |
| `00-idioma.png` | Selector de idioma desplegado | barra superior |
| `00-mi-cuenta.png` | Pantalla Mi cuenta | `/account` |

### Capturas requeridas — Manual 01

| Archivo | Pantalla | URL |
|---------|----------|-----|
| `01-catalogo-lista.png` | Lista de SKUs con filtros | `/products` |
| `01-detalle-sku-tabs.png` | Detalle SKU con tabs visibles | `/products/{id}` |
| `01-nuevo-sku-paso1.png` | Wizard paso 1 - Identidad | `/products/new` |
| `01-editar-identidad.png` | Tab Identidad en modo edición | `/products/{id}` → tab Identidad → Editar |
| `01-tab-imagenes.png` | Tab Imágenes con galería | `/products/{id}` → tab Imágenes |
| `01-tab-traducciones.png` | Tab Traducciones con estados | `/products/{id}` → tab Traducciones |
| `01-importer.png` | Pantalla de importer | `/products/import` |
| `01-tab-auditoria.png` | Tab Auditoría con historial | `/products/{id}` → tab Auditoría |

### Capturas requeridas — Manual 08

| Archivo | Pantalla | URL |
|---------|----------|-----|
| `08-mis-propuestas.png` | Mis propuestas - Comercial | `/prices/my-proposals` |
| `08-cola-resumen.png` | Cola de aprobación completa | `/prices/queue` |
| `08-sidebar-detalle.png` | Sidebar de detalle abierto | `/prices/queue` → clic en fila |
| `08-bulk-seleccion.png` | Selección múltiple en cola | `/prices/queue` → marcar checkboxes |
| `08-sidebar-completo.png` | Sidebar con todas las secciones | `/prices/queue` → clic en fila |
| `08-escalado.png` | Precio escalado en cola | `/prices/queue?filter=escalated` |
| `08-delegacion.png` | Configuración de delegación | `/account` → Delegación |

---

## Convenciones de los manuales

- **Roles mencionados:** `Comercial` / `Gerente` / `TI` (nombres de display, no IDs técnicos)
- **URLs:** relativas al servidor frontend (`http://localhost:3000` en local, URL de producción en producción)
- **Imágenes:** formato `png`, resolución mínima 1280×800 px, sin datos sensibles (usar datos de demo)
- **Idioma de captura:** las capturas deben tomarse con el sistema en español (ES)
