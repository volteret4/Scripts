#!/usr/bin/env bash
#
# Script Name: 2test.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#




tempfile=$(mktemp)
dialog --radiolist 'checklist' 15 10 10 'huan'  1 'off'  'dietpi' 2 'off' 'pi' 3 'off' 'hulio' 4 'off' 2>>$tempfile

clear
cat $tempfile
echo $tempfile
