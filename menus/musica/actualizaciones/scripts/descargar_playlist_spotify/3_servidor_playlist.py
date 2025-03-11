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
from urllib.parse import parse_qs
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
            
    def process_download(self, album, ruta):
        logger.info(f"Procesando descarga: Album '{album}' en ruta '{ruta}'")
        
        # Ruta completa donde buscar los archivos
        ruta_completa = os.path.join(self.carpeta_descargas_qbitorrent, ruta)
        logger.info(f"Buscando archivos en la ruta completa: {ruta_completa}")
        
        if not os.path.exists(ruta_completa):
            logger.error(f"La ruta de descarga '{ruta_completa}' no existe")
            return False
            
        # Buscar todas las canciones que pertenecen a este álbum
        canciones_album = [cancion for cancion in self.canciones if cancion.get('album') == album]
        
        if not canciones_album:
            logger.warning(f"No se encontraron canciones para el álbum '{album}' en el JSON")
            return False
            
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
        for cancion_info in canciones_album:
            nombre_cancion = cancion_info.get('cancion')
            if not nombre_cancion:
                continue
                
            # Patrón para buscar la canción - ignoramos números y caracteres especiales
            # Buscamos el nombre de la canción como una substring del nombre de archivo
            patron = re.compile(re.escape(nombre_cancion), re.IGNORECASE)
            
            for archivo in archivos_musica:
                nombre_archivo = os.path.basename(archivo)
                if patron.search(nombre_archivo):
                    # Destino para la copia
                    artista = cancion_info.get('artista', 'Desconocido')
                    album_dir = os.path.join(self.output_path, artista, album)
                    
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
            if self.path == '/download-complete':
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length).decode('utf-8')
                    try:
                        data = json.loads(post_data)
                        logger.info(f"Datos POST recibidos: {data}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decodificando JSON: {e}. Datos recibidos: {post_data}")
                        self.send_response(400)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b'Error: JSON invalido')
                        return
                    
                    album = data.get('album')
                    ruta = data.get('ruta')
                    
                    if album and ruta:
                        logger.info(f"Recibida notificación: Album '{album}', Ruta '{ruta}'")
                        
                        if self.processor:
                            success = self.processor.process_download(album, ruta)
                            self.__class__.increment_count()
                            
                            if success:
                                self.send_response(200)
                                self.send_header('Content-type', 'text/plain')
                                self.end_headers()
                                self.wfile.write(b'Procesamiento completado')
                                return
                        
                        # Si llegamos aquí, algo falló
                        self.send_response(500)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b'Error procesando la descarga')
                        return
                
                # Si llegamos aquí, los datos son incorrectos
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Datos incorrectos')
            else:
                # Agregamos soporte para una ruta de verificación simple
                if self.path == '/status':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Servidor activo')
                    return
                
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
        "path_destino_flac": "./output",
        "carpeta_descargas_qbitorrent": "./downloads",
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