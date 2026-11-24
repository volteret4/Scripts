#!/home/huan/Scripts/python_venv/bin/python
"""Similar tracks via Last.fm. Falls back to related artists from MusicBrainz."""
import sys
import json
import requests
from pathlib import Path

if len(sys.argv) < 3:
    sys.exit(1)

artist = sys.argv[1]
title  = sys.argv[2]
HEADERS = {"User-Agent": "ddb-infobar-ng/1.0"}


def lastfm_similar(artist, title, api_key):
    r = requests.get("http://ws.audioscrobbler.com/2.0/", params={
        "method":      "track.getsimilar",
        "artist":      artist,
        "track":       title,
        "api_key":     api_key,
        "format":      "json",
        "autocorrect": 1,
        "limit":       20,
    }, timeout=10)
    data = r.json()
    if "error" in data:
        return None, data["message"]
    tracks = data.get("similartracks", {}).get("track", [])
    return tracks, None


def mb_related_artists(artist):
    r = requests.get("https://musicbrainz.org/ws/2/artist", params={
        "query": f'artist:"{artist}"', "fmt": "json", "limit": 1,
    }, headers=HEADERS, timeout=10)
    results = r.json().get("artists", [])
    if not results:
        return []
    mbid = results[0]["id"]

    r2 = requests.get(f"https://musicbrainz.org/ws/2/artist/{mbid}", params={
        "inc": "artist-rels", "fmt": "json",
    }, headers=HEADERS, timeout=10)
    relations = r2.json().get("relations", [])

    related = []
    for rel in relations:
        if rel.get("target-type") != "artist":
            continue
        rtype = rel.get("type", "")
        if rtype in ("member of band", "collaboration", "is person",
                     "instrumental supporting musician"):
            continue
        name = rel["artist"]["name"]
        related.append((rtype, name))
    return related


def lastfm_lines():
    config_path = Path("~/.lastfm_module/config.json").expanduser()
    if not config_path.exists():
        return []
    try:
        api_key = json.loads(config_path.read_text())["api_key"]
        tracks, err = lastfm_similar(artist, title, api_key)
    except Exception:
        return []
    out = []
    for t in tracks or []:
        match = int(float(t.get("match", 0)) * 100)
        out.append(f"  {t['artist']['name']}  —  {t['name']}  ({match}%)")
    return out


def mb_lines():
    try:
        return [f"  {name}  [{rtype}]" for rtype, name in mb_related_artists(artist)[:20]]
    except Exception:
        return []


def audiomuse_lines():
    try:
        import darkone_links as L
        return L.audiomuse_sections(artist, title)
    except Exception as e:
        return [f"(AudioMuse no disponible: {type(e).__name__})"]


from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=2) as ex:
    f_am = ex.submit(audiomuse_lines)
    f_lf = ex.submit(lastfm_lines)
    am, lf = f_am.result(), f_lf.result()

out = []
if am:
    out += am
if lf:
    out += ["## Last.fm"] + lf
else:
    mb = mb_lines()
    if mb:
        out += [f"## Artistas relacionados con {artist} (MusicBrainz)"] + mb
if not out:
    out = [f"No se encontraron similares para '{title}' de {artist}."]
print("\n".join(out))
sys.exit(0)
