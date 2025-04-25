# Despliegue con Docker

Este documento explica cómo desplegar Calendar Work Time Tracker utilizando Docker y Docker Compose.

## Prerrequisitos

- Docker instalado en el servidor
- Docker Compose instalado en el servidor
- Credenciales de Google para acceder a Google Calendar (archivo `credentials.json` o variables de entorno)
- No es necesario tener el `token.pickle` previamente, se generará automáticamente

## Pasos para el despliegue

### 1. Preparar el archivo .env

Copia el archivo `.env.example` a `.env` y edita las variables según tus necesidades:

```bash
cp .env.example .env
nano .env
```

Asegúrate de configurar una `SECRET_KEY` segura y valores adecuados para tu entorno.
Mantén `FLASK_ENV=production` para el modo de autenticación sin navegador, recomendado para servidores.

### 2. Configurar las credenciales de Google Calendar

Tienes dos opciones para configurar las credenciales:

#### Opción 1: Usando el archivo credentials.json

El archivo `credentials.json` debe estar en el directorio raíz del proyecto. Este archivo contiene las credenciales de Google para acceder a Google Calendar.

#### Opción 2: Usando variables de entorno (recomendado para producción)

Añade las siguientes variables al archivo `.env`:

```
GOOGLE_CLIENT_ID=tu_client_id
GOOGLE_CLIENT_SECRET=tu_client_secret
GOOGLE_REDIRECT_URI=https://tu-dominio.com
```

### 3. Construye y ejecuta el contenedor

Para construir y ejecutar la aplicación usando Docker Compose:

```bash
docker-compose up -d
```

Este comando:
- Construirá la imagen Docker si no existe
- Creará y ejecutará el contenedor en modo desconectado (background)
- Montará los volúmenes necesarios para persistencia de datos

### 4. Verificar el estado

Para verificar que la aplicación está funcionando correctamente:

```bash
docker-compose ps
docker logs calendar-work-time-tracker
```

La aplicación debería estar disponible en `http://tu-servidor:5000`

### 5. Autenticación inicial

Cuando ejecutes la aplicación por primera vez en modo producción, necesitarás completar el flujo de autenticación de Google sin navegador:

1. Revisa los logs del contenedor para encontrar la URL de autenticación:
   ```bash
   docker logs calendar-work-time-tracker | grep "vaya a la siguiente URL"
   ```

2. Copia esa URL y ábrela en un navegador en tu computadora local (no en el servidor)

3. Completa el proceso de autenticación con Google

4. Google te proporcionará un código de autorización

5. Introduce ese código en la consola del contenedor:
   ```bash
   docker attach calendar-work-time-tracker
   ```
   (Pega el código y presiona Enter. Puedes desconectarte después con Ctrl+P, Ctrl+Q)

Una vez completado este proceso, se generará un archivo `token.pickle` que se guardará en el volumen montado y se usará para futuras autenticaciones sin necesidad de repetir estos pasos.

### 6. Actualización de la aplicación

Para actualizar la aplicación cuando hay cambios en el código:

```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

### 7. Respaldo de datos

Los siguientes archivos son importantes y deben ser respaldados:

- `.env`: Configuración de la aplicación e incluye credenciales de Google si usas variables de entorno
- `credentials.json`: Credenciales de Google Calendar (si usas este método)
- `token.pickle`: Token de autenticación (generado automáticamente)
- `logs/`: Directorio de logs

### 8. Configuración con Nginx (Opcional)

Para exponer la aplicación a través de un dominio con HTTPS, puedes configurar Nginx como proxy inverso. El archivo `nginx-config.conf` proporciona una configuración de ejemplo.

### Solución de problemas

#### El token.pickle no se genera

Si tienes problemas para generar el token.pickle:

1. Asegúrate de que el servidor tiene acceso a internet
2. Verifica que puedes acceder a la aplicación desde un navegador
3. Comprueba que el directorio donde se ejecuta docker-compose tiene permisos de escritura

#### Problemas con credenciales

Si tienes problemas con la autenticación:

1. Verifica que estás usando las credenciales correctas (variables de entorno o archivo)
2. Asegúrate de que las URIs de redirección en Google Cloud Console son correctas
3. Prueba eliminando el token.pickle y volviendo a autenticarte

```bash
rm token.pickle
docker-compose restart
```

#### No puedo ver la URL de autenticación

Si no puedes ver la URL de autenticación en los logs:

```bash
# Ver los logs completos
docker logs calendar-work-time-tracker

# O filtrar específicamente por mensajes de autenticación
docker logs calendar-work-time-tracker | grep -A 10 "Entorno de producción detectado"
``` 