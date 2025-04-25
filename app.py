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

# Función para limpiar variables de entorno de comentarios
def clean_env_value(value):
    if value and isinstance(value, str):
        # Si hay un # que no está al inicio, considerarlo como inicio de comentario
        if '#' in value and not value.startswith('#'):
            return value.split('#')[0].strip()
    return value

# Cargar variables de entorno
load_dotenv()

# Configuración de la aplicación
app = Flask(__name__)
app.config['SECRET_KEY'] = clean_env_value(os.getenv('SECRET_KEY', 'clave_por_defecto_no_usar_en_produccion'))
app.config['SESSION_TYPE'] = clean_env_value(os.getenv('SESSION_STORAGE', 'filesystem'))
# Extraer solo el valor numérico, eliminando cualquier comentario
session_lifetime = clean_env_value(os.getenv('SESSION_LIFETIME', '3600')) # Reducir a 1 hora por defecto
if session_lifetime and ' ' in session_lifetime:
    session_lifetime = session_lifetime.split(' ')[0]
app.config['PERMANENT_SESSION_LIFETIME'] = int(session_lifetime)

# Configuraciones adicionales para prevenir problemas de sesión
app.config['SESSION_USE_SIGNER'] = True  # Firmar cookies de sesión
app.config['SESSION_FILE_THRESHOLD'] = 500  # Límite de archivos en filesystem storage
app.config['SESSION_PERMANENT'] = False  # Por defecto sesiones no permanentes

# Configuración para forzar que las cookies sean enviadas solo en conexiones seguras en producción
env = clean_env_value(os.getenv('FLASK_ENV', 'production'))
if env != 'development':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_SECURE'] = True
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True

# Deshabilitar caché globalmente si está configurado
disable_cache = os.getenv('DISABLE_CACHE', 'false').lower() in ('true', 'yes', '1')
if disable_cache:
    # No cachear recursos estáticos
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    @app.after_request
    def add_no_cache_headers(response):
        """Añadir encabezados para prevenir caché en todas las respuestas"""
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        # Añadir timestamp para forzar refrescos
        response.headers['X-Timestamp'] = str(datetime.now().timestamp())
        return response

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
logger.add(lambda msg: print(msg), level=log_level, format=log_format)

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
    """Valida la configuración recibida y aplica valores predeterminados SOLO si es necesario"""
    # Devolver el valor predeterminado solo si NO hay configuración
    if not config_data:
        logger.warning("No se recibió configuración. Usando valores predeterminados.")
        return get_default_config()
    
    if isinstance(config_data, str) and not config_data.strip():
        logger.warning("Se recibió configuración como string vacío. Usando valores predeterminados.")
        return get_default_config()
    
    try:
        if isinstance(config_data, str):
            config = json.loads(config_data)
        else:
            config = config_data
        
        # Verificar que existan todas las claves necesarias sin reemplazarlas
        default_config = get_default_config()
        for key in default_config.keys():
            if key not in config:
                logger.warning(f"Falta campo '{key}' en la configuración. Usando valor predeterminado: {default_config[key]}")
                config[key] = default_config[key]
        
        # ¡IMPORTANTE: NO modificar los valores existentes!
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear configuración JSON: {e}")
        return get_default_config()
    except Exception as e:
        logger.error(f"Error inesperado al procesar configuración: {e}")
        return get_default_config()

