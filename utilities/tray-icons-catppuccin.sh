#!/bin/bash
# Iconos de bandeja unificados (Catppuccin Mocha) para el tema Sardi-Arc.
#
# Crea en ~/.local/share/icons/Sardi-Arc una capa que se fusiona con el tema
# del sistema: solo añade la carpeta "panel" con los iconos monocromos de
# Papirus-Dark recoloreados. Los iconos de las aplicaciones no cambian.
# Volver a ejecutarlo tras actualizar papirus-icon-theme o sardi-icons.
set -euo pipefail

SRC=/usr/share/icons/Papirus-Dark
SYS=/usr/share/icons/Sardi-Arc/index.theme
DST="$HOME/.local/share/icons/Sardi-Arc"

TEXT="#CDD6F4"      # Text
HIGHLIGHT="#CBA6F7" # Mauve
NEUTRAL="#FAB387"   # Peach
POSITIVE="#A6E3A1"  # Green
NEGATIVE="#F38BA8"  # Red

rm -rf "$DST/panel"
for size in 16 22 24; do
    mkdir -p "$DST/panel/$size"
    for f in "$SRC/${size}x${size}/panel/"*.svg; do
        name=$(basename "$f")
        sed -e "s/#dfdfdf/$TEXT/Ig" -e "s/#4285f4/$HIGHLIGHT/Ig" -e "s/#ff9800/$NEUTRAL/Ig" \
            -e "s/#4caf50/$POSITIVE/Ig" -e "s/#f44336/$NEGATIVE/Ig" "$(readlink -f "$f")" > "$DST/panel/$size/$name"
    done
    # Nombre del icono de bandeja que tiene configurado DeaDBeeF
    cp "$DST/panel/$size/deadbeef-panel.svg" "$DST/panel/$size/deadbeef_tray_icon.svg"
done

# index.theme del sistema con las carpetas "panel" delante (más prioridad)
dirs="panel/16,panel/22,panel/24"
sed "s|^Directories=|Directories=$dirs,|" "$SYS" > "$DST/index.theme"
for size in 16 22 24; do
    printf '\n[panel/%s]\nContext=Status\nSize=%s\nMinSize=%s\nMaxSize=%s\nType=Scalable\n' \
        "$size" "$size" "$size" "$size" >> "$DST/index.theme"
done
gtk-update-icon-cache -f -q "$DST" 2>/dev/null || true
# Qt (CopyQ, KeePassXC…) busca los temas en ~/.icons, no en ~/.local/share/icons
[ -e "$HOME/.icons/Sardi-Arc" ] || ln -s "$DST" "$HOME/.icons/Sardi-Arc"
echo "Iconos de bandeja listos en $DST"
