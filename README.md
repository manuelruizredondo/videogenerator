# VideoGenerator — Escaparate Dual 4K

Genera un vídeo MP4 `3840 × 4320 px / 25 fps / H.264` para reproducir en loop desde USB en **dos televisores 4K apilados verticalmente**.

---

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg          # macOS (o: sudo apt install ffmpeg)
```

Fuentes opcionales (mejor tipografía): descarga [Montserrat](https://fonts.google.com/specimen/Montserrat) y coloca los `.ttf` en `fonts/`.

---

## Flujo de trabajo

```
Google Sheets  →  sync_from_sheets.py  →  data/products.json  →  generate_video.py  →  output/escaparate.mp4
```

O directamente editando `data/products.json` a mano.

---

## Comandos disponibles

| Acción | Comando |
|---|---|
| Generar vídeo | `python generate_video.py` |
| Previsualizar | `python preview.py` |
| Sincronizar desde Sheets | `python sync_from_sheets.py` |
| Crear plantilla en Sheets | `python crear_plantilla_sheets.py` |

También puedes hacer doble clic en los archivos `.command` del proyecto.

---

## Formato de productos (`data/products.json`)

```json
[
  {
    "producto":    "Nombre del producto",
    "descripcion": "Descripción breve",
    "precio":      "999 €",
    "imagen":      "assets/backgrounds/foto.jpg",
    "duracion":    7
  }
]
```

- `imagen` y `duracion` son opcionales (sin imagen → degradado oscuro; sin duración → usa `slide_duration` de `config.json`).

---

## Distribución en pantalla

```
┌──────────────────┐  ← TV Superior
│  [TITULAR]       │
├──────────────────┤  ← línea de unión (zona libre ±280 px)
│  [Descripción]   │  ← TV Inferior
│  [  PRECIO  ]    │
└──────────────────┘
```

Animación por slide: fondo → titular (0.5 s) → descripción (2 s) → precio (3 s) → fade-out.

---

## Configuración (`config.json`)

Los parámetros más útiles:

| Parámetro | Qué controla |
|---|---|
| `slide_duration` | Duración por defecto de cada slide (segundos) |
| `overlay_alpha` | Oscurecimiento del fondo (0–255) |
| `encoder_preset` | Velocidad de codificación (`ultrafast` → `veryslow`) |
| `encoder_crf` | Calidad H.264 (18 = alta, 28 = media) |
| `title.font_size` | Tamaño del titular en píxeles |

---

## Solución de problemas

| Problema | Solución |
|---|---|
| FFmpeg no encontrado | `brew install ffmpeg` |
| Vídeo muy oscuro | Reduce `overlay_alpha` en `config.json` |
| Texto cortado | Reduce `font_size` o aumenta `slide_duration` |
| Generación lenta | Cambia `encoder_preset` a `ultrafast` |
