# 🎵 Concert Bot - Bot de Telegram para Búsqueda de Conciertos

Un bot de Telegram avanzado que permite buscar conciertos, gestionar artistas favoritos y recibir notificaciones automáticas de nuevos eventos.

## ✨ Características

### 🔍 Búsqueda de Conciertos

- **Múltiples fuentes**: Ticketmaster, Spotify y Setlist.fm
- **Búsqueda por país**: Personalizada según tu ubicación
- **Resultados en tiempo real**: Con enlaces directos a entradas

### ⭐ Gestión de Favoritos

- **Artistas favoritos**: Guarda tus artistas preferidos
- **Notificaciones personalizadas**: Activar/desactivar por artista
- **Gestión completa**: Añadir, eliminar y configurar notificaciones

### 🔔 Notificaciones Automáticas

- **Búsquedas diarias**: Automáticas a las 9:00 AM
- **Alertas inmediatas**: Cuando hay nuevos conciertos
- **Control granular**: Por usuario y por artista

### 🌍 Configuración Personal

- **País personalizable**: Para búsquedas localizadas
- **Idioma**: Soporte multiidioma
- **Estadísticas**: Seguimiento de tu actividad

## 🚀 Instalación

### Requisitos Previos

- Python 3.8 o superior
- Token de bot de Telegram (obtener de @BotFather)
- APIs opcionales para mayor funcionalidad

### 1. Clonar y Preparar

```bash
# Clonar el repositorio
git clone <tu-repositorio>
cd concert-bot

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configuración

Crear archivo `.env` con tus credenciales:

```env
# OBLIGATORIO - Token del bot de Telegram
TELEGRAM_BOT_TOKEN=tu_token_aqui

# OPCIONALES - APIs para mayor funcionalidad
TICKETMASTER_API_KEY=tu_api_key_ticketmaster
SPOTIFY_CLIENT_ID=tu_spotify_client_id
SPOTIFY_CLIENT_SECRET=tu_spotify_client_secret
SETLISTFM_API_KEY=tu_setlistfm_api_key

# CONFIGURACIÓN OPCIONAL
CONCERT_BOT_DB_PATH=concert_bot.db
LOG_LEVEL=INFO
```

### 3. Obtener APIs (Opcional pero Recomendado)

#### Ticketmaster API

1. Ir a [Ticketmaster Developer](https://developer.ticketmaster.com/)
2. Crear cuenta y obtener API Key
3. Añadir a `.env` como `TICKETMASTER_API_KEY`

#### Spotify API

1. Ir a [Spotify for Developers](https://developer.spotify.com/)
2. Crear aplicación y obtener Client ID y Secret
3. Añadir a `.env` como `SPOTIFY_CLIENT_ID` y `SPOTIFY_CLIENT_SECRET`

#### Setlist.fm API

1. Ir a [Setlist.fm API](https://api.setlist.fm/)
2. Solicitar API Key
3. Añadir a `.env` como `SETLISTFM_API_KEY`

### 4. Ejecutar

```bash
# Sistema completo (recomendado)
python main.py

# Solo bot de Telegram
python main.py bot

# Solo búsquedas programadas
python main.py scheduler

# Solo inicializar base de datos
python main.py init-db
```

## 📱 Comandos del Bot

### Comandos Básicos

- `/start` - Iniciar y registrarse
- `/help` - Mostrar ayuda
- `/b <artista>` - Buscar conciertos para un artista

### Gestión de Favoritos

- `/fav <artista>` - Añadir artista a favoritos
- `/favoritos` - Ver y gestionar artistas favoritos

### Configuración

- `/pais` - Configurar tu país
- `/notificaciones` - Activar/desactivar notificaciones
- `/stats` - Ver tus estadísticas

### Ejemplos de Uso

```
/b Metallica
/fav Coldplay
/pais
/notificaciones
```

## 🗂️ Estructura del Proyecto

```
concert-bot/
├── main.py                    # Lanzador principal
├── database_manager.py        # Gestión de base de datos
├── scheduled_search_manager.py # Búsquedas automáticas
├── enhanced_telegram_bot.py   # Bot de Telegram mejorado
├── telegram_bot.py           # Bot original (referencia)
├── apis/                     # Servicios de APIs
│   ├── ticketmaster.py
│   ├── spotify.py
│   ├── setlistfm.py
│   └── mb_artist_info.py
├── requirements.txt          # Dependencias
├── .env                     # Configuración (crear)
├── cache/                   # Cache de búsquedas
└── concert_bot.db          # Base de datos (se crea automáticamente)
```

## 🗄️ Base de Datos

El bot usa SQLite con las siguientes tablas:

### `users`

- Información de usuarios de Telegram
- Configuración personal (país, notificaciones)

### `user_artists`

- Artistas favoritos por usuario
- Estado de notificaciones por artista

### `concerts`

- Conciertos encontrados
- Deduplicación automática

### `notifications_sent`

- Historial de notificaciones enviadas
- Evita duplicados

### `scheduled_searches`

- Búsquedas programadas
- Control de frecuencia

## ⚙️ Configuración Avanzada

### Variables de Entorno

```env
# Base de datos
CONCERT_BOT_DB_PATH=./data/concert_bot.db

