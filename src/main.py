"""
main.py — Punto de entrada del ETL.

Ejecuta todo el flujo: extraer -> limpiar -> guardar -> cargar a PostgreSQL.
Uso (desde la carpeta del proyecto, con el entorno virtual activo):

    python -m src.main
"""

import copy
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.clean import guardar_resultados, limpiar_todo
from src.extract import ErrorExtraccion, leer_todo
from src.load import ErrorCarga, cargar_todo

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_LOGS = RAIZ / "logs"

logger = logging.getLogger(__name__)


class FormatoConsola(logging.Formatter):
    """Formato para la pantalla: igual que el log, pero SIN el traceback.

    El detalle técnico de un error (rutas, consultas) va solo al archivo de
    log. El usuario ve únicamente el mensaje corto.
    """

    def format(self, record):
        copia = copy.copy(record)  # copia, para no alterar lo que escribe el archivo
        copia.exc_info = None
        copia.exc_text = None
        return super().format(copia)


def configurar_logging():
    """Envía los mensajes a dos sitios: archivo (completo) y pantalla (resumido)."""
    CARPETA_LOGS.mkdir(parents=True, exist_ok=True)

    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.handlers.clear()  # evita mensajes repetidos si se llama dos veces

    # Archivo: con fecha, nivel y traceback completo. Rota al llegar a 1 MB.
    archivo = RotatingFileHandler(
        CARPETA_LOGS / "etl.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    archivo.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    # Pantalla: solo el mensaje, sin detalles técnicos
    consola = logging.StreamHandler()
    consola.setFormatter(FormatoConsola("%(levelname)s: %(message)s"))

    raiz.addHandler(archivo)
    raiz.addHandler(consola)


def main():
    """Corre el ETL completo. Devuelve 0 si salió bien y 1 si falló."""
    configurar_logging()
    inicio = time.perf_counter()
    logger.info("=== Inicio del ETL ===")

    try:
        crudos = leer_todo()
        limpios, rechazados = limpiar_todo(crudos)
        guardar_resultados(limpios, rechazados)
        totales = cargar_todo(limpios)
    except (ErrorExtraccion, ErrorCarga) as error:
        # Errores previstos: su mensaje ya es seguro para el usuario
        logger.error("ETL detenido: %s", error)
        return 1
    except Exception:
        # Errores imprevistos: el detalle completo va solo al archivo de log
        logger.exception("Error inesperado en el ETL. Revisa logs/etl.log")
        return 1

    descartadas = sum(len(df) for df in rechazados.values())
    segundos = time.perf_counter() - inicio
    logger.info(
        "=== ETL terminado en %.1f s | filas en la base: %s | filas descartadas: %d ===",
        segundos, totales, descartadas,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())