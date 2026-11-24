#!/usr/bin/env bash
#
# Script Name: migrar_sda_ext4.sh
# Description: Une las dos particiones exFAT del SSD SATA en una sola ext4 montada en /mnt/windows.
# Author: volteret4
# Notes:
#   Se ejecuta por fases, en este orden, con sudo. Ninguna fase lanza la siguiente:
#
#     comprobar            solo lectura: discos, SMART, espacio, procesos, colisiones
#     copiar-ppp           copia el contenido de /mnt/Datos al NVMe y lo verifica
#     formatear-externo    DESTRUCTIVO, opcional: vacía el HGST USB y crea una ext4 en /mnt/externo
#     copia-externa RUTA   opcional: otra copia verificada en un disco externo ya montado
#     descartar-datos      opcional: borra la copia del NVMe y lo de /mnt/Datos ya no se restaura
#     preparar-windows     para syncthing, borra SteamLibrary y hace el manifiesto de /mnt/windows
#     formatear-sda2       DESTRUCTIVO: crea ext4 en sda2 (borra /mnt/Datos)
#     copiar-a-ext4        copia /mnt/windows y lo de /mnt/Datos a la ext4 y lo verifica
#     finalizar            DESTRUCTIVO: borra sda3, amplía sda2, cambia fstab, monta en /mnt/windows
#     limpiar              borra las copias temporales del NVMe
#
#   Cada fase destructiva exige que la verificación anterior haya terminado bien y una
#   confirmación escrita. Las particiones se reconocen por UUID y modelo de disco, no por
#   sda2/sda3, porque la letra puede cambiar al conectar discos externos.
#
#   Los permisos se conservan (777, como en exFAT) para que syncthing no vea cambios en todo.
#
# Uso: sudo bash migrar_sda_ext4.sh FASE

set -euo pipefail
export LC_ALL=C

USUARIO=huan
UUID_DATOS=C437-CEE9
UUID_WINDOWS=A26A-AAE7
MODELO=CT500MX500SSD1
# Por modelo y tamaño: el número de serie es del adaptador USB y lo comparte con el disco de backup
MODELO_EXTERNO=545050A7E680
TAMANO_EXTERNO=500107862016
MONTAJE_EXTERNO=${MONTAJE_EXTERNO:-/mnt/externo}

RAIZ_DATOS=${RAIZ_DATOS:-/mnt/Datos}
RAIZ_WINDOWS=${RAIZ_WINDOWS:-/mnt/windows}
NUEVO=${NUEVO:-/mnt/windows_nuevo}
TMP_A=${TMP_A:-/home/$USUARIO/.migrar_sda/ppp_a}   # hasta LIMITE_A bytes, en /home
TMP_B=${TMP_B:-/var/migrar_sda/ppp_b}              # el resto, en /
ESTADO=${ESTADO:-/home/$USUARIO/.local/state/migrar_sda}
LIMITE_A=${LIMITE_A:-$((50 * 1024 ** 3))}
MODO_PRUEBA=${MODO_PRUEBA:-0}                      # sin discos reales: solo copias y verificación

RSYNC_EXCLUIR=(--exclude='/$RECYCLE.BIN' --exclude='/System Volume Information'
               --exclude='/DumpStack.log.tmp' --exclude='/SteamLibrary')

error() { echo "ERROR: $*" >&2; exit 1; }
paso() { echo; echo "== $*"; }
requiere() { [ -e "$ESTADO/$1" ] || error "falta terminar antes la fase «$2»"; }
hecho() { touch "$ESTADO/$1"; echo "OK: $2"; }

confirmar() {
    [ "$MODO_PRUEBA" = 1 ] && return 0
    local respuesta
    echo
    echo "$1"
    read -r -p "Escribe exactamente «$2» para continuar: " respuesta
    [ "$respuesta" = "$2" ] || error "cancelado, no se ha tocado nada"
}

# Archivos de un árbol, sin lo que dejó Windows ni SteamLibrary. $1: -printf o -print0 y su formato
listar_archivos() {
    find . \( -path './$RECYCLE.BIN' -o -path './System Volume Information' -o -path './SteamLibrary' \) -prune \
        -o -type f ! -path './DumpStack.log.tmp' "$@"
}

manifiesto_de_lista() { # raíz, lista con NUL, salida
    (cd "$1" && xargs -0 -r sha256sum < "$2" > "$3.parcial")
    mv -f "$3.parcial" "$3"
}

