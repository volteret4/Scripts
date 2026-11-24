# 🎵 Bandcamp HTML Generator V2 - Documentación

## 🆕 Novedades de la Versión 2

### Cambios Principales:

1. **✅ --include-read**: Procesa también correos ya leídos
2. **✅ --delete**: Opción para eliminar correos después de procesarlos
3. **✅ Botones de acción**: Cada embed tiene botones para marcar como leído y eliminar
4. **✅ API Server**: Servidor Flask para gestionar acciones desde la interfaz web
5. **✅ Sesión persistente**: Mantiene la conexión IMAP abierta sin pedir contraseña repetidamente
6. **✅ Generador de índice separado**: Script independiente para crear index.html

---

## 📦 Archivos Incluidos

### Scripts Principales:

1. **bc_html_generator_imap_v2.py** - Procesador de correos (versión mejorada)
2. **generate_index.py** - Generador de índice HTML
3. **api_server.py** - Servidor API para botones de acción

### Documentación:

4. **README_V2.md** - Este archivo
5. Resto de documentación original (FAQ, CONFIGURACION_PROVEEDORES, etc.)

---

## 🚀 Guía de Uso Rápida

### Paso 1: Procesar Correos

```bash
# Procesar solo correos NO leídos (default)
python3 bc_html_generator_imap_v2.py \
  --server imap.gmail.com \
  --email tu@gmail.com \
  --folders "INBOX/Music:Rock"

# Procesar TODOS los correos (incluyendo leídos)
python3 bc_html_generator_imap_v2.py \
  --server imap.gmail.com \
  --email tu@gmail.com \
  --folders "INBOX/Music:Rock" \
  --include-read

# Eliminar correos después de procesar (¡CUIDADO!)
python3 bc_html_generator_imap_v2.py \
  --server imap.gmail.com \
  --email tu@gmail.com \
  --folders "INBOX/Music:Rock" \
  --delete
```

### Paso 2: Generar Índice

```bash
# Leer carpeta bandcamp_html y generar index.html
python3 generate_index.py

# O especificar carpeta diferente
python3 generate_index.py /ruta/a/tu/coleccion
```

### Paso 3: Iniciar API Server (opcional, para botones)

```bash
# Instalar dependencias primero
pip install flask flask-cors --break-system-packages

# Iniciar servidor
python3 api_server.py
```

El servidor se ejecutará en `http://localhost:5000`

---

## 📋 Nuevas Opciones de Línea de Comandos

### bc_html_generator_imap_v2.py

```bash
# Opciones nuevas:
--include-read        # Incluye correos ya leídos (default: solo no leídos)
--delete              # Elimina correos después de procesarlos
--no-mark-read        # NO marca correos como leídos

# Ejemplos:
--include-read --no-mark-read    # Procesa todos sin modificarlos
--include-read --delete           # Procesa todos y los elimina
--delete                          # Solo procesa no leídos y los elimina
```

### generate_index.py

```bash
# Uso básico:
python3 generate_index.py [DIRECTORIO]

# Ejemplos:
python3 generate_index.py                    # Usa bandcamp_html/
python3 generate_index.py mi_coleccion       # Usa mi_coleccion/
python3 generate_index.py /path/absoluto     # Usa ruta absoluta

# Con directorio de salida diferente:
python3 generate_index.py mi_coleccion --output otra_carpeta
```

---

## 🎯 Flujo de Trabajo Completo

### Flujo Simple (Sin API):

```bash
# 1. Procesar correos
python3 bc_html_generator_imap_v2.py --interactive

# 2. Generar índice
python3 generate_index.py

# 3. Abrir en navegador
open bandcamp_html/index.html
```

### Flujo Completo (Con API y Botones):

```bash
# 1. Instalar dependencias del API
pip install flask flask-cors --break-system-packages

# 2. Procesar correos (mantener sesión abierta)
python3 bc_html_generator_imap_v2.py --interactive

# 3. Generar índice
python3 generate_index.py

# 4. Iniciar servidor API (en otra terminal)
python3 api_server.py

# 5. Abrir en navegador
# Abre http://localhost:5000/index.html
```

---

## 🔘 Botones de Acción en la Interfaz

Cada embed en los archivos HTML tiene dos botones:

### 1. 📖 Marcar como leído

- Marca el correo original como leído en el servidor IMAP
- No requiere recargar la página
- Muestra notificación de confirmación

### 2. 🗑️ Eliminar

- Elimina el correo original del servidor IMAP permanentemente
- Pide confirmación antes de eliminar
- Oculta el embed de la página tras eliminar

**Nota:** Los botones solo funcionan si el API server está ejecutándose.

---

## 🔧 Configuración del API Server

