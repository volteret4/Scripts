#!/home/huan/Scripts/python_venv/bin/python
import sys
import requests
from urllib.parse import quote

if len(sys.argv) < 3:
    sys.exit(1)

artist = sys.argv[1]
title  = sys.argv[2]

try:
    r = requests.get(
        f"https://api.lyrics.ovh/v1/{quote(artist)}/{quote(title)}",
        timeout=10,
    )
    if r.ok:
        data = r.json()
        lyrics = data.get("lyrics", "").strip()
        if lyrics:
            print(lyrics)
            sys.exit(0)
except Exception:
    pass

sys.exit(1)