verificar() { # raíz, manifiesto
    [ -s "$2" ] || { [ -e "$2" ] && return 0; error "no existe $2"; }
    echo "Verificando $(wc -l < "$2") archivos en $1 ..."
    (cd "$1" && sha256sum -c --quiet "$2") || error "la verificación de $1 ha fallado: no sigas"
}

# ── Discos ───────────────────────────────────────────────────────────────────
dev_de_uuid() { blkid -U "$1" || error "no encuentro la partición con UUID $1"; }

disco_de() { # partición -> disco, comprobando el modelo
    local disco modelo
    disco=/dev/$(lsblk -no PKNAME "$1" | head -n1)
    modelo=$(lsblk -dno MODEL "$disco" | xargs)
    [ "$modelo" = "$MODELO" ] || error "$1 está en un disco con modelo «$modelo», se esperaba $MODELO"
    echo "$disco"
}

comprobar_montaje() { # partición, punto de montaje
    [ "$(findmnt -rno SOURCE "$2" || true)" = "$1" ] || error "$1 no está montada en $2"
}

nadie_usa() { # punto de montaje
    # Sin -v: con -v siempre aparece la línea «kernel mount»
    if [ -n "$(fuser -m "$1" 2>/dev/null | xargs || true)" ]; then
        fuser -vm "$1" >&2 || true
        error "hay procesos usando $1: ciérralos y repite la fase"
    fi
}

parar_syncthing() {
    pkill -u "$USUARIO" -x syncthing 2>/dev/null || true
    sleep 2
    ! pgrep -u "$USUARIO" -x syncthing > /dev/null || error "syncthing sigue en marcha"
    echo "syncthing parado (volverá al reiniciar el equipo)"
}

# Borra la partición 3 y amplía la 2 hasta el final. Vale para un disco o una imagen de prueba
ampliar_tabla() { # disco
    sgdisk -d 3 "$1"
    sgdisk -t 2:8300 -c 2:windows "$1"
    parted -s "$1" resizepart 2 100%
}

elegir_externo() { # recibe por stdin líneas «dispositivo modelo tamaño»; exige una sola coincidencia
    local encontrados
    encontrados=$(awk -v m="$MODELO_EXTERNO" -v s="$TAMANO_EXTERNO" '$2 == m && $3 == s { print $1 }')
    [ -n "$encontrados" ] || error "no encuentro el disco externo $MODELO_EXTERNO de $TAMANO_EXTERNO bytes"
    [ "$(wc -l <<< "$encontrados")" = 1 ] || error "hay más de un disco que coincide: $encontrados"
    echo "$encontrados"
}

tabla_externo() { # disco o imagen: tabla GPT nueva con una sola partición Linux
    sgdisk -Z "$1"
    sgdisk -n 1:0:0 -t 1:8300 -c 1:externo "$1"
}

# ── Fases ────────────────────────────────────────────────────────────────────
fase_formatear_externo() {
    local disco montajes punto
    disco=$(lsblk -dbnpo NAME,MODEL,SIZE | elegir_externo)
    [ "$(lsblk -dno TRAN "$disco" | xargs)" = usb ] || error "$disco no es un disco USB"
    montajes=$(lsblk -rno MOUNTPOINTS "$disco" | grep -v '^$' || true)
    while IFS= read -r punto; do
        [ -n "$punto" ] && nadie_usa "$punto"
    done <<< "$montajes"
    lsblk -o NAME,SIZE,FSTYPE,LABEL,MODEL,MOUNTPOINTS "$disco"
    confirmar "Se BORRA TODO $disco (los ${TAMANO_EXTERNO} bytes del modelo $MODELO_EXTERNO) y se crea una ext4." "BORRAR externo"
    while IFS= read -r punto; do
        [ -n "$punto" ] && umount "$punto"
    done <<< "$montajes"
    wipefs -a "$disco"?* || true
    tabla_externo "$disco"
    partprobe "$disco"
    udevadm settle
    wipefs -a "${disco}1" || true
    mkfs.ext4 -F -L externo -m 0 "${disco}1"
    mkdir -p "$MONTAJE_EXTERNO"
    mount "${disco}1" "$MONTAJE_EXTERNO"
    chown "$USUARIO:$USUARIO" "$MONTAJE_EXTERNO"
    hecho ok_disco_externo "ext4 creada y montada en $MONTAJE_EXTERNO"
}

