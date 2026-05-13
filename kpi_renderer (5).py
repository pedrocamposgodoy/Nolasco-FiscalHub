# ================================================================
# kpi_renderer.py — KPIs estilo Nolasco Capital
# Padding natural, estilos 100% inline, sin height fijo.
# Marco oscuro + relieve garantizados.
# ================================================================

import streamlit as st

ACCENT_F = "#534AB7"
ACCENT_C = "#185FA5"
GREEN    = "#059669"
RED      = "#DC2626"
AMBER    = "#D97706"
GREY     = "#475569"

_FONT   = "'Plus Jakarta Sans','DM Sans',system-ui,sans-serif"
_BORDER = "2px solid #94A3B8"
_SHADOW = "0 6px 16px rgba(0,0,0,0.14),0 2px 6px rgba(0,0,0,0.10),inset 0 1px 0 rgba(255,255,255,0.85)"


def render_kpi_row(kpis_data: list):
    """
    Renderiza KPIs en fila. Estilos 100% inline — funciona en Streamlit.

    kpis_data: lista de dicts:
        label    (str)  — etiqueta
        value    (str)  — número grande
        color    (str)  — color del valor y borde superior
        subtitle (str)  — subtexto. Opcional.
    """
    cols = st.columns(len(kpis_data))
    for col, kpi in zip(cols, kpis_data):
        label    = kpi.get("label","")
        value    = str(kpi.get("value",""))
        color    = kpi.get("color", GREY)
        subtitle = kpi.get("subtitle","")

        sub = (
            f'<p style="font-size:14px;color:#94A3B8;margin:4px 0 0;'
            f'font-family:{_FONT};font-weight:500;">{subtitle}</p>'
        ) if subtitle else ""

        html = (
            f'<div style="'
            f'background:#FFFFFF;'
            f'border-radius:12px;'
            f'padding:20px 22px 18px;'
            f'border:{_BORDER};'
            f'border-top:5px solid {color};'
            f'box-shadow:{_SHADOW};'
            f'box-sizing:border-box;">'
            f'<p style="font-family:{_FONT};font-size:13px;font-weight:800;'
            f'color:#94A3B8;margin:0 0 8px;text-transform:uppercase;'
            f'letter-spacing:0.10em;">{label}</p>'
            f'<p style="font-family:{_FONT};font-size:2.6rem;font-weight:900;'
            f'color:{color};margin:0;line-height:1;'
            f'letter-spacing:-0.02em;">{value}</p>'
            f'{sub}'
            f'</div>'
        )
        col.markdown(html, unsafe_allow_html=True)


def render_kpi_large(label: str, value: str,
                     delta: str = None, color: str = ACCENT_F,
                     subtitle: str = None):
    """KPI grande para cabecera."""
    delta_html = ""
    if delta:
        pos   = delta.startswith("↑") or delta.startswith("+")
        dc    = GREEN if pos else RED
        dbg   = "rgba(5,150,105,0.1)" if pos else "rgba(220,38,38,0.1)"
        delta_html = (
            f'<div style="margin-top:10px;">'
            f'<span style="background:{dbg};color:{dc};'
            f'padding:4px 10px;border-radius:6px;'
            f'font-size:15px;font-weight:700;">{delta}</span>'
            f'</div>'
        )
    sub_html = (
        f'<p style="font-size:15px;color:#94A3B8;margin:4px 0 0;">'
        f'{subtitle}</p>'
    ) if subtitle else ""

    html = (
        f'<div style="background:#FFFFFF;border-radius:12px;padding:24px;'
        f'border:{_BORDER};border-top:5px solid {color};'
        f'box-shadow:{_SHADOW};">'
        f'<p style="font-family:{_FONT};font-size:13px;font-weight:800;'
        f'color:#94A3B8;margin:0 0 8px;text-transform:uppercase;'
        f'letter-spacing:0.10em;">{label}</p>'
        f'<p style="font-family:{_FONT};font-size:3.1rem;font-weight:900;'
        f'color:{color};margin:0;line-height:1;'
        f'letter-spacing:-0.02em;">{value}</p>'
        f'{sub_html}{delta_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def render_kpi_grid(kpis_data: list):
    """
    Renderiza KPIs en CSS Grid nativo — sin st.columns().
    Esto garantiza que padding-top:38% crea altura proporcional real.
    Ideal para 4 KPIs de revisión de cliente.

    kpis_data: lista de dicts: label, value, color, subtitle (opcional)
    """
    n = len(kpis_data)
    cards_html = (
        f'<div style="display:grid;grid-template-columns:repeat({n},1fr);' +
        f'gap:12px;margin-bottom:16px;">'
    )

    for kpi in kpis_data:
        label    = kpi.get("label","")
        value    = str(kpi.get("value",""))
        color    = kpi.get("color", GREY)
        subtitle = kpi.get("subtitle","")

        border_color = kpi.get("border_color", color)  # color del cliente si se pasa
        sub = (
            f'<p style="font-size:13px;color:#94A3B8;margin:4px 0 0;' +
            f'font-family:{_FONT};font-weight:500;">{subtitle}</p>'
        ) if subtitle else ""

        cards_html += (
            f'<div style="' +
            f'background:#FFFFFF;' +
            f'border-radius:12px;' +
            f'padding:22px 20px 18px;' +
            f'border:{_BORDER};' +
            f'border-top:5px solid {border_color};' +
            f'box-shadow:{_SHADOW};' +
            f'box-sizing:border-box;">' +
            f'<p style="font-family:{_FONT};font-size:13px;font-weight:800;' +
            f'color:#94A3B8;margin:0 0 8px;text-transform:uppercase;' +
            f'letter-spacing:0.10em;">{label}</p>' +
            f'<p style="font-family:{_FONT};font-size:2.6rem;font-weight:900;' +
            f'color:{color};margin:0;line-height:1;' +
            f'letter-spacing:-0.02em;">{value}</p>' +
            f'{sub}' +
            f'</div>'
        )

    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)
