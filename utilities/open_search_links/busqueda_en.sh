#!/usr/bin/env bash
#
# Script Name: busqueda_en.sh
# Description: Buscar texto seleccionado (copiado automáticamente xclip) en diversos motores pasados como argumento
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
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

elif [[ ${enlace} =~ 'record.club' ]]; then
    busqueda="$(echo $busqueda | sed 's/\nby / /')"
fi

# selecciona url apropiada al motor
if [[ -z $motor ]]; then
    echo "Falta argumento para elegir motor de busqueda"

elif [[ $motor =~ 'youtube' ]]; then
    busqueda="$(echo $busqueda | sed 's/ /%20/g' )"
    url="https://yt.pollete.duckdns.org/search?q=${busqueda}"

    # Usar script local en lugar del servidor remoto
    url_api="$("$HOME"/Scripts/python_venv/bin/python "${HOME}/Scripts/utilities/open_search_links/busqueda_api/youtube-1arg.py" "${busqueda}")"
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

elif [[ $motor =~ 'hdolimpo' ]]; then
    url="https://hd-olimpo.club/torrents?perPage=50&name=${busqueda}"


elif [[ $motor =~ 'discogs' ]]; then
    busqueda="$(echo $busqueda | sed 's/-//g' | sed 's/&/and/g')"

    # Usar scripts locales en lugar del servidor remoto
    masterid="$("$HOME"/Scripts/python_venv/bin/python "${HOME}/Scripts/Musica/blog/vvmm/modules/discogs.py" $busqueda)"

    if [[ $masterid =~ 'Uso: python discogs_api.py' ]]; then
        url="https://www.discogs.com/search?q=${busqueda}"
    elif [[ $masterid =~ 'bash_script' ]]; then
        releaseid="$("$HOME"/Scripts/python_venv/bin/python "${HOME}/Scripts/Musica/blog/vvmm/modules/release_id.py" $busqueda)"
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
