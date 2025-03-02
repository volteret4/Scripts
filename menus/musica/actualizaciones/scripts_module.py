from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                           QScrollArea, QWidget, QGridLayout, QLineEdit,
                           QTextEdit, QSplitter)
from PyQt6.QtCore import Qt, QProcess
import json
import sys
from base_module import BaseModule, THEME
from pathlib import Path

class ScriptWidget(QWidget):
    def __init__(self, script_name, script_info, parent=None):
        super().__init__(parent)
        self.script_name = script_name
        self.script_info = script_info
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
        
        if isinstance(self.parent(), ScriptRunnerModule):
            self.parent().run_script(self.script_info, cmd)

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
        scripts_container = QWidget()
        scripts_container.setStyleSheet(f"background-color: {THEME['bg']};")
        self.scripts_layout = QVBoxLayout(scripts_container)
        self.scripts_layout.setSpacing(5)
        self.scripts_layout.setContentsMargins(0, 0, 0, 0)
        
        # Cargar scripts del JSON
        if self.config_file:
            self.load_scripts()
            self.create_script_widgets()
        
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
        main_layout.addWidget(scripts_container, stretch=1)
        main_layout.addWidget(self.log_text)

    def load_scripts(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            self.scripts = config.get(self.scripts_section, {})
            
        except Exception as e:
            self.log_message(f"Error loading configuration: {str(e)}", error=True)

    def create_script_widgets(self):
        for script_name, script_info in self.scripts.items():
            script_widget = ScriptWidget(script_name, script_info, self)
            self.scripts_layout.addWidget(script_widget)

# Modificaciones para ScriptRunnerModule.run_script
    def run_script(self, script_info, additional_args=None):
        try:
            script_path = Path(script_info.get('path', ''))
            self.log_message(f"Script original path: {script_path}")
            
            # Si la ruta es relativa, hacerla absoluta respecto al directorio del config
            if not script_path.is_absolute():
                config_dir = Path(self.config_file).parent
                script_path = config_dir / script_path
            
            self.log_message(f"Script resolved path: {script_path}")
            
            # Verificar que el archivo existe
            if not script_path.exists():
                error_msg = f"Error: Script file does not exist: {script_path}"
                self.log_message(error_msg, error=True)
                
                # Mostrar el mensaje en rojo y más prominente
                self.log_text.append(f'<p style="color: red; font-weight: bold; background-color: {THEME["bg"]}; padding: 5px; border: 1px solid red; border-radius: 3px;">⚠️ PATH ERROR: El archivo no existe en la ruta especificada: {script_path}</p>')
                return
                
            process = QProcess(self)
            process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            process.readyRead.connect(lambda p=process: self.handle_process_output(p))
            process.finished.connect(lambda code, status, p=process: self.handle_process_finished(p, code, status))
            
            cmd = [sys.executable, str(script_path)]
            if additional_args:
                cmd.extend(additional_args)
            
            self.log_message(f"Running command: {' '.join(cmd)}")
            
            self.processes[process] = script_path.name
            process.start(cmd[0], cmd[1:])
            
        except Exception as e:
            self.log_message(f"Error running script: {str(e)}", error=True)
            import traceback
            self.log_message(traceback.format_exc(), error=True)
            
            # Mostrar el error de manera más visible
            self.log_text.append(f'<p style="color: red; font-weight: bold; background-color: {THEME["bg"]}; padding: 5px; border: 1px solid red; border-radius: 3px;">⚠️ ERROR AL EJECUTAR: {str(e)}</p>')

    def handle_process_output(self, process):
        try:
            data = process.readAll()
            if data:
                output = data.data().decode('utf-8', errors='replace')
                script_name = self.processes.get(process, "Unknown script")
                self.log_message(f"[{script_name}] {output.strip()}")
        except Exception as e:
            self.log_message(f"Error reading process output: {str(e)}", error=True)

    def handle_process_finished(self, process, exit_code, exit_status):
        script_name = self.processes.get(process, "Unknown script")
        if exit_code == 0:
            self.log_message(f"[{script_name}] Completed successfully")
        else:
            self.log_message(f"[{script_name}] Failed with exit code {exit_code}", error=True)
        self.processes.pop(process, None)

    def log_message(self, message, error=False):
        if error:
            # Para errores, usar formato más visible
            self.log_text.append(f'<span style="color: red; font-weight: bold;">{message}</span>')
        else:
            # Para mensajes normales
            self.log_text.append(f'<span style="color: white;">{message}</span>')
        
        # Asegurarse de que el mensaje más reciente sea visible
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def apply_theme(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {THEME['bg']};
                color: {THEME['fg']};
            }}
        """)