import streamlit as st
import pandas as pd
from supabase import create_client

# 1. IMPORTACIÓN DE TUS MÓDULOS REALES
from nolasco_styles import inject_global_css
from kpi_renderer import render_kpi_grid, GREEN, RED, AMBER, GREY
from sabio_fiscal import render_sabio_fiscal
from fiscal_export import render_seccion_fiscal
from data_manager import clean_fiscal_data, get_resumen_por_propietario

# 2. CONFIGURACIÓN
st.set_page_config(page_title="Fiscal Hub | Portal Asesor", layout="wide")
inject_global_css("ficahub")

# Funciones puente que pide tu fiscal_export.py
def safe_float(x):
    try:
        if x is None or x == "": return 0.0
        return float(str(x).replace(',', '.'))
    except:
        return 0.0

def calcular_modelo_100(row):
    """Cálculo exacto para el Modelo 100 basado en tus columnas"""
    ingresos = safe_float(row.get('renta', 0)) * 12
    # Gastos deducibles (Límite intereses + reparación = ingresos, el resto suma)
    deducibles = (
        safe_float(row.get('ibi_anual', 0)) +
        safe_float(row.get('seguro_anual', 0)) +
        safe_float(row.get('comunidad', 0)) +
        safe_float(row.get('intereses_hipoteca', 0)) +
        safe_float(row.get('amortizacion_fiscal', 0))
    )
    return ingresos - deducibles

# 3. CARGA DE DATOS
@st.cache_data
def load_all_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase = create_client(url, key)
        res = supabase.table("inmuebles").select("*").execute()
        df = pd.DataFrame(res.data)
        return clean_fiscal_data(df)
    except Exception as e:
        st.error(f"Error cargando Supabase: {e}")
        return pd.DataFrame()

def main():
    df = load_all_data()
    if df.empty:
        st.warning("Base de datos vacía o desconectada.")
        return

    # --- SIDEBAR: GESTIÓN DE CARTERA ---
    st.sidebar.title("💎 Fiscal Hub Pro")
    
    # Selector de Propietario (Tus 3 clientes creados)
    lista_titulares = sorted(df['titular'].unique())
    titular_sel = st.sidebar.selectbox("👤 Seleccionar Cliente", lista_titulares)
    
    # Filtrar datos por ese cliente
    df_cliente = df[df['titular'] == titular_sel]
    
    menu = st.sidebar.radio("Navegación", ["Dashboard Cartera", "Ficha Inmueble", "Fiscalidad (Export)", "Sabio IA"])

    if menu == "Dashboard Cartera":
        st.title(f"Cartera de {titular_sel}")
        resumen = get_resumen_por_propietario(df_cliente)
        
        # KPIs Globales del Cliente usando tu kpi_renderer
        total_renta = df_cliente['ingresos_anuales'].sum()
        total_neto = df_cliente['rendimiento_neto'].sum()
        
        kpis = [
            {"label": "Ingresos Totales", "value": f"{total_renta:,.0f}€", "color": GREY},
            {"label": "Rendimiento Neto", "value": f"{total_neto:,.0f}€", "color": GREEN if total_neto > 0 else RED},
            {"label": "Nº Activos", "value": f"{len(df_cliente)}", "color": AMBER}
        ]
        render_kpi_grid(kpis)
        
        st.subheader("Desglose de Activos")
        st.dataframe(df_cliente[['nombre', 'renta', 'rendimiento_neto', 'ibi_anual']], use_container_width=True)

    elif menu == "Ficha Inmueble":
        inmueble_sel = st.selectbox("Seleccionar activo", df_cliente['nombre'])
        row = df_cliente[df_cliente['nombre'] == inmueble_sel].iloc[0]
        
        st.title(f"🏠 {inmueble_sel}")
        # Aquí puedes usar el código de KPIs que te pasé anteriormente...

    elif menu == "Fiscalidad (Export)":
        st.title("📄 Generación de Informes Fiscales")
        # Esta es la conexión crítica con tu fiscal_export.py
        # Le pasamos el DF filtrado del cliente para que solo exporte lo suyo
        df_mov_vacio = pd.DataFrame() # Si no usas movimientos de caja aún
        render_seccion_fiscal(df_cliente, df_mov_vacio, safe_float, calcular_modelo_100)

    elif menu == "Sabio IA":
        st.title("🤖 Consultoría Estratégica")
        contexto = f"Cliente {titular_sel} con {len(df_cliente)} inmuebles. Datos: {df_cliente.to_dict()}"
        render_sabio_fiscal("ficahub", contexto)

if __name__ == "__main__":
    main()
