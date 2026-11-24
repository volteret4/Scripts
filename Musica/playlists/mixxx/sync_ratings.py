#!/usr/bin/env python3
"""
Script Name: sync_ratings.py
Description: Sincroniza en los dos sentidos las valoraciones (0-5 estrellas) entre Mixxx y Navidrome.
Author: volteret4
Repository: https://github.com/volteret4/
License:
Notes:
    - Las valoraciones no están en los archivos: Mixxx las guarda en su base de datos y Navidrome
      en la suya, por usuario (aquí "mix"). Por eso se sincronizan por la ruta de la canción:
      /mnt/windows/Mix/X en Mixxx y X en la biblioteca "mixxx" de Navidrome.
    - Ninguna de las dos guarda de forma comparable cuándo se valoró, así que se recuerda el último
      valor común en ~/.local/state/mixxx_sync_ratings.json y gana el lado que haya cambiado. Así
      también se propaga quitar una valoración. Si han cambiado los dos, no se toca y se avisa.
    - Mixxx debe estar CERRADO para escribir en su base de datos (mixxx-sync.sh lo lanza al abrir y
      al cerrar) y antes de escribir se guarda una copia, igual que en sync_crates.py.
    - La contraseña se lee por ssh del .env de pepecono, para no tener otra copia aquí.

Uso:
    sync_ratings.py [--dry-run] [--quiet] [--notify]
"""
import argparse
import hashlib
import json
import os
import secrets
import shlex
import sqlite3
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request

from sync_crates import MIX_PATH, MIXXX_DB, backup_db, mixxx_running, notify

ND_URL = "http://192.168.1.133:4533"
ND_SSH_HOST = "pepecono"
ND_ENV_FILE = "/home/pepe/Scripts/Musica/playlists/navidrome/.env"
ND_LIBRARY_ID = 2
STATE_FILE = os.path.expanduser("~/.local/state/mixxx_sync_ratings.json")
PAGE_SIZE = 500


def norm(path):
    """Clave de comparación de rutas: NFC (syncthing normaliza) y sin distinguir mayúsculas (exFAT)."""
    return unicodedata.normalize("NFC", path).casefold()


def decide(mixxx, navidrome, base):
    """Qué hacer con una canción, sabiendo el último valor común (base, None si no hay).

    Devuelve "igual", "a_navidrome", "a_mixxx" o "conflicto".
    """
    if mixxx == navidrome:
        return "igual"
    if base is None:
        if not mixxx:
            return "a_mixxx"
        if not navidrome:
            return "a_navidrome"
        return "conflicto"
    if navidrome == base:
        return "a_navidrome"
    if mixxx == base:
        return "a_mixxx"
    return "conflicto"


class Navidrome:
    def __init__(self):
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ND_SSH_HOST, f"cat {shlex.quote(ND_ENV_FILE)}"],
            capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"no se pudo leer {ND_ENV_FILE} en {ND_SSH_HOST}: {result.stderr.strip()}")
        env = dict(line.strip().split("=", 1) for line in result.stdout.splitlines()
                   if "=" in line and not line.lstrip().startswith("#"))
        self.user = env["ND_USER"].strip('"')
        self.password = env["ND_PASS"].strip('"')
        self.token = self._login()

    def _login(self):
        body = json.dumps({"username": self.user, "password": self.password}).encode()
        request = urllib.request.Request(f"{ND_URL}/auth/login", data=body,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as resp:
            return json.load(resp)["token"]

    def songs(self):
        """{ruta normalizada: (id, valoración)} de la biblioteca de Mix."""
        songs = {}
        start = 0
        while True:
            query = urllib.parse.urlencode({"_start": start, "_end": start + PAGE_SIZE, "_sort": "id",
                                            "library_id": ND_LIBRARY_ID, "missing": "false"})
            request = urllib.request.Request(f"{ND_URL}/api/song?{query}",
                                             headers={"x-nd-authorization": f"Bearer {self.token}"})
            with urllib.request.urlopen(request, timeout=120) as resp:
                page = json.load(resp)
            for song in page:
                # La API no filtra la ruta por biblioteca en todas las versiones: comprobarlo aquí
                if song.get("libraryId", ND_LIBRARY_ID) == ND_LIBRARY_ID:
                    songs[norm(song["path"].removeprefix("/mixxx/"))] = (song["id"], song.get("rating") or 0)
            if len(page) < PAGE_SIZE:
                return songs
            start += PAGE_SIZE

    def set_rating(self, song_id, rating):
        salt = secrets.token_hex(6)
        token = hashlib.md5((self.password + salt).encode()).hexdigest()
        query = urllib.parse.urlencode({"u": self.user, "t": token, "s": salt, "v": "1.16.1", "c": "sync_ratings",
                                        "f": "json", "id": song_id, "rating": rating})
        with urllib.request.urlopen(f"{ND_URL}/rest/setRating?{query}", timeout=30) as resp:
            body = json.load(resp)["subsonic-response"]
        if body["status"] != "ok":
            raise RuntimeError(f"setRating: {body.get('error')}")


def mixxx_tracks(db):
    """{ruta relativa normalizada: (id, valoración, ruta relativa)} de las pistas vivas de Mix."""
    tracks = {}
    for track_id, rating, location in db.execute("""
            SELECT l.id, l.rating, tl.location
            FROM library l JOIN track_locations tl ON l.location = tl.id
            WHERE l.mixxx_deleted = 0"""):
        rel = os.path.relpath(location, MIX_PATH)
        if not rel.startswith(".."):
            tracks[norm(rel)] = (track_id, rating or 0, rel)
    return tracks


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=0, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, STATE_FILE)


