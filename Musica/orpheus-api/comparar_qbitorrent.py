#!/usr/bin/env python3

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from sops_env import load_sops_env

load_sops_env()

# -----------------------
# CONFIGURACION
# -----------------------

ORPHEUS_API_KEY = os.getenv("ORPHEUS_APIKEY")
ORPHEUS_USER_ID = int(os.getenv("ORPHEUS_USER_ID", "0"))

CACHE_DIR = Path("/home/huan/Scripts/Musica/orpheus-api/.cache")
ORPHEUS_CACHE = CACHE_DIR / "orpheus_seeding.json"
QBIT_CACHE = CACHE_DIR / "qbittorrent.json"

QBIT_URL = os.getenv("QBIT_URL")
QBIT_USER = os.getenv("QBIT_USER")
QBIT_PASS = os.getenv("QBIT_PASS")

ORPHEUS_RE = re.compile(r"torrentid=(\d+)")


# --------------------------------------------------
# CACHE
# --------------------------------------------------


def save_cache(path, data):
    CACHE_DIR.mkdir(exist_ok=True)

    payload = {
        "generated": datetime.now().isoformat(),
        "data": data,
    }

    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def load_cache(path):
    if not path.exists():
        return None

    with open(path) as f:
        return json.load(f)["data"]


# --------------------------------------------------
# ORPHEUS
# --------------------------------------------------


def get_orpheus_seeding():
    headers = {"Authorization": f"token {ORPHEUS_API_KEY}"}

    torrent_ids = set()
    page = 1

    while True:
        r = requests.get(
            "https://orpheus.network/ajax.php",
            headers=headers,
            params={
                "action": "user_torrents",
                "userid": ORPHEUS_USER_ID,
                "type": "seeding",
                "limit": 500,
                "page": page,
            },
            timeout=60,
        )

        r.raise_for_status()

        data = r.json()
        torrents = data["response"]["seeding"]

        if not torrents:
            break

        for torrent in torrents:
            torrent_ids.add(int(torrent["torrentId"]))

        print(f"[ORPHEUS] page={page} torrents={len(torrents)}")

        if len(torrents) < 500:
            break

        page += 1

    return torrent_ids


def get_orpheus_seeding_cached(use_cache=True):
    if use_cache:
        cached = load_cache(ORPHEUS_CACHE)

        if cached is not None:
            print("[CACHE] Orpheus")
            return set(cached)

    print("[API] Orpheus")

    torrent_ids = get_orpheus_seeding()

    save_cache(
        ORPHEUS_CACHE,
        sorted(torrent_ids),
    )

    return torrent_ids


# --------------------------------------------------
# QBIT
# --------------------------------------------------


def login(session):
    r = session.post(
        f"{QBIT_URL}/api/v2/auth/login",
        data={
            "username": QBIT_USER,
            "password": QBIT_PASS,
        },
        timeout=30,
    )

    if r.text != "Ok.":
        raise RuntimeError("Login qBittorrent failed")


def get_torrents(session):
    r = session.get(
        f"{QBIT_URL}/api/v2/torrents/info",
        timeout=60,
    )

    r.raise_for_status()

    return r.json()


def get_properties(session, torrent_hash):
    r = session.get(
        f"{QBIT_URL}/api/v2/torrents/properties",
        params={"hash": torrent_hash},
        timeout=30,
    )

    r.raise_for_status()

    return r.json()


def get_qbit_torrents(session):
    torrents = get_torrents(session)

    result = []

    total = len(torrents)

    for idx, torrent in enumerate(torrents, start=1):

        if idx % 100 == 0:
            print(f"[QBIT] {idx}/{total}")

        try:
            props = get_properties(
                session,
                torrent["hash"],
            )

        except Exception as e:
            print(
                f"[ERROR] {torrent['name']} -> {e}"
            )
            continue

        comment = props.get("comment", "")

        if not comment:
            continue

        match = ORPHEUS_RE.search(comment)

        if not match:
            continue

        result.append(
            {
                "torrent_id": int(match.group(1)),
                "hash": torrent["hash"],
                "name": torrent["name"],
            }
        )

    return result


def get_qbit_torrents_cached(session, use_cache=True):
    if use_cache:
        cached = load_cache(QBIT_CACHE)

        if cached is not None:
            print("[CACHE] qBittorrent")
            return cached

    print("[API] qBittorrent")

    data = get_qbit_torrents(session)

    save_cache(
        QBIT_CACHE,
        data,
    )

    return data

def delete_torrents(session, hashes):
    r = session.post(
        f"{QBIT_URL}/api/v2/torrents/delete",
        data={
            "hashes": "|".join(hashes),
            "deleteFiles": False,
        },
        timeout=60,
    )
    r.raise_for_status()


def pause_torrents(session, hashes):
    r = session.post(
        f"{QBIT_URL}/api/v2/torrents/pause",
        data={
            "hashes": "|".join(hashes),
        },
        timeout=60,
    )
    r.raise_for_status()


def resume_torrents(session, hashes):
    r = session.post(
        f"{QBIT_URL}/api/v2/torrents/resume",
        data={
            "hashes": "|".join(hashes),
        },
        timeout=60,
    )
    r.raise_for_status()


# --------------------------------------------------
# MAIN
# --------------------------------------------------


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--no-cache",
        action="store_true",
    )

    actions = parser.add_mutually_exclusive_group()

    actions.add_argument(
        "--pause",
        action="store_true",
    )

    actions.add_argument(
        "--resume",
        action="store_true",
    )

    actions.add_argument(
        "--delete",
        action="store_true",
    )

    args = parser.parse_args()

    use_cache = not args.no_cache

    print("Loading Orpheus...")
    orpheus_ids = get_orpheus_seeding_cached(
        use_cache=use_cache
    )

    print(f"Orpheus seeding: {len(orpheus_ids)}")

    print("Login qBittorrent...")

    session = requests.Session()

    login(session)

    qbit_torrents = get_qbit_torrents_cached(
        session,
        use_cache=use_cache,
    )

    print(
        f"qBittorrent Orpheus torrents: "
        f"{len(qbit_torrents)}"
    )

    missing = []

    for torrent in qbit_torrents:

        torrent_id = torrent["torrent_id"]

        if torrent_id not in orpheus_ids:
            missing.append(
                {
                    "torrent_id": torrent_id,
                    "hash": torrent["hash"],
                    "name": torrent["name"],
                }
            )

    print("\n=== RESULTS ===")
    print(f"Orpheus seeding : {len(orpheus_ids)}")
    print(f"qBittorrent     : {len(qbit_torrents)}")
    print(f"Missing         : {len(missing)}")

    if missing:
        print("\n=== IN QBIT BUT NOT IN ORPHEUS ===")

        for item in sorted(
            missing,
            key=lambda x: x["torrent_id"]
        ):
            print(
                f'{item["torrent_id"]} | '
                f'{item["name"]}'
            )

    hashes = [
        item["hash"]
        for item in missing
    ]

    if not hashes:
        return

    if args.pause:

        print(
            f"\nPausing {len(hashes)} torrents..."
        )

        pause_torrents(
            session,
            hashes,
        )

    elif args.resume:

        print(
            f"\nResuming {len(hashes)} torrents..."
        )

        resume_torrents(
            session,
            hashes,
        )

    elif args.delete:

        answer = input(
            f"\nDelete {len(hashes)} torrents? [y/N] "
        )

        if answer.lower() != "y":
            print("Cancelled")
            return

        delete_torrents(
            session,
            hashes,
        )

        print(
            f"Deleted {len(hashes)} torrents."
        )


if __name__ == "__main__":
    main()
