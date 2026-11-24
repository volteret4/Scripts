#!/usr/bin/env python3
import os
import json
import argparse
import subprocess

def analyze_flac(file_path):
    """Devuelve sample_rate y bits_per_sample de un archivo FLAC."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate,bits_per_sample",
             "-of", "json", file_path],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        sample_rate = int(stream.get("sample_rate", 0))
        bits_per_sample = int(stream.get("bits_per_sample", 0))
        return sample_rate, bits_per_sample
    except Exception as e:
        print(f"[ERROR] No se pudo analizar {file_path}: {e}")
        return 0, 0


def convert_to_16bit_44100(file_path):
    """Convierte el archivo FLAC a 16 bits / 44100 Hz."""
    tmp_file = f"{file_path}.tmp.flac"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path,
            "-ar", "44100", "-sample_fmt", "s16",
            "-map_metadata", "0", tmp_file
        ], check=True)
        os.replace(tmp_file, file_path)
        print(f"[OK] Convertido: {file_path}")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Falló conversión de {file_path}: {e}")
        if os.path.exists(tmp_file):
            os.remove(tmp_file)


def process_directory(base_path):
    """Recorre el directorio recursivamente y convierte FLACs si exceden los límites."""
    for root, _, files in os.walk(base_path):
        for file in files:
            if not file.lower().endswith(".flac"):
                continue

            file_path = os.path.join(root, file)
            sample_rate, bits = analyze_flac(file_path)

            if bits > 16 or sample_rate > 44100:
                print(f"[INFO] {file_path}: {bits} bits, {sample_rate} Hz → CONVERTIR")
                convert_to_16bit_44100(file_path)
            else:
                print(f"[OK] {file_path}: {bits} bits, {sample_rate} Hz → OK")


def main():
    parser = argparse.ArgumentParser(
        description="Convierte archivos FLAC mayores de 16 bits o 44100 Hz a ese formato."
    )
    parser.add_argument("--path", required=True, help="Ruta del directorio a analizar")

    args = parser.parse_args()
    base_path = os.path.abspath(args.path)

    if not os.path.isdir(base_path):
        print(f"[ERROR] {base_path} no es un directorio válido.")
        return

    print(f"Analizando: {base_path}\n")
    process_directory(base_path)


if __name__ == "__main__":
    main()
