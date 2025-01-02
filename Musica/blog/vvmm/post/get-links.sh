#!/usr/bin/env bash
#
# Script Name: get-links.sh
# Description: Obtener links de varias webs para un nuevo post.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO:
# Notes:
#   Dependencies:   - python3 con los paquetes: lxml, google-api-python-client, requests, bs4
#                   - hugo, jq, git,
#                   - api accounts for: youtube, spotify, lastfm, discogs
#
#



# DECLARACION DE VARIABLES:

# Rutas.
dir="${HOME}/scripts/blog/vvmm/post/enlaces"
blog="${HOME}/web/vvmm"

# Parametros
artista="${1}"
albuma="${2}"
# eliminamos caracteres no alfanumericos.....que pena no poder poner una tilde
artist="$(bash "$HOME/scripts/limpiar_var.sh" "$artista}")"
album="$(bash $HOME/scripts/limpiar_var.sh ${albuma})"

# .env_root: COLORES!
#source ${HOME}/scripts/.env_root

# Generos o Estilos
tagA="${3}"
tagB="${4}"
tagC="${5}"
tagD="${6}"
tagE="${7}"


# OBTENER ENLACES A SERVICIOS:

# lastfm sin espacios? quejica los cojones                 # desact...30.4.24
#l_artist="$(echo $artist | sed 's/ /%20/g')"
lastfm="$(bash ${dir}/lastfm.sh "$artist" "$album")"
#allmusic="$(python3 ${dir}/allmusic.py ${artist} ${album})"
bandcamp="$(python3 ${dir}/bandcamp.py "$artist" "$album" | sed 's/\?from=.*//')"
spotify="$(python3 ${dir}/spotify.py "$artist" "$album")"
youtube="$(python3 ${dir}/youtube.py "$artist" "$album")"
musicbrainz="$(python3 ${dir}/musicbrainz.py "$artist" "$album")"
rym="$(python3 ${dir}/rym.py ${artist} ${album})"
# master id de discogs para obtener info.
masterid="$(python3 ${dir}/discogs.py "$artist" "$album")"

# lanzar script de bash para buscar releases si no hay masterid.
if [ $masterid = 'bash_script' ]
    then
        temp_dg="$(bash "${dir}"/releases_discogs.sh "$album")"
        discogs="$(echo "$temp_dg" | awk -F ' ' '{print $2}')"
        releaseid="$(echo "$temp_dg" | awk -F ' ' '{print $1}')"
        echo "ES RELEASE ID: $releaseid"
    else
        discogs="https://www.discogs.com/master/$masterid"
        echo "ES MASTERID: $masterid"
fi

 # PREPARA EL POST:

# Rellena las variables con rutas de imagen y links.
youtube="[![youtube](../links/svg/youtube.png (youtube))]("$youtube")"
bandcamp="[![bandcamp](../links/svg/bandcamp.png (bandcamp))]("$bandcamp")"
spotify="[![spotify](../links/svg/spotify.png (putify))]("$spotify")"
musicbrainz="[![musicbrainz](../links/svg/musicbrainz.png (musicbrainz))]("$musicbrainz")"
discogs="[![discogs](../links/svg/discogs.png (discogs))]("$discogs")"
rym="[![rateyourmusic](../links/svg/sonemic.png (las leyendas cuentan que un dia tuvo el nombre de Sonemic))]("$rym")"
lastfm="[![lastfm](../links/svg/lastfm.png (lastfm))]("$lastfm")"


# CREA EL POST
cd ${blog}
post="${artist}-${album}"
artista_guion="${artist} _"                                         # Aqui adjunta el guion bajo
post_pre="${artista_guion}-${album}"
post_guiones="$(echo "$post_pre" | sed 's/ /-/g' | sed 's/,//g')"
post_file="${blog}/content/posts/${post_guiones}/index.md"
if [[ -f $post_file ]]
then
  echo "Ya existe el post $post_file"
  exit 1
else
     hugo new --kind post-bundle posts/${post_guiones}              # Aqui lo crea, con un guin bajo para que lo pase a normal en la web.
fi

# ANADIR CONTENIDO AL POST

# Anadir iconos con urls al post.
echo "![cover](image.jpeg ($artist - $album))" >> "$post_file"
echo " " >> "$post_file"
#echo "${allmusic}" >> "$post_file"
echo "${bandcamp}" >> "$post_file"
echo "${discogs}" >> "$post_file"
echo "${lastfm}" >> "$post_file"
echo "${musicbrainz}" >> "$post_file"
#echo "${rym}" >> "$post_file"
echo "${spotify}" >> "$post_file"
echo "${youtube}" >> "$post_file"
echo " " >> "$post_file"


# Anadir CONTENIDO desde discogs.
# Obtener info de discogs con masterid o releaseid.
if [[ $masterid != 'bash_script' ]]
    then
        python3 "${dir}"/info_discogs.py "${masterid}" "$post_file"
    elif [[ -n $releaseid ]]
        then
            python3 "${dir}"/info_release_discogs.py "$releaseid" "$post_file"
fi


# Descarga CARATULA de spotify.
cd $(dirname $post_file)
python3 "$dir"/caratula-spotify.py "$artist" "$album"


# A�ade las TAGS si existieran.
if [[ -n $tagA ]]
then
	sed -i 's/\#- tagA/- '"$tagA"'/' "${post_file}"
fi
if [[ -n $tagB ]]
    then
        sed -i 's/\#- tagB/- '"$tagB"'/' "${post_file}"
fi
if [[ -n $tagC ]]
    then
        sed -i 's/\#- tagC/- '"$tagC"'/' "${post_file}"
fi
if [[ -n $tagD ]]
    then
        sed -i 's/\#- tagD/- '"$tagD"'/' "${post_file}"
fi
if [[ -n $tagE ]]
    then
        sed -i 's/\tagE/- '"$tagE"'/' "${post_file}"
fi


# Undraft.
sed -i 's/draft: true/draft: false/' "${post_file}"


# Publicar con hugo.
cd ${blog}
hugo


# Subir a github.
git add .
git commit -m "${artist} ${album}"
git push



#   DEBUG
echo "#################"
echo "# DEBUG MOMEMT  #"
echo "#################"
echo ""
echo ""
echo -e "artist    $artist, saneado de $artista"
echo -e "album     $album, saneado de  $albuma"
echo ""
echo -e "${AZUL}bc    $bandcamp"
echo -e "dg    $discogs"
echo -e "yt    $youtube"
echo -e "lf    $lastfm"
echo -e "sp    $spotify"
#echo -e "am    $allmusic"
echo -e "mb    $musicbrainz ${NC}"
echo -e ""
echo -e "${AMARILLO_CLARO}tagA  $tagA"
echo -e "tagB  $tagB"
echo -e "tagC  $tagC"
echo -e "tagD  $tagD"
echo -e "tagE  $tagE ${NC}"
echo -e ""
echo -e "dir   $dir"
echo -e "blog  $blog"
echo ""
echo ""
echo ""
echo ""
echo "#############"
echo "## post.md ##"
echo "#############"
echo ""
echo ""
cat "${post_file}"


