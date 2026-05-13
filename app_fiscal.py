import streamlit as st
import pandas as pd
from supabase import create_client, Client

# 1. IMPORTACIÓN DE TUS MÓDULOS
from nolasco_styles import inject_global_css
from kpi_renderer import render_kpi_grid, GREEN, RED, AMBER, GREY
from sabio_fiscal import render_sabio_fiscal
from fiscal_export import render_seccion_fiscal
from data_manager import clean_fiscal_data

# 2. CONFIGURACIÓN E INYECCIÓN DE ESTILO
st.set_page_config(page_title="Fiscal Hub | Portal Asesor", layout="wide")
inject_global_css("ficahub")

# Inicializar cliente Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# 3. LÓGICA DE AUTENTICACIÓN (LOGIN)
def login_form():
    st.markdown('<div class="nc-card" style="max-width:400px; margin: 100px auto;">', unsafe_allow_html=True)
    st.title("🔐 Acceso Asesor")
    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")
    
    if st.button("Entrar al Portal"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.success("Acceso concedido")
            st.rerun()
        except Exception as e:
            st.error("Error: Credenciales no válidas")
    st.markdown('</div>', unsafe_allow_html=True)

# 4. CARGA DE DATOS FILTRADOS
@st.cache_data
def load_data(user_id):
    try:
        res = supabase.table("inmuebles").select("*").eq("user_id", user_id).execute()
        df = pd.DataFrame(res.data)
        return clean_fiscal_data(df)
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame()

# 5. FUNCIONES COMPATIBLES CON FISCAL_EXPORT
def safe_float(x):
    try:
        if x is None or x == "": return 0.0
        return float(str(x).replace(',', '.'))
    except:
        return 0.0

# REPARACIÓN: Firma compatible con fiscal_export.py (acepta row, df_mov y año_fiscal)
def calcular_modelo_100(row, df_mov=None, año_fiscal=None):
    ingresos = safe_float(row.get('renta', 0)) * 12
    gastos = (
        safe_float(row.get('ibi_anual', 0)) + 
        safe_float(row.get('seguro_anual', 0)) +
        safe_float(row.get('comunidad', 0)) +
        safe_float(row.get('intereses_hipoteca', 0)) +
        safe_float(row.get('amortizacion_fiscal', 0))
    )
    return ingresos - gastos

# 6. FUNCIÓN PRINCIPAL
def main():
    # Verificación de usuario
    if "user" not in st.session_state:
        login_form()
        st.stop()

    # Sidebar: Usuario y Logout
    st.sidebar.write(f"👤 {st.session_state.user.email}")
    if st.sidebar.button("Cerrar Sesión"):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

    # Carga de datos
    df = load_data(st.session_state.user.id)
    
    if df.empty:
        st.info("No se han encontrado inmuebles asociados a esta cuenta.")
        return

    st.sidebar.divider()
    st.sidebar.title("💎 Fiscal Hub Pro")

    # Identificar columna de propietario (titular)
    col_propietario = 'titular' if 'titular' in df.columns else 'nombre'
    lista_propietarios = sorted(df[col_propietario].unique())
    propietario_sel = st.sidebar.selectbox("Seleccionar Cliente", lista_propietarios)
    
    df_cliente = df[df[col_propietario] == propietario_sel]

    # Menú de Navegación
    menu = st.sidebar.radio("Navegación", ["Dashboard", "Fiscalidad", "Sabio IA"])

    if menu == "Dashboard":
        st.title(f"Cartera: {propietario_sel}")
        total_renta = (df_cliente['renta'] * 12).sum()
        # Usamos lambda para llamar a la función solo con el primer argumento en el Dashboard
        total_neto = df_cliente.apply(lambda r: calcular_modelo_100(r), axis=1).sum()
        
        kpis = [
            {"label": "Renta Bruta Anual", "value": f"{total_renta:,.0f}€", "color": GREY},
            {"label": "Rendimiento Neto", "value": f"{total_neto:,.0f}€", "color": GREEN if total_neto > 0 else RED},
            {"label": "Activos", "value": str(len(df_cliente)), "color": AMBER}
        ]
        render_kpi_grid(kpis)
        st.dataframe(df_cliente[['nombre', 'tipo', 'renta', 'ibi_anual']], use_container_width=True)

    elif menu == "Fiscalidad":
        st.title("📄 Generación de Informes Fiscales")
        
        # Parche de mayúsculas para compatibilidad con fiscal_export.py
        df_export = df_cliente.rename(columns={
            'nombre': 'Nombre',
            'renta': 'Renta',
            'ibi_anual': 'IBI',
            'titular': 'Titular'
        })
        
        df_mov_vacio = pd.DataFrame() 
        # Llamada al exportador con la función corregida
        render_seccion_fiscal(df_export, df_mov_vacio, safe_float, calcular_modelo_100)

    elif menu == "Sabio IA":
        st.title("🤖 Consultoría Estratégica")
        resumen = df_cliente[['nombre', 'renta', 'ibi_anual']].to_dict('records')
        render_sabio_fiscal("ficahub", f"Contexto del cliente {propietario_sel}: {resumen}")

if __name__ == "__main__":
    main()
