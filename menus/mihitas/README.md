# Creador de Posts - Obsidian a Hugo (PyQt6 + Temas)

Aplicación en Python con interfaz gráfica PyQt6 para convertir notas de Obsidian a posts de Hugo para múltiples blogs.

## 🚀 Características

- **Interfaz gráfica moderna** con PyQt6
- **🎨 Sistema de temas dinámicos** con archivo YAML
- **Selector de archivos con hotkeys** (1-9 para selección rápida)
- **Gestor de tags inteligente** con archivo JSON persistente
- **Selector de imágenes de ejemplo** con múltiples servicios
- **Soporte para múltiples blogs** (notas y mihitas)
- **Procesamiento asíncrono** sin bloquear la interfaz
- **Git integration** automática
- **Extracción automática de tags** desde archivos Obsidian
- **Persistencia de configuración** (tema, preferencias)

## 📋 Requisitos

### Dependencias Python

````bash
pip install -r# Creador de Posts - Obsidian a Hugo (PyQt6)

Aplicación en Python con interfaz gráfica PyQt6 para convertir notas de Obsidian a posts de Hugo para múltiples blogs.

## 🚀 Características

- **Interfaz gráfica moderna** con PyQt6
- **Selector de archivos con hotkeys** (1-9 para selección rápida)
- **Gestor de tags inteligente** con archivo JSON persistente
- **Selector de imágenes de ejemplo** con múltiples servicios
- **Soporte para múltiples blogs** (notas y mihitas)
- **Procesamiento asíncrono** sin bloquear la interfaz
- **Git integration** automática
- **Extracción automática de tags** desde archivos Obsidian

## 📋 Requisitos

### Dependencias Python
```bash
pip install PyQt6 requests
````

### Estructura de directorios esperada

```
/mnt/NFS/blogs/
├── notas/
│   ├── content/post/
│   └── static/
└── mihitas/
    ├── content/posts/
    └── static/

/mnt/windows/FTP/wiki/Obsidian/
├── (archivos .md)
└── Dibujos/img/
    └── (imágenes)
```

## 🎯 Uso

### Modo interactivo (seleccionar archivo en la interfaz)

```bash
python crear_post.py
```

### Modo directo (especificar archivo)

```bash
python crear_post.py /ruta/al/archivo.md
```

### Con archivo específico y todos los blogs preseleccionados

```bash
python crear_post.py /ruta/al/archivo.md --all
```

### Solo con todos los blogs preseleccionados (modo interactivo)

```bash
python crear_post.py --all
```

## 🖼️ Selector de Imágenes

El selector genera imágenes de ejemplo usando servicios gratuitos:

- **Picsum Photos** - Imágenes aleatorias de alta calidad
- **PlaceImg** - Imágenes categorizadas
- **Lorem Picsum ID** - Imágenes específicas por ID

### Uso del selector

```bash
python image_selector.py /directorio/destino
```

## ⌨️ Atajos de Teclado

### Ventana principal

- **1-9**: Seleccionar archivo por número
- **Enter**: Procesar post
- **Escape**: Cancelar/cerrar

### Selector de tags

- **1-9**: Toggle tag por número
- **➕**: Añadir nuevo tag

### Selector de imágenes

- **1-9**: Seleccionar imagen por número
- **Enter**: Descargar imagen seleccionada

## 📁 Archivos

### `crear_post.py`

Aplicación principal con interfaz gráfica completa.

### `image_selector.py`

Selector de imágenes independiente con ejemplos generados.

### `tags.json`

Archivo de configuración de tags que se actualiza automáticamente:

```json
{
  "tags": ["python", "programacion", "tutorial"]
}
```

## 🔧 Configuración

### Blogs soportados

1. **Blog Notas** (`/mnt/NFS/blogs/notas/`)
   - Formato: YAML frontmatter
   - Requiere categoría
   - Directorio: `content/post/`

2. **Blog Mihitas** (`/mnt/NFS/blogs/mihitas/`)
   - Formato: TOML frontmatter
   - Sin categoría requerida
   - Directorio: `content/posts/`

### Personalización

Edita las constantes en `BlogConfig` para ajustar rutas:

```python
class BlogConfig:
    NOTAS = {
        'name': 'notas',
        'dir': '/tu/ruta/blogs/notas',
        'content_dir': '/tu/ruta/blogs/notas/content/post/',
        # ...
    }
