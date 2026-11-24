import requests
import json

headers = {
    "Authorization": "token x+RTjmrZ7m61SfIwBqMH+MQolBBhLkqqpsKSi0yFboA03geqwUDcs09o2Xg2IGbHdX5tBZYoMX0L8v1oFSB+aoF4DYRRv0SYO2kohL/C5wVFNnReuOtD"
}

r = requests.get(
    "https://orpheus.network/ajax.php",
    headers=headers,
    params={
        "action": "user_torrents",
        "userid": 4856,
        "type": "seeding"
    }
)

print(r.status_code)
print(json.dumps(r.json(), indent=2))
