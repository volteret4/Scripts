#!/usr/bin/env python
#
# Script Name: analizar_http_404.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



#!/usr/bin/env python
#
# Script Name: analizar_http_404.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#



#!/usr/bin/env python

import sys
from scapy.all import *

# Rutas a los archivos por defecto
FILE1_PATH = '/home/huan/wireshark/http_capture.pcap'
FILE2_PATH = '/home/huan/wireshark/https_capture.pcap'

def analyze_pcap(filename, default_file=False):
    if default_file:
        print(f'Analizando archivo por defecto: {filename}')
    else:
        print(f'Analizando archivo: {filename}')

    pkts = rdpcap(filename)

    for pkt in pkts:
        if pkt.haslayer(TCP) and pkt.haslayer(Raw) and pkt.haslayer(IP):
            if pkt[TCP].dport == 80 or pkt[TCP].sport == 80 or pkt[TCP].dport == 443 or pkt[TCP].sport == 443:
                raw = str(pkt[Raw].load)
                ip_src = pkt[IP].src
                ip_dst = pkt[IP].dst
                tcp_src = pkt[TCP].sport
                tcp_dst = pkt[TCP].dport

                # Analiza los encabezados personalizados sospechosos
                if 'X-Forwarded-For' in raw:
                    print(f'[!] POSIBLE ATAQUE CON X-Forwarded-For: {ip_src}:{tcp_src} -> {ip_dst}:{tcp_dst} [{filename}]')

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        for filename in sys.argv[1:]:
            analyze_pcap(filename)
    else:
        analyze_pcap(FILE1_PATH, default_file=True)
        analyze_pcap(FILE2_PATH, default_file=True)