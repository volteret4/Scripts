#!/usr/bin/env bash
#
# Script Name: kp_busqueda.sh
# Description: Abrir/traer keepassxc al frente con el cajón de búsqueda enfocado
# Author: volteret4
# Repository: https://github.com/volteret4/
#

# Guardar el monitor enfocado ANTES de lanzar: al restaurarse, keepassxc
# coge el foco y awesome pasaría a considerar enfocado su monitor original
scr=$(awesome-client "return require('awful').screen.focused().index" | awk '{print $2}')

# Lanzar o traer al frente (keepassxc es instancia única: una 2ª llamada
# muestra la ventana existente, incluso si está en la bandeja, y sale).
if pgrep -x keepassxc >/dev/null; then
    keepassxc >/dev/null 2>&1
else
    setsid -f keepassxc >/dev/null 2>&1
fi

# Esperar a que la ventana principal sea visible (máx ~10 s)
wid=""
for _ in $(seq 50); do
    wid=$(xdotool search --onlyvisible --name 'KeePassXC$' 2>/dev/null | tail -n1)
    [ -n "$wid" ] && break
    sleep 0.2
done
[ -z "$wid" ] && exit 1

# Traer la ventana a la etiqueta del monitor enfocado (si no, awesome
# salta al monitor/etiqueta donde se creó la ventana la primera vez)
awesome-client "local awful = require('awful'); for _, c in ipairs(client.get()) do if c.window == $wid then c.minimized = false; c:move_to_tag(screen[${scr:-1}].selected_tag); awful.placement.centered(c) end end" >/dev/null 2>&1

# Activar vía EWMH (awesome respeta _NET_ACTIVE_WINDOW)
xdotool windowactivate --sync "$wid"
sleep 0.15

# Esperar a soltar Super y mandar Ctrl+F sin modificadores colgados
xdotool keyup Super_L Super_R
xdotool key --clearmodifiers ctrl+f
