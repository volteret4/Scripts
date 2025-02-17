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
        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        """Método que deben implementar las clases hijas."""
        raise NotImplementedError

    def apply_theme(self):
        """Los módulos pueden sobrescribir este método para personalizar su tema."""
        pass