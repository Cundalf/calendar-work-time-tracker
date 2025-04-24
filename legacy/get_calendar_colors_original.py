import os.path
import pickle
import sys

# --- Google API Libraries ---
# (Necesitas las mismas librerías que el script principal)
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Error: Faltan librerías de Google. En tu entorno virtual activo, ejecuta:")
    print("pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

# --- Configuración ---
# Scopes necesarios: Solo lectura del calendario es suficiente para colores.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token_colors.pickle' # Usar un archivo de token diferente para evitar conflictos

# --- Funciones ---

def authenticate_for_colors():
    """Autentica con Google Calendar (simplificado para este script)."""
    creds = None
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error Crítico: No se encontró el archivo '{CREDENTIALS_FILE}'.")
        print("Asegúrate de que esté en el mismo directorio que este script.")
        return None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            try:
                creds = pickle.load(token)
            except Exception as e:
                print(f"Advertencia: No se pudo cargar {TOKEN_FILE}. Error: {e}. Re-autenticando.")
                creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error al refrescar token: {e}. Re-autenticación necesaria.")
                if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)
                creds = None
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Error durante flujo de autenticación: {e}")
                return None
        try:
            with open(TOKEN_FILE, 'wb') as token: pickle.dump(creds, token)
        except Exception as e: print(f"Error al guardar token: {e}")

    try:
        service = build('calendar', 'v3', credentials=creds)
        print("Conectado a Google Calendar para obtener colores...")
        return service
    except Exception as e:
        print(f"Error al construir servicio de Google Calendar: {e}")
        return None

def display_event_colors(service):
    """Obtiene y muestra los colores de eventos disponibles."""
    try:
        print("\n--- Colores de Evento Disponibles ---")
        colors_data = service.colors().get().execute()
        event_colors = colors_data.get('event', {})
        if not event_colors:
            print("No se pudieron obtener los colores de los eventos desde la API.")
            return

        # Nombres comunes aproximados (igual que antes)
        standard_color_names = {
            '1': "Lavanda (Azul claro)", '2': "Salvia (Verde azulado)",
            '3': "Uva (Morado)",         '4': "Flamingo (Rosa)",
            '5': "Banana (Amarillo)",    '6': "Mandarina (Naranja)",
            '7': "Pavo Real (Cyan)",     '8': "Grafito (Gris oscuro)",
            '9': "Arándano (Azul oscuro)",'10': "Albahaca (Verde oscuro)",
            '11': "Tomate (Rojo oscuro)"
        }

        print("==============================================================")
        print(" ID | Nombre Común (Estándar Google) | Color (Fondo / Texto)")
        print("==============================================================")
        sorted_ids = sorted(event_colors.keys(), key=int)
        for color_id in sorted_ids:
             color_info = event_colors[color_id]
             background = color_info.get('background', 'N/A')
             foreground = color_info.get('foreground', 'N/A')
             name = standard_color_names.get(color_id, f"Color Personalizado ID {color_id}") # Manejar posibles colores no estándar
             print(f" {color_id.rjust(2)} | {name.ljust(29)} | {background} / {foreground}")
        print("==============================================================")

        print("\nINSTRUCCIONES PARA CONFIGURAR EL SCRIPT PRINCIPAL:")
        print("1. Identifica visualmente los colores que usas para tus etiquetas en Google Calendar.")
        print("2. Busca el 'ID' correspondiente a cada uno de esos colores en la lista de arriba.")
        print("3. Abre el script principal ('calendar_time_tracker_v4_labels.py' o como lo llames).")
        print("4. Edita el diccionario 'COLOR_ID_TO_SERVICE = {'")
        print("5. Añade una línea por cada etiqueta, usando el ID como clave (entre comillas)")
        print("   y el nombre exacto de tu servicio como valor (entre comillas).")
        print("\n   Ejemplo de configuración en el script principal:")
        print("   COLOR_ID_TO_SERVICE = {")
        print("       '8': 'Infraestructura',  # Asigna el color Grafito (ID 8) a 'Infraestructura'")
        print("       '2': 'Capacitaciones',   # Asigna el color Salvia (ID 2) a 'Capacitaciones'")
        print("       '11': 'Gestión',         # Asigna el color Tomate (ID 11) a 'Gestión'")
        print("       # ... añade tus otras etiquetas aquí ...")
        print("   }")
        print("-" * 60)

    except HttpError as error:
        print(f"\nError HTTP obteniendo colores: {error}")
        print("Verifica tu conexión y que la API de Calendar esté habilitada en Google Cloud.")
    except Exception as e:
        print(f"\nError inesperado obteniendo colores: {e}")

# --- Ejecución Principal ---
if __name__ == '__main__':
    print("Obteniendo IDs de colores de Google Calendar...")
    calendar_service = authenticate_for_colors()

    if calendar_service:
        display_event_colors(calendar_service)
    else:
        print("\nNo se pudo autenticar con Google Calendar.")
        print("Asegúrate de tener 'credentials.json' y conexión a internet.")

    print("\nScript de obtención de colores finalizado.")