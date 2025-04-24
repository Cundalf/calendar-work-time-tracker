import datetime
import os.path
import pickle
import pytz # Para manejar zonas horarias robustamente
from collections import defaultdict
from dateutil.relativedelta import relativedelta, MO # para calcular inicios de semana
import sys

# --- Google API Libraries ---
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Error: Faltan librerías de Google. Ejecuta:")
    print("pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib pytz python-dateutil")
    sys.exit(1)
# Opcional: para fallback de timezone
try:
    import tzlocal
except ImportError:
    pass # tzlocal es opcional

# --- CONFIGURACIÓN ---

# --- Colores de Evento Disponibles ---
# ==============================================================
#  ID | Nombre Común (Estándar Google) | Color (Fondo / Texto)
# ==============================================================
#   1 | Lavanda (Azul claro)          | #a4bdfc / #1d1d1d
#   2 | Salvia (Verde azulado)        | #7ae7bf / #1d1d1d
#   3 | Uva (Morado)                  | #dbadff / #1d1d1d
#   4 | Flamingo (Rosa)               | #ff887c / #1d1d1d
#   5 | Banana (Amarillo)             | #fbd75b / #1d1d1d
#   6 | Mandarina (Naranja)           | #ffb878 / #1d1d1d
#   7 | Pavo Real (Cyan)              | #46d6db / #1d1d1d
#   8 | Grafito (Gris oscuro)         | #e1e1e1 / #1d1d1d
#   9 | Arándano (Azul oscuro)        | #5484ed / #1d1d1d
#  10 | Albahaca (Verde oscuro)       | #51b749 / #1d1d1d
#  11 | Tomate (Rojo oscuro)          | #dc2127 / #1d1d1d
# ==============================================================


# 1. Mapeo de ID de COLOR de Etiqueta a Nombre de Servicio:
#    (Configura esto usando la salida del script 'get_calendar_colors.py')
COLOR_ID_TO_SERVICE = {
     '11': 'Personas',   
     '6': 'Delivery',
     '9': 'Infraestructura', 
     '4': 'Capacitacion Interna', 
     '10': 'Personas PdC', 
     '3': 'Organizacion', 
    # 'ID_Color_Tuyo': 'Nombre Del Servicio Correspondiente',
    # ... Añade aquí los IDs de TUS etiquetas y sus servicios ...
}

# 2. Servicios para Tipos de Evento SIN Etiqueta de Color Asignada:
OOO_SERVICE = 'FUERA DE OFICINA'
FOCUS_TIME_SERVICE = 'TIEMPO CONCENTRACION (Sin Et.)'
DEFAULT_SERVICE = 'RSG (Default & Libre)' # Para eventos 'default' sin etiqueta y tiempo libre

# 3. Duración del Almuerzo en MINUTOS
LUNCH_DURATION_MINUTES = 60

# 4. Google Calendar API Scopes (Solo lectura del calendario ahora)
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# --- FIN DE LA CONFIGURACIÓN ---

# --- Funciones Auxiliares (Autenticación, Timezone, etc.) ---

def authenticate_google_calendar():
    # (Función sin cambios respecto a v4, pero ya no necesita el scope de settings)
    creds = None
    token_file = 'token.pickle' # Usamos el token principal de nuevo
    credentials_file = 'credentials.json'

    if not os.path.exists(credentials_file):
        print(f"Error Crítico: No se encontró '{credentials_file}'.")
        return None

    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            try: creds = pickle.load(token)
            except Exception as e: print(f"Adv: No se cargó {token_file}: {e}. Re-autenticando."); creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try: creds.refresh(Request()); print("Token refrescado.")
            except Exception as e:
                print(f"Error refrescando token: {e}. Re-autenticación.");
                if os.path.exists(token_file): os.remove(token_file)
                creds = None
        if not creds:
            try:
                print("Iniciando flujo de autenticación...")
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
                print("Autenticación completada.")
            except Exception as e: print(f"Error en flujo auth: {e}"); return None
        try:
            with open(token_file, 'wb') as token: pickle.dump(creds, token)
            print(f"Credenciales guardadas en {token_file}")
        except Exception as e: print(f"Error guardando token: {e}")

    # Verificar scopes concedidos (menos crítico ahora, pero buena práctica)
    granted_scopes = creds.scopes if hasattr(creds, 'scopes') else []
    missing_scopes = [s for s in SCOPES if s not in granted_scopes]
    if missing_scopes:
        print("\nAdvertencia: Faltan permisos (scopes) básicos:")
        for scope in missing_scopes: print(f"  - {scope}")
        print(f"-> Elimina '{token_file}' y re-ejecuta para concederlos <-\n")

    try:
        service = build('calendar', 'v3', credentials=creds)
        print("Servicio de Google Calendar conectado.")
        return service
    except Exception as e:
        print(f"Error al construir servicio: {e}")
        return None

