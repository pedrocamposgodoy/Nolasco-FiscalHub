# ================================================================
# sabio_fiscal.py
# Asesor Fiscal IA — FiscalHub
#
# Arquitectura idéntica a sabio_patrimonial.py de Nolasco Capital.
# Adaptado para análisis de decisiones fiscales proactivas.
## ================================================================
# fiscalhub_app.py — FiscalHub · Portal Asesoría Fiscal
# Nolasco Capital ecosystem
# Diseño: degradados azul/gris pastel · sidebar azul marino
# ================================================================

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date
import io
import html as _html
from nolasco_styles import inject_global_css
from kpi_renderer import render_kpi_row, render_kpi_grid, ACCENT_F, RED, AMBER, GREEN

# Paleta determinista por cliente — 8 colores profesionales
# Siempre el mismo color para el mismo cliente_id
_PALETA_CLI = [
    "#1E3A5F",  # azul marino
    "#3D2B6B",  # morado oscuro
    "#1A4731",  # verde oscuro
    "#7A2D1A",  # rojo ladrillo
    "#1A3A4A",  # azul petróleo
    "#4A3000",  # marrón dorado
    "#2D1A4A",  # índigo oscuro
    "#3B3B3B",  # gris antracita
]

def _color_cli(cliente_id: str) -> str:
    """Color determinista para un cliente — siempre el mismo."""
    return _PALETA_CLI[abs(hash(str(cliente_id))) % len(_PALETA_CLI)]

def _e(s):
    """Escapar caracteres HTML especiales en datos de usuario."""
    return _html.escape(str(s)) if s else ""

st.set_page_config(
    page_title="FiscalHub · Nolasco Capital",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SUPABASE_URL = "https://odxixtgqcyddfqaapqgi.supabase.co"
SUPABASE_KEY = "sb_publishable_Obgti7yMfXw8wCUL2FbTtA_EWeyHuM9"

def _h(token=None):
    t = token or st.session_state.get("fh_token") or SUPABASE_KEY
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {t}",
            "Content-Type": "application/json", "Prefer": "return=representation"}

def _hd():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}

# ── INYECTAR ESTILO GLOBAL ──────────────────────────────────────
# El CSS completo se gestiona desde nolasco_styles.py (único fuente de verdad)
# Esto se llama UNA VEZ al inicio de la app


# ── Helpers ──────────────────────────────────────────────────────
def sf(v, d=0):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)): return float(d)
        return float(v)
    except: return float(d)

def _gv(row, *keys, d=0):
    for k in keys:
        v = row.get(k)
        if v is not None:
            try:
                f = float(v)
                if not pd.isna(f): return f
            except: pass
    return float(d)

def fmt_eur(n, sign=False):
    n = float(n or 0)
    s = f"{abs(n):,.0f}".replace(",",".")
    prefix = "−" if n < 0 else ("+" if sign else "")
    return f"{prefix}{s} €"

def days_to_irpf():
    hoy = date.today()
    cierre = date(hoy.year, 6, 30)
    if hoy > cierre: cierre = date(hoy.year+1, 6, 30)
    return (cierre - hoy).days

# ── Auth ─────────────────────────────────────────────────────────
def login_asesor(email, password):
    r = requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password})
    if r.status_code == 200:
        d = r.json()
        return {"ok": True, "user_id": d["user"]["id"],
                "email": d["user"]["email"], "token": d["access_token"]}
    return {"ok": False, "error": r.json().get("error_description", "Error de acceso")}

def registrar_asesor(email, password, nombre, despacho):
    r = requests.post(f"{SUPABASE_URL}/auth/v1/signup",
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password})
    if r.status_code == 200:
        uid = r.json().get("id") or r.json().get("user", {}).get("id")
        if uid:
            requests.post(f"{SUPABASE_URL}/rest/v1/asesores", headers=_h(),
                json={"user_id": uid, "nombre": nombre, "despacho": despacho, "email": email})
        return {"ok": True}
    return {"ok": False, "error": r.json().get("error_description", "Error de registro")}

def get_asesor_info(user_id):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/asesores?user_id=eq.{user_id}&select=*", headers=_h())
    if r.status_code == 200 and r.json(): return r.json()[0]
    return {"nombre": "Asesor", "despacho": "Despacho Fiscal", "email": ""}

# ── Supabase data ─────────────────────────────────────────────────
def get_clientes_vinculados(asesor_user_id):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/accesos_asesor"
        f"?asesor_user_id=eq.{asesor_user_id}&activo=eq.true&select=*", headers=_h())
    return r.json() if r.status_code == 200 else []

def get_inmuebles_propietario(pid):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/inmuebles?user_id=eq.{pid}&select=*", headers=_hd())
    return pd.DataFrame(r.json()) if r.status_code == 200 and r.json() else pd.DataFrame()

def get_movimientos_propietario(pid):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/movimientos?user_id=eq.{pid}&select=*", headers=_hd())
    return pd.DataFrame(r.json()) if r.status_code == 200 and r.json() else pd.DataFrame()

def vincular_propietario(asesor_user_id, codigo):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/accesos_asesor"
        f"?codigo=eq.{codigo.upper()}&activo=eq.true&select=*", headers=_h())
    if r.status_code == 200 and r.json():
        acc = r.json()[0]
        pid = acc.get("propietario_id")
        nombre = acc.get("nombre") or acc.get("nombre_propietario", "Propietario")
        if not pid: return {"ok": False, "error": "Código sin propietario"}
        requests.patch(f"{SUPABASE_URL}/rest/v1/accesos_asesor?id=eq.{acc['id']}",
            headers={**_h(), "Prefer": "return=minimal"}, json={"asesor_user_id": asesor_user_id})
        return {"ok": True, "propietario_id": pid, "nombre": nombre}
    return {"ok": False, "error": "Código no válido o ya utilizado"}

# ── Análisis fiscal ───────────────────────────────────────────────
def calcular_semaforo_inmueble(row):
    """Evalúa un inmueble — devuelve problemas detectados y estado semáforo."""
    problemas = []
    renta     = _gv(row,"renta","Renta")
    ibi       = _gv(row,"ibi_anual","IBI_Anual")
    amort     = _gv(row,"amortizacion_fiscal","Amortizacion_Fiscal")
    seguro    = _gv(row,"seguro_anual","Seguro_Anual")
    comunidad = _gv(row,"comunidad","Comunidad")
    catastral = _gv(row,"valor_catastral","Valor_Catastral")
    precio    = _gv(row,"precio_compra","Precio_Compra")
    tipo      = str(row.get("tipo_arrendamiento") or row.get("Tipo_Arrendamiento","")).lower()
    fecha_str = str(row.get("fecha_inicio_contrato") or row.get("Fecha_Inicio_Contrato","") or "")
    ingresos  = renta * 12

    if amort == 0 and renta > 0:
        if catastral == 0 and precio == 0:
            problemas.append({"tipo":"crit","titulo":"Amortización sin calcular",
                "desc":"Falta valor catastral y precio de compra.","accion":"Solicitar escritura o consultar catastro"})
        else:
            problemas.append({"tipo":"crit","titulo":"Amortización a 0 — revisar",
                "desc":f"Catastral: {fmt_eur(catastral)} · Precio compra: {fmt_eur(precio)}",
                "accion":"Calcular 3% s/ MAX(precio compra, catastral) × % construcción"})

    if ibi == 0 and renta > 0:
        problemas.append({"tipo":"crit","titulo":"IBI no registrado",
            "desc":"Casilla 0106 a cero.","accion":"Solicitar recibo IBI 2024 al propietario"})

    if seguro == 0 and renta > 0:
        problemas.append({"tipo":"warn","titulo":"Seguro de hogar no registrado",
            "desc":"Puede ser deducible.","accion":"Verificar si el propietario tiene póliza"})

    if comunidad == 0 and renta > 0:
        problemas.append({"tipo":"warn","titulo":"Comunidad de propietarios a 0",
            "desc":"Revisar si tiene gastos de comunidad.","accion":"Confirmar con propietario"})

    gastos_total = ibi + seguro + comunidad*12 + amort
    if ingresos > 0 and gastos_total > ingresos * 0.70:
        problemas.append({"tipo":"warn","titulo":"Gastos > 70% de los ingresos",
            "desc":f"Gastos: {fmt_eur(gastos_total)} · Ingresos: {fmt_eur(ingresos)}",
            "accion":"Revisar si hay gastos duplicados o importes incorrectos"})

    es_larga = "larga" in tipo or "habitual" in tipo or tipo == ""
    if es_larga:
        try:
            anyo = int(fecha_str[:4]) if fecha_str and len(fecha_str) >= 4 else 0
            if 0 < anyo <= 2023:
                problemas.append({"tipo":"warn","titulo":"Posible reducción 60% — confirmar",
                    "desc":f"Contrato desde {anyo}. Verificar condiciones Art. 23.2 LIRPF.",
                    "accion":"Confirmar fecha y condiciones antes de aplicar"})
        except: pass

    if any(p["tipo"] == "crit" for p in problemas):   estado = "cr"
    elif any(p["tipo"] == "warn" for p in problemas):  estado = "wn"
    else:                                               estado = "ok"

    return {"problemas": problemas, "estado": estado}

def calcular_modelo100_inmueble(row, df_mov):
    nombre    = str(row.get("nombre") or row.get("Nombre",""))
    renta     = _gv(row,"renta","Renta")
    dias      = int(_gv(row,"dias_arrendados_anio","Dias_Arrendados_Anio",d=365))
    factor    = min(dias,365)/365
    ingresos  = renta * 12 * factor
    intereses = _gv(row,"intereses_hipoteca","Intereses_Hipoteca") * factor
    ibi       = _gv(row,"ibi_anual","IBI_Anual") * factor
    comunidad = _gv(row,"comunidad","Comunidad") * 12 * factor
    seguro_h  = _gv(row,"seguro_anual","Seguro_Anual") * factor
    seguro_v  = _gv(row,"seguro_vida","Seguro_Vida") * factor
    ascensor  = _gv(row,"gasto_ascensor","Gasto_Ascensor") * factor
    com_seg   = comunidad + seguro_h + seguro_v + ascensor
    suministros = _gv(row,"servicios_suministros","Servicios_Suministros") * factor
    gastos_jur  = _gv(row,"gastos_juridicos","Gastos_Juridicos") * factor
    retenciones = _gv(row,"retenciones_irpf","Retenciones_IRPF")
    precio   = _gv(row,"precio_compra","Precio_Compra")
    imptos   = _gv(row,"impuestos_compra","Impuestos_Compra")
    gastos_c = _gv(row,"gastos_compra","Gastos_Compra")
    catastral= _gv(row,"valor_catastral","Valor_Catastral")
    pct_c    = _gv(row,"pct_construccion","Pct_Construccion",d=0.75)
    base_amort = max(precio+imptos+gastos_c, catastral)
    amort    = base_amort * pct_c * 0.03 * factor
    reparaciones = 0.0
    if not df_mov.empty:
        ca = "apartamento" if "apartamento" in df_mov.columns else "Apartamento"
        ct = "tipo" if "tipo" in df_mov.columns else "Tipo"
        cc = "categoria" if "categoria" in df_mov.columns else "Categoría"
        ci = "importe" if "importe" in df_mov.columns else "Importe"
        mask = ((df_mov.get(ca,pd.Series())==nombre) &
                (df_mov.get(ct,pd.Series())=="Gasto") &
                (df_mov.get(cc,pd.Series()).isin(["Mantenimiento","Reparación"])))
        reparaciones = float(df_mov[mask][ci].sum()) * factor if mask.any() else 0
    total_gastos = intereses+reparaciones+ibi+com_seg+suministros+gastos_jur+amort
    rend_neto    = ingresos - total_gastos
    tipo  = str(row.get("tipo_arrendamiento") or row.get("Tipo_Arrendamiento","")).lower()
    fecha = str(row.get("fecha_inicio_contrato") or row.get("Fecha_Inicio_Contrato","") or "")
    es_larga = "larga" in tipo or "habitual" in tipo or tipo == ""
    red_pct = 0
    if es_larga:
        try:
            anyo = int(fecha[:4]) if fecha and len(fecha)>=4 else 0
            red_pct = 60 if 0<anyo<=2023 else 50
        except: red_pct = 50
    reduccion = rend_neto * red_pct/100 if rend_neto > 0 else 0
    rend_final = rend_neto - reduccion
    return {
        "ingresos": round(ingresos,2), "intereses": round(intereses,2),
        "reparaciones": round(reparaciones,2), "ibi": round(ibi,2),
        "comunidad_seguros": round(com_seg,2), "suministros": round(suministros,2),
        "gastos_juridicos": round(gastos_jur,2), "amortizacion": round(amort,2),
        "total_gastos": round(total_gastos,2), "rend_neto": round(rend_neto,2),
        "red_pct": red_pct, "reduccion": round(reduccion,2),
        "rend_final": round(rend_final,2), "retenciones": round(retenciones,2), "dias": dias,
    }

def calcular_modelo100_global(df_inm, df_mov):
    if df_inm.empty: return {}
    total = {k:0 for k in ["ingresos","intereses","reparaciones","ibi","comunidad_seguros",
             "suministros","gastos_juridicos","amortizacion","total_gastos","rend_neto",
             "reduccion","rend_final","retenciones"]}
    for _, row in df_inm.iterrows():
        m = calcular_modelo100_inmueble(row, df_mov)
        for k in total: total[k] += m.get(k,0)
    return {k: round(v,2) for k,v in total.items()}

def calcular_alertas_cliente(df_inm, df_mov):
    alertas = []
    if df_inm.empty: return alertas
    for _, row in df_inm.iterrows():
        nombre = str(row.get("nombre") or row.get("Nombre",""))
        sem = calcular_semaforo_inmueble(row)
        for p in sem["problemas"]:
            alertas.append({**p, "inmueble": nombre, "categoria": "Fiscal"})
    return alertas

