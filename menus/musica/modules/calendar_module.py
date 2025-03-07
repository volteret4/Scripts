import sys
from datetime import datetime, timedelta
import caldav
import vobject
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QComboBox, QPushButton, QScrollArea, QFrame,
                           QSizePolicy, QGridLayout, QTimeEdit, QDialog,
                           QLineEdit, QTextEdit)
from PyQt6.QtCore import Qt, QTime, QDateTime, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QFont
from base_module import BaseModule, THEMES


class RadicaleCalendarModule(BaseModule):
    """Módulo de calendario que se sincroniza con Radicale"""
    
    def __init__(self, radicale_url, username="", password="", parent=None, theme='Tokyo Night', **kwargs):
        super().__init__(parent, theme)
        self.radicale_url = radicale_url
        self.username = username
        self.password = password
        self.client = None
        self.calendars = []
        self.selected_calendar = None
        
        self.available_themes = kwargs.pop('temas', [])
        self.selected_theme = kwargs.pop('tema_seleccionado', theme)
        
        self.setup_ui()
        self.connect_to_radicale()

    def apply_theme(self, theme_name=None): 
        # Optional: Override if you need custom theming beyond base theme
        super().apply_theme(theme_name)

    def init_ui(self):
        """Implement the base module's UI initialization method"""
        self.setup_ui()  # Call the existing setup_ui method
        
    def setup_ui(self):
        """Configura la interfaz del módulo"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Selector de calendario y botones
        toolbar_layout = QHBoxLayout()
        
        # Selector de calendario
        toolbar_layout.addWidget(QLabel("Calendario:"))
        self.calendar_selector = QComboBox()
        self.calendar_selector.currentIndexChanged.connect(self.on_calendar_selected)
        toolbar_layout.addWidget(self.calendar_selector)
        
        # Espacio
        toolbar_layout.addStretch()
        
        # Botón para actualizar
        self.refresh_button = QPushButton("Actualizar")
        self.refresh_button.clicked.connect(self.load_calendars)
        toolbar_layout.addWidget(self.refresh_button)
        
        # Botón para crear evento
        self.add_event_button = QPushButton("Nuevo Evento")
        self.add_event_button.clicked.connect(self.create_event)
        toolbar_layout.addWidget(self.add_event_button)
        
        layout.addLayout(toolbar_layout)
        
        # Vista diaria
        self.daily_view = DailyCalendarView(self)
        layout.addWidget(self.daily_view)
        
    def connect_to_radicale(self):
        """Conecta con el servidor Radicale"""
        try:
            # Crear cliente de caldav con más logging
            print(f"Conectando a: {self.radicale_url}")
            print(f"Usuario: {self.username}")
            
            self.client = caldav.DAVClient(
                url=self.radicale_url,
                username=self.username,
                password=self.password
            )
            
            # Verificar la conexión
            principal = self.client.principal()
            calendars = principal.calendars()
            
            print(f"Calendarios encontrados: {len(calendars)}")
            for cal in calendars:
                print(f"Calendario: {cal.name} - URL: {cal.url}")
            
            # Cargar calendarios disponibles
            self.load_calendars()
            
        except Exception as e:
            print(f"Error COMPLETO al conectar con Radicale: {e}")
            print(traceback.format_exc())
            
    def load_calendars(self):
        """Carga los calendarios disponibles del servidor"""
        if not self.client:
            return
            
        try:
            # Limpiar selector
            self.calendar_selector.clear()
            self.calendars = []
            
            # Obtener principal
            principal = self.client.principal()
            calendars = principal.calendars()
            
            # Añadir al selector
            for cal in calendars:
                cal_name = cal.name or str(cal.url).split('/')[-2]
                self.calendars.append(cal)
                self.calendar_selector.addItem(cal_name)
                
            # Seleccionar el primero por defecto
            if self.calendars:
                self.selected_calendar = self.calendars[0]
                self.load_events()
                
        except Exception as e:
            print(f"Error al cargar calendarios: {e}")
            
    def on_calendar_selected(self, index):
        """Maneja el cambio de calendario seleccionado"""
        if 0 <= index < len(self.calendars):
            self.selected_calendar = self.calendars[index]
            self.load_events()
            
    def load_events(self):
        """Carga los eventos del calendario seleccionado para la fecha actual"""
        if not self.selected_calendar:
            print("No hay calendario seleccionado")
            return
            
        try:
            # Limpiar eventos existentes
            self.daily_view.clear_events()
            
            # Obtener fecha actual de la vista
            current_date = self.daily_view.current_date
            
            # Definir intervalo (todo el día)
            start_date = datetime.combine(current_date, datetime.min.time())
            end_date = datetime.combine(current_date, datetime.max.time())
            
            print(f"Buscando eventos entre {start_date} y {end_date}")
            
            # Usar .search en lugar de .date_search
            events = self.selected_calendar.search(
                start=start_date,
                end=end_date,
                expand=True
            )
            
            print(f"Eventos encontrados: {len(events)}")  
            
            # Añadir eventos a la vista
            for event in events:
                try:
                    # Añadir un atributo calendar al evento si no existe
                    if not hasattr(event, 'calendar'):
                        event.calendar = self.selected_calendar
                    
                    # Convertir a objeto vobject si es necesario
                    if not hasattr(event, 'vobject_instance'):
                        # Intentar parsear el evento
                        import vobject
                        event.vobject_instance = vobject.readOne(event.data)
                    
                    self.daily_view.add_event(event)
                except Exception as event_error:
                    print(f"Error procesando evento individual: {event_error}")
                    print(traceback.format_exc())
                    
        except Exception as e:
            print(f"Error COMPLETO al cargar eventos: {e}")
            print(traceback.format_exc())
            
    def create_event(self):
        """Crea un nuevo evento en el calendario seleccionado"""
        if not self.selected_calendar:
            return
            
        dialog = EventDialog(self)
        if dialog.exec():
            try:
                # Obtener datos del diálogo
                event_data = dialog.get_event_data()
                
                # Crear fechas con la fecha actual de la vista
                current_date = self.daily_view.current_date
                start_time = event_data['start_time']
                end_time = event_data['end_time']
                
                start_datetime = datetime(
                    current_date.year, current_date.month, current_date.day,
                    start_time.hour(), start_time.minute()
                )
                
                end_datetime = datetime(
                    current_date.year, current_date.month, current_date.day,
                    end_time.hour(), end_time.minute()
                )
                
                # Crear evento iCalendar
                vcal = vobject.iCalendar()
                vevent = vcal.add('vevent')
                vevent.add('summary').value = event_data['summary']
                vevent.add('dtstart').value = start_datetime
                vevent.add('dtend').value = end_datetime
                
                if event_data['description']:
                    vevent.add('description').value = event_data['description']
                
                # Guardar en el calendario
                self.selected_calendar.save_event(vcal.serialize())
                
                # Recargar eventos
                self.load_events()
                
            except Exception as e:
                print(f"Error al crear evento: {e}")
                
    def edit_event(self, event):
        """Edita un evento existente"""
        if not event:
            return
            
        dialog = EventDialog(self, event, self.selected_calendar)
        if dialog.exec():
            try:
                # Obtener datos actualizados
                event_data = dialog.get_event_data()
                
                # Modificar el evento
                vevent = event.vobject_instance.vevent
                
                # Actualizar título
                if hasattr(vevent, 'summary'):
                    vevent.summary.value = event_data['summary']
                else:
                    vevent.add('summary').value = event_data['summary']
                
                # Actualizar descripción
                if hasattr(vevent, 'description'):
                    vevent.description.value = event_data['description']
                elif event_data['description']:
                    vevent.add('description').value = event_data['description']
                
                # Actualizar horas manteniendo la fecha
                if hasattr(vevent, 'dtstart') and hasattr(vevent, 'dtend'):
                    start_date = vevent.dtstart.value.date()
                    end_date = vevent.dtend.value.date()
                    
                    start_time = event_data['start_time']
                    end_time = event_data['end_time']
                    
                    new_start = datetime.combine(
                        start_date,
                        datetime.min.time().replace(
                            hour=start_time.hour(),
                            minute=start_time.minute()
                        )
                    )
                    
                    new_end = datetime.combine(
                        end_date,
                        datetime.min.time().replace(
                            hour=end_time.hour(),
                            minute=end_time.minute()
                        )
                    )
                    
                    vevent.dtstart.value = new_start
                    vevent.dtend.value = new_end
                
                # Guardar cambios
                event.save()
                
                # Recargar eventos
                self.load_events()
                
            except Exception as e:
                print(f"Error al editar evento: {e}")





class EventDialog(QDialog):
    """Diálogo para crear o editar eventos"""
    def __init__(self, parent=None, event=None, calendar=None):
        super().__init__(parent, theme)
        self.event = event
        self.calendar = calendar
        self.setup_ui()
        if event:
            self.load_event_data()

    def setup_ui(self):
        """Configura la interfaz de usuario del diálogo"""
        self.setWindowTitle("Evento de Calendario")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Título
        layout.addWidget(QLabel("Título:"))
        self.title_edit = QLineEdit()
        layout.addWidget(self.title_edit)
        
        # Hora inicio
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Hora inicio:"))
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        self.start_time.setTime(QTime.currentTime())
        time_layout.addWidget(self.start_time)
        
        # Hora fin
        time_layout.addWidget(QLabel("Hora fin:"))
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        self.end_time.setTime(QTime.currentTime().addSecs(3600))  # +1 hora
        time_layout.addWidget(self.end_time)
        
        layout.addLayout(time_layout)
        
        # Descripción
        layout.addWidget(QLabel("Descripción:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        layout.addWidget(self.description_edit)
        
        # Botones
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Guardar")
        self.save_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)

    def load_event_data(self):
        """Carga los datos del evento al editar"""
        if not self.event:
            return
            
        vevent = self.event.vobject_instance.vevent
        
        if hasattr(vevent, 'summary'):
            self.title_edit.setText(str(vevent.summary.value))
            
        if hasattr(vevent, 'dtstart'):
            start_time = vevent.dtstart.value
            if isinstance(start_time, datetime):
                self.start_time.setTime(QTime(start_time.hour, start_time.minute))
        
        if hasattr(vevent, 'dtend'):
            end_time = vevent.dtend.value
            if isinstance(end_time, datetime):
                self.end_time.setTime(QTime(end_time.hour, end_time.minute))
        
        if hasattr(vevent, 'description'):
            self.description_edit.setText(str(vevent.description.value))

    def get_event_data(self):
        """Obtiene los datos ingresados para el evento"""
        return {
            'summary': self.title_edit.text(),
            'description': self.description_edit.toPlainText(),
            'start_time': self.start_time.time(),
            'end_time': self.end_time.time()
        }


class CalendarEvent(QFrame):
    """Widget para mostrar un evento en la vista diaria"""
    clicked = pyqtSignal(object)  # Señal que se emite cuando se hace clic en el evento
    
    def __init__(self, event, parent=None):
        super().__init__(parent)
        self.event = event
        self.setup_ui()
        
    def setup_ui(self):
        """Configura la interfaz del widget de evento"""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setMinimumHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # Determinar color basado en el calendario
        color = self.get_calendar_color()
        self.set_background_color(color)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        
        # Extraer información del evento
        summary = "Sin título"
        start_time = ""
        end_time = ""
        
        vevent = self.event.vobject_instance.vevent
        
        if hasattr(vevent, 'summary'):
            summary = str(vevent.summary.value)
            
        if hasattr(vevent, 'dtstart') and hasattr(vevent, 'dtend'):
            start = vevent.dtstart.value
            end = vevent.dtend.value
            if isinstance(start, datetime) and isinstance(end, datetime):
                start_time = start.strftime("%H:%M")
                end_time = end.strftime("%H:%M")
                
        # Crear etiquetas
        time_label = QLabel(f"{start_time} - {end_time}")
        time_label.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        
        title_label = QLabel(summary)
        title_label.setStyleSheet("font-weight: bold; color: white;")
        title_label.setWordWrap(True)
        
        layout.addWidget(time_label)
        layout.addWidget(title_label)
        
    def get_calendar_color(self):
        """Obtiene un color basado en el nombre del calendario"""
        # Colores predefinidos para calendarios frecuentes
        calendar_colors = {
            "personal": QColor(66, 133, 244),   # Azul
            "trabajo": QColor(219, 68, 55),     # Rojo
            "familia": QColor(244, 180, 0),     # Amarillo
            "cumpleaños": QColor(15, 157, 88),  # Verde
            "vacaciones": QColor(171, 71, 188)  # Violeta
        }
        
        cal_url = str(self.event.calendar.url)
        
        # Buscar coincidencias parciales en la URL del calendario
        for name, color in calendar_colors.items():
            if name.lower() in cal_url.lower():
                return color
                
        # Si no hay coincidencia, usar un color por defecto
        return QColor(100, 100, 100)  # Gris
        
    def set_background_color(self, color):
        """Establece el color de fondo del evento"""
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, color)
        self.setAutoFillBackground(True)
        self.setPalette(palette)
        
    def mousePressEvent(self, event):
        """Maneja el evento de clic del mouse"""
        super().mousePressEvent(event)
        self.clicked.emit(self.event)


class DailyCalendarView(QWidget):
    """Vista diaria del calendario"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_date = datetime.now().date()
        self.events = []
        self.setup_ui()
        
    def setup_ui(self):
        """Configura la interfaz de la vista diaria"""
        layout = QVBoxLayout(self)
        
        # Cabecera con navegación
        header_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("←")
        self.prev_button.clicked.connect(self.previous_day)
        self.prev_button.setMaximumWidth(40)
        
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.next_button = QPushButton("→")
        self.next_button.clicked.connect(self.next_day)
        self.next_button.setMaximumWidth(40)
        
        header_layout.addWidget(self.prev_button)
        header_layout.addWidget(self.date_label)
        header_layout.addWidget(self.next_button)
        
        layout.addLayout(header_layout)
        
        # Vista de horas
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.hours_widget = QWidget()
        self.hours_layout = QGridLayout(self.hours_widget)
        self.hours_layout.setColumnStretch(1, 1)
        self.hours_layout.setSpacing(0)
        
        # Crear filas para cada hora del día
        for hour in range(24):
            time_label = QLabel(f"{hour:02d}:00")
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            time_label.setStyleSheet("padding: 5px; font-weight: bold;")
            time_label.setMinimumWidth(60)
            
            hour_frame = QFrame()
            hour_frame.setFrameShape(QFrame.Shape.StyledPanel)
            hour_frame.setStyleSheet("background-color: rgba(255, 255, 255, 0.05);")
            hour_frame.setMinimumHeight(60)
            
            # Layout para los eventos de esa hora
            hour_layout = QVBoxLayout(hour_frame)
            hour_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            hour_layout.setContentsMargins(2, 2, 2, 2)
            hour_layout.setSpacing(2)
            
            self.hours_layout.addWidget(time_label, hour, 0)
            self.hours_layout.addWidget(hour_frame, hour, 1)
        
        scroll_area.setWidget(self.hours_widget)
        layout.addWidget(scroll_area)
        
        # Actualizar la vista
        self.update_date_label()
        
    def update_date_label(self):
        """Actualiza la etiqueta de fecha"""
        day_name = self.current_date.strftime("%A")
        day_number = self.current_date.strftime("%d")
        month = self.current_date.strftime("%B")
        year = self.current_date.strftime("%Y")
        
        self.date_label.setText(f"{day_name} {day_number} de {month}, {year}")
        
    def previous_day(self):
        """Navega al día anterior"""
        self.current_date -= timedelta(days=1)
        self.update_date_label()
        self.parent().load_events()
        
    def next_day(self):
        """Navega al día siguiente"""
        self.current_date += timedelta(days=1)
        self.update_date_label()
        self.parent().load_events()
        
    def clear_events(self):
        """Limpia todos los eventos de la vista"""
        # Limpiar todos los eventos de la vista
        for hour in range(24):
            # El frame de la hora está en la columna 1
            hour_frame = self.hours_layout.itemAtPosition(hour, 1).widget()
            if hour_frame:
                # Eliminar todos los widgets dentro del layout del frame
                layout = hour_frame.layout()
                if layout:
                    while layout.count():
                        item = layout.takeAt(0)
                        widget = item.widget()
                        if widget:
                            widget.deleteLater()
        
    def add_event(self, event):
        """Añade un evento a la vista diaria"""
        vevent = event.vobject_instance.vevent
        
        if not hasattr(vevent, 'dtstart') or not hasattr(vevent, 'dtend'):
            return
            
        start = vevent.dtstart.value
        end = vevent.dtend.value
        
        # Verificar que el evento ocurre en la fecha actual
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            return
            
        if start.date() != self.current_date and end.date() != self.current_date:
            return
            
        # Crear widget del evento
        event_widget = CalendarEvent(event)
        event_widget.clicked.connect(lambda evt: self.parent().edit_event(evt))
        
        # Añadir el evento a la hora correspondiente
        hour = start.hour
        if 0 <= hour < 24:
            hour_frame = self.hours_layout.itemAtPosition(hour, 1).widget()
            if hour_frame:
                hour_frame.layout().addWidget(event_widget)


