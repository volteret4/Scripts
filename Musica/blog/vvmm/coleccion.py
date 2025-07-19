#!/usr/bin/env python3
"""
Script Name: discogs_collection_manager.py
Description: Gestor automático de colección de Discogs para crear posts individuales
Author: volteret4
Dependencies: requests, sqlite3, os
"""

import os
import sys
import json
import sqlite3
import requests
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import logging

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

class Config:
    def __init__(self):
        # Rutas del proyecto
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir

        # Cargar variables de entorno
        self.load_env_file()
        self.content_dir = self.project_root / ".content"
        self.logs_dir = self.content_dir / "logs"
        self.cache_dir = self.content_dir / "cache"
        self.blog_dir = Path("/mnt/NFS/blogs/vvmm")
        self.collection_dir = self.blog_dir / "content" / "coleccion"

        # Crear directorios necesarios
        for dir_path in [self.logs_dir, self.cache_dir, self.collection_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Configuración de archivos
        today = datetime.now().strftime("%Y%m%d")
        self.log_file = self.logs_dir / f"discogs_collection_{today}.log"
        self.registry_file = self.cache_dir / "discogs_collection_registry.json"
        self.collection_raw_file = self.cache_dir / "discogs_collection_raw.json"
        self.collection_parsed_file = self.cache_dir / "discogs_collection_parsed.json"

        # Configuración de API
        self.discogs_token = os.getenv('DISCOGS_TOKEN')
        self.discogs_username = os.getenv('DISCOGS_USERNAME', 'pollolpc')
        self.database_path = os.getenv('DATABASE_PATH', str(self.project_root / 'music_database.db'))

        if not self.discogs_token:
            raise ValueError("DISCOGS_TOKEN no encontrado en variables de entorno")

    def load_env_file(self):
        """Cargar archivo .env si existe"""
        env_file = self.script_dir / '.env'
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip('"\'')

# =============================================================================
# LOGGING
# =============================================================================

def setup_logging(log_file: Path, debug: bool = False):
    """Configurar logging"""
    level = logging.DEBUG if debug else logging.INFO

    # Configurar formato
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Handler para archivo
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configurar logger
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# =============================================================================
# CLIENTE DISCOGS
# =============================================================================

class DiscogsClient:
    def __init__(self, token: str, username: str):
        self.token = token
        self.username = username
        self.base_url = "https://api.discogs.com"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Discogs token={token}',
            'User-Agent': 'DiscogsBlogManager/1.0'
        })

    def test_connection(self) -> bool:
        """Test de conectividad con la API"""
        try:
            # Test de identidad
            logging.info("1. Verificando identidad...")
            response = self.session.get(f"{self.base_url}/oauth/identity")
            response.raise_for_status()

            identity = response.json()
            actual_username = identity.get('username')
            user_id = identity.get('id')

            logging.info(f"✅ Autenticación exitosa: {actual_username} (ID: {user_id})")

            if actual_username != self.username:
                logging.warning(f"Actualizando username de {self.username} a {actual_username}")
                self.username = actual_username

            # Test de colección
            logging.info("2. Verificando acceso a colección...")
            response = self.session.get(
                f"{self.base_url}/users/{self.username}/collection/folders/0/releases",
                params={'page': 1, 'per_page': 1}
            )
            response.raise_for_status()

            collection_info = response.json()
            total_items = collection_info.get('pagination', {}).get('items', 0)
            total_pages = collection_info.get('pagination', {}).get('pages', 0)

            logging.info(f"✅ Acceso a colección exitoso: {total_items} items en {total_pages} páginas")

            if total_items == 0:
                logging.warning("⚠️  La colección está vacía")
                return False

            # Mostrar ejemplo
            if collection_info.get('releases'):
                first_release = collection_info['releases'][0]
                artist = first_release['basic_information']['artists'][0]['name']
                title = first_release['basic_information']['title']
                logging.info(f"📀 Ejemplo: {artist} - {title}")

            logging.info("✅ Todos los tests pasaron correctamente")
            return True

        except requests.RequestException as e:
            logging.error(f"❌ Error de conectividad: {e}")
            return False
        except Exception as e:
            logging.error(f"❌ Error inesperado: {e}")
            return False

    def get_collection(self) -> List[Dict]:
        """Obtener toda la colección"""
        logging.info("Obteniendo colección de Discogs...")

        all_releases = []
        page = 1
        per_page = 100

        while True:
            logging.debug(f"Obteniendo página {page} de la colección...")

            try:
                response = self.session.get(
                    f"{self.base_url}/users/{self.username}/collection/folders/0/releases",
                    params={'page': page, 'per_page': per_page}
                )
                response.raise_for_status()

                data = response.json()
                releases = data.get('releases', [])

                if not releases:
                    break

                all_releases.extend(releases)
                logging.debug(f"Releases encontrados en página {page}: {len(releases)}")

                # Verificar si hay más páginas
                pagination = data.get('pagination', {})
                current_page = pagination.get('page', 1)
                total_pages = pagination.get('pages', 1)

                if current_page >= total_pages:
                    break

                page += 1
                time.sleep(1)  # Rate limiting

            except requests.RequestException as e:
                logging.error(f"Error obteniendo página {page}: {e}")
                break

        logging.info(f"Colección obtenida: {len(all_releases)} discos")
        return all_releases

