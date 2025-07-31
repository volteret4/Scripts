import os
import json
import time
import base64
import requests
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
import urllib.parse
from typing import Dict

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False
    print("Warning: spotipy not available. Some features will be limited.")

class SpotifyService:
    """Servicio para interactuar con la API de Spotify con detección de país mejorada"""

    def __init__(self, client_id, client_secret, redirect_uri, cache_dir, cache_duration=24, spotify_client=None):
        """Inicialización mejorada del servicio de Spotify"""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"

        self.cache_dir = Path(cache_dir)
        self.cache_duration = cache_duration

        # ELIMINADO: Variables de token global
        # self.access_token = None
        # self.token_expiry = None

        # Variables para capturar errores
        self.last_error = None
        self.authenticated = False

        # Variables Spotipy
        self.sp = spotify_client
        self.sp_oauth = None

        # Cache para geolocalización
        self.location_cache = {}


        # Mapeo de ciudades a países (principales ciudades)
        self.city_country_map = {
            # España
            'madrid': 'ES', 'barcelona': 'ES', 'valencia': 'ES', 'sevilla': 'ES', 'seville': 'ES',
            'bilbao': 'ES', 'malaga': 'ES', 'valencia': 'ES', 'zaragoza': 'ES', 'valladolid': 'ES',
            'vigo': 'ES', 'gijon': 'ES', 'cadiz': 'ES', 'cordoba': 'ES', 'alicante': 'ES',
            'santander': 'ES', 'salamanca': 'ES', 'burgos': 'ES', 'leon': 'ES', 'tarragona': 'ES',

            # Reino Unido
            'london': 'GB', 'manchester': 'GB', 'birmingham': 'GB', 'glasgow': 'GB', 'liverpool': 'GB',
            'leeds': 'GB', 'sheffield': 'GB', 'edinburgh': 'GB', 'bristol': 'GB', 'cardiff': 'GB',
            'nottingham': 'GB', 'newcastle': 'GB', 'belfast': 'GB', 'brighton': 'GB', 'plymouth': 'GB',

            # Francia
            'paris': 'FR', 'marseille': 'FR', 'lyon': 'FR', 'toulouse': 'FR', 'nice': 'FR',
            'nantes': 'FR', 'strasbourg': 'FR', 'montpellier': 'FR', 'bordeaux': 'FR', 'lille': 'FR',
            'rennes': 'FR', 'reims': 'FR', 'le havre': 'FR', 'saint-etienne': 'FR', 'toulon': 'FR',

            # Estados Unidos
            'new york': 'US', 'los angeles': 'US', 'chicago': 'US', 'houston': 'US', 'phoenix': 'US',
            'philadelphia': 'US', 'san antonio': 'US', 'san diego': 'US', 'dallas': 'US', 'san jose': 'US',
            'austin': 'US', 'jacksonville': 'US', 'fort worth': 'US', 'columbus': 'US', 'charlotte': 'US',
            'san francisco': 'US', 'indianapolis': 'US', 'seattle': 'US', 'denver': 'US', 'washington': 'US',
            'boston': 'US', 'el paso': 'US', 'detroit': 'US', 'nashville': 'US', 'portland': 'US',
            'memphis': 'US', 'oklahoma city': 'US', 'las vegas': 'US', 'louisville': 'US', 'baltimore': 'US',
            'milwaukee': 'US', 'albuquerque': 'US', 'tucson': 'US', 'fresno': 'US', 'sacramento': 'US',
            'kansas city': 'US', 'mesa': 'US', 'atlanta': 'US', 'omaha': 'US', 'colorado springs': 'US',
            'raleigh': 'US', 'miami': 'US', 'oakland': 'US', 'minneapolis': 'US', 'tulsa': 'US',
            'cleveland': 'US', 'wichita': 'US', 'arlington': 'US', 'new orleans': 'US', 'bakersfield': 'US',
            'tampa': 'US', 'honolulu': 'US', 'aurora': 'US', 'anaheim': 'US', 'santa ana': 'US',
            'st. louis': 'US', 'riverside': 'US', 'corpus christi': 'US', 'lexington': 'US', 'pittsburgh': 'US',
            'anchorage': 'US', 'stockton': 'US', 'cincinnati': 'US', 'st. paul': 'US', 'toledo': 'US',
            'greensboro': 'US', 'newark': 'US', 'plano': 'US', 'henderson': 'US', 'lincoln': 'US',
            'buffalo': 'US', 'jersey city': 'US', 'chula vista': 'US', 'fort wayne': 'US', 'orlando': 'US',
            'st. petersburg': 'US', 'chandler': 'US', 'laredo': 'US', 'norfolk': 'US', 'durham': 'US',
            'madison': 'US', 'lubbock': 'US', 'irvine': 'US', 'winston-salem': 'US', 'glendale': 'US',
            'garland': 'US', 'hialeah': 'US', 'reno': 'US', 'chesapeake': 'US', 'gilbert': 'US',
            'baton rouge': 'US', 'irving': 'US', 'scottsdale': 'US', 'north las vegas': 'US', 'fremont': 'US',
            'boise': 'US', 'richmond': 'US', 'san bernardino': 'US', 'birmingham': 'US', 'spokane': 'US',
            'rochester': 'US', 'des moines': 'US', 'modesto': 'US', 'fayetteville': 'US', 'tacoma': 'US',
            'oxnard': 'US', 'fontana': 'US', 'columbus': 'US', 'montgomery': 'US', 'moreno valley': 'US',
            'shreveport': 'US', 'aurora': 'US', 'yonkers': 'US', 'akron': 'US', 'huntington beach': 'US',
            'little rock': 'US', 'augusta': 'US', 'amarillo': 'US', 'glendale': 'US', 'mobile': 'US',
            'grand rapids': 'US', 'salt lake city': 'US', 'tallahassee': 'US', 'huntsville': 'US', 'grand prairie': 'US',
            'knoxville': 'US', 'worcester': 'US', 'newport news': 'US', 'brownsville': 'US', 'overland park': 'US',
            'santa clarita': 'US', 'providence': 'US', 'garden grove': 'US', 'chattanooga': 'US', 'oceanside': 'US',
            'jackson': 'US', 'fort lauderdale': 'US', 'santa rosa': 'US', 'rancho cucamonga': 'US', 'port st. lucie': 'US',
            'tempe': 'US', 'ontario': 'US', 'vancouver': 'US', 'cape coral': 'US', 'sioux falls': 'US',
            'springfield': 'US', 'peoria': 'US', 'pembroke pines': 'US', 'elk grove': 'US', 'corona': 'US',
            'lansing': 'US', 'eugene': 'US', 'palmdale': 'US', 'salinas': 'US', 'springfield': 'US',
            'pasadena': 'US', 'fort collins': 'US', 'hayward': 'US', 'pomona': 'US', 'cary': 'US',
            'rockford': 'US', 'alexandria': 'US', 'escondido': 'US', 'mckinney': 'US', 'kansas city': 'US',
            'joliet': 'US', 'sunnyvale': 'US', 'torrance': 'US', 'bridgeport': 'US', 'lakewood': 'US',
            'hollywood': 'US', 'paterson': 'US', 'naperville': 'US', 'syracuse': 'US', 'mesquite': 'US',
            'dayton': 'US', 'savannah': 'US', 'clarksville': 'US', 'orange': 'US', 'pasadena': 'US',
            'fullerton': 'US', 'killeen': 'US', 'frisco': 'US', 'hampton': 'US', 'mcallen': 'US',
            'warren': 'US', 'west valley city': 'US', 'columbia': 'US', 'olathe': 'US', 'sterling heights': 'US',
            'new haven': 'US', 'miramar': 'US', 'waco': 'US', 'thousand oaks': 'US', 'cedar rapids': 'US',

            # Alemania
            'berlin': 'DE', 'hamburg': 'DE', 'munich': 'DE', 'cologne': 'DE', 'frankfurt': 'DE',
            'stuttgart': 'DE', 'dusseldorf': 'DE', 'dortmund': 'DE', 'essen': 'DE', 'leipzig': 'DE',
            'bremen': 'DE', 'dresden': 'DE', 'hannover': 'DE', 'nuremberg': 'DE', 'duisburg': 'DE',

            # Italia
            'rome': 'IT', 'milan': 'IT', 'naples': 'IT', 'turin': 'IT', 'palermo': 'IT',
            'genoa': 'IT', 'bologna': 'IT', 'florence': 'IT', 'bari': 'IT', 'catania': 'IT',
            'venice': 'IT', 'verona': 'IT', 'messina': 'IT', 'padua': 'IT', 'trieste': 'IT',

            # Países Bajos
            'amsterdam': 'NL', 'rotterdam': 'NL', 'the hague': 'NL', 'utrecht': 'NL', 'eindhoven': 'NL',
            'tilburg': 'NL', 'groningen': 'NL', 'almere': 'NL', 'breda': 'NL', 'nijmegen': 'NL',

            # Bélgica
            'brussels': 'BE', 'antwerp': 'BE', 'ghent': 'BE', 'charleroi': 'BE', 'liege': 'BE',
            'bruges': 'BE', 'namur': 'BE', 'leuven': 'BE', 'mons': 'BE', 'aalst': 'BE',

            # Portugal
            'lisbon': 'PT', 'porto': 'PT', 'braga': 'PT', 'coimbra': 'PT', 'funchal': 'PT',
            'aveiro': 'PT', 'setubal': 'PT', 'faro': 'PT', 'viseu': 'PT', 'leiria': 'PT',

            # Canada
            'toronto': 'CA', 'montreal': 'CA', 'vancouver': 'CA', 'calgary': 'CA', 'ottawa': 'CA',
            'edmonton': 'CA', 'winnipeg': 'CA', 'quebec city': 'CA', 'hamilton': 'CA', 'halifax': 'CA',

            # Australia
            'sydney': 'AU', 'melbourne': 'AU', 'brisbane': 'AU', 'perth': 'AU', 'adelaide': 'AU',
            'gold coast': 'AU', 'newcastle': 'AU', 'canberra': 'AU', 'sunshine coast': 'AU', 'wollongong': 'AU',

            # México
            'mexico city': 'MX', 'guadalajara': 'MX', 'monterrey': 'MX', 'puebla': 'MX', 'tijuana': 'MX',
            'leon': 'MX', 'juarez': 'MX', 'torreon': 'MX', 'queretaro': 'MX', 'san luis potosi': 'MX',

            # Brasil
            'sao paulo': 'BR', 'rio de janeiro': 'BR', 'brasilia': 'BR', 'salvador': 'BR', 'fortaleza': 'BR',
            'belo horizonte': 'BR', 'manaus': 'BR', 'curitiba': 'BR', 'recife': 'BR', 'porto alegre': 'BR',

            # Argentina
            'buenos aires': 'AR', 'cordoba': 'AR', 'rosario': 'AR', 'mendoza': 'AR', 'tucuman': 'AR',
            'la plata': 'AR', 'mar del plata': 'AR', 'salta': 'AR', 'santa fe': 'AR', 'san juan': 'AR',

            # Japón
            'tokyo': 'JP', 'yokohama': 'JP', 'osaka': 'JP', 'nagoya': 'JP', 'sapporo': 'JP',
            'kobe': 'JP', 'kyoto': 'JP', 'fukuoka': 'JP', 'kawasaki': 'JP', 'saitama': 'JP',

            # Otros países importantes
            'stockholm': 'SE', 'copenhagen': 'DK', 'oslo': 'NO', 'helsinki': 'FI',
            'vienna': 'AT', 'zurich': 'CH', 'warsaw': 'PL', 'prague': 'CZ',
            'budapest': 'HU', 'dublin': 'IE', 'athens': 'GR', 'moscow': 'RU',
        }
        # Validar credenciales
        if not self.client_id or not self.client_secret:
            self.last_error = "Credenciales Spotify incompletas"
            print(f"❌ {self.last_error}")
            return

        # Crear directorio de caché si no existe
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.last_error = f"Error creando directorio de caché: {str(e)}"
            print(f"❌ {self.last_error}")
            return

        # Limpiar tokens expirados al inicializar
        self.cleanup_expired_tokens()

        # Mostrar estadísticas
        auth_users = self.get_authenticated_users_count()
        print(f"📊 Usuarios autenticados en Spotify: {auth_users}")


    def process_authorization_code(self, user_id: int, authorization_code: str) -> tuple[bool, str, dict]:
        """
        Procesa el código de autorización y obtiene tokens
        VERSIÓN MEJORADA con mejor manejo de errores

        Args:
            user_id: ID del usuario
            authorization_code: Código recibido de Spotify

        Returns:
            Tupla (éxito, mensaje, user_info)
        """
        if not SPOTIPY_AVAILABLE:
            return False, "Spotipy no disponible", {}

        try:
            logger.info(f"Procesando código para usuario {user_id}: {authorization_code[:10]}...")

            # Cargar estado de autenticación
            auth_data = self._load_auth_state(user_id)
            if not auth_data:
                logger.warning(f"No se encontró estado de auth para usuario {user_id}")
                return False, "Sesión de autenticación expirada. Genera una nueva URL.", {}

            # Crear OAuth manager
            sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=auth_data['redirect_uri'],
                scope=auth_data['scope'],
                show_dialog=False
            )

            logger.info(f"OAuth manager creado, intercambiando código...")

            # Intercambiar código por tokens
            try:
                token_info = sp_oauth.get_access_token(authorization_code)
            except Exception as oauth_error:
                logger.error(f"Error en get_access_token: {oauth_error}")

                # Intentar con diferentes métodos
                try:
                    # Método alternativo: usar requests directamente
                    token_info = self._exchange_code_manually(authorization_code, auth_data)
                except Exception as manual_error:
                    logger.error(f"Error en intercambio manual: {manual_error}")
                    return False, f"Código inválido o expirado. Error: {str(oauth_error)}", {}

            if not token_info or 'access_token' not in token_info:
                logger.error(f"Token info inválido: {token_info}")
                return False, "No se pudieron obtener tokens. Verifica el código.", {}

            logger.info("Tokens obtenidos correctamente, obteniendo perfil...")

            # Crear cliente autenticado
            sp = spotipy.Spotify(auth=token_info['access_token'])

            # Obtener información del usuario
            try:
                user_profile = sp.current_user()
                logger.info(f"Perfil obtenido: {user_profile.get('id')}")

                user_info = {
                    'spotify_id': user_profile.get('id'),
                    'display_name': user_profile.get('display_name', user_profile.get('id')),
                    'followers': user_profile.get('followers', {}).get('total', 0),
                    'email': user_profile.get('email', ''),
                    'country': user_profile.get('country', ''),
                    'product': user_profile.get('product', 'free')
                }

                # Obtener playlists
                try:
                    playlists = sp.current_user_playlists(limit=1)
                    user_info['public_playlists'] = playlists.get('total', 0)
                except Exception as playlist_error:
                    logger.warning(f"Error obteniendo playlists: {playlist_error}")
                    user_info['public_playlists'] = 0

            except Exception as profile_error:
                logger.error(f"Error obteniendo perfil: {profile_error}")
                # Usar información básica si no se puede obtener el perfil completo
                user_info = {
                    'spotify_id': 'unknown',
                    'display_name': 'Usuario Spotify',
                    'followers': 0,
                    'email': '',
                    'country': '',
                    'product': 'unknown',
                    'public_playlists': 0
                }

            # Guardar tokens para uso futuro
            self._save_user_tokens(user_id, token_info, user_info)

            # Limpiar estado de auth
            auth_file = self.cache_dir / f"spotify_auth_{user_id}.json"
            if auth_file.exists():
                auth_file.unlink()

            logger.info(f"Autenticación exitosa para usuario {user_id}")
            return True, "Autenticación exitosa", user_info

        except Exception as e:
            logger.error(f"Error procesando código de autorización: {e}")
            return False, f"Error en autenticación: {str(e)}", {}



    def _save_user_tokens(self, user_id: int, token_info: dict, user_info: dict):
        """Guarda los tokens del usuario autenticado"""
        try:
            tokens_file = self.cache_dir / f"spotify_tokens_{user_id}.json"

            tokens_data = {
                'access_token': token_info.get('access_token'),
                'refresh_token': token_info.get('refresh_token'),
                'expires_at': token_info.get('expires_at'),
                'scope': token_info.get('scope'),
                'user_info': user_info,
                'saved_at': time.time()
            }

            with open(tokens_file, 'w') as f:
                json.dump(tokens_data, f)

        except Exception as e:
            print(f"⚠️ Error guardando tokens: {e}")

    def _load_user_tokens(self, user_id: int) -> dict:
        """Carga los tokens guardados del usuario"""
        try:
            tokens_file = self.cache_dir / f"spotify_tokens_{user_id}.json"

            if not tokens_file.exists():
                return {}

            with open(tokens_file, 'r') as f:
                return json.load(f)

        except Exception as e:
            print(f"⚠️ Error cargando tokens: {e}")
            return {}

    def _refresh_user_token(self, user_id: int) -> bool:
        """Refresca el token de acceso si es necesario - VERSIÓN MEJORADA"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            tokens_data = self._load_user_tokens(user_id)
            if not tokens_data:
                logger.info(f"No hay tokens para usuario {user_id}")
                return False

            # Verificar si necesita refresh (con margen de 5 minutos)
            expires_at = tokens_data.get('expires_at', 0)
            current_time = time.time()

            if current_time < expires_at - 300:  # 5 minutos de margen
                logger.info(f"Token aún válido para usuario {user_id}")
                return True

            refresh_token = tokens_data.get('refresh_token')
            if not refresh_token:
                logger.warning(f"No hay refresh token para usuario {user_id}")
                return False

            logger.info(f"Refrescando token para usuario {user_id}")

            # Crear OAuth para refresh
            sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri
            )

            # Refrescar token
            new_token_info = sp_oauth.refresh_access_token(refresh_token)

            if new_token_info:
                logger.info(f"Token refrescado exitosamente para usuario {user_id}")

                # Actualizar tokens guardados manteniendo la info del usuario
                user_info = tokens_data.get('user_info', {})

                # Actualizar solo los campos necesarios
                tokens_data.update({
                    'access_token': new_token_info.get('access_token'),
                    'expires_at': new_token_info.get('expires_at'),
                    'refreshed_at': current_time
                })

                # Si viene nuevo refresh token, actualizarlo
                if 'refresh_token' in new_token_info:
                    tokens_data['refresh_token'] = new_token_info['refresh_token']

                # Guardar tokens actualizados
                self._save_user_tokens(user_id, tokens_data, user_info)
                return True

            logger.error(f"No se pudo refrescar token para usuario {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error refrescando token para usuario {user_id}: {e}")
            return False

    def cleanup_expired_tokens(self):
        """Limpia tokens expirados para liberar espacio"""
        try:
            current_time = time.time()

            # Buscar archivos de tokens
            for token_file in self.cache_dir.glob("spotify_tokens_*.json"):
                try:
                    with open(token_file, 'r') as f:
                        tokens_data = json.load(f)

                    expires_at = tokens_data.get('expires_at', 0)
                    saved_at = tokens_data.get('saved_at', 0)

                    # Eliminar si ha expirado hace más de 7 días y no hay refresh token
                    if (current_time - expires_at > 7 * 24 * 3600 and
                        not tokens_data.get('refresh_token')):
                        token_file.unlink()
                        print(f"🧹 Token expirado eliminado: {token_file.name}")

                    # Eliminar tokens muy antiguos (más de 30 días)
                    elif current_time - saved_at > 30 * 24 * 3600:
                        token_file.unlink()
                        print(f"🧹 Token antiguo eliminado: {token_file.name}")

                except Exception as e:
                    print(f"⚠️ Error limpiando {token_file}: {e}")

        except Exception as e:
            print(f"⚠️ Error en limpieza de tokens: {e}")

    def get_authenticated_users_count(self) -> int:
        """Obtiene el número de usuarios autenticados"""
        try:
            count = 0
            current_time = time.time()

            for token_file in self.cache_dir.glob("spotify_tokens_*.json"):
                try:
                    with open(token_file, 'r') as f:
                        tokens_data = json.load(f)

                    expires_at = tokens_data.get('expires_at', 0)
                    refresh_token = tokens_data.get('refresh_token')

                    # Contar como válido si no ha expirado o tiene refresh token
                    if current_time < expires_at or refresh_token:
                        count += 1

                except Exception:
                    continue

            return count
        except Exception:
            return 0



    def get_authenticated_client(self, user_id: int):
        """
        Obtiene un cliente de Spotify autenticado para un usuario
        VERSIÓN MEJORADA CON LOGGING
        """
        import logging
        logger = logging.getLogger(__name__)

        if not SPOTIPY_AVAILABLE:
            logger.warning("Spotipy no disponible")
            return None

        try:
            logger.info(f"Obteniendo cliente autenticado para usuario {user_id}")

            # Cargar tokens
            tokens_data = self._load_user_tokens(user_id)
            if not tokens_data:
                logger.info(f"No hay tokens guardados para usuario {user_id}")
                return None

            # Refrescar token si es necesario
            if not self._refresh_user_token(user_id):
                logger.warning(f"No se pudo refrescar token para usuario {user_id}")
                return None

            # Recargar tokens actualizados
            tokens_data = self._load_user_tokens(user_id)
            access_token = tokens_data.get('access_token')

            if not access_token:
                logger.error(f"No hay access token para usuario {user_id}")
                return None

            # Crear cliente autenticado
            logger.info(f"Cliente autenticado creado para usuario {user_id}")
            return spotipy.Spotify(auth=access_token)

        except Exception as e:
            logger.error(f"Error obteniendo cliente autenticado para usuario {user_id}: {e}")
            return None


    def get_user_followed_artists_real(self, user_id: int, limit: int = 50) -> tuple[list, str]:
        """
        Obtiene los artistas realmente seguidos por el usuario autenticado
        VERSIÓN CON DEBUG MEJORADO

        Args:
            user_id: ID del usuario
            limit: Límite de artistas a obtener

        Returns:
            Tupla (lista_artistas, mensaje_estado)
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"=== get_user_followed_artists_real: usuario {user_id}, límite {limit} ===")

        try:
            logger.info("Obteniendo cliente autenticado...")
            sp = self.get_authenticated_client(user_id)

            if not sp:
                logger.error("No se pudo obtener cliente autenticado")
                return [], "Usuario no autenticado. Usa el comando de autenticación."

            logger.info("Cliente autenticado obtenido correctamente")

            artists = []
            after = None
            total_fetched = 0

            logger.info(f"Iniciando bucle de obtención de artistas (límite: {limit})")

            # Spotify limita a 50 por request para followed artists
            iteration = 0
            while total_fetched < limit:
                iteration += 1
                batch_limit = min(50, limit - total_fetched)

                logger.info(f"Iteración {iteration}: obteniendo {batch_limit} artistas (after={after})")

                try:
                    response = sp.current_user_followed_artists(
                        limit=batch_limit,
                        after=after
                    )

                    logger.info(f"Respuesta de Spotify recibida: {type(response)}")

                    if not response:
                        logger.warning("Respuesta vacía de Spotify")
                        break

                    artists_data = response.get('artists', {})
                    logger.info(f"Datos de artistas: {type(artists_data)}, keys: {list(artists_data.keys()) if artists_data else 'None'}")

                    artist_items = artists_data.get('items', [])
                    logger.info(f"Items de artistas: {len(artist_items)}")

                    if not artist_items:
                        logger.info("No hay más artistas en esta respuesta")
                        break

                    for i, artist in enumerate(artist_items):
                        logger.info(f"Procesando artista {i+1}: {artist.get('name', 'sin nombre')}")

                        artist_info = {
                            'id': artist.get('id'),
                            'name': artist.get('name'),
                            'followers': artist.get('followers', {}).get('total', 0),
                            'popularity': artist.get('popularity', 0),
                            'genres': artist.get('genres', []),
                            'external_urls': artist.get('external_urls', {}),
                            'images': artist.get('images', [])
                        }

                        artists.append(artist_info)
                        total_fetched += 1

                        if total_fetched >= limit:
                            logger.info(f"Límite alcanzado: {total_fetched}")
                            break

                    # Preparar para siguiente batch
                    cursors = artists_data.get('cursors', {})
                    after = cursors.get('after')

                    logger.info(f"Cursor 'after' para siguiente batch: {after}")

                    if not after:
                        logger.info("No hay más páginas disponibles")
                        break

                    # Evitar bucle infinito
                    if iteration > 10:
                        logger.warning("Máximo de iteraciones alcanzado")
                        break

                except Exception as e:
                    logger.error(f"Error en batch {iteration}: {e}")
                    import traceback
                    logger.error(f"Traceback del batch: {traceback.format_exc()}")
                    break

            logger.info(f"Obtención completada: {len(artists)} artistas obtenidos")

            # Log de algunos artistas para verificar
            for i, artist in enumerate(artists[:3]):
                logger.info(f"Artista {i+1}: {artist.get('name')} (followers: {artist.get('followers', 0)})")

            return artists, f"Se obtuvieron {len(artists)} artistas seguidos"

        except Exception as e:
            logger.error(f"Error crítico en get_user_followed_artists_real: {e}")
            import traceback
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return [], f"Error: {str(e)}"



    def follow_artists_batch(self, user_id: int, artist_ids: list) -> tuple[int, int, str]:
        """
        Sigue una lista de artistas en Spotify

        Args:
            user_id: ID del usuario
            artist_ids: Lista de IDs de artistas de Spotify

        Returns:
            Tupla (seguidos_exitosos, errores, mensaje)
        """
        try:
            sp = self.get_authenticated_client(user_id)
            if not sp:
                return 0, len(artist_ids), "Usuario no autenticado"

            followed = 0
            errors = 0

            # Procesar en lotes de 50 (límite de Spotify)
            for i in range(0, len(artist_ids), 50):
                batch = artist_ids[i:i+50]

                try:
                    sp.user_follow_artists(batch)
                    followed += len(batch)
                    time.sleep(0.1)  # Pausa breve

                except Exception as e:
                    print(f"❌ Error siguiendo lote: {e}")
                    errors += len(batch)

            return followed, errors, f"Seguidos: {followed}, Errores: {errors}"

        except Exception as e:
            print(f"❌ Error en follow_artists_batch: {e}")
            return 0, len(artist_ids), f"Error: {str(e)}"

    def is_user_authenticated(self, user_id: int) -> bool:
        """Verifica si un usuario tiene autenticación válida"""
        tokens_data = self._load_user_tokens(user_id)
        if not tokens_data:
            return False

        # Verificar si el token no ha expirado
        expires_at = tokens_data.get('expires_at', 0)
        if time.time() >= expires_at:
            # Intentar refresh
            return self._refresh_user_token(user_id)

        return True

    def revoke_user_authentication(self, user_id: int) -> bool:
        """Revoca la autenticación de un usuario (elimina tokens)"""
        try:
            tokens_file = self.cache_dir / f"spotify_tokens_{user_id}.json"
            if tokens_file.exists():
                tokens_file.unlink()

            auth_file = self.cache_dir / f"spotify_auth_{user_id}.json"
            if auth_file.exists():
                auth_file.unlink()

            return True

        except Exception as e:
            print(f"❌ Error revocando autenticación: {e}")
            return False


    def setup(self):
        """Configurar Spotify - VERSIÓN CORREGIDA SIN TOKEN GLOBAL"""
        try:
            # Verificar si ya tenemos un error de inicialización
            if self.last_error:
                print(f"❌ Error previo en inicialización: {self.last_error}")
                return False

            # Si spotipy no está disponible, usar solo Client Credentials para búsquedas públicas
            if not SPOTIPY_AVAILABLE:
                print("⚠️ Spotipy no disponible, usando Client Credentials Flow básico")
                # NO guardar token global, solo verificar que las credenciales funcionan
                test_token = self._get_client_credentials_token()
                if test_token:
                    print("✅ Spotify configurado con Client Credentials (búsquedas públicas)")
                    return True
                else:
                    self.last_error = "No se pudo obtener token con Client Credentials"
                    return False

            # Con spotipy disponible, configurar OAuth
            print("✅ Spotify configurado con OAuth (tokens por usuario)")
            return True

        except Exception as e:
            self.last_error = f"Error configurando Spotify: {str(e)}"
            print(f"❌ {self.last_error}")
            return False

    def _get_client_credentials_token(self):
        """Obtener token temporal para búsquedas públicas (sin usuario específico)"""
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "client_credentials"
        }

        try:
            response = requests.post(self.auth_url, headers=headers, data=data, timeout=10)
            response.raise_for_status()

            token_info = response.json()
            access_token = token_info.get("access_token")

            if access_token:
                print(f"✅ Token de búsqueda pública obtenido")
                return access_token
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Error obteniendo token público: {e}")
            return None



    def detect_country_from_city(self, city_name):
        """
        Detecta el país basándose en el nombre de la ciudad

        Args:
            city_name (str): Nombre de la ciudad

        Returns:
            str: Código de país (ej: 'ES', 'US', 'FR') o cadena vacía si no se detecta
        """
        if not city_name:
            return ''

        city_clean = city_name.lower().strip()

        # Remover texto común que no es parte del nombre de la ciudad
        city_clean = re.sub(r'\s*\(.*?\)\s*', '', city_clean)  # Remover paréntesis
        city_clean = re.sub(r'\s*,.*$', '', city_clean)  # Remover todo después de coma
        city_clean = city_clean.strip()

        # Buscar en el mapeo directo
        if city_clean in self.city_country_map:
            country = self.city_country_map[city_clean]
            print(f"🌍 País detectado por mapeo directo: {city_name} -> {country}")
            return country

        # Buscar coincidencias parciales
        for city_key, country_code in self.city_country_map.items():
            if city_key in city_clean or city_clean in city_key:
                print(f"🌍 País detectado por coincidencia parcial: {city_name} ({city_clean}) -> {country_code}")
                return country_code

        print(f"🌍 País no detectado para: {city_name}")
        return ''

    def get_country_from_geocoding(self, location):
        """
        Obtiene el país usando APIs de geocodificación

        Args:
            location (str): Ubicación (ciudad, venue, etc.)

        Returns:
            str: Código de país o cadena vacía
        """
        if not location:
            return ''

        # Verificar caché primero
        cache_key = location.lower().strip()
        if cache_key in self.location_cache:
            return self.location_cache[cache_key]

        country = ''

        try:
            # Método 1: Nominatim (OpenStreetMap) - gratuito
            country = self._get_country_nominatim(location)

            if not country:
                # Método 2: REST Countries API como fallback
                country = self._get_country_rest_countries(location)

        except Exception as e:
            print(f"❌ Error en geocodificación para {location}: {e}")

        # Guardar en caché
        self.location_cache[cache_key] = country

        if country:
            print(f"🌍 País obtenido por geocodificación: {location} -> {country}")

        return country

    def _get_country_nominatim(self, location):
        """Obtiene país usando Nominatim (OpenStreetMap)"""
        try:
            # Limpiar ubicación
            clean_location = re.sub(r'\s*\(.*?\)\s*', '', location).strip()

            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': clean_location,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            headers = {
                'User-Agent': 'SpotifyBot/1.0 (https://example.com/contact)'
            }

            response = requests.get(url, params=params, headers=headers, timeout=5)
            response.raise_for_status()

            data = response.json()
            if data and len(data) > 0:
                address = data[0].get('address', {})
                country_code = address.get('country_code', '').upper()

                if country_code:
                    return country_code

        except Exception as e:
            print(f"⚠️ Error en Nominatim: {e}")

        return ''

    def _get_country_rest_countries(self, location):
        """Obtiene país usando REST Countries API como fallback"""
        try:
            # Extraer posible nombre de país de la ubicación
            location_parts = location.replace(',', ' ').split()

            for part in location_parts:
                if len(part) > 3:  # Solo considerar palabras significativas
                    url = f"https://restcountries.com/v3.1/name/{part}"
                    response = requests.get(url, timeout=3)

                    if response.status_code == 200:
                        data = response.json()
                        if data and len(data) > 0:
                            country_code = data[0].get('cca2', '')
                            if country_code:
                                return country_code

        except Exception as e:
            print(f"⚠️ Error en REST Countries: {e}")

        return ''


    def search_artist(self, name, user_id=None):
        """Buscar un artista por nombre - VERSIÓN CORREGIDA"""
        cache_file = self._get_cache_file_path(f"artist_{name}")
        cached_data = self._load_from_cache(cache_file)

        if cached_data:
            print(f"🔄 Usando caché para artista: {name}")
            return cached_data

        # Intentar usar token de usuario autenticado si está disponible
        token = None
        if user_id:
            sp = self.get_authenticated_client(user_id)
            if sp:
                try:
                    # Usar cliente autenticado
                    results = sp.search(q=name, type='artist', limit=1)
                    artists = results.get("artists", {}).get("items", [])

                    if artists:
                        artist_data = artists[0]
                        self._save_to_cache(cache_file, artist_data)
                        print(f"✅ Artista encontrado en Spotify (usuario {user_id}): {artist_data.get('name')}")
                        return artist_data
                except Exception as e:
                    print(f"⚠️ Error con cliente autenticado, intentando con token público: {e}")

        # Fallback: usar token público temporal
        token = self._get_client_credentials_token()
        if not token:
            print(f"❌ No se pudo obtener token para buscar: {name}")
            return None

        headers = {
            "Authorization": f"Bearer {token}"
        }

        params = {
            "q": name,
            "type": "artist",
            "limit": 1
        }

        try:
            response = requests.get(f"{self.base_url}/search", headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            artists = data.get("artists", {}).get("items", [])

            if artists:
                artist_data = artists[0]
                self._save_to_cache(cache_file, artist_data)
                print(f"✅ Artista encontrado en Spotify (token público): {artist_data.get('name')}")
                return artist_data

            print(f"📭 No se encontró artista en Spotify: {name}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Error buscando artista en Spotify: {e}")
            return None

    def search_artist_url(self, artist_name):
        """Buscar URL del artista en Spotify"""
        artist_data = self.search_artist(artist_name)
        if artist_data and 'external_urls' in artist_data:
            return artist_data['external_urls'].get('spotify', '')
        return ''

    def search_artist_and_concerts(self, artist_name):
        """
        Busca un artista en Spotify y sus conciertos con detección de país mejorada
        """
        print(f"🎵 Buscando conciertos de {artist_name} en Spotify...")

        # Verificar caché primero
        cache_file = self._get_cache_file_path(f"spotify_concerts_{artist_name}")
        cached_data = self._load_from_cache(cache_file)

        if cached_data:
            print(f"🔄 Usando caché de conciertos para: {artist_name}")
            return cached_data, f"Se encontraron {len(cached_data)} conciertos para {artist_name} (caché)"

        # Buscar artista directamente en Spotify
        artist_url = self.search_artist_url(artist_name)

        if not artist_url:
            print(f"📭 No se encontró URL de Spotify para {artist_name}")
            return [], f"No se encontró URL de Spotify para {artist_name}"

        # Scrapear conciertos
        try:
            return self.scrape_artist_concerts(artist_url, artist_name)
        except Exception as e:
            print(f"❌ Error en scraping de Spotify para {artist_name}: {e}")
            return [], f"Error scrapeando Spotify: {str(e)}"

    def scrape_artist_concerts(self, artist_url, artist_name):
        """
        Scraping de conciertos usando requests con detección de país mejorada
        """
        print(f"🔍 Scrapeando conciertos de {artist_name} desde {artist_url}")

        try:
            # Intentar scraping con requests primero
            return self._scrape_with_requests(artist_url, artist_name)
        except Exception as e:
            print(f"❌ Error en scraping: {e}")
            return [], f"Error scrapeando Spotify: {str(e)}"

    def _scrape_with_requests(self, artist_url, artist_name):
        """Método de scraping usando requests con detección de país"""
        try:
            print(f"🌐 Intentando scraping con requests para {artist_name}...")

            match = re.search(r'/artist/([^/]+)', artist_url)
            if not match:
                return [], "URL de artista inválida"

            artist_id = match.group(1)
            concerts_url = f"https://open.spotify.com/artist/{artist_id}/concerts"

            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.8,en;q=0.6',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            response = requests.get(concerts_url, headers=headers, timeout=30)
            response.raise_for_status()

            # Buscar enlaces de conciertos en el HTML
            concert_urls = self._extract_concert_urls_from_html(response.text)

            if not concert_urls:
                print(f"📭 No se encontraron enlaces de conciertos en HTML para {artist_name}")
                return [], f"No se encontraron conciertos para {artist_name} en Spotify"

            print(f"🔗 Encontrados {len(concert_urls)} enlaces de conciertos para {artist_name}")

            # Extraer información de cada concierto
            concerts = []
            max_concerts = min(len(concert_urls), 20)  # Limitar para evitar timeouts

            for i, concert_url in enumerate(concert_urls[:max_concerts]):
                print(f"📍 Procesando concierto {i+1}/{max_concerts}: {concert_url}")

                concert_info = self._extract_enhanced_concert_info(concert_url, artist_name)
                if concert_info:
                    concerts.append(concert_info)

                # Pausa para no sobrecargar
                time.sleep(0.5)

            # Guardar en caché
            if concerts:
                cache_file = self._get_cache_file_path(f"spotify_concerts_{artist_name}")
                self._save_to_cache(cache_file, concerts)

            return concerts, f"Se encontraron {len(concerts)} conciertos para {artist_name}"

        except Exception as e:
            print(f"❌ Error en scraping con requests: {e}")
            return [], f"Error scrapeando Spotify: {str(e)}"

    def _extract_concert_urls_from_html(self, html_content):
        """Extrae URLs de conciertos del HTML"""
        concert_urls = []

        # Patrón para encontrar URLs de conciertos
        concert_url_pattern = r'https://open\.spotify\.com/concert/[a-zA-Z0-9]+'
        matches = re.findall(concert_url_pattern, html_content)

        # Eliminar duplicados manteniendo el orden
        seen = set()
        for url in matches:
            if url not in seen:
                seen.add(url)
                concert_urls.append(url)

        return concert_urls

    def _extract_enhanced_concert_info(self, concert_url, artist_name):
        """Extrae información de concierto con detección de país mejorada"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            response = requests.get(concert_url, headers=headers, timeout=10)
            response.raise_for_status()

            # Extraer información del HTML
            concert_info = self._parse_enhanced_spotify_page(response.text, artist_name, concert_url)

            if concert_info:
                # Detectar país usando múltiples estrategias
                country = self._detect_country_multiple_strategies(concert_info)
                concert_info['country'] = country

                if country:
                    print(f"🌍 País detectado para concierto: {country}")
                else:
                    print(f"⚠️ No se pudo detectar país para: {concert_info.get('city', 'ubicación desconocida')}")

                return concert_info
            else:
                return self._create_enhanced_fallback_concert_info(concert_url, artist_name)

        except Exception as e:
            print(f"❌ Error extrayendo info de {concert_url}: {e}")
            return self._create_enhanced_fallback_concert_info(concert_url, artist_name)

    def _parse_enhanced_spotify_page(self, html_content, artist_name, concert_url):
        """Parsea página de Spotify con extracción mejorada de información"""

        # Extraer título de la página
        title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)

        if not title_match:
            return None

        title = title_match.group(1)

        # Intentar múltiples patrones de extracción
        concert_info = None

        # Patrón 1: Título con información completa
        concert_info = self._parse_spotify_title_enhanced(title, artist_name, concert_url)

        if not concert_info:
            # Patrón 2: Buscar en el contenido de la página
            concert_info = self._parse_spotify_content(html_content, artist_name, concert_url)

        if not concert_info:
            # Patrón 3: Extracción básica como fallback
            concert_info = self._parse_spotify_title(title, artist_name, concert_url)

        return concert_info

    def _parse_spotify_title_enhanced(self, title, artist_name, concert_url):
        """Versión mejorada del parser de títulos de Spotify"""
        concert_info = {
            'artist': artist_name,
            'artist_name': artist_name,
            'name': '',
            'venue': '',
            'city': '',
            'country': '',
            'date': '',
            'time': '',
            'url': concert_url,
            'source': 'Spotify'
        }

        try:
            # Limpiar título
            title = re.sub(r'\s*\|\s*Spotify\s*, ', '', title.strip())

            # Patrón 1: "Artist Tickets City (Venue) on Date at Time"
            pattern1 = r'Tickets\s+([^(]+?)\s*\(([^)]+)\)\s+on\s+(\d{1,2}/\d{1,2}/\d{4})\s+at\s+([^|]+)'
            match1 = re.search(pattern1, title, re.IGNORECASE)

            if match1:
                city = match1.group(1).strip()
                venue = match1.group(2).strip()
                date_str = match1.group(3).strip()
                time_str = match1.group(4).strip()

                concert_info.update({
                    'city': city,
                    'venue': venue,
                    'time': time_str,
                    'name': f"{artist_name} at {venue}"
                })

                # Convertir fecha
                try:
                    date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                    concert_info['date'] = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    concert_info['date'] = date_str

                print(f"✅ Patrón 1 - Info extraída: venue='{venue}', city='{city}', date='{concert_info['date']}'")
                return concert_info

            # Patrón 2: "Artist Tickets at Venue, City on Date"
            pattern2 = r'Tickets\s+at\s+([^,]+),\s*([^o]+?)\s+on\s+(\d{1,2}/\d{1,2}/\d{4})'
            match2 = re.search(pattern2, title, re.IGNORECASE)

            if match2:
                venue = match2.group(1).strip()
                city = match2.group(2).strip()
                date_str = match2.group(3).strip()

                concert_info.update({
                    'venue': venue,
                    'city': city,
                    'name': f"{artist_name} at {venue}"
                })

                # Convertir fecha
                try:
                    date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                    concert_info['date'] = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    concert_info['date'] = date_str

                print(f"✅ Patrón 2 - Info extraída: venue='{venue}', city='{city}', date='{concert_info['date']}'")
                return concert_info

            # Patrón 3: "Artist Tickets Location Date"
            pattern3 = r'Tickets\s+([^0-9]+?)\s+(\d{1,2}/\d{1,2}/\d{4})'
            match3 = re.search(pattern3, title, re.IGNORECASE)

            if match3:
                location = match3.group(1).strip()
                date_str = match3.group(2).strip()

                # Intentar separar venue y city del location
                if ',' in location:
                    parts = location.split(',')
                    venue = parts[0].strip()
                    city = parts[1].strip()
                else:
                    venue = location
                    city = location

                concert_info.update({
                    'venue': venue,
                    'city': city,
                    'name': f"{artist_name} at {venue}"
                })

                # Convertir fecha
                try:
                    date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                    concert_info['date'] = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    concert_info['date'] = date_str

                print(f"✅ Patrón 3 - Info extraída: venue='{venue}', city='{city}', date='{concert_info['date']}'")
                return concert_info

        except Exception as e:
            print(f"❌ Error parseando título mejorado: {e}")

        return None

    def _parse_spotify_content(self, html_content, artist_name, concert_url):
        """Parsea el contenido HTML buscando información de concierto"""
        try:
            # Buscar metadatos estructurados
            concert_info = {
                'artist': artist_name,
                'artist_name': artist_name,
                'name': f"{artist_name} Concert",
                'venue': '',
                'city': '',
                'country': '',
                'date': '',
                'time': '',
                'url': concert_url,
                'source': 'Spotify'
            }

            # Buscar datos en JSON-LD si están presentes
            json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
            json_matches = re.findall(json_ld_pattern, html_content, re.DOTALL | re.IGNORECASE)

            for json_text in json_matches:
                try:
                    data = json.loads(json_text)
                    if isinstance(data, dict) and data.get('@type') == 'Event':
                        # Extraer información del evento
                        name = data.get('name', '')
                        location = data.get('location', {})

                        if isinstance(location, dict):
                            venue_name = location.get('name', '')
                            address = location.get('address', {})

                            if isinstance(address, dict):
                                city = address.get('addressLocality', '')
                                country = address.get('addressCountry', '')
                            elif isinstance(address, str):
                                city = address

                        start_date = data.get('startDate', '')

                        if venue_name or city or start_date:
                            concert_info.update({
                                'name': name or f"{artist_name} at {venue_name}",
                                'venue': venue_name,
                                'city': city,
                                'country': country,
                                'date': start_date[:10] if len(start_date) >= 10 else start_date
                            })

                            print(f"✅ Info extraída de JSON-LD: venue='{venue_name}', city='{city}', country='{country}'")
                            return concert_info

                except json.JSONDecodeError:
                    continue

            # Buscar patrones en el HTML
            # Buscar fechas
            date_patterns = [
                r'(\d{1,2}/\d{1,2}/\d{4})',
                r'(\d{4}-\d{2}-\d{2})',
                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}'
            ]

            for pattern in date_patterns:
                date_matches = re.findall(pattern, html_content, re.IGNORECASE)
                if date_matches:
                    concert_info['date'] = date_matches[0]
                    break

            # Buscar información de ubicación en meta tags
            venue_pattern = r'<meta[^>]*property=["\']venue["\'][^>]*content=["\']([^"\']+)["\']'
            venue_match = re.search(venue_pattern, html_content, re.IGNORECASE)
            if venue_match:
                concert_info['venue'] = venue_match.group(1)

            city_pattern = r'<meta[^>]*property=["\']city["\'][^>]*content=["\']([^"\']+)["\']'
            city_match = re.search(city_pattern, html_content, re.IGNORECASE)
            if city_match:
                concert_info['city'] = city_match.group(1)

            if concert_info['venue'] or concert_info['city'] or concert_info['date']:
                print(f"✅ Info extraída del contenido HTML")
                return concert_info

        except Exception as e:
            print(f"❌ Error parseando contenido HTML: {e}")

        return None

    def _detect_country_multiple_strategies(self, concert_info):
        """Detecta país usando múltiples estrategias"""
        country = ''

        # Estrategia 1: Si ya tenemos país en la info extraída
        if concert_info.get('country'):
            country = concert_info['country'].upper()
            if len(country) == 2:  # Código de país válido
                return country

        # Estrategia 2: Detectar por nombre de ciudad
        city = concert_info.get('city', '')
        if city:
            country = self.detect_country_from_city(city)
            if country:
                return country

        # Estrategia 3: Usar venue para detectar ubicación
        venue = concert_info.get('venue', '')
        if venue:
            country = self.detect_country_from_city(venue)
            if country:
                return country

        # Estrategia 4: Geocodificación de la ubicación completa
        full_location = ''
        if venue and city:
            full_location = f"{venue}, {city}"
        elif city:
            full_location = city
        elif venue:
            full_location = venue

        if full_location:
            country = self.get_country_from_geocoding(full_location)
            if country:
                return country

        # Estrategia 5: Buscar en el nombre del concierto
        concert_name = concert_info.get('name', '')
        if concert_name:
            country = self.detect_country_from_city(concert_name)
            if country:
                return country

        return ''

    def _parse_spotify_title(self, title, artist_name, concert_url):
        """Versión original del parser (como fallback)"""
        concert_info = {
            'artist': artist_name,
            'artist_name': artist_name,
            'name': '',
            'venue': '',
            'city': '',
            'country': '',
            'date': '',
            'time': '',
            'url': concert_url,
            'source': 'Spotify'
        }

        try:
            # Limpiar título
            title = re.sub(r'\s*\|\s*Spotify\s*, ', '', title.strip())

            # Patrón principal: "Artist Tickets City (Venue) on Date at Time"
            pattern = r'Tickets\s+([^(]+?)\s*\(([^)]+)\)\s+on\s+(\d{1,2}/\d{1,2}/\d{4})\s+at\s+([^|]+)'
            match = re.search(pattern, title, re.IGNORECASE)

            if match:
                city = match.group(1).strip()
                venue = match.group(2).strip()
                date_str = match.group(3).strip()
                time_str = match.group(4).strip()

                concert_info['city'] = city
                concert_info['venue'] = venue
                concert_info['time'] = time_str

                # Convertir fecha
                try:
                    date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                    concert_info['date'] = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    concert_info['date'] = date_str

                # Crear nombre del concierto
                concert_info['name'] = f"{artist_name} at {venue}"

                print(f"✅ Info extraída del título original: venue='{venue}', city='{city}', date='{concert_info['date']}'")
                return concert_info

            else:
                # Patrón más simple como fallback
                simple_pattern = r'([^|]+?)\s+Tickets'
                simple_match = re.search(simple_pattern, title, re.IGNORECASE)

                if simple_match:
                    location = simple_match.group(1).strip()
                    concert_info['venue'] = f"{location} (Venue)"
                    concert_info['city'] = location
                    concert_info['name'] = f"{artist_name} Concert"

                    print(f"✅ Info básica extraída: location='{location}'")
                    return concert_info

        except Exception as e:
            print(f"❌ Error parseando título original: {e}")

        return None

    def _create_enhanced_fallback_concert_info(self, concert_url, artist_name):
        """Crea información básica del concierto cuando falla la extracción"""
        concert_info = {
            'artist': artist_name,
            'artist_name': artist_name,
            'name': f"{artist_name} Concert",
            'venue': 'Venue information not available',
            'city': 'Location not available',
            'country': '',
            'date': '',
            'time': '',
            'url': concert_url,
            'source': 'Spotify'
        }

        # Intentar extraer alguna información básica del URL
        concert_id_match = re.search(r'/concert/([^/?]+)', concert_url)
        if concert_id_match:
            concert_id = concert_id_match.group(1)
            concert_info['name'] = f"{artist_name} Concert ({concert_id[:8]})"

        return concert_info



    def _get_cache_file_path(self, cache_key):
        """Generar ruta al archivo de caché"""
        safe_key = "".join(x for x in cache_key if x.isalnum() or x in " _-").rstrip()
        safe_key = safe_key.replace(" ", "_").lower()
        return self.cache_dir / f"spotify_{safe_key}.json"

    def _load_from_cache(self, cache_file):
        """Cargar datos de caché si existen y son válidos"""
        if not cache_file.exists():
            return None

        try:
            file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            cache_age = datetime.now() - file_time

            if cache_age > timedelta(hours=self.cache_duration):
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                if isinstance(data, dict) and 'timestamp' in data:
                    cache_time = datetime.fromisoformat(data['timestamp'])
                    if (datetime.now() - cache_time) > timedelta(hours=self.cache_duration):
                        return None
                    return data.get('data', data)
                else:
                    return data

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"⚠️ Error leyendo caché: {e}")
            return None

    def _save_to_cache(self, cache_file, data):
        """Guardar resultados en caché"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"⚠️ Error guardando caché: {e}")

    def clear_cache(self, pattern=None):
        """Limpiar caché"""
        if pattern:
            for file in self.cache_dir.glob(f"spotify_{pattern}*.json"):
                file.unlink()
        else:
            for file in self.cache_dir.glob("spotify_*.json"):
                file.unlink()

    async def handle_spotify_authentication(query, user: Dict):
        """
        Inicia el proceso de autenticación OAuth
        VERSIÓN MEJORADA con mejores instrucciones
        """
        if not spotify_service:
            await query.edit_message_text("❌ Servicio de Spotify no disponible.")
            return

        try:
            # Generar URL de autenticación
            auth_url = spotify_service.generate_auth_url(user['id'])

            if not auth_url:
                await query.edit_message_text(
                    "❌ Error generando URL de autenticación.\n"
                    "Verifica que las credenciales de Spotify estén configuradas."
                )
                return

            # Crear mensaje con instrucciones mejoradas
            message = (
                "🔐 *Autenticación de Spotify*\n\n"
                "**Pasos para conectar tu cuenta:**\n\n"

                "1️⃣ **Abre el enlace** (clic en el botón de abajo)\n\n"

                "2️⃣ **Inicia sesión** con tu cuenta de Spotify\n\n"

                "3️⃣ **Acepta los permisos** solicitados\n\n"

                "4️⃣ **Copia el código:**\n"
                "   • La página mostrará un código o dirá 'Authorization successful'\n"
                "   • Si ves una URL larga, copia toda la URL\n"
                "   • Si ves solo un código, copia solo el código\n\n"

                "5️⃣ **Pégalo aquí** en el chat\n\n"

                "⏰ *Tienes 10 minutos para completar este proceso.*\n"
                "❓ Si tienes problemas, genera una nueva URL."
            )

            keyboard = [
                [InlineKeyboardButton("🔗 Abrir enlace de Spotify", url=auth_url)],
                [InlineKeyboardButton("❓ ¿Problemas?", callback_data=f"spotify_auth_help_{user['id']}")],
                [InlineKeyboardButton("❌ Cancelar", callback_data=f"spotify_cancel_{user['id']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )

            # Marcar que estamos esperando el código
            # Esto se debe hacer en el callback handler donde tengas acceso a context

        except Exception as e:
            logger.error(f"Error en autenticación Spotify: {e}")
            await query.edit_message_text(
                "❌ Error iniciando autenticación. Inténtalo de nuevo."
            )

    def generate_auth_url(self, user_id: int) -> str:
        """
        Genera URL de autorización de Spotify para un usuario específico
        VERSIÓN CORREGIDA con mejor gestión
        """
        if not SPOTIPY_AVAILABLE:
            return ""

        try:
            # Usar user_id como state para asociar la respuesta
            state = f"user_{user_id}_{int(time.time())}"

            # Crear OAuth manager con scopes específicos
            scope = "user-follow-read user-follow-modify playlist-read-private user-read-email user-read-private playlist-read-collaborative"

            # CORRECCIÓN: Usar redirect_uri específico por usuario si es necesario
            redirect_uri = self.redirect_uri

            sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                state=state,
                show_dialog=True  # Fuerza mostrar diálogo de login
            )

            auth_url = sp_oauth.get_authorize_url()

            # Guardar el state temporalmente para validar después
            self._save_auth_state(user_id, state, sp_oauth, redirect_uri)

            logger.info(f"URL de autorización generada para usuario {user_id}")
            logger.info(f"Redirect URI: {redirect_uri}")

            return auth_url

        except Exception as e:
            logger.error(f"Error generando URL de autorización: {e}")
            return ""



    def _save_auth_state(self, user_id: int, state: str, sp_oauth, redirect_uri: str):
        """Guarda el estado de autenticación temporalmente - VERSIÓN CORREGIDA"""
        try:
            auth_file = self.cache_dir / f"spotify_auth_{user_id}.json"

            auth_data = {
                'state': state,
                'timestamp': time.time(),
                'redirect_uri': redirect_uri,  # CORRECCIÓN: Guardar redirect_uri específico
                'scope': sp_oauth.scope,
                'client_id': self.client_id,  # Para validación
                'client_secret': self.client_secret  # Para intercambio de código
            }

            with open(auth_file, 'w') as f:
                json.dump(auth_data, f)

        except Exception as e:
            print(f"⚠️ Error guardando estado de auth: {e}")


    def _load_auth_state(self, user_id: int) -> dict:
        """Carga el estado de autenticación guardado"""
        try:
            auth_file = self.cache_dir / f"spotify_auth_{user_id}.json"

            if not auth_file.exists():
                return {}

            with open(auth_file, 'r') as f:
                auth_data = json.load(f)

            # Verificar que no haya expirado (30 minutos)
            if time.time() - auth_data.get('timestamp', 0) > 1800:
                auth_file.unlink()  # Eliminar archivo expirado
                return {}

            return auth_data

        except Exception as e:
            print(f"⚠️ Error cargando estado de auth: {e}")
            return {}

    def _exchange_code_manually(self, authorization_code: str, auth_data: dict) -> dict:
        """
        Intercambia código por tokens usando requests directamente
        VERSIÓN MEJORADA
        """
        import requests
        import base64
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Preparar datos para el intercambio
            auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

            headers = {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            data = {
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": auth_data['redirect_uri']
            }

            logger.info(f"Intercambiando código con redirect_uri: {auth_data['redirect_uri']}")

            response = requests.post("https://accounts.spotify.com/api/token",
                                   headers=headers, data=data, timeout=10)

            logger.info(f"Respuesta de Spotify: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Error de Spotify: {response.text}")
                response.raise_for_status()

            token_data = response.json()
            logger.info("Tokens obtenidos correctamente")

            return token_data

        except Exception as e:
            logger.error(f"Error en intercambio manual de código: {e}")
            raise




    def search_and_get_followed_artists_simulation(self, username: str, limit: int = 20) -> tuple[list, str]:
        """
        Simula obtener artistas seguidos usando búsquedas populares
        (Para cuando no hay autenticación OAuth)

        Args:
            username: Nombre de usuario (no se usa realmente)
            limit: Límite de artistas a retornar

        Returns:
            Tupla (lista_artistas, mensaje_estado)
        """
        try:
            # Lista de artistas populares para simular
            popular_artists = [
                "Taylor Swift", "Bad Bunny", "The Weeknd", "Drake", "Billie Eilish",
                "Ariana Grande", "Post Malone", "Dua Lipa", "Ed Sheeran", "Olivia Rodrigo",
                "Harry Styles", "Doja Cat", "Justin Bieber", "SZA", "Lana Del Rey",
                "Kendrick Lamar", "Bruno Mars", "Rihanna", "Adele", "Eminem",
                "Coldplay", "Imagine Dragons", "Maroon 5", "OneRepublic", "The Chainsmokers",
                "BTS", "BLACKPINK", "TWICE", "NewJeans", "Stray Kids"
            ]

            artists = []
            processed = 0

            # Obtener información de cada artista usando la API
            for artist_name in popular_artists[:limit]:
                if processed >= limit:
                    break

                try:
                    artist_data = self.search_artist(artist_name)

                    if artist_data:
                        artist_info = {
                            'id': artist_data.get('id', ''),
                            'name': artist_data.get('name', artist_name),
                            'followers': artist_data.get('followers', {}).get('total', 0),
                            'popularity': artist_data.get('popularity', 0),
                            'genres': artist_data.get('genres', []),
                            'external_urls': artist_data.get('external_urls', {}),
                            'images': artist_data.get('images', [])
                        }
                        artists.append(artist_info)
                        processed += 1
                    else:
                        # Si no se encuentra, crear entrada básica
                        artists.append({
                            'id': f'sim_{processed}',
                            'name': artist_name,
                            'followers': 0,
                            'popularity': 50,
                            'genres': ['pop'],
                            'external_urls': {},
                            'images': []
                        })
                        processed += 1

                    # Pausa para no sobrecargar la API
                    time.sleep(0.2)

                except Exception as e:
                    print(f"⚠️ Error obteniendo info de {artist_name}: {e}")
                    # Crear entrada básica en caso de error
                    artists.append({
                        'id': f'sim_{processed}',
                        'name': artist_name,
                        'followers': 0,
                        'popularity': 50,
                        'genres': ['pop'],
                        'external_urls': {},
                        'images': []
                    })
                    processed += 1

            return artists, f"Simulación: {len(artists)} artistas populares mostrados"

        except Exception as e:
            print(f"❌ Error en simulación de artistas: {e}")
            return [], f"Error en simulación: {str(e)}"

    def check_user_exists(self, username: str) -> bool:
        """
        Verifica si un usuario existe en Spotify (simulado)

        Args:
            username: Nombre de usuario

        Returns:
            True siempre (no podemos verificar realmente sin OAuth)
        """
        # Sin OAuth no podemos verificar usuarios reales
        # Asumimos que existe para permitir la configuración
        return True

    def get_user_info(self, username: str) -> dict:
        """
        Obtiene información básica de un usuario (simulado)

        Args:
            username: Nombre de usuario

        Returns:
            Diccionario con información básica
        """
        return {
            'display_name': username,
            'followers': 0,
            'public_playlists': 0,
            'country': '',
            'product': 'free'
        }

    def get_user_playlists_count(self, username: str) -> int:
        """
        Obtiene el número de playlists de un usuario (simulado)

        Args:
            username: Nombre de usuario

        Returns:
            Número de playlists (simulado)
        """
        return 0



    def get_user_playlists_detailed(self, user_id: int, limit: int = 50) -> tuple[list, str]:
        """
        Obtiene las playlists del usuario autenticado con información detallada

        Args:
            user_id: ID del usuario
            limit: Límite de playlists a obtener

        Returns:
            Tupla (lista_playlists, mensaje_estado)
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"=== get_user_playlists_detailed: usuario {user_id}, límite {limit} ===")

        try:
            sp = self.get_authenticated_client(user_id)
            if not sp:
                return [], "Usuario no autenticado. Usa el comando de autenticación."

            playlists = []
            offset = 0
            total_fetched = 0

            # Spotify limita a 50 por request para playlists
            while total_fetched < limit:
                batch_limit = min(50, limit - total_fetched)

                try:
                    response = sp.current_user_playlists(
                        limit=batch_limit,
                        offset=offset
                    )

                    if not response or 'items' not in response:
                        break

                    playlist_items = response['items']

                    if not playlist_items:
                        break

                    for playlist in playlist_items:
                        playlist_info = {
                            'id': playlist.get('id'),
                            'name': playlist.get('name'),
                            'description': playlist.get('description', ''),
                            'tracks_total': playlist.get('tracks', {}).get('total', 0),
                            'public': playlist.get('public', False),
                            'collaborative': playlist.get('collaborative', False),
                            'owner': playlist.get('owner', {}).get('display_name', ''),
                            'external_urls': playlist.get('external_urls', {}),
                            'images': playlist.get('images', [])
                        }

                        playlists.append(playlist_info)
                        total_fetched += 1

                        if total_fetched >= limit:
                            break

                    # Verificar si hay más páginas
                    if len(playlist_items) < batch_limit:
                        break

                    offset += batch_limit

                except Exception as e:
                    logger.error(f"Error en batch de playlists: {e}")
                    break

            return playlists, f"Se obtuvieron {len(playlists)} playlists"

        except Exception as e:
            logger.error(f"Error obteniendo playlists: {e}")
            return [], f"Error: {str(e)}"

    def get_playlist_tracks(self, user_id: int, playlist_id: str) -> tuple[list, str]:
        """
        Obtiene las canciones de una playlist específica

        Args:
            user_id: ID del usuario
            playlist_id: ID de la playlist

        Returns:
            Tupla (lista_canciones, mensaje_estado)
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"=== get_playlist_tracks: playlist {playlist_id} ===")

        try:
            sp = self.get_authenticated_client(user_id)
            if not sp:
                return [], "Usuario no autenticado."

            tracks = []
            offset = 0

            while True:
                try:
                    response = sp.playlist_tracks(
                        playlist_id,
                        limit=100,  # Máximo por request
                        offset=offset
                    )

                    if not response or 'items' not in response:
                        break

                    track_items = response['items']

                    if not track_items:
                        break

                    for item in track_items:
                        track = item.get('track')
                        if not track or track.get('type') != 'track':
                            continue

                        # Obtener artistas
                        artists = track.get('artists', [])

                        for artist in artists:
                            artist_info = {
                                'id': artist.get('id'),
                                'name': artist.get('name'),
                                'external_urls': artist.get('external_urls', {}),
                                'track_name': track.get('name', ''),
                                'track_id': track.get('id', '')
                            }
                            tracks.append(artist_info)

                    # Verificar si hay más páginas
                    if len(track_items) < 100:
                        break

                    offset += 100

                except Exception as e:
                    logger.error(f"Error en batch de tracks: {e}")
                    break

            # Eliminar artistas duplicados pero mantener info de tracks
            unique_artists = {}
            for track in tracks:
                artist_id = track['id']
                if artist_id not in unique_artists:
                    unique_artists[artist_id] = {
                        'id': artist_id,
                        'name': track['name'],
                        'external_urls': track['external_urls'],
                        'tracks': []
                    }
                unique_artists[artist_id]['tracks'].append({
                    'name': track['track_name'],
                    'id': track['track_id']
                })

            artist_list = list(unique_artists.values())

            return artist_list, f"Se encontraron {len(artist_list)} artistas únicos"

        except Exception as e:
            logger.error(f"Error obteniendo tracks de playlist: {e}")
            return [], f"Error: {str(e)}"

    def get_playlist_by_url(self, user_id: int, playlist_url: str) -> tuple[dict, str]:
        """
        Obtiene información de una playlist por su URL

        Args:
            user_id: ID del usuario
            playlist_url: URL de la playlist de Spotify

        Returns:
            Tupla (info_playlist, mensaje_estado)
        """
        import re
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Extraer ID de la playlist de la URL
            playlist_id_match = re.search(r'playlist/([a-zA-Z0-9]+)', playlist_url)
            if not playlist_id_match:
                return {}, "URL de playlist inválida"

            playlist_id = playlist_id_match.group(1)
            logger.info(f"ID de playlist extraído: {playlist_id}")

            sp = self.get_authenticated_client(user_id)
            if not sp:
                return {}, "Usuario no autenticado"

            # Obtener información de la playlist
            playlist_info = sp.playlist(playlist_id)

            if not playlist_info:
                return {}, "No se pudo obtener información de la playlist"

            playlist_data = {
                'id': playlist_info.get('id'),
                'name': playlist_info.get('name'),
                'description': playlist_info.get('description', ''),
                'tracks_total': playlist_info.get('tracks', {}).get('total', 0),
                'public': playlist_info.get('public', False),
                'collaborative': playlist_info.get('collaborative', False),
                'owner': playlist_info.get('owner', {}).get('display_name', ''),
                'external_urls': playlist_info.get('external_urls', {}),
                'images': playlist_info.get('images', [])
            }

            return playlist_data, "Playlist encontrada"

        except Exception as e:
            logger.error(f"Error obteniendo playlist por URL: {e}")
            return {}, f"Error: {str(e)}"
