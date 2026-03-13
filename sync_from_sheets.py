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

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

PRODUCTS_FIELDS = [
    "titulo_1", "titulo_2", "titulo_3",
    "descripcion", "precio_antes", "precio", "imagen",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def _check_deps() -> None:
    try:
        import gspread  # noqa: F401
        from google.oauth2.credentials import Credentials  # noqa: F401
        from google.auth.transport.requests import Request  # noqa: F401
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
    except ImportError:
        print("❌  Faltan dependencias. Ejecuta:")
        print("    pip install gspread google-auth google-auth-oauthlib google-auth-httplib2")
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

    headers = [h.strip().lower() for h in rows[0]]
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
        if product:
            products.append(product)

    return products


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    _check_deps()
    import gspread

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

    # ── Config ────────────────────────────────────────────────────────────────
    config  = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    n_cfg   = sync_config(sh, config)
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


if __name__ == "__main__":
    main()
