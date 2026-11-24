#!/usr/bin/env python3
"""Script para generar main.py actualizado con soporte multi-reproductor"""

# Leer archivo original
with open('main.py', 'r', encoding='utf-8') as f:
    original = f.read()

# Nuevo import para music_players
new_import = """
# Módulo de detección de reproductores
try:
    from music_players import PlayerManager
    PLAYER_MANAGER_AVAILABLE = True
except ImportError:
    PLAYER_MANAGER_AVAILABLE = False
    print("Advertencia: music_players.py no encontrado. Usando solo playerctl.")"""

# Insertar después de las importaciones de spotipy
insert_pos = original.find("except ImportError:\n    SPOTIFY_AVAILABLE = False") + len("except ImportError:\n    SPOTIFY_AVAILABLE = False")
part1 = original[:insert_pos]
part2 = original[insert_pos:]

modified = part1 + new_import + part2

# Buscar y reemplazar el método __init__ para añadir player_manager
init_addition = """

        # Inicializar gestor de reproductores
        if PLAYER_MANAGER_AVAILABLE:
            self.player_manager = PlayerManager(self.logger)
            available = self.player_manager.get_available_players()
            if available:
                self.logger.info(f"Reproductores disponibles: {', '.join(available)}")
        else:
            self.player_manager = None
"""

# Encontrar donde añadir esto (después de _load_environment())
search_str = "        # Variables de estado"
modified = modified.replace(search_str, init_addition + "\n        # Variables de estado")

# Ahora reemplazar el método get_current_song_metadata
old_method_start = '    def get_current_song_metadata(self) -> bool:'
old_method_end = '            return True'

# Encontrar el inicio del método
start_idx = modified.find(old_method_start)
if start_idx == -1:
    print("ERROR: No se encontró el método get_current_song_metadata")
    exit(1)

# Encontrar el final del método (buscamos el próximo método que empiece con "def ")
temp = modified[start_idx + len(old_method_start):]
next_method = temp.find('\n    def ')
if next_method == -1:
    print("ERROR: No se encontró el final del método")
    exit(1)

end_idx = start_idx + len(old_method_start) + next_method

# Nuevo método get_current_song_metadata
new_method = '''    def get_current_song_metadata(self) -> bool:
        """Obtener metadata de la canción en reproducción (multi-source)"""
        self.logger.info("=" * 60)
        self.logger.info("🎵 DETECCIÓN DE MÚSICA EN REPRODUCCIÓN")
        self.logger.info("=" * 60)

        metadata = None

        # Intentar con PlayerManager primero (Airsonic, Spotify Web, etc.)
        if PLAYER_MANAGER_AVAILABLE and self.player_manager:
            metadata = self.player_manager.get_now_playing()

        # Fallback a playerctl si no se encontró nada
        if not metadata:
            self.logger.info("🔄 Intentando con playerctl (reproductores locales)...")
            metadata = self._get_metadata_from_playerctl()

        if not metadata:
            self.logger.error("❌ No se pudo detectar música en reproducción")
            self._notify("Error", "No hay reproductores de música activos")
            return False

        # Procesar metadata
        artist_raw = metadata.get('artist_raw', '')
        album_raw = metadata.get('album_raw', '')
        title_raw = metadata.get('title_raw', '')

        if not artist_raw or not title_raw:
            self.logger.error("❌ Metadata incompleta")
            self._notify("Error", "No se pudo obtener información de la canción")
            return False

        # Limpiar para URLs pero mantener raw para búsquedas en BD
        self.current_metadata = {
            'artist_raw': artist_raw,
            'album_raw': album_raw,
            'title_raw': title_raw,
            'artist': self._clean_for_url(artist_raw),
            'album': self._clean_for_url(album_raw),
            'title': self._clean_for_url(title_raw),
            'source': metadata.get('source', 'unknown'),
            'player': metadata.get('player', 'unknown'),
            'year': metadata.get('year', ''),
            'genre': metadata.get('genre', ''),
            'track_number': metadata.get('track_number', ''),
            'disc_number': metadata.get('disc_number', '1'),
        }

        # Información adicional específica de la fuente
        if 'cover_art_id' in metadata:
            self.current_metadata['cover_art_id'] = metadata['cover_art_id']
        if 'spotify_uri' in metadata:
            self.current_metadata['spotify_uri'] = metadata['spotify_uri']

        self.logger.info("=" * 60)
        self.logger.info("✅ METADATA DETECTADA:")
        self.logger.info(f"   Fuente: {self.current_metadata['source']}")
        self.logger.info(f"   Reproductor: {self.current_metadata['player']}")
        self.logger.info(f"   Artista: {artist_raw}")
        self.logger.info(f"   Álbum: {album_raw}")
        self.logger.info(f"   Título: {title_raw}")
        if self.current_metadata.get('year'):
            self.logger.info(f"   Año: {self.current_metadata['year']}")
        if self.current_metadata.get('genre'):
            self.logger.info(f"   Género: {self.current_metadata['genre']}")
        self.logger.info("=" * 60)

        return True

    def _get_metadata_from_playerctl(self) -> Optional[Dict[str, str]]:
        """Método legacy: obtener metadata usando playerctl directamente"""
        try:
            result = subprocess.run(['playerctl', '-l'],
                                  capture_output=True, text=True, check=True)
            players = result.stdout.strip().split('\\n')

            if not players or players == ['']:
                return None

        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

        # Buscar reproductor activo
        active_player = None
        for player in players:
            try:
                status = subprocess.run(['playerctl', '-p', player, 'status'],
                                      capture_output=True, text=True, check=True)
                if status.stdout.strip() == 'Playing':
                    active_player = player
                    break
            except subprocess.CalledProcessError:
                continue

        if not active_player:
            active_player = players[0]

        # Obtener metadata
        try:
            def get_metadata(field):
                try:
                    result = subprocess.run(['playerctl', '-p', active_player, 'metadata', field],
                                          capture_output=True, text=True, check=True)
                    return result.stdout.strip().replace('"', '').replace(':', '')
                except subprocess.CalledProcessError:
                    return ""

            artist = get_metadata('artist')
            album = get_metadata('album')
            title = get_metadata('title')

            if not artist or not title:
                return None

            if not album:
                album = title

            return {
                'source': 'playerctl',
                'artist_raw': artist,
                'album_raw': album,
                'title_raw': title,
                'player': active_player,
            }

        except Exception as e:
            self.logger.error(f"Error con playerctl: {e}")
            return None
'''

# Reemplazar el método
modified = modified[:start_idx] + new_method + '\n' + modified[end_idx:]

# Escribir el archivo final
with open('main_updated.py', 'w', encoding='utf-8') as f:
    f.write(modified)

print("✅ Archivo main.py actualizado generado correctamente")
