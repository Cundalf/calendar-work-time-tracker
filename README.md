# Calendar Work Time Tracker (Web App)

## Descripción General

Calendar Work Time Tracker es una aplicación web construida con Flask que te permite analizar y visualizar cómo distribuyes tu tiempo laboral basándose en los eventos de tu Google Calendar. Esta aplicación procesa los eventos según etiquetas de color o tipos de eventos (como Fuera de oficina, Tiempo de concentración) y genera reportes visuales que muestran las horas dedicadas a cada categoría o servicio.

## Características Principales

- **Interfaz Web Intuitiva**: Accede a todas las funcionalidades a través de una interfaz web moderna y fácil de usar.
- **Autenticación con Google Calendar**: Conexión segura con tu cuenta de Google para acceder a los eventos de tu calendario.
- **Personalización de Configuración**: Define tus propias categorías y asócialas a los colores de tu calendario.
- **Reportes Detallados**: Visualiza un desglose semanal y total del tiempo dedicado a cada categoría.
- **Filtros por Fechas**: Selecciona períodos específicos para analizar.
- **Personalización de Horario Laboral**: Define tus propias horas de trabajo.
- **Persistencia de Configuración**: Guarda tus preferencias en el navegador.

## Prerrequisitos

- **Python 3.8 o superior**: Asegúrate de tener Python instalado en tu sistema.
- **Cuenta de Google**: Necesitas una cuenta de Google para acceder a Google Calendar.
- **Acceso a Google Cloud Console**: Necesitarás crear un proyecto y habilitar la API de Google Calendar.

## Instalación y Configuración

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/calendar-work-time-tracker.git
cd calendar-work-time-tracker
```

### 2. Configurar Entorno Virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Linux/macOS:
source venv/bin/activate
# En Windows:
venv\Scripts\activate
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
   - Crea un ID de cliente OAuth para aplicación web
   - Configura las URI de redireccionamiento (generalmente `http://localhost:5000` para desarrollo)
   - Descarga el archivo JSON de credenciales y renómbralo a `credentials.json`
   - Coloca este archivo en la raíz del proyecto

#### 4.2 Configuración en Producción (usando variables de entorno)

Para entornos de producción, es más seguro y flexible usar variables de entorno en lugar del archivo `credentials.json`:

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la API de Google Calendar para tu proyecto
4. Crea Credenciales OAuth para Web:
   - Ve a "APIs y servicios" -> "Credenciales"
   - Crea un ID de cliente OAuth para aplicación web
   - Configura las URI de redireccionamiento con la URL de tu aplicación en producción
5. Anota el Client ID y Client Secret
6. Configura las siguientes variables de entorno en tu servidor:
   ```
   GOOGLE_CLIENT_ID=tu_client_id
   GOOGLE_CLIENT_SECRET=tu_client_secret
   GOOGLE_REDIRECT_URI=https://tu-dominio.com
   ```

La aplicación intentará primero usar las variables de entorno, y si no están disponibles, buscará el archivo `credentials.json`.

### 5. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con el siguiente contenido:

```
SECRET_KEY=tu_clave_secreta_para_flask
```

### 6. Ejecutar la Aplicación

```bash
python app.py
```

La aplicación estará disponible en `http://localhost:5000`

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

## Documentación Adicional

- [legacy/README.md](legacy/README.md): Información sobre la versión anterior basada en scripts de línea de comandos.
- [DESARROLLO.md](DESARROLLO.md): Historia del desarrollo del proyecto y cómo fue creado utilizando IA y la metodología Vibe Coding.

## Licencia

Este proyecto está disponible como software de código abierto.

---

*Nota: Esta aplicación accede a tus datos de calendario únicamente de forma local y no almacena información en servidores remotos.*

