#!/bin/bash

md_file="${1}"

echo "$md_file"

/home/huan/Scripts/menus/mihitas/publicado_md.sh "$md_file"
/home/huan/Scripts/menus/mihitas/crear_post.py --all "$md_file"
