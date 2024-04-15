#!/usr/bin/env bash
#
# Script Name: keepass_merge.sh 
# Description: Merge two kdbx databases
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       keepassxc
#



kb_curro="/mnt/Datos/FTP/Trabajo/trabajo.kdbx"
kb_og="/mnt/Datos/FTP/Moviles/Database.kdbx"

pw=$(zenity --info --text "se esta actualizando keepass")

cp "${kb_og}" "${kb_og}".BAK
cp "${kb_curro}" "${kb_curro}".BAK

keepassxc-cli merge -s "${kb_og}" "${kb_curro}" --password="${pw}"
