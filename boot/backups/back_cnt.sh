#!/usr/bin/env bash
#
# Script Name: back_cnt.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#




fecha=$(date +"%d-%m-%y")

cd $HOME/contenedores/backups_contenedores


# docker commit -p transmission transmission.bak
# docker save -o transmission.$fecha.tar transmission.bak
# echo "transmission"
# docker commit -p lidarr lidarr.bak
# docker save -o lidarr.$fecha.tar lidarr.bak
# echo "lidarr"
# docker commit -p portainer portainer.bak
# docker save -o portainer.$fecha.tar portainer.bak
# echo "portainer"
# docker commit -p jackett jackett.bak
# docker save -o jackett.$fecha.tar jackett.bak
# echo "jackett"
docker commit -p duplicati duplicati.bak
docker save -o duplicati.$fecha.tar duplicati.bak
echo "duplicati"
# docker commit -p syncthing syncthing.bak
# docker save -o syncthing.$fecha.tar syncthing.bak
# echo "syncthing"
docker commit -p radicale radicale.bak
docker save -o radicale.$fecha.tar radicale.bak
echo "radicale"
docker commit -p wallabag wallabag.bak
docker save -o wallabag.$fecha.tar wallabag.bak
echo "wallabag"
# docker commit -p ttrss ttrss.bak
# docker save -o ttrss.$fecha.tar ttrss.bak
# echo "ttrss"
# docker commit -p mercury mercury.bak
# docker save -o mercury.$fecha.tar mercury.bak
# echo "mercury"
# docker commit -p wireguard wireguard.bak
# docker save -o wireguard.$fecha.tar wireguard.bak
# echo "wireguard"
docker commit -p postgres postgres.bak
docker save -o postgres.$fecha.tar postgres.bak
echo "postgres"
