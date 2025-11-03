# Ejemplos de Configuración por Proveedor

## 🔵 Gmail

### Preparación:

1. Ir a https://myaccount.google.com/security
2. Activar "Verificación en dos pasos"
3. Ir a "Contraseñas de aplicaciones" (https://myaccount.google.com/apppasswords)
4. Crear una contraseña para "Correo"
5. Copiar la contraseña de 16 caracteres

### Configuración:

```bash
Servidor: imap.gmail.com
Puerto: 993
Email: tu_email@gmail.com
Contraseña: [Contraseña de aplicación de 16 caracteres]
```

### Ejemplo de comando:

```bash
python3 bc_html_generator_imap.py \
  --server imap.gmail.com \
  --email mimusica@gmail.com \
  --folders "INBOX:General" "Music:Rock"
```

### Estructura de carpetas típica en Gmail:

- `INBOX` - Bandeja de entrada
- `[Gmail]/Sent Mail` - Enviados
- `[Gmail]/Drafts` - Borradores
- Tus etiquetas aparecen como carpetas

---

## 🔷 Outlook / Hotmail / Live.com

### Preparación:

1. No necesita contraseña de aplicación especial
2. Usa tu contraseña normal
3. Si tienes verificación en dos pasos, puede que necesites una contraseña de aplicación

### Configuración:

```bash
Servidor: imap-mail.outlook.com
Puerto: 993
Email: tu_email@outlook.com
Contraseña: [Tu contraseña normal]
```

### Ejemplo de comando:

```bash
python3 bc_html_generator_imap.py \
  --server imap-mail.outlook.com \
  --email mimusica@outlook.com \
  --folders "Inbox:General"
```

### Estructura de carpetas típica en Outlook:

- `Inbox` - Bandeja de entrada
- `Sent` - Enviados
- `Drafts` - Borradores
- `Archive` - Archivo

---

## 🟣 Yahoo Mail

### Preparación:

1. Ir a https://login.yahoo.com/account/security
2. Activar "Generar contraseña de aplicación"
3. Crear una contraseña para "Otra aplicación"
4. Usar esa contraseña

### Configuración:

```bash
Servidor: imap.mail.yahoo.com
Puerto: 993
Email: tu_email@yahoo.com
Contraseña: [Contraseña de aplicación]
```

### Ejemplo de comando:

```bash
python3 bc_html_generator_imap.py \
  --server imap.mail.yahoo.com \
  --email mimusica@yahoo.com \
  --folders "Inbox:General"
```

---

## ⚪ iCloud Mail

### Preparación:

1. Ir a https://appleid.apple.com
2. Sección "Seguridad"
3. Generar contraseña específica de app
4. Usar esa contraseña

### Configuración:

```bash
Servidor: imap.mail.me.com
Puerto: 993
Email: tu_email@icloud.com
Contraseña: [Contraseña específica de app]
```

### Ejemplo de comando:

```bash
python3 bc_html_generator_imap.py \
  --server imap.mail.me.com \
  --email mimusica@icloud.com \
  --folders "INBOX:General"
```

---

## 🟠 Otros proveedores comunes

### AOL Mail

```bash
Servidor: imap.aol.com
Puerto: 993
```

### GMX

```bash
Servidor: imap.gmx.com
Puerto: 993
```

### Mail.com

```bash
Servidor: imap.mail.com
Puerto: 993
```

### Zoho Mail

```bash
Servidor: imap.zoho.com
Puerto: 993
```

### ProtonMail (Bridge requerido)

```bash
Servidor: 127.0.0.1
Puerto: 1143
Nota: Requiere ProtonMail Bridge instalado y ejecutándose
```

---

## 📝 Consejos generales

### Encontrar configuración IMAP de tu proveedor:

1. Busca en Google: "[tu proveedor] IMAP settings"
2. Busca en la ayuda de tu proveedor de email
3. Generalmente es: `imap.[proveedor].com` puerto `993`

### Problemas comunes:

**"Authentication failed"**

- Verifica email y contraseña
- Para Gmail/Yahoo/iCloud: usa contraseña de aplicación
- Verifica que IMAP esté activado en tu cuenta

**"Connection refused"**

- Verifica el servidor y puerto
- Verifica tu conexión a internet
- Algunos proveedores requieren activar IMAP en configuración

**"Timeout"**

- Tu proveedor puede estar bloqueando la conexión
- Verifica firewall/antivirus
- Intenta con otro puerto si está disponible

### Activar IMAP en proveedores comunes:

**Gmail:**

- Configuración → Ver todos los ajustes → Reenvío y correo POP/IMAP → Activar IMAP

**Outlook:**

- IMAP está activado por defecto

**Yahoo:**

- Configuración → Más opciones → Buzones de correo → Acceso IMAP → Activar

---

## 🔐 Seguridad

**IMPORTANTE:**

- Nunca compartas tus contraseñas
- Usa contraseñas de aplicación cuando estén disponibles
- No uses el parámetro `--password` en scripts guardados
- Revoca contraseñas de aplicación si dejas de usar el script

---

## 🎯 Ejemplo completo paso a paso (Gmail)

```bash
# 1. Listar carpetas disponibles
python3 bc_html_generator_imap.py \
  --server imap.gmail.com \
  --email mimusica@gmail.com \
  --list-folders

# 2. Una vez que veas tus carpetas, procesarlas
python3 bc_html_generator_imap.py \
  --server imap.gmail.com \
  --email mimusica@gmail.com \
  --folders \
    "INBOX/Bandcamp/Rock:Rock" \
    "INBOX/Bandcamp/Electronic:Electronic" \
    "INBOX/Bandcamp/Jazz:Jazz" \
  --output-dir mi_coleccion \
  --items-per-page 12

# 3. Abrir el resultado
# Navega a: mi_coleccion/index.html
```

---

## ℹ️ Notas adicionales

- Todos estos ejemplos usan SSL/TLS (puerto 993)
- La mayoría de proveedores modernos requieren SSL
- Si tu proveedor usa un puerto diferente, especifícalo con `--port`
- El script detecta automáticamente la estructura de carpetas de cada proveedor
