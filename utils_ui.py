import streamlit as st


def load_custom_css():
    """Carrega o CSS global com suporte nativo a LIGHT e DARK mode."""
    st.markdown("""
    <style>
        /* Fonte Moderna */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* --- DEFINIÇÃO DE VARIÁVEIS (Adaptação Automática) --- */
        :root {
            --bg-color: #F8FAFC;         /* Fundo Claro (Cinza Gelo) */
            --sidebar-bg: #FFFFFF;       /* Sidebar Branca */
            --card-bg: #FFFFFF;          /* Card Branco */
            --text-color: #1E293B;       /* Texto Principal Escuro */
            --text-secondary: #64748B;   /* Texto Secundário Cinza */
            --sidebar-text: #475569;     /* Texto Menu */
            --border-color: #E2E8F0;     /* Bordas Claras */
            --input-bg: #FFFFFF;         /* Input Branco */
            --hover-bg: #F1F5F9;         /* Hover Suave */
            --primary-color: #16A34A;    /* Verde Principal */
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        /* Detecta Modo Escuro e inverte as cores para alto contraste */
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-color: #0E1117;         /* Fundo Escuro Profundo */
                --sidebar-bg: #161B22;       /* Sidebar Escura */
                --card-bg: #1F2937;          /* Card Cinza Escuro */
                --text-color: #F1F5F9;       /* Texto Principal Claro */
                --text-secondary: #94A3B8;   /* Texto Secundário Claro */
                --sidebar-text: #E2E8F0;     /* Texto Menu Claro */
                --border-color: #374151;     /* Bordas Escuras */
                --input-bg: #111827;         /* Input Muito Escuro */
                --hover-bg: #374151;         /* Hover Escuro */
                --primary-color: #22C55E;    /* Verde Mais Vibrante para Dark */
                --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
                --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
            }
        }

        /* Força variáveis se o Streamlit injetar classe dark manualmente */
        [data-theme="dark"] {
            --bg-color: #0E1117;
            --sidebar-bg: #161B22;
            --card-bg: #1F2937;
            --text-color: #F1F5F9;
            --text-secondary: #94A3B8;
            --sidebar-text: #E2E8F0;
            --border-color: #374151;
            --input-bg: #111827;
            --hover-bg: #374151;
            --primary-color: #22C55E;
        }

        /* --- APLICAÇÃO GLOBAL --- */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
        }

        .stApp {
            background-color: var(--bg-color);
        }

        /* Força cor de texto em elementos markdown */
        p, .stMarkdown, .stText {
            color: var(--text-color) !important;
        }

        .stCaption {
            color: var(--text-secondary) !important;
        }

        /* --- SIDEBAR --- */
        [data-testid="stSidebar"] {
            background-color: var(--sidebar-bg);
            border-right: 1px solid var(--border-color);
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: var(--text-color) !important;
        }
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: var(--sidebar-text);
        }

        /* Links de Navegação */
        div[data-testid="stSidebarNav"] a, div[data-testid="stSidebarNav"] span {
            color: var(--sidebar-text) !important;
            font-weight: 500;
        }
        div[data-testid="stSidebarNav"] a:hover, div[data-testid="stSidebarNav"] a:hover span {
            background-color: rgba(34, 197, 94, 0.15) !important; 
            color: var(--primary-color) !important;
        }

        /* --- CARDS (KPIs) --- */
        .ui-card {
            background-color: var(--card-bg);
            padding: 20px;
            border-radius: 12px;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .ui-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
            border-color: var(--primary-color);
        }

        .card-label {
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .card-value {
            font-size: 2.2rem;
            font-weight: 800;
            color: var(--text-color);
            line-height: 1;
        }

        .card-subtext {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 8px;
            opacity: 0.8;
        }

        /* Ícones SVG nos cards */
        .card-icon svg {
            width: 32px;
            height: 32px;
            opacity: 0.9;
        }

        /* --- BOTÕES (Incluindo Download) --- */
        /* Agrupa stButton e stDownloadButton */
        .stButton button, .stDownloadButton button {
            border-radius: 8px;
            font-weight: 600;
            border: none;
            transition: all 0.2s;
            padding: 0.5rem 1rem;
            box-shadow: var(--shadow-sm);
        }

        /* Botão Primário */
        .stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {
            background-color: var(--primary-color);
            color: #FFFFFF !important;
        }
        .stButton button[kind="primary"]:hover, .stDownloadButton button[kind="primary"]:hover {
            filter: brightness(1.1);
            transform: scale(1.01);
            box-shadow: var(--shadow-md);
        }

        /* Botão Secundário */
        .stButton button[kind="secondary"], .stDownloadButton button[kind="secondary"] {
            background-color: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--border-color);
        }
        .stButton button[kind="secondary"]:hover, .stDownloadButton button[kind="secondary"]:hover {
            background-color: var(--hover-bg);
            border-color: var(--text-secondary);
            color: var(--text-color);
        }

        /* --- INPUTS & SELECTBOXES --- */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input, .stTextArea textarea, .stDateInput input {
            background-color: var(--input-bg) !important;
            color: var(--text-color) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px;
        }
        ul[data-testid="stSelectboxVirtualDropdown"] {
            background-color: var(--card-bg) !important;
        }
        li[role="option"] {
            color: var(--text-color) !important;
        }

        .stTextInput label, .stSelectbox label, .stNumberInput label, .stTextArea label, .stDateInput label {
            color: var(--text-secondary) !important;
            font-weight: 500;
        }

        /* --- TABELAS --- */
        [data-testid="stDataFrame"] {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
        }
        [data-testid="stDataFrame"] div[role="grid"] {
            color: var(--text-color);
        }
        [data-testid="stDataFrame"] thead th {
            background-color: var(--hover-bg) !important;
            color: var(--text-secondary) !important;
            font-weight: 600;
            border-bottom: 1px solid var(--border-color) !important;
        }

        /* --- TOAST & EXPANDER --- */
        div[data-testid="stToast"] {
            background-color: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-md);
        }
        .streamlit-expanderHeader {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            border-radius: 8px;
        }
        .streamlit-expanderContent {
            background-color: transparent;
            color: var(--text-color);
            border: 1px solid var(--border-color);
            border-top: none;
        }

        /* --- CABEÇALHO PADRÃO --- */
        .ui-header-container {
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }
        .ui-header-title {
            font-family: 'Inter', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-color);
            margin: 0;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .ui-header-subtitle {
            font-size: 0.95rem;
            color: var(--text-secondary);
            margin-top: 4px;
            font-weight: 400;
        }

        /* --- EMPTY STATE --- */
        .ui-empty-state {
            text-align: center;
            padding: 40px 20px;
            background-color: var(--card-bg);
            border: 1px dashed var(--border-color);
            border-radius: 12px;
            color: var(--text-secondary);
            margin-top: 20px;
        }

    </style>
    """, unsafe_allow_html=True)