### Instalación de Dependencias:

```bash
pip install flask flask-cors --break-system-packages
```

### Configuración:

El servidor API usa puerto 5000 por defecto. Para cambiar:

```python
# Edita api_server.py, última línea:
app.run(host='0.0.0.0', port=TU_PUERTO, debug=True)
```

### Endpoints Disponibles:

#### POST /api/mark-read

Marca un correo como leído.

**Body:**

```json
{
  "server": "imap.gmail.com",
  "port": 993,
  "email": "tu@email.com",
  "emailId": "123",
  "folder": "INBOX"
}
```

#### POST /api/delete-email

Elimina un correo.

**Body:**

```json
{
  "server": "imap.gmail.com",
  "port": 993,
  "email": "tu@email.com",
  "emailId": "123",
  "folder": "INBOX"
}
```

#### POST /api/create-session

Crea una sesión IMAP explícitamente.

**Body:**

```json
{
  "server": "imap.gmail.com",
  "port": 993,
  "email": "tu@email.com",
  "password": "tu_contraseña"
}
```

#### GET /api/sessions

Lista sesiones activas (debugging).

---

## 🔐 Gestión de Sesiones

### Cómo Funciona:

1. La primera petición crea una sesión IMAP
2. La sesión se guarda en memoria del servidor
3. Peticiones subsiguientes usan la sesión existente
4. No necesitas volver a introducir la contraseña
5. Sesiones inactivas (>30 min) se limpian automáticamente

### Ventajas:

- ✅ No necesitas contraseña en cada petición
- ✅ Más rápido (reutiliza conexión)
- ✅ Más seguro (contraseña solo una vez)

### Limitaciones:

- ⚠️ Las sesiones se pierden si reinicias el servidor
- ⚠️ El servidor guarda sesiones en memoria (no persistente)
- ⚠️ Para producción, considera usar Redis o similar

---

## 🗂️ Estructura de Archivos Generados

```
bandcamp_html/
├── index.html              # Índice principal (generado por generate_index.py)
├── Rock.html               # Género Rock con botones de acción
├── Electronic.html         # Género Electronic con botones
├── Jazz.html               # Género Jazz con botones
└── Metal.html              # Etc.
```

Cada archivo de género:

- Contiene todos los embeds del género
- Incluye botones de marcar leído y eliminar
- Tiene paginación si hay muchos discos
- Incluye metadata de conexión IMAP para el API

---

## 💡 Casos de Uso

### Caso 1: Limpiar Bandeja (Procesar y Eliminar)

```bash
# Procesa correos y los elimina
python3 bc_html_generator_imap_v2.py \
  --server imap.gmail.com \
  --email tu@gmail.com \
  --folders "INBOX:Bandcamp" \
  --delete

python3 generate_index.py
```

**Útil para:** Mantener la bandeja limpia mientras archivas la música.

### Caso 2: Archivar Sin Modificar

```bash
# Procesa todos los correos sin marcar ni eliminar
python3 bc_html_generator_imap_v2.py \
  --server imap.gmail.com \
  --email tu@gmail.com \
  --folders "INBOX:Bandcamp" \
  --include-read \
  --no-mark-read

python3 generate_index.py
```

**Útil para:** Crear archivo HTML sin tocar los correos originales.

### Caso 3: Revisión Incremental

```bash
# Primera vez: procesa no leídos, marca como leídos
python3 bc_html_generator_imap_v2.py --interactive

# Siguientes veces: solo procesa nuevos (no leídos)
python3 bc_html_generator_imap_v2.py --interactive

# Regenerar índice cada vez
python3 generate_index.py
```

**Útil para:** Ir añadiendo música nueva periódicamente.

### Caso 4: Gestión Activa con Botones

```bash
# 1. Procesar todos sin eliminar
python3 bc_html_generator_imap_v2.py \
  --interactive \
  --include-read \
  --no-mark-read

# 2. Generar índice
python3 generate_index.py

# 3. Iniciar API
python3 api_server.py

# 4. Abrir navegador y usar botones para gestionar
```

**Útil para:** Gestionar correos desde la interfaz web, eliminando uno a uno.

---

## ⚠️ Advertencias Importantes

### Sobre --delete:

```bash
⚠️  ¡CUIDADO! --delete ELIMINA CORREOS PERMANENTEMENTE

El script pedirá confirmación explícita:
- Debes escribir 'SI' (en mayúsculas) para confirmar
- Los correos eliminados NO se pueden recuperar
- Asegúrate de tener backup si es importante
```

### Sobre Sesiones:

```bash
ℹ️  Las sesiones IMAP son mantenidas por el API server

- Si cierras el API server, pierdes las sesiones
- Si reinicias el servidor, debes volver a autenticar
- Las sesiones se limpian automáticamente tras 30 min de inactividad
```

