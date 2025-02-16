import json
import os
import time
import pylast
import socket
import re
from lastfm_credentials import API_KEY, API_SECRET, USERNAME, PASSWORD_HASH

MPV_SOCKET = "/home/huan/.config/mpv/socket"

network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET, username=USERNAME, password_hash=PASSWORD_HASH)

def mpv_command(command):
    """Envía un comando a mpv a través del socket IPC."""
    if not os.path.exists(MPV_SOCKET):
        return None
    
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(MPV_SOCKET)
            sock.sendall(json.dumps({"command": command}).encode() + b"\n")
            response = sock.recv(4096).decode()
            return json.loads(response)
    except Exception as e:
        print(f"⚠ Error al conectar con mpv: {e}")
        return None

def get_metadata():
    """Obtiene la metadata del archivo que se está reproduciendo."""
    result = mpv_command(["get_property", "media-title"])
    title = result.get("data") if result else None

    duration_result = mpv_command(["get_property", "duration"])
    duration = int(duration_result.get("data", 0)) if duration_result else 0

    return title, duration

def parse_artist_title(title):
    """Intenta extraer el artista y la canción del título."""
    if not title:
        return None, None
    
    # Expresión regular para detectar formato "Artista - Canción"
    match = re.match(r"(.+?)\s*[-–]\s*(.+)", title)
    if match:
        artist, song = match.groups()
        return artist.strip(), song.strip()

    # Si no se encuentra un formato claro, no devuelve artista
    return None, title.strip()

def scrobble():
    """Envía el scrobble a Last.fm después de cierto tiempo."""
    last_scrobbled = None
    while True:
        title, duration = get_metadata()
        if title and duration > 30:  # Solo scrobblea si dura más de 30s
            artist, song = parse_artist_title(title)
            if artist and song and last_scrobbled != title:
                try:
                    #rint(f"Scrobbleando: {artist} - {song} ({duration}s)")
                    print(f"Artista: {artist}")
                    print(f"Canción: {song}")
                    network.scrobble(artist, song, int(time.time()))
                    last_scrobbled = title
                    time.sleep(120)  # Espera 2 minutos entre scrobbles
                except Exception as e:
                    print(f"❌ Error al enviar scrobble: {e}")
            else:
                print(f"🚫 No se scrobblea: {title} (artista desconocido)")
        time.sleep(60)  # Verifica cada 60s

if __name__ == "__main__":
    scrobble()
