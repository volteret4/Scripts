#!/usr/bin/env bash
#
# Script Name: backup-arco.sh 
# Description: Copy files to borg folder syncronize to run with crontab
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 

# Notes:
#

borg_folder=/home/huan/Documentos/backup-usb/arco

rsync -av /home/huan/Scripts ${borg_folder}/home/huan/Scripts/
rsync -av /etc/fstab ${borg_folder}/etc/
rsync -av /home/huan/.ssh ${borg_folder}/home/huan/.ssh/
rsync -av /home/huan/.dotfiles/ ${borg_folder}/home/huan/.dotffiles/
#rdiff-backup /home/huan/Documentos/backup-usb/ dietpi:/mnt/backup-usb/