# --- COMPONENTES VISUAIS (Python Wrappers) ---

def ui_header(title, subtitle="", icon=""):
    """Renderiza um cabeçalho de página padronizado."""
    icon_html = ""
    if icon:
        if str(icon).strip().startswith("<svg"):
            clean_svg = str(icon).replace("\n", "").replace("\r", "").strip()
            icon_html = f"<div style='width: 32px; height: 32px; display: flex; align-items: center;'>{clean_svg}</div>"
        else:
            icon_html = f"<span>{icon}</span>"

    st.markdown(f"""
    <div class="ui-header-container">
        <div class="ui-header-title">{icon_html} {title}</div>
        <div class="ui-header-subtitle">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def ui_kpi_card(col, title, value, icon_svg="", color="#64748B", subtext=""):
    """Renderiza um card de KPI padronizado (Versão Atualizada)."""
    if color in ["#ddd", "#E0E0E0", "transparent", "white"]:
        color = "#64748B"

    icon_render = ""
    if icon_svg:
        svg = str(icon_svg).replace('\n', '').strip()
        if svg.startswith("<svg"):
            icon_render = svg
        else:
            icon_render = f"<span style='font-size: 1.5rem;'>{icon_svg}</span>"

    html = f"""
    <div class="ui-card" style="border-left: 4px solid {color};">
        <div class="card-label" style="color: {color};">
            <div style="width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;">{icon_render}</div>
            {title}
        </div>
        <div class="card-value">{value}</div>
        <div class="card-subtext">{subtext}</div>
    </div>
    """
    col.markdown(html, unsafe_allow_html=True)


def ui_empty_state(message="Nenhum dado encontrado.", icon="🔍"):
    """Renderiza um visual para quando não há dados."""
    st.markdown(f"""
    <div class="ui-empty-state">
        <div style="font-size: 2rem; margin-bottom: 10px;">{icon}</div>
        <p>{message}</p>
    </div>
    """, unsafe_allow_html=True)


def card_kpi(col, titulo, valor, icone="📊", cor_borda="transparent", subtexto=""):
    """Alias para compatibilidade com código antigo."""
    ui_kpi_card(col, titulo, valor, icone, cor_borda, subtexto)