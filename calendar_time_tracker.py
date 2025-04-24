import datetime
import os.path
import pickle
import pytz # Para manejar zonas horarias robustamente
from collections import defaultdict
from dateutil.relativedelta import relativedelta, MO # para calcular inicios de semana

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- CONFIGURACIÓN ---
# Puedes modificar estos valores según tus necesidades

# 1. Mapeo de Etiquetas (Keywords en el título/descripción del evento) a Servicios:
#    La clave es la palabra clave a buscar (en minúsculas).
#    El valor es el nombre del servicio como quieres que aparezca en el reporte.
LABEL_TO_SERVICE = {
    'infra': 'Infraestructura',
    'personas': 'Personas',
    'pdc': 'Personas',
    'capint': 'Capacitacion Interna',
    'esfera': 'Capacitacion Interna',
    'rsg' : 'Coso'
    # Añade más mapeos aquí: 'palabraclave': 'Nombre Servicio'
}

# 2. Servicio por defecto para tiempo sin eventos o eventos sin etiqueta específica:
DEFAULT_SERVICE = 'RSG'

# 3. Categoría para reuniones sin una etiqueta específica (si quieres separarlas del default)
#    Si quieres que las reuniones sin etiqueta vayan al DEFAULT_SERVICE, pon esto a None.
MEETING_SERVICE = None # O por ejemplo: '5 - Reuniones Internas'

# 4. Palabras clave que identifican una reunión (en minúsculas) si MEETING_SERVICE está definido
MEETING_KEYWORDS = ['meet', 'reunion', 'call', 'sync']

# 5. Horario Laboral Estándar (formato HH:MM) - ¡IMPORTANTE!
#    Esto se usa para calcular el tiempo "libre" que se asigna al DEFAULT_SERVICE.
#    Asegúrate que coincida con tu configuración en Google Calendar o tu horario real.
WORK_START_TIME = datetime.time(9, 0)
WORK_END_TIME = datetime.time(18, 0)
# Días laborales (0=Lunes, 1=Martes, ..., 6=Domingo)
WORK_DAYS = [0, 1, 2, 3, 4] # Lunes a Viernes

# 6. Google Calendar API Scopes - 'readonly' es suficiente
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# --- FIN DE LA CONFIGURACIÓN ---

