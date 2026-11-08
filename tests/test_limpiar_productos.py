import pandas as pd

from src.clean import limpiar_productos


def crear_productos_crudos():
    """Seis filas (todo como texto, como en el archivo). Cada una tiene un caso distinto."""
    return pd.DataFrame({
        "producto_id": ["1", "2", "2", "x", "5", "6"],
        "nombre":      ["  pan   FRANCÉS ", "torta", "torta", "pan", "   ", "café"],
        "categoria":   ["PANADERÍA", "  dulces ", "dulces", "pan", "pan", "   "],
    })
    # Fila 0: válida pero sucia | Fila 1: válida | Fila 2: ID repetido
    # Fila 3: ID no numérico    | Fila 4: nombre vacío | Fila 5: categoría vacía (se conserva)


def test_limpiar_productos_conserva_y_corrige_las_filas_validas():
    limpio, _ = limpiar_productos(crear_productos_crudos())
    assert limpio["producto_id"].tolist() == [1, 2, 6]
    assert limpio["nombre"].tolist() == ["Pan Francés", "Torta", "Café"]
    assert limpio["categoria"].iloc[:2].tolist() == ["Panadería", "Dulces"]


def test_limpiar_productos_conserva_el_producto_si_solo_falta_la_categoria():
    limpio, _ = limpiar_productos(crear_productos_crudos())
    assert pd.isna(limpio["categoria"].iloc[2])   # producto 6 sigue, sin categoría


def test_limpiar_productos_guarda_los_descartados_con_su_motivo():
    _, rechazado = limpiar_productos(crear_productos_crudos())
    assert len(rechazado) == 3
    assert set(rechazado["motivo_rechazo"]) == {
        "producto_id vacío o no numérico",
        "producto duplicado",
        "nombre vacío",
    }


def test_limpiar_productos_no_modifica_el_dataframe_original():
    crudo = crear_productos_crudos()
    copia = crudo.copy()
    limpiar_productos(crudo)
    pd.testing.assert_frame_equal(crudo, copia)