"""import_product_images.py — Descarga imágenes del Excel y las sube a Supabase Storage.

Fuente: INVOICE ENRIQUECIDA v5 > columna "URL Imagen (PIM)"
Destino: Supabase Storage bucket `product-images` + tabla `product_assets`

Uso:
    python scripts/import_product_images.py [--dry-run] [--limit N] [--sku CODIGO]

Requiere en el entorno (o en mt-pricing-backend/.env):
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ALEMBIC_DATABASE_URL
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

import openpyxl
import psycopg2
import requests
from PIL import Image

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

EXCEL_PATH = (
    Path(__file__).parent.parent
    / "Documentos referencia de articulos"
    / "stock_dubai_v25_GAP_ANALYSIS_2026-05-07 (1).xlsx"
)
SHEET_NAME = "INVOICE ENRIQUECIDA v5"
COL_SKU = 0   # "Código"
COL_URL = 65  # "URL Imagen (PIM)"
HEADER_ROW = 2
DATA_START_ROW = 3

BUCKET = "product-images"
KIND = "photo"

# Carga credenciales desde .env del backend si no están en el entorno
_ENV_FILE = Path(__file__).parent.parent / "mt-pricing-backend" / ".env"


def _load_env() -> None:
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        # Strip inline comment (e.g. KEY=value   # comment)
        if not (val.startswith('"') or val.startswith("'")):
            comment_pos = val.find(" #")
            if comment_pos != -1:
                val = val[:comment_pos]
        val = val.strip().strip('"').strip("'")
        if key and val and key not in os.environ:
            os.environ[key] = val


_load_env()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DATABASE_URL = os.environ.get("ALEMBIC_DATABASE_URL", "") or os.environ.get("DATABASE_URL", "")


# ---------------------------------------------------------------------------
# Modelos de datos
# ---------------------------------------------------------------------------

class ImageRow(NamedTuple):
    sku: str
    url: str


class DownloadResult(NamedTuple):
    content: bytes
    mime_type: str
    width: int | None
    height: int | None
    sha256: str


# ---------------------------------------------------------------------------
# Lectura del Excel
# ---------------------------------------------------------------------------

def read_excel_rows() -> list[ImageRow]:
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]
    rows: list[ImageRow] = []
    for row in ws.iter_rows(min_row=DATA_START_ROW, values_only=True):
        sku_raw = row[COL_SKU] if len(row) > COL_SKU else None
        url_raw = row[COL_URL] if len(row) > COL_URL else None
        if not sku_raw or not url_raw:
            continue
        url = str(url_raw).strip()
        sku = str(sku_raw).strip()
        if url.startswith("http") and sku:
            rows.append(ImageRow(sku=sku, url=url))
    wb.close()
    return rows


# ---------------------------------------------------------------------------
# Descarga de imagen
# ---------------------------------------------------------------------------

def download_image(url: str, session: requests.Session) -> DownloadResult:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    content = resp.content
    mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    sha256 = hashlib.sha256(content).hexdigest()

    width = height = None
    try:
        img = Image.open(io.BytesIO(content))
        width, height = img.size
    except Exception:
        pass

    return DownloadResult(
        content=content,
        mime_type=mime,
        width=width,
        height=height,
        sha256=sha256,
    )


# ---------------------------------------------------------------------------
# Supabase Storage upload
# ---------------------------------------------------------------------------

def upload_to_storage(
    sku: str,
    result: DownloadResult,
    session: requests.Session,
    dry_run: bool = False,
) -> str:
    ext = "jpg" if "jpeg" in result.mime_type or "jpg" in result.mime_type else "jpg"
    storage_path = f"{sku}/primary.{ext}"

    if dry_run:
        print(f"    [DRY-RUN] Subiría: {BUCKET}/{storage_path} ({len(result.content)} bytes)")
        return storage_path

    upload_url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": result.mime_type,
        "x-upsert": "true",  # reemplaza si ya existe
    }
    resp = session.put(upload_url, data=result.content, headers=headers, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Storage upload failed [{resp.status_code}]: {resp.text[:200]}"
        )

    return storage_path


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def get_db_connection():
    # Convierte asyncpg URL a psycopg2 (síncrono)
    url = DATABASE_URL
    if "+asyncpg" in url:
        url = url.replace("postgresql+asyncpg", "postgresql")
    if "+psycopg" in url:
        url = url.replace("postgresql+psycopg", "postgresql")
    return psycopg2.connect(url)


def sku_exists_in_db(cur, sku: str) -> bool:
    cur.execute("SELECT 1 FROM products WHERE sku = %s AND deleted_at IS NULL LIMIT 1", (sku,))
    return cur.fetchone() is not None


def asset_already_exists(cur, sku: str) -> bool:
    cur.execute(
        "SELECT 1 FROM product_assets WHERE sku = %s AND kind = 'photo' AND status = 'active' LIMIT 1",
        (sku,),
    )
    return cur.fetchone() is not None


def upsert_asset(
    cur,
    sku: str,
    storage_path: str,
    original_url: str,
    result: DownloadResult,
    dry_run: bool = False,
) -> None:
    if dry_run:
        print(f"    [DRY-RUN] INSERT product_assets sku={sku} path={storage_path}")
        return

    asset_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO product_assets (
            id, sku, kind, bucket, storage_path, original_url,
            is_primary, position, mime_type, hash_sha256,
            bytes_size, width, height, status
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            true, 0, %s, %s,
            %s, %s, %s, 'active'
        )
        ON CONFLICT DO NOTHING
        """,
        (
            asset_id,
            sku,
            KIND,
            BUCKET,
            storage_path,
            original_url,
            result.mime_type,
            result.sha256,
            len(result.content),
            result.width,
            result.height,
        ),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Importar imágenes PIM desde Excel")
    parser.add_argument("--dry-run", action="store_true", help="No escribe nada")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N filas (0=todas)")
    parser.add_argument("--sku", type=str, default="", help="Procesar solo este SKU")
    parser.add_argument("--skip-db", action="store_true", help="No verifica ni inserta en BD")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY requeridos.")
        sys.exit(1)

    print(f"[INFO] Leyendo Excel: {EXCEL_PATH.name}")
    rows = read_excel_rows()
    print(f"   {len(rows)} filas con URL encontradas")

    if args.sku:
        rows = [r for r in rows if r.sku == args.sku]
        print(f"   Filtrado por SKU={args.sku}: {len(rows)} filas")

    if args.limit:
        rows = rows[: args.limit]
        print(f"   Limitado a {args.limit} filas")

    # Conectar BD
    conn = cur = None
    if not args.skip_db and not args.dry_run:
        print("[INFO] Conectando a Supabase PostgreSQL...")
        try:
            conn = get_db_connection()
            conn.autocommit = False
            cur = conn.cursor()
            print("   Conexion OK")
        except Exception as e:
            print(f"   WARN: Sin BD ({e}). Continuando sin verificacion de SKUs.")

    session = requests.Session()
    session.headers["User-Agent"] = "MT-PIM-Importer/1.0"

    # Caché de descargas: url -> DownloadResult (evita re-descargar misma imagen)
    download_cache: dict[str, DownloadResult] = {}

    stats = {"ok": 0, "skip_no_sku": 0, "skip_exists": 0, "error": 0}

    print(f"\n[START] Iniciando importacion {'(DRY-RUN)' if args.dry_run else ''}...\n")

    for i, row in enumerate(rows, 1):
        sku, url = row.sku, row.url
        prefix = f"[{i:03d}/{len(rows):03d}] {sku}"

        # Verificar que el SKU existe en productos
        if cur:
            if not sku_exists_in_db(cur, sku):
                print(f"{prefix} -> SKIP (SKU no existe en products)")
                stats["skip_no_sku"] += 1
                continue

            if asset_already_exists(cur, sku):
                print(f"{prefix} -> SKIP (ya tiene imagen)")
                stats["skip_exists"] += 1
                continue

        # Descargar (con cache por URL)
        if url not in download_cache:
            try:
                print(f"{prefix} -> Descargando {url[:60]}")
                dl = download_image(url, session)
                download_cache[url] = dl
                print(f"    OK {dl.width}x{dl.height} {dl.mime_type} {len(dl.content)/1024:.1f}KB sha256={dl.sha256[:8]}")
            except Exception as e:
                print(f"{prefix} -> ERROR descarga: {e}")
                stats["error"] += 1
                continue
        else:
            dl = download_cache[url]
            print(f"{prefix} -> (cache) sha256={dl.sha256[:8]}")

        # Subir a Supabase Storage
        try:
            storage_path = upload_to_storage(sku, dl, session, dry_run=args.dry_run)
        except Exception as e:
            print(f"{prefix} -> ERROR storage: {e}")
            stats["error"] += 1
            continue

        # Insertar en BD
        try:
            upsert_asset(cur, sku, storage_path, url, dl, dry_run=args.dry_run)
            if cur and not args.dry_run:
                conn.commit()
            stats["ok"] += 1
            print(f"{prefix} -> OK {storage_path}")
        except Exception as e:
            print(f"{prefix} -> ERROR BD: {e}")
            if conn:
                conn.rollback()
            stats["error"] += 1

        # Pausa ligera para no saturar Storage API
        if not args.dry_run and i % 10 == 0:
            time.sleep(0.5)

    # Cierre
    if cur:
        cur.close()
    if conn:
        conn.close()

    print(f"""
{'='*50}
OK:                 {stats['ok']}
Skip (sin SKU BD):  {stats['skip_no_sku']}
Skip (ya existe):   {stats['skip_exists']}
Errores:            {stats['error']}
URLs unicas desc.:  {len(download_cache)}
{'='*50}
""")


if __name__ == "__main__":
    main()
