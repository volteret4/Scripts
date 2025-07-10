# VVMM Post Creator

Creador automático de posts para blogs musicales usando Hugo. Integra múltiples servicios musicales y automatiza todo el flujo desde la obtención de metadatos de la canción en reproducción hasta la publicación del post.

## 🎵 Características

- **Detección automática** de música en reproducción (Deadbeef, Strawberry)
- **Integración con servicios musicales**: Spotify, Discogs, Last.fm, YouTube, MusicBrainz, Bandcamp, Wikipedia
- **Descarga automática** de carátulas de álbumes
- **Gestión de playlists** de Spotify
- **Generación automática** de posts en Hugo
- **Publicación automática** en Git/GitHub
- **Interfaz gráfica** para selección de tags y playlists

## 📁 Estructura del Proyecto

```
vvmm-post-creator/
├── vvmm_post_creator.sh          # Script principal
├── setup.sh                      # Script de instalación
├── .env                          # Variables de entorno (crear desde template)
├── .content/
│   ├── logs/                     # Logs de la aplicación
│   └── cache/                    # Cache y archivos temporales
├── modules/                      # Módulos de funcionalidad
│   ├── bandcamp.py
│   ├── spotify.py
│   ├── discogs.py
│   ├── caratula-spotify.py
│   ├── sp_menu_playlists.py
│   └── ...
└── README.md                     # Esta documentación
```

## 🚀 Instalación Rápida

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd vvmm-post-creator
```

### 2. Ejecutar el script de instalación
```bash
chmod +x setup.sh
./setup.sh
```

### 3. Configurar credenciales de API
Edita el archivo `.env` y añade tus credenciales:
```bash
nano .env
```

### 4. Verificar instalación
```bash
./vvmm_post_creator.sh --validate-only
```

## 🔧 Requisitos del Sistema

### Comandos requeridos
- `python3` y `pip3`
- `hugo`
- `git`
- `yad` (para interfaces gráficas)
- `notify-send` (para notificaciones)
- `qutebrowser` (para preview)
- `curl` y `jq`

### Reproductores de música soportados
- **Deadbeef** (preferido)
- **Strawberry Music Player**
- Cualquier reproductor compatible con `playerctl`

### Python Dependencies
Se instalan automáticamente en un entorno virtual:
- `spotipy`
- `python-dotenv`
- `requests`
- `beautifulsoup4`
- `lxml`
- `google-api-python-client`
- `wikipediaapi`

## 🔑 Configuración de APIs

### Spotify API
1. Ve a [Spotify Dashboard](https://developer.spotify.com/dashboard/)
2. Crea una nueva aplicación
3. Obtén `Client ID` y `Client Secret`
4. Configura redirect URI: `http://127.0.0.1:8090`

