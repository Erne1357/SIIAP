# app/utils/datetime_utils.py

from datetime import datetime
import zoneinfo

# Zona horaria local de Ciudad Juárez
LOCAL_TZ = zoneinfo.ZoneInfo("America/Ciudad_Juarez")

def now_local():
    """
    Devuelve la hora actual en la zona horaria local de Ciudad Juárez.
    """
    return datetime.now(LOCAL_TZ)

def to_local_timezone(dt):
    """
    Convierte un datetime a la zona horaria local de Ciudad Juárez.
    
    Args:
        dt: datetime object (puede tener o no zona horaria)
    
    Returns:
        datetime object en zona horaria local
    """
    if dt.tzinfo is None:
        # Si no tiene zona horaria, asumir que es hora local
        return dt.replace(tzinfo=LOCAL_TZ)
    else:
        # Convertir a hora local
        return dt.astimezone(LOCAL_TZ)