def construir_cartera(clientes_vinculados):
    cartera = []
    for acc in clientes_vinculados:
        pid = acc.get("propietario_id") or acc.get("user_id")
        nombre_raw = acc.get("nombre") or acc.get("nombre_propietario","")
        email_raw  = acc.get("email","")
        if nombre_raw and " " not in nombre_raw and "@" not in nombre_raw:
            nombre = nombre_raw
        elif email_raw:
            nombre = email_raw.split("@")[0].replace("."," ").title()
        else:
            nombre = nombre_raw or "Propietario"
        if not pid: continue
        df_inm = get_inmuebles_propietario(pid)
        df_mov = get_movimientos_propietario(pid)
        alertas = calcular_alertas_cliente(df_inm, df_mov)
        modelo  = calcular_modelo100_global(df_inm, df_mov)
        criticas = len([a for a in alertas if a["tipo"]=="crit"])
        medias   = len([a for a in alertas if a["tipo"]=="warn"])
        impacto  = sum(a.get("impacto",0) for a in alertas)
        estado   = "critico" if criticas>0 else "medio" if medias>0 else "ok"
        cartera.append({
            "id": pid, "nombre": nombre,
            "inmuebles": len(df_inm), "criticas": criticas, "medias": medias,
            "impacto": impacto, "estado": estado,
            "alertas": alertas, "df_inm": df_inm, "df_mov": df_mov, "modelo100": modelo,
        })
    cartera.sort(key=lambda x:({"critico":0,"medio":1,"ok":2}[x["estado"]],-x["criticas"]))
    return cartera

# ── Sidebar ───────────────────────────────────────────────────────
def render_sidebar():
    asesor   = st.session_state.get("fh_asesor", {})
    nombre   = asesor.get("nombre","Asesor")
    despacho = asesor.get("despacho","Despacho Fiscal")
    iniciales= "".join(p[0].upper() for p in nombre.split()[:2])
    dias     = days_to_irpf()
    pct      = max(0, min(100, int((90-dias)/90*100)))
    color    = "#DC2626" if dias<30 else "#D97706" if dias<60 else "#059669"

    st.markdown(f"""
    <div class="sb-brand">
      <div style="display:flex;align-items:center;gap:10px;">
        <div class="sb-logo">NC</div>
        <div class="sb-wordmark">FiscalHub</div>
      </div>
      <div class="sb-tag">Portal asesoría fiscal</div>
    </div>
    <div class="sb-advisor">
      <div class="sb-avatar">{iniciales}</div>
      <div>
        <div class="sb-advisor-name">{nombre}</div>
        <div class="sb-advisor-desc">{despacho}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    for label, key in [("🗂 Cartera","cartera"),("⚠️ Alertas","alertas"),
                        ("📥 Exportar","exportar"),("🔗 Vincular","vincular")]:
        if st.sidebar.button(label, key=f"sb_{key}", use_container_width=True):
            for k in ["fh_cliente_sel","fh_inmueble_sel"]:
                st.session_state.pop(k, None)
            st.session_state.fh_menu = key
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"""
    <div class="sb-irpf">
      <div class="sb-irpf-label">Cierre IRPF 2025</div>
      <div class="sb-irpf-num" style="color:{color};">{dias}
        <span style="font-size:14px;font-weight:600;margin-left:4px;opacity:0.7;">días</span>
      </div>
      <div class="sb-irpf-sub">30 jun · campaña 2025</div>
      <div class="sb-bar"><div class="sb-fill" style="width:{pct}%;background:{color};"></div></div>
      <div class="sb-bar-labels"><span>hoy</span><span>30 jun</span></div>
    </div>""", unsafe_allow_html=True)

    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        for k in ["fh_logged","fh_user_id","fh_token","fh_asesor","fh_menu",
                  "fh_cliente_sel","fh_inmueble_sel","fh_cartera","fh_validaciones"]:
            st.session_state.pop(k, None)
        st.rerun()

# ── LOGIN ─────────────────────────────────────────────────────────
def pantalla_login():
    inject_global_css("ficahub")
    st.markdown("<div style='height:12vh;'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;margin-bottom:22px;">
          <div style="display:inline-flex;align-items:center;gap:10px;margin-bottom:6px;">
            <div style="width:32px;height:32px;border:2px solid #534AB7;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:'Playfair Display',serif;font-size:13px;color:#534AB7;font-weight:700;">NC</div>
            <span style="font-family:'Playfair Display',serif;font-size:24px;color:#1e293b;font-weight:700;">FiscalHub</span>
          </div>
          <div style="font-size:9px;letter-spacing:0.18em;text-transform:uppercase;color:#94A3B8;margin-top:4px;">Portal Asesoría Fiscal · Nolasco Capital</div>
        </div>
        <div style="background:#FFFFFF;border:1px solid rgba(83,74,183,0.12);border-radius:12px;padding:24px 22px 20px;box-shadow:0 4px 24px rgba(83,74,183,0.08);">
        """, unsafe_allow_html=True)

        tab_li, tab_re = st.tabs(["Acceder", "Registrarse"])
        with tab_li:
            em = st.text_input("", key="li_em", placeholder="email@despacho.es", label_visibility="collapsed")
            pw = st.text_input("", type="password", key="li_pw", placeholder="Contraseña", label_visibility="collapsed")
            if st.button("Entrar →", key="li_btn", use_container_width=True, type="primary"):
                if em and pw:
                    with st.spinner("Verificando..."):
                        res = login_asesor(em, pw)
                    if res["ok"]:
                        st.session_state.update({"fh_logged":True,"fh_user_id":res["user_id"],
                            "fh_token":res["token"],"fh_asesor":get_asesor_info(res["user_id"]),"fh_menu":"cartera"})
                        st.rerun()
                    else: st.error(res.get("error","Credenciales incorrectas"))
                else: st.warning("Introduce email y contraseña")

        with tab_re:
            c1,c2 = st.columns(2)
            with c1: nm = st.text_input("",key="rg_nm",placeholder="Nombre completo",label_visibility="collapsed")
            with c2: ds = st.text_input("",key="rg_ds",placeholder="Despacho",label_visibility="collapsed")
            em_r = st.text_input("",key="rg_em",placeholder="email@despacho.es",label_visibility="collapsed")
            pw_r = st.text_input("",type="password",key="rg_pw",placeholder="Contraseña (mín. 8 car.)",label_visibility="collapsed")
            if st.button("Crear cuenta →",key="rg_btn",use_container_width=True,type="primary"):
                if all([nm,ds,em_r,pw_r]):
                    if len(pw_r)<8: st.error("Mínimo 8 caracteres")
                    else:
                        with st.spinner("Creando..."): res = registrar_asesor(em_r,pw_r,nm,ds)
                        if res["ok"]: st.success("✅ Cuenta creada. Revisa tu email y accede.")
                        else: st.error(res.get("error","Error"))
                else: st.warning("Completa todos los campos")
        st.markdown("</div>", unsafe_allow_html=True)

# ── CARTERA ───────────────────────────────────────────────────────
def pantalla_cartera():
    cartera = st.session_state.get("fh_cartera", [])
    if not cartera:
        st.markdown("""<div style="text-align:center;padding:60px 20px;">
          <div style="font-size:36px;margin-bottom:14px;">🔗</div>
          <div style="font-family:'DM Serif Display',serif;font-size:22px;color:#1E2A3A;margin-bottom:8px;">Sin clientes vinculados</div>
          <div style="font-size:13px;color:#5A6A7E;">Ve a Vincular e introduce el código que te dé el propietario desde Nolasco Capital.</div>
        </div>""", unsafe_allow_html=True)
        return

    total_inm  = sum(c["inmuebles"] for c in cartera)
    total_crit = sum(c["criticas"]  for c in cartera)
    total_imp  = sum(c["impacto"]   for c in cartera)
    n_crit = sum(1 for c in cartera if c["estado"]=="critico")
    n_med  = sum(1 for c in cartera if c["estado"]=="medio")
    n_ok   = sum(1 for c in cartera if c["estado"]=="ok")

    st.markdown(f"""<div style="margin-bottom:20px;">
      <div class="nc-page-label">Granada · Despacho fiscal</div>
      <div class="nc-page-title">Cartera de clientes</div>
      <div class="nc-page-sub">{len(cartera)} propietarios · {total_inm} inmuebles · campaña IRPF 2025</div>
    </div>""", unsafe_allow_html=True)

    render_kpi_row([
        {"label":"👥 Clientes",        "value":str(len(cartera)),
         "color":ACCENT_F,
         "subtitle":f"{n_crit} críticos · {n_med} revisar · {n_ok} OK"},
        {"label":"🏠 Inmuebles",       "value":str(total_inm),
         "color":ACCENT_F,             "subtitle":"Activos patrimoniales"},
        {"label":"🚨 Alertas críticas","value":str(total_crit),
         "color":RED,                  "subtitle":"Antes del 30 jun"},
        {"label":"💶 Impacto fiscal",  "value":fmt_eur(total_imp),
         "color":AMBER,                "subtitle":"Recuperable · cartera"},
    ])


    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    cf1,cf2 = st.columns([3,1])
    with cf1: filtro = st.radio("",["Todos","Críticos","A revisar","OK"],horizontal=True,key="fh_filtro",label_visibility="collapsed")
    with cf2: busqueda = st.text_input("",placeholder="🔍 Buscar...",key="fh_busqueda",label_visibility="collapsed")

    rows = [c for c in cartera if
            (filtro=="Todos" or (filtro=="Críticos" and c["estado"]=="critico") or
             (filtro=="A revisar" and c["estado"]=="medio") or (filtro=="OK" and c["estado"]=="ok")) and
            (not busqueda or busqueda.lower() in c["nombre"].lower())]

    # Colores header por estado
    # Estado semántico para badge
    _ECOL  = {"critico":"#DC2626","medio":"#D97706","ok":"#059669"}
    _ELBL  = {"critico":"⚠ Crítico","medio":"◔ Revisar","ok":"✓ OK"}
    _BADGE = {"critico":"rgba(220,38,38,0.12)",
              "medio":"rgba(217,119,6,0.12)","ok":"rgba(5,150,105,0.12)"}

    def _cli_icon(nombre):
        n = nombre.lower()
        if any(x in n for x in ["bufete","abogad","juríd","legal"]): return "⚖️","Bufete"
        if any(x in n for x in ["inmo","piso","alquil"]): return "🏢","Inmobiliaria"
        if any(x in n for x in ["médic","clínic","salud"]): return "🏥","Clínica"
        if any(x in n for x in ["restaur","hostel","bar","café"]): return "🍽️","Hostelería"
        if any(x in n for x in ["sl","slu","s.l","s.a"]): return "🏛️","Empresa"
        return "👤","Particular"

    MAX_COLS = 4
    for fila_start in range(0, len(rows), MAX_COLS):
        fila_rows = rows[fila_start:fila_start+MAX_COLS]
        cols = st.columns(MAX_COLS)
        for col_idx, c in enumerate(fila_rows):
            estado   = c["estado"]
            hdr      = _color_cli(c["id"])  # color único por cliente
            txt      = _ECOL[estado]
            lbl      = _ELBL[estado]
            badge_bg = _BADGE[estado]
            icon, tipo = _cli_icon(c["nombre"])
            imp_v    = fmt_eur(abs(c["impacto"])) if c["impacto"] else "—"
            cr_col   = "#DC2626" if c["criticas"]>0 else "#64748B"
            med_col  = "#D97706" if c["medias"]>0   else "#64748B"
            modelo   = c.get("modelo100",{})
            ingresos = fmt_eur(modelo.get("ingresos",0))
            base_imp = fmt_eur(modelo.get("rend_final",0))
            with cols[col_idx]:
                hdr_html = (
                    f'<div style="background:{hdr};border-radius:12px 12px 0 0;' +
                    f'padding:14px 16px 12px;display:flex;align-items:center;gap:10px;margin-bottom:-1px;">' +
                    f'<span style="font-size:22px;">{icon}</span>' +
                    f'<div style="flex:1;min-width:0;">' +
                    f'<div style="font-size:18px;font-weight:800;color:#FFF;line-height:1.2;' +
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{c["nombre"]}</div>' +
                    f'<div style="font-size:10px;color:rgba(255,255,255,0.65);margin-top:2px;">' +
                    f'<span style="font-size:13px;opacity:0.75;">{tipo} · {c["inmuebles"]} inmuebles</span></div></div>' +
                    f'<span style="background:rgba(255,255,255,0.15);color:#FFF;font-size:9px;' +
                    f'font-weight:700;padding:3px 8px;border-radius:6px;">{lbl}</span></div>'
                )
                body_html = (
                    '<div style="background:#FFF;border:2px solid #E2E8F0;border-top:none;' +
                    'border-radius:0 0 12px 12px;padding:14px 16px 12px;">' +
                    '<div style="display:flex;justify-content:space-between;margin-bottom:8px;' +
                    'padding-bottom:8px;border-bottom:1px solid #F1F5F9;">' +
                    f'<span style="font-size:14px;color:#94A3B8;font-weight:600;">Tipo</span>' +
                    f'<span style="font-size:14px;color:#1e293b;font-weight:700;">{tipo}</span></div>' +
                    f'<div style="display:flex;justify-content:space-between;margin-bottom:5px;">' +
                    f'<span style="font-size:14px;color:#94A3B8;">📥 0102 Ingresos</span>' +
                    f'<span style="font-size:16px;font-weight:800;color:#059669;">{ingresos}</span></div>' +
                    f'<div style="display:flex;justify-content:space-between;margin-bottom:5px;">' +
                    f'<span style="font-size:14px;color:#94A3B8;">🚨 Alertas críticas</span>' +
                    f'<span style="font-size:16px;font-weight:800;color:{cr_col};">{c["criticas"]}</span></div>' +
                    f'<div style="display:flex;justify-content:space-between;margin-bottom:10px;">' +
                    f'<span style="font-size:14px;color:#94A3B8;">⚡ A revisar</span>' +
                    f'<span style="font-size:16px;font-weight:800;color:{med_col};">{c["medias"]}</span></div>' +
                    f'<div style="background:{badge_bg};border-radius:6px;padding:5px 10px;' +
                    f'text-align:center;font-size:14px;font-weight:700;color:{txt};">' +
                    f'Base imp. est.: {base_imp}</div></div>'
                )
                st.markdown(hdr_html + body_html, unsafe_allow_html=True)
                if st.button("→ Ver expediente completo",
                             key=f"cli_{c['id']}_{fila_start}_{col_idx}",
                             use_container_width=True):
                    st.session_state.fh_cliente_sel = c["id"]
                    st.session_state.fh_menu = "cliente"
                    st.rerun()
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)



