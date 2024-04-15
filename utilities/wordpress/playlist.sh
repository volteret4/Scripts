#!/usr/bin/env bash
#
# Script Name: playlist.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#




# Prompt the user to enter an artist and a song using Zenity
input=$(zenity --entry --text "Enter artist_song:")

# Split the input by the "_" character to get the artist and song
IFS="_" read -r artist song <<< "$input"

# Search for the YouTube URL for the given artist and song
yt_url=$(youtube-dl -v --get-id "ytsearch:$artist $song")

# Search for the Spotify URL for the given artist and song
spot_url=$(spotdl --search-query "$artist_ $song")

# Append the new artist, song, and URLs to the existing JSON file
jq --arg artist "$artist" --arg song "$song" --arg yt_url "$yt_url" --arg spot_url "$spot_url" '. + [{artist: $artist, song: $song, yt_url: $yt_url, spot_url: $spot_url}]' data.json > tmp.json
mv tmp.json data.json