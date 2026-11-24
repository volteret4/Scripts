#!/usr/bin/env python3
#
# Script Name: claude_dictado.py
# Description: Ventana flotante que dicta una consulta con nerd-dictation y
#              muestra la respuesta de Claude (claude -p, cuenta Pro).
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Lanzar/controlar con claude-dictado.sh (SIGUSR1 = alternar dictado/enviar).
#   Atajos en la ventana:
#     Ctrl+Enter  enviar (para el dictado si está activo)
#     Ctrl+D      empezar/parar dictado
#     Ctrl+N      conversación nueva
#   El contexto vive solo en memoria mientras la ventana está abierta:
#   claude se lanza con --no-session-persistence y no guarda nada en disco.
#     Esc         cerrar
#   Dependencies: - nerd-dictation (+ vosk en el venv)
#                 - claude (Claude Code CLI, sesión iniciada con claude.ai)
#                 - tkinter

import codecs
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import tkinter as tk

HOME = os.path.expanduser("~")
NERD_DICTATION = os.path.join(HOME, "gits/nerd-dictation/nerd-dictation")
VENV_PYTHON = os.path.join(HOME, "Scripts/python_venv/bin/python")
VOSK_MODEL = os.environ.get("CLAUDE_DICTADO_MODEL", os.path.join(HOME, ".config/nerd-dictation/model"))
# awesome lanza los programas sin ~/.local/bin en el PATH
CLAUDE = shutil.which("claude") or os.path.join(HOME, ".local/bin/claude")
COOKIE = "/tmp/claude-dictado.cookie"
PIDFILE = "/tmp/claude-dictado.pid"
LOGFILE = "/tmp/claude-dictado.log"
WORKDIR = os.path.join(HOME, ".cache/claude-dictado")

SYSTEM_PROMPT = (
    "Respondes dentro de una pequeña ventana flotante de escritorio. "
    "La consulta viene de un dictado por voz en español y puede contener errores "
    "de transcripción: interpreta la intención. Sé conciso y responde en español. "
    "Evita tablas anchas; usa texto plano o listas cortas."
)

BG, FG, BG_IN, ACCENT, DIM = "#1e1f29", "#e6e6e6", "#282a36", "#d97757", "#8a8fa3"
CODE_BG, LINK = "#14151c", "#8ab4f8"
SANS, MONO = "Noto Sans", "JetBrainsMono Nerd Font"

# Markdown en línea: **negrita**, `código`, [enlace](url), *cursiva*
MD_INLINE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|(?<![\w*])\*(?!\s)([^*]+?)\*(?!\w)")


def claude_env():
    """Entorno sin claves de API para que claude use siempre la cuenta Pro."""
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
        env.pop(k, None)
    return env


