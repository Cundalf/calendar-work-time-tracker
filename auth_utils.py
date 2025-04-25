"""
Utilidades para la autenticación con Google Calendar API.
Este módulo maneja la autenticación OAuth2 con Google.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Local imports
from config_utils import clean_env_value

# Google Calendar API Scopes
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Variable global para almacenar el flujo de autenticación en curso
_current_flow = None

def get_oauth_flow(force_new=False):
    """
    Obtener o crear el flujo OAuth para autenticación web
    
    Args:
        force_new: Forzar la creación de un nuevo flujo
        
    Returns:
        Objeto de flujo OAuth o None si no se puede crear
    """
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
    """
    Generar URL para autorización de OAuth
    
    Returns:
        URL de autorización o None si hay error
    """
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
    """
    Completar el flujo OAuth con el código de autorización
    
    Args:
        code: Código de autorización recibido de Google
        
    Returns:
        Objeto Credentials o None si hay error
    """
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
    """
    Convertir objeto Credentials a diccionario para almacenar en sesión
    
    Args:
        credentials: Objeto Credentials de Google
        
    Returns:
        Diccionario con los datos de las credenciales
    """
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

def dict_to_credentials(credentials_dict):
    """
    Convertir diccionario de sesión a objeto Credentials
    
    Args:
        credentials_dict: Diccionario con datos de credenciales
        
    Returns:
        Objeto Credentials de Google o None si hay error
    """
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
        Tuple con (Servicio de Google Calendar, credenciales actualizadas) o (None, None)
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