#!/usr/bin/env python3
import requests
import hashlib
import time
import argparse
import sys
import os
import json
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, ConnectionError, Timeout, SSLError

# === CARGAR VARIABLES DEL .env ===
load_dotenv()

LISTENBRAINZ_USER = os.getenv("LISTENBRAINZ_USER")
LASTFM_USER = os.getenv("LASTFM_USER")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")
LASTFM_SESSION_KEY = os.getenv("LASTFM_SESSION_KEY")

LIMIT = 100  # cantidad de scrobbles a comparar


# === CONFIGURACIÓN ROBUSTA DE REQUESTS ===

def create_robust_session():
    """Crea una sesión de requests con configuración robusta para manejar errores de red"""
    session = requests.Session()

    # Configurar estrategia de reintentos
    retry_strategy = Retry(
        total=3,  # máximo 3 reintentos
        status_forcelist=[429, 500, 502, 503, 504],  # códigos de estado a reintentar
        backoff_factor=1,  # esperar 1, 2, 4 segundos entre reintentos
        allowed_methods=["HEAD", "GET", "POST"]  # métodos permitidos para reintentar
    )

    # Configurar adaptador HTTP con reintentos
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Configurar headers para parecer más "humano"
    session.headers.update({
        'User-Agent': 'ListenBrainz-to-LastFM-Sync/1.0 (Python/requests)',
        'Accept': 'application/json',
        'Connection': 'keep-alive'
    })

    return session


def robust_request(session, method, url, **kwargs):
    """Realiza una petición HTTP robusta con manejo de errores"""
    # Configurar timeouts por defecto si no se especifican
    if 'timeout' not in kwargs:
        kwargs['timeout'] = (10, 30)  # (connect_timeout, read_timeout)

    max_attempts = 3
    base_delay = 2

    for attempt in range(max_attempts):
        try:
            if method.upper() == 'GET':
                response = session.get(url, **kwargs)
            elif method.upper() == 'POST':
                response = session.post(url, **kwargs)
            else:
                raise ValueError(f"Método HTTP no soportado: {method}")

            response.raise_for_status()
            return response

        except (ConnectionError, SSLError, Timeout) as e:
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)  # backoff exponencial
                print(f"⚠️ Error de conexión (intento {attempt + 1}/{max_attempts}): {str(e)[:100]}...")
                print(f"🔄 Reintentando en {delay} segundos...")
                time.sleep(delay)
                continue
            else:
                print(f"❌ Error de conexión persistente después de {max_attempts} intentos:")
                print(f"   {str(e)}")
                raise

        except RequestException as e:
            print(f"❌ Error en la petición HTTP: {str(e)}")
            raise

        except Exception as e:
            print(f"❌ Error inesperado: {str(e)}")
            raise


# Crear sesión global robusta
SESSION = create_robust_session()


# === FUNCIONES ===

def get_listenbrainz_scrobbles(user, limit=100, min_ts=None, max_ts=None):
    """Obtiene scrobbles de ListenBrainz con manejo robusto de errores y paginación"""
    url = f"https://api.listenbrainz.org/1/user/{user}/listens?count={limit}"

    # Añadir parámetros de tiempo si se especifican
    if min_ts:
        url += f"&min_ts={min_ts}"
    if max_ts:
        url += f"&max_ts={max_ts}"

    print(f"🔍 Conectando a ListenBrainz API para usuario: {user}")
    if min_ts or max_ts:
        min_date = format_timestamp(min_ts) if min_ts else "inicio"
        max_date = format_timestamp(max_ts) if max_ts else "ahora"
        print(f"📅 Rango temporal: {min_date} → {max_date}")

    try:
        r = robust_request(SESSION, 'GET', url)
        data = r.json()

        if "payload" not in data or "listens" not in data["payload"]:
            print("⚠️ Respuesta inesperada de ListenBrainz API")
            return []

        listens = data["payload"]["listens"]
        print(f"✅ Obtenidos {len(listens)} scrobbles de ListenBrainz")

        scrobbles = [
            {
                "artist": l["track_metadata"]["artist_name"],
                "track": l["track_metadata"]["track_name"],
                "album": l["track_metadata"].get("release_name", ""),
                "timestamp": l["listened_at"],
                "listenbrainz_id": l.get("recording_msid", ""),
            }
            for l in listens
        ]

        # Mostrar rango temporal obtenido
        if scrobbles:
            oldest = min(s["timestamp"] for s in scrobbles)
            newest = max(s["timestamp"] for s in scrobbles)
            print(f"📅 Rango obtenido: {format_timestamp(oldest)} → {format_timestamp(newest)}")

        return scrobbles

    except Exception as e:
        print(f"❌ Error al obtener scrobbles de ListenBrainz: {str(e)}")
        print("💡 Sugerencias:")
        print("   - Verifica tu conexión a internet")
        print("   - Comprueba que el usuario de ListenBrainz sea correcto")
        print("   - Intenta con un limit menor")
        sys.exit(1)


