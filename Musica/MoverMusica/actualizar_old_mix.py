#!/usr/bin/env python3
"""
Script para actualizar archivos de música en subcarpetas:
1. Renombrar archivos según formato "$artista - $song ($date $album) [$label]"
2. Marcar todas las canciones como favoritas en ListenBrainz (y en Last.fm, si hay claves de su API de pago)

Autor: Basado en el script mover_mix_playerctl.py
"""

import os
import sys
import subprocess
import json
import re
import hashlib
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Token de https://listenbrainz.org/settings/
LISTENBRAINZ_TOKEN = os.getenv("LISTENBRAINZ_TOKEN")
LISTENBRAINZ_API = "https://api.listenbrainz.org/1/"

# Configuración de Last.fm
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")
LASTFM_USERNAME = os.getenv("LASTFM_USERNAME")
LASTFM_PASSWORD = os.getenv("LASTFM_PASSWORD")

# Verificar que las credenciales de Last.fm están disponibles
lastfm_credentials_valid = all([
    LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_USERNAME, LASTFM_PASSWORD
])

def create_lastfm_signature(params, api_secret):
    """Crear firma para peticiones a Last.fm API"""
    # Ordenar parámetros alfabéticamente y crear string para firma
    sorted_params = sorted(params.items())
    signature_string = ""

    for name, value in sorted_params:
        if name != "format":  # Excluir format de la firma
            signature_string += name + str(value)

    # Añadir clave secreta
    signature_string += api_secret

    # Calcular MD5
    return hashlib.md5(signature_string.encode("utf-8")).hexdigest()

def get_lastfm_session_key():
    """Obtener session key de Last.fm"""
    if not lastfm_credentials_valid:
        print("⚠️ Faltan credenciales de Last.fm en el archivo .env")
        return None

    # Obtener token de autenticación
    auth_url = "https://ws.audioscrobbler.com/2.0/"
    auth_params = {
        "method": "auth.getMobileSession",
        "username": LASTFM_USERNAME,
        "password": LASTFM_PASSWORD,
        "api_key": LASTFM_API_KEY,
        "format": "json"
    }

    # Crear firma para autenticación
    signature = create_lastfm_signature(auth_params, LASTFM_API_SECRET)
    auth_params["api_sig"] = signature

    try:
        # Realizar petición de autenticación
        auth_response = requests.post(auth_url, data=auth_params)

        if auth_response.status_code != 200:
            print(f"⚠️ Error de autenticación en Last.fm: {auth_response.text}")
            return None

        session_key = auth_response.json().get("session", {}).get("key")

        if not session_key:
            print("⚠️ No se pudo obtener session key de Last.fm")
            return None

        return session_key

    except Exception as e:
        print(f"⚠️ Error obteniendo session key de Last.fm: {e}")
        return None

def add_to_lastfm_loved(artist, title, session_key):
    """Añadir canción a las loved tracks de Last.fm usando la API"""
    if not session_key:
        return False

    try:
        auth_url = "https://ws.audioscrobbler.com/2.0/"

        # Añadir canción a loved tracks
        love_params = {
            "method": "track.love",
            "artist": artist,
            "track": title,
            "api_key": LASTFM_API_KEY,
            "sk": session_key,
            "format": "json"
        }

        # Crear firma para petición love
        love_signature = create_lastfm_signature(love_params, LASTFM_API_SECRET)
        love_params["api_sig"] = love_signature

        # Realizar petición para marcar como loved
        love_response = requests.post(auth_url, data=love_params)

        if love_response.status_code != 200:
            print(f"⚠️ Error añadiendo '{artist} - {title}' a loved tracks: {love_response.text}")
            return False

        print(f"✓ Canción '{artist} - {title}' añadida a loved tracks de Last.fm")
        return True

    except Exception as e:
        print(f"⚠️ Error añadiendo canción a Last.fm: {e}")
        return False

def listenbrainz_call(method, path, **kw):
    """Petición a ListenBrainz respetando su límite de peticiones"""
    for _ in range(3):
        response = requests.request(method, LISTENBRAINZ_API + path, timeout=20,
                                    headers={"Authorization": f"Token {LISTENBRAINZ_TOKEN}"}, **kw)
        if response.status_code != 429:
            break
        time.sleep(float(response.headers.get("X-RateLimit-Reset-In", 10)) + 1)
    response.raise_for_status()
    return response.json()

