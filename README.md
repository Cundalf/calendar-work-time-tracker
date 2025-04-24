# Google Calendar Time Tracker Scripts

## Descripción General

Este proyecto contiene un conjunto de scripts de Python diseñados para leer eventos de tu Google Calendar, categorizar el tiempo según las **etiquetas de color** asignadas a los eventos o el tipo de evento (Fuera de oficina, Tiempo de concentración), y generar un resumen semanal y total del periodo consultado, mostrando las horas dedicadas a cada servicio definido.

Está pensado para usuarios que desean analizar cómo distribuyen su tiempo laboral basándose en la organización de su calendario.

## Scripts Incluidos

Este proyecto consta de dos archivos Python principales:

1.  **`get_calendar_colors.py`**:
    * Un script auxiliar que se ejecuta una vez para ayudarte a encontrar los IDs numéricos de las etiquetas de color que usas en tu Google Calendar. Necesitarás estos IDs para configurar el script principal.
2.  **`calendar_time_tracker.py`**:
    * El script principal que realiza el análisis y cálculo del tiempo. Es el que ejecutarás regularmente para obtener tus reportes. Debes configurarlo editando su contenido.

## Prerrequisitos

* **Python 3:** Asegúrate de tener Python 3 instalado en tu sistema. ([https://www.python.org/](https://www.python.org/))
* **Archivos del Script:** Debes tener los archivos `get_calendar_colors.py` y `calendar_time_tracker.py`.
* **Cuenta de Google:** Necesitas una cuenta de Google para acceder a Google Calendar y Google Cloud Console.
* **Acceso a Google Cloud Console:** Necesitarás crear un proyecto y habilitar la API de Google Calendar para obtener un archivo de credenciales.

## Configuración Inicial (Pasos Detallados)

Sigue estos pasos **una sola vez** para preparar tu entorno.

### 1. Configuración de Google Cloud y Credenciales

Necesitas autorizar a los scripts para que lean tu calendario de forma segura usando OAuth 2.0.

1.  **Ve a Google Cloud Console:** [https://console.cloud.google.com/](https://console.cloud.google.com/)
2.  **Crea un Proyecto:** Si no tienes uno, crea un nuevo proyecto (puedes llamarlo "Calendar Time Tracker" o similar).
3.  **Habilita la API de Google Calendar:**
    * En el menú de navegación, ve a "APIs y servicios" -> "Biblioteca".
    * Busca "Google Calendar API" y haz clic en "Habilitar".
4.  **Crea Credenciales OAuth:**
    * Ve a "APIs y servicios" -> "Credenciales".
    * Haz clic en "+ CREAR CREDENCIALES" -> "ID de cliente de OAuth".
    * Si te pide configurar una "Pantalla de consentimiento de OAuth", hazlo:
        * Elige "Externo" (o "Interno" si usas Google Workspace y solo tú lo usarás).
        * Ingresa un nombre para la aplicación (ej. "Calendar Tracker Script"), tu correo electrónico de asistencia y guarda. No necesitas añadir scopes aquí.
    * Ahora, vuelve a "Credenciales" -> "+ CREAR CREDENCIALES" -> "ID de cliente de OAuth".
    * Selecciona "Tipo de aplicación" -> **"Aplicación de escritorio"**.
    * Dale un nombre (ej. "Calendar Tracker Desktop Client").
    * Haz clic en "CREAR".
5.  **Descarga `credentials.json`:**
    * Aparecerá una ventana con tu ID de cliente y secreto. Haz clic en **"DESCARGAR JSON"**.
    * **IMPORTANTE:** Renombra el archivo descargado a exactamente **`credentials.json`** y guárdalo en el **mismo directorio** donde tienes los scripts (`.py`). **¡No compartas este archivo con nadie!**

### 2. Crear un Entorno Virtual (Recomendado)

Para evitar conflictos con otros paquetes de Python en tu sistema, es **altamente recomendable** usar un entorno virtual (`venv`).

1.  **Abre tu terminal o línea de comandos.**
2.  **Navega** al directorio donde guardaste `credentials.json` y los scripts `.py`.
3.  **Crea el entorno virtual:**
    ```bash
    # En Linux/macOS
    python3 -m venv venv
    # En Windows (puede ser python en lugar de python3)
    python -m venv venv
    ```
    Esto creará una carpeta llamada `venv`.
4.  **Activa el entorno virtual:**
    * **Linux/macOS:** `source venv/bin/activate`
    * **Windows (CMD):** `venv\Scripts\activate.bat`
    * **Windows (PowerShell):** `venv\Scripts\Activate.ps1` (Si falla, puede que necesites ejecutar `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` primero en PowerShell).
    * Sabrás que está activo porque verás `(venv)` al principio del prompt de tu terminal.

### 3. Instalar Dependencias

Con el entorno virtual **activo**, instala las librerías de Python necesarias ejecutando este comando en tu terminal:

```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib pytz python-dateutil tzlocal
```

## Configuración del Script Principal

La configuración principal se realiza **editando el archivo `calendar_time_tracker.py`**.

### 1. Obtener IDs de Color de Etiquetas (Usando `get_calendar_colors.py`)

Antes de configurar el script principal, necesitas saber qué ID numérico corresponde a cada etiqueta de color que usas en Google Calendar.

1.  Asegúrate de que tu entorno virtual esté **activo** y que estés en el directorio correcto (donde están `credentials.json` y los scripts `.py`).
2.  Ejecuta el script auxiliar:
    ```bash
    python get_calendar_colors.py
    ```
3.  **Autorización:** La primera vez, se abrirá tu navegador para que autorices al script a acceder (solo lectura) a tu calendario. Concede los permisos. Esto creará un archivo `token_colors.pickle` (que es independiente del token del script principal).
4.  **Salida:** El script imprimirá una tabla con los IDs de color (números del '1' al '11' generalmente), un nombre común del color estándar y los códigos de color hexadecimales.
5.  **Identifica tus Etiquetas:** Mira los colores que usas para tus etiquetas personalizadas en Google Calendar (ej. "Rojo Tomate", "Verde Salvia", etc.) y busca el **ID** numérico correspondiente en la tabla impresa. Anota qué ID corresponde a cada una de tus etiquetas/servicios.

### 2. Configurar `calendar_time_tracker.py`

1.  Abre el archivo `calendar_time_tracker.py` con un editor de texto o un editor de código Python.
2.  Localiza la sección que empieza con `# --- CONFIGURACIÓN ---` cerca del principio del archivo.
3.  **Edita la variable `COLOR_ID_TO_SERVICE`:**
    * Esta es la configuración **más importante** y vincula tus etiquetas de color con los nombres de tus servicios.
    * Es un diccionario de Python. Debes modificarlo para que cada entrada sea: `'ID_Color': 'Nombre del Servicio'`
    * Usa los IDs numéricos (como **strings**, ej. `'8'`) que obtuviste del script `get_calendar_colors.py`.
    * Asigna el nombre exacto (como **string**, ej. `'Infraestructura'`) que quieres que aparezca en el reporte para esa etiqueta de color.
    * **Ejemplo:**
        ```python
        COLOR_ID_TO_SERVICE = {
            '8': 'Infraestructura',  # Color Grafito (ID 8)
            '2': 'Capacitaciones',   # Color Salvia (ID 2)
            '11': 'Gestión',         # Color Tomate (ID 11)
            '5': 'Proyecto Banana',  # Color Banana (ID 5)
            # ... añade o modifica según TUS etiquetas y servicios ...
        }
        ```
4.  **Edita las variables de Servicios por Tipo:**
    * `OOO_SERVICE`: Cambia el string `'FUERA DE OFICINA'` por el nombre que quieras para los eventos de tipo "Fuera de oficina" que *no* tengan una etiqueta de color asignada.
    * `FOCUS_TIME_SERVICE`: Cambia el string `'TIEMPO CONCENTRACION (Sin Et.)'` por el nombre que quieras para los eventos de tipo "Tiempo de concentración" que *no* tengan una etiqueta de color asignada.
    * `DEFAULT_SERVICE`: Cambia el string `'RSG (Default & Libre)'` por el nombre que quieras para:
        * Eventos "normales" que *no* tengan una etiqueta de color asignada.
        * El tiempo calculado como "libre" dentro de tu horario laboral.
5.  **Edita la variable `LUNCH_DURATION_MINUTES`:**
    * Cambia el número `60` por la cantidad de minutos que dura tu almuerzo habitualmente (ej. `90` para 1.5 horas, `0` si no quieres descontar almuerzo). Este tiempo se restará del total de horas laborales disponibles cada día.

6.  **Guarda** los cambios realizados en el archivo `calendar_time_tracker.py`.

## Cómo Usar el Script Principal para Calcular Tiempo

Una vez completada la configuración inicial y la configuración del script v5:

1.  Asegúrate de que tu entorno virtual (`venv`) esté **activo**.
2.  Asegúrate de que `credentials.json` esté en el mismo directorio.
3.  Ejecuta el script principal desde tu terminal:
    ```bash
    python calendar_time_tracker.py
    ```
4.  **Autorización (Primera Vez para este script):** Si es la primera vez que ejecutas `calendar_time_tracker.py` (o si borraste `token.pickle`), se abrirá tu navegador para que autorices el acceso a tu calendario. Concede los permisos. Esto crea el archivo `token.pickle`.
5.  **Input de Horario Laboral:**
    * El script te pedirá la "Hora de inicio" y "Hora de fin".
    * Introduce la hora en formato `HH:MM` (ej. `08:30`, `17:00`).
    * O presiona `Enter` en cada pregunta para usar los valores por defecto (09:00 para inicio, 18:00 para fin).
6.  **Input de Fechas:**
    * Introduce la fecha de inicio del periodo que quieres analizar en formato `YYYY-MM-DD`.
    * Introduce la fecha de fin del periodo en formato `YYYY-MM-DD`.
7.  **Procesamiento y Salida:** El script se conectará a tu calendario, procesará los eventos dentro del rango de fechas y horario laboral, y finalmente imprimirá en la consola:
    * Un resumen por cada semana dentro del rango, mostrando las horas por servicio.
    * Un resumen total para todo el periodo solicitado, con las horas acumuladas por servicio.
    * El tiempo se muestra en horas con un decimal (ej. `8.5h`).

## Solución de Problemas / Notas

* **Errores de Autenticación/Permisos:** Si tienes problemas persistentes con la autorización de Google, intenta **eliminar los archivos `token.pickle` y/o `token_colors.pickle`** y vuelve a ejecutar el script correspondiente para forzar una nueva autorización completa desde cero.
* **`credentials.json` no encontrado:** Verifica que el archivo se llama exactamente `credentials.json` y está en el mismo directorio que los scripts `.py`.
* **Resultados Incorrectos o Inesperados:**
    * La causa más común es una configuración incorrecta de `COLOR_ID_TO_SERVICE` en el script v5. Asegúrate de que los IDs de color sean correctos (strings `'1'`, `'2'`, etc.) y que los nombres de servicio sean los deseados.
    * Verifica que estás aplicando consistentemente las etiquetas de color correctas a tus eventos en Google Calendar.
    * Confirma que el horario laboral que ingresas (o el default) y la `LUNCH_DURATION_MINUTES` configurada reflejen tu realidad.
* **Días Laborales Fijos:** Este script asume internamente una semana laboral de Lunes a Viernes. Este comportamiento está codificado y no se configura externamente en esta versión.