def get_calendar_timezone(service):
    # (Función sin cambios respecto a v4)
    try:
        settings = service.settings().get(setting='timezone').execute()
        tz_str = settings['value']
        print(f"Zona horaria obtenida de Google Calendar: {tz_str}")
        return pytz.timezone(tz_str)
    except HttpError as error:
        print(f"Error HTTP obteniendo zona horaria: {error}. Fallback.")
    except Exception as e:
        print(f"Error inesperado obteniendo timezone: {e}. Fallback.")
    # Fallback
    try:
        import tzlocal
        local_tz_name = tzlocal.get_localzone_name()
        print(f"Usando zona horaria local del sistema: {local_tz_name}")
        return pytz.timezone(local_tz_name)
    except Exception as e_local:
         print(f"Fallback de Timezone falló ({e_local}). Usando UTC.")
         return pytz.utc

def get_manual_working_hours():
    """Pide al usuario el horario laboral manualmente, con defaults."""
    print("\nConfiguración del Horario Laboral:")
    default_start = datetime.time(9, 0)
    default_end = datetime.time(18, 0)
    user_start_time = None
    user_end_time = None

    while user_start_time is None:
        try:
            start_str = input(f"  Hora de inicio (HH:MM) [Default: {default_start.strftime('%H:%M')}]: ")
            if not start_str: # Si el usuario presiona Enter
                user_start_time = default_start
                print(f"  > Usando default: {user_start_time.strftime('%H:%M')}")
            else:
                user_start_time = datetime.datetime.strptime(start_str, '%H:%M').time()
            break # Sale del bucle si es válido o default
        except ValueError:
            print("    Formato inválido. Usa HH:MM (ej. 09:00)")

    while user_end_time is None:
        try:
            end_str = input(f"  Hora de fin (HH:MM) [Default: {default_end.strftime('%H:%M')}]: ")
            if not end_str: # Si el usuario presiona Enter
                user_end_time = default_end
                print(f"  > Usando default: {user_end_time.strftime('%H:%M')}")
            else:
                user_end_time = datetime.datetime.strptime(end_str, '%H:%M').time()

            # Validar que fin sea después de inicio
            if user_end_time <= user_start_time:
                print("    La hora de fin debe ser posterior a la hora de inicio.")
                user_end_time = None # Forzar a preguntar de nuevo
            else:
                break # Sale del bucle si es válido o default
        except ValueError:
            print("    Formato inválido. Usa HH:MM (ej. 18:00)")

    # Días laborales por defecto: Lunes a Viernes
    user_work_days = [0, 1, 2, 3, 4]
    days_str = "Lunes a Viernes"
    print(f"Horario laboral configurado: {user_start_time.strftime('%H:%M')} - {user_end_time.strftime('%H:%M')}, {days_str}.")
    return user_start_time, user_end_time, user_work_days

def get_events(service, start_date, end_date, timezone):
    # (Función sin cambios respecto a v4)
    try:
        time_min = timezone.localize(datetime.datetime.combine(start_date, datetime.time.min)).isoformat()
        time_max = timezone.localize(datetime.datetime.combine(end_date + datetime.timedelta(days=1), datetime.time.min)).isoformat()
    except Exception as e: print(f"Error localizando fechas API: {e}"); return None
    print(f"\nBuscando eventos desde {start_date.strftime('%Y-%m-%d')} hasta {end_date.strftime('%Y-%m-%d')}...")
    # ... (resto idéntico a v4 para paginación y obtención) ...
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
            if not page_token: break
        except HttpError as error: print(f'Error HTTP obteniendo eventos: {error}'); return None
        except Exception as e: print(f'Error inesperado obteniendo eventos: {e}'); return None
    print(f"Encontrados {len(all_events)} eventos.")
    return all_events

