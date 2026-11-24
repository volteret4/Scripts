#!/usr/bin/env bash
#
# Script Name: dashboard_agent.sh
# Description: Punto de entrada unico invocado via "command=" forzado en
#              authorized_keys por el dashboard de backups en pepecono.
#              Decide que hacer segun $SSH_ORIGINAL_COMMAND (lo que el
#              cliente SSH pidio), nunca ejecuta comandos arbitrarios.
#
set -uo pipefail

STATUS_DIR="$HOME/.cache/kopia-status"

case "${SSH_ORIGINAL_COMMAND:-}" in
    snapshot)
        exec "$HOME/Scripts/kopia/kopia-notify.sh" "Snapshot arcolinux" -- "$HOME/Scripts/kopia/snapshot_arcolinux.sh"
        ;;
    wake-proxmox)
        exec "$HOME/Scripts/kopia/kopia-notify.sh" "Despertar proxmox manual" -- "$HOME/Scripts/kopia/wake_proxmox.sh"
        ;;
    status)
        mkdir -p "$STATUS_DIR"
        for f in "$STATUS_DIR"/*.json; do
            [ -e "$f" ] || continue
            cat "$f"
            echo
        done
        ;;
    log)
        mkdir -p "$STATUS_DIR"
        cat "$STATUS_DIR/Snapshot_arcolinux.log" 2>/dev/null
        ;;
    kopia-snapshots)
        # kopia aplica ACL por usuario: pepe no puede listar snapshots de huan
        # via el repo compartido, asi que el propio huan se los da aqui.
        SOURCES=(
            "$HOME/.local/share/chezmoi"
            "$HOME/Scripts"
            "$HOME/.cache/kopia-untracked-staging/pollo"
            "/etc/fstab"
            "/etc/ssh/sshd_config"
        )
        for src in "${SOURCES[@]}"; do
            echo "### $src"
            kopia snapshot list "$src" --json 2>/dev/null
            echo
        done
        ;;
    *)
        echo "Comando no permitido" >&2
        exit 1
        ;;
esac
