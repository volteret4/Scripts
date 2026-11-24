#!/usr/bin/env bash
set -euo pipefail

SEED_DIR="$HOME/.claude/jobs/7618a065/tmp/seed"
KEYS="$HOME/.ssh/keys"
mkdir -p "$SEED_DIR"

PUBKEY_HOST_TO_GUEST=$(cat "$KEYS/vm_claude_host_to_guest.pub")

# --- mount_and_claude.sh (runs inside the guest) ---
cat > "$SEED_DIR/mount_and_claude.sh" <<'REMOTE_EOF'
#!/usr/bin/env bash
set -euo pipefail

HOST_GW=$(ip route show default | awk '{print $3; exit}')
HOST_USER="huan"
IDENTITY="$HOME/.ssh/keys/vm_claude_guest_to_host"
PROJECT_NAME="${1:?uso: mount_and_claude.sh <nombre_proyecto> <ruta_absoluta_en_host>}"
HOST_PROJECT_PATH="${2:?uso: mount_and_claude.sh <nombre_proyecto> <ruta_absoluta_en_host>}"

mkdir -p "$HOME/.claude" "$HOME/projects/$PROJECT_NAME"

is_mounted() { mountpoint -q "$1"; }

if ! is_mounted "$HOME/.claude"; then
    sshfs -o IdentityFile="$IDENTITY",StrictHostKeyChecking=accept-new,reconnect,ServerAliveInterval=15 \
        "$HOST_USER@$HOST_GW:/home/$HOST_USER/.claude" "$HOME/.claude"
fi

if ! is_mounted "$HOME/projects/$PROJECT_NAME"; then
    sshfs -o IdentityFile="$IDENTITY",StrictHostKeyChecking=accept-new,reconnect,ServerAliveInterval=15 \
        "$HOST_USER@$HOST_GW:$HOST_PROJECT_PATH" "$HOME/projects/$PROJECT_NAME"
fi

cd "$HOME/projects/$PROJECT_NAME"
exec "$HOME/.local/bin/claude" --continue
REMOTE_EOF
chmod 644 "$SEED_DIR/mount_and_claude.sh"

# --- user-data (static part up to the private key placeholder) ---
cat > "$SEED_DIR/user-data" <<EOF
#cloud-config
hostname: claude-vm
users:
  - name: huan
    groups: [wheel]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - $PUBKEY_HOST_TO_GUEST
packages:
  - openssh
  - sshfs
write_files:
  - path: /root/claude-vm-payload/guest_to_host_key
    permissions: '0600'
    content: |
EOF

sed 's/^/      /' "$KEYS/vm_claude_guest_to_host" >> "$SEED_DIR/user-data"

cat >> "$SEED_DIR/user-data" <<'EOF'
  - path: /root/claude-vm-payload/mount_and_claude.sh
    permissions: '0755'
    content: |
EOF

sed 's/^/      /' "$SEED_DIR/mount_and_claude.sh" >> "$SEED_DIR/user-data"

cat >> "$SEED_DIR/user-data" <<'EOF'
runcmd:
  # write_files runs before the users module, so /home/huan doesn't exist yet:
  # stage payload under /root (always present) and install it here instead.
  - systemctl enable --now sshd
  - install -d -m 0700 -o huan -g huan /home/huan/bin /home/huan/.ssh /home/huan/.ssh/keys /home/huan/projects
  - install -m 0600 -o huan -g huan /root/claude-vm-payload/guest_to_host_key /home/huan/.ssh/keys/vm_claude_guest_to_host
  - install -m 0755 -o huan -g huan /root/claude-vm-payload/mount_and_claude.sh /home/huan/bin/mount_and_claude.sh
  - rm -rf /root/claude-vm-payload
  - su - huan -c 'curl -fsSL https://claude.ai/install.sh | bash'
EOF

cat > "$SEED_DIR/meta-data" <<'EOF'
instance-id: claude-vm-001
local-hostname: claude-vm
EOF

echo "user-data y meta-data generados en $SEED_DIR"
wc -l "$SEED_DIR/user-data" "$SEED_DIR/meta-data"
