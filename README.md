# Calendar Work Time Tracker

Una aplicación web para analizar y visualizar el tiempo dedicado a diferentes tipos de trabajo en tu calendario de Google.

## Características

- **Análisis por Etiquetas de Color**: Categoriza automáticamente tus eventos según los colores que uses en Google Calendar
- **Vista por Semanas**: Visualiza tiempo dedicado a cada categoría de trabajo por semana
- **Resumen del Período**: Obtén totales y porcentajes para un intervalo de fechas completo
- **Configuración Personalizada**: Define tus propias categorías y horarios laborales
- **Autenticación Web**: Proceso intuitivo de autenticación con Google Calendar a través del navegador

## Prerrequisitos

- Python 3.8+ 
- Cuenta de Google y acceso a Google Calendar
- Credenciales de API de Google (ver instrucciones de instalación)

## Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/calendar-work-time-tracker.git
cd calendar-work-time-tracker
```

### 2. Crear y Activar Entorno Virtual

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Credenciales de Google

#### 4.1 Configuración en Desarrollo (usando credentials.json)

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la API de Google Calendar para tu proyecto
4. Crea Credenciales OAuth:
   - Ve a "APIs y servicios" -> "Credenciales"
   - Crea un ID de cliente OAuth para **Aplicación Web** (importante)
   - Configura las URI de redireccionamiento: `http://localhost:5000/oauth2callback`
   - Descarga el archivo JSON de credenciales y renómbralo a `credentials.json`
   - Coloca este archivo en la raíz del proyecto

#### 4.2 Configuración en Producción (usando variables de entorno)

Para entornos de producción, es más seguro y flexible usar variables de entorno en lugar del archivo `credentials.json`:

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la API de Google Calendar para tu proyecto
4. Crea Credenciales OAuth para Web:
   - Ve a "APIs y servicios" -> "Credenciales"
   - Crea un ID de cliente OAuth para **Aplicación Web** (importante)
   - Configura las URI de redireccionamiento: `https://tu-dominio.com/oauth2callback`
5. Anota el Client ID y Client Secret
6. Configura las siguientes variables de entorno en tu servidor:
   ```
   GOOGLE_CLIENT_ID=tu_client_id
   GOOGLE_CLIENT_SECRET=tu_client_secret
   GOOGLE_REDIRECT_URI=https://tu-dominio.com/oauth2callback
   ```

La aplicación intentará primero usar las variables de entorno, y si no están disponibles, buscará el archivo `credentials.json`.

### 5. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con el siguiente contenido:

```
SECRET_KEY=tu_clave_secreta_para_flask
FLASK_ENV=production  # Cambiar a 'development' para desarrollo local
```

### 6. Ejecutar la Aplicación

```bash
python app.py
```

La aplicación estará disponible en `http://localhost:5000`

### 7. Autenticación con Google Calendar

La aplicación utiliza un flujo de autenticación web unificado que funciona tanto en entornos de desarrollo como de producción:

1. Al acceder por primera vez o cuando se necesite autorización, verás una página de autenticación
2. Haz clic en el botón para iniciar el proceso de autorización con Google
3. Se abrirá una ventana de Google donde deberás seleccionar tu cuenta y autorizar el acceso
4. Después de autorizar, serás redirigido automáticamente de vuelta a la aplicación
5. La aplicación guardará el token para futuros accesos y no necesitarás repetir este proceso hasta que el token expire

## Cómo Usar la Aplicación

1. **Inicio y Autenticación**: 
   - Al acceder por primera vez, se te solicitará autorizar el acceso a tu Google Calendar.

2. **Configuración Personal**:
   - En la sección de Configuración, personaliza:
     - Horario laboral (hora de inicio y fin)
     - Asignación de colores de calendario a categorías de trabajo
     - Comportamiento de tipos especiales de eventos

3. **Generar Reportes**:
   - En la sección Dashboard:
     - Selecciona un rango de fechas
     - Haz clic en "Calcular" para generar el reporte
     - Visualiza los resultados organizados por semana y totales del período

4. **Interpretar Resultados**:
   - Revisa el tiempo dedicado a cada categoría
   - Analiza la distribución porcentual de tu tiempo
   - Identifica patrones y oportunidades de mejora

## Estructura del Proyecto

- `app.py`: Aplicación principal de Flask
- `calendar_time_tracker.py`: Núcleo de la funcionalidad de procesamiento de eventos
- `templates/`: Plantillas HTML para la interfaz web
- `static/`: Archivos estáticos (CSS, JavaScript, imágenes)
- `requirements.txt`: Dependencias del proyecto

## Solución de Problemas

- **Errores de Autenticación**: Si experimentas problemas con la autenticación, elimina el archivo `token.pickle` y reinicia la aplicación.
- **Resultados Inesperados**: Verifica que la configuración de colores y categorías corresponda con la forma en que organizas tu calendario.
- **Problemas de Instalación**: Asegúrate de que todas las dependencias estén correctamente instaladas.
- **Problemas de Redirección**: Asegúrate de que la URL de redirección en Google Cloud Console coincida exactamente con la configurada en tu aplicación.

## Documentación Adicional

- [legacy/README.md](legacy/README.md): Información sobre la versión anterior basada en scripts de línea de comandos.
- [DESARROLLO.md](DESARROLLO.md): Historia del desarrollo del proyecto y cómo fue creado utilizando IA y la metodología Vibe Coding.
- [README.docker.md](README.docker.md): Instrucciones detalladas para desplegar con Docker.
- [README.deployment.md](README.deployment.md): Guía completa para despliegue en producción.

## Licencia

Este proyecto está disponible como software de código abierto.

---

*Nota: Esta aplicación accede a tus datos de calendario únicamente de forma local y no almacena información en servidores remotos.*

