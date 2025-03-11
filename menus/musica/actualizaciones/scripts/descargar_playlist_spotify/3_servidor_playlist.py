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
    def __init__(self, json_file, output_path, carpeta_descargas_qbitorrent):
        self.json_file = json_file
        self.output_path = output_path
        self.carpeta_descargas_qbitorrent = carpeta_descargas_qbitorrent
        self.load_canciones()
        
    def load_canciones(self):
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                self.canciones = json.load(f)
            logger.info(f"Cargado archivo de canciones con {len(self.canciones)} entradas")
        except Exception as e:
            logger.error(f"Error cargando el archivo JSON: {e}")
            self.canciones = []

    def normalizar_texto(self, texto):
        """Normaliza el texto para facilitar comparaciones quitando años y texto entre paréntesis."""
        if not texto:
            return ""
        # Eliminar años y cualquier texto entre paréntesis
        texto = re.sub(r'\(\d{4}.*?\)', '', texto)
        texto = re.sub(r'\(\s*\)', '', texto)  # Eliminar paréntesis vacíos restantes
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
        ruta_parts = ruta.split(' - ', 1)
        artista_ruta = ruta_parts[0] if len(ruta_parts) > 0 else ""
        album_ruta = ruta_parts[1] if len(ruta_parts) > 1 else ruta
        
        # Normalizar nombres para facilitar la comparación
        artista_ruta_norm = self.normalizar_texto(artista_ruta)
        album_ruta_norm = self.normalizar_texto(album_ruta)
        album_param_norm = self.normalizar_texto(album)
        
        logger.info(f"Información normalizada: Artista '{artista_ruta_norm}', Album ruta '{album_ruta_norm}', Album param '{album_param_norm}'")
        
        # Buscar canciones que coincidan con el artista y álbum normalizados
        canciones_coincidentes = []
        for cancion in self.canciones:
            artista_json_norm = self.normalizar_texto(cancion.get('artista', ''))
            album_json_norm = self.normalizar_texto(cancion.get('album', ''))
            
            # Verificar si hay coincidencia con la información normalizada
            if (artista_json_norm == artista_ruta_norm and 
                (album_json_norm == album_ruta_norm or album_json_norm in album_ruta_norm or album_ruta_norm in album_json_norm)):
                canciones_coincidentes.append(cancion)
        
        # Si no encontramos coincidencias, intentamos solo con el álbum proporcionado como parámetro
        if not canciones_coincidentes and album:
            logger.info(f"No se encontraron coincidencias exactas. Intentando con el álbum proporcionado: '{album}'")
            for cancion in self.canciones:
                album_json_norm = self.normalizar_texto(cancion.get('album', ''))
                if album_json_norm == album_param_norm or album_json_norm in album_param_norm or album_param_norm in album_json_norm:
                    canciones_coincidentes.append(cancion)
        
        if not canciones_coincidentes:
            logger.warning(f"No se encontraron canciones que coincidan con Artista='{artista_ruta}', Album='{album_ruta}' en el JSON")
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
            
            # Patrón para buscar la canción - buscamos el nombre como substring
            patron = re.compile(re.escape(nombre_cancion), re.IGNORECASE)
            
            for archivo in archivos_musica:
                nombre_archivo = os.path.basename(archivo)
                if patron.search(nombre_archivo):
                    # Usar la ruta como carpeta destino
                    album_dir = os.path.join(self.output_path, ruta)
                    
                    # Crear carpetas si no existen
                    os.makedirs(album_dir, exist_ok=True)
                    
                    # Destino final
                    destino = os.path.join(album_dir, nombre_archivo)
                    
                    # Copiar archivo
                    try:
                        shutil.copy2(archivo, destino)
                        logger.info(f"Copiado: '{nombre_archivo}' a '{destino}'")
                        canciones_procesadas += 1
                        break  # Pasar a la siguiente canción
                    except Exception as e:
                        logger.error(f"Error copiando '{archivo}': {e}")
        
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

def run_server(server_address, processor, num_torrents):
    RequestHandler.processor = processor
    RequestHandler.processed_count = 0
    RequestHandler.max_torrents = num_torrents
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
        "carpeta_descargas_qbitorrent": "/mnt/NFS/lidarr/torrents_backup",
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
        config["carpeta_descargas_qbitorrent"]
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
    run_server((config["host"], config["temp_server_port"]), processor, args.numero_torrents)
    
    return 0

if __name__ == "__main__":
    exit(main())