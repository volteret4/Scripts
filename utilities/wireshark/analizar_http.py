#!/usr/bin/env python
#
# Script Name: analizar_http.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



#!/usr/bin/env python
#
# Script Name: analizar_http.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



#!/usr/bin/env python


import sys
from scapy.all import *

# Archivos pcap predefinidos
default_files = ["/home/huan/wireshark/http_capture.pcap", "/home/huan/wireshark/https_capture.pcap"]

# Define una función para filtrar paquetes HTTP GET con cadenas de consulta sospechosas
def filter_http(pkt):
    if pkt.haslayer(TCP) and pkt[TCP].dport == 80 and 'GET' in str(pkt[TCP].payload):
        # Extrae la cadena de consulta de la solicitud HTTP GET
        query_string = str(pkt[TCP].payload).split('\r\n')[0].split(' ')[1]
        # Verifica si la cadena de consulta contiene caracteres especiales
        if "'" in query_string or '"' in query_string or ';' in query_string:
            return True
    return False

# Función para analizar un archivo pcap y buscar cadenas de consulta sospechosas
def analyze_pcap(pcap_file):
    # Carga el archivo de captura de red
    pkts = rdpcap(pcap_file)

    # Filtra los paquetes que cumplan el filtro HTTP y la función personalizada
    filtered_pkts = filter(filter_http, pkts)

    # Recorre todos los paquetes filtrados
    for pkt in filtered_pkts:
        # Muestra información del paquete que contiene la cadena de consulta manipulada
        print(f'Paquete sospechoso en el archivo {pcap_file}, puerto {pkt[TCP].sport}:')
        print(pkt.summary())
        print(pkt.show())

# Si no se proporciona un archivo pcap como argumento, se intenta abrir el archivo predefinido
if len(sys.argv) < 2:
    print("Se debe proporcionar al menos un archivo pcap como argumento. Intentando abrir archivo predefinido...")
    pcap_files = default_files
else:
    pcap_files = sys.argv[1:]

# Analiza cada archivo pcap proporcionado
for pcap_file in pcap_files:
    analyze_pcap(pcap_file)