def find_historical_range(user, lastfm_oldest_ts):
    """Encuentra el rango de scrobbles históricos que no están en Last.fm"""
    print("🕰️ Explorando scrobbles históricos en ListenBrainz...")

    # Obtener los scrobbles más antiguos disponibles
    oldest_scrobbles = get_listenbrainz_scrobbles(user, limit=1, max_ts=lastfm_oldest_ts-1)

    if not oldest_scrobbles:
        print("📅 No hay scrobbles más antiguos que los de Last.fm")
        return None, None

    oldest_available = oldest_scrobbles[0]["timestamp"]
    print(f"📅 Scrobble más antiguo en ListenBrainz: {format_timestamp(oldest_available)}")
    print(f"📅 Scrobble más antiguo en Last.fm: {format_timestamp(lastfm_oldest_ts)}")

    # Calcular el rango de días
    days_diff = (lastfm_oldest_ts - oldest_available) / (24 * 3600)
    print(f"📊 Diferencia: {days_diff:.1f} días de scrobbles históricos")

    return oldest_available, lastfm_oldest_ts - 1


def get_historical_scrobbles_batch(user, start_ts, end_ts, batch_size=1000):
    """Obtiene scrobbles históricos en lotes para manejar grandes cantidades"""
    print(f"\n📚 Obteniendo scrobbles históricos en lotes de {batch_size}")
    print(f"📅 Desde: {format_timestamp(start_ts)}")
    print(f"📅 Hasta: {format_timestamp(end_ts)}")

    all_scrobbles = []
    current_max_ts = end_ts
    batch_num = 1

    while current_max_ts > start_ts:
        print(f"\n📦 Lote {batch_num}: ", end="")

        batch_scrobbles = get_listenbrainz_scrobbles(
            user,
            limit=batch_size,
            max_ts=current_max_ts
        )

        if not batch_scrobbles:
            print("No hay más scrobbles")
            break

        # Filtrar solo los scrobbles en el rango deseado
        filtered_batch = [s for s in batch_scrobbles if s["timestamp"] >= start_ts]
        all_scrobbles.extend(filtered_batch)

        # Preparar para el siguiente lote
        oldest_in_batch = min(s["timestamp"] for s in batch_scrobbles)

        if oldest_in_batch >= current_max_ts:
            print("⚠️ No se puede paginar más (mismo timestamp)")
            break

        current_max_ts = oldest_in_batch - 1
        batch_num += 1

        print(f"Total acumulado: {len(all_scrobbles)}")

        # Pausa entre lotes para ser respetuoso con la API
        time.sleep(0.5)

        # Límite de seguridad
        if batch_num > 50:
            print("⚠️ Límite de lotes alcanzado (50), usa rangos más específicos")
            break

    print(f"\n✅ Total de scrobbles históricos obtenidos: {len(all_scrobbles)}")
    return all_scrobbles
    """Obtiene scrobbles de Last.fm usando solo API de lectura con manejo robusto"""
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "user.getrecenttracks",
        "user": user,
        "api_key": api_key,
        "limit": limit,
        "format": "json",
    }

    print(f"🔍 Conectando a Last.fm API para usuario: {user}")
    try:
        r = robust_request(SESSION, 'GET', url, params=params)
        data = r.json()

        if "recenttracks" not in data or "track" not in data["recenttracks"]:
            if "error" in data:
                print(f"❌ Error de Last.fm API: {data['message']}")
            else:
                print("⚠️ No se pudieron obtener scrobbles de Last.fm.")
            sys.exit(1)

        tracks = data["recenttracks"]["track"]

        # Manejar caso donde solo hay 1 track (no es lista)
        if isinstance(tracks, dict):
            tracks = [tracks]

        result = []
        for t in tracks:
            if "date" in t:  # Solo tracks que ya fueron scrobbleados (no "now playing")
                result.append({
                    "artist": t["artist"]["#text"],
                    "track": t["name"],
                    "album": t["album"]["#text"],
                    "timestamp": int(t["date"]["uts"]),
                })

        print(f"✅ Obtenidos {len(result)} scrobbles de Last.fm")
        return result

    except Exception as e:
        print(f"❌ Error al obtener scrobbles de Last.fm: {str(e)}")
        print("💡 Sugerencias:")
        print("   - Verifica tu API key de Last.fm")
        print("   - Comprueba que el usuario de Last.fm sea correcto")
        print("   - Verifica tu conexión a internet")
        sys.exit(1)


