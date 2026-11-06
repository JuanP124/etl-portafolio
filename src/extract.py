"""
extract.py — Etapa EXTRACT del ETL.

Lee los archivos crudos de data/raw/ y los entrega tal cual, sin limpiar.
Todo se lee como texto: así ninguna conversión ocurre "a escondidas" y
cada regla de limpieza (en clean.py) decide qué hacer con cada valor.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Carpeta data/raw, calculada desde la ubicación de este archivo
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_RAW = RAIZ / "data" / "raw"

# Columnas que debe tener cada archivo (validación de entrada)
COLUMNAS_ESPERADAS = {
    "clientes": ["cliente_id", "nombre", "email", "ciudad", "fecha_registro"],
    "productos": ["producto_id", "nombre", "categoria"],
    "ventas": ["venta_id", "cliente_id", "producto_id", "fecha", "cantidad", "monto"],
}


class ErrorExtraccion(Exception):
    """Falla al leer los datos crudos.

    El mensaje es seguro para mostrarlo al usuario: no incluye rutas ni
    detalles técnicos. El detalle completo queda solo en los logs.
    """


def _leer(nombre, archivo, es_excel=False):
    """Lee un archivo crudo como texto y verifica que tenga sus columnas."""
    ruta = CARPETA_RAW / archivo
    try:
        if es_excel:
            df = pd.read_excel(ruta, dtype=str)
        else:
            df = pd.read_csv(ruta, dtype=str, encoding="utf-8")
    except Exception:
        # El detalle técnico (con traceback) va solo al log
        logger.exception("No se pudo leer el archivo %s", archivo)
        raise ErrorExtraccion(
            f"No se pudo leer el archivo de {nombre}. Revisa los logs."
        ) from None

    faltantes = set(COLUMNAS_ESPERADAS[nombre]) - set(df.columns)
    if faltantes:
        logger.error("Al archivo %s le faltan columnas: %s", archivo, sorted(faltantes))
        raise ErrorExtraccion(
            f"El archivo de {nombre} no tiene el formato esperado. Revisa los logs."
        )

    # Solo en el log: nombre de archivo y cantidad de filas, nunca el contenido
    logger.info("Leído %s: %d filas", archivo, len(df))
    return df[COLUMNAS_ESPERADAS[nombre]]


def leer_clientes():
    return _leer("clientes", "clientes.csv")


def leer_productos():
    return _leer("productos", "productos.xlsx", es_excel=True)


def leer_ventas():
    return _leer("ventas", "ventas.csv")


def leer_todo():
    """Devuelve un diccionario con los tres DataFrames crudos."""
    return {
        "clientes": leer_clientes(),
        "productos": leer_productos(),
        "ventas": leer_ventas(),
    }