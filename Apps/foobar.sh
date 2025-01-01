#!/usr/bin/env bash
#
# Script Name: foobar.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



cd ~/.foobar2000/
if [ "$1" != "" ]; then
filename=`echo z:$1 | sed 's/\\//\\\\/g'`
wine foobar2000.exe "$filename" &
else
wine foobar2000.exe &
fi
