#!/usr/bin/env bash

# Variables
ansible_dir=/home/pepe/.ansible
ansible_cmd="ansible-playbook -i $ansible_dir/hosts_$USER --vault-password-file=$ansible_dir/.vault_pass"


# Despierta proxmox y debian
"${ansible_cmd}" "${ansible_dir}"/playbooks/tools/wakeonlan.yml

sleep 60

# Inicia Kopia
"${ansible_cmd}" "${ansible_dir}"/playbooks/docker/start_kopia.yml

sleep 30

# Actualiza paquetes
"${ansible_cmd}" "${ansible_dir}"/playbooks/update/apt_update.yml