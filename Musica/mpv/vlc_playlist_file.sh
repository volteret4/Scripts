#!/usr/bin/env bash
#
# Script Name: vlc_playlist_file.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

#yt="^https://www.youtube*|^http://youtube*|^http://www.youtube*|^https://youtu.be*"
#yt="^https?:\/\/(www\.)?(.+)?(bandcamp|youtube|youtu.be)(.com)?"
playlist="$1"
url="$2"
mpv --input-ipc-server="/tmp/mpvsocket" --ytdl-format="best" --replaygain="track" --force-window --osd-level=3 --osd-msg3="${url}" --term-playing-msg="Title: ""${media-title} - ${media-artist} - ${media-album}""" --playlist="${playlist}" &

# while IFS= read -r line; do
#     if [[ $line =~ $yt ]]
#         then
#             echo "yt link"
#             #vlc --playlist-enqueue $(youtube-dl -ge -f best --audio-quality 0 $line | sed '1~2 s/ /_/g') &/
#             #vlc --playlist-enqueue $(youtube-dl -ge -f best --audio-quality 0 --output "%(uploader)s%(title)s.%(ext)s" $line | sed '1~2 s/ /_/g') &/
#             mpv --force-window --term-playing-msg='Title: ${media-title}' $line
#         else
#             echo "bc link"
#             #vlc --playlist-enqueue $(youtube-dl -ge $line | sed '1~2 s/ /_/g') &/
#             mpv --force-window --term-playing-msg='Title: ${media-title}' $line
#     fi
# done < "$1"


# youtube-dl --extract-audio --audio-format mp3 --output "%(uploader)s%(title)s.%(ext)s" http://www.youtube.com/watch?v=rtOvBOTyX00

# mpv --term-playing-msg='Title: ${media-title}' http://www.youtube.com/watch?v=rtOvBOTyX00