def get_lastfm_scrobbles(user, api_key, limit=100):
    """Obtiene scrobbles de Last.fm usando solo API de lectura con manejo robusto"""
    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "user.getrecenttracks",
        "user": user,
        "api_key": api_key,
        "limit": limit,
        "format": "json",
    }

    print(f"🔍 Conectando a Last.fm API para usuario: {user}")
    try:
        r = robust_request(SESSION, 'GET', url, params=params)
        data = r.json()

        if "recenttracks" not in data or "track" not in data["recenttracks"]:
            if "error" in data:
                print(f"❌ Error de Last.fm API: {data['message']}")
            else:
                print("⚠️ No se pudieron obtener scrobbles de Last.fm.")
            sys.exit(1)

        tracks = data["recenttracks"]["track"]

        # Manejar caso donde solo hay 1 track (no es lista)
        if isinstance(tracks, dict):
            tracks = [tracks]

        result = []
        for t in tracks:
            if "date" in t:  # Solo tracks que ya fueron scrobbleados (no "now playing")
                result.append({
                    "artist": t["artist"]["#text"],
                    "track": t["name"],
                    "album": t["album"]["#text"],
                    "timestamp": int(t["date"]["uts"]),
                })

        print(f"✅ Obtenidos {len(result)} scrobbles de Last.fm")
        return result

    except Exception as e:
        print(f"❌ Error al obtener scrobbles de Last.fm: {str(e)}")
        print("💡 Sugerencias:")
        print("   - Verifica tu API key de Last.fm")
        print("   - Comprueba que el usuario de Last.fm sea correcto")
        print("   - Verifica tu conexión a internet")
        sys.exit(1)


def lastfm_api_sig(params, secret):
    """Genera la firma md5 que requiere Last.fm para escritura"""
    sig_str = "".join(f"{k}{v}" for k, v in sorted(params.items())) + secret
    return hashlib.md5(sig_str.encode("utf-8")).hexdigest()


