#!/usr/bin/env python
#
# Script Name: analizar_http_files2.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

import os
import argparse

def is_file_empty(file_path):
    """
    Comprueba si un archivo está vacío.
    """
    return os.stat(file_path).st_size == 0

def analyze_pcap(pcap_file):
    """
    Analiza un archivo pcap y muestra los paquetes HTTP, TLS y DNS.
    """
    print(f"Analizando archivo: {pcap_file}")

    # Comprobar si el archivo está vacío
    if is_file_empty(pcap_file):
        print("Archivo vacío:", pcap_file)
        return

    # Ejecutar tshark para filtrar paquetes
    filter_str = "tcp port 23 or (tcp port 80 and (http.request.method == 'POST' or http.request.method == 'GET' or http.request.method == 'HEAD')) or (tcp port 443 and (tls.handshake.type == 1 or tls.handshake.type == 2)) or (udp port 53 and dns.qry.type == 1)"
    cmd = f"tshark -r {pcap_file} -Y '{filter_str}' -T fields -e ip.src -e ip.dst -e tcp.srcport -e tcp.dstport -e http.request.method -e http.host -e http.request.uri -e tls.handshake.type -e dns.qry.name"
    result = os.popen(cmd).read().splitlines()

    # Contador de casos encontrados
    num_cases = 0

    # Analizar paquetes
    for line in result:
        fields = line.split('\t')
        src_ip, dst_ip, src_port, dst_port, http_method, http_host, http_path, tls_type, dns_name = fields

        # Analizar HTTP
        if http_method:
            print(f"    - Paquete HTTP: {src_ip}:{src_port} -> {dst_ip}:{dst_port} {http_method} {http_host}{http_path}")
            num_cases += 1

        # Analizar TLS
        elif tls_type:
            print(f"    - Paquete TLS: {src_ip}:{src_port} -> {dst_ip}:{dst_port} {tls_type}")
            num_cases += 1

        # Analizar DNS
        elif dns_name:
            print(f"    - Paquete DNS: {src_ip}:{src_port} -> {dst_ip}:{dst_port} {dns_name}")
            num_cases += 1

    # Imprimir el número de casos encontrados
    print(f"    - Número de casos encontrados: {num_cases}")


if __name__ == "__main__":
    # Argumentos de línea de comandos
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Archivo pcap a analizar")
    args = parser.parse_args()

    # Archivos a analizar
    if args.file:
        pcap_files = [args.file]
    else:
        pcap_folder = "/home/huan/wireshark/"
        pcap_files = [os.path.join(pcap_folder, f) for f in os.listdir(pcap_folder) if f.endswith(".pcap")]

    # Analizar cada archivo
    for pcap_file in pcap_files:
        analyze_pcap(pcap_file)