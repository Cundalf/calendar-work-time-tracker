# Guía de Despliegue en Producción

Esta guía detalla los pasos para desplegar Calendar Work Time Tracker en un servidor de producción.

## Prerrequisitos

- Servidor Linux (Ubuntu/Debian recomendado)
- Python 3.8+ instalado
- Nginx
- Dominio configurado (opcional, pero recomendado)

## 1. Preparar el Servidor

```bash
# Actualizar el sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias
sudo apt install -y python3-pip python3-venv nginx git
```

## 2. Clonar el Repositorio

```bash
# Elegir ubicación adecuada
sudo mkdir -p /var/www/calendar-app
sudo chown $USER:$USER /var/www/calendar-app

# Clonar repositorio
git clone https://github.com/tu-usuario/calendar-work-time-tracker.git /var/www/calendar-app
cd /var/www/calendar-app
```

## 3. Configurar Entorno Virtual y Dependencias

```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## 4. Configurar Variables de Entorno

```bash
# Copiar plantilla
cp .env.example .env

# Editar con valores reales
nano .env
```

Es **crítico** cambiar la `SECRET_KEY` por una cadena aleatoria y segura:

```bash
# Generar clave segura
python -c "import secrets; print(secrets.token_hex(24))"
```

## 5. Configurar Credenciales de Google Calendar

1. Copia tu archivo `credentials.json` en el directorio raíz
2. La primera vez que se ejecute la aplicación, deberás seguir el flujo de autorización

## 6. Configurar Nginx

```bash
# Copiar archivo de configuración
sudo cp nginx-config.conf /etc/nginx/sites-available/calendar-app

# Editar con valores correctos
sudo nano /etc/nginx/sites-available/calendar-app

# Activar configuración
sudo ln -s /etc/nginx/sites-available/calendar-app /etc/nginx/sites-enabled/
sudo nginx -t  # Verificar sintaxis
sudo systemctl restart nginx
```

## 7. Configurar Servicio Systemd

```bash
# Copiar archivo de servicio
sudo cp calendar-app.service /etc/systemd/system/

# Editar con rutas correctas
sudo nano /etc/systemd/system/calendar-app.service

# Activar servicio
sudo systemctl daemon-reload
sudo systemctl enable calendar-app
sudo systemctl start calendar-app
sudo systemctl status calendar-app  # Verificar estado
```

## 8. Seguridad Adicional

### Configurar HTTPS con Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tudominio.com
```

### Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 9. Monitoreo y Logs

- **Logs de aplicación**: `/var/www/calendar-app/logs/app.log`
- **Logs de Nginx**: `/var/log/nginx/calendar-app-access.log` y `/var/log/nginx/calendar-app-error.log`
- **Logs de Systemd**: `sudo journalctl -u calendar-app`

## 10. Actualización de la Aplicación

```bash
cd /var/www/calendar-app
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart calendar-app
```

## 11. Respaldo de Datos

Es importante hacer respaldo de:
- Archivo `.env`
- Archivo `credentials.json`
- Archivo `token.pickle`

Estos archivos contienen la configuración y la autenticación con Google Calendar.

## 12. Configuración para Diferentes Ambientes

La aplicación distingue entre ambientes de desarrollo y producción mediante la variable `FLASK_ENV`.

- **Producción**: `FLASK_ENV=production` (valor por defecto)
- **Desarrollo**: `FLASK_ENV=development` (para pruebas locales)

## Solución de Problemas

### Permisos
```bash
sudo chown -R www-data:www-data /var/www/calendar-app
sudo chmod -R 755 /var/www/calendar-app
```

### Problemas con la autenticación de Google
Si hay problemas con la autenticación:
```bash
# Eliminar token actual
rm /var/www/calendar-app/token.pickle

# Luego ejecutar la aplicación y completar la autenticación
```

### La aplicación no inicia
```bash
# Verificar logs
sudo journalctl -u calendar-app -n 50
``` 