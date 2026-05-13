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
st.set_page_config(page_title="Fiscal Hub | Login Asesor", layout="wide")
inject_global_css("ficahub")

# Inicializar cliente Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# 3. LÓGICA DE AUTENTICACIÓN (LOGIN REAL)
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
def load_data():
    # Solo traemos los inmuebles que pertenecen al usuario logueado
    user_id = st.session_state.user.id
    res = supabase.table("inmuebles").select("*").eq("user_id", user_id).execute()
    df = pd.DataFrame(res.data)
    return clean_fiscal_data(df)

# 5. FUNCIONES PUENTE
def safe_float(x):
    try: return float(str(x).replace(',', '.')) if x else 0.0
    except: return 0.0

def calcular_modelo_100(row):
    # Usamos las columnas de tu CSV que sí están en Supabase
    ingresos = safe_float(row.get('renta', 0)) * 12
    gastos = safe_float(row.get('ibi_anual', 0)) + safe_float(row.get('seguro_anual', 0))
    return ingresos - gastos

# 6. CUERPO PRINCIPAL
def main():
    if "user" not in st.session_state:
        login_form()
        st.stop()

    # Si llegamos aquí, el usuario está logueado
    st.sidebar.write(f"Conectado como: {st.session_state.user.email}")
    if st.sidebar.button("Cerrar Sesión"):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

    df = load_data()
    
    if df.empty:
        st.info("No tienes inmuebles asignados todavía.")
        return

    # --- SIDEBAR: SELECTOR DE CLIENTE (TITULAR) ---
    st.sidebar.title("💎 Fiscal Hub Pro")
    
    # Si no hay columna 'titular', usamos el campo 'nombre' del inmueble o agrupamos
    # He visto en tu CSV que la columna se llama 'titular' (ej: alba, alvaro)
    col_propietario = 'titular' if 'titular' in df.columns else 'nombre'
    
    lista_clientes = sorted(df[col_propietario].unique())
    cliente_sel = st.sidebar.selectbox("👤 Seleccionar Cliente", lista_clientes)
    
    df_cliente = df[df[col_propietario] == cliente_sel]
    
    menu = st.sidebar.radio("Navegación", ["Dashboard", "Fiscalidad", "Sabio IA"])

    if menu == "Dashboard":
        st.title(f"Cartera: {cliente_sel}")
        # KPIs con tu kpi_renderer
        total_renta = (df_cliente['renta'] * 12).sum()
        kpis = [
            {"label": "Renta Bruta", "value": f"{total_renta:,.0f}€", "color": GREY},
            {"label": "Activos", "value": str(len(df_cliente)), "color": AMBER}
        ]
        render_kpi_grid(kpis)
        st.dataframe(df_cliente[['nombre', 'renta', 'ibi_anual']])

   elif menu == "Fiscalidad":
        st.title("📄 Generación de Informes Fiscales")
        
        # FIX: Renombramos 'nombre' a 'Nombre' para que fiscal_export.py no de error
        # También nos aseguramos de que otras columnas críticas tengan la mayúscula que espera el módulo
        df_export = df_cliente.rename(columns={
            'nombre': 'Nombre',
            'renta': 'Renta',
            'ibi_anual': 'IBI',
            'titular': 'Titular'
        })
        
        # Enviamos el dataframe con los nombres de columna corregidos
        df_mov_vacio = pd.DataFrame() 
        render_seccion_fiscal(df_export, df_mov_vacio, safe_float, calcular_modelo_100)
    
    
    elif menu == "Sabio IA":
        contexto = f"Datos: {df_cliente.to_dict('records')}"
        render_sabio_fiscal("ficahub", contexto)

if __name__ == "__main__":
    main()
