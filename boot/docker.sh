#!/usr/bin/env bash
#
# Script Name: install_docker.sh
# Description: Install docker on debian based systems
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: Adapt for arch systems 
# Notes:
#

echo 'Actualizando repositorios'
apt update -y && apt upgrade -y
echo 'Descargando Docker'
curl -fsSL test.docker.com -o get-docker.sh
echo 'Instalando Docker'
sh get-docker.sh
sleep 5
echo 'Espera 5 segundos'
echo 'Elegir y añadir Usuario no root al grupo docker'
user=$(zenity --list \
                    --title="usuarios" \
                    --height=200 \
                    --width=100 \
                    --ok-label="Aceptar" \
                    --cancel-label="Cancelar" \
                    --text="Selecciona un usuario:" \
                    --radiolist \
                    --column="" \
                    --column="Componente" \
                    1 "huan" 2 "hulio" 3 "dietpi" 4 "pi")
ans=$?
if [ $ans -eq 0 ]
then
    echo "Has elegido: ${user}"
else
    echo "No has elegido ningún componente"
fi
echo 'Creando usuarios y grupos'
groupadd docker
usermod -aG docker "${user}"
newgrp docker
chown "${user}":"${user}" /home/"${user}"/.docker -R
chmod g+rwx "/home/${user}/.docker" -R

echo 'activando servicios systemd'
systemctl enable docker.service
systemctl enable containerd.service

echo 'instalando docker-compose'
apt-get install libffi-dev libssl-dev
apt install python3-dev
apt-get install -y python3 python3-pip
pip3 install docker-compose
echo'chimpún'
