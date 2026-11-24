#!/usr/bin/env bash
#
# Script Name: snapshot_arcolinux.sh
# Description: Crea snapshots Kopia de dotfiles (chezmoi), Scripts, datos no
#              trackeados de ~/gits/pollo y config de sistema seleccionada.
#
set -uo pipefail

"$HOME/Scripts/kopia/wake_proxmox.sh" || { echo "Aborto: proxmox no responde, no se puede snapshotear"; exit 1; }

# El host proxmox responde por SSH antes de que el LXC lxc-docker (192.168.1.89)
# termine de arrancar y levante el servidor kopia dentro de él. Sin esta espera,
# "kopia snapshot create" falla la mayoría de días porque el repo aún no está listo.
KOPIA_REPO_HOST="192.168.1.89"
KOPIA_REPO_PORT=51515
REPO_MAX_TRIES=30
REPO_SLEEP=10
repo_ready=0
for i in $(seq 1 "$REPO_MAX_TRIES"); do
    if nc -z -w3 "$KOPIA_REPO_HOST" "$KOPIA_REPO_PORT" 2>/dev/null; then
        repo_ready=1
        break
    fi
    sleep "$REPO_SLEEP"
done
[ "$repo_ready" -eq 1 ] || { echo "Aborto: servidor kopia en lxc-docker ($KOPIA_REPO_HOST:$KOPIA_REPO_PORT) no responde tras $((REPO_MAX_TRIES * REPO_SLEEP))s"; exit 1; }

"$HOME/Scripts/kopia/stage_untracked_pollo.sh"

SOURCES=(
    "$HOME/.local/share/chezmoi"
    "$HOME/Scripts"
    "$HOME/.cache/kopia-untracked-staging/pollo"
    "/etc/fstab"
    "/etc/ssh/sshd_config"
)

STATUS=0
for src in "${SOURCES[@]}"; do
    kopia snapshot create --no-send-snapshot-report "$src" || STATUS=1
done

# Programa una comprobación de inactividad en proxmox (15 min); si nadie más
# lo está usando (Jellyfin, etc.) se apaga solo. Se hace siempre, no solo si
# lo despertamos nosotros, para cubrir también el caso del WOL nocturno fijo.
ssh proxmox "sudo systemd-run --on-active=900 --unit=kopia-idle-shutdown-\$(date +%s) /root/kopia-idle-shutdown-check.sh" 2>&1 \
    || echo "Aviso: no se pudo programar el apagado diferido de proxmox"

exit "$STATUS"
