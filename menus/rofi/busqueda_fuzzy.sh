#!/usr/bin/env bash

# Directorio base para la búsqueda
mix="/mnt/windows/Mix"
DIRECTORY="${1:-/mnt/windows/Mix}"
APP="${2:-xdg-open}"
if [[ $DIRECTORY =~ $mix ]];then
  APP="deadbeef"
fi

PLAYER="deadbeef"

# Verifica si el directorio existe
if [ ! -d "$DIRECTORY" ]; then
  echo "El directorio proporcionado no existe."
  exit 1
fi

# Función para abrir el directorio actual
open_dir() {
  thunar "$DIRECTORY"
}

# Función para reproducir música con Deadbeef
play_music() {
  $PLAYER --play
}

# Función para pausar/reanudar la reproducción de música con Deadbeef
pause_resume_music() {
  $PLAYER --toggle-pause
}

# Comando para buscar archivos en el directorio especificado
# Usa fd para listar archivos y pasa la lista a rofi
SEARCH_CMD="fd --hidden --follow --exclude .git --relative-path . $DIRECTORY"
FILES=()
while IFS= read -r line; do
    FILES+=("$(echo "$line" | sed "s|$DIRECTORY/||")")
done < <($SEARCH_CMD)

# Muestra la lista de archivos en rofi
SELECTED_FILE=$(printf "%s\n" "${FILES[@]}" | rofi -dmenu -i -p "Buscar archivo:")

# # Verifica si se seleccionó un archivo
# if [ -n "$SELECTED_FILE" ]; then
#   # Abre el archivo seleccionado (puedes cambiar esto según tu necesidad, por ejemplo, abrir con un editor específico)
#   $APP "$DIRECTORY/$SELECTED_FILE"
# else
#   echo "No se seleccionó ningún archivo."
# fi

# Configurar combinaciones de teclas de acceso rápido para rofi
ROFI_OPTIONS="-kb-accept-entry ctrl+o"
ROFI_OPTIONS="$ROFI_OPTIONS -kb-custom-1 ctrl+p"
ROFI_OPTIONS="$ROFI_OPTIONS -kb-custom-2 ctrl+e"

# Captura las teclas de acceso rápido
while true; do
  # Espera por la entrada del usuario
  key=$(rofi -dmenu -p "Acceso rápido:" $ROFI_OPTIONS <<EOF
Abrir directorio actual (Ctrl+O)
Reproducir música (Ctrl+P)
Pausar/Reanudar música (Ctrl+E)
EOF
)

  # Ejecuta la acción correspondiente según la tecla presionada
  case "$key" in
    "Abrir directorio actual (Ctrl+O)")
      open_dir
      ;;
    "Reproducir música (Ctrl+P)")
      play_music
      ;;
    "Pausar/Reanudar música (Ctrl+E)")
      pause_resume_music
      ;;
    *)
      # Salir del bucle si se presiona Escape o se cierra la ventana de rofi
      break
      ;;
  esac
done