def format_timestamp(timestamp):
    """Convierte timestamp a fecha legible"""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def analyze_scrobbles_to_upload(scrobbles):
    """Analiza los scrobbles y genera estadísticas"""
    # Inicializar estructura base que siempre se retorna
    base_analysis = {
        "total_scrobbles": len(scrobbles),
        "date_range": {},
        "daily_distribution": {},
        "top_artists": {},
        "top_albums": {},
        "unique_artists": 0,
        "unique_albums": 0
    }

    if not scrobbles:
        return base_analysis

    # Agrupar por día
    daily_counts = defaultdict(int)
    artists = defaultdict(int)
    albums = defaultdict(int)

    timestamps = [s["timestamp"] for s in scrobbles]
    min_ts = min(timestamps)
    max_ts = max(timestamps)

    for scrobble in scrobbles:
        # Contar por día
        date_str = datetime.fromtimestamp(scrobble["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d")
        daily_counts[date_str] += 1

        # Contar artistas y álbumes
        artists[scrobble["artist"]] += 1
        if scrobble["album"]:
            albums[scrobble["album"]] += 1

    # Actualizar con datos reales
    base_analysis.update({
        "date_range": {
            "from": format_timestamp(min_ts),
            "to": format_timestamp(max_ts),
            "from_timestamp": min_ts,
            "to_timestamp": max_ts
        },
        "daily_distribution": dict(daily_counts),
        "top_artists": dict(sorted(artists.items(), key=lambda x: x[1], reverse=True)[:10]),
        "top_albums": dict(sorted(albums.items(), key=lambda x: x[1], reverse=True)[:10]) if albums else {},
        "unique_artists": len(artists),
        "unique_albums": len(albums) if albums else 0
    })

    return base_analysis


def save_scrobbles_json(scrobbles, filename="scrobbles_to_upload.json"):
    """Guarda los scrobbles en un archivo JSON"""
    data = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_scrobbles": len(scrobbles),
            "script_version": "enhanced_1.0"
        },
        "analysis": analyze_scrobbles_to_upload(scrobbles),
        "scrobbles": scrobbles
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return filename


def print_analysis_summary(analysis):
    """Imprime un resumen detallado del análisis"""
    print("\n" + "="*60)
    print("📊 RESUMEN DE SCROBBLES A AÑADIR")
    print("="*60)

    if analysis["total_scrobbles"] == 0:
        print("🎯 No hay scrobbles nuevos para añadir.")
        return

    print(f"🎧 Total de scrobbles: {analysis['total_scrobbles']:,}")
    print(f"📅 Período: {analysis['date_range']['from']} → {analysis['date_range']['to']}")
    print(f"🎵 Artistas únicos: {analysis['unique_artists']}")
    if analysis['unique_albums'] > 0:
        print(f"💿 Álbumes únicos: {analysis['unique_albums']}")

    print("\n📈 DISTRIBUCIÓN POR DÍAS:")
    for date, count in sorted(analysis['daily_distribution'].items()):
        print(f"  {date}: {count:3d} scrobbles")

    print("\n🎤 TOP 10 ARTISTAS:")
    for i, (artist, count) in enumerate(analysis['top_artists'].items(), 1):
        print(f"  {i:2d}. {artist} ({count} scrobbles)")

    if analysis['top_albums']:
        print("\n💿 TOP 10 ÁLBUMES:")
        for i, (album, count) in enumerate(analysis['top_albums'].items(), 1):
            print(f"  {i:2d}. {album} ({count} scrobbles)")