fase_comprobar() {
    local dev_d dev_w disco
    dev_d=$(dev_de_uuid "$UUID_DATOS")
    dev_w=$(dev_de_uuid "$UUID_WINDOWS")
    disco=$(disco_de "$dev_d")
    [ "$(disco_de "$dev_w")" = "$disco" ] || error "las dos particiones no están en el mismo disco"
    comprobar_montaje "$dev_d" "$RAIZ_DATOS"
    comprobar_montaje "$dev_w" "$RAIZ_WINDOWS"
    lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS "$disco"

    paso "Salud de $disco"
    smartctl -H -A "$disco" | grep -E 'overall-health|Reallocated_Sector|Reported_Uncorrect|Current_Pending|Offline_Uncorrect|Percent_Lifetime|Power_On_Hours' || true
    paso "Salud del NVMe"
    smartctl -H -A /dev/nvme0n1 | grep -E 'overall-health|Percentage Used|Media and Data Integrity' || true

    paso "Espacio"
    local necesario libre_home libre_raiz
    necesario=$(du -sb "$RAIZ_DATOS" | cut -f1)
    libre_home=$(df -B1 --output=avail /home | tail -n1 | xargs)
    libre_raiz=$(df -B1 --output=avail / | tail -n1 | xargs)
    echo "A copiar: $((necesario / 1024 ** 3)) GiB; libres: /home $((libre_home / 1024 ** 3)) GiB, / $((libre_raiz / 1024 ** 3)) GiB"
    [ "$LIMITE_A" -lt "$libre_home" ] || error "no cabe la parte de /home"
    [ $((necesario - LIMITE_A)) -lt "$libre_raiz" ] || error "no cabe la parte de /"

    paso "Nombres repetidos entre las dos particiones"
    local repetidos
    repetidos=$(comm -12 <(cd "$RAIZ_DATOS" && listar_archivos -print | sort) <(cd "$RAIZ_WINDOWS" && listar_archivos -print | sort) | wc -l)
    [ "$repetidos" = 0 ] || error "$repetidos archivos se llaman igual en las dos particiones"
    echo "Ninguno"

    paso "Procesos usando las particiones"
    fuser -vm "$RAIZ_DATOS" "$RAIZ_WINDOWS" 2>&1 || true
    echo "(las líneas «kernel mount» son normales)"
}

fase_copiar_ppp() {
    mkdir -p "$ESTADO" "$TMP_A" "$TMP_B"
    local lista_a=$ESTADO/lista_a lista_b=$ESTADO/lista_b
    paso "Repartiendo $RAIZ_DATOS entre $TMP_A y $TMP_B"
    (cd "$RAIZ_DATOS" && listar_archivos -printf '%s\t%p\0') | sort -z | gawk \
        -v RS='\0' -v ORS='\0' -v lim="$LIMITE_A" -v a="$lista_a" -v b="$lista_b" \
        'BEGIN { printf "" > a; printf "" > b }
         { n = index($0, "\t"); t += substr($0, 1, n - 1); print substr($0, n + 1) > (t <= lim ? a : b) }'

    paso "Manifiesto del original"
    manifiesto_de_lista "$RAIZ_DATOS" "$lista_a" "$ESTADO/manifiesto_a"
    manifiesto_de_lista "$RAIZ_DATOS" "$lista_b" "$ESTADO/manifiesto_b"

    # Las carpetas van en la primera lista para conservar también las vacías
    (cd "$RAIZ_DATOS" && find . \( -path './$RECYCLE.BIN' -o -path './System Volume Information' \) -prune -o -type d -print0) > "$ESTADO/lista_dirs"
    paso "Copiando"
    cat "$ESTADO/lista_dirs" "$lista_a" | rsync -a --info=stats1 --from0 --files-from=- "$RAIZ_DATOS"/ "$TMP_A"/
    rsync -a --info=stats1 --from0 --files-from="$lista_b" "$RAIZ_DATOS"/ "$TMP_B"/

    paso "Verificando la copia"
    verificar "$TMP_A" "$ESTADO/manifiesto_a"
    verificar "$TMP_B" "$ESTADO/manifiesto_b"
    hecho ok_ppp "copia de $RAIZ_DATOS verificada en el NVMe"
}

fase_copia_externa() {
    local destino=${1:-}
    requiere ok_ppp copiar-ppp
    [ -n "$destino" ] && [ -d "$destino" ] || error "indica una carpeta de destino que exista"
    [ "$MODO_PRUEBA" = 1 ] || mountpoint -q "$(findmnt -rno TARGET -T "$destino")" || error "$destino no está en un disco montado"
    rsync -a --no-perms --no-owner --no-group --info=stats1 "$TMP_A"/ "$destino"/
    rsync -a --no-perms --no-owner --no-group --info=stats1 "$TMP_B"/ "$destino"/
    verificar "$destino" "$ESTADO/manifiesto_a"
    verificar "$destino" "$ESTADO/manifiesto_b"
    hecho ok_externa "segunda copia verificada en $destino"
}

