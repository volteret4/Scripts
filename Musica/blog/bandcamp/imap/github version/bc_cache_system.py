#!/usr/bin/env python3
"""
Sistema de caché para correos de Bandcamp
Evita descargar el mismo correo múltiples veces
Soporta múltiples cuentas, carpetas, estados (leído/no leído)
"""

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path


class EmailCache:
    """
    Gestiona un caché de correos procesados para evitar descargas duplicadas.

    Estructura del caché:
    {
        "server:email:folder:message_id": {
            "url": "https://...",
            "subject": "...",
            "date": "...",
            "embed": "...",
            "processed_at": "2024-11-04T12:00:00",
            "was_read": false,
            "genre": "Rock"
        }
    }
    """

    def __init__(self, cache_file='.bandcamp_cache.json'):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self):
        """Carga el caché desde disco"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print(f"⚠️  Error al leer caché, creando nuevo")
                return {}
        return {}

    def save(self):
        """Guarda el caché a disco"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"⚠️  Error al guardar caché: {e}")

    def _make_key(self, server, email, folder, message_id):
        """Genera una clave única para un correo"""
        return f"{server}:{email}:{folder}:{message_id}"

    def has(self, server, email, folder, message_id):
        """Verifica si un correo ya está en caché"""
        key = self._make_key(server, email, folder, message_id)
        return key in self.cache

    def get(self, server, email, folder, message_id):
        """Obtiene un correo del caché"""
        key = self._make_key(server, email, folder, message_id)
        return self.cache.get(key)

    def add(self, server, email, folder, message_id, embed_data):
        """Añade un correo al caché"""
        key = self._make_key(server, email, folder, message_id)

        # Añadir timestamp de procesamiento
        cache_entry = embed_data.copy()
        cache_entry['processed_at'] = datetime.now().isoformat()
        cache_entry['cache_key'] = key

        self.cache[key] = cache_entry

    def get_stats(self):
        """Obtiene estadísticas del caché"""
        return {
            'total_emails': len(self.cache),
            'servers': len(set(k.split(':')[0] for k in self.cache.keys())),
            'accounts': len(set(':'.join(k.split(':')[:2]) for k in self.cache.keys())),
            'folders': len(set(':'.join(k.split(':')[:3]) for k in self.cache.keys()))
        }

    def clean_old_entries(self, days=90):
        """Limpia entradas antiguas del caché"""
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        removed = 0

        keys_to_remove = []
        for key, entry in self.cache.items():
            if 'processed_at' in entry:
                try:
                    entry_time = datetime.fromisoformat(entry['processed_at']).timestamp()
                    if entry_time < cutoff:
                        keys_to_remove.append(key)
                except:
                    pass

        for key in keys_to_remove:
            del self.cache[key]
            removed += 1

        if removed > 0:
            self.save()
            print(f"🗑️  Limpiadas {removed} entradas antiguas del caché")

        return removed


class SyncTracker:
    """
    Rastrea qué álbumes se han agregado a la colección y cuáles se han eliminado.
    Esto permite distinguir entre:
    - Álbumes que nunca existieron en la colección
    - Álbumes que existieron pero el usuario los eliminó (escuchó)

    Estructura:
    {
        "genre": {
            "embed_id": {
                "url": "...",
                "added_at": "2024-11-04T12:00:00",
                "removed_at": "2024-11-05T15:30:00",  # Si fue eliminado
                "status": "active"|"removed"
            }
        }
    }
    """

    def __init__(self, tracker_file='.bandcamp_sync_tracker.json'):
        self.tracker_file = tracker_file
        self.tracker = self._load_tracker()

    def _load_tracker(self):
        """Carga el tracker desde disco"""
        if os.path.exists(self.tracker_file):
            try:
                with open(self.tracker_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def save(self):
        """Guarda el tracker a disco"""
        try:
            with open(self.tracker_file, 'w', encoding='utf-8') as f:
                json.dump(self.tracker, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"⚠️  Error al guardar tracker: {e}")

    def mark_as_added(self, genre, embed_id, url):
        """Marca un álbum como agregado a la colección"""
        if genre not in self.tracker:
            self.tracker[genre] = {}

        if embed_id not in self.tracker[genre]:
            self.tracker[genre][embed_id] = {
                'url': url,
                'added_at': datetime.now().isoformat(),
                'status': 'active'
            }

    def mark_as_removed(self, genre, embed_id):
        """Marca un álbum como eliminado de la colección"""
        if genre in self.tracker and embed_id in self.tracker[genre]:
            self.tracker[genre][embed_id]['removed_at'] = datetime.now().isoformat()
            self.tracker[genre][embed_id]['status'] = 'removed'

    def was_previously_added(self, genre, embed_id):
        """Verifica si un álbum fue agregado previamente (y posiblemente eliminado)"""
        return (genre in self.tracker and
                embed_id in self.tracker[genre])

    def was_removed(self, genre, embed_id):
        """Verifica si un álbum fue específicamente eliminado por el usuario"""
        if genre in self.tracker and embed_id in self.tracker[genre]:
            return self.tracker[genre][embed_id].get('status') == 'removed'
        return False

    def get_active_count(self, genre=None):
        """Obtiene el conteo de álbumes activos"""
        if genre:
            if genre not in self.tracker:
                return 0
            return sum(1 for e in self.tracker[genre].values()
                      if e.get('status') == 'active')

        # Total de todos los géneros
        return sum(sum(1 for e in embeds.values() if e.get('status') == 'active')
                  for embeds in self.tracker.values())


def get_embed_id(url):
    """Genera el mismo ID que usa el HTML para un embed"""
    return f"embed_{abs(hash(url))}"


if __name__ == '__main__':
    # Ejemplo de uso
    print("Sistema de Caché de Bandcamp - Demo\n")

    # Crear caché
    cache = EmailCache()
    stats = cache.get_stats()
    print(f"📊 Estadísticas del caché:")
    print(f"   Total correos: {stats['total_emails']}")
    print(f"   Servidores: {stats['servers']}")
    print(f"   Cuentas: {stats['accounts']}")
    print(f"   Carpetas: {stats['folders']}")

    # Crear tracker
    tracker = SyncTracker()
    print(f"\n📊 Álbumes activos: {tracker.get_active_count()}")

    print("\n✅ Sistema listo para usar")
    print("\nUso en bc_export_to_json.py:")
    print("  cache = EmailCache()")
    print("  if not cache.has(server, email, folder, message_id):")
    print("      # Procesar correo...")
    print("      cache.add(server, email, folder, message_id, embed_data)")
    print("      cache.save()")