def scrobble_to_lastfm(track, api_key, secret, session_key, dry_run=False):
    """Envía un scrobble a Last.fm (solo si no es dry-run) con manejo robusto"""
    if dry_run:
        # En dry-run, solo mostramos información sin hacer llamadas de escritura
        return True

    # Validar que el timestamp no sea demasiado futuro o muy antiguo
    current_time = int(time.time())
    track_time = int(track["timestamp"])

    # Last.fm rechaza scrobbles del futuro o de más de 14 días de antigüedad en algunos casos
    if track_time > current_time:
        print(f"⚠️ Scrobble del futuro rechazado: {track['artist']} - {track['track']} (timestamp futuro)")
        return False

    # Para scrobbles muy antiguos, Last.fm puede ser más permisivo, pero vamos a verificar
    min_allowed_time = 946684800  # 1 enero 2000 UTC
    if track_time < min_allowed_time:
        print(f"⚠️ Timestamp muy antiguo: {track['artist']} - {track['track']} ({format_timestamp(track_time)})")
        return False

    url = "https://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "track.scrobble",
        "artist[0]": track["artist"][:255],  # Limitar longitud
        "track[0]": track["track"][:255],    # Limitar longitud
        "timestamp[0]": str(track_time),
        "api_key": api_key,
        "sk": session_key,
    }

    # Solo añadir álbum si existe y no está vacío
    if track.get("album") and track["album"].strip():
        params["album[0]"] = track["album"][:255]  # Limitar longitud

    sig = lastfm_api_sig(params, secret)
    params["api_sig"] = sig
    params["format"] = "json"

    try:
        r = robust_request(SESSION, 'POST', url, data=params)
        response_data = r.json()

        # Verificar diferentes tipos de respuesta de Last.fm
        if "scrobbles" in response_data:
            scrobbles_data = response_data["scrobbles"]
            if "@attr" in scrobbles_data:
                accepted = int(scrobbles_data["@attr"].get("accepted", 0))
                ignored = int(scrobbles_data["@attr"].get("ignored", 0))

                if accepted > 0:
                    print(f"✅ Scrobble enviado: {track['artist']} - {track['track']}")
                    return True
                else:
                    print(f"⚠️ Scrobble ignorado: {track['artist']} - {track['track']}")
                    if "scrobble" in scrobbles_data and scrobbles_data["scrobble"]:
                        scrobble_info = scrobbles_data["scrobble"]
                        if isinstance(scrobble_info, list):
                            scrobble_info = scrobble_info[0]
                        if "ignoredMessage" in scrobble_info:
                            print(f"   Motivo: {scrobble_info['ignoredMessage']['#text']}")
                    return False

        # Si llegamos aquí, hay un error
        if "error" in response_data:
            print(f"❌ Error API Last.fm: {response_data.get('message', 'Error desconocido')}")
        else:
            print(f"⚠️ Respuesta inesperada de Last.fm: {response_data}")

        return False

    except Exception as e:
        print(f"⚠️ Error de conexión: {track['artist']} - {track['track']}")
        print(f"   Error: {str(e)[:100]}...")
        return False


def load_scrobbles_from_json(filename):
    """Carga scrobbles desde un archivo JSON generado previamente"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("scrobbles", [])
    except FileNotFoundError:
        print(f"❌ Archivo {filename} no encontrado.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ Error al leer JSON desde {filename}.")
        sys.exit(1)


# === MAIN ===

def parse_date_to_timestamp(date_str):
    """Convierte una fecha YYYY-MM-DD a timestamp UTC"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        print(f"❌ Formato de fecha inválido: {date_str}. Usa YYYY-MM-DD")
        sys.exit(1)


