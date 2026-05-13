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

# 3. LÓGICA DE LOGIN
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

# 4. CARGA DE DATOS
@st.cache_data
def load_data(user_id):
    try:
        # Cargamos todos para la demo
        res = supabase.table("inmuebles").select("*").execute()
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

class ModeloDict(dict):
    """Evita que la app se rompa si falta una casilla del IRPF."""
    def __getitem__(self, key):
        return super().get(key, 0.0)

def calcular_modelo_100(row, df_mov=None, año_fiscal=None):
    """Mapeo de casillas compatible con fiscal_export.py"""
    ingresos = safe_float(row.get('renta', 0)) * 12
    ibi = safe_float(row.get('ibi_anual', 0))
    intereses = safe_float(row.get('intereses_hipoteca', 0))
    seguros_comu = safe_float(row.get('seguro_anual', 0)) + safe_float(row.get('comunidad', 0))
    amortizacion = safe_float(row.get('amortizacion_fiscal', 0))
    
    gastos_deducibles = intereses + ibi + seguros_comu + amortizacion
    rendimiento_neto = ingresos - gastos_deducibles
    
    res = ModeloDict({
        "0102": ingresos, "0104": ibi, "0106": intereses,
        "0111": seguros_comu, "0113": amortizacion,
        "0149": rendimiento_neto, "0150": rendimiento_neto * 0.6 if rendimiento_neto > 0 else 0.0,
        "0062_0075": ingresos, "reduccion_pct": 0.60, "total_gastos": gastos_deducibles
    })
    return res

# 6. FUNCIÓN PRINCIPAL
def main():
    if "user" not in st.session_state:
        login_form()
        st.stop()

    # Sidebar: Info
    st.sidebar.write(f"👤 {st.session_state.user.email}")
    if st.sidebar.button("Cerrar Sesión"):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

    df = load_data(st.session_state.user.id)
    if df.empty:
        st.info("No hay datos disponibles.")
        return

    st.sidebar.title("💎 Fiscal Hub Pro")
    
    # Selector de Propietario (Titular)
    col_propietario = 'titular' if 'titular' in df.columns else 'nombre'
    lista_propietarios = sorted(df[col_propietario].unique())
    propietario_sel = st.sidebar.selectbox("Seleccionar Cliente", lista_propietarios)
    
    df_cliente = df[df[col_propietario] == propietario_sel]
    menu = st.sidebar.radio("Navegación", ["Dashboard", "Fiscalidad", "Sabio IA"])

    if menu == "Dashboard":
        st.title(f"Cartera: {propietario_sel}")
        total_renta = (df_cliente['renta'] * 12).sum()
        total_neto = df_cliente.apply(lambda r: calcular_modelo_100(r)['0149'], axis=1).sum()
        
        kpis = [
            {"label": "Renta Bruta", "value": f"{total_renta:,.0f}€", "color": GREY},
            {"label": "Rendimiento Neto", "value": f"{total_neto:,.0f}€", "color": GREEN if total_neto > 0 else RED},
            {"label": "Activos", "value": str(len(df_cliente)), "color": AMBER}
        ]
        render_kpi_grid(kpis)
        st.dataframe(df_cliente[['nombre', 'tipo', 'renta', 'ibi_anual']], use_container_width=True)

    elif menu == "Fiscalidad":
        st.title("📄 Generación de Informes Fiscales")
        df_export = df_cliente.rename(columns={'nombre': 'Nombre', 'renta': 'Renta', 'ibi_anual': 'IBI', 'titular': 'Titular'})
        render_seccion_fiscal(df_export, pd.DataFrame(), safe_float, calcular_modelo_100)

    elif menu == "Sabio IA":
        st.title("🤖 Sabio Fiscal")
        resumen = df_cliente[['nombre', 'renta', 'ibi_anual']].to_dict('records')
        
        # FIX: Añadimos el argumento 'seccion' para que no de TypeError
        render_sabio_fiscal(
            app="ficahub", 
            seccion=f"analisis_{propietario_sel.replace(' ', '_')}", 
            contexto=f"Datos del cliente {propietario_sel}: {resumen}"
        )

if __name__ == "__main__":
    main()
