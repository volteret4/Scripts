#!/usr/bin/env python
#
# Script Name: analizar_http_iny_codigo.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#

from scapy.all import *


# Rutas a los archivos por defecto
FILE1_PATH = '/home/huan/wireshark/http_capture.pcap'
FILE2_PATH = '/home/huan/wireshark/https_capture.pcap'

def filter_http(pkt):
    if pkt.haslayer(TCP) and pkt[TCP].dport == 80 and pkt.haslayer(Raw):
        # Verifica si es una solicitud HTTP GET
        if 'GET' in str(pkt[TCP].payload):
            # Extrae la cadena de consulta de la solicitud HTTP GET
            query_string = str(pkt[TCP].payload).split('\r\n')[0].split(' ')[1]
            # Verifica si la cadena de consulta contiene caracteres especiales
            if "'" in query_string or '"' in query_string or ';' in query_string or '%' in query_string or '%2F' in query_string or 'script' in query_string or 'iframe' in query_string or 'ping' in query_string or 'ls' in query_string:
                return True
        # Verifica si es una solicitud HTTP POST con encabezado personalizado
        elif 'POST' in str(pkt[TCP].payload) and 'X-Inject-Code' in str(pkt[TCP].payload):
            # Verifica si el encabezado personalizado contiene un comando SQL
            if 'SELECT' in str(pkt[TCP].payload) or 'DELETE' in str(pkt[TCP].payload):
                return True
    return False


def analyze_pcap(filename, default_file=False):
    # Carga el archivo de captura de red
    if default_file:
        pkts = rdpcap(FILE1_PATH)
    else:
        pkts = rdpcap(filename)

    # Recorre todos los paquetes que cumplan el filtro HTTP
    for pkt in pkts.filter(filter_http):
        # Muestra información del paquete sospechoso
        print(f'Paquete sospechoso en el puerto {pkt[TCP].sport}:')
        print(pkt.summary())
        print(pkt.show())

    # Indica que se está analizando un archivo por defecto
    if default_file:
        print(f"Analizando archivo de captura por defecto: {filename}")


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 2:
        print(f'Usage: {sys.argv[0]} [filename.pcap]')
        sys.exit(1)

    filename = None
    if len(sys.argv) == 2:
        filename = sys.argv[1]

    # Analiza el archivo de captura especificado o el archivo de captura por defecto
    if filename:
        analyze_pcap(filename)
    else:
        analyze_pcap(FILE1_PATH, default_file=True)
        analyze_pcap(FILE2_PATH, default_file=True)