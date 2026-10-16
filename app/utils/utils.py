# File: app/utils/utils.py
# utils.py - Funciones utilitarias para la aplicación

def getPeriod():
    """
    Returns the current period as a string in the format 'YYYY-YYYY'.
    """
    from app.utils.datetime_utils import now_local
    today = now_local()
    year = today.year
    if today.month < 8:  # January to July
        return f"{year - 1}-{year}"
    else:  # August to December
        return f"{year}-{year + 1}"