def authenticate_google_calendar():
    """Autentica con la API de Google Calendar usando OAuth 2.0."""
    creds = None
    # El archivo token.pickle almacena los tokens de acceso y actualización del usuario.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # Si no hay credenciales válidas disponibles, permite al usuario iniciar sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refrescando token: {e}. Eliminando token.pickle y re-autenticando.")
                os.remove('token.pickle')
                creds = None # Forzará la re-autenticación
                # Vuelve a intentar el flujo si falla la recarga
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            # Si no existe token.pickle o el refresh falló
            if not os.path.exists('credentials.json'):
                print("Error: No se encontró el archivo 'credentials.json'.")
                print("Descárgalo desde Google Cloud Console y guárdalo en el mismo directorio.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Guarda las credenciales para la próxima ejecución
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print(f'Ocurrió un error al construir el servicio: {error}')
        return None
    except Exception as e:
        print(f"Ocurrió un error inesperado durante la autenticación: {e}")
        # Podría ser útil eliminar token.pickle si hay problemas persistentes
        if os.path.exists('token.pickle'):
             print("Intentando eliminar token.pickle por si está corrupto.")
             try:
                 os.remove('token.pickle')
             except OSError as oe:
                 print(f"No se pudo eliminar token.pickle: {oe}")
        return None


def get_calendar_timezone(service):
    """Obtiene la zona horaria del calendario primario del usuario."""
    try:
        settings = service.settings().get(setting='timezone').execute()
        return pytz.timezone(settings['value'])
    except HttpError as error:
        print(f"Error obteniendo la zona horaria del calendario: {error}")
        # Usar una zona horaria por defecto o intentar deducirla podría ser una opción
        print("Usando UTC como zona horaria por defecto.")
        return pytz.utc
    except Exception as e:
        print(f"Error inesperado obteniendo timezone: {e}. Usando UTC.")
        return pytz.utc

def get_events(service, start_date, end_date, timezone):
    """Obtiene eventos del calendario primario dentro del rango de fechas."""
    # Formatea las fechas a RFC3339 y asegúrate de que son timezone-aware
    time_min = timezone.localize(datetime.datetime.combine(start_date, datetime.time.min)).isoformat()
    # Para end_date, usamos el final del día
    time_max = timezone.localize(datetime.datetime.combine(end_date, datetime.time.max)).isoformat()

    print(f"Buscando eventos desde {time_min} hasta {time_max}...")
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True, # Expande eventos recurrentes
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        print(f"Encontrados {len(events)} eventos.")
        return events
    except HttpError as error:
        print(f'Ocurrió un error al obtener eventos: {error}')
        return []
    except Exception as e:
         print(f'Ocurrió un error inesperado obteniendo eventos: {e}')
         return []

def parse_datetime(dt_str):
    """Parsea string de fecha/hora de la API, devolviendo un objeto datetime timezone-aware."""
    try:
        # Intenta parsear con formato de fecha y hora
        dt = datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt
    except ValueError:
        # Intenta parsear como solo fecha (eventos de todo el día)
        try:
            dt_date = datetime.date.fromisoformat(dt_str)
            # Asignamos medianoche UTC como referencia, marcándolo como all_day
            return pytz.utc.localize(datetime.datetime.combine(dt_date, datetime.time.min))
        except ValueError:
            print(f"Advertencia: No se pudo parsear la fecha/hora: {dt_str}")
            return None
    except Exception as e:
        print(f"Error inesperado parseando fecha {dt_str}: {e}")
        return None

def get_service_for_event(event):
    """Determina a qué servicio pertenece un evento basado en su título/descripción."""
    summary = event.get('summary', '').lower()
    description = event.get('description', '').lower()
    event_text = summary + ' ' + description

    # 1. Buscar etiquetas específicas
    for keyword, service_name in LABEL_TO_SERVICE.items():
        if keyword in event_text:
            return service_name

    # 2. Verificar si es una reunión sin etiqueta (si MEETING_SERVICE está configurado)
    if MEETING_SERVICE:
        for keyword in MEETING_KEYWORDS:
            if keyword in summary: # Buscar solo en el título para reuniones
                return MEETING_SERVICE

    # 3. Si no coincide con nada, podría ser DEFAULT o necesita otra lógica
    #    Por ahora, si no es etiqueta específica ni reunión específica,
    #    su tiempo se contará como "ocupado", y el tiempo libre irá al default.
    #    Si quieres que eventos SIN etiqueta vayan al default, devuelve DEFAULT_SERVICE aquí.
    # return DEFAULT_SERVICE
    return None # Indica que es un evento "genérico" si no se clasifica arriba

def calculate_weekly_summary(events, start_date, end_date, timezone):
    """Calcula el tiempo total por servicio para cada semana en el rango."""
    weekly_totals = defaultdict(lambda: defaultdict(datetime.timedelta))
    current_date = start_date

    while current_date <= end_date:
        # Determinar inicio y fin de la semana actual (Lunes a Domingo)
        week_start = current_date + relativedelta(weekday=MO(-1))
        week_end = week_start + datetime.timedelta(days=6)

        # Asegurarse de que no nos pasamos del rango solicitado
        actual_week_start = max(week_start, start_date)
        actual_week_end = min(week_end, end_date)

        # Calcular tiempo total laboral en la semana (considerando solo WORK_DAYS)
        total_work_time_week = datetime.timedelta()
        temp_date = actual_week_start
        while temp_date <= actual_week_end:
            if temp_date.weekday() in WORK_DAYS:
                start_dt = timezone.localize(datetime.datetime.combine(temp_date, WORK_START_TIME))
                end_dt = timezone.localize(datetime.datetime.combine(temp_date, WORK_END_TIME))
                total_work_time_week += (end_dt - start_dt)
            temp_date += datetime.timedelta(days=1)

        # Calcular tiempo ocupado por eventos categorizados en la semana
        booked_time_week = datetime.timedelta()

        for event in events:
            event_start_str = event['start'].get('dateTime', event['start'].get('date'))
            event_end_str = event['end'].get('dateTime', event['end'].get('date'))

            if not event_start_str or not event_end_str:
                continue # Ignorar eventos sin fecha de inicio/fin válida

            start_dt = parse_datetime(event_start_str)
            end_dt = parse_datetime(event_end_str)

            if not start_dt or not end_dt:
                continue # Ignorar si no se pudo parsear

            # Convertir a la zona horaria del calendario para comparar
            start_dt = start_dt.astimezone(timezone)
            end_dt = end_dt.astimezone(timezone)

            # Ignorar eventos de todo el día para cálculo de tiempo (a menos que se quiera otra lógica)
            if 'date' in event['start']:
                continue

            # Solo considerar eventos que ocurren dentro de los días laborales y horario laboral
            current_event_date = start_dt.date()
            while current_event_date <= end_dt.date() and current_event_date <= actual_week_end :
                 if current_event_date >= actual_week_start and current_event_date.weekday() in WORK_DAYS:
                    # Definir límites del día laboral en timezone-aware datetime
                    day_work_start = timezone.localize(datetime.datetime.combine(current_event_date, WORK_START_TIME))
                    day_work_end = timezone.localize(datetime.datetime.combine(current_event_date, WORK_END_TIME))

                    # Calcular la intersección del evento con el horario laboral del día actual
                    overlap_start = max(start_dt, day_work_start)
                    overlap_end = min(end_dt, day_work_end)

                    if overlap_end > overlap_start: # Si hay solapamiento dentro del horario laboral
                        duration = overlap_end - overlap_start
                        service = get_service_for_event(event)

                        if service: # Si el evento fue categorizado
                            weekly_totals[week_start][service] += duration
                            booked_time_week += duration
                        elif MEETING_SERVICE is None and DEFAULT_SERVICE:
                            # Si las reuniones no tienen categoría propia y deben ir al default
                             weekly_totals[week_start][DEFAULT_SERVICE] += duration
                             booked_time_week += duration
                        # Si service es None y MEETING_SERVICE existe, se ignora aquí
                        # porque solo contamos tiempo categorizado o default implícito.

                 # Avanzar al siguiente día si el evento dura varios días
                 current_event_date += datetime.timedelta(days=1)


        # Calcular tiempo 'libre' (DEFAULT_SERVICE)
        # Tiempo libre = Total tiempo laboral - Tiempo ocupado por eventos categorizados
        free_time_week = total_work_time_week - booked_time_week
        if free_time_week > datetime.timedelta(0):
            weekly_totals[week_start][DEFAULT_SERVICE] += free_time_week

        # Avanzar a la siguiente semana
        current_date = week_end + datetime.timedelta(days=1)

    return weekly_totals

def format_timedelta(td):
    """Formatea un timedelta a horas con un decimal."""
    total_seconds = td.total_seconds()
    hours = total_seconds / 3600
    return f"{hours:.1f}h"

# --- Ejecución Principal ---
if __name__ == '__main__':
    print("Iniciando script de seguimiento de tiempo de Google Calendar...")
    service = authenticate_google_calendar()

    if service:
        # --- Pide las fechas al usuario ---
        while True:
            try:
                start_date_str = input("Introduce la fecha de inicio (YYYY-MM-DD): ")
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                break
            except ValueError:
                print("Formato de fecha inválido. Usa YYYY-MM-DD.")

        while True:
            try:
                end_date_str = input("Introduce la fecha de fin (YYYY-MM-DD): ")
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if end_date < start_date:
                    print("La fecha de fin no puede ser anterior a la fecha de inicio.")
                else:
                    break
            except ValueError:
                print("Formato de fecha inválido. Usa YYYY-MM-DD.")
        # --- Fin Petición Fechas ---

        calendar_tz = get_calendar_timezone(service)
        print(f"Usando zona horaria del calendario: {calendar_tz}")

        all_events = get_events(service, start_date, end_date, calendar_tz)

        if all_events is not None:
            weekly_summary = calculate_weekly_summary(all_events, start_date, end_date, calendar_tz)

            print("\n--- Resumen Semanal del Tiempo Laboral ---")
            if not weekly_summary:
                print("No se encontraron datos para el período especificado.")
            else:
                # Ordenar semanas por fecha de inicio
                sorted_weeks = sorted(weekly_summary.keys())

                for week_start_date in sorted_weeks:
                    week_end_date = week_start_date + datetime.timedelta(days=6)
                    # Ajustar la fecha de fin de semana mostrada si el rango termina antes
                    display_week_end = min(week_end_date, end_date)

                    print(f"\nSemana ({week_start_date.strftime('%d/%m')} - {display_week_end.strftime('%d/%m/%Y')}):")
                    
                    week_data = weekly_summary[week_start_date]
                    if not week_data:
                        print("  Sin actividad registrada en horario laboral.")
                        continue
                        
                    # Ordenar servicios alfabéticamente para consistencia
                    sorted_services = sorted(week_data.keys())
                    total_week_hours = datetime.timedelta(0)

                    for service_name in sorted_services:
                        duration = week_data[service_name]
                        if duration > datetime.timedelta(seconds=1): # Mostrar solo si hay tiempo > 1s
                           print(f"  {service_name} -> {format_timedelta(duration)}")
                           total_week_hours += duration
                    
                    print(f"  -----------------------------")
                    print(f"  Total Semana: {format_timedelta(total_week_hours)}")


    else:
        print("No se pudo autenticar con Google Calendar. Saliendo.")