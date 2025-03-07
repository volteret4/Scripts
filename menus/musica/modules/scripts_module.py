from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                           QScrollArea, QWidget, QGridLayout, QLineEdit,
                           QTextEdit, QSplitter, QMessageBox, QComboBox,
                           QDialog, QCheckBox)
from PyQt6.QtCore import Qt, QProcess, QSettings
import json
import sys
from base_module import BaseModule, THEMES
from pathlib import Path
import os


class ScriptRunnerModule(BaseModule):
    def __init__(self, config_file=None, scripts_section="scripts", parent=None, theme='Tokyo Night', **kwargs,):
        self.theme = theme
        self.config_file = config_file
        self.scripts_section = scripts_section
        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)
        self.scripts = {}
        self.processes = {}
        self.show_args = True  # Default to showing arguments
        super().__init__(parent, theme)

    def apply_theme(self, theme_name=None):
        # Optional: Override if you need custom theming beyond base theme
        super().apply_theme(theme_name)

    def init_ui(self):
        """Inicializa la interfaz del módulo."""
        # Layout principal
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        self.setLayout(main_layout)
        
        # Header con botón de ajustes avanzados
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 5)
        
        title_label = QLabel("Script Runner")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.toggle_args_btn = QPushButton("Advanced Settings")
        self.toggle_args_btn.setFixedWidth(140)
        self.toggle_args_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        self.toggle_args_btn.clicked.connect(self.toggle_advanced_settings)
        
        header_layout.addWidget(title_label, 1)
        header_layout.addWidget(self.toggle_args_btn)
        
        main_layout.addLayout(header_layout)
        
        # Área de scripts con scroll invisible
        scripts_scroll = QScrollArea()
        scripts_scroll.setWidgetResizable(True)
        scripts_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scripts_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scripts_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 10px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(128, 128, 128, 0.5);
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        scripts_container = QWidget()
        self.scripts_layout = QVBoxLayout(scripts_container)
        self.scripts_layout.setSpacing(5)
        self.scripts_layout.setContentsMargins(0, 0, 0, 0)
        self.scripts_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scripts_scroll.setWidget(scripts_container)
        
        # Cargar scripts del JSON y la configuración guardada
        if self.config_file:
            self.load_scripts()
            self.load_settings()
            self.create_script_widgets()
        else:
            self.log_message("No se ha proporcionado un archivo de configuración", error=True)
        
        # Área de log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid;
                border-radius: 3px;
                padding: 5px;
            }}
        """)
        
        # Añadir widgets al layout principal
        main_layout.addWidget(scripts_scroll, stretch=1)
        main_layout.addWidget(self.log_text)

    def load_settings(self):
        """Carga la configuración guardada de mostrar/ocultar argumentos"""
        try:
            if not self.config_file:
                return
                
            settings_file = Path(self.config_file).parent / "script_runner_settings.json"
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.show_args = settings.get('show_arguments', True)
            else:
                # Crear archivo de configuración por defecto si no existe
                self.save_settings()
        except Exception as e:
            self.log_message(f"Error al cargar la configuración: {str(e)}", error=True)
    
    def save_settings(self):
        """Guarda la configuración de mostrar/ocultar argumentos"""
        try:
            if not self.config_file:
                return
                
            settings_file = Path(self.config_file).parent / "script_runner_settings.json"
            settings = {'show_arguments': self.show_args}
            
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.log_message(f"Error al guardar la configuración: {str(e)}", error=True)

    def toggle_advanced_settings(self):
        """Muestra u oculta los argumentos de todos los scripts"""
        self.show_args = not self.show_args
        
        # Actualizar todos los widgets de script
        for i in range(self.scripts_layout.count()):
            widget = self.scripts_layout.itemAt(i).widget()
            if isinstance(widget, ScriptWidget):
                widget.set_args_visible(self.show_args)
        
        # Guardar la configuración
        self.save_settings()
        
        # Actualizar el texto del botón
        btn_text = "Hide Arguments" if self.show_args else "Show Arguments"
        self.toggle_args_btn.setText(btn_text)

    def create_script_widgets(self):
        for script_name, script_info in self.scripts.items():
            # Pasamos self como el módulo y como parent
            script_widget = ScriptWidget(script_name, script_info, module=self, parent=self, show_args=self.show_args)
            self.scripts_layout.addWidget(script_widget)

    def load_scripts(self):
        try:
            if not os.path.exists(self.config_file):
                self.log_message(f"Error: El archivo de configuración no existe: {self.config_file}", error=True)
                return
                
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            self.scripts = config.get(self.scripts_section, {})
            if not self.scripts:
                self.log_message(f"Advertencia: No se encontraron scripts en la sección '{self.scripts_section}'", error=True)
                
        except json.JSONDecodeError:
            self.log_message(f"Error: El archivo de configuración no es un JSON válido", error=True)
        except Exception as e:
            self.log_message(f"Error loading configuration: {str(e)}", error=True)

    def run_script(self, script_name, script_info, additional_args=None):
        try:
            # Obtener la ruta del script
            if 'path' not in script_info:
                error_msg = f"Error: No se especificó una ruta para el script '{script_name}'"
                self.log_message(error_msg, error=True)
                self.show_error_dialog("Error de configuración", error_msg)
                return
                
            script_path = Path(script_info.get('path', ''))
            self.log_message(f"Script original path: {script_path}")
            
            # Si la ruta es relativa, hacerla absoluta respecto al directorio del config
            if not script_path.is_absolute() and self.config_file:
                config_dir = Path(self.config_file).parent
                script_path = config_dir / script_path
                self.log_message(f"Script resolved path: {script_path}")
            
            # Verificar que el archivo existe
            if not script_path.exists():
                error_msg = f"Error: El archivo del script no existe: {script_path}"
                self.log_message(error_msg, error=True)
                self.show_error_dialog("Error de ruta", f"El script '{script_name}' no existe en la ruta:\n{script_path}")
                return
                
            process = QProcess(self)
            process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            process.readyRead.connect(lambda p=process: self.handle_process_output(p))
            process.finished.connect(lambda code, status, p=process, name=script_name: 
                                     self.handle_process_finished(p, code, status, name))
            process.errorOccurred.connect(lambda error, p=process, name=script_name: 
                                         self.handle_process_error(p, error, name))
            
            cmd = [sys.executable, str(script_path)]
            if additional_args:
                cmd.extend(additional_args)
            
            self.log_message(f"Ejecutando comando: {' '.join(cmd)}")
            
            self.processes[process] = script_name
            process.start(cmd[0], cmd[1:])
            
        except Exception as e:
            error_msg = f"Error al ejecutar el script '{script_name}': {str(e)}"
            self.log_message(error_msg, error=True)
            import traceback
            self.log_message(traceback.format_exc(), error=True)
            self.show_error_dialog("Error de ejecución", error_msg)

    def handle_process_output(self, process):
        try:
            data = process.readAll()
            if data:
                output = data.data().decode('utf-8', errors='replace')
                script_name = self.processes.get(process, "Script desconocido")
                self.log_message(f"[{script_name}] {output.strip()}")
        except Exception as e:
            self.log_message(f"Error al leer la salida del proceso: {str(e)}", error=True)

    def handle_process_finished(self, process, exit_code, exit_status, script_name):
        if exit_code == 0:
            self.log_message(f"[{script_name}] Completado con éxito", success=True)
        else:
            error_msg = f"[{script_name}] Falló con código de salida {exit_code}"
            self.log_message(error_msg, error=True)
        self.processes.pop(process, None)

    def handle_process_error(self, process, error, script_name):
        error_msg = f"[{script_name}] Error del proceso: {error}"
        self.log_message(error_msg, error=True)
        self.show_error_dialog("Error de proceso", 
                               f"El script '{script_name}' encontró un error:\n{error}")
         
    def log_message(self, message, error=False, success=False, theme='Tokyo Night'):
        # Replace newlines with HTML breaks to preserve formatting
        formatted_message = message.replace('\n', '<br>')
        
        if error:
            self.log_text.append(f'<span style="color: #ff5555; font-weight: bold;">{formatted_message}</span>')
        elif success:
            self.log_text.append(f'<span style="color: #50fa7b; font-weight: bold;">{formatted_message}</span>')
        else:
            self.log_text.append(f'<span style="color: {THEMES:{theme:["fg"]}};">{formatted_message}</span>')
        
        # Asegurarse de que el mensaje más reciente sea visible
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def show_error_dialog(self, title, message):
        error_dialog = QMessageBox(self)
        error_dialog.setWindowTitle(title)
        error_dialog.setText(message)
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid;
                padding: 5px 10px;
                border-radius: 3px;
            }}
        """)
        error_dialog.exec()
  
    def save_scripts_config(self, script_name, script_info):
        """Guarda los cambios en la configuración del script en el archivo JSON."""
        try:
            if not self.config_file:
                self.log_message("No hay un archivo de configuración definido", error=True)
                return False
                
            # Leer el archivo de configuración actual
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except FileNotFoundError:
                self.log_message(f"No se encuentra el archivo de configuración: {self.config_file}", error=True)
                return False
            except json.JSONDecodeError:
                self.log_message(f"El archivo de configuración no es un JSON válido", error=True)
                return False
                
            # Actualizar el script específico
            if self.scripts_section not in config:
                config[self.scripts_section] = {}
                
            config[self.scripts_section][script_name] = script_info
            
            # Guardar el archivo actualizado
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                self.log_message(f"Configuración guardada para el script '{script_name}'", success=True)
                return True
            except Exception as e:
                self.log_message(f"Error al guardar la configuración: {str(e)}", error=True)
                return False
                
        except Exception as e:
            self.log_message(f"Error inesperado al guardar la configuración: {str(e)}", error=True)
            import traceback
            self.log_message(traceback.format_exc(), error=True)
            return False


