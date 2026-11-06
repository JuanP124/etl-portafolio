"""
Generador de datos sintéticos "sucios" para el proyecto ETL.

Crea tres archivos en data/raw/:
  - clientes.csv    (200 clientes)
  - productos.xlsx  (15 productos, en formato Excel)
  - ventas.csv      (1500 ventas)

Todo está inventado con Faker: no hay personas ni negocios reales.
Los errores se meten a propósito para practicar la limpieza.
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

# --- Configuración -----------------------------------------------------------
SEMILLA = 42  # misma semilla = mismos datos cada vez (resultado reproducible)
N_CLIENTES = 200
N_VENTAS = 1500

# Carpeta data/raw, calculada desde la ubicación de este archivo
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_RAW = RAIZ / "data" / "raw"

# Generador aleatorio propio y Faker con nombres de Colombia
azar = random.Random(SEMILLA)
Faker.seed(SEMILLA)
fake = Faker("es_CO")

CIUDADES = [
    "Bogotá", "Medellín", "Cali", "Barranquilla",
    "Cartagena", "Bucaramanga", "Pereira", "Manizales",
]

# Catálogo inventado: (nombre, categoría, precio en pesos)
CATALOGO = [
    ("Cuaderno universitario", "Papelería", 8500),
    ("Resma de papel", "Papelería", 22000),
    ("Set de marcadores", "Papelería", 15000),
    ("Audífonos inalámbricos", "Electrónica", 95000),
    ("Cargador USB-C", "Electrónica", 38000),
    ("Mouse óptico", "Electrónica", 45000),
    ("Teclado compacto", "Electrónica", 120000),
    ("Lámpara de escritorio", "Hogar", 67000),
    ("Termo de acero", "Hogar", 52000),
    ("Organizador de cables", "Hogar", 14000),
    ("Mochila urbana", "Accesorios", 110000),
    ("Billetera de cuero", "Accesorios", 78000),
    ("Gorra deportiva", "Accesorios", 35000),
    ("Botella deportiva", "Deporte", 28000),
    ("Banda elástica", "Deporte", 19000),
]


# --- Funciones que ensucian los datos ----------------------------------------
def fecha_en_formato_mixto(fecha):
    """Devuelve la fecha como texto, con un formato elegido al azar."""
    formato = azar.choice(["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"])
    return fecha.strftime(formato)


def texto_inconsistente(texto):
    """Cambia mayúsculas/minúsculas o agrega espacios sobrantes, al azar."""
    variante = azar.choice(["igual", "mayusculas", "minusculas", "espacios"])
    if variante == "mayusculas":
        return texto.upper()
    if variante == "minusculas":
        return texto.lower()
    if variante == "espacios":
        return f"  {texto} "
    return texto


def email_invalido(email):
    """Rompe un email de cinco maneras distintas."""
    usuario, _, dominio = email.partition("@")
    return azar.choice([
        usuario,                  # sin arroba
        f"{usuario}@@{dominio}",  # doble arroba
        f"{usuario}@",            # sin dominio
        f"{usuario} @{dominio}",  # espacio dentro
        f"{usuario}.{dominio}",   # punto en vez de arroba
    ])


def monto_como_texto(monto):
    """Convierte un monto entero a texto con formatos distintos."""
    formato = azar.choice(["plano", "decimales", "signo", "miles", "cop"])
    if formato == "plano":
        return str(monto)                           # 125000
    if formato == "decimales":
        return f"{monto:.2f}"                       # 125000.00
    if formato == "signo":
        return f"${monto:,}".replace(",", ".")      # $125.000
    if formato == "miles":
        return f"{monto:,}"                         # 125,000
    return f"COP {monto}"                           # COP 125000


def con_duplicados(df, proporcion):
    """Repite una proporción de filas y mezcla el orden."""
    repetidas = df.sample(frac=proporcion, random_state=SEMILLA)
    resultado = pd.concat([df, repetidas], ignore_index=True)
    return resultado.sample(frac=1, random_state=SEMILLA).reset_index(drop=True)


# --- Creación de cada tabla --------------------------------------------------
def crear_clientes():
    filas = []
    for cliente_id in range(1, N_CLIENTES + 1):
        email = fake.safe_email()  # solo dominios de ejemplo: nada real
        registro = fake.date_between(
            start_date=date(2023, 1, 1), end_date=date(2025, 12, 31)
        )
        nombre = texto_inconsistente(fake.name())
        ciudad = texto_inconsistente(azar.choice(CIUDADES))

        # Errores a propósito
        if azar.random() < 0.08:
            email = email_invalido(email)
        if azar.random() < 0.06:
            email = None
        if azar.random() < 0.05:
            ciudad = None

        filas.append({
            "cliente_id": cliente_id,
            "nombre": nombre,
            "email": email,
            "ciudad": ciudad,
            "fecha_registro": fecha_en_formato_mixto(registro),
        })
    return con_duplicados(pd.DataFrame(filas), 0.05)


def crear_productos():
    filas = []
    for producto_id, (nombre, categoria, _precio) in enumerate(CATALOGO, start=1):
        categoria = texto_inconsistente(categoria)
        if azar.random() < 0.10:
            categoria = None
        filas.append({
            "producto_id": producto_id,
            "nombre": nombre,
            "categoria": categoria,
        })
    return pd.DataFrame(filas)


def crear_ventas():
    precios = {i: p for i, (_, _, p) in enumerate(CATALOGO, start=1)}
    inicio = date(2025, 1, 1)
    total_dias = (date(2026, 10, 31) - inicio).days

    filas = []
    for venta_id in range(1, N_VENTAS + 1):
        cliente_id = azar.randint(1, N_CLIENTES)
        producto_id = azar.randint(1, len(CATALOGO))
        cantidad = azar.randint(1, 5)
        monto = precios[producto_id] * cantidad
        fecha = inicio + timedelta(days=azar.randint(0, total_dias))

        # Errores a propósito
        if azar.random() < 0.02:
            cliente_id = azar.randint(900, 999)  # cliente que no existe
        if azar.random() < 0.03:
            cantidad = None
        if azar.random() < 0.02:
            cantidad = azar.choice([0, -1])      # cantidad imposible
        monto_texto = None if azar.random() < 0.02 else monto_como_texto(monto)

        filas.append({
            "venta_id": venta_id,
            "cliente_id": cliente_id,
            "producto_id": producto_id,
            "fecha": fecha_en_formato_mixto(fecha),
            "cantidad": cantidad,
            "monto": monto_texto,
        })

    df = pd.DataFrame(filas)
    df["cantidad"] = df["cantidad"].astype("Int64")  # enteros, sin ".0"
    return con_duplicados(df, 0.04)


# --- Programa principal ------------------------------------------------------
def main():
    CARPETA_RAW.mkdir(parents=True, exist_ok=True)

    clientes = crear_clientes()
    productos = crear_productos()
    ventas = crear_ventas()

    clientes.to_csv(CARPETA_RAW / "clientes.csv", index=False, encoding="utf-8")
    productos.to_excel(CARPETA_RAW / "productos.xlsx", index=False)
    ventas.to_csv(CARPETA_RAW / "ventas.csv", index=False, encoding="utf-8")

    print(f"clientes.csv:   {len(clientes)} filas")
    print(f"productos.xlsx: {len(productos)} filas")
    print(f"ventas.csv:     {len(ventas)} filas")
    print(f"Archivos creados en: {CARPETA_RAW}")


if __name__ == "__main__":
    main()