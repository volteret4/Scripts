#!/bin/bash

# Comprobar si Spotify está en ejecución
if pgrep -x "spotify" > /dev/null; then
    # Si está abierto, intenta abrir la URL
    spotify --uri "$1" &
else
    # Si no está abierto, inicia Spotify con la URL
    env LD_PRELOAD=/usr/lib/spotify-adblock.so spotify --uri "$1" &
fi