# ── PANTALLA CLIENTE ──────────────────────────────────────────────
def pantalla_cliente():
    cliente_id = st.session_state.get("fh_cliente_sel")
    cartera    = st.session_state.get("fh_cartera", [])
    cliente    = next((c for c in cartera if c["id"]==cliente_id), None)
    if not cliente: st.warning("Selecciona un cliente."); return

    df_inm  = cliente["df_inm"]
    df_mov  = cliente["df_mov"]
    modelo  = cliente["modelo100"]
    nombre  = cliente["nombre"]
    vlds    = st.session_state.get("fh_validaciones", {}).get(cliente_id, {})

    if st.button("← Volver a cartera", key="cli_back"):
        st.session_state.fh_menu = "cartera"
        st.session_state.pop("fh_cliente_sel", None)
        st.session_state.pop("fh_inmueble_sel", None)
        st.rerun()

    st.markdown(f"""<div style="margin-bottom:14px;">
      <div class="nc-page-label">Revisión IRPF 2025</div>
      <div class="nc-page-title">{nombre}</div>
      <div class="nc-page-sub">{cliente["inmuebles"]} inmuebles · Campaña IRPF 2025</div>
    </div>""", unsafe_allow_html=True)

    _cc = _color_cli(cliente_id)  # color único del cliente — se usa en border-top
    # Número semántico + border-top con color del cliente
    render_kpi_grid([
        {"label":"📥 0102 Ingresos",
         "value":fmt_eur(modelo.get("ingresos",0)),
         "color":GREEN,   "border_color":_cc, "subtitle":"Rendimiento íntegro"},
        {"label":"📤 Gastos deducibles",
         "value":f"−{fmt_eur(modelo.get('total_gastos',0))}",
         "color":RED,     "border_color":_cc, "subtitle":"Total deducible"},
        {"label":"⚖️ 0149 Rend. neto",
         "value":fmt_eur(modelo.get("rend_neto",0)),
         "color":ACCENT_F,"border_color":_cc, "subtitle":"Antes de reducción"},
        {"label":"🧾 0156 Base imp. est.",
         "value":fmt_eur(modelo.get("rend_final",0)),
         "color":AMBER,   "border_color":_cc, "subtitle":"⚠️ Orientativa"},
    ])


    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # Verificar si todos validados
    col_n = "nombre" if "nombre" in df_inm.columns else "Nombre"
    nombres_inm = [str(r.get(col_n,"")) for _,r in df_inm.iterrows()] if not df_inm.empty else []
    todos_ok = all(
        vlds.get(nm,{}).get("estado") in ("ok","vl") or
        calcular_semaforo_inmueble(df_inm[df_inm[col_n]==nm].iloc[0])["estado"] == "ok"
        for nm in nombres_inm
    ) if nombres_inm else False

    if todos_ok:
        st.markdown("""<div class="nc-callout pos" style="margin-bottom:8px;">
          <strong>✅ Todos los inmuebles revisados</strong> — listo para el resumen global y exportar.
        </div>""", unsafe_allow_html=True)
        if st.button("📊 Resumen global → Exportar", type="primary", key="cli_global"):
            st.session_state.fh_menu = "resumen_global"
            st.rerun()

    st.markdown('<div class="nc-section">Inmuebles</div>', unsafe_allow_html=True)
    if df_inm.empty:
        st.info("Sin inmuebles registrados para este cliente."); return

    # Color del cliente — mismo para todos sus inmuebles
    _cc = _color_cli(cliente_id)

    # Grid de 4 columnas — mismo patrón que cards de cliente
    MAX_COLS = 4
    inm_list = list(df_inm.iterrows())
    for fila_start in range(0, len(inm_list), MAX_COLS):
        fila_rows = inm_list[fila_start:fila_start+MAX_COLS]
        cols = st.columns(MAX_COLS)
        for col_idx, (_, row) in enumerate(fila_rows):
            idx        = fila_start + col_idx
            nombre_inm = str(row.get(col_n,""))
            sem        = calcular_semaforo_inmueble(row)
            vld        = vlds.get(nombre_inm,{})
            vld_estado = vld.get("estado","")
            vld_manual = vld.get("manual", False)

            # Métricas
            renta     = _gv(row,"renta","Renta")
            ibi       = _gv(row,"ibi_anual","IBI_Anual")
            amort     = _gv(row,"amortizacion_fiscal","Amortizacion_Fiscal")
            seguro    = _gv(row,"seguro_anual","Seguro_Anual")
            comunidad = _gv(row,"comunidad","Comunidad")*12
            gastos    = ibi+amort+seguro+comunidad
            neto      = renta*12 - gastos
            tipo_arr  = str(row.get("tipo_arrendamiento") or row.get("Tipo_Arrendamiento","Larga Duración"))
            inquilino = str(row.get("inquilino") or row.get("Inquilino","—"))[:28]

            # Estado visual
            if vld_estado in ("ok","vl"):
                est_lbl = "✓ Validado" if vld_manual else "✓ Correcto"
                est_bg  = "rgba(5,150,105,0.10)"
                est_col = "#059669"
            elif sem["estado"] in ("cr","critico"):
                n_cr    = len([p for p in sem["problemas"] if p["tipo"]=="crit"])
                est_lbl = f"⚠ {n_cr} crítico{'s' if n_cr>1 else ''}"
                est_bg  = "rgba(220,38,38,0.10)"
                est_col = "#DC2626"
            elif sem["estado"] in ("wn","advertencia"):
                n_wn    = len([p for p in sem["problemas"] if p["tipo"]=="warn"])
                est_lbl = f"◔ {n_wn} aviso{'s' if n_wn>1 else ''}"
                est_bg  = "rgba(217,119,6,0.10)"
                est_col = "#D97706"
            else:
                est_lbl = "✓ Correcto"
                est_bg  = "rgba(5,150,105,0.10)"
                est_col = "#059669"

            # Primera alerta
            alerta_txt = ""
            if sem["problemas"] and vld_estado not in ("ok","vl"):
                p0 = sem["problemas"][0]["titulo"]
                mas = f" +{len(sem['problemas'])-1} más" if len(sem["problemas"])>1 else ""
                alerta_txt = f"⚠ {p0}{mas}"
            elif vld_manual:
                alerta_txt = "✓ Validado manualmente"

            neto_col = "#059669" if neto >= 0 else "#DC2626"

            with cols[col_idx]:
                # Header con color del cliente
                hdr = (
                    f'<div style="background:{_cc};border-radius:12px 12px 0 0;' +
                    f'padding:12px 14px 10px;margin-bottom:-1px;">' +
                    f'<div style="font-size:15px;font-weight:800;color:#FFF;' +
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
                    f'{nombre_inm}</div>' +
                    f'<div style="font-size:11px;color:rgba(255,255,255,0.65);margin-top:2px;">' +
                    f'{inquilino} · {tipo_arr}</div>' +
                    f'</div>'
                )
                body = (
                    f'<div style="background:#FFF;border:2px solid #E2E8F0;' +
                    f'border-top:none;border-radius:0 0 12px 12px;' +
                    f'padding:12px 14px 10px;">' +
                    # alerta
                    (f'<div style="font-size:12px;color:{est_col};font-weight:600;' +
                     f'margin-bottom:8px;padding:4px 8px;background:{est_bg};' +
                     f'border-radius:6px;">{alerta_txt}</div>' if alerta_txt else
                     f'<div style="height:4px;"></div>') +
                    # métricas
                    f'<div style="display:flex;justify-content:space-between;margin-bottom:5px;">' +
                    f'<span style="font-size:12px;color:#94A3B8;">📈 Renta/mes</span>' +
                    f'<span style="font-size:13px;font-weight:800;color:#059669;">{fmt_eur(renta)}</span></div>' +
                    f'<div style="display:flex;justify-content:space-between;margin-bottom:5px;">' +
                    f'<span style="font-size:12px;color:#94A3B8;">📉 Gastos/año</span>' +
                    f'<span style="font-size:13px;font-weight:800;color:#DC2626;">−{fmt_eur(gastos)}</span></div>' +
                    f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">' +
                    f'<span style="font-size:12px;color:#94A3B8;">⚖️ Neto/año</span>' +
                    f'<span style="font-size:13px;font-weight:800;color:{neto_col};">{fmt_eur(neto)}</span></div>' +
                    # badge estado
                    f'<div style="background:{est_bg};border-radius:6px;padding:4px 10px;' +
                    f'text-align:center;font-size:12px;font-weight:700;color:{est_col};">' +
                    f'{est_lbl}</div></div>'
                )
                st.markdown(hdr + body, unsafe_allow_html=True)

                # Botones — Revisar y Validar
                b1, b2 = st.columns(2)
                with b1:
                    if st.button(f"🔍 Revisar",
                                 key=f"rev_{cliente_id[:8]}_{idx}",
                                 use_container_width=True):
                        st.session_state.fh_inmueble_sel = nombre_inm
                        st.session_state.fh_menu = "ficha"
                        st.rerun()
                with b2:
                    if vld_manual:
                        if st.button("↩ Desvalidar",
                                     key=f"dvl_{cliente_id[:8]}_{idx}",
                                     use_container_width=True):
                            st.session_state.fh_validaciones[cliente_id].pop(nombre_inm, None)
                            st.rerun()
                    elif vld_estado not in ("ok","vl") and sem["estado"] not in ("ok",""):
                        if st.button("✅ Validar",
                                     key=f"vld_{cliente_id[:8]}_{idx}",
                                     use_container_width=True):
                            if "fh_validaciones" not in st.session_state:
                                st.session_state.fh_validaciones = {}
                            if cliente_id not in st.session_state.fh_validaciones:
                                st.session_state.fh_validaciones[cliente_id] = {}
                            st.session_state.fh_validaciones[cliente_id][nombre_inm] = {
                                "estado":"vl","manual":True,
                                "fecha":date.today().strftime("%d/%m/%Y")}
                            st.rerun()
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── FICHA INMUEBLE ────────────────────────────────────────────────
def pantalla_ficha_inmueble():
    cliente_id  = st.session_state.get("fh_cliente_sel")
    nombre_inm  = st.session_state.get("fh_inmueble_sel","")
    cartera     = st.session_state.get("fh_cartera", [])
    cliente     = next((c for c in cartera if c["id"]==cliente_id), None)
    if not cliente or not nombre_inm: st.warning("Selecciona un inmueble."); return

    df_inm = cliente["df_inm"]
    df_mov = cliente["df_mov"]
    col_n  = "nombre" if "nombre" in df_inm.columns else "Nombre"
    rows   = df_inm[df_inm[col_n]==nombre_inm]
    if rows.empty: st.warning(f"No se encontró: {nombre_inm}"); return
    row = rows.iloc[0]

    sem    = calcular_semaforo_inmueble(row)
    modelo = calcular_modelo100_inmueble(row, df_mov)
    vlds   = st.session_state.get("fh_validaciones",{}).get(cliente_id,{})

    c_back, c_vld = st.columns([3,1])
    with c_back:
        if st.button("← Volver al cliente", key="fic_back"):
            st.session_state.fh_menu = "cliente"
            st.session_state.pop("fh_inmueble_sel", None)
            st.session_state.pop("fh_pdf_export", None)
            st.rerun()
    with c_vld:
        if vlds.get(nombre_inm,{}).get("estado") != "vl" and sem["estado"] in ("cr","wn"):
            if st.button("✅ Validar manualmente", key="fic_vld", use_container_width=True):
                if "fh_validaciones" not in st.session_state: st.session_state.fh_validaciones = {}
                if cliente_id not in st.session_state.fh_validaciones: st.session_state.fh_validaciones[cliente_id] = {}
                st.session_state.fh_validaciones[cliente_id][nombre_inm] = {
                    "estado":"vl","manual":True,"fecha":date.today().strftime("%d/%m/%Y")}
                st.rerun()

    ROOF = {"Casa":("#6B2737","#8B3547"),"Despacho":("#185FA5","#1A6FBF"),
            "Garaje":("#4A5568","#5A6580"),"Apartamento":("#B8924A","#CFA55A")}
    def _rtype(tipo,nombre):
        t=(str(tipo)+" "+str(nombre)).lower()
        if any(x in t for x in ["despacho","oficina","salon"]): return "Despacho"
        if any(x in t for x in ["casa","chalet","abarqueros"]): return "Casa"
        if any(x in t for x in ["cochera","garaje"]): return "Garaje"
        return "Apartamento"
    rt   = _rtype(row.get("tipo_arrendamiento",""),nombre_inm)
    c1,c2= ROOF[rt]
    sem_color = {"cr":"var(--cr)","wn":"var(--wn)","ok":"var(--ok)"}[sem["estado"]]
    sem_label = {"cr":"🔴 Requiere acción","wn":"🟡 Revisar","ok":"🟢 Correcto"}[sem["estado"]]

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#FFFFFF 0%,#F4F8FC 100%);border:0.5px solid rgba(74,122,181,0.2);border-radius:14px;overflow:hidden;margin-bottom:14px;box-shadow:0 2px 16px rgba(30,58,95,0.08);">
      <svg viewBox="0 0 600 52" style="display:block;width:100%;margin-bottom:-1px;" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs><linearGradient id="rh" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/>
        </linearGradient></defs>
        <rect width="600" height="52" fill="url(#rh)"/>
        <text x="300" y="32" text-anchor="middle" font-family="DM Serif Display,serif" font-size="17" fill="white" opacity="0.95">{nombre_inm}</text>
        <text x="300" y="47" text-anchor="middle" font-family="IBM Plex Sans,sans-serif" font-size="10" fill="white" opacity="0.6">{rt} · {row.get("tipo_arrendamiento") or row.get("Tipo_Arrendamiento","Larga Duración")}</text>
      </svg>
      <div style="padding:10px 16px;display:flex;align-items:center;justify-content:space-between;">
        <div>
          <span style="font-size:13px;font-weight:500;color:#1E2A3A;">{row.get("inquilino") or row.get("Inquilino","Sin inquilino")}</span>
          <span style="font-size:11px;color:#8A9BB0;margin-left:10px;">CP {row.get("cp") or row.get("CP","—")}</span>
        </div>
        <span style="font-size:12px;font-weight:500;color:{sem_color};">{sem_label}</span>
      </div>
    </div>""", unsafe_allow_html=True)

    if sem["problemas"]:
        for p in sem["problemas"]:
            cls = "cr" if p["tipo"]=="crit" else "wn"
            st.markdown(f"""<div class="callout {cls}" style="margin-bottom:6px;">
              <strong>{"🔴" if p["tipo"]=="crit" else "🟡"} {p["titulo"]}</strong><br>
              <span style="font-size:12px;">{p["desc"]}</span><br>
              <span style="font-size:11px;opacity:0.8;">→ {p["accion"]}</span>
            </div>""", unsafe_allow_html=True)

    left, right = st.columns([1, 1])
    with left:
        renta     = _gv(row,"renta","Renta")
        ibi       = _gv(row,"ibi_anual","IBI_Anual")
        amort     = _gv(row,"amortizacion_fiscal","Amortizacion_Fiscal")
        seguro    = _gv(row,"seguro_anual","Seguro_Anual")
        comunidad = _gv(row,"comunidad","Comunidad")*12
        hipoteca  = _gv(row,"intereses_hipoteca","Intereses_Hipoteca")
        gastos_jur= _gv(row,"gastos_juridicos","Gastos_Juridicos")
        suministros=_gv(row,"servicios_suministros","Servicios_Suministros")
        gastos_items = [
            ("0102","Ingresos íntegros",  renta*12,    True,  "Renta anual"),
            ("0105","Intereses hipoteca", hipoteca,    hipoteca>0,   "Préstamo vinculado"),
            ("0106","IBI y tributos",      ibi,         ibi>0,        "Recibo IBI 2024"),
            ("0107","Comunidad propiet.", comunidad,   comunidad>0,  "Cuota anual"),
            ("0109","Amortización 3%",    amort,       amort>0,      "3% s/ valor construcción"),
            ("0110","Seguro hogar+vida",  seguro,      seguro>0,     "Póliza hogar/vida"),
            ("0111","Suministros",        suministros, suministros>0,"Servicios incluidos"),
            ("0112","Gastos jurídicos",   gastos_jur,  gastos_jur>0, "Honorarios, gestión"),
        ]
        chk_html = ""
        for cas, label, amt, on, hint in gastos_items:
            box = '<div class="nc-chk-on">✓</div>' if on else '<div class="nc-chk-off">✗</div>'
            amt_str = fmt_eur(amt) if amt else "Pendiente"
            amc = "" if on else "miss"
            chk_html += f"""<div class="nc-chk-item">
              {box}<div class="chk-cas">{cas}</div>
              <div class="chk-lbl">{label}<div class="chk-hint">{hint}</div></div>
              <div class="chk-amt {amc}">{amt_str}</div>
            </div>"""
        faltan = sum(1 for _,_,a,on,_ in gastos_items[1:] if not on)
        st.markdown(f"""<div class="nc-panel">
          <div class="nc-panel-head"><span class="nc-panel-title">Gastos deducibles</span>
            <span style="font-size:11px;color:var(--txm);">{len(gastos_items)-faltan-1}/{len(gastos_items)-1} registrados</span>
          </div>{chk_html}</div>""", unsafe_allow_html=True)

    with right:
        m = modelo
        casillas = [
            ("0102","Rendimiento íntegro","Ingresos anuales",m["ingresos"],False,False),
            ("0105","Intereses hipoteca","Préstamo vinculado",-m["intereses"],False,False),
            ("0106","IBI y tributos","Recibo IBI",-m["ibi"],False,False),
            ("0107","Comunidad + Seguros","Cuota + pólizas",-m["comunidad_seguros"],False,False),
            ("0104","Reparaciones","Del diario contable",-m["reparaciones"],False,False),
            ("0109","Amortización 3%","MAX(compra,catastral)×%c×3%",-m["amortizacion"],False,False),
            ("0111","Otros deducibles","Jurídicos, suministros",-(m["gastos_juridicos"]+m["suministros"]),False,False),
            ("0149","RENDIMIENTO NETO","",m["rend_neto"],True,False),
            (f"0150",f"Reducción {m['red_pct']}% (orient.)","⚠️ Validar",-m["reduccion"],False,False),
            ("0156","BASE IMPONIBLE EST.","Orientativa",m["rend_final"],False,True),
            ("0153","Retenciones pract.","",  -m["retenciones"],False,False),
        ]
        filas_m = ""
        for cas, label, sub, val, is_sum, is_final in casillas:
            tr_cls = "final" if is_final else ("sum" if is_sum else "")
            vc = ""
            if is_final: vc = "style='color:var(--acc2);'"
            elif is_sum: vc = "style='color:var(--tx2);'"
            elif val < 0: vc = "style='color:var(--cr);'"
            elif val > 0: vc = "style='color:var(--ok);'"
            sub_html = f'<div class="l-sub">{sub}</div>' if sub else ""
            filas_m += f"""<tr class="{tr_cls}">
              <td><span class="cas">{cas}</span></td>
              <td>{label}{sub_html}</td>
              <td class="r" {vc}>{fmt_eur(val)}</td>
            </tr>"""
        st.markdown(f"""<table class="nc-m100">
          <thead><tr><th style="width:55px;">Casilla</th><th>Descripción</th><th class="r">Importe</th></tr></thead>
          <tbody>{filas_m}</tbody></table>""", unsafe_allow_html=True)

    # ── FISCALIDAD PROACTIVA ─────────────────────────────────────
    st.markdown('<div class="nc-section" style="margin-top:28px;">🔬 Laboratorio Fiscal · Decisiones Proactivas</div>',
                unsafe_allow_html=True)

    # ── Función de simulación ────────────────────────────────────
    def _simular(row, dec):
        """Recalcula Modelo 100 aplicando las decisiones del asesor."""
        ingresos    = sf(row.get("renta") or row.get("Renta",0)) * 12
        intereses   = dec.get("intereses", sf(row.get("intereses_hipoteca",0)))
        ibi         = dec.get("ibi",       sf(row.get("ibi_anual",0)))
        com_seg     = sf(row.get("comunidad",0))*12 + sf(row.get("seguro_anual",0))
        suministros = sf(row.get("suministros_anual",0))
        jur         = sf(row.get("gastos_juridicos_anual",0))
        # Reparaciones: el asesor decide qué parte va como gasto directo
        rep_total   = sf(row.get("reparaciones_anual",0))
        rep_gasto   = dec.get("rep_como_gasto",  rep_total)  # deducible 100% hoy
        rep_mejora  = dec.get("rep_como_mejora", 0)          # amortizable 5%/año
        amort_mejora= rep_mejora * 0.05
        # Amortización 3% construcción — el asesor puede calcularla aquí
        amort_3pct  = dec.get("amortizacion_3pct",
                              sf(row.get("amortizacion_fiscal",0)))
        # Mobiliario 10% anual
        amort_mob   = dec.get("amortizacion_mobiliario", 0)
        # Gastos de formalización (notaría, registro) → amortizables
        gastos_form = dec.get("gastos_formalizacion", 0) / 10  # 10 años
        # Total
        total_gastos = (intereses + ibi + com_seg + suministros + jur +
                        rep_gasto + amort_3pct + amort_mob + amort_mejora + gastos_form)
        rend_neto = ingresos - total_gastos
        # Reducción
        red_pct = dec.get("reduccion_pct", m.get("red_pct", 50))
        reduccion = rend_neto * red_pct / 100 if rend_neto > 0 else 0
        rend_final = rend_neto - reduccion
        return {
            "ingresos": round(ingresos,2),
            "total_gastos": round(total_gastos,2),
            "rend_neto": round(rend_neto,2),
            "reduccion": round(reduccion,2),
            "red_pct": red_pct,
            "rend_final": round(rend_final,2),
        }

    # ── Estado de decisiones en session_state ────────────────────
    dec_key = f"dec_{cliente_id[:8]}_{nombre_inm[:10]}"
    if dec_key not in st.session_state:
        st.session_state[dec_key] = {}

    dec = st.session_state[dec_key]

    # ── KPI IMPACTO: Antes vs. Después ───────────────────────────
    m_sim      = _simular(row, dec)
    base_orig  = m.get("rend_final", 0)
    base_sim   = m_sim["rend_final"]
    ahorro     = base_orig - base_sim
    ahorro_pct = round(ahorro / base_orig * 100, 1) if base_orig else 0
    col_imp    = st.columns(4)

    for _col, _lbl, _val2, _color2, _border2 in [
        (col_imp[0], "📊 Base original",  fmt_eur(base_orig), "#475569",              "#94A3B8"),
        (col_imp[1], "🔬 Base simulada",  fmt_eur(base_sim),  _color_cli(cliente_id), _color_cli(cliente_id)),
        (col_imp[2], "💶 Ahorro est.",    fmt_eur(ahorro),
         "#059669" if ahorro>0 else "#DC2626",
         "#059669" if ahorro>0 else "#DC2626"),
        (col_imp[3], "📉 Reducción",      f"{ahorro_pct}%",
         "#059669" if ahorro_pct>0 else "#475569",
         "#059669" if ahorro_pct>0 else "#94A3B8"),
    ]:
        _col.markdown(
            f'<div style="background:#FFF;border-radius:10px;padding:14px 16px;'
            f'border:2px solid #94A3B8;border-top:4px solid {_border2};'
            f'box-shadow:0 4px 12px rgba(0,0,0,0.08);">'
            f'<div style="font-size:10px;font-weight:800;color:#94A3B8;'
            f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">{_lbl}</div>'
            f'<div style="font-size:1.6rem;font-weight:900;color:{_color2};line-height:1;">{_val2}</div>'
            f'</div>',
            unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── PALANCAS FISCALES + IA (dos columnas) ────────────────────
    col_dec, col_ia = st.columns([5, 5])

    with col_dec:
        st.markdown("""<div style="font-size:13px;font-weight:700;color:#1e293b;
            border-left:3px solid #534AB7;padding-left:10px;margin-bottom:14px;">
            ⚙️ Palancas Fiscales</div>""", unsafe_allow_html=True)

        # 1. Reparación vs. Mejora
        rep_total_v = sf(row.get("reparaciones_anual", 0))
        if rep_total_v > 600:
            st.markdown(f"**🔧 Reparaciones ({fmt_eur(rep_total_v)}) — ¿Gasto o Mejora?**")
            rep_pct = st.slider("% como gasto directo (resto → amortización 5%/año)",
                                0, 100, dec.get("rep_pct_gasto", 100),
                                key=f"sl_rep_{dec_key}")
            dec["rep_como_gasto"]  = rep_total_v * rep_pct / 100
            dec["rep_como_mejora"] = rep_total_v * (100 - rep_pct) / 100
            dec["rep_pct_gasto"]   = rep_pct
            if rep_pct < 100:
                st.caption(f"→ {fmt_eur(dec['rep_como_gasto'])} gasto hoy · "
                           f"{fmt_eur(dec['rep_como_mejora'])} amortizable "
                           f"({fmt_eur(dec['rep_como_mejora']*0.05)}/año × 20 años)")

        # 2. Amortización 3% construcción
        st.markdown("**🏗️ Amortización 3% construcción (casilla 0109)**")
        precio_c   = sf(row.get("precio_compra",0))
        catastral  = sf(row.get("valor_catastral",0))
        pct_const  = sf(row.get("porcentaje_construccion", 0.7))
        amort_calc = max(precio_c, catastral) * pct_const * 0.03
        amort_actual = sf(row.get("amortizacion_fiscal",0))
        usar_calc = st.checkbox(
            f"Usar cálculo automático ({fmt_eur(amort_calc)}/año)",
            value=dec.get("usar_amort_calc", amort_actual == 0),
            key=f"ck_amort_{dec_key}")
        if usar_calc:
            dec["amortizacion_3pct"] = amort_calc
            dec["usar_amort_calc"]   = True
            st.caption(f"→ MAX({fmt_eur(precio_c)}, {fmt_eur(catastral)}) × {pct_const*100:.0f}% × 3% = {fmt_eur(amort_calc)}")
        else:
            dec["amortizacion_3pct"] = amort_actual
            dec["usar_amort_calc"]   = False

        # 3. Mobiliario 10%/año
        st.markdown("**🛋️ Amortización mobiliario (10%/año)**")
        mob_val = st.number_input("Valor mobiliario en el inmueble (€)",
                                   min_value=0.0, value=float(dec.get("mob_val",0)),
                                   step=500.0, key=f"ni_mob_{dec_key}")
        dec["mob_val"] = mob_val
        dec["amortizacion_mobiliario"] = mob_val * 0.10
        if mob_val > 0:
            st.caption(f"→ {fmt_eur(mob_val * 0.10)}/año deducible")

        # 4. Gastos de formalización
        st.markdown("**📝 Gastos de formalización (notaría, registro)**")
        form_val = st.number_input("Gastos de formalización en su día (€)",
                                    min_value=0.0, value=float(dec.get("form_val",0)),
                                    step=200.0, key=f"ni_form_{dec_key}")
        dec["form_val"] = form_val
        dec["gastos_formalizacion"] = form_val
        if form_val > 0:
            st.caption(f"→ {fmt_eur(form_val/10)}/año deducible durante 10 años")

        # 5. Reducción (60% vs 50%)
        st.markdown("**📋 Reducción por arrendamiento habitual**")
        red_actual = m.get("red_pct", 50)
        red_elegida = st.radio(
            "Porcentaje de reducción:",
            [50, 60],
            index=0 if dec.get("reduccion_pct", red_actual) == 50 else 1,
            horizontal=True,
            key=f"rd_red_{dec_key}",
            help="60% si contrato antes de mayo 2023 (Art. 23.2 LIRPF). 50% en adelante.")
        dec["reduccion_pct"] = red_elegida
        if red_elegida == 60 and red_actual == 50:
            st.caption("⚠️ Verificar fecha contrato antes de aplicar 60%")

        # Botón reset
        if st.button("↺ Restablecer decisiones", key=f"rst_{dec_key}"):
            st.session_state.pop(dec_key, None)
            st.rerun()

        st.session_state[dec_key] = dec

    # ── ANÁLISIS PROACTIVO ────────────────────────────────────────
    with col_ia:
        st.markdown("""<div style="font-size:13px;font-weight:700;color:#1e293b;
            border-left:3px solid #534AB7;padding-left:10px;margin-bottom:14px;">
            ⚡ Análisis Proactivo</div>""", unsafe_allow_html=True)

        # ── Datos base para proyección ────────────────────────────
        from datetime import date
        hoy        = date.today()
        mes_actual = hoy.month
        dias_año   = 366 if hoy.year % 4 == 0 else 365
        dia_año    = hoy.timetuple().tm_yday
        pct_año    = dia_año / dias_año
        meses_rest = 12 - mes_actual

        renta_mes  = sf(row.get("renta") or row.get("Renta", 0))
        ing_anual  = renta_mes * 12
        ing_acum   = renta_mes * mes_actual       # acumulado estimado a hoy
        ing_proy   = renta_mes * 12               # proyección a 31/12

        # Cuota estimada IRPF (tipo marginal medio propietario Granada ~30%)
        TIPO_MARGINAL = 0.30
        def _cuota(base): return max(base * TIPO_MARGINAL, 0)

        cuota_actual = _cuota(base_orig)
        cuota_sim    = _cuota(base_sim)
        cuota_ahorro = cuota_actual - cuota_sim

        # ── KPIs proyección anual ─────────────────────────────────
        st.markdown(f"""
        <div style="background:#F8F9FA;border-radius:10px;padding:14px 16px;
                    border:1px solid #E2E8F0;margin-bottom:12px;">
            <div style="font-size:10px;font-weight:800;color:#94A3B8;
                        text-transform:uppercase;letter-spacing:0.08em;
                        margin-bottom:10px;">
                📅 Proyección a 31 de diciembre
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <div>
                    <div style="font-size:10px;color:#94A3B8;margin-bottom:2px;">
                        Ingresos acumulados</div>
                    <div style="font-size:16px;font-weight:800;color:#059669;">
                        {fmt_eur(ing_acum)}</div>
                    <div style="font-size:10px;color:#94A3B8;">
                        hasta {hoy.strftime('%d/%m/%Y')}</div>
                </div>
                <div>
                    <div style="font-size:10px;color:#94A3B8;margin-bottom:2px;">
                        Proyección anual</div>
                    <div style="font-size:16px;font-weight:800;color:#1e293b;">
                        {fmt_eur(ing_proy)}</div>
                    <div style="font-size:10px;color:#94A3B8;">
                        al ritmo actual</div>
                </div>
                <div>
                    <div style="font-size:10px;color:#94A3B8;margin-bottom:2px;">
                        Cuota IRPF estimada</div>
                    <div style="font-size:16px;font-weight:800;color:#DC2626;">
                        {fmt_eur(cuota_actual)}</div>
                    <div style="font-size:10px;color:#94A3B8;">
                        sin optimizar (~30%)</div>
                </div>
                <div>
                    <div style="font-size:10px;color:#94A3B8;margin-bottom:2px;">
                        Cuota con decisiones</div>
                    <div style="font-size:16px;font-weight:800;
                                color:{'#059669' if cuota_sim < cuota_actual else '#DC2626'};">
                        {fmt_eur(cuota_sim)}</div>
                    <div style="font-size:10px;color:#94A3B8;">
                        ahorro: {fmt_eur(cuota_ahorro)}</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        # ── Simulador: ¿qué pasa si invierto X antes de diciembre? ─
        st.markdown("""<div style="font-size:12px;font-weight:700;color:#1e293b;
            margin-bottom:8px;">💡 Simulador de inversión proactiva</div>""",
            unsafe_allow_html=True)

        inversion = st.number_input(
            "Si invierto antes del 31/12 (€):",
            min_value=0.0, max_value=50000.0,
            value=float(dec.get("inversion_proactiva", 0)),
            step=500.0, key=f"inv_prot_{dec_key}")
        dec["inversion_proactiva"] = inversion

        tipo_inv = st.radio(
            "Esta inversión es:",
            ["Reparación (deducible 100% este año)",
             "Mejora (amortizable 5%/año × 20 años)"],
            key=f"tipo_inv_{dec_key}", horizontal=False)

        if inversion > 0:
            if "Reparación" in tipo_inv:
                deduccion_inv = inversion          # 100% este año
                etiqueta_inv  = "deducción directa"
            else:
                deduccion_inv = inversion * 0.05   # 5% × 20 años
                etiqueta_inv  = f"{fmt_eur(inversion*0.05)}/año × 20 años"

            base_con_inv  = max(base_sim - deduccion_inv, 0)
            cuota_con_inv = _cuota(base_con_inv)
            ahorro_inv    = cuota_sim - cuota_con_inv
            roi_inv       = (ahorro_inv / inversion * 100) if inversion > 0 else 0

            # Subida de alquiler para compensar la inversión
            meses_recup   = inversion / renta_mes if renta_mes > 0 else 0
            subida_nec    = (inversion / 12 / 120) * 100  # % subida para recuperar en 10 años

            st.markdown(f"""
            <div style="background:#EEEDFE;border-radius:10px;padding:14px 16px;
                        border:1px solid #534AB7;margin-top:8px;">
                <div style="font-size:10px;font-weight:800;color:#534AB7;
                            text-transform:uppercase;letter-spacing:0.08em;
                            margin-bottom:8px;">
                    📊 Impacto de la inversión
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                    <div>
                        <div style="font-size:10px;color:#534AB7;">Deducción aplicada</div>
                        <div style="font-size:15px;font-weight:800;color:#534AB7;">
                            {fmt_eur(deduccion_inv)}</div>
                        <div style="font-size:10px;color:#64748B;">{etiqueta_inv}</div>
                    </div>
                    <div>
                        <div style="font-size:10px;color:#534AB7;">Nueva base imponible</div>
                        <div style="font-size:15px;font-weight:800;color:#1e293b;">
                            {fmt_eur(base_con_inv)}</div>
                    </div>
                    <div>
                        <div style="font-size:10px;color:#534AB7;">Ahorro fiscal</div>
                        <div style="font-size:15px;font-weight:800;color:#059669;">
                            {fmt_eur(ahorro_inv)}</div>
                        <div style="font-size:10px;color:#64748B;">
                            ROI fiscal: {roi_inv:.1f}%</div>
                    </div>
                    <div>
                        <div style="font-size:10px;color:#534AB7;">Subida alquiler necesaria</div>
                        <div style="font-size:15px;font-weight:800;color:#D97706;">
                            +{subida_nec:.1f}%</div>
                        <div style="font-size:10px;color:#64748B;">
                            para recuperar en 10 años</div>
                    </div>
                </div>
                <div style="margin-top:10px;padding-top:10px;
                            border-top:1px solid rgba(83,74,183,0.2);
                            font-size:11px;color:#534AB7;font-weight:600;">
                    {'✅ Inversión fiscalmente eficiente — el ahorro compensa el desembolso en ' + f'{meses_recup:.0f} meses' if roi_inv > 20 else '⚠️ Valorar si el ahorro fiscal justifica la inversión — ROI bajo'}
                </div>
            </div>""", unsafe_allow_html=True)

        # ── Botón análisis IA ─────────────────────────────────────
        analisis_key = f"analisis_ia_{dec_key}_{hash(str(dec))}_{int(inversion)}"
        if analisis_key not in st.session_state:
            st.session_state[analisis_key] = None

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if st.button("🔬 Generar análisis fiscal",
                     key=f"btn_analisis_{dec_key}",
                     use_container_width=True, type="primary"):
            # Construir prompt con todos los datos reales
            amort_correcta = (max(sf(row.get("precio_compra",0)),
                                  sf(row.get("valor_catastral",0))) *
                              sf(row.get("porcentaje_construccion",0.7)) * 0.03)
            prompt = (
                f"Inmueble: {nombre_inm} | "
                f"Tipo: {row.get('tipo_arrendamiento','Larga Duración')} | "
                f"Renta: {fmt_eur(renta_mes)}/mes\n"
                f"Ingresos anuales: {fmt_eur(ing_proy)} | "
                f"Meses restantes año: {meses_rest}\n\n"
                f"MODELO 100 ACTUAL:\n"
                f"  Gastos declarados: {fmt_eur(m.get('total_gastos',0))} | "
                f"  Base imponible: {fmt_eur(base_orig)} | "
                f"  Cuota estimada: {fmt_eur(cuota_actual)}\n\n"
                f"DECISIONES ACTIVAS DEL ASESOR:\n"
                f"  Amortización 3%: {fmt_eur(dec.get('amortizacion_3pct',0))} "
                f"(correcta sería {fmt_eur(amort_correcta)})\n"
                f"  Reparación como gasto: {fmt_eur(dec.get('rep_como_gasto',0))} | "
                f"  Como mejora: {fmt_eur(dec.get('rep_como_mejora',0))}\n"
                f"  Mobiliario: {fmt_eur(dec.get('amortizacion_mobiliario',0))} | "
                f"  Formalización: {fmt_eur(dec.get('gastos_formalizacion',0)/10)}/año\n"
                f"  Reducción: {dec.get('reduccion_pct',50)}%\n\n"
                f"CON DECISIONES APLICADAS:\n"
                f"  Base simulada: {fmt_eur(base_sim)} | "
                f"  Cuota simulada: {fmt_eur(cuota_sim)} | "
                f"  Ahorro: {fmt_eur(cuota_ahorro)}\n\n"
                + (f"INVERSIÓN PROACTIVA PLANTEADA: {fmt_eur(inversion)} "
                   f"({'Reparación' if 'Reparación' in tipo_inv else 'Mejora'})\n"
                   f"  Deducción: {fmt_eur(deduccion_inv)} | "
                   f"  Nueva base: {fmt_eur(base_con_inv)} | "
                   f"  Ahorro adicional: {fmt_eur(ahorro_inv)} | "
                   f"  ROI fiscal: {roi_inv:.1f}%\n" if inversion > 0 else "") +
                f"\nALERTAS DETECTADAS: "
                f"{'; '.join([p.get('titulo','') for p in calcular_semaforo_inmueble(row).get('problemas',[])])}\n\n"
                f"Dame en 4 frases: (1) valoración de las decisiones activas, "
                f"(2) si la inversión proactiva es fiscalmente óptima o hay alternativa mejor, "
                f"(3) riesgo ante inspección, (4) acción concreta antes del 31/12."
            )
            from sabio_fiscal import _llamar_claude, SYSTEM_PROMPTS
            system = (
                "Eres el Asesor Fiscal IA de FiscalHub. Hablas a un asesor fiscal profesional. "
                "Analiza la situación fiscal de este inmueble concreto con los datos reales proporcionados. "
                "Tono profesional entre colegas. Máximo 4 frases. Con euros reales. "
                "Distingue lo seguro de lo que tiene riesgo ante inspección."
            )
            with st.spinner("Analizando situación fiscal..."):
                resultado = _llamar_claude(system, prompt, max_tokens=400)
            st.session_state[analisis_key] = resultado

        # Mostrar resultado del análisis
        if st.session_state.get(analisis_key):
            st.markdown(f"""
            <div style="background:#F0EEFF;border-radius:10px;
                        padding:14px 16px;margin-top:8px;
                        border-left:4px solid #534AB7;
                        font-size:13px;color:#1e293b;line-height:1.7;">
                {st.session_state[analisis_key]}
            </div>""", unsafe_allow_html=True)
            if st.button("↺ Regenerar", key=f"regen_{dec_key}",
                         use_container_width=False):
                st.session_state.pop(analisis_key, None)
                st.rerun()

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    # ── BOTONES FINALES ──────────────────────────────────────────
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    e1,e2,_ = st.columns([1,1,2])
    with e1:
        gen_pdf = st.button("📄 Generar PDF", key="fic_pdf", use_container_width=True, type="primary")
        if gen_pdf or "fh_pdf_export" in st.session_state:
            if gen_pdf:
                try:
                    import reportlab
                    from fiscal_export import generar_pdf_global
                    fila = _build_fila_export(row, df_mov, modelo)
                    pdf  = generar_pdf_global([fila], _build_totales_export([fila]),
                        nombre_propietario=cliente["nombre"],
                        nombre_asesoria=st.session_state.get("fh_asesor",{}).get("despacho",""),
                        año_fiscal=2025)
                    st.session_state["fh_pdf_export"] = pdf.getvalue() if pdf else _pdf_simple(nombre_inm, cliente["nombre"], modelo)
                except:
                    st.session_state["fh_pdf_export"] = _pdf_simple(nombre_inm, cliente["nombre"], modelo)
            if "fh_pdf_export" in st.session_state:
                st.download_button("⬇️ Descargar PDF", data=st.session_state["fh_pdf_export"],
                    file_name=f"IRPF_{nombre_inm[:20].replace(' ','_')}_2025.pdf",
                    mime="application/pdf", use_container_width=True, key="fic_pdf_dl")
    with e2:
        if st.button("✅ Marcar revisado", key="fic_ok", use_container_width=True):
            if "fh_validaciones" not in st.session_state: st.session_state.fh_validaciones = {}
            if cliente_id not in st.session_state.fh_validaciones: st.session_state.fh_validaciones[cliente_id] = {}
            st.session_state.fh_validaciones[cliente_id][nombre_inm] = {
                "estado":"ok","manual":False,"fecha":date.today().strftime("%d/%m/%Y")}
            st.session_state.fh_menu = "cliente"
            st.session_state.pop("fh_inmueble_sel", None)
            st.session_state.pop("fh_pdf_export", None)
            st.rerun()

