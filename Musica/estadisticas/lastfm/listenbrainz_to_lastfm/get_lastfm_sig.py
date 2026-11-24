import hashlib
# from dotenv import load_dotenv
import os
# load_dotenv()

api_key = os.getenv("LASTFM_API_KEY")
api_secret = os.getenv("LASTFM_API_SECRET")
token = os.getenv("LASTFM_SESSION_TOKEN")

cadena = f"api_key{api_key}methodauth.getSessiontoken{token}{api_secret}"
api_sig = hashlib.md5(cadena.encode("utf-8")).hexdigest()

print(api_sig)
