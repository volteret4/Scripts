from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLineEdit, QLabel, QMessageBox, QGroupBox
)
from PyQt6.QtCore import pyqtSignal
from base_module import BaseModule
import json
from pathlib import Path

class ConfigField(QWidget):
    """Widget para un campo individual de configuración"""
    def __init__(self, label: str, value: str, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(label)
        self.label.setMinimumWidth(150)
        self.input = QLineEdit(str(value))
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.input)
        
    def get_value(self):
        return self.input.text()

class ConfigEditorModule(BaseModule):
    config_updated = pyqtSignal()

    def __init__(self, config_path: str, parent=None):
        # Inicializa config_data antes de llamar a super().__init__
        self.config_data = {
            "modules": []
        }
        self.config_path = config_path
        self.fields = {}
        
        # Carga la configuración antes de llamar a super().__init__
        self.load_config()
        
        # Ahora llama a super().__init__, que llamará a self.init_ui()
        super().__init__(parent)

    def load_config(self):
        """Carga la configuración desde el archivo"""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    if isinstance(loaded_config, dict) and "modules" in loaded_config:
                        self.config_data = loaded_config
                    else:
                        raise ValueError("Invalid config file format")
            else:
                # Si el archivo no existe, creamos uno nuevo con la configuración predeterminada
                self.save_all_config()
                QMessageBox.information(
                    self,
                    "Config Created",
                    f"New config file created at {self.config_path}"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error loading config from {self.config_path}: {str(e)}\nUsing default configuration."
            )

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        if not self.config_data["modules"]:
            # Si no hay módulos configurados, mostrar un mensaje
            label = QLabel("No modules configured. Add modules to config file.")
            layout.addWidget(label)
        else:
            # Crear grupos para cada módulo
            for module in self.config_data["modules"]:
                group = QGroupBox(module["name"])
                group_layout = QVBoxLayout()
                
                # Campos específicos para cada módulo
                fields = {}
                
                # Procesar argumentos del módulo
                for key, value in module["args"].items():
                    field = ConfigField(key, value)
                    group_layout.addWidget(field)
                    fields[key] = field
                    
                self.fields[module["name"]] = fields
                
                # Botón de guardar para este módulo
                save_button = QPushButton(f"Save {module['name']} Settings")
                save_button.clicked.connect(lambda checked, m=module["name"]: self.save_module_config(m))
                group_layout.addWidget(save_button)
                
                group.setLayout(group_layout)
                layout.addWidget(group)
                
            # Botón para guardar todo
            save_all_button = QPushButton("Save All Changes")
            save_all_button.clicked.connect(self.save_all_config)
            layout.addWidget(save_all_button)

    def save_module_config(self, module_name: str):
        """Guarda la configuración de un módulo específico"""
        try:
            # Actualizar los valores en config_data
            for module in self.config_data["modules"]:
                if module["name"] == module_name:
                    for key, field in self.fields[module_name].items():
                        module["args"][key] = field.get_value()
                    break
                    
            # Guardar en archivo
            with open(self.config_path, 'w') as f:
                json.dump(self.config_data, f, indent=2)
                
            QMessageBox.information(self, "Success", f"Configuration for {module_name} saved successfully")
            self.config_updated.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving config: {str(e)}")
            
    def save_all_config(self):
        """Guarda todos los cambios en la configuración"""
        try:
            # Actualizar todos los valores
            for module in self.config_data["modules"]:
                module_name = module["name"]
                if module_name in self.fields:
                    for key, field in self.fields[module_name].items():
                        module["args"][key] = field.get_value()
                        
            # Guardar en archivo
            with open(self.config_path, 'w') as f:
                json.dump(self.config_data, f, indent=2)
                
            QMessageBox.information(self, "Success", "All configurations saved successfully")
            self.config_updated.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving config: {str(e)}")