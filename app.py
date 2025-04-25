# Standard library imports
import os
import json
from datetime import datetime, time, timedelta
from collections import defaultdict

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from dotenv import load_dotenv
from loguru import logger

# Local application imports
from calendar_time_tracker import (
    authenticate_google_calendar, 
    get_calendar_timezone, 
    get_events, 
    calculate_weekly_summary, 
    format_timedelta,
    get_authorization_url,
    complete_oauth_flow,
    credentials_to_dict
)

# Cargar variables de entorno
load_dotenv()

# Configuración de la aplicación
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clave_por_defecto_no_usar_en_produccion')
app.config['SESSION_TYPE'] = 'filesystem'
# Extraer solo el valor numérico, eliminando cualquier comentario
session_lifetime = os.getenv('SESSION_LIFETIME', '86400')
if session_lifetime and ' ' in session_lifetime:
    session_lifetime = session_lifetime.split(' ')[0]
app.config['PERMANENT_SESSION_LIFETIME'] = int(session_lifetime)  # 24 horas por defecto

# Configuración de logs
log_level = os.getenv('LOG_LEVEL', 'INFO')
if log_level and ' ' in log_level:  # Eliminar posibles comentarios
    log_level = log_level.split(' ')[0]
log_format = os.getenv('LOG_FORMAT', '{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}')
if log_format and ' ' in log_format:  # Eliminar posibles comentarios
    log_format = log_format.split('#')[0].strip()
log_path = os.getenv('LOG_PATH', 'logs/')
if log_path and ' ' in log_path:  # Eliminar posibles comentarios
    log_path = log_path.split(' ')[0]

# Asegurar que existe el directorio de logs
os.makedirs(log_path, exist_ok=True)

# Configurar Loguru
logger.remove()  # Remover el handler por defecto
logger.add(f"{log_path}/app.log", 
           level=log_level, 
           format=log_format, 
           rotation="10 MB", 
           retention="1 month")
# Agregar handler para mostrar todos los logs en la consola
logger.add(lambda msg: print(msg), level=log_level, format=log_format)  # Mostrar todos los logs en consola, no solo warnings

# Definir horario predeterminado (para usar time explícitamente)
DEFAULT_WORK_START = time(9, 0)  # 9:00 AM
DEFAULT_WORK_END = time(17, 0)   # 5:00 PM

# Función para obtener configuración predeterminada
def get_default_config():
    """Retorna una configuración predeterminada con valores seguros"""
    return {
        'work_start_time': '09:00',
        'work_end_time': '17:00',
        'lunch_duration_minutes': 60,
        'default_service': 'TIEMPO NO ETIQUETADO',
        'ooo_service': 'FUERA DE OFICINA',
        'focus_time_service': 'TIEMPO DE CONCENTRACIÓN',
        'unlabeled_service': 'SIN ETIQUETA',
        'group_unlabeled': False,
        'use_color_tags': False,
        'color_tags': {}
    }

# Función para validar la configuración y aplicar defaults cuando sea necesario
def validate_config(config_data):
    """Valida la configuración recibida y aplica valores predeterminados si es necesario"""
    logger.info(f"Iniciando validación de configuración. Tipo recibido: {type(config_data)}")
    
    if not config_data:
        logger.warning("No se recibió configuración. Usando valores predeterminados.")
        return get_default_config()
    
    if isinstance(config_data, str) and not config_data.strip():
        logger.warning("Se recibió configuración como string vacío. Usando valores predeterminados.")
        return get_default_config()
    
    try:
        if isinstance(config_data, str):
            logger.info(f"Parseando configuración como string JSON. Longitud: {len(config_data)}")
            config = json.loads(config_data)
        else:
            logger.info(f"Usando configuración que ya es un objeto. Tipo: {type(config_data)}")
            config = config_data
            
        logger.info(f"Configuración después del parsing: {config}")
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear configuración JSON: {e}. Usando valores predeterminados.")
        logger.error(f"String que causó el error: '{config_data}'")
        return get_default_config()
    except Exception as e:
        logger.error(f"Error inesperado al procesar configuración: {e}. Usando valores predeterminados.")
        return get_default_config()
    
    # Validar campos esenciales y aplicar defaults si faltan
    default_config = get_default_config()
    for key, default_value in default_config.items():
        if key not in config:
            logger.warning(f"Falta campo '{key}' en la configuración. Usando valor predeterminado: {default_value}")
            config[key] = default_value
        elif config[key] is None:
            logger.warning(f"Campo '{key}' es None. Usando valor predeterminado: {default_value}")
            config[key] = default_value
        elif isinstance(config[key], str) and config[key].strip() == '':
            logger.warning(f"Campo '{key}' es string vacío. Usando valor predeterminado: {default_value}")
            config[key] = default_value
        else:
            logger.info(f"Campo '{key}' configurado correctamente con valor: {config[key]}")
    
    return config