```

## 🎨 Características de la Interfaz

### Panel izquierdo - Selector de archivos

- Lista archivos .md del directorio Obsidian
- Ordenados por fecha de modificación
- Hotkeys 1-9 para selección rápida
- Botón refrescar para actualizar lista

### Panel derecho - Configuración

- **Título**: Auto-generado desde nombre de archivo
- **Descripción**: Campo de texto libre
- **Categoría**: Solo para blog notas
- **Tags**: Checkboxes con gestión persistente
- **Blogs**: Selección individual o todos

### Procesamiento

- **Barra de progreso** indeterminada durante procesamiento
- **Log de progreso** con detalles de cada paso
- **Commits automáticos** a git con mensajes aleatorios
- **Limpieza automática** del formulario tras éxito

## 🚨 Manejo de Errores

- **Validación completa** de entrada
- **Timeouts** en descargas de imágenes
- **Fallbacks** para servicios no disponibles
- **Mensajes descriptivos** de error
- **Recuperación elegante** sin crasheos

## 🔄 Flujo de Trabajo

### Modo Interactivo

1. **Ejecutar** `python crear_post.py`
2. **Seleccionar archivo** .md de la lista (hotkeys 1-9)
3. **Revisar título** auto-generado
4. **Añadir descripción** personalizada
5. **Seleccionar tags** existentes o crear nuevos
6. **Elegir blogs** de destino
7. **Procesar** - la app hace el resto automáticamente

### Modo Directo

1. **Ejecutar** `python crear_post.py archivo.md [--all]`
2. **El archivo se carga automáticamente** en la interfaz
3. **Continuar desde el paso 3** del modo interactivo

### Procesamiento Automático

- Convierte sintaxis Obsidian → Hugo
- Copia imágenes referenciadas
- Genera frontmatter apropiado
- Crea estructura de directorios
- Hace commit a git

## 🎯 Ventajas sobre Script Bash Original

- ✅ **Soporte para argumentos** - Modo interactivo Y directo
- ✅ **Interfaz gráfica intuitiva** vs línea de comandos
- ✅ **Selección visual** de archivos y opciones
- ✅ **Gestión persistente** de tags
- ✅ **Hotkeys numerados** para rapidez
- ✅ **Validación en tiempo real** de entrada
- ✅ **Progreso visual** del procesamiento
- ✅ **Manejo robusto** de errores
- ✅ **Threading** para no bloquear UI
- ✅ **Carga automática** de archivos desde argumentos

## 🐛 Troubleshooting

### Error: "tags.json not found"

El archivo se crea automáticamente en la primera ejecución.

### Error: "Directory not exists"

Verifica que las rutas en `BlogConfig` sean correctas.

### Error: "Git commit failed"

Asegúrate de tener credenciales SSH configuradas:

```bash
ssh-add ~/.ssh/keys/github
```

### Imágenes no cargan en selector

Verifica conexión a internet. Los servicios están hardcodeados pero son gratuitos y estables.

## 📝 TODO / Mejoras Futuras

- [ ] Configuración visual de rutas de blogs
- [ ] Preview de markdown antes de procesar
- [ ] Soporte para más formatos de imagen
- [ ] Integración con servicios de imágenes con API
- [ ] Plantillas de frontmatter personalizables
- [ ] Historial de posts creados
- [ ] Dark theme toggle

## 📄 Licencia

MIT License - Ver archivo LICENSE para detalles.