fase_descartar_datos() {
    requiere ok_ppp copiar-ppp
    confirmar "Se borran $TMP_A y $TMP_B. Lo de $RAIZ_DATOS no se restaurará: se perderá al formatear." "DESCARTAR Datos"
    rm -rf "$TMP_A" "$TMP_B"
    rmdir "$(dirname "$TMP_A")" "$(dirname "$TMP_B")" 2>/dev/null || true
    # Manifiestos vacíos: las verificaciones posteriores ya no esperan esos archivos
    : > "$ESTADO/manifiesto_a"
    : > "$ESTADO/manifiesto_b"
    hecho ok_descartado "copia del NVMe borrada; $RAIZ_DATOS sigue intacta hasta formatear-sda2"
}

fase_preparar_windows() {
    requiere ok_ppp copiar-ppp
    [ "$MODO_PRUEBA" = 1 ] || parar_syncthing
    if [ -d "$RAIZ_WINDOWS/SteamLibrary" ]; then
        confirmar "Se borra $RAIZ_WINDOWS/SteamLibrary ($(du -sh "$RAIZ_WINDOWS/SteamLibrary" | cut -f1))." "BORRAR SteamLibrary"
        rm -rf "$RAIZ_WINDOWS/SteamLibrary"
    fi
    paso "Manifiesto de $RAIZ_WINDOWS"
    (cd "$RAIZ_WINDOWS" && listar_archivos -print0) | sort -z > "$ESTADO/lista_windows"
    manifiesto_de_lista "$RAIZ_WINDOWS" "$ESTADO/lista_windows" "$ESTADO/manifiesto_windows"
    hecho ok_windows "manifiesto de $(wc -l < "$ESTADO/manifiesto_windows") archivos"
}

fase_formatear() {
    requiere ok_ppp copiar-ppp
    requiere ok_windows preparar-windows
    local dev_d partuuid
    dev_d=$(dev_de_uuid "$UUID_DATOS")
    disco_de "$dev_d" > /dev/null
    comprobar_montaje "$dev_d" "$RAIZ_DATOS"
    verificar "$TMP_A" "$ESTADO/manifiesto_a"
    verificar "$TMP_B" "$ESTADO/manifiesto_b"
    nadie_usa "$RAIZ_DATOS"
    if [ -e "$ESTADO/ok_descartado" ]; then
        echo "AVISO: el contenido de $RAIZ_DATOS no tiene copia y SE PERDERÁ DEFINITIVAMENTE."
    elif [ ! -e "$ESTADO/ok_externa" ]; then
        echo "AVISO: sin copia externa, el contenido de $RAIZ_DATOS queda solo en el NVMe hasta copiar-a-ext4."
    fi
    lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS "$dev_d"
    confirmar "Se BORRA $dev_d ($RAIZ_DATOS) y se crea una ext4 vacía." "BORRAR Datos"
    partuuid=$(lsblk -no PARTUUID "$dev_d")
    [ -n "$partuuid" ] || error "no pude leer el PARTUUID de $dev_d"
    echo "$partuuid" > "$ESTADO/partuuid"
    umount "$RAIZ_DATOS"
    wipefs -a "$dev_d"
    mkfs.ext4 -F -L windows -m 0 "$dev_d"
    mkdir -p "$NUEVO"
    mount "$dev_d" "$NUEVO"
    hecho ok_formato "ext4 creada y montada en $NUEVO"
}

fase_copiar_a_ext4() {
    requiere ok_windows preparar-windows
    [ "$MODO_PRUEBA" = 1 ] || requiere ok_formato formatear-sda2
    [ "$MODO_PRUEBA" = 1 ] || mountpoint -q "$NUEVO" || error "$NUEVO no está montado"
    paso "Copiando $RAIZ_WINDOWS"
    rsync -a --info=stats1 "${RSYNC_EXCLUIR[@]}" "$RAIZ_WINDOWS"/ "$NUEVO"/
    verificar "$NUEVO" "$ESTADO/manifiesto_windows"
    if [ ! -e "$ESTADO/ok_descartado" ]; then
        paso "Devolviendo lo de /mnt/Datos"
        rsync -a --info=stats1 --ignore-existing "$TMP_A"/ "$NUEVO"/
        rsync -a --info=stats1 --ignore-existing "$TMP_B"/ "$NUEVO"/
        verificar "$NUEVO" "$ESTADO/manifiesto_a"
        verificar "$NUEVO" "$ESTADO/manifiesto_b"
    fi
    hecho ok_copia "todo copiado y verificado en $NUEVO"
}