# =============================================================================
# PROCESADOR DE COLECCIÓN
# =============================================================================

class CollectionProcessor:
    def __init__(self, config: Config):
        self.config = config
        self.registry = self.load_registry()

    def load_registry(self) -> Dict:
        """Cargar registro de items procesados"""
        if self.config.registry_file.exists():
            with open(self.config.registry_file) as f:
                registry = json.load(f)

            processed_count = len(registry.get('processed', []))
            added_count = len(registry.get('added', []))
            skipped_count = len(registry.get('skipped', []))

            logging.info("Registro existente encontrado:")
            logging.info(f"  - Items procesados: {processed_count}")
            logging.info(f"  - Items añadidos: {added_count}")
            logging.info(f"  - Items saltados: {skipped_count}")

            return registry
        else:
            logging.info("Inicializando registro de colección...")
            return {"processed": [], "added": [], "skipped": []}

    def save_registry(self):
        """Guardar registro"""
        with open(self.config.registry_file, 'w') as f:
            json.dump(self.registry, f, indent=2)

    def is_processed(self, discogs_id: str) -> bool:
        """Verificar si un item ya fue procesado"""
        return str(discogs_id) in self.registry.get('processed', [])

    def mark_processed(self, discogs_id: str, action: str):
        """Marcar item como procesado"""
        discogs_id = str(discogs_id)

        if discogs_id not in self.registry['processed']:
            self.registry['processed'].append(discogs_id)

        if action == 'added' and discogs_id not in self.registry['added']:
            self.registry['added'].append(discogs_id)
        elif action == 'skipped' and discogs_id not in self.registry['skipped']:
            self.registry['skipped'].append(discogs_id)

        self.save_registry()

    def parse_collection(self, raw_collection: List[Dict]) -> List[Dict]:
        """Procesar items de la colección"""
        logging.info("Procesando items de la colección...")

        parsed_items = []

        for item in raw_collection:
            try:
                basic_info = item.get('basic_information', {})

                parsed_item = {
                    'discogs_id': basic_info.get('id'),
                    'artist': basic_info.get('artists', [{}])[0].get('name', 'Unknown Artist'),
                    'title': basic_info.get('title', 'Unknown Title'),
                    'year': basic_info.get('year', 0),
                    'labels': ', '.join([label.get('name', '') for label in basic_info.get('labels', [])]),
                    'genres': ', '.join(basic_info.get('genres', [])),
                    'styles': ', '.join(basic_info.get('styles', [])),
                    'date_added': item.get('date_added', ''),
                    'resource_url': basic_info.get('resource_url', ''),
                    'cover_image': basic_info.get('cover_image', basic_info.get('thumb', '')),
                    'thumb': basic_info.get('thumb', '')
                }

                parsed_items.append(parsed_item)

            except Exception as e:
                logging.warning(f"Error procesando item: {e}")
                continue

        logging.info(f"Items procesados: {len(parsed_items)}")
        return parsed_items

# =============================================================================
# CREADOR DE POSTS
# =============================================================================

