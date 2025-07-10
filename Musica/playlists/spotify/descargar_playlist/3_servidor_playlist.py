#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
import logging
from urllib.parse import parse_qs, urlparse
import logging.handlers





# Configurar logging para escribir a archivo y consola
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "servidor_playlist.log")
file_handler = logging.handlers.RotatingFileHandler(
    log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
)
console_handler = logging.StreamHandler()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

class TorrentProcessor:
    def __init__(self, json_file, output_path, carpeta_descargas_qbitorrent, num_torrents=0):
        self.json_file = json_file
        self.output_path = output_path
        self.carpeta_descargas_qbitorrent = carpeta_descargas_qbitorrent
        self.num_torrents = num_torrents
        self.load_canciones()
        
    def load_canciones(self):
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            # Convertir el nuevo formato a un formato compatible
            self.canciones = []
            self.formato_agrupado = True
            
            # Detectar automáticamente el formato
            if datos and isinstance(datos, list):
                # Verificar si es el nuevo formato agrupado
                if "canciones" in datos[0]:
                    logger.info("Detectado formato JSON agrupado por artista/álbum")
                    self.formato_agrupado = True
                    
                    # Para cada grupo, expandir las canciones
                    for grupo in datos:
                        artista = grupo.get('artista', '')
                        album = grupo.get('album', '')
                        canciones_lista = grupo.get('canciones', [])
                        
                        # Convertir cada canción en un objeto individual
                        for nombre_cancion in canciones_lista:
                            self.canciones.append({
                                'artista': artista,
                                'album': album,
                                'cancion': nombre_cancion
                            })
                else:
                    # Formato antiguo (lista de canciones individuales)
                    logger.info("Detectado formato JSON de canciones individuales")
                    self.formato_agrupado = False
                    self.canciones = datos
            
            logger.info(f"Cargado archivo de canciones con {len(self.canciones)} entradas")
        except Exception as e:
            logger.error(f"Error cargando el archivo JSON: {e}")
            self.canciones = []
            self.formato_agrupado = False

    def normalizar_texto(self, texto):
        """
        Normaliza el texto para facilitar comparaciones, eliminando años, versiones
        especiales, remasterizaciones, puntuación, etc.
        """
        if not texto:
            return ""
        
        
        
        # Eliminar texto entre paréntesis
        texto = re.sub(r'\([^)]*\)', '', texto)
        
        # Eliminar años (incluso los que no están entre paréntesis)
        texto = re.sub(r'\b\d{4}\b', '', texto)
        
        # Eliminar palabras clave específicas que pueden aparecer sin paréntesis
        palabras_clave = [
            'remaster(ed)?', 'deluxe', 'edition', 'version', 'expanded',
            'anniversary', 'special', 'bonus', 'track', 'disc \d+',
            'downloads'  # Añadido para manejar rutas como '/downloads/...'
        ]
        
        for palabra in palabras_clave:
            texto = re.sub(r'\b' + palabra + r'\b', '', texto, flags=re.IGNORECASE)
        
        # Eliminar cualquier símbolo de puntuación (dos puntos, comas, punto y coma, etc.)
        texto = re.sub(r'[:\-,;/]', ' ', texto)
        
        # Simplificar espacios múltiples y caracteres especiales
        texto = re.sub(r'[\s\-_\.]+', ' ', texto)
        
        # Eliminar artículos del inicio ("The", "A", "El", etc) para mejor comparación
        texto = re.sub(r'^(the|a|an|el|la|los|las)\s+', '', texto, flags=re.IGNORECASE)
        
        return texto.strip().lower()
            
  
    def process_download(self, album, ruta):
        logger.info(f"Procesando descarga: Album '{album}' en ruta '{ruta}'")
        
        # Ruta completa donde buscar los archivos
        ruta_completa = os.path.join(self.carpeta_descargas_qbitorrent, ruta)
        logger.info(f"Buscando archivos en la ruta completa: {ruta_completa}")
        
        if not os.path.exists(ruta_completa):
            logger.error(f"La ruta de descarga '{ruta_completa}' no existe")
            return False
        
        # Extraer artista y álbum del nombre de la ruta
        # Formato esperado: "Artista - Album" o variaciones
        # También manejar formatos como "Artista - YYYY - Album"
        ruta_parts = re.split(r'\s+-\s+', ruta, 1)
        
        artista_ruta = ruta_parts[0] if len(ruta_parts) > 0 else ""
        album_ruta = ruta_parts[1] if len(ruta_parts) > 1 else ruta
        
        # Si la segunda parte contiene un año (por ejemplo "2007 - El Cartel The Big Boss")
        # extraer solo el nombre del álbum
        if len(ruta_parts) > 1 and re.match(r'^\d{4}\s+-\s+', album_ruta):
            album_ruta = re.sub(r'^\d{4}\s+-\s+', '', album_ruta)
        
        # Normalizar nombres para facilitar la comparación
        artista_ruta_norm = self.normalizar_texto(artista_ruta)
        album_ruta_norm = self.normalizar_texto(album_ruta)
        album_param_norm = self.normalizar_texto(album)
        
        logger.info(f"Información normalizada: Artista '{artista_ruta_norm}', Album ruta '{album_ruta_norm}', Album param '{album_param_norm}'")
        
        # Método para calcular similitud entre strings
        def calcular_similitud(s1, s2):
            if not s1 or not s2:
                return 0
            
            s1, s2 = s1.lower(), s2.lower()
            
            # Coincidencia exacta
            if s1 == s2:
                return 1.0
                
            # Una es substring de la otra
            if s1 in s2 or s2 in s1:
                return 0.8
                
            # Palabras comunes
            palabras1 = set(s1.split())
            palabras2 = set(s2.split())
            comunes = palabras1.intersection(palabras2)
            
            if comunes:
                # Si hay al menos 2 palabras comunes, consideramos que hay buena similitud
                if len(comunes) >= 2:
                    return 0.7
                return len(comunes) / max(len(palabras1), len(palabras2))
                
            return 0
        
        # Buscar canciones que coincidan con el artista y álbum
        canciones_coincidentes = []
        album_coincidencias = {}
        
        for cancion in self.canciones:
            artista_json = cancion.get('artista', '')
            album_json = cancion.get('album', '')
            
            # Saltar entradas sin artista o álbum
            if not artista_json or not album_json:
                continue
                
            artista_json_norm = self.normalizar_texto(artista_json)
            album_json_norm = self.normalizar_texto(album_json)
            
            # Calcular similitud de artista
            similitud_artista = calcular_similitud(artista_json_norm, artista_ruta_norm)
            
            # Si el artista coincide razonablemente, evaluar el álbum
            if similitud_artista >= 0.7:
                similitud_album = calcular_similitud(album_json_norm, album_ruta_norm)
                
                # También evaluar contra el parámetro album si es diferente
                similitud_album_param = 0
                if album_param_norm != album_ruta_norm:
                    similitud_album_param = calcular_similitud(album_json_norm, album_param_norm)
                    
                similitud_album_final = max(similitud_album, similitud_album_param)
                
                # Si la similitud del álbum es suficiente, añadir a coincidencias
                if similitud_album_final >= 0.6:
                    score = similitud_artista * 0.4 + similitud_album_final * 0.6
                    key = f"{artista_json}|{album_json}"
                    
                    if key not in album_coincidencias or score > album_coincidencias[key]['score']:
                        album_coincidencias[key] = {
                            'score': score,
                            'cancion': cancion
                        }
        
        # Ordenar coincidencias por score y añadir a la lista final
        for key, data in sorted(album_coincidencias.items(), key=lambda x: x[1]['score'], reverse=True):
            artista_album = key.split('|')
            logger.info(f"Coincidencia encontrada: Artista='{artista_album[0]}', Album='{artista_album[1]}', Score={data['score']:.2f}")
            canciones_coincidentes.append(data['cancion'])
        
        if not canciones_coincidentes:
            logger.warning(f"No se encontraron canciones que coincidan con Artista='{artista_ruta}', Album='{album_ruta}' en el JSON")
            # Intentar un último recurso: buscar todas las canciones y mostrar sus artistas/álbumes
            logger.info("Listando todas las entradas en el JSON para diagnóstico:")
            for i, cancion in enumerate(self.canciones[:10]):  # Limitado a 10 para no saturar el log
                artista = cancion.get('artista', 'N/A')
                album = cancion.get('album', 'N/A')
                logger.info(f"  {i+1}. Artista='{artista}', Album='{album}'")
            
            return False
        
        logger.info(f"Se encontraron {len(canciones_coincidentes)} canciones coincidentes en el JSON")
        
        # Obtener archivos de música de la carpeta descargada
        archivos_musica = []
        for root, dirs, files in os.walk(ruta_completa):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.ogg', '.m4a')):
                    archivos_musica.append(os.path.join(root, file))
        
        if not archivos_musica:
            logger.warning(f"No se encontraron archivos de música en '{ruta_completa}'")
            return False
        
        logger.info(f"Se encontraron {len(archivos_musica)} archivos de música")
        
        # Para cada canción en el JSON, buscar un archivo correspondiente
        canciones_procesadas = 0
        
        for cancion_info in canciones_coincidentes:
            nombre_cancion = cancion_info.get('cancion')
            if not nombre_cancion:
                continue
            
            # Normalizar nombre de canción (eliminar remaster, version, etc.)
            nombre_cancion_norm = self.normalizar_texto(nombre_cancion)
            logger.info(f"Buscando coincidencia para: '{nombre_cancion}' (norm: '{nombre_cancion_norm}')")
            
            encontrado = False
            mejor_coincidencia = None
            mejor_puntaje = 0
            
            for archivo in archivos_musica[:]:  # Trabajamos con una copia para poder eliminar elementos
                nombre_archivo = os.path.basename(archivo)
                nombre_sin_extension = os.path.splitext(nombre_archivo)[0]
                
                # Normalizar nombre de archivo
                nombre_archivo_norm = self.normalizar_texto(nombre_sin_extension)
                
                # Calcular puntaje de similitud
                if nombre_archivo_norm.lower() == nombre_cancion_norm.lower():
                    puntaje = 1.0  # Coincidencia exacta
                elif nombre_archivo_norm.lower() in nombre_cancion_norm.lower() or nombre_cancion_norm.lower() in nombre_archivo_norm.lower():
                    # Substring
                    puntaje = 0.8
                else:
                    # Verificar palabras en común
                    palabras_archivo = set(nombre_archivo_norm.lower().split())
                    palabras_cancion = set(nombre_cancion_norm.lower().split())
                    comunes = palabras_archivo.intersection(palabras_cancion)
                    if comunes:
                        puntaje = len(comunes) / max(len(palabras_archivo), len(palabras_cancion))
                    else:
                        # Buscar números de pista al inicio del nombre del archivo
                        # Por ejemplo: "01 - Canción" o "1. Canción"
                        track_match = re.match(r'^\s*(\d+)[\s\.\-]+(.+)', nombre_archivo_norm)
                        if track_match:
                            # Extraer el nombre sin el número de pista
                            nombre_sin_track = track_match.group(2).strip()
                            # Recalcular similitud
                            if nombre_sin_track.lower() == nombre_cancion_norm.lower():
                                puntaje = 0.9
                            elif nombre_sin_track.lower() in nombre_cancion_norm.lower() or nombre_cancion_norm.lower() in nombre_sin_track.lower():
                                puntaje = 0.7
                            else:
                                puntaje = 0
                        else:
                            puntaje = 0
                
                logger.info(f"  Archivo: '{nombre_archivo}', puntaje: {puntaje:.2f}")
                
                if puntaje > mejor_puntaje:
                    mejor_puntaje = puntaje
                    mejor_coincidencia = archivo
            
            # Si encontramos una coincidencia con puntaje suficiente
            if mejor_coincidencia and mejor_puntaje >= 0.5:
                # Usar la ruta como carpeta destino
                album_dir = os.path.join(self.output_path, ruta)
                
                # Crear carpetas si no existen
                os.makedirs(album_dir, exist_ok=True)
                
                # Nombre del archivo
                nombre_archivo = os.path.basename(mejor_coincidencia)
                
                # Destino final
                destino = os.path.join(album_dir, nombre_archivo)
                
                # Copiar archivo
                try:
                    shutil.copy2(mejor_coincidencia, destino)
                    logger.info(f"Copiado: '{nombre_archivo}' a '{destino}' (puntaje: {mejor_puntaje:.2f})")
                    canciones_procesadas += 1
                    archivos_musica.remove(mejor_coincidencia)  # Eliminar de la lista para que no se use para otra canción
                    encontrado = True
                except Exception as e:
                    logger.error(f"Error copiando '{mejor_coincidencia}': {e}")
            
            if not encontrado:
                logger.warning(f"No se encontró archivo con suficiente similitud para la canción '{nombre_cancion}'")
        
        logger.info(f"Procesamiento completado. {canciones_procesadas} canciones copiadas")
        
        # Si se procesaron canciones correctamente, eliminar la carpeta original
        if canciones_procesadas > 0:
            try:
                logger.info(f"Eliminando carpeta de descarga original: {ruta_completa}")
                shutil.rmtree(ruta_completa)
                logger.info(f"Carpeta eliminada correctamente: {ruta_completa}")
            except Exception as e:
                logger.error(f"Error eliminando carpeta de descarga original '{ruta_completa}': {e}")
        
        return canciones_procesadas > 0

