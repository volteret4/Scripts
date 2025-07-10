#!/usr/bin/env bash
#
# Script Name: scrcpy_poco.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#




# Iniciar ADB
adb server

# Enviar a tasker señar para que active adb sin clables



# Conectar a Poco
adb connect 192.168.1.131:3434

# Iniciar scrcpy
scrcpy
