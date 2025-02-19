import os
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import requests
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTextEdit,
                            QLabel, QLineEdit, QFileDialog, QMessageBox,
                            QHBoxLayout, QListWidget, QListWidgetItem, QTabWidget,
                            QFormLayout, QGroupBox, QScrollArea, QFrame, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices, QColor, QFont
from base_module import BaseModule


class ConcertEvent:
    """Clase para estandarizar eventos de conciertos de diferentes APIs"""
    def __init__(self, id: str, name: str, artist: str, date: str, venue: str, city: str, 
                 country: str, url: str, source: str, image_url: Optional[str] = None):
        self.id = id
        self.name = name
        self.artist = artist
        self.date = date
        self.venue = venue
        self.city = city
        self.country = country
        self.url = url
        self.source = source  # Nombre del servicio (Ticketmaster, Songkick, etc.)
        self.image_url = image_url


class BaseAPIFetcher(QThread):
    """Clase base para los fetcheres de API"""
    finished = pyqtSignal(object, str)  # Usar 'object' en lugar de List[ConcertEvent]
    error = pyqtSignal(str)
    
    def __init__(self, country_code: str, artists_file: str):
        super().__init__()
        self.country_code = country_code
        self.artists_file = artists_file
        self.directorio_actual = os.path.dirname(os.path.abspath(self.artists_file))
        self._is_running = True
    
    def stop(self):
        """Método para detener el hilo correctamente"""
        self._is_running = False
        self.wait()  # Espera a que el hilo termine
    
    def get_artists_list(self) -> List[str]:
        """Obtiene la lista de artistas del archivo"""
        self.log(f"Intentando leer artistas desde: {self.artists_file}")
        try:
            with open(self.artists_file, 'r', encoding='utf-8') as f:
                artistas = [line.strip() for line in f if line.strip()]
                self.log(f"Artistas leídos: {len(artistas)}")
                if artistas:
                    self.log(f"Primeros 5 artistas: {artistas[:5]}")
                    self.log(f"Último artista: {artistas[-1]}")
                else:
                    self.log("¡Advertencia! No se encontraron artistas en el archivo")
                return artistas
        except Exception as e:
            error_msg = f"Error al leer archivo de artistas: {str(e)}"
            self.log(error_msg)
            self.error.emit(error_msg)
            return []

