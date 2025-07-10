#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de depuración para entender qué referencias se detectan
"""

import os
import re


def debug_script_references(content_folder, app_path):
    """Función de depuración para ver qué referencias encuentra."""
    print("=== DEPURACIÓN DE REFERENCIAS ===")
    print(f"Content folder: {content_folder}")
    print(f"App path: {app_path}")
    print()
    
    # Verificar que las carpetas existen
    if not os.path.exists(content_folder):
        print(f"❌ Content folder no existe: {content_folder}")
        return
    
    if not os.path.exists(app_path):
        print(f"❌ App path no existe: {app_path}")
        return
    
    print("✅ Ambas carpetas existen")
    print()
    
    # Buscar archivos markdown en content_folder
    print("=== ARCHIVOS EN CONTENT FOLDER ===")
    md_files = []
    for root, _, files in os.walk(content_folder):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                md_files.append(file_path)
                print(f"📄 {os.path.relpath(file_path, content_folder)}")
    
    if not md_files:
        print("❌ No se encontraron archivos .md")
        return
    
    print()
    
    # Analizar cada archivo para encontrar referencias
    print("=== ANÁLISIS DE REFERENCIAS ===")
    all_references = []
    
    for file_path in md_files:
        print(f"\n📄 Analizando: {os.path.relpath(file_path, content_folder)}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"   ❌ Error leyendo: {e}")
            continue
        
        # Buscar referencias ![[...]]
        refs = re.findall(r'!\[\[([^]]+)\]\]', content)
        
        if refs:
            print(f"   ✅ Referencias encontradas: {len(refs)}")
            for ref in refs:
                print(f"      📌 {ref}")
                all_references.append(ref)
        else:
            print(f"   ⚠️  No se encontraron referencias")
    
    if not all_references:
        print("\n❌ No se encontraron referencias en ningún archivo")
        return
    
    print(f"\n=== TOTAL DE REFERENCIAS ÚNICAS ===")
    unique_refs = list(set(all_references))
    for ref in unique_refs:
        print(f"📌 {ref}")
    
    print(f"\n=== BUSCANDO ARCHIVOS EN APP_PATH ===")
    
    # Buscar archivos .py.md en app_path
    py_md_files = []
    for root, _, files in os.walk(app_path):
        for file in files:
            if file.endswith('.py.md'):
                file_path = os.path.join(root, file)
                py_md_files.append(file_path)
                print(f"🐍 {os.path.relpath(file_path, app_path)}")
    
    print(f"\n=== COINCIDENCIAS ===")
    
    for ref in unique_refs:
        print(f"\n🔍 Buscando: {ref}")
        
        # Casos posibles:
        possible_names = []
        
        if ref.endswith('.py'):
            possible_names.append(ref + '.md')
        else:
            possible_names.append(ref + '.py.md')
        
        print(f"   Posibles nombres: {possible_names}")
        
        found = False
        for possible_name in possible_names:
            for py_md_file in py_md_files:
                if py_md_file.endswith(possible_name):
                    print(f"   ✅ ENCONTRADO: {os.path.relpath(py_md_file, app_path)}")
                    found = True
                    break
        
        if not found:
            print(f"   ❌ NO ENCONTRADO")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Uso: python debug_script_detection.py <content_folder> <app_path>")
        sys.exit(1)
    
    content_folder = sys.argv[1]
    app_path = sys.argv[2]
    
    debug_script_references(content_folder, app_path)