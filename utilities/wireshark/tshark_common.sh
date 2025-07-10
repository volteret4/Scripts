#!/usr/bin/env bash
#
# Script Name: tshark_common.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#


# Configurar la ruta donde se guardarán los archivos de captura
carpeta="${HOME}/wireshark"

# Crear la carpeta si no existe
mkdir -p "${carpeta}"

# Nombre del archivo de captura
archivo="${carpeta}/todas_las_capturas.pcap"

# Duración de la captura en segundos
duracion=180

# Captura de tráfico Telnet
echo "Captura de tráfico Telnet"
tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 23" -w "${archivo}" -F pcap

# Captura de tráfico SSH
echo "Captura de tráfico SSH"
tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 22" -w "${archivo}" -F pcap

# Captura de tráfico SNMP
echo "Captura de tráfico SNMP"
tshark -i wlp5s0 -a duration:"${duracion}" -f "udp port 161" -w "${archivo}" -F pcap

# Captura de tráfico IMAP
echo "Captura de tráfico IMAP"
tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 143" -w "${archivo}" -F pcap

# Captura de tráfico FTP
echo "Captura de tráfico FTP"
tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 21" -w "${archivo}" -F pcap

# Captura de tráfico POP3
echo "Captura de tráfico POP3"
tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 110" -w "${archivo}" -F pcap

# Captura de tráfico SMTP
echo "Captura de tráfico SMTP"
tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 25" -w "${archivo}" -F pcap

# Captura de tráfico DNS
echo "Captura de tráfico DNS"
tshark -i wlp5s0 -a duration:"${duracion}" -f "udp port 53" -w "${archivo}" -F pcap

# Captura de tráfico HTTP
echo "Captura de tráfico HTTP"
tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 80" -w "${archivo}" -F pcap

# Captura de tráfico HTTPS
echo "Captura de tráfico HTTP"
tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 443" -w "${archivo}" -F pcap


#Añadidos

# Captura de tráfico ssh pollo

if [ "$host" = "dietpi" ]; then
    echo "Scanning port 2266 on host $ip..."
    tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 2266" -w "${archivo}" -F pcap
fi

if [ "$host" = "moode" ]; then
    echo "Scanning port 2266 on host $ip..."
    tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 2261" -w "${archivo}" -F pcap
fi

if [ "$host" = "kali" ]; then
    echo "Scanning port 2255 on host $ip..."
    tshark -i wlp5s0 -a duration:"${duracion}" -f "tcp port 2255" -w "${archivo}" -F pcap
fi