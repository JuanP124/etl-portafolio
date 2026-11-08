import pandas as pd
import pytest

from src.clean import (
    _monto_a_numero,
    convertir_entero,
    convertir_fechas,
    es_duplicado,
    limitar_rango_fechas,
    normalizar_texto,
    validar_email,
)


def test_normalizar_texto_limpia_espacios_y_pone_mayuscula_inicial():
    resultado = normalizar_texto(pd.Series(["  juan   pérez  ", "MARÍA"]))
    assert resultado.tolist() == ["Juan Pérez", "María"]


def test_normalizar_texto_vacio_pasa_a_nulo():
    resultado = normalizar_texto(pd.Series(["   "]))
    assert resultado.isna().all()


def test_convertir_entero_descarta_lo_que_no_es_entero():
    resultado = convertir_entero(pd.Series(["12", " 7 ", "12.5", "abc"]))
    assert resultado.iloc[0] == 12
    assert resultado.iloc[1] == 7
    assert pd.isna(resultado.iloc[2])
    assert pd.isna(resultado.iloc[3])


@pytest.mark.parametrize("texto, esperado", [
    ("125000", 125000.0),
    ("125000.50", 125000.5),
    ("$125.000", 125000.0),
    ("125,000", 125000.0),
    ("COP 125.000", 125000.0),
])
def test_monto_formatos_validos(texto, esperado):
    assert _monto_a_numero(texto) == esperado


@pytest.mark.parametrize("texto", ["-5", "abc", "", None])
def test_monto_invalido_da_nan(texto):
    assert pd.isna(_monto_a_numero(texto))


def test_validar_email():
    resultado = validar_email(pd.Series(["  JUAN@Gmail.com ", "juan@@gmail", "sin_arroba.com"]))
    assert resultado.iloc[0] == "juan@gmail.com"
    assert pd.isna(resultado.iloc[1])
    assert pd.isna(resultado.iloc[2])


def test_convertir_fechas_acepta_varios_formatos():
    resultado = convertir_fechas(pd.Series(["2026-05-10", "10/05/2026", "10-05-2026", "basura"]))
    esperada = pd.Timestamp("2026-05-10")
    assert resultado.iloc[0] == esperada
    assert resultado.iloc[1] == esperada  # 10 de mayo, NO 5 de octubre
    assert resultado.iloc[2] == esperada
    assert pd.isna(resultado.iloc[3])


def test_limitar_rango_fechas_quita_antiguas_y_futuras():
    manana = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    fechas = pd.Series(pd.to_datetime(["2019-12-31", "2026-05-10"]))
    fechas.loc[2] = manana
    resultado = limitar_rango_fechas(fechas)
    assert pd.isna(resultado.iloc[0])
    assert resultado.iloc[1] == pd.Timestamp("2026-05-10")
    assert pd.isna(resultado.iloc[2])


def test_es_duplicado_conserva_la_primera_aparicion():
    df = pd.DataFrame({"id": [1, 2, 1]})
    assert es_duplicado(df, "id").tolist() == [False, False, True]