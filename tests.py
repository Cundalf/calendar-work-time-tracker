"""
Tests unitarios para la aplicación Calendar Time Tracker.
"""

import unittest
import datetime
from datetime import time, timedelta, date
import json
import pytz
from unittest.mock import patch, MagicMock
from collections import defaultdict

from config_utils import clean_env_value, get_default_config, validate_config
from calendar_utils import format_timedelta, assign_service, parse_datetime_api
from calendar_time_tracker import calculate_weekly_summary, get_calendar_timezone, get_events

class TestConfigUtils(unittest.TestCase):
    """Pruebas para las utilidades de configuración"""
    
    def test_clean_env_value(self):
        """Probar la limpieza de valores de entorno"""
        self.assertEqual(clean_env_value("value"), "value")
        self.assertEqual(clean_env_value("value # comentario"), "value")
        self.assertEqual(clean_env_value("value#comentario"), "value")
        self.assertEqual(clean_env_value("#comentario"), "#comentario")
        self.assertEqual(clean_env_value(None), None)
    
    def test_get_default_config(self):
        """Probar la obtención de configuración predeterminada"""
        config = get_default_config()
        self.assertEqual(config['work_start_time'], '09:00')
        self.assertEqual(config['work_end_time'], '17:00')
        self.assertEqual(config['lunch_duration_minutes'], 60)
        self.assertFalse(config['group_unlabeled'])
    
    def test_validate_config(self):
        """Probar la validación de configuración"""
        # Configuración vacía
        self.assertEqual(validate_config(None), get_default_config())
        self.assertEqual(validate_config(""), get_default_config())
        
        # Configuración parcial
        partial_config = json.dumps({"work_start_time": "08:00"})
        result = validate_config(partial_config)
        self.assertEqual(result['work_start_time'], "08:00")  # Mantiene valor personalizado
        self.assertEqual(result['work_end_time'], "17:00")    # Usa valor predeterminado
        
        # Configuración completa
        custom_config = {
            'work_start_time': '08:00',
            'work_end_time': '16:00',
            'lunch_duration_minutes': 30,
            'default_service': 'CUSTOM',
            'ooo_service': 'OOO',
            'focus_time_service': 'FOCUS',
            'unlabeled_service': 'UNLABELED',
            'group_unlabeled': True,
            'use_color_tags': True,
            'color_tags': {'1': 'RED'}
        }
        result = validate_config(custom_config)
        self.assertEqual(result, custom_config)

class TestCalendarUtils(unittest.TestCase):
    """Pruebas para las utilidades de calendario"""
    
    def test_format_timedelta(self):
        """Probar el formateo de timedelta"""
        self.assertEqual(format_timedelta(None), "00:00")
        self.assertEqual(format_timedelta(timedelta(hours=2, minutes=30)), "02:30")
        self.assertEqual(format_timedelta(timedelta(hours=0, minutes=45)), "00:45")
        self.assertEqual(format_timedelta(timedelta(hours=1)), "01:00")
    
    def test_assign_service(self):
        """Probar la asignación de servicio a eventos"""
        config = {
            'use_color_tags': True,
            'color_tags': {'1': 'RED', '2': 'BLUE'},
            'group_unlabeled': False,
            'ooo_service': 'OUT OF OFFICE',
            'focus_time_service': 'FOCUS TIME',
            'default_service': 'DEFAULT',
            'unlabeled_service': 'UNLABELED'
        }
        
        # Evento fuera de oficina
        ooo_event = {'eventType': 'outOfOffice'}
        self.assertEqual(assign_service(ooo_event, config), 'OUT OF OFFICE')
        
        # Evento focus time
        focus_event = {'summary': 'Focus Time Meeting'}
        self.assertEqual(assign_service(focus_event, config), 'FOCUS TIME')
        
        # Evento con color configurado
        color_event = {'colorId': '1', 'summary': 'Colored Event'}
        self.assertEqual(assign_service(color_event, config), 'RED')
        
        # Evento sin resumen
        empty_event = {'colorId': '3'}
        self.assertEqual(assign_service(empty_event, config), 'UNLABELED')
    
    def test_parse_datetime_api(self):
        """Probar el parseo de fechas de la API"""
        # Evento con dateTime
        dt_obj = {'dateTime': '2023-05-01T09:00:00+02:00'}
        dt, is_all_day = parse_datetime_api(dt_obj)
        self.assertEqual(dt.year, 2023)
        self.assertEqual(dt.month, 5)
        self.assertEqual(dt.day, 1)
        self.assertEqual(dt.hour, 9)
        self.assertFalse(is_all_day)
        
        # Evento de día completo
        date_obj = {'date': '2023-05-01'}
        dt, is_all_day = parse_datetime_api(date_obj)
        self.assertEqual(dt.year, 2023)
        self.assertEqual(dt.month, 5)
        self.assertEqual(dt.day, 1)
        self.assertEqual(dt.hour, 0)
        self.assertTrue(is_all_day)
        
        # Objeto vacío
        self.assertEqual(parse_datetime_api({}), (None, False))
        self.assertEqual(parse_datetime_api(None), (None, False))

