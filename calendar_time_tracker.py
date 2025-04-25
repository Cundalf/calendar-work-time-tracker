# Standard library imports
import datetime
import os.path
import pickle
from collections import defaultdict
import base64
import json

# Third-party imports
import pytz
from dateutil.relativedelta import relativedelta, MO
import os

# Importar tzlocal si está disponible
try:
    import tzlocal
    TZLOCAL_AVAILABLE = True
except ImportError:
    TZLOCAL_AVAILABLE = False

# --- Google API Libraries ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Google Calendar API Scopes
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Variable global para almacenar el flujo de autenticación en curso
_current_flow = None

# Función para limpiar variables de entorno con comentarios
def clean_env_value(value):
    if value and isinstance(value, str):
        # Si hay un # que no está al inicio, considerarlo como inicio de comentario
        if '#' in value and not value.startswith('#'):
            return value.split('#')[0].strip()
    return value

# --- FUNCIONES PRINCIPALES ---

def get_oauth_flow(force_new=False):
    """Obtener o crear el flujo OAuth para autenticación web"""
    global _current_flow
    
    if _current_flow is None or force_new:
        # Comprobar si existen variables de entorno para las credenciales
        client_id = clean_env_value(os.environ.get('GOOGLE_CLIENT_ID'))
        client_secret = clean_env_value(os.environ.get('GOOGLE_CLIENT_SECRET'))
        redirect_uri = clean_env_value(os.environ.get('GOOGLE_REDIRECT_URI'))
        
        if client_id and client_secret:
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": [redirect_uri or "http://localhost:5000/oauth2callback"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            _current_flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            # Configurar la URL de redirección correcta
            _current_flow.redirect_uri = redirect_uri or "http://localhost:5000/oauth2callback"
        elif os.path.exists('credentials.json'):
            _current_flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        else:
            return None
    
    return _current_flow

def get_authorization_url():
    """Generar URL para autorización de OAuth"""
    flow = get_oauth_flow()
    if not flow:
        return None
        
    # Configurar la solicitud de autorización para obtener refresh token
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )
    
    return auth_url

def complete_oauth_flow(code):
    """Completar el flujo OAuth con el código de autorización y devolver las credenciales"""
    flow = get_oauth_flow()
    if not flow:
        return None
    
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Ya no guardamos en archivo, devolvemos las credenciales para guardar en sesión
        return creds
    except Exception as e:
        print(f"Error al completar flujo OAuth: {e}")
        return None

def credentials_to_dict(credentials):
    """Convertir objeto Credentials a diccionario para almacenar en sesión"""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def dict_to_credentials(credentials_dict):
    """Convertir diccionario de sesión a objeto Credentials"""
    if not credentials_dict:
        return None
    
    try:
        return Credentials(
            token=credentials_dict['token'],
            refresh_token=credentials_dict['refresh_token'],
            token_uri=credentials_dict['token_uri'],
            client_id=credentials_dict['client_id'],
            client_secret=credentials_dict['client_secret'],
            scopes=credentials_dict['scopes']
        )
    except Exception as e:
        print(f"Error al convertir diccionario a credenciales: {e}")
        return None

def authenticate_google_calendar(credentials_dict=None):
    """
    Autenticar con Google Calendar API y devolver servicio
    
    Args:
        credentials_dict: Diccionario con las credenciales almacenadas en sesión
        
    Returns:
        Servicio de Google Calendar o None si no hay credenciales válidas
    """
    creds = dict_to_credentials(credentials_dict)
    
    # Si hay credenciales y están expiradas, intentar renovarlas
    if creds and creds.expired and creds.refresh_token:
        try: 
            creds.refresh(Request())
            # Devolver las credenciales actualizadas y el servicio
            return build('calendar', 'v3', credentials=creds), credentials_to_dict(creds)
        except Exception as e:
            print(f"Error al refrescar token: {e}")
            creds = None
    
    # Construir y devolver el servicio si hay credenciales válidas
    if creds and creds.valid:
        try:
            return build('calendar', 'v3', credentials=creds), credentials_to_dict(creds)
        except Exception as e:
            print(f"Error al construir servicio: {e}")
    
    # Si no hay credenciales válidas, se necesita autorización
    return None, None

def get_calendar_timezone(service):
    """Obtener zona horaria del calendario del usuario"""
    try:
        settings = service.settings().get(setting='timezone').execute()
        return pytz.timezone(settings['value'])
    except Exception as e:
        print(f"Error al obtener zona horaria del calendario: {e}")
        # Fallback a zona horaria local o UTC
        if TZLOCAL_AVAILABLE:
            try:
                local_tz_name = tzlocal.get_localzone_name()
                return pytz.timezone(local_tz_name)
            except Exception as e:
                print(f"Error al obtener zona horaria local: {e}")
                pass
        return pytz.utc

def get_events(service, start_date, end_date, timezone):
    """Obtener eventos del calendario en el rango de fechas especificado"""
    try:
        time_min = timezone.localize(datetime.datetime.combine(start_date, datetime.time.min)).isoformat()
        time_max = timezone.localize(datetime.datetime.combine(end_date + datetime.timedelta(days=1), datetime.time.min)).isoformat()
    except Exception as e:
        print(f"Error con fechas: {e}")
        return None
        
    all_events = []
    page_token = None
    
    while True:
        try:
            events_result = service.events().list(
                calendarId='primary', timeMin=time_min, timeMax=time_max,
                singleEvents=True, orderBy='startTime', pageToken=page_token,
                maxResults=2500
            ).execute()
            events = events_result.get('items', [])
            all_events.extend(events)
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break
        except Exception as e:
            print(f'Error obteniendo eventos: {e}')
            return None
            
    return all_events

