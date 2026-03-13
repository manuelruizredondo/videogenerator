# VideoGenerator — Escaparate Dual 4K

Genera un único vídeo MP4 `3840 × 4320 px / 25 fps / H.264` listo para reproducir en loop desde USB en dos televisores 4K apilados verticalmente.

---

## Estructura del proyecto

```
VideoGenerator/
├── generate_video.py     # Script principal
├── config.json           # Configuración visual (tamaños, tiempos, colores)
├── requirements.txt      # Dependencias Python
├── data/
│   └── products.json     # Datos de productos
├── assets/
│   └── backgrounds/      # Imágenes de fondo (jpg, png, webp)
├── fonts/                # Fuentes TrueType (.ttf) opcionales
└── output/               # Vídeos generados (se crea automáticamente)
```

---

## Instalación

### 1. Python y dependencias

```bash
# Crear entorno virtual (recomendado)
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 3. Fuentes (recomendado)

Para mejor calidad tipográfica, descarga una fuente Bold y Regular y colócala en `fonts/`:

```
fonts/
├── Montserrat-Bold.ttf
└── Montserrat-Regular.ttf
```

Descarga gratuita: https://fonts.google.com/specimen/Montserrat

Sin fuente personalizada, el script usará las fuentes del sistema (Arial, DejaVu, etc.) o la fuente de emergencia de Pillow.

---

## Uso rápido

```bash
# Con los datos de ejemplo (genera output/escaparate.mp4)
python generate_video.py

# Especificando archivos
python generate_video.py -d data/products.json -c config.json -o output/final.mp4

# Con CSV
python generate_video.py -d data/products_example.csv
```

---

## Formato de los datos (`data/products.json`)

```json
[
  {
    "producto":    "Nombre del producto o titular",
    "descripcion": "Descripción breve visible en la TV inferior.",
    "precio":      "999 €",
    "imagen":      "assets/backgrounds/foto.jpg",
    "duracion":    7
  }
]
```

| Campo        | Obligatorio | Descripción                                                      |
|--------------|-------------|------------------------------------------------------------------|
| `producto`   | ✅           | Título grande (TV superior)                                      |
| `descripcion`| ✅           | Texto descriptivo (TV inferior, zona alta)                       |
| `precio`     | ✅           | Precio destacado (TV inferior, zona baja)                        |
| `imagen`     | —           | Ruta a imagen de fondo. Si está vacío se usa un degradado oscuro |
| `fondo`      | —           | Alias de `imagen`                                                |
| `duracion`   | —           | Duración de este slide en segundos (por defecto: `slide_duration` de `config.json`) |

---

## Configuración visual (`config.json`)

| Parámetro          | Descripción                                                                |
|--------------------|----------------------------------------------------------------------------|
| `fps`              | Fotogramas por segundo del vídeo final                                     |
| `slide_duration`   | Duración por defecto de cada slide (segundos)                              |
| `safe_margin`      | Margen seguro desde los bordes del canvas (px)                             |
| `split_safe_zone`  | Zona libre alrededor de la línea de unión física de pantallas (px)         |
| `overlay_alpha`    | Oscurecimiento del fondo (0=sin overlay, 255=negro total)                  |
| `vignette_strength`| Viñeta en bordes (0=sin viñeta, 255=muy oscuro)                            |
| `encoder_preset`   | Velocidad/calidad H.264: `ultrafast`, `fast`, `medium`, `slow`, `veryslow` |
| `encoder_crf`      | Calidad H.264: 0=sin pérdida, 18=alta calidad, 28=calidad media            |
| `title.font_size`  | Tamaño del titular en píxeles (210 ≈ texto muy grande)                     |
| `title.appear_at`  | Segundo en que aparece el titular                                           |
| `description.*`    | Lo mismo para la descripción                                               |
| `price.*`          | Lo mismo para el precio                                                    |
| `fade_out_duration`| Duración del fade-out al final de cada slide                               |

---

## Animación de cada slide

```
t = 0.0 s  → Fade-in del fondo
t = 0.5 s  → Aparece el titular        (TV superior)
t = 2.0 s  → Aparece la descripción    (TV inferior — arriba)
t = 3.0 s  → Aparece el precio         (TV inferior — abajo)
t = 6–8 s  → Fade-out de todo
```

---

## Distribución en pantalla

```
┌──────────────────────────────┐  ← y = 0
│                              │
│      [TITULAR GRANDE]        │  TV Superior
│                              │
├──────────────────────────────┤  ← y = 2160  (línea de unión — zona libre ±280 px)
│                              │
│   [Descripción del producto] │  TV Inferior
│                              │
│        [  PRECIO  ]          │
│                              │
└──────────────────────────────┘  ← y = 4320
```

---

## Compatibilidad con USB / TV

El vídeo generado cumple los requisitos de reproducción en loop desde USB:

- **Formato**: MP4 (contenedor)  
- **Codec vídeo**: H.264 (`libx264`)  
- **Pixel format**: `yuv420p` (compatible con todos los televisores)  
- **`-movflags +faststart`**: metadatos al inicio del archivo para reproducción inmediata  
- **Resolución**: 3840 × 4320 px  
- **FPS**: 25  

---

## Solución de problemas

| Problema | Solución |
|---|---|
| `FFmpeg no encontrado` | `brew install ffmpeg` |
| `Fuente no encontrada` | Añade un `.ttf` en `fonts/` |
| `Imagen no encontrada` | Se usará degradado oscuro automático |
| Vídeo muy oscuro | Reduce `overlay_alpha` en `config.json` (p.ej. `80`) |
| Texto cortado | Reduce `font_size` o amplía `slide_duration` |
| Generación muy lenta | Cambia `encoder_preset` a `fast` o `ultrafast` en `config.json` |
