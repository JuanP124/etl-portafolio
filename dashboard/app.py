"""
app.py — Dashboard analítico en Streamlit (versión 2: diseño mejorado).

Se conecta a PostgreSQL con dashboard_user: SOLO LECTURA y sin acceso a la
columna email. Se ejecuta desde la carpeta del proyecto, con el venv activo:

    streamlit run dashboard/app.py
"""

import logging
import html
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_LOGS = RAIZ / "logs"

VARIABLES_REQUERIDAS = [
    "DASH_DB_USER", "DASH_DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME",
]
# El dashboard nunca debe usar al administrador ni al usuario del ETL
USUARIOS_PROHIBIDOS = {"postgres", "etl_user"}

# Colores del diseño: un solo acento (morado) y tonos neutros
MORADO = "#8B5CF6"
GRIS = "#A1A1B5"
LINEA = "#262638"
PALETA = ["#8B5CF6", "#6366F1", "#38BDF8", "#34D399", "#FBBF24", "#F472B6"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

st.set_page_config(page_title="Dashboard de ventas", page_icon="📊", layout="wide")

# Ajustes visuales menores: más aire arriba y sin el pie de página de Streamlit
st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1400px;}
    footer {visibility: hidden;}
    h1 {font-weight: 700; letter-spacing: -0.5px;}
    </style>
    """,
    unsafe_allow_html=True,
)


class ErrorDashboard(Exception):
    """Error con un mensaje seguro para mostrar al usuario.

    El detalle técnico va solo al archivo logs/dashboard.log.
    """


@st.cache_resource
def configurar_logging():
    """Crea el log del dashboard (se ejecuta una sola vez por sesión del servidor)."""
    CARPETA_LOGS.mkdir(parents=True, exist_ok=True)
    registro = logging.getLogger("dashboard")
    registro.setLevel(logging.INFO)
    archivo = RotatingFileHandler(
        CARPETA_LOGS / "dashboard.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    archivo.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    registro.addHandler(archivo)
    return registro


logger = configurar_logging()


@st.cache_resource
def obtener_engine():
    """Crea la conexión de solo lectura con las credenciales del archivo .env."""
    load_dotenv(RAIZ / ".env")

    faltantes = [v for v in VARIABLES_REQUERIDAS if not os.getenv(v)]
    if faltantes:
        # Se registran los NOMBRES de las variables, nunca sus valores
        logger.error("Faltan variables en .env: %s", faltantes)
        raise ErrorDashboard("Falta configuración de la base de datos. Revisa el archivo .env.")

    usuario = os.environ["DASH_DB_USER"]
    if usuario in USUARIOS_PROHIBIDOS:
        logger.error("El dashboard está configurado con un usuario con demasiados permisos")
        raise ErrorDashboard("El dashboard debe usar un usuario de solo lectura. Revisa el archivo .env.")

    try:
        puerto = int(os.environ["DB_PORT"])
    except ValueError:
        logger.error("DB_PORT no es un número válido")
        raise ErrorDashboard("La configuración de la base de datos no es válida.") from None

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=usuario,
        password=os.environ["DASH_DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=puerto,
        database=os.environ["DB_NAME"],
    )
    # hide_parameters=True: los datos de las filas no aparecen en mensajes de error
    return create_engine(url, hide_parameters=True, pool_pre_ping=True)


def _consultar(consulta, parametros=None):
    """Ejecuta una consulta con parámetros y devuelve un DataFrame."""
    try:
        with obtener_engine().connect() as conexion:
            return pd.read_sql_query(consulta, conexion, params=parametros)
    except ErrorDashboard:
        raise
    except Exception:
        logger.exception("Falló una consulta a la base de datos")
        raise ErrorDashboard("No se pudo consultar la base de datos. Revisa los logs.") from None


# Nunca se usa SELECT * sobre clientes: dashboard_user no puede leer el email.
# Los valores (:desde, :hasta) van como parámetros, nunca pegados al texto SQL.
SQL_VENTAS = text("""
    SELECT v.venta_id, v.fecha, v.cantidad, v.monto,
           c.cliente_id, c.nombre AS cliente, c.ciudad,
           p.nombre AS producto, p.categoria
    FROM ventas v
    JOIN clientes  c ON c.cliente_id  = v.cliente_id
    JOIN productos p ON p.producto_id = v.producto_id
    WHERE v.fecha BETWEEN :desde AND :hasta
