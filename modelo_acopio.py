"""Herramientas de predicción de volumen de acopio.

Contiene utilidades para cargar el CSV histórico de acopios y generar
predicciones de volumen nacional mediante una regresión lineal simple.
El módulo intenta ser robusto frente a formatos locales de números y
nombres de columnas.
"""

import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np
import os


def predecir_acopio():
    """Cargar datos históricos de acopio y predecir 6 meses siguientes.

    Esta función normaliza los valores numéricos (quita separadores de
    miles, normaliza comas decimales), entrena una regresión lineal
    sobre la columna nacional y devuelve un DataFrame con las 6 filas
    de predicción. En caso de errores de lectura, intenta rutas
    alternativas y, si no puede, lanza excepción para que la vista la
    gestione.
    """

    # Ruta del archivo CSV
    ruta = os.path.join("DataSheet", "Volumen de Acopio Directos - Res 0017 de 2012.csv")

    # Cargar los datos
    try:
        df = pd.read_csv(ruta, sep=';', encoding='latin-1')
    except FileNotFoundError:
        # Si falla, intentar con ruta relativa al archivo
        ruta_alt = os.path.join(os.path.dirname(__file__), "DataSheet", "Volumen de Acopio Directos - Res 0017 de 2012.csv")
        df = pd.read_csv(ruta_alt, sep=';', encoding='latin-1')
    
    # Normalizar nombres de columnas: quitar espacios y tildes
    def normalize_col(col):
        import unicodedata
        col = col.strip().upper()
        col = unicodedata.normalize('NFKD', col).encode('ASCII', 'ignore').decode('ASCII')
        return col

    df.columns = [normalize_col(c) for c in df.columns]

    # Asegurar nombres esperados - detectar columna de año y mes de forma robusta
    year_col = None
    month_col = None
    for c in df.columns:
        if 'ANO' in c or 'AÑO' in c or 'ANIO' in c or 'YEAR' in c:
            year_col = c
        if 'MES' in c or 'MONTH' in c:
            month_col = c

    # Si no detectamos explícitamente, intentar con posiciones comunes (primera=year, segunda=mes)
    if year_col is None and len(df.columns) >= 1:
        # buscar una columna que parezca numérica en los primeros 3
        for c in df.columns[:3]:
            try:
                pd.to_numeric(df[c].dropna().iloc[:5])
                year_col = c
                break
            except Exception:
                continue
    if month_col is None and len(df.columns) >= 2:
        # asumir que la segunda columna es mes si existe
        month_col = df.columns[1]

    if year_col:
        df = df.rename(columns={year_col: 'AÑO'})
    if month_col:
        df = df.rename(columns={month_col: 'MES'})

    # Limpiar: quitar espacios, nd, etc.
    #df['NACIONAL'] = df['NACIONAL'].astype(str)
    #df['NACIONAL'] = df['NACIONAL'].str.strip().replace('nd', '0')
    #=======================================================
    # Detectar columna que contenga 'NACIONAL'
    
    nacional_col = next((c for c in df.columns if 'NACIONAL' in c), None)
    if not nacional_col:
        print("⚠️ No se encontró columna de volumen nacional. Columnas disponibles:", df.columns.tolist())
        return pd.DataFrame()
    df[nacional_col] = df[nacional_col].astype(str).str.strip().replace('nd', '0')
    if df[nacional_col].str.contains(r'\.', regex=True).any():
        # remover puntos de miles de forma literal
        df[nacional_col] = df[nacional_col].str.replace('.', '', regex=False)
    # normalizar coma decimal a punto
    df[nacional_col] = df[nacional_col].str.replace(',', '.', regex=False)
    df[nacional_col] = pd.to_numeric(df[nacional_col], errors='coerce')
    df.dropna(subset=[nacional_col], inplace=True)
    df = df.rename(columns={nacional_col: 'NACIONAL'})



    #======================================================================
    
    # Si hay números con formato español (1.234.567,89)
    #if df['NACIONAL'].str.contains('\.').any():
        #df['NACIONAL'] = df['NACIONAL'].str.replace('.', '')
    
    # Reemplazar comas por puntos para decimales
    #df['NACIONAL'] = df['NACIONAL'].str.replace(',', '.')
    
    # Convertir a float y eliminar filas con NA si quedan
    #df['NACIONAL'] = pd.to_numeric(df['NACIONAL'], errors='coerce')
    #df.dropna(subset=['NACIONAL'], inplace=True)

    # Crear un índice de tiempo
    #df['AÑO'] = df['AÑO'].astype(int)
    #df['MES_NUM'] = df['MES'].replace({
       # 'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
        #'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
        #'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
    #}).astype(int)

    # Diccionario de meses en español
    meses_dict = {
        'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
        'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
        'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
    }

    # Normalizar nombres de mes
    df['MES'] = df['MES'].astype(str).str.strip().str.upper()

    # Mapear a número y eliminar filas con errores
    df['MES_NUM'] = df['MES'].map(meses_dict)
    df.dropna(subset=['MES_NUM'], inplace=True)
    df['MES_NUM'] = df['MES_NUM'].astype(int)





    # Crear columna "periodo" para numerar el tiempo
    df = df.sort_values(by=['AÑO', 'MES_NUM'])
    df['PERIODO'] = range(1, len(df) + 1)

    # Preparar datos para el modelo
    X = df[['PERIODO']]
    y = df['NACIONAL']

    # Entrenar modelo
    modelo = LinearRegression()
    modelo.fit(X, y)

    # Predicción para los próximos 6 meses
    ult_periodo = df['PERIODO'].max()
    futuros = np.array(range(ult_periodo + 1, ult_periodo + 7)).reshape(-1, 1)
    predicciones = modelo.predict(futuros)
    # Calcular los meses futuros
    ultimo_mes = int(df.iloc[-1]['MES_NUM'])
    ultimo_año = int(df.iloc[-1]['AÑO'])

    meses_futuros = []
    mes_actual = ultimo_mes
    año_actual = ultimo_año

    meses = {
        1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
        5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
        9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
    }

    for i in range(6):
        mes_actual += 1
        if mes_actual > 12:
            mes_actual = 1
            año_actual += 1
        meses_futuros.append({
            'AÑO': año_actual,
            'MES': meses[mes_actual],
            'PREDICCION': float(predicciones[i])
        })

    
        print("✅ Predicciones generadas:")
        print(pd.DataFrame(meses_futuros))

    return pd.DataFrame(meses_futuros)