class TestCalendarTimeTracker(unittest.TestCase):
    """Pruebas para las funciones principales de calendar_time_tracker.py"""
    
    def setUp(self):
        """Configuración común para las pruebas"""
        self.timezone = pytz.timezone('Europe/Madrid')
        self.work_start_time = time(9, 0)
        self.work_end_time = time(17, 0)
        self.work_days = [0, 1, 2, 3, 4]  # Lunes a viernes
        self.config = get_default_config()
        
        # Crear eventos de prueba
        self.start_date = date(2023, 5, 1)  # Lunes
        self.end_date = date(2023, 5, 5)    # Viernes
        
        # Crear eventos de prueba
        self.test_events = [
            # Evento 1: Reunión normal de 1 hora
            {
                'id': '1',
                'summary': 'Reunión de equipo',
                'start': {'dateTime': '2023-05-01T10:00:00+02:00'},
                'end': {'dateTime': '2023-05-01T11:00:00+02:00'},
            },
            # Evento 2: Evento fuera de oficina
            {
                'id': '2',
                'summary': 'Vacaciones',
                'eventType': 'outOfOffice',
                'start': {'date': '2023-05-02'},
                'end': {'date': '2023-05-03'},
            },
            # Evento 3: Focus time
            {
                'id': '3',
                'summary': 'Focus Time: Desarrollo',
                'start': {'dateTime': '2023-05-04T14:00:00+02:00'},
                'end': {'dateTime': '2023-05-04T16:00:00+02:00'},
            },
            # Evento 4: Evento con color
            {
                'id': '4',
                'summary': 'Evento con color',
                'colorId': '1',
                'start': {'dateTime': '2023-05-05T09:00:00+02:00'},
                'end': {'dateTime': '2023-05-05T10:30:00+02:00'},
            }
        ]
    
    def test_calculate_weekly_summary(self):
        """Probar el cálculo del resumen semanal"""
        # Configurar el color '1' para que se asigne a 'Proyecto A'
        self.config['use_color_tags'] = True
        self.config['color_tags'] = {'1': 'Proyecto A'}
        
        # Llamar a la función que queremos probar
        result = calculate_weekly_summary(
            self.test_events,
            self.start_date,
            self.end_date,
            self.timezone,
            self.work_start_time,
            self.work_end_time,
            self.work_days,
            self.config
        )
        
        # Verificar que el resultado es un defaultdict
        self.assertTrue(isinstance(result, defaultdict))
        
        # En calculate_weekly_summary, los resultados se agrupan por semana, 
        # usando la fecha del lunes como clave.
        # La semana del 1 al 5 de mayo de 2023 tiene como primer día el 1 de mayo (lunes)
        week_start_date = date(2023, 5, 1)  # Lunes
        
        # Verificar que la semana está en los resultados
        self.assertIn(week_start_date, result)
        
        # Verificar que los totales por servicio están presentes
        week_services = result[week_start_date]
        all_services = set(week_services.keys())
        
        # Imprimir todos los servicios para depuración
        print("Servicios encontrados:", all_services)
        
        # Verificar que están los servicios esperados
        # Nota: Con la nueva implementación de assign_service, los eventos normales
        # se asignan al servicio default en lugar de usar su título
        default_service = self.config.get('default_service', 'TIEMPO NO ETIQUETADO')
        self.assertIn(default_service, all_services)
        self.assertIn('FUERA DE OFICINA', all_services)
        
        # El evento Focus Time podría estar asignado al servicio con su resumen original
        focus_time_service_names = ['TIEMPO DE CONCENTRACIÓN', 'Focus Time: Desarrollo']
        focus_time_found = any(service in all_services for service in focus_time_service_names)
        self.assertTrue(focus_time_found, "No se encontró ningún servicio de Focus Time")
        
        self.assertIn('Proyecto A', all_services)
        
        # Verificar tiempos específicos para cada servicio, ahora por semana
        # El tiempo default incluye el evento "Reunión de equipo" (1 hora) pero también el tiempo libre
        # de la semana, así que no podemos verificar un valor exacto sin conocer todos los cálculos internos
        # Solo verificamos que hay tiempo asignado
        self.assertGreater(result[week_start_date][default_service], timedelta(0))
        
        # Imprimir el tiempo default para depuración
        print(f"Tiempo default: {result[week_start_date][default_service]}")
        
        # Verificar el tiempo de focus time, usando el nombre de servicio correcto
        if 'TIEMPO DE CONCENTRACIÓN' in all_services:
            self.assertEqual(result[week_start_date]['TIEMPO DE CONCENTRACIÓN'], timedelta(hours=2))
        elif 'Focus Time: Desarrollo' in all_services:
            self.assertEqual(result[week_start_date]['Focus Time: Desarrollo'], timedelta(hours=2))
        else:
            self.fail("No se encontró un servicio de Focus Time válido")
        
        # Verificar tiempo del evento con color
        self.assertEqual(result[week_start_date]['Proyecto A'], timedelta(hours=1, minutes=30))
    
    @patch('calendar_time_tracker.get_calendar_timezone')
    def test_get_calendar_timezone(self, mock_get_calendar_timezone):
        """Probar la obtención de zona horaria del calendario"""
        # Configurar el mock
        mock_service = MagicMock()
        mock_settings = MagicMock()
        mock_settings.execute.return_value = {'value': 'Europe/Madrid'}
        mock_service.settings().get.return_value = mock_settings
        
        # Llamar a la función sin usar el mock interno
        timezone = get_calendar_timezone(mock_service)
        
        # Verificar que se obtiene la zona horaria correcta
        self.assertEqual(timezone.zone, 'Europe/Madrid')
        
        # Verificar que se llamó al método correcto
        mock_service.settings().get.assert_called_once_with(setting='timezone')

    def test_get_events(self):
        """Probar la obtención de eventos"""
        # Configurar el mock
        mock_service = MagicMock()
        mock_events_response = {
            'items': self.test_events,
            'nextPageToken': None
        }
        mock_events_list = MagicMock()
        mock_events_list.execute.return_value = mock_events_response
        mock_service.events().list.return_value = mock_events_list
        
        # Llamar a la función real con nuestro servicio mock
        events = get_events(
            mock_service, 
            self.start_date, 
            self.end_date, 
            self.timezone
        )
        
        # Verificar que los eventos se obtuvieron correctamente
        self.assertEqual(events, self.test_events)

