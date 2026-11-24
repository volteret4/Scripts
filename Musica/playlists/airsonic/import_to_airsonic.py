#!/usr/bin/env python3
"""
Script para importar playlists M3U en Airsonic usando la API de Subsonic.
"""

import os
import argparse
import hashlib
import random
import string
import requests
import sys
from urllib.parse import quote
from pathlib import Path

class AirsonicClient:
    """Cliente para interactuar con la API de Airsonic/Subsonic."""

    def __init__(self, url, username, password, client_name='M3U_Importer'):
        """
        Inicializa el cliente de Airsonic.

        Args:
            url: URL base del servidor Airsonic (ej: http://localhost:4040)
            username: Nombre de usuario
            password: Contraseña
            client_name: Nombre del cliente (por defecto: M3U_Importer)
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.client_name = client_name
        self.api_version = '1.16.1'

    def _generate_token(self):
        """Genera un token de autenticación."""
        salt = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        token = hashlib.md5(f"{self.password}{salt}".encode()).hexdigest()
        return token, salt

    def _make_request(self, endpoint, params=None):
        """
        Realiza una petición a la API de Airsonic.

        Args:
            endpoint: Endpoint de la API (sin .view)
            params: Parámetros adicionales

        Returns:
            Respuesta JSON de la API
        """
        if params is None:
            params = {}

        # Generar token de autenticación
        token, salt = self._generate_token()

        # Parámetros base
        base_params = {
            'u': self.username,
            't': token,
            's': salt,
            'v': self.api_version,
            'c': self.client_name,
            'f': 'json'
        }

        # Combinar parámetros
        base_params.update(params)

        # Construir URL
        url = f"{self.url}/rest/{endpoint}.view"

        try:
            response = requests.get(url, params=base_params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Verificar respuesta
            if 'subsonic-response' not in data:
                raise Exception("Respuesta inválida del servidor")

            subsonic_response = data['subsonic-response']

            if subsonic_response.get('status') != 'ok':
                error = subsonic_response.get('error', {})
                error_msg = error.get('message', 'Error desconocido')
                raise Exception(f"Error de Airsonic: {error_msg}")

            return subsonic_response

        except requests.exceptions.RequestException as e:
            raise Exception(f"Error de conexión: {e}")

    def ping(self):
        """Verifica la conexión con el servidor."""
        try:
            self._make_request('ping')
            return True
        except Exception as e:
            print(f"Error al conectar: {e}", file=sys.stderr)
            return False

    def get_song_by_path(self, path):
        """
        Busca una canción por su ruta.

        Args:
            path: Ruta de la canción (formato /music/...)

        Returns:
            ID de la canción o None si no se encuentra
        """
        # Limpiar la ruta
        clean_path = path.strip()

        # Extraer información de la ruta
        parts = Path(clean_path).parts

        if len(parts) < 2:
            return None

        # Intentar buscar por nombre de archivo
        filename = parts[-1]
        # Quitar extensión para la búsqueda
        search_term = Path(filename).stem

        try:
            response = self._make_request('search3', {
                'query': search_term,
                'songCount': 50
            })

            # Buscar coincidencia exacta en los resultados
            search_result = response.get('searchResult3', {})
            songs = search_result.get('song', [])

            for song in songs:
                song_path = song.get('path', '')
                # Comparar rutas (normalizar para comparación)
                if clean_path.endswith(song_path) or song_path.endswith(parts[-1]):
                    return song.get('id')

            return None

        except Exception as e:
            print(f"  Error buscando '{filename}': {e}", file=sys.stderr)
            return None

    def create_playlist(self, name):
        """
        Crea una nueva playlist.

        Args:
            name: Nombre de la playlist

        Returns:
            ID de la playlist creada
        """
        try:
            response = self._make_request('createPlaylist', {
                'name': name
            })

            playlist = response.get('playlist', {})
            playlist_id = playlist.get('id')

            if not playlist_id:
                raise Exception("No se pudo obtener el ID de la playlist")

            return playlist_id

        except Exception as e:
            raise Exception(f"Error creando playlist: {e}")

    def add_to_playlist(self, playlist_id, song_ids):
        """
        Añade canciones a una playlist.

        Args:
            playlist_id: ID de la playlist
            song_ids: Lista de IDs de canciones
        """
        if not song_ids:
            return

        try:
            # Airsonic permite múltiples songId en una sola petición
            params = {'playlistId': playlist_id}

            # Añadir cada song_id como parámetro separado
            for song_id in song_ids:
                params[f'songIdToAdd'] = song_id
                self._make_request('updatePlaylist', params)
                params.pop('songIdToAdd')

        except Exception as e:
            raise Exception(f"Error añadiendo canciones a playlist: {e}")

    def get_playlists(self):
        """Obtiene lista de playlists existentes."""
        try:
            response = self._make_request('getPlaylists')
            playlists = response.get('playlists', {}).get('playlist', [])
            return playlists
        except Exception as e:
            print(f"Error obteniendo playlists: {e}", file=sys.stderr)
            return []

def read_m3u(m3u_path):
    """Lee un archivo m3u y devuelve una lista de rutas."""
    paths = []
    with open(m3u_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                paths.append(line)
    return paths

def import_playlist(client, m3u_path, playlist_name=None, skip_missing=False):
    """
    Importa una playlist M3U en Airsonic.

    Args:
        client: Cliente de Airsonic
        m3u_path: Ruta al archivo M3U
        playlist_name: Nombre de la playlist (si no se especifica, usa el nombre del archivo)
        skip_missing: Si es True, ignora canciones no encontradas; si es False, aborta
    """
    # Leer M3U
    print(f"\nLeyendo: {m3u_path}")
    paths = read_m3u(m3u_path)
    print(f"Canciones en la playlist: {len(paths)}")

    # Determinar nombre de la playlist
    if not playlist_name:
        playlist_name = Path(m3u_path).stem

    print(f"Nombre de la playlist: {playlist_name}")

    # Buscar IDs de canciones
    print(f"\nBuscando canciones en Airsonic...")
    song_ids = []
    not_found = []

    for i, path in enumerate(paths, 1):
        print(f"  [{i}/{len(paths)}] Buscando: {Path(path).name}", end='')
        song_id = client.get_song_by_path(path)

        if song_id:
            song_ids.append(song_id)
            print(" ✓")
        else:
            not_found.append(path)
            print(" ✗")

    # Verificar resultados
    print(f"\n{'='*60}")
    print(f"Encontradas: {len(song_ids)}/{len(paths)}")
    print(f"No encontradas: {len(not_found)}")
    print(f"{'='*60}")

    if not_found:
        print("\nCanciones no encontradas:")
        for path in not_found[:10]:  # Mostrar solo las primeras 10
            print(f"  - {path}")
        if len(not_found) > 10:
            print(f"  ... y {len(not_found) - 10} más")

    # Decidir si continuar
    if not_found and not skip_missing:
        response = input(f"\n¿Continuar creando la playlist sin las {len(not_found)} canciones no encontradas? (s/n): ")
        if response.lower() != 's':
            print("Importación cancelada")
            return False

    if not song_ids:
        print("\n❌ No se encontró ninguna canción. Importación cancelada.")
        return False

    # Crear playlist
    print(f"\nCreando playlist '{playlist_name}'...")
    try:
        playlist_id = client.create_playlist(playlist_name)
        print(f"✓ Playlist creada (ID: {playlist_id})")
    except Exception as e:
        print(f"❌ Error creando playlist: {e}", file=sys.stderr)
        return False

    # Añadir canciones
    print(f"Añadiendo {len(song_ids)} canciones...")
    try:
        # Añadir en lotes de 10 para evitar URLs muy largas
        batch_size = 10
        for i in range(0, len(song_ids), batch_size):
            batch = song_ids[i:i+batch_size]
            client.add_to_playlist(playlist_id, batch)
            print(f"  Añadidas {min(i+batch_size, len(song_ids))}/{len(song_ids)} canciones", end='\r')

        print(f"\n✅ Playlist '{playlist_name}' importada exitosamente")
        return True

    except Exception as e:
        print(f"\n❌ Error añadiendo canciones: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Importa playlists M3U en Airsonic/Subsonic.'
    )

    # Configuración del servidor
    parser.add_argument('--url', required=True, help='URL del servidor Airsonic (ej: http://localhost:4040)')
    parser.add_argument('--username', required=True, help='Nombre de usuario de Airsonic')
    parser.add_argument('--password', required=True, help='Contraseña de Airsonic')

    # Archivos a importar
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--m3u', help='Archivo M3U individual a importar')
    group.add_argument('--dir', help='Directorio con archivos M3U a importar')

    # Opciones adicionales
    parser.add_argument('--name', help='Nombre de la playlist (solo para --m3u)')
    parser.add_argument('--skip-missing', action='store_true', help='Ignorar canciones no encontradas sin preguntar')

    args = parser.parse_args()

    # Crear cliente de Airsonic
    print("Conectando a Airsonic...")
    client = AirsonicClient(args.url, args.username, args.password)

    # Verificar conexión
    if not client.ping():
        print("❌ No se pudo conectar a Airsonic", file=sys.stderr)
        sys.exit(1)

    print("✓ Conexión establecida")

    # Obtener lista de archivos M3U
    m3u_files = []
    if args.m3u:
        if not os.path.exists(args.m3u):
            print(f"Error: El archivo {args.m3u} no existe", file=sys.stderr)
            sys.exit(1)
        m3u_files.append(args.m3u)
    elif args.dir:
        if not os.path.isdir(args.dir):
            print(f"Error: El directorio {args.dir} no existe", file=sys.stderr)
            sys.exit(1)
        m3u_files = [
            os.path.join(args.dir, f)
            for f in os.listdir(args.dir)
            if f.lower().endswith('.m3u')
        ]

    if not m3u_files:
        print("No se encontraron archivos M3U para importar", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Playlists a importar: {len(m3u_files)}")
    print(f"{'='*60}")

    # Importar cada playlist
    success_count = 0
    for m3u_file in m3u_files:
        if import_playlist(client, m3u_file, args.name, args.skip_missing):
            success_count += 1

    # Resumen final
    print(f"\n{'='*60}")
    print(f"RESUMEN")
    print(f"{'='*60}")
    print(f"Playlists importadas: {success_count}/{len(m3u_files)}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
