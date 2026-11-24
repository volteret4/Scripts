#!/usr/bin/env bash

TEMPLATE="$HOME/.config/zellij/templates/claude_vm_proyecto.kdl"
RUTAS="$HOME/.config/zellij/templates/rutas_proyectos_claude.txt"
DEST="$HOME/.config/zellij/layouts/claude-vm"

mkdir -p "$DEST"
rm -f "$DEST"/*.kdl

while IFS= read -r ruta || [[ -n "$ruta" ]]; do
    [[ -z "$ruta" ]] && continue
    nombre=$(basename "$ruta")
    destino="$DEST/$nombre.kdl"
    if [[ -f "$destino" ]]; then
        echo "Ya existe, omitiendo: $destino"
        continue
    fi
    remote_dir="${ruta/\/home\/huan\//\/home\/pepe\/}"
    sed -e "s|{{PROJECT_DIR}}|$ruta|g" \
        -e "s|{{REMOTE_DIR}}|$remote_dir|g" \
        "$TEMPLATE" > "$destino"
    echo "Creado: $destino"
done < "$RUTAS"
