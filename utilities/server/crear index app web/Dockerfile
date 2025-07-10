FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    lsof \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
RUN pip install --no-cache-dir requests psutil

# Copiar archivos del proyecto
COPY dashboard_generator.py .
COPY dashboard_extensions.py* ./
COPY config.py* ./

# Crear script de entrada
COPY <<EOF /app/docker-entrypoint.sh
#!/bin/bash
echo "🚀 Iniciando Dashboard Generator"
echo "   Intervalo de actualización: \${UPDATE_INTERVAL:-300} segundos"

while true; do
    echo "🔄 Actualizando dashboard - \$(date)"
    python dashboard_generator.py
    
    if [ \$? -eq 0 ]; then
        echo "✅ Dashboard actualizado correctamente"
    else
        echo "❌ Error actualizando dashboard"
    fi
    
    echo "⏳ Esperando \${UPDATE_INTERVAL:-300} segundos..."
    sleep \${UPDATE_INTERVAL:-300}
done
EOF

RUN chmod +x /app/docker-entrypoint.sh

CMD ["/app/docker-entrypoint.sh"]