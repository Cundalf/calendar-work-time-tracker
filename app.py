from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, time
import os
from dotenv import load_dotenv
from calendar_time_tracker import authenticate_google_calendar, get_calendar_timezone, get_events, calculate_weekly_summary
import json

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

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
            return redirect(url_for('dashboard'))
        
        service = authenticate_google_calendar()
        if not service:
            flash('Error al autenticar con Google Calendar', 'error')
            return redirect(url_for('dashboard'))
        
        timezone = get_calendar_timezone(service)
        events = get_events(service, start_date, end_date, timezone)
        
        if events is None:
            flash('Error al obtener eventos del calendario', 'error')
            return redirect(url_for('dashboard'))
        
        # Obtener configuración del localStorage (se enviará desde el frontend)
        config_data = request.form.get('config')
        if not config_data:
            flash('Error: No se encontró la configuración del usuario', 'error')
            return redirect(url_for('dashboard'))
            
        config = json.loads(config_data)
        
        weekly_summary = calculate_weekly_summary(
            events, start_date, end_date, timezone,
            datetime.strptime(config['work_start_time'], '%H:%M').time(),
            datetime.strptime(config['work_end_time'], '%H:%M').time(),
            [0, 1, 2, 3, 4]  # Lunes a Viernes
        )
        
        return render_template('results.html', weekly_summary=weekly_summary)
        
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True) 