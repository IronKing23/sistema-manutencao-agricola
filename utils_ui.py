import streamlit as st


def load_custom_css():
    st.markdown("""
    <style>
        /* --- IMPORTANDO FONTE MODERNA --- */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* --- SIDEBAR PERSONALIZADA --- */
        [data-testid="stSidebar"] {
            background-color: #1E2329;
            border-right: 1px solid #333;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: #E0E0E0 !important;
        }
        [data-testid="stSidebar"] span {
            color: #B0B3B8;
        }

        /* Botões da Sidebar */
        div[data-testid="stSidebarNav"] a {
            border-radius: 8px;
            margin-bottom: 5px; 
        }

        /* --- CARDS (KPIs) --- */
        .ui-card {
            background-color: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border: 1px solid #E5E7EB;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .ui-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
            border-color: #2E7D32;
        }

        .card-title {
            color: #6B7280;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }

        .card-value {
            color: #111827;
            font-size: 1.8rem;
            font-weight: 800;
            line-height: 1.2;
        }

        .card-icon {
            float: right;
            font-size: 1.5rem;
            color: #D1D5DB;
        }

        /* --- BOTÕES --- */
        .stButton button {
            border-radius: 8px;
            font-weight: 600;
            padding-top: 0.5rem;
            padding-bottom: 0.5rem;
            transition: all 0.2s;
        }
        /* Botão Primário (Verde) */
        .stButton button[kind="primary"] {
            background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%);
            border: none;
            box-shadow: 0 4px 6px rgba(46, 125, 50, 0.2);
        }
        .stButton button[kind="primary"]:hover {
            box-shadow: 0 6px 12px rgba(46, 125, 50, 0.3);
            transform: scale(1.02);
        }

        /* --- TABELAS --- */
        [data-testid="stDataFrame"] {
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            overflow: hidden;
        }

        /* --- TOAST --- */
        div[data-testid="stToast"] {
            border-radius: 10px;
            background-color: #fff;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
    </style>
    """, unsafe_allow_html=True)


def card_kpi(col, titulo, valor, icone="📊", cor_borda="transparent"):
    html = f"""
    <div class="ui-card" style="border-left: 4px solid {cor_borda};">
        <div class="card-icon">{icone}</div>
        <div class="card-title">{titulo}</div>
        <div class="card-value">{valor}</div>
    </div>
    """
    col.markdown(html, unsafe_allow_html=True)