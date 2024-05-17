#!/bin/bash

# Guarda la configuración original
CONFIG_FILE=~/.config/dunst/dunstrc/dunstrc
BACKUP_CONFIG=$CONFIG_FILE.backup
cp $CONFIG_FILE $BACKUP_CONFIG

# Cambia la configuración para centrar y aumentar el tamaño de la fuente
sed -i '/^origin=/c\origin=center' $CONFIG_FILE
sed -i '/^scale=/c\scale=20' $CONFIG_FILE

# Envía la notificación
notify-send "Título" "Mensaje largo aquí"

# Restaura la configuración original
mv $BACKUP_CONFIG $CONFIG_FILE