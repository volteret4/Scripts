#!/home/huan/Scripts/python_venv/bin/python

import sys
import os.path
from urllib.parse import unquote
import lyricsgenius
import os
from sops_env import load_sops_env

load_sops_env()

token = os.getenv('GENIUS_TOKEN')
genius = lyricsgenius.Genius(token)

genius.verbose = False
genius.remove_section_headers = False

if len(sys.argv) > 1:
    artist = unquote(sys.argv[1].replace('_', ' '))
else:
    print("No artist passed")
    sys.exit(2)

if len(sys.argv) > 2:
    title = unquote(sys.argv[2].replace('_', ' '))
else:
    print("No song title passed")
    sys.exit(3)

song = genius.search_song(title, artist)

if song:
    print(song.lyrics)
else:
    sys.exit(4)

sys.exit(0)
