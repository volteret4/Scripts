from PyQt6.QtWidgets import QWidget, QMessageBox
from typing import Dict, Optional

# Default themes
THEMES = {
    "Tokyo Night": {  # Tokyo Night
        'bg': '#1a1b26',
        'fg': '#a9b1d6',
        'accent': '#7aa2f7',
        'secondary_bg': '#24283b',
        'border': '#414868',
        'selection': '#364A82',
        'button_hover': '#3d59a1'
    },
    "Solarized Dark": {  # Solarized Dark
        'bg': '#002b36',
        'fg': '#839496',
        'accent': '#268bd2',
        'secondary_bg': '#073642',
        'border': '#586e75',
        'selection': '#2d4b54',
        'button_hover': '#4b6e83'
    },
    "Monokai": {  # Monokai
        'bg': '#272822',
        'fg': '#f8f8f2',
        'accent': '#a6e22e',
        'secondary_bg': '#3e3d32',
        'border': '#75715e',
        'selection': '#49483e',
        'button_hover': '#5c6370'
    }
}

class BaseModule(QWidget):
    """Clase base para todos los módulos."""
    def __init__(self, parent=None, theme='Tokyo Night'):
        super().__init__(parent)
        self.tab_manager = None
        self._module_registry = {}
        self.current_theme = theme
        self.themes = THEMES  # Assuming THEMES is imported or defined
        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        """Método que deben implementar las clases hijas."""
        raise NotImplementedError("Subclasses must implement init_ui method")

    def apply_theme(self, theme_name: Optional[str] = None):
        """
        Universal theme application method.
        
        Args:
            theme_name (str, optional): Name of the theme to apply. 
                                        If None, uses the current theme.
        """
        # Update current theme if a new theme is provided
        if theme_name is not None:
            self.current_theme = theme_name

        # Ensure the theme exists, fallback to default if not
        if self.current_theme not in self.themes:
            self.current_theme = list(self.themes.keys())[0]

        # Get the current theme dictionary
        theme = self.themes[self.current_theme]

        # Optional: Apply theme to the entire module
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme['bg']};
                color: {theme['fg']};
            }}
            
            QLabel {{
                color: {theme['fg']};
            }}
            
            QPushButton {{
                background-color: {theme['secondary_bg']};
                color: {theme['fg']};
                border: 1px solid {theme['border']};
                border-radius: 3px;
            }}
            
            QPushButton:hover {{
                background-color: {theme['button_hover']};
            }}
            
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {theme['secondary_bg']};
                color: {theme['fg']};
                border: 1px solid {theme['border']};
                border-radius: 3px;
            }}
        """)

        # Recursive theme application to child widgets
        self._apply_theme_to_children(self, theme)

    def _apply_theme_to_children(self, parent, theme):
        """
        Recursively apply theme to child widgets
        
        Args:
            parent (QWidget): Parent widget to start theme application
            theme (dict): Theme dictionary
        """
        for child in parent.findChildren(QWidget):
            try:
                if hasattr(child, 'apply_theme'):
                    child.apply_theme(self.current_theme)
            except Exception as e:
                print(f"Warning: Could not apply theme to {child}: {e}")

    def set_tab_manager(self, tab_manager):
        """Establece la referencia al gestor de pestañas y actualiza el registro de módulos"""
        self.tab_manager = tab_manager
        
        # Crear un registro de módulos basado en los tabs disponibles
        if tab_manager and hasattr(tab_manager, 'tabs'):
            self._module_registry = {
                tab_name.lower().replace(' ', '_'): module 
                for tab_name, module in tab_manager.tabs.items()
            }

    def switch_tab(self, tab_name, method_to_call=None, *args, **kwargs):
        """Método de conveniencia para cambiar de pestaña desde el módulo"""
        if self.tab_manager:
            return self.tab_manager.switch_to_tab(tab_name, method_to_call, *args, **kwargs)
        else:
            print("No hay referencia al gestor de pestañas")
            return False

    def get_module(self, module_name):
        """
        Obtiene un módulo del registro por su nombre.
        
        Args:
            module_name (str): Nombre del módulo en formato lowercase con guiones bajos
        
        Returns:
            El módulo solicitado o None si no se encuentra
        """
        return self._module_registry.get(module_name)

    def call_module_method(self, module_name, method_name, *args, **kwargs):
        """Llama a un método de otro módulo"""
        if not self.tab_manager:
            print("TabManager no configurado")
            return None
        
        module = self.tab_manager.tabs.get(module_name)
        if module is None:
            print(f"Módulo '{module_name}' no encontrado")
            return None
        
        if hasattr(module, method_name):
            method = getattr(module, method_name)
            if callable(method):
                return method(*args, **kwargs)
        
        print(f"Método '{method_name}' no encontrado en '{module_name}'")
        return None