### Sobre Seguridad:

```bash
🔒 IMPORTANTE: Seguridad del API Server

- El API server NO tiene autenticación
- Cualquiera con acceso al puerto puede usarlo
- Solo para uso LOCAL, no expongas a internet
- En producción, añade autenticación/autorización
```

---

## 🐛 Solución de Problemas

### Los botones no funcionan

**Causa:** API server no está ejecutándose

**Solución:**

```bash
# Terminal 1: Iniciar API server
python3 api_server.py

# Terminal 2: Abrir navegador
# http://localhost:5000/index.html
```

### Error "Module 'flask' not found"

**Causa:** Flask no instalado

**Solución:**

```bash
pip install flask flask-cors --break-system-packages
```

### "API no disponible" en navegador

**Causa:** Los archivos HTML están abiertos como file:// en vez de http://

**Solución:**

```bash
# En vez de abrir directamente:
open bandcamp_html/index.html  # ❌

# Usa el API server:
python3 api_server.py
# Luego abre: http://localhost:5000/index.html  # ✅
```

### "Authentication failed" después de crear sesión

**Causa:** Sesión expiró o servidor reiniciado

**Solución:**

1. Reiniciar el API server
2. Recargar la página
3. Intentar de nuevo (creará nueva sesión)

### generate_index.py no encuentra géneros

**Causa:** Los archivos HTML no tienen el formato esperado

**Solución:**

1. Verifica que los archivos sean generados por bc_html_generator_imap_v2.py
2. No edites manualmente los archivos HTML
3. Regenera los archivos si es necesario

---

## 📊 Comparación V1 vs V2

| Característica     | Versión 1 | Versión 2            |
| ------------------ | --------- | -------------------- |
| Procesar correos   | ✅        | ✅                   |
| Generar HTML       | ✅        | ✅                   |
| Marcar como leído  | ✅        | ✅                   |
| Incluir ya leídos  | ❌        | ✅                   |
| Eliminar correos   | ❌        | ✅                   |
| Botones de acción  | ❌        | ✅                   |
| API Server         | ❌        | ✅                   |
| Sesión persistente | ❌        | ✅                   |
| Índice separado    | ❌        | ✅                   |
| Genera index.html  | ✅        | ✅ (script separado) |

---

## 🔄 Migración desde V1

Si ya usas la V1:

1. **Tus archivos HTML actuales son compatibles** con generate_index.py
2. **No necesitas regenerar todo**, solo usar generate_index.py
3. **Para usar botones**, necesitas regenerar con V2 y usar API server

**Proceso:**

```bash
# Opción A: Mantener lo que tienes + generar índice
python3 generate_index.py bandcamp_html

# Opción B: Regenerar todo con V2 (incluye botones)
python3 bc_html_generator_imap_v2.py --interactive --include-read
python3 generate_index.py
```

---

## 🎓 Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     FLUJO COMPLETO V2                       │
└─────────────────────────────────────────────────────────────┘

1. PROCESAMIENTO:
   bc_html_generator_imap_v2.py
   ↓
   Conecta a IMAP → Lee correos → Extrae Bandcamp → Genera HTMLs
   ↓
   bandcamp_html/Rock.html, Electronic.html, etc.

2. ÍNDICE:
   generate_index.py
   ↓
   Lee HTMLs en carpeta → Extrae info → Genera index.html
   ↓
   bandcamp_html/index.html

3. API (OPCIONAL):
   api_server.py
   ↓
   Servidor Flask en puerto 5000
   ↓
   Gestiona sesiones IMAP → Procesa peticiones de botones
   ↓
   Botones en HTML funcionan

4. USUARIO:
   Navegador → http://localhost:5000/index.html
   ↓
   Navega géneros → Escucha música → Usa botones de acción
```

---

## 📝 Próximos Pasos

1. Lee esta documentación completa
2. Prueba el flujo básico sin API
3. Si te gusta, instala Flask y prueba el API
4. Explora las opciones avanzadas (--include-read, --delete)
5. Automatiza con cron/scripts si quieres

---

## 🆘 Soporte

- **Documentación completa:** Este archivo (README_V2.md)
- **Configuración proveedores:** CONFIGURACION_PROVEEDORES.md
- **Preguntas frecuentes:** FAQ.md
- **Ayuda comando:** `python3 script.py --help`

---

## ✨ Créditos

Versión 2 creada con mejoras solicitadas:

- Soporte para correos leídos
- Opción de eliminar
- Botones de acción interactivos
- API server para gestión en tiempo real
- Generador de índice independiente

**¡Disfruta tu colección de Bandcamp mejorada! 🎵**
