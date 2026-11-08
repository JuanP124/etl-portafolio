import pandas as pd

from src.clean import limpiar_ventas

# IDs que "sobrevivieron" a la limpieza de clientes y productos
IDS_CLIENTES = [10]
IDS_PRODUCTOS = [100]


def crear_ventas_crudas():
    """Nueve filas (todo como texto, como en el CSV). Cada una tiene un caso distinto."""
    filas = [
        # venta_id, cliente_id, producto_id, fecha,        cantidad, monto
        ["1",       "10",       "100",       "27-04-2025", "2",      "COP 22000"],  # 0 válida, sucia
        ["2",       "10",       "100",       "2025-10-28", "3",      "$25.500"],    # 1 válida, sucia
        ["1",       "10",       "100",       "2025-01-01", "1",      "1000"],       # 2 venta repetida
        ["x",       "10",       "100",       "2025-01-01", "1",      "1000"],       # 3 ID no numérico
        ["4",       "10",       "100",       "2019-05-01", "1",      "1000"],       # 4 fecha anterior a 2020
        ["5",       "10",       "100",       "2025-01-01", "0",      "1000"],       # 5 cantidad cero
        ["6",       "10",       "100",       "2025-01-01", "1",      "mucho"],      # 6 monto ilegible
        ["7",       "999",      "100",       "2025-01-01", "1",      "1000"],       # 7 cliente inexistente
        ["8",       "10",       "999",       "2025-01-01", "1",      "1000"],       # 8 producto inexistente
    ]
    columnas = ["venta_id", "cliente_id", "producto_id", "fecha", "cantidad", "monto"]
    return pd.DataFrame(filas, columns=columnas)


def test_limpiar_ventas_conserva_y_convierte_las_ventas_validas():
    limpio, _ = limpiar_ventas(crear_ventas_crudas(), IDS_CLIENTES, IDS_PRODUCTOS)
    assert limpio["venta_id"].tolist() == [1, 2]
    assert limpio["cantidad"].tolist() == [2, 3]
    assert limpio["monto"].tolist() == [22000.0, 25500.0]
    assert limpio["fecha"].tolist() == [pd.Timestamp("2025-04-27"), pd.Timestamp("2025-10-28")]


def test_limpiar_ventas_descarta_cada_caso_con_su_motivo():
    _, rechazado = limpiar_ventas(crear_ventas_crudas(), IDS_CLIENTES, IDS_PRODUCTOS)
    assert len(rechazado) == 7
    assert set(rechazado["motivo_rechazo"]) == {
        "algún ID vacío o no numérico",
        "venta duplicada",
        "fecha inválida o fuera de rango",
        "cantidad vacía, cero o negativa",
        "monto vacío o con formato no reconocido",
        "cliente_id no existe en clientes limpios",
        "producto_id no existe en productos limpios",
    }


def test_limpiar_ventas_guarda_la_version_cruda_de_lo_descartado():
    _, rechazado = limpiar_ventas(crear_ventas_crudas(), IDS_CLIENTES, IDS_PRODUCTOS)
    assert "mucho" in rechazado["monto"].tolist()   # no se guarda el NaN, sino el texto original
    assert "x" in rechazado["venta_id"].tolist()


def test_limpiar_ventas_no_modifica_el_dataframe_original():
    crudo = crear_ventas_crudas()
    copia = crudo.copy()
    limpiar_ventas(crudo, IDS_CLIENTES, IDS_PRODUCTOS)
    pd.testing.assert_frame_equal(crudo, copia)