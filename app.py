from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, time
import os
from dotenv import load_dotenv
from calendar_time_tracker import authenticate_google_calendar, get_calendar_timezone, get_events, calculate_weekly_summary

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Modelos de la base de datos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    work_start_time = db.Column(db.Time, default=time(9, 0))
    work_end_time = db.Column(db.Time, default=time(18, 0))
    default_service = db.Column(db.String(100), default='SERVICIO PRINCIPAL')
    ooo_service = db.Column(db.String(100), default='FUERA DE OFICINA')
    focus_time_service = db.Column(db.String(100), default='TIEMPO DE CONCENTRACIÓN')
    use_color_tags = db.Column(db.Boolean, default=False)
    color_tags = db.Column(db.JSON, default={})

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rutas
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/config')
@login_required
def config():
    return render_template('config.html')

@app.route('/calculate', methods=['POST'])
@login_required
def calculate():
    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    
    service = authenticate_google_calendar()
    if not service:
        flash('Error al autenticar con Google Calendar', 'error')
        return redirect(url_for('dashboard'))
    
    timezone = get_calendar_timezone(service)
    events = get_events(service, start_date, end_date, timezone)
    
    if events is None:
        flash('Error al obtener eventos del calendario', 'error')
        return redirect(url_for('dashboard'))
    
    weekly_summary = calculate_weekly_summary(
        events, start_date, end_date, timezone,
        current_user.work_start_time, current_user.work_end_time,
        [0, 1, 2, 3, 4]  # Lunes a Viernes
    )
    
    return render_template('results.html', weekly_summary=weekly_summary)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 