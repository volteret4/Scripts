#!/usr/bin/env python
#
# Script Name: server.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#

import http.server
import socketserver

PORT = 678

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print("Servidor temporal en el puerto", PORT)
    httpd.serve_forever()
