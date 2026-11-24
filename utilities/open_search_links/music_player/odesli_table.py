#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script Name: odesli_table.py
# Description: Compone un mensaje en markdown (tabla) con los álbumes buscados
#              recientemente con odesli.py: Artista | Álbum | Enlaces.
#              Lee las entradas que odesli.py deja en el historial de CopyQ
#              (formato "*artista* - álbum: url") y, para cada una, vuelve a
#              consultar la API de Odesli con esa misma URL para sacar los
#              enlaces por plataforma (YouTube Music, Spotify, Apple Music...).
#              Si Odesli no devuelve ninguna plataforma para un álbum (p.ej.
#              Bandcamp, que Odesli no soporta en absoluto), esa fila cae al
#              enlace general, igual que hace odesli.py.
# Author: volteret4
# Repository: https://github.com/volteret4/
#
# Dependencies: python3, requests, dotenv, copyq, dunst (notificaciones)
#
# Uso:
#   python3 odesli_table.py               # revisa los últimos 30 elementos de CopyQ
#   python3 odesli_table.py --scan 50     # revisa más historial

import argparse
import os
import re
import subprocess
import sys
import time
from dotenv import load_dotenv
import requests

ENV_PATH = "/home/huan/Scripts/utilities/open_search_links/music_player/.env"
ODESLI_API = "https://api.odesli.co/v1-alpha.1/links"

# Formato exacto que escribe odesli.py en copy_to_clipboard():
#   f"*{artist}* - {album}: {odesli_url}"
ENTRY_PATTERN = re.compile(r'^\*(.+?)\*\s*-\s*(.+?):\s*(https?://\S+)\s*$')

# Orden de preferencia para la columna "Enlaces": las que más se usan primero.
# Bandcamp no aparece nunca aquí porque Odesli no soporta esa plataforma.
PLATFORM_LABELS = [
    ("youtubeMusic", "YT Music"),
    ("youtube", "YouTube"),
    ("spotify", "Spotify"),
    ("appleMusic", "Apple Music"),
    ("deezer", "Deezer"),
    ("tidal", "Tidal"),
    ("soundcloud", "SoundCloud"),
    ("amazonMusic", "Amazon Music"),
]


# ──────────────────────────────────────────────
#  COPYQ
# ──────────────────────────────────────────────

def read_copyq_entries(limit):
    """Devuelve el texto de los `limit` elementos más recientes del
    historial de CopyQ (row 0 = el más reciente)."""
    try:
        count_res = subprocess.run(["copyq", "count"], capture_output=True, text=True, timeout=5)
        total = int(count_res.stdout.strip())
    except (ValueError, subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"No se pudo leer el historial de CopyQ: {e}", file=sys.stderr)
        return []

    n = min(limit, total)
    if n <= 0:
        return []

    # El separador hay que fijarlo en la MISMA invocación que el "read":
    # copyq es un cliente que habla con un servidor en segundo plano, y el
    # separador no persiste entre invocaciones distintas del binario.
    separator = "\x1e"
    rows = [str(i) for i in range(n)]
    res = subprocess.run(
        ["copyq", "separator", separator, "read"] + rows,
        capture_output=True, text=True, timeout=15,
    )
    return res.stdout.split(separator)


def find_recent_odesli_searches(scan_limit):
    """Entre los últimos `scan_limit` elementos de CopyQ, las búsquedas de
    odesli.py (artista, álbum, url), sin duplicados (se queda con la más
    reciente de cada álbum), en el mismo orden en que aparecen en el
    historial (más reciente primero)."""
    entries = read_copyq_entries(scan_limit)
    seen = set()
    matches = []
    for raw in entries:
        text = raw.strip()
        m = ENTRY_PATTERN.match(text)
        if not m:
            continue
        artist, album, url = (g.strip() for g in m.groups())
        key = (artist.lower(), album.lower())
        if key in seen:
            continue
        seen.add(key)
        matches.append((artist, album, url))
    return matches


# ──────────────────────────────────────────────
#  ODESLI
# ──────────────────────────────────────────────

