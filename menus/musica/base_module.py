from PyQt6.QtWidgets import QWidget

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
        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        """Método que deben implementar las clases hijas."""
        raise NotImplementedError

    def apply_theme(self, theme_name=None):
        """Aplica el tema actual o uno nuevo."""
        if theme_name:
            self.current_theme = theme_name
        
        theme = THEMES.get(self.current_theme, THEMES['Tokyo Night'])
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme['bg']};
                color: {theme['fg']};
            }}
            
            QPushButton {{
                background-color: {theme['secondary_bg']};
                color: {theme['fg']};
                border: 1px solid {theme['border']};
                border-radius: 3px;
                padding: 5px 10px;
            }}
            
            QPushButton:hover {{
                background-color: {theme['button_hover']};
            }}
        """)

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