def parse_datetime_api(dt_obj):
    # (Función sin cambios respecto a v4)
    if not dt_obj: return None, False
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
        else: return None, False
        return dt, is_all_day
    except Exception: return None, False # Simplificado

def assign_service(event):
    # (Función sin cambios respecto a v4)
    color_id = event.get('colorId')
    event_type = event.get('eventType', 'default')
    if color_id and color_id in COLOR_ID_TO_SERVICE:
        return COLOR_ID_TO_SERVICE[color_id]
    if event_type == 'outOfOffice': return OOO_SERVICE
    if event_type == 'focusTime': return FOCUS_TIME_SERVICE
    return DEFAULT_SERVICE # Incluye 'default' y cualquier otro tipo no reconocido

def format_timedelta(td):
    # (Función sin cambios respecto a v4)
    if not isinstance(td, datetime.timedelta): return "0.0h"
    total_seconds = td.total_seconds()
    if -1 < total_seconds < 0: total_seconds = 0
    hours = total_seconds / 3600
    return f"{hours:.1f}h"

# --- Función Principal de Cálculo ---

def calculate_weekly_summary(events, start_date, end_date, timezone, work_start_time, work_end_time, work_days):
    # (Función sin cambios respecto a v4 - usa la lógica de colores/tipos)
    weekly_totals = defaultdict(lambda: defaultdict(datetime.timedelta))
    current_date = start_date
    lunch_delta = datetime.timedelta(minutes=LUNCH_DURATION_MINUTES)

    # Preparar eventos (parsear fechas, asignar servicio)
    parsed_events = []
    for event in events:
        # ... (parseo idéntico a v4) ...
        start_dt_api, start_is_all_day = parse_datetime_api(event.get('start'))
        end_dt_api, end_is_all_day = parse_datetime_api(event.get('end'))
        if not start_dt_api or not end_dt_api: continue
        try:
            start_dt = start_dt_api.astimezone(timezone)
            end_dt = end_dt_api.astimezone(timezone)
        except Exception: continue
        if start_is_all_day and end_dt.time() == datetime.time.min and end_dt.date() > start_dt.date():
             end_dt = end_dt - datetime.timedelta(seconds=1)

        parsed_events.append({
            'summary': event.get('summary', 'N/A'),
            'start': start_dt, 'end': end_dt,
            'is_all_day': start_is_all_day,
            'service': assign_service(event) # <--- Lógica central aquí
        })

    # --- Bucle Semanal y Diario (lógica idéntica a v4) ---
    while current_date <= end_date:
        week_start = current_date + relativedelta(weekday=MO(-1))
        week_end = week_start + datetime.timedelta(days=6)
        actual_week_start_day = max(week_start, start_date)
        actual_week_end_day = min(week_end, end_date)
        total_potential_work_time_week = datetime.timedelta()
        total_booked_time_week = datetime.timedelta() # Acumula TODO el tiempo ocupado

        temp_date = actual_week_start_day
        while temp_date <= actual_week_end_day:
            # ... (cálculo de horas laborales del día idéntico a v4) ...
            daily_work_start_dt, daily_work_end_dt = None, None
            is_work_day = temp_date.weekday() in work_days
            if is_work_day:
                try:
                    daily_work_start_dt = timezone.localize(datetime.datetime.combine(temp_date, work_start_time))
                    daily_work_end_dt = timezone.localize(datetime.datetime.combine(temp_date, work_end_time))
                    daily_potential_time = (daily_work_end_dt - daily_work_start_dt) - lunch_delta
                    if daily_potential_time < datetime.timedelta(0): daily_potential_time = datetime.timedelta(0)
                    total_potential_work_time_week += daily_potential_time
                except Exception as e: print(f"Error localizando horario {temp_date}: {e}"); is_work_day = False

            # ... (procesamiento de eventos que solapan con el día, idéntico a v4) ...
            for event_data in parsed_events:
                start_dt, end_dt = event_data['start'], event_data['end']
                service, is_all_day = event_data['service'], event_data['is_all_day']

                if start_dt.date() <= temp_date <= end_dt.date():
                    if is_all_day:
                        if service == OOO_SERVICE and is_work_day and daily_work_start_dt and daily_work_end_dt:
                            duration = daily_work_end_dt - daily_work_start_dt
                            weekly_totals[week_start][service] += duration
                            total_booked_time_week += duration
                        continue # Ignorar otros all-day

                    if not is_work_day: continue # Ignorar eventos con hora en días no laborables

                    overlap_start = max(start_dt, daily_work_start_dt)
                    overlap_end = min(end_dt, daily_work_end_dt)
                    duration = datetime.timedelta(0)
                    if overlap_end > overlap_start: duration = overlap_end - overlap_start

                    if duration > datetime.timedelta(seconds=1):
                        weekly_totals[week_start][service] += duration
                        total_booked_time_week += duration

            temp_date += datetime.timedelta(days=1)
        # --- Fin Bucle Diario ---

        # ... (cálculo y asignación de tiempo libre, idéntico a v4) ...
        free_time_week = total_potential_work_time_week - total_booked_time_week
        if free_time_week < datetime.timedelta(0): free_time_week = datetime.timedelta(0)
        if free_time_week > datetime.timedelta(seconds=1) and DEFAULT_SERVICE:
            weekly_totals[week_start][DEFAULT_SERVICE] += free_time_week

        current_date = week_end + datetime.timedelta(days=1)
    # --- Fin Bucle Semanal ---

    return weekly_totals

