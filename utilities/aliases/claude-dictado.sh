#!/usr/bin/env bash
#
# Script Name: claude-dictado.sh
# Description: Abre la ventana de dictado para Claude o, si ya está abierta,
#              alterna dictado/enviar (SIGUSR1).
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies: - claude_dictado.py (mismo directorio)

PIDFILE="/tmp/claude-dictado.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    kill -USR1 "$(cat "$PIDFILE")"
else
    exec python3 "$(dirname "$(readlink -f "$0")")/claude_dictado.py"
fi
