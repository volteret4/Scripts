# FreshRSS Embed Generator

Script para extraer enlaces de **Bandcamp**, **YouTube** y **SoundCloud** desde feeds de FreshRSS y generar páginas HTML con los embeds correspondientes.

## Características

- 🎵 Extrae enlaces de Bandcamp, YouTube y SoundCloud
- 📡 Se conecta a FreshRSS mediante la API de Google Reader
- 📂 Procesa feeds individuales o categorías completas
- 🔍 Opción de procesar solo artículos no leídos
- 📝 Genera un HTML por cada feed/categoría con todos los embeds
- 📄 **Paginación con lazy loading**: Solo carga la página actual, las demás bajo demanda
- ⚡ **Rendimiento optimizado**: Los embeds se cargan dinámicamente con JavaScript
- 🎨 Interfaz web moderna y responsive
- ⌨️ Navegación con teclado (flechas izquierda/derecha)

## Requisitos

```bash
pip install requests --break-system-packages
```

## Configuración de FreshRSS

Este script utiliza la API compatible con Google Reader de FreshRSS. Asegúrate de que:

1. Tu instalación de FreshRSS tenga la API habilitada
2. Tienes un usuario con contraseña (no funciona con autenticación OAuth)
3. La URL de tu servidor es accesible desde donde ejecutas el script

## Uso

### Modo interactivo (recomendado)

```bash
python3 freshrss_embed_generator.py --interactive --list-feeds
```

El script te pedirá:

- URL del servidor FreshRSS
- Usuario
- Contraseña

### Listar feeds disponibles

```bash
python3 freshrss_embed_generator.py \
  --server https://rss.example.com \
  --username tu_usuario \
  --list-feeds
```

### Listar categorías disponibles

```bash
python3 freshrss_embed_generator.py \
  --server https://rss.example.com \
  --username tu_usuario \
  --list-categories
```

### Procesar feeds específicos

```bash
python3 freshrss_embed_generator.py \
  --server https://rss.example.com \
  --username tu_usuario \
  --feeds "feed/123" "feed/456" \
  --output-dir mi_musica
```

### Procesar categorías completas

```bash
python3 freshrss_embed_generator.py \
  --interactive \
  --categories "Música" "Podcasts" \
  --unread-only
```

### Procesar solo artículos no leídos

```bash
python3 freshrss_embed_generator.py \
  --server https://rss.example.com \
  --username tu_usuario \
  --categories "Bandcamp" \
  --unread-only \
  --max-articles 50
```

## Opciones disponibles

### Conexión

- `--interactive`: Modo interactivo para configuración
- `--server URL`: URL del servidor FreshRSS
- `--username USER`: Usuario de FreshRSS
- `--password PASS`: Contraseña (mejor usar --interactive)

### Operación

- `--list-feeds`: Lista todos los feeds y sale
- `--list-categories`: Lista todas las categorías y sale
- `--feeds FEED_IDS`: IDs de feeds a procesar (ej: feed/123)
- `--categories NAMES`: Nombres de categorías a procesar
- `--unread-only`: Solo procesar artículos no leídos
- `--max-articles N`: Máximo de artículos a obtener (default: 100)

### Salida

- `--output-dir DIR`: Directorio de salida (default: freshrss_embeds)
- `--items-per-page N`: Número de embeds por página (default: 8)

## Ejemplos de uso

### Ejemplo 1: Explorar tu FreshRSS

```bash
# Ver todos los feeds
python3 freshrss_embed_generator.py --interactive --list-feeds

# Ver todas las categorías
python3 freshrss_embed_generator.py --interactive --list-categories
```

### Ejemplo 2: Procesar una categoría de música

```bash
python3 freshrss_embed_generator.py \
  --interactive \
  --categories "Música Electrónica" \
  --output-dir electronica
```

### Ejemplo 3: Procesar varios feeds específicos

```bash
python3 freshrss_embed_generator.py \
  --server https://rss.midominio.com \
  --username mi_usuario \
  --feeds "feed/42" "feed/108" "feed/256" \
  --output-dir bandcamp_nuevos
```

### Ejemplo 4: Solo artículos nuevos de varias categorías

```bash
python3 freshrss_embed_generator.py \
  --interactive \
  --categories "Rock" "Jazz" "Experimental" \
  --unread-only \
  --max-articles 50
```

### Ejemplo 5: Controlar embeds por página

```bash
# 12 embeds por página en lugar del default de 8
python3 freshrss_embed_generator.py \
  --interactive \
  --categories "Música" \
  --items-per-page 12
```

### Ejemplo 6: Generar índice de todos los feeds

```bash
# Después de generar los embeds, crea el índice
python3 generate_index.py --input-dir freshrss_embeds
```

## Servicios soportados

### 🎵 Bandcamp

