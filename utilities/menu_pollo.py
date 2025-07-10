#!/usr/bin/env python3
#
# Script Name: menu_pollo.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#
import tkinter as tk
import sys

# Define theme colors
background_color = "#282c34"
foreground_color = "#ffffff"
button_background = "#33373b"
button_foreground = "#ffffff"

def close_window(event=None):
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
    elif event.char.lower() == 'o':
        button_pressed("Otra_Carpeta")
    elif event.char.lower() in shortcuts:
        button_pressed(shortcuts[event.char.lower()])

root = tk.Tk()
root.title("botonsitos")
root.config(bg=background_color)  # Set background color of the window

# Frame para contener los botones con margen perimetral
button_frame = tk.Frame(root, bg=background_color)
button_frame.pack(padx=10, pady=10)  # Ajustar el margen perimetral

# Crear el botón "Otra_Carpeta" que ocupa todas las columnas
btn_otra_carpeta = tk.Button(button_frame, text="Otra_Carpeta", command=lambda: button_pressed("Otra_Carpeta"))
btn_otra_carpeta.config(bg=button_background, fg=button_foreground)
btn_otra_carpeta.grid(row=0, column=0, columnspan=5, pady=5, sticky="ew")  # Ajustar el margen entre botones y ocupar todas las columnas

# Definir los atajos y las etiquetas correspondientes
shortcuts = {}
row_counter = 1
column_counter = 0
for arg in sys.argv[1:]:
    btn_text, shortcut = arg.split(":")  # Separar texto y atajo
    shortcuts[shortcut.lower()] = btn_text
    btn = tk.Button(button_frame, text=btn_text, command=lambda text=btn_text: button_pressed(text))
    btn.config(bg=button_background, fg=button_foreground)
    btn.grid(row=row_counter, column=column_counter, pady=5, padx=5)  # Ajustar el margen entre botones
    row_counter += 1
    if row_counter == 6:  # Si llegamos a la fila 6, reiniciar fila y avanzar a la siguiente columna
        row_counter = 1
        column_counter += 1

# Enlazar la función key al evento de presionar teclas
root.bind("<Key>", key)

root.mainloop()