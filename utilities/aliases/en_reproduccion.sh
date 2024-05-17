
# Obterner ruta del archivo en reproducción
deadbeef="$(deadbeef --nowplaying-tf "%artist%")"

if [ -z "$deadbeef" ]
      then
            dir=$(playerctl metadata xesam:url)
            dir2=$(sed 's/^file:\/\///' <<< "${dir}")

            archivo=$(echo "${dir2}" | sed -n 's/^\(.*\/\)*\(.*\)/\2/p') # deja solo la ultima carpeta de una ruta, tras el último /
            archivo="$(echo ${archivo} | sed 's/[\":]//g')"
            #archivo2="${archivo//&/and/}"
            cancion=$(playerctl -p strawberry metadata title) # obtener titulo de la canción
#            dup=$(find /mnt/A26A-AAE7/Mix -iname "*$cancion*") # comprobar duplicados
      else
            dir2=$(deadbeef --nowplaying-tf "%path%")
            archivo=$(deadbeef --nowplaying-tf "%filename_ext%")
            archivo="$(echo ${archivo} | sed 's/[\":]//g')"
            artista=$(deadbeef --nowplaying-tf "%artist%")
            cancion=$(deadbeef --nowplaying-tf "%title%")
#            dup=$(find ${mixxx} -iname "*${cancion}*") # comprobar duplicados
fi

art="$(echo "$artista" | sed 's/ /-/g')"
can="$(echo "$cancion" | sed 's/ /-/g')"

echo "${art} ${can}"