def sync(dry_run=False, quiet=False):
    api = Navidrome()
    songs = api.songs()
    db = sqlite3.connect(MIXXX_DB, timeout=10)
    tracks = mixxx_tracks(db)
    # Si una de las dos listas viene vacía es que algo va mal, no que no haya música
    if not songs or not tracks:
        db.close()
        raise RuntimeError(f"biblioteca vacía: {len(tracks)} canciones en Mixxx, {len(songs)} en Navidrome")

    state = load_state()
    new_state = {}
    to_navidrome, to_mixxx, conflicts = [], [], []
    for key in tracks.keys() & songs.keys():
        track_id, mixxx, rel = tracks[key]
        song_id, navidrome = songs[key]
        action = decide(mixxx, navidrome, state.get(key))
        if action == "a_navidrome":
            to_navidrome.append((song_id, mixxx, navidrome, rel))
            new_state[key] = mixxx
        elif action == "a_mixxx":
            to_mixxx.append((track_id, navidrome, mixxx, rel))
            new_state[key] = navidrome
        elif action == "conflicto":
            conflicts.append((mixxx, navidrome, rel))
            if key in state:
                new_state[key] = state[key]
        else:
            new_state[key] = mixxx

    if not quiet:
        for _, new, old, rel in sorted(to_navidrome, key=lambda c: c[3]):
            print(f"  Mixxx -> Navidrome: {old} -> {new}  {rel}")
        for _, new, old, rel in sorted(to_mixxx, key=lambda c: c[3]):
            print(f"  Navidrome -> Mixxx: {old} -> {new}  {rel}")
    for mixxx, navidrome, rel in sorted(conflicts, key=lambda c: c[2]):
        print(f"  CONFLICTO (Mixxx {mixxx}, Navidrome {navidrome}): {rel}")

    if not dry_run:
        for song_id, rating, _, _ in to_navidrome:
            api.set_rating(song_id, rating)
        if to_mixxx:
            print(f"Copia de seguridad: {backup_db()}")
            with db:
                db.executemany("UPDATE library SET rating = ? WHERE id = ?",
                               [(rating, track_id) for track_id, rating, _, _ in to_mixxx])
        save_state(new_state)
    db.close()

    only_one = sum(1 for k in tracks.keys() ^ songs.keys()
                   if (tracks[k][1] if k in tracks else songs[k][1]))
    return {"a_navidrome": len(to_navidrome), "a_mixxx": len(to_mixxx), "conflictos": len(conflicts),
            "comunes": len(tracks.keys() & songs.keys()), "valoradas_solo_en_un_lado": only_one}


def main():
    ap = argparse.ArgumentParser(description="Sincroniza las valoraciones entre Mixxx y Navidrome")
    ap.add_argument("--dry-run", action="store_true", help="mostrar cambios sin escribir nada")
    ap.add_argument("--quiet", action="store_true", help="solo resumen")
    ap.add_argument("--notify", action="store_true", help="avisar con notify-send si hay cambios o conflictos")
    args = ap.parse_args()

    if not os.path.exists(MIXXX_DB):
        sys.exit(f"No existe {MIXXX_DB}")
    if mixxx_running() and not args.dry_run:
        msg = "Mixxx está abierto: las valoraciones se sincronizarán al cerrarlo."
        print(msg, file=sys.stderr)
        sys.exit(2)

    try:
        stats = sync(dry_run=args.dry_run, quiet=args.quiet)
    except (OSError, RuntimeError, KeyError, ValueError, sqlite3.Error) as e:
        msg = f"Error: {e}"
        print(msg, file=sys.stderr)
        if args.notify:
            notify("Valoraciones Mixxx/Navidrome", msg, urgent=True)
        sys.exit(1)

    summary = (f"{stats['a_navidrome']} a Navidrome, {stats['a_mixxx']} a Mixxx, "
               f"{stats['conflictos']} conflictos, {stats['comunes']} canciones comunes")
    if stats["valoradas_solo_en_un_lado"]:
        summary += f"\n{stats['valoradas_solo_en_un_lado']} valoradas cuya canción aún no está en el otro lado"
    print(("[simulación] " if args.dry_run else "") + summary)
    if args.notify and (stats["a_navidrome"] or stats["a_mixxx"] or stats["conflictos"]):
        notify("Valoraciones Mixxx/Navidrome", summary, urgent=bool(stats["conflictos"]))


if __name__ == "__main__":
    main()
