"""Vistas y utilidades para el análisis de precios.

Contiene la vista `/precio` que carga datos, calcula estadísticas,
genera gráficos y prepara predicciones para renderizar en la plantilla
`precio.html`.
"""

from flask import Blueprint, render_template, request
import pandas as pd
import io, base64
import matplotlib
# Solucionamos el warning de Matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from modelo_precio import predecir_precio_nacional, predecir_precio_departamento, cargar_datos

precio_bp = Blueprint('precio', __name__, template_folder='templates')

# Nota: la función `mostrar_precio` realiza cargas y transformaciones pesadas
# (pandas + matplotlib). Mantener la lógica en la vista centralizada facilita
# gestionar errores y capturar excepciones para no romper el servidor.

@precio_bp.route('/precio', methods=['GET', 'POST'])
def mostrar_precio():
    """Vista principal para mostrar análisis y predicciones de precios.

    Maneja dos formularios POST (selección por año y por departamento)
    y siempre carga la predicción nacional para mostrar en la plantilla.
    """
    try:
        print("--- Iniciando nueva petición a /precio ---")
        df, departamentos = cargar_datos()
        años_disponibles = sorted(df["AÑO"].unique().tolist())
        print(f"Datos cargados. Años disponibles: {años_disponibles}, Departamentos: {len(departamentos)}")

        contexto = {
            "años_disponibles": años_disponibles,
            "año_actual": df["AÑO"].max(),
            "depto_mayor": "N/A",
            "precio_max": 0,
            "depto_menor": "N/A",
            "precio_min": 0,
            "grafico": None,
            "predicciones": [],
            "departamentos_disponibles": departamentos,
            "departamento_actual": None,
            "pred_departamento": []
        }

        # --- Manejar la selección de AÑO (POST) ---
        if request.method == 'POST' and 'año' in request.form:
            anio_sel = int(request.form.get("año"))
            contexto["año_actual"] = anio_sel
            print(f"Formulario de AÑO recibido: {anio_sel}")
            
            try:
                df_anio = df[df["AÑO"] == anio_sel].copy()
                if not df_anio.empty:
                    df_melted = df_anio.melt(id_vars=["AÑO", "MES"], value_vars=departamentos, var_name="DEPARTAMENTO", value_name="PRECIO").dropna()
                    if not df_melted.empty:
                        idx_max = df_melted['PRECIO'].idxmax()
                        idx_min = df_melted['PRECIO'].idxmin()
                        contexto["depto_mayor"] = df_melted.loc[idx_max, "DEPARTAMENTO"]
                        contexto["precio_max"] = int(df_melted.loc[idx_max, "PRECIO"])
                        contexto["depto_menor"] = df_melted.loc[idx_min, "DEPARTAMENTO"]
                        contexto["precio_min"] = int(df_melted.loc[idx_min, "PRECIO"])
                        print(f"Estadísticas calculadas: Max={contexto['depto_mayor']}, Min={contexto['depto_menor']}")

                    # Generar gráfica
                    df_anio["NACIONAL"] = df_anio[departamentos].mean(axis=1)
                    precio_nacional_mensual = df_anio.groupby(df_anio['MES_NUM'])['NACIONAL'].mean()
                    
                    fig, ax = plt.subplots(figsize=(10, 5))
                    precio_nacional_mensual.plot(kind='line', marker='o', ax=ax, linewidth=2, markersize=8, color="mediumblue")
                    ax.set_title(f"Precio Nacional Promedio Mensual - {anio_sel}") # Quité el emoji para evitar warnings de fuente
                    ax.set_xlabel("Mes")
                    ax.set_ylabel("Precio (COP/L)")
                    ax.set_xticks(range(1, 13))
                    ax.set_xticklabels(['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'], rotation=45)
                    ax.grid(True)
                    plt.tight_layout()
                    buf = io.BytesIO()
                    plt.savefig(buf, format="png")
                    buf.seek(0)
                    contexto["grafico"] = base64.b64encode(buf.getvalue()).decode("utf-8")
                    plt.close(fig)
                    print("Gráfica generada con éxito.")
                else:
                    print(f"ADVERTENCIA: No se encontraron datos para el año {anio_sel}")

            except Exception as e:
                print(f"ERROR al calcular estadísticas o gráfica para el año {anio_sel}: {e}")


        # --- Manejar la selección de DEPARTAMENTO (POST) ---
        if request.method == 'POST' and 'departamento' in request.form:
            depto_sel = request.form.get("departamento")
            contexto["departamento_actual"] = depto_sel
            print(f"Formulario de DEPARTAMENTO recibido: {depto_sel}")
            
            try:
                df_pred_depto = predecir_precio_departamento(depto_sel)
                if not df_pred_depto.empty:
                    # --- CAMBIO CLAVE: Renombramos la columna para que coincida con el HTML ---
                    columna_original = f"PREDICCION_{depto_sel}"
                    columna_nueva = f"PRECIO_{depto_sel.upper()}"
                    df_pred_depto = df_pred_depto.rename(columns={columna_original: columna_nueva})

                    # Mapear nombres de meses en inglés a español para evitar dependencias de locale
                    meses_map_en_es = {
                        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril',
                        'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto',
                        'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
                    }

                    df_pred_depto['AÑO'] = df_pred_depto['FECHA'].dt.year
                    meses_en = df_pred_depto['FECHA'].dt.strftime('%B')
                    df_pred_depto['MES'] = meses_en.map(lambda m: meses_map_en_es.get(m, m))
                    contexto["pred_departamento"] = df_pred_depto.to_dict(orient='records')
                    print(f"Predicción para '{depto_sel}' calculada y renombrada.")
            except Exception as e:
                print(f"ERROR al predecir para el departamento '{depto_sel}': {e}")


        # --- Siempre cargar la predicción nacional ---
        try:
            df_pred_nac, _ = predecir_precio_nacional()
            if not df_pred_nac.empty:
                # --- CAMBIO CLAVE: Renombramos la columna para que coincida con el HTML ---
                df_pred_nac = df_pred_nac.rename(columns={'PREDICCION_NACIONAL': 'PRECIO_NACIONAL'})

                # Mapear meses en inglés a español (evita depender de la configuración regional del sistema)
                meses_map_en_es = {
                    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril',
                    'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto',
                    'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
                }

                df_pred_nac['AÑO'] = df_pred_nac['FECHA'].dt.year
                meses_en_nac = df_pred_nac['FECHA'].dt.strftime('%B')
                df_pred_nac['MES'] = meses_en_nac.map(lambda m: meses_map_en_es.get(m, m))
                contexto["predicciones"] = df_pred_nac.to_dict(orient='records')
                print("Predicción nacional calculada y renombrada.")
        except Exception as e:
            print(f"ERROR al calcular la predicción nacional: {e}")

        print("--- Preparando renderizado de la plantilla ---")
        return render_template("precio.html", **contexto)

    except Exception as e:
        print(f"ERROR CRÍTICO en la función mostrar_precio(): {e}")
        return f"Ocurrió un error inesperado: {e}", 500