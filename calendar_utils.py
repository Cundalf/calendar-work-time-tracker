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
    
    # Primero, manejar casos especiales
    if event_type == 'outOfOffice':
        return ooo_service
    
    # Verificar si es un evento de Focus Time (sin distinguir mayúsculas/minúsculas)
    summary = event.get('summary', '')
    if summary.lower().startswith('focus time'):
        return focus_time_service
    
    # Asignar por color si está habilitado y existe el color
    if use_color_tags and color_id and color_id in color_id_to_service:
        return color_id_to_service[color_id]
    
    # Verificar si el evento tiene resumen
    if not summary.strip():
        return unlabeled_service
    
    # Verificar si debemos agrupar eventos sin etiqueta específica
    if group_unlabeled:
        # Aquí puedes implementar lógica para determinar si un evento
        # debe ser agrupado como "sin etiqueta" o usar el resumen
        # Por ejemplo, puedes buscar ciertos patrones en el resumen
        return default_service
    
    # Por defecto, usar el resumen del evento como nombre del servicio
    return summary 