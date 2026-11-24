#!/usr/bin/env python3
"""
Script Name: sync_crates.py
Description: Sincroniza los cajones (crates) de Mixxx con las playlists .m3u de la carpeta Mix:
             un cajón por cada .m3u, con exactamente las mismas canciones.
Author: volteret4
Repository: https://github.com/volteret4/
License:
Notes:
    - Escribe directamente en ~/.mixxx/mixxxdb.sqlite, así que Mixxx debe estar CERRADO
      (si está abierto no hace nada, salvo con --force).
    - Antes de escribir guarda una copia de la base de datos (se conservan las 5 últimas).
    - Canciones movidas de carpeta: si Mixxx tiene la pista registrada en una ruta que ya no
      existe y hay un fichero con el mismo nombre y tamaño en la ruta nueva, actualiza la ruta
      (igual que hace Mixxx al reescanear) para conservar cues, BPM, etc.
    - Canciones que Mixxx aún no conoce: se quedan fuera del cajón hasta que Mixxx las escanee
      (RescanOnStartup) y se vuelva a ejecutar este script (mixxx-sync.sh lo hace al cerrar Mixxx).
    - Solo toca los cajones que llevan el nombre de un .m3u (o que creó este script);
      los demás cajones y las playlists de Mixxx no se tocan.

Uso:
    sync_crates.py [--dry-run] [--force] [--quiet]
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time

MIX_PATH = "/mnt/windows/Mix"
MIXXX_DB = os.path.expanduser("~/.mixxx/mixxxdb.sqlite")
BACKUP_DIR = os.path.expanduser("~/.mixxx/backups_sync_crates")
STATE_FILE = os.path.expanduser("~/.local/state/mixxx_sync_crates.json")
KEEP_BACKUPS = 5
CRATE_NAME_MAX = 48  # varchar(48) en la tabla crates


def notify(title, msg, urgent=False):
    try:
        subprocess.run(["notify-send", "-u", "critical" if urgent else "normal", title, msg],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass


def mixxx_running():
    return subprocess.run(["pgrep", "-x", "mixxx"], stdout=subprocess.DEVNULL).returncode == 0


def read_m3u(path):
    """Rutas absolutas de un .m3u (las relativas se resuelven respecto a la carpeta del .m3u)."""
    base = os.path.dirname(path)
    tracks = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tracks.append(os.path.normpath(line if os.path.isabs(line) else os.path.join(base, line)))
    return tracks


def backup_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dest = os.path.join(BACKUP_DIR, f"mixxxdb.{time.strftime('%Y%m%d%H%M%S')}.sqlite")
    src = sqlite3.connect(MIXXX_DB)
    dst = sqlite3.connect(dest)
    src.backup(dst)
    dst.close()
    src.close()
    for old in sorted(glob.glob(os.path.join(BACKUP_DIR, "mixxxdb.*.sqlite")))[:-KEEP_BACKUPS]:
        os.remove(old)
    return dest


def load_state():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f).get("crates", []))
    except (OSError, ValueError):
        return set()


def save_state(names):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"crates": sorted(names)}, f, indent=1)


class Library:
    def __init__(self, db):
        self.db = db
        # ruta -> track_id (pistas vivas: no borradas en Mixxx)
        self.by_path = {}
        self.by_path_ci = {}  # exFAT no distingue mayúsculas
        # pistas cuya ruta ya no existe en disco: (nombre, tamaño) -> [(track_id, loc_id)]
        self.missing = {}
        rows = db.execute("""
            SELECT l.id, tl.id, tl.location, tl.filename, tl.filesize
            FROM library l JOIN track_locations tl ON l.location = tl.id
            WHERE l.mixxx_deleted = 0""").fetchall()
        for track_id, loc_id, location, filename, filesize in rows:
            if os.path.exists(location):
                self.by_path[location] = track_id
                self.by_path_ci[location.casefold()] = track_id
            else:
                self.missing.setdefault((filename, filesize), []).append((track_id, loc_id))
        self.taken_locations = {r[0] for r in db.execute("SELECT location FROM track_locations")}

    def find(self, path):
        return self.by_path.get(path) or self.by_path_ci.get(path.casefold())

    def relocate(self, path, dry_run):
        """Busca una pista cuya ruta antigua ya no existe con el mismo nombre y tamaño."""
        try:
            size = os.path.getsize(path)
        except OSError:
            return None
        candidates = self.missing.get((os.path.basename(path), size), [])
        if len(candidates) != 1 or path in self.taken_locations:
            return None
        track_id, loc_id = candidates.pop()
        if not dry_run:
            self.db.execute("""
                UPDATE track_locations
                SET location = ?, filename = ?, directory = ?, filesize = ?,
                    fs_deleted = 0, needs_verification = 0
                WHERE id = ?""", (path, os.path.basename(path), os.path.dirname(path), size, loc_id))
        self.by_path[path] = track_id
        self.by_path_ci[path.casefold()] = track_id
        self.taken_locations.add(path)
        return track_id


def sync(dry_run=False, quiet=False):
    playlists = {}
    for m3u in sorted(glob.glob(os.path.join(MIX_PATH, "*.m3u"))):
        name = os.path.splitext(os.path.basename(m3u))[0][:CRATE_NAME_MAX]
        playlists[name] = read_m3u(m3u)

    db = sqlite3.connect(MIXXX_DB, timeout=10)
    lib = Library(db)
    crates = {name: cid for cid, name in db.execute("SELECT id, name FROM crates")}
    managed_before = load_state()

    stats = {"creados": 0, "borrados": 0, "añadidas": 0, "quitadas": 0, "reubicadas": 0}
    pending = []  # canciones del .m3u que Mixxx aún no tiene

    with db:  # una única transacción: o se aplica todo o nada
        for name, paths in playlists.items():
            wanted = set()
            for path in paths:
                track_id = lib.find(path)
                if track_id is None:
                    track_id = lib.relocate(path, dry_run)
                    if track_id is not None:
                        stats["reubicadas"] += 1
                if track_id is None:
                    pending.append(path)
                else:
                    wanted.add(track_id)

            crate_id = crates.get(name)
            if crate_id is None:
                stats["creados"] += 1
                if dry_run:
                    current = set()
                else:
                    crate_id = db.execute("INSERT INTO crates (name) VALUES (?)", (name,)).lastrowid
                    crates[name] = crate_id
                    current = set()
            else:
                current = {r[0] for r in db.execute(
                    "SELECT track_id FROM crate_tracks WHERE crate_id = ?", (crate_id,))}

            add, remove = wanted - current, current - wanted
            stats["añadidas"] += len(add)
            stats["quitadas"] += len(remove)
            if not dry_run:
                db.executemany("INSERT INTO crate_tracks (crate_id, track_id) VALUES (?, ?)",
                               [(crate_id, t) for t in add])
                db.executemany("DELETE FROM crate_tracks WHERE crate_id = ? AND track_id = ?",
                               [(crate_id, t) for t in remove])
                db.execute("UPDATE crates SET count = ? WHERE id = ?", (len(wanted), crate_id))
            if not quiet and (add or remove):
                print(f"  {name}: +{len(add)} -{len(remove)} (total {len(wanted)})")

        # Cajones creados por este script cuyo .m3u ya no existe
        for name in managed_before - set(playlists):
            crate_id = crates.get(name)
            if crate_id is None:
                continue
            stats["borrados"] += 1
            if not quiet:
                print(f"  {name}: cajón eliminado (ya no hay .m3u)")
            if not dry_run:
                db.execute("DELETE FROM crate_tracks WHERE crate_id = ?", (crate_id,))
                db.execute("DELETE FROM crates WHERE id = ?", (crate_id,))

        if dry_run:
            db.rollback()

    db.close()
    if not dry_run:
        save_state(set(playlists))
    return stats, pending


def main():
    ap = argparse.ArgumentParser(description="Sincroniza cajones de Mixxx con los .m3u de " + MIX_PATH)
    ap.add_argument("--dry-run", action="store_true", help="mostrar cambios sin escribir nada")
    ap.add_argument("--force", action="store_true", help="escribir aunque Mixxx esté abierto (no recomendado)")
    ap.add_argument("--quiet", action="store_true", help="solo resumen")
    ap.add_argument("--notify", action="store_true", help="mostrar el resumen con notify-send")
    args = ap.parse_args()

    if not os.path.exists(MIXXX_DB):
        sys.exit(f"No existe {MIXXX_DB}")
    if mixxx_running() and not args.force and not args.dry_run:
        msg = "Mixxx está abierto: los cajones se sincronizarán al cerrarlo (mixxx-sync.sh) o ejecutando sync_crates.py."
        print(msg, file=sys.stderr)
        if args.notify:
            notify("Cajones Mixxx", msg)
        sys.exit(2)

    if not args.dry_run:
        print(f"Copia de seguridad: {backup_db()}")
    stats, pending = sync(dry_run=args.dry_run, quiet=args.quiet)

    summary = (f"{stats['creados']} cajones creados, {stats['borrados']} eliminados, "
               f"+{stats['añadidas']} / -{stats['quitadas']} canciones, {stats['reubicadas']} reubicadas")
    if pending:
        summary += f"\n{len(pending)} canciones aún no están en la biblioteca de Mixxx (entrarán tras su próximo escaneo)"
    print(("[simulación] " if args.dry_run else "") + summary)
    if pending and not args.quiet:
        for p in pending[:20]:
            print("    pendiente:", os.path.relpath(p, MIX_PATH))
        if len(pending) > 20:
            print(f"    … y {len(pending) - 20} más")
    if args.notify:
        notify("Cajones Mixxx", summary)


if __name__ == "__main__":
    main()