def parse_datetime_api(dt_obj):
    """Parsear objeto datetime de la API de Google Calendar"""
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

def assign_service(event, config):
    """Asignar servicio a un evento según la configuración"""
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
    if event_type == 'outOfOffice' and ooo_service: 
        return ooo_service
    if event_type == 'focusTime' and focus_time_service: 
        return focus_time_service
    
    # Luego, verificar etiquetas de color si están habilitadas
    if use_color_tags and color_id and color_id in color_id_to_service:
        return color_id_to_service[color_id]
    
    # Finalmente, para eventos sin etiqueta configurada o sin color
    if use_color_tags and group_unlabeled and color_id:
        # Si tiene color pero no está en la configuración
        return unlabeled_service
    
    # Eventos sin color o para casos restantes
    return default_service

def format_timedelta(td):
    """Formatear un timedelta en formato 'X.Xh'"""
    if not isinstance(td, datetime.timedelta):
        return "0.0h"
        
    total_seconds = max(0, td.total_seconds())  # Asegurar que no sea negativo
    hours = total_seconds / 3600
    return f"{hours:.1f}h"

def calculate_weekly_summary(events, start_date, end_date, timezone, work_start_time, work_end_time, work_days, config=None):
    """Calcular resumen semanal de tiempo por servicio"""
    # Verificar que la configuración no sea None
    if config is None:
        config = {}
    
    # Configuración de lunch
    lunch_duration = config.get('lunch_duration_minutes', 60)
    try:
        lunch_duration = int(lunch_duration)
    except (ValueError, TypeError):
        lunch_duration = 60
    
    weekly_totals = defaultdict(lambda: defaultdict(datetime.timedelta))
    current_date = start_date
    lunch_delta = datetime.timedelta(minutes=lunch_duration)

    # Preparar eventos
    parsed_events = []
    for event in events:
        start_dt_api, start_is_all_day = parse_datetime_api(event.get('start'))
        end_dt_api, end_is_all_day = parse_datetime_api(event.get('end'))
        if not start_dt_api or not end_dt_api:
            continue
            
        try:
            start_dt = start_dt_api.astimezone(timezone)
            end_dt = end_dt_api.astimezone(timezone)
        except Exception as e:
            print(f"Error al convertir zona horaria: {e}, evento: {event.get('summary', 'Sin título')}")
            continue
            
        if start_is_all_day and end_dt.time() == datetime.time.min and end_dt.date() > start_dt.date():
            end_dt = end_dt - datetime.timedelta(seconds=1)

        parsed_events.append({
            'summary': event.get('summary', 'N/A'),
            'start': start_dt,
            'end': end_dt,
            'is_all_day': start_is_all_day,
            'service': assign_service(event, config)
        })

    # Bucle por semanas
    while current_date <= end_date:
        week_start = current_date + relativedelta(weekday=MO(-1))
        week_end = week_start + datetime.timedelta(days=6)
        actual_week_start_day = max(week_start, start_date)
        actual_week_end_day = min(week_end, end_date)
        total_potential_work_time_week = datetime.timedelta()
        total_booked_time_week = datetime.timedelta()

        # Bucle por días de la semana
        temp_date = actual_week_start_day
        while temp_date <= actual_week_end_day:
            # Calcular horas laborales del día
            daily_work_start_dt, daily_work_end_dt = None, None
            is_work_day = temp_date.weekday() in work_days
            
            if is_work_day:
                try:
                    daily_work_start_dt = timezone.localize(datetime.datetime.combine(temp_date, work_start_time))
                    daily_work_end_dt = timezone.localize(datetime.datetime.combine(temp_date, work_end_time))
                    daily_potential_time = (daily_work_end_dt - daily_work_start_dt) - lunch_delta
                    if daily_potential_time < datetime.timedelta(0):
                        daily_potential_time = datetime.timedelta(0)
                    total_potential_work_time_week += daily_potential_time
                except Exception as e:
                    print(f"Error al calcular horas laborales del día {temp_date}: {e}")
                    is_work_day = False

            # Procesar eventos que solapan con el día
            for event_data in parsed_events:
                start_dt, end_dt = event_data['start'], event_data['end']
                service, is_all_day = event_data['service'], event_data['is_all_day']

                # Valores desde la configuración
                ooo_service = config.get('ooo_service', '')

                if start_dt.date() <= temp_date <= end_dt.date():
                    if is_all_day:
                        if service == ooo_service and is_work_day and daily_work_start_dt and daily_work_end_dt:
                            duration = daily_work_end_dt - daily_work_start_dt
                            weekly_totals[week_start][service] += duration
                            total_booked_time_week += duration
                        continue  # Ignorar otros all-day

                    if not is_work_day:
                        continue  # Ignorar eventos con hora en días no laborables

                    if not daily_work_start_dt or not daily_work_end_dt:
                        continue

                    overlap_start = max(start_dt, daily_work_start_dt)
                    overlap_end = min(end_dt, daily_work_end_dt)
                    duration = datetime.timedelta(0)
                    if overlap_end > overlap_start:
                        duration = overlap_end - overlap_start

                    if duration > datetime.timedelta(seconds=1):
                        weekly_totals[week_start][service] += duration
                        total_booked_time_week += duration

            temp_date += datetime.timedelta(days=1)

        # Tiempo libre para esta semana
        free_time_week = total_potential_work_time_week - total_booked_time_week
        if free_time_week < datetime.timedelta(0):
            free_time_week = datetime.timedelta(0)
        
        # Asignar tiempo libre al servicio predeterminado
        default_service = config.get('default_service', '')
        if free_time_week > datetime.timedelta(seconds=1) and default_service:
            weekly_totals[week_start][default_service] += free_time_week

        current_date = week_end + datetime.timedelta(days=1)

    return weekly_totals