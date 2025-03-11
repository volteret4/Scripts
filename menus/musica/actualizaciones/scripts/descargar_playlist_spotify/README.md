# Requisitos

- qbitorrent con watchfolder e inicio automático
- modifica
- script descarga_finalizada.sh
- python venv con spotipy, tabulate, bencodepy


#### Activar watchfolder en qbittorrent

![watch_folder](.content/image-1.png)

Cambia el path a la ruta dentro del contenedor de qbitorrent
Añade el path cuando crees el contenedor, no he encontrado tus docker_compose.yml


#### Activar script en qbitorrent

![script](.content/image.png)

```bash
bash /config/scripts/descarga_completa_gpt.sh "%N" "%F"
```

Cambia el path a la ruta dentro del contenedor de qbitorrent
Añade el path cuando crees el contenedor, no he encontrado tus docker_compose.yml


#### python_venv

Cada vez que accedas por ssh deberás usar este comando antes de usar el primer script. Dudo que te sirva mi python_venv, he tenido errores al copiarlo

```bash
source /storage/polladas/moode/script/python_venv
```

#### edita contenedor

Añade Esto al docker-compose.yml

```yml
extra_hosts:
- "host.docker.internal:host-gateway"
``` 

O esto al docker run

```bash
--add-host="host.docker.internal:host-gateway"
```


# Uso


## Uso manual para pobres

Recomendado la primera vez, con esa cara que tienes. Así podrás ver el log, sino lanzará el proceso de fondo

```bash
bash setup.sh --manual
```


## Uso automático

```bash
bash setup.sh --automatico
```



## Uso manual para tiesos

#### 1. Edita el archivo config.json:


- `path destino` Ruta donde terminarán las canciones. Se usará también como `output path`

- `carpeta_final` Ruta a la carpeta watch_folder de qbitorrent.

- `lidarr_url` y `jackett_url` son las ip de mi pepecono en tu tailnet.

- `modo` **Interactivo** si crees que hay nombres muy típicos en los artistas ("The The", "Queen"), **Automático** si vas a tener suerte. ;)


El resto son opcionales:

- `carpeta_torrents` Es temporal para guardar torrents.

- `spotify_user` puedes usar cualquiera. Intercambiable por `playlist_id` y `playlist_url`; 1º nombre, 2º url 3º id

- `skip_torrents` **OPCIONAL** Si es `True`no descargará nada, solo buscará en mi biblioteca. 

- `db_path` está en mi carpeta.

- `client_id` y `client_secret` son de spotify, si en algun momento falla algo del acceso o la creación del json preguntame a ver si no lo he actualizado.

- `jackett_api_key` y `lidarr_api_key` son los programas con los que consulto los trackers. 


#### 2. Haz source al python_venv

```bash
source /storage/polladas/moode/script/python_venv
```

Si fallara al usar mi python_venv por lo que sea, puedes hacer con el lo que quieras, es una copia del mio.

##### 2.A Si prefieres crear uno nuevo (opcional):

```bash
mkdir python_venv
python -m venv python_venv
pip install spotipy tabulate bencodepy
# pip install json creo que viene por defecto
```



#### 3. Ejecutar:

```bash
python "/storage/popollo/scripts/descargar_playlist_spotify/1_mover_canciones_playlist_spotify.py" --config_file "/storage/popollo/scripts/config.json"
```

O puedes usar el alias `popollo`


O lanzarlo con comandos
...


O lanzarlo solo, te pedirá lo necesario
...




> Te recomendaría un docker de airsonic usando este docker_compose y con una app en el movil tienes acceso a los archivos descargados....
> https://docs.linuxserver.io/images/docker-airsonic-advanced/

```yml
services:
  airsonic-advanced:
    image: lscr.io/linuxserver/airsonic-advanced:latest
    container_name: airsonic-advanced
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Madrid
      #- CONTEXT_PATH= #optional
      #- JAVA_OPTS= #optional
    volumes:
      - /storage/dockers/airsonic-advanced/config:/config
      - /storage/dockers/airsonic-advanced/music:/music
      - /storage/dockers/airsonic-advanced/playlists:/playlists
      - /storage/dockers/airsonic-advanced/podcasts:/podcasts 
      #- /storage/dockers/airsonic-advanced/other media:/media #optional
    ports:
      - 4040:4040
    #devices:
      #- /dev/snd:/dev/snd #optional
    restart: unless-stopped
```