#!/usr/bin/env python3
"""
Script Name: renombrar_mix.py
Description: Arregla los nombres mal puestos de las canciones de Mix: «Artista - Título (año álbum) [sello]»,
             con nombre_mix() de mover_mix_playerctl.py (el mismo formato que al copiar).
Author: volteret4
Repository: https://github.com/volteret4/
License:
Notes:
    - Solo toca nombres con pinta de rotos: espacios dobles, «-  ()» o «-» al final, sin artista
      (« - Título») o sin título («Artista -  (...)»), o empezando por número de pista («01 - ...»).
      Los que solo difieren en el año (p. ej. tras fecha_original_mix.py) se dejan.
    - Actualiza la ruta en la base de datos de Mixxx para no perder cues/análisis: con --apply
      Mixxx tiene que estar cerrado (se guarda copia de la base de datos antes).
    - Nunca borra ni pisa archivos: solo renombra, y apunta cada cambio en un registro para --deshacer.
    - Al terminar regenera las playlists .m3u de Mix.

Uso:
    renombrar_mix.py              # simulación: muestra qué renombraría
    renombrar_mix.py --apply      # renombra (con Mixxx cerrado)
    renombrar_mix.py RUTA [RUTA...]
    renombrar_mix.py --deshacer ~/.mixxx/backups_renombrar/renombrados.FECHA.tsv   # volver atrás
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

from mutagen import File

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mover_mix_playerctl import nombre_mix, MusicMover  # noqa: E402

MIX_PATH = "/mnt/windows/Mix"
MIXXX_DB = os.path.expanduser("~/.mixxx/mixxxdb.sqlite")
BACKUP_DIR = os.path.expanduser("~/.mixxx/backups_renombrar")
EXTS = (".flac", ".mp3")

ROTO = re.compile(r"  |^\s*-|-\s*(\(\s*\))?$| - \(|^\d{1,3}[ .-]")


def tag(tags, *keys):
    """Primer valor de cualquiera de las claves, sin distinguir mayúsculas"""
    lower = {k.lower(): v for k, v in tags.items()}
    for key in keys:
        value = lower.get(key)
        if value:
            value = value[0] if isinstance(value, list) else value
            if str(value).strip():
                return str(value).strip()
    return ""


def iter_files(targets):
    for target in targets:
        if os.path.isfile(target):
            yield os.path.abspath(target)
            continue
        for root, _, names in os.walk(target):
            for name in sorted(names):
                if name.lower().endswith(EXTS):
                    yield os.path.join(root, name)


def main():
    ap = argparse.ArgumentParser(description="Arreglar los nombres mal puestos de las canciones de Mix")
    ap.add_argument("paths", nargs="*", help=f"archivos o carpetas (por defecto {MIX_PATH})")
    ap.add_argument("--apply", action="store_true", help="renombrar (sin esto, solo simula)")
    ap.add_argument("--deshacer", metavar="REGISTRO", help="devolver los nombres de un registro de una ejecución anterior")
    args = ap.parse_args()

    if (args.apply or args.deshacer) and subprocess.run(["pgrep", "-x", "mixxx"], capture_output=True).returncode == 0:
        sys.exit("Mixxx está abierto: ciérralo antes de usar --apply (hay que actualizar su base de datos).")

    if args.deshacer:
        with open(args.deshacer) as f:
            pairs = [line.rstrip("\n").split("\t") for line in f if "\t" in line]
        renombrar([(new, old) for old, new in reversed(pairs)], None)
        return

    changes, skipped = [], []
    for path in iter_files(args.paths or [MIX_PATH]):
        stem, ext = os.path.splitext(os.path.basename(path))
        if not ROTO.search(stem):
            continue
        try:
            audio = File(path, easy=True)
        except Exception as e:
            skipped.append(f"{path}: {e}")
            continue
        tags = audio.tags if audio is not None and audio.tags is not None else {}
        name = nombre_mix(tag(tags, "artist", "albumartist", "album artist", "album_artist"),
                          tag(tags, "title"), tag(tags, "album"),
                          tag(tags, "date", "year"), tag(tags, "label", "organization", "publisher"))
        if not name:
            skipped.append(f"sin artista/título en los tags: {path}")
            continue
        new = os.path.join(os.path.dirname(path), name + ext.lower())
        if new == path:
            continue
        if os.path.exists(new):
            skipped.append(f"ya existe {new} (¿duplicado?): {path}")
            continue
        changes.append((path, new))
        print(f"{os.path.relpath(path, MIX_PATH)}\n  → {name + ext.lower()}")

    for line in skipped:
        print(f"⚠️  {line}", file=sys.stderr)

    if not args.apply:
        print(f"\n{len(changes)} archivos a renombrar (simulación; con Mixxx cerrado, --apply los renombra)")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    renombrar(changes, os.path.join(BACKUP_DIR, time.strftime("renombrados.%Y%m%d%H%M%S.tsv")))


def mover_en_mixxx(db, old, new):
    """Cambiar la ruta de la pista en Mixxx. Si Mixxx ya tiene otra entrada con la ruta nueva (un archivo
    que ya no existe, fs_deleted), se intercambian: la buena (con sus cues) pasa a la ruta nueva y la
    fantasma se queda con la vieja, que tampoco existe ya. No se borra ninguna fila."""
    with db:
        ghost = db.execute("SELECT id FROM track_locations WHERE location = ?", (new,)).fetchone()
        if ghost:
            db.execute("UPDATE track_locations SET location = ? WHERE id = ?", (f"{new}.intercambio", ghost[0]))
        db.execute("UPDATE track_locations SET location = ?, filename = ? WHERE location = ?",
                   (new, os.path.basename(new), old))
        if ghost:
            db.execute("UPDATE track_locations SET location = ?, filename = ?, fs_deleted = 1 WHERE id = ?",
                       (old, os.path.basename(old), ghost[0]))


def renombrar(changes, registro):
    """Renombrar (nunca se borra nada ni se pisa un archivo existente) y apuntarlo en la base de datos
    de Mixxx y en el registro (antiguo<TAB>nuevo), que sirve para --deshacer"""
    db = None
    if os.path.exists(MIXXX_DB) and changes:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup = os.path.join(BACKUP_DIR, time.strftime("mixxxdb.%Y%m%d%H%M%S.sqlite"))
        shutil.copy2(MIXXX_DB, backup)
        print(f"Copia de la base de datos de Mixxx en {backup}")
        db = sqlite3.connect(MIXXX_DB, timeout=10)

    log = open(registro, "a") if registro else None
    done = 0
    for old, new in changes:
        if not os.path.exists(old) or os.path.exists(new):
            print(f"⚠️  no se renombra (falta el original o ya existe el destino): {old}", file=sys.stderr)
            continue
        try:
            os.rename(old, new)
        except OSError as e:
            print(f"⚠️  {old}: {e}", file=sys.stderr)
            continue
        done += 1
        if log:
            log.write(f"{old}\t{new}\n")
            log.flush()
        if db:
            try:
                mover_en_mixxx(db, old, new)
            except sqlite3.Error as e:
                print(f"⚠️  Mixxx no actualizado ({e}): {old} -> {new}", file=sys.stderr)
    if db:
        db.close()
    if log:
        log.close()
        print(f"Registro (para volver atrás: renombrar_mix.py --deshacer {registro})")

    _Mover().update_playlists()
    print(f"\n{done} de {len(changes)} archivos renombrados")


class _Mover:
    """Lo justo de MusicMover para regenerar las playlists sin abrir el reproductor ni Airsonic"""
    mixxx_path = MIX_PATH
    get_folder_tree = MusicMover.get_folder_tree
    update_playlists = MusicMover.update_playlists
    _write_playlist = MusicMover._write_playlist
    _write_aggregate = MusicMover._write_aggregate


if __name__ == "__main__":
    main()
