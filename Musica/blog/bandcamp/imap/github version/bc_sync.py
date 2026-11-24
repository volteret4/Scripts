#!/usr/bin/env python3
"""
Script de sincronización CORRECTO
Elimina álbumes escuchados de tu colección
USA ALBUM_ID/TRACK_ID DE BANDCAMP (ej: album_1212060845)
"""

import json
import os
import re
from datetime import datetime


def extract_bandcamp_id(embed_code):
    """
    Extrae el album_id o track_id del código embed de Bandcamp.
    """
    if not embed_code:
        return None

    # Buscar album=XXXXXXXX
    album_match = re.search(r'album=(\d+)', embed_code)
    if album_match:
        return f"album_{album_match.group(1)}"

    # Buscar track=XXXXXXXX
    track_match = re.search(r'track=(\d+)', embed_code)
    if track_match:
        return f"track_{track_match.group(1)}"

    return None


def sanitize_genre_name(genre):
    """
    Convierte un nombre de género al formato usado en localStorage
    """
    return re.sub(r'[^\w\s-]', '', genre).strip().replace(' ', '_')


def load_listened_from_browser(localStorage_file, debug=False):
    """Lee browser_data.json exportado"""
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

        listened_by_genre = {}

        for key, value in data.items():
            if key.startswith('bandcamp_listened_'):
                # Extraer el género del key
                genre = key.replace('bandcamp_listened_', '')

                if isinstance(value, list):
                    listened_by_genre[genre] = set(value)
                elif isinstance(value, str):
                    try:
                        listened_by_genre[genre] = set(json.loads(value))
                    except:
                        listened_by_genre[genre] = set()

                if debug:
                    print(f"\n   {genre}: {len(listened_by_genre[genre])} IDs")
                    if listened_by_genre[genre]:
                        sample = list(listened_by_genre[genre])[:3]
                        for s in sample:
                            print(f"      - {s}")

        print(f"✅ Escuchados cargados:")
        for genre, ids in listened_by_genre.items():
            print(f"   • {genre}: {len(ids)} álbumes")

        return listened_by_genre

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_collection(json_file, debug=False):
    """Carga bandcamp_data.json"""
    print(f"\n📂 Leyendo: {json_file}")

    if not os.path.exists(json_file):
        print(f"❌ No existe: {json_file}")
        return {}

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total = sum(len(embeds) for embeds in data.values())
        print(f"✅ Colección cargada: {total} álbumes en {len(data)} géneros")

        if debug:
            print(f"\n🔍 DEBUG - Géneros en colección:")
            for genre, embeds in data.items():
                print(f"   • '{genre}': {len(embeds)} álbumes")
                if embeds:
                    sample = embeds[0]
                    embed_id = extract_bandcamp_id(sample.get('embed', ''))
                    print(f"      Ejemplo embed: {sample['embed'][:80]}...")
                    print(f"      Ejemplo ID: {embed_id}")

        return data

    except Exception as e:
        print(f"❌ Error: {e}")
        return {}


def sync_collection(collection, listened_by_genre, debug=False):
    """
    Elimina álbumes escuchados de la colección
    USA ALBUM_ID DE BANDCAMP para hacer la comparación
    """
    print(f"\n🔄 Sincronizando...")

    synced = {}
    stats = {'kept': 0, 'removed': 0, 'by_genre': {}}

    for genre, embeds in collection.items():
        # Probar con el género tal cual y con versión sanitizada
        sanitized_genre = sanitize_genre_name(genre)

        # Buscar coincidencias
        listened_ids = set()
        matched_key = None

        # Intentar coincidencia exacta primero
        if genre in listened_by_genre:
            listened_ids = listened_by_genre[genre]
            matched_key = genre
        # Intentar con versión sanitizada
        elif sanitized_genre in listened_by_genre:
            listened_ids = listened_by_genre[sanitized_genre]
            matched_key = sanitized_genre

        if debug and listened_ids:
            print(f"\n🔍 DEBUG - {genre}:")
            print(f"   Género original: '{genre}'")
            print(f"   Género sanitizado: '{sanitized_genre}'")
            print(f"   Matched key: '{matched_key}'")
            print(f"   Escuchados: {len(listened_ids)} IDs")
            print(f"   Sample IDs: {list(listened_ids)[:3]}")

        kept = []
        removed = 0

        for embed in embeds:
            # Extraer el album_id del embed
            embed_id = extract_bandcamp_id(embed.get('embed', ''))

            if not embed_id:
                # Si no se puede extraer ID, mantener el álbum
                kept.append(embed)
                if debug:
                    print(f"      ⚠️  Sin ID, manteniendo: {embed.get('subject', 'Sin título')[:50]}")
                continue

            if embed_id in listened_ids:
                # Escuchado → Eliminar
                removed += 1
                if debug:
                    print(f"      ❌ Removiendo: {embed.get('subject', 'Sin título')[:50]}")
                    print(f"         ID: {embed_id}")
            else:
                # No escuchado → Mantener
                kept.append(embed)

        if kept:
            synced[genre] = kept

        stats['by_genre'][genre] = {
            'original': len(embeds),
            'kept': len(kept),
            'removed': removed,
            'matched_key': matched_key
        }
        stats['kept'] += len(kept)
        stats['removed'] += removed

        status = f"  {genre}: {len(embeds)} → {len(kept)} (-{removed})"
        if matched_key and removed > 0:
            status += f" [matched: {matched_key}]"
        print(status)

    return synced, stats