def query_odesli(url, api_key):
    """Vuelve a consultar Odesli con una URL que YA es un pageUrl de Odesli
    (song.link/album.link) -- se acepta como entrada igual que cualquier
    URL de plataforma, y devuelve linksByPlatform con todos los enlaces."""
    try:
        params = {"url": url}
        if api_key:
            params["key"] = api_key
        resp = requests.get(ODESLI_API, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"[Odesli] HTTP {resp.status_code} para {url}", file=sys.stderr)
            return None
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[Odesli] Error consultando {url}: {e}", file=sys.stderr)
        return None


def format_links_cell(data, fallback_url):
    """Enlaces individuales por plataforma si los hay; si no, el enlace
    general (mismo criterio de fallback que usa odesli.py)."""
    links_by_platform = (data or {}).get("linksByPlatform") or {}

    parts = []
    for key, label in PLATFORM_LABELS:
        entry = links_by_platform.get(key)
        if entry and entry.get("url"):
            parts.append(f"[{label}]({entry['url']})")

    if not parts and links_by_platform:
        # Hay plataformas pero ninguna de la lista prioritaria: mostrar
        # algunas igualmente en vez de caer directo al enlace general.
        for key, entry in list(links_by_platform.items())[:4]:
            url = entry.get("url")
            if url:
                parts.append(f"[{key}]({url})")

    if parts:
        return " · ".join(parts)
    return f"[Enlace general]({fallback_url})"


# ──────────────────────────────────────────────
#  MARKDOWN
# ──────────────────────────────────────────────

def escape_md_cell(text):
    """Evita que el texto rompa la tabla (saltos de línea, barras verticales)."""
    return text.replace("\n", " ").strip().replace("|", "\\|")


def build_message(rows):
    lines = [
        f"### 🔗 Enlaces buscados ({len(rows)})",
        "",
        "| Artista | Álbum | Enlaces |",
        "|---|---|---|",
    ]
    for artist, album, cell in rows:
        lines.append(f"| {escape_md_cell(artist)} | {escape_md_cell(album)} | {cell} |")
    return "\n".join(lines)


# ──────────────────────────────────────────────
#  PORTAPAPELES Y NOTIFICACIONES
# ──────────────────────────────────────────────

def copy_to_clipboard(text):
    try:
        subprocess.run(["copyq", "add", text], check=True)
        return True
    except Exception as e:
        print(f"Error copiando al portapapeles: {e}", file=sys.stderr)
        return False


def notify(title, message, urgent=False):
    try:
        cmd = ["dunstify", "-t", "5000"]
        if urgent:
            cmd.extend(["-u", "critical"])
        cmd.extend([title, message])
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        subprocess.run(cmd, env=env)
    except Exception:
        pass


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compone una tabla markdown (Artista | Álbum | Enlaces) con las "
                     "últimas búsquedas de odesli.py guardadas en el historial de CopyQ."
    )
    parser.add_argument(
        "--scan", type=int, default=30,
        help="Cuántos elementos recientes del historial de CopyQ revisar (por defecto: 30)",
    )
    args = parser.parse_args()

    load_dotenv(dotenv_path=ENV_PATH)
    api_key = os.getenv("ODESLI_API_KEY")

    matches = find_recent_odesli_searches(args.scan)
    if not matches:
        msg = f"No se encontraron búsquedas de odesli.py en los últimos {args.scan} elementos de CopyQ"
        print(msg, file=sys.stderr)
        notify("Tabla de enlaces", msg, urgent=True)
        sys.exit(1)

    print(f"Encontrados {len(matches)} álbum(es) en el historial de CopyQ")

    rows = []
    for i, (artist, album, url) in enumerate(matches):
        print(f"[{i + 1}/{len(matches)}] Consultando Odesli: {artist} - {album}")
        data = query_odesli(url, api_key)
        cell = format_links_cell(data, url)
        rows.append((artist, album, cell))
        if i < len(matches) - 1:
            time.sleep(1)  # cortesía con la API, igual que odesli.py con MusicBrainz

    message = build_message(rows)
    print("\n" + message + "\n")

    copy_to_clipboard(message)
    notify("🔗 Tabla de enlaces", f"{len(rows)} álbum(es) · copiada al portapapeles")


if __name__ == "__main__":
    main()
