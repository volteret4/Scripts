#!/usr/bin/env python3
"""
Script Name: update_collection.py
Description: Actualiza el artículo de colección de discos del blog VVMM
Author: volteret4
License: MIT

Actualiza content/coleccion/coleccion.md con la colección de Discogs
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
from urllib.parse import urlparse

class DiscogsCollectionUpdater:
    def __init__(self, project_root: str = None, debug: bool = False):
        """Inicializar el actualizador de colección"""
        self.project_root = Path(project_root) if project_root else Path(__file__).parent

        # Configurar logging
        self.setup_logging(debug)

        # Cargar configuración
        self.load_config()

        # Configurar rutas
        self.setup_paths()

        # Configurar cliente de Discogs
        self.setup_discogs_client()

    def setup_logging(self, debug: bool):
        """Configurar sistema de logging"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        level = logging.DEBUG if debug else logging.INFO

        # Crear directorio de logs
        log_dir = self.project_root / '.content' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"collection_update_{datetime.now().strftime('%Y%m%d')}.log"

        # Configurar logging para archivo y consola
        logging.basicConfig(
            level=level,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self):
        """Cargar variables de entorno y configuración"""
        # Intentar cargar .env si existe
        env_file = self.project_root / '.env'
        if env_file.exists():
            self.logger.debug(f"Cargando variables desde {env_file}")
            with open(env_file) as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        try:
                            key, value = line.strip().split('=', 1)
                            os.environ[key] = value.strip('"\'')
                        except ValueError:
                            continue

        # Verificar token de Discogs
        self.discogs_token = os.getenv('DISCOGS_TOKEN')
        if not self.discogs_token:
            self.logger.error("Variable DISCOGS_TOKEN no encontrada")
            sys.exit(1)

        # Otras configuraciones
        self.blog_dir = Path(os.getenv('BLOG_DIR', '/mnt/NFS/blogs/vvmm'))
        self.rate_limit_delay = 1.2  # Segundos entre requests

    def setup_paths(self):
        """Configurar rutas del proyecto"""
        self.content_dir = self.project_root / '.content'
        self.cache_dir = self.content_dir / 'cache'
        self.logs_dir = self.content_dir / 'logs'

        # Rutas específicas del blog
        self.collection_dir = self.blog_dir / 'content' / 'coleccion'
        self.collection_file = self.collection_dir / 'coleccion.md'
        self.covers_dir = self.collection_dir / 'covers'

        # Crear directorios necesarios
        for directory in [self.cache_dir, self.logs_dir, self.collection_dir, self.covers_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.collection_cache = self.cache_dir / 'discogs_collection.json'

    def setup_discogs_client(self):
        """Configurar cliente HTTP para Discogs"""
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Discogs token={self.discogs_token}',
            'User-Agent': 'VVMM-CollectionUpdater/1.0 +https://github.com/volteret4'
        })

        # URLs base
        self.discogs_api_base = 'https://api.discogs.com'

    def get_discogs_user(self) -> str:
        """Obtener información del usuario actual"""
        self.logger.info("Obteniendo información del usuario de Discogs...")

        try:
            response = self.session.get(f'{self.discogs_api_base}/oauth/identity')
            response.raise_for_status()

            user_data = response.json()
            username = user_data.get('username')

            if not username:
                raise ValueError("No se pudo obtener el nombre de usuario")

            self.logger.info(f"Usuario de Discogs: {username}")
            return username

        except requests.RequestException as e:
            self.logger.error(f"Error obteniendo usuario: {e}")
            raise

    def get_collection_from_cache(self) -> Optional[List[Dict]]:
        """Intentar cargar colección desde cache"""
        if not self.collection_cache.exists():
            return None

        # Verificar si el cache es reciente (menos de 1 día)
        cache_age = time.time() - self.collection_cache.stat().st_mtime
        if cache_age > 24 * 3600:  # 24 horas
            self.logger.info("Cache expirado, actualizando desde Discogs")
            return None

        try:
            with open(self.collection_cache, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.logger.info(f"Usando colección desde cache ({len(data)} elementos)")
            return data

        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Error leyendo cache: {e}")
            return None

    def save_collection_to_cache(self, collection_data: List[Dict]):
        """Guardar colección en cache"""
        try:
            with open(self.collection_cache, 'w', encoding='utf-8') as f:
                json.dump(collection_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Colección guardada en cache: {self.collection_cache}")

        except IOError as e:
            self.logger.error(f"Error guardando cache: {e}")

    def get_discogs_collection(self, username: str, force_refresh: bool = False) -> List[Dict]:
        """Obtener colección completa de Discogs"""
        # Intentar usar cache primero
        if not force_refresh:
            cached_data = self.get_collection_from_cache()
            if cached_data:
                return cached_data

        self.logger.info(f"Obteniendo colección fresca desde Discogs para {username}...")

        all_items = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            self.logger.info(f"Obteniendo página {page} de {total_pages}...")

            try:
                url = f'{self.discogs_api_base}/users/{username}/collection/folders/0/releases'
                params = {
                    'page': page,
                    'per_page': 100
                }

                response = self.session.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # Actualizar información de paginación
                pagination = data.get('pagination', {})
                total_pages = pagination.get('pages', 1)
                total_items = pagination.get('items', 0)

                if page == 1:
                    self.logger.info(f"Total de elementos en la colección: {total_items}")

                # Procesar elementos de esta página
                releases = data.get('releases', [])
                processed_items = self.process_collection_page(releases)
                all_items.extend(processed_items)

                self.logger.debug(f"Procesados {len(processed_items)} elementos de la página {page}")

                page += 1

                # Respetar rate limits
                if page <= total_pages:
                    time.sleep(self.rate_limit_delay)

            except requests.RequestException as e:
                self.logger.error(f"Error obteniendo página {page}: {e}")
                raise

        self.logger.info(f"Colección completa obtenida: {len(all_items)} elementos")

        # Guardar en cache
        self.save_collection_to_cache(all_items)

        return all_items

    def process_collection_page(self, releases: List[Dict]) -> List[Dict]:
        """Procesar una página de elementos de la colección"""
        processed_items = []

        for item in releases:
            basic_info = item.get('basic_information', {})

            # Extraer información básica
            processed_item = {
                'id': item.get('id'),
                'instance_id': item.get('instance_id'),
                'date_added': item.get('date_added'),
                'rating': item.get('rating'),
                'release_id': basic_info.get('id'),
                'title': basic_info.get('title', ''),
                'year': basic_info.get('year'),
                'master_id': basic_info.get('master_id'),
                'master_url': basic_info.get('master_url'),
                'resource_url': basic_info.get('resource_url'),
                'thumb': basic_info.get('thumb', ''),
                'cover_image': basic_info.get('cover_image', ''),
                'artists': [
                    {'name': a.get('name', ''), 'id': a.get('id')}
                    for a in basic_info.get('artists', [])
                ],
                'labels': [
                    {'name': l.get('name', ''), 'catno': l.get('catno', '')}
                    for l in basic_info.get('labels', [])
                ],
                'genres': basic_info.get('genres', []),
                'styles': basic_info.get('styles', []),
                'formats': [
                    {'name': f.get('name', ''), 'qty': f.get('qty', '1')}
                    for f in basic_info.get('formats', [])
                ]
            }

            processed_items.append(processed_item)

        return processed_items

    def clean_filename(self, text: str) -> str:
        """Limpiar texto para usar como nombre de archivo (formato compatible con existentes)"""
        import re
        # Reemplazar caracteres problemáticos pero mantener guiones
        clean = re.sub(r'[^\w\s-]', '', text)
        clean = re.sub(r'\s+', '-', clean)  # Espacios a guiones
        clean = re.sub(r'-+', '-', clean)   # Múltiples guiones a uno
        return clean.strip('-')

    def find_existing_cover(self, artist_str: str, title: str) -> Optional[str]:
        """Buscar carátula existente con diferentes formatos de nombre"""
        artist_clean = self.clean_filename(artist_str)
        title_clean = self.clean_filename(title)

        # Patrones de nombres a buscar (basado en tus archivos existentes)
        patterns = [
            f"{artist_clean}-_-{title_clean}.jpg",
            f"{artist_clean}_-_{title_clean}.jpg",
            f"{artist_clean}_{title_clean}.jpg",
            f"{artist_clean}-{title_clean}.jpg"
        ]

        for pattern in patterns:
            cover_path = self.covers_dir / pattern
            if cover_path.exists():
                self.logger.debug(f"Carátula existente encontrada: {pattern}")
                return pattern

        return None

    def download_cover_with_retries(self, cover_url: str, cover_path: Path, max_retries: int = 3) -> bool:
        """Descargar carátula con reintentos y headers apropiados"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.logger.debug(f"Intento {attempt + 1} para {cover_path.name}")
                    time.sleep(2 ** attempt)  # Backoff exponencial

                response = requests.get(cover_url, headers=headers, timeout=30, stream=True)
                response.raise_for_status()

                # Verificar que es una imagen válida
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    self.logger.warning(f"Respuesta no es imagen: {content_type}")
                    continue

                # Descargar y guardar
                with open(cover_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # Verificar que el archivo se escribió correctamente
                if cover_path.exists() and cover_path.stat().st_size > 0:
                    return True
                else:
                    self.logger.warning(f"Archivo vacío o no creado: {cover_path}")
                    continue

            except requests.RequestException as e:
                self.logger.debug(f"Error en intento {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    self.logger.warning(f"Error descargando carátula después de {max_retries} intentos: {e}")
                continue
            except IOError as e:
                self.logger.warning(f"Error escribiendo archivo {cover_path}: {e}")
                break

        return False
    def download_cover(self, item: Dict) -> Optional[str]:
        """Descargar carátula de un álbum"""
        # Extraer información del álbum
        artists = item.get('artists', [])
        artist_names = [a.get('name', '') for a in artists]
        artist_str = ', '.join(artist_names) if artist_names else 'Artista_Desconocido'

        title = item.get('title', 'Titulo_Desconocido')
        release_id = item.get('release_id', '')

        # Buscar carátula existente primero
        existing_cover = self.find_existing_cover(artist_str, title)
        if existing_cover:
            return existing_cover

        # URL de carátula (preferir cover_image sobre thumb)
        cover_url = item.get('cover_image') or item.get('thumb', '')

        if not cover_url or cover_url == 'null':
            self.logger.debug(f"No hay carátula para {artist_str} - {title}")
            return None

        # Generar nombre de archivo (formato compatible con existentes)
        artist_clean = self.clean_filename(artist_str)
        title_clean = self.clean_filename(title)
        cover_filename = f"{artist_clean}-_-{title_clean}.jpg"
        cover_path = self.covers_dir / cover_filename

        # Si ya existe con este formato, no descargar de nuevo
        if cover_path.exists():
            self.logger.debug(f"Carátula ya existe: {cover_filename}")
            return cover_filename

        # Intentar descargar carátula
        self.logger.debug(f"Descargando carátula: {cover_filename}")

        if self.download_cover_with_retries(cover_url, cover_path):
            self.logger.debug(f"Carátula descargada: {cover_filename}")
            return cover_filename
        else:
            # Si falla la descarga, intentar buscar de nuevo por si se descargó con otro nombre
            existing_cover = self.find_existing_cover(artist_str, title)
            if existing_cover:
                self.logger.info(f"Usando carátula existente: {existing_cover}")
                return existing_cover

            self.logger.warning(f"No se pudo descargar carátula para {artist_str} - {title}")
            return None

    def download_all_covers(self, collection_data: List[Dict], covers_only: bool = False):
        """Descargar todas las carátulas de la colección"""
        if covers_only:
            self.logger.info("Modo solo carátulas - descargando carátulas faltantes")
        else:
            self.logger.info("Descargando carátulas de la colección...")

        downloaded = 0
        total = len(collection_data)

        for i, item in enumerate(collection_data, 1):
            if i % 10 == 0:
                self.logger.info(f"Progreso carátulas: {i}/{total}")

            cover_filename = self.download_cover(item)
            if cover_filename:
                downloaded += 1

            # Pequeña pausa para no sobrecargar
            time.sleep(0.1)

        self.logger.info(f"Carátulas descargadas: {downloaded}/{total}")

    def format_date(self, date_str: str) -> str:
        """Formatear fecha para mostrar"""
        if not date_str:
            return ''

        try:
            # Intentar parsear fecha ISO
            if 'T' in date_str:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')

            return date_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            return date_str.split('T')[0] if 'T' in date_str else date_str

    def generate_album_html(self, item: Dict) -> str:
        """Generar HTML para un álbum individual compatible con Hugo"""
        # Extraer información
        artists = item.get('artists', [])
        artist_names = [a.get('name', '') for a in artists]
        artist_str = ', '.join(artist_names) if artist_names else 'Artista Desconocido'

        title = item.get('title', 'Título Desconocido')
        year = item.get('year', '')
        release_id = item.get('release_id', '')

        # Información adicional
        date_added = self.format_date(item.get('date_added', ''))
        genres = item.get('genres', [])
        styles = item.get('styles', [])

        # Buscar carátula existente
        existing_cover = self.find_existing_cover(artist_str, title)
        if existing_cover:
            cover_filename = existing_cover
        else:
            artist_clean = self.clean_filename(artist_str)
            title_clean = self.clean_filename(title)
            cover_filename = f"{artist_clean}-_-{title_clean}.jpg"

        # Generar Markdown + shortcode Hugo en lugar de HTML crudo
        content = f"## {artist_str} - {title}\n\n"

        # Usar shortcode de Hugo para la imagen y layout
        content += f'{{{{< album-display artist="{artist_str}" title="{title}" cover="covers/{cover_filename}" >}}}}\n\n'

        # Información en lista Markdown
        if date_added:
            content += f'**📅 Fecha agregado:** {date_added}  \n'

        if year:
            content += f'**🗓️ Año:** {year}  \n'

        if genres:
            genres_str = ', '.join(genres)
            content += f'**🎵 Géneros:** {genres_str}  \n'

        if styles:
            styles_str = ', '.join(styles)
            content += f'**🎨 Estilos:** {styles_str}  \n'

        # Enlaces si están disponibles
        if release_id:
            content += f'**🔗 Discogs:** [Ver en Discogs](https://www.discogs.com/release/{release_id})  \n'

        content += '\n{{< /album-display >}}\n\n'
        content += '---\n\n'

        return content

    def generate_collection_article(self, collection_data: List[Dict]):
        """Generar el artículo completo de la colección"""
        self.logger.info("Generando artículo de colección...")

        # Ordenar por fecha de agregado (más reciente primero)
        sorted_data = sorted(
            collection_data,
            key=lambda x: x.get('date_added', ''),
            reverse=True
        )

        # Generar frontmatter
        now = datetime.now()
        content = f"""---
title: "coleccion"
date: {now.strftime('%Y-%m-%dT%H:%M:%S%z')}
tags:
  - coleccion
  - discogs
menu: main
---

# Mi Colección de Discos

Esta es mi colección personal de discos obtenida desde [Discogs](https://www.discogs.com).

**Última actualización:** {now.strftime('%d de %B de %Y a las %H:%M')}
**Total de álbumes:** {len(collection_data)}

---

"""

        # Generar contenido para cada álbum
        for item in sorted_data:
            content += self.generate_album_html(item)

        # Escribir archivo
        try:
            with open(self.collection_file, 'w', encoding='utf-8') as f:
                f.write(content)

            self.logger.info(f"Artículo generado: {self.collection_file}")

        except IOError as e:
            self.logger.error(f"Error escribiendo artículo: {e}")
            raise

    def run(self, force_refresh: bool = False, covers_only: bool = False, no_covers: bool = False):
        """Ejecutar actualización completa"""
        self.logger.info("=== Iniciando actualización de colección de discos ===")

        try:
            # Obtener usuario
            username = self.get_discogs_user()

            # Obtener colección
            collection_data = self.get_discogs_collection(username, force_refresh)

            if not collection_data:
                self.logger.error("No se pudo obtener la colección")
                return False

            self.logger.info(f"Total de elementos en colección: {len(collection_data)}")

            # Descargar carátulas si no está deshabilitado
            if not no_covers:
                self.download_all_covers(collection_data, covers_only)

            # Generar artículo si no es modo solo carátulas
            if not covers_only:
                self.generate_collection_article(collection_data)

            # Estadísticas finales
            covers_count = len(list(self.covers_dir.glob("*.jpg")))
            self.logger.info(f"Carátulas disponibles: {covers_count}")

            self.logger.info("✅ Actualización de colección completada")

            # Notificación del sistema
            try:
                import subprocess
                subprocess.run([
                    'notify-send',
                    'Colección Actualizada',
                    f'Se procesaron {len(collection_data)} álbumes con {covers_count} carátulas'
                ], check=False)
            except (FileNotFoundError, subprocess.SubprocessError):
                pass  # notify-send no disponible

            return True

        except Exception as e:
            self.logger.error(f"Error durante la actualización: {e}")
            return False

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Actualizar colección de discos del blog VVMM desde Discogs'
    )

    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Activar modo debug'
    )

    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Forzar actualización desde Discogs (ignorar cache)'
    )

    parser.add_argument(
        '--covers-only',
        action='store_true',
        help='Solo descargar carátulas, no regenerar artículo'
    )

    parser.add_argument(
        '--no-covers',
        action='store_true',
        help='No descargar carátulas'
    )

    parser.add_argument(
        '--project-root',
        help='Ruta raíz del proyecto (por defecto: directorio del script)'
    )

    args = parser.parse_args()

    # Crear actualizador
    updater = DiscogsCollectionUpdater(
        project_root=args.project_root,
        debug=args.debug
    )

    # Ejecutar actualización
    success = updater.run(
        force_refresh=args.force_refresh,
        covers_only=args.covers_only,
        no_covers=args.no_covers
    )

    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
