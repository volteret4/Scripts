#!/usr/bin/env bash
#
# Script Name: copiar_color_clipboard.sh
# Description: 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - python3, 
#

xcolor -s | xargs -I {} copyq add "{}"