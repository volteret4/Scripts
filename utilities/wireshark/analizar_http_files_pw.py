#!/usr/bin/env python
#
# Script Name: analizar_http_files_pw.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#


import argparse
import os
from scapy.all import *

# Filtros para detectar ataques
FILTERS = [
    "tcp port 23", # Telnet
    "tcp port 21", # FTP
    "tcp port 22", # SSH
    "tcp port 80", # HTTP
    "tcp port 443", # HTTPS
    "ip and not icmp", # Ping of Death
    "tcp[tcpflags] & (tcp-syn|tcp-fin) != 0", # SYN/FIN flood
    "udp and ((ip[2:4] - udp[8:10]) > 0)", # UDP flood
    "ip proto 50 or ip proto 51" # IPSec
]

def filter_http(pkt):
    """
    Función de filtro para HTTP
    """
    if pkt.haslayer(TCP) and pkt.haslayer(Raw):
        if pkt[TCP].dport == 80 and b"GET" in pkt[Raw].load:
            return True
        elif pkt[TCP].dport == 443 and pkt.haslayer(SSL):
            return True
    return False

def analyze_pcap(pcap_file):
    """
    Analiza un archivo pcap en busca de paquetes maliciosos
    """
    pkts = rdpcap(pcap_file)
    print(f"Analizando archivo {pcap_file}...")
    for filter_str in FILTERS:
        print(f"Buscando paquetes con filtro: {filter_str}")
        pkts_filtered = pkts.filter(filter_str)
        if len(pkts_filtered) > 0:
            print(f"Se han encontrado {len(pkts_filtered)} paquetes maliciosos:")
            for pkt in pkts_filtered:
                print(pkt.summary())
        else:
            print("No se han encontrado paquetes maliciosos.")

    # Buscar intentos de carga remota de archivos
    filter_file = "file=//"
    pkts_filtered = pkts.filter(filter_http)
    if len(pkts_filtered) > 0:
        print(f"Se han encontrado {len(pkts_filtered)} intentos de carga remota de archivos:")
        for pkt in pkts_filtered:
            if filter_file.encode() in pkt[Raw].load:
                print(pkt.summary())
    else:
        print("No se han encontrado intentos de carga remota de archivos.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analizar archivos pcap en busca de paquetes maliciosos.")
    parser.add_argument("-f", "--file", help="archivo pcap a analizar")
    args = parser.parse_args()

    if args.file:
        analyze_pcap(args.file)
    else:
        # Analizar los archivos especificados en estas variables
        pcap_files = ["/home/huan/wireshark/http_capture.pcap", "/home/huan/wireshark/https_capture.pcap"]
        for pcap_file in pcap_files:
            if os.path.isfile(pcap_file):
                analyze_pcap(pcap_file)
            else:
                print(f"No se ha encontrado el archivo {pcap_file}.")