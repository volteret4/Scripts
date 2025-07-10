import tkinter as tk


playlist_file = "/home/huan/Scripts/Musica/playlists/spotify/playlists.txt"

# Función para manejar el clic en un botón de playlist
def handle_click(playlist_id):
    print(playlist_id)
    root.quit()  # Cerrar la ventana Tkinter

# Función para manejar el clic en el botón "NUEVA LISTA"
def nueva_lista_click():
    print("nuevalista")
    root.quit()  # Cerrar la ventana Tkinter

# Abrir el archivo y leer las líneas
with open(playlist_file, "r") as file:
    lines = file.readlines()

# Verificar que el número de líneas es múltiplo de 3
if len(lines) % 3 != 0:
    print("El archivo no tiene un formato válido. Debe contener un nombre de lista, un ID y una línea vacía entre cada conjunto de líneas.")
    exit()

# Crear una ventana de Tkinter
root = tk.Tk()
root.title("Selecciona una playlist")

# Configuración del color de fondo
root.config(bg="#0a0a0a")

# Configuración de la fuente
button_font = ("Helvetica", 10, "bold")

# Definir una función para crear los botones
def create_buttons():
    max_buttons_per_column = 7
    num_columns = (len(lines) + max_buttons_per_column - 1) // max_buttons_per_column
    buttons_created = 0
    for column in range(num_columns):
        for row in range(max_buttons_per_column):
            index = column * max_buttons_per_column * 3 + row * 3
            if index >= len(lines):
                break
            playlist_name = lines[index].strip().replace("Nombre: ", "")
            playlist_id = lines[index + 1].strip().replace("ID: ", "")
            button = tk.Button(root, text=playlist_name, command=lambda id=playlist_id: handle_click(id), font=button_font, bg="#1DB954", fg="black")
            button.grid(row=row, column=column, padx=5, pady=5)
            buttons_created += 1
            if buttons_created >= len(lines) / 3:
                break

    # Botón "NUEVA LISTA"
    nueva_lista_button = tk.Button(root, text="NUEVA LISTA", command=nueva_lista_click, font=button_font, bg="#1DB954", fg="black")
    nueva_lista_button.grid(row=max_buttons_per_column, columnspan=num_columns, padx=5, pady=5, sticky="ew")

# Crear los botones
create_buttons()

root.mainloop()