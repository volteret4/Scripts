#!/usr/bin/env python3
import http.server
import socketserver
import os
import sys
import signal
import json
import argparse
import socket
import markdown  # Necesitas instalar: pip install markdown

# Parse command line arguments
parser = argparse.ArgumentParser(description='Simple JSON editor server')
parser.add_argument('--manual', action='store_true', help='Run in manual mode')
parser.add_argument('--follow', type=str, help='Script to run after saving')
parser.add_argument('--args', type=str, help='Arguments for the follow script')
parser.add_argument('--port', type=int, default=8112, help='Port to run the server on')
args = parser.parse_args()

# Configuration
PORT = args.port
CONFIG_FILE = "config.json"
README_FILE = "README.md"
FOLLOW_SCRIPT = args.follow
FOLLOW_ARGS = args.args.split() if args.args else []
MANUAL_MODE = args.manual

# Ensure config file exists
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        f.write('{}')

# Get local IP
try:
    hostname = socket.gethostname()
    IP = socket.gethostbyname(hostname)
except:
    IP = "localhost"

# Create HTML for the editor
EDITOR_HTML = f"""<!DOCTYPE html>
<html>
<head>
    <title>Editor de JSON</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        textarea {{ width: 100%; height: 300px; margin-bottom: 15px; }}
        button {{ padding: 10px 20px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }}
    </style>
</head>
<body>
    <h1>Editor de {CONFIG_FILE}</h1>
    <textarea id="jsonEditor"></textarea>
    <button onclick="guardarJSON()">Guardar y Cerrar Servidor</button>

    <script>
        // Cargar el JSON inicial
        fetch('/{CONFIG_FILE}')
            .then(response => response.text())
            .then(data => {{
                document.getElementById('jsonEditor').value = data;
            }});

        // Función para guardar el JSON
        function guardarJSON() {{
            const jsonData = document.getElementById('jsonEditor').value;
            
            fetch('/save-json', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'text/plain'
                }},
                body: jsonData
            }})
            .then(response => {{
                if(response.ok) {{
                    alert('JSON guardado. Servidor por tabaco. Si elegiste manual, ejecuta el primer script, parguela. python 1_mover_canciones_playlist_spotify --config config.json');
                    window.close();
                }} else {{
                    alert('Error al guardar el JSON');
                }}
            }});
        }}
    </script>
</body>
</html>"""

# HTML template for rendering markdown
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>RADME</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        a {{
            color: #0366d6;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}
        h1 {{
            padding-bottom: 0.3em;
            font-size: 2em;
            border-bottom: 1px solid #eaecef;
        }}
        h2 {{
            padding-bottom: 0.3em;
            font-size: 1.5em;
            border-bottom: 1px solid #eaecef;
        }}
        code {{
            padding: 0.2em 0.4em;
            margin: 0;
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 85%;
            background-color: rgba(27, 31, 35, 0.05);
            border-radius: 3px;
        }}
        pre {{
            padding: 16px;
            overflow: auto;
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 85%;
            line-height: 1.45;
            background-color: #f6f8fa;
            border-radius: 3px;
        }}
        pre code {{
            padding: 0;
            background-color: transparent;
        }}
        blockquote {{
            padding: 0 1em;
            color: #6a737d;
            border-left: 0.25em solid #dfe2e5;
            margin: 0;
        }}
        ul, ol {{
            padding-left: 2em;
        }}
        table {{
            border-spacing: 0;
            border-collapse: collapse;
            width: 100%;
            overflow: auto;
        }}
        table th, table td {{
            padding: 6px 13px;
            border: 1px solid #dfe2e5;
        }}
        table tr {{
            background-color: #fff;
            border-top: 1px solid #c6cbd1;
        }}
        table tr:nth-child(2n) {{
            background-color: #f6f8fa;
        }}
    </style>
</head>
<body>
    {content}
</body>
</html>
"""

# Update README with editor link
if os.path.exists(README_FILE):
    with open(README_FILE, 'r') as f:
        readme_content = f.read()
    if f"http://{IP}:{PORT}/editor.html" not in readme_content:
        readme_content += f"\n\n[Editar archivo de configuración](http://{IP}:{PORT}/editor.html)"
else:
    readme_content = f"# Servidor Temporal\n\n[Editar archivo de configuración](http://{IP}:{PORT}/editor.html)"

# Convert markdown to HTML
html_content = HTML_TEMPLATE.format(
    content=markdown.markdown(
        readme_content, 
        extensions=['fenced_code', 'tables', 'nl2br', 'sane_lists', 'attr_list']
    )
)

should_shutdown = False

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/editor.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(EDITOR_HTML.encode())
        elif self.path == f'/{CONFIG_FILE}':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            with open(CONFIG_FILE, 'rb') as file:
                self.wfile.write(file.read())
        elif self.path.startswith('/.content/') or self.path.startswith('/content/'):
            # Manejar imágenes y otros archivos estáticos
            file_path = self.path[1:]  # Quitar el primer slash
            if os.path.exists(file_path):
                self.send_response(200)
                # Determinar tipo MIME basado en la extensión del archivo
                if file_path.endswith('.png'):
                    self.send_header('Content-type', 'image/png')
                elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                    self.send_header('Content-type', 'image/jpeg')
                elif file_path.endswith('.gif'):
                    self.send_header('Content-type', 'image/gif')
                elif file_path.endswith('.svg'):
                    self.send_header('Content-type', 'image/svg+xml')
                elif file_path.endswith('.css'):
                    self.send_header('Content-type', 'text/css')
                elif file_path.endswith('.js'):
                    self.send_header('Content-type', 'application/javascript')
                else:
                    self.send_header('Content-type', 'application/octet-stream')
                self.end_headers()
                with open(file_path, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                self.send_response(404)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'File not found')
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode())

    def do_POST(self):
        global should_shutdown
        if self.path == '/save-json':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            # Save the JSON data
            with open(CONFIG_FILE, 'w') as file:
                file.write(post_data)
                
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'JSON guardado correctamente.')
            
            # Signal to shutdown the server
            should_shutdown = True

class StoppableHTTPServer(socketserver.TCPServer):
    allow_reuse_address = True
    
    def run(self):
        try:
            self.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.server_close()

def signal_handler(sig, frame):
    print('\nServidor cerrado manualmente')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Start the server
server = StoppableHTTPServer(("", PORT), MyHandler)
print(f"Servidor iniciado en http://{IP}:{PORT}")
print(f"Para acceder al editor de JSON: http://{IP}:{PORT}/editor.html")
print("Presiona Ctrl+C para cerrar manualmente el servidor")

# Server loop with shutdown capability
import threading
server_thread = threading.Thread(target=server.run)
server_thread.daemon = True
server_thread.start()

# Check if shutdown is requested
while not should_shutdown:
    threading.Event().wait(0.1)
    if should_shutdown:
        print("JSON guardado. Cerrando servidor...")
        server.shutdown()
        server.server_close()
        break

# Run follow-up script if needed
if should_shutdown and not MANUAL_MODE and FOLLOW_SCRIPT:
    import subprocess
    print(f"Ejecutando script: {FOLLOW_SCRIPT} {' '.join(FOLLOW_ARGS)}")
    subprocess.run([FOLLOW_SCRIPT] + FOLLOW_ARGS, shell=True)

print("Servidor cerrado")