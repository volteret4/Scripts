import logging
import requests
from bs4 import BeautifulSoup
import re
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
                            QLabel, QScrollArea, QWidget, QComboBox, QProgressBar,
                            QSplitter, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtWebEngineWidgets import QWebEngineView
from base_module import BaseModule

class MusicSearchModule(BaseModule):
    """Módulo de búsqueda de música en Bandcamp y SoundCloud"""
    
    def __init__(self, parent=None, theme='Tokyo Night'):
        super().__init__(parent, theme)
            # Configurar fontconfig antes de inicializar la UI
        self.setup_fontconfig()
        
        # Verificar dependencias
        self.dependencies_ok = self.check_dependencies()
    
    
    def init_ui(self):
        """Inicializa la interfaz del módulo"""
        # Layout principal
        self.main_layout = QVBoxLayout(self)
        
        # Sección de búsqueda
        self.search_layout = QHBoxLayout()
        
        # Selector de fuente de búsqueda
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Todos", "Bandcamp", "SoundCloud"])
        self.search_layout.addWidget(self.source_combo)
        
        # Campo de búsqueda
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar artista, álbum o canción...")
        self.search_input.returnPressed.connect(self.perform_search)
        self.search_layout.addWidget(self.search_input, 1)
        
        # Botón de búsqueda
        self.search_button = QPushButton("Buscar")
        self.search_button.clicked.connect(self.perform_search)
        self.search_layout.addWidget(self.search_button)
        
        self.main_layout.addLayout(self.search_layout)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)
        
        # Área de resultados
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_scroll.setWidget(self.results_widget)
        
        # Crear un separador
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Área para mostrar la información del álbum seleccionado
        self.info_frame = QFrame()
        self.info_layout = QVBoxLayout(self.info_frame)
        self.info_title = QLabel("Selecciona un álbum para ver más detalles")
        self.info_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_layout.addWidget(self.info_title)
        
        # WebView para mostrar el iframe embebido
        try:
            self.web_view = QWebEngineView()
            self.web_view.setMinimumHeight(150)
            self.web_view.setMaximumHeight(200)
            self.info_layout.addWidget(self.web_view)
        except Exception as e:
            logging.error(f"Error creando QWebEngineView: {e}")
            self.web_view = None
            self.info_layout.addWidget(QLabel("No se pudo cargar el reproductor web. Verifica la instalación de QtWebEngine."))
        
        # Configurar el splitter
        self.splitter.addWidget(self.results_scroll)
        self.splitter.addWidget(self.info_frame)
        self.splitter.setSizes([2000, 1000])  # Distribución inicial del splitter
        
        self.main_layout.addWidget(self.splitter)
        
        # Estado inicial
        self.search_results = []
        self.current_result = None
        
        self.setup_module()
    
    def setup_module(self):
        """Configuración adicional del módulo"""
        # Configurar para ignorar errores SSL en QtWebEngine (solo para desarrollo)
        try:
            if self.web_view:
                from PyQt6.QtWebEngineCore import QWebEngineSettings
                settings = self.web_view.settings()
                settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
                settings.setAttribute(QWebEngineSettings.WebAttribute.WebSecurityEnabled, False)
                logging.info("Configuración de seguridad WebEngine modificada para desarrollo")
        except Exception as e:
            logging.error(f"Error configurando WebEngine: {e}")
        
        # Desactivar advertencias de SSL para requests (solo para desarrollo)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def perform_search(self):
        """Realiza la búsqueda según los parámetros ingresados"""
        query = self.search_input.text().strip()
        if not query:
            return
        
        self.clear_results()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        
        # Determinar las fuentes de búsqueda
        source = self.source_combo.currentText()
        
        # Iniciar el hilo de búsqueda
        self.search_thread = SearchThread(query, source)
        self.search_thread.progress_update.connect(self.update_progress)
        self.search_thread.search_complete.connect(self.display_results)
        self.search_thread.start()
    
    def update_progress(self, progress):
        """Actualiza el progreso de la búsqueda"""
        self.progress_bar.setValue(progress)
    
    def clear_results(self):
        """Limpia los resultados anteriores"""
        # Limpiar el layout de resultados
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Restablecer la información
        self.info_title.setText("Selecciona un álbum para ver más detalles")
        if self.web_view:
            self.web_view.setHtml("")
        
        self.search_results = []
        self.current_result = None
    
    def display_results(self, results):
        """Muestra los resultados de búsqueda"""
        self.search_results = results
        self.progress_bar.setVisible(False)
        
        if not results:
            no_results = QLabel("No se encontraron resultados")
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_layout.addWidget(no_results)
            return
        
        # Crear widgets para cada resultado
        for i, result in enumerate(results):
            result_widget = self.create_result_widget(result, i)
            self.results_layout.addWidget(result_widget)
        
        # Agregar un widget espaciador al final
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.results_layout.addWidget(spacer)
    
    def create_result_widget(self, result, index):
        """Crea un widget para mostrar un resultado de búsqueda"""
        frame = QFrame()
        frame.setObjectName(f"result_{index}")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setFrameShadow(QFrame.Shadow.Raised)
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(frame)
        
        # Título del resultado
        title_label = QLabel(f"<b>{result['title']}</b>")
        layout.addWidget(title_label)
        
        # Artista
        artist_label = QLabel(f"Artista: {result['artist']}")
        layout.addWidget(artist_label)
        
        # Fuente (Bandcamp o SoundCloud)
        source_label = QLabel(f"Fuente: {result['source'].capitalize()}")
        layout.addWidget(source_label)
        
        # URL (mostrar como link)
        url_label = QLabel(f"<a href='{result['url']}'>{result['url']}</a>")
        url_label.setOpenExternalLinks(True)
        layout.addWidget(url_label)
        
        # Conectar evento de clic
        frame.mousePressEvent = lambda e, r=result: self.show_result_details(r)
        
        return frame
    
    def show_result_details(self, result):
        """Muestra los detalles de un resultado seleccionado"""
        self.current_result = result
        
        # Actualizar el título
        self.info_title.setText(f"{result['title']} - {result['artist']}")
        
        
        # Mostrar el iframe embebido si está disponible, o una vista alternativa si no lo está
        if self.web_view:
            if 'embed_html' in result and result['embed_html']:
                self.web_view.setHtml(result['embed_html'])
            else:
                # Crear una vista alternativa para mostrar los detalles del resultado
                source_icon = "🎵" if result['source'] == 'soundcloud' else "📀"
                html_content = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; text-align: center; }}
                        h2 {{ color: #333; }}
                        .details {{ margin: 15px 0; }}
                        .source {{ font-style: italic; color: #777; }}
                        .link {{ margin-top: 15px; }}
                        a {{ color: #0366d6; text-decoration: none; }}
                        a:hover {{ text-decoration: underline; }}
                    </style>
                </head>
                <body>
                    <h2>{source_icon} {result['title']}</h2>
                    <div class="details">Artista: {result['artist']}</div>
                    <div class="source">Fuente: {result['source'].capitalize()}</div>
                    <div class="link">
                        <a href="{result['url']}" target="_blank">Abrir en {result['source'].capitalize()}</a>
                    </div>
                </body>
                </html>
                """
                self.web_view.setHtml(html_content)
    
    def search_bandcamp(self, query):
        """Search for music on Bandcamp and get embedded players"""
        try:
            # Format search URL
            search_url = f"https://bandcamp.com/search?q={query.replace(' ', '+')}"
            # Send request with fake user agent to avoid being blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://bandcamp.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            }
            logging.info(f"Realizando búsqueda en Bandcamp: {search_url}")
            
            # Añadir verificación SSL desactivada para desarrollo
            response = requests.get(search_url, headers=headers, timeout=15, verify=False)
            
            if response.status_code != 200:
                logging.error(f"Error buscando en Bandcamp: Status code {response.status_code}")
                return []
            
            # Parse HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            # Find results - Bandcamp specific structure
            results = soup.select('li.searchresult')
            
            if not results:
                # Intentar con selector alternativo en caso de cambios en la estructura
                results = soup.select('.result-items li')
                logging.info(f"Usando selector alternativo para Bandcamp: encontrados {len(results)} resultados")
            
            bandcamp_results = []
            for result in results[:5]:  # Limit to 5 results
                try:
                    title_elem = result.select_one('.heading') or result.select_one('div.heading a')
                    artist_elem = result.select_one('.subhead') or result.select_one('.itemsubtext')
                    # Buscar enlaces específicos a álbumes/tracks dentro del resultado
                    album_link = result.select_one('a[href*="/album/"], a[href*="/track/"]')
                    
                    if not album_link:
                        link_elem = result.select_one('a.artcont') or result.select_one('a')
                        url = link_elem['href'] if link_elem and 'href' in link_elem.attrs else None
                    else:
                        url = album_link['href']
                    
                    if title_elem and url:
                        title = title_elem.text.strip()
                        artist = artist_elem.text.strip() if artist_elem else "Unknown Artist"
                        
                        # Si la URL no tiene protocolo, añadirlo
                        if url.startswith('//'):
                            url = 'https:' + url
                        elif not url.startswith('http'):
                            # Si es relativa sin //, añadir dominio completo
                            url = f"https://bandcamp.com{url}" if url.startswith('/') else f"https://bandcamp.com/{url}"
                        
                        # Extraer el ID del álbum o pista de la URL
                        album_id = None
                        
                        # Intentar obtener el ID del álbum desde la URL
                        # Las URLs típicas de Bandcamp son como: https://artist.bandcamp.com/album/album_name
                        # o https://bandcamp.com/album/1234567890
                        album_match = re.search(r'/album/(\d+)', url)
                        if album_match:
                            album_id = album_match.group(1)
                        else:
                            # Intentar buscar el ID por otro método
                            track_match = re.search(r'/track/(\d+)', url)
                            if track_match:
                                album_id = track_match.group(1)
                        
                        # Si no se encontró un ID numérico, usar toda la URL para el embebido
                        parsed_url = urlparse(url)
                        domain = parsed_url.netloc
                        path = parsed_url.path
                        
                        # Crear un iframe que use la URL completa en lugar de intentar extraer IDs
                        embed_html = f'''
                        <iframe style="border: 0; width: 100%; height: 120px;" 
                                src="https://bandcamp.com/EmbeddedPlayer/size=large/bgcol=ffffff/linkcol=0687f5/tracklist=false/artwork=small/transparent=true/" 
                                seamless>
                            <a href="{url}">{title} by {artist}</a>
                        </iframe>
                        '''
                        bandcamp_results.append({
                            "source": "bandcamp",
                            "title": title,
                            "artist": artist,
                            "url": url,
                            "embed_html": embed_html
                        })
                        logging.info(f"Encontrado en Bandcamp: {title} - {artist} - URL: {url}")
                except Exception as e:
                    logging.error(f"Error analizando resultado de Bandcamp: {e}")
            return bandcamp_results
        except Exception as e:
            logging.error(f"Error buscando en Bandcamp: {e}")
            # Mostrar más detalles del error
            import traceback
            logging.error(traceback.format_exc())
            return []

    def search_soundcloud(self, query):
        """Search for music on SoundCloud and get embed URLs"""
        try:
            # Format search URL
            search_url = f"https://soundcloud.com/search?q={query.replace(' ', '%20')}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://soundcloud.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            
            logging.info(f"Realizando búsqueda en SoundCloud: {search_url}")
            # Añadir verificación SSL desactivada para desarrollo (solo usar en desarrollo)
            response = requests.get(search_url, headers=headers, timeout=15, verify=False)
            
            if response.status_code != 200:
                logging.error(f"Error buscando en SoundCloud: Status code {response.status_code}")
                return []
            
            # Parse HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # SoundCloud structure is more complex due to JavaScript rendering
            # Intentar varios selectores para adaptarse a cambios en la estructura
            soundcloud_results = []
            
            # Métodos de búsqueda - probar diferentes selectores
            selectors = [
                'h2 a[href^="/"]',
                'a.soundTitle__title',
                'a[itemprop="url"]',
                '.sound__content a'
            ]
            
            track_elements = []
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    track_elements = elements
                    logging.info(f"SoundCloud: usando selector {selector}, encontrados {len(elements)} elementos")
                    break
            
            # Si no encontramos resultados, buscar URLs en el script JSON
            if not track_elements:
                logging.info("Intentando extraer datos de SoundCloud desde scripts JSON")
                try:
                    # Buscar datos en scripts JSON
                    scripts = soup.find_all('script')
                    for script in scripts:
                        if script.string and '"url":' in script.string and '"title":' in script.string:
                            # Extraer URLs y títulos con regex
                            urls = re.findall(r'"url":"(https://soundcloud.com/[^"]+)"', script.string)
                            titles = re.findall(r'"title":"([^"]+)"', script.string)
                            artists = re.findall(r'"username":"([^"]+)"', script.string)
                            
                            # Crear resultados a partir de los datos encontrados
                            for i in range(min(len(urls), len(titles), 5)):
                                full_url = urls[i].replace('\\u0026', '&')
                                title = titles[i]
                                artist = artists[i] if i < len(artists) else "Unknown Artist"
                                
                                embed_html = f'<iframe width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay" src="https://w.soundcloud.com/player/?url={full_url}&color=%23ff5500&auto_play=false&hide_related=false&show_comments=false&show_user=true&show_reposts=false&show_teaser=true"></iframe>'
                                
                                soundcloud_results.append({
                                    "source": "soundcloud",
                                    "title": title,
                                    "artist": artist,
                                    "url": full_url,
                                    "embed_html": embed_html
                                })
                                logging.info(f"Encontrado en SoundCloud (JSON): {title} - URL: {full_url}")                        
                except Exception as e:
                    logging.error(f"Error extrayendo JSON de SoundCloud: {e}")
            
            # Procesar elementos de track encontrados por selectores
            for i, track_element in enumerate(track_elements[:5]):
                try:
                    url_path = track_element.get('href', '')
                    if not url_path or not url_path.startswith('/'):
                        continue
                        
                    # Get full URL
                    full_url = f"https://soundcloud.com{url_path}"
                    
                    # Get title from the link text
                    title = track_element.get_text().strip()
                    
                    # Try to find the artist (probar diferentes selectores)
                    artist = "Unknown Artist"
                    artist_selectors = [
                        # Intentar encontrar elemento hermano o padre que contenga el artista
                        lambda el: el.find_previous('a', attrs={'class': 'soundTitle__username'}),
                        lambda el: el.find_previous('span', attrs={'class': 'soundTitle__username'}),
                        lambda el: el.parent.find_next('a', attrs={'class': 'soundTitle__username'}),
                        lambda el: el.find_parent('div').find_previous('a', attrs={'itemprop': 'author'})
                    ]
                    
                    for selector_func in artist_selectors:
                        artist_element = selector_func(track_element)
                        if artist_element:
                            artist = artist_element.get_text().strip()
                            break
                    
                    # Create embed HTML
                    embed_html = f'<iframe width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay" src="https://w.soundcloud.com/player/?url={full_url}&color=%23ff5500&auto_play=false&hide_related=false&show_comments=false&show_user=true&show_reposts=false&show_teaser=true"></iframe>'
                    
                    soundcloud_results.append({
                        "source": "soundcloud",
                        "title": title,
                        "artist": artist,
                        "url": full_url,
                        "embed_html": embed_html
                    })
                    logging.info(f"Encontrado en SoundCloud: {title} - URL: {full_url}")
                except Exception as e:
                    logging.error(f"Error analizando resultado de SoundCloud: {e}")
            
            return soundcloud_results
        except Exception as e:
            logging.error(f"Error buscando en SoundCloud: {e}")
            # Mostrar más detalles del error
            import traceback
            logging.error(traceback.format_exc())
            return []


    def setup_fontconfig(self):
        """Configura fontconfig para evitar errores en sistemas Linux"""
        import os
        import platform
        
        if platform.system() == 'Linux':
            try:
                # Verificar si existe el archivo de configuración de fontconfig
                fontconfig_paths = [
                    '/etc/fonts/fonts.conf',
                    '/usr/share/fontconfig/conf.avail/fonts.conf',
                    '/usr/local/etc/fonts/fonts.conf'
                ]
                
                fontconfig_exists = any(os.path.exists(path) for path in fontconfig_paths)
                
                if not fontconfig_exists:
                    logging.warning("No se encontró el archivo de configuración de fontconfig")
                    
                    # Crear un archivo de configuración básico si no existe
                    user_config_dir = os.path.expanduser('~/.config/fontconfig')
                    os.makedirs(user_config_dir, exist_ok=True)
                    
                    user_config_file = os.path.join(user_config_dir, 'fonts.conf')
                    
                    if not os.path.exists(user_config_file):
                        with open(user_config_file, 'w') as f:
                            f.write('''<?xml version="1.0"?>
    <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
    <fontconfig>
        <dir>/usr/share/fonts</dir>
        <dir>/usr/local/share/fonts</dir>
        <dir prefix="xdg">fonts</dir>
        <dir>~/.fonts</dir>
        <match target="font">
            <edit name="autohint" mode="assign">
                <bool>true</bool>
            </edit>
            <edit name="hinting" mode="assign">
                <bool>true</bool>
            </edit>
            <edit mode="assign" name="hintstyle">
                <const>hintslight</const>
            </edit>
            <edit name="antialias" mode="assign">
                <bool>true</bool>
            </edit>
        </match>
    </fontconfig>''')
                    
                    # Establecer la variable de entorno para que fontconfig encuentre el archivo
                    os.environ['FONTCONFIG_FILE'] = user_config_file
                    logging.info(f"Se ha creado un archivo de configuración fontconfig en {user_config_file}")
                    
            except Exception as e:
                logging.error(f"Error configurando fontconfig: {e}")


    def check_dependencies(self):
        """Verifica las dependencias del sistema y bibliotecas necesarias"""
        import shutil
        import subprocess
        
        missing_deps = []
        
        # Verificar comandos del sistema
        system_deps = ['fc-list', 'xdg-open']
        for dep in system_deps:
            if shutil.which(dep) is None:
                missing_deps.append(dep)
        
        # Verificar bibliotecas Qt
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            missing_deps.append('PyQt6.QtWebEngineWidgets')
        
        # Verificar la instalación de fontconfig en Linux
        import platform
        if platform.system() == 'Linux':
            try:
                # Intentar ejecutar fc-list para verificar que fontconfig funciona
                subprocess.run(['fc-list'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                missing_deps.append('fontconfig')
        
        if missing_deps:
            deps_str = ", ".join(missing_deps)
            logging.warning(f"Faltan dependencias: {deps_str}")
            
            # Sugerir comandos de instalación
            if 'fontconfig' in missing_deps:
                if platform.system() == 'Linux':
                    distro = ""
                    try:
                        # Intentar detectar la distribución
                        with open('/etc/os-release', 'r') as f:
                            for line in f:
                                if line.startswith('ID='):
                                    distro = line.split('=')[1].strip().strip('"\'')
                                    break
                    except:
                        pass
                    
                    if distro == 'ubuntu' or distro == 'debian':
                        logging.info("Sugerencia: Ejecuta 'sudo apt-get install fontconfig'")
                    elif distro == 'fedora':
                        logging.info("Sugerencia: Ejecuta 'sudo dnf install fontconfig'")
                    elif distro == 'arch':
                        logging.info("Sugerencia: Ejecuta 'sudo pacman -S fontconfig'")
        
        return len(missing_deps) == 0


class SearchThread(QThread):
    """Hilo para realizar búsquedas sin bloquear la interfaz"""
    progress_update = pyqtSignal(int)
    search_complete = pyqtSignal(list)
    
    def __init__(self, query, source):
        super().__init__()
        self.query = query
        self.source = source
        self.module = MusicSearchModule()  # Instancia temporal para acceder a los métodos de búsqueda
    
    def run(self):
        """Ejecuta las búsquedas en un hilo separado"""
        results = []
        
        try:
            if self.source in ["Todos", "Bandcamp"]:
                self.progress_update.emit(30)
                bandcamp_results = self.module.search_bandcamp(self.query)
                results.extend(bandcamp_results)
                self.progress_update.emit(60)
            
            if self.source in ["Todos", "SoundCloud"]:
                self.progress_update.emit(70)
                soundcloud_results = self.module.search_soundcloud(self.query)
                results.extend(soundcloud_results)
                self.progress_update.emit(90)
            
            self.progress_update.emit(100)
            self.search_complete.emit(results)
        
        except Exception as e:
            logging.error(f"Error en el hilo de búsqueda: {e}")
            self.progress_update.emit(100)
            self.search_complete.emit([])