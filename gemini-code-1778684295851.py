import streamlit as st
import anthropic

# 1. PALETA DE COLORES PROFESIONAL (Basada en tu marca)
_NAVY    = "#0F172A"  # Sidebar
_SLATE   = "#F8FAFC"  # Fondo principal
_ACCENT  = "#534AB7"  # Indigo Fiscal Hub
_BORDER  = "#E2E8F0"
_TEXT    = "#1E293B"

APP_TOKENS = {
    "ficahub": {
        "sidebar_bg": _NAVY,
        "sidebar_txt": "#CBD5E1",
        "body_bg": _SLATE,
        "accent": _ACCENT,
        "accent_light": "#EEF2FF",
        "card_bg": "#FFFFFF"
    }
}

def inject_global_css(app_name="ficahub"):
    t = APP_TOKENS.get(app_name)
    
    st.markdown(f"""
        <style>
        /* 1. Reset y Fondo */
        .stApp {{
            background-color: {t['body_bg']};
        }}

        /* 2. Sidebar Estilo "Enterprise" */
        [data-testid="stSidebar"] {{
            background-color: {t['sidebar_bg']} !important;
            border-right: 1px solid {t['sidebar_border'] if 'sidebar_border' in t else '#1E293B'};
        }}
        [data-testid="stSidebar"] * {{
            color: {t['sidebar_txt']} !important;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        
        /* 3. Títulos y Tipografía */
        h1, h2, h3 {{
            color: {_NAVY} !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
        }}

        /* 4. Contenedores de tarjetas (nc-card) */
        .nc-card {{
            background: white;
            padding: 24px;
            border-radius: 16px;
            border: 1px solid {_BORDER};
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
        }}

        /* 5. Estilo de los Chats (Bocadillos) */
        .chat-bubble-user {{
            background: {t['accent']};
            color: white;
            padding: 12px 16px;
            border-radius: 16px 16px 4px 16px;
            margin: 8px 0;
            float: right;
            clear: both;
            max-width: 80%;
            font-size: 0.9rem;
        }}
        .chat-bubble-ai {{
            background: white;
            color: {_TEXT};
            padding: 12px 16px;
            border-radius: 16px 16px 16px 4px;
            border: 1px solid {_BORDER};
            margin: 8px 0;
            float: left;
            clear: both;
            max-width: 80%;
            font-size: 0.9rem;
        }}
        </style>
    """, unsafe_allow_html=True)

# Mantenemos tu lógica de chat pero la estilizamos
def render_chat_ui(role, content):
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">{content}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{content}</div>', unsafe_allow_html=True)