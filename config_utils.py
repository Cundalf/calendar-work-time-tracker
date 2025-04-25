"""
Utilidades para la gestión de la configuración de la aplicación.
Este módulo contiene funciones para limpiar valores de variables de entorno,
y gestionar la configuración de la aplicación.
"""

import json
from datetime import time
from loguru import logger

# Función para limpiar variables de entorno de comentarios
def clean_env_value(value):
    """
    Limpia el valor de una variable de entorno, eliminando cualquier comentario.
    
    Args:
        value: El valor de la variable de entorno
        
    Returns:
        El valor limpio de comentarios
    """
    if value and isinstance(value, str):
        # Si hay un # que no está al inicio, considerarlo como inicio de comentario
        if '#' in value and not value.startswith('#'):
            return value.split('#')[0].strip()
    return value

# Función para obtener configuración predeterminada
def get_default_config():
    """
    Retorna una configuración predeterminada con valores seguros
    
    Returns:
        Diccionario con la configuración predeterminada
    """
    return {
        'work_start_time': '09:00',
        'work_end_time': '17:00',
        'lunch_duration_minutes': 60,
        'default_service': 'TIEMPO NO ETIQUETADO',
        'ooo_service': 'FUERA DE OFICINA',
        'focus_time_service': 'TIEMPO DE CONCENTRACIÓN',
        'unlabeled_service': 'SIN ETIQUETA',
        'group_unlabeled': False,
        'use_color_tags': False,
        'color_tags': {}
    }

# Función para validar la configuración y aplicar defaults cuando sea necesario
def validate_config(config_data):
    """
    Valida la configuración recibida y aplica valores predeterminados SOLO si es necesario
    
    Args:
        config_data: Datos de configuración, puede ser un diccionario o string JSON
        
    Returns:
        Configuración validada como diccionario
    """
    # Devolver el valor predeterminado solo si NO hay configuración
    if not config_data:
        logger.warning("No se recibió configuración. Usando valores predeterminados.")
        return get_default_config()
    
    if isinstance(config_data, str) and not config_data.strip():
        logger.warning("Se recibió configuración como string vacío. Usando valores predeterminados.")
        return get_default_config()
    
    try:
        if isinstance(config_data, str):
            config = json.loads(config_data)
        else:
            config = config_data
        
        # Verificar que existan todas las claves necesarias sin reemplazarlas
        default_config = get_default_config()
        for key in default_config.keys():
            if key not in config:
                logger.warning(f"Falta campo '{key}' en la configuración. Usando valor predeterminado: {default_config[key]}")
                config[key] = default_config[key]
        
        # ¡IMPORTANTE: NO modificar los valores existentes!
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear configuración JSON: {e}")
        return get_default_config()
    except Exception as e:
        logger.error(f"Error inesperado al procesar configuración: {e}")
        return get_default_config() 