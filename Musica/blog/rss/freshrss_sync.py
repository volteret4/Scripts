#!/usr/bin/env python3
"""
Script de sincronización para FreshRSS - VERSIÓN CORREGIDA
Elimina embeds escuchados que fueron marcados en el navegador

CORRECCIONES APLICADAS:
1. Recompacta las páginas después de eliminar embeds para evitar páginas vacías
2. Recalcula la numeración de páginas secuencialmente (1, 2, 3...)
3. Maneja correctamente el caso donde la primera página queda vacía
4. Actualiza correctamente el totalPages en el HTML

Este script lee el browser_data.json exportado desde sync_tools_freshrss.html
y actualiza los archivos HTML generados para no mostrar los embeds ya escuchados.

USO:
    python3 freshrss_sync_fixed.py --localStorage-file browser_data.json --feed-dir docs
"""

import json
import os
import re
import argparse
from datetime import datetime
from pathlib import Path


def sanitize_feed_name(feed_name):
    """Convierte un nombre de feed al formato usado en localStorage"""
    return re.sub(r'[^\w\s-]', '', feed_name).strip().replace(' ', '_')


def load_listened_from_browser(localStorage_file, debug=False):
    """Lee browser_data.json exportado desde sync_tools_freshrss.html"""
    print(f"\n📥 Leyendo: {localStorage_file}")

    if not os.path.exists(localStorage_file):
        print(f"❌ No existe: {localStorage_file}")
        return {}

    try:
        with open(localStorage_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if debug:
            print(f"\n🔍 DEBUG - Contenido de localStorage:")
            for key in data.keys():
                print(f"   • {key}")

        listened_by_feed = {}

        for key, value in data.items():
            if key.startswith('freshrss_listened_'):
                # Extraer el nombre del feed
                feed_name = key.replace('freshrss_listened_', '')

                if isinstance(value, list):
                    listened_by_feed[feed_name] = set(value)
                elif isinstance(value, str):
                    try:
                        listened_by_feed[feed_name] = set(json.loads(value))
                    except:
                        listened_by_feed[feed_name] = set()

                if debug:
                    print(f"\n   {feed_name}: {len(listened_by_feed[feed_name])} IDs")
                    if listened_by_feed[feed_name]:
                        sample = list(listened_by_feed[feed_name])[:3]
                        for s in sample:
                            print(f"      - {s}")

        print(f"✅ Escuchados cargados:")
        for feed, ids in listened_by_feed.items():
            print(f"   • {feed}: {len(ids)} embeds")

        return listened_by_feed

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {}


def scan_feed_htmls(feed_dir, debug=False):
    """
    Escanea el directorio de feeds y extrae información de cada HTML.

    Returns:
        dict: {feed_name: {'file': filepath, 'embeds': [...], 'total': count}}
    """
    print(f"\n📁 Escaneando directorio: {feed_dir}")

    if not os.path.exists(feed_dir):
        print(f"❌ El directorio {feed_dir} no existe")
        return {}

    feeds_info = {}
    html_files = [f for f in os.listdir(feed_dir) if f.endswith('.html') and f != 'index.html']

    print(f"📄 Archivos HTML encontrados: {len(html_files)}\n")

    for html_file in sorted(html_files):
        # Obtener el nombre base del archivo (sin .html)
        feed_name = html_file[:-5]

        filepath = os.path.join(feed_dir, html_file)

        # Leer el HTML y buscar el objeto JavaScript con los datos
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Buscar allPagesData en el JavaScript
            pages_data_match = re.search(
                r'const allPagesData = ({.+?});',
                html_content,
                re.DOTALL
            )

            if not pages_data_match:
                print(f"  ⚠️  {feed_name}: No se encontró allPagesData")
                continue

            # Parsear el JSON
            pages_data_json = pages_data_match.group(1)
            pages_data = json.loads(pages_data_json)

            # Contar embeds
            total_embeds = sum(len(page_items) for page_items in pages_data.values())

            feeds_info[feed_name] = {
                'file': filepath,
                'pages_data': pages_data,
                'total': total_embeds
            }

            print(f"  ✓ {feed_name}: {total_embeds} embeds")

            if debug:
                print(f"      Páginas: {len(pages_data)}")
                # Mostrar algunos IDs de muestra
                for page_num, items in list(pages_data.items())[:1]:
                    for item in items[:2]:
                        print(f"      Ejemplo ID: {item.get('id', 'N/A')}")

        except Exception as e:
            print(f"  ❌ {feed_name}: Error al procesar - {e}")
            if debug:
                import traceback
                traceback.print_exc()

    return feeds_info


def sync_feed(feed_info, listened_ids, debug=False):
    """
    Elimina los embeds escuchados de los datos de un feed y recompacta las páginas.

    CORRECCIÓN PRINCIPAL: Después de filtrar, recompacta todos los items
    en páginas secuenciales para evitar páginas vacías.

    Returns:
        dict: Nuevos pages_data filtrados y recompactados
        dict: Estadísticas de la sincronización
    """
    pages_data = feed_info['pages_data']
    stats = {'original': 0, 'kept': 0, 'removed': 0}

    # PASO 1: Recopilar todos los items filtrados en una sola lista
    all_filtered_items = []

    for page_num, items in pages_data.items():
        for item in items:
            stats['original'] += 1
            item_id = item.get('id')

            if not item_id:
                # Sin ID, mantener por defecto
                all_filtered_items.append(item)
                stats['kept'] += 1
                if debug:
                    print(f"      ⚠️  Sin ID, manteniendo: {item.get('title', 'Sin título')[:50]}")
                continue

            if item_id in listened_ids:
                # Escuchado → Eliminar
                stats['removed'] += 1
                if debug:
                    print(f"      ❌ Removiendo: {item.get('title', 'Sin título')[:50]}")
                    print(f"         ID: {item_id}")
            else:
                # No escuchado → Mantener
                all_filtered_items.append(item)
                stats['kept'] += 1

    # PASO 2: CORRECCIÓN PRINCIPAL - Recompactar en páginas secuenciales
    # Asumir 8 items por página (valor por defecto del generador)
    items_per_page = 8

    # Intentar detectar el tamaño de página actual
    if pages_data:
        # Usar el tamaño de la primera página como referencia
        first_page_items = list(pages_data.values())[0]
        if len(first_page_items) > 0:
            items_per_page = len(first_page_items)

    synced_pages = {}

    # Dividir todos los items filtrados en páginas nuevas
    for i in range(0, len(all_filtered_items), items_per_page):
        page_items = all_filtered_items[i:i + items_per_page]
        if page_items:  # Solo crear páginas que tengan items
            page_number = (i // items_per_page) + 1
            synced_pages[str(page_number)] = page_items

    if debug:
        print(f"      📊 Recompactación:")
        print(f"         Items totales filtrados: {len(all_filtered_items)}")
        print(f"         Items por página: {items_per_page}")
        print(f"         Páginas resultantes: {len(synced_pages)}")
        for page_num, items in synced_pages.items():
            print(f"         Página {page_num}: {len(items)} items")

    return synced_pages, stats


def regenerate_html(feed_name, original_filepath, synced_pages_data, output_dir=None):
    """
    Regenera el archivo HTML con los datos sincronizados.
    CORRECCIÓN: Actualiza correctamente las estadísticas y totalPages.
    """
    # Leer el HTML original
    with open(original_filepath, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Calcular nuevas estadísticas
    total_items = sum(len(items) for items in synced_pages_data.values())
    total_pages = len(synced_pages_data)

    # Convertir a JSON
    pages_data_json = json.dumps(synced_pages_data, ensure_ascii=False, indent=2)

    # Reemplazar allPagesData
    html_content = re.sub(
        r'const allPagesData = {.+?};',
        f'const allPagesData = {pages_data_json};',
        html_content,
        flags=re.DOTALL
    )

    # CORRECCIÓN: Reemplazar totalPages correctamente
    html_content = re.sub(
        r'const totalPages = \d+;',
        f'const totalPages = {total_pages};',
        html_content
    )

    # CORRECCIÓN: Reemplazar estadísticas en el header
    html_content = re.sub(
        r'Total: \d+ embeds únicos \| Páginas: \d+',
        f'Total: {total_items} embeds únicos | Páginas: {total_pages}',
        html_content
    )

    # CORRECCIÓN ADICIONAL: Si hay 0 páginas, crear una página vacía para evitar errores de JavaScript
    if total_pages == 0:
        empty_pages_data = {"1": []}
        pages_data_json = json.dumps(empty_pages_data, ensure_ascii=False, indent=2)

        html_content = re.sub(
            r'const allPagesData = {.+?};',
            f'const allPagesData = {pages_data_json};',
            html_content,
            flags=re.DOTALL
        )

        html_content = re.sub(
            r'const totalPages = \d+;',
            'const totalPages = 1;',
            html_content
        )

        html_content = re.sub(
            r'Total: \d+ embeds únicos \| Páginas: \d+',
            'Total: 0 embeds únicos | Páginas: 1',
            html_content
        )

        print(f"      📝 Creada página vacía para evitar errores JavaScript")

    # Guardar
    output_path = original_filepath
    if output_dir:
        output_path = os.path.join(output_dir, os.path.basename(original_filepath))

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return output_path


def print_stats(all_stats):
    """Muestra estadísticas de sincronización"""
    print("\n" + "="*70)
    print("📊 RESULTADO DE LA SINCRONIZACIÓN")
    print("="*70)

    total_original = sum(s['original'] for s in all_stats.values())
    total_kept = sum(s['kept'] for s in all_stats.values())
    total_removed = sum(s['removed'] for s in all_stats.values())

    print(f"\n✅ Embeds mantenidos: {total_kept}")
    print(f"➖ Embeds eliminados: {total_removed}")
    print(f"📋 Total original: {total_original}")

    print("\n🔍 Por feed:")
    for feed, stats in sorted(all_stats.items()):
        if stats['removed'] > 0 or stats['kept'] > 0:
            print(f"\n  {feed}:")
            print(f"    Original:   {stats['original']}")
            print(f"    Mantenidos: {stats['kept']}")
            print(f"    Eliminados: {stats['removed']}")


def main():
    parser = argparse.ArgumentParser(
        description='Sincroniza embeds escuchados en FreshRSS HTMLs (VERSIÓN CORREGIDA)'
    )
    parser.add_argument('--localStorage-file', required=True,
                       help='browser_data.json exportado desde sync_tools_freshrss.html')
    parser.add_argument('--feed-dir', default='docs',
                       help='Directorio con los HTMLs de feeds (default: docs)')
    parser.add_argument('--output-dir',
                       help='Directorio de salida (default: sobrescribe los originales)')
    parser.add_argument('--debug', action='store_true',
                       help='Mostrar información detallada de debug')
    parser.add_argument('--stats-only', action='store_true',
                       help='Solo mostrar estadísticas sin hacer cambios')

    args = parser.parse_args()

    print("\n" + "="*70)
    print("🔄 SINCRONIZACIÓN FRESHRSS - VERSIÓN CORREGIDA")
    print("="*70)
    print("🔧 CORRECCIONES APLICADAS:")
    print("   ✓ Recompactación de páginas para evitar páginas vacías")
    print("   ✓ Renumeración secuencial de páginas (1, 2, 3...)")
    print("   ✓ Manejo correcto cuando la primera página queda vacía")
    print("   ✓ Actualización correcta de totalPages en HTML")
    print("🔑 Usando IDs de embeds como identificador")

    # Cargar localStorage
    listened = load_listened_from_browser(args.localStorage_file, debug=args.debug)
    if not listened:
        print("\n❌ No hay datos de escuchados")
        return

    # Escanear feeds
    feeds_info = scan_feed_htmls(args.feed_dir, debug=args.debug)
    if not feeds_info:
        print("\n❌ No hay feeds para sincronizar")
        return

    # Crear directorio de salida si se especificó
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    # Sincronizar cada feed
    print(f"\n{'='*70}")
    print("🔄 Sincronizando feeds...")
    print(f"{'='*70}\n")

    all_stats = {}

    for feed_name, feed_info in feeds_info.items():
        # Obtener IDs escuchados para este feed
        # Intentar con el nombre exacto y con versión sanitizada
        listened_ids = set()

        if feed_name in listened:
            listened_ids = listened[feed_name]
        else:
            # Buscar con todas las variantes posibles
            for key in listened.keys():
                if sanitize_feed_name(key) == feed_name or key == feed_name:
                    listened_ids = listened[key]
                    break

        if args.debug:
            print(f"\n🔍 DEBUG - {feed_name}:")
            print(f"   Escuchados: {len(listened_ids)} IDs")
            if listened_ids:
                print(f"   Sample: {list(listened_ids)[:3]}")

        # Sincronizar
        synced_pages, stats = sync_feed(feed_info, listened_ids, debug=args.debug)
        all_stats[feed_name] = stats

        original_pages = len(feed_info['pages_data'])
        new_pages = len(synced_pages)

        print(f"  {feed_name}: {stats['original']} → {stats['kept']} (-{stats['removed']})")
        print(f"    Páginas: {original_pages} → {new_pages}")

        # Regenerar HTML si no es solo stats
        if not args.stats_only:
            output_path = regenerate_html(
                feed_name,
                feed_info['file'],
                synced_pages,
                output_dir=args.output_dir
            )
            print(f"    ✓ Actualizado: {output_path}")

    # Estadísticas finales
    print_stats(all_stats)

    total_removed = sum(s['removed'] for s in all_stats.values())

    if total_removed == 0 and not args.stats_only:
        print("\n⚠️  ADVERTENCIA: No se eliminó ningún embed")
        print("\nPosibles causas:")
        print("   1. Los nombres de feed no coinciden entre localStorage y los archivos")
        print("   2. No has marcado embeds como escuchados en el navegador")
        print("   3. Los IDs de los embeds no coinciden")
        print("\n💡 Ejecuta de nuevo con --debug para más información")

    print("\n" + "="*70)
    print("✅ COMPLETADO")
    print("="*70)

    if not args.stats_only:
        print(f"\n🔍 Próximos pasos:")
        print(f"   1. Verifica los HTMLs en: {args.output_dir or args.feed_dir}")
        print(f"   2. Abre los feeds en tu navegador para comprobar los cambios")
        print(f"   3. Si todo está bien, sube los cambios:")
        print(f"      git add {args.output_dir or args.feed_dir}/")
        print(f"      git commit -m 'Sync: removed listened embeds'")
        print(f"      git push")
    print()


if __name__ == '__main__':
    main()
