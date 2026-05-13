import streamlit as st
import pandas as pd
from supabase import create_client

# 1. IMPORTACIÓN DE TUS MÓDULOS (Las piezas que ya tienes)
from nolasco_styles import inject_global_css
from kpi_renderer import render_kpi_grid, GREEN, RED, AMBER, GREY
from sabio_fiscal import render_sabio_fiscal
from fiscal_export import render_seccion_fiscal

# 2. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Fiscal Hub | Portal Asesor", layout="wide", initial_sidebar_state="expanded")

# Inyectamos el estilo global (Usamos "ficahub" como definiste en tu archivo de estilos)
inject_global_css("ficahub")

# 3. CONEXIÓN A DATOS (SupaBase)
# Nota: Asegúrate de tener SUPABASE_URL y SUPABASE_KEY en tus Secrets de Streamlit
def get_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase = create_client(url, key)
        # Traemos todos los inmuebles
        response = supabase.table("inmuebles").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

# Funciones auxiliares necesarias para el módulo de exportación
def safe_float(x):
    try: return float(x) if x is not None else 0.0
    except: return 0.0

def calcular_modelo_100(row):
    """Lógica simplificada para el cálculo del rendimiento neto"""
    ingresos = safe_float(row.get('renta', 0)) * 12
    gastos = (
        safe_float(row.get('ibi_anual', 0)) +
        safe_float(row.get('seguro_anual', 0)) +
        safe_float(row.get('intereses_hipoteca', 0)) +
        safe_float(row.get('comunidad', 0)) +
        safe_float(row.get('amortizacion_fiscal', 0))
    )
    return ingresos - gastos

# 4. CUERPO PRINCIPAL
def main():
    df = get_data()
    
    if df.empty:
        st.warning("No se encontraron datos en Supabase. Revisa la conexión.")
        return

    # SIDEBAR: Navegación y Filtros
    st.sidebar.title("💎 Fiscal Hub")
    menu = st.sidebar.radio("Navegación", ["Dashboard", "Fiscalidad", "Consultas IA"])
    
    selected_inmueble = st.sidebar.selectbox("Seleccionar Inmueble", df['nombre'].unique())
    row_data = df[df['nombre'] == selected_inmueble].iloc[0]

    if menu == "Dashboard":
        st.title(f"Análisis: {selected_inmueble}")
        
        # --- CAPA 3: Visualización con KPI_RENDERER ---
        rendimiento = calcular_modelo_100(row_data)
        
        kpis = [
            {"label": "Ingresos Anuales", "value": f"{safe_float(row_data['renta'])*12:,.0f}€", "color": GREY},
            {"label": "Rendimiento Neto", "value": f"{rendimiento:,.0f}€", "color": GREEN if rendimiento > 0 else RED},
            {"label": "IBI Anual", "value": f"{safe_float(row_data['ibi_anual']):,.0f}€", "color": AMBER},
            {"label": "Amortización (3%)", "value": f"{safe_float(row_data['amortizacion_fiscal']):,.0f}€", "color": GREY}
        ]
        render_kpi_grid(kpis)

        st.divider()

        # --- CAPA 1: Auditoría ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔍 Auditoría de Integridad")
            if not row_data['ref_catastral']:
                st.error("Falta Referencia Catastral")
            else:
                st.success(f"Ref. Catastral: {row_data['ref_catastral']}")
            
            if safe_float(row_data['amortizacion_fiscal']) == 0:
                st.warning("Atención: La amortización no está calculada.")

    elif menu == "Fiscalidad":
        # Llamamos a tu módulo de exportación real
        # Creamos un df_mov vacío por ahora para que no falle la firma de tu función
        df_mov_vacio = pd.DataFrame() 
        render_seccion_fiscal(df, df_mov_vacio, safe_float, calcular_modelo_100)

    elif menu == "Consultas IA":
        # --- CAPA 2: IA CONTEXTUAL ---
        st.title("🤖 Sabio Fiscal")
        # Le pasamos el contexto del inmueble actual
        contexto = f"Inmueble: {selected_inmueble}. Ingresos: {row_data['renta']}. Gastos: {row_data['ibi_anual']}..."
        render_sabio_fiscal("ficahub", contexto)

if __name__ == "__main__":
    main()