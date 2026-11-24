#!/usr/bin/env bash
# Comando del panel de zellij: asegura la VM, monta el proyecto dentro y lanza claude.
# Uso: vm_claude_pane.sh <ruta_absoluta_del_proyecto_en_host>

set -uo pipefail

PROJECT_DIR="${1:?uso: vm_claude_pane.sh <ruta_del_proyecto>}"
PROJECT_NAME=$(basename "$PROJECT_DIR")

if "$HOME/Scripts/menus/vm/vm_claude_ensure.sh"; then
    ssh -t claude-vm "~/bin/mount_and_claude.sh '$PROJECT_NAME' '$PROJECT_DIR'"
fi

echo "[vm_claude_pane] sesion en claude-vm terminada, cayendo a shell local"
exec "$SHELL"
