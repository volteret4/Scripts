#!/bin/bash

md_file="${1}"

echo "$md_file"

/home/huan/Scripts/blogs/mihitas/publicado_md.sh "$md_file"
/home/huan/Scripts/blogs/mihitas/crear_post.sh --all "$md_file"
