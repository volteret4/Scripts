import os
import json
import time
import base64
import requests
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
import urllib.parse

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
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"

        self.cache_dir = Path(cache_dir)
        self.cache_duration = cache_duration
        self.access_token = None
        self.token_expiry = None

        # Variable para capturar errores
        self.last_error = None
        self.authenticated = False

        # Variables Spotipy
        self.sp = spotify_client
        self.sp_oauth = None
        self.spotify_user_id = None

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

        # Intentar cargar token guardado
        self._load_saved_token()

    def setup(self):
        """Configurar y autenticar con Spotify"""
        try:
            # Verificar si ya tenemos un error de inicialización
            if self.last_error:
                print(f"❌ Error previo en inicialización: {self.last_error}")
                return False

            # Si spotipy no está disponible, usar solo Client Credentials
            if not SPOTIPY_AVAILABLE:
                print("⚠️ Spotipy no disponible, usando Client Credentials Flow")
                token = self.get_client_credentials()
                if token:
                    self.authenticated = True
                    print("✅ Spotify configurado con Client Credentials")
                    return True
                else:
                    self.last_error = "No se pudo obtener token con Client Credentials"
                    return False

            # Definir scope para permisos de Spotify
            scope = "playlist-read-private playlist-read-collaborative user-follow-read user-read-email"

            # Crear instancia OAuth
            self.sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=scope,
                open_browser=False,
                cache_path=str(self.cache_dir / "spotify_token.txt")
            )

            # Intentar obtener token (sin interacción del usuario para el bot)
            try:
                # Primero intentar Client Credentials Flow que no requiere autorización del usuario
                token = self.get_client_credentials()
                if token:
                    # Crear cliente básico con Client Credentials
                    # Este no tendrá acceso a datos del usuario pero puede buscar artistas
                    self.authenticated = True
                    print("✅ Spotify configurado con Client Credentials Flow")
                    return True
            except Exception as e:
                print(f"⚠️ Client Credentials falló: {e}")

            # Si llegamos aquí, usar un modo limitado
            self.authenticated = False
            print("⚠️ Spotify en modo limitado (sin autenticación completa)")
            return True

        except Exception as e:
            self.last_error = f"Error configurando Spotify: {str(e)}"
            print(f"❌ {self.last_error}")
            return False

    def get_client_credentials(self):
        """Obtener token usando Client Credentials Flow"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

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
            self.access_token = token_info.get("access_token")

            expires_in = token_info.get("expires_in", 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            self._save_token()

            print(f"✅ Token de Spotify obtenido (expira en {expires_in}s)")
            return self.access_token
        except requests.exceptions.RequestException as e:
            print(f"❌ Error obteniendo token de Spotify: {e}")
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

    def search_artist(self, name):
        """Buscar un artista por nombre"""
        cache_file = self._get_cache_file_path(f"artist_{name}")
        cached_data = self._load_from_cache(cache_file)

        if cached_data:
            print(f"🔄 Usando caché para artista: {name}")
            return cached_data

        token = self.get_client_credentials()
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
                print(f"✅ Artista encontrado en Spotify: {artist_data.get('name')}")
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

    def _load_saved_token(self):
        """Cargar token guardado si existe y es válido"""
        token_file = self.cache_dir / "spotify_token.json"

        if token_file.exists():
            try:
                with open(token_file, "r") as f:
                    token_data = json.load(f)

                expiry_time = datetime.fromisoformat(token_data.get("expiry", ""))

                if datetime.now() < expiry_time - timedelta(minutes=5):
                    self.access_token = token_data.get("access_token")
                    self.token_expiry = expiry_time
                    return True
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"⚠️ Error cargando token guardado: {e}")

        return False

    def _save_token(self):
        """Guardar token actual en caché"""
        if not self.access_token or not self.token_expiry:
            return

        token_file = self.cache_dir / "spotify_token.json"

        try:
            token_data = {
                "access_token": self.access_token,
                "expiry": self.token_expiry.isoformat()
            }

            with open(token_file, "w") as f:
                json.dump(token_data, f)
        except Exception as e:
            print(f"⚠️ Error guardando token: {e}")

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