class ScriptDetailsDialog(QDialog):
    """Diálogo para mostrar los detalles de un script"""
    def __init__(self, script_name, script_info, parent=None):
        super().__init__(parent)
        self.script_name = script_name
        self.script_info = script_info
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle(f"Detalles del script: {self.script_name}")
        self.resize(500, 300)
        
        layout = QVBoxLayout(self)
        
        # Información del script
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        
        # Recopilar la información del script
        path = self.script_info.get('path', 'No especificada')
        description = self.script_info.get('description', 'No hay descripción disponible')
        
        # Formatear la información
        html_content = f"""
        <h2>{self.script_name}</h2>
        <p><b>Ruta:</b> {path}</p>
        <p><b>Descripción:</b><br>{description}</p>
        <p><b>Argumentos:</b></p>
        <ul>
        """
        
        # Añadir argumentos
        args = self.script_info.get('args', {})
        if not args:
            html_content += "<li>No hay argumentos definidos</li>"
        else:
            for key, value in args.items():
                if isinstance(value, list):
                    value_str = ", ".join([str(v) for v in value])
                    html_content += f"<li><b>{key}</b>: [opciones: {value_str}]</li>"
                else:
                    html_content += f"<li><b>{key}</b>: {value}</li>"
        
        html_content += "</ul>"
        
        info_text.setHtml(html_content)
        layout.addWidget(info_text)
        
        # Botón de cerrar
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)


