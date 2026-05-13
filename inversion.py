"""Módulo de inversión ganadera.

Proporciona la vista `/inversion` y utilidades para trabajar con los
datasets de censo y acopio, calcular estimaciones por raza y generar
recomendaciones basadas en predicciones. Contiene funciones para cargar
datos, limpiar series y calcular métricas usadas por las plantillas.
"""

from flask import Blueprint, render_template, request, current_app
import traceback
import pandas as pd
import os

from modelo_acopio import predecir_acopio
from modelo_precio import predecir_precio, cargar_datos as cargar_precios

inversion_bp = Blueprint('inversion', __name__, template_folder='templates')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def cargar_censo_bovino():
    """Carga y limpia el CSV del censo bovino.

    Normaliza columnas y convierte campos numéricos, devolviendo un
    DataFrame listo para cálculos de análisis.
    """
    ruta = os.path.join(BASE_DIR, 'DataSheet', 'CENSO-BOVINO-2025.csv')
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")
    df = pd.read_csv(ruta, sep=';', encoding='utf-8')
    df.columns = [col.strip().lower() for col in df.columns]
    for col in df.columns:
        if col != 'departamento':
            df[col] = df[col].astype(str).str.replace('.', '', regex=False)\
                                       .str.replace(',', '.', regex=False)\
                                       .str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
    if df.empty:
        raise ValueError("El DataFrame del censo está vacío")
    return df

def cargar_datos_raza():
    """Construye y devuelve un DataFrame con información aproximada de razas por departamento.

    Esta función usa tablas definidas en código para evitar depender de
    un dataset externo y facilita pruebas locales.
    """
    region_1 = ['ANTIOQUIA', 'BOGOTÁ DC', 'BOYACÁ', 'CALDAS', 'CAUCA', 'CUNDINAMARCA',
                'NARIÑO', 'QUINDÍO', 'RISARALDA', 'VALLE DEL CAUCA']
    region_2 = ['ARAUCA', 'ATLÁNTICO', 'BOLIVAR', 'CAQUETÁ', 'CASANARE', 'CESAR', 'CÓRDOBA',
                'GUAVIARE', 'HUILA', 'LA GUAJIRA', 'MAGDALENA', 'META', 'NORTE DE SANTANDER',
                'PUTUMAYO', 'SANTANDER', 'SUCRE', 'TOLIMA']
    razas_r1 = ['Holstein', 'Simmental Suizo', 'Jersey', 'Normando']
    volumen_r1 = [25, 18, 16, 14]
    razas_r2 = ['Gyr']
    volumen_r2 = [12]
    data = []
    for dpto in region_1:
        for raza, litros in zip(razas_r1, volumen_r1):
            data.append({'departamento': dpto, 'razas': raza, 'volumen diario': litros, 'region': 1})
    for dpto in region_2:
        for raza, litros in zip(razas_r2, volumen_r2):
            data.append({'departamento': dpto, 'razas': raza, 'volumen diario': litros, 'region': 2})
    return pd.DataFrame(data)


# Estadísticas por raza (valores por vaca en litros/día y composición)
BREED_STATS = {
    'Holstein': {'min': 30.0, 'max': 40.0, 'avg': 35.0, 'fat': 3.5, 'protein': 3.1},
    'Simmental Suizo': {'min': 20.0, 'max': 30.0, 'avg': 25.0, 'fat': 4.0, 'protein': 3.4},
    'Jersey': {'min': 18.0, 'max': 25.0, 'avg': 21.5, 'fat': 5.0, 'protein': 3.8},
    'Normando': {'min': 20.0, 'max': 28.0, 'avg': 24.0, 'fat': 4.2, 'protein': 3.5},
    'Gyr': {'min': 10.0, 'max': 18.0, 'avg': 14.0, 'fat': 4.75, 'protein': 3.65}
}