### Discogs API
1. Ve a [Discogs Developers](https://www.discogs.com/settings/developers)
2. Genera un token personal
3. Añádelo a tu `.env`

### Last.fm API (Opcional)
1. Ve a [Last.fm API](https://www.last.fm/api/account/create)
2. Crea una cuenta de desarrollador
3. Obtén tu API key

### YouTube API (Opcional)
1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un proyecto y habilita YouTube Data API v3
3. Crea credenciales (API key)

## ⚙️ Configuración

### Archivo .env
```bash
# APIs requeridas
SPOTIFY_CLIENT=tu_spotify_client_id
SPOTIFY_SECRET=tu_spotify_client_secret
DISCOGS_TOKEN=tu_discogs_token

# APIs opcionales
LASTFM_API_KEY=tu_lastfm_api_key
YT_TOKEN=tu_youtube_api_key

# Configuración del entorno
PYTHON_VENV_PATH=./venv
ENABLE_PREVIEW=true
ENABLE_GIT_PUSH=true
DEBUG_MODE=false
```

### Rutas importantes
- **Blog Hugo**: `/mnt/NFS/blogs/vvmm`
- **Script de reproducción**: `/home/huan/Scripts/utilities/aliases/en_reproduccion.sh`
- **Menú de playlists**: `/home/huan/Scripts/menus/spotify/sp_menu_playlists.py`

## 🎮 Uso

### Uso básico
```bash
# Crear post basado en música actual
./vvmm_post_creator.sh

# Con debug activado
./vvmm_post_creator.sh --debug

# Sin preview del sitio
./vvmm_post_creator.sh --no-preview

# Sin publicación en Git
./vvmm_post_creator.sh --no-git
```

### Opciones disponibles
- `--help`: Mostrar ayuda
- `--debug`: Activar modo debug
- `--no-preview`: Deshabilitar preview del sitio
- `--no-git`: Deshabilitar push a GitHub
- `--validate-only`: Solo validar entorno

### Flujo de trabajo
1. **Reproduce música** en tu reproductor favorito
2. **Ejecuta el script** principal
3. **Selecciona tags** en la interfaz gráfica
4. **Elige playlist** de Spotify (opcional)
5. **Revisa el preview** del post generado
6. **Publicación automática** en Hugo y Git

## 📝 Estructura del Post Generado

Cada post incluye:
- **Carátula del álbum** (descargada automáticamente)
- **Enlaces a servicios musicales** (Spotify, Discogs, etc.)
- **Información del álbum** (desde Discogs)
- **Tracklist completa** con colaboraciones
- **Tags personalizados**
- **Metadatos Hugo** apropiados

## 🔧 Personalización

### Añadir nuevos servicios musicales
1. Crear script en `modules/nuevo_servicio.py`
2. Añadir llamada en `search_music_services()`
3. Actualizar `generate_service_links()`

### Modificar formato de posts
Edita las funciones de generación de contenido:
- `add_content_to_post()`
- `add_discogs_info()`
- `format_post_content()`

### Personalizar interfaz gráfica
Modifica `modules/sp_menu_playlists.py` para cambiar la apariencia del menú de playlists.

## 📊 Logs y Debug

### Ubicación de logs
- **Logs generales**: `.content/logs/vvmm_YYYYMMDD.log`
- **Logs de errores**: `.content/logs/errors_YYYYMMDD.log`
- **Logs de Hugo**: `.content/logs/hugo_server.log`

### Modo debug
```bash
./vvmm_post_creator.sh --debug
```
Proporciona información detallada sobre:
- Búsquedas en APIs
- Contenido de archivos generados
- Estados de procesos
- Información de validación

## 🐛 Solución de Problemas

### Error: "No se encontró metadata de reproducción"
- Verifica que el reproductor esté funcionando
- Asegúrate de que deadbeef o strawberry estén instalados
- Comprueba la ruta del script `en_reproduccion.sh`

### Error: "Token de Spotify inválido"
- Regenera el token ejecutando `modules/sp_playlist.py`
- Verifica las credenciales en `.env`
- Asegúrate de que el redirect URI esté configurado

### Error: "No se puede descargar carátula"
- Verifica conexión a internet
- Comprueba tokens de APIs
- Revisa logs para errores específicos

### Posts duplicados
El sistema verifica automáticamente posts existentes por nombre de archivo.

## 🔄 Actualizaciones

### Actualizar dependencias Python
```bash
source ./venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Actualizar Hugo
Sigue las instrucciones oficiales de [Hugo](https://gohugo.io/getting-started/installing/).

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia [MIT](LICENSE).

## 📞 Soporte

- **Issues**: Reporta bugs o solicita features en GitHub Issues
- **Wiki**: Documentación adicional en GitHub Wiki
- **Discussions**: Preguntas y discusiones en GitHub Discussions

## 🙏 Agradecimientos

- **Hugo** por el excelente generador de sitios estáticos
- **Spotify API** por el acceso a metadatos musicales
- **Discogs API** por la información detallada de álbumes
- **Deadbeef** y **Strawberry** por el soporte de reproducción

---

Hecho con ❤️ por [volteret4](https://github.com/volteret4)