""")


@st.cache_data(ttl=300)
def cargar_rango():
    """Fecha mínima, fecha máxima y momento de la última carga del ETL."""
    df = _consultar(text(
        "SELECT MIN(fecha) AS desde, MAX(fecha) AS hasta, MAX(cargado_en) AS carga FROM ventas"
    ))
    desde, hasta, carga = df.loc[0, "desde"], df.loc[0, "hasta"], df.loc[0, "carga"]
    if pd.isna(desde):
        raise ErrorDashboard("Todavía no hay ventas cargadas. Ejecuta primero el ETL.")
    return pd.Timestamp(desde).date(), pd.Timestamp(hasta).date(), pd.Timestamp(carga)


@st.cache_data(ttl=300, show_spinner="Consultando la base de datos...")
def cargar_ventas(desde, hasta):
    """Ventas del rango de fechas, ya unidas con cliente y producto."""
    df = _consultar(SQL_VENTAS, {"desde": desde, "hasta": hasta})
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["monto"] = df["monto"].astype(float)
    df["categoria"] = df["categoria"].fillna("Sin categoría")
    df["ciudad"] = df["ciudad"].fillna("Sin ciudad")
    return df


# --- Formato y estilo de gráficos --------------------------------------------
def pesos(valor):
    """Formato de pesos colombianos: COP 1.234.567"""
    return "COP " + f"{valor:,.0f}".replace(",", ".")


def mes_texto(marca):
    """Nombre del mes en español: 'jul 2026'."""
    return f"{MESES[marca.month - 1]} {marca.year}"


def estilo(grafico, altura=300):
    """Aplica el estilo oscuro común a todos los gráficos."""
    return (
        grafico.properties(height=altura)
        .configure(background="transparent")
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=GRIS, titleColor=GRIS, gridColor=LINEA,
            domainColor=LINEA, tickColor=LINEA, labelLimit=400,
        )
        .configure_legend(labelColor=GRIS, titleColor=GRIS, orient="bottom")
    )


def grafico_mensual(mensual):
    """Área con línea: ventas por mes, en millones de COP."""
    datos = mensual.reset_index(drop=True)
    datos["millones"] = datos["monto"] / 1_000_000
    datos["mes"] = datos["mes_ts"].map(mes_texto)
    # Etiquetas del eje en español (las genera el navegador con esta expresión)
    meses_js = "[" + ",".join(f"'{m}'" for m in MESES) + "]"
    expresion = f"{meses_js}[month(datum.value)] + ' ' + year(datum.value)"
    relleno = alt.Gradient(
        gradient="linear",
        stops=[
            alt.GradientStop(color="rgba(139,92,246,0)", offset=0),
            alt.GradientStop(color="rgba(139,92,246,0.55)", offset=1),
        ],
        x1=1, x2=1, y1=1, y2=0,
    )
    return alt.Chart(datos).mark_area(
        color=relleno, interpolate="monotone",
        line={"color": MORADO, "strokeWidth": 2.5},
        point={"color": MORADO, "size": 45},
    ).encode(
        x=alt.X("mes_ts:T", title=None, axis=alt.Axis(labelExpr=expresion, labelAngle=-45)),
        y=alt.Y("millones:Q", title="Millones de COP"),
        tooltip=[
            alt.Tooltip("mes:N", title="Mes"),
            alt.Tooltip("millones:Q", title="Ventas (millones COP)", format=",.1f"),
        ],
    )


def grafico_barras(datos, columna_nombre):
    """Barras horizontales ordenadas, con los nombres completos a la izquierda."""
    datos = datos.assign(millones=datos["monto"] / 1_000_000)
    return alt.Chart(datos).mark_bar(color=MORADO, cornerRadiusEnd=4).encode(
        y=alt.Y(f"{columna_nombre}:N", sort="-x", title=None),
        x=alt.X("millones:Q", title="Millones de COP"),
        tooltip=[
            alt.Tooltip(f"{columna_nombre}:N", title="Nombre"),
            alt.Tooltip("millones:Q", title="Ventas (millones COP)", format=",.2f"),
        ],
    )


# Tonos de morado bien distintos entre sí. En la torta, las porciones vecinas
# alternan oscuro/claro para que se note la diferencia.
PALETA_MORADO = ["#5B21B6", "#C4B5FD", "#7C3AED", "#EDE9FE", "#A78BFA", "#8B5CF6"]
TONOS_CLAROS = {"#C4B5FD", "#EDE9FE", "#A78BFA"}  # llevan texto oscuro encima

ESTILO_EXTRA = """
<style>
.kpi-titulo {color:#A1A1B5; font-size:0.85rem; font-weight:600; letter-spacing:0.3px;}
.kpi-valor {color:#F4F1FF; font-weight:700; white-space:nowrap; font-size:clamp(1.05rem, 1.55vw, 1.75rem); margin:2px 0 4px 0;}
.leyenda {display:flex; flex-direction:column; gap:6px; margin-top:4px;}
.leyenda-fila {display:flex; align-items:center; gap:10px; font-size:0.92rem; color:#E6E6F0;}
.leyenda-punto {width:12px; height:12px; border-radius:50%; flex:none;}
.leyenda-nombre {flex:1;}
.leyenda-pct {font-weight:700;}
.pf {position:relative; overflow:hidden; background:linear-gradient(145deg,#1d1736 0%,#14141F 70%); border:1px solid #2d2450; border-radius:16px; padding:18px 16px 16px 16px; min-height:200px;}
.pf::before {content:""; position:absolute; top:0; left:0; right:0; height:4px; background:linear-gradient(90deg,#8B5CF6,#C4B5FD);}
.pf-icono {font-size:1.5rem; margin-bottom:6px;}
.pf-titulo {color:#A78BFA; font-size:0.72rem; font-weight:700; letter-spacing:1.2px; text-transform:uppercase;}
.pf-valor {color:#FFFFFF; font-size:1.15rem; font-weight:700; line-height:1.25; margin:6px 0 2px 0; min-height:2.9rem;}
.pf-detalle {color:#A1A1B5; font-size:0.85rem;}
.pf-barra {height:6px; background:#262638; border-radius:99px; margin:12px 0 6px 0; overflow:hidden;}
.pf-barra div {height:100%; background:linear-gradient(90deg,#7C3AED,#C4B5FD); border-radius:99px;}
.pf-pct {color:#E6E6F0; font-size:0.8rem; font-weight:600;}
</style>
"""


def hora_local(marca):
    """Pasa la hora de la base (UTC) a hora de Colombia."""
    if marca.tzinfo is None:
        marca = marca.tz_localize("UTC")
    return marca.tz_convert("America/Bogota")


def degradado():
    """Relleno morado que se desvanece hacia abajo."""
    return alt.Gradient(
        gradient="linear",
        stops=[
            alt.GradientStop(color="rgba(139,92,246,0)", offset=0),
            alt.GradientStop(color="rgba(139,92,246,0.55)", offset=1),
        ],
        x1=1, x2=1, y1=1, y2=0,
    )


def mini_grafico(serie):
    """Mini-gráfico morado con la evolución mensual de un KPI."""
    datos = pd.DataFrame({"mes_ts": serie.index.to_timestamp(), "valor": serie.to_numpy()})
    datos["mes"] = datos["mes_ts"].map(mes_texto)
    return (
        alt.Chart(datos)
        .mark_area(color=degradado(), interpolate="monotone",
                   line={"color": MORADO, "strokeWidth": 2})
        .encode(
            x=alt.X("mes_ts:T", axis=None),
            y=alt.Y("valor:Q", axis=None, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("mes:N", title="Mes"),
                     alt.Tooltip("valor:Q", title="Valor", format=",.0f")],
        )
        .properties(height=60)
        .configure(background="transparent")
        .configure_view(stroke=None)
    )


def tarjeta_kpi(columna, titulo, valor, serie):
    """KPI con el valor completo (sin cortar) y su mini-gráfico debajo."""
    with columna.container(border=True):
        st.markdown(
            f'<div class="kpi-titulo">{html.escape(titulo)}</div>'
            f'<div class="kpi-valor">{html.escape(valor)}</div>',
            unsafe_allow_html=True,
        )
        if len(serie) > 1:
            st.altair_chart(mini_grafico(serie), theme=None)


def grafico_torta(por_categoria):
    """Torta con el porcentaje dentro de cada porción. Devuelve (gráfico, datos)."""
    datos = por_categoria.rename("monto").reset_index()
    datos["pct"] = datos["monto"] / datos["monto"].sum()
    datos["etiqueta"] = datos["pct"].map(lambda p: f"{p:.0%}" if p >= 0.04 else "")
    datos["color"] = (PALETA_MORADO * 2)[: len(datos)]
    datos["texto"] = datos["color"].map(lambda c: "#1B1033" if c in TONOS_CLAROS else "#FFFFFF")

    base = alt.Chart(datos).encode(
        theta=alt.Theta("monto:Q", stack=True),
        order=alt.Order("monto:Q", sort="descending"),
    )
    arcos = base.mark_arc(innerRadius=50, outerRadius=120, stroke="#14141F", strokeWidth=2).encode(
        color=alt.Color(
            "categoria:N",
            scale=alt.Scale(domain=datos["categoria"].tolist(), range=datos["color"].tolist()),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("categoria:N", title="Categoría"),
            alt.Tooltip("monto:Q", title="Ventas (COP)", format=",.0f"),
            alt.Tooltip("pct:Q", title="Participación", format=".1%"),
        ],
    )
    porcentajes = base.mark_text(radius=85, size=14, fontWeight="bold").encode(
        text="etiqueta:N", color=alt.Color("texto:N", scale=None, legend=None)
    )
    return arcos + porcentajes, datos


def leyenda_html(datos):
    """Leyenda propia: punto de color, nombre y porcentaje de cada categoría."""
    filas = "".join(
        f'<div class="leyenda-fila"><span class="leyenda-punto" style="background:{fila.color}"></span>'
        f'<span class="leyenda-nombre">{html.escape(fila.categoria)}</span>'
        f'<span class="leyenda-pct">{fila.pct:.0%}</span></div>'
        for fila in datos.itertuples()
    )
    return f'<div class="leyenda">{filas}</div>'


def grafico_ciudades(por_ciudad):
    """Barras gruesas, sin números en el eje y con el valor dentro de cada barra."""
    datos = por_ciudad.rename("monto").reset_index()
    datos["millones"] = datos["monto"] / 1_000_000
    umbral = datos["millones"].max() * 0.12  # barras muy cortas llevan el número afuera

    base = alt.Chart(datos).encode(y=alt.Y("ciudad:N", sort="-x", title=None))
    barras = base.mark_bar(color=MORADO, size=30, cornerRadiusEnd=6).encode(
        x=alt.X("millones:Q", title="Millones de COP",
                axis=alt.Axis(labels=False, ticks=False, grid=False, domain=False)),
        tooltip=[
            alt.Tooltip("ciudad:N", title="Ciudad"),
            alt.Tooltip("millones:Q", title="Ventas (millones COP)", format=",.2f"),
        ],
    )
    dentro = base.mark_text(align="right", dx=-10, color="white", fontWeight="bold", fontSize=13).encode(
        x="millones:Q", text=alt.Text("millones:Q", format=",.1f")
    ).transform_filter(f"datum.millones >= {umbral}")
    fuera = base.mark_text(align="left", dx=6, color="#E6E6F0", fontWeight="bold", fontSize=13).encode(
        x="millones:Q", text=alt.Text("millones:Q", format=",.1f")
    ).transform_filter(f"datum.millones < {umbral}")
    return barras + dentro + fuera


def tarjeta_fuerte(columna, icono, titulo, valor, detalle, parte, total):
    """Tarjeta de 'punto fuerte' con barra de participación."""
    pct = parte / total
    columna.markdown(
        '<div class="pf">'
        f'<div class="pf-icono">{icono}</div>'
        f'<div class="pf-titulo">{html.escape(titulo)}</div>'
        f'<div class="pf-valor">{html.escape(valor)}</div>'
        f'<div class="pf-detalle">{html.escape(detalle)}</div>'
        f'<div class="pf-barra"><div style="width:{min(pct, 1) * 100:.0f}%"></div></div>'
        f'<div class="pf-pct">{pct:.0%} de las ventas</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def main():
    st.markdown(ESTILO_EXTRA, unsafe_allow_html=True)
    minimo, maximo, carga = cargar_rango()

    # --- Encabezado ---
    izquierda, derecha = st.columns([3, 1])
    with izquierda:
        st.title("📊 Dashboard de ventas")
        st.caption("Datos sintéticos generados con Faker · conexión de solo lectura a PostgreSQL")
    with derecha:
        st.caption(f"Última carga del ETL: {hora_local(carga):%d/%m/%Y %H:%M}")

    # --- Filtros (barra lateral) ---
    st.sidebar.header("Filtros")
    rango = st.sidebar.date_input(
        "Rango de fechas", value=(minimo, maximo), min_value=minimo, max_value=maximo
    )
    if not isinstance(rango, (tuple, list)) or len(rango) != 2:
        st.info("Elige la fecha de inicio y la de fin en la barra lateral.")
        st.stop()
    desde, hasta = rango
    if desde > hasta:
        st.error("La fecha de inicio no puede ser posterior a la fecha de fin.")
        st.stop()

    ventas = cargar_ventas(desde, hasta)
    categorias = sorted(ventas["categoria"].unique())
    ciudades = sorted(ventas["ciudad"].unique())
    cat_elegidas = st.sidebar.multiselect("Categorías", categorias, default=categorias)
    ciu_elegidas = st.sidebar.multiselect("Ciudades", ciudades, default=ciudades)
    ventas = ventas[ventas["categoria"].isin(cat_elegidas) & ventas["ciudad"].isin(ciu_elegidas)]

    if ventas.empty:
        st.warning("No hay ventas con los filtros elegidos.")
        st.stop()
    st.sidebar.caption(f"Mostrando {len(ventas):,} ventas".replace(",", "."))

    # --- Agrupaciones ---
    periodo = ventas["fecha"].dt.to_period("M")
    mensual = ventas.groupby(periodo).agg(
        monto=("monto", "sum"),
        ventas=("venta_id", "count"),
        clientes=("cliente_id", "nunique"),
        unidades=("cantidad", "sum"),
    )
    mensual["ticket"] = mensual["monto"] / mensual["ventas"]
    mensual["mes_ts"] = mensual.index.to_timestamp()

    total = ventas["monto"].sum()
    base = total if total else 1  # evita dividir por cero en los porcentajes
    por_categoria = ventas.groupby("categoria")["monto"].sum().sort_values(ascending=False)
    por_producto = ventas.groupby("producto")["monto"].sum().sort_values(ascending=False)
    por_ciudad = ventas.groupby("ciudad")["monto"].sum().sort_values(ascending=False)
    por_cliente = (
        ventas.groupby(["cliente_id", "cliente"])["monto"].sum().sort_values(ascending=False)
    )

    # --- KPIs ---
    kpis = [
        ("Ventas totales", pesos(total), mensual["monto"]),
        ("Número de ventas", f"{len(ventas):,}".replace(",", "."), mensual["ventas"]),
        ("Ticket promedio", pesos(total / len(ventas)), mensual["ticket"]),
        ("Clientes activos", str(ventas["cliente_id"].nunique()), mensual["clientes"]),
        ("Unidades vendidas", f"{int(ventas['cantidad'].sum()):,}".replace(",", "."), mensual["unidades"]),
    ]
    for columna, (titulo, valor, serie) in zip(st.columns(5), kpis):
        tarjeta_kpi(columna, titulo, valor, serie)

    tab_resumen, tab_ranking, tab_detalle = st.tabs(["Resumen", "Clientes y productos", "Detalle"])

    # --- Pestaña 1: resumen ---
    with tab_resumen:
        ancha, angosta = st.columns([2, 1])
        with ancha.container(border=True):
            st.subheader("Ventas por mes")
            st.altair_chart(estilo(grafico_mensual(mensual), 430), theme=None)
        with angosta.container(border=True):
            st.subheader("Ventas por categoría")
            torta, datos_torta = grafico_torta(por_categoria)
            st.altair_chart(estilo(torta, 260), theme=None)
            st.markdown(leyenda_html(datos_torta), unsafe_allow_html=True)

        with st.container(border=True):
            st.subheader("Ventas por ciudad")
            st.altair_chart(
                estilo(grafico_ciudades(por_ciudad), max(len(por_ciudad) * 44, 220)), theme=None
            )

        # --- Puntos fuertes del negocio (se calculan con los datos filtrados) ---
        st.subheader("Puntos fuertes del negocio")
        mejor_mes = mensual["monto"].idxmax()
        categorias_conocidas = por_categoria.drop("Sin categoría", errors="ignore")
        ciudades_conocidas = por_ciudad.drop("Sin ciudad", errors="ignore")
        cinco = st.columns(5)
        tarjeta_fuerte(cinco[0], "📅", "Mes más fuerte", mes_texto(mejor_mes.to_timestamp()),
                       pesos(mensual.loc[mejor_mes, "monto"]), mensual.loc[mejor_mes, "monto"], base)
        tarjeta_fuerte(cinco[1], "🏆", "Producto estrella", por_producto.index[0],
                       pesos(por_producto.iloc[0]), por_producto.iloc[0], base)
        if not categorias_conocidas.empty:
            tarjeta_fuerte(cinco[2], "🛍️", "Categoría líder", categorias_conocidas.index[0],
                           pesos(categorias_conocidas.iloc[0]), categorias_conocidas.iloc[0], base)
        if not ciudades_conocidas.empty:
            tarjeta_fuerte(cinco[3], "📍", "Ciudad líder", ciudades_conocidas.index[0],
                           pesos(ciudades_conocidas.iloc[0]), ciudades_conocidas.iloc[0], base)
        tarjeta_fuerte(cinco[4], "👥", "Concentración", "10 mejores clientes",
                       pesos(por_cliente.head(10).sum()), por_cliente.head(10).sum(), base)

    # --- Pestaña 2: rankings ---
    with tab_ranking:
        izquierda, derecha = st.columns(2)
        with izquierda.container(border=True):
            st.subheader("Top 10 clientes")
            top_clientes = por_cliente.head(10).reset_index()
            top_clientes["etiqueta"] = (
                top_clientes["cliente"] + " (#" + top_clientes["cliente_id"].astype(str) + ")"
            )
            st.altair_chart(estilo(grafico_barras(top_clientes, "etiqueta"), 380), theme=None)
        with derecha.container(border=True):
            st.subheader("Top 10 productos")
            st.altair_chart(
                estilo(grafico_barras(por_producto.head(10).reset_index(), "producto"), 380),
                theme=None,
            )

    # --- Pestaña 3: detalle (nunca incluye el email) ---
    with tab_detalle:
        st.caption("Las 200 ventas más recientes con los filtros elegidos")
        detalle = ventas.sort_values("fecha", ascending=False).head(200)[
            ["venta_id", "fecha", "cliente", "producto", "categoria", "ciudad", "cantidad", "monto"]
        ]
        st.dataframe(
            detalle,
            hide_index=True,
            column_config={
                "venta_id": "ID",
                "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                "cliente": "Cliente",
                "producto": "Producto",
                "categoria": "Categoría",
                "ciudad": "Ciudad",
                "cantidad": "Cant.",
                "monto": st.column_config.NumberColumn("Monto (COP)", format="$%d"),
            },
        )


try:
    main()
except ErrorDashboard as error:
    st.error(str(error))
except Exception:
    # Errores imprevistos: el detalle va solo al log, el usuario ve un mensaje corto
    logger.exception("Error inesperado en el dashboard")
    st.error("Ocurrió un error inesperado. Revisa los logs.")