def _pdf_simple(nombre_inm, nombre_cliente, modelo):
    from reportlab.pdfgen import canvas as rlc
    from reportlab.lib.pagesizes import A4
    buf = io.BytesIO()
    c = rlc.Canvas(buf, pagesize=A4); w,h = A4
    c.setFont("Helvetica-Bold",14); c.drawString(50,h-60,f"FiscalHub — IRPF 2025 · {nombre_cliente}")
    c.setFont("Helvetica-Bold",12); c.drawString(50,h-90,f"Inmueble: {nombre_inm}")
    c.setFont("Helvetica",11); y = h-130
    for lbl,val in [("0102 Ingresos:",fmt_eur(modelo.get("ingresos",0))),
                    ("0149 Rend. neto:",fmt_eur(modelo.get("rend_neto",0))),
                    (f"0150 Reducción {modelo.get('red_pct',50)}%:",fmt_eur(-modelo.get("reduccion",0))),
                    ("0156 Base imp. est.:",fmt_eur(modelo.get("rend_final",0))),
                    ("0153 Retenciones:",fmt_eur(-modelo.get("retenciones",0)))]:
        c.drawString(50,y,f"{lbl}  {val}"); y-=22
    c.setFont("Helvetica-Oblique",9)
    c.drawString(50,50,"Documento informativo — validar con asesor fiscal")
    c.save(); buf.seek(0)
    return buf.getvalue()

