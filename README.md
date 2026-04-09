# VideoGenerator — Escaparate Dual 4K

Genera un vídeo MP4 `3840 × 4320 px / 25 fps / H.264` para reproducir en loop desde USB en **dos televisores 4K apilados verticalmente**.

---

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg          # macOS (o: sudo apt install ffmpeg)
```

---

## Comandos disponibles

| Acción | Comando |
|---|---|
| Generar vídeo (alta calidad) | `python generate_video.py` |
| Generar vídeo (rápido) | doble clic en `LOW VIDEO.command` |
| Previsualizar en HTML | `python preview.py` |
| Formato Instagram | `python generate_instagram.py` |
| Sincronizar desde Sheets | `python sync_from_sheets.py` |

También puedes hacer doble clic en los archivos `.command` del proyecto.

---

## Cómo hacer un slide

Los slides se definen en `data/products.json`. Cada slide es un objeto JSON dentro del array:

```json
[
  {
    "titulo_1":   "TEXTO PEQUEÑO SUPERIOR",
    "titulo_2":   "Título Principal Grande",
    "titulo_3":   "subtítulo o especialidades",
    "descripcion": "Texto descriptivo en la pantalla de abajo.\nPuedes usar \\n para saltar de línea.",
    "precio":     "99 €",
    "imagen":     "assets/backgrounds/mifoto.jpg",
    "duracion":   "8"
  }
]
```

**Campos obligatorios:** solo `imagen`. El resto son opcionales (si no hay texto, simplemente no aparece).

**Imágenes y vídeos:** puedes usar `.jpg`, `.png`, `.mp4`, `.mov`, etc. Los vídeos se reproducen en loop durante el slide.

---

## Tipos de slide

Hay **2 tipos de layout** que se controlan con el campo `"template"` en cada slide.

### Tipo 1: `centered` (por defecto)

El fondo ocupa toda la pantalla. El texto aparece centrado. Es el tipo estándar.

```
┌────────────────────────┐  ← TV Superior
│      [LOGO ARRIBA]     │
│                        │
│  titulo_1 (pequeño)    │
│  titulo_2 (grande)     │
│  titulo_3 (subtítulo)  │
│                        │
├────────────────────────┤  ← línea de unión entre pantallas
│                        │
│      descripcion       │  ← TV Inferior
│                        │
│        PRECIO          │
│    [LOGO ABAJO]        │
└────────────────────────┘
```

No hace falta especificar nada, es el comportamiento por defecto.

### Tipo 2: `split`

El panel izquierdo es oscuro con el texto alineado a la izquierda. El vídeo/imagen entra animado desde la derecha. Ideal para vídeos verticales estilo Instagram Reel.

```
┌──────────────┬──────────────────┐
│              │                  │
│   titulo_2   │   imagen/vídeo   │
│   titulo_3   │   (entra desde   │
│   descripcion│    la derecha)   │
│   precio     │                  │
└──────────────┴──────────────────┘
```

```json
{
  "template": "split",
  "split_ratio": 0.45,
  ...
}
```

`split_ratio` controla dónde se divide la pantalla: `0.5` = mitad y mitad, `0.4` = 40% texto / 60% vídeo.

---

## Campos de control por slide

Todos estos campos son **opcionales** y se añaden dentro de cada objeto del `products.json`.

### Textos y contenido

| Campo | Tipo | Descripción |
|---|---|---|
| `titulo_1` | texto | Título pequeño (TV superior) |
| `titulo_2` | texto | Título grande principal (TV superior) |
| `titulo_3` | texto | Subtítulo o especialidades (TV superior) |
| `descripcion` | texto | Descripción (TV inferior). Usa `\n` para saltos de línea |
| `precio` | texto | Precio o llamada a la acción (TV inferior) |
| `precio_antes` | texto | Precio tachado que aparece junto al precio actual |
| `imagen` | ruta | Fondo del slide (`.jpg`, `.png`, `.mp4`, `.mov`…) |
| `duracion` | número | Duración del slide en segundos |

### Layout

| Campo | Tipo | Descripción |
|---|---|---|
| `template` | `"centered"` / `"split"` | Tipo de layout (por defecto: `"centered"`) |
| `split_ratio` | número 0-1 | Solo para `split`: proporción del panel de texto (0.45 = 45%) |

### Logos

| Campo | Tipo | Descripción |
|---|---|---|
| `show_logo` | `true` / `false` | Muestra u oculta el logo superior en este slide (por defecto: `true`) |
| `show_logo_footer` | `true` / `false` | Muestra u oculta el logo inferior en este slide (por defecto: `true`) |

### Velado oscuro

| Campo | Tipo | Descripción |
|---|---|---|
| `show_overlay` | `true` / `false` | Activa o desactiva el velado oscuro sobre el fondo (por defecto: `true`) |
| `overlay_alpha` | número 0-255 | Intensidad del velado (0 = sin velado, 255 = negro total). El global está en `config.json` |
| `overlay_appear_at` | segundos | En qué momento empieza a aparecer el velado |
| `overlay_fade_duration` | segundos | Cuánto tarda en aparecer el velado |

### Tamaños de fuente (overrides por slide)

| Campo | Descripción |
|---|---|
| `font_size_titulo_1` | Tamaño en px del título 1 solo para este slide |
| `font_size_titulo_2` | Tamaño en px del título 2 solo para este slide |
| `font_size_titulo_3` | Tamaño en px del título 3 solo para este slide |
| `font_size_descripcion` | Tamaño en px de la descripción solo para este slide |
| `font_size_precio` | Tamaño en px del precio solo para este slide |

---

## Ejemplos

### Slide básico con foto

```json
{
  "titulo_1": "NOVEDAD",
  "titulo_2": "Blanqueamiento Dental",
  "titulo_3": "Tratamiento profesional en 1 hora",
  "descripcion": "Consigue una sonrisa perfecta.\nAsesoría gratuita incluida.",
  "precio": "199 €",
  "imagen": "assets/backgrounds/dientes.jpg",
  "duracion": "8"
}
```

### Slide sin velado (fondo ya oscuro)

```json
{
  "titulo_2": "Medicina Estética",
  "descripcion": "Tratamientos personalizados.",
  "precio": "Pide tu cita",
  "imagen": "assets/backgrounds/oscuro.mp4",
  "show_overlay": false
}
```

### Slide sin logos (slide especial de bienvenida)

```json
{
  "titulo_1": "BIENVENIDO",
  "titulo_2": "Centre Mèdic Basté",
  "imagen": "assets/backgrounds/intro.mp4",
  "show_logo": false,
  "show_logo_footer": false,
  "duracion": "10"
}
```

### Slide solo con logo superior, sin logo inferior

```json
{
  "titulo_2": "Oferta del Mes",
  "precio": "50% DTO.",
  "imagen": "assets/backgrounds/promo.jpg",
  "show_logo_footer": false
}
```

### Slide con precio tachado y velado más fuerte

```json
{
  "titulo_1": "ANIVERSARIO · 10% DTO.",
  "titulo_2": "Implantes Dentales",
  "descripcion": "Precio especial solo este mes.",
  "precio_antes": "1.200 €",
  "precio": "1.080 €",
  "imagen": "assets/backgrounds/clinica.jpg",
  "overlay_alpha": 160
}
```

### Slide tipo split (dos paneles)

```json
{
  "template": "split",
  "split_ratio": 0.45,
  "titulo_2": "Medicina Estética Facial",
  "titulo_3": "Toxina · Labios · Armonización",
  "descripcion": "Resultados naturales y duraderos.",
  "precio": "Desde 290 €",
  "imagen": "assets/backgrounds/estetica.mp4"
}
```

---

## Distribución en pantalla (template centered)

```
┌──────────────────────────────────────────┐  y = 0
│                                          │
│            [LOGO SUPERIOR]               │
│                                          │
│              titulo_1                    │
│          TITULO_2 GRANDE                 │
│              titulo_3                    │
│                                          │
├──────────────────────────────────────────┤  y = 2160  ← unión física entre TVs
│            (zona libre ±280 px)          │
│                                          │
│              descripcion                 │
│                                          │
│              [ PRECIO ]                  │
│                                          │
│            [LOGO INFERIOR]               │
└──────────────────────────────────────────┘  y = 4320
```

---

## Configuración global (`config.json`)

Estos parámetros aplican a todos los slides. Se pueden sobreescribir por slide en `products.json`.

| Parámetro | Qué controla |
|---|---|
| `overlay_alpha` | Oscurecimiento del fondo en todos los slides (0–255) |
| `hold_duration` | Segundos que todo permanece visible antes del fade-out |
| `fade_out_duration` | Duración del fundido de salida del slide |
| `encoder_preset` | Velocidad de codificación (`ultrafast` → `veryslow`) |
| `encoder_crf` | Calidad H.264 (18 = muy alta, 28 = media) |
| `vignette_strength` | Oscurecimiento de los bordes (0–255) |
| `bg_zoom` | Zoom lento del fondo tipo Ken Burns (0 = sin zoom, 0.1 = zoom del 10%) |
| `logo.position` | Posición del logo: `top-center`, `top-left`, `bottom-right`… |
| `logo_footer.position` | Posición del logo inferior |

---

## Solución de problemas

| Problema | Solución |
|---|---|
| FFmpeg no encontrado | `brew install ffmpeg` (macOS) o `sudo apt install ffmpeg` (Linux) |
| Vídeo muy oscuro | Reduce `overlay_alpha` en `config.json` o añade `"show_overlay": false` al slide |
| Texto cortado | Reduce `font_size_titulo_2` en el slide problemático |
| Generación lenta | Cambia `encoder_preset` a `ultrafast` en `config.json` |
| Logo no desaparece en un slide | Añade `"show_logo": false` o `"show_logo_footer": false` en ese slide |
