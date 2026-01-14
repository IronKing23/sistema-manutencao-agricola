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

        /* --- APLICAÇÃO GLOBAL --- */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* Fundo e Texto Base da Aplicação */
        .stApp {
            background-color: var(--bg-color);
            color: var(--text-color);
        }

        /* Força a cor do texto para elementos comuns */
        p, .stMarkdown, .stText {
            color: var(--text-color) !important;
        }

        /* Legendas (Captions) */
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

        .card-title {
            color: var(--text-secondary);
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }

        .card-value {
            color: var(--text-color);
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.2;
        }

        /* Ícones SVG nos cards */
        .card-icon svg {
            width: 32px;
            height: 32px;
            opacity: 0.9;
            filter: drop-shadow(0 2px 2px rgba(0,0,0,0.1));
        }

        /* --- BOTÕES --- */
        .stButton button {
            border-radius: 8px;
            font-weight: 600;
            border: none;
            transition: all 0.2s;
            padding: 0.5rem 1rem;
            box-shadow: var(--shadow-sm);
        }
        /* Botão Primário */
        .stButton button[kind="primary"] {
            background-color: var(--primary-color);
            color: #FFFFFF !important; /* Sempre branco */
        }
        .stButton button[kind="primary"]:hover {
            filter: brightness(1.1);
            transform: scale(1.01);
            box-shadow: var(--shadow-md);
        }
        /* Botão Secundário */
        .stButton button[kind="secondary"] {
            background-color: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--border-color);
        }
        .stButton button[kind="secondary"]:hover {
            background-color: var(--hover-bg);
            border-color: var(--text-secondary);
        }

        /* --- INPUTS, SELECTBOXES & DATEINPUT --- */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input, .stTextArea textarea, .stDateInput input {
            background-color: var(--input-bg) !important;
            color: var(--text-color) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px;
        }
        /* Dropdown options popup */
        ul[data-testid="stSelectboxVirtualDropdown"] {
            background-color: var(--card-bg) !important;
        }
        li[role="option"] {
            color: var(--text-color) !important;
        }

        /* Foco */
        .stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within, .stTextArea textarea:focus {
            border-color: var(--primary-color) !important;
            box-shadow: 0 0 0 1px var(--primary-color) !important;
        }
        /* Labels dos Inputs */
        .stTextInput label, .stSelectbox label, .stNumberInput label, .stTextArea label, .stDateInput label, .stRadio label {
            color: var(--text-secondary) !important;
            font-weight: 500;
        }

        /* --- TABELAS --- */
        [data-testid="stDataFrame"] {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
        }
        /* Garante cor do texto nas células */
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
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
        }

        /* --- HEADERS --- */
        h1, h2, h3, h4, h5, h6 {
            color: var(--text-color) !important;
            font-weight: 700;
        }
        .stMarkdown hr {
            border-top: 1px solid var(--border-color);
        }

        /* Badge de Alerta */
        .pulse-badge {
            background-color: rgba(220, 38, 38, 0.15);
            color: #F87171; /* Vermelho claro para ler no dark */
            border: 1px solid #EF4444;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: 700;
            animation: pulse-red 2s infinite;
            vertical-align: middle;
            margin-left: 8px;
        }
        @media (prefers-color-scheme: light) {
            .pulse-badge {
                 background-color: #FEF2F2;
                 color: #DC2626;
            }
        }
        @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(220, 38, 38, 0); }
            100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
        }

    </style>
    """, unsafe_allow_html=True)


def card_kpi(col, titulo, valor, icone="📊", cor_borda="transparent", subtexto=""):
    """Renderiza um card de KPI moderno. Suporta Emoji ou SVG."""
    # Ajuste de borda para visibilidade em ambos os temas
    if cor_borda in ["#ddd", "#E0E0E0", "transparent", "white"]:
        cor_borda = "#64748B"  # Slate 500 (visível no dark e light)

    # Verifica se é SVG
    icon_html = icone
    if not str(icone).strip().startswith("<svg"):
        icon_html = f'<span style="font-size: 1.8rem;">{icone}</span>'

    html = f"""
    <div class="ui-card" style="border-left: 4px solid {cor_borda};">
        <div>
            <div class="card-icon">{icon_html}</div>
            <div class="card-title">{titulo}</div>
            <div class="card-value">{valor}</div>
            <div style="font-size: 0.85em; color: var(--text-secondary); margin-top: 5px;">{subtexto}</div>
        </div>
    </div>
    """
    col.markdown(html, unsafe_allow_html=True)