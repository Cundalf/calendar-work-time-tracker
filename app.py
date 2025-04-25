# Standard library imports
import os
import json
from datetime import datetime, time, timedelta
from collections import defaultdict

# Third-party imports
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from loguru import logger

# Local application imports
from calendar_time_tracker import (
    authenticate_google_calendar, 
    get_calendar_timezone, 
    get_events, 
    calculate_weekly_summary, 
    format_timedelta
)

# Cargar variables de entorno
load_dotenv()

# Configuración de la aplicación
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clave_por_defecto_no_usar_en_produccion')

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
logger.add(lambda msg: print(msg), level="WARNING", format=log_format)  # Solo warnings y errors a consola

# Definir horario predeterminado (para usar time explícitamente)
DEFAULT_WORK_START = time(9, 0)  # 9:00 AM
DEFAULT_WORK_END = time(17, 0)   # 5:00 PM

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

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        
        if end_date < start_date:
            flash('La fecha de fin no puede ser anterior a la fecha de inicio', 'error')
            logger.warning(f"Intento de búsqueda con fechas inválidas: start={start_date}, end={end_date}")
            return redirect(url_for('dashboard'))
        
        service = authenticate_google_calendar()
        if not service:
            flash('Error al autenticar con Google Calendar', 'error')
            logger.error("Falló la autenticación con Google Calendar")
            return redirect(url_for('dashboard'))
        
        timezone = get_calendar_timezone(service)
        events = get_events(service, start_date, end_date, timezone)
        
        if events is None:
            flash('Error al obtener eventos del calendario', 'error')
            logger.error(f"Error al obtener eventos para el rango {start_date} - {end_date}")
            return redirect(url_for('dashboard'))
        
        # Obtener configuración del localStorage (se enviará desde el frontend)
        config_data = request.form.get('config')
        if not config_data:
            flash('Error: No se encontró la configuración del usuario', 'error')
            logger.error("Configuración de usuario no encontrada")
            return redirect(url_for('dashboard'))
            
        config = json.loads(config_data)
        
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