#!/usr/bin/env bash
#
# Script Name: tcpdump_captures.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#


carpeta="/home/huan/wireshark"

# Función para mostrar la barra de progreso
function progress_bar() {
    local duration=${1}

    # Calcula la proporción de la barra que se debe llenar cada segundo
    local increment=$((100 / duration))

    for (( elapsed=1; elapsed<=duration; elapsed++ )); do
        # Imprime la barra de progreso
        printf "["
        for (( progress=0; progress<elapsed*increment; progress+=2 )); do
            printf "#"
        done
        for (( remain=progress; remain<100; remain+=2 )); do
            printf "-"
        done
        printf "] %s/%s segundos\r" "${elapsed}" "${duration}"
        sleep 1
    done
    echo -e
}

# Captura de tráfico HTTP durante 180 segundos
echo -e "\n \033[1m\033[4mCapturando tráfico HTTP...\033[0m \n"
tcpdump -i wlp5s0 port 80 -w "${carpeta}/http_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico HTTPS durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico HTTPS...\033[0m\n"
tcpdump -i wlp5s0 port 443 -w "${carpeta}/https_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico DNS durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico DNS...\033[0m \n"
tcpdump -i wlp5s0 port 53 -w "${carpeta}/dns_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico SMTP durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico SMTP...\033[0m \n"
tcpdump -i wlp5s0 port 25 -w "${carpeta}/smtp_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico POP3 durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico POP3...\033[0m \n"
tcpdump -i wlp5s0 port 110 -w "${carpeta}/pop3_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico IMAP durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico IMAP...\033[0m \n"
tcpdump -i wlp5s0 port 143 -w "${carpeta}/imap_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico FTP durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico FTP...\033[0m \n"
tcpdump -i wlp5s0 port 21 -w "${carpeta}/ftp_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico Telnet durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico Telnet...\033[0m \n"
tcpdump -i wlp5s0 port 23 -w "${carpeta}/telnet_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico SSH durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico SSH...\033[0m \n"
tcpdump -i wlp5s0 port 22 -w "${carpeta}/ssh_capture.pcap" -G 180 -W 1 &
progress_bar 180

# Captura de tráfico SNMP durante 180 segundos
echo -e "/n \033[1m\033[4mCapturando tráfico SNMP...\033[0m \n"
tcpdump -i wlp5s0 port 161 -w ${carpeta}/snmp_capture.pcap -G 180 -W 1 &

echo -e "/n \033[1m\033[5m\033[4m\033[31m¡Captura finalizada!\033[0m \n"