class App:
    def __init__(self):
        self.events = queue.Queue()
        self.dictation = None       # Popen de nerd-dictation
        self.dict_text = ""         # texto dictado (con backspaces aplicados)
        self.dict_rendered = 0      # caracteres pintados en la caja
        self.send_after_dictation = False
        self.claude = None          # Popen de claude
        self.history = []           # [(pregunta, respuesta)] solo en memoria
        self.current_q = ""
        self.current_a = ""
        self.streamed = False

        self.root = tk.Tk(className="ClaudeDictado")
        self.root.title("Claude dictado")
        self.root.configure(bg=BG)
        w, h = 680, 560
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 3
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.attributes("-topmost", True)

        frame = tk.Frame(self.root, bg=BG)
        frame.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 6))
        scroll = tk.Scrollbar(frame)
        scroll.pack(side="right", fill="y")
        self.answer = tk.Text(frame, wrap="word", bg=BG_IN, fg=FG, relief="flat", padx=10, pady=8,
                              font=("Sans", 11), yscrollcommand=scroll.set, state="disabled")
        self.answer.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.answer.yview)
        self.answer.configure(font=(SANS, 11), spacing1=2, spacing3=2, cursor="arrow")
        self.answer.tag_configure("q", foreground=ACCENT, font=(SANS, 11, "bold"), spacing1=10, spacing3=6)
        self.answer.tag_configure("err", foreground="#ff6e6e")
        self.answer.tag_configure("bold", font=(SANS, 11, "bold"))
        self.answer.tag_configure("italic", font=(SANS, 11, "italic"))
        self.answer.tag_configure("code", font=(MONO, 10), background=CODE_BG, foreground="#f1c48c")
        self.answer.tag_configure("pre", font=(MONO, 10), background=CODE_BG, foreground="#cfd3dc",
                                  lmargin1=14, lmargin2=14, spacing1=0, spacing3=0)
        self.answer.tag_configure("h1", font=(SANS, 16, "bold"), spacing1=10, spacing3=4)
        self.answer.tag_configure("h2", font=(SANS, 14, "bold"), spacing1=8, spacing3=4)
        self.answer.tag_configure("h3", font=(SANS, 12, "bold"), spacing1=6, spacing3=2)
        self.answer.tag_configure("quote", foreground=DIM, font=(SANS, 11, "italic"), lmargin1=16, lmargin2=16)
        self.answer.tag_configure("hr", foreground=DIM, justify="center")
        self.answer.tag_configure("link", foreground=LINK, underline=True)
        self.answer.tag_bind("link", "<Enter>", lambda e: self.answer.config(cursor="hand2"))
        self.answer.tag_bind("link", "<Leave>", lambda e: self.answer.config(cursor="arrow"))
        for level in range(1, 5):
            ind = 14 + 18 * (level - 1)
            self.answer.tag_configure(f"li{level}", lmargin1=ind, lmargin2=ind + 16)
        self.links = 0
        self.render_pending = False

        self.status = tk.Label(self.root, anchor="w", bg=BG, fg=ACCENT, font=("Sans", 10, "bold"), padx=10)
        self.status.pack(fill="x")

        self.query = tk.Text(self.root, height=4, wrap="word", bg=BG_IN, fg=FG, insertbackground=FG,
                             relief="flat", padx=10, pady=8, font=("Sans", 12), undo=True)
        self.query.pack(fill="x", padx=10, pady=(4, 2))

        hint = tk.Label(self.root, anchor="w", bg=BG, fg=DIM, font=("Sans", 8), padx=10,
                        text="Atajo: dictar/enviar · Ctrl+Enter enviar · Ctrl+D dictar · Ctrl+N nueva · Esc cerrar")
        hint.pack(fill="x", pady=(0, 8))

        self.root.bind("<Control-Return>", lambda e: (self.send_or_stop(), "break")[1])
        self.root.bind("<Control-d>", lambda e: (self.toggle(), "break")[1])
        self.root.bind("<Control-n>", lambda e: self.new_conversation())
        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        signal.signal(signal.SIGUSR1, lambda *_: self.events.put(("toggle", None)))
        signal.signal(signal.SIGTERM, lambda *_: self.events.put(("quit", None)))

        os.makedirs(WORKDIR, exist_ok=True)
        with open(PIDFILE, "w") as f:
            f.write(str(os.getpid()))

        self.root.after(50, self.poll)
        self.start_dictation()
        self.query.focus_set()

    # ------------------------------------------------------------------ UI
    def set_status(self, text):
        self.status.config(text=text)

    def answer_append(self, text, tag=None):
        self.answer.config(state="normal")
        self.answer.insert("end", text, tag)
        self.answer.see("end")
        self.answer.config(state="disabled")

    # ----------------------------------------------------------- markdown
    def md_inline(self, text, tags=()):
        pos = 0
        for m in MD_INLINE.finditer(text):
            self.answer.insert("end", text[pos:m.start()], tags)
            bold, code, ltext, url, italic = m.groups()
            if bold is not None:
                self.md_inline(bold, tags + ("bold",))
            elif code is not None:
                self.answer.insert("end", code, tags + ("code",))
            elif ltext is not None:
                self.links += 1
                name = f"link{self.links}"
                self.answer.tag_bind(name, "<Button-1>",
                                     lambda e, u=url: subprocess.Popen(["xdg-open", u], stdout=subprocess.DEVNULL,
                                                                       stderr=subprocess.DEVNULL))
                self.answer.insert("end", ltext, tags + ("link", name))
            else:
                self.answer.insert("end", italic, tags + ("italic",))
            pos = m.end()
        self.answer.insert("end", text[pos:], tags)

    def md_render(self, md):
        in_code = False
        for line in md.split("\n"):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                self.answer.insert("end", line + "\n", ("pre",))
                continue
            m = re.match(r"(#{1,6})\s+(.*)", stripped)
            if m:
                self.md_inline(m.group(2), (f"h{min(len(m.group(1)), 3)}",))
                self.answer.insert("end", "\n")
                continue
            if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
                self.answer.insert("end", "─" * 30 + "\n", ("hr",))
                continue
            m = re.match(r"(\s*)([-*+]|\d+[.)])\s+(.*)", line)
            if m:
                level = min(len(m.group(1).expandtabs(4)) // 2 + 1, 4)
                bullet = "•" if m.group(2) in "-*+" else m.group(2)
                tag = f"li{level}"
                self.answer.insert("end", f"{bullet} ", (tag,))
                self.md_inline(m.group(3), (tag,))
                self.answer.insert("end", "\n", (tag,))
                continue
            if stripped.startswith(">"):
                self.md_inline(stripped.lstrip("> "), ("quote",))
                self.answer.insert("end", "\n", ("quote",))
                continue
            if stripped.startswith("|"):
                if not re.fullmatch(r"\|[\s:|-]+\|?", stripped):
                    self.answer.insert("end", stripped + "\n", ("pre",))
                continue
            self.md_inline(line)
            self.answer.insert("end", "\n")

    def render_answer(self):
        """Repinta la respuesta actual (desde la marca astart) como markdown."""
        self.render_pending = False
        at_bottom = self.answer.yview()[1] > 0.98
        self.answer.config(state="normal")
        self.answer.delete("astart", "end-1c")
        self.md_render(self.current_a.rstrip())
        if at_bottom:
            self.answer.see("end")
        self.answer.config(state="disabled")

    def schedule_render(self):
        if not self.render_pending:
            self.render_pending = True
            self.root.after(80, self.render_answer)

    def render_dictation(self):
        start = "dstart"
        self.query.delete(start, f"{start} + {self.dict_rendered} chars")
        self.query.insert(start, self.dict_text)
        self.dict_rendered = len(self.dict_text)
        self.query.see("end")

    # ------------------------------------------------------------ dictado
    def start_dictation(self):
        if self.dictation or self.claude:
            return
        self.query.mark_set("dstart", "end-1c")
        self.query.mark_gravity("dstart", "left")
        self.dict_text, self.dict_rendered = "", 0
        if os.path.exists(COOKIE):
            os.remove(COOKIE)
        cmd = [VENV_PYTHON, NERD_DICTATION, "begin", "--cookie", COOKIE,
               "--vosk-model-dir", VOSK_MODEL, "--simulate-input-tool", "STDOUT",
               "--full-sentence", "--numbers-as-digits", "--numbers-min-value", "10"]
        log = open(LOGFILE, "a")
        self.dictation = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, stdin=subprocess.DEVNULL)
        threading.Thread(target=self.read_dictation, args=(self.dictation,), daemon=True).start()
        self.set_status("🎙  Escuchando…  (pulsa el atajo otra vez para enviar)")

    def read_dictation(self, proc):
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while True:
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                break
            self.events.put(("dict", decoder.decode(chunk)))
        proc.wait()
        self.events.put(("dict_end", proc.returncode))

    def stop_dictation(self, send):
        if not self.dictation:
            return
        self.send_after_dictation = send
        self.set_status("⏳  Terminando dictado…")
        # Si el modelo aún está cargando, la cookie no existe y "end" no haría nada
        if not os.path.exists(COOKIE):
            self.root.after(200, lambda: self.stop_dictation(send))
            return
        subprocess.Popen([VENV_PYTHON, NERD_DICTATION, "end", "--cookie", COOKIE],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # -------------------------------------------------------------- claude
    def send(self):
        text = self.query.get("1.0", "end-1c").strip()
        if not text or self.claude:
            if not text:
                self.set_status("Nada que enviar. Ctrl+D para dictar.")
            return
        self.answer_append(("\n" if self.answer.index("end-1c") != "1.0" else "") + f"▶ {text}\n", "q")
        self.answer.mark_set("astart", "end-1c")
        self.answer.mark_gravity("astart", "left")
        prompt = text
        if self.history:
            prev = "\n\n".join(f"Usuario: {q}\n\nClaude: {a}" for q, a in self.history)
            prompt = f"Conversación previa:\n\n{prev}\n\n---\nNueva pregunta del usuario: {text}"
        cmd = [CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--include-partial-messages", "--no-session-persistence",
               "--append-system-prompt", SYSTEM_PROMPT,
               "--allowedTools", "WebSearch", "WebFetch"]
        self.current_q, self.current_a = text, ""
        self.streamed = False
        try:
            self.claude = subprocess.Popen(cmd, cwd=WORKDIR, env=claude_env(), stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except OSError as e:
            self.answer_append(f"[error] No se pudo lanzar claude: {e}\n", "err")
            self.set_status("Error lanzando claude")
            return
        threading.Thread(target=self.read_claude, args=(self.claude,), daemon=True).start()
        self.query.delete("1.0", "end")
        self.set_status("🤖  Pensando…")

    def read_claude(self, proc):
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            self.events.put(("claude", msg))
        err = proc.stderr.read()
        proc.wait()
        self.events.put(("claude_end", (proc.returncode, err)))

    def handle_claude(self, msg):
        t = msg.get("type")
        if t == "stream_event":
            ev = msg.get("event", {})
            if ev.get("type") == "message_start" and self.current_a.strip():
                self.current_a += "\n\n"  # varias respuestas seguidas (p.ej. tras una búsqueda web)
            elif ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
                if not self.streamed:
                    self.set_status("🤖  Respondiendo…")
                self.streamed = True
                self.current_a += ev["delta"]["text"]
                self.schedule_render()
            elif ev.get("type") == "content_block_start" and ev.get("content_block", {}).get("type") == "tool_use":
                self.set_status(f"🔧  Usando {ev['content_block'].get('name', 'herramienta')}…")
        elif t == "result":
            if msg.get("is_error"):
                self.answer_append(f"\n[error] {msg.get('result', '')}", "err")
            else:
                if not self.streamed:
                    self.current_a = msg.get("result", "")
                self.render_answer()
                self.history.append((self.current_q, msg.get("result") or self.current_a))

    # ------------------------------------------------------------ acciones
    def toggle(self):
        if self.claude:
            self.set_status("🤖  Espera a que termine la respuesta…")
        elif self.dictation:
            self.stop_dictation(send=True)
        else:
            self.start_dictation()

    def send_or_stop(self):
        if self.dictation:
            self.stop_dictation(send=True)
        else:
            self.send()

    def new_conversation(self):
        if self.claude:
            return
        self.history = []
        self.answer.config(state="normal")
        self.answer.delete("1.0", "end")
        self.answer.config(state="disabled")
        self.set_status("Conversación nueva. Ctrl+D para dictar.")

    def quit(self):
        if self.dictation:
            subprocess.run([VENV_PYTHON, NERD_DICTATION, "end", "--cookie", COOKIE],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self.dictation.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.dictation.kill()
        if self.claude:
            self.claude.terminate()
        for f in (PIDFILE, COOKIE):
            try:
                os.remove(f)
            except FileNotFoundError:
                pass
        self.root.destroy()

    # ----------------------------------------------------------- bucle
    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "toggle":
                    self.toggle()
                elif kind == "quit":
                    self.quit()
                    return
                elif kind == "dict":
                    for ch in data:
                        if ch == "\x08":
                            self.dict_text = self.dict_text[:-1]
                        else:
                            self.dict_text += ch
                    self.render_dictation()
                elif kind == "dict_end":
                    self.dictation = None
                    if data not in (0, None):
                        self.set_status(f"Error en nerd-dictation (código {data}), mira {LOGFILE}")
                    elif self.send_after_dictation:
                        self.send()
                    else:
                        self.set_status("Dictado parado. Ctrl+Enter para enviar.")
                    self.send_after_dictation = False
                elif kind == "claude":
                    self.handle_claude(data)
                elif kind == "claude_end":
                    code, err = data
                    self.claude = None
                    if code != 0 and err.strip():
                        self.answer_append(f"\n[error] {err.strip()}", "err")
                    self.set_status("✅  Listo. Atajo o Ctrl+D para seguir preguntando, Ctrl+N conversación nueva.")
        except queue.Empty:
            pass
        self.root.after(50, self.poll)


if __name__ == "__main__":
    App().root.mainloop()