def recording_mbid(file_path, artist, title):
    """MBID de la grabación: la etiqueta de Picard o, si no la lleva, la búsqueda de ListenBrainz"""
    try:
        import mutagen
        tags = mutagen.File(file_path, easy=True) or {}
        mbid = (tags.get('musicbrainz_trackid') or [''])[0].strip()
        if re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', mbid, re.I):
            return mbid.lower()
    except Exception:
        pass
    found = listenbrainz_call("GET", "metadata/lookup/", params={"artist_name": artist, "recording_name": title})
    return found.get('recording_mbid')

def add_to_listenbrainz_loved(file_path, artist, title):
    """Marcar la canción como favorita en ListenBrainz"""
    try:
        mbid = recording_mbid(file_path, artist, title)
        if not mbid:
            print(f"⚠️ '{artist} - {title}' no está en MusicBrainz: no se puede marcar en ListenBrainz")
            return False
        listenbrainz_call("POST", "feedback/recording-feedback", json={"recording_mbid": mbid, "score": 1})
        print(f"✓ Canción '{artist} - {title}' añadida a favoritas de ListenBrainz")
        return True
    except (requests.RequestException, ValueError) as e:
        print(f"⚠️ Error añadiendo '{artist} - {title}' a ListenBrainz: {e}")
        return False

def get_file_metadata(file_path):
    """Obtener metadatos del archivo usando ffprobe o exiftool"""
    metadata = {
        'artist': '',
        'title': '',
        'album': '',
        'date': '',
        'label': ''
    }

    # Intentar con ffprobe primero
    try:
        # Verificar si ffprobe está disponible
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)

        # Leer metadatos
        metadata_result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path],
            capture_output=True, text=True, check=True
        )

        # Analizar JSON
        try:
            json_data = json.loads(metadata_result.stdout)
            tags = json_data.get('format', {}).get('tags', {})

            # Extraer metadatos (probando diferentes formatos de etiquetas)
            metadata['artist'] = tags.get('artist', tags.get('ARTIST', ''))
            metadata['title'] = tags.get('title', tags.get('TITLE', ''))
            metadata['album'] = tags.get('album', tags.get('ALBUM', ''))
            metadata['date'] = tags.get('date', tags.get('DATE', ''))
            if not metadata['date']:
                metadata['date'] = tags.get('year', tags.get('YEAR', ''))
            metadata['label'] = tags.get('label', tags.get('LABEL',
                                tags.get('publisher', tags.get('PUBLISHER', ''))))

            # Si tenemos artist y title, considerar exitoso
            if metadata['artist'] and metadata['title']:
                return metadata

        except json.JSONDecodeError:
            pass

    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Si ffprobe falla, intentar con exiftool
    try:
        # Verificar si exiftool está disponible
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)

        # Leer metadatos
        artist_result = subprocess.run(['exiftool', '-Artist', '-s3', file_path],
                                    capture_output=True, text=True)
        metadata['artist'] = artist_result.stdout.strip()

        title_result = subprocess.run(['exiftool', '-Title', '-s3', file_path],
                                    capture_output=True, text=True)
        metadata['title'] = title_result.stdout.strip()

        album_result = subprocess.run(['exiftool', '-Album', '-s3', file_path],
                                    capture_output=True, text=True)
        metadata['album'] = album_result.stdout.strip()

        date_result = subprocess.run(['exiftool', '-Year', '-s3', file_path],
                                  capture_output=True, text=True)
        metadata['date'] = date_result.stdout.strip()

        label_result = subprocess.run(['exiftool', '-Label', '-s3', file_path],
                                   capture_output=True, text=True)
        metadata['label'] = label_result.stdout.strip()

    except (subprocess.SubprocessError, FileNotFoundError):
        print(f"⚠️ No se pudieron leer los metadatos de {file_path}")

    return metadata

