"""Predicción y preprocesamiento de precios pagados al productor.

Provee funciones para cargar y limpiar los CSV de precios, y generar
predicciones tanto a nivel nacional como por departamento. El módulo
es tolerante a formatos locales (puntos como separador de miles,
comas como decimales) y normaliza nombres de columnas.
"""

import pandas as pd
import numpy as np
import os
import unicodedata
import re
from sklearn.linear_model import LinearRegression

def cargar_datos():
    """
    Carga y limpia los datos del archivo CSV.
    Esta versión es más robusta para encontrar las columnas de Año y Mes.
    """
    rutas = [
        os.path.join("DataSheet", "PRECIO_PAGADO_AL_PRODUCTOR_2_-_RES_0017_DE_2012.csv"),
        os.path.join("DataSheet", "Precio Pagado al Productor - Res 0017 de 2012.csv")
    ]
    for ruta in rutas:
        if os.path.exists(ruta):
            try:
                df = pd.read_csv(ruta, sep=";", encoding="latin-1", engine="python", on_bad_lines='warn')
                break
            except Exception as e:
                print(f"Error al leer el archivo {ruta}: {e}")
                continue
    else:
        raise FileNotFoundError("⚠️ No se encontró el archivo de precios en la carpeta DataSheet")

    def normalizar(col):
        col = col.strip().upper()
        col = unicodedata.normalize("NFKD", col).encode("ASCII", "ignore").decode("ASCII")
        return col

    df.columns = [normalizar(c) for c in df.columns]
    
    posibles_anos = ['ANO', 'ANIO', 'YEAR', 'IAAO']
    col_ano = next((c for c in df.columns if any(p in c for p in posibles_anos)), None)
    posibles_meses = ['MES', 'MONTH']
    col_mes = next((c for c in df.columns if any(p in c for p in posibles_meses)), None)

    if not col_ano or not col_mes:
        print("❌ No se encontraron columnas de AÑO y MES.")
        print(f"Columnas disponibles: {df.columns.tolist()}")
        raise KeyError("❌ No se encontraron columnas de AÑO y MES.")

    df.rename(columns={col_ano: "AÑO", col_mes: "MES"}, inplace=True)
    df["AÑO"] = pd.to_numeric(df["AÑO"], errors="coerce").astype("Int64")
    df.dropna(subset=["AÑO", "MES"], inplace=True)

    columnas_excluidas = ["AÑO", "MES", "MES_NUM", "FECHA"]
    departamentos = [c for c in df.columns if c not in columnas_excluidas]

    for col in departamentos:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace("nd", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .apply(lambda x: re.findall(r"\d+\.\d+|\d+", str(x))[0] if re.findall(r"\d+\.\d+|\d+", str(x)) else None)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(subset=departamentos, how="all", inplace=True)

    meses_map = {
        'ENERO':1,'FEBRERO':2,'MARZO':3,'ABRIL':4,'MAYO':5,'JUNIO':6,
        'JULIO':7,'AGOSTO':8,'SEPTIEMBRE':9,'OCTUBRE':10,'NOVIEMBRE':11,'DICIEMBRE':12
    }
    df["MES_NUM"] = df["MES"].astype(str).str.upper().map(meses_map)
    df.dropna(subset=["MES_NUM"], inplace=True)
    df["MES_NUM"] = df["MES_NUM"].astype(int)
    df["FECHA"] = pd.to_datetime(df["AÑO"].astype(str) + "-" + df["MES_NUM"].astype(str) + "-01")

    return df, departamentos

def predecir_precio_nacional():
    """Entrena un modelo simple (regresión lineal) sobre la serie nacional
    y devuelve un DataFrame con las predicciones para los próximos 6 meses
    junto con un DataFrame de estadísticas resumen.
    """
    df, departamentos = cargar_datos()
    print(f"DEBUG: Datos cargados. Shape: {df.shape}")

    df["NACIONAL"] = df[departamentos].mean(axis=1)
    df = df.dropna(subset=["NACIONAL", "FECHA"]).sort_values("FECHA")
    print(f"DEBUG: DataFrame para predicción nacional. Shape: {df.shape}")
    print(f"DEBUG: Muestra de datos para predicción nacional:\n{df.head()}")

    if df.empty:
        print("🚨 ADVERTENCIA: El DataFrame para la predicción nacional está VACÍO. No se puede entrenar el modelo.")
        # Devuelve un DataFrame vacío pero con las columnas correctas para que no falle el HTML
        fechas_futuras = pd.date_range(start=pd.to_datetime('today'), periods=6, freq="MS")
        df_predicciones = pd.DataFrame({"FECHA": fechas_futuras, "PREDICCION_NACIONAL": 0})
        df_estadistica = pd.DataFrame()
        return df_predicciones, df_estadistica

    df["ORDEN"] = range(len(df))
    X = df[["ORDEN"]]
    y = df["NACIONAL"]
    modelo = LinearRegression()
    modelo.fit(X, y)

    ult_orden = df["ORDEN"].max()
    fechas_futuras = pd.date_range(df["FECHA"].max() + pd.DateOffset(months=1), periods=6, freq="MS")
    ordenes_futuras = np.arange(ult_orden + 1, ult_orden + 7).reshape(-1, 1)
    predicciones = modelo.predict(ordenes_futuras)

    df_predicciones = pd.DataFrame({
        "FECHA": fechas_futuras,
        "PREDICCION_NACIONAL": predicciones
    })

    df_melted = df.melt(id_vars=["AÑO", "MES", "FECHA"], value_vars=departamentos, var_name="DEPARTAMENTO", value_name="PRECIO").dropna()
    idx_max = df_melted['PRECIO'].idxmax()
    idx_min = df_melted['PRECIO'].idxmin()
    max_info = df_melted.loc[idx_max]
    min_info = df_melted.loc[idx_min]
    df_estadistica = pd.DataFrame([{
        "AÑO": max_info["AÑO"], "DEPTO_MAYOR_PRECIO": max_info["DEPARTAMENTO"], "MES_MAX": max_info["MES"], "PRECIO_MAX": max_info["PRECIO"],
        "DEPTO_MENOR_PRECIO": min_info["DEPARTAMENTO"], "MES_MIN": min_info["MES"], "PRECIO_MIN": min_info["PRECIO"]
    }])

    return df_predicciones, df_estadistica


def predecir_precio_departamento(departamento):
    """Entrena un modelo por departamento y devuelve un DataFrame con
    las predicciones para los próximos 6 meses. Si el departamento no
    tiene datos suficientes, devuelve un DataFrame con ceros en las
    predicciones para no romper la vista que las consume.
    """
    df, departamentos = cargar_datos()
    print(f"DEBUG: Datos cargados para depto {departamento}. Shape: {df.shape}")

    if departamento not in departamentos:
        raise ValueError(f"❌ El departamento '{departamento}' no está en los datos disponibles.")

    df_depto = df.dropna(subset=[departamento, "FECHA"]).sort_values("FECHA")
    print(f"DEBUG: DataFrame para predicción de {departamento}. Shape: {df_depto.shape}")
    print(f"DEBUG: Muestra de datos para predicción de {departamento}:\n{df_depto.head()}")

    if df_depto.empty:
        print(f"🚨 ADVERTENCIA: El DataFrame para la predicción de {departamento} está VACÍO. No se puede entrenar el modelo.")
        # Devuelve un DataFrame vacío pero con las columnas correctas
        fechas_futuras = pd.date_range(start=pd.to_datetime('today'), periods=6, freq="MS")
        return pd.DataFrame({"FECHA": fechas_futuras, f"PREDICCION_{departamento}": 0})

    df_depto["ORDEN"] = range(len(df_depto))
    X = df_depto[["ORDEN"]]
    y = df_depto[departamento]
    modelo = LinearRegression()
    modelo.fit(X, y)

    ult_orden = df_depto["ORDEN"].max()
    fechas_futuras = pd.date_range(df_depto["FECHA"].max() + pd.DateOffset(months=1), periods=6, freq="MS")
    ordenes_futuras = np.arange(ult_orden + 1, ult_orden + 7).reshape(-1, 1)
    predicciones = modelo.predict(ordenes_futuras)

    df_predicciones = pd.DataFrame({
        "FECHA": fechas_futuras,
        f"PREDICCION_{departamento}": predicciones
    })

    return df_predicciones

def predecir_precio(departamento=None):
    if departamento:
        return predecir_precio_departamento(departamento)
    else:
        return predecir_precio_nacional()
