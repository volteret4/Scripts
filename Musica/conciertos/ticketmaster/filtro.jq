
# filtro_eventos.jq (with null handling and missing price ranges)

.["_embedded"].events[] | {
  "nombre_artista": .name,
  "fecha_concierto": (.dates.start.localDate // ""),
  "hora_concierto": (.dates.start.localTime // ""),
  "url_evento": .url,
  "genero": (.classifications[0].genre.name // ""),
  "subgenero": (.classifications[0].subGenre.name // ""),
   
  # Escape backslashes within strings for "nombre_local" and "ciudad"
  "nombre_local": (.["_embedded"].venues[0].name // ""),
  "ciudad": (.["_embedded"].venues[0].city.name // ""),
  "fecha_hora_inicio_venta": .sales.public.startDateTime,
  
  # Use the or operator to provide a default value for missing price ranges
#  "precio_minimo": (
#    .priceRanges[] | select(.type == "standard including fees") | .min // empty
#  ),
#  "precio_maximo": (
#    .priceRanges[] | select(.type == "standard including fees") | .max // empty
#  )
}