# Contexto global para las plantillas
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

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
    # Limpiar toda la sesión completamente
    session.clear()
    flash('Sesión cerrada. Se ha desconectado de Google Calendar', 'success')
    
    # Log detallado
    logger.info("Usuario ha cerrado sesión, se ha limpiado toda la sesión")
    
    # Redirigir al dashboard con un parámetro para forzar recarga limpia
    return redirect(url_for('dashboard', _fresh=datetime.now().timestamp()))

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        # Obtener datos de fechas del formulario
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        
        if end_date < start_date:
            flash('La fecha de fin no puede ser anterior a la fecha de inicio', 'error')
            logger.warning(f"Intento de búsqueda con fechas inválidas: start={start_date}, end={end_date}")
            return redirect(url_for('dashboard'))
            
        # Extraer la configuración directamente del request
        config_data = request.form.get('config', '{}')
        logger.info(f"Procesando cálculo para el rango: {start_date} - {end_date}")
        
        # Obtener credenciales de la sesión
        credentials = session.get('credentials')
        
        # Autenticar con Google Calendar
        service, updated_credentials = authenticate_google_calendar(credentials)
        
        # Si hay credenciales actualizadas, guardarlas en la sesión
        if updated_credentials:
            session['credentials'] = updated_credentials
            session.modified = True
        
        if not service:
            logger.warning("Redirección a autenticación - usuario sin credenciales")
            flash('Se requiere autenticación. Por favor inténtelo nuevamente después de iniciar sesión.', 'info')
            return redirect(url_for('auth', next=url_for('dashboard')))
        
        timezone = get_calendar_timezone(service)
        events = get_events(service, start_date, end_date, timezone)
        
        if events is None:
            flash('Error al obtener eventos del calendario', 'error')
            logger.error(f"Error al obtener eventos para el rango {start_date} - {end_date}")
            return redirect(url_for('dashboard'))
            
        # Procesar la configuración recibida
        try:
            config = json.loads(config_data) if isinstance(config_data, str) else config_data
            
            # Verificar campos obligatorios
            default_config = get_default_config()
            for key in default_config:
                if key not in config:
                    logger.warning(f"Campo '{key}' faltante, usando valor por defecto: {default_config[key]}")
                    config[key] = default_config[key]
        except Exception as e:
            logger.error(f"Error al procesar configuración: {e}")
            config = get_default_config()
        
        # Calcular resumen semanal
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
        
        # Procesar resumen semanal - CORREGIDO para manejar el formato correcto
        sorted_weeks = sorted(weekly_summary.keys())
        for week_key in sorted_weeks:
            week_services = weekly_summary[week_key]
            week_total = timedelta()
            
            # Crear descripción de la semana
            week_end = week_key + timedelta(days=6)
            week_description = f"{week_key.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}"
            
            # Agregar los totales de servicios de esta semana a los totales del período
            services_in_week = {}
            for service, time_spent in week_services.items():
                period_totals[service] += time_spent
                grand_total_time += time_spent
                week_total += time_spent
                services_in_week[service] = {
                    'time': time_spent,
                    'formatted': format_timedelta(time_spent)
                }
            
            # Crear estructura de días para mantener compatibilidad con la plantilla
            # (La estructura actual no tiene desglose por días, solo por semana)
            days = {}
            
            processed_summary.append({
                'week': week_key,
                'week_description': week_description,
                'days': days,
                'services': services_in_week,
                'week_total': week_total,
                'week_total_formatted': format_timedelta(week_total)
            })
        
        # Convertir los totales del período a formato legible
        formatted_period_totals = {}
        for service, time_spent in period_totals.items():
            formatted_period_totals[service] = {
                'time': time_spent,
                'formatted': format_timedelta(time_spent)
            }
        
        # Si no hay resultados, mostrar mensaje
        if not processed_summary:
            flash('No se encontraron datos para el período seleccionado', 'warning')
            return redirect(url_for('dashboard'))
        
        # Preparar resumen de período para la plantilla
        period_summary = []
        for service, time_data in formatted_period_totals.items():
            percentage = 0
            if grand_total_time.total_seconds() > 0:
                percentage = round((time_data['time'].total_seconds() / grand_total_time.total_seconds()) * 100, 1)
            
            period_summary.append({
                'name': service,
                'duration': time_data['formatted'],
                'percentage': percentage
            })
        
        # Ordenar por porcentaje descendente
        period_summary.sort(key=lambda x: x['percentage'], reverse=True)
        
        # Preparar resumen de semanas para la plantilla
        weekly_summary = []
        for week_data in processed_summary:
            services_list = []
            for service_name, service_data in week_data['services'].items():
                services_list.append({
                    'name': service_name,
                    'duration': service_data['formatted'],
                    'color': None  # Opcionalmente, se podría añadir color si está disponible en la configuración
                })
            
            # Ordenar servicios por nombre
            services_list.sort(key=lambda x: x['name'])
            
            weekly_summary.append({
                'start_date': week_data['week'].strftime('%d/%m/%Y'),
                'end_date': (week_data['week'] + timedelta(days=6)).strftime('%d/%m/%Y'),
                'services': services_list,
                'total_hours': week_data['week_total_formatted']
            })
        
        # Preparar resumen de configuración
        config_summary = {
            'work_time': f"{config['work_start_time']} - {config['work_end_time']}",
            'lunch': f"{config['lunch_duration_minutes']} min",
            'default_service': config['default_service'],
            'use_color_tags': config['use_color_tags']
        }
        
        # Si hay resultados, mostrar la tabla
        return render_template(
            'results.html',
            weekly_summary=weekly_summary,
            period_summary=period_summary,
            start_date=start_date.strftime('%d/%m/%Y'),
            end_date=end_date.strftime('%d/%m/%Y'),
            total_hours=format_timedelta(grand_total_time),
            config_summary=config_summary
        )
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        flash(f'Error al procesar la solicitud: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

# Ruta para depuración de sesión - solo habilitada en modo desarrollo
@app.route('/debug/session')
def debug_session():
    """Mostrar el contenido de la sesión para depuración"""
    env = os.getenv('FLASK_ENV', 'production')
    debug_mode = env == 'development'
    
    if not debug_mode:
        return jsonify({'error': 'Esta función solo está disponible en modo desarrollo'})
    
    # Convertir la sesión en un diccionario serializable
    session_data = {}
    for key, value in session.items():
        try:
            json.dumps({key: value})
            session_data[key] = value
        except TypeError:
            session_data[key] = str(value)
    
    return jsonify({
        'session': session_data,
        'timestamp': datetime.now().isoformat()
    })

# Para producción, no ejecutar app.run() directamente
# Usar gunicorn o similar
if __name__ == '__main__':
    # Configuración según el entorno
    env = clean_env_value(os.getenv('FLASK_ENV', 'production'))
    debug_mode = env == 'development'
    host = clean_env_value(os.getenv('HOST', '0.0.0.0'))
    port = int(clean_env_value(os.getenv('PORT', 5000)))
    
    if debug_mode:
        logger.info(f"Iniciando en modo desarrollo: http://{host}:{port}")
    else:
        logger.info(f"Iniciando en modo producción: {host}:{port}")
    
    app.run(host=host, port=port, debug=debug_mode) 