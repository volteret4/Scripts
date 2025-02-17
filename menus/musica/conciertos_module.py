import os
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import requests
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTextEdit,
                            QLabel, QLineEdit, QFileDialog, QMessageBox,
                            QHBoxLayout, QListWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from base_module import BaseModule

class ConciertosFetcher(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, api_key: str, country_code: str, artists_file: str):
        super().__init__()
        self.api_key = api_key
        self.country_code = country_code
        self.artists_file = artists_file
        self.directorio_actual = os.path.dirname(os.path.abspath(self.artists_file))
        
    def run(self):
        try:
            # Obtener fechas
            fecha_actual = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
            fecha_proxima = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Definir archivos
            json_file = os.path.join(self.directorio_actual, "filtrado.json")
            bak_file = os.path.join(self.directorio_actual, "filtrado.bak")
            
            # Leer la lista de artistas
            with open(self.artists_file, 'r', encoding='utf-8') as f:
                artistas_lista = [line.strip() for line in f if line.strip()]
            
            # Hacer backup del archivo json anterior si existe
            if os.path.exists(json_file):
                if os.path.exists(bak_file):
                    os.remove(bak_file)
                os.rename(json_file, bak_file)
            
            # Obtener datos de la API de Ticketmaster
            url = f"https://app.ticketmaster.com/discovery/v2/events.json?size=200&classificationName=music&startDateTime={fecha_actual}&endDateTime={fecha_proxima}&countryCode={self.country_code}&apikey={self.api_key}"
            
            response = requests.get(url)
            if response.status_code != 200:
                self.error.emit(f"Error en la API de Ticketmaster: {response.status_code} - {response.text}")
                return
                
            json_data = response.json()
            
            # Filtrar los conciertos según los artistas
            conciertos_filtrados = []
            
            if 'events' in json_data and json_data['events']:
                for event in json_data['events']:
                    for artista in artistas_lista:
                        if artista.lower() in event['name'].lower():
                            conciertos_filtrados.append(event)
                            break
            
            # Si no hay conciertos para los artistas, termina
            if not conciertos_filtrados:
                self.finished.emit("No se encontraron conciertos para los artistas especificados.")
                return
            
            # Guardar los conciertos filtrados como un archivo JSON
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(conciertos_filtrados, f, ensure_ascii=False, indent=2)
            
            # Comprobar existencia de archivos
            if not os.path.exists(json_file):
                self.error.emit(f"Error: El archivo '{json_file}' no existe.")
                return
                
            if not os.path.exists(bak_file) and len(conciertos_filtrados) > 0:
                # Si es la primera vez, no hay comparación que hacer
                self.finished.emit(f"Se encontraron {len(conciertos_filtrados)} conciertos. Archivo creado correctamente.")
                return
            
            # Comparar para encontrar nuevos conciertos
            if os.path.exists(bak_file):
                with open(bak_file, 'r', encoding='utf-8') as f:
                    try:
                        old_data = json.load(f)
                    except json.JSONDecodeError:
                        old_data = []
                
                old_ids = set(event.get('id', '') for event in old_data)
                new_events = [event for event in conciertos_filtrados if event.get('id', '') not in old_ids]
                
                if new_events:
                    # Guardar los nuevos conciertos en un archivo para mostrar
                    seis_meses_path = os.path.join(self.directorio_actual, "seis-meses.txt")
                    with open(seis_meses_path, 'w', encoding='utf-8') as f:
                        for event in new_events:
                            f.write(f"{event['name']} - {event.get('dates', {}).get('start', {}).get('localDate', 'Sin fecha')}\n")
                    
                    # Enviar notificación si está configurado el servicio ntfy
                    try:
                        notification_text = '\n'.join([f"{event['name']} - {event.get('dates', {}).get('start', {}).get('localDate', 'Sin fecha')}" for event in new_events])
                        requests.post(
                            "https://ntfy.pollete.duckdns.org/conciertos",
                            headers={
                                "Title": "Ticketmaster - Nuevos conciertos",
                                "Priority": "min",
                                "Tags": "loudspeaker"
                            },
                            data=notification_text
                        )
                    except Exception as e:
                        # No es crítico si falla la notificación
                        pass
                    
                    self.finished.emit(f"Se encontraron {len(conciertos_filtrados)} conciertos en total, con {len(new_events)} nuevos eventos.")
                else:
                    self.finished.emit(f"Se encontraron {len(conciertos_filtrados)} conciertos, pero no hay eventos nuevos.")
            else:
                self.finished.emit(f"Se encontraron {len(conciertos_filtrados)} conciertos. No hay eventos anteriores para comparar.")
                
        except Exception as e:
            import traceback
            self.error.emit(f"Error durante la obtención de conciertos: {str(e)}\n{traceback.format_exc()}")

