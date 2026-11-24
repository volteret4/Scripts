#!/usr/bin/env bash
# Crea (si hace falta) y arranca la VM claude-vm, y espera a que SSH responda.
set -euo pipefail

export LC_ALL=C
VIRSH="virsh -c qemu:///session"
DOMAIN="claude-vm"
IMAGES="$HOME/.local/share/libvirt/images"
BASE_IMG="$IMAGES/base/Arch-Linux-x86_64-cloudimg.qcow2"
OVERLAY="$IMAGES/claude-vm.qcow2"
SEED_ISO="$IMAGES/claude-vm-seed.iso"
DOMAIN_XML="$HOME/Scripts/menus/vm/claude-vm.xml"
SSH_TIMEOUT=180

log() { echo "[vm_claude_ensure] $*" >&2; }

wait_for_ssh() {
    local waited=0
    while ! ssh -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=accept-new claude-vm true 2>/dev/null; do
        sleep 2
        waited=$((waited + 2))
        if (( waited >= SSH_TIMEOUT )); then
            log "timeout esperando SSH en claude-vm"
            return 1
        fi
    done
}

if ! $VIRSH dominfo "$DOMAIN" >/dev/null 2>&1; then
    log "el dominio $DOMAIN no existe todavía"
    for f in "$BASE_IMG" "$OVERLAY" "$SEED_ISO" "$DOMAIN_XML"; do
        if [[ ! -f "$f" ]]; then
            log "falta $f — provisiona la VM manualmente antes de usar este script (ver plan/README)"
            exit 1
        fi
    done
    $VIRSH define "$DOMAIN_XML"
fi

estado=$($VIRSH domstate "$DOMAIN")
if [[ "$estado" != "running" ]]; then
    log "arrancando $DOMAIN"
    $VIRSH start "$DOMAIN"
fi

log "esperando SSH..."
wait_for_ssh

log "esperando cloud-init (solo tarda en el primer arranque)..."
ssh -o StrictHostKeyChecking=accept-new claude-vm 'cloud-init status --wait' >/dev/null 2>&1 || true

log "claude-vm lista"
