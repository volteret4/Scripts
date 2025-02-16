#!/usr/bin/env bash
#
# Script Name: mpv_lastfm_starter.sh
# Description:  Inicia mpv junto al script que 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# TODO: 
# Notes:
#   Dependencies:  - python3, 
#

python3 "$HOME"/Scripts/utilities/aliases/mpv_lastfm.py &
mpv "$@"
