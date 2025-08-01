import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import requests

class TicketmasterService:
    """Servicio para interactuar con la API de Ticketmaster con soporte de caché"""

    def __init__(self, api_key, cache_dir, cache_duration=24):
        self.api_key = api_key
        self.base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
        self.cache_dir = Path(cache_dir)
        self.cache_duration = cache_duration  # horas

        # Crear directorio de caché si no existe
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search_concerts(self, artist_name, country_code="ES", size=50):
        """
        Buscar conciertos para un artista en un país específico, primero en caché y luego en API

        Args:
            artist_name (str): Nombre del artista a buscar
            country_code (str): Código de país ISO (ES, US, etc.)
            size (int): Número máximo de resultados

        Returns:
            tuple: (lista de conciertos, mensaje)
        """
        if not self.api_key:
            return [], "No se ha configurado API Key para Ticketmaster"

        # Comprobar si tenemos resultado en caché válido
        cache_file = self._get_cache_file_path(artist_name, country_code)
        cached_data = self._load_from_cache(cache_file)

        if cached_data:
            return cached_data, f"Se encontraron {len(cached_data)} conciertos para {artist_name} (caché)"

        # Si no hay caché válido, consultar API
        params = {
            "keyword": artist_name,
            "countryCode": country_code,
            "size": size,
            "sort": "date,asc",
            "apikey": self.api_key
        }

        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if '_embedded' not in data or 'events' not in data['_embedded']:
                return [], "No se encontraron eventos"

            concerts = []
            for event in data['_embedded']['events']:
                # Extraer datos relevantes con validación de calidad
                venue_info = self._extract_venue_info(event)

                # FILTRO DE CALIDAD: Solo guardar si tenemos ciudad válida
                if venue_info['city'] == 'Unknown city' or not venue_info['city']:
                    continue

                concert = {
                    'artist': artist_name,
                    'name': event.get('name', 'No title'),
                    'venue': venue_info['venue'],
                    'city': venue_info['city'],
                    'country': venue_info['country'],
                    'country_code': venue_info['country_code'],
                    'date': event.get('dates', {}).get('start', {}).get('localDate', 'Unknown date'),
                    'time': event.get('dates', {}).get('start', {}).get('localTime', ''),
                    'image': next((img.get('url', '') for img in event.get('images', [])
                            if img.get('ratio') == '16_9' and img.get('width') > 500),
                            event.get('images', [{}])[0].get('url', '') if event.get('images') else ''),
                    'url': event.get('url', ''),
                    'source': 'Ticketmaster',
                    'id': event.get('id', '')
                }
                concerts.append(concert)

            # Guardar en caché
            self._save_to_cache(cache_file, concerts)

            return concerts, f"Se encontraron {len(concerts)} conciertos para {artist_name}"

        except requests.exceptions.RequestException as e:
            return [], f"Error en la solicitud: {str(e)}"
        except ValueError as e:
            return [], f"Error procesando respuesta: {str(e)}"

    def search_concerts_global(self, artist_name, size=200):
        """
        Buscar conciertos para un artista globalmente (todos los países)

        Args:
            artist_name (str): Nombre del artista a buscar
            size (int): Número máximo de resultados

        Returns:
            tuple: (lista de conciertos, mensaje)
        """
        if not self.api_key:
            return [], "No se ha configurado API Key para Ticketmaster"

        # Comprobar si tenemos resultado en caché válido
        cache_file = self._get_cache_file_path_global(artist_name)
        cached_data = self._load_from_cache(cache_file)

        if cached_data:
            return cached_data, f"Se encontraron {len(cached_data)} conciertos para {artist_name} (caché global)"

        # Si no hay caché válido, consultar API globalmente
        params = {
            "keyword": artist_name,
            "size": size,
            "sort": "date,asc",
            "apikey": self.api_key
            # Sin countryCode para búsqueda global
        }

        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if '_embedded' not in data or 'events' not in data['_embedded']:
                return [], "No se encontraron eventos"

            concerts = []
            for event in data['_embedded']['events']:
                # Extraer datos relevantes incluyendo país
                venue_info = self._extract_venue_info(event)

                # FILTRO DE CALIDAD: Solo guardar si tenemos ciudad válida
                if venue_info['city'] == 'Unknown city' or not venue_info['city']:
                    continue

                concert = {
                    'artist': artist_name,
                    'name': event.get('name', 'No title'),
                    'venue': venue_info['venue'],
                    'city': venue_info['city'],
                    'country': venue_info['country'],
                    'country_code': venue_info['country_code'],
                    'date': event.get('dates', {}).get('start', {}).get('localDate', 'Unknown date'),
                    'time': event.get('dates', {}).get('start', {}).get('localTime', ''),
                    'url': event.get('url', ''),
                    'source': 'Ticketmaster',
                    'id': event.get('id', '')
                }
                concerts.append(concert)

            # Guardar en caché
            self._save_to_cache(cache_file, concerts)

            return concerts, f"Se encontraron {len(concerts)} conciertos globales para {artist_name}"

        except requests.exceptions.RequestException as e:
            return [], f"Error en la solicitud: {str(e)}"
        except ValueError as e:
            return [], f"Error procesando respuesta: {str(e)}"

    def _extract_venue_info(self, event):
        """
        Extrae información de venue de manera robusta con múltiples fallbacks
        Basado en la estructura oficial de la API de Ticketmaster
        """
        venue_info = {
            'venue': 'Unknown venue',
            'city': 'Unknown city',
            'country': 'Unknown country',
            'country_code': ''
        }

        # Intentar obtener datos del venue
        venues = event.get('_embedded', {}).get('venues', [])
        if not venues:
            return venue_info

        venue = venues[0]  # Primer venue

        # 1. NOMBRE DEL VENUE
        venue_info['venue'] = venue.get('name', 'Unknown venue')

        # 2. CIUDAD - Según documentación de Ticketmaster
        city = None

        # Método principal: venue.city.name
        if 'city' in venue and isinstance(venue['city'], dict):
            city = venue['city'].get('name')

        # Fallback 1: venue.address.line2 (a veces la ciudad está aquí)
        if not city and 'address' in venue and isinstance(venue['address'], dict):
            city = venue['address'].get('line2')

        # Fallback 2: venue.state.name si no hay ciudad específica
        if not city and 'state' in venue and isinstance(venue['state'], dict):
            state_name = venue['state'].get('name')
            if state_name and len(state_name) > 2:  # Evitar códigos como "CA", "TX"
                city = state_name

        # Fallback 3: venue.markets[0].name
        if not city and 'markets' in venue and venue['markets']:
            market = venue['markets'][0]
            if isinstance(market, dict):
                city = market.get('name')

        venue_info['city'] = city if city else 'Unknown city'

        # 3. PAÍS Y CÓDIGO DE PAÍS - Según documentación
        country = None
        country_code = None

        # Método principal: venue.country
        if 'country' in venue and isinstance(venue['country'], dict):
            country = venue['country'].get('name')
            country_code = venue['country'].get('countryCode')

        # Fallback 1: venue.address.country
        if not country_code and 'address' in venue and isinstance(venue['address'], dict):
            address_country = venue['address'].get('country')
            if isinstance(address_country, dict):
                country = address_country.get('name')
                country_code = address_country.get('countryCode')
            elif isinstance(address_country, str) and len(address_country) == 2:
                country_code = address_country.upper()

        # Fallback 2: venue.state.stateCode para determinar país (US/CA principalmente)
        if not country_code and 'state' in venue and isinstance(venue['state'], dict):
            state_code = venue['state'].get('stateCode')
            if state_code:
                # Estados Unidos y Canadá tienen códigos de estado conocidos
                us_states = {'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'}
                ca_provinces = {'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT'}

                if state_code in us_states:
                    country_code = 'US'
                    country = 'United States'
                elif state_code in ca_provinces:
                    country_code = 'CA'
                    country = 'Canada'

        venue_info['country'] = country if country else 'Unknown country'
        venue_info['country_code'] = country_code if country_code else ''

        return venue_info

    def _get_cache_file_path(self, artist_name, country_code):
        """Generar ruta al archivo de caché para un artista y país"""
        # Normalizar nombre para archivo
        safe_name = "".join(x for x in artist_name if x.isalnum() or x in " _-").rstrip()
        safe_name = safe_name.replace(" ", "_").lower()

        return self.cache_dir / f"ticketmaster_{safe_name}_{country_code}.json"

    def _get_cache_file_path_global(self, artist_name):
        """Generar ruta al archivo de caché global para un artista"""
        # Normalizar nombre para archivo
        safe_name = "".join(x for x in artist_name if x.isalnum() or x in " _-").rstrip()
        safe_name = safe_name.replace(" ", "_").lower()

        return self.cache_dir / f"ticketmaster_global_{safe_name}.json"

    def _load_from_cache(self, cache_file):
        """Cargar datos de caché si existen y son válidos"""
        if not cache_file.exists():
            return None

        try:
            # Verificar si el archivo es reciente
            file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            cache_age = datetime.now() - file_time

            if cache_age > timedelta(hours=self.cache_duration):
                # Caché expirado
                return None

            # Cargar datos
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Verificar timestamp del caché
                if 'timestamp' in data:
                    cache_time = datetime.fromisoformat(data['timestamp'])
                    if (datetime.now() - cache_time) > timedelta(hours=self.cache_duration):
                        return None

                    # Devolver solo los conciertos (no el timestamp)
                    return data.get('concerts', [])
                else:
                    # Formato antiguo sin timestamp
                    return data

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error leyendo caché: {e}")
            return None

    def _save_to_cache(self, cache_file, concerts):
        """Guardar resultados en caché"""
        try:
            # Guardar con timestamp
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'concerts': concerts
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error guardando caché: {e}")

    def clear_cache(self, artist_name=None, country_code=None):
        """
        Limpiar caché

        Args:
            artist_name (str, optional): Si se proporciona, solo limpia caché de ese artista
            country_code (str, optional): Si se proporciona junto con artist_name, solo limpia
                                        caché de ese artista en ese país
        """
        if artist_name and country_code:
            # Limpiar caché específico
            cache_file = self._get_cache_file_path(artist_name, country_code)
            if cache_file.exists():
                cache_file.unlink()
        elif artist_name:
            # Limpiar todos los cachés de un artista
            safe_name = "".join(x for x in artist_name if x.isalnum() or x in " _-").rstrip()
            safe_name = safe_name.replace(" ", "_").lower()

            for file in self.cache_dir.glob(f"ticketmaster_{safe_name}_*.json"):
                file.unlink()
        else:
            # Limpiar todos los cachés
            for file in self.cache_dir.glob("ticketmaster_*.json"):
                file.unlink()
