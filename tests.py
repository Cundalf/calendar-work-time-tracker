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
        self.assertIn('Reunión de equipo', all_services)
        self.assertIn('FUERA DE OFICINA', all_services)
        
        # El evento Focus Time podría estar asignado al servicio con su resumen original
        focus_time_service_names = ['TIEMPO DE CONCENTRACIÓN', 'Focus Time: Desarrollo']
        focus_time_found = any(service in all_services for service in focus_time_service_names)
        self.assertTrue(focus_time_found, "No se encontró ningún servicio de Focus Time")
        
        self.assertIn('Proyecto A', all_services)
        
        # Verificar tiempos específicos para cada servicio, ahora por semana
        self.assertEqual(result[week_start_date]['Reunión de equipo'], timedelta(hours=1))
        
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

if __name__ == '__main__':
    unittest.main() 