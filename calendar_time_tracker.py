import datetime
import os.path
import pickle
import pytz
from collections import defaultdict
from dateutil.relativedelta import relativedelta, MO
import sys

# --- Google API Libraries ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Google Calendar API Scopes
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# --- FUNCIONES PRINCIPALES ---

def authenticate_google_calendar():
    """Autenticar con Google Calendar API y devolver servicio"""
    creds = None
    token_file = 'token.pickle'
    credentials_file = 'credentials.json'

    if not os.path.exists(credentials_file):
        print(f"Error: No se encontró '{credentials_file}'.")
        return None

    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            try: 
                creds = pickle.load(token)
            except Exception as e: 
                print(f"Error cargando token: {e}")
                creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try: 
                creds.refresh(Request())
            except Exception:
                creds = None
                if os.path.exists(token_file):
                    os.remove(token_file)
        
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e: 
                print(f"Error en autenticación: {e}")
                return None
                
            try:
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"Error guardando token: {e}")

    try:
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error al construir servicio: {e}")
        return None

def get_calendar_timezone(service):
    """Obtener zona horaria del calendario del usuario"""
    try:
        settings = service.settings().get(setting='timezone').execute()
        return pytz.timezone(settings['value'])
    except Exception:
        # Fallback a zona horaria local o UTC
        try:
            import tzlocal
            local_tz_name = tzlocal.get_localzone_name()
            return pytz.timezone(local_tz_name)
        except Exception:
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
    except Exception:
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
        
    total_seconds = td.total_seconds()
    if -1 < total_seconds < 0:
        total_seconds = 0
        
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
        except Exception:
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
                except Exception:
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