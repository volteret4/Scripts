# Music Web Explorer - Versión Unificada

Una aplicación web para explorar y gestionar tu colección de música, ahora completamente unificada en un solo servidor con soporte para Docker.

## 🏗️ Arquitectura Unificada

- **Servidor único**: Todo funciona en un mismo contenedor/servidor
- **Flask + Nginx**: Flask para la API y lógica, Nginx como proxy reverso
- **Base de datos local**: SQLite con toda la información de la colección
- **Sin acceso directo a archivos**: La app solo lee la base de datos
- **Descargas SSH**: Comandos `rsync` independientes al servidor pepecono como usuario `dietpi`
- **Docker ready**: Fácil despliegue con contenedores

## 📁 Estructura del Proyecto

```
music-web-explorer/
├── app.py                    # Aplicación Flask principal
├── music_manager.py          # Utilidades de gestión
├── config.ini               # Configuración unificada
├── requirements.txt          # Dependencias Python
├── templates/
│   └── index.html           # Interfaz web
├── docker/
│   ├── nginx.conf           # Configuración Nginx
│   ├── supervisord.conf     # Configuración Supervisor
│   └── entrypoint.sh        # Script de inicio del contenedor
├── Dockerfile               # Definición del contenedor
├── docker-compose.yml       # Orquestación con Docker Compose
├── start_unified.sh         # Inicio sin Docker
└── README_UNIFIED.md        # Esta documentación
```

## 🚀 Instalación y Uso

### Opción 1: Con Docker (Recomendado)

1. **Clonar o copiar archivos**:
   ```bash
   # Crear directorio del proyecto
   mkdir music-web-explorer
   cd music-web-explorer
   
   # Copiar todos los archivos del proyecto aquí
   ```

2. **Ajustar docker-compose.yml**:
   ```yaml
   volumes:
     # Ajusta estas rutas según tu sistema:
     - /ruta/a/tu/musica.sqlite:/app/data/musica.sqlite:ro
     - ~/.ssh:/home/dietpi/.ssh:ro  # Claves SSH para acceso a pepecono
     - ./downloads:/downloads
     - ./logs:/app/logs
   ```

3. **Construir y ejecutar**:
   ```bash
   # Construir imagen
   docker-compose build
   
   # Iniciar servicios
   docker-compose up -d
   
   # Ver logs
   docker-compose logs -f
   ```

4. **Acceder a la aplicación**:
   - Web: http://localhost:8447
   - API directa: http://localhost:5157
   - Health check: http://localhost/health.html

### Opción 2: Sin Docker

1. **Instalar dependencias**:
   ```bash
   # Python y pip
   sudo apt update
   sudo apt install python3 python3-pip sqlite3
   
   # Dependencias Python
   pip3 install -r requirements.txt
   ```

2. **Configurar config.ini**:
   ```ini
   [database]
   path = /ruta/completa/a/tu/musica.sqlite
   
   [music]
   root_path = /ruta/completa/a/tu/coleccion
   
   [download]
   path = ./downloads
   source_type = local
   ```

3. **Ejecutar**:
   ```bash
   # Método simple
   ./start_unified.sh
   
   # O manualmente
   python3 app.py
   ```

## ⚙️ Configuración

### config.ini Principal

```ini
[database]
path = /app/data/musica.sqlite  # Ruta a tu BD SQLite

[music]
root_path = /app/music          # Ruta a tu colección

[download]
path = /downloads           # Donde se guardan descargas
source_type = local             # 'local' o 'ssh'
# Para SSH (opcional):
# ssh_host = servidor.remoto.com
# ssh_user = tu_usuario

[web]
port = 5157
host = 0.0.0.0
debug = false

[logging]
level = INFO
file = /app/logs/music_web.log
```

### Tipos de Descarga

1. **Local (`source_type = local`)**:
   - Copia directa de archivos en el mismo servidor
   - Más rápido y eficiente
   - Usa `cp` o `shutil` internamente

2. **SSH (`source_type = ssh`)**:
   - Descarga desde servidor remoto via SSH
   - Requiere configurar `ssh_host` y `ssh_user`
   - Usa `rsync` con claves SSH

## 🐳 Docker: Detalles Técnicos

### Volúmenes Importantes

