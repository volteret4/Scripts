import sys
import os
from typing import Dict
import json
from pathlib import Path
import importlib.util
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                            QVBoxLayout, QTabWidget)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from base_module import BaseModule
import traceback

# Tema Tokyo Night (puedes personalizarlo o cargar desde config)
THEME = {
    'bg': '#1a1b26',
    'fg': '#a9b1d6',
    'accent': '#7aa2f7',
    'secondary_bg': '#24283b',
    'border': '#414868',
    'selection': '#364A82',
    'button_hover': '#3d59a1'
}

class TabManager(QMainWindow):
    def __init__(self, config_path: str, font_family="Inter"):
        super().__init__()
        self.font_family = font_family
        self.config_path = config_path
        self.tabs: Dict[str, QWidget] = {}
        self.init_ui()
        self.load_modules()

    def init_ui(self):
        """Inicializa la interfaz principal."""
        self.setWindowTitle('Multi-Module Manager')
        self.setMinimumSize(1200, 800)

        # Widget principal
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Crear el widget de pestañas
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self.apply_theme()

    def load_modules(self):
        """Carga los módulos desde la configuración."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
            for module_config in config['modules']:
                parent_dir = Path(__file__).parent
                relative_path = Path(module_config['path'])
                module_path = str(parent_dir / relative_path)
                module_name = module_config.get('name', Path(module_path).stem)
                module_args = module_config.get('args', {})
                
                try:
                    # Cargar el módulo dinámicamente
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Buscar la clase principal del módulo
                        main_class = None
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if isinstance(attr, type) and issubclass(attr, BaseModule) and attr != BaseModule:
                                main_class = attr
                                break
                                
                        if main_class:
                            # Instanciar el módulo
                            module_instance = main_class(**module_args)
                            
                            # Si es el editor de configuración, conectar la señal
                            if module_name == "Config Editor":
                                module_instance.config_updated.connect(self.reload_application)
                            
                            # Añadir al gestor de pestañas
                            self.tab_widget.addTab(module_instance, module_name)
                            self.tabs[module_name] = module_instance
                        else:
                            print(f"No se encontró una clase válida en el módulo {module_name}")
                            
                except Exception as e:
                    print(f"Error loading module {module_name}: {e}")
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"Error loading configuration: {e}")
            traceback.print_exc()

    def apply_theme(self):
        """Aplica el tema a toda la aplicación."""
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {THEME['bg']};
                color: {THEME['fg']};
                font-family: {self.font_family};
            }}
            
            QTabWidget::pane {{
                border: 1px solid {THEME['border']};
                background-color: {THEME['bg']};
                border-radius: 3px;
            }}
            
            QTabBar::tab {{
                background-color: {THEME['secondary_bg']};
                color: {THEME['fg']};
                border: 1px solid {THEME['border']};
                padding: 5px 10px;
                margin-right: 2px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {THEME['bg']};
                border-bottom-color: {THEME['bg']};
            }}
            
            QTabBar::tab:hover {{
                background-color: {THEME['button_hover']};
            }}
            
            QLineEdit {{
                background-color: {THEME['secondary_bg']};
                border: 1px solid {THEME['border']};
                padding: 5px;
                border-radius: 3px;
            }}
            
            QPushButton {{
                background-color: {THEME['secondary_bg']};
                border: 1px solid {THEME['border']};
                padding: 5px 10px;
                border-radius: 3px;
            }}
            
            QPushButton:hover {{
                background-color: {THEME['button_hover']};
            }}
            
            QListWidget {{
                background-color: {THEME['secondary_bg']};
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                padding: 5px;
            }}
            
            QListWidget::item:selected {{
                background-color: {THEME['selection']};
            }}
        """)


    def reload_application(self):
        """Recarga todos los módulos después de un cambio en la configuración"""
        # Guardar el índice de la pestaña actual
        current_index = self.tab_widget.currentIndex()
        
        # Eliminar todas las pestañas existentes
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        
        # Limpiar el diccionario de pestañas
        self.tabs.clear()
        
        # Recargar los módulos
        self.load_modules()
        
        # Restaurar el índice de la pestaña si es posible
        if current_index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(current_index)



def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Module Manager')
    parser.add_argument('config_path', help='Ruta al archivo de configuración JSON')
    parser.add_argument('--font', default='Inter', help='Fuente a usar en la interfaz')
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    manager = TabManager(args.config_path, font_family=args.font)
    manager.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()