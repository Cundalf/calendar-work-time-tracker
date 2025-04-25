"""
Utilidades para el manejo de eventos de Google Calendar.
Este módulo contiene funciones para procesar eventos de calendar.
"""

import datetime
import pytz
from collections import defaultdict

def parse_datetime_api(dt_obj):
    """
    Parsear objeto datetime de la API de Google Calendar
    
    Args:
        dt_obj: Objeto de fecha/hora de la API de Google
        
    Returns:
        Tuple (datetime, is_all_day)
    """
    if not dt_obj:
        return None, False
        
    is_all_day = False
    dt = None
    
    try:
        if 'dateTime' in dt_obj:
            dt_str = dt_obj['dateTime']
            dt = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        elif 'date' in dt_obj:
            dt_date = datetime.date.fromisoformat(dt_obj['date'])
            dt = pytz.utc.localize(datetime.datetime.combine(dt_date, datetime.time.min))
            is_all_day = True
        else:
            return None, False
            
        return dt, is_all_day
    except Exception as e:
        print(f"Error al parsear fecha: {e}, objeto: {dt_obj}")
        return None, False

def format_timedelta(td):
    """
    Formatear un objeto timedelta en formato legible (HH:MM)
    
    Args:
        td: Objeto timedelta
        
    Returns:
        String formateado como 'HH:MM'
    """
    if not td:
        return "00:00"
        
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return f"{hours:02d}:{minutes:02d}"

def assign_service(event, config):
    """
    Asignar servicio a un evento según la configuración
    
    Args:
        event: Evento de Google Calendar
        config: Configuración de servicios
        
    Returns:
        Nombre del servicio asignado
    """
    # Obtener valores de la configuración
    color_id_to_service = config.get('color_tags', {})
    use_color_tags = config.get('use_color_tags', False)
    group_unlabeled = config.get('group_unlabeled', False)
    ooo_service = config.get('ooo_service', '')
    focus_time_service = config.get('focus_time_service', '')
    default_service = config.get('default_service', '')
    unlabeled_service = config.get('unlabeled_service', 'SIN ETIQUETA')
    
    # Lógica de asignación de servicio
    color_id = event.get('colorId')
    event_type = event.get('eventType', 'default')
    summary = event.get('summary', '')
    
    # Tipos de eventos:
    # "birthday": Es un evento especial de todo el día con una recurrencia anual.
    # "default": Es un evento normal o no se especifica más.
    # "focusTime": Es un evento de tiempo dedicado.
    # "fromGmail": Un evento de Gmail. No se puede crear este tipo de evento.
    # "outOfOffice": Un evento fuera de la oficina.
    # "workingLocation": Es un evento de ubicación de trabajo.


    # Prioridad 1: Si es un evento fuera de oficina por tipo
    if event_type == 'outOfOffice':
        return ooo_service
    
    # Prioridad 2: Si es un evento Focus Time por tipo
    if event_type == 'focusTime' or summary.lower().startswith('focus time'):
        if not use_color_tags or not color_id:
            return focus_time_service
    
    # Prioridad 3: Si se usa etiquetas de color y el evento tiene un color definido en la configuración
    if use_color_tags and color_id and color_id in color_id_to_service:
        return color_id_to_service[color_id]
    
    # Prioridad 4: Si el evento tiene color pero no lo tenemos configurado lo agrupamos si esta habilitada la opcion
    if group_unlabeled and color_id and color_id not in color_id_to_service:
        return unlabeled_service

    # Prioridad 5: Si el evento no tiene resumen o está vacío
    if not summary.strip():
        return unlabeled_service
    
    # Prioridad 6: Servicio por defecto
    return default_service