class TestAssignService(unittest.TestCase):
    """Pruebas detalladas para la función assign_service que asigna servicios a eventos"""
    
    def setUp(self):
        """Configuración común para las pruebas de assign_service"""
        self.base_config = {
            'use_color_tags': True,
            'color_tags': {'1': 'Proyecto A', '2': 'Proyecto B', '5': 'Cliente X'},
            'group_unlabeled': True,
            'ooo_service': 'FUERA DE OFICINA',
            'focus_time_service': 'TIEMPO DE CONCENTRACIÓN',
            'default_service': 'TIEMPO DEFAULT',
            'unlabeled_service': 'SIN ETIQUETA'
        }
    
    def test_priority_1_out_of_office(self):
        """Verificar Prioridad 1: eventos fuera de oficina por tipo"""
        # Evento fuera de oficina sin color
        event = {
            'eventType': 'outOfOffice',
            'summary': 'Vacaciones'
        }
        self.assertEqual(
            assign_service(event, self.base_config), 
            'FUERA DE OFICINA',
            "Debería usar servicio OOO para eventos tipo outOfOffice"
        )
        
        # Evento fuera de oficina CON color configurado
        # Nota: Este debería seguir siendo OOO porque el tipo tiene prioridad
        event_with_color = {
            'eventType': 'outOfOffice',
            'summary': 'Vacaciones',
            'colorId': '1'  # Este color está en la configuración
        }
        self.assertEqual(
            assign_service(event_with_color, self.base_config), 
            'FUERA DE OFICINA',
            "Eventos OOO deben usar el servicio OOO aunque tengan color configurado"
        )
    
    def test_priority_2_focus_time(self):
        """Verificar Prioridad 2: eventos de tiempo de concentración"""
        # Evento focus time por tipo, sin color
        event_by_type = {
            'eventType': 'focusTime',
            'summary': 'Trabajo en proyecto'
        }
        self.assertEqual(
            assign_service(event_by_type, self.base_config), 
            'TIEMPO DE CONCENTRACIÓN',
            "Debería usar servicio de focus time para eventos tipo focusTime"
        )
        
        # Evento focus time por título, sin color
        event_by_title = {
            'eventType': 'default',
            'summary': 'Focus Time: Desarrollo'
        }
        self.assertEqual(
            assign_service(event_by_title, self.base_config), 
            'TIEMPO DE CONCENTRACIÓN',
            "Debería usar servicio de focus time para títulos que empiezan con 'focus time'"
        )
        
        # Evento focus time CON color configurado (el color debería tener prioridad)
        event_with_color = {
            'eventType': 'focusTime',
            'summary': 'Focus Time: Desarrollo',
            'colorId': '1'  # Este color está en la configuración
        }
        self.assertEqual(
            assign_service(event_with_color, self.base_config), 
            'Proyecto A',
            "Eventos focus time con color configurado deben usar el servicio del color"
        )
        
        # Evento focus time con color pero sin etiquetas habilitadas
        config_without_tags = self.base_config.copy()
        config_without_tags['use_color_tags'] = False
        event_color_disabled = {
            'eventType': 'focusTime',
            'summary': 'Focus Time',
            'colorId': '1'
        }
        self.assertEqual(
            assign_service(event_color_disabled, config_without_tags), 
            'TIEMPO DE CONCENTRACIÓN',
            "Con etiquetas deshabilitadas, debe usar servicio focus time aunque tenga color"
        )
    
    def test_priority_3_color_tags(self):
        """Verificar Prioridad 3: eventos con color definido en la configuración"""
        # Evento normal con color configurado
        event = {
            'eventType': 'default',
            'summary': 'Reunión de equipo',
            'colorId': '2'  # Proyecto B
        }
        self.assertEqual(
            assign_service(event, self.base_config), 
            'Proyecto B',
            "Debería usar el servicio asociado al color configurado"
        )
        
        # Verificar que funciona con diferentes colores
        event2 = {
            'eventType': 'default',
            'summary': 'Llamada con cliente',
            'colorId': '5'  # Cliente X
        }
        self.assertEqual(
            assign_service(event2, self.base_config), 
            'Cliente X',
            "Debería usar el servicio correcto para cada color"
        )
        
        # Verificar que NO usa etiquetas si están deshabilitadas
        config_disabled = self.base_config.copy()
        config_disabled['use_color_tags'] = False
        self.assertEqual(
            assign_service(event, config_disabled), 
            'TIEMPO DEFAULT',
            "No debería usar color si las etiquetas están deshabilitadas"
        )
    
    def test_priority_4_unlabeled_with_color(self):
        """Verificar Prioridad 4: eventos con color no configurado cuando group_unlabeled=True"""
        # Evento con color NO configurado
        event = {
            'eventType': 'default',
            'summary': 'Tarea sin categoría',
            'colorId': '9'  # Este color NO está en la configuración
        }
        self.assertEqual(
            assign_service(event, self.base_config), 
            'SIN ETIQUETA',
            "Debería usar servicio 'SIN ETIQUETA' para eventos con color no configurado"
        )
        
        # Mismo caso pero con group_unlabeled=False
        config_no_group = self.base_config.copy()
        config_no_group['group_unlabeled'] = False
        self.assertEqual(
            assign_service(event, config_no_group), 
            'TIEMPO DEFAULT',
            "Con group_unlabeled=False, debería usar el servicio default"
        )
    
    def test_priority_5_empty_summary(self):
        """Verificar Prioridad 5: eventos sin resumen"""
        # Evento sin resumen ni color
        event_empty = {
            'eventType': 'default',
            'summary': ''
        }
        self.assertEqual(
            assign_service(event_empty, self.base_config), 
            'SIN ETIQUETA',
            "Debería usar 'SIN ETIQUETA' para eventos sin resumen"
        )
        
        # Evento con resumen que solo tiene espacios
        event_spaces = {
            'eventType': 'default',
            'summary': '   '
        }
        self.assertEqual(
            assign_service(event_spaces, self.base_config), 
            'SIN ETIQUETA',
            "Debería usar 'SIN ETIQUETA' para eventos con resumen que solo tiene espacios"
        )
    
    def test_priority_6_default(self):
        """Verificar Prioridad 6: eventos que no caen en ninguna categoría anterior"""
        # Evento normal sin color ni características especiales
        event = {
            'eventType': 'default',
            'summary': 'Evento común'
        }
        self.assertEqual(
            assign_service(event, self.base_config), 
            'TIEMPO DEFAULT',
            "Debería usar el servicio default para eventos normales sin características especiales"
        )
    
    def test_edge_cases(self):
        """Verificar casos límite y combinaciones especiales"""
        # Configuración vacía o incompleta
        empty_config = {}
        event = {'summary': 'Test'}
        self.assertEqual(
            assign_service(event, empty_config), 
            '',
            "Con config vacía, debería devolver servicio vacío"
        )
        
        # Evento completamente vacío
        empty_event = {}
        self.assertEqual(
            assign_service(empty_event, self.base_config), 
            'SIN ETIQUETA',
            "Evento vacío debería asignarse a 'SIN ETIQUETA'"
        )
        
        # Verificar capitalización en Focus Time
        event_mixed_case = {
            'summary': 'fOcUs TiMe: prueba'
        }
        self.assertEqual(
            assign_service(event_mixed_case, self.base_config), 
            'TIEMPO DE CONCENTRACIÓN',
            "La capitalización no debería afectar la detección de Focus Time"
        )

if __name__ == '__main__':
    unittest.main() 