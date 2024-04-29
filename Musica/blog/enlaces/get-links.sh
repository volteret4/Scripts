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

dir="${HOME}/scripts"
blog="${HOME}/web/vvmm"

artist="${1}"
album="${2}"

tagA="${3}"
tagB="${4}"
tagC="${5}"
tagD="${6}"
tagE="${7}"

# Lanza varios scripts para obtener las urls de diferentes servicios

# bandcamp sin guiones y con espacios? quejica los cojones   # desact...
l_artist="$(echo $artist | sed 's/ //g')"

#allmusic="$(python3 ${dir}/allmusic.py ${artist} ${album})"
bandcamp="$(python3 ${dir}/bandcamp.py "$artist" "$album")"
spotify="$(python3 ${dir}/spotify.py "$artist" "$album")"
discogs="$(python3 ${dir}/discogs.py "$artist" "$album")"
lastfm="$(bash ${dir}/lastfm.sh "$l_artist" "$album")"
youtube="$(python3 ${dir}/youtube.py)"
musicbrainz="$(python3 ${dir}/musicbrainz.py)"
rym="$(python3 ${dir}/rym.py ${artist} ${album})"
#="$(python3 ${dir}/)"


# Rellena las variables con rutas de imagen y links
youtube="[![youtube](../links/svg/youtube.png (youtube))]("$youtube")"
bandcamp="[![bandcamp](../links/svg/bandcamp.png (bandcamp))]("$bandcamp")"
spotify="[![spotify](../links/svg/spotify.png (putify))]("$spotify")"
musicbrainz="[![musicbrainz](../links/svg/musicbrainz.png (musicbrainz))]("$musicbrainz")"
discogs="[![discogs](../links/svg/discogs.png (discogs))]("$discogs")"
rym="[![rateyourmusic](../links/svg/sonemic.png (las leyendas cuentan que un día tuvo el nombre de Sonemic))]("$rym")"
lastfm="[![lastfm](../links/svg/lastfm.png (lastfm))]("$lastfm")"


 # Crea el post
cd ${blog}
post="${artist}-${album}"
artista_guion="${artist} _"
post_pre="${artista_guion}-${album}"
post_guiones="$(echo "$post_pre" | sed 's/ /-/g' | sed 's/,//g')"
post_file="${blog}/content/posts/${post_guiones}/index.md"
if [[ -f $post_file ]]
then
  echo "Ya existe el post $post_file"
  exit 1
else
     hugo new --kind post-bundle posts/${post_guiones}
fi

# Añadir iconos con urls al post.
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


# Descarga caratula de spotify.
cd $(dirname $post_file)
python3 "$dir"/caratula-spotify.py "$artist" "$album"

# AÃade las tags si existieran.
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


#
#   DEBUG
#

echo "#################"
echo "# DEBUG MOMEMT  #"
echo "#################"
echo ""
echo "artist    $artist"
echo "album     $album"
echo ""
echo "bc    $bandcamp"
echo "dg    $discogs"
echo "yt    $youtube"
echo "lf    $lastfm"
echo "sp    $spotify"
echo "am    $allmusic"
echo ""
echo "tagA  $tagA"
echo "tagB  $tagB"
echo "tagC  $tagC"
echo "tagD  $tagD"
echo "tagE  $tagE"
echo ""
echo "dir   $dir"
2echo "blog  $blog"