class RequestHandler(BaseHTTPRequestHandler):
    processor = None
    processed_count = 0
    max_torrents = 0
    shutdown_event = threading.Event()
    
    @classmethod
    def increment_count(cls):
        cls.processed_count += 1
        logger.info(f"Torrents procesados: {cls.processed_count}/{cls.max_torrents if cls.max_torrents > 0 else 'ilimitado'}")
        if cls.max_torrents > 0 and cls.processed_count >= cls.max_torrents:
            logger.info("Se completaron todos los torrents solicitados. Preparando para cerrar servidor...")
            cls.shutdown_event.set()
    
    def do_POST(self):
        logger.info(f"Recibida solicitud POST desde {self.client_address}")
        logger.info(f"Headers: {dict(self.headers)}")
        
        try:
            if self.path.startswith('/download-complete'):
                # Procesar tanto el cuerpo JSON como los parámetros de URL
                album = None
                ruta = None
                
                # Verificar si hay parámetros en la URL
                parsed_url = urlparse(self.path)
                if parsed_url.query:
                    query_params = parse_qs(parsed_url.query)
                    logger.info(f"Parámetros URL recibidos: {query_params}")
                    album = query_params.get('album', [''])[0]
                    ruta = query_params.get('ruta', [''])[0]
                
                # Verificar si hay cuerpo de solicitud
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length).decode('utf-8')
                    logger.info(f"Datos POST recibidos (raw): {post_data}")
                    
                    # Intentar procesar como JSON
                    try:
                        data = json.loads(post_data)
                        logger.info(f"Datos POST procesados como JSON: {data}")
                        # Priorizar datos del cuerpo sobre los de la URL
                        if data.get('album'):
                            album = data.get('album')
                        if data.get('ruta'):
                            ruta = data.get('ruta')
                    except json.JSONDecodeError:
                        # Si no es JSON válido, intentar procesar como form-urlencoded
                        try:
                            form_data = parse_qs(post_data)
                            logger.info(f"Datos POST procesados como form-urlencoded: {form_data}")
                            # Priorizar datos del cuerpo sobre los de la URL
                            if form_data.get('album'):
                                album = form_data.get('album')[0]
                            if form_data.get('ruta'):
                                ruta = form_data.get('ruta')[0]
                        except Exception as e:
                            logger.warning(f"No se pudo procesar el cuerpo como form-urlencoded: {e}")
                
                # Si no hay datos suficientes, intentar extraer información del nombre del torrent
                if not album or not ruta:
                    logger.info("Intentando extraer información del nombre del torrent desde los encabezados...")
                    
                    # Buscar en cabeceras específicas de qBittorrent
                    torrent_name = self.headers.get('X-Torrent-Name') or self.headers.get('X-Torrent-Hash')
                    
                    if torrent_name:
                        logger.info(f"Nombre del torrent encontrado: {torrent_name}")
                        # Si no tenemos ruta, usamos el nombre del torrent
                        if not ruta:
                            ruta = torrent_name
                        
                        # Si no tenemos álbum, intentamos extraerlo del nombre
                        if not album:
                            # Suponemos que el formato es "Artista - Album"
                            parts = torrent_name.split(' - ', 1)
                            if len(parts) > 1:
                                album = parts[1]
                            else:
                                album = torrent_name
                
                # Procesar la descarga si tenemos suficiente información
                if album and ruta:
                    logger.info(f"Procesando con: Album '{album}', Ruta '{ruta}'")
                    
                    if self.processor:
                        success = self.processor.process_download(album, ruta)
                        self.__class__.increment_count()
                        
                        if success:
                            self.send_response(200)
                            self.send_header('Content-type', 'text/plain')
                            self.end_headers()
                            self.wfile.write(b'Procesamiento completado')
                            return
                    
                    # Si llegamos aquí, el procesamiento falló
                    self.send_response(500)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Error procesando la descarga')
                    return
                
                # Datos insuficientes
                logger.warning(f"Datos insuficientes: album='{album}', ruta='{ruta}'")
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Datos insuficientes para procesar la descarga')
            elif self.path.startswith('/status'):
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Servidor activo')
            else:
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Not Found')
        except Exception as e:
            logger.error(f"Error procesando solicitud: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())
    
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")

def run_server(server_address, processor, num_canciones, num_torrents):
    """
    Función que inicia el servidor HTTP para procesar las solicitudes
    
    Parámetros:
    - server_address: tupla (host, puerto) para el servidor
    - processor: instancia de TorrentProcessor para procesar los torrents
    - num_canciones: número total de canciones a procesar
    - num_torrents: número de torrents a procesar antes de cerrar el servidor
    """
    # Asignar los valores a la clase RequestHandler
    RequestHandler.processor = processor
    RequestHandler.processed_count = 0
    RequestHandler.max_torrents = num_torrents  # Ahora recibe el parámetro correctamente
    RequestHandler.shutdown_event.clear()
    
    # Crear una subclase de HTTPServer que permita reutilizar la dirección
    class ReuseAddrHTTPServer(HTTPServer):
        allow_reuse_address = True
    
    httpd = ReuseAddrHTTPServer(server_address, RequestHandler)
    
    # Hacer el método serve_forever() en un hilo separado
    def server_thread():
        logger.info(f"Servidor iniciado en {server_address[0]}:{server_address[1]}")
        try:
            httpd.serve_forever()
        except Exception as e:
            logger.error(f"Error en el servidor: {e}")
    
    thread = threading.Thread(target=server_thread)
    thread.daemon = True
    thread.start()
    
    # Verificar periódicamente si debemos cerrar el servidor
    try:
        logger.info("Servidor listo y esperando solicitudes...")
        logger.info("Para realizar una prueba manual, puedes ejecutar:")
        logger.info(f"curl -X POST http://localhost:{server_address[1]}/download-complete -H 'Content-Type: application/json' -d '{{'album': 'Nombre del Album', 'ruta': 'ruta/relativa/a/descarga'}}'")
        
        while not RequestHandler.shutdown_event.is_set():
            RequestHandler.shutdown_event.wait(1)
            
        logger.info("Cerrando servidor después de procesar todos los torrents...")
    except KeyboardInterrupt:
        logger.info("Recibida señal de interrupción. Cerrando servidor...")
    
    # Cerrar el servidor
    httpd.shutdown()
    httpd.server_close()
    logger.info("Servidor cerrado correctamente")

def load_config(config_file):
    """Cargar configuración desde archivo JSON"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"Configuración cargada desde {config_file}")
        return config
    except Exception as e:
        logger.error(f"Error cargando configuración: {e}")
        return {}



def main():
    parser = argparse.ArgumentParser(description='Servidor temporal para procesamiento de torrents')
    parser.add_argument('--config-file', 
                        help='Ruta al archivo JSON de configuración')
    parser.add_argument('--numero-torrents', type=int, default=0, 
                        help='Número de torrents a procesar antes de detener el servidor (0 para infinito)')
    parser.add_argument('--numero-canciones', type=int, default=0, 
                        help='Número de canciones en el playlist.')
    parser.add_argument('--json-file', 
                        help='Ruta al archivo JSON con la lista de canciones')
    parser.add_argument('--output-path', 
                        help='Ruta de destino para copiar las canciones')
    parser.add_argument('--host', default='0.0.0.0', 
                        help='Dirección IP del servidor (por defecto: 0.0.0.0)')
    parser.add_argument('--temp_server_port', type=int, default=8584, 
                        help='Puerto del servidor (por defecto: 8584)')
    parser.add_argument('--carpeta-descargas-qbitorrent',
                        help='Carpeta descargas de qbitorrent, donde descarga tus cositas')

    args = parser.parse_args()
    
    # Configuración por defecto
    config = {
        "json_file": ".content/playlist_songs.json",
        "path_destino_flac": "./canciones",
        "carpeta_descargas_qbitorrent": "/var/media/TOSHIBA/torrent",
        "temp_server_port": 8584,
        "host": "0.0.0.0"
    }
    
    # Cargar configuración desde archivo JSON si se proporciona
    if args.config_file and os.path.isfile(args.config_file):
        file_config = load_config(args.config_file)
        config.update(file_config)
    
    # Los argumentos de línea de comandos tienen prioridad sobre la configuración del archivo
    if args.json_file:
        config["json_file"] = args.json_file
    if args.output_path:
        config["path_destino_flac"] = args.output_path
    if args.carpeta_descargas_qbitorrent:
        config["carpeta_descargas_qbitorrent"] = args.carpeta_descargas_qbitorrent
    if args.temp_server_port:
        config["temp_server_port"] = args.temp_server_port
    if args.host:
        config["host"] = args.host
    
    # Convertir puerto a entero si viene como string
    if isinstance(config["temp_server_port"], str):
        config["temp_server_port"] = int(config["temp_server_port"])
    
    # Validar configuración
    if not os.path.isfile(config["json_file"]):
        logger.error(f"El archivo JSON '{config['json_file']}' no existe")
        return 1
    
    if not os.path.isdir(config["path_destino_flac"]):
        logger.warning(f"La carpeta de destino '{config['path_destino_flac']}' no existe. Intentando crearla...")
        try:
            os.makedirs(config["path_destino_flac"], exist_ok=True)
        except Exception as e:
            logger.error(f"Error creando carpeta de destino: {e}")
            return 1
            
    if not os.path.isdir(config["carpeta_descargas_qbitorrent"]):
        logger.warning(f"La carpeta de descargas '{config['carpeta_descargas_qbitorrent']}' no existe. Intentando crearla...")
        try:
            os.makedirs(config["carpeta_descargas_qbitorrent"], exist_ok=True)
        except Exception as e:
            logger.error(f"Error creando carpeta de descargas: {e}")
            return 1
    
    # Crear procesador
    processor = TorrentProcessor(
        config["json_file"], 
        config["path_destino_flac"], 
        config["carpeta_descargas_qbitorrent"],
        args.numero_torrents
    )
    
    # Mostrar la configuración actual
    logger.info("Configuración del servidor:")
    logger.info(f"  - Host: {config['host']}")
    logger.info(f"  - Puerto: {config['temp_server_port']}")
    logger.info(f"  - Archivo JSON: {config['json_file']}")
    logger.info(f"  - Ruta de destino: {config['path_destino_flac']}")
    logger.info(f"  - Carpeta de descargas: {config['carpeta_descargas_qbitorrent']}")
    logger.info(f"  - Número de torrents a procesar: {args.numero_torrents if args.numero_torrents > 0 else 'ilimitado'}")
    
    # Iniciar servidor
    run_server(
        (config["host"], config["temp_server_port"]), 
        processor, 
        args.numero_canciones,
        args.numero_torrents
    )    
    return 0

if __name__ == "__main__":
    exit(main())