# Contexto global para las plantillas
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Agregar encabezados de no caché a todas las respuestas
@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Rutas
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/config')
def config():
    return render_template('config.html')

@app.route('/privacy-policy')
def privacy_policy():
    """Mostrar la política de privacidad y uso de cookies"""
    return render_template('privacy_policy.html')

@app.route('/auth')
def auth():
    """Mostrar página de autenticación con Google"""
    # Guardar la URL a la que redirigir después de la autenticación
    next_url = request.args.get('next', url_for('dashboard'))
    session['next_url'] = next_url
    
    # Obtener URL de autorización
    auth_url = get_authorization_url()
    
    logger.info("Mostrando página de autenticación con Google")
    return render_template('auth.html', auth_url=auth_url)

@app.route('/auth/google')
def auth_google():
    """Iniciar el flujo de autenticación con Google"""
    # Guardar la URL a la que redirigir después de la autenticación
    next_url = request.args.get('next', url_for('dashboard'))
    session['next_url'] = next_url
    
    # Obtener URL de autorización
    auth_url = get_authorization_url()
    if not auth_url:
        flash('Error al generar URL de autorización. Verifique la configuración.', 'error')
        logger.error("Error al generar URL de autorización de Google")
        return redirect(url_for('dashboard'))
    
    logger.info("Redirigiendo a Google para autenticación")
    return redirect(auth_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Manejar la respuesta de Google OAuth"""
    error = request.args.get('error', '')
    if error:
        flash(f'Error en la autenticación: {error}', 'error')
        logger.error(f"Error en callback OAuth: {error}")
        return redirect(url_for('dashboard'))
    
    code = request.args.get('code', '')
    if not code:
        flash('No se recibió código de autorización', 'error')
        logger.error("No se recibió código de autorización en callback")
        return redirect(url_for('dashboard'))
    
    # Completar el flujo de OAuth con el código recibido
    credentials = complete_oauth_flow(code)
    if not credentials:
        flash('Error al procesar código de autorización', 'error')
        logger.error("Error al completar flujo OAuth")
        return redirect(url_for('dashboard'))
    
    # Guardar las credenciales en la sesión del usuario
    session['credentials'] = credentials_to_dict(credentials)
    session.modified = True
    
    flash('Autenticación con Google completada correctamente', 'success')
    logger.info("Autenticación con Google completada exitosamente")
    
    # Redirigir a la URL guardada o al dashboard
    next_url = session.pop('next_url', url_for('dashboard'))
    return redirect(next_url)

@app.route('/logout')
def logout():
    """Cerrar sesión y eliminar credenciales"""
    if 'credentials' in session:
        session.pop('credentials')
    flash('Sesión cerrada. Se ha desconectado de Google Calendar', 'success')
    return redirect(url_for('dashboard'))

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        # Log completo de todos los datos recibidos en la solicitud
        logger.info(f"Solicitud POST recibida: {request.form}")
        logger.info(f"Headers recibidos: {dict(request.headers)}")
        
        # Verificar si hay un timestamp para prevenir caché
        timestamp = request.form.get('timestamp')
        if timestamp:
            logger.info(f"Timestamp recibido: {timestamp} - {datetime.fromtimestamp(int(timestamp)/1000).strftime('%Y-%m-%d %H:%M:%S')}")
        
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        
        if end_date < start_date:
            flash('La fecha de fin no puede ser anterior a la fecha de inicio', 'error')
            logger.warning(f"Intento de búsqueda con fechas inválidas: start={start_date}, end={end_date}")
            return redirect(url_for('dashboard'))
        
        # Guardar datos del formulario en la sesión para restaurarlos después de autenticación
        form_data = {
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'config': request.form.get('config', '{}'),
            'timestamp': timestamp  # Añadir timestamp para prevenir caché
        }
        session['form_data'] = form_data
        logger.debug(f"Datos guardados en sesión: {form_data}")
        
        # Obtener credenciales de la sesión
        credentials = session.get('credentials')
        
        # Autenticar con Google Calendar
        service, updated_credentials = authenticate_google_calendar(credentials)
        
        # Si hay credenciales actualizadas, guardarlas en la sesión
        if updated_credentials:
            session['credentials'] = updated_credentials
            session.modified = True
        
        if not service:
            # Necesita autenticación
            logger.info("Redirigiendo a autenticación con Google Calendar")
            return redirect(url_for('auth', next=url_for('calculate_with_session')))
        
        timezone = get_calendar_timezone(service)
        events = get_events(service, start_date, end_date, timezone)
        
        if events is None:
            flash('Error al obtener eventos del calendario', 'error')
            logger.error(f"Error al obtener eventos para el rango {start_date} - {end_date}")
            return redirect(url_for('dashboard'))
        
        # Obtener configuración del localStorage (se enviará desde el frontend)
        config_data = request.form.get('config')
        
        # Registro detallado de la configuración recibida
        logger.info(f"Configuración recibida del formulario: {config_data}")
        
        # Validar y aplicar valores predeterminados cuando sea necesario
        config = validate_config(config_data)
        
        # Registrar la configuración final que se usará
        logger.info(f"Configuración final a utilizar: {json.dumps(config, indent=2)}")
        
        # Log de valores específicos importantes
        logger.info(f"Usando horario: {config['work_start_time']} - {config['work_end_time']}")
        logger.info(f"Servicio predeterminado: {config['default_service']}")
        logger.info(f"Etiquetas de color habilitadas: {config.get('use_color_tags', False)}")
        
        weekly_summary = calculate_weekly_summary(
            events, start_date, end_date, timezone,
            datetime.strptime(config['work_start_time'], '%H:%M').time(),
            datetime.strptime(config['work_end_time'], '%H:%M').time(),
            [0, 1, 2, 3, 4],  # Lunes a Viernes
            config  # Pasar la configuración completa para usar color_tags y servicios
        )
        
        # Procesar resultados para enviar a la plantilla
        processed_summary = []
        period_totals = defaultdict(timedelta)
        grand_total_time = timedelta()
        
        # Procesar resumen semanal
        sorted_weeks = sorted(weekly_summary.keys())
        for week_start_date in sorted_weeks:
            week_end_date = week_start_date + timedelta(days=6)
            display_week_end = min(week_end_date, end_date)
            
            week_data = weekly_summary[week_start_date]
            if not week_data:
                continue
                
            sorted_services = sorted(week_data.keys())
            week_services = []
            total_week_hours = timedelta()
            
            for service_name in sorted_services:
                duration = week_data[service_name]
                if duration > timedelta(seconds=1):
                    week_services.append({
                        'name': service_name,
                        'duration': format_timedelta(duration),
                        'raw_duration': duration
                    })
                    total_week_hours += duration
                    period_totals[service_name] += duration
                    grand_total_time += duration
            
            processed_summary.append({
                'start_date': week_start_date.strftime('%d/%m'),
                'end_date': display_week_end.strftime('%d/%m/%Y'),
                'services': week_services,
                'total_hours': format_timedelta(total_week_hours),
                'raw_total': total_week_hours
            })
        
        # Procesar totales del periodo
        period_summary = []
        if period_totals:
            for service_name, duration in sorted(period_totals.items()):
                if duration > timedelta(seconds=1):
                    # Calcular porcentaje
                    percentage = (duration.total_seconds() / grand_total_time.total_seconds()) * 100 if grand_total_time.total_seconds() > 0 else 0
                    
                    period_summary.append({
                        'name': service_name,
                        'duration': format_timedelta(duration),
                        'percentage': round(percentage, 1)
                    })
        
        logger.info(f"Cálculo completado para {start_date} - {end_date}: {format_timedelta(grand_total_time)} horas totales")
        return render_template(
            'results.html', 
            weekly_summary=processed_summary,
            period_summary=period_summary,
            start_date=start_date.strftime('%d/%m/%Y'),
            end_date=end_date.strftime('%d/%m/%Y'),
            total_hours=format_timedelta(grand_total_time)
        )
        
    except Exception as e:
        error_msg = f'Error inesperado: {str(e)}'
        flash(error_msg, 'error')
        logger.exception(f"Error en calculate: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/calculate_with_session', methods=['GET'])
def calculate_with_session():
    """Procesar cálculo con datos guardados en sesión después de autenticación"""
    if 'form_data' not in session:
        flash('No hay datos de búsqueda en la sesión', 'error')
        return redirect(url_for('dashboard'))
    
    form_data = session.pop('form_data')
    # Re-crear una solicitud POST con los datos almacenados
    class MockPost:
        def __init__(self, data):
            self.form = data
    
    # Guardar la request original
    original_request = request
    try:
        # Mockear la request con nuestro objeto
        request.__class__.form = form_data
        # Llamar a la función de cálculo
        return calculate()
    finally:
        # Restaurar la request original
        request.__class__ = original_request.__class__

# Para producción, no ejecutar app.run() directamente
# Usar gunicorn o similar
if __name__ == '__main__':
    # Configuración según el entorno
    env = os.getenv('FLASK_ENV', 'production')
    debug_mode = env == 'development'
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    
    if debug_mode:
        logger.info(f"Iniciando en modo desarrollo: http://{host}:{port}")
    else:
        logger.info(f"Iniciando en modo producción: {host}:{port}")
    
    app.run(host=host, port=port, debug=debug_mode) 