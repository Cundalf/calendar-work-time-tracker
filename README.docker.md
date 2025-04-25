# Despliegue con Docker

Este documento explica cómo desplegar Calendar Work Time Tracker utilizando Docker y Docker Compose.

## Prerrequisitos

- Docker instalado en el servidor
- Docker Compose instalado en el servidor
- Archivo `credentials.json` (obligatorio)
- No es necesario tener el `token.pickle` previamente, se generará automáticamente

## Pasos para el despliegue

### 1. Preparar el archivo .env

Copia el archivo `.env.example` a `.env` y edita las variables según tus necesidades:

```bash
cp .env.example .env
nano .env
```

Asegúrate de configurar una `SECRET_KEY` segura y valores adecuados para tu entorno.

### 2. Asegúrate de tener el archivo credentials.json

El archivo `credentials.json` debe estar en el directorio raíz del proyecto. Este archivo contiene las credenciales de Google para acceder a Google Calendar.

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

Cuando accedas por primera vez a la aplicación, necesitarás completar el flujo de autenticación de Google:

1. Accede a la aplicación a través del navegador en `http://tu-servidor:5000`
2. Se te redirigirá automáticamente al flujo de autenticación de Google
3. Completa la autenticación y autoriza el acceso a tu calendario
4. El archivo `token.pickle` se generará automáticamente y se almacenará en el volumen montado

**Nota importante**: Para que este flujo funcione, el servidor debe tener acceso a internet y el usuario debe poder completar la autenticación a través del navegador. El contenedor está configurado para persistir el token.pickle automáticamente.

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

- `credentials.json`: Credenciales de Google Calendar
- `token.pickle`: Token de autenticación (generado automáticamente)
- `.env`: Configuración de la aplicación
- `logs/`: Directorio de logs

### 8. Configuración con Nginx (Opcional)

Para exponer la aplicación a través de un dominio con HTTPS, puedes configurar Nginx como proxy inverso. El archivo `nginx-config.conf` proporciona una configuración de ejemplo.

### Solución de problemas

#### El token.pickle no se genera

Si tienes problemas para generar el token.pickle:

1. Asegúrate de que el servidor tiene acceso a internet
2. Verifica que puedes acceder a la aplicación desde un navegador
3. Comprueba que el directorio donde se ejecuta docker-compose tiene permisos de escritura
4. Revisa los logs para ver posibles errores:
   ```bash
   docker logs calendar-work-time-tracker
   ```

#### Permisos de archivos

Si hay problemas con permisos de archivos dentro del contenedor:

```bash
# Asegurar que los archivos tienen los permisos adecuados
chmod 644 credentials.json .env
chmod -R 777 logs
# Si ya tienes un token.pickle:
chmod 664 token.pickle
```

#### Logs del contenedor

Para ver los logs del contenedor:

```bash
docker logs -f calendar-work-time-tracker
```

#### Entrar al contenedor

Para entrar al contenedor y depurar problemas:

```bash
docker exec -it calendar-work-time-tracker bash
``` 