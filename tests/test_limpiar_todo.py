import pandas as pd

import src.clean as clean


def crear_crudos():
    """Mini base cruda: el cliente 3 y el producto 2 se descartan por nombre vacío."""
    clientes = pd.DataFrame({
        "cliente_id":     ["1", "2", "3"],
        "nombre":         ["ana", "luis", "   "],
        "email":          ["ana@example.com", "luis@example.com", "otro@example.com"],
        "ciudad":         ["cali", "cali", "cali"],
        "fecha_registro": ["2023-01-01", "2023-01-01", "2023-01-01"],
    })
    productos = pd.DataFrame({
        "producto_id": ["1", "2"],
        "nombre":      ["pan", "   "],
        "categoria":   ["panadería", "dulces"],
    })
    ventas = pd.DataFrame({
        "venta_id":    ["1", "2", "3", "4"],
        "cliente_id":  ["1", "2", "3", "1"],   # la venta 3 usa el cliente descartado
        "producto_id": ["1", "1", "1", "2"],   # la venta 4 usa el producto descartado
        "fecha":       ["2025-01-01"] * 4,
        "cantidad":    ["1"] * 4,
        "monto":       ["1000"] * 4,
    })
    return {"clientes": clientes, "productos": productos, "ventas": ventas}


def test_limpiar_todo_devuelve_las_tres_tablas_limpias_y_rechazadas():
    limpios, rechazados = clean.limpiar_todo(crear_crudos())
    assert set(limpios) == {"clientes", "productos", "ventas"}
    assert set(rechazados) == {"clientes", "productos", "ventas"}


def test_limpiar_todo_descarta_ventas_de_clientes_y_productos_descartados():
    limpios, rechazados = clean.limpiar_todo(crear_crudos())
    assert limpios["clientes"]["cliente_id"].tolist() == [1, 2]
    assert limpios["productos"]["producto_id"].tolist() == [1]
    assert limpios["ventas"]["venta_id"].tolist() == [1, 2]
    assert len(rechazados["clientes"]) == 1
    assert len(rechazados["productos"]) == 1
    assert set(rechazados["ventas"]["motivo_rechazo"]) == {
        "cliente_id no existe en clientes limpios",
        "producto_id no existe en productos limpios",
    }


def test_guardar_resultados_crea_los_seis_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(clean, "CARPETA_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(clean, "CARPETA_REJECTED", tmp_path / "rejected")
    limpios, rechazados = clean.limpiar_todo(crear_crudos())
    clean.guardar_resultados(limpios, rechazados)
    for nombre in ["clientes", "productos", "ventas"]:
        assert (tmp_path / "processed" / f"{nombre}_limpio.csv").exists()
        assert (tmp_path / "rejected" / f"{nombre}_rechazados.csv").exists()


def test_guardar_resultados_los_csv_conservan_los_datos(tmp_path, monkeypatch):
    monkeypatch.setattr(clean, "CARPETA_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(clean, "CARPETA_REJECTED", tmp_path / "rejected")
    limpios, rechazados = clean.limpiar_todo(crear_crudos())
    clean.guardar_resultados(limpios, rechazados)
    ventas = pd.read_csv(tmp_path / "processed" / "ventas_limpio.csv")
    assert ventas["venta_id"].tolist() == [1, 2]
    rechazadas = pd.read_csv(tmp_path / "rejected" / "ventas_rechazados.csv")
    assert "motivo_rechazo" in rechazadas.columns
    assert len(rechazadas) == 2