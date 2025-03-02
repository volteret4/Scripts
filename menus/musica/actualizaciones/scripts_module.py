from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                           QScrollArea, QWidget, QGridLayout, QLineEdit,
                           QTextEdit, QSplitter, QMessageBox)
from PyQt6.QtCore import Qt, QProcess
import json
import sys
from base_module import BaseModule, THEME
from pathlib import Path
import os

class ScriptWidget(QWidget):
    def __init__(self, script_name, script_info, module=None, parent=None):
        super().__init__(parent)
        self.script_name = script_name
        self.script_info = script_info
        self.module = module  # Referencia directa al módulo
        self.arg_inputs = {}
        self.init_ui()

    def init_ui(self):
        # Un único layout horizontal para todo
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Contenedor para el nombre del script
        name_container = QWidget()
        name_container.setStyleSheet(f"background-color: {THEME['secondary_bg']};")
        name_layout = QHBoxLayout(name_container)
        name_layout.setContentsMargins(10, 5, 10, 5)
        
        title = QLabel(self.script_name)
        title.setStyleSheet(f"""
            color: {THEME['fg']};
            font-weight: bold;
        """)
        name_layout.addWidget(title)
        layout.addWidget(name_container)
        
        # Contenedor para los argumentos
        args_container = QWidget()
        args_container.setStyleSheet(f"background-color: {THEME['secondary_bg']};")
        args_layout = QHBoxLayout(args_container)
        args_layout.setContentsMargins(10, 5, 10, 5)
        
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
            
            # Input
            input_field = QLineEdit()
            input_field.setText(str(value) if value is not None else '')
            input_field.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {THEME['bg']};
                    color: {THEME['fg']};
                    border: 1px solid {THEME['border']};
                    border-radius: 3px;
                    padding: 5px;
                }}
            """)
            self.arg_inputs[key] = input_field
            
            # Añadir al grid
            args_grid.addWidget(label, row, col * 2)
            args_grid.addWidget(input_field, row, col * 2 + 1)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        args_layout.addLayout(args_grid)
        layout.addWidget(args_container, stretch=1)
        
        # Contenedor para el botón
        button_container = QWidget()
        button_container.setStyleSheet(f"background-color: {THEME['secondary_bg']};")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(10, 5, 10, 5)
        
        # Botón de ejecución
        run_button = QPushButton("Run")
        run_button.setFixedSize(60, 30)
        run_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg']};
                color: {THEME['fg']};
                border: 1px solid {THEME['border']};
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {THEME['button_hover']};
            }}
        """)
        run_button.clicked.connect(self.get_command)
        button_layout.addWidget(run_button)
        layout.addWidget(button_container)

    def get_command(self):
        cmd = []
        for key, input_field in self.arg_inputs.items():
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

class ScriptRunnerModule(BaseModule):
    def __init__(self, config_file=None, scripts_section="scripts", **kwargs):
        self.config_file = config_file
        self.scripts_section = scripts_section
        self.scripts = {}
        self.processes = {}
        super().__init__()
        
    def init_ui(self):
        """Inicializa la interfaz del módulo."""
        # Layout principal
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        self.setLayout(main_layout)
        
        # Área de scripts
        scripts_scroll = QScrollArea()
        scripts_scroll.setWidgetResizable(True)
        scripts_scroll.setStyleSheet(f"background-color: {THEME['bg']}; border: none;")
        
        scripts_container = QWidget()
        scripts_container.setStyleSheet(f"background-color: {THEME['bg']};")
        self.scripts_layout = QVBoxLayout(scripts_container)
        self.scripts_layout.setSpacing(5)
        self.scripts_layout.setContentsMargins(0, 0, 0, 0)
        
        scripts_scroll.setWidget(scripts_container)
        
        # Cargar scripts del JSON
        if self.config_file:
            self.load_scripts()
            self.create_script_widgets()
        else:
            self.log_message("No se ha proporcionado un archivo de configuración", error=True)
        
        # Área de log
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {THEME['secondary_bg']};
                color: {THEME['fg']};
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                padding: 5px;
            }}
        """)
        
        # Añadir widgets al layout principal
        main_layout.addWidget(scripts_scroll, stretch=1)
        main_layout.addWidget(self.log_text)

    def create_script_widgets(self):
        for script_name, script_info in self.scripts.items():
            # Pasamos self como el módulo y como parent
            script_widget = ScriptWidget(script_name, script_info, module=self, parent=self)
            self.scripts_layout.addWidget(script_widget)

    def print_widget_hierarchy(widget, level=0):
        print("  " * level + f"Widget: {type(widget).__name__}")
        for child in widget.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            print_widget_hierarchy(child, level + 1)
            



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

    def create_script_widgets(self):
        for script_name, script_info in self.scripts.items():
            script_widget = ScriptWidget(script_name, script_info, self)
            self.scripts_layout.addWidget(script_widget)

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

    def log_message(self, message, error=False, success=False):
        if error:
            self.log_text.append(f'<span style="color: #ff5555; font-weight: bold;">{message}</span>')
        elif success:
            self.log_text.append(f'<span style="color: #50fa7b; font-weight: bold;">{message}</span>')
        else:
            self.log_text.append(f'<span style="color: {THEME["fg"]};">{message}</span>')
        
        # Asegurarse de que el mensaje más reciente sea visible
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        # Y luego desde algún punto del código:

    def show_error_dialog(self, title, message):
        error_dialog = QMessageBox(self)
        error_dialog.setWindowTitle(title)
        error_dialog.setText(message)
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setStyleSheet(f"""
            QMessageBox {{
                background-color: {THEME['bg']};
                color: {THEME['fg']};
            }}
            QPushButton {{
                background-color: {THEME['secondary_bg']};
                color: {THEME['fg']};
                border: 1px solid {THEME['border']};
                padding: 5px 10px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {THEME['button_hover']};
            }}
        """)
        error_dialog.exec()

    def apply_theme(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {THEME['bg']};
                color: {THEME['fg']};
            }}
        """)