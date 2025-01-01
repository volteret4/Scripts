#!/bin/bash

# Monta la tarjeta SD (ajusta según tu sistema)
MOUNTPOINT="/mnt/fiio_sd"
MIXXX="/mnt/windows/Mix"
mkdir -p $MOUNTPOINT
mount -U '6431-3262' $MOUNTPOINT  # Reemplaza 'sdX1' con el dispositivo correcto

# Realiza alguna acción, como copiar archivos
# rsync -avzh $MIXXX/ $MOUNTPOINT

# Desmonta la tarjeta SD
umount $MOUNTPOINT
yad text --text="Se ha terminado de sincronizar la tarjeta SD"
#rmdir $MOUNTPOINT