- Detecta URLs de álbumes y tracks
- Genera embeds interactivos con reproductor
- Formato: `https://artista.bandcamp.com/album/nombre`

### 📺 YouTube

- Detecta URLs de videos
- Genera embeds con reproductor completo
- Formatos soportados:
  - `https://youtube.com/watch?v=ID`
  - `https://youtu.be/ID`

### 🔊 SoundCloud

- Detecta URLs de tracks
- Genera embeds con reproductor de SoundCloud
- Formato: `https://soundcloud.com/artista/track`

## Estructura de los HTML generados

Cada archivo HTML incluye:

- **Header**: Título del feed/categoría y estadísticas
- **Paginación**: Controles para navegar entre páginas
- **Embeds dinámicos**: Los embeds se cargan con lazy loading
- **Información de cada embed**:
  - Tipo de servicio (Bandcamp/YouTube/SoundCloud)
  - Título del artículo
  - Fecha de publicación
  - Autor (si está disponible)
  - Feed de origen (en categorías)
  - Enlace al artículo original
  - Player embebido

### 🚀 Paginación y Lazy Loading

El sistema genera:

- **Un HTML principal** con el visor paginado
- **Un archivo JSON único** con todas las páginas como keys

**Ventajas:**

- ⚡ Carga inicial rápida
- 💾 Un solo archivo de datos (más fácil de gestionar)
- 📱 Mejor experiencia en móviles
- ⌨️ Navegación con teclado (← →)
- 🔄 Páginas se cargan instantáneamente desde el JSON

**Archivos generados:**

```
freshrss_embeds/
├── Música_Electrónica.html          # Visor principal
├── Música_Electrónica_data.json     # Todas las páginas en un JSON
└── ...
```

## Generador de Índice

Después de generar los embeds, puedes crear un índice navegable:

```bash
python3 generate_index.py --input-dir freshrss_embeds
```

Esto creará un archivo `index.html` con:

- 📊 Estadísticas globales (total de embeds por servicio)
- 🔍 Buscador de feeds
- 📱 Tarjetas navegables para cada feed
- 📅 Fecha de última actualización de cada feed

## Estructura del directorio de salida

```
freshrss_embeds/
├── index.html                          # Índice principal (generado con generate_index.py)
├── Música_Electrónica.html
├── Música_Electrónica_data.json
├── Rock_Indie.html
├── Rock_Indie_data.json
├── Jazz_Experimental.html
└── Jazz_Experimental_data.json
```

## Notas técnicas

### API de FreshRSS

El script usa la API compatible con Google Reader de FreshRSS:

- Endpoint: `/api/greader.php`
- Autenticación: ClientLogin
- No requiere tokens de API adicionales

### Extracción de enlaces

El script busca enlaces en:

- Título del artículo
- Contenido HTML del artículo
- URL del artículo

### Limitaciones

- SoundCloud: El embed usa el player público, puede requerir configuración adicional para tracks privados
- Bandcamp: Solo funciona con URLs de formato estándar
- YouTube: Solo videos públicos

## Comparación con bc_imap_generator.py

| Característica    | bc_imap_generator.py       | freshrss_embed_generator.py   |
| ----------------- | -------------------------- | ----------------------------- |
| Fuente            | Email IMAP                 | FreshRSS                      |
| Servicios         | Solo Bandcamp              | Bandcamp, YouTube, SoundCloud |
| Organización      | Por carpeta de email       | Por feed/categoría RSS        |
| API               | IMAP                       | Google Reader API             |
| Botones de acción | Sí (marcar leído/eliminar) | No (solo visualización)       |
| Paginación        | Sí                         | Sí (con lazy loading)         |
| Items por página  | Configurable               | Configurable (default: 8)     |

## Solución de problemas

### Error de autenticación

- Verifica que el usuario y contraseña sean correctos
- Asegúrate de que la API esté habilitada en FreshRSS
- No uses autenticación de terceros (OAuth), necesitas usuario/contraseña de FreshRSS

### No encuentra feeds

- Verifica la URL del servidor (incluye http:// o https://)
- Comprueba que tienes feeds suscritos en FreshRSS
- Usa `--list-feeds` para ver los feeds disponibles

### No extrae enlaces

- Revisa que los artículos contengan enlaces directos a los servicios
- Algunos feeds pueden tener enlaces acortados o redirecciones
- Aumenta `--max-articles` para procesar más artículos

## Contribuir

Mejoras y sugerencias son bienvenidas. El script está diseñado para ser extensible:

- Añadir más servicios de música: edita las funciones `extract_*_url()`
- Personalizar HTML: modifica `generate_feed_html()`
- Cambiar formato de embeds: edita `generate_*_embed()`

## Licencia

Script de uso libre. Úsalo y modifícalo como necesites.
