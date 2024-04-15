#!/usr/bin/env python
#
# Script Name: server.py 
# Description: open a temporal file server on the folder executed.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#


import http.server
import socketserver

PORT = 678

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print("Servidor temporal en el puerto", PORT)
    httpd.serve_forever()
