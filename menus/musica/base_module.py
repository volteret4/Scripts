# base_module.py
from PyQt6.QtWidgets import QWidget

# Tema Tokyo Night
THEME = {
    'bg': '#1a1b26',
    'fg': '#a9b1d6',
    'accent': '#7aa2f7',
    'secondary_bg': '#24283b',
    'border': '#414868',
    'selection': '#364A82',
    'button_hover': '#3d59a1'
}

class BaseModule(QWidget):
    """Clase base para todos los módulos."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_manager = None
        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        """Método que deben implementar las clases hijas."""
        raise NotImplementedError

    def apply_theme(self):
        """Los módulos pueden sobrescribir este método para personalizar su tema."""
        pass

    
    def set_tab_manager(self, tab_manager):
        """Establece la referencia al gestor de pestañas"""
        self.tab_manager = tab_manager
    
    def switch_tab(self, tab_name, method_to_call=None, *args, **kwargs):
        """Método de conveniencia para cambiar de pestaña desde el módulo"""
        if self.tab_manager:
            return self.tab_manager.switch_to_tab(tab_name, method_to_call, *args, **kwargs)
        else:
            print("No hay referencia al gestor de pestañas")
            return False