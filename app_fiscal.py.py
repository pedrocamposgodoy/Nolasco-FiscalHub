import streamlit as st
import pandas as pd
from supabase import create_client

# 1. IMPORTACIÓN DE TUS MÓDULOS
from nolasco_styles import inject_global_css
from kpi_renderer import render_kpi_grid, GREEN, RED, AMBER, GREY
from sabio_fiscal import render_sabio_fiscal
from fiscal_export import render_seccion_fiscal
from data_manager import clean_fiscal_data

# 2. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Fiscal Hub | Acceso Asesor", layout="wide")
inject_global_css("ficahub")

# 3. SISTEMA DE LOGIN SENCILLO
def check_password():
    """Devuelve True si el usuario introdujo la contraseña correcta."""
    def password_entered():
        # Aquí puedes poner la contraseña que quieras
        if st.session_state["password"] == "asesor2024":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # No guardamos la contraseña
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Pantalla de Login
        st.markdown('<div class="nc-card" style="max-width:400px; margin: 100px auto;">', unsafe_allow_html=True)
        st.title("🔐 Acceso Fiscal Hub")
        st.text_input("Contraseña de Asesor", type="password", on_change=password_entered, key="password")
        if "password_correct" in st.session_state:
            st.error("😕 Contraseña incorrecta")
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    return st.session_state["password_correct"]

# 4. CARGA DE DATOS (Asegura traer TODOS los registros)
@st.cache_data
def load_all_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase = create_client(url, key)
        # Traemos todos sin límites para ver a todos los propietarios
        res = supabase.table("inmuebles").select("*").execute()
        df = pd.DataFrame(res.data)
        return clean_fiscal_data(df)
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {e}")
        return pd.DataFrame()

# 5. FUNCIONES PUENTE PARA EXPORTACIÓN
def safe_float(x):
    try: return float(str(x).replace(',', '.')) if x else 0.0
    except: return 0.0

def calcular_modelo_100(row):
    ingresos = safe_float(row.get('renta', 0)) * 12
    gastos = sum([safe_float(row.get(c, 0)) for c in ['ibi_anual', 'seguro_anual', 'intereses_hipoteca', 'comunidad', 'amortizacion_fiscal']])
    return ingresos - gastos

# 6. INTERFAZ PRINCIPAL
def main():
    if not check_password():
        st.stop()  # Si no hay login, se detiene aquí

    df = load_all_data()
    
    if df.empty:
        st.info("Esperando datos de Supabase...")
        return

    # --- SIDEBAR: MULTI-PROPIETARIO ---
    st.sidebar.image("https://odxixtgqcyddfqaapqgi.supabase.co/storage/v1/object/public/logos/logo_fiscalhub.png", width=200) # Si tienes logo
    st.sidebar.title("Panel de Control")
    
    # Aquí obtenemos la lista de todos los titulares diferentes
    propietarios = sorted(df['titular'].unique())
    titular_sel = st.sidebar.selectbox("👤 Seleccionar Cliente", propietarios)
    
    # Filtramos la base de datos por el dueño elegido
    df_cliente = df[df['titular'] == titular_sel]
    
    menu = st.sidebar.radio("Sección", ["Resumen Cartera", "Detalle Activo", "Fiscalidad", "Sabio IA"])

    if menu == "Resumen Cartera":
        st.title(f"Cartera: {titular_sel}")
        # KPIs totales del cliente
        total_renta = (df_cliente['renta'] * 12).sum()
        total_neto = df_cliente.apply(calcular_modelo_100, axis=1).sum()
        
        kpis = [
            {"label": "Renta Bruta Anual", "value": f"{total_renta:,.0f}€", "color": GREY},
            {"label": "Rendimiento Neto", "value": f"{total_neto:,.0f}€", "color": GREEN if total_neto > 0 else RED},
            {"label": "Nº de Inmuebles", "value": f"{len(df_cliente)}", "color": AMBER}
        ]
        render_kpi_grid(kpis)
        
        st.subheader("Inmuebles vinculados")
        st.table(df_cliente[['nombre', 'tipo', 'renta', 'ibi_anual']])

    elif menu == "Detalle Activo":
        inmueble = st.selectbox("Activo a analizar", df_cliente['nombre'])
        row = df_cliente[df_cliente['nombre'] == inmueble].iloc[0]
        st.title(f"🏠 {inmueble}")
        # Aquí meteríamos los KPIs individuales que ya vimos

    elif menu == "Fiscalidad":
        render_seccion_fiscal(df_cliente, pd.DataFrame(), safe_float, calcular_modelo_100)

    elif menu == "Sabio IA":
        contexto = f"Datos del cliente {titular_sel}: {df_cliente.to_dict('records')}"
        render_sabio_fiscal("ficahub", contexto)

if __name__ == "__main__":
    main()
