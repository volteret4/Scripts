#!/home/huan/Scripts/python_venv/bin/python
import sys
import re
import json
import time
import requests
from pathlib import Path

if len(sys.argv) < 3:
    sys.exit(1)

artist  = sys.argv[1]
album   = sys.argv[2]
if not album:
    sys.exit(1)

HEADERS = {"User-Agent": "ddb-infobar-ng/1.0"}
MB_BASE = "https://musicbrainz.org/ws/2"
WP      = "https://en.wikipedia.org/w/api.php"


# textos completos (darkone_links.py): Last.fm sin «Read more», Wikipedia entera
try:
    from darkone_links import lastfm_full as full_text, wikipedia_full as wp_full
except Exception:
    def full_text(block):
        return re.sub(r"<[^>]+>", "", (block or {}).get("summary", "")).strip()

    def wp_full(title):
        return title, ""


def wp_album(artist, album):
    """Artículo completo del disco en Wikipedia («Álbum (artista album)», «Álbum (album)», «Álbum»)."""
    for t in (f"{album} ({artist} album)", f"{album} (album)", album):
        try:
            _, text = wp_full(t)
        except Exception:
            text = ""
        # que el artículo sea de este disco: debe nombrar al artista
        if text and artist.lower() in text.lower():
            return text
    return ""


# ── Last.fm ──────────────────────────────────────────────────────────────────

def lastfm_album(artist, album, api_key):
    r = requests.get("http://ws.audioscrobbler.com/2.0/", params={
        "method": "album.getinfo", "artist": artist, "album": album,
        "api_key": api_key, "format": "json", "autocorrect": 1,
    }, timeout=10)
    data = r.json()
    if "error" in data:
        return None
    alb      = data["album"]
    plays    = int(alb.get("playcount", 0))
    listeners= int(alb.get("listeners", 0))
    tags     = [t["name"] for t in alb.get("tags", {}).get("tag", [])[:5]]
    wiki     = full_text(alb.get("wiki"))
    try:
        wp = wp_album(artist, album)
    except Exception:
        wp = ""
    tracks_r = alb.get("tracks", {}).get("track", [])
    if isinstance(tracks_r, dict):
        tracks_r = [tracks_r]

    lines = [
        f"{alb.get('name', album)}  —  {alb.get('artist', artist)}",
        f"Reproducciones: {plays:,}   Oyentes: {listeners:,}",
    ]
    if tags:
        lines.append(f"Géneros: {', '.join(tags)}")
    if wiki:
        lines += ["", wiki]
    if tracks_r:
        lines += ["", "Canciones:"]
        for i, t in enumerate(tracks_r, 1):
            dur  = int(t.get("duration", 0))
            mm, ss = divmod(dur, 60)
            lines.append(f"  {i:>2}. {t['name']}  ({mm}:{ss:02d})")
    # después, el artículo completo de Wikipedia (si aporta: no si es más o menos lo mismo)
    if wp and len(wp) > len(wiki) * 1.3:
        lines += ["", "## Wikipedia", wp]
    return "\n".join(lines)


# ── MusicBrainz ──────────────────────────────────────────────────────────────

def mb_release(artist, album):
    r = requests.get(f"{MB_BASE}/release", params={
        "query": f'release:"{album}" AND artist:"{artist}"',
        "fmt": "json", "limit": 3,
    }, headers=HEADERS, timeout=10)
    releases = r.json().get("releases", [])
    for rel in releases:
        if rel.get("status") == "Official":
            return rel
    return releases[0] if releases else None


def mb_tracks(mbid):
    time.sleep(0.5)
    r = requests.get(f"{MB_BASE}/release/{mbid}", params={
        "inc": "recordings", "fmt": "json",
    }, headers=HEADERS, timeout=10)
    return r.json()


def wp_extract(title):
    r = requests.get(WP, params={
        "action": "query", "titles": title,
        "prop": "extracts", "exintro": True,
        "explaintext": True, "redirects": True, "format": "json",
    }, headers=HEADERS, timeout=10)
    pages = r.json()["query"]["pages"]
    page  = next(iter(pages.values()))
    return page.get("extract", "").strip()


# ── Main ─────────────────────────────────────────────────────────────────────

def base_info():
    # 1. Last.fm
    config_path = Path("~/.lastfm_module/config.json").expanduser()
    if config_path.exists():
        try:
            api_key = json.loads(config_path.read_text())["api_key"]
            result  = lastfm_album(artist, album, api_key)
            if result:
                return result
        except Exception:
            pass

    # 2. Fallback: MusicBrainz + Wikipedia
    lines = [f"{album}  —  {artist}"]
    rel   = mb_release(artist, album)
    if rel:
        year = (rel.get("date") or rel.get("first-release-date") or "")[:4]
        label_info = rel.get("label-info") or []
        label = ""
        if label_info and isinstance(label_info, list) and label_info[0].get("label"):
            label = label_info[0]["label"].get("name", "")
        if year:
            lines.append(f"Año: {year}" + (f"   Sello: {label}" if label else ""))

        detail = mb_tracks(rel["id"])
        tracks = []
        for medium in detail.get("media", []):
            for t in medium.get("tracks", []):
                dur  = (t.get("length") or 0) // 1000
                mm, ss = divmod(dur, 60)
                tracks.append((t.get("position", ""), t["title"], mm, ss))

        extract = wp_album(artist, album)
        if extract:
            lines += ["", extract]
        if tracks:
            lines += ["", "Canciones:"]
            for pos, title, mm, ss in tracks:
                lines.append(f"  {pos:>2}. {title}  ({mm}:{ss:02d})")
    else:
        lines.append("(sin datos)")
    return "\n".join(lines)


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return []


def my_sections():
    """Encarta, Grapa, vvmm, colecciones y Discogs (darkone_links.py)."""
    try:
        import darkone_links as L
    except Exception:
        return []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_discogs = ex.submit(safe, L.discogs_album_lines, artist, album)
        f_vvmm    = ex.submit(safe, L.vvmm_lines, artist, album)
        try:
            enc, album_e = L.encarta_lines("album", artist, album)
            artist_e = L.encarta_entity("artist", artist)
        except Exception:
            enc, album_e, artist_e = [], None, None
        grapa = safe(L.grapa_album_lines, artist_e, album_e)
        mine = enc + f_vvmm.result() + grapa
        discogs = f_discogs.result()
    colecciones = safe(L.colecciones_album_lines, artist, album)
    out = []
    if mine:
        out += ["## Mi colección"] + mine + [""]
    if colecciones:
        out += ["## Colecciones"] + colecciones + [""]
    if discogs:
        out += ["## Discogs"] + discogs + [""]
    return out


from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=2) as ex:
    f_base = ex.submit(base_info)
    mine   = my_sections()
    base   = f_base.result()
print("\n".join(mine + ["## Info", base]))
sys.exit(0)
