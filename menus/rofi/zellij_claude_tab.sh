#!/usr/bin/env bash

LAYOUTS_ROOT="$HOME/.config/zellij/layouts"
LAYOUTS_CLAUDE="$HOME/.config/zellij/layouts/claude"
TEMPLATE="claude_proyecto.kdl"

declare -A layout_paths

while IFS= read -r f; do
    nombre=$(basename "$f" .kdl)
    layout_paths[$nombre]="$f"
done < <(
    find "$LAYOUTS_ROOT"  -maxdepth 1 -name "*.kdl" ! -name "$TEMPLATE"
    find "$LAYOUTS_CLAUDE" -maxdepth 1 -name "*.kdl"
)

seleccion=$(printf '%s\n' "${!layout_paths[@]}" | sort \
    | rofi -dmenu -i -p "Zellij tab: " -theme-str 'window {width: 600px;}')

[[ -z "$seleccion" ]] && exit 0

zellij action new-tab \
    --name "$seleccion" \
    --layout "${layout_paths[$seleccion]}"