class ScriptWidget(QWidget):
    def __init__(self, script_name, script_info, module=None, parent=None, theme='Tokyo Night', show_args=True):
        super().__init__(parent)
        self.script_name = script_name
        self.script_info = script_info
        self.module = module
        self.arg_inputs = {}
        self.show_args = show_args
        self.init_ui()

    def init_ui(self):
        # Layout principal vertical para el widget completo
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Contenedor para el título y botones en la parte superior
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(10, 5, 10, 5)
        title_layout.setSpacing(10)
        
        # Título del script clickeable
        title = QLabel(self.script_name)
        title.setStyleSheet("font-weight: bold; cursor: pointer;")
        title.mousePressEvent = self.show_script_details
        title_layout.addWidget(title, 1)  # 1 = stretch factor
        
        # Botones de Run y Save
        run_button = QPushButton("Run")
        run_button.setFixedSize(60, 25)
        run_button.setStyleSheet("""
            QPushButton {
                border: 1px solid;
                border-radius: 3px;
            }
        """)
        run_button.clicked.connect(self.get_command)
        
        save_button = QPushButton("Save")
        save_button.setFixedSize(60, 25)
        save_button.setStyleSheet("""
            QPushButton {
                border: 1px solid;
                border-radius: 3px;
            }
        """)
        save_button.clicked.connect(self.save_args)
        
        title_layout.addWidget(save_button)
        title_layout.addWidget(run_button)
        
        main_layout.addWidget(title_container)
        
        # Contenedor para los argumentos (se puede mostrar/ocultar)
        self.args_container = QWidget()
        args_layout = QVBoxLayout(self.args_container)
        args_layout.setContentsMargins(10, 0, 10, 5)
        args_layout.setSpacing(5)
        
        # Grid para los argumentos
        args_grid = QGridLayout()
        args_grid.setSpacing(10)
        
        # Procesar argumentos
        args = self.script_info.get('args', {})
        if isinstance(args, list):
            args_dict = {}
            for arg in args:
                if arg.startswith('--'):
                    key = arg[2:]
                    args_dict[key] = ''
                elif arg.startswith('-'):
                    key = arg[1:]
                    args_dict[key] = ''
            args = args_dict

        # Crear inputs para cada argumento
        row = 0
        col = 0
        max_cols = 2  # Dos pares de label+input por fila
        for key, value in args.items():
            # Label
            label = QLabel(key)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            # Contenedor para el input y posible botón de añadir
            input_container = QWidget()
            input_layout = QHBoxLayout(input_container)
            input_layout.setContentsMargins(0, 0, 0, 0)
            input_layout.setSpacing(3)
            
            # Determinar si el valor es una lista para crear un dropdown
            if isinstance(value, list):
                # Crear un combobox
                input_field = QComboBox()
                for item in value:
                    input_field.addItem(str(item))
                input_field.setEditable(True)  # Permitir editar el texto directamente
                input_field.setStyleSheet("""
                    QComboBox {
                        border: 1px solid;
                        border-radius: 3px;
                        padding: 5px;
                    }
                    QComboBox::drop-down {
                        border: none;
                    }
                """)
                
                # Botón para añadir una nueva opción
                add_button = QPushButton("+")
                add_button.setFixedSize(25, 25)
                add_button.setStyleSheet("""
                    QPushButton {
                        border: 1px solid;
                    }
                """)
                add_button.clicked.connect(lambda checked=False, cb=input_field: self.add_new_option(cb))
                
                input_layout.addWidget(input_field)
                input_layout.addWidget(add_button)
            else:
                # Input normal para valores no-lista
                input_field = QLineEdit()
                input_field.setText(str(value) if value is not None else '')
                input_field.setStyleSheet("""
                    QLineEdit {
                        border: 1px solid;
                        border-radius: 3px;
                        padding: 5px;
                    }
                """)
                input_layout.addWidget(input_field)
            
            self.arg_inputs[key] = input_field
            
            # Añadir al grid
            args_grid.addWidget(label, row, col * 2)
            args_grid.addWidget(input_container, row, col * 2 + 1)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        args_layout.addLayout(args_grid)
        main_layout.addWidget(self.args_container)
        
        # Configurar la visibilidad de los argumentos según la preferencia actual
        self.set_args_visible(self.show_args)
        
        # Añadir una línea horizontal al final
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: rgba(128, 128, 128, 0.3);")
        main_layout.addWidget(line)

    def set_args_visible(self, visible):
        """Muestra u oculta los argumentos del script"""
        self.show_args = visible
        self.args_container.setVisible(visible)
        
        # Ajustar el tamaño del widget según sea necesario
        self.adjustSize()

    def show_script_details(self, event):
        """Muestra un diálogo con los detalles del script"""
        dialog = ScriptDetailsDialog(self.script_name, self.script_info, self)
        dialog.exec()

    def add_new_option(self, combobox):
        """Añade el valor actual del combobox como nueva opción si no existe ya"""
        current_text = combobox.currentText().strip()
        if not current_text:
            return
            
        # Comprobar si ya existe para evitar duplicados
        exists = False
        for i in range(combobox.count()):
            if combobox.itemText(i) == current_text:
                exists = True
                break
                
        # Si no existe, añadirlo
        if not exists:
            combobox.addItem(current_text)
            self.module.log_message(f"Añadida nueva opción: {current_text}", success=True)

    def save_args(self):
        """Guarda los valores actuales de los argumentos en el archivo de configuración."""
        if self.module is None or not isinstance(self.module, ScriptRunnerModule) or not self.module.config_file:
            if self.module:
                self.module.log_message("No se puede guardar: no hay un archivo de configuración válido", error=True)
            return
            
        # Recopilar los valores actuales
        updated_args = {}
        for key, input_field in self.arg_inputs.items():
            if isinstance(input_field, QComboBox):
                # Para combobox, guardar todos los elementos como una lista
                values = [input_field.itemText(i) for i in range(input_field.count())]
                updated_args[key] = values
            else:
                # Para inputs normales, guardar el valor actual
                updated_args[key] = input_field.text().strip()
        
        # Actualizar los argumentos en el script_info
        self.script_info['args'] = updated_args
        
        # Llamar al método del módulo para guardar en el archivo
        self.module.save_scripts_config(self.script_name, self.script_info)

    def get_command(self):
        cmd = []
        for key, input_field in self.arg_inputs.items():
            # Obtener el valor dependiendo del tipo de widget
            if isinstance(input_field, QComboBox):
                value = input_field.currentText().strip()
            else:
                value = input_field.text().strip()
                
            if len(key) == 1:
                cmd.append(f"-{key}")
            else:
                cmd.append(f"--{key}")
            if value:
                cmd.append(value)
        
        # Usar la referencia directa al módulo en lugar de depender de parent()
        if self.module is not None and isinstance(self.module, ScriptRunnerModule):
            self.module.run_script(self.script_name, self.script_info, cmd)
        else:
            print(f"Error: Module reference is not valid or not a ScriptRunnerModule")