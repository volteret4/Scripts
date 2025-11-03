#!/usr/bin/env python3
"""
Servidor local para marcar correos como leídos en Thunderbird.
Este servidor debe ejecutarse mientras usas el HTML de Bandcamp.

Uso:
    python3 thunderbird_server.py

El servidor escucha en http://localhost:8765
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import mailbox
import os
import re
import shutil
from pathlib import Path


class ThunderbirdHandler(BaseHTTPRequestHandler):
    """Manejador HTTP para las peticiones de marcado de correos."""

    def do_OPTIONS(self):
        """Maneja peticiones OPTIONS para CORS."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        """Maneja peticiones POST para marcar correos como leídos."""
        if self.path == '/mark_read':
            try:
                # Leer el cuerpo de la petición
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                message_id = data.get('message_id')
                mbox_path = data.get('mbox_path')

                if not message_id or not mbox_path:
                    self.send_error_response('Missing message_id or mbox_path')
                    return

                # Intentar marcar el correo como leído
                success = mark_email_as_read(message_id, mbox_path)

                if success:
                    self.send_json_response({'success': True, 'message': 'Email marcado como leído'})
                else:
                    self.send_json_response({'success': False, 'message': 'No se encontró el correo'})

            except Exception as e:
                self.send_error_response(str(e))
        else:
            self.send_error(404)

    def send_json_response(self, data):
        """Envía una respuesta JSON."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, message):
        """Envía una respuesta de error."""
        self.send_json_response({'success': False, 'error': message})

    def log_message(self, format, *args):
        """Personaliza el logging."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def mark_email_as_read_direct(message_id, mbox_path):
    """
    Método alternativo: marca el correo modificando el archivo mbox directamente.
    Este método es más agresivo pero más confiable con Thunderbird.
    """
    try:
        if not os.path.exists(mbox_path):
            print(f"❌ No existe el archivo mbox: {mbox_path}")
            return False

        print(f"📂 Leyendo mbox: {mbox_path}")

        # Leer todo el contenido del mbox
        with open(mbox_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Buscar el mensaje por Message-ID
        # Los mensajes en mbox empiezan con "From "
        messages = content.split('\nFrom ')

        found = False
        modified = False

        for i, msg in enumerate(messages):
            if f'Message-ID: {message_id}' in msg or f'Message-Id: {message_id}' in msg:
                print(f"✓ Mensaje encontrado en posición {i}")

                # Buscar la línea de Status o X-Mozilla-Status
                lines = msg.split('\n')
                has_status = False
                has_xmoz = False

                for j, line in enumerate(lines):
                    # Modificar Status existente
                    if line.startswith('Status:'):
                        has_status = True
                        # Añadir R (Read) si no está
                        if 'R' not in line:
                            lines[j] = line.rstrip() + 'R'
                            print(f"  Modificado Status: {lines[j]}")
                            modified = True

                    # Modificar X-Mozilla-Status (formato de Thunderbird)
                    elif line.startswith('X-Mozilla-Status:'):
                        has_xmoz = True
                        # El status es un número hexadecimal
                        # 0001 = Read, 0002 = Replied, etc.
                        try:
                            status_match = re.search(r'X-Mozilla-Status:\s*([0-9a-fA-F]+)', line)
                            if status_match:
                                current_status = int(status_match.group(1), 16)
                                # Añadir flag de leído (0x0001)
                                new_status = current_status | 0x0001
                                lines[j] = f'X-Mozilla-Status: {new_status:04x}'
                                print(f"  Modificado X-Mozilla-Status: {lines[j]}")
                                modified = True
                        except:
                            pass

                # Si no hay Status, añadirlo después de Message-ID
                if not has_status:
                    for j, line in enumerate(lines):
                        if line.startswith('Message-ID:') or line.startswith('Message-Id:'):
                            lines.insert(j + 1, 'Status: RO')
                            print(f"  Añadido Status: RO")
                            modified = True
                            break

                # Si no hay X-Mozilla-Status, añadirlo
                if not has_xmoz:
                    for j, line in enumerate(lines):
                        if line.startswith('Message-ID:') or line.startswith('Message-Id:'):
                            lines.insert(j + 1, 'X-Mozilla-Status: 0001')
                            print(f"  Añadido X-Mozilla-Status: 0001")
                            modified = True
                            break

                # Reconstruir el mensaje
                messages[i] = '\n'.join(lines)
                found = True
                break

        if not found:
            print(f"⚠️  No se encontró el correo")
            return False

        if not modified:
            print(f"ℹ️  El correo ya estaba marcado como leído")
            return True

        # Guardar el mbox modificado
        print(f"💾 Guardando cambios...")

        # Hacer backup primero
        backup_path = mbox_path + '.backup'
        import shutil
        shutil.copy2(mbox_path, backup_path)
        print(f"  Backup creado: {backup_path}")

        # Escribir el nuevo contenido
        new_content = '\nFrom '.join(messages)
        with open(mbox_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✅ Correo marcado como leído (método directo)")
        return True

    except Exception as e:
        print(f"❌ Error en método directo: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def mark_email_as_read(message_id, mbox_path):
    """
    Marca un correo como leído en el archivo mbox de Thunderbird.
    Intenta primero el método estándar, y si falla usa el método directo.

    Args:
        message_id: El Message-ID del correo
        mbox_path: Ruta al archivo mbox

    Returns:
        bool: True si se marcó correctamente, False si no se encontró
    """
    print(f"\n{'='*70}")
    print(f"📧 Marcando correo como leído")
    print(f"{'='*70}")

    # Intentar método estándar primero
    print(f"\n🔧 Método 1: Usando mailbox.mbox...")

    try:
        if not os.path.exists(mbox_path):
            print(f"❌ No existe el archivo mbox: {mbox_path}")
            return False

        print(f"📂 Abriendo mbox: {mbox_path}")

        # Abrir el mbox con lock para evitar conflictos
        mbox = mailbox.mbox(mbox_path, create=False)
        mbox.lock()

        try:
            # Buscar el mensaje por Message-ID
            found = False

            print(f"🔍 Buscando correo con Message-ID: {message_id[:50]}...")

            for key, message in mbox.items():
                msg_id = message.get('Message-ID', '')
                if msg_id == message_id:
                    print(f"✓ Correo encontrado!")
                    print(f"  Asunto: {message.get('Subject', 'Sin asunto')[:60]}")
                    print(f"  Flags actuales: '{message.get_flags()}'")

                    # Añadir flags de leído
                    if 'R' not in message.get_flags():
                        message.add_flag('R')
                    if 'S' not in message.get_flags():
                        message.add_flag('S')

                    # Actualizar el mensaje en el mbox
                    mbox[key] = message

                    print(f"  Flags después: '{message.get_flags()}'")

                    found = True
                    break

            if not found:
                print(f"⚠️  No se encontró el correo")
                return False

            # Hacer flush explícito de los cambios
            print(f"💾 Guardando cambios...")
            mbox.flush()

            print(f"✅ Correo marcado como leído (método estándar)")
            return True

        finally:
            # Siempre desbloquear y cerrar el mbox
            mbox.unlock()
            mbox.close()
            print(f"🔓 Mbox cerrado")

    except Exception as e:
        print(f"⚠️  Método estándar falló: {type(e).__name__}: {e}")
        print(f"\n🔧 Método 2: Modificación directa del archivo...")

        # Intentar método directo
        return mark_email_as_read_direct(message_id, mbox_path)


def main():
    """Inicia el servidor."""
    host = 'localhost'
    port = 8765

    server = HTTPServer((host, port), ThunderbirdHandler)

    print("="*70)
    print("🚀 Servidor de Thunderbird iniciado")
    print("="*70)
    print(f"📡 Escuchando en: http://{host}:{port}")
    print(f"📧 Listo para marcar correos como leídos")
    print()
    print("⚠️  IMPORTANTE:")
    print("   • Cierra Thunderbird ANTES de marcar correos")
    print("   • Si Thunderbird está abierto, puede no reflejar los cambios")
    print("   • Los cambios son permanentes en los archivos mbox")
    print("   • Se crean backups automáticos (.backup)")
    print()
    print("💡 Flujo recomendado:")
    print("   1. Cierra Thunderbird")
    print("   2. Inicia este servidor")
    print("   3. Abre tu colección de Bandcamp en el navegador")
    print("   4. Marca discos como 'Escuchado'")
    print("   5. Detén el servidor (Ctrl+C)")
    print("   6. Abre Thunderbird para ver los cambios")
    print()
    print("🔧 Métodos de marcado:")
    print("   1. mailbox.mbox (estándar)")
    print("   2. Modificación directa (si falla el primero)")
    print()
    print("⚠️  No cierres esta ventana mientras uses la colección")
    print("   Presiona Ctrl+C para detener el servidor")
    print("="*70)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Servidor detenido")
        print("✓ Los correos marcados permanecerán como leídos")
        print("ℹ️  Abre Thunderbird para verificar los cambios")
        server.shutdown()


if __name__ == '__main__':
    main()
