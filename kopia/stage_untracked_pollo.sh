#!/usr/bin/env bash
#
# Script Name: stage_untracked_pollo.sh
# Description: Copia a un directorio de staging los ficheros no trackeados
#              (y no ignorados) de cada repo git bajo ~/gits/pollo, para que
#              Kopia pueda respaldar ese staging sin duplicar todo el repo
#              (el propio git ya respalda lo trackeado via sus remotos).
#
set -uo pipefail

POLLO_DIR="$HOME/gits/pollo"
STAGE_DIR="$HOME/.cache/kopia-untracked-staging/pollo"

# Artefactos regenerables que no queremos aunque git los vea como "no trackeados"
# (repos sin .gitignore adecuado para su stack)
EXCLUDE_REGEX='(^|/)(\.gradle|\.idea|\.venv|venv|node_modules|__pycache__|\.cache|build|dist|target)(/|$)'

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

find "$POLLO_DIR" -maxdepth 2 -name ".git" -type d 2>/dev/null | while read -r gitdir; do
    repo_dir="$(dirname "$gitdir")"
    repo_name="$(basename "$repo_dir")"

    files="$(cd "$repo_dir" && git ls-files --others --exclude-standard | grep -vE "$EXCLUDE_REGEX")"
    [ -z "$files" ] && continue

    while IFS= read -r rel_path; do
        src="$repo_dir/$rel_path"
        dst="$STAGE_DIR/$repo_name/$rel_path"
        mkdir -p "$(dirname "$dst")"
        cp -a "$src" "$dst" 2>/dev/null
    done <<< "$files"
done

echo "Staging listo en $STAGE_DIR: $(find "$STAGE_DIR" -type f | wc -l) ficheros"
