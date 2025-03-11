import random
import pandas as pd
from datetime import datetime, timedelta
import openpyxl

class GeneradorTurnos:
    def __init__(self, fecha_inicio, semanas=4):
        self.fecha_inicio = fecha_inicio
        self.semanas = semanas
        
        # Definir trabajadores: farmacéuticos y técnicos
        self.farmaceuticos = ["Farm1", "Farm2"]
        self.tecnicos = ["Tec1", "Tec2", "Tec3", "Tec4", "Tec5", "Tec6"]
        self.todos_trabajadores = self.farmaceuticos + self.tecnicos
        
        # Para seguimiento de horas trabajadas
        self.horas_semanales = {trabajador: 0 for trabajador in self.todos_trabajadores}
        
        # Para seguimiento de turnos consecutivos
        self.ultimo_turno = {trabajador: None for trabajador in self.todos_trabajadores}
        
        # Crear el calendario vacío
        self.crear_calendario_vacio()
    
    def crear_calendario_vacio(self):
        """Crear un DataFrame vacío para el calendario."""
        fecha_fin = self.fecha_inicio + timedelta(days=7*self.semanas-1)
        fechas = pd.date_range(start=self.fecha_inicio, end=fecha_fin)
        
        # Crear DataFrame con fechas como índice
        self.calendario = pd.DataFrame(index=fechas, columns=["Dia", "Mañana", "Tarde"])
        self.calendario["Dia"] = self.calendario.index.day_name()
    
    def asignar_turnos_semana(self, fecha_inicio_semana):
        """Asignar turnos para una semana completa."""
        # Resetear horas trabajadas para la semana
        self.horas_semanales = {trabajador: 0 for trabajador in self.todos_trabajadores}
        
        # Iterar por cada día de la semana
        for i in range(7):
            fecha = fecha_inicio_semana + timedelta(days=i)
            # Corregido: Usar weekday() en lugar de day_name()
            dia_semana = fecha.weekday()
            
            # Determinar el número de trabajadores necesarios según el día
            # 5 = sábado, 6 = domingo
            if dia_semana in [5, 6]:
                trabajadores_por_turno = 2
                horas_turno = 6
            else:
                trabajadores_por_turno = 4
                horas_turno = 6
            
            # Asignar turno de mañana (priorizando farmacéuticos)
            disponibles_manana = [t for t in self.todos_trabajadores 
                                if self.horas_semanales[t] + horas_turno <= 38]
            
            # Intentar asignar farmacéuticos primero en la mañana
            asignados_manana = []
            for farm in self.farmaceuticos:
                if farm in disponibles_manana and self.ultimo_turno[farm] != "Tarde":
                    asignados_manana.append(farm)
                    if len(asignados_manana) >= trabajadores_por_turno:
                        break
            
            # Completar con técnicos si es necesario
            disponibles_manana = [t for t in disponibles_manana 
                                if t not in asignados_manana and self.ultimo_turno[t] != "Tarde"]
            random.shuffle(disponibles_manana)
            
            while len(asignados_manana) < trabajadores_por_turno and disponibles_manana:
                asignados_manana.append(disponibles_manana.pop())
            
            # Actualizar horas y último turno
            for trabajador in asignados_manana:
                self.horas_semanales[trabajador] += horas_turno
                self.ultimo_turno[trabajador] = "Mañana"
            
            # Asignar turno de tarde (evitando asignar farmacéuticos si es posible)
            disponibles_tarde = [t for t in self.todos_trabajadores 
                               if t not in asignados_manana and
                               self.horas_semanales[t] + horas_turno <= 38 and
                               self.ultimo_turno[t] != "Mañana"]
            
            # Priorizar técnicos para la tarde
            tecnicos_tarde = [t for t in disponibles_tarde if t in self.tecnicos]
            random.shuffle(tecnicos_tarde)
            
            asignados_tarde = tecnicos_tarde[:trabajadores_por_turno]
            
            # Si no hay suficientes técnicos, añadir farmacéuticos
            if len(asignados_tarde) < trabajadores_por_turno:
                farms_tarde = [t for t in disponibles_tarde if t in self.farmaceuticos]
                random.shuffle(farms_tarde)
                while len(asignados_tarde) < trabajadores_por_turno and farms_tarde:
                    asignados_tarde.append(farms_tarde.pop())
            
            # Actualizar horas y último turno
            for trabajador in asignados_tarde:
                self.horas_semanales[trabajador] += horas_turno
                self.ultimo_turno[trabajador] = "Tarde"
            
            # Guardar en el calendario
            fecha_pd = pd.Timestamp(fecha)  # Convertir a timestamp de pandas para usarlo como índice
            self.calendario.loc[fecha_pd, "Mañana"] = ", ".join(asignados_manana) if asignados_manana else "Sin asignar"
            self.calendario.loc[fecha_pd, "Tarde"] = ", ".join(asignados_tarde) if asignados_tarde else "Sin asignar"
    
    def generar_calendario_completo(self):
        """Generar el calendario para todas las semanas."""
        for semana in range(self.semanas):
            fecha_inicio_semana = self.fecha_inicio + timedelta(days=7*semana)
            self.asignar_turnos_semana(fecha_inicio_semana)
        
        return self.calendario
    
    def obtener_horas_totales(self):
        """Calcular el total de horas trabajadas por cada empleado."""
        horas_totales = {trabajador: 0 for trabajador in self.todos_trabajadores}
        
        for _, row in self.calendario.iterrows():
            # Contar horas para turno de mañana
            trabajadores_manana = row["Mañana"].split(", ") if isinstance(row["Mañana"], str) else []
            for trabajador in trabajadores_manana:
                if trabajador in horas_totales:
                    horas_totales[trabajador] += 6
            
            # Contar horas para turno de tarde
            trabajadores_tarde = row["Tarde"].split(", ") if isinstance(row["Tarde"], str) else []
            for trabajador in trabajadores_tarde:
                if trabajador in horas_totales:
                    horas_totales[trabajador] += 6
        
        return horas_totales
    
    def mostrar_resumen(self):
        """Mostrar resumen de turnos y horas trabajadas."""
        horas_totales = self.obtener_horas_totales()
        
        print("\n=== RESUMEN DE HORAS TRABAJADAS ===")
        print("Farmacéuticos:")
        for farm in self.farmaceuticos:
            print(f"  - {farm}: {horas_totales[farm]} horas")
        
        print("\nTécnicos:")
        for tec in self.tecnicos:
            print(f"  - {tec}: {horas_totales[tec]} horas")
        
        # Calcular promedios
        promedio_farm = sum(horas_totales[f] for f in self.farmaceuticos) / len(self.farmaceuticos)
        promedio_tec = sum(horas_totales[t] for t in self.tecnicos) / len(self.tecnicos)
        
        print(f"\nPromedio horas farmacéuticos: {promedio_farm:.2f}")
        print(f"Promedio horas técnicos: {promedio_tec:.2f}")

# Ejemplo de uso
if __name__ == "__main__":
    # Definir fecha de inicio (primer lunes)
    fecha_inicio = datetime.now()
    # Ajustar a lunes
    while fecha_inicio.weekday() != 0:  # 0 es lunes
        fecha_inicio += timedelta(days=1)
    
    # Crear generador para 4 semanas
    generador = GeneradorTurnos(fecha_inicio, semanas=4)
    
    # Generar el calendario
    calendario = generador.generar_calendario_completo()
    
    # Mostrar el calendario
    print("=== CALENDARIO DE TURNOS ===")
    # Formatear el índice para mostrarlo más legible
    calendario_formateado = calendario.copy()
    calendario_formateado.index = calendario_formateado.index.strftime('%d-%m-%Y')
    print(calendario_formateado)
    
    # Mostrar resumen de horas
    generador.mostrar_resumen()
    
    # Exportar a Excel si es necesario
    calendario.to_excel("calendario_turnos.xlsx")
    print("\nCalendario exportado a 'calendario_turnos.xlsx'")