# Logging
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR

# Configuración del bot
MAX_CONCERTS_PER_SERVICE=5
SEARCH_TIMEOUT=30
```

### Programación de Búsquedas

Las búsquedas automáticas se ejecutan:

- **Diariamente a las 9:00 AM**
- **Solo para artistas con usuarios activos**
- **Con deduplicación automática**

### Cache

- **Duración**: 24 horas por defecto
- **Ubicación**: `./cache/`
- **Limpieza automática**: Semanal

## 🔧 Resolución de Problemas

### Bot no responde

1. Verificar `TELEGRAM_BOT_TOKEN` en `.env`
2. Comprobar conexión a Internet
3. Revisar logs en `concert_bot_main.log`

### No encuentra conciertos

1. Verificar APIs configuradas en `.env`
2. Probar con artistas conocidos
3. Verificar configuración de país

### Notificaciones no llegan

1. Verificar que las notificaciones están activadas (`/notificaciones`)
2. Comprobar que el artista está en favoritos (`/favoritos`)
3. Verificar logs de búsquedas programadas

### Errores de base de datos

```bash
# Reinicializar base de datos
python main.py init-db
```

## 📊 Monitoreo

### Logs

- `concert_bot_main.log` - Log principal
- `scheduled_searches.log` - Log de búsquedas automáticas

### Estadísticas de Usuario

```
/stats
```

Muestra:

- Artistas favoritos
- Conciertos próximos
- Notificaciones enviadas
- Configuración actual

## 🔒 Privacidad y Datos

### Datos Almacenados

- **ID de Telegram** (para identificación)
- **Nombre de usuario** (opcional, para logs)
- **Artistas favoritos**
- **Configuración personal** (país, notificaciones)

### Datos NO Almacenados

- **Mensajes privados**
- **Información personal sensible**
- **Historial de búsquedas manuales**

### Cumplimiento GDPR

- **Exportación de datos**: Disponible por comando
- **Eliminación**: Los usuarios pueden eliminar sus datos
- **Consentimiento**: Registro explícito requerido

## 🔄 Actualizaciones

### Actualizar el Bot

```bash
git pull
pip install -r requirements.txt --upgrade
python main.py
```

### Migración de Datos

La base de datos se actualiza automáticamente al iniciar.

## 🤝 Contribuir

### Desarrollo

1. Fork del repositorio
2. Crear rama feature: `git checkout -b nueva-caracteristica`
3. Commit cambios: `git commit -am 'Añadir nueva característica'`
4. Push a la rama: `git push origin nueva-caracteristica`
5. Crear Pull Request

### Reportar Bugs

Usar GitHub Issues con:

- Descripción detallada
- Pasos para reproducir
- Logs relevantes
- Información del sistema

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 🙏 Agradecimientos

- **Telegram Bot API** - Framework de bots
- **Ticketmaster API** - Datos de conciertos
- **Spotify API** - Información de artistas
- **Setlist.fm API** - Setlists y fechas de conciertos
- **MusicBrainz** - Metadatos musicales

## 📞 Soporte

- **Issues**: GitHub Issues
- **Documentación**: Este README
- **Logs**: Revisar archivos de log para diagnósticos

---

¡Disfruta descubriendo nuevos conciertos! 🎵🎸🥁
