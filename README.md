# ETL de ventas: limpieza de datos con Python, PostgreSQL y Streamlit

Pipeline ETL que toma datos de ventas desordenados (CSV y Excel), los limpia con reglas explícitas, los carga en PostgreSQL y los muestra en un dashboard (*Sales Performance Analytics*).

## Qué problema resuelve

Los datos reales casi nunca llegan limpios. Este proyecto parte de datos sintéticos con errores metidos a propósito (generados con Faker, sin personas ni negocios reales): 200 clientes, 15 productos y 1500 ventas.

Errores que se corrigen o se descartan:

- IDs vacíos, no numéricos o repetidos.
- Nombres y ciudades con espacios de más y mayúsculas inconsistentes.
- Emails con formato inválido.
- Fechas en varios formatos (`2025-10-28`, `27/04/2025`, `27-04-2025`), anteriores a 2020 o en el futuro.
- Montos escritos de formas distintas (`COP 22000`, `$25.500`, `125,000`).
- Cantidades en cero o negativas.
- Ventas que apuntan a clientes o productos que no existen.

## Cómo funciona

```
extraer (CSV/Excel) -> limpiar -> guardar resultados -> cargar a PostgreSQL -> dashboard
```

Decisiones de diseño:

- **Una función por regla de limpieza**, pequeña e independiente, para poder probarla sola.
- **Fechas con formato explícito.** Dejar que pandas adivine puede leer `10/05/2026` como 5 de octubre; aquí se lee siempre como día/mes/año.
- **Lo que no se puede corregir se descarta y se guarda aparte** en `data/rejected/`, con el motivo del rechazo.
- **Los logs guardan solo conteos**, nunca el contenido de las filas (no se registran emails ni nombres).
- **Permisos mínimos en la base de datos:** un usuario para el ETL y otro distinto para el dashboard.
- **Credenciales fuera del código**, en un archivo `.env` que no se sube al repositorio.

## Estructura del proyecto

```
src/         extract.py, clean.py, load.py, main.py, generar_datos.py
dashboard/   app.py (Streamlit)
sql/         01_esquema.sql
tests/       pruebas con pytest
data/        raw/ (entrada), processed/ (limpio), rejected/ (descartado)
logs/        registros de ejecución
```

## Instalación

Desde la carpeta del proyecto (Windows, PowerShell):

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Abre `.env` y reemplaza los valores de ejemplo (`cambia_esto`) por los de tu base de datos local. Nunca subas ese archivo.

## Base de datos

Crea el esquema y los usuarios ejecutando `sql/01_esquema.sql` en PostgreSQL con un usuario administrador, por ejemplo:

```powershell
psql -U postgres -f sql/01_esquema.sql
```

## Uso

```powershell
python -m src.generar_datos      # crea los datos sucios en data/raw/
python -m src.main               # extrae, limpia, guarda y carga a PostgreSQL
streamlit run dashboard/app.py   # abre el dashboard
```

## Pruebas

```powershell
pip install -r requirements-dev.txt
pytest
```

Hay 32 pruebas que cubren cada regla de limpieza, la limpieza de cada tabla, el descarte de ventas cuyo cliente o producto fue rechazado, y el guardado de los archivos.

## Tecnologías

Python, pandas, SQLAlchemy, PostgreSQL, Streamlit, Plotly y pytest.