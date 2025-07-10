#!/usr/bin/env bash
#
# Script Name: borg.sh 
# Description: Backup using borg
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 

# Notes:
#   Dependencies:
#       borg
#

borg create --list -C zstd borg:arco::dotfiles-`date +%Y%m%d_%H%M%S` /home/huan/.dotfiles
borg prune --list --keep-last 5 borg@server.ip:bkp