def _build_fila_export(row, df_mov, modelo):
    return {
        "inmueble": str(row.get("nombre") or row.get("Nombre","")),
        "ref_catastral": str(row.get("ref_catastral") or "N/A"),
        "tipo": str(row.get("tipo_arrendamiento") or "Larga Duración"),
        "inquilino": str(row.get("inquilino") or ""),
        "nif_inquilino": str(row.get("nif_inquilino") or ""),
        "dias": modelo.get("dias",365),
        "ingresos": modelo["ingresos"],"intereses": modelo["intereses"],
        "reparaciones": modelo["reparaciones"],"ibi": modelo["ibi"],
        "comunidad_seguros": modelo["comunidad_seguros"],"suministros": modelo["suministros"],
        "gastos_juridicos": modelo["gastos_juridicos"],"amortizacion": modelo["amortizacion"],
        "amort_detalle":"","total_gastos": modelo["total_gastos"],
        "rend_neto": modelo["rend_neto"],"reduccion_pct": modelo["red_pct"],
        "reduccion_imp": modelo["reduccion"],"rend_final": modelo["rend_final"],
        "retenciones": modelo["retenciones"],"nota_reduccion":"Orientativa","ahorro_potencial":0,
    }

def _build_totales_export(filas):
    keys=["ingresos","intereses","reparaciones","ibi","comunidad_seguros","suministros",
          "gastos_juridicos","amortizacion","total_gastos","rend_neto","reduccion_imp","rend_final","retenciones"]
    t={k:sum(f.get(k,0) for f in filas) for k in keys}
    t.update({"n_inmuebles":len(filas),"año_fiscal":2025})
    return t

