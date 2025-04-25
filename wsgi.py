"""
Punto de entrada WSGI para Calendar Work Time Tracker
Permite ejecutar la aplicación con Gunicorn u otro servidor WSGI
"""
import os
from app import app

# Asegurarse de que no haya problemas de caché
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Logs adicionales en startup
if os.environ.get('FLASK_ENV') == 'production':
    print("Arrancando en modo producción")
else:
    print("Arrancando en modo desarrollo")

if __name__ == "__main__":
    app.run() 