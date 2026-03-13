#!/usr/bin/env python3
"""
crear_plantilla_sheets.py

Crea automáticamente un Google Sheet con toda la estructura necesaria
para editar config.json y data/products.json desde el navegador.

Uso:
    python crear_plantilla_sheets.py

Resultado:
    - Se abre el navegador para autorizar (primera vez)
    - Se crea el spreadsheet en tu Google Drive
    - Se guarda su URL en sheets_settings.json
    - Se imprime la URL para que la puedas compartir con tu equipo
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

# Necesita permisos de escritura para crear el spreadsheet
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# ─────────────────────────────────────────────────────────────────────────────
#  Mapa completo: (descripción, clave JSON en notación punto, nota)
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_SECTIONS = {
    "⚙️ General": [
        ("FPS",                          "fps",                    "Fotogramas por segundo (25 recomendado)"),
        ("Pausa visible (seg)",           "hold_duration",          "Segundos con todo visible antes del fade-out"),
        ("Dur. fade-out slide (seg)",     "fade_out_duration",      "Duración del fade-out al final de cada slide"),
        ("Zoom fondo Ken Burns",          "bg_zoom",                "0=sin zoom  0.01=crece 1% a lo largo del slide"),
        ("Segundo aparición fondo",       "bg_appear_at",           "Retraso antes de que aparezca la imagen/vídeo de fondo"),
        ("Color intro fondo",             "intro_bg_color",         "Color RGB inicial antes del fondo p.ej. [10,10,14]"),
        ("Transparencia overlay",         "overlay_alpha",          "Oscuridad del overlay  0=transparente  255=negro total"),
        ("Segundo aparición overlay",     "overlay_appear_at",      "Segundo en que el fondo empieza a oscurecerse"),
        ("Dur. fade overlay (seg)",       "overlay_fade_duration",  "Segundos hasta que el overlay llega a su máximo"),
        ("Intensidad viñeta",             "vignette_strength",      "Oscurecimiento de bordes  0=sin viñeta  255=máximo"),
        ("Margen de seguridad (px)",      "safe_margin",            "Píxeles de margen respecto a los bordes del canvas"),
        ("Zona segura unión pantallas (px)", "split_safe_zone",     "Píxeles libres alrededor de la línea de unión de TVs (y=2160)"),
    ],
    "📝 Títulos": [
        ("Título 1 · Campo datos",        "titles.0.field",         "Columna de products.json que se mostrará aquí"),
        ("Título 1 · Fuente",             "titles.0.font",          "Ruta relativa al .ttf/.otf (ej: fonts/neutrif/font-bold.ttf)"),
        ("Título 1 · Tamaño (px)",        "titles.0.font_size",     "Tamaño en píxeles (canvas 3840px de ancho)"),
        ("Título 1 · Color",              "titles.0.color",         "Color RGB p.ej. [255,255,255]"),
        ("Título 1 · Aparece en (seg)",   "titles.0.appear_at",     "Segundo exacto en que empieza el fade-in"),
        ("Título 1 · Dur. fade-in (seg)", "titles.0.fade_duration", "Duración del fade-in en segundos"),
        ("Título 1 · Margen superior (px)","titles.0.margin_top",   "Distancia (px) desde el borde superior de la zona segura"),
        ("Título 2 · Campo datos",        "titles.1.field",         "Columna de products.json que se mostrará aquí"),
        ("Título 2 · Fuente",             "titles.1.font",          "Ruta relativa al .ttf/.otf"),
        ("Título 2 · Tamaño (px)",        "titles.1.font_size",     "Tamaño en píxeles"),
        ("Título 2 · Color",              "titles.1.color",         "Color RGB p.ej. [255,255,255]"),
        ("Título 2 · Aparece en (seg)",   "titles.1.appear_at",     "Segundo exacto en que empieza el fade-in"),
        ("Título 2 · Dur. fade-in (seg)", "titles.1.fade_duration", "Duración del fade-in en segundos"),
        ("Título 2 · Margen superior (px)","titles.1.margin_top",   "Espacio (px) entre el título anterior y éste"),
        ("Título 3 · Campo datos",        "titles.2.field",         "Columna de products.json que se mostrará aquí"),
        ("Título 3 · Fuente",             "titles.2.font",          "Ruta relativa al .ttf/.otf"),
        ("Título 3 · Tamaño (px)",        "titles.2.font_size",     "Tamaño en píxeles"),
        ("Título 3 · Color",              "titles.2.color",         "Color RGB p.ej. [255,255,255]"),
        ("Título 3 · Aparece en (seg)",   "titles.2.appear_at",     "Segundo exacto en que empieza el fade-in"),
        ("Título 3 · Dur. fade-in (seg)", "titles.2.fade_duration", "Duración del fade-in en segundos"),
        ("Título 3 · Margen superior (px)","titles.2.margin_top",   "Espacio (px) entre el título anterior y éste"),
    ],
    "💰 Descripción y Precios": [
        ("Descripción · Fuente",             "description.font",                 "Ruta relativa al .ttf/.otf"),
        ("Descripción · Tamaño (px)",        "description.font_size",            "Tamaño en píxeles"),
        ("Descripción · Color",              "description.color",                "Color RGB p.ej. [210,215,225]"),
        ("Descripción · Aparece en (seg)",   "description.appear_at",            "Segundo exacto en que empieza el fade-in"),
        ("Descripción · Dur. fade-in (seg)", "description.fade_duration",        "Duración del fade-in en segundos"),
        ("Precio · Fuente",                  "price.font",                       "Ruta relativa al .ttf/.otf"),
        ("Precio · Tamaño (px)",             "price.font_size",                  "Tamaño en píxeles"),
        ("Precio · Color",                   "price.color",                      "Color RGB p.ej. [255,220,50]"),
        ("Precio · Aparece en (seg)",        "price.appear_at",                  "Segundo exacto en que empieza el fade-in"),
        ("Precio · Dur. fade-in (seg)",      "price.fade_duration",              "Duración del fade-in en segundos"),
        ("Precio anterior · Fuente",         "price_before.font",                "Ruta relativa al .ttf/.otf"),
        ("Precio anterior · Tamaño (px)",    "price_before.font_size",           "Tamaño en píxeles"),
        ("Precio anterior · Color",          "price_before.color",               "Color RGB p.ej. [170,170,170]"),
        ("Precio anterior · Espacio (px)",   "price_before.gap",                 "Píxeles entre el precio tachado y el precio actual"),
        ("Precio anterior · Color tachado",  "price_before.strikethrough_color", "Color RGB de la línea de tachado p.ej. [220,80,80]"),
    ],
    "🖼️ Logos": [
        ("Logo cabecera · Archivo",       "logo.file",              "Ruta relativa al archivo (ej: assets/logo.png)"),
        ("Logo cabecera · Ancho (px)",    "logo.width",             "Ancho en píxeles (la altura se calcula automáticamente)"),
        ("Logo cabecera · Posición",      "logo.position",          "top-center / top-left / top-right"),
        ("Logo cabecera · Margen sup (px)","logo.margin_top",       "Píxeles desde el borde superior"),
        ("Logo cabecera · Margen lat (px)","logo.margin_side",      "Píxeles desde el borde lateral (solo left/right)"),
        ("Logo cabecera · Aparece en",    "logo.appear_at",         "Segundo en que empieza el fade-in"),
        ("Logo cabecera · Dur. fade-in",  "logo.fade_duration",     "Duración del fade-in en segundos"),
        ("Logo cabecera · Entra desde",   "logo.enter_from",        "top / bottom / left / right — o vacío para sin animación"),
        ("Logo cabecera · Dur. entrada",  "logo.slide_duration",    "Duración del movimiento de entrada en segundos"),
        ("Logo pie · Archivo",            "logo_footer.file",       "Ruta relativa al archivo (ej: assets/logofooter.png)"),
        ("Logo pie · Ancho (px)",         "logo_footer.width",      "Ancho en píxeles"),
        ("Logo pie · Posición",           "logo_footer.position",   "bottom-center / bottom-left / bottom-right"),
        ("Logo pie · Margen inf (px)",    "logo_footer.margin_top", "Píxeles desde el borde inferior"),
        ("Logo pie · Margen lat (px)",    "logo_footer.margin_side","Píxeles desde el borde lateral"),
        ("Logo pie · Aparece en",         "logo_footer.appear_at",  "Segundo en que empieza el fade-in"),
        ("Logo pie · Dur. fade-in",       "logo_footer.fade_duration","Duración del fade-in en segundos"),
        ("Logo pie · Entra desde",        "logo_footer.enter_from", "top / bottom / left / right"),
        ("Logo pie · Dur. entrada",       "logo_footer.slide_duration","Duración del movimiento de entrada en segundos"),
    ],
    "🎬 Encoder": [
        ("Preset encoder", "encoder_preset", "ultrafast / fast / medium / slow / veryslow"),
        ("Calidad CRF",    "encoder_crf",    "0=sin pérdida  18=muy alta calidad  28=calidad media"),
    ],
}

PRODUCTS_HEADER = [
    "titulo_1", "titulo_2", "titulo_3",
    "descripcion", "precio_antes", "precio", "imagen",
]
PRODUCTS_HEADER_LABELS = [
    "Título 1 (grande)", "Título 2 (subtítulo)", "Título 3 (detalle)",
    "Descripción", "Precio anterior (tachado)", "Precio actual", "Imagen / vídeo (ruta)",
]

# Colores corporativos para el formato del spreadsheet
COLOR_HEADER      = {"red": 0.13, "green": 0.13, "blue": 0.16}   # gris oscuro
COLOR_SECTION     = {"red": 0.09, "green": 0.09, "blue": 0.12}   # negro casi puro
COLOR_KEY_BG      = {"red": 0.95, "green": 0.95, "blue": 0.97}   # blanco azulado
COLOR_WHITE       = {"red": 1.0,  "green": 1.0,  "blue": 1.0}
COLOR_HEADER_TEXT = {"red": 1.0,  "green": 1.0,  "blue": 1.0}


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTENTICACIÓN  (igual que sync_from_sheets pero con permisos de escritura)
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

    # El token para crear plantilla puede requerir scopes distintos al de sync.
    # Guardamos en un token separado para no interferir.
    token_create = CREDS_DIR / "token_create.json"
    creds = None
    if token_create.exists():
        creds = Credentials.from_authorized_user_file(str(token_create), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not OAUTH_PATH.exists():
                print(f"\n❌  No se encontró el archivo de credenciales en:\n    {OAUTH_PATH}")
                print("\n  Sigue estos pasos para obtenerlo:")
                print("  1. Ve a https://console.cloud.google.com/")
                print("  2. Activa la API 'Google Sheets API' en tu proyecto")
                print("  3. Ve a Credenciales → Crear credencial → ID de cliente OAuth 2.0")
                print("     Tipo de aplicación: Aplicación de escritorio")
                print("  4. Descarga el JSON y guárdalo como:")
                print(f"     {OAUTH_PATH}\n")
                sys.exit(1)
            flow  = InstalledAppFlow.from_client_secrets_file(str(OAUTH_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        CREDS_DIR.mkdir(parents=True, exist_ok=True)
        token_create.write_text(creds.to_json(), encoding="utf-8")

    return creds


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPER: valor actual de una clave en notación punto
# ═══════════════════════════════════════════════════════════════════════════════

def get_nested(obj, dot_path: str, default: str = "") -> str:
    try:
        cur = obj
        for key in dot_path.split("."):
            k   = int(key) if key.isdigit() else key
            cur = cur[k]
        if isinstance(cur, (list, dict)):
            return json.dumps(cur, ensure_ascii=False)
        return str(cur)
    except (KeyError, IndexError, TypeError):
        return default


# ═══════════════════════════════════════════════════════════════════════════════
#  FORMATEO DE HOJAS
# ═══════════════════════════════════════════════════════════════════════════════

def fmt_header_row(ws, row_idx: int, n_cols: int) -> list:
    return [{
        "repeatCell": {
            "range": {
                "sheetId":          ws.id,
                "startRowIndex":    row_idx,
                "endRowIndex":      row_idx + 1,
                "startColumnIndex": 0,
                "endColumnIndex":   n_cols,
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": COLOR_HEADER,
                    "textFormat": {
                        "foregroundColor": COLOR_HEADER_TEXT,
                        "bold":            True,
                        "fontSize":        11,
                    },
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    }]


def fmt_col_widths(ws, widths: list[int]) -> list:
    reqs = []
    for i, w in enumerate(widths):
        reqs.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId":    ws.id,
                    "dimension":  "COLUMNS",
                    "startIndex": i,
                    "endIndex":   i + 1,
                },
                "properties": {"pixelSize": w},
                "fields":     "pixelSize",
            }
        })
    return reqs


def fmt_freeze(ws, rows: int = 1, cols: int = 0) -> list:
    return [{
        "updateSheetProperties": {
            "properties": {
                "sheetId":      ws.id,
                "gridProperties": {
                    "frozenRowCount":    rows,
                    "frozenColumnCount": cols,
                },
            },
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }
    }]


# ═══════════════════════════════════════════════════════════════════════════════
#  CREAR HOJAS DE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

def create_config_sheets(sh, config: dict) -> list:
    """Crea una hoja por cada sección de CONFIG_SECTIONS. Devuelve requests de formato."""
    fmt_requests = []

    for title, rows_def in CONFIG_SECTIONS.items():
        try:
            ws = sh.add_worksheet(title=title, rows=len(rows_def) + 5, cols=4)
        except Exception:
            ws = sh.worksheet(title)
            ws.clear()

        # Cabecera
        ws.update("A1:D1", [["Descripción", "Clave", "Valor", "Notas"]])
        fmt_requests += fmt_header_row(ws, 0, 4)
        fmt_requests += fmt_freeze(ws, rows=1)
        fmt_requests += fmt_col_widths(ws, [280, 260, 180, 380])

        # Datos
        data_rows = []
        for desc, key, note in rows_def:
            current_val = get_nested(config, key)
            data_rows.append([desc, key, current_val, note])

        if data_rows:
            ws.update(f"A2:D{1 + len(data_rows)}", data_rows)

        # Columna Clave en gris claro (no editable visualmente)
        fmt_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId":          ws.id,
                    "startRowIndex":    1,
                    "endRowIndex":      1 + len(rows_def),
                    "startColumnIndex": 1,
                    "endColumnIndex":   2,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": COLOR_KEY_BG,
                        "textFormat": {"italic": True, "fontSize": 9},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

        # Columna Valor en negrita para destacarla
        fmt_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId":          ws.id,
                    "startRowIndex":    1,
                    "endRowIndex":      1 + len(rows_def),
                    "startColumnIndex": 2,
                    "endColumnIndex":   3,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
            }
        })

    return fmt_requests


# ═══════════════════════════════════════════════════════════════════════════════
#  CREAR HOJA DE PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════

def create_products_sheet(sh, products: list) -> list:
    """Crea la hoja '📦 Productos' con los datos actuales."""
    fmt_requests = []
    n_rows = max(len(products) + 10, 20)

    try:
        ws = sh.add_worksheet(title="📦 Productos", rows=n_rows, cols=len(PRODUCTS_HEADER))
    except Exception:
        ws = sh.worksheet("📦 Productos")
        ws.clear()

    # Cabecera doble: fila 1 = etiquetas legibles, fila 2 = claves JSON (usadas por el sync)
    ws.update("A1", [PRODUCTS_HEADER_LABELS])
    ws.update("A2", [PRODUCTS_HEADER])

    fmt_requests += fmt_header_row(ws, 0, len(PRODUCTS_HEADER))
    fmt_requests += fmt_freeze(ws, rows=2)
    fmt_requests += fmt_col_widths(ws, [220, 220, 280, 380, 200, 160, 360])

    # Fila 2 (claves) en gris claro
    fmt_requests.append({
        "repeatCell": {
            "range": {
                "sheetId":          ws.id,
                "startRowIndex":    1,
                "endRowIndex":      2,
                "startColumnIndex": 0,
                "endColumnIndex":   len(PRODUCTS_HEADER),
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": COLOR_KEY_BG,
                    "textFormat": {"italic": True, "fontSize": 9},
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    })

    # Datos de productos actuales
    if products:
        data_rows = []
        for p in products:
            row = [p.get(f, "") for f in PRODUCTS_HEADER]
            data_rows.append(row)
        ws.update(f"A3:G{2 + len(data_rows)}", data_rows)

    return fmt_requests


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    _check_deps()
    import gspread

    config   = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    products = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))

    print("🔑  Autenticando con Google (se abrirá el navegador si es la primera vez)...")
    creds = load_creds()
    gc    = gspread.authorize(creds)

    print("📊  Creando el spreadsheet en Google Drive...")
    sh = gc.create("VideoGenerator — Configuración y Productos")

    # Eliminar la hoja por defecto "Hoja 1"
    default_ws = sh.get_worksheet(0)

    # Crear hojas de config y productos
    fmt_requests  = create_config_sheets(sh, config)
    fmt_requests += create_products_sheet(sh, products)

    # Aplicar todos los formatos de una vez
    if fmt_requests:
        sh.batch_update({"requests": fmt_requests})

    # Eliminar la hoja vacía por defecto
    try:
        sh.del_worksheet(default_ws)
    except Exception:
        pass

    url = f"https://docs.google.com/spreadsheets/d/{sh.id}"

    # Guardar en sheets_settings.json
    SHEETS_CFG_PATH.write_text(
        json.dumps({"spreadsheet_id": sh.id, "spreadsheet_url": url}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n✅  Spreadsheet creado correctamente:")
    print(f"   {url}")
    print(f"\n   ID guardado en: sheets_settings.json")
    print(f"\n   ➡️  Abre la URL, edita los valores en la columna 'Valor'")
    print(f"       y ejecuta 'Sincronizar Sheets.command' para aplicar los cambios.\n")

    # Abrir en el navegador automáticamente
    import subprocess
    subprocess.run(["open", url], check=False)


if __name__ == "__main__":
    main()