class ConciertosModule(BaseModule):
    def __init__(self, api_key: str = "", country_code: str = "ES", artists_file: str = ""):
        # Primero asignamos los valores
        self.api_key = api_key
        self.country_code = country_code
        self.artists_file = artists_file
        # Luego llamamos al inicializador de la clase base
        super().__init__()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Configuración
        config_layout = QHBoxLayout()
        
        # API Key
        config_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit(self.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        config_layout.addWidget(self.api_key_input)
        
        # Country Code
        config_layout.addWidget(QLabel("País (código):"))
        self.country_code_input = QLineEdit(self.country_code)
        self.country_code_input.setMaximumWidth(50)
        config_layout.addWidget(self.country_code_input)
        
        # Archivo de artistas
        config_layout.addWidget(QLabel("Archivo de artistas:"))
        self.artists_file_input = QLineEdit(self.artists_file)
        config_layout.addWidget(self.artists_file_input)
        
        self.select_file_btn = QPushButton("...")
        self.select_file_btn.setMaximumWidth(30)
        self.select_file_btn.clicked.connect(self.select_artists_file)
        config_layout.addWidget(self.select_file_btn)
        
        layout.addLayout(config_layout)
        
        # Botón de búsqueda
        self.fetch_btn = QPushButton("Buscar Conciertos")
        self.fetch_btn.clicked.connect(self.fetch_conciertos)
        layout.addWidget(self.fetch_btn)
        
        # Lista de conciertos
        self.concerts_list = QListWidget()
        layout.addWidget(self.concerts_list)
        
        # Área de log
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        layout.addWidget(self.log_area)
        
        # Inicialización
        self.log("Módulo inicializado. Configure los parámetros y haga clic en 'Buscar Conciertos'.")
        if self.artists_file:
            self.load_existing_concerts()
    
    def select_artists_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo de artistas", "", "Archivos de texto (*.txt)"
        )
        if file_path:
            self.artists_file_input.setText(file_path)
    
    def fetch_conciertos(self):
        api_key = self.api_key_input.text().strip()
        country_code = self.country_code_input.text().strip()
        artists_file = self.artists_file_input.text().strip()
        
        if not api_key:
            QMessageBox.warning(self, "Error", "Debe proporcionar una API Key válida de Ticketmaster")
            return
            
        if not country_code:
            QMessageBox.warning(self, "Error", "Debe proporcionar un código de país válido (ej: ES, US)")
            return
            
        if not artists_file or not os.path.isfile(artists_file):
            QMessageBox.warning(self, "Error", "Seleccione un archivo de artistas válido")
            return
        
        # Guardar configuración actual
        self.api_key = api_key
        self.country_code = country_code
        self.artists_file = artists_file
        
        # Desactivar interfaz mientras se realiza la búsqueda
        self.fetch_btn.setEnabled(False)
        self.log("Obteniendo conciertos...")
        
        # Iniciar el proceso en segundo plano
        self.fetcher = ConciertosFetcher(api_key, country_code, artists_file)
        self.fetcher.finished.connect(self.on_fetch_finished)
        self.fetcher.error.connect(self.on_fetch_error)
        self.fetcher.start()
    
    def on_fetch_finished(self, message):
        self.log(message)
        self.fetch_btn.setEnabled(True)
        self.load_existing_concerts()
    
    def on_fetch_error(self, error_message):
        self.log(f"ERROR: {error_message}")
        QMessageBox.critical(self, "Error", error_message)
        self.fetch_btn.setEnabled(True)
    
    def load_existing_concerts(self):
        if not self.artists_file:
            return
            
        json_file = os.path.join(os.path.dirname(os.path.abspath(self.artists_file)), "filtrado.json")
        
        if not os.path.exists(json_file):
            self.concerts_list.clear()
            return
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                conciertos_data = json.load(f)
            
            self.concerts_list.clear()
            
            for event in conciertos_data:
                name = event.get('name', 'Sin nombre')
                date = event.get('dates', {}).get('start', {}).get('localDate', 'Sin fecha')
                venue = event.get('_embedded', {}).get('venues', [{}])[0].get('name', 'Sin lugar')
                
                self.concerts_list.addItem(f"{name} - {date} @ {venue}")
            
            self.log(f"Se cargaron {len(conciertos_data)} conciertos del archivo existente.")
            
        except Exception as e:
            self.log(f"Error al cargar el archivo de conciertos: {str(e)}")
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        # Desplazar hacia abajo
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())