fase_finalizar() {
    requiere ok_copia copiar-a-ext4
    local dev_w dev_n disco uuid_nuevo fstab=/etc/fstab
    dev_w=$(dev_de_uuid "$UUID_WINDOWS")
    disco=$(disco_de "$dev_w")
    dev_n=$(readlink -f "/dev/disk/by-partuuid/$(cat "$ESTADO/partuuid")")
    comprobar_montaje "$dev_w" "$RAIZ_WINDOWS"
    comprobar_montaje "$dev_n" "$NUEVO"
    [ "$dev_w" = "${disco}3" ] && [ "$dev_n" = "${disco}2" ] || error "la tabla no es la esperada: $dev_n y $dev_w"
    nadie_usa "$RAIZ_WINDOWS"
    nadie_usa "$NUEVO"
    lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS "$disco"
    confirmar "Se BORRA $dev_w ($RAIZ_WINDOWS) y se amplía $dev_n hasta el final del disco." "BORRAR windows"

    uuid_nuevo=$(blkid -s UUID -o value "$dev_n")
    [ -n "$uuid_nuevo" ] || error "no pude leer el UUID de $dev_n"

    umount "$RAIZ_WINDOWS"
    umount "$NUEVO"

    # fstab antes de tocar la tabla: las líneas antiguas no llevan nofail y, si algo
    # fallara después, el equipo no arrancaría pidiendo unas particiones que ya no existen.
    # El UUID de la ext4 no cambia al ampliarla.
    cp -p "$fstab" "$fstab.bak.$(date +%Y%m%d%H%M%S)"
    sed -i -e "/^UUID=${UUID_DATOS}[[:space:]]/d" -e "/^UUID=${UUID_WINDOWS}[[:space:]]/d" "$fstab"
    echo "UUID=$uuid_nuevo /mnt/windows ext4 defaults,noatime,nofail 0 2" >> "$fstab"
    systemctl daemon-reload

    wipefs -a "$dev_w"
    ampliar_tabla "$disco"
    partprobe "$disco"
    udevadm settle
    # Por si un automontador la ha cogido al cambiar la tabla
    umount "$dev_n" 2>/dev/null || true
    # Código 1 de e2fsck: corrigió algo y el sistema de archivos ya está bien
    e2fsck -f -y "$dev_n" || [ $? -eq 1 ]
    resize2fs "$dev_n"
    mount /mnt/windows
    chown "$USUARIO:$USUARIO" /mnt/windows
    rmdir "$NUEVO" "$RAIZ_DATOS" 2>/dev/null || true

    verificar /mnt/windows "$ESTADO/manifiesto_windows"
    verificar /mnt/windows "$ESTADO/manifiesto_a"
    verificar /mnt/windows "$ESTADO/manifiesto_b"
    df -h /mnt/windows
    hecho ok_final "migración terminada y verificada. Reinicia para comprobar fstab y recuperar syncthing"
}

fase_limpiar() {
    requiere ok_final finalizar
    confirmar "Se borran las copias temporales $TMP_A y $TMP_B." "BORRAR temporales"
    rm -rf "$TMP_A" "$TMP_B"
    rmdir "$(dirname "$TMP_A")" "$(dirname "$TMP_B")" 2>/dev/null || true
    echo "OK: temporales borrados"
}

# ── Principal ────────────────────────────────────────────────────────────────
[ "${BASH_SOURCE[0]}" = "$0" ] || return 0
fase=${1:-}
[ "$MODO_PRUEBA" = 1 ] || [ "$(id -u)" = 0 ] || error "ejecútalo con sudo"
mkdir -p "$ESTADO"
case "$fase" in
    comprobar) fase_comprobar ;;
    copiar-ppp) fase_copiar_ppp ;;
    formatear-externo) fase_formatear_externo ;;
    copia-externa) fase_copia_externa "${2:-}" ;;
    descartar-datos) fase_descartar_datos ;;
    preparar-windows) fase_preparar_windows ;;
    formatear-sda2) fase_formatear ;;
    copiar-a-ext4) fase_copiar_a_ext4 ;;
    finalizar) fase_finalizar ;;
    limpiar) fase_limpiar ;;
    *) sed -n '2,/^# Uso:/p' "$0"; exit 2 ;;
esac
chown -R "$USUARIO:$USUARIO" "$ESTADO" 2>/dev/null || true
