#!/usr/bin/env python3
#
# Script Name: menu_pollo2.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
import sys

# Define theme colors
background_color = "#0B67C4"
foreground_color = "#ffffff"
button_background = "#0973DE"
button_foreground = "#ffffff"
button_border_color = "#0A6DD2"
button_pressed_color = "#78EF8A"
border_radius = 10  # Radio para los bordes redondeados

def create_rounded_rectangle_image(size, radius, color):
    """Crea una imagen con un rectángulo redondeado."""
    image = Image.new("RGBA", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((radius, 0, size[0] - radius, size[1]), fill=color)
    draw.rectangle((0, radius, size[0], size[1] - radius), fill=color)
    draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=color)
    draw.pieslice((0, size[1] - radius * 2, radius * 2, size[1]), 90, 180, fill=color)
    draw.pieslice((size[0] - radius * 2, 0, size[0], radius * 2), 270, 360, fill=color)
    draw.pieslice((size[0] - radius * 2, size[1] - radius * 2, size[0], size[1]), 0, 90, fill=color)
    return image

def close_window():
    root.destroy()

def button_pressed(button_text):
    print(button_text)
    root.destroy()  # Cerrar la ventana cuando se pulsa un botón
    # Enviar el nombre del botón pulsado a Bash
    sys.stdout.write(button_text + "\n")
    sys.stdout.flush()

def key(event):
    if event.char == '\x1b':  # Escape key
        close_window()
    elif event.char.lower() in shortcuts:
        button_pressed(shortcuts[event.char.lower()])

root = tk.Tk()
root.title("Botones redondeados")
root.config(bg=background_color)  # Set background color of the window

# Frame para contener los botones con margen perimetral
button_frame = tk.Frame(root, bg=background_color)
button_frame.pack(padx=10, pady=10)  # Ajustar el margen perimetral

# Crear el botón "Otra_Carpeta" que ocupa todas las columnas
btn_otra_carpeta = tk.Button(button_frame, text="Otra_Carpeta", bg=button_background, fg=button_foreground, highlightbackground=button_border_color, bd=0, width=20, command=lambda: button_pressed("Otra_Carpeta"))
btn_otra_carpeta.grid(row=0, column=0, columnspan=5, pady=5, padx=5, sticky="ew")  # Ajustar el margen entre botones y ocupar todas las columnas

# Definir los atajos y las etiquetas correspondientes
shortcuts = {}
row_counter = 1
column_counter = 0
for arg in sys.argv[1:]:
    btn_text, shortcut = arg.split(":")  # Separar texto y atajo
    shortcuts[shortcut.lower()] = btn_text
    btn = tk.Button(button_frame, text=btn_text, command=lambda text=btn_text: button_pressed(text), bg=button_background, fg=button_foreground, highlightbackground=button_border_color, bd=0, width=20)
    btn.grid(row=row_counter, column=column_counter, pady=5, padx=5, sticky="ew")  # Ajustar el margen entre botones
    row_counter += 1
    if row_counter == 6:  # Si llegamos a la fila 6, reiniciar fila y avanzar a la siguiente columna
        row_counter = 1
        column_counter += 1

# Enlazar la función key al evento de presionar teclas
root.bind("<Key>", key)

root.mainloop()