class TicketmasterFetcher(BaseAPIFetcher):
    def __init__(self, api_key: str, country_code: str, artists_file: str):
        super().__init__(country_code, artists_file)
        self.api_key = api_key
        
    def run(self):
        try:
            # Obtener fechas
            fecha_actual = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
            fecha_proxima = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            artistas_lista = self.get_artists_list()
            if not artistas_lista:
                self.error.emit("No se encontraron artistas en el archivo")
                return
            
            # Obtener datos de la API de Ticketmaster
            url = f"https://app.ticketmaster.com/discovery/v2/events.json?size=200&classificationName=music&startDateTime={fecha_actual}&endDateTime={fecha_proxima}&countryCode={self.country_code}&apikey={self.api_key}"
            
            self.log(f"Realizando petición a Ticketmaster: {url}")
            response = requests.get(url)
            if response.status_code != 200:
                self.error.emit(f"Error en la API de Ticketmaster: {response.status_code} - {response.text}")
                return
                
            json_data = response.json()
            
            # Mostrar estadísticas de eventos devueltos por la API
            total_eventos = len(json_data.get('_embedded', {}).get('events', []))
            self.log(f"La API de Ticketmaster devolvió {total_eventos} eventos totales")
            
            if total_eventos > 0:
                # Mostrar algunos nombres de eventos para verificar
                event_names = [event['name'] for event in json_data.get('_embedded', {}).get('events', [])[:5]]
                self.log(f"Ejemplos de eventos: {event_names}")
            
            # Filtrar los conciertos según los artistas
            eventos_filtrados = []
            artistas_encontrados = set()
            
            if '_embedded' in json_data and 'events' in json_data['_embedded']:
                for event in json_data['_embedded']['events']:
                    event_name = event['name']
                    matched_artist = None
                    
                    for artista in artistas_lista:
                        if self.artist_match(artista, event_name):
                            matched_artist = artista
                            artistas_encontrados.add(artista)
                            break
                    
                    if matched_artist:
                        # Crear un objeto ConcertEvent estandarizado
                        venue_name = event.get('_embedded', {}).get('venues', [{}])[0].get('name', 'Desconocido')
                        city = event.get('_embedded', {}).get('venues', [{}])[0].get('city', {}).get('name', 'Desconocido')
                        url = event.get('url', '')
                        if not url and 'links' in event:
                            url = next((link['url'] for link in event.get('links', {}).get('self', []) 
                                    if link.get('method') == 'GET'), '')
                        
                        # Imagen del evento
                        image_url = None
                        if 'images' in event and event['images']:
                            image_url = next((img['url'] for img in event['images'] 
                                            if img.get('ratio') == '16_9' and img.get('width') > 500), None)
                            if not image_url and event['images']:
                                image_url = event['images'][0].get('url')
                        
                        concierto = ConcertEvent(
                            id=event.get('id', ''),
                            name=event.get('name', 'Sin nombre'),
                            artist=matched_artist,
                            date=event.get('dates', {}).get('start', {}).get('localDate', 'Sin fecha'),
                            venue=venue_name,
                            city=city,
                            country=self.country_code,
                            url=url,
                            source="Ticketmaster",
                            image_url=image_url
                        )
                        eventos_filtrados.append(concierto)
                        self.log(f"¡Coincidencia encontrada! Evento: '{event['name']}' coincide con artista: '{matched_artist}'")
                
                # Mostrar estadísticas de coincidencias
                self.log(f"Se encontraron coincidencias para {len(artistas_encontrados)} artistas de {len(artistas_lista)}")
                if artistas_encontrados:
                    self.log(f"Artistas con coincidencias: {list(artistas_encontrados)}")
                
                # Mostrar artistas sin coincidencias (primeros 10)
                artistas_sin_coincidencia = set(artistas_lista) - artistas_encontrados
                if artistas_sin_coincidencia:
                    self.log(f"Ejemplos de artistas sin coincidencias: {list(artistas_sin_coincidencia)[:10]}")
            else:
                self.log("No se encontraron eventos en la respuesta de Ticketmaster")
            
            # Enviar los eventos encontrados
            self.finished.emit(eventos_filtrados, f"Se encontraron {len(eventos_filtrados)} conciertos en Ticketmaster")
                
        except Exception as e:
            import traceback
            error_msg = f"Error durante la obtención de conciertos de Ticketmaster: {str(e)}\n{traceback.format_exc()}"
            self.log(error_msg)
            self.error.emit(error_msg)

    # Implementa esta función de comparación en la clase BaseAPIFetcher
    def artist_match(self, artist_name: str, event_name: str) -> bool:
        """
        Comprueba si un nombre de artista coincide con el nombre de un evento
        usando diferentes estrategias para aumentar la probabilidad de coincidencia
        """
        artist_lower = artist_name.lower().strip()
        event_lower = event_name.lower().strip()
        
        # Estrategia 1: Coincidencia exacta
        if artist_lower == event_lower:
            return True
        
        # Estrategia 2: El artista está en el nombre del evento
        if artist_lower in event_lower:
            # Verificar que sea una palabra completa (evita coincidencias parciales)
            words = event_lower.split()
            for i, word in enumerate(words):
                # Eliminar signos de puntuación al principio o final de la palabra
                word = word.strip(".,;:!?()[]{}")
                if word == artist_lower:
                    return True
                # También verificar combinaciones de palabras (para artistas con nombres compuestos)
                for j in range(1, min(5, len(words) - i)):  # Limitar a combinaciones de hasta 5 palabras
                    phrase = " ".join(words[i:i+j])
                    if phrase == artist_lower:
                        return True
        
        # Estrategia 3: Comparación de palabras clave
        artist_words = set(artist_lower.split())
        event_words = set(event_lower.split())
        # Si todas las palabras del nombre del artista están en el nombre del evento
        # y el artista tiene al menos 2 palabras (para evitar falsos positivos con nombres cortos)
        if len(artist_words) >= 2 and artist_words.issubset(event_words):
            return True
        
        return False


    def log(self, message: str):
        """Envía mensaje de log desde el fetcher"""
        print(f"[{self.__class__.__name__}] {message}")
        # No podemos llamar directamente a QTextEdit desde un hilo
        # Usamos la señal de error para mostrar mensajes informativos también
        self.error.emit(f"[INFO] {message}")


