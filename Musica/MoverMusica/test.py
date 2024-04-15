#!/usr/bin/env python
#
# Script Name: test.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Define la variable de entorno
os.environ["SPOTIPY_REDIRECT_URI"] = "http://127.0.0.1:8899"
os.environ["SPOTIPY_CLIENT_ID"] = os.getenv("SPOTIPY_CLIENT_ID")
os.environ["SPOTIPY_CLIENT_SECRET"] = os.getenv("SPOTIPY_CLIENT_SECRET")


scope = 'playlist-modify-public'
username = 'pollolpc'

token = SpotifyOAuth(scope=scope,username=username)
spotifyObject = spotipy.Spotify(auth_manager = token)

filename = sys.argv[1]
playlist_id = sys.argv[2]


#   Agregar canciones a playlist
with open('/home/pi/python_venv/spotify/canciones.txt', 'r') as file:
    for line in file:
        track = spotifyObject.search(q=line.strip(), type='track')
        if len(track['tracks']['items']) > 0:
            track_uris = [track['tracks']['items'][0]['uri']]  # Agrega la URI de la canción a una lista
            spotifyObject.playlist_add_items(playlist_id=playlist_id, items=track_uris)