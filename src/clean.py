"""
clean.py — Etapa CLEAN del ETL.

Cada regla de limpieza es una función pequeña e independiente.
Luego limpiar_clientes / limpiar_productos / limpiar_ventas las combinan.

Lo que se puede corregir se corrige; lo que no, se descarta y se guarda
aparte en data/rejected/ con el motivo. Los logs guardan solo CONTEOS,
nunca el contenido de las filas (no se registran emails ni nombres).
"""

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_PROCESSED = RAIZ / "data" / "processed"
CARPETA_REJECTED = RAIZ / "data" / "rejected"

# Formatos de fecha que aceptamos (todos día/mes/año o año-mes-día)
FORMATOS_FECHA = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
FECHA_MINIMA = pd.Timestamp("2020-01-01")

PATRON_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")


# --- Reglas de limpieza (una función por regla) ------------------------------
def normalizar_texto(serie):
    """Quita espacios sobrantes, deja un solo espacio entre palabras y pone Mayúscula Inicial."""
    limpio = serie.str.strip().str.replace(r"\s+", " ", regex=True).str.title()
    return limpio.where(limpio != "")  # texto vacío pasa a valor nulo


def convertir_entero(serie):
    """Convierte texto a entero. Lo que no sea un entero exacto queda vacío."""
    numerico = pd.to_numeric(serie.str.strip(), errors="coerce")
    numerico = numerico.where(numerico % 1 == 0)  # descarta 12.5, por ejemplo
    return numerico.astype("Int64")


def convertir_fechas(serie):
    """Convierte fechas escritas en varios formatos a fechas reales.

    Cada formato se prueba de forma EXPLÍCITA. Dejar que pandas adivine es
    peligroso: puede leer 10/05/2026 como 5 de octubre en vez de 10 de mayo.
    """
    texto = serie.str.strip()
    resultado = None
    for formato in FORMATOS_FECHA:
        parcial = pd.to_datetime(texto, format=formato, errors="coerce")
        resultado = parcial if resultado is None else resultado.fillna(parcial)
    return resultado


def limitar_rango_fechas(fechas):
    """Deja vacías las fechas imposibles: anteriores a 2020 o en el futuro."""
    hoy = pd.Timestamp.today().normalize()
    return fechas.where((fechas >= FECHA_MINIMA) & (fechas <= hoy))


def _monto_a_numero(valor):
    """Convierte un monto en texto a número, o NaN si no se entiende.

    Distingue el punto de miles ($125.000) del punto decimal (125000.50):
    un punto seguido de exactamente 3 dígitos es separador de miles.
    """
    if pd.isna(valor):
        return float("nan")
    texto = str(valor).upper().replace("COP", "").replace("$", "").replace(" ", "")
    if re.fullmatch(r"\d+(\.\d{1,2})?", texto):    # 125000 o 125000.50
        return float(texto)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):  # 125.000
        return float(texto.replace(".", ""))
    if re.fullmatch(r"\d{1,3}(,\d{3})+", texto):   # 125,000
        return float(texto.replace(",", ""))
    return float("nan")  # incluye negativos y cualquier formato desconocido


def convertir_montos(serie):
    """Convierte una columna de montos en texto a números con 2 decimales."""
    return serie.map(_monto_a_numero).astype("float64").round(2)


def validar_email(serie):
    """Pone el email en minúsculas; si no tiene forma válida, queda vacío."""
    limpio = serie.str.strip().str.lower()
    es_valido = limpio.map(
        lambda e: bool(PATRON_EMAIL.match(e)) if isinstance(e, str) else False
    )
    return limpio.where(es_valido)


def es_duplicado(df, columna_id):
    """Marca las copias repetidas de un ID (la primera aparición se conserva)."""
    return df.duplicated(subset=columna_id, keep="first")


