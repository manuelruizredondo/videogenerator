#!/usr/bin/env python3
"""
sync_from_sheets.py

Descarga la configuración y los productos desde Google Sheets
y actualiza config.json y data/products.json en el proyecto.

Primera ejecución: abre el navegador para autorizar acceso a Google.
Las siguientes: es automático (token guardado en credentials/token.json).
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT    = Path(__file__).parent
CONFIG_PATH     = PROJECT_ROOT / "config.json"
PRODUCTS_PATH   = PROJECT_ROOT / "data" / "products.json"
SHEETS_CFG_PATH = PROJECT_ROOT / "sheets_settings.json"
CREDS_DIR       = PROJECT_ROOT / "credentials"
TOKEN_PATH      = CREDS_DIR / "token.json"
OAUTH_PATH      = CREDS_DIR / "oauth_client.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",   # lectura + escritura
    "https://www.googleapis.com/auth/drive.readonly",
]

DRIVE_MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
}

PRODUCTS_FIELDS = [
    "titulo_1", "titulo_2", "titulo_3",
    "descripcion", "precio_antes", "precio", "imagen",
    "duracion",
    # Tamaños de fuente opcionales por producto (sobreescriben config.json)
    "font_size_titulo_1", "font_size_titulo_2", "font_size_titulo_3",
    "font_size_descripcion", "font_size_precio", "font_size_precio_antes",
]

# Mapeo de cabeceras de Google Sheets → nombres internos de campo
HEADER_MAP = {
    "título 1 (grande)":          "titulo_1",
    "título 2 (subtítulo)":       "titulo_2",
    "título 3 (detalle)":         "titulo_3",
    "descripción":                "descripcion",
    "precio anterior (tachado)":  "precio_antes",
    "precio actual":              "precio",
    "imagen / vídeo (ruta)":      "imagen",
    "duración (segundos)":        "duracion",
    "duracion":                   "duracion",
    # Tamaños de fuente (columnas opcionales en Sheets)
    "tamaño título 1":            "font_size_titulo_1",
    "tamaño título 2":            "font_size_titulo_2",
    "tamaño título 3":            "font_size_titulo_3",
    "tamaño descripción":         "font_size_descripcion",
    "tamaño precio":              "font_size_precio",
    "tamaño precio anterior":     "font_size_precio_antes",
    # Alias directos por si se usan cabeceras cortas
    "titulo_1": "titulo_1",
    "titulo_2": "titulo_2",
    "titulo_3": "titulo_3",
    "descripcion": "descripcion",
    "precio_antes": "precio_antes",
    "precio": "precio",
    "imagen": "imagen",
    "font_size_titulo_1": "font_size_titulo_1",
    "font_size_titulo_2": "font_size_titulo_2",
    "font_size_titulo_3": "font_size_titulo_3",
    "font_size_descripcion": "font_size_descripcion",
    "font_size_precio": "font_size_precio",
    "font_size_precio_antes": "font_size_precio_antes",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def _check_deps() -> None:
    try:
        import gspread  # noqa: F401
        from google.oauth2.credentials import Credentials  # noqa: F401
        from google.auth.transport.requests import Request  # noqa: F401
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except ImportError:
        print("❌  Faltan dependencias. Ejecuta:")
        print("    pip install gspread google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        sys.exit(1)


def load_creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not OAUTH_PATH.exists():
                print(f"\n❌  No se encontró el archivo de credenciales en:\n    {OAUTH_PATH}")
                print("\n  Sigue estos pasos para obtenerlo:")
                print("  1. Ve a https://console.cloud.google.com/")
                print("  2. Crea un proyecto (o usa uno existente)")
                print("  3. Activa la API 'Google Sheets API'")
                print("  4. Ve a Credenciales → Crear credencial → ID de cliente OAuth 2.0")
                print("     Tipo de aplicación: Aplicación de escritorio")
                print("  5. Descarga el JSON y guárdalo en:")
                print(f"     {OAUTH_PATH}\n")
                sys.exit(1)
            flow  = InstalledAppFlow.from_client_secrets_file(str(OAUTH_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        CREDS_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════

def cast_value(raw: str):
    """Convierte el string de la celda al tipo Python más adecuado."""
    s = raw.strip()
    if not s:
        return None
    if s.lower() in ("true", "verdadero", "sí", "si"):
        return True
    if s.lower() in ("false", "falso", "no"):
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if s.startswith(("[", "{")):
        try:
            return json.loads(s)
        except Exception:
            pass
    return s


def set_nested(obj, dot_path: str, value) -> None:
    """Escribe value en obj siguiendo la ruta punto (ej: 'titles.0.font_size')."""
    keys = dot_path.split(".")
    cur  = obj
    for key in keys[:-1]:
        k = int(key) if key.isdigit() else key
        if isinstance(k, int):
            cur = cur[k]
        else:
            cur = cur.setdefault(k, {})
    last = keys[-1]
    if last.isdigit():
        cur[int(last)] = value
    else:
        cur[last] = value


# ═══════════════════════════════════════════════════════════════════════════════
#  SINCRONIZACIÓN CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

def sync_config(sh, config: dict) -> int:
    """
    Lee todas las hojas del spreadsheet que tienen columnas 'Clave' y 'Valor'
    y aplica sus valores sobre el dict config.
    Devuelve el número de claves actualizadas.
    """
    updated     = 0
    skip_titles = {"productos", "products", "📦 productos"}

    for ws in sh.worksheets():
        if ws.title.lower().strip() in skip_titles:
            continue

        rows = ws.get_all_values()
        if len(rows) < 2:
            continue

        headers = [h.strip().lower() for h in rows[0]]
        try:
            key_col = headers.index("clave")
            val_col = headers.index("valor")
        except ValueError:
            continue   # hoja sin las columnas esperadas

        for row in rows[1:]:
            if len(row) <= max(key_col, val_col):
                continue
            key = row[key_col].strip()
            val = row[val_col].strip()
            if not key or key.startswith("#"):
                continue
            parsed = cast_value(val)
            if parsed is None:
                continue
            try:
                set_nested(config, key, parsed)
                updated += 1
            except Exception as e:
                print(f"  ⚠️  [{ws.title}] clave '{key}': {e}")

    return updated


# ═══════════════════════════════════════════════════════════════════════════════
#  SINCRONIZACIÓN PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════

def sync_products(sh) -> list | None:
    """
    Busca una hoja cuyo título contenga 'producto' y la lee como tabla de productos.
    Devuelve la lista de productos o None si no se encontró la hoja.
    """
    ws = None
    for sheet in sh.worksheets():
        if "producto" in sheet.title.lower():
            ws = sheet
            break
    if ws is None:
        return None

    rows = ws.get_all_values()
    if len(rows) < 2:
        return []

    raw_headers = [h.strip().lower() for h in rows[0]]
    # Normalizar cabeceras usando el mapa; ignorar las que no reconocemos
    headers = [HEADER_MAP.get(h, h) for h in raw_headers]
    products = []

    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue   # fila completamente vacía
        product = {}
        for field in PRODUCTS_FIELDS:
            try:
                idx = headers.index(field)
                val = row[idx].strip() if idx < len(row) else ""
                if val:
                    product[field] = val
            except ValueError:
                pass
        # Descartar la fila de referencia (fila 2) donde cada valor == nombre del campo
        if not product:
            continue
        is_ref_row = all(v == k for k, v in product.items())
        if not is_ref_row:
            products.append(product)

    return products


# ═══════════════════════════════════════════════════════════════════════════════
#  SINCRONIZACIÓN ASSETS DESDE GOOGLE DRIVE
# ═══════════════════════════════════════════════════════════════════════════════

def _list_drive_files(service, folder_id: str) -> list:
    """Lista recursivamente todos los archivos de una carpeta de Drive."""
    results = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
            pageSize=200,
            pageToken=page_token,
        ).execute()
        for item in resp.get("files", []):
            if item["mimeType"] == "application/vnd.google-apps.folder":
                results.extend(_list_drive_files(service, item["id"]))
            else:
                results.append(item)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results


def sync_assets_from_drive(creds, folder_id: str, local_dir: Path) -> tuple[int, int]:
    """
    Descarga los archivos de imagen/vídeo de una carpeta de Drive a local_dir.
    Solo descarga si el archivo no existe o ha cambiado (por tamaño).
    Devuelve (descargados, omitidos).
    """
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io

    service    = build("drive", "v3", credentials=creds, cache_discovery=False)
    local_dir.mkdir(parents=True, exist_ok=True)

    files      = _list_drive_files(service, folder_id)
    media_files = [
        f for f in files
        if Path(f["name"]).suffix.lower() in DRIVE_MEDIA_EXTENSIONS
    ]

    downloaded = 0
    skipped    = 0

    for file in media_files:
        dest = local_dir / file["name"]
        remote_size = int(file.get("size", 0))

        # Omitir si ya existe con el mismo tamaño
        if dest.exists() and dest.stat().st_size == remote_size:
            skipped += 1
            continue

        print(f"  ⬇  {file['name']}  ({remote_size / 1024 / 1024:.1f} MB)")
        request = service.files().get_media(fileId=file["id"])
        buf     = io.BytesIO()
        dl      = MediaIoBaseDownload(buf, request, chunksize=8 * 1024 * 1024)
        done    = False
        while not done:
            _, done = dl.next_chunk()
        dest.write_bytes(buf.getvalue())
        downloaded += 1

    return downloaded, skipped


# ═══════════════════════════════════════════════════════════════════════════════
#  SUBIDA DE PRODUCTOS → GOOGLE SHEETS
# ═══════════════════════════════════════════════════════════════════════════════

# Mapa inverso: campo interno → cabecera legible en Sheets
FIELD_TO_HEADER = {v: k for k, v in HEADER_MAP.items() if k not in HEADER_MAP.values()}
# Priorizar las cabeceras "bonitas" (las que tienen caracteres especiales/acentos)
FIELD_TO_HEADER.update({
    "titulo_1":             "Título 1 (grande)",
    "titulo_2":             "Título 2 (subtítulo)",
    "titulo_3":             "Título 3 (detalle)",
    "descripcion":          "Descripción",
    "precio_antes":         "Precio anterior (tachado)",
    "precio":               "Precio actual",
    "imagen":               "Imagen / vídeo (ruta)",
    "duracion":             "Duración (segundos)",
    "font_size_titulo_1":   "Tamaño título 1",
    "font_size_titulo_2":   "Tamaño título 2",
    "font_size_titulo_3":   "Tamaño título 3",
    "font_size_descripcion":"Tamaño descripción",
    "font_size_precio":     "Tamaño precio",
    "font_size_precio_antes":"Tamaño precio anterior",
})


def push_products_to_sheets(sh, products: list) -> int:
    """
    Sube la lista de productos al Google Sheet.
    Respeta las cabeceras existentes y añade columnas nuevas si hacen falta.
    Devuelve el número de filas escritas.
    """
    ws = None
    for sheet in sh.worksheets():
        if "producto" in sheet.title.lower():
            ws = sheet
            break
    if ws is None:
        print("❌  Hoja 'Productos' no encontrada en el spreadsheet.")
        return 0

    # ── Leer cabeceras actuales ───────────────────────────────────────────────
    existing_headers_raw = ws.row_values(1)
    existing_headers     = [h.strip() for h in existing_headers_raw]

    # ── Determinar qué cabeceras necesitamos (unión de campos de todos los productos) ──
    needed_fields: list[str] = []
    for field in PRODUCTS_FIELDS:
        if any(field in p for p in products):
            needed_fields.append(field)

    # Construir lista final de cabeceras: primero las existentes, luego las nuevas
    final_headers = list(existing_headers)
    header_to_col: dict[str, int] = {}   # cabecera → índice 0-based

    for h in existing_headers:
        h_lower  = h.strip().lower()
        field    = HEADER_MAP.get(h_lower, h_lower)
        col_idx  = existing_headers.index(h)
        header_to_col[field] = col_idx

    for field in needed_fields:
        if field not in header_to_col:
            nice_header = FIELD_TO_HEADER.get(field, field)
            final_headers.append(nice_header)
            header_to_col[field] = len(final_headers) - 1

    # ── Construir fila de referencia (fila 2) y filas de datos ──────────────
    n_cols = len(final_headers)

    # Fila 2: nombres internos de campo (referencia visual en el Sheet)
    ref_row = [""] * n_cols
    for field, col_idx in header_to_col.items():
        ref_row[col_idx] = field

    rows_to_write: list[list] = []
    for product in products:
        row = [""] * n_cols
        for field, value in product.items():
            if field in header_to_col:
                row[header_to_col[field]] = str(value)
        rows_to_write.append(row)

    # ── Actualizar la hoja en batch ───────────────────────────────────────────
    # 1. Actualizar cabeceras si hay columnas nuevas
    if len(final_headers) > len(existing_headers):
        ws.update([final_headers], "1:1")

    # 2. Borrar filas de datos existentes (fila 2 en adelante)
    last_data_row = ws.row_count
    if last_data_row >= 2:
        clear_range = f"A2:{chr(ord('A') + n_cols - 1)}{last_data_row}"
        ws.batch_clear([clear_range])

    # 3. Escribir fila de referencia en fila 2
    ws.update([ref_row], "A2")

    # 4. Escribir datos de productos desde fila 3
    if rows_to_write:
        ws.update(rows_to_write, "A3")

    return len(rows_to_write)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse
    _check_deps()
    import gspread

    parser = argparse.ArgumentParser(description="Sincroniza datos con Google Sheets y Drive")
    parser.add_argument(
        "--push", action="store_true",
        help="Sube products.json local → Google Sheets (en lugar de descargar)",
    )
    args = parser.parse_args()

    if not SHEETS_CFG_PATH.exists():
        print("❌  No se encontró sheets_settings.json")
        print("   Ejecuta primero: python crear_plantilla_sheets.py")
        sys.exit(1)

    sheets_cfg     = json.loads(SHEETS_CFG_PATH.read_text(encoding="utf-8"))
    spreadsheet_id = sheets_cfg.get("spreadsheet_id") or sheets_cfg.get("spreadsheet_url", "")
    if not spreadsheet_id:
        print("❌  sheets_settings.json no contiene 'spreadsheet_id'")
        sys.exit(1)

    print("🔑  Autenticando con Google...")
    creds = load_creds()
    gc    = gspread.authorize(creds)

    print("📊  Conectando con el spreadsheet...")
    try:
        sh = (
            gc.open_by_url(spreadsheet_id)
            if "docs.google.com" in spreadsheet_id
            else gc.open_by_key(spreadsheet_id)
        )
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌  Spreadsheet no encontrado: {spreadsheet_id}")
        print("   Asegúrate de que la cuenta autorizada tiene acceso a la hoja.")
        sys.exit(1)

    # ══════════════════════════════════════════════════════════════════════════
    if args.push:
        # ── MODO SUBIDA: local → Sheets ───────────────────────────────────────
        if not PRODUCTS_PATH.exists():
            print(f"❌  No se encontró {PRODUCTS_PATH}")
            sys.exit(1)
        products = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))
        if not products:
            print("⚠️   products.json está vacío, no hay nada que subir.")
            sys.exit(0)
        print(f"⬆️   Subiendo {len(products)} productos a Google Sheets...")
        n = push_products_to_sheets(sh, products)
        print(f"✅  {n} productos subidos a la hoja 'Productos'")
        return
    # ══════════════════════════════════════════════════════════════════════════

    # ── MODO DESCARGA: Sheets → local ─────────────────────────────────────────

    # ── Config ────────────────────────────────────────────────────────────────
    config_raw = CONFIG_PATH.read_text(encoding="utf-8")
    config     = json.loads(config_raw)
    n_cfg      = sync_config(sh, config)
    # Backup antes de sobrescribir por si la sincronización corrompió algo
    CONFIG_PATH.with_suffix(".json.bak").write_text(config_raw, encoding="utf-8")
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅  config.json   → {n_cfg} valores actualizados")

    # ── Productos ─────────────────────────────────────────────────────────────
    products = sync_products(sh)
    if products is not None:
        PRODUCTS_PATH.write_text(
            json.dumps(products, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"✅  products.json → {len(products)} productos sincronizados")
    else:
        print("ℹ️   Hoja 'Productos' no encontrada (products.json sin cambios)")

    # ── Assets desde Google Drive ──────────────────────────────────────────────
    drive_folder_id = sheets_cfg.get("drive_folder_id", "").strip()
    if drive_folder_id:
        local_assets = PROJECT_ROOT / sheets_cfg.get("drive_assets_local", "assets/backgrounds")
        print(f"\n📁  Sincronizando assets desde Google Drive → {local_assets.relative_to(PROJECT_ROOT)}/")
        try:
            dl, sk = sync_assets_from_drive(creds, drive_folder_id, local_assets)
            print(f"✅  Drive assets → {dl} descargados, {sk} ya actualizados")
        except Exception as e:
            print(f"❌  Error sincronizando Drive: {e}")
    else:
        print("ℹ️   drive_folder_id no configurado en sheets_settings.json (Drive omitido)")


if __name__ == "__main__":
    main()
