#!/usr/bin/env bash
#
# Script Name: banbantonton.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#


copyq_content=$(copyq eval -- "tab('banbantonton'); for(i=size(); i>0; --i) print(str(read(i-1)) + '\n');")

links=""
for link in $copyq_content; do
    page_content=$(wget -qO- "$link")
    # O alternativamente, usando curl:
    # page_content=$(curl -s "$link")
    
    youtube_links=$(echo "$page_content" | grep -oP 'https?://www\.youtube\.com/watch\?v=[^"'\''<&]*')
    bandcamp_links=$(echo "$page_content" | grep -oP 'https?://[^"'\''<&]*\.bandcamp\.com/[^"'\''<&]*')

    links+="$youtube_links"$'\n'"$bandcamp_links"$'\n'
done

unique_links=$(echo "$links" | sort | uniq)

file=$(mktemp)

echo "$unique_links" > ${file}

bash ${HOME}/Scripts/mpv/vlc_playlist_file.sh ${file}
