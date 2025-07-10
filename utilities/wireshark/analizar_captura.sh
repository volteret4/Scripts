#!/usr/bin/env bash
#
# Script Name: analizar_captura.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#


# Ruta del archivo PCAP a analizar
pcap_file="/home/huan/wireshark/todas_las_capturas.pcap"

# Análisis de amenazas en DNS
echo "DNS WARNINGS:"
tshark -r "$pcap_file" -Y "dns.flags.rcode != 0" -T fields -e dns.qry.name | sort | uniq -c | sort -rn | head -n 5

# Análisis de amenazas en HTTP
echo "HTTP WARNINGS:"
tshark -r "$pcap_file" -Y "http.request.method == GET" -T fields -e http.host -e http.request.uri | sort | uniq -c | sort -rn | head -n 5

# Análisis de amenazas en HTTPS
echo "HTTPS WARNINGS:"
tshark -r "$pcap_file" -Y "ssl.handshake.type == 1" -T fields -e ssl.handshake.extensions_server_name | sort | uniq -c | sort -rn | head -n 5

# Análisis de amenazas en Telnet
echo "TELNET WARNINGS:"
tshark -r "$pcap_file" -Y "telnet" -T fields -e telnet.data | sort | uniq -c | sort -rn | head -n 5

# Análisis de amenazas en SSH
echo "SSH WARNINGS:"
tshark -r "$pcap_file" -Y "ssh" -T fields -e ssh.version | sort | uniq -c | sort -rn | head -n 5

# Análisis de amenazas en SNMP
echo "SNMP WARNINGS:"
tshark -r "$pcap_file" -Y "snmp" -T fields -e snmp.community | sort | uniq -c | sort -rn | head -n 5

# Análisis de amenazas en IMAP
echo "IMAP WARNINGS:"
tshark -r "$pcap_file" -Y "imap" -T fields -e imap.command.data | sort | uniq -c | sort -rn | head -n 5

# Análisis de amenazas en FTP
echo "FTP WARNINGS:"
tshark -r "$pcap_file" -Y "ftp" -T fields -e ftp.request.command | sort | uniq -c | sort -rn | head -n 5

# Análisis de amenazas en POP3
echo "POP3 WARNINGS:"
tshark -r "$pcap_file" -Y "pop" -T fields -e pop.command.data | sort | uniq -c | sort -rn | head -n 5