```yaml
volumes:
  # Base de datos (solo lectura)
  - ./data/musica.sqlite:/app/data/musica.sqlite:ro
  
  # Colección musical (solo lectura)  
  - /mnt/musica:/app/music:ro
  
  # Descargas (lectura/escritura)
  - ./downloads:/downloads
  
  # Logs (lectura/escritura)
  - ./logs:/app/logs
  
  # SSH keys (opcional, solo lectura)
  - ~/.ssh:/root/.ssh:ro
```

### Puertos

- **8447**: Nginx (interfaz web principal)
- **5157**: Flask API (acceso directo opcional)

### Servicios Internos

- **Supervisor**: Gestiona nginx + flask
- **Nginx**: Proxy reverso y archivos estáticos
- **Flask**: API y lógica de aplicación

## 🔧 Funcionalidades

### Características Principales

- ✅ **Búsqueda de artistas** en tiempo real
- ✅ **Exploración de álbumes** con imágenes
- ✅ **Navegador de carpetas** de música
- ✅ **Estadísticas** de la colección
- ✅ **Descarga de álbumes** (local o SSH)
- ✅ **Interfaz responsive** para móvil
- ✅ **API REST** completa
- ✅ **Health checks** integrados

### API Endpoints

```
GET  /                          # Interfaz web
GET  /api/stats                 # Estadísticas generales
GET  /api/search/artists?q=...  # Buscar artistas
GET  /api/artist/<id>           # Detalles de artista
GET  /api/album/<id>            # Detalles de álbum
POST /api/album/<id>/download   # Descargar álbum
GET  /api/download/<id>/status  # Estado de descarga
GET  /api/folders?path=...      # Explorar carpetas
```

## 📊 Monitoreo y Logs

### Archivos de Log

```bash
# Ver todos los logs
docker-compose logs -f

# Logs específicos
tail -f logs/music_web.log      # Aplicación Flask
tail -f logs/nginx_access.log   # Accesos web
tail -f logs/nginx_error.log    # Errores Nginx
tail -f logs/supervisord.log    # Supervisor
```

### Health Checks

```bash
# Verificar estado del contenedor
docker-compose ps

# Health check manual
curl http://localhost/health.html

# Verificar API
curl http://localhost/api/stats
```

## 🛠️ Desarrollo y Debugging

### Ejecutar en modo desarrollo

```bash
# Modificar config.ini
[web]
debug = true

# Reiniciar
docker-compose restart

# Ver logs en tiempo real
docker-compose logs -f music-web-explorer
```

### Acceso al contenedor

```bash
# Shell en el contenedor
docker-compose exec music-web-explorer bash

# Ver procesos
docker-compose exec music-web-explorer ps aux

# Ver archivos
docker-compose exec music-web-explorer ls -la /app
```

## 🔒 Seguridad

### Recomendaciones

1. **Base de datos**: Solo lectura desde la aplicación
2. **Colección musical**: Solo lectura, protege tus archivos
3. **SSH keys**: Solo lectura si usas descarga SSH
4. **Red**: Usa proxy reverso (nginx) para SSL en producción
5. **Backups**: Haz backup regular de downloads y logs

### Firewalls

```bash
# Solo permitir puertos necesarios
ufw allow 80
ufw allow 443  # Si usas SSL
# NO abrir 5157 externamente a menos que sea necesario
```

## 🚨 Troubleshooting

### Problemas Comunes

1. **Base de datos no encontrada**:
   ```bash
   # Verificar volumen
   docker-compose exec music-web-explorer ls -la /app/data/
   ```

2. **Colección musical vacía**:
   ```bash
   # Verificar montaje
   docker-compose exec music-web-explorer ls -la /app/music/
   ```

3. **Permisos de descarga**:
   ```bash
   # Verificar permisos
   docker-compose exec music-web-explorer ls -la /downloads/
   chmod 755 downloads/
   ```

4. **Puerto ocupado**:
   ```bash
   # Ver qué usa el puerto
   sudo netstat -tulpn | grep :80
   # Cambiar puerto en docker-compose.yml
   ```

### Comandos Útiles

```bash
# Reconstruir completamente
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Ver uso de recursos
docker stats music-web-explorer

# Limpiar todo
docker-compose down -v
docker rmi music-web-explorer_music-web-explorer
```

## 📋 TODO / Roadmap

- [ ] Soporte para múltiples formatos de BD
- [ ] Integración con servicios de streaming
- [ ] Player de música integrado
- [ ] Gestión de playlists
- [ ] API de sincronización automática
- [ ] Interfaz de administración
- [ ] Soporte para múltiples usuarios

---

**¡Tu música, tu servidor, tu control total!** 🎵