def obtener_mejor_mes():
    """Retorna una tupla (mes, precio, acopio) con el mes de mayor rentabilidad.

    Implementado como función simple que usa datos estáticos para
    facilitar demos cuando no hay modelos disponibles.
    """
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    precios = [1450, 1480, 1500, 1520, 1490, 1510, 1530, 1620, 1580, 1550, 1500, 1480]
    acopios = [88, 90, 91, 89, 87, 92, 93, 92, 90, 89, 88, 87]
    df = pd.DataFrame({'mes': meses, 'precio': precios, 'acopio': acopios})
    df['rentabilidad'] = df['precio'] / df['acopio']
    if df.empty:
        return "No disponible", 0, 0
    mejor = df.sort_values(by='rentabilidad', ascending=False).iloc[0]
    return mejor['mes'], mejor['precio'], mejor['acopio']

def cargar_acopio():
    """Carga el CSV de acopio y devuelve un DataFrame limpio."""
    ruta = os.path.join(BASE_DIR, 'DataSheet', 'Volumen de Acopio Directos - Res 0017 de 2012.csv')
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Archivo de acopio no encontrado: {ruta}")
    df = pd.read_csv(ruta, sep=';', encoding='utf-8')
    # Normalizar nombres de columnas (minúsculas, sin espacios exteriores)
    df.columns = [c.strip().lower() for c in df.columns]
    # Limpiar columnas numéricas: quitar puntos miles y 'nd'
    def clean_num(x):
        if pd.isna(x):
            return pd.NA
        s = str(x).strip()
        if s.lower() in ('nd', ''):
            return pd.NA
        # Quitar separadores de miles (puntos o espacios) y normalizar comas decimales
        s = s.replace('.', '').replace(' ', '')
        s = s.replace(',', '.')
        try:
            return float(s)
        except Exception:
            return pd.NA

    for col in df.columns:
        if col not in ('año', 'ano', 'mes'):
            df[col] = df[col].apply(clean_num)
    return df

def mejores_meses_acopio(n_top=3, departamento=None):
    """Devuelve los n_top meses con mayor acopio promedio. Si departamento es None usa NACIONAL, si no usa la columna del departamento."""
    try:
        df_acopio = cargar_acopio()
    except Exception:
        return []
    # localizar columna correspondiente (el DataFrame usa nombres en minúsculas)
    requested = 'nacional' if departamento is None else departamento.lower()
    cols_clean = {c.upper().replace(' ', ''): c for c in df_acopio.columns}
    key = requested.upper().replace(' ', '')
    if key in cols_clean:
        col_name = cols_clean[key]
    else:
        return []
    # Agrupar por mes y calcular media
    if 'mes' not in df_acopio.columns:
        return []
    df2 = df_acopio[[ 'mes', col_name ]].copy()
    df2 = df2.dropna(subset=[col_name])
    if df2.empty:
        return []
    grouped = df2.groupby('mes', sort=False)[col_name].mean()
    top = grouped.sort_values(ascending=False).head(n_top)
    return [{'mes': m, 'valor': float(v)} for m, v in top.items()]

def mejores_meses_por_acopio(n=3):
    """Devuelve los n meses con mayor volumen de acopio (lista de meses)."""
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    acopios = [88, 90, 91, 89, 87, 92, 93, 92, 90, 89, 88, 87]
    df_m = pd.DataFrame({'mes': meses, 'acopio': acopios})
    top = df_m.sort_values(by='acopio', ascending=False).head(n)
    return top['mes'].tolist()

