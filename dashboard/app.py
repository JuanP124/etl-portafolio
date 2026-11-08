"""
app.py — Sales Performance Analytics (versión 5, números en negrita).

Se conecta a PostgreSQL con dashboard_user: SOLO LECTURA y sin acceso a la
columna email. Se ejecuta desde la carpeta del proyecto, con el venv activo:

    streamlit run dashboard/app.py
"""

import html
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
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

# Textos para los datos que vienen vacíos en la base
SIN_CATEGORIA = "Uncategorized"
SIN_CIUDAD = "No city"

# --- Paleta del diseño: un solo acento (morado) y un dorado para resaltar ---
MORADO = "#8B5CF6"
DORADO = "#FBBF24"
TEXTO = "#E6E6F0"
GRIS = "#A1A1B5"
LINEA = "#262638"
# Tonos de morado bien distintos entre sí (para la dona)
PALETA_MORADO = ["#5B21B6", "#C4B5FD", "#7C3AED", "#EDE9FE", "#A78BFA", "#8B5CF6"]
TONOS_CLAROS = {"#C4B5FD", "#EDE9FE", "#A78BFA"}  # llevan texto oscuro encima
MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CONFIG_PLOTLY = {"displayModeBar": False}  # sin barra de herramientas sobre los gráficos

