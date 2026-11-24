#!/usr/bin/env python3
"""
Script Name: mixxx_to_airsonic.py
Description: Copia las playlists de Mixxx (las que tienen nombre, no el historial de sesiones)
             a airsonic, como playlists del usuario "mix" sobre la carpeta de medios "Mixxx".
Author: volteret4
Repository: https://github.com/volteret4/
License:
Notes:
    - Lee ~/.mixxx/mixxxdb.sqlite en solo lectura (Mixxx puede estar abierto).
    - Las canciones se buscan en airsonic por su ruta: /mnt/windows/Mix/X  ->  /Mixxx/X
      (la carpeta Mix se clona con syncthing en pepecono). Las que airsonic aún no ha
      escaneado se quedan fuera; usa --scan para lanzar antes un escaneo.
    - Cada playlist de airsonic queda marcada en su comentario ("Mixxx: <nombre>"), así se
      actualiza la misma en cada ejecución (se reemplazan sus canciones, en el orden de Mixxx).
    - Con --prune borra las playlists marcadas cuya lista ya no existe en Mixxx.
    - Credenciales en ../airsonic/.env: AIRSONIC_URL, AIRSONIC_MIX_PASSWORD y, opcional,
      AIRSONIC_MIX_USER (por defecto "mix"). Ese usuario necesita acceso a la carpeta "Mixxx".

Uso:
    mixxx_to_airsonic.py [--dry-run] [--scan] [--prune] [--quiet]
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

MIX_PATH = "/mnt/windows/Mix"
MIXXX_DB = os.path.expanduser("~/.mixxx/mixxxdb.sqlite")
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "airsonic", ".env")
AIRSONIC_FOLDER = "Mixxx"
COMMENT_PREFIX = "Mixxx: "
API_VERSION = "1.15.0"  # airsonic-advanced rechaza versiones mayores


def load_env(path):
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip("'\"")
    return env


def norm(path):
    """Clave de comparación de rutas: NFC (syncthing normaliza) y sin distinguir mayúsculas (exFAT)."""
    return unicodedata.normalize("NFC", path).casefold()


class Airsonic:
    def __init__(self, url, user, password):
        self.base = url.rstrip("/") + "/rest/"
        # airsonic-advanced no acepta token+salt, solo la contraseña codificada en hex
        self.auth = {"u": user, "p": "enc:" + password.encode().hex(),
                     "v": API_VERSION, "c": "mixxx_to_airsonic", "f": "json"}

    def call(self, method, **params):
        data = list(self.auth.items())
        for key, value in params.items():
            for v in value if isinstance(value, (list, tuple)) else [value]:
                data.append((key, v))
        # GET: airsonic rechaza los POST a /rest por la protección CSRF
        url = self.base + method + "?" + urllib.parse.urlencode(data)
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = json.load(resp)["subsonic-response"]
        if body["status"] != "ok":
            raise RuntimeError(f"{method}: {body['error']['message']}")
        return body

    def folder_id(self, name):
        for folder in self.call("getMusicFolders")["musicFolders"].get("musicFolder", []):
            if folder["name"] == name:
                return folder["id"]
        return None

    def songs_by_path(self, folder_id):
        """Recorre la carpeta de medios y devuelve {ruta relativa normalizada: id de canción}."""
        songs = {}
        indexes = self.call("getIndexes", musicFolderId=folder_id)["indexes"]
        pending = [a["id"] for idx in indexes.get("index", []) for a in idx.get("artist", [])]
        children = list(indexes.get("child", []))
        while pending or children:
            if not children:
                children = self.call("getMusicDirectory", id=pending.pop())["directory"].get("child", [])
                continue  # la carpeta puede estar vacía
            child = children.pop()
            if child.get("isDir"):
                pending.append(child["id"])
            elif child.get("path"):
                path = child["path"].lstrip("/")
                if path.startswith(AIRSONIC_FOLDER + "/"):
                    path = path[len(AIRSONIC_FOLDER) + 1:]
                songs[norm(path)] = child["id"]
        return songs

    def scan(self, quiet):
        self.call("startScan")
        while self.call("getScanStatus")["scanStatus"].get("scanning"):
            if not quiet:
                print("  escaneando…", end="\r", flush=True)
            time.sleep(5)


def mixxx_playlists():
    """{nombre: [rutas]} de las playlists normales de Mixxx (hidden=0: ni Auto DJ ni historial)."""
    db = sqlite3.connect(f"file:{MIXXX_DB}?mode=ro", uri=True, timeout=10)
    playlists = {}
    for pid, name in db.execute("SELECT id, name FROM Playlists WHERE hidden = 0 ORDER BY position"):
        playlists[name] = [r[0] for r in db.execute("""
            SELECT tl.location
            FROM PlaylistTracks pt
            JOIN library l ON l.id = pt.track_id
            JOIN track_locations tl ON tl.id = l.location
            WHERE pt.playlist_id = ?
            ORDER BY pt.position""", (pid,))]
    db.close()
    return playlists


def sync(api, dry_run=False, prune=False, quiet=False):
    folder_id = api.folder_id(AIRSONIC_FOLDER)
    if folder_id is None:
        sys.exit(f'El usuario de airsonic no tiene acceso a la carpeta "{AIRSONIC_FOLDER}" '
                 f"(Ajustes > Usuarios > Carpetas de medios).")
    songs = api.songs_by_path(folder_id)
    if not quiet:
        print(f"{len(songs)} canciones en la carpeta {AIRSONIC_FOLDER} de airsonic")

    existing = {}  # nombre en Mixxx -> id de la playlist de airsonic
    for p in api.call("getPlaylists")["playlists"].get("playlist", []):
        comment = p.get("comment", "")
        if comment.startswith(COMMENT_PREFIX):
            existing[comment[len(COMMENT_PREFIX):]] = p["id"]

    stats = {"creadas": 0, "actualizadas": 0, "borradas": 0, "canciones": 0}
    missing = []  # (playlist, ruta) que airsonic no tiene
    playlists = mixxx_playlists()

    for name, paths in playlists.items():
        ids = []
        for path in paths:
            rel = os.path.relpath(path, MIX_PATH)
            song_id = None if rel.startswith("..") else songs.get(norm(rel))
            if song_id is None:
                missing.append((name, path))
            else:
                ids.append(song_id)
        stats["canciones"] += len(ids)

        playlist_id = existing.get(name)
        stats["actualizadas" if playlist_id else "creadas"] += 1
        if not quiet:
            print(f"  {name}: {len(ids)}/{len(paths)} canciones" + ("" if playlist_id else " (nueva)"))
        if dry_run:
            continue
        if playlist_id:
            api.call("createPlaylist", playlistId=playlist_id, songId=ids)
        else:
            api.call("createPlaylist", name=name, songId=ids)
            # airsonic-advanced no devuelve la playlist creada: la más reciente con ese nombre
            playlist_id = max((p for p in api.call("getPlaylists")["playlists"].get("playlist", [])
                               if p["name"] == name and p["owner"] == api.auth["u"]),
                              key=lambda p: int(p["id"]))["id"]
        api.call("updatePlaylist", playlistId=playlist_id, comment=COMMENT_PREFIX + name)

    if prune:
        for name in existing.keys() - playlists.keys():
            stats["borradas"] += 1
            if not quiet:
                print(f"  {name}: borrada (ya no existe en Mixxx)")
            if not dry_run:
                api.call("deletePlaylist", id=existing[name])

    return stats, missing


def main():
    ap = argparse.ArgumentParser(description="Copia las playlists de Mixxx a airsonic (carpeta Mixxx)")
    ap.add_argument("--dry-run", action="store_true", help="mostrar cambios sin escribir nada")
    ap.add_argument("--scan", action="store_true", help="escanear la biblioteca de airsonic antes")
    ap.add_argument("--prune", action="store_true", help="borrar las playlists que ya no están en Mixxx")
    ap.add_argument("--quiet", action="store_true", help="solo resumen")
    args = ap.parse_args()

    if not os.path.exists(MIXXX_DB):
        sys.exit(f"No existe {MIXXX_DB}")
    env = load_env(ENV_FILE)
    if "AIRSONIC_MIX_PASSWORD" not in env:
        sys.exit(f"Falta AIRSONIC_MIX_PASSWORD en {os.path.normpath(ENV_FILE)}")
    api = Airsonic(env["AIRSONIC_URL"], env.get("AIRSONIC_MIX_USER", "mix"), env["AIRSONIC_MIX_PASSWORD"])

    if args.scan and not args.dry_run:
        api.scan(args.quiet)
    stats, missing = sync(api, dry_run=args.dry_run, prune=args.prune, quiet=args.quiet)

    summary = (f"{stats['creadas']} playlists creadas, {stats['actualizadas']} actualizadas, "
               f"{stats['borradas']} borradas, {stats['canciones']} canciones")
    if missing:
        summary += f"\n{len(missing)} canciones no están en airsonic (¿sin sincronizar o sin escanear? prueba --scan)"
    print(("[simulación] " if args.dry_run else "") + summary)
    if missing and not args.quiet:
        for name, path in missing[:20]:
            print(f"    falta [{name}]:", os.path.relpath(path, MIX_PATH))
        if len(missing) > 20:
            print(f"    … y {len(missing) - 20} más")


if __name__ == "__main__":
    main()
