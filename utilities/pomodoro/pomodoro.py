import tkinter as tk
from tkinter import messagebox
import time
import pystray
from PIL import Image, ImageTk
from threading import Thread

class PomodoroTimer:
    def __init__(self, master):
        self.master = master
        self.master.title("Pomodoro Timer")
        self.master.configure(bg="#1e1e1e")  # Color de fondo oscuro

        self.minutes = 25
        self.seconds = 0
        self.is_running = False

        self.label = tk.Label(self.master, text="25:00", font=("Arial", 24), fg="white", bg="#1e1e1e")  # Texto blanco
        self.label.pack(pady=10)

        self.start_button = tk.Button(self.master, text="Inicio", command=self.start_timer, bg="#282828", fg="white")  # Botón de inicio
        self.start_button.pack(side=tk.LEFT, padx=10)

        self.stop_button = tk.Button(self.master, text="Detener", command=self.stop_timer, bg="#282828", fg="white")  # Botón de detención
        self.stop_button.pack(side=tk.RIGHT, padx=10)

        self.master.bind('<Escape>', self.close_window)  # Manejar el evento de tecla Escape

        # Crear icono en el systray en un hilo separado
        Thread(target=self.create_systray_icon).start()

    def start_timer(self):
        if not self.is_running:
            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            self.run_timer()

    def stop_timer(self):
        if self.is_running:
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.reset_timer()

    def reset_timer(self):
        self.minutes = 25
        self.seconds = 0
        self.label.config(text="25:00")

    def run_timer(self):
        while self.is_running and (self.minutes > 0 or self.seconds > 0):
            if self.seconds == 0:
                self.minutes -= 1
                self.seconds = 59
            else:
                self.seconds -= 1

            time_str = "{:02d}:{:02d}".format(self.minutes, self.seconds)
            self.label.config(text=time_str)
            time.sleep(1)

        if self.is_running:
            messagebox.showinfo("Pomodoro Timer", "¡Tiempo terminado!")
            self.reset_timer()
            self.start_button.config(state=tk.NORMAL)
        else:
            self.reset_timer()

    def close_window(self, event):
        self.master.destroy()

    def create_systray_icon(self):
        image = Image.open("pomodoro.png")
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar/Ocultar", self.toggle_window),
            pystray.MenuItem("Salir", self.close_window_from_systray)
        )
        self.icon = pystray.Icon("PomodoroTimer", image, "Pomodoro Timer", menu)
        self.icon.run()

    def toggle_window(self, icon, item):
        if self.master.winfo_viewable():
            self.master.withdraw()
        else:
            self.master.deiconify()

    def close_window_from_systray(self, icon, item):
        self.master.withdraw()  # Ocultar la ventana principal
        icon.stop()  # Detener el icono de la bandeja del sistema
        self.master.destroy()  # Cerrar la ventana principal

def main():
    root = tk.Tk()
    root.configure(bg="#1e1e1e")  # Color de fondo oscuro para la ventana principal
    pomodoro_timer = PomodoroTimer(root)
    root.mainloop()

if __name__ == "__main__":
    main()