def test_api_connections():
    """Prueba las conexiones a las APIs antes de proceder"""
    print("🔧 Probando conexiones a las APIs...")

    # Probar ListenBrainz (endpoint público)
    try:
        url = "https://api.listenbrainz.org/1/stats/sitewide/artists"
        r = robust_request(SESSION, 'GET', url, timeout=(5, 10))
        print("✅ Conexión a ListenBrainz: OK")
    except Exception as e:
        print(f"❌ Conexión a ListenBrainz: FALLO ({str(e)[:50]}...)")
        return False

    # Probar Last.fm (endpoint público)
    try:
        url = "https://ws.audioscrobbler.com/2.0/"
        params = {"method": "chart.gettopartists", "api_key": LASTFM_API_KEY, "format": "json", "limit": "1"}
        r = robust_request(SESSION, 'GET', url, params=params, timeout=(5, 10))
        print("✅ Conexión a Last.fm: OK")
    except Exception as e:
        print(f"❌ Conexión a Last.fm: FALLO ({str(e)[:50]}...)")
        return False

    print("🌐 Todas las conexiones funcionan correctamente\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sincroniza tus scrobbles de ListenBrainz con Last.fm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Análisis en seco de scrobbles recientes (recomendado primero)
  python script.py --dry-run --limit 500

  # Buscar scrobbles históricos automáticamente
  python script.py --dry-run --historical --batch-size 2000

  # Buscar en un rango de fechas específico
  python script.py --dry-run --from-date 2020-01-01 --to-date 2022-12-31

  # Cargar desde JSON generado previamente
  python script.py --from-json scrobbles_to_upload.json

  # Subir scrobbles reales (después del dry-run)
  python script.py --limit 500

  # Probar solo las conexiones
  python script.py --test-connection
        """
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Analiza qué se subiría sin modificar Last.fm. Genera JSON para revisión.")
    parser.add_argument("--limit", type=int, default=LIMIT,
                        help="Cantidad de scrobbles a comparar (default: 100)")
    parser.add_argument("--from-json", type=str, metavar="FILE",
                        help="Carga scrobbles desde un archivo JSON generado previamente")
    parser.add_argument("--output-json", type=str, default="scrobbles_to_upload.json",
                        help="Nombre del archivo JSON a generar en dry-run (default: scrobbles_to_upload.json)")
    parser.add_argument("--test-connection", action="store_true",
                        help="Solo prueba las conexiones a las APIs y sale")
    parser.add_argument("--historical", action="store_true",
                        help="Busca scrobbles históricos (más antiguos que los de Last.fm)")
    parser.add_argument("--from-date", type=str, metavar="YYYY-MM-DD",
                        help="Fecha de inicio para buscar scrobbles (formato: 2020-01-01)")
    parser.add_argument("--to-date", type=str, metavar="YYYY-MM-DD",
                        help="Fecha de fin para buscar scrobbles (formato: 2023-12-31)")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Tamaño de lote para scrobbles históricos (default: 1000)")
    parser.add_argument("--test-upload", type=int, metavar="N",
                        help="Probar subiendo solo los primeros N scrobbles (para debugging)")
    parser.add_argument("--debug", action="store_true",
                        help="Mostrar información de debugging detallada")
    args = parser.parse_args()

    # Probar conexiones si se solicita
    if args.test_connection:
        if not all([LASTFM_API_KEY]):
            print("❌ Falta LASTFM_API_KEY para probar conexiones.")
            sys.exit(1)
        success = test_api_connections()
        sys.exit(0 if success else 1)

    # Si cargamos desde JSON, no necesitamos todas las credenciales
    if args.from_json:
        if not all([LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_SESSION_KEY]):
            print("❌ Faltan credenciales de Last.fm para subir scrobbles.")
            sys.exit(1)

        print(f"📁 Cargando scrobbles desde {args.from_json}...")
        scrobbles_to_upload = load_scrobbles_from_json(args.from_json)

        if not scrobbles_to_upload:
            print("ℹ️ No hay scrobbles en el archivo JSON.")
            return

        # Modo de prueba: solo subir algunos scrobbles
        if args.test_upload:
            print(f"🧪 Modo de prueba: solo se subirán los primeros {args.test_upload} scrobbles")
            scrobbles_to_upload = scrobbles_to_upload[:args.test_upload]

        analysis = analyze_scrobbles_to_upload(scrobbles_to_upload)
        print_analysis_summary(analysis)

        # Mostrar información de debugging si se solicita
        if args.debug and scrobbles_to_upload:
            print("\n🔍 INFORMACIÓN DE DEBUG:")
            sample_scrobble = scrobbles_to_upload[0]
            print(f"Ejemplo de scrobble: {json.dumps(sample_scrobble, indent=2)}")
            print(f"Timestamp ejemplo: {sample_scrobble['timestamp']} → {format_timestamp(sample_scrobble['timestamp'])}")
            current_time = int(time.time())
            print(f"Tiempo actual: {current_time} → {format_timestamp(current_time)}")
            print(f"Diferencia: {(current_time - sample_scrobble['timestamp']) / (24*3600):.1f} días")

        if not args.test_upload:
            confirm = input(f"\n¿Continuar con la subida de {len(scrobbles_to_upload)} scrobbles? [y/N]: ")
            if confirm.lower() != 'y':
                print("❌ Operación cancelada.")
                return

    else:
        # Flujo normal: obtener datos de APIs
        if not all([LISTENBRAINZ_USER, LASTFM_USER, LASTFM_API_KEY]):
            print("❌ Faltan variables básicas en el archivo .env.")
            sys.exit(1)

        if not args.dry_run and not all([LASTFM_API_SECRET, LASTFM_SESSION_KEY]):
            print("❌ Faltan credenciales de Last.fm para subir scrobbles.")
            print("💡 Usa --dry-run para análisis sin subir.")
            sys.exit(1)

        # Probar conexiones antes de proceder
        if not test_api_connections():
            print("❌ No se pueden alcanzar las APIs. Verifica tu conexión.")
            sys.exit(1)

        # Determinar modo de operación: histórico vs reciente
        if args.historical or args.from_date or args.to_date:
            print("🕰️ Modo histórico activado")

            # Obtener algunos scrobbles de Last.fm para determinar el rango
            lfm_scrobbles = get_lastfm_scrobbles(LASTFM_USER, LASTFM_API_KEY, args.limit)

            if args.from_date or args.to_date:
                # Usar fechas específicas
                start_ts = parse_date_to_timestamp(args.from_date) if args.from_date else None
                end_ts = parse_date_to_timestamp(args.to_date) if args.to_date else None

                if args.from_date and args.to_date:
                    print(f"📅 Buscando entre {args.from_date} y {args.to_date}")
                    lb_scrobbles = get_historical_scrobbles_batch(
                        LISTENBRAINZ_USER, start_ts, end_ts, args.batch_size
                    )
                elif args.from_date:
                    print(f"📅 Buscando desde {args.from_date}")
                    lb_scrobbles = get_listenbrainz_scrobbles(
                        LISTENBRAINZ_USER, args.limit, min_ts=start_ts
                    )
                else:  # args.to_date
                    print(f"📅 Buscando hasta {args.to_date}")
                    lb_scrobbles = get_listenbrainz_scrobbles(
                        LISTENBRAINZ_USER, args.limit, max_ts=end_ts
                    )
            else:
                # Modo automático: buscar antes del scrobble más antiguo de Last.fm
                if lfm_scrobbles:
                    oldest_lastfm = min(s["timestamp"] for s in lfm_scrobbles)
                    start_ts, end_ts = find_historical_range(LISTENBRAINZ_USER, oldest_lastfm)

                    if start_ts and end_ts:
                        lb_scrobbles = get_historical_scrobbles_batch(
                            LISTENBRAINZ_USER, start_ts, end_ts, args.batch_size
                        )
                    else:
                        lb_scrobbles = []
                else:
                    print("❌ No se pudieron obtener scrobbles de Last.fm para referencia")
                    sys.exit(1)
        else:
            # Modo normal: obtener scrobbles recientes
            print("📡 Obteniendo scrobbles recientes...")
            lb_scrobbles = get_listenbrainz_scrobbles(LISTENBRAINZ_USER, args.limit)
            lfm_scrobbles = get_lastfm_scrobbles(LASTFM_USER, LASTFM_API_KEY, args.limit)

        print(f"📊 ListenBrainz: {len(lb_scrobbles)} scrobbles")
        print(f"📊 Last.fm: {len(lfm_scrobbles)} scrobbles")

        # Comparar por artista, track y timestamp para evitar duplicados
        lfm_signatures = {(s["artist"], s["track"], s["timestamp"]) for s in lfm_scrobbles}

        print(f"🔍 Creadas {len(lfm_signatures)} firmas únicas de Last.fm")

        scrobbles_to_upload = [
            s for s in lb_scrobbles
            if (s["artist"], s["track"], s["timestamp"]) not in lfm_signatures
        ]

        print(f"🎯 Scrobbles únicos encontrados: {len(scrobbles_to_upload)}")

        # Debug: mostrar algunos ejemplos si hay pocos
        if len(scrobbles_to_upload) <= 5 and len(scrobbles_to_upload) > 0:
            print("🔍 Ejemplos de scrobbles a subir:")
            for i, s in enumerate(scrobbles_to_upload[:3], 1):
                print(f"  {i}. {s['artist']} - {s['track']} [{format_timestamp(s['timestamp'])}]")

        # Debug: mostrar algunos ejemplos de Last.fm si no hay nada que subir
        if len(scrobbles_to_upload) == 0 and len(lfm_scrobbles) > 0:
            print("🔍 Ejemplos de scrobbles más recientes en Last.fm:")
            for i, s in enumerate(lfm_scrobbles[:3], 1):
                print(f"  {i}. {s['artist']} - {s['track']} [{format_timestamp(s['timestamp'])}]")
            print("🔍 Ejemplos de scrobbles más recientes en ListenBrainz:")
            for i, s in enumerate(lb_scrobbles[:3], 1):
                print(f"  {i}. {s['artist']} - {s['track']} [{format_timestamp(s['timestamp'])}]")

        analysis = analyze_scrobbles_to_upload(scrobbles_to_upload)
        print_analysis_summary(analysis)

        if not scrobbles_to_upload:
            print("\n✅ Todas las canciones ya están sincronizadas.")
            return

        if args.dry_run:
            # Guardar JSON para revisión posterior
            json_file = save_scrobbles_json(scrobbles_to_upload, args.output_json)
            print(f"\n💾 Scrobbles guardados en: {json_file}")
            print(f"🔍 Revisa el archivo y usa --from-json {json_file} para subir")
            print("\n✅ Dry-run completado. No se ha enviado nada a Last.fm.")
            return

    # Subir scrobbles (ya sea desde JSON o recién obtenidos)
    if not args.dry_run:
        print(f"\n🚀 Iniciando subida de {len(scrobbles_to_upload)} scrobbles...")
        success_count = 0
        failure_count = 0
        consecutive_failures = 0

        # Subir en orden cronológico (más antiguos primero)
        for i, scrobble in enumerate(reversed(scrobbles_to_upload), 1):
            print(f"[{i}/{len(scrobbles_to_upload)}] ", end="")

            if args.debug:
                print(f"\nDEBUG: {json.dumps(scrobble, indent=2)}")

            if scrobble_to_lastfm(scrobble, LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_SESSION_KEY):
                success_count += 1
                consecutive_failures = 0
            else:
                failure_count += 1
                consecutive_failures += 1

                # Si hay muchos fallos consecutivos, preguntar si continuar
                if consecutive_failures >= 10:
                    print(f"\n⚠️ {consecutive_failures} fallos consecutivos.")
                    continue_upload = input("¿Continuar? [y/N]: ")
                    if continue_upload.lower() != 'y':
                        print("❌ Subida cancelada por el usuario.")
                        break
                    consecutive_failures = 0

            time.sleep(1)  # Evitar rate limit

            # Mostrar progreso cada 100 scrobbles
            if i % 100 == 0:
                print(f"\n📊 Progreso: {i}/{len(scrobbles_to_upload)} - Éxitos: {success_count}, Fallos: {failure_count}")

        print(f"\n✅ Sincronización completada: {success_count}/{len(scrobbles_to_upload)} scrobbles subidos.")
        if failure_count > 0:
            print(f"⚠️ {failure_count} scrobbles no se pudieron subir.")
            print("💡 Los motivos más comunes:")
            print("   - Timestamps muy antiguos o futuros")
            print("   - Nombres de artista/canción muy largos")
            print("   - Tracks ya existentes en Last.fm")
            print("   - Problemas temporales de conectividad")


if __name__ == "__main__":
    main()
