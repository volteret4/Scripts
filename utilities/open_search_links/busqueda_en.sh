#!/usr/bin/env bash
#
# Script Name: busqueda_en.sh 
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en diversos motores pasados como argumento
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       Firefox     Thorium-browser   Floorp    chromium    Floorp     DeaDBeef    strawberry       xdotool
#

# Variables
INVIDIOUS_URL="http://localhost:3000"
motor="$1"  # donde se realizara la busqueda
busqueda="$(xclip -o)"
busqueda="${busqueda//&/and}"    # elementos a buscar
#busqueda="${busqueda//–/}"

app="$(bash "${HOME}/Scripts/snippets/if_firefox_active.sh")"  # obtener app activa
enlace="$(awk 'NR == 2 {print $NF}' $app)"
notify-send -t 10000 "bandcamp $enlace"
# Quitar \n by de algunas busquedas
if [[ "${enlace}" =~ 'bandcamp' ]]; then
    busqueda="$(echo $busqueda | sed ':a;N;$!ba;s/\n[b]y/ /g')"
    notify-send -t 5000 "bandcamp $busqueda"
elif [[ ${enlace} =~ 'record.club' ]]; then
    busqueda="$(echo $busqueda | sed 's/\nby / /')"
fi


# selecciona url apropiada al motor
if [[ -z $motor ]]; then
    echo "Falta argumento para elegir motor de busqueda"


elif [[ $motor =~ 'youtube' ]]; then
    busqueda="$(echo $busqueda | sed 's/ /-/g' )"
    url="https://www.youtube.com/results?search_query=${busqueda}"
    comando="python3 /home/ansible/scripts/blog/vvmm/post/enlaces/youtube-1arg.py "${busqueda}""
    echo "com: $comando"
    url_api="$(ssh hugo "$comando")"
    echo "url $url_api"

    if [[ -z $url_api ]]; then
        echo "no se encontró nada en la api"
    else
        copyq add ${url}
        url="$(echo ${url_api} | awk 'NR==1 {print $1}' )"
        echo "cambiando a url de la api. guardada la anterior en el portapapeles"
    fi
    echo "urls: $url"
    instancia_invidious="$INVIDIOUS_URL"
    url="$(echo "${url}" | sed "s|https://www.youtube.com|$instancia_invidious|g; s|https://youtube.com|$instancia_invidious|g")"

elif [[ $motor =~ 'bandcamp' ]]; then
    url="https://bandcamp.com/search?q=${busqueda}"


elif [[ $motor =~ 'discogs' ]]; then
    busqueda="$(echo $busqueda | sed 's/-//g' | sed 's/&/and/g')"
    # comando="python3 /home/ansible/scripts/busqueda_apis/busq_discogs.py ${busqueda}"
    comando="python3 /home/ansible/scripts/blog/vvmm/post/enlq/discogs/discogs.py $busqueda"
    masterid="$(ssh hugo "$comando")"
    if [[ $masterid =~ 'Uso: python discogs_api.py' ]]; then
        url="https://www.discogs.com/search?q=${busqueda}"
    elif [[ $masterid =~ 'bash_script' ]]; then
        comando="python3 /home/ansible/scripts/blog/vvmm/post/enlaces/discogs/release_id.py $busqueda"
        releaseid="$(ssh hugo $comando)"
        if [[ $releaseid =~ 'Uso: python script.py' ]]; then
            url="https://www.discogs.com/search?q=${busqueda}"
        elif [[ -z $releaseid ]]; then
            url="https://www.discogs.com/search?q=${busqueda}"
        else
            url="https://www.discogs.com/release/${releaseid}"
            copyq add "$url"
        fi
    else
        url="https://www.discogs.com/master/${masterid}"
        copyq add "$url"
    fi


elif [[ $motor =~ 'google' ]]; then
    url="https://www.google.com/search?q=${busqueda}"

elif [[ $motor =~ 'orpheus' ]]; then
    url="https://orpheus.network/torrents.php?searchstr=${busqueda}"

elif [[ $motor =~ 'rutracker' ]]; then
    url="https://rutracker.org/forum/tracker.php?nm=${busqueda}"

elif [[ $motor =~ 'rym' ]]; then
    url="https://rateyourmusic.com/search?searchterm=${busqueda}"

elif [[ $motor =~ 'spotify' ]]; then
    busqueda="${busqueda//\ /_}"
    echo u-"${url}"
    url="https://open.spotify.com/search/${busqueda}"
    url_encoded="$(echo "${url}" | base64)"
    url_decoded="$(echo "${url_encoded}" | base64 -d)"
    echo e-"${url}"
    echo d-"${url_decoded}"
    spotify "${url_decoded}"
    exit 0
    
elif [[ $motor =~ 'wikipedia' ]]; then
    url="https://en.wikipedia.org/w/index.php?search=${busqueda}"
fi


echo "antes del if $app"



if [[ "${app}" =~ "strawberry|DeaDBeef" ]]; then
        #bash "$HOME/Scripts/utilities/open_search_links/music_player/${motor}_metadata.sh"
        echo "PENDIENTE"
    elif [[ ${app} =~ 'zen' ]]; then
        zen-browser "${url}" &
    elif [[ ${app} =~ 'Thorium' ]]; then
        thorium-browser "${url}" &
    elif [[ ${app} =~ 'Firefox' ]]; then
        firefox "${url}" &
    elif [[ ${app} =~ 'Chromium' ]]; then
        chromium "${url}" &
    elif [[ ${app} =~ "Floorp" ]]; then
        floorp "${url}" &
    else
        echo "${busqueda}"
        qutebrowser --target window "${url}" &
fi