class PostCreator:
    def __init__(self, config: Config):
        self.config = config

    def ask_confirmation(self, item: Dict, item_number: int, total_items: int) -> bool:
        """Preguntar confirmación al usuario"""
        artist = item['artist']
        album = item['title']
        year = item['year']
        labels = item['labels']
        date_added = item['date_added']

        print(f"\n=== Disco {item_number} de {total_items} ===")
        print(f"Artista: {artist}")
        print(f"Álbum: {album}")
        print(f"Año: {year}")
        print(f"Sello: {labels}")
        print(f"Fecha agregado: {date_added}")

        # Intentar usar yad si está disponible
        try:
            message = (
                f"<b>¿Añadir este disco al blog?</b>\n\n"
                f"<b>Artista:</b> {artist}\n"
                f"<b>Álbum:</b> {album}\n"
                f"<b>Año:</b> {year}\n"
                f"<b>Sello:</b> {labels}\n"
                f"<b>Fecha agregado:</b> {date_added}\n\n"
                f"<i>ENTER = Añadir | ESCAPE/No = Saltar</i>"
            )

            result = subprocess.run([
                'yad', '--question',
                '--title', f'Gestión de Colección ({item_number}/{total_items})',
                '--text', message,
                '--width', '600',
                '--height', '250',
                '--center',
                '--on-top',
                '--button', '✅ Añadir (Enter):0',
                '--button', '⏭️ Saltar (Esc):1',
                '--timeout', '0'
            ], capture_output=True, text=True)

            return result.returncode == 0

        except FileNotFoundError:
            # Fallback a input manual
            while True:
                response = input("¿Añadir este disco? [Enter=Sí, n=No, q=Salir]: ").strip().lower()
                if response in ['', 'y', 'yes', 's', 'si']:
                    return True
                elif response in ['n', 'no']:
                    return False
                elif response in ['q', 'quit', 'salir']:
                    sys.exit(0)
                else:
                    print("Respuesta no válida. Usa Enter para sí, n para no, q para salir.")

    def get_database_info(self, artist: str, album: str) -> Optional[Dict]:
        """Obtener información adicional de la base de datos"""
        if not Path(self.config.database_path).exists():
            return None

        try:
            conn = sqlite3.connect(self.config.database_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COALESCE(al.spotify_url, ''),
                    COALESCE(al.bandcamp_url, ''),
                    COALESCE(al.lastfm_url, ''),
                    COALESCE(al.youtube_url, ''),
                    COALESCE(al.musicbrainz_url, ''),
                    COALESCE(al.wikipedia_url, ''),
                    COALESCE(al.genre, ''),
                    COALESCE(al.label, ''),
                    COALESCE(al.producers, ''),
                    COALESCE(al.total_tracks, 0)
                FROM albums al
                JOIN artists a ON al.artist_id = a.id
                WHERE LOWER(TRIM(a.name)) = LOWER(TRIM(?))
                AND LOWER(TRIM(al.name)) = LOWER(TRIM(?))
                LIMIT 1
            """, (artist, album))

            result = cursor.fetchone()
            conn.close()

            if result:
                return {
                    'spotify_url': result[0],
                    'bandcamp_url': result[1],
                    'lastfm_url': result[2],
                    'youtube_url': result[3],
                    'musicbrainz_url': result[4],
                    'wikipedia_url': result[5],
                    'genre': result[6],
                    'label': result[7],
                    'producers': result[8],
                    'total_tracks': result[9]
                }
        except Exception as e:
            logging.debug(f"Error consultando base de datos: {e}")

        return None

    def create_post(self, item: Dict) -> bool:
        """Crear post de Hugo"""
        try:
            artist = item['artist']
            album = item['title']

            # Limpiar nombres para URLs
            artist_clean = self.clean_name(artist)
            album_clean = self.clean_name(album)

            # Crear directorio del post
            post_dir = self.config.collection_dir / f"{artist_clean}---{album_clean}"
            post_dir.mkdir(parents=True, exist_ok=True)

            # Crear archivo del post
            post_file = post_dir / "index.md"

            # Obtener información adicional de la base de datos
            db_info = self.get_database_info(artist, album)

            # Crear contenido del post
            content = self.generate_post_content(item, db_info)

            with open(post_file, 'w', encoding='utf-8') as f:
                f.write(content)

            # Descargar carátula
            self.download_cover(item['cover_image'], post_dir)

            logging.info(f"Post creado: {artist} - {album}")
            return True

        except Exception as e:
            logging.error(f"Error creando post: {e}")
            return False

    def clean_name(self, name: str) -> str:
        """Limpiar nombre para URL"""
        import re
        # Remover caracteres especiales, mantener guiones y espacios
        cleaned = re.sub(r'[^\w\s-]', '', name)
        # Convertir espacios a guiones, eliminar guiones múltiples
        cleaned = re.sub(r'\s+', '-', cleaned)
        cleaned = re.sub(r'-+', '-', cleaned)
        return cleaned.strip('-')

    def generate_post_content(self, item: Dict, db_info: Optional[Dict]) -> str:
        """Generar contenido del post"""
        artist = item['artist']
        album = item['title']
        year = item['year']
        date_added = item['date_added']

        # Convertir fecha a formato Hugo
        try:
            date_obj = datetime.fromisoformat(date_added.replace('Z', '+00:00'))
            hugo_date = date_obj.strftime('%Y-%m-%dT%H:%M:%S%z')
        except:
            hugo_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%z')

        # Generar front matter más simple
        content = f"""---
title: "{artist} - {album}"
date: {hugo_date}
image: "image.jpeg"
draft: false
tags:
- coleccion
- discogs
#- tagC
#- tagD
#- tagE
---

![cover](image.jpeg ({artist} - {album}))

"""

        # Generar enlaces en el formato deseado
        content += self.generate_service_links(item, db_info)

        # Añadir información de Discogs como bloque citado
        content += self.generate_discogs_info_block(item, db_info)

        return content


    def generate_discogs_info_block(self, item: Dict, db_info: Optional[Dict]) -> str:
        """Generar bloque de información de Discogs como cita"""
        content = "> Información del álbum facilitada por discogs.com:\n>\n"

        # Información básica
        year = item.get('year', 'Desconocido')
        content += f"> **Fecha de lanzamiento**: {year if year and year != 0 else 'Desconocida'}\n>\n"

        genres = item.get('genres', 'Desconocidos')
        content += f"> **Géneros**: {genres if genres else 'Desconocidos'}\n>\n"

        styles = item.get('styles', 'Desconocidos')
        content += f"> **Estilos**: {styles if styles else 'Desconocidos'}\n>\n"

        labels = item.get('labels', 'Desconocido')
        content += f"> **Sello:** {labels if labels else 'Desconocido'}\n>\n"

        # Si hay información adicional de la base de datos, añadirla
        if db_info:
            if db_info.get('producers'):
                content += f"> **Productores:** {db_info['producers']}\n>\n"

            if db_info.get('total_tracks') and db_info['total_tracks'] > 0:
                content += f"> **Total de pistas:** {db_info['total_tracks']}\n>\n"

        content += "> **Tracklist:**\n\n"

        return content


    def generate_service_links(self, item: Dict, db_info: Optional[Dict]) -> str:
        """Generar enlaces a servicios musicales"""
        artist_clean = self.clean_name(item['artist'])
        album_clean = self.clean_name(item['album'] if 'album' in item else item['title'])

        links = []

        # Bandcamp - buscar o usar de DB
        if db_info and db_info.get('bandcamp_url'):
            links.append(f'[![bandcamp](../links/svg/bandcamp.png "bandcamp")]({db_info["bandcamp_url"]})')
        else:
            search_url = f"https://bandcamp.com/search?q={artist_clean}%20{album_clean}"
            links.append(f'[![bandcamp](../links/svg/bandcamp.png "bandcamp")]({search_url})')

        # Discogs - usar resource_url del item
        discogs_url = item.get('resource_url', f"https://www.discogs.com/release/{item['discogs_id']}")
        links.append(f'[![discogs](../links/svg/discogs.png "discogs")]({discogs_url})')

        # Spotify
        if db_info and db_info.get('spotify_url'):
            links.append(f'[![spotify](../links/svg/spotify.png "spotify")]({db_info["spotify_url"]})')
        else:
            links.append('<!-- [![spotify](../links/svg/spotify.png "spotify")]() -->')

        # Last.fm
        if db_info and db_info.get('lastfm_url'):
            links.append(f'[![lastfm](../links/svg/lastfm.png "lastfm")]({db_info["lastfm_url"]})')
        else:
            links.append('<!-- [![lastfm](../links/svg/lastfm.png "lastfm")]() -->')

        # MusicBrainz
        if db_info and db_info.get('musicbrainz_url'):
            links.append(f'[![musicbrainz](../links/svg/musicbrainz.png "musicbrainz")]({db_info["musicbrainz_url"]})')
        else:
            links.append('<!-- [![musicbrainz](../links/svg/musicbrainz.png "musicbrainz")]() -->')

        # Wikipedia
        if db_info and db_info.get('wikipedia_url'):
            links.append(f'[![wikipedia](../links/svg/wikipedia.png "wikipedia")]({db_info["wikipedia_url"]})')
        else:
            links.append('<!-- [![wikipedia](../links/svg/wikipedia.png "wikipedia")]() -->')

        # YouTube
        if db_info and db_info.get('youtube_url'):
            links.append(f'[![youtube](../links/svg/youtube.png "youtube")]({db_info["youtube_url"]})')
        else:
            links.append('<!-- [![youtube](../links/svg/youtube.png "youtube")]() -->')

        return '\n'.join(links) + '\n\n'

    def download_cover(self, cover_url: str, post_dir: Path) -> bool:
        """Descargar carátula"""
        if not cover_url or cover_url == 'null':
            logging.warning("No hay URL de carátula disponible")
            return False

        try:
            response = requests.get(cover_url, stream=True, timeout=30)
            response.raise_for_status()

            cover_file = post_dir / "image.jpeg"
            with open(cover_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logging.debug("Carátula descargada correctamente")
            return True

        except Exception as e:
            logging.warning(f"Error descargando carátula: {e}")
            return False




# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Gestor de Colección de Discogs')
    parser.add_argument('-d', '--debug', action='store_true', help='Activar modo debug')
    parser.add_argument('-t', '--test', action='store_true', help='Solo ejecutar tests de API')
    parser.add_argument('-f', '--force', action='store_true', help='Forzar reprocesamiento de todos los items')

    args = parser.parse_args()

    try:
        # Configuración
        config = Config()
        logger = setup_logging(config.log_file, args.debug)

        logging.info("=== Iniciando Gestor de Colección de Discogs ===")

        # Cliente Discogs
        client = DiscogsClient(config.discogs_token, config.discogs_username)

        # Test de conexión
        if not client.test_connection():
            logging.error("Error en tests de conectividad")
            return 1

        if args.test:
            logging.info("Solo tests solicitados, terminando")
            return 0

        # Procesador de colección
        processor = CollectionProcessor(config)

        if args.force:
            config.registry_file.unlink(missing_ok=True)
            processor.registry = {"processed": [], "added": [], "skipped": []}
            logging.info("Registro borrado, se procesarán todos los items")

        # Obtener colección
        raw_collection = client.get_collection()
        if not raw_collection:
            logging.warning("No se obtuvo colección o está vacía")
            return 1

        # Procesar items
        parsed_items = processor.parse_collection(raw_collection)
        if not parsed_items:
            logging.warning("No hay items parseados para procesar")
            return 1

        # Crear posts
        post_creator = PostCreator(config)

        processed_count = 0
        added_count = 0
        skipped_count = 0
        already_processed_count = 0

        for i, item in enumerate(parsed_items, 1):
            discogs_id = str(item['discogs_id'])

            if processor.is_processed(discogs_id):
                already_processed_count += 1
                continue

            processed_count += 1

            if post_creator.ask_confirmation(item, i, len(parsed_items)):
                if post_creator.create_post(item):
                    processor.mark_processed(discogs_id, 'added')
                    added_count += 1
                    logging.info(f"✅ Post creado para: {item['artist']} - {item['title']}")
                else:
                    logging.error(f"❌ Error creando post para: {item['artist']} - {item['title']}")
            else:
                processor.mark_processed(discogs_id, 'skipped')
                skipped_count += 1
                logging.info(f"Usuario saltó: {item['artist']} - {item['title']}")

        # Resumen final
        logging.info("=== Procesamiento completado ===")
        logging.info(f"Items ya procesados: {already_processed_count}")
        logging.info(f"Items nuevos procesados: {processed_count}")
        logging.info(f"Posts añadidos: {added_count}")
        logging.info(f"Items saltados: {skipped_count}")

        return 0

    except Exception as e:
        logging.error(f"Error fatal: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