def rename_file_with_metadata(file_path, metadata):
    """Renombrar archivo con formato basado en metadatos"""
    try:
        # Obtener directorio y extensión del archivo
        dir_path = os.path.dirname(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()

        # Verificar si tenemos información suficiente
        if not metadata['artist'] and not metadata['title']:
            print(f"⚠️ No hay suficientes metadatos para renombrar {file_path}")
            return file_path

        # Construir nuevo nombre de archivo
        new_filename = f"{metadata['artist']} - {metadata['title']}"

        # Añadir date y album si están disponibles
        if metadata['date'] or metadata['album']:
            date_album_part = ""
            if metadata['date']:
                date_album_part += metadata['date']
            if metadata['album']:
                if date_album_part:
                    date_album_part += " "
                date_album_part += metadata['album']

            new_filename += f" ({date_album_part})"

        # Añadir label si está disponible
        if metadata['label']:
            new_filename += f" [{metadata['label']}]"

        # Limpiar caracteres problemáticos del nombre de archivo
        new_filename = re.sub(r'[/\\?%*:|"<>]', '-', new_filename)

        # Añadir extensión
        new_filename += file_ext

        # Ruta completa del nuevo archivo
        new_file_path = os.path.join(dir_path, new_filename)

        # Evitar renombrar si el nombre es el mismo
        if file_path == new_file_path:
            return file_path

        # Evitar sobrescribir archivos existentes
        if os.path.exists(new_file_path) and file_path != new_file_path:
            print(f"⚠️ Ya existe un archivo con el nombre {new_filename}, no se puede renombrar")
            return file_path

        print(f"🔄 Renombrando: {os.path.basename(file_path)} -> {new_filename}")

        # Renombrar usando os.rename
        os.rename(file_path, new_file_path)
        return new_file_path

    except Exception as e:
        print(f"⚠️ Error renombrando {file_path}: {e}")
        return file_path

def process_music_directory(base_path, add_to_lastfm=True, session_key=None, dry_run=False, verbose=False,
                            add_to_listenbrainz=False):
    """Procesar todos los archivos de música en una ruta y sus subcarpetas"""
    # Extensiones de archivos de música
    music_extensions = ['.mp3', '.flac', '.ogg', '.wav', '.m4a', '.opus']

    # Contadores para estadísticas
    stats = {
        'total_files': 0,
        'renamed_files': 0,
        'lastfm_loved': 0,
        'listenbrainz_loved': 0,
        'errors': 0
    }

    # Recorrer todas las carpetas y subcarpetas
    for root, dirs, files in os.walk(base_path):
        # Saltar carpetas ocultas
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for file in files:
            # Verificar si es un archivo de música
            file_ext = os.path.splitext(file)[1].lower()
            if file_ext not in music_extensions:
                continue

            stats['total_files'] += 1
            file_path = os.path.join(root, file)

            if verbose:
                print(f"\n📄 Procesando: {file_path}")

            # Obtener metadatos
            metadata = get_file_metadata(file_path)

            # Si no hay metadatos suficientes, continuar con el siguiente archivo
            if not metadata['artist'] or not metadata['title']:
                print(f"⚠️ No se pudieron obtener metadatos para {file}")
                stats['errors'] += 1
                continue

            if verbose:
                print(f"  📋 Metadatos: {metadata['artist']} - {metadata['title']} | "
                      f"Álbum: {metadata['album']} | Fecha: {metadata['date']} | "
                      f"Label: {metadata['label']}")

            # Renombrar archivo
            if not dry_run:
                new_path = rename_file_with_metadata(file_path, metadata)
                if new_path != file_path:
                    stats['renamed_files'] += 1
                    file_path = new_path
            else:
                # En modo dry run, simular el renombre
                dir_path = os.path.dirname(file_path)
                file_ext = os.path.splitext(file_path)[1].lower()
                new_filename = f"{metadata['artist']} - {metadata['title']}"
                if metadata['date'] or metadata['album']:
                    date_album_part = ""
                    if metadata['date']:
                        date_album_part += metadata['date']
                    if metadata['album']:
                        if date_album_part:
                            date_album_part += " "
                        date_album_part += metadata['album']
                    new_filename += f" ({date_album_part})"
                if metadata['label']:
                    new_filename += f" [{metadata['label']}]"
                new_filename = re.sub(r'[/\\?%*:|"<>]', '-', new_filename) + file_ext
                print(f"🔄 [DRY RUN] Renombrar: {file} -> {new_filename}")

            # Marcar como favorita en ListenBrainz
            if add_to_listenbrainz and dry_run:
                print(f"❤️ [DRY RUN] Marcar favorita en ListenBrainz: {metadata['artist']} - {metadata['title']}")
            elif add_to_listenbrainz:
                # Una petición por segundo
                time.sleep(1)
                if add_to_listenbrainz_loved(file_path, metadata['artist'], metadata['title']):
                    stats['listenbrainz_loved'] += 1

            # Añadir a Last.fm loved tracks
            if add_to_lastfm and session_key and not dry_run:
                # Pausa para evitar demasiadas peticiones rápidas a Last.fm
                time.sleep(0.5)

                if add_to_lastfm_loved(metadata['artist'], metadata['title'], session_key):
                    stats['lastfm_loved'] += 1
            elif add_to_lastfm and dry_run:
                print(f"❤️ [DRY RUN] Añadir a Last.fm loved: {metadata['artist']} - {metadata['title']}")

    return stats

def main():
    """Función principal del script"""
    parser = argparse.ArgumentParser(description='Actualizar archivos de música: renombrar y marcar como favoritas en ListenBrainz (y Last.fm).')
    parser.add_argument('path', help='Ruta base donde buscar archivos de música')
    parser.add_argument('--no-listenbrainz', action='store_true', help='No marcar favoritas en ListenBrainz')
    parser.add_argument('--no-lastfm', action='store_true', help='No añadir canciones a Last.fm loved')
    parser.add_argument('--dry-run', action='store_true', help='Mostrar qué se haría sin realizar cambios')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar información detallada')

    args = parser.parse_args()

    base_path = os.path.abspath(args.path)
    if not os.path.exists(base_path):
        print(f"Error: La ruta {base_path} no existe")
        return 1

    print(f"Procesando archivos de música en: {base_path}")

    # Verificar que tenemos las herramientas necesarias
    tools_available = []
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        tools_available.append('ffprobe')
    except:
        pass

    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
        tools_available.append('exiftool')
    except:
        pass

    if not tools_available:
        print("⚠️ No se encontró ffprobe ni exiftool. Al menos una de estas herramientas es necesaria.")
        print("Instala ffmpeg (incluye ffprobe) o exiftool:")
        print("  sudo apt install ffmpeg    # Para distribuciones basadas en Debian/Ubuntu")
        print("  sudo dnf install ffmpeg    # Para distribuciones basadas en Fedora")
        print("  sudo pacman -S ffmpeg      # Para distribuciones basadas en Arch")
        return 1

    print(f"✓ Herramientas disponibles: {', '.join(tools_available)}")

    # Obtener session key para Last.fm si es necesario
    if not args.no_listenbrainz and not LISTENBRAINZ_TOKEN:
        print("ℹ️ Sin LISTENBRAINZ_TOKEN en el .env: no se marcarán favoritas en ListenBrainz")

    session_key = None
    if not args.no_lastfm:
        if lastfm_credentials_valid:
            print("Autenticando con Last.fm...")
            session_key = get_lastfm_session_key()
            if session_key:
                print("✓ Autenticación con Last.fm exitosa")
            else:
                print("⚠️ No se pudo autenticar con Last.fm")
        else:
            print("⚠️ Last.fm: Faltan credenciales en el archivo .env")
            print("Para habilitar la función de Last.fm, añade estas variables a tu archivo .env:")
            print("  LASTFM_API_KEY=tu_api_key")
            print("  LASTFM_API_SECRET=tu_api_secret")
            print("  LASTFM_USERNAME=tu_usuario")
            print("  LASTFM_PASSWORD=tu_contraseña")

    # Modo dry run
    if args.dry_run:
        print("\n🔍 MODO DRY RUN: No se realizarán cambios reales\n")

    # Procesar directorios
    start_time = time.time()
    stats = process_music_directory(
        base_path,
        add_to_lastfm=not args.no_lastfm,
        add_to_listenbrainz=bool(LISTENBRAINZ_TOKEN) and not args.no_listenbrainz,
        session_key=session_key,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    end_time = time.time()

    # Mostrar estadísticas
    print("\n📊 Estadísticas:")
    print(f"  Total de archivos procesados: {stats['total_files']}")
    if not args.dry_run:
        print(f"  Archivos renombrados: {stats['renamed_files']}")
        if LISTENBRAINZ_TOKEN and not args.no_listenbrainz:
            print(f"  Favoritas en ListenBrainz: {stats['listenbrainz_loved']}")
        if not args.no_lastfm:
            print(f"  Canciones añadidas a Last.fm loved: {stats['lastfm_loved']}")
    print(f"  Errores: {stats['errors']}")
    print(f"  Tiempo total: {end_time - start_time:.2f} segundos")

    return 0

if __name__ == "__main__":
    sys.exit(main())
