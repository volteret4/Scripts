"""
Script Name: relacionar_mix.py
Description: Diagrama flotante para anotar relaciones de mezcla entre canciones
             ("A mezcla bien con B"): la canción principal en el centro, con
             tantas canciones "antes" y "después" como se quiera, buscadas en
             cualquier subcarpeta de Mix.
Author: volteret4
Repository: https://github.com/volteret4/

Las relaciones se guardan en el library.db del servidor (submódulo
mixxx_info de repeat-one en pepecono, tabla song_relations) a través de su
API (MIXXX_INFO_API, /api/relations) -- el servidor es la fuente de verdad y
se actualiza solo a diario, ya no se copia un library.db local. Las muestra
en su web (pestaña "🔗 Relaciones"). Se identifican por artista+título, no
por ruta: mover_mix_playerctl.py renombra y mueve ficheros al reclasificarlos,
así que una ruta no es un identificador estable con el tiempo.

Se lanza normalmente desde mover_mix_playerctl.py (Shift+Enter o Ctrl+Enter
en el diálogo de comentario), pero también funciona suelto -- sin --track usa
la canción que esté sonando ahora mismo (playerctl/deadbeef).

Uso:
    python3 relacionar_mix.py
    python3 relacionar_mix.py --track '{"artist": "...", "title": "...", "path": "..."}'
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mover_mix_playerctl import MusicMover, apply_tokyo_night_theme, show_notification

MIXXX_PATH = "/mnt/windows/Mix"
MIXXX_INFO_API = os.environ.get("MIXXX_INFO_API", "http://192.168.1.133:8754").rstrip("/")


# ---------------------------------------------------------------------------
# Persistencia: API de mixxx_info en pepecono (tabla song_relations)
# ---------------------------------------------------------------------------

class ApiConn:
    """Sustituye a la conexión sqlite de antes: mismas funciones de abajo
    (fetch/add/delete_relation) pero contra la API del servidor."""

    def __init__(self, base):
        self.base = base

    def request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
        return json.loads(raw) if raw else None

    def close(self):
        pass


def get_conn():
    conn = ApiConn(MIXXX_INFO_API)
    conn.request("GET", "/api/relations?" + urllib.parse.urlencode({"artist": "-", "title": "-"}))
    return conn


def _same(a, b):
    return (a or "").lower() == (b or "").lower()


def fetch_relations(conn, artist, title):
    """(antes, despues): filas donde esta canción es el destino / el origen,
    como tuplas (id, artista, título, ruta, comentario, created_at)."""
    rows = conn.request("GET", "/api/relations?" + urllib.parse.urlencode({"artist": artist, "title": title}))
    before, after = [], []
    for r in rows:
        f, t = r["from"], r["to"]
        if _same(t["artist"], artist) and _same(t["title"], title):
            before.append((r["id"], f["artist"], f["title"], f["path"], r["comment"], r["created_at"]))
        if _same(f["artist"], artist) and _same(f["title"], title):
            after.append((r["id"], t["artist"], t["title"], t["path"], r["comment"], r["created_at"]))
    return before, after


def add_relation(conn, from_artist, from_title, from_path, to_artist, to_title, to_path, comment):
    conn.request("POST", "/api/relations", {
        "from_artist": from_artist, "from_title": from_title, "from_path": from_path,
        "to_artist": to_artist, "to_title": to_title, "to_path": to_path, "comment": comment,
    })


def delete_relation(conn, relation_id):
    conn.request("DELETE", f"/api/relations/{relation_id}")


# ---------------------------------------------------------------------------
# Búsqueda en Mix
# ---------------------------------------------------------------------------

def search_mix(query, limit=40):
    query = query.strip()
    if len(query) < 2:
        return []
    cmd = ['find', MIXXX_PATH, '-type', 'f', '-iname', f'*{query}*']
    result = subprocess.run(cmd, capture_output=True, text=True)
    paths = sorted(p for p in result.stdout.strip().split('\n') if p)
    return paths[:limit]


def guess_from_filename(path):
    """Los ficheros ya reclasificados siguen el patrón que usa set_tags():
    "Artista - Título (fecha álbum) [sello]" -- es el camino rápido, sin
    subprocesos, y cubre casi todo lo que hay bajo Mix."""
    name = os.path.splitext(os.path.basename(path))[0]
    name = re.sub(r'\s*\[[^\]]*\]\s*$', '', name)
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name)
    if ' - ' in name:
        artist, title = name.split(' - ', 1)
        return artist.strip(), title.strip()
    return "", name.strip()


def read_tags(path):
    """Artista/título para mostrar en la búsqueda: primero por nombre de
    fichero (rápido); si no seguía el patrón esperado, ffprobe como último
    recurso (mucho más lento si hay muchos resultados)."""
    artist, title = guess_from_filename(path)
    if artist and title:
        return artist, title
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', path],
            capture_output=True, text=True, check=True, timeout=5,
        )
        tags = json.loads(result.stdout).get('format', {}).get('tags', {})
        a = tags.get('artist') or tags.get('ARTIST') or tags.get('Artist')
        t = tags.get('title') or tags.get('TITLE') or tags.get('Title')
        if a and t:
            return a.strip(), t.strip()
    except Exception:
        pass
    return artist, title or os.path.splitext(os.path.basename(path))[0]


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class SongPickerDialog(QDialog):
    """Buscar una canción en cualquier subcarpeta de Mix."""

    def __init__(self, direction_label, parent=None):
        super().__init__(parent)
        self.result_song = None  # (artist, title, path)
        self.setWindowTitle(f"Buscar canción — {direction_label}")
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Escribe parte del artista, título o fichero (mín. 2 letras)…")
        self.search_edit.textChanged.connect(self.do_search)
        layout.addWidget(self.search_edit)

        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(self.accept_selection)
        layout.addWidget(self.results_list)

        hint = QLabel("Enter / doble clic para elegir · Esc para cancelar")
        hint.setStyleSheet("color: #565f89; font-size: 11px; background: transparent;")
        layout.addWidget(hint)

        self.search_edit.setFocus()

    def do_search(self, text):
        self.results_list.clear()
        for path in search_mix(text):
            artist, title = read_tags(path)
            label = f"{artist} - {title}" if artist else title
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, (artist, title, path))
            self.results_list.addItem(item)

    def accept_selection(self, item=None):
        item = item or self.results_list.currentItem()
        if not item:
            return
        self.result_song = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept_selection()
            return
        super().keyPressEvent(event)


class RelationsDialog(QDialog):
    """Ventana flotante: canción principal en el centro, con sus relaciones
    "antes"/"después" a cada lado, como un mini diagrama de flujo."""

    def __init__(self, conn, artist, title, path, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.artist = artist
        self.title = title
        self.path = path
        self.before = []
        self.after = []

        self.setWindowTitle(f"Relaciones — {artist} - {title}")
        self.setMinimumSize(920, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        header = QLabel(f"🎧 {artist} — {title}")
        header.setWordWrap(True)
        header.setStyleSheet("font-size: 15px; font-weight: bold; color: #7aa2f7; background: transparent;")
        outer.addWidget(header)

        self.flow_layout = QHBoxLayout()
        self.flow_layout.setSpacing(16)
        outer.addLayout(self.flow_layout, stretch=1)

        footer = QHBoxLayout()
        copy_btn = QPushButton("Copiar como Mermaid")
        copy_btn.clicked.connect(self.copy_mermaid)
        footer.addWidget(copy_btn)
        footer.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("danger")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        outer.addLayout(footer)

        self.reload()

    # -- construcción del diagrama -----------------------------------------

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout(child.layout())

    def _api(self, fn, *args):
        """Llama a la API; si falla avisa en vez de tumbar el diálogo (PyQt6
        aborta con una excepción sin capturar dentro de un slot)."""
        try:
            return fn(self.conn, *args), True
        except (urllib.error.URLError, OSError, ValueError) as e:
            QMessageBox.warning(self, "mixxx_info", f"Error con la API ({MIXXX_INFO_API}): {e}")
            return None, False

    def reload(self):
        self._clear_layout(self.flow_layout)
        rel, ok = self._api(fetch_relations, self.artist, self.title)
        self.before, self.after = rel if ok else ([], [])

        self.flow_layout.addLayout(self.build_column("⬅ Antes", self.before, "before"))
        self.flow_layout.addWidget(self.build_arrow())
        self.flow_layout.addWidget(self.build_main_box())
        self.flow_layout.addWidget(self.build_arrow())
        self.flow_layout.addLayout(self.build_column("Después ➡", self.after, "after"))

    def build_main_box(self):
        box = QFrame()
        box.setMinimumWidth(190)
        box.setMaximumWidth(220)
        box.setStyleSheet("background-color: #7aa2f7; border-radius: 10px; padding: 4px;")
        lay = QVBoxLayout(box)
        lbl = QLabel(f"{self.artist}\n{self.title}")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #181825; font-weight: bold; background: transparent;")
        lay.addWidget(lbl)
        return box

    def build_arrow(self):
        lbl = QLabel("→")
        lbl.setStyleSheet("color: #565f89; font-size: 22px; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    def build_column(self, title_text, rows, direction):
        col = QVBoxLayout()
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("color: #a9b1d6; font-size: 11px; font-weight: bold; background: transparent;")
        col.addWidget(title_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(260)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(8)

        for rel_id, r_artist, r_title, _r_path, comment, _created in rows:
            inner_layout.addWidget(self.build_node_box(rel_id, r_artist, r_title, comment))
        inner_layout.addStretch()
        scroll.setWidget(inner)
        col.addWidget(scroll, stretch=1)

        add_btn = QPushButton(f"+ Añadir {'antes' if direction == 'before' else 'después'}")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(lambda: self.add_song(direction))
        col.addWidget(add_btn)
        return col

    def build_node_box(self, relation_id, artist, title, comment):
        box = QFrame()
        box.setStyleSheet("background-color: #414868; border-radius: 8px;")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 8)

        top = QHBoxLayout()
        lbl = QLabel(f"{artist} - {title}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #c0caf5; background: transparent;")
        top.addWidget(lbl, stretch=1)

        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(24)
        del_btn.setStyleSheet("color: #f7768e; background: transparent; border: none; font-weight: bold;")
        del_btn.clicked.connect(lambda: self.remove_relation(relation_id))
        top.addWidget(del_btn)
        lay.addLayout(top)

        if comment:
            note = QLabel(comment)
            note.setWordWrap(True)
            note.setStyleSheet("color: #9ece6a; font-size: 11px; font-style: italic; background: transparent;")
            lay.addWidget(note)

        return box

    # -- acciones ------------------------------------------------------------

    def add_song(self, direction):
        picker = SongPickerDialog("antes" if direction == "before" else "después", self)
        if picker.exec() != QDialog.DialogCode.Accepted or not picker.result_song:
            return
        other_artist, other_title, other_path = picker.result_song
        if not other_artist and not other_title:
            return

        comment, ok = QInputDialog.getText(
            self, "Comentario", "¿Por qué funciona esta transición? (opcional)"
        )
        comment = comment.strip() if ok and comment else ""

        if direction == "before":
            self._api(add_relation, other_artist, other_title, other_path,
                      self.artist, self.title, self.path, comment)
        else:
            self._api(add_relation, self.artist, self.title, self.path,
                      other_artist, other_title, other_path, comment)
        self.reload()

    def remove_relation(self, relation_id):
        self._api(delete_relation, relation_id)
        self.reload()

    def copy_mermaid(self):
        lines = ["graph LR"]
        main_id = "MAIN"
        lines.append(f'  {main_id}["{self.artist} - {self.title}"]')
        for i, (_rel_id, r_artist, r_title, _r_path, comment, _created) in enumerate(self.before):
            node = f"B{i}"
            lines.append(f'  {node}["{r_artist} - {r_title}"]')
            label = f'|"{comment}"|' if comment else ""
            lines.append(f"  {node} -->{label} {main_id}")
        for i, (_rel_id, r_artist, r_title, _r_path, comment, _created) in enumerate(self.after):
            node = f"A{i}"
            lines.append(f'  {node}["{r_artist} - {r_title}"]')
            label = f'|"{comment}"|' if comment else ""
            lines.append(f"  {main_id} -->{label} {node}")

        QApplication.clipboard().setText("\n".join(lines))
        show_notification("Mermaid copiado", "Diagrama copiado al portapapeles")


def main():
    parser = argparse.ArgumentParser(description="Relacionar canciones de Mix para posibles mezclas")
    parser.add_argument("--track", help="JSON con {artist, title, path} de la canción principal")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    apply_tokyo_night_theme(app)

    if args.track:
        try:
            info = json.loads(args.track)
        except json.JSONDecodeError:
            QMessageBox.critical(None, "Error", "No se pudo leer la información de la canción recibida")
            sys.exit(1)
    else:
        try:
            info = MusicMover().get_current_track_info()
        except Exception as e:
            QMessageBox.critical(None, "Error", f"No se pudo obtener la canción actual: {e}")
            sys.exit(1)

    artist = (info.get("artist") or "").strip()
    title = (info.get("title") or "").strip()
    path = info.get("path") or ""

    if not artist and not title:
        QMessageBox.critical(None, "Error", "La canción no tiene artista ni título: no se puede relacionar")
        sys.exit(1)

    try:
        conn = get_conn()
    except (urllib.error.URLError, OSError, ValueError) as e:
        QMessageBox.critical(None, "Error", f"No se pudo conectar con mixxx_info ({MIXXX_INFO_API}): {e}")
        sys.exit(1)
    try:
        dialog = RelationsDialog(conn, artist, title, path)
        dialog.exec()
    finally:
        conn.close()

    sys.exit()


if __name__ == "__main__":
    main()
