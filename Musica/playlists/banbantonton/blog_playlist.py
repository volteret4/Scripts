#!/bin/bash

# Configuración
BLOG_URL="https://banbantonton.com"
FEED_URL="$BLOG_URL/feed"
LINK_PATTERN='https?://\(bandcamp\|youtube\|soundcloud\)\.com[^"]*'
PLAYLIST_FILE="/tmp/playlist.m3u"

# Función para obtener URLs de los posts desde el feed
fetch_post_urls_from_feed() {
    feed_url="$1"
    echo "Obteniendo URLs de los posts desde: $feed_url"  # Depuración
    curl -s "$feed_url" | grep -oP 'https://banbantonton\.com/\d{4}/\d{2}/\d{2}/[^"]+' | sort -u
}

# Función para obtener enlaces de una publicación
fetch_links_from_post() {
    post_url="$1"
    echo "Obteniendo enlaces de: $post_url"  # Depuración
    html=$(curl -s "$post_url")
    links=$(echo "$html" | grep -oP "$LINK_PATTERN" | sort -u)
    echo "Enlaces encontrados: $links"  # Depuración
    echo "$links"
}

# Función para limpiar las URLs
clean_url() {
    url="$1"
    # Aquí podemos hacer alguna limpieza si es necesario, como eliminar parámetros innecesarios
    # Ejemplo de limpieza: eliminar fragmentos de URL si es necesario
    cleaned_url=$(echo "$url" | sed 's/\?[^ ]*$//')  # Elimina parámetros query si existen
    echo "$cleaned_url"
}

# Crear la playlist con los enlaces
create_playlist() {
    links=("$@")
    echo "Creando playlist con los enlaces: ${links[@]}"  # Depuración
    echo "${links[@]}" > "$PLAYLIST_FILE"
}

# Reproducir la playlist con MPC
play_with_mpd() {
    echo "Reproduciendo la playlist con MPC..."  # Depuración
    mpd --kill && mpd play
}

# Obtener las URLs de los posts desde el feed
post_urls=($(fetch_post_urls_from_feed "$FEED_URL"))

# Recoger todos los enlaces de los posts
all_links=()
for post_url in "${post_urls[@]}"; do
    echo "Procesando URL del post: $post_url"  # Depuración
    links=$(fetch_links_from_post "$post_url")
    
    # Limpiar y acumular los enlaces en all_links
    for link in $links; do
        cleaned_link=$(clean_url "$link")
        all_links+=("$cleaned_link")
    done
done

# Mostrar el total de enlaces encontrados para depuración
echo "Total de enlaces encontrados: ${#all_links[@]}"  # Depuración

# Crear la playlist y reproducir
if [ ${#all_links[@]} -gt 0 ]; then
    create_playlist "${all_links[@]}"
    if [ ! -z "$PLAYLIST_FILE" ]; then
        play_with_mpd
        echo "Playlist creada en: $PLAYLIST_FILE"  # Depuración
    else
        echo "No se pudo crear la playlist."  # Depuración
    fi
    
else
    echo "No se encontraron enlaces para ese mes."
fi
