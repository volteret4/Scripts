#!/usr/bin/env bash
#
# Script Name: sync_vdir.sh
# Description: Sincronizar vdirsyncer
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - python3, 
#

# Sincronizar
vdirsyncer sync

# Copiar a Obsidian
rsync -avh /home/huan/.config/vdirsyncer/calendars/tareas/ /mnt/windows/FTP/wiki/Obsidian/calendars/tareas