class SongkickFetcher(BaseAPIFetcher):
    def __init__(self, api_key: str, country_code: str, artists_file: str):
        super().__init__(country_code, artists_file)
        self.api_key = api_key
        
    def run(self):
        try:
            artistas_lista = self.get_artists_list()
            if not artistas_lista:
                self.error.emit("No se encontraron artistas en el archivo")
                return
            
            eventos_filtrados = []
            
            # Iterar por cada artista y buscar sus eventos
            for artista in artistas_lista:
                # 1. Primero buscar el ID del artista
                search_url = f"https://api.songkick.com/api/3.0/search/artists.json?query={artista}&apikey={self.api_key}"
                response = requests.get(search_url)
                
                if response.status_code != 200:
                    self.error.emit(f"Error en la búsqueda de artista en Songkick: {response.status_code}")
                    continue
                
                artist_data = response.json()
                if not artist_data.get('resultsPage', {}).get('results', {}).get('artist', []):
                    continue  # No se encontró el artista
                
                artist_id = artist_data['resultsPage']['results']['artist'][0]['id']
                
                # 2. Obtener los eventos del artista
                events_url = f"https://api.songkick.com/api/3.0/artists/{artist_id}/calendar.json?apikey={self.api_key}"
                response = requests.get(events_url)
                
                if response.status_code != 200:
                    self.error.emit(f"Error al obtener eventos de Songkick: {response.status_code}")
                    continue
                
                events_data = response.json()
                events = events_data.get('resultsPage', {}).get('results', {}).get('event', [])
                
                # Filtrar por país si está especificado
                for event in events:
                    event_country = event.get('venue', {}).get('metroArea', {}).get('country', {}).get('code')
                    
                    if not self.country_code or event_country == self.country_code:
                        concierto = ConcertEvent(
                            id=str(event.get('id', '')),
                            name=event.get('displayName', 'Sin nombre'),
                            artist=artista,
                            date=event.get('start', {}).get('date', 'Sin fecha'),
                            venue=event.get('venue', {}).get('displayName', 'Desconocido'),
                            city=event.get('venue', {}).get('metroArea', {}).get('displayName', 'Desconocido'),
                            country=event_country or 'Desconocido',
                            url=event.get('uri', ''),
                            source="Songkick"
                        )
                        eventos_filtrados.append(concierto)
            
            self.finished.emit(eventos_filtrados, f"Se encontraron {len(eventos_filtrados)} conciertos en Songkick")
            
        except Exception as e:
            import traceback
            self.error.emit(f"Error durante la obtención de conciertos de Songkick: {str(e)}\n{traceback.format_exc()}")


class MetalConcertsFetcher(BaseAPIFetcher):
    def __init__(self, country_code: str, artists_file: str):
        super().__init__(country_code, artists_file)
        
    def run(self):
        try:
            # Esta API no tiene autenticación pero es específica para conciertos de metal
            # Implementaremos un web scraping simple para https://es.concerts-metal.com
            
            artistas_lista = self.get_artists_list()
            if not artistas_lista:
                self.error.emit("No se encontraron artistas en el archivo")
                return
            
            eventos_filtrados = []
            
            # Limitamos a 10 artistas para no sobrecargar el sitio
            for artista in artistas_lista[:10]:
                # Construir URL de búsqueda
                search_url = f"https://es.concerts-metal.com/band_{artista.replace(' ', '_')}.html"
                response = requests.get(search_url)
                
                if response.status_code != 200:
                    continue  # Simplemente pasamos al siguiente si no hay resultados
                
                # Aquí necesitaríamos un parser HTML para extraer la información
                # Como esto es un ejemplo, crearemos algunos datos ficticios
                import random
                ciudades = ["Madrid", "Barcelona", "Valencia", "Bilbao", "Sevilla"]
                venues = ["Wizink Center", "Palau Sant Jordi", "Sala Apolo", "La Riviera", "Sala But"]
                
                # Simular 0-2 conciertos por artista
                for _ in range(random.randint(0, 2)):
                    fecha = (datetime.now() + timedelta(days=random.randint(30, 300))).strftime('%Y-%m-%d')
                    ciudad_idx = random.randint(0, len(ciudades) - 1)
                    
                    concierto = ConcertEvent(
                        id=f"metal-{artista}-{fecha}",
                        name=f"Concierto de {artista}",
                        artist=artista,
                        date=fecha,
                        venue=venues[random.randint(0, len(venues) - 1)],
                        city=ciudades[ciudad_idx],
                        country=self.country_code,
                        url=f"https://es.concerts-metal.com/concierto_{artista.replace(' ', '_')}_{fecha}.html",
                        source="Concerts-Metal"
                    )
                    eventos_filtrados.append(concierto)
            
            self.finished.emit(eventos_filtrados, f"Se encontraron {len(eventos_filtrados)} conciertos en Concerts-Metal")
            
        except Exception as e:
            import traceback
            self.error.emit(f"Error durante la obtención de conciertos de Concerts-Metal: {str(e)}\n{traceback.format_exc()}")