# --- Ayudas internas ---------------------------------------------------------
def _descartar(df, mascara, motivo, crudo, rechazadas):
    """Quita de df las filas marcadas y guarda su versión CRUDA con el motivo."""
    marcadas = mascara.to_numpy(dtype=bool)
    cantidad = int(marcadas.sum())
    if cantidad:
        rechazadas.append(crudo.loc[df.index[marcadas]].assign(motivo_rechazo=motivo))
        logger.info("Descartadas %d filas: %s", cantidad, motivo)
    return df[~marcadas]


def _contar_cambios(antes, despues):
    """Cuenta cuántos valores existentes cambiaron al limpiarlos."""
    return int(((antes != despues) & antes.notna()).sum())


def _contar_fechas_no_iso(texto_crudo, fechas):
    """Cuenta fechas válidas que venían en un formato distinto a AAAA-MM-DD."""
    es_iso = texto_crudo.str.strip().str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    es_iso = es_iso.fillna(False).astype(bool)
    return int((fechas.notna() & ~es_iso).sum())


def _unir_rechazadas(rechazadas, crudo):
    if rechazadas:
        return pd.concat(rechazadas)
    return crudo.head(0).assign(motivo_rechazo="")


def _resumen(nombre, crudo, limpio, rechazado):
    logger.info(
        "%s: %d crudas -> %d limpias, %d descartadas",
        nombre, len(crudo), len(limpio), len(rechazado),
    )


# --- Limpieza de cada tabla --------------------------------------------------
def limpiar_clientes(crudo):
    rechazadas = []
    df = crudo.copy()

    df["cliente_id"] = convertir_entero(df["cliente_id"])
    df = _descartar(df, df["cliente_id"].isna(),
                    "cliente_id vacío o no numérico", crudo, rechazadas)
    df = _descartar(df, es_duplicado(df, "cliente_id"),
                    "cliente duplicado", crudo, rechazadas)

    for columna in ["nombre", "ciudad"]:
        antes = df[columna]
        df[columna] = normalizar_texto(antes)
        logger.info("Texto normalizado en clientes.%s: %d valores corregidos",
                    columna, _contar_cambios(antes, df[columna]))
    df = _descartar(df, df["nombre"].isna(),
                    "nombre vacío", crudo, rechazadas)

    # Email inválido: se vacía el campo pero el cliente se conserva
    antes = df["email"].str.strip().str.lower()
    df["email"] = validar_email(df["email"])
    invalidos = int((antes.notna() & df["email"].isna()).sum())
    logger.info("Emails inválidos dejados vacíos: %d (el cliente se conserva)", invalidos)

    texto_fecha = df["fecha_registro"]
    fechas = limitar_rango_fechas(convertir_fechas(texto_fecha))
    logger.info("Fechas de registro reformateadas: %d", _contar_fechas_no_iso(texto_fecha, fechas))
    logger.info("Fechas de registro inválidas dejadas vacías: %d",
                int((fechas.isna() & texto_fecha.notna()).sum()))
    df["fecha_registro"] = fechas

    limpio = df[["cliente_id", "nombre", "email", "ciudad", "fecha_registro"]]
    rechazado = _unir_rechazadas(rechazadas, crudo)
    _resumen("Clientes", crudo, limpio, rechazado)
    return limpio.reset_index(drop=True), rechazado


def limpiar_productos(crudo):
    rechazadas = []
    df = crudo.copy()

    df["producto_id"] = convertir_entero(df["producto_id"])
    df = _descartar(df, df["producto_id"].isna(),
                    "producto_id vacío o no numérico", crudo, rechazadas)
    df = _descartar(df, es_duplicado(df, "producto_id"),
                    "producto duplicado", crudo, rechazadas)

    for columna in ["nombre", "categoria"]:
        antes = df[columna]
        df[columna] = normalizar_texto(antes)
        logger.info("Texto normalizado en productos.%s: %d valores corregidos",
                    columna, _contar_cambios(antes, df[columna]))
    df = _descartar(df, df["nombre"].isna(),
                    "nombre vacío", crudo, rechazadas)

    limpio = df[["producto_id", "nombre", "categoria"]]
    rechazado = _unir_rechazadas(rechazadas, crudo)
    _resumen("Productos", crudo, limpio, rechazado)
    return limpio.reset_index(drop=True), rechazado