# --- Ejecución Principal ---
if __name__ == '__main__':
    print("Iniciando script de seguimiento de tiempo v5 (Etiquetas Color / Horas Manuales)...")
    service = authenticate_google_calendar()

    if service:
        calendar_tz = get_calendar_timezone(service)
        print(f"Usando zona horaria: {calendar_tz}")

        # Obtener horario laboral manualmente
        work_start, work_end, work_days = get_manual_working_hours()
        if work_start is None: sys.exit(1) # Salir si hay error en la obtención manual

        # Pedir fechas (idéntico a v4)
        while True:
            try:
                start_date_str = input("\nIntroduce la fecha de inicio (YYYY-MM-DD): ")
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                break
            except ValueError: print("Formato inválido.")
        while True:
            try:
                end_date_str = input("Introduce la fecha de fin (YYYY-MM-DD): ")
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if end_date < start_date: print("La fecha de fin no puede ser anterior.")
                else: break
            except ValueError: print("Formato inválido.")

        all_events = get_events(service, start_date, end_date, calendar_tz)

        if all_events is not None:
            # --- Cálculo y Reporte (idéntico a v4) ---
            weekly_summary = calculate_weekly_summary(
                all_events, start_date, end_date, calendar_tz,
                work_start, work_end, work_days
            )
            # ... (impresión de resultados idéntica a v4) ...
            print("\n--- Resumen Semanal del Tiempo Laboral ---")
            if not weekly_summary: print("No se encontraron datos.")
            else:
                sorted_weeks = sorted(weekly_summary.keys())
                period_totals = defaultdict(datetime.timedelta)
                grand_total_time = datetime.timedelta()
                for week_start_date in sorted_weeks:
                    week_end_date = week_start_date + datetime.timedelta(days=6)
                    display_week_end = min(week_end_date, end_date)
                    print(f"\nSemana ({week_start_date.strftime('%d/%m')} - {display_week_end.strftime('%d/%m/%Y')}):")
                    week_data = weekly_summary[week_start_date]
                    if not week_data: print("  Sin actividad registrada."); continue
                    sorted_services = sorted(week_data.keys())
                    total_week_hours = datetime.timedelta()
                    for service_name in sorted_services:
                        duration = week_data[service_name]
                        if duration > datetime.timedelta(seconds=1):
                           print(f"  {service_name} -> {format_timedelta(duration)}")
                           total_week_hours += duration
                           period_totals[service_name] += duration
                           grand_total_time += duration
                    print(f"  -----------------------------")
                    print(f"  Total Semana: {format_timedelta(total_week_hours)}")
                print("\n\n--- Resumen Total del Periodo ---")
                print(f"({start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')})")
                if not period_totals: print("  Sin actividad registrada.")
                else:
                    sorted_total_services = sorted(period_totals.keys())
                    for service_name in sorted_total_services:
                        total_duration = period_totals[service_name]
                        if total_duration > datetime.timedelta(seconds=1): print(f"  {service_name} -> {format_timedelta(total_duration)}")
                    print(f"  =============================")
                    print(f"  Total General Periodo: {format_timedelta(grand_total_time)}")
    else:
        print("\nNo se pudo autenticar. Verifica 'credentials.json'. Saliendo.")