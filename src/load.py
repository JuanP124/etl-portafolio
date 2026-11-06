"""
load.py — Etapa LOAD del ETL.

Carga los datos limpios en PostgreSQL con el usuario etl_user (permisos
mínimos: leer, insertar y actualizar; no borrar ni modificar la estructura).

Es IDEMPOTENTE: si se corre dos veces, no duplica filas. Usa
INSERT ... ON CONFLICT DO UPDATE sobre la llave primaria de cada tabla.
"""

import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent

# Variables que debe tener el archivo .env
VARIABLES_REQUERIDAS = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"]

# Orden de carga: ventas depende de clientes y productos (llaves foráneas)
ORDEN_CARGA = ["clientes", "productos", "ventas"]

# Las consultas llevan parámetros (:nombre): los valores NUNCA se pegan al
# texto SQL, así que no hay riesgo de inyección SQL.
SQL_UPSERT = {
    "clientes": text("""
        INSERT INTO clientes (cliente_id, nombre, email, ciudad, fecha_registro)
        VALUES (:cliente_id, :nombre, :email, :ciudad, :fecha_registro)
        ON CONFLICT (cliente_id) DO UPDATE SET
            nombre         = EXCLUDED.nombre,
            email          = EXCLUDED.email,
            ciudad         = EXCLUDED.ciudad,
            fecha_registro = EXCLUDED.fecha_registro,
            cargado_en     = now()
    """),
    "productos": text("""
        INSERT INTO productos (producto_id, nombre, categoria)
        VALUES (:producto_id, :nombre, :categoria)
        ON CONFLICT (producto_id) DO UPDATE SET
            nombre     = EXCLUDED.nombre,
            categoria  = EXCLUDED.categoria,
            cargado_en = now()
    """),
    "ventas": text("""
        INSERT INTO ventas (venta_id, cliente_id, producto_id, fecha, cantidad, monto)
        VALUES (:venta_id, :cliente_id, :producto_id, :fecha, :cantidad, :monto)
        ON CONFLICT (venta_id) DO UPDATE SET
            cliente_id  = EXCLUDED.cliente_id,
            producto_id = EXCLUDED.producto_id,
            fecha       = EXCLUDED.fecha,
            cantidad    = EXCLUDED.cantidad,
            monto       = EXCLUDED.monto,
            cargado_en  = now()
    """),
}


class ErrorCarga(Exception):
    """Falla al cargar los datos en la base.

    El mensaje es seguro para mostrarlo al usuario: no incluye rutas,
    consultas ni credenciales. El detalle completo queda solo en los logs.
    """


def _crear_engine():
    """Crea la conexión a PostgreSQL con las credenciales del archivo .env."""
    load_dotenv(RAIZ / ".env")

    faltantes = [v for v in VARIABLES_REQUERIDAS if not os.getenv(v)]
    if faltantes:
        # Se registran los NOMBRES de las variables, nunca sus valores
        logger.error("Faltan variables en el archivo .env: %s", faltantes)
        raise ErrorCarga(
            "Falta configuración de la base de datos. Revisa el archivo .env."
        )

    try:
        puerto = int(os.environ["DB_PORT"])
    except ValueError:
        logger.error("DB_PORT no es un número válido")
        raise ErrorCarga(
            "La configuración de la base de datos no es válida. Revisa el archivo .env."
        ) from None

    # URL.create arma la conexión de forma segura, sin pegar texto a mano
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=puerto,
        database=os.environ["DB_NAME"],
    )
    # hide_parameters=True evita que los datos de las filas (emails, nombres)
    # aparezcan dentro de los mensajes de error y terminen en los logs.
    return create_engine(url, hide_parameters=True)


def _a_registros(df):
    """Convierte un DataFrame en una lista de diccionarios lista para la base.

    - Las fechas pasan a objetos date de Python.
    - Los valores vacíos (NaN, NaT, <NA>) pasan a None, que en SQL es NULL.
    """
    df = df.copy()
    for columna in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[columna]):
            df[columna] = df[columna].dt.date
    df = df.astype(object)
    df = df.where(df.notna(), None)
    return df.to_dict(orient="records")


def cargar_todo(limpios):
    """Carga los tres DataFrames limpios y devuelve el total de filas por tabla."""
    engine = _crear_engine()
    try:
        # engine.begin() abre UNA transacción: si algo falla, se deshace todo
        with engine.begin() as conexion:
            for nombre in ORDEN_CARGA:
                registros = _a_registros(limpios[nombre])
                if registros:
                    conexion.execute(SQL_UPSERT[nombre], registros)
                logger.info("Procesadas %d filas para %s", len(registros), nombre)

            # Los nombres de tabla salen de la lista fija ORDEN_CARGA,
            # nunca de datos externos.
            totales = {
                nombre: conexion.execute(text(f"SELECT COUNT(*) FROM {nombre}")).scalar_one()
                for nombre in ORDEN_CARGA
            }
    except Exception:
        # El detalle técnico va solo al log; al usuario, un mensaje genérico
        logger.exception("Falló la carga a la base de datos")
        raise ErrorCarga(
            "No se pudo cargar la información a la base de datos. Revisa los logs."
        ) from None
    finally:
        engine.dispose()

    logger.info("Total de filas en la base: %s", totales)
    return totales