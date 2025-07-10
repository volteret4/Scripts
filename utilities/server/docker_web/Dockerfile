# Music Web Explorer - Dockerfile Unificado
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    nginx \
    sqlite3 \
    rsync \
    openssh-client \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario para la aplicación
RUN useradd -m -s /bin/bash musicapp

# Crear directorios de la aplicación
RUN mkdir -p /app/data /app/music /downloads /app/logs /app/static /app/templates
RUN chown -R musicapp:musicapp /app

# Directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar archivos de la aplicación
COPY app.py music_manager.py config.ini ./
COPY templates/ ./templates/

# Copiar configuraciones
COPY docker/nginx.conf /etc/nginx/sites-available/default
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/entrypoint.sh /entrypoint.sh

# Hacer ejecutable el entrypoint
RUN chmod +x /entrypoint.sh

# Cambiar propietario de archivos de aplicación
RUN chown -R musicapp:musicapp /app

# Configurar nginx
RUN rm /etc/nginx/sites-enabled/default
RUN ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/

# Exponer puertos
EXPOSE 80 5157

# Volúmenes para datos persistentes
VOLUME ["/app/data", "/app/music", "/downloads", "/app/logs"]

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]