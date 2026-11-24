#!/bin/bash
# Script para cargar álbumes sin género en MusicBrainz Picard
# Generado automáticamente

# Archivo con la lista de álbumes (cambia esto si usaste otro nombre)
ALBUM_LIST="$1"

# Verifica que el archivo existe
if [ ! -f "$ALBUM_LIST" ]; then
    echo "❌ Error: No se encuentra el archivo $ALBUM_LIST"
    echo "Genera el archivo primero con:"
    echo "  python clean_music_genres.py /ruta/musica -r --export-missing $ALBUM_LIST"
    exit 1
fi

# Verifica que Picard esté instalado
if ! command -v picard &> /dev/null; then
    echo "❌ Error: MusicBrainz Picard no está instalado"
    echo "Instálalo con: sudo apt install picard (Ubuntu/Debian)"
    exit 1
fi

# Contar álbumes (excluir líneas de comentario que empiezan con #)
TOTAL=$(grep -v '^#' "$ALBUM_LIST" | grep -v '^$' | wc -l)

echo "📂 Cargando $TOTAL álbumes en Picard desde $ALBUM_LIST..."

# Leer el archivo y cargar en Picard
# Filtra líneas de comentario y líneas vacías
picard $(grep -v '^#' "$ALBUM_LIST" | grep -v '^$')

echo "✅ Listo!"
