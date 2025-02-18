from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLineEdit, QLabel, QMessageBox, QGroupBox,
    QScrollArea, QFrame, QApplication, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from base_module import BaseModule
import json
from pathlib import Path

class ConfigField(QWidget):
    """Widget para un campo individual de configuración"""
    def __init__(self, label: str, value, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(label)
        self.label.setMinimumWidth(150)
        
        # Convertir el valor a string para el QLineEdit
        str_value = str(value) if not isinstance(value, (dict, list)) else json.dumps(value)
        self.input = QLineEdit(str_value)
        self.original_value = value
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.input)
        
    def get_value(self):
        # Intenta convertir el valor de vuelta a su tipo original
        text = self.input.text()
        
        # Si el valor original era un número, convertir de vuelta
        if isinstance(self.original_value, int):
            try:
                return int(text)
            except ValueError:
                return text
        elif isinstance(self.original_value, float):
            try:
                return float(text)
            except ValueError:
                return text
        elif isinstance(self.original_value, bool):
            lower_text = text.lower()
            if lower_text in ('true', 't', 'yes', 'y', '1'):
                return True
            elif lower_text in ('false', 'f', 'no', 'n', '0'):
                return False
            else:
                return text
        
        return text

class NestedConfigGroup(QGroupBox):
    """Widget para visualizar y editar configuración anidada"""
    def __init__(self, title: str, config_data: dict, parent=None):
        super().__init__(title, parent)
        self.config_data = config_data
        self.fields = {}
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        for key, value in config_data.items():
            if isinstance(value, dict):
                # Crear un grupo anidado para el diccionario
                nested_group = NestedConfigGroup(key, value)
                layout.addWidget(nested_group)
                self.fields[key] = nested_group
            else:
                # Crear un campo simple para valores no anidados
                field = ConfigField(key, value)
                layout.addWidget(field)
                self.fields[key] = field
    
    def get_value(self):
        result = {}
        for key, field in self.fields.items():
            result[key] = field.get_value()
        return result

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
        # Crear el layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Crear un widget para contener todos los elementos
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)
        container_layout.setContentsMargins(10, 10, 10, 10)
        
        # Área de desplazamiento
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(container)
        
        main_layout.addWidget(scroll_area)
        
        if not self.config_data["modules"]:
            # Si no hay módulos configurados, mostrar un mensaje
            label = QLabel("No modules configured. Add modules to config file.")
            container_layout.addWidget(label)
        else:
            # Crear grupos para cada módulo
            for module in self.config_data["modules"]:
                group = QGroupBox(module["name"])
                group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                group_layout = QVBoxLayout()
                
                # Campos específicos para cada módulo
                fields = {}
                
                # Procesar argumentos del módulo
                for key, value in module["args"].items():
                    if isinstance(value, dict):
                        # Usar NestedConfigGroup para estructuras anidadas
                        nested_group = NestedConfigGroup(key, value)
                        group_layout.addWidget(nested_group)
                        fields[key] = nested_group
                    else:
                        # Usar ConfigField para valores simples
                        field = ConfigField(key, value)
                        group_layout.addWidget(field)
                        fields[key] = field
                    
                self.fields[module["name"]] = fields
                
                # Botón de guardar para este módulo
                save_button = QPushButton(f"Save {module['name']} Settings")
                save_button.clicked.connect(lambda checked, m=module["name"]: self.save_module_config(m))
                group_layout.addWidget(save_button)
                
                group.setLayout(group_layout)
                container_layout.addWidget(group)
                
            # Botón para guardar todo
            save_all_button = QPushButton("Save All Changes")
            save_all_button.clicked.connect(self.save_all_config)
            container_layout.addWidget(save_all_button)
        
        # Agregar un espacio flexible al final para que todo quede alineado arriba
        container_layout.addStretch()

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