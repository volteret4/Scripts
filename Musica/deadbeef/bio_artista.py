#!/home/huan/Scripts/python_venv/bin/python
import sys
import re
import json
import requests
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit(1)

artist  = sys.argv[1]
HEADERS = {"User-Agent": "ddb-infobar-ng/1.0"}
WP      = "https://en.wikipedia.org/w/api.php"


# textos completos (darkone_links.py): Last.fm sin «Read more», Wikipedia entera
try:
    from darkone_links import lastfm_full as full_text, wikipedia_full as wp_full
except Exception:
    def full_text(block):
        return re.sub(r"<[^>]+>", "", (block or {}).get("summary", "")).strip()

    def wp_full(title):
        return wp_extract(title)

# ── Last.fm ──────────────────────────────────────────────────────────────────

def lastfm_bio(artist, api_key):
    r = requests.get("http://ws.audioscrobbler.com/2.0/", params={
        "method": "artist.getinfo", "artist": artist,
        "api_key": api_key, "format": "json", "autocorrect": 1,
    }, timeout=10)
    data = r.json()
    if "error" in data:
        return None
    a         = data["artist"]
    listeners = int(a.get("stats", {}).get("listeners", 0))
    plays     = int(a.get("stats", {}).get("playcount", 0))
    tags      = [t["name"] for t in a.get("tags", {}).get("tag", [])[:5]]
    bio       = full_text(a.get("bio"))
    lines = [
        a.get("name", artist),
        f"Oyentes: {listeners:,}   Reproducciones: {plays:,}",
    ]
    if tags:
        lines.append(f"Géneros: {', '.join(tags)}")
    if bio:
        lines += ["", bio]
    # después, el artículo completo de Wikipedia (si aporta: no si es más o menos lo mismo)
    try:
        wp = wikipedia_bio(artist)
    except Exception:
        wp = ""
    if wp and len(wp) > len(bio) * 1.3:
        lines += ["", "## Wikipedia", wp]
    return "\n".join(lines)


# ── MusicBrainz ──────────────────────────────────────────────────────────────

def mb_artist(name):
    r = requests.get("https://musicbrainz.org/ws/2/artist", params={
        "query": f'artist:"{name}"', "fmt": "json", "limit": 1,
    }, headers=HEADERS, timeout=10)
    results = r.json().get("artists", [])
    if not results:
        return None
    a    = results[0]
    tags = [t["name"] for t in a.get("tags", [])[:5]]
    return {
        "name":           a.get("name", name),
        "type":           a.get("type", ""),
        "country":        a.get("country", ""),
        "area":           a.get("area", {}).get("name", ""),
        "begin":          a.get("life-span", {}).get("begin", ""),
        "tags":           tags,
        "disambiguation": a.get("disambiguation", ""),
    }


# ── Wikipedia ────────────────────────────────────────────────────────────────

def wp_extract(title):
    r = requests.get(WP, params={
        "action": "query", "titles": title,
        "prop": "extracts", "exintro": True,
        "explaintext": True, "redirects": True,
        "format": "json",
    }, headers=HEADERS, timeout=10)
    pages = r.json()["query"]["pages"]
    page  = next(iter(pages.values()))
    return page.get("title"), page.get("extract", "").strip()


MUSIC_WORDS = ("band", "musician", "singer", "rapper", "producer", " dj", "composer", "album", "record label",
               "duo", "group", "songwriter", "guitarist", "electronic music")


def is_music(text):
    head = text[:1500].lower()
    return any(w in head for w in MUSIC_WORDS)


def wikipedia_bio(artist):
    """Artículo completo de Wikipedia del artista (comprobando que sea de música)."""
    title, extract = wp_full(artist)
    if extract and not is_music(extract):
        extract = ""
    if not extract:
        r2 = requests.get(WP, params={
            "action": "query", "list": "search",
            "srsearch": f"{artist} band musician", "srlimit": 1,
            "format": "json",
        }, headers=HEADERS, timeout=10)
        results = r2.json()["query"]["search"]
        if results:
            title, extract = wp_full(results[0]["title"])
            if extract and (not is_music(extract) or artist.lower() not in extract[:2000].lower()):
                extract = ""
    return extract


# ── Main ─────────────────────────────────────────────────────────────────────

def base_bio():
    # 1. Last.fm
    config_path = Path("~/.lastfm_module/config.json").expanduser()
    if config_path.exists():
        try:
            api_key = json.loads(config_path.read_text())["api_key"]
            result  = lastfm_bio(artist, api_key)
            if result:
                return result
        except Exception:
            pass

    # 2. Fallback: MusicBrainz metadata + Wikipedia bio
    lines = []
    mb = mb_artist(artist)
    if mb:
        name_line = mb["name"]
        if mb["disambiguation"]:
            name_line += f"  ({mb['disambiguation']})"
        lines.append(name_line)
        meta = [x for x in [mb["type"], mb["area"] or mb["country"]] if x]
        if mb["begin"]:
            meta.append(f"desde {mb['begin'][:4]}")
        if meta:
            lines.append("  ".join(meta))
        if mb["tags"]:
            lines.append(f"Géneros: {', '.join(mb['tags'])}")
        lines.append("")

    extract = wikipedia_bio(artist)
    if extract:
        lines.append(extract)
    if not lines:
        return f"No se encontró información sobre '{artist}'."
    return "\n".join(lines)


def my_sections():
    """Mix, Encarta, Grapa y vvmm (darkone_links.py)."""
    try:
        import darkone_links as L
    except Exception:
        return []
    out = []
    for fn in (lambda: L.mix_artist_lines(artist),
               lambda: L.encarta_lines("artist", artist)[0],
               lambda: L.grapa_artist_lines(L.encarta_entity("artist", artist)),
               lambda: L.vvmm_lines(artist)):
        try:
            out += fn()
        except Exception:
            pass
    return (["## Mi colección"] + out + [""]) if out else []


from concurrent.futures import ThreadPoolExecutor
def photos():
    try:
        import darkone_links as L
        return L.photo_line(artist)
    except Exception:
        return []


with ThreadPoolExecutor(max_workers=2) as ex:
    f_base  = ex.submit(base_bio)
    f_photo = ex.submit(photos)
    mine    = my_sections()
    base    = f_base.result()
    fotos   = f_photo.result()
print("\n".join(fotos + mine + ["## Biografía", base]))
sys.exit(0)
