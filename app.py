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
app.config['SESSION_TYPE'] = os.getenv('SESSION_STORAGE', 'filesystem')
# Extraer solo el valor numérico, eliminando cualquier comentario
session_lifetime = os.getenv('SESSION_LIFETIME', '3600') # Reducir a 1 hora por defecto
if session_lifetime and ' ' in session_lifetime:
    session_lifetime = session_lifetime.split(' ')[0]
app.config['PERMANENT_SESSION_LIFETIME'] = int(session_lifetime)

# Configuraciones adicionales para prevenir problemas de sesión
app.config['SESSION_USE_SIGNER'] = True  # Firmar cookies de sesión
app.config['SESSION_FILE_THRESHOLD'] = 500  # Límite de archivos en filesystem storage
app.config['SESSION_PERMANENT'] = False  # Por defecto sesiones no permanentes

# Configuración para forzar que las cookies sean enviadas solo en conexiones seguras en producción
if os.getenv('FLASK_ENV') != 'development':
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
    """Valida la configuración recibida y aplica valores predeterminados SOLO si es necesario"""
    logger.info(f"Iniciando validación de configuración. Tipo recibido: {type(config_data)}")
    
    # Devolver el valor predeterminado solo si NO hay configuración
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
        
        # Verificar que existan todas las claves necesarias sin reemplazarlas
        default_config = get_default_config()
        for key in default_config.keys():
            if key not in config:
                logger.warning(f"Falta campo '{key}' en la configuración. Usando valor predeterminado: {default_config[key]}")
                config[key] = default_config[key]
        
        # ¡IMPORTANTE: NO modificar los valores existentes!
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear configuración JSON: {e}. Usando valores predeterminados.")
        logger.error(f"String que causó el error: '{config_data}'")
        return get_default_config()
    except Exception as e:
        logger.error(f"Error inesperado al procesar configuración: {e}. Usando valores predeterminados.")
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
        # HARD RESET - Forzar limpieza completa de sesión
        if 'form_data' in session:
            del session['form_data']
            logger.info("FORZADO: Limpieza de form_data en sesión")
            
        # Volcar todo el contenido de la solicitud para depuración
        logger.info(f"RAW REQUEST DATA: {request.get_data(as_text=True)}")
        logger.info(f"FORM: {request.form}")
        logger.info(f"COOKIES: {request.cookies}")
        logger.info(f"SESSION: {dict(session)}")
        
        # Log de datos recibidos
        logger.info(f"Solicitud POST recibida: {request.form}")
        logger.info(f"Headers recibidos: {dict(request.headers)}")
        
        # Verificar timestamp
        timestamp = request.form.get('timestamp')
        if timestamp:
            logger.info(f"Timestamp recibido: {timestamp} - {datetime.fromtimestamp(int(timestamp)/1000).strftime('%Y-%m-%d %H:%M:%S')}")
        
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        
        if end_date < start_date:
            flash('La fecha de fin no puede ser anterior a la fecha de inicio', 'error')
            logger.warning(f"Intento de búsqueda con fechas inválidas: start={start_date}, end={end_date}")
            return redirect(url_for('dashboard'))
            
        # IMPORTANTE: Extraer la configuración directamente del request
        # No guardar en sesión para evitar contaminación
        config_data = request.form.get('config', '{}')
        logger.info(f"CONFIG RECIBIDA DIRECTAMENTE: {config_data}")
        
        # NO GUARDAR DATOS DEL FORMULARIO EN SESIÓN - SOLO LAS CREDENCIALES
        
        # Obtener credenciales de la sesión
        credentials = session.get('credentials')
        
        # Autenticar con Google Calendar
        service, updated_credentials = authenticate_google_calendar(credentials)
        
        # Si hay credenciales actualizadas, guardarlas en la sesión
        if updated_credentials:
            session['credentials'] = updated_credentials
            session.modified = True
        
        if not service:
            # En lugar de usar los datos del form, redirigir y empezar de nuevo
            logger.info("Redirigiendo a autenticación con Google Calendar - NO SE GUARDA CONFIG")
            flash('Se requiere autenticación. Por favor inténtelo nuevamente después de iniciar sesión.', 'info')
            return redirect(url_for('auth', next=url_for('dashboard')))
        
        timezone = get_calendar_timezone(service)
        events = get_events(service, start_date, end_date, timezone)
        
        if events is None:
            flash('Error al obtener eventos del calendario', 'error')
            logger.error(f"Error al obtener eventos para el rango {start_date} - {end_date}")
            return redirect(url_for('dashboard'))
            
        # Procesar la configuración recibida directamente
        try:
            config = json.loads(config_data) if isinstance(config_data, str) else config_data
            logger.info(f"CONFIGURACIÓN PARSEADA: {config}")
            
            # Verificar campos obligatorios
            default_config = get_default_config()
            for key in default_config:
                if key not in config:
                    logger.warning(f"Campo '{key}' faltante, usando valor por defecto: {default_config[key]}")
                    config[key] = default_config[key]
        except Exception as e:
            logger.error(f"ERROR FATAL AL PROCESAR CONFIGURACIÓN: {e}")
            logger.error(f"DATOS QUE CAUSARON ERROR: {config_data}")
            config = get_default_config()
        
        # Registrar configuración final
        logger.info(f"CONFIGURACIÓN FINAL A USAR: {json.dumps(config, indent=2)}")
        
        # Log de valores específicos importantes
        logger.info(f"Usando horario: {config['work_start_time']} - {config['work_end_time']}")
        logger.info(f"Servicio predeterminado: {config['default_service']}")
        logger.info(f"Etiquetas de color habilitadas: {config.get('use_color_tags', False)}")
        
        # Para verificación adicional, añadir análisis del valor original vs. procesado 
        if config_data and isinstance(config_data, str):
            try:
                original_config = json.loads(config_data)
                for key in ['default_service', 'ooo_service', 'focus_time_service', 'unlabeled_service']:
                    if key in original_config and key in config:
                        if original_config[key] != config[key]:
                            logger.warning(f"¡DIFERENCIA DETECTADA en '{key}'! Original: '{original_config[key]}', Actual: '{config[key]}'")
            except:
                pass
        
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
        
        # Añadir información resumida de la configuración usada para mostrarla en los resultados
        config_summary = {
            'work_time': f"{config['work_start_time']} a {config['work_end_time']}",
            'lunch': f"{config['lunch_duration_minutes']} min",
            'default_service': config['default_service'],
            'use_color_tags': config['use_color_tags']
        }
        
        return render_template(
            'results.html', 
            weekly_summary=processed_summary,
            period_summary=period_summary,
            start_date=start_date.strftime('%d/%m/%Y'),
            end_date=end_date.strftime('%d/%m/%Y'),
            total_hours=format_timedelta(grand_total_time),
            config_summary=config_summary  # Pasar el resumen de configuración
        )
        
    except Exception as e:
        error_msg = f'Error inesperado: {str(e)}'
        flash(error_msg, 'error')
        logger.exception(f"Error en calculate: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/calculate_with_session', methods=['GET'])
def calculate_with_session():
    """DEPRECATED - Ya no se usa este método"""
    logger.warning("DEPRECATED: calculate_with_session fue llamado pero ya no se utiliza")
    flash('La sesión ha expirado. Por favor intente nuevamente.', 'error')
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
            # Intentar serializar para ver si es JSONifiable
            json.dumps({key: value})
            session_data[key] = value
        except TypeError:
            # Si no es serializable, incluir una representación en cadena
            session_data[key] = str(value)
    
    return jsonify({
        'session': session_data,
        'session_id': session.sid if hasattr(session, 'sid') else None,
        'timestamp': datetime.now().isoformat()
    })

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