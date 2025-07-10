# modules/submodules/shared/spotify_service.py
import os
import json
import time
import base64
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
from threading import Timer
import http.server
import socketserver
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
import re


class SpotifyAuthHandler(http.server.SimpleHTTPRequestHandler):
    """Manejador de autorización para Spotify callback"""

    def __init__(self, *args, auth_code_callback=None, **kwargs):
        self.auth_code_callback = auth_code_callback
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Procesar solicitud GET con código de autorización"""
        query = urllib.parse.urlparse(self.path).query
        query_components = dict(qc.split("=") for qc in query.split("&") if "=" in qc)

        if "code" in query_components:
            auth_code = query_components["code"]
            self.auth_code_callback(auth_code)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            success_html = """
            <html>
            <head><title>Autorización Spotify Completada</title></head>
            <body>
                <h1>Autorización Completada</h1>
                <p>Puedes cerrar esta ventana y volver a la aplicación.</p>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            error_html = """
            <html>
            <head><title>Error de Autorización</title></head>
            <body>
                <h1>Error de Autorización</h1>
                <p>No se recibió código de autorización. Por favor, intenta nuevamente.</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())

        self.server.server_close()
        return

class SpotifyService:
    """Servicio unificado para interactuar con la API de Spotify"""

    def __init__(self, client_id, client_secret, redirect_uri, cache_dir, cache_duration=24, spotify_client=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.base_url = "https://api.spotify.com/v1"
        self.auth_url = "https://accounts.spotify.com/api/token"
        self.authorize_url = "https://accounts.spotify.com/authorize"

        self.cache_dir = Path(cache_dir)
        self.cache_duration = cache_duration
        self.access_token = None
        self.token_expiry = None

        # Variable para capturar errores
        self.last_error = None

        # Variables Spotipy
        self.sp = spotify_client
        self.sp_oauth = None
        self.authenticated = False

        # Validar credenciales
        if not self.client_id or not self.client_secret:
            self.last_error = "Credenciales Spotify incompletas"
            return

        # Crear directorio de caché si no existe
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.last_error = f"Error creando directorio de caché: {str(e)}"
            return

        # Intentar cargar token guardado
        self._load_saved_token()

    def setup(self):
        """Configurar y autenticar con Spotify"""
        try:
            # Verificar si ya tenemos un error de inicialización
            if self.last_error:
                print(f"Error previo en inicialización: {self.last_error}")
                return False

            # Definir scope para permisos de Spotify
            scope = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-follow-read user-read-email"

            # Crear instancia OAuth
            self.sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=scope,
                open_browser=False,
                cache_path=str(self.cache_dir / "spotify_token.txt")
            )

            # Obtener token
            token_info = self._get_token_or_authenticate()

            if token_info:
                # Crear cliente Spotify con el token
                self.sp = spotipy.Spotify(auth=token_info['access_token'])

                # Obtener información del usuario
                try:
                    user_info = self.sp.current_user()
                    self.spotify_user_id = user_info['id']
                    print(f"Authenticated as user: {self.spotify_user_id}")
                    self.authenticated = True
                    return True
                except Exception as e:
                    self.last_error = f"Error obteniendo info de usuario: {str(e)}"
                    print(self.last_error)
                    return False
            else:
                self.last_error = "No se pudo obtener token de autenticación"
                return False

        except ImportError as e:
            self.last_error = f"Error importando spotipy: {str(e)}. ¿Está instalado?"
            print(self.last_error)
            return False
        except Exception as e:
            self.last_error = f"Error configurando Spotify: {str(e)}"
            print(self.last_error)
            return False

    def _load_saved_token(self):
        """Cargar token guardado si existe y es válido"""
        token_file = self.cache_dir / "spotify_token.json" or ".cache" / "spotify_token.txt"

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
                print(f"Error cargando token guardado: {e}")

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
            print(f"Error guardando token: {e}")

    def _get_token_or_authenticate(self):
        """Obtener token válido o iniciar autenticación"""
        try:
            # Verificar token en caché
            cached_token = self.sp_oauth.get_cached_token()
            if cached_token and not self.sp_oauth.is_token_expired(cached_token):
                return cached_token
            elif cached_token:
                try:
                    new_token = self.sp_oauth.refresh_access_token(cached_token['refresh_token'])
                    return new_token
                except Exception as e:
                    print(f"Token refresh failed: {str(e)}")

            # Si no hay token válido, realizar nueva autenticación
            print("Iniciando autenticación de Spotify...")
            return self._perform_new_authentication()
        except Exception as e:
            print(f"Error en get_token_or_authenticate: {str(e)}")
            return None

    def _perform_new_authentication(self):
        """Realizar autenticación desde cero"""
        auth_url = self.sp_oauth.get_authorize_url()

        # Para interactuar con el usuario, podría usar PyQt dialogs aquí
        print(f"Por favor, visita: {auth_url}")
        redirect_url = input("Ingresa la URL de redirección: ")

        if redirect_url:
            try:
                if '%3A' in redirect_url or '%2F' in redirect_url:
                    redirect_url = unquote(redirect_url)

                code = None
                if redirect_url.startswith('http'):
                    code = self.sp_oauth.parse_response_code(redirect_url)
                elif 'code=' in redirect_url:
                    code = redirect_url.split('code=')[1].split('&')[0]
                else:
                    code = redirect_url

                if code:
                    token_info = self.sp_oauth.get_access_token(code)
                    return token_info
            except Exception as e:
                print(f"Error en autenticación: {str(e)}")

        return None

    def get_client_credentials(self):
        """Obtener token usando Client Credentials Flow"""
        if self.access_token and datetime.now() < self.token_expiry:
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
            response = requests.post(self.auth_url, headers=headers, data=data)
            response.raise_for_status()

            token_info = response.json()
            self.access_token = token_info.get("access_token")

            expires_in = token_info.get("expires_in", 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            self._save_token()

            return self.access_token
        except requests.exceptions.RequestException as e:
            print(f"Error obteniendo token: {e}")
            return None

    def search_artist(self, name):
        """Buscar un artista por nombre"""
        cache_file = self._get_cache_file_path(f"artist_{name}")
        cached_data = self._load_from_cache(cache_file)

        if cached_data:
            return cached_data

        token = self.get_client_credentials()
        if not token:
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
            response = requests.get(f"{self.base_url}/search", headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            artists = data.get("artists", {}).get("items", [])

            if artists:
                artist_data = artists[0]
                self._save_to_cache(cache_file, artist_data)
                return artist_data

            return None
        except requests.exceptions.RequestException as e:
            print(f"Error buscando artista: {e}")
            return None

    def get_artist_concerts_from_db_or_search(self, artist_name, db_path):
        """Obtener información de conciertos para un artista"""
        import sqlite3

        # Verificar caché primero
        cache_file = self._get_cache_file_path(f"spotify_concerts_{artist_name}")
        cached_data = self._load_from_cache(cache_file)

        if cached_data:
            return cached_data, f"Se encontraron {len(cached_data)} conciertos para {artist_name} (caché)"

        # Buscar en BD
        artist_url = None
        try:
            db_conn = sqlite3.connect(db_path)
            cursor = db_conn.cursor()
            cursor.execute("SELECT spotify_url FROM artists WHERE name = ?", (artist_name,))
            result = cursor.fetchone()

            if result and result[0]:
                artist_url = result[0]
            else:
                artist_url = self.search_artist_url(artist_name)
                if result:
                    cursor.execute("UPDATE artists SET spotify_url = ? WHERE name = ?", (artist_url, artist_name))
                    db_conn.commit()
        except Exception as e:
            print(f"Error accessing database: {e}")
            artist_url = self.search_artist_url(artist_name)
        finally:
            if 'db_conn' in locals():
                db_conn.close()

        if not artist_url:
            return [], f"No se encontró URL de Spotify para {artist_name}"

        # Scrapear conciertos
        return self.scrape_artist_concerts(artist_url, artist_name)

    def search_artist_url(self, artist_name):
        """Buscar URL del artista en Spotify"""
        artist_data = self.search_artist(artist_name)
        if artist_data and 'external_urls' in artist_data:
            return artist_data['external_urls'].get('spotify', '')
        return ''

    def scrape_artist_concerts(self, artist_url, artist_name):
        """Scrapear conciertos de un artista usando Selenium con múltiples estrategias"""
        match = re.search(r'/artist/([^/]+)', artist_url)
        if not match:
            return [], "URL de artista inválida"

        artist_id = match.group(1)
        concerts_url = f"https://open.spotify.com/artist/{artist_id}/concerts"

        # Configuración robusta de Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-javascript')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--window-size=1920,1080')

        driver = None
        concerts = []

        try:
            # Intentar crear el driver con manejo de errores
            try:
                driver = webdriver.Chrome(options=chrome_options)
                driver.set_page_load_timeout(30)
            except WebDriverException as e:
                print(f"Error creando driver Chrome: {e}")
                return [], f"Error iniciando navegador: {str(e)}"

            # Navegar a la página
            try:
                print(f"Navegando a: {concerts_url}")
                driver.get(concerts_url)
            except TimeoutException:
                print("Timeout al cargar la página")
                return [], "Timeout al cargar página de Spotify"
            except WebDriverException as e:
                print(f"Error navegando: {e}")
                return [], f"Error navegando a Spotify: {str(e)}"

            # Esperar a que la página cargue con múltiples estrategias
            selectors_to_try = [
                '[data-testid="concert-row"]',
                '.concert-item',
                '.event-item',
                '.UtdfKFkqUnNS1UWu3BG_',  # Posible selector de Spotify
                '[class*="concert"]',
                '[class*="event"]'
            ]

            concert_elements = []
            wait = WebDriverWait(driver, 20)

            for selector in selectors_to_try:
                try:
                    print(f"Intentando selector: {selector}")
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    concert_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if concert_elements:
                        print(f"Encontrados {len(concert_elements)} elementos con selector: {selector}")
                        break
                except TimeoutException:
                    print(f"Timeout con selector: {selector}")
                    continue
                except Exception as e:
                    print(f"Error con selector {selector}: {e}")
                    continue

            # Si no encontramos elementos específicos, buscar patrones más generales
            if not concert_elements:
                print("Buscando patrones alternativos...")

                # Buscar elementos que contengan fechas o información de conciertos
                alternative_selectors = [
                    'div[role="row"]',
                    'div[class*="row"]',
                    'article',
                    'li[class*="item"]',
                    'div[class*="item"]'
                ]

                for alt_selector in alternative_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, alt_selector)
                        # Filtrar elementos que puedan contener información de conciertos
                        for element in elements:
                            text = element.text.lower()
                            if any(keyword in text for keyword in ['concert', 'tour', 'live', 'show', '2024', '2025']):
                                concert_elements.append(element)

                        if concert_elements:
                            print(f"Encontrados {len(concert_elements)} elementos candidatos con selector: {alt_selector}")
                            break
                    except Exception as e:
                        print(f"Error con selector alternativo {alt_selector}: {e}")
                        continue

            # Procesar elementos encontrados
            if concert_elements:
                print(f"Procesando {len(concert_elements)} elementos de concierto")

                for i, element in enumerate(concert_elements[:10]):  # Limitar a 10 para evitar timeouts
                    try:
                        print(f"Procesando elemento {i+1}")
                        concert = self._extract_concert_info(element, artist_name)
                        if concert:
                            concerts.append(concert)
                    except Exception as e:
                        print(f"Error procesando elemento {i+1}: {e}")
                        continue
            else:
                print("No se encontraron elementos de concierto")
                # Intentar método alternativo usando requests
                return self._scrape_with_requests(artist_url, artist_name)

            # Actualizar caché
            if concerts:
                cache_file = self._get_cache_file_path(f"spotify_concerts_{artist_name}")
                self._save_to_cache(cache_file, concerts)

            return concerts, f"Se encontraron {len(concerts)} conciertos para {artist_name} (scraping)"

        except Exception as e:
            print(f"Error general en scraping: {e}")
            # Intentar método alternativo
            return self._scrape_with_requests(artist_url, artist_name)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    print(f"Error cerrando driver: {e}")

    def _extract_concert_info(self, element, artist_name):
        """Extrae información de concierto de un elemento"""
        try:
            # Obtener texto del elemento
            element_text = element.text
            element_html = element.get_attribute('outerHTML')

            # Buscar fecha usando múltiples estrategias
            date = self._extract_date_from_element(element)

            # Buscar venue y ciudad
            venue, city = self._extract_venue_and_city(element, element_text)

            # Buscar URL del concierto
            concert_url = self._extract_concert_url(element)

            # Si encontramos información válida, crear el concierto
            if date or venue or city:
                concert = {
                    'artist': artist_name,
                    'name': f"{venue} Concert" if venue else f"{artist_name} Concert",
                    'venue': venue or 'Unknown venue',
                    'city': city or 'Unknown city',
                    'date': date or '',
                    'time': '',
                    'image': '',
                    'url': concert_url or '',
                    'source': 'Spotify'
                }
                print(f"Concierto extraído: {concert}")
                return concert

        except Exception as e:
            print(f"Error extrayendo información del concierto: {e}")

        return None

    def _extract_date_from_element(self, element):
        """Extrae fecha del elemento usando múltiples estrategias"""
        try:
            # Buscar elemento time con datetime
            time_elements = element.find_elements(By.TAG_NAME, 'time')
            for time_elem in time_elements:
                datetime_attr = time_elem.get_attribute('datetime')
                if datetime_attr:
                    return datetime_attr[:10] if len(datetime_attr) >= 10 else datetime_attr

            # Buscar patrones de fecha en el texto
            text = element.text
            date_patterns = [
                r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
                r'(\d{1,2}/\d{1,2}/\d{4})',  # DD/MM/YYYY o MM/DD/YYYY
                r'(\d{1,2}\s+\w+\s+\d{4})',  # DD Month YYYY
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)

        except Exception as e:
            print(f"Error extrayendo fecha: {e}")

        return ''

    def _extract_venue_and_city(self, element, text):
        """Extrae venue y ciudad del elemento"""
        venue = ''
        city = ''

        try:
            # Buscar selectores específicos para venue
            venue_selectors = [
                '[data-testid="event-venue"]',
                '.venue-name',
                '.event-venue',
                'strong'
            ]

            for selector in venue_selectors:
                try:
                    venue_elem = element.find_element(By.CSS_SELECTOR, selector)
                    if venue_elem:
                        venue = venue_elem.text.strip()
                        break
                except:
                    continue

            # Si no encontramos venue con selectores, buscar en el texto
            if not venue:
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not any(char.isdigit() for char in line[:4]):  # Evitar líneas que empiecen con fechas
                        if len(line) > 3 and len(line) < 100:  # Longitud razonable para un venue
                            venue = line
                            break

            # Extraer ciudad (usualmente después del venue)
            if venue and ',' in venue:
                parts = venue.split(',')
                venue = parts[0].strip()
                city = parts[1].strip() if len(parts) > 1 else ''

        except Exception as e:
            print(f"Error extrayendo venue/ciudad: {e}")

        return venue, city

    def _extract_concert_url(self, element):
        """Extrae URL del concierto"""
        try:
            # Buscar enlaces dentro del elemento
            links = element.find_elements(By.TAG_NAME, 'a')
            for link in links:
                href = link.get_attribute('href')
                if href and 'concert' in href:
                    return href

            # Si el elemento mismo es un enlace
            href = element.get_attribute('href')
            if href:
                return href

        except Exception as e:
            print(f"Error extrayendo URL: {e}")

        return ''

    def _scrape_with_requests(self, artist_url, artist_name):
        """Método alternativo usando requests cuando Selenium falla"""
        try:
            print("Intentando scraping con requests como fallback...")

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

            # Buscar JSON con datos de conciertos en el HTML
            import re
            json_pattern = r'<script[^>]*type="application/json"[^>]*>(.*?)</script>'
            json_matches = re.findall(json_pattern, response.text, re.DOTALL)

            concerts = []
            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    # Buscar datos de conciertos en la estructura JSON
                    concerts.extend(self._extract_concerts_from_json(data, artist_name))
                except json.JSONDecodeError:
                    continue

            if concerts:
                cache_file = self._get_cache_file_path(f"spotify_concerts_{artist_name}")
                self._save_to_cache(cache_file, concerts)
                return concerts, f"Se encontraron {len(concerts)} conciertos para {artist_name} (requests fallback)"
            else:
                return [], f"No se encontraron conciertos para {artist_name} en Spotify"

        except Exception as e:
            print(f"Error en scraping con requests: {e}")
            return [], f"Error scrapeando Spotify: {str(e)}"

    def _extract_concerts_from_json(self, data, artist_name):
        """Extrae conciertos de datos JSON"""
        concerts = []

        try:
            # Función recursiva para buscar conciertos en estructuras JSON anidadas
            def search_concerts(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key in ['concerts', 'events', 'shows', 'tour'] and isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    concert = self._parse_concert_json(item, artist_name)
                                    if concert:
                                        concerts.append(concert)
                        else:
                            search_concerts(value, f"{path}.{key}")
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        search_concerts(item, f"{path}[{i}]")

            search_concerts(data)

        except Exception as e:
            print(f"Error extrayendo conciertos de JSON: {e}")

        return concerts

    def _parse_concert_json(self, concert_data, artist_name):
        """Parsea un objeto JSON de concierto individual"""
        try:
            venue = concert_data.get('venue', {})
            if isinstance(venue, str):
                venue_name = venue
                city = ''
            else:
                venue_name = venue.get('name', '')
                city = venue.get('city', '')

            date = concert_data.get('date', '')
            if isinstance(concert_data.get('startDate'), str):
                date = concert_data['startDate'][:10]

            concert = {
                'artist': artist_name,
                'name': concert_data.get('name', f"{venue_name} Concert"),
                'venue': venue_name,
                'city': city,
                'date': date,
                'time': concert_data.get('time', ''),
                'image': concert_data.get('image', ''),
                'url': concert_data.get('url', ''),
                'source': 'Spotify'
            }

            # Solo devolver si tenemos información mínima
            if venue_name or city or date:
                return concert

        except Exception as e:
            print(f"Error parseando concierto JSON: {e}")

        return None

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
            print(f"Error leyendo caché: {e}")
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
            print(f"Error guardando caché: {e}")

    def clear_cache(self, pattern=None):
        """Limpiar caché"""
        if pattern:
            for file in self.cache_dir.glob(f"spotify_{pattern}*.json"):
                file.unlink()
        else:
            for file in self.cache_dir.glob("spotify_*.json"):
                file.unlink()

    # ESPECIFICO PARA EL BOT
    def search_artist_and_concerts(self, artist_name):
        """
        Busca un artista en Spotify y sus conciertos sin usar BD

        Args:
            artist_name (str): Nombre del artista a buscar

        Returns:
            tuple: (lista de conciertos, mensaje)
        """
        # Verificar caché primero
        cache_file = self._get_cache_file_path(f"spotify_concerts_{artist_name}")
        cached_data = self._load_from_cache(cache_file)

        if cached_data:
            return cached_data, f"Se encontraron {len(cached_data)} conciertos para {artist_name} (caché)"

        # Buscar artista directamente en Spotify
        artist_url = self.search_artist_url(artist_name)

        if not artist_url:
            return [], f"No se encontró URL de Spotify para {artist_name}"

        # Scrapear conciertos con manejo robusto de errores
        try:
            return self.scrape_artist_concerts(artist_url, artist_name)
        except Exception as e:
            print(f"Error en scraping de Spotify: {e}")
            return [], f"Error scrapeando Spotify: {str(e)}"
