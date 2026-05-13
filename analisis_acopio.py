"""Script de análisis rápido del acopio.

Este archivo contiene un pequeño flujo de ejemplo para calcular una
predicción simple por mes y generar una gráfica. Originalmente estaba
escrito para ejecutarse como script; se encapsula ahora bajo un
bloque `__main__` para evitar ejecución al importar desde otros módulos.
"""

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder
import numpy as np


def main():
    """Ejecuta el flujo principal del script de análisis de acopio.

    - Carga el CSV de acopio
    - Normaliza columnas
    - Entrena un modelo simple de regresión por mes
    - Genera una gráfica guardada en `static/images/grafico_acopio.png`
    """
    # === 1. Cargar el archivo CSV ===
    archivo = "DataSheet/Volumen de Acopio Directos - Res 0017 de 2012.csv"
    df = pd.read_csv(archivo, sep=None, engine='python')

    # === 2. Limpieza y normalización de columnas ===
    df.columns = [col.strip() for col in df.columns]

    # === 3. Identificar columnas clave ===
    col_mes = [c for c in df.columns if 'mes' in c.lower()][0]
    col_vol = [c for c in df.columns if 'vol' in c.lower() or 'litros' in c.lower() or 'acopio' in c.lower() or 'total' in c.lower()][0]

    # === 4. Agrupación por mes ===
    df_group = df.groupby(col_mes)[col_vol].mean().reset_index()

    # === 5. Modelo de Machine Learning ===
    meses = df_group[col_mes].tolist()
    le = LabelEncoder()
    X = le.fit_transform(meses).reshape(-1, 1)
    y = df_group[col_vol].values

    modelo = LinearRegression()
    modelo.fit(X, y)
    y_pred = modelo.predict(X)

    # Visualización comparativa
    plt.figure(figsize=(10,5))
    plt.plot(meses, y, label='Volumen real', marker='o')
    plt.plot(meses, y_pred, label='Predicción ML', linestyle='--', color='orange')
    plt.title("Predicción de Acopio de Leche por Mes")
    plt.xlabel("Mes")
    plt.ylabel("Volumen Promedio de Acopio")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    # Guardar gráfica para uso en la app
    plt.savefig('static/images/grafico_acopio.png')
    plt.close()

    # === 6. Estadística desde enero 2024 ===
    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df_2024 = df[df['Fecha'] >= '2024-01-01']
    else:
        # intentar inferir año desde la columna de mes si contiene fecha
        try:
            df['Año'] = pd.to_datetime(df[col_mes], errors='coerce').dt.year
        except Exception:
            df['Año'] = pd.NA
        df_2024 = df[df['Año'] >= 2024]

    if not df_2024.empty:
        vol_por_mes = df_2024.groupby(col_mes)[col_vol].sum().reset_index()
        mes_max_vol = vol_por_mes.sort_values(by=col_vol, ascending=False).iloc[0]
        print("\n🔹 Mes con mayor volumen desde 2024:", mes_max_vol[col_mes], "-", mes_max_vol[col_vol])
        if 'Departamento' in df_2024.columns:
            vol_por_depto = df_2024.groupby('Departamento')[col_vol].sum().reset_index()
            depto_max_vol = vol_por_depto.sort_values(by=col_vol, ascending=False).iloc[0]
            print("🔹 Departamento destacado:", depto_max_vol['Departamento'], "-", depto_max_vol[col_vol])
        else:
            print("🔹 No se encontró columna de departamento.")


if __name__ == '__main__':
    main()
