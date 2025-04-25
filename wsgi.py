"""
Punto de entrada WSGI para Calendar Work Time Tracker
Permite ejecutar la aplicación con Gunicorn u otro servidor WSGI
"""
from app import app

if __name__ == "__main__":
    app.run() 