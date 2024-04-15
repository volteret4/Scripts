#!/usr/bin/env python
#
# Script Name: analizar_http_fuerza_bruta.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

import argparse
from scapy.all import *

# Variables de archivo
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
    pkts = rdpcap(filename)

    # Muestra la línea correspondiente al archivo analizado
    if default_file:
        print(f'Analizando archivo de captura por defecto: {filename}')
    else:
        print(f'Analizando archivo de captura: {filename}')

    # Recorre todos los paquetes que cumplan el filtro HTTP
    for pkt in pkts.filter(filter_http):
        # Muestra información del paquete sospechoso
        print(f'Paquete sospechoso en el puerto {pkt[TCP].sport}:')
        print(pkt.summary())
        print(pkt.show())


def main():
    # Configura la línea de comandos y los argumentos
    parser = argparse.ArgumentParser(description='Analiza un archivo de captura pcap para detectar solicitudes de archivos o recursos no autorizados o fuera de lugar.')
    parser.add_argument('filename', nargs='*', help='nombre del archivo de captura pcap a analizar')
    args = parser.parse_args()

    # Analiza los archivos especificados o los archivos predeterminados
    if args.filename:
        for filename in args.filename:
            analyze_pcap(filename)
    else:
        analyze_pcap(FILE1_PATH, default_file=True)
        analyze_pcap(FILE2_PATH, default_file=True)


if __name__ == '__main__':
    main()