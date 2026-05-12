# Neo4j — Política de Residencia de Datos UAE

**Aplica a:** Neo4j 5.20 Community Edition (KG de materiales, Fase 1.5)
**Última revisión:** 2026-05-12
**Owner:** Equipo BR-MT / psierra@br-innovation.com

---

## Resumen ejecutivo

Neo4j se utiliza como graph store para el Knowledge Graph (KG) de materiales del
proyecto MT Middle East. Almacena SKUs, materiales técnicos y relaciones de
compatibilidad entre productos — datos sin PII (Personally Identifiable Information).

El despliegue se realiza sobre infraestructura **Hetzner** (zona EU/AE según ambiente),
**no** en Neo4j Aura ni ningún cloud gestionado externo. Esto garantiza control total
sobre la ubicación física de los datos y es compatible con los requerimientos de
residencia de datos de clientes UAE.

---

## Política de residencia de datos UAE

### Principios

| Principio | Detalle |
|-----------|---------|
| **Infraestructura** | Hetzner EU zone (Nuremberg/Falkenstein) o Hetzner AE (Ashburn/Singapore según contrato) — nunca Neo4j Aura ni AWS/GCP/Azure sin aprobación explícita. |
| **Datos almacenados** | SKUs, códigos de material, atributos técnicos, relaciones de compatibilidad. **Ningún dato personal de usuarios MT** se almacena en Neo4j. |
| **Sin PII** | El KG no contiene nombres, emails, documentos de identidad, datos financieros ni ningún dato cubierto por DIFC Data Protection Law 2020 o ADGM Data Protection Regulations. |
| **Acceso externo** | El puerto Bolt (7687) **no está expuesto públicamente**. Solo accesible dentro de la red privada Docker/Hetzner. |
| **Backups** | Volumen Docker montado en disco Hetzner, con snapshot diario automatizado vía Hetzner Snapshot API. Ver sección Backup. |

### Clasificación de datos en Neo4j

```
Nodo :Material      → código SKU, descripción técnica, unidad de medida
Nodo :Category      → categoría de producto (no personal)
Relación :COMPATIBLE_WITH  → compatibilidad entre materiales
Relación :BELONGS_TO       → categorización
```

Ningún nodo ni relación contiene campos de usuario final (userId, email, teléfono).

### Auditoria

- Los accesos al graph store se loguean a nivel de aplicación (FastAPI, `app/core/logging.py`).
- Las consultas Cypher de modificación (CREATE/MERGE/DELETE) se registran con timestamp y servicio origen.
- Los logs se envían a Better Stack Logs (token configurado en `BETTER_STACK_LOGS_TOKEN`).

---

## Configuración de red

### Dev local (Docker Compose)

| Puerto host | Puerto contenedor | Protocolo | Acceso |
|-------------|------------------|-----------|--------|
| `17474`     | `7474`           | HTTP      | Neo4j Browser — solo localhost |
| `17687`     | `7687`           | Bolt      | Driver Python — solo localhost |

```
# Acceso desde el stack interno (backend, worker)
NEO4J_URI=bolt://neo4j:7687

# Acceso desde el host (scripts, IDE, healthcheck)
NEO4J_URI=bolt://localhost:17687
```

### Staging / Producción (Hetzner)

- Neo4j corre en la red privada del servidor Hetzner.
- Puerto Bolt **no expuesto** en firewall público (`ufw deny 7687/tcp`).
- Backend y Worker acceden via `bolt://neo4j:7687` dentro de la red Docker.
- Acceso administrativo: túnel SSH (`ssh -L 17687:localhost:7687 deploy@<hetzner-ip>`).

---

## Proceso de backup y restore

### Backup automático

```bash
# Hetzner Snapshot diario — configurado en crontab del servidor
# Captura el volumen Docker completo (incluyendo neo4j_data)
0 3 * * * /opt/scripts/hetzner-snapshot.sh neo4j_data
```

El volumen `neo4j_data` persiste en `/var/lib/docker/volumes/mt-pricing-dev_neo4j_data`.

### Backup manual (online)

```bash
# Desde el host con Neo4j corriendo
docker exec mt-neo4j neo4j-admin database dump neo4j \
  --to-path=/tmp/neo4j-backup-$(date +%Y%m%d).dump

# Copiar fuera del contenedor
docker cp mt-neo4j:/tmp/neo4j-backup-$(date +%Y%m%d).dump ./backups/
```

### Restore

```bash
# 1. Detener el contenedor
docker compose -f docker-compose.dev.yml stop neo4j

# 2. Restaurar dump
docker run --rm \
  -v mt-pricing-dev_neo4j_data:/data \
  -v $(pwd)/backups:/backups \
  neo4j:5.20-community \
  neo4j-admin database load neo4j --from-path=/backups/neo4j-backup-YYYYMMDD.dump --overwrite-destination

# 3. Reiniciar
docker compose -f docker-compose.dev.yml start neo4j
```

### Verificación post-restore

```bash
# Healthcheck básico
./scripts/healthcheck_neo4j.sh

# Contar nodos (debería ser > 0 en un KG poblado)
cypher-shell -u neo4j -p devpassword -a bolt://localhost:17687 \
  "MATCH (n) RETURN labels(n)[0] AS tipo, count(n) AS total ORDER BY total DESC"
```

---

## Escalado y limitaciones

### Community Edition — Fase 1.5

Neo4j 5.20 **Community Edition** es suficiente para Fase 1.5 por las siguientes razones:

| Factor | Community | Req. Fase 1.5 |
|--------|-----------|---------------|
| Instancias | 1 (standalone) | 1 suficiente |
| Bases de datos | 1 (`neo4j`) | 1 suficiente |
| Nodos estimados | Sin límite hard | ~50K SKUs |
| Concurrencia | Limitada vs Enterprise | Carga batch interna |
| Auth avanzado | No (RBAC) | No requerido Fase 1 |

### Upgrade a Enterprise

Si en Fase 2+ se requiere:
- Alta disponibilidad (clustering)
- Multi-tenancy con bases de datos aisladas
- RBAC granular
- Auditoría nativa

Se deberá migrar a **Neo4j Enterprise** o evaluar **AuraDB Enterprise** con región
Dubai/UAE garantizada contractualmente.

El proceso de migración es transparente: misma imagen `neo4j:5.20-enterprise`,
mismo volumen de datos, mismo driver Python (`neo4j` SDK).

---

## Contacto y escalación

| Rol | Contacto |
|-----|----------|
| Owner técnico | psierra@br-innovation.com |
| Repositorio | `br-mt/br-mt-ecommerce` |
| Runbook relacionado | `docs/runbooks/disaster-recovery.md` |