def save_collection(data, output_file):
    """Guarda la colección sincronizada"""
    print(f"\n💾 Guardando: {output_file}")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Guardado correctamente")
    except Exception as e:
        print(f"❌ Error: {e}")


def print_stats(stats):
    """Muestra estadísticas"""
    print("\n" + "="*70)
    print("📊 RESULTADO DE LA SINCRONIZACIÓN")
    print("="*70)
    print(f"\n✅ Álbumes mantenidos: {stats['kept']}")
    print(f"➖ Álbumes eliminados: {stats['removed']}")

    print("\n📝 Por género:")
    for genre, gs in sorted(stats['by_genre'].items()):
        if gs['removed'] > 0 or gs['kept'] > 0:
            print(f"\n  {genre}:")
            print(f"    Original:   {gs['original']}")
            print(f"    Mantenidos: {gs['kept']}")
            print(f"    Eliminados: {gs['removed']}")
            if gs.get('matched_key'):
                print(f"    Match key:  '{gs['matched_key']}'")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Sincroniza colección Bandcamp usando album_id')
    parser.add_argument('--localStorage-file', required=True,
                       help='browser_data.json exportado desde sync_tools.html')
    parser.add_argument('--input', default='bandcamp_data.json',
                       help='Tu colección actual (default: bandcamp_data.json)')
    parser.add_argument('--output', default='bandcamp_data_synced.json',
                       help='Colección sincronizada (default: bandcamp_data_synced.json)')
    parser.add_argument('--debug', action='store_true',
                       help='Mostrar información detallada de debug')

    args = parser.parse_args()

    print("\n" + "="*70)
    print("🔄 SINCRONIZACIÓN BANDCAMP (ALBUM_ID)")
    print("="*70)
    print("🔑 Usando album_id/track_id de Bandcamp como identificador")

    # Cargar localStorage
    listened = load_listened_from_browser(args.localStorage_file, debug=args.debug)
    if not listened:
        print("\n❌ No hay datos de escuchados")
        return

    # Cargar colección
    collection = load_collection(args.input, debug=args.debug)
    if not collection:
        print("\n❌ No hay colección para sincronizar")
        return

    # Sincronizar
    synced, stats = sync_collection(collection, listened, debug=args.debug)

    # Guardar
    save_collection(synced, args.output)

    # Estadísticas
    print_stats(stats)

    if stats['removed'] == 0:
        print("\n⚠️  ADVERTENCIA: No se eliminó ningún álbum")
        print("\nPosibles causas:")
        print("   1. Los géneros en el JSON no coinciden con los de localStorage")
        print("   2. Los embeds no tienen album_id (corrupto)")
        print("   3. No has marcado álbumes como escuchados en el navegador")
        print("\n💡 Ejecuta de nuevo con --debug para más información")

    print("\n" + "="*70)
    print("✅ COMPLETADO")
    print("="*70)
    print(f"\n📝 Próximos pasos:")
    print(f"   1. Verifica: {args.output}")
    print(f"   2. Reemplaza: mv {args.output} {args.input}")
    print(f"   3. Regenera: python3 bc_static_generator_bandcamp_id.py --input {args.input}")
    print()


if __name__ == '__main__':
    main()