def serie_anual_departamento(departamento, ano=2025):
    """Devuelve la serie mensual (12 meses) del año `ano` para el departamento indicado.
    Resultado: lista de dicts [{'mes': 'Enero', 'valor': float}, ...] en orden de enero a diciembre.
    """
    try:
        df_acopio = cargar_acopio()
    except Exception:
        return []

    # localizar columna similar al nombre de departamento
    cols_clean = {c.upper().replace(' ', '').replace('Á', 'A').replace('É','E').replace('Í','I').replace('Ó','O').replace('Ú','U'): c for c in df_acopio.columns}
    key = departamento.upper().replace(' ', '').replace('Á', 'A').replace('É','E').replace('Í','I').replace('Ó','O').replace('Ú','U')
    if key in cols_clean:
        col = cols_clean[key]
    elif departamento in df_acopio.columns:
        col = departamento
    else:
        # no coincide
        return []

    meses_order = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                   'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

    series = []
    try:
        dff = df_acopio.copy()
        # Normalizar columna de año/mes para evitar comparaciones fallidas por tipo
        if 'año' in dff.columns:
            dff['año'] = pd.to_numeric(dff['año'], errors='coerce')
            filtro = dff['año'] == int(ano)
        elif 'ano' in dff.columns:
            dff['ano'] = pd.to_numeric(dff['ano'], errors='coerce')
            filtro = dff['ano'] == int(ano)
        else:
            filtro = pd.Series([False]*len(dff))

        # normalizar columna 'mes'
        if 'mes' in dff.columns:
            dff['mes'] = dff['mes'].astype(str).str.strip().str.lower()

        df_year = dff[filtro]
        for m in meses_order:
            row = df_year[df_year['mes'].str.lower() == m]
            if not row.empty:
                val = row.iloc[0][col]
                try:
                    valf = float(val)
                except Exception:
                    valf = 0.0
            else:
                valf = 0.0
            series.append({'mes': m.title(), 'valor': valf})
    except Exception:
        return []
    return series

def generar_analisis_censo(df):
    grupos = ['terneras < 1 año', 'hembras 1 - 2 años', 'hembras 2 - 3 años', 'hembras > 3 años']
    grupos_existentes = [g for g in grupos if g in df.columns]
    mayores = []
    menores = []
    for g in grupos_existentes:
        if df[g].notna().any():
            try:
                depto_max = df.loc[df[g].idxmax()]
                depto_min = df.loc[df[g].idxmin()]
                mayores.append({'grupo': g, 'departamento': depto_max['departamento'], 'cantidad': int(depto_max[g])})
                menores.append({'grupo': g, 'departamento': depto_min['departamento'], 'cantidad': int(depto_min[g])})
            except (ValueError, KeyError):
                continue
    total_nacional = df[grupos_existentes].sum()
    total_general = total_nacional.sum()
    distribucion = {g: round(total_nacional[g] / total_general * 100, 2) for g in grupos_existentes} if total_general > 0 else {g: 0 for g in grupos_existentes}
    if 'total bovinos' in df.columns and df['total bovinos'].notna().any():
        depto_total_max = df.loc[df['total bovinos'].idxmax()]
        depto_total_min = df.loc[df['total bovinos'].idxmin()]
        depto_max_info = {'nombre': depto_total_max['departamento'], 'cantidad': int(depto_total_max['total bovinos'])}
        depto_min_info = {'nombre': depto_total_min['departamento'], 'cantidad': int(depto_total_min['total bovinos'])}
    else:
        depto_max_info = {'nombre': 'No disponible', 'cantidad': 0}
        depto_min_info = {'nombre': 'No disponible', 'cantidad': 0}
    return {
        'mayores': mayores,
        'menores': menores,
        'distribucion': distribucion,
        'depto_max': depto_max_info,
        'depto_min': depto_min_info
    }