def limpiar_ventas(crudo, ids_clientes, ids_productos):
    """ids_clientes e ids_productos son los IDs que sobrevivieron a la limpieza."""
    rechazadas = []
    df = crudo.copy()

    for columna in ["venta_id", "cliente_id", "producto_id"]:
        df[columna] = convertir_entero(df[columna])
    df = _descartar(df, df[["venta_id", "cliente_id", "producto_id"]].isna().any(axis=1),
                    "algún ID vacío o no numérico", crudo, rechazadas)
    df = _descartar(df, es_duplicado(df, "venta_id"),
                    "venta duplicada", crudo, rechazadas)

    texto_fecha = df["fecha"]
    fechas = limitar_rango_fechas(convertir_fechas(texto_fecha))
    logger.info("Fechas de ventas reformateadas: %d", _contar_fechas_no_iso(texto_fecha, fechas))
    df["fecha"] = fechas
    df = _descartar(df, df["fecha"].isna(),
                    "fecha inválida o fuera de rango", crudo, rechazadas)

    df["cantidad"] = convertir_entero(df["cantidad"])
    df = _descartar(df, df["cantidad"].fillna(0) <= 0,
                    "cantidad vacía, cero o negativa", crudo, rechazadas)

    texto_monto = df["monto"]
    df["monto"] = convertir_montos(texto_monto)
    es_plano = texto_monto.str.fullmatch(r"\d+").fillna(False).astype(bool)
    logger.info("Montos convertidos desde texto con formato: %d",
                int((df["monto"].notna() & ~es_plano).sum()))
    df = _descartar(df, df["monto"].isna(),
                    "monto vacío o con formato no reconocido", crudo, rechazadas)

    df = _descartar(df, ~df["cliente_id"].isin(ids_clientes),
                    "cliente_id no existe en clientes limpios", crudo, rechazadas)
    df = _descartar(df, ~df["producto_id"].isin(ids_productos),
                    "producto_id no existe en productos limpios", crudo, rechazadas)

    limpio = df[["venta_id", "cliente_id", "producto_id", "fecha", "cantidad", "monto"]]
    rechazado = _unir_rechazadas(rechazadas, crudo)
    _resumen("Ventas", crudo, limpio, rechazado)
    return limpio.reset_index(drop=True), rechazado


# --- Orquestación y guardado -------------------------------------------------
def limpiar_todo(crudos):
    """Recibe el diccionario de extract.leer_todo(); devuelve (limpios, rechazados)."""
    clientes, rech_clientes = limpiar_clientes(crudos["clientes"])
    productos, rech_productos = limpiar_productos(crudos["productos"])
    ventas, rech_ventas = limpiar_ventas(
        crudos["ventas"],
        clientes["cliente_id"].tolist(),
        productos["producto_id"].tolist(),
    )
    limpios = {"clientes": clientes, "productos": productos, "ventas": ventas}
    rechazados = {"clientes": rech_clientes, "productos": rech_productos, "ventas": rech_ventas}
    return limpios, rechazados


def guardar_resultados(limpios, rechazados):
    """Guarda los limpios en data/processed/ y los descartados en data/rejected/."""
    CARPETA_PROCESSED.mkdir(parents=True, exist_ok=True)
    CARPETA_REJECTED.mkdir(parents=True, exist_ok=True)
    for nombre, df in limpios.items():
        df.to_csv(CARPETA_PROCESSED / f"{nombre}_limpio.csv", index=False, encoding="utf-8")
    for nombre, df in rechazados.items():
        df.to_csv(CARPETA_REJECTED / f"{nombre}_rechazados.csv", index=False, encoding="utf-8")
    logger.info("Resultados guardados en data/processed y data/rejected")