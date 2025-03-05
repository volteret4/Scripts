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
from base_module import BaseModule, THEMES
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
    def __init__(self, config_path: str, font_family="Inter", font_size="14px"):
        super().__init__()
        self.font_family = font_family
        self.font_size = font_size
        self.config_path = config_path
        self.tabs: Dict[str, QWidget] = {}
        
        # Load initial theme from config
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.available_themes = config.get('temas', ['Tokyo Night', 'Solarized Dark', 'Monokai'])
        self.current_theme = config.get('tema_seleccionado', 'Tokyo Night')
        
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

        self.apply_theme(self.font_size)

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
                    print(f"Intentando cargar módulo desde {module_path}\n")
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

                    
                            # Pasar referencia al TabManager
                            if hasattr(module_instance, 'set_tab_manager'):
                                module_instance.set_tab_manager(self)                           

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




    def apply_theme(self, font_size="14px"):
        """Aplica el tema a toda la aplicación."""
        theme = THEMES.get(self.current_theme, THEMES['Tokyo Night'])
        
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {theme['bg']};
                color: {theme['fg']};
                font-family: {self.font_family};
                font-size: {self.font_size};
            }}
            
            QTabWidget::pane {{
                border: 1px solid {theme['border']};
                background-color: {theme['bg']};
                border-radius: 3px;
            }}
            
            QTabBar::tab {{
                background-color: {theme['secondary_bg']};
                color: {theme['fg']};
                border: 1px solid {theme['border']};
                padding: 5px 10px;
                margin-right: 2px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {theme['bg']};
                border-bottom-color: {theme['bg']};
            }}
            
            QTabBar::tab:hover {{
                background-color: {theme['button_hover']};
            }}
            
            QLineEdit {{
                background-color: {theme['secondary_bg']};
                border: 1px solid {theme['border']};
                padding: 5px;
                border-radius: 3px;
            }}
            
            QPushButton {{
                background-color: {theme['secondary_bg']};
                border: 1px solid {theme['border']};
                padding: 5px 10px;
                border-radius: 3px;
            }}
            
            QPushButton:hover {{
                background-color: {theme['button_hover']};
            }}
            
            QListWidget {{
                background-color: {theme['secondary_bg']};
                border: 1px solid {theme['border']};
                border-radius: 3px;
                padding: 5px;
            }}
            
            QListWidget::item:selected {{
                background-color: {theme['selection']};
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


    def cleanup_threads():
        """Ensure all threads are properly stopped before application exit"""
        for thread in QThread.allThreads():
            if thread != QThread.currentThread():
                try:
                    # If it's our worker, call stop method
                    if hasattr(thread, 'stop'):
                        thread.stop()
                    # Wait for thread to finish
                    thread.wait(5000)  # 5 second timeout
                except Exception as e:
                    print(f"Error cleaning up thread: {e}")


    def change_theme(self, new_theme):
        """Cambia el tema de toda la aplicación."""
        if new_theme in self.available_themes:
            self.current_theme = new_theme
            
            # Reapply theme to TabManager
            self.apply_theme()
            
            # Reapply theme to all modules
            for module in self.tabs.values():
                module.apply_theme(new_theme)
            
            # Update config file
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            config['tema_seleccionado'] = new_theme
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)


    def switch_to_tab(self, tab_name, method_to_call=None, *args, **kwargs):
        """
        Cambia a la pestaña especificada y opcionalmente llama a un método en ese módulo.
        
        Args:
            tab_name (str): Nombre de la pestaña a la que cambiar
            method_to_call (str, optional): Nombre del método a llamar en el módulo destino
            *args, **kwargs: Argumentos a pasar al método
        
        Returns:
            bool: True si se pudo cambiar y llamar al método, False en caso contrario
        """
        # Buscar el índice de la pestaña por nombre
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_name:
                # Cambiar a esa pestaña
                self.tab_widget.setCurrentIndex(i)
                
                # Si hay un método que llamar
                if method_to_call and tab_name in self.tabs:
                    tab_module = self.tabs[tab_name]
                    if hasattr(tab_module, method_to_call):
                        method = getattr(tab_module, method_to_call)
                        if callable(method):
                            method(*args, **kwargs)
                            return True
                        else:
                            print(f"El atributo '{method_to_call}' no es una función en el módulo '{tab_name}'")
                    else:
                        print(f"El módulo '{tab_name}' no tiene un método llamado '{method_to_call}'")
                return True
        
        print(f"No se encontró la pestaña '{tab_name}'")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Module Manager')
    parser.add_argument('config_path', help='Ruta al archivo de configuración JSON')
    parser.add_argument('--font', default='Inter', help='Fuente a usar en la interfaz')
    parser.add_argument('--font_size', default='12px', help='Tamaño de la Fuente a usar en la interfaz')
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    manager = TabManager(args.config_path, font_family=args.font)
    manager.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()