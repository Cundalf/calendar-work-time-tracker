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

1. Crea un proyecto en la [Google Cloud Console](https://console.cloud.google.com/)
2. Habilita la API de Google Calendar
3. Crea credenciales OAuth para **Aplicación Web**
4. Configura la URI de redirección como `https://tu-dominio.com/oauth2callback`
5. Descarga el archivo JSON de credenciales y renómbralo a `credentials.json`
6. Coloca este archivo en el directorio raíz del proyecto

#### Opción 2: Usando variables de entorno (recomendado para producción)

Añade las siguientes variables al archivo `.env`:

```
GOOGLE_CLIENT_ID=tu_client_id
GOOGLE_CLIENT_SECRET=tu_client_secret
GOOGLE_REDIRECT_URI=https://tu-dominio.com/oauth2callback
```

Asegúrate de que la URI de redirección coincida exactamente con la configurada en Google Cloud Console.

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

La primera vez que accedas a la aplicación desde el navegador, se te mostrará una pantalla de autenticación:

1. Haz clic en el botón "Autorizar acceso a Google Calendar"
2. Se abrirá la página de Google para que selecciones tu cuenta y autorices el acceso
3. Una vez completada la autorización, Google te redirigirá de vuelta a la aplicación
4. La aplicación guardará el token de autenticación automáticamente

El token se almacenará en el volumen montado y no necesitarás repetir este proceso hasta que el token expire (generalmente después de varias semanas o meses).

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
3. Verifica que la aplicación es accesible desde el exterior en la URL configurada
4. Prueba eliminando el token.pickle y volviendo a autenticarte

```bash
rm token.pickle
docker-compose restart
```

#### Errores de redirección

Si recibes errores relacionados con URI de redirección:

1. Verifica que `GOOGLE_REDIRECT_URI` coincida exactamente con lo configurado en Google Cloud Console
2. Si estás usando un proxy inverso como Nginx, asegúrate de que pasa correctamente las solicitudes a tu contenedor
3. Verifica que estás usando HTTPS si tu ruta de redirección usa HTTPS