# ── RESUMEN GLOBAL ────────────────────────────────────────────────
def pantalla_resumen_global():
    cliente_id = st.session_state.get("fh_cliente_sel")
    cartera    = st.session_state.get("fh_cartera", [])
    cliente    = next((c for c in cartera if c["id"]==cliente_id), None)
    if not cliente: st.warning("Selecciona un cliente."); return

    df_inm = cliente["df_inm"]; df_mov = cliente["df_mov"]; nombre = cliente["nombre"]
    vlds   = st.session_state.get("fh_validaciones",{}).get(cliente_id,{})
    modelo = calcular_modelo100_global(df_inm, df_mov)
    col_n  = "nombre" if "nombre" in df_inm.columns else "Nombre"
    nombres= [str(r.get(col_n,"")) for _,r in df_inm.iterrows()] if not df_inm.empty else []
    n_manual = sum(1 for nm in nombres if vlds.get(nm,{}).get("manual",False))

    if st.button("← Volver al cliente", key="gl_back"):
        st.session_state.fh_menu = "cliente"; st.rerun()

    st.markdown(f"""<div style="margin-bottom:14px;">
      <div class="nc-page-label">Resumen global IRPF 2025</div>
      <div class="nc-page-title">{nombre}</div>
      <div class="nc-page-sub">{len(nombres)} inmuebles · Modelo 100 consolidado</div>
    </div>""", unsafe_allow_html=True)

    if n_manual > 0:
        st.markdown(f"""<div class="nc-callout warn">
          <strong>⚠️ {n_manual} inmueble{"s" if n_manual>1 else ""} con validación manual</strong> —
          Verificar antes de presentar a la AEAT.
        </div>""", unsafe_allow_html=True)

    _cc_gl = _color_cli(cliente_id)
    render_kpi_grid([
        {"label":"📥 0102 Ingresos",
         "value":fmt_eur(modelo.get("ingresos",0)),
         "color":GREEN,    "border_color":_cc_gl, "subtitle":f"{len(nombres)} inmuebles"},
        {"label":"📤 Gastos deducibles",
         "value":f"−{fmt_eur(modelo.get('total_gastos',0))}",
         "color":RED,      "border_color":_cc_gl, "subtitle":"Total deducible"},
        {"label":"⚖️ 0149 Rend. neto",
         "value":fmt_eur(modelo.get("rend_neto",0)),
         "color":ACCENT_F, "border_color":_cc_gl, "subtitle":"Antes de reducción"},
        {"label":"🧾 0156 Base imp.",
         "value":fmt_eur(modelo.get("rend_final",0)),
         "color":AMBER,    "border_color":_cc_gl, "subtitle":"⚠️ Orientativa"},
    ])

    st.markdown('<div class="nc-section">Desglose por inmueble</div>', unsafe_allow_html=True)
    if not df_inm.empty:
        cards_html = '<div class="nc-alert-grid">'
        for _,row in df_inm.iterrows():
            nm     = str(row.get(col_n,""))
            m      = calcular_modelo100_inmueble(row, df_mov)
            manual = vlds.get(nm,{}).get("manual",False)
            tipo   = str(row.get("tipo_arrendamiento") or row.get("Tipo_Arrendamiento","Larga Duración"))
            inq    = str(row.get("inquilino") or row.get("Inquilino","—"))
            roof_cls  = "manual" if manual else ""
            badge_html = f'<span class="global-card-badge manual">✎ Manual</span>' if manual else \
                         f'<span class="global-card-badge">✓ Automático</span>'
            cards_html += f"""
            <div class="nc-card">
              <div class="global-card-roof {roof_cls}"></div>
              <div class="nc-card">
                <div class="nc-title">{nm}</div>
                <div class="nc-subtitle">{inq[:20]} · {tipo}</div>
                <div class="global-card-metrics">
                  <div class="global-metric">
                    <div class="global-metric-lbl">0102 Ingresos</div>
                    <div class="global-metric-val ok">{fmt_eur(m["ingresos"])}</div>
                  </div>
                  <div class="global-metric">
                    <div class="global-metric-lbl">Gastos totales</div>
                    <div class="global-metric-val cr">−{fmt_eur(m["total_gastos"])}</div>
                  </div>
                  <div class="global-metric">
                    <div class="global-metric-lbl">0149 Rend. neto</div>
                    <div class="global-metric-val tx">{fmt_eur(m["rend_neto"])}</div>
                  </div>
                  <div class="global-metric">
                    <div class="global-metric-lbl">Reducción {m["red_pct"]}%</div>
                    <div class="global-metric-val tx">−{fmt_eur(m["reduccion"])}</div>
                  </div>
                </div>
                <div class="global-card-footer">
                  <div>
                    <div class="global-card-base-lbl">0156 Base imp. estimada</div>
                    <div class="global-card-base-val">{fmt_eur(m["rend_final"])}</div>
                  </div>
                  {badge_html}
                </div>
              </div>
            </div>"""
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    asesor = st.session_state.get("fh_asesor",{})
    nombre_asesor = asesor.get("despacho", asesor.get("nombre",""))
    e1,e2 = st.columns(2)
    with e1:
        if st.button("📄 Exportar PDF completo", type="primary", use_container_width=True, key="gl_pdf"):
            try:
                import reportlab; from fiscal_export import generar_pdf_global
                filas = [_build_fila_export(row,df_mov,calcular_modelo100_inmueble(row,df_mov)) for _,row in df_inm.iterrows()]
                totales = _build_totales_export(filas)
                pdf = generar_pdf_global(filas,totales,nombre_propietario=nombre,nombre_asesoria=nombre_asesor,año_fiscal=2025)
                st.session_state["fh_gl_pdf"] = pdf.getvalue() if pdf else _pdf_simple(f"Global ({len(nombres)} inm.)",nombre,modelo)
            except: st.session_state["fh_gl_pdf"] = _pdf_simple(f"Global ({len(nombres)} inm.)",nombre,modelo)
        if "fh_gl_pdf" in st.session_state:
            st.download_button("⬇️ Descargar PDF",data=st.session_state["fh_gl_pdf"],
                file_name=f"IRPF_{nombre.replace(' ','_')}_2025_global.pdf",
                mime="application/pdf",use_container_width=True,key="gl_pdf_dl")
    with e2:
        if st.button("📊 Exportar Excel", use_container_width=True, key="gl_xlsx"):
            try:
                from fiscal_export import generar_excel_asesor
                filas = [_build_fila_export(row,df_mov,calcular_modelo100_inmueble(row,df_mov)) for _,row in df_inm.iterrows()]
                xlsx = generar_excel_asesor(_build_totales_export(filas),_build_totales_export(filas),
                    nombre_propietario=nombre,nombre_asesoria=nombre_asesor,año_fiscal=2025)
                if xlsx: st.session_state["fh_gl_xlsx"] = xlsx.getvalue()
            except Exception as e: st.error(f"Error Excel: {e}")
        if "fh_gl_xlsx" in st.session_state:
            st.download_button("⬇️ Descargar Excel",data=st.session_state["fh_gl_xlsx"],
                file_name=f"IRPF_{nombre.replace(' ','_')}_2025.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,key="gl_xlsx_dl")

# ── ALERTAS ───────────────────────────────────────────────────────
def pantalla_alertas():
    cartera = st.session_state.get("fh_cartera", [])
    todas = []
    for c in cartera:
        for a in c.get("alertas",[]):
            todas.append({**a, "cliente_nombre": c["nombre"], "cliente_id": c["id"]})
    todas.sort(key=lambda x:(0 if x["tipo"]=="crit" else 1))
    n_cr = len([a for a in todas if a["tipo"]=="crit"])
    n_wn = len([a for a in todas if a["tipo"]=="warn"])

    st.markdown(f"""<div style="margin-bottom:16px;">
      <div class="nc-page-label">Cartera completa · por urgencia</div>
      <div class="nc-page-title">Alertas fiscales</div>
      <div class="nc-page-sub">{len(todas)} alertas · {n_cr} críticas · {n_wn} a revisar</div>
    </div>""", unsafe_allow_html=True)

    imp = sum(a.get("impacto",0) for a in todas if a.get("impacto",0)>0)
    render_kpi_row([
        {"label":"🚨 Críticas",   "value":str(n_cr),
         "color":RED,    "subtitle":"Antes del 30 jun"},
        {"label":"⚡ A revisar",  "value":str(n_wn),
         "color":AMBER,  "subtitle":"Esta semana"},
        {"label":"💶 Impacto",    "value":fmt_eur(imp),
         "color":ACCENT_F, "subtitle":"Recuperable"},
    ])

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    if not todas: st.success("✅ Sin alertas activas."); return

    # Separar críticas y medias
    criticas = [a for a in todas if a["tipo"] == "crit"]
    medias   = [a for a in todas if a["tipo"] == "warn"]

    def _render_alertas_grid(lista, seccion_key):
        """Cards de alerta con patrón header coloreado + body + botón clicable."""
        MAX_COLS = 4
        for fila_start in range(0, len(lista), MAX_COLS):
            fila_rows = lista[fila_start:fila_start+MAX_COLS]
            cols = st.columns(MAX_COLS)
            for col_idx, a in enumerate(fila_rows):
                es_crit = a["tipo"] == "crit"
                tipo_lbl = "⚠️ Crítica" if es_crit else "◔ Revisar"
                # Color header: color del cliente (determinista)
                cli_id  = a.get("cliente_id", a.get("cliente_nombre",""))
                hdr_col = _color_cli(cli_id)
                # Badge color por tipo
                badge_bg = "rgba(220,38,38,0.12)" if es_crit else "rgba(217,119,6,0.12)"
                badge_col= "#DC2626" if es_crit else "#D97706"
                nm      = _e(a.get("cliente_nombre",""))
                inm     = _e(a.get("inmueble","")[:40])
                titulo  = _e(a.get("titulo",""))
                desc    = _e(a.get("desc","")[:120])
                accion  = _e(a.get("accion","")[:80])

                with cols[col_idx]:
                    html = (
                        f'<div style="background:{hdr_col};border-radius:12px 12px 0 0;'
                        f'padding:12px 14px 10px;margin-bottom:-1px;">'
                        f'<div style="font-size:11px;color:rgba(255,255,255,0.65);'
                        f'font-weight:600;letter-spacing:0.05em;margin-bottom:3px;">'
                        f'{tipo_lbl}</div>'
                        f'<div style="font-size:15px;font-weight:800;color:#FFF;'
                        f'line-height:1.2;">{nm}</div>'
                        f'<div style="font-size:11px;color:rgba(255,255,255,0.65);'
                        f'margin-top:2px;">📍 {inm}</div>'
                        f'</div>'
                        f'<div style="background:#FFF;border:2px solid #E2E8F0;'
                        f'border-top:none;border-radius:0 0 12px 12px;'
                        f'padding:12px 14px 10px;">'
                        f'<div style="font-size:14px;font-weight:700;color:#1e293b;'
                        f'margin-bottom:4px;">{titulo}</div>'
                        f'<div style="font-size:12px;color:#64748B;margin-bottom:8px;'
                        f'line-height:1.4;">{desc}</div>'
                        f'<div style="background:{badge_bg};border-radius:6px;'
                        f'padding:5px 10px;font-size:11px;font-weight:700;'
                        f'color:{badge_col};">→ {accion}</div>'
                        f'</div>'
                    )
                    st.markdown(html, unsafe_allow_html=True)
                    # Botón clicable — navega al cliente
                    cli_obj = next((c for c in cartera
                                    if c["nombre"]==a.get("cliente_nombre","")), None)
                    if st.button("🔍 Ir al cliente",
                                 key=f"alt_{seccion_key}_{fila_start}_{col_idx}",
                                 use_container_width=True):
                        if cli_obj:
                            st.session_state.fh_cliente_sel = cli_obj["id"]
                            st.session_state.fh_menu = "cliente"
                            st.rerun()
                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    if criticas:
        st.markdown('<div class="nc-section">🔴 Críticas — acción urgente</div>',
                    unsafe_allow_html=True)
        _render_alertas_grid(criticas, "cr")

    if medias:
        st.markdown('<div class="nc-section" style="margin-top:20px;">🟡 A revisar esta semana</div>',
                    unsafe_allow_html=True)
        _render_alertas_grid(medias, "wn")

# ── EXPORTAR ──────────────────────────────────────────────────────
def pantalla_exportar():
    cartera = st.session_state.get("fh_cartera",[])
    st.markdown("""<div style="margin-bottom:20px;">
      <div class="nc-page-label">Generación de entregables</div>
      <div class="nc-page-title">Exportar documentos</div>
      <div class="nc-page-sub">Revisa y exporta el modelo 100 de cada cliente.</div>
    </div>""", unsafe_allow_html=True)

    if not cartera:
        st.info("Sin clientes vinculados.")
        return

    _HDR = {"critico":"#7F1D1D","medio":"#78350F","ok":"#14532D"}
    _COL = {"critico":"#DC2626","medio":"#D97706","ok":"#059669"}
    _LBL = {"critico":"⚠ Crítico","medio":"◔ Revisar","ok":"✓ OK"}

    MAX_COLS = 4
    for fila_start in range(0, len(cartera), MAX_COLS):
        fila_rows = cartera[fila_start:fila_start+MAX_COLS]
        cols = st.columns(MAX_COLS)
        for col_idx, c in enumerate(fila_rows):
            estado  = c["estado"]
            hdr     = _HDR[estado]
            txt     = _COL[estado]
            lbl     = _LBL[estado]
            modelo  = c.get("modelo100",{})
            ingresos= fmt_eur(modelo.get("ingresos",0))
            base    = fmt_eur(modelo.get("rend_final",0))
            gastos  = fmt_eur(modelo.get("total_gastos",0))
            rend    = fmt_eur(modelo.get("rend_neto",0))
            criticas= c["criticas"]
            badge_bg= {"critico":"rgba(220,38,38,0.10)",
                       "medio":"rgba(217,119,6,0.10)",
                       "ok":"rgba(5,150,105,0.10)"}[estado]
            chk = "✅" if criticas == 0 else "⚠️"

            with cols[col_idx]:
                st.markdown(
                    f'<div style="background:{hdr};border-radius:12px 12px 0 0;' +
                    f'padding:14px 16px 12px;display:flex;align-items:center;' +
                    f'gap:10px;margin-bottom:-1px;">' +
                    f'<span style="font-size:22px;">📋</span>' +
                    f'<div style="flex:1;min-width:0;">' +
                    f'<div style="font-size:16px;font-weight:800;color:#FFF;' +
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
                    f'{c["nombre"]}</div>' +
                    f'<div style="font-size:12px;color:rgba(255,255,255,0.65);margin-top:2px;">' +
                    f'{c["inmuebles"]} inmuebles · campaña 2025</div></div>' +
                    f'<span style="background:rgba(255,255,255,0.15);color:#FFF;' +
                    f'font-size:11px;font-weight:700;padding:3px 8px;' +
                    f'border-radius:6px;">{lbl}</span></div>' +
                    f'<div style="background:#FFF;border:2px solid #E2E8F0;' +
                    f'border-top:none;border-radius:0 0 12px 12px;' +
                    f'padding:14px 16px 12px;">' +
                    f'<div style="display:flex;justify-content:space-between;' +
                    f'margin-bottom:6px;">' +
                    f'<span style="font-size:13px;color:#94A3B8;">📥 0102 Ingresos</span>' +
                    f'<span style="font-size:14px;font-weight:800;color:#059669;">{ingresos}</span></div>' +
                    f'<div style="display:flex;justify-content:space-between;' +
                    f'margin-bottom:6px;">' +
                    f'<span style="font-size:13px;color:#94A3B8;">📤 Gastos deducibles</span>' +
                    f'<span style="font-size:14px;font-weight:800;color:#DC2626;">-{gastos}</span></div>' +
                    f'<div style="display:flex;justify-content:space-between;' +
                    f'margin-bottom:6px;">' +
                    f'<span style="font-size:13px;color:#94A3B8;">⚖️ 0149 Rend. neto</span>' +
                    f'<span style="font-size:14px;font-weight:800;color:#534AB7;">{rend}</span></div>' +
                    f'<div style="display:flex;justify-content:space-between;' +
                    f'margin-bottom:10px;">' +
                    f'<span style="font-size:13px;color:#94A3B8;">{chk} Alertas</span>' +
                    f'<span style="font-size:14px;font-weight:800;color:{txt};">{criticas}</span></div>' +
                    f'<div style="background:{badge_bg};border-radius:6px;' +
                    f'padding:6px 10px;text-align:center;' +
                    f'font-size:13px;font-weight:700;color:{txt};">' +
                    f'🧾 Base imp. est.: {base}</div></div>',
                    unsafe_allow_html=True)

                if st.button("📄 Ir a revisión completa",
                             key=f"exp_{c['id']}_{col_idx}",
                             use_container_width=True, type="primary"):
                    st.session_state.fh_cliente_sel = c["id"]
                    st.session_state.fh_menu = "cliente"
                    st.rerun()
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── VINCULAR ──────────────────────────────────────────────────────
def pantalla_vincular():
    st.markdown("""<div style="margin-bottom:16px;">
      <div class="nc-page-label">Conectar con Nolasco Capital</div>
      <div class="nc-page-title">Vincular cliente</div>
      <div class="nc-page-sub">Introduce el código de 6 dígitos del propietario.</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("""<div class="nc-callout info" style="max-width:560px;margin-bottom:20px;">
      <strong>¿Cómo funciona?</strong> El propietario entra en Nolasco Capital →
      Privacidad → "Compartir con Asesor" → genera un código. Te lo envía y lo introduces aquí.
    </div>""", unsafe_allow_html=True)
    codigo = st.text_input("Código:", max_chars=10, placeholder="Ej: 628410", key="vincular_codigo")
    if st.button("🔗 Vincular", use_container_width=True, type="primary", key="vincular_btn"):
        if codigo.strip():
            with st.spinner("Verificando..."):
                res = vincular_propietario(st.session_state.fh_user_id, codigo.strip().upper())
            if res["ok"]:
                st.success(f"✅ Vinculado — {res.get('nombre','Propietario')} en tu cartera.")
                vinculos = get_clientes_vinculados(st.session_state.fh_user_id)
                st.session_state.fh_cartera = construir_cartera(vinculos)
                st.rerun()
            else: st.error(f"❌ {res.get('error','Código no válido')}")
        else: st.warning("Introduce un código")


# ── MOCK DATA — activar con ?demo=1 en la URL ─────────────────────
def _mock_cartera():
    """Cartera de demostración con 6 clientes ficticios + los reales."""
    import pandas as pd
    from datetime import date, timedelta

    def _inm(nombre, inquilino, tipo, renta, ibi, amort, seguro, comunidad,
             hipoteca=0, tiene_alerta=False, alerta_tipo="crit", alerta_txt=""):
        return {
            "nombre": nombre, "inquilino": inquilino,
            "tipo_arrendamiento": tipo, "renta": renta,
            "ibi_anual": ibi, "amortizacion_fiscal": amort,
            "seguro_anual": seguro, "comunidad": comunidad,
            "intereses_hipoteca": hipoteca,
            "tiene_alerta": tiene_alerta,
            "alerta_tipo": alerta_tipo, "alerta_txt": alerta_txt,
            "fecha_vencimiento_contrato": str(date.today() + timedelta(days=30)) if tiene_alerta else "",
            "precio_compra": 180000, "valor_catastral": 95000,
            "porcentaje_construccion": 0.7,
        }

    clientes_mock = [
        {
            "id": "mock-001", "nombre": "García Martínez, Ana",
            "estado": "critico", "criticas": 3, "medias": 1,
            "inmuebles": 3, "impacto": -2400,
            "alertas": [
                {"tipo":"crit","titulo":"Amortización a 0 — revisar","desc":"Catastral: 95.000 € · Precio compra: 180.000 €","accion":"Calcular 3% s/ MAX(precio compra, catastral) × % construcción","inmueble":"Calle Mayor 12","cliente_nombre":"García Martínez, Ana"},
                {"tipo":"crit","titulo":"Contrato próximo a vencer","desc":"Vence en 28 días sin renovar","accion":"Notificar al inquilino y preparar nuevo contrato","inmueble":"Av. Constitución 4","cliente_nombre":"García Martínez, Ana"},
                {"tipo":"crit","titulo":"ROE negativo","desc":"La hipoteca consume el 110% de los ingresos netos","accion":"Revisar si refinanciar o vender el activo","inmueble":"Plaza Nueva 8","cliente_nombre":"García Martínez, Ana"},
                {"tipo":"warn","titulo":"Rentabilidad por debajo de mercado","desc":"Rendimiento actual 3.2% vs 6.8% de media en CP 18001","accion":"Evaluar subida de renta en próxima renovación","inmueble":"Calle Mayor 12","cliente_nombre":"García Martínez, Ana"},
            ],
            "modelo100": {"ingresos":28800,"total_gastos":22400,"rend_neto":6400,"reduccion":3200,"rend_final":3200,"retenciones":5472,"intereses":4200,"reparaciones":800,"ibi":1240,"comunidad_seguros":3600,"suministros":0,"gastos_juridicos":0,"amortizacion":12560,"red_pct":50},
            "df_inm": pd.DataFrame([
                _inm("Calle Mayor 12","Luisa Fernández","Larga Duración",900,620,3800,380,1200,1800,True,"crit","Amortización a 0"),
                _inm("Av. Constitución 4","Roberto Sanz","Larga Duración",750,480,2900,290,900,0,True,"crit","Contrato vence 28 días"),
                _inm("Plaza Nueva 8","Carmen López","Larga Duración",550,390,2100,210,720,1600,True,"crit","ROE negativo"),
            ]),
            "df_mov": pd.DataFrame(),
        },
        {
            "id": "mock-002", "nombre": "López Ruiz, Carlos",
            "estado": "critico", "criticas": 2, "medias": 2,
            "inmuebles": 4, "impacto": -1800,
            "alertas": [
                {"tipo":"crit","titulo":"Amortización a 0 — revisar","desc":"Catastral: 112.000 € · Precio compra: 210.000 €","accion":"Calcular 3% s/ MAX","inmueble":"Gran Vía 33","cliente_nombre":"López Ruiz, Carlos"},
                {"tipo":"crit","titulo":"Gastos sin justificar","desc":"3 recibos de reparaciones sin factura adjunta","accion":"Solicitar facturas al propietario antes del 30/06","inmueble":"Recogidas 18","cliente_nombre":"López Ruiz, Carlos"},
                {"tipo":"warn","titulo":"IBI pendiente de actualizar","desc":"El IBI declarado no coincide con el recibo 2024","accion":"Verificar con el Ayuntamiento","inmueble":"Gran Vía 33","cliente_nombre":"López Ruiz, Carlos"},
                {"tipo":"warn","titulo":"Seguro infradeducido","desc":"Seguro hogar+vida deducible al 100% — solo se declaró el 50%","accion":"Corregir casilla 0110","inmueble":"Recogidas 18","cliente_nombre":"López Ruiz, Carlos"},
            ],
            "modelo100": {"ingresos":42000,"total_gastos":31200,"rend_neto":10800,"reduccion":5400,"rend_final":5400,"retenciones":7980,"intereses":6800,"reparaciones":1200,"ibi":1820,"comunidad_seguros":4800,"suministros":0,"gastos_juridicos":0,"amortizacion":16580,"red_pct":50},
            "df_inm": pd.DataFrame([
                _inm("Gran Vía 33","Marcos Vega","Larga Duración",1200,820,5200,480,1560,2400,True,"crit","Amortización a 0"),
                _inm("Recogidas 18","Sofía Moreno","Larga Duración",950,640,3900,360,1200,0,True,"crit","Gastos sin justificar"),
                _inm("Camino Ronda 5","Pedro Jiménez","Temporada",700,420,2800,260,840,0,False),
                _inm("Arabial 22","Nuria Castro","Larga Duración",650,380,2400,220,720,0,False),
            ]),
            "df_mov": pd.DataFrame(),
        },
        {
            "id": "mock-003", "nombre": "Martínez Peña, Isabel",
            "estado": "medio", "criticas": 0, "medias": 2,
            "inmuebles": 2, "impacto": 0,
            "alertas": [
                {"tipo":"warn","titulo":"Contrato vence en 45 días","desc":"Arrendamiento de larga duración próximo a expirar","accion":"Iniciar proceso de renovación o búsqueda de nuevo inquilino","inmueble":"Paseo Colón 7","cliente_nombre":"Martínez Peña, Isabel"},
                {"tipo":"warn","titulo":"Rentabilidad por debajo de mercado","desc":"Renta 4.1% vs 6.5% de media en CP 18002","accion":"Evaluar incremento según IRAV 2026 (2.47%)","inmueble":"San Juan de Dios 14","cliente_nombre":"Martínez Peña, Isabel"},
            ],
            "modelo100": {"ingresos":19200,"total_gastos":12800,"rend_neto":6400,"reduccion":3200,"rend_final":3200,"retenciones":3648,"intereses":2400,"reparaciones":400,"ibi":980,"comunidad_seguros":2400,"suministros":0,"gastos_juridicos":0,"amortizacion":6620,"red_pct":50},
            "df_inm": pd.DataFrame([
                _inm("Paseo Colón 7","Alberto García","Larga Duración",900,680,3200,300,960,0,True,"warn","Contrato vence 45 días"),
                _inm("San Juan de Dios 14","Elena Ruiz","Larga Duración",700,520,2400,240,720,0,True,"warn","Rentabilidad baja"),
            ]),
            "df_mov": pd.DataFrame(),
        },
        {
            "id": "mock-004", "nombre": "Sánchez Torres, Miguel",
            "estado": "ok", "criticas": 0, "medias": 0,
            "inmuebles": 2, "impacto": 0,
            "alertas": [],
            "modelo100": {"ingresos":22800,"total_gastos":14600,"rend_neto":8200,"reduccion":4100,"rend_final":4100,"retenciones":4332,"intereses":0,"reparaciones":600,"ibi":1100,"comunidad_seguros":3200,"suministros":0,"gastos_juridicos":0,"amortizacion":9700,"red_pct":50},
            "df_inm": pd.DataFrame([
                _inm("Alhambra 3","Rosa Blanco","Larga Duración",1100,760,4200,420,1320,0,False),
                _inm("Zaidín Norte 8","Jesús Molina","Larga Duración",800,580,3100,300,960,0,False),
            ]),
            "df_mov": pd.DataFrame(),
        },
        {
            "id": "mock-005", "nombre": "Fernández Gómez, Laura",
            "estado": "ok", "criticas": 0, "medias": 0,
            "inmuebles": 1, "impacto": 0,
            "alertas": [],
            "modelo100": {"ingresos":9600,"total_gastos":6200,"rend_neto":3400,"reduccion":1700,"rend_final":1700,"retenciones":1824,"intereses":0,"reparaciones":200,"ibi":480,"comunidad_seguros":1200,"suministros":0,"gastos_juridicos":0,"amortizacion":4320,"red_pct":50},
            "df_inm": pd.DataFrame([
                _inm("Neptuno 5","Diana Prieto","Larga Duración",800,480,2400,240,720,0,False),
            ]),
            "df_mov": pd.DataFrame(),
        },
        {
            "id": "mock-006", "nombre": "Romero Díaz, Antonio",
            "estado": "critico", "criticas": 1, "medias": 0,
            "inmuebles": 1, "impacto": -600,
            "alertas": [
                {"tipo":"crit","titulo":"Amortización a 0 — revisar","desc":"Catastral: 78.000 € · Precio compra: 145.000 €","accion":"Calcular 3% s/ MAX","inmueble":"Genil 12","cliente_nombre":"Romero Díaz, Antonio"},
            ],
            "modelo100": {"ingresos":9600,"total_gastos":7800,"rend_neto":1800,"reduccion":900,"rend_final":900,"retenciones":1824,"intereses":0,"reparaciones":300,"ibi":560,"comunidad_seguros":1440,"suministros":0,"gastos_juridicos":0,"amortizacion":5500,"red_pct":50},
            "df_inm": pd.DataFrame([
                _inm("Genil 12","Francisco Ruiz","Larga Duración",800,560,2800,280,840,0,True,"crit","Amortización a 0"),
            ]),
            "df_mov": pd.DataFrame(),
        },
    ]
    return sorted(clientes_mock, key=lambda x:({"critico":0,"medio":1,"ok":2}[x["estado"]],-x["criticas"]))


# ── MAIN ──────────────────────────────────────────────────────────
def main():
    inject_global_css("ficahub")
    if "fh_logged" not in st.session_state: st.session_state.fh_logged = False
    if "fh_menu"   not in st.session_state: st.session_state.fh_menu   = "cartera"

    if not st.session_state.fh_logged:
        pantalla_login(); return

    # Demo mode — añade ?demo=1 a la URL para ver mock data
    demo_mode = st.query_params.get("demo", "0") == "1"

    if "fh_cartera" not in st.session_state:
        with st.spinner("Cargando cartera..."):
            if demo_mode:
                # Cargar reales + mock
                vinculos = get_clientes_vinculados(st.session_state.fh_user_id)
                cartera_real = construir_cartera(vinculos)
                cartera_mock = _mock_cartera()
                # Evitar duplicados por nombre
                nombres_reales = {c["nombre"] for c in cartera_real}
                extra = [c for c in cartera_mock if c["nombre"] not in nombres_reales]
                st.session_state.fh_cartera = cartera_real + extra
            else:
                vinculos = get_clientes_vinculados(st.session_state.fh_user_id)
                st.session_state.fh_cartera = construir_cartera(vinculos)

    if demo_mode:
        st.sidebar.markdown(
            '<div style="background:#FFC107;color:#795548;font-size:10px;font-weight:700;'
            'padding:4px 10px;border-radius:6px;margin:4px 10px;text-align:center;'
            'letter-spacing:0.06em;">🎭 MODO DEMO</div>',
            unsafe_allow_html=True
        )

    with st.sidebar:
        render_sidebar()

    menu = st.session_state.get("fh_menu","cartera")
    st.markdown('<div class="nc-page">', unsafe_allow_html=True)
    if   menu == "cartera":        pantalla_cartera()
    elif menu == "cliente":        pantalla_cliente()
    elif menu == "ficha":          pantalla_ficha_inmueble()
    elif menu == "resumen_global": pantalla_resumen_global()
    elif menu == "alertas":        pantalla_alertas()
    elif menu == "exportar":       pantalla_exportar()
    elif menu == "vincular":       pantalla_vincular()
    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
# USO en fiscalhub_app.py:
#   from sabio_fiscal import render_sabio_fiscal
#   render_sabio_fiscal("ficha", contexto_dict, decisiones_dict)
# ================================================================

import streamlit as st
import anthropic
import os

ACCENT       = "#534AB7"
ACCENT_LIGHT = "#EEEDFE"
TEXT_PRI     = "#0F172A"

# ── SYSTEM PROMPTS ──────────────────────────────────────────────
SYSTEM_PROMPTS = {

    "ficha": """Eres el Asesor Fiscal IA de FiscalHub. Hablas a un asesor fiscal profesional.
Estás analizando un inmueble concreto y las decisiones fiscales que el asesor ha seleccionado.

DATOS DEL INMUEBLE:
{contexto}

DECISIONES ACTIVAS DEL ASESOR:
{decisiones}

IMPACTO CALCULADO:
- Base imponible original: {base_original} €
- Base imponible simulada: {base_simulada} €
- Ahorro estimado: {ahorro} €
- Reducción aplicada: {reduccion_pct}%

TU MISIÓN:
1. Valora si la combinación de decisiones es fiscalmente óptima y prudente ante Hacienda
2. Identifica si hay alguna decisión que pueda generar riesgo de inspección
3. Sugiere si hay alguna palanca adicional no seleccionada que mejoraría el resultado

REGLAS ESTRICTAS:
- Máximo 4 frases. Con números reales del contexto.
- Usa terminología fiscal correcta (casillas, artículos LIRPF si aplica)
- Tono profesional entre colegas. El asesor sabe de fiscalidad.
- Distingue claramente entre lo que es seguro y lo que tiene riesgo
- No inventas datos. Solo analizas lo que se te proporciona.""",

    "proactiva": """Eres el Asesor Fiscal IA de FiscalHub. Análisis proactivo de fin de año.
Estás proyectando la situación fiscal del inmueble si se tomaran acciones antes del 31 de diciembre.

DATOS DEL INMUEBLE:
{contexto}

MESES RESTANTES DEL AÑO: {meses_restantes}
INGRESOS ACUMULADOS A HOY: {ingresos_acumulados} €
RITMO PROYECTADO FIN DE AÑO: {ingresos_proyectados} €

TU MISIÓN:
- Si los ingresos proyectados son altos, sugiere qué gastos o mejoras anticipar antes del 31/12
- Si hay margen de maniobra, indica exactamente cuánto puede gastar sin superar el umbral óptimo
- Menciona plazos concretos (qué hacer en noviembre vs. diciembre)

REGLAS:
- Máximo 3 frases. Con euros y fechas concretas.
- Tono urgente si quedan menos de 3 meses. Preventivo si hay más tiempo.
- Solo lo que es fiscalmente seguro.""",
}

CHIPS = {
    "ficha": [
        "¿Es seguro ante inspección?",
        "¿Hay riesgo en esta combinación?",
        "¿Qué más puedo deducir?",
        "¿Reparación o mejora?",
    ],
    "proactiva": [
        "¿Cuánto puedo gastar antes de diciembre?",
        "¿Qué es mejor anticipar?",
        "¿Cómo reduzco la base ahora?",
    ],
}

LABELS = {
    "ficha":     "◈ Asesor Fiscal IA · Análisis de Decisiones",
    "proactiva": "◈ Asesor Fiscal IA · Fiscalidad Proactiva",
}


# ── API ─────────────────────────────────────────────────────────
def _get_api_key() -> str:
    # Intentar todas las variantes posibles del nombre
    for nombre in ["ANTHROPIC_API_KEY", "anthropic_api_key", "ANTHROPIC_KEY"]:
        try:
            key = st.secrets[nombre]
            if key: return str(key)
        except Exception:
            pass
    # Fallback variable de entorno
    return os.getenv("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_KEY", ""))


def _llamar_claude(system: str, pregunta: str, max_tokens: int = 350) -> str:
    api_key = _get_api_key()
    if not api_key:
        return "Configura ANTHROPIC_API_KEY en los secrets para activar el Asesor Fiscal IA."
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": pregunta}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"El Asesor IA no está disponible ({str(e)[:60]})."


def _insight_proactivo(seccion: str, contexto: dict, decisiones: dict,
                        base_original: float, base_simulada: float) -> str:
    """Insight automático al abrir la sección. Cacheado por inmueble+decisiones."""
    ahorro = base_original - base_simulada
    cache_key = f"sabio_fiscal_{seccion}_{hash(str(decisiones))}"

    if cache_key in st.session_state:
        return st.session_state[cache_key]

    ahorro_pct = round((ahorro / base_original * 100) if base_original else 0, 1)
    system = SYSTEM_PROMPTS[seccion].format(
        contexto=contexto,
        decisiones=decisiones,
        base_original=round(base_original, 2),
        base_simulada=round(base_simulada, 2),
        ahorro=round(ahorro, 2),
        reduccion_pct=ahorro_pct,
        meses_restantes=decisiones.get("meses_restantes", "—"),
        ingresos_acumulados=decisiones.get("ingresos_acumulados", "—"),
        ingresos_proyectados=decisiones.get("ingresos_proyectados", "—"),
    )
    resultado = _llamar_claude(system,
        "Analiza esta situación y da tu valoración más importante en 3 frases.",
        max_tokens=200)
    st.session_state[cache_key] = resultado
    return resultado


# ── RENDER PRINCIPAL ────────────────────────────────────────────
def render_sabio_fiscal(seccion: str, contexto: dict, decisiones: dict,
                         base_original: float = 0.0, base_simulada: float = 0.0):
    """
    Asesor Fiscal IA integrado en la ficha del inmueble.

    seccion:       "ficha" | "proactiva"
    contexto:      datos del inmueble (dict)
    decisiones:    decisiones activas del asesor (dict)
    base_original: base imponible sin cambios
    base_simulada: base imponible con las decisiones aplicadas
    """
    hist_key    = f"sabio_fiscal_hist_{seccion}"
    counter_key = f"sabio_fiscal_cnt_{seccion}"
    if hist_key    not in st.session_state: st.session_state[hist_key]    = []
    if counter_key not in st.session_state: st.session_state[counter_key] = 0

    label  = LABELS.get(seccion, "◈ Asesor Fiscal IA")
    chips  = CHIPS.get(seccion, [])
    ahorro = base_original - base_simulada

    with st.expander(f"🧠 {label}", expanded=True):

        # Insight proactivo automático
        with st.spinner("El Asesor IA está analizando las decisiones..."):
            insight = _insight_proactivo(seccion, contexto, decisiones,
                                          base_original, base_simulada)

        # Bocadillo insight
        st.markdown(f"""
        <div style="background:{ACCENT_LIGHT};border:1.5px solid {ACCENT};
                    border-radius:12px;padding:14px 18px;margin-bottom:12px;">
            <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;
                        text-transform:uppercase;color:{ACCENT};margin-bottom:6px;">
                {label}
            </div>
            <div style="font-size:13px;color:{TEXT_PRI};line-height:1.65;">
                {insight}
            </div>
        </div>""", unsafe_allow_html=True)

        # Chips rápidos
        if chips:
            chip_html = "".join([
                f'<span style="background:{ACCENT_LIGHT};color:{ACCENT};'
                f'font-size:11px;font-weight:600;padding:5px 12px;'
                f'border-radius:20px;margin-right:6px;margin-bottom:4px;'
                f'display:inline-block;cursor:pointer;">{c}</span>'
                for c in chips
            ])
            st.markdown(f'<div style="margin:6px 0 12px">{chip_html}</div>',
                        unsafe_allow_html=True)

        # Input conversacional — key con counter para vaciar tras envío
        cnt = st.session_state[counter_key]
        col_inp, col_btn = st.columns([0.82, 0.18])
        with col_inp:
            pregunta = st.text_input("",
                key=f"sabio_fiscal_input_{seccion}_{cnt}",
                placeholder="Pregunta sobre estas decisiones fiscales...",
                label_visibility="collapsed")
        with col_btn:
            enviar = st.button("Enviar", key=f"sabio_fiscal_btn_{seccion}_{cnt}")

        # Procesar pregunta
        if enviar and pregunta.strip():
            ahorro_pct = round((ahorro / base_original * 100) if base_original else 0, 1)
            system = SYSTEM_PROMPTS[seccion].format(
                contexto=contexto,
                decisiones=decisiones,
                base_original=round(base_original, 2),
                base_simulada=round(base_simulada, 2),
                ahorro=round(ahorro, 2),
                reduccion_pct=ahorro_pct,
                meses_restantes=decisiones.get("meses_restantes", "—"),
                ingresos_acumulados=decisiones.get("ingresos_acumulados", "—"),
                ingresos_proyectados=decisiones.get("ingresos_proyectados", "—"),
            )
            with st.spinner("Analizando..."):
                respuesta = _llamar_claude(system, pregunta.strip())
            st.session_state[hist_key].append(
                {"role": "user",      "content": pregunta.strip()})
            st.session_state[hist_key].append(
                {"role": "assistant", "content": respuesta})
            # Vaciar input incrementando el counter
            st.session_state[counter_key] += 1
            st.rerun()

        # Historial
        for msg in st.session_state[hist_key]:
            if msg["role"] == "user":
                st.markdown(f"""
                <div style="text-align:right;margin:8px 0">
                    <span style="background:{ACCENT_LIGHT};color:{TEXT_PRI};
                        padding:8px 14px;border-radius:16px 16px 4px 16px;
                        font-size:12px;display:inline-block;max-width:80%">
                        {msg['content']}
                    </span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background:#F8F9FA;border-radius:12px;
                            padding:12px 14px;font-size:12px;
                            color:{TEXT_PRI};line-height:1.6;margin:8px 0;
                            border-left:3px solid {ACCENT};">
                    {msg['content']}
                </div>""", unsafe_allow_html=True)

        # Botón limpiar
        if st.session_state[hist_key]:
            if st.button("🗑 Limpiar conversación",
                         key=f"sabio_fiscal_clear_{seccion}_{cnt}"):
                st.session_state[hist_key]    = []
                st.session_state[counter_key] = 0
                st.session_state.pop(f"sabio_fiscal_{seccion}_"
                                     f"{hash(str(decisiones))}", None)
                st.rerun()
