from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLineEdit, QLabel, QMessageBox, QGroupBox,
    QScrollArea, QFrame, QApplication, QSizePolicy,
    QComboBox, QCheckBox, QInputDialog
)
from PyQt6.QtCore import pyqtSignal, Qt
from base_module import BaseModule, THEMES
import json
from pathlib import Path
import copy
import sys



class ConfigEditorModule(BaseModule):
    config_updated = pyqtSignal()
    module_theme_changed = pyqtSignal(str, str)  # Signal to change theme for a specific module

    def __init__(self, config_path: str, parent=None, theme='Tokyo Night', **kwargs):
        # Initialize config_data with new global configuration options
        self.config_data = {
            "temas": THEMES,  # Always use THEMES from base_module
            "tema_seleccionado": theme,
            "logging": ["true", "false"],
            "logging_state": "true",
            
            # New global configuration options
            "global_theme_config": {
                "enable_individual_themes": True,
                "shared_db_paths": {
                    # Example of how shared database paths might be configured
                    "music_database": "/home/huan/Scripts/MOODE.sqlite"
                }
            },
            
            "modules": [],
            "modulos_desactivados": []  # Add list for disabled modules
        }
        self.config_path = config_path
        self.fields = {}
        self.module_checkboxes = {}  # Store module checkboxes

        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)        
        
        self.load_config()
        
        super().__init__(parent, theme)
        

    def apply_theme(self, theme_name=None):
        super().apply_theme(theme_name)

    def load_config(self):
        """Load configuration from file"""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    
                    # Overwrite themes with THEMES
                    loaded_config["temas"] = list(THEMES.keys())
                    
                    # Validate selected theme
                    if loaded_config["tema_seleccionado"] not in THEMES:
                        loaded_config["tema_seleccionado"] = list(THEMES.keys())[0]
                    
                    # Ensure modulos_desactivados exists
                    if "modulos_desactivados" not in loaded_config:
                        loaded_config["modulos_desactivados"] = []
                    
                    self.config_data = loaded_config
            else:
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
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a container widget for all elements
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)
        container_layout.setContentsMargins(10, 10, 10, 10)
        
        # Scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(container)
        
        main_layout.addWidget(scroll_area)
        
        # Group for global configurations
        global_group = QGroupBox("Global Configuration")
        global_layout = QVBoxLayout()
        global_group.setLayout(global_layout)

        # Global theme selection dropdown
        theme_field = ConfigField("Global Theme", list(THEMES.keys()))
        theme_field.set_value(self.config_data["tema_seleccionado"])
        global_layout.addWidget(theme_field)
        
        # Logging state dropdown
        logging_field = ConfigField("Logging", self.config_data["logging"])
        logging_field.set_value(self.config_data["logging_state"])
        global_layout.addWidget(logging_field)
        
        # New global theme configuration checkbox
        enable_individual_themes = QCheckBox("Enable Individual Module Themes")
        enable_individual_themes.setChecked(
            self.config_data.get("global_theme_config", {}).get("enable_individual_themes", True)
        )
        global_layout.addWidget(enable_individual_themes)
        
        # Shared database paths configuration
        shared_db_group = QGroupBox("Shared Database Paths")
        shared_db_layout = QVBoxLayout()
        shared_db_group.setLayout(shared_db_layout)
        
        global_theme_config = self.config_data.get("global_theme_config", {})
        shared_db_paths = global_theme_config.get("shared_db_paths", {})
        
        # Dropdown for existing database paths
        db_path_layout = QHBoxLayout()
        db_path_label = QLabel("Database Path:")
        self.db_paths_dropdown = QComboBox()
        self.db_paths_dropdown.addItems(list(shared_db_paths.keys()))
        
        # Path input field
        self.db_path_input = QLineEdit()
        self.db_path_input.setPlaceholderText("Enter database path")
        
        # Buttons
        add_path_button = QPushButton("Add Path")
        remove_path_button = QPushButton("Remove Path")
        
        # Layout for dropdown and buttons
        db_path_layout.addWidget(db_path_label)
        db_path_layout.addWidget(self.db_paths_dropdown)
        db_path_layout.addWidget(self.db_path_input)
        db_path_layout.addWidget(add_path_button)
        db_path_layout.addWidget(remove_path_button)
        
        shared_db_layout.addLayout(db_path_layout)
        
        # Connect buttons
        add_path_button.clicked.connect(self.add_shared_db_path)
        remove_path_button.clicked.connect(self.remove_shared_db_path)
        
        # If there are existing paths, populate the input with the first one
        if shared_db_paths:
            first_key = list(shared_db_paths.keys())[0]
            self.db_path_input.setText(shared_db_paths[first_key])
        
        # Update input when dropdown selection changes
        self.db_paths_dropdown.currentTextChanged.connect(self.update_db_path_input)
        
        global_layout.addWidget(shared_db_group)
        
        container_layout.addWidget(global_group)
        
        # Create "Active Modules" group
        active_modules_group = QGroupBox("Active Modules")
        active_modules_layout = QVBoxLayout()
        active_modules_group.setLayout(active_modules_layout)
        
        # Create "Disabled Modules" group
        disabled_modules_group = QGroupBox("Disabled Modules")
        disabled_modules_layout = QVBoxLayout()
        disabled_modules_group.setLayout(disabled_modules_layout)
        
        # Flag to check if we need to show any modules section
        has_active_modules = False
        has_disabled_modules = False
        
        # Module configurations - Active modules
        if self.config_data["modules"]:
            has_active_modules = True
            # Create groups for each active module
            for module in self.config_data["modules"]:
                module_group = self.create_module_group(module, True)
                active_modules_layout.addWidget(module_group)
        
        # Disabled modules
        if "modulos_desactivados" in self.config_data and self.config_data["modulos_desactivados"]:
            has_disabled_modules = True
            # Create groups for each disabled module
            for module in self.config_data["modulos_desactivados"]:
                module_group = self.create_module_group(module, False)
                disabled_modules_layout.addWidget(module_group)
        
        # Only add the groups if they have modules
        if has_active_modules:
            container_layout.addWidget(active_modules_group)
        else:
            # If no active modules, show a message
            label = QLabel("No active modules configured.")
            active_modules_layout.addWidget(label)
            container_layout.addWidget(active_modules_group)
        
        if has_disabled_modules:
            container_layout.addWidget(disabled_modules_group)
        
        if not has_active_modules and not has_disabled_modules:
            # If no modules at all, show a general message
            label = QLabel("No modules configured. Add modules to config file.")
            container_layout.addWidget(label)
        
        # Button to save all changes
        save_all_button = QPushButton("Save All Changes")
        save_all_button.clicked.connect(lambda: self.save_all_config(
            enable_individual_themes.isChecked()
        ))
        container_layout.addWidget(save_all_button)
        
        # Add flexible space at the end to align everything at the top
        container_layout.addStretch()



    def create_module_group(self, module, is_active):
        """Create a group for a module with enable/disable checkbox and ordering buttons"""
        module_name = module["name"]
        
        # Create the group
        group = QGroupBox()
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        group_layout = QVBoxLayout()
        
        # Create header with checkbox and ordering buttons
        header_layout = QHBoxLayout()
        
        # Enable/disable checkbox
        enable_checkbox = QCheckBox(module_name)
        enable_checkbox.setChecked(is_active)
        enable_checkbox.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(enable_checkbox)
        
        # Add spacer to push ordering buttons to the right
        header_layout.addStretch()
        
        # Add ordering buttons
        move_up_button = QPushButton("↑")
        move_up_button.setFixedWidth(30)
        move_up_button.setToolTip("Move module up")
        move_up_button.clicked.connect(lambda: self.move_module(module_name, "up"))
        
        move_down_button = QPushButton("↓")
        move_down_button.setFixedWidth(30)
        move_down_button.setToolTip("Move module down")
        move_down_button.clicked.connect(lambda: self.move_module(module_name, "down"))
        
        header_layout.addWidget(move_up_button)
        header_layout.addWidget(move_down_button)
        
        # Store the checkbox for later use
        self.module_checkboxes[module_name] = enable_checkbox
        
        group_layout.addLayout(header_layout)
        
     # Fields specific to each module
        fields = {}
        
        # Add module-specific theme dropdown if individual themes are enabled
        if (self.config_data.get("global_theme_config", {}).get("enable_individual_themes", True) and 
            "temas" in module.get("args", {})):
            theme_dropdown = ConfigField(f"Theme", module["args"]["temas"])
            theme_dropdown.set_value(module["args"].get("tema_seleccionado", list(THEMES.keys())[0]))
            group_layout.addWidget(theme_dropdown)
            fields["theme_dropdown"] = theme_dropdown
        
        # Process module arguments
        for key, value in module.get("args", {}).items():
            # Skip 'temas' and 'tema_seleccionado' as they're handled separately
            if key in ["temas", "tema_seleccionado"]:
                continue
            
            if isinstance(value, dict):
                # Use NestedConfigGroup for nested structures
                nested_group = NestedConfigGroup(key, value)
                group_layout.addWidget(nested_group)
                fields[key] = nested_group
            else:
                # Use ConfigField for simple values
                field = ConfigField(key, value)
                group_layout.addWidget(field)
                fields[key] = field
        
        self.fields[module_name] = fields
        
        # Save button for this module
        save_button = QPushButton(f"Save {module_name} Settings")
        save_button.clicked.connect(lambda checked, m=module_name: self.save_module_config(m))
        group_layout.addWidget(save_button)
        
        group.setLayout(group_layout)
        return group



   # Añadir este nuevo método a la clase ConfigEditorModule
    def move_module(self, module_name, direction):
        """Move a module up or down in its list"""
        # Find the module's current list and position
        module_index = -1
        module_list = None
        is_active = self.module_checkboxes[module_name].isChecked()
        
        if is_active:
            # Check in active modules
            for i, module in enumerate(self.config_data["modules"]):
                if module["name"] == module_name:
                    module_index = i
                    module_list = self.config_data["modules"]
                    break
        else:
            # Check in disabled modules
            for i, module in enumerate(self.config_data["modulos_desactivados"]):
                if module["name"] == module_name:
                    module_index = i
                    module_list = self.config_data["modulos_desactivados"]
                    break
        
        if module_list is None or module_index == -1:
            QMessageBox.warning(self, "Error", f"Cannot find module '{module_name}' in the configuration")
            return
        
        # Calculate new position
        new_index = -1
        if direction == "up" and module_index > 0:
            new_index = module_index - 1
        elif direction == "down" and module_index < len(module_list) - 1:
            new_index = module_index + 1
        
        if new_index == -1:
            # Module already at the top/bottom
            return
        
        # Move the module
        module = module_list.pop(module_index)
        module_list.insert(new_index, module)
        
        # Save the changes
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config_data, f, indent=2)
            
            # Notify user and emit signal
            QMessageBox.information(
                self, 
                "Module Reordered", 
                f"Module '{module_name}' has been moved {direction}."
            )
            
            # Emit config updated signal to trigger reload
            self.config_updated.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving configuration: {str(e)}")


    def update_db_path_input(self, current_key):
        """Update the path input when a new database is selected from dropdown"""
        global_theme_config = self.config_data.get("global_theme_config", {})
        shared_db_paths = global_theme_config.get("shared_db_paths", {})
        
        if current_key in shared_db_paths:
            self.db_path_input.setText(shared_db_paths[current_key])




    def add_shared_db_path(self):
        """Add a new shared database path"""
        path = self.db_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Invalid Input", "Please enter a database path.")
            return
        
        # Prompt for database key
        key, ok = QInputDialog.getText(self, "Database Key", "Enter a key for this database path:")
        if not ok or not key:
            return
        
        # Sanitize the key
        key = key.lower().replace(' ', '_')
        
        # Ensure global_theme_config exists
        if "global_theme_config" not in self.config_data:
            self.config_data["global_theme_config"] = {}
        
        if "shared_db_paths" not in self.config_data["global_theme_config"]:
            self.config_data["global_theme_config"]["shared_db_paths"] = {}
        
        # Check for existing key
        if key in self.config_data["global_theme_config"]["shared_db_paths"]:
            reply = QMessageBox.question(self, "Overwrite", 
                f"A path for '{key}' already exists. Do you want to replace it?",
                QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.No:
                return
        
        # Add or update the path
        self.config_data["global_theme_config"]["shared_db_paths"][key] = path
        
        # Save the configuration to file
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config_data, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save configuration: {str(e)}")
            return
        
        # Update dropdown
        self.db_paths_dropdown.blockSignals(True)
        self.db_paths_dropdown.clear()
        self.db_paths_dropdown.addItems(list(self.config_data["global_theme_config"]["shared_db_paths"].keys()))
        self.db_paths_dropdown.setCurrentText(key)
        self.db_paths_dropdown.blockSignals(False)
        
        # Update path input
        self.db_path_input.setText(path)
        
        # Emit config updated signal
        self.config_updated.emit()
        
        # Show success message
        QMessageBox.information(self, "Success", f"Database path '{key}' added successfully.")





    def remove_shared_db_path(self):
        """Remove selected shared database path"""
        current_key = self.db_paths_dropdown.currentText()
        if not current_key:
            QMessageBox.warning(self, "No Selection", "Please select a database path to remove.")
            return
        
        # Confirmation dialog using StandardButton
        respuesta = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            f"Are you sure you want to delete the database path '{current_key}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if respuesta == QMessageBox.StandardButton.Yes:
            try:
                # Ensure the path exists before trying to delete
                if "global_theme_config" in self.config_data and \
                "shared_db_paths" in self.config_data["global_theme_config"]:
                    
                    db_paths = self.config_data["global_theme_config"]["shared_db_paths"]
                    if current_key in db_paths:
                        del db_paths[current_key]
                    
                    # Save updated configuration to file
                    with open(self.config_path, 'w') as f:
                        json.dump(self.config_data, f, indent=2)
                    
                    # Update dropdown
                    self.db_paths_dropdown.removeItem(self.db_paths_dropdown.currentIndex())
                    
                    # Clear input
                    self.db_path_input.clear()
                    
                    # Emit config updated signal
                    self.config_updated.emit()
                    
                    # Show success message
                    QMessageBox.information(self, "Success", f"Database path '{current_key}' removed.")
                else:
                    QMessageBox.warning(self, "Error", "Configuration structure is invalid.")
            
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not remove database path: {str(e)}")
                

    def save_module_config(self, module_name: str):
        """Save configuration for a specific module"""
        try:
            # Find the module in either active or disabled modules
            is_active = self.module_checkboxes[module_name].isChecked()
            
            # Find where the module currently exists (active or disabled list)
            module_list = None
            module_index = -1
            
            # Look in active modules first
            for i, module in enumerate(self.config_data["modules"]):
                if module["name"] == module_name:
                    module_list = self.config_data["modules"]
                    module_index = i
                    break
            
            # If not found in active, look in disabled
            if module_index == -1:
                for i, module in enumerate(self.config_data["modulos_desactivados"]):
                    if module["name"] == module_name:
                        module_list = self.config_data["modulos_desactivados"]
                        module_index = i
                        break
            
            if module_list is None or module_index == -1:
                QMessageBox.critical(self, "Error", f"Module {module_name} not found in configuration")
                return
            
            # Update module settings
            module = module_list[module_index]
            module_fields = self.fields[module_name]
            
            # Handle module theme change
            if "theme_dropdown" in module_fields:
                new_theme = module_fields["theme_dropdown"].get_value()
                module["args"]["tema_seleccionado"] = new_theme
                
                # Emit signal to change theme for this specific module
                if is_active:  # Only emit if module is active
                    self.module_theme_changed.emit(module_name, new_theme)
            
            # Update other fields
            for key, field in module_fields.items():
                if key != "theme_dropdown":
                    module["args"][key] = field.get_value()
            
            # Move module if needed between active/disabled lists
            source_list = module_list
            dest_list = self.config_data["modules"] if is_active else self.config_data["modulos_desactivados"]
            
            if source_list != dest_list:
                # Remove from source list
                module = source_list.pop(module_index)
                # Add to destination list
                dest_list.append(module)
                
                QMessageBox.information(
                    self, 
                    "Module Status Changed",
                    f"Module '{module_name}' has been {'enabled' if is_active else 'disabled'}."
                )
            
            # Save to file
            with open(self.config_path, 'w') as f:
                json.dump(self.config_data, f, indent=2)
                
            QMessageBox.information(self, "Success", f"Configuration for {module_name} saved successfully")
            self.config_updated.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving config: {str(e)}")

    def save_all_config(self, enable_individual_themes=True):
        """Save all configuration changes"""
        try:
            # Ensure global_theme_config exists
            if "global_theme_config" not in self.config_data:
                self.config_data["global_theme_config"] = {}
            
            # Update enable individual themes setting
            self.config_data["global_theme_config"]["enable_individual_themes"] = enable_individual_themes
            
            # Ensure shared_db_paths exists
            if "shared_db_paths" not in self.config_data["global_theme_config"]:
                self.config_data["global_theme_config"]["shared_db_paths"] = {}
            
            # Add current path if not empty
            current_key = self.db_paths_dropdown.currentText()
            current_path = self.db_path_input.text().strip()
            if current_key and current_path:
                self.config_data["global_theme_config"]["shared_db_paths"][current_key] = current_path
            
            # Update global theme
            theme_fields = [f for f in self.findChildren(ConfigField) if f.label.text() == "Global Theme"]
            if theme_fields:
                new_global_theme = theme_fields[0].get_value()
                self.config_data["tema_seleccionado"] = new_global_theme
            
            # Update logging state
            logging_fields = [f for f in self.findChildren(ConfigField) if f.label.text() == "Logging"]
            if logging_fields:
                self.config_data["logging_state"] = logging_fields[0].get_value()
            
            # Process all module checkboxes to move modules between active/disabled lists
            for module_name, checkbox in self.module_checkboxes.items():
                is_active = checkbox.isChecked()
                
                # Find the module in either list
                found_in_active = False
                found_in_disabled = False
                active_index = -1
                disabled_index = -1
                
                # Check active modules
                for i, module in enumerate(self.config_data["modules"]):
                    if module["name"] == module_name:
                        found_in_active = True
                        active_index = i
                        break
                
                # Check disabled modules
                for i, module in enumerate(self.config_data["modulos_desactivados"]):
                    if module["name"] == module_name:
                        found_in_disabled = True
                        disabled_index = i
                        break
                
                # Move module if needed
                if found_in_active and not is_active:
                    # Move from active to disabled
                    module = self.config_data["modules"].pop(active_index)
                    self.config_data["modulos_desactivados"].append(module)
                elif found_in_disabled and is_active:
                    # Move from disabled to active
                    module = self.config_data["modulos_desactivados"].pop(disabled_index)
                    self.config_data["modules"].append(module)
                
                # Update module settings
                module_list = self.config_data["modules"] if is_active else self.config_data["modulos_desactivados"]
                
                # Find module in the appropriate list
                for module in module_list:
                    if module["name"] == module_name:
                        if module_name in self.fields:
                            module_fields = self.fields[module_name]
                            
                            # Update module theme if individual themes are enabled
                            if "theme_dropdown" in module_fields:
                                theme_value = module_fields["theme_dropdown"].get_value()
                                module["args"]["tema_seleccionado"] = theme_value
                            
                            # Update other module-specific fields
                            for key, field in module_fields.items():
                                if key != "theme_dropdown":
                                    module["args"][key] = field.get_value()
                        break
            
            # Save file
            with open(self.config_path, 'w') as f:
                json.dump(self.config_data, f, indent=2)
            
            QMessageBox.information(self, "Success", "All configurations saved successfully")
            self.config_updated.emit()
            
            return True  # Indicate successful save
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving config: {str(e)}")
            return False  # Indicate save failure






class ConfigField(QWidget):
    """Widget para un campo individual de configuración"""
    def __init__(self, label: str, value):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(label)
        self.label.setMinimumWidth(150)
        
        # Si el valor es una lista, crear un QComboBox
        if isinstance(value, list):
            self.input = QComboBox()
            self.input.addItems(map(str, value))
            # Intentar preseleccionar un valor por defecto o el primer elemento
            self.original_value = value[0] if value else None
            self.input.setCurrentText(str(self.original_value))
        else:
            # Convertir el valor a string para el QLineEdit
            str_value = str(value) if not isinstance(value, (dict, list)) else json.dumps(value)
            self.input = QLineEdit(str_value)
            self.original_value = value
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.input)
        
    def apply_theme(self, theme_name=None):
        """
        Optional method to apply theme if needed.
        Remove the super() call since QWidget doesn't have this method.
        """
        pass 

    def get_value(self):
        # Para listas (QComboBox), devolver el elemento seleccionado
        if isinstance(self.input, QComboBox):
            return self.input.currentText()
        
        # Lógica existente para otros tipos de entrada
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


    def set_value(self, value):
        """Método para establecer el valor del campo"""
        if isinstance(self.input, QComboBox):
            self.input.setCurrentText(str(value))
        else:
            self.input.setText(str(value))

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

