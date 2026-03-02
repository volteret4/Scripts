#!/bin/bash

echo "🔍 Verificando el servidor Flask de Música Pollete..."
echo ""

# 1. Verificar que el servidor está corriendo
echo "1. Verificando si el servidor está corriendo en el puerto 5001..."
if curl -s http://192.168.1.133:5001/api/status > /dev/null; then
    echo "✅ Servidor corriendo correctamente"
else
    echo "❌ El servidor NO está respondiendo"
    echo "   Ejecuta: systemctl status musica-pollete"
    exit 1
fi

# 2. Verificar el endpoint de status
echo ""
echo "2. Consultando /api/status..."
STATUS=$(curl -s http://192.168.1.133:5001/api/status)
echo "   Respuesta: $STATUS"

# 3. Verificar que los archivos existen
echo ""
echo "3. Verificando archivos necesarios..."
if [ -f "/opt/musica-pollete/resultado_flacs.json" ]; then
    echo "   ✅ resultado_flacs.json existe"
else
    echo "   ❌ resultado_flacs.json NO encontrado"
fi

if [ -f "/opt/musica-pollete/resumen_flacs.html" ]; then
    echo "   ✅ resumen_flacs.html existe"
else
    echo "   ❌ resumen_flacs.html NO encontrado"
    echo "      Ejecuta: cd /opt/musica-pollete && python3 html_generator.py"
fi

# 4. Verificar la carpeta de descargas
echo ""
echo "4. Verificando carpeta de descargas..."
if [ -d "/mnt/downloads" ]; then
    echo "   ✅ /mnt/downloads existe"
    ls -lh /mnt/downloads | head -5
else
    echo "   ⚠️  /mnt/downloads NO existe - se creará al descargar"
fi

# 5. Verificar nginx
echo ""
echo "5. Verificando configuración de nginx..."
if docker ps | grep -q swag; then
    echo "   ✅ SWAG está corriendo"
    echo "   Verificando logs recientes:"
    docker logs swag --tail 5 2>&1 | grep -i "musica\|error" || echo "   Sin errores relacionados con musica"
else
    echo "   ⚠️  SWAG no está corriendo"
    echo "      Ejecuta: docker restart swag"
fi

# 6. Probar las rutas
echo ""
echo "6. Probando rutas del servidor..."
echo "   GET / :"
curl -s -o /dev/null -w "   HTTP %{http_code}\n" http://192.168.1.133:5001/

echo "   GET /discos_nuevos.html :"
curl -s -o /dev/null -w "   HTTP %{http_code}\n" http://192.168.1.133:5001/discos_nuevos.html

echo "   GET /api/status :"
curl -s -o /dev/null -w "   HTTP %{http_code}\n" http://192.168.1.133:5001/api/status

echo ""
echo "✅ Verificación completa"
echo ""
echo "Si todo está OK, accede a: https://musica.pollete.duckdns.org"
echo "Para ver logs en tiempo real: journalctl -u musica-pollete -f"
