#!/usr/bin/env python3
"""
API Server para gestionar correos IMAP desde la interfaz HTML
Mantiene sesión abierta y procesa peticiones de marcar como leído y eliminar
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import imaplib
import os
import json
import threading
import time


app = Flask(__name__)
CORS(app)  # Permitir peticiones desde archivos HTML locales

# Almacenamiento de sesiones IMAP (en memoria)
# En producción deberías usar un sistema más robusto (Redis, base de datos, etc.)
sessions = {}
session_lock = threading.Lock()


class IMAPSession:
    """Clase para manejar sesiones IMAP persistentes"""

    def __init__(self, server, port, email, password):
        self.server = server
        self.port = port
        self.email = email
        self.password = password
        self.connection = None
        self.last_activity = time.time()
        self.connect()

    def connect(self):
        """Conecta al servidor IMAP"""
        try:
            if self.port == 993:
                self.connection = imaplib.IMAP4_SSL(self.server, self.port)
            else:
                self.connection = imaplib.IMAP4(self.server, self.port)

            self.connection.login(self.email, self.password)
            print(f"✓ Sesión IMAP creada para {self.email}")
            return True
        except Exception as e:
            print(f"❌ Error conectando IMAP: {e}")
            return False

    def is_alive(self):
        """Verifica si la conexión sigue activa"""
        try:
            self.connection.noop()
            return True
        except:
            return False

    def reconnect(self):
        """Reconecta si la sesión está cerrada"""
        if not self.is_alive():
            print(f"🔄 Reconectando sesión para {self.email}...")
            return self.connect()
        return True

    def mark_as_read(self, folder, email_id):
        """Marca un correo como leído"""
        try:
            self.reconnect()
            self.connection.select(f'"{folder}"')
            self.connection.store(email_id, '+FLAGS', '\\Seen')
            self.last_activity = time.time()
            print(f"✓ Correo {email_id} marcado como leído en {folder}")
            return True
        except Exception as e:
            print(f"❌ Error marcando como leído: {e}")
            return False

    def delete_email(self, folder, email_id):
        """Elimina un correo"""
        try:
            self.reconnect()
            self.connection.select(f'"{folder}"')
            self.connection.store(email_id, '+FLAGS', '\\Deleted')
            self.connection.expunge()
            self.last_activity = time.time()
            print(f"✓ Correo {email_id} eliminado de {folder}")
            return True
        except Exception as e:
            print(f"❌ Error eliminando correo: {e}")
            return False

    def close(self):
        """Cierra la conexión"""
        try:
            if self.connection:
                self.connection.close()
                self.connection.logout()
                print(f"✓ Sesión cerrada para {self.email}")
        except:
            pass


def get_session_key(server, email):
    """Genera una clave única para la sesión"""
    return f"{server}:{email}"


def get_or_create_session(server, port, email, password=None):
    """Obtiene una sesión existente o crea una nueva"""
    session_key = get_session_key(server, email)

    with session_lock:
        # Si la sesión existe y está viva, usarla
        if session_key in sessions:
            session = sessions[session_key]
            if session.is_alive():
                session.last_activity = time.time()
                return session
            else:
                # Sesión muerta, eliminarla
                del sessions[session_key]

        # Crear nueva sesión (requiere contraseña)
        if password is None:
            return None

        session = IMAPSession(server, port, email, password)
        if session.connection:
            sessions[session_key] = session
            return session

        return None


# Limpieza automática de sesiones inactivas
def cleanup_inactive_sessions():
    """Elimina sesiones inactivas (más de 30 minutos sin usar)"""
    while True:
        time.sleep(300)  # Revisar cada 5 minutos

        with session_lock:
            current_time = time.time()
            inactive_keys = []

            for key, session in sessions.items():
                # Si lleva más de 30 minutos inactiva, cerrarla
                if current_time - session.last_activity > 1800:
                    inactive_keys.append(key)

            for key in inactive_keys:
                print(f"🧹 Limpiando sesión inactiva: {key}")
                sessions[key].close()
                del sessions[key]


# Iniciar hilo de limpieza
cleanup_thread = threading.Thread(target=cleanup_inactive_sessions, daemon=True)
cleanup_thread.start()


@app.route('/api/mark-read', methods=['POST'])
def mark_read():
    """Endpoint para marcar un correo como leído"""
    try:
        data = request.json

        server = data.get('server')
        port = data.get('port', 993)
        email = data.get('email')
        password = data.get('password')  # Opcional si ya hay sesión
        email_id = data.get('emailId')
        folder = data.get('folder')

        if not all([server, email, email_id, folder]):
            return jsonify({'error': 'Faltan parámetros'}), 400

        # Obtener o crear sesión
        session = get_or_create_session(server, port, email, password)

        if not session:
            return jsonify({'error': 'No se pudo establecer sesión IMAP'}), 401

        # Marcar como leído
        success = session.mark_as_read(folder, email_id)

        if success:
            return jsonify({'success': True, 'message': 'Marcado como leído'})
        else:
            return jsonify({'error': 'Error al marcar como leído'}), 500

    except Exception as e:
        print(f"❌ Error en /api/mark-read: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-email', methods=['POST'])
def delete_email():
    """Endpoint para eliminar un correo"""
    try:
        data = request.json

        server = data.get('server')
        port = data.get('port', 993)
        email = data.get('email')
        password = data.get('password')  # Opcional si ya hay sesión
        email_id = data.get('emailId')
        folder = data.get('folder')

        if not all([server, email, email_id, folder]):
            return jsonify({'error': 'Faltan parámetros'}), 400

        # Obtener o crear sesión
        session = get_or_create_session(server, port, email, password)

        if not session:
            return jsonify({'error': 'No se pudo establecer sesión IMAP'}), 401

        # Eliminar correo
        success = session.delete_email(folder, email_id)

        if success:
            return jsonify({'success': True, 'message': 'Correo eliminado'})
        else:
            return jsonify({'error': 'Error al eliminar correo'}), 500

    except Exception as e:
        print(f"❌ Error en /api/delete-email: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/create-session', methods=['POST'])
def create_session():
    """Endpoint para crear una sesión IMAP explícitamente"""
    try:
        data = request.json

        server = data.get('server')
        port = data.get('port', 993)
        email = data.get('email')
        password = data.get('password')

        if not all([server, email, password]):
            return jsonify({'error': 'Faltan parámetros (server, email, password)'}), 400

        session = get_or_create_session(server, port, email, password)

        if session:
            return jsonify({
                'success': True,
                'message': 'Sesión creada',
                'session_key': get_session_key(server, email)
            })
        else:
            return jsonify({'error': 'No se pudo crear la sesión'}), 401

    except Exception as e:
        print(f"❌ Error en /api/create-session: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """Lista las sesiones activas (para debugging)"""
    with session_lock:
        active_sessions = []
        for key, session in sessions.items():
            active_sessions.append({
                'key': key,
                'email': session.email,
                'server': session.server,
                'last_activity': time.time() - session.last_activity,
                'alive': session.is_alive()
            })

        return jsonify({
            'count': len(active_sessions),
            'sessions': active_sessions
        })


@app.route('/')
def index():
    """Página de información del API"""
    return """
    <html>
    <head>
        <title>Bandcamp IMAP API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #667eea; }
            code {
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: monospace;
            }
            .endpoint {
                margin: 20px 0;
                padding: 15px;
                background: #f9f9f9;
                border-left: 4px solid #667eea;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 Bandcamp IMAP API Server</h1>
            <p>Servidor API para gestionar correos IMAP desde la colección de Bandcamp</p>

            <h2>Endpoints Disponibles:</h2>

            <div class="endpoint">
                <h3>POST /api/mark-read</h3>
                <p>Marca un correo como leído</p>
                <p><strong>Body:</strong> <code>{ server, port, email, password, emailId, folder }</code></p>
            </div>

            <div class="endpoint">
                <h3>POST /api/delete-email</h3>
                <p>Elimina un correo</p>
                <p><strong>Body:</strong> <code>{ server, port, email, password, emailId, folder }</code></p>
            </div>

            <div class="endpoint">
                <h3>POST /api/create-session</h3>
                <p>Crea una sesión IMAP explícitamente</p>
                <p><strong>Body:</strong> <code>{ server, port, email, password }</code></p>
            </div>

            <div class="endpoint">
                <h3>GET /api/sessions</h3>
                <p>Lista las sesiones activas (debugging)</p>
            </div>

            <h2>Estado:</h2>
            <p>✅ Servidor funcionando en <code>http://localhost:5000</code></p>
            <p>📊 Sesiones activas: Ver <a href="/api/sessions">/api/sessions</a></p>

            <h2>Uso:</h2>
            <p>1. Inicia este servidor: <code>python3 api_server.py</code></p>
            <p>2. Abre tus archivos HTML de Bandcamp en el navegador</p>
            <p>3. Los botones enviarán peticiones a este servidor automáticamente</p>
        </div>
    </body>
    </html>
    """


@app.route('/<path:filename>')
def serve_html(filename):
    """Sirve archivos HTML desde el directorio bandcamp_html"""
    html_dir = 'bandcamp_html'
    if os.path.exists(html_dir):
        return send_from_directory(html_dir, filename)
    return "Directorio bandcamp_html no encontrado", 404


if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 BANDCAMP IMAP API SERVER")
    print("="*80)
    print("\n📡 Iniciando servidor en http://localhost:5000")
    print("🔧 Los botones de acción en los HTML conectarán a este servidor")
    print("💡 Presiona Ctrl+C para detener\n")
    print("="*80 + "\n")

    # Ejecutar servidor
    app.run(host='0.0.0.0', port=5000, debug=True)