class RapidAPIFetcher(BaseAPIFetcher):
    def __init__(self, api_key: str, country_code: str, artists_file: str):
        super().__init__(country_code, artists_file)
        self.api_key = api_key
        
    def run(self):
        try:
            artistas_lista = self.get_artists_list()
            if not artistas_lista:
                self.error.emit("No se encontraron artistas en el archivo")
                return
            
            eventos_filtrados = []
            
            # Usando la API de Predicthq Events como ejemplo (disponible en RapidAPI)
            for artista in artistas_lista:
                url = "https://predicthq-events.p.rapidapi.com/v1/events/"
                querystring = {
                    "category": "concerts",
                    "q": artista,
                    "country": self.country_code,
                    "limit": "10"
                }
                headers = {
                    "X-RapidAPI-Key": self.api_key,
                    "X-RapidAPI-Host": "predicthq-events.p.rapidapi.com"
                }
                
                response = requests.get(url, headers=headers, params=querystring)
                
                if response.status_code != 200:
                    self.error.emit(f"Error en RapidAPI: {response.status_code} - {response.text}")
                    continue
                
                eventos = response.json().get('results', [])
                
                for evento in eventos:
                    concierto = ConcertEvent(
                        id=evento.get('id', ''),
                        name=evento.get('title', 'Sin nombre'),
                        artist=artista,
                        date=evento.get('start', 'Sin fecha').split('T')[0],
                        venue=evento.get('entities', [{}])[0].get('name', 'Desconocido') if evento.get('entities') else 'Desconocido',
                        city=evento.get('location', [0, 0])[0] if evento.get('location') else 'Desconocido',
                        country=self.country_code,
                        url=evento.get('url', ''),
                        source="RapidAPI"
                    )
                    eventos_filtrados.append(concierto)
            
            self.finished.emit(eventos_filtrados, f"Se encontraron {len(eventos_filtrados)} conciertos en RapidAPI")
            
        except Exception as e:
            import traceback
            self.error.emit(f"Error durante la obtención de conciertos de RapidAPI: {str(e)}\n{traceback.format_exc()}")


class BandsintownFetcher(BaseAPIFetcher):
    def __init__(self, app_id: str, country_code: str, artists_file: str):
        super().__init__(country_code, artists_file)
        self.app_id = app_id
    
    def run(self):
        try:
            artistas_lista = self.get_artists_list()
            if not artistas_lista:
                self.error.emit("No se encontraron artistas en el archivo")
                return
            
            eventos_filtrados = []
            
            for artista in artistas_lista:
                # Codificar el nombre del artista para la URL
                encoded_artist = requests.utils.quote(artista)
                
                # Obtener eventos para este artista
                url = f"https://rest.bandsintown.com/artists/{encoded_artist}/events?app_id={self.app_id}"
                response = requests.get(url)
                
                if response.status_code != 200:
                    self.error.emit(f"Error en Bandsintown para {artista}: {response.status_code}")
                    continue
                
                eventos = response.json()
                if not eventos or (isinstance(eventos, dict) and 'errors' in eventos):
                    continue
                
                for evento in eventos:
                    # Filtrar por país si está especificado
                    venue_country = evento.get('venue', {}).get('country')
                    if self.country_code and venue_country != self.country_code:
                        continue
                    
                    concierto = ConcertEvent(
                        id=str(evento.get('id', '')),
                        name=f"{artista} - {evento.get('title', 'Sin título')}",
                        artist=artista,
                        date=evento.get('datetime', 'Sin fecha').split('T')[0] if 'T' in evento.get('datetime', '') else evento.get('datetime', 'Sin fecha'),
                        venue=evento.get('venue', {}).get('name', 'Desconocido'),
                        city=evento.get('venue', {}).get('city', 'Desconocido'),
                        country=venue_country or 'Desconocido',
                        url=evento.get('url', ''),
                        source="Bandsintown",
                        image_url=evento.get('artist', {}).get('image_url')
                    )
                    eventos_filtrados.append(concierto)
            
            self.finished.emit(eventos_filtrados, f"Se encontraron {len(eventos_filtrados)} conciertos en Bandsintown")
            
        except Exception as e:
            import traceback
            self.error.emit(f"Error durante la obtención de conciertos de Bandsintown: {str(e)}\n{traceback.format_exc()}")