# Configuración de página en modo ancho (debe ser la primera llamada a Streamlit)
st.set_page_config(page_title="Sales Performance Analytics", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1500px;}
    footer {visibility: hidden;}

    /* Títulos más gruesos */
    h1, h2, h3, [data-testid="stHeading"] h1, [data-testid="stHeading"] h2,
    [data-testid="stHeading"] h3 {font-weight: 800 !important; letter-spacing: -0.3px;}
    button[data-baseweb="tab"] p {font-weight: 700;}
    [data-testid="stSidebar"] h2 {font-weight: 800 !important;}

    /* Tarjetas KPI */
    .kpi {position:relative; overflow:hidden; min-height:200px; padding:18px 16px 14px 16px;
          background:linear-gradient(145deg,#1d1736 0%,#14141F 70%);
          border:1px solid #2d2450; border-radius:16px;}
    .kpi::before {content:""; position:absolute; top:0; left:0; right:0; height:4px;
                  background:linear-gradient(90deg,#8B5CF6,#C4B5FD);}
    .kpi-icono {font-size:1.5rem; margin-bottom:6px;}
    .kpi-titulo {color:#A78BFA; font-size:.72rem; font-weight:800; letter-spacing:1.2px; text-transform:uppercase;}
    .kpi-valor {color:#FFFFFF; font-weight:800; line-height:1.15; margin:8px 0 2px 0; white-space:nowrap;
                font-size:clamp(1.25rem, 1.9vw, 1.9rem);}
    .kpi-detalle {color:#A1A1B5; font-size:.8rem; min-height:2.3em;}
    .kpi-pie {display:flex; align-items:center; justify-content:space-between; gap:8px;
              margin-top:10px; padding-top:10px; border-top:1px solid #262638;}
    .kpi-etiqueta {color:#A1A1B5; font-size:.72rem;}
    .delta {font-weight:700; font-size:.82rem; padding:3px 10px; border-radius:99px; white-space:nowrap;}
    .delta-sube {color:#34D399; background:rgba(52,211,153,.14);}
    .delta-baja {color:#F87171; background:rgba(248,113,113,.14);}
    .delta-nulo {color:#A1A1B5; background:rgba(161,161,181,.12);}

    /* Hitos de desempeño */
    .hito {display:flex; align-items:center; gap:12px; padding:10px 12px; margin-bottom:8px;
           background:linear-gradient(145deg,#1d1736 0%,#14141F 75%); border:1px solid #2d2450;
           border-left:4px solid #8B5CF6; border-radius:12px;}
    .hito-icono {font-size:1.35rem; flex:none;}
    .hito-texto {flex:1; min-width:0;}
    .hito-titulo {color:#A78BFA; font-size:.68rem; font-weight:800; letter-spacing:1.1px; text-transform:uppercase;}
    .hito-valor {color:#FFFFFF; font-weight:700; font-size:1rem; line-height:1.2;}
    .hito-cifra {text-align:right; flex:none;}
    .hito-monto {color:#FFFFFF; font-weight:700; font-size:.92rem;}
    .hito-pct {color:#A1A1B5; font-size:.75rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


class ErrorDashboard(Exception):
    """Error con un mensaje seguro para mostrar al usuario.

    El detalle técnico va solo al archivo logs/dashboard.log.
    """


# =============================================================================
# Conexión y logs
# =============================================================================
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
        raise ErrorDashboard("Database configuration is missing. Check the .env file.")

    usuario = os.environ["DASH_DB_USER"]
    if usuario in USUARIOS_PROHIBIDOS:
        logger.error("El dashboard está configurado con un usuario con demasiados permisos")
        raise ErrorDashboard("The dashboard must use a read-only user. Check the .env file.")

    try:
        puerto = int(os.environ["DB_PORT"])
    except ValueError:
        logger.error("DB_PORT no es un número válido")
        raise ErrorDashboard("The database configuration is not valid.") from None

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
        raise ErrorDashboard("Could not query the database. Check the logs.") from None


# =============================================================================
# Carga de datos (con caché para no repetir consultas en cada interacción)
# =============================================================================
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
        raise ErrorDashboard("No sales loaded yet. Run the ETL first.")
    return pd.Timestamp(desde).date(), pd.Timestamp(hasta).date(), pd.Timestamp(carga)


@st.cache_data(ttl=300)
def cargar_opciones():
    """Categorías y ciudades disponibles en TODA la base (no dependen de las fechas)."""
    cats = _consultar(
        text("SELECT DISTINCT COALESCE(categoria, :sin) AS valor FROM productos"),
        {"sin": SIN_CATEGORIA},
    )
    ciud = _consultar(
        text("SELECT DISTINCT COALESCE(ciudad, :sin) AS valor FROM clientes"),
        {"sin": SIN_CIUDAD},
    )
    return sorted(cats["valor"].tolist()), sorted(ciud["valor"].tolist())


@st.cache_data(ttl=300, show_spinner="Querying the database...")
def cargar_ventas(desde, hasta):
    """Ventas del rango de fechas, ya unidas con cliente y producto."""
    df = _consultar(SQL_VENTAS, {"desde": desde, "hasta": hasta})
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["monto"] = df["monto"].astype(float)
    df["categoria"] = df["categoria"].fillna(SIN_CATEGORIA)
    df["ciudad"] = df["ciudad"].fillna(SIN_CIUDAD)
    return df


# =============================================================================
# Formato de números y textos
# =============================================================================
def num(valor, decimales=0):
    """Número con formato inglés: 1,234,567.8"""
    return f"{valor:,.{decimales}f}"


def pesos(valor):
    """Monto completo: COP 1,234,567"""
    return "COP " + num(valor)


def pesos_corto(valor):
    """Monto abreviado para que quepa entero en una tarjeta: COP 220.5 M"""
    if abs(valor) >= 1_000_000_000:
        return f"COP {num(valor / 1_000_000_000, 2)} B"
    if abs(valor) >= 1_000_000:
        return f"COP {num(valor / 1_000_000, 1)} M"
    if abs(valor) >= 1_000:
        return f"COP {num(valor / 1_000)} K"
    return pesos(valor)


def mes_texto(marca):
    """Nombre del mes: 'Jul 2026'."""
    return f"{MESES[marca.month - 1]} {marca.year}"


def hora_local(marca):
    """Pasa la hora de la base (UTC) a hora de Colombia."""
    if marca.tzinfo is None:
        marca = marca.tz_localize("UTC")
    return marca.tz_convert("America/Bogota")


def variacion_mensual(serie, desde, hasta):
    """Cambio porcentual entre los dos últimos meses COMPLETOS del rango.

    Un mes a medias no se compara: daría una variación engañosa.
    Devuelve None si no hay al menos dos meses completos.
    """
    completos = [
        p for p in serie.index
        if p.start_time.date() >= desde and p.end_time.date() <= hasta
    ]
    if len(completos) < 2:
        return None
    anterior, ultimo = serie.loc[completos[-2]], serie.loc[completos[-1]]
    if anterior == 0:
        return None
    return ultimo / anterior - 1


# =============================================================================
# Gráficos (Plotly)
# =============================================================================
# Fuente en negrita para los números de los ejes
FUENTE_EJE = dict(size=13, color=TEXTO, weight="bold")


def estilo(fig, altura, margen=None):
    """Aplica el estilo oscuro común a todos los gráficos."""
    fig.update_layout(
        height=altura,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXTO, size=13),
        margin=margen or dict(l=0, r=10, t=10, b=0),
    )
    return fig


def grafico_mensual(mensual):
    """Área con marcadores; el mes de mayor venta se resalta con una anotación."""
    etiquetas = [mes_texto(p.to_timestamp()) for p in mensual.index]
    valores = (mensual["monto"] / 1_000_000).tolist()
    i_pico = valores.index(max(valores))

    colores = [MORADO] * len(valores)
    tamanos = [8] * len(valores)
    colores[i_pico], tamanos[i_pico] = DORADO, 15

    fig = go.Figure(go.Scatter(
        x=etiquetas, y=valores, mode="lines+markers",
        line=dict(color=MORADO, width=3, shape="spline"),
        fill="tozeroy", fillcolor="rgba(139,92,246,0.22)",
        marker=dict(color=colores, size=tamanos, line=dict(color="#0B0B14", width=1.5)),
        hovertemplate="%{x}<br>COP %{y:,.1f} M<extra></extra>",
    ))
    fig.add_annotation(
        x=etiquetas[i_pico], y=valores[i_pico],
        text=f"<b>Peak: {etiquetas[i_pico]}</b><br><b>COP {num(valores[i_pico], 1)} M</b>",
        showarrow=True, arrowhead=2, arrowcolor=DORADO, ax=0, ay=-55,
        bgcolor="#1d1736", bordercolor=DORADO, borderwidth=1,
        font=dict(color="#FFFFFF", size=13),
    )
    fig.update_xaxes(
        type="category", tickangle=-45, showgrid=False, linecolor=LINEA, tickfont=FUENTE_EJE,
    )
    fig.update_yaxes(
        title_text="Millions of COP", gridcolor=LINEA, zeroline=False,
        range=[0, (max(valores) or 1) * 1.3], tickfont=FUENTE_EJE,
    )
    return estilo(fig, 400, dict(l=0, r=10, t=30, b=0))


def grafico_categorias(por_categoria):
    """Dona en tonos morados, con porcentaje y valor dentro (en negrita); leyenda arriba."""
    datos = por_categoria.rename("monto").reset_index()
    total = datos["monto"].sum()
    colores = (PALETA_MORADO * 2)[: len(datos)]
    colores_texto = ["#1B1033" if c in TONOS_CLAROS else "#FFFFFF" for c in colores]
    textos = [
        f"<b>{m / total:.0%}</b><br><b>{num(m / 1_000_000, 1)} M</b>" for m in datos["monto"]
    ]

    fig = go.Figure(go.Pie(
        labels=datos["categoria"], values=datos["monto"], hole=0.5, sort=False,
        text=textos, textinfo="text", textposition="inside",
        insidetextorientation="horizontal",
        textfont=dict(color=colores_texto, size=14),
        marker=dict(colors=colores, line=dict(color="#0B0B14", width=2)),
        hovertemplate="%{label}<br>COP %{value:,.0f}<br>%{percent}<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{num(total / 1_000_000, 1)} M</b><br><b>COP</b>", showarrow=False,
        x=0.5, y=0.5, font=dict(size=15, color=TEXTO),
    )
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    return estilo(fig, 400, dict(l=0, r=0, t=70, b=0))


def barras_horizontales(datos, columna, altura):
    """Barras gruesas: mayor valor arriba, valor en negrita dentro de la barra, sin eje numérico.

    datos necesita las columnas [columna, 'monto'].
    """
    datos = datos.sort_values("monto", ascending=True)  # la última barra queda arriba
    millones = datos["monto"] / 1_000_000
    fig = go.Figure(go.Bar(
        x=millones, y=datos[columna], orientation="h",
        marker=dict(color=MORADO),
        text=[f"<b>{num(m, 1)} M</b>" for m in millones],
        textposition="auto", insidetextanchor="end",
        textfont=dict(color="#FFFFFF", size=14),
        hovertemplate="%{y}<br>COP %{x:,.2f} M<extra></extra>",
    ))
    fig.update_xaxes(
        title_text="Millions of COP", showticklabels=False, showgrid=False, zeroline=False,
    )
    fig.update_yaxes(title_text=None, automargin=True, categoryorder="total ascending")
    fig.update_layout(bargap=0.18)
    return estilo(fig, altura)


# =============================================================================
# Piezas de interfaz
# =============================================================================
def tarjeta_kpi(columna, icono, titulo, valor, detalle, variacion):
    """Tarjeta KPI: icono, título, valor abreviado, detalle exacto y variación mensual."""
    if variacion is None:
        pastilla = '<span class="delta delta-nulo">n/a</span>'
    else:
        clase = "delta-sube" if variacion >= 0 else "delta-baja"
        flecha = "▲" if variacion >= 0 else "▼"
        pastilla = f'<span class="delta {clase}">{flecha} {abs(variacion):.1%}</span>'
    columna.markdown(
        '<div class="kpi">'
        f'<div class="kpi-icono">{icono}</div>'
        f'<div class="kpi-titulo">{html.escape(titulo)}</div>'
        f'<div class="kpi-valor">{html.escape(valor)}</div>'
        f'<div class="kpi-detalle">{html.escape(detalle)}</div>'
        f'<div class="kpi-pie"><span class="kpi-etiqueta">vs previous month</span>{pastilla}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def hitos_html(hitos, total):
    """Tarjetas de 'Performance Highlights'. hitos = [(icono, título, valor, monto)]."""
    tarjetas = []
    for icono, titulo, valor, monto in hitos:
        tarjetas.append(
            '<div class="hito">'
            f'<div class="hito-icono">{icono}</div>'
            '<div class="hito-texto">'
            f'<div class="hito-titulo">{html.escape(titulo)}</div>'
            f'<div class="hito-valor">{html.escape(valor)}</div>'
            "</div>"
            '<div class="hito-cifra">'
            f'<div class="hito-monto">{html.escape(pesos_corto(monto))}</div>'
            f'<div class="hito-pct">{monto / total:.0%} of total</div>'
            "</div></div>"
        )
    return "".join(tarjetas)


def main():
    minimo, maximo, carga = cargar_rango()
    categorias, ciudades = cargar_opciones()

    # ------------------------------------------------------------------
    # Barra lateral: filtros.
    # Viven FUERA de las pestañas y tienen 'key', así su estado se conserva
    # al cambiar de pestaña (Streamlit ejecuta todas las pestañas en cada paso).
    # ------------------------------------------------------------------
    st.sidebar.header("Filters")
    rango = st.sidebar.date_input(
        "Date range", value=(minimo, maximo),
        min_value=minimo, max_value=maximo, key="f_fechas",
    )
    if not isinstance(rango, (tuple, list)) or len(rango) != 2:
        st.info("Choose a start and an end date in the sidebar.")
        st.stop()
    desde, hasta = rango
    if desde > hasta:
        st.error("The start date cannot be later than the end date.")
        st.stop()

    # Filtros vacíos por defecto: vacío significa "mostrar todo"
    sel_categorias = st.sidebar.multiselect(
        "Categories", categorias, default=[], placeholder="All categories", key="f_categorias"
    )
    sel_ciudades = st.sidebar.multiselect(
        "Cities", ciudades, default=[], placeholder="All cities", key="f_ciudades"
    )

    ventas = cargar_ventas(desde, hasta)
    if sel_categorias:  # solo se filtra si el usuario eligió algo
        ventas = ventas[ventas["categoria"].isin(sel_categorias)]
    if sel_ciudades:
        ventas = ventas[ventas["ciudad"].isin(sel_ciudades)]

    st.sidebar.caption(f"Showing {num(len(ventas))} transactions")
    st.sidebar.divider()
    # El detalle técnico vive en la barra lateral, no en el cuerpo principal
    st.sidebar.caption("Synthetic data generated with Faker · read-only connection to PostgreSQL")
    st.sidebar.caption(f"Last ETL load: {hora_local(carga):%Y-%m-%d %H:%M} (Colombia time)")

    # --- Encabezado ---
    st.title("📊 Sales Performance Analytics")
    st.caption(f"Executive summary · {desde:%Y-%m-%d} to {hasta:%Y-%m-%d}")

    if ventas.empty:
        st.warning("No sales match the selected filters.")
        st.stop()

    # --- Agrupaciones ---
    periodo = ventas["fecha"].dt.to_period("M")
    mensual = ventas.groupby(periodo).agg(
        monto=("monto", "sum"),
        ventas=("venta_id", "count"),
        clientes=("cliente_id", "nunique"),
        unidades=("cantidad", "sum"),
    )
    # Todos los meses del rango (los meses sin ventas cuentan como 0)
    meses = pd.period_range(pd.Period(desde, freq="M"), pd.Period(hasta, freq="M"), freq="M")
    mensual = mensual.reindex(meses, fill_value=0)
    mensual["ticket"] = (mensual["monto"] / mensual["ventas"]).where(mensual["ventas"] > 0, 0.0)

    total = ventas["monto"].sum()
    por_categoria = ventas.groupby("categoria")["monto"].sum().sort_values(ascending=False)
    por_producto = ventas.groupby("producto")["monto"].sum().sort_values(ascending=False)
    # Las ventas sin ciudad no se muestran en el gráfico ni en los hitos
    por_ciudad = (
        ventas.groupby("ciudad")["monto"].sum().drop(SIN_CIUDAD, errors="ignore")
        .sort_values(ascending=False)
    )
    por_cliente = (
        ventas.groupby(["cliente_id", "cliente"])["monto"].sum().sort_values(ascending=False)
    )

    tab_resumen, tab_ranking, tab_detalle = st.tabs(
        ["Overview", "Customers & Products", "Details"]
    )

    # ==================================================================
    # Pestaña 1: Overview
    # ==================================================================
    with tab_resumen:
        # --- Franja superior: 5 KPIs con variación mensual ---
        ticket = total / len(ventas)
        kpis = [
            ("💰", "Total sales", pesos_corto(total), pesos(total), mensual["monto"]),
            ("🧾", "Transaction volume", num(len(ventas)),
             "Orders recorded in the selected range", mensual["ventas"]),
            ("🎫", "Average ticket", pesos_corto(ticket), pesos(ticket), mensual["ticket"]),
            ("👥", "Active customers", num(ventas["cliente_id"].nunique()),
             "Customers with at least one purchase", mensual["clientes"]),
            ("📦", "Units sold", num(int(ventas["cantidad"].sum())),
             "Total units shipped", mensual["unidades"]),
        ]
        for columna, (icono, titulo, valor, detalle, serie) in zip(st.columns(5), kpis):
            tarjeta_kpi(columna, icono, titulo, valor, detalle,
                        variacion_mensual(serie, desde, hasta))
        st.caption(
            "Changes compare the latest full month in the range with the previous full month. "
            "n/a means the range has fewer than two full months."
        )

        # --- Bloque central: tendencia (66%) y categorías (33%) ---
        ancha, angosta = st.columns([2, 1])
        with ancha.container(border=True):
            st.subheader("Monthly Sales")
            st.plotly_chart(grafico_mensual(mensual), theme=None, config=CONFIG_PLOTLY)
        with angosta.container(border=True):
            st.subheader("Sales by Category")
            st.plotly_chart(grafico_categorias(por_categoria), theme=None, config=CONFIG_PLOTLY)

        # --- Bloque inferior: ciudades (izquierda) e hitos (derecha) ---
        izquierda, derecha = st.columns([3, 2])
        with izquierda.container(border=True):
            st.subheader("Sales by City")
            if por_ciudad.empty:
                st.info("No sales with a registered city in this selection.")
            else:
                altura = max(len(por_ciudad) * 52, 340)
                st.plotly_chart(
                    barras_horizontales(por_ciudad.rename("monto").reset_index(), "ciudad", altura),
                    theme=None, config=CONFIG_PLOTLY,
                )
        with derecha.container(border=True):
            st.subheader("Performance Highlights")
            mejor_mes = mensual["monto"].idxmax()
            categorias_conocidas = por_categoria.drop(SIN_CATEGORIA, errors="ignore")
            hitos = [
                ("📅", "Peak month", mes_texto(mejor_mes.to_timestamp()), mensual.loc[mejor_mes, "monto"]),
                ("🏆", "Top product", por_producto.index[0], por_producto.iloc[0]),
            ]
            if not categorias_conocidas.empty:
                hitos.append(("🛍️", "Top category", categorias_conocidas.index[0],
                              categorias_conocidas.iloc[0]))
            if not por_ciudad.empty:
                hitos.append(("📍", "Top city", por_ciudad.index[0], por_ciudad.iloc[0]))
            hitos.append(("👥", "Concentration", "Top 10 customers", por_cliente.head(10).sum()))
            st.markdown(hitos_html(hitos, total), unsafe_allow_html=True)

    # ==================================================================
    # Pestaña 2: Customers & Products
    # ==================================================================
    with tab_ranking:
        izquierda, derecha = st.columns(2)
        with izquierda.container(border=True):
            st.subheader("Top 10 Customers")
            top_clientes = por_cliente.head(10).rename("monto").reset_index()
            top_clientes["etiqueta"] = (
                top_clientes["cliente"] + " (#" + top_clientes["cliente_id"].astype(str) + ")"
            )
            st.plotly_chart(
                barras_horizontales(top_clientes[["etiqueta", "monto"]], "etiqueta", 460),
                theme=None, config=CONFIG_PLOTLY,
            )
        with derecha.container(border=True):
            st.subheader("Top 10 Products")
            top_productos = por_producto.head(10).rename("monto").reset_index()
            st.plotly_chart(
                barras_horizontales(top_productos, "producto", 460),
                theme=None, config=CONFIG_PLOTLY,
            )

    # ==================================================================
    # Pestaña 3: Details (nunca incluye el email)
    # ==================================================================
    with tab_detalle:
        st.caption("The 200 most recent transactions for the selected filters")
        detalle = ventas.sort_values("fecha", ascending=False).head(200)[
            ["venta_id", "fecha", "cliente", "producto", "categoria", "ciudad", "cantidad", "monto"]
        ]
        st.dataframe(
            detalle,
            hide_index=True,
            column_config={
                "venta_id": "ID",
                "fecha": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "cliente": "Customer",
                "producto": "Product",
                "categoria": "Category",
                "ciudad": "City",
                "cantidad": "Qty",
                "monto": st.column_config.NumberColumn("Amount (COP)", format="$%d"),
            },
        )


try:
    main()
except ErrorDashboard as error:
    st.error(str(error))
except Exception:
    # Errores imprevistos: el detalle va solo al log, el usuario ve un mensaje corto
    logger.exception("Error inesperado en el dashboard")
    st.error("An unexpected error occurred. Check the logs.")