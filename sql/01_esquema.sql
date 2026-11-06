-- Esquema de etl_portafolio_db.
-- Se ejecuta como administrador (postgres). Es seguro repetirlo: usa IF NOT EXISTS.
-- Orden de carga: clientes, productos y al final ventas (ventas depende de las otras dos).

CREATE TABLE IF NOT EXISTS clientes (
    cliente_id     INTEGER PRIMARY KEY,
    nombre         TEXT NOT NULL,
    email          TEXT,
    ciudad         TEXT,
    fecha_registro DATE,
    cargado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS productos (
    producto_id INTEGER PRIMARY KEY,
    nombre      TEXT NOT NULL,
    categoria   TEXT,
    cargado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ventas (
    venta_id    INTEGER PRIMARY KEY,
    cliente_id  INTEGER NOT NULL REFERENCES clientes (cliente_id),
    producto_id INTEGER NOT NULL REFERENCES productos (producto_id),
    fecha       DATE NOT NULL,
    cantidad    INTEGER NOT NULL CHECK (cantidad > 0),
    monto       NUMERIC(12, 2) NOT NULL CHECK (monto >= 0),
    cargado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Acelera las consultas del dashboard por rango de fechas
CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas (fecha);

-- Permisos mínimos
GRANT USAGE ON SCHEMA public TO etl_user, dashboard_user;

-- El ETL puede leer, insertar y actualizar, pero no borrar
GRANT SELECT, INSERT, UPDATE ON clientes, productos, ventas TO etl_user;

-- El dashboard solo lee, y no puede ver la columna email
GRANT SELECT (cliente_id, nombre, ciudad, fecha_registro) ON clientes TO dashboard_user;
GRANT SELECT ON productos, ventas TO dashboard_user;