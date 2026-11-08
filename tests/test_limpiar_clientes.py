import pandas as pd

from src.clean import limpiar_clientes


def crear_clientes_crudos():
    """Seis filas, cada una con un problema distinto (todo como texto, como en el CSV)."""
    return pd.DataFrame({
        "cliente_id":     ["1", "2", "2", "x", "5", "6"],
        "nombre":         ["  ana   PÉREZ ", "luis gómez", "luis gómez", "pedro", "   ", "maría"],
        "email":          ["ANA@Example.com", "no-es-email", "luis@example.com",
                           "pedro@example.com", "z@example.com", "maria@example.com"],
        "ciudad":         ["MEDELLÍN", "bogotá", "bogotá", "cali", "cali", "  cali "],
        "fecha_registro": ["2023-06-05", "13/07/2023", "2023-01-01",
                           "2023-01-01", "2023-01-01", "2019-05-01"],
    })
    # Fila 0: correcta pero sucia | Fila 1: email inválido | Fila 2: ID repetido
    # Fila 3: ID no numérico      | Fila 4: nombre vacío   | Fila 5: fecha anterior a 2020


def test_limpiar_clientes_conserva_y_corrige_las_filas_validas():
    limpio, _ = limpiar_clientes(crear_clientes_crudos())
    assert limpio["cliente_id"].tolist() == [1, 2, 6]
    assert limpio["nombre"].tolist() == ["Ana Pérez", "Luis Gómez", "María"]
    assert limpio["ciudad"].tolist() == ["Medellín", "Bogotá", "Cali"]


def test_limpiar_clientes_vacia_email_y_fecha_invalidos_pero_conserva_al_cliente():
    limpio, _ = limpiar_clientes(crear_clientes_crudos())
    assert limpio["email"].iloc[0] == "ana@example.com"
    assert pd.isna(limpio["email"].iloc[1])               # cliente 2 sigue, sin email
    assert limpio["fecha_registro"].iloc[1] == pd.Timestamp("2023-07-13")
    assert pd.isna(limpio["fecha_registro"].iloc[2])      # cliente 6 sigue, sin fecha


def test_limpiar_clientes_guarda_los_descartados_con_su_motivo():
    _, rechazado = limpiar_clientes(crear_clientes_crudos())
    assert len(rechazado) == 3
    assert set(rechazado["motivo_rechazo"]) == {
        "cliente_id vacío o no numérico",
        "cliente duplicado",
        "nombre vacío",
    }
    assert "x" in rechazado["cliente_id"].tolist()        # se guarda la versión cruda


def test_limpiar_clientes_no_modifica_el_dataframe_original():
    crudo = crear_clientes_crudos()
    copia = crudo.copy()
    limpiar_clientes(crudo)
    pd.testing.assert_frame_equal(crudo, copia)