@inversion_bp.route('/inversion', methods=['GET', 'POST'])
def inversion():
    try:
        df_censo = cargar_censo_bovino()
        df_raza = cargar_datos_raza()
        analisis = generar_analisis_censo(df_censo)

        # Generar tabla HTML del censo para mostrar en el modal
        try:
            tabla_censo_df = df_censo.copy()
            # Mejorar nombres de columnas para visualización
            tabla_censo_df.columns = [c.title() for c in tabla_censo_df.columns]
            tabla_censo = tabla_censo_df.to_html(classes="table table-striped table-sm table-hover",
                                                 index=False, border=0, justify="center", na_rep="")
        except Exception:
            tabla_censo = "<p class='text-danger'>No fue posible cargar la tabla del censo.</p>"

        departamentos = df_raza['departamento'].unique().tolist()
        # Obtener años disponibles del dataset de acopio para el selector
        try:
            df_acopio_all = cargar_acopio()
            years = []
            if 'año' in df_acopio_all.columns:
                years = pd.to_numeric(df_acopio_all['año'], errors='coerce').dropna().astype(int).unique().tolist()
            elif 'ano' in df_acopio_all.columns:
                years = pd.to_numeric(df_acopio_all['ano'], errors='coerce').dropna().astype(int).unique().tolist()
            available_years = sorted(years)
        except Exception:
            available_years = []

        # año seleccionado por el usuario (selector). Por defecto, el último año disponible o 2025
        try:
            anio_sel = int(request.form.get('anio')) if request.form.get('anio') else (available_years[-1] if available_years else 2025)
        except Exception:
            anio_sel = available_years[-1] if available_years else 2025
        depto_sel = request.form.get('departamento')
        raza_sel = request.form.get('raza')
        num_vacas = request.form.get('num_vacas')

        # Normalizar raza seleccionada para evitar problemas por mayúsculas/espacios
        if raza_sel:
            try:
                raza_sel = raza_sel.strip()
            except Exception:
                pass

        # Si se seleccionó una raza, obtener sus estadísticas básicas para mostrar (min/max/avg por vaca)
        if raza_sel:
            # búsqueda insensible a mayúsculas en BREED_STATS
            bkey = next((k for k in BREED_STATS.keys() if str(k).strip().lower() == raza_sel.strip().lower()), None)
            breed_stats = BREED_STATS.get(bkey) if bkey else BREED_STATS.get(raza_sel) or BREED_STATS.get(raza_sel.strip())
            if breed_stats:
                breed_min = float(breed_stats.get('min', 0.0))
                breed_max = float(breed_stats.get('max', 0.0))
                breed_avg = float(breed_stats.get('avg', 0.0))
            else:
                breed_min = breed_max = breed_avg = 0.0
        else:
            breed_stats = None
            breed_min = breed_max = breed_avg = 0.0

        volumen_diario = None
        volumen_mensual = None
        mejor_mes = None
        precio_mes = None
        acopio_mes = None
        volumen_predicho = None
        precio_predicho = None
        rentabilidad_predicha = None
        recomendacion = None
    # valores por raza/finca (por defecto) - sólo inicializar totales de finca aquí
        farm_min_diaria = farm_max_diaria = farm_avg_diaria = 0.0
        farm_min_mensual = farm_max_mensual = farm_avg_mensual = 0.0

        if depto_sel:
            # comparar departamentos tal cual (se generan en mayúsculas desde cargar_datos_raza)
            depto_filtrado = df_raza[df_raza['departamento'] == depto_sel]

            if raza_sel and num_vacas:
                # comparar razas normalizando espacios y case
                raza_mask = df_raza['razas'].astype(str).str.strip().str.lower() == raza_sel.lower()
                raza_info = depto_filtrado[raza_mask]
                if not raza_info.empty:
                    volumen_diario = raza_info['volumen diario'].values[0]
                    volumen_mensual = volumen_diario * int(num_vacas) * 30

            mejor_mes, precio_mes, acopio_mes = obtener_mejor_mes()

        # Si se seleccionó una raza, determinar el mejor departamento/region para producción
        mejor_depto_info = None
        mejores_meses = mejores_meses_por_acopio(3)
        if raza_sel:
            try:
                # filtrar filas de la raza normalizando
                raza_rows = df_raza[df_raza['razas'].astype(str).str.strip().str.lower() == raza_sel.lower()]
                if not raza_rows.empty:
                    # Departamento con mayor volumen diario por vaca para esa raza
                    idx = raza_rows['volumen diario'].idxmax()
                    row = raza_rows.loc[idx]
                    mejor_depto_info = {
                        'departamento': row['departamento'],
                        'region': int(row['region']) if 'region' in row and pd.notna(row['region']) else None,
                        'volumen_diario_por_vaca': float(row['volumen diario'])
                    }
                    # volumen total estimado según número de vacas si se proporcionó
                    try:
                        nv = int(num_vacas) if num_vacas else None
                        if nv:
                            mejor_depto_info['volumen_total_diario'] = mejor_depto_info['volumen_diario_por_vaca'] * nv
                            mejor_depto_info['volumen_total_mensual'] = mejor_depto_info['volumen_total_diario'] * 30
                    except Exception:
                        pass
            except Exception:
                mejor_depto_info = None

            try:
                volumen_predicho = predecir_acopio(mejor_mes)
                precio_predicho = predecir_precio(mejor_mes)
                rentabilidad_predicha = precio_predicho / volumen_predicho
                recomendacion = f"📌 En {mejor_mes} se espera un acopio de {volumen_predicho:.2f} litros y un precio de {precio_predicho:.2f} COP/litro. Rentabilidad estimada: {rentabilidad_predicha:.2f} COP/litro. Es un mes óptimo para invertir en producción lechera."
            except Exception as e:
                recomendacion = f"No se pudo generar la predicción: {str(e)}"

    # Si usuario indicó raza y número de vacas, calcular mejor departamento/region y meses recomendados
        mejor_depto = None
        mejor_region = None
        meses_recomendados = []
        meses_depto = []
        lista_mejores_departamentos = []
        show_modal_analisis = False
        input_error = None
        lista_mejores_info = []
        lista_mejores_series = []
        if raza_sel and num_vacas:
            try:
                num_vacas_int = int(num_vacas)
                if num_vacas_int <= 0:
                    raise ValueError("El número de vacas debe ser mayor que 0")
            except Exception:
                num_vacas_int = None
                input_error = "Ingrese un número válido de vacas (entero mayor que 0)."

            if num_vacas_int and raza_sel:
                # departamentos que tienen esa raza (comparación insensible a mayúsculas/espacios)
                df_razas_sel = df_raza[df_raza['razas'].astype(str).str.strip().str.lower() == raza_sel.strip().lower()]
                if not df_razas_sel.empty:
                    # mejor departamento: el que tenga mayor 'volumen diario' por vaca
                    df_sorted = df_razas_sel.sort_values(by='volumen diario', ascending=False)
                    # top 3 departamentos para esta raza
                    lista_mejores_departamentos = df_sorted['departamento'].head(3).tolist()
                    mejor_row = df_sorted.iloc[0]
                    mejor_depto = mejor_row['departamento']
                    mejor_region = int(mejor_row['region']) if 'region' in mejor_row else None

                    # cálculo producción estimada para ese departamento
                    volumen_por_vaca = float(mejor_row['volumen diario'])
                    produccion_diaria = volumen_por_vaca * num_vacas_int
                    produccion_mensual = produccion_diaria * 30

                    # Estadísticas de la raza (min, max, avg) por vaca y composición
                    breed_stats = BREED_STATS.get(raza_sel) if raza_sel else None
                    if breed_stats and num_vacas_int:
                        # valores por vaca
                        breed_min = float(breed_stats.get('min', 0.0))
                        breed_max = float(breed_stats.get('max', 0.0))
                        breed_avg = float(breed_stats.get('avg', 0.0))
                        # totales para la finca (por número de vacas)
                        farm_min_diaria = breed_min * num_vacas_int
                        farm_max_diaria = breed_max * num_vacas_int
                        farm_avg_diaria = breed_avg * num_vacas_int
                        farm_min_mensual = farm_min_diaria * 30
                        farm_max_mensual = farm_max_diaria * 30
                        farm_avg_mensual = farm_avg_diaria * 30
                    else:
                        breed_stats = None
                        breed_min = breed_max = breed_avg = 0.0
                        farm_min_diaria = farm_max_diaria = farm_avg_diaria = 0.0
                        farm_min_mensual = farm_max_mensual = farm_avg_mensual = 0.0

                    # mejores meses según acopio: a nivel nacional y para el departamento seleccionado
                    meses_recomendados = mejores_meses_acopio(n_top=3, departamento=None)
                    meses_depto = mejores_meses_acopio(n_top=3, departamento=mejor_depto)

                    # calcular máximos para visualización (evitar división por cero)
                    meses_recomendados_max = max([m['valor'] for m in meses_recomendados]) if meses_recomendados else 0
                    meses_depto_max = max([m['valor'] for m in meses_depto]) if meses_depto else 0

                    # Añadir porcentaje relativo para facilitar render en template (0-100)
                    if meses_recomendados_max > 0:
                        for m in meses_recomendados:
                            m['pct'] = (m['valor'] / meses_recomendados_max) * 100
                    else:
                        for m in meses_recomendados:
                            m['pct'] = 0

                    if meses_depto_max > 0:
                        for m in meses_depto:
                            m['pct'] = (m['valor'] / meses_depto_max) * 100
                    else:
                        for m in meses_depto:
                            m['pct'] = 0

                    # pasar los resultados a variables que la plantilla espera
                    # (si ya existen, sobreescribimos para mostrar info más útil)
                    volumen_diario = produccion_diaria
                    volumen_mensual = produccion_mensual
                    # construir lista con info por departamento (producción estimada para la cantidad dada)
                    for _, row in df_sorted.head(3).iterrows():
                        vpv = float(row['volumen diario'])
                        depto = row['departamento']
                        region = int(row['region']) if 'region' in row else None
                        prod_diaria = vpv * num_vacas_int
                        prod_mensual = prod_diaria * 30
                        lista_mejores_info.append({
                            'departamento': depto,
                            'region': region,
                            'volumen_por_vaca': vpv,
                            'prod_diaria': prod_diaria,
                            'prod_mensual': prod_mensual
                        })

                    
                    # Obtener precios más recientes solo para los departamentos listados (máx 3)
                    precios_departamentos = []
                    try:
                        df_precios, cols_precios = cargar_precios()
                        # Normalizar nombres de columnas de precios (ya vienen normalizados en modelo_precio)
                        def _norm(s):
                            try:
                                import unicodedata
                                ns = str(s).strip().upper()
                                ns = unicodedata.normalize('NFKD', ns).encode('ASCII', 'ignore').decode('ASCII')
                                ns = ns.replace(' ', '')
                                return ns
                            except Exception:
                                return str(s).strip().upper()

                        cols_norm = {(_norm(c)): c for c in cols_precios}

                        for info in lista_mejores_info:
                            depto = info['departamento']
                            key = _norm(depto)
                            precio_val = None
                            if key in cols_norm:
                                col_name = cols_norm[key]
                                # tomar el último valor no nulo ordenado por FECHA
                                try:
                                    serie = df_precios[[col_name, 'FECHA']].dropna(subset=[col_name]).sort_values('FECHA')
                                    if not serie.empty:
                                        precio_val = float(serie.iloc[-1][col_name])
                                except Exception:
                                    precio_val = None
                            else:
                                # intentar fallback: promedio nacional del último registro
                                try:
                                    deps = [c for c in cols_precios]
                                    df_precios['NACIONAL_PROM'] = df_precios[deps].mean(axis=1)
                                    serie = df_precios[['NACIONAL_PROM', 'FECHA']].dropna(subset=['NACIONAL_PROM']).sort_values('FECHA')
                                    if not serie.empty:
                                        precio_val = float(serie.iloc[-1]['NACIONAL_PROM'])
                                except Exception:
                                    precio_val = None

                            precios_departamentos.append({
                                'departamento': depto,
                                'precio': precio_val,
                                'precio_str': f"{precio_val:,.0f}" if precio_val is not None else 'N/A'
                            })
                    except Exception:
                        # Si falla la carga de precios, inicializar lista vacía con N/A
                        precios_departamentos = [{'departamento': i['departamento'], 'precio': None, 'precio_str': 'N/A'} for i in lista_mejores_info]

            # Generar series anuales por departamento recomendado (para gráficos) usando el año seleccionado
            lista_mejores_series = []
            try:
                for info in lista_mejores_info:
                    dept = info['departamento']
                    serie = serie_anual_departamento(dept, ano=anio_sel)
                    has_data = any((m.get('valor') or 0) > 0 for m in serie)
                    lista_mejores_series.append({
                        'departamento': dept,
                        'year': anio_sel,
                        'meses': serie,
                        'has_data': has_data
                    })
            except Exception:
                lista_mejores_series = []

            # (Proyección desactivada temporalmente para evitar errores en el frontend)

        # Preparar cadenas formateadas para mostrar en la plantilla
        def _fmt_num(x, decimals=2):
            try:
                return f"{float(x):,.{decimals}f}"
            except Exception:
                return f"{0:,.{decimals}f}"

        def _fmt_comp(x):
            try:
                return f"{float(x):.1f}"
            except Exception:
                return "0.0"

        breed_min_str = _fmt_num(breed_min)
        breed_max_str = _fmt_num(breed_max)
        breed_avg_str = _fmt_num(breed_avg)

        farm_min_diaria_str = _fmt_num(farm_min_diaria)
        farm_max_diaria_str = _fmt_num(farm_max_diaria)
        farm_avg_diaria_str = _fmt_num(farm_avg_diaria)
        farm_min_mensual_str = _fmt_num(farm_min_mensual)
        farm_max_mensual_str = _fmt_num(farm_max_mensual)
        farm_avg_mensual_str = _fmt_num(farm_avg_mensual)

        fat_str = _fmt_comp(breed_stats.get('fat')) if breed_stats and 'fat' in breed_stats else "0.0"
        protein_str = _fmt_comp(breed_stats.get('protein')) if breed_stats and 'protein' in breed_stats else "0.0"

        # Construir una tabla HTML (cadena) con nombres completos para mostrar en la tarjeta
        # Se evita tocar plantillas; se pasa la cadena para que la plantilla la renderice con |safe
        try:
            nv_int = None
            try:
                nv_int = int(num_vacas) if num_vacas else None
            except Exception:
                nv_int = None

            rows = []
            # Valores por vaca (litros/día)
            rows.append(("Mínimo por vaca (Litro/día)", breed_min_str))
            rows.append(("Máximo por vaca (Litro/día)", breed_max_str))
            rows.append(("Promedio por vaca (Litro/día)", breed_avg_str))
            # Composición
            rows.append(("Grasa en leche", fat_str))
            rows.append(("Proteína en leche", protein_str))

            # Totales para la cantidad indicada de vacas (mostrar número y singular/plural)
            if nv_int:
                vaca_label = "vaca" if nv_int == 1 else "vacas"
                rows.append((f"Total mínimo - {nv_int} {vaca_label} (Litros/día)", farm_min_diaria_str))
                rows.append((f"Total mínimo - {nv_int} {vaca_label} (Litros/mes)", farm_min_mensual_str))
                rows.append((f"Total máximo - {nv_int} {vaca_label} (Litos/día)", farm_max_diaria_str))
                rows.append((f"Total máximo - {nv_int} {vaca_label} (Litros/mes)", farm_max_mensual_str))
                rows.append((f"Total promedio - {nv_int} {vaca_label} (Litros/día)", farm_avg_diaria_str))
                rows.append((f"Total promedio - {nv_int} {vaca_label} (Litros/mes)", farm_avg_mensual_str))

            # Construir HTML
            tbl_lines = ["<table class='table table-sm table-bordered'>",
                         "<tbody>"]
            for label, val in rows:
                tbl_lines.append(f"<tr><th style='width:65%;'>{label}</th><td style='text-align:right;font-weight:600;'>{val}</td></tr>")
            tbl_lines.append("</tbody></table>")
            breed_table_html = '\n'.join(tbl_lines)
        except Exception:
            breed_table_html = ""

        # Determinar modo para la UI: 'historico' cuando el año seleccionado
        # es distinto al último año disponible; por defecto 'consulta'.
        try:
            mode = 'consulta'
            if anio_sel and available_years:
                try:
                    latest_year = max(available_years)
                except Exception:
                    latest_year = available_years[-1] if available_years else None
                if latest_year and str(anio_sel) != str(latest_year):
                    mode = 'historico'
        except Exception:
            mode = 'consulta'

        return render_template('inversion.html',
                               departamentos=departamentos,
                               razas=df_raza['razas'].unique().tolist(),
                               analisis=analisis,
                               depto_sel=depto_sel,
                               raza_sel=raza_sel,
                               num_vacas=num_vacas,
                               volumen_diario=volumen_diario,
                               volumen_mensual=volumen_mensual,
                               mejor_mes=mejor_mes,
                               precio_mes=precio_mes,
                               acopio_mes=acopio_mes,
                               volumen_predicho=volumen_predicho,
                               precio_predicho=precio_predicho,
                               rentabilidad_predicha=rentabilidad_predicha,
                               recomendacion=recomendacion,
                               tabla_censo=tabla_censo,
                               mejor_depto=mejor_depto,
                               mejor_region=mejor_region,
                               meses_recomendados=meses_recomendados,
                               meses_depto=meses_depto,
                               lista_mejores_departamentos=lista_mejores_departamentos,
                               lista_mejores_info=lista_mejores_info,
                               lista_mejores_series=lista_mejores_series,
                               available_years=available_years,
                               anio_sel=anio_sel,
                               mode=mode,
                               debug=current_app.debug,
                               input_error=input_error,
                               meses_recomendados_max=meses_recomendados_max if 'meses_recomendados_max' in locals() else 0,
                               meses_depto_max=meses_depto_max if 'meses_depto_max' in locals() else 0,
                               breed_stats=breed_stats,
                               breed_min=breed_min,
                               breed_max=breed_max,
                               breed_avg=breed_avg,
                               farm_min_diaria=farm_min_diaria,
                               farm_max_diaria=farm_max_diaria,
                               farm_avg_diaria=farm_avg_diaria,
                               farm_min_mensual=farm_min_mensual,
                               farm_max_mensual=farm_max_mensual,
                               farm_avg_mensual=farm_avg_mensual,
                               # cadenas formateadas para la UI (evita tocar templates)
                               breed_min_str=breed_min_str,
                               breed_max_str=breed_max_str,
                               breed_avg_str=breed_avg_str,
                               farm_min_diaria_str=farm_min_diaria_str,
                               farm_max_diaria_str=farm_max_diaria_str,
                               farm_avg_diaria_str=farm_avg_diaria_str,
                               farm_min_mensual_str=farm_min_mensual_str,
                               farm_max_mensual_str=farm_max_mensual_str,
                               farm_avg_mensual_str=farm_avg_mensual_str,
                               fat_str=fat_str,
                               protein_str=protein_str,
                               breed_table_html=breed_table_html,
                               precios_departamentos=precios_departamentos if 'precios_departamentos' in locals() else [])
                               
    except Exception as e:
        tb = traceback.format_exc()
        # intentar escribir un log en instancia para facilitar diagnóstico
        try:
            log_dir = os.path.join(BASE_DIR, 'instance')
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'inversion_error.log'), 'a', encoding='utf-8') as f:
                f.write('\n--- ERROR en /inversion ---\n')
                f.write(tb)
        except Exception:
            # si falla escribir el log, ignoramos para no enmascarar el error original
            pass
        # Si estamos en modo DEBUG, devolver el traceback en la respuesta para facilitar debugging local
        try:
            if current_app and current_app.debug:
                return f"<pre>{tb}</pre>"
        except Exception:
            pass
        # Mensaje genérico para producción
        return f"<h4 style='color:red;'>Error en inversión. Revisa el archivo instance/inversion_error.log para más detalles.</h4>"
    
    # 🔁 Compatibilidad con inversion.py
    def predecir_precio():
        """Función de compatibilidad: expone la predicción nacional cuando
        se invoca sin argumentos. Está definida aquí para preservar la
        API histórica usada en algunas plantillas/llamadas antiguas.
        """
        return predecir_precio_nacional()