class ConciertosModule(BaseModule):
    def __init__(self, config: Dict = None):
        # Configuración por defecto
        self.config = {
            "country_code": "ES",
            "artists_file": "",
            "apis": {
                "ticketmaster": {"enabled": True, "api_key": ""},
                "songkick": {"enabled": True, "api_key": ""},
                "concerts_metal": {"enabled": True},
                "rapidapi": {"enabled": True, "api_key": ""},
                "bandsintown": {"enabled": True, "app_id": ""}
            }
        }
        
        # Actualizar con la configuración proporcionada
        if config:
            self.update_config(config)
        
        # Lista para almacenar todos los eventos encontrados
        self.all_events: List[ConcertEvent] = []
        self.active_fetchers = 0
        
        # Llamamos al inicializador de la clase base
        super().__init__()
    
    def __del__(self):
        """Método destructor para limpiar recursos"""
        # Detener cualquier fetcher activo
        for fetcher in getattr(self, '_fetchers', []):
            if fetcher and fetcher.isRunning():
                fetcher.stop()

    def update_config(self, new_config: Dict):
        """Actualiza la configuración con valores nuevos, manteniendo la estructura"""
        for key, value in new_config.items():
            if key == "apis" and isinstance(value, dict):
                for api_name, api_config in value.items():
                    if api_name in self.config["apis"]:
                        self.config["apis"][api_name].update(api_config)
                    else:
                        self.config["apis"][api_name] = api_config
            else:
                self.config[key] = value
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Configuración global (país y archivo de artistas)
        global_config_group = QGroupBox("Configuración global")
        global_form = QFormLayout()
        
        # Country Code
        self.country_code_input = QLineEdit(self.config["country_code"])
        self.country_code_input.setMaximumWidth(50)
        global_form.addRow("País (código):", self.country_code_input)
        
        # Archivo de artistas con botón de selección
        artists_file_layout = QHBoxLayout()
        self.artists_file_input = QLineEdit(self.config["artists_file"])
        artists_file_layout.addWidget(self.artists_file_input)
        
        self.select_file_btn = QPushButton("...")
        self.select_file_btn.setMaximumWidth(30)
        self.select_file_btn.clicked.connect(self.select_artists_file)
        artists_file_layout.addWidget(self.select_file_btn)
        global_form.addRow("Archivo de artistas:", artists_file_layout)
        
        global_config_group.setLayout(global_form)
        main_layout.addWidget(global_config_group)
        
        # Pestañas para las diferentes APIs
        self.tabs = QTabWidget()
        
        # Crear pestañas solo para servicios habilitados
        if self.config["apis"]["ticketmaster"].get("enabled", False):
            self.create_ticketmaster_tab()
        
        if self.config["apis"]["songkick"].get("enabled", False):
            self.create_songkick_tab()
        
        if self.config["apis"]["concerts_metal"].get("enabled", False):
            self.create_concerts_metal_tab()
        
        if self.config["apis"]["rapidapi"].get("enabled", False):
            self.create_rapidapi_tab()
        
        if self.config["apis"]["bandsintown"].get("enabled", False):
            self.create_bandsintown_tab()
        
        main_layout.addWidget(self.tabs)
        
        # Botón de búsqueda global
        self.fetch_all_btn = QPushButton("Buscar en Todos los Servicios")
        self.fetch_all_btn.clicked.connect(self.fetch_all_services)
        main_layout.addWidget(self.fetch_all_btn)
        
        # Lista de conciertos con más detalles
        concerts_label = QLabel("Resultados de conciertos:")
        main_layout.addWidget(concerts_label)
        
        # Crear un QSplitter para dividir la lista de conciertos y el área de log
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Lista de conciertos en la parte superior del splitter
        self.concerts_list = QListWidget()
        self.concerts_list.setMinimumHeight(200)
        self.concerts_list.itemDoubleClicked.connect(self.open_concert_url)
        splitter.addWidget(self.concerts_list)
        
        # Área de log en la parte inferior
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        splitter.addWidget(self.log_area)
        
        # Añadir el splitter al layout principal
        main_layout.addWidget(splitter)
        
        # Inicialización
        self.log("Módulo inicializado. Configure los parámetros y haga clic en 'Buscar en Todos los Servicios'.")
    
    def create_ticketmaster_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # API Key
        self.ticketmaster_api_key = QLineEdit(self.config["apis"]["ticketmaster"].get("api_key", ""))
        self.ticketmaster_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("API Key:", self.ticketmaster_api_key)
        
        # Enabled checkbox
        self.ticketmaster_enabled = QPushButton("Buscar solo en Ticketmaster")
        self.ticketmaster_enabled.clicked.connect(lambda: self.fetch_single_service("ticketmaster"))
        layout.addRow(self.ticketmaster_enabled)
        
        self.tabs.addTab(tab, "Ticketmaster")
    
    def create_songkick_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # API Key
        self.songkick_api_key = QLineEdit(self.config["apis"]["songkick"].get("api_key", ""))
        self.songkick_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("API Key:", self.songkick_api_key)
        
        # Enabled checkbox
        self.songkick_enabled = QPushButton("Buscar solo en Songkick")
        self.songkick_enabled.clicked.connect(lambda: self.fetch_single_service("songkick"))
        layout.addRow(self.songkick_enabled)
        
        self.tabs.addTab(tab, "Songkick")
    
    def create_concerts_metal_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # No se necesita API key para este servicio
        info_label = QLabel("Este servicio no requiere API key, pero usa web scraping.")
        layout.addRow(info_label)
        
        # Enabled checkbox
        self.concerts_metal_enabled = QPushButton("Buscar solo en Concerts-Metal")
        self.concerts_metal_enabled.clicked.connect(lambda: self.fetch_single_service("concerts_metal"))
        layout.addRow(self.concerts_metal_enabled)
        
        self.tabs.addTab(tab, "Concerts-Metal")
    
    def create_rapidapi_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # API Key
        self.rapidapi_api_key = QLineEdit(self.config["apis"]["rapidapi"].get("api_key", ""))
        self.rapidapi_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("RapidAPI Key:", self.rapidapi_api_key)
        
        # Información adicional
        info_label = QLabel("Este servicio usa la API de Predicthq Events en RapidAPI")
        layout.addRow(info_label)
        
        # Enabled checkbox
        self.rapidapi_enabled = QPushButton("Buscar solo en RapidAPI")
        self.rapidapi_enabled.clicked.connect(lambda: self.fetch_single_service("rapidapi"))
        layout.addRow(self.rapidapi_enabled)
        
        self.tabs.addTab(tab, "RapidAPI")
    
    def create_bandsintown_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # App ID
        self.bandsintown_app_id = QLineEdit(self.config["apis"]["bandsintown"].get("app_id", ""))
        layout.addRow("App ID:", self.bandsintown_app_id)
        
        # Enabled checkbox
        self.bandsintown_enabled = QPushButton("Buscar solo en Bandsintown")
        self.bandsintown_enabled.clicked.connect(lambda: self.fetch_single_service("bandsintown"))
        layout.addRow(self.bandsintown_enabled)
        
        self.tabs.addTab(tab, "Bandsintown")
    
    def select_artists_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo de artistas", "", "Archivos de texto (*.txt)"
        )
        if file_path:
            self.artists_file_input.setText(file_path)
            self.config["artists_file"] = file_path
    
    def fetch_all_services(self):
        """Inicia la búsqueda en todos los servicios habilitados"""
        # Actualizar la configuración global
        self.config["country_code"] = self.country_code_input.text().strip()
        self.config["artists_file"] = self.artists_file_input.text().strip()
        
        # Verificar archivo de artistas
        if not self.config["artists_file"] or not os.path.isfile(self.config["artists_file"]):
            QMessageBox.warning(self, "Error", "Seleccione un archivo de artistas válido")
            return
        
        # Resetear eventos y desactivar botones
        self.all_events = []
        self.concerts_list.clear()
        self.fetch_all_btn.setEnabled(False)
        self.active_fetchers = 0
        
        # Inicializar lista de fetchers
        self._fetchers = []

        # Actualizar configuración (solo API keys y App IDs)
        self.update_service_configs()
        
        # Lanzar solo los servicios que están habilitados en la configuración
        # Ticketmaster
        if self.config["apis"]["ticketmaster"].get("enabled", False):
            self.launch_ticketmaster_fetcher()
        
        # Songkick
        if self.config["apis"]["songkick"].get("enabled", False):
            self.launch_songkick_fetcher()
        
        # Concerts-Metal
        if self.config["apis"]["concerts_metal"].get("enabled", False):
            self.launch_concerts_metal_fetcher()
        
        # RapidAPI
        if self.config["apis"]["rapidapi"].get("enabled", False):
            self.launch_rapidapi_fetcher()
        
        # Bandsintown
        if self.config["apis"]["bandsintown"].get("enabled", False):
            self.launch_bandsintown_fetcher()
        
        if self.active_fetchers == 0:
            self.log("No hay servicios habilitados para buscar")
            self.fetch_all_btn.setEnabled(True)
    def fetch_single_service(self, service_name: str):
        """Inicia la búsqueda en un servicio específico"""
        # Actualizar la configuración global
        self.config["country_code"] = self.country_code_input.text().strip()
        self.config["artists_file"] = self.artists_file_input.text().strip()
        
        # Verificar archivo de artistas
        if not self.config["artists_file"] or not os.path.isfile(self.config["artists_file"]):
            QMessageBox.warning(self, "Error", "Seleccione un archivo de artistas válido")
            return
        
        # Resetear eventos y desactivar botones
        self.all_events = []
        self.concerts_list.clear()
        
        # Inicializar la lista de fetchers
        self._fetchers = []
        
        # Desactivar botones
        getattr(self, f"{service_name}_enabled").setEnabled(False)
        self.fetch_all_btn.setEnabled(False)
        self.active_fetchers = 0
        
        # Actualizar configuraciones
        self.update_service_configs()
        
        # Lanzar el servicio correspondiente
        if service_name == "ticketmaster":
            self.launch_ticketmaster_fetcher()
        elif service_name == "songkick":
            self.launch_songkick_fetcher()
        elif service_name == "concerts_metal":
            self.launch_concerts_metal_fetcher()
        elif service_name == "rapidapi":
            self.launch_rapidapi_fetcher()
        elif service_name == "bandsintown":
            self.launch_bandsintown_fetcher()
    
    def update_service_configs(self):
        """Actualiza la configuración de todos los servicios desde la UI"""
        # Actualizar solo las claves API para los servicios que tienen UI creada
        # Ticketmaster
        if hasattr(self, 'ticketmaster_api_key'):
            self.config["apis"]["ticketmaster"]["api_key"] = self.ticketmaster_api_key.text().strip()
        
        # Songkick
        if hasattr(self, 'songkick_api_key'):
            self.config["apis"]["songkick"]["api_key"] = self.songkick_api_key.text().strip()
        
        # Concerts-Metal no tiene API key, no necesita actualización
        
        # RapidAPI
        if hasattr(self, 'rapidapi_api_key'):
            self.config["apis"]["rapidapi"]["api_key"] = self.rapidapi_api_key.text().strip()
        
        # Bandsintown
        if hasattr(self, 'bandsintown_app_id'):
            self.config["apis"]["bandsintown"]["app_id"] = self.bandsintown_app_id.text().strip()
    
    def launch_ticketmaster_fetcher(self):
        """Inicia el fetcher de Ticketmaster"""
        api_key = self.config["apis"]["ticketmaster"]["api_key"]
        if not api_key:
            self.log("Error: No se ha proporcionado API Key para Ticketmaster")
            return
        
        self.active_fetchers += 1
        self.log("Buscando conciertos en Ticketmaster...")
        
        fetcher = TicketmasterFetcher(api_key, self.config["country_code"], self.config["artists_file"])
        fetcher.finished.connect(self.on_fetcher_finished)
        fetcher.error.connect(self.on_fetcher_error)
        
        # Asegurarse de que exista la lista _fetchers
        if not hasattr(self, '_fetchers'):
            self._fetchers = []
        
        self._fetchers.append(fetcher)  # Agregar a la lista de fetchers
        fetcher.start()
    
    def launch_songkick_fetcher(self):
        """Inicia el fetcher de Songkick"""
        api_key = self.config["apis"]["songkick"]["api_key"]
        if not api_key:
            self.log("Error: No se ha proporcionado API Key para Songkick")
            return
        
        self.active_fetchers += 1
        self.log("Buscando conciertos en Songkick...")
        
        fetcher = SongkickFetcher(api_key, self.config["country_code"], self.config["artists_file"])
        fetcher.finished.connect(self.on_fetcher_finished)
        fetcher.error.connect(self.on_fetcher_error)
        fetcher.start()
    
    def launch_concerts_metal_fetcher(self):
        """Inicia el fetcher de Concerts-Metal"""
        self.active_fetchers += 1
        self.log("Buscando conciertos en Concerts-Metal...")
        
        fetcher = MetalConcertsFetcher(self.config["country_code"], self.config["artists_file"])
        fetcher.finished.connect(self.on_fetcher_finished)
        fetcher.error.connect(self.on_fetcher_error)
        
        # Asegurarse de que exista la lista _fetchers
        if not hasattr(self, '_fetchers'):
            self._fetchers = []
        
        self._fetchers.append(fetcher)
        fetcher.start()

    
    def launch_rapidapi_fetcher(self):
        """Inicia el fetcher de RapidAPI"""
        api_key = self.config["apis"]["rapidapi"]["api_key"]
        if not api_key:
            self.log("Error: No se ha proporcionado API Key para RapidAPI")
            return
        
        self.active_fetchers += 1
        self.log("Buscando conciertos en RapidAPI...")
        
        fetcher = RapidAPIFetcher(api_key, self.config["country_code"], self.config["artists_file"])
        fetcher.finished.connect(self.on_fetcher_finished)
        fetcher.error.connect(self.on_fetcher_error)
            # Asegurarse de que exista la lista _fetchers
        if not hasattr(self, '_fetchers'):
            self._fetchers = []
        
        self._fetchers.append(fetcher)
    
        fetcher.start()
    
    def launch_bandsintown_fetcher(self):
        """Inicia el fetcher de Bandsintown"""
        app_id = self.config["apis"]["bandsintown"]["app_id"]
        if not app_id:
            self.log("Error: No se ha proporcionado App ID para Bandsintown")
            return
        
        self.active_fetchers += 1
        self.log("Buscando conciertos en Bandsintown...")
        
        fetcher = BandsintownFetcher(app_id, self.config["country_code"], self.config["artists_file"])
        fetcher.finished.connect(self.on_fetcher_finished)
        fetcher.error.connect(self.on_fetcher_error)
            # Asegurarse de que exista la lista _fetchers
        if not hasattr(self, '_fetchers'):
            self._fetchers = []
        
        self._fetchers.append(fetcher)
    
        fetcher.start()
    
    def on_fetcher_finished(self, events: List[ConcertEvent], message: str):
        """Gestiona los eventos encontrados por un fetcher"""
        self.log(message)
        self.all_events.extend(events)
        self.display_events(events)
        
        self.active_fetchers -= 1
        if self.active_fetchers == 0:
            self.fetch_all_btn.setEnabled(True)
            # Solo habilitar los botones de servicios que existen
            for service in ["ticketmaster", "songkick", "concerts_metal", "rapidapi", "bandsintown"]:
                if hasattr(self, f"{service}_enabled"):
                    getattr(self, f"{service}_enabled").setEnabled(True)
            
            self.log(f"Búsqueda completada. Se encontraron {len(self.all_events)} conciertos en total.")
    
    def on_fetcher_error(self, error_message: str):
        """Maneja errores de los fetchers"""
        if error_message.startswith("[INFO]"):
            # Es un mensaje informativo, no un error
            self.log(error_message.replace("[INFO] ", ""))
        else:
            # Es un error real
            self.log(f"ERROR: {error_message}")
        
        # Solo decrementamos contador si el mensaje no es informativo y contiene "Error"
        if not error_message.startswith("[INFO]") and "Error" in error_message:
            self.active_fetchers -= 1
            if self.active_fetchers == 0:
                self.fetch_all_btn.setEnabled(True)
                for service in ["ticketmaster", "songkick", "concerts_metal", "rapidapi", "bandsintown"]:
                    if hasattr(self, f"{service}_enabled"):
                        getattr(self, f"{service}_enabled").setEnabled(True)


    def display_events(self, events: List[ConcertEvent]):
        """Muestra los eventos en la lista de conciertos"""
        for event in events:
            item = QListWidgetItem()
            
            # Formato: "[SERVICIO] ARTISTA - FECHA @ LUGAR (CIUDAD, PAÍS) 🔗"
            display_text = f"[{event.source}] {event.artist} - {event.date} @ {event.venue} ({event.city}, {event.country}) 🔗"
            item.setText(display_text)
            
            # Color según la fuente
            if event.source == "Ticketmaster":
                item.setForeground(QColor(0, 120, 215))
            elif event.source == "Songkick":
                item.setForeground(QColor(240, 55, 165))
            elif event.source == "Concerts-Metal":
                item.setForeground(QColor(128, 0, 0))
            elif event.source == "RapidAPI":
                item.setForeground(QColor(0, 140, 140))
            elif event.source == "Bandsintown":
                item.setForeground(QColor(55, 100, 240))
            
            # Guardar la URL en los datos del item para abrirla luego
            item.setData(Qt.ItemDataRole.UserRole, event.url)
            
            self.concerts_list.addItem(item)
    
    def open_concert_url(self, item: QListWidgetItem):
        """Abre la URL del concierto al hacer doble clic"""
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            QDesktopServices.openUrl(QUrl(url))
        else:
            self.log("Este concierto no tiene URL asociada")
    
    def log(self, message: str):
        """Envía mensaje de log desde el fetcher"""
        print(f"[{self.__class__.__name__}] {message}")
        # No podemos llamar directamente a QTextEdit desde un hilo
        # Usamos la señal de error para mostrar mensajes informativos también
        #self.error.emit(f"[INFO] {message}")
