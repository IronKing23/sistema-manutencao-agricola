import streamlit as st


def load_custom_css():
    """Carrega o CSS global da aplicação (TEMA 'SOFT LIGHT' - Profissional e Legível)."""
    st.markdown("""
    <style>
        /* Fonte Moderna */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* --- CONFIGURAÇÃO GERAL --- */
        /* Fundo da aplicação em um cinza muito suave (Off-White) para conforto visual */
        .stApp {
            background-color: #F1F5F9; 
        }

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #1E293B; /* Texto Cinza Escuro (Quase preto) para alto contraste */
        }

        /* --- SIDEBAR (Barra Lateral) --- */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF; /* Sidebar Branca Limpa */
            border-right: 1px solid #E2E8F0; /* Borda sutil */
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: #0F172A !important;
        }

        /* Links de Navegação */
        div[data-testid="stSidebarNav"] a {
            color: #475569 !important; /* Texto cinza médio */
            font-weight: 500;
            border-radius: 6px;
            margin-bottom: 2px;
            transition: all 0.2s;
        }
        div[data-testid="stSidebarNav"] a:hover {
            background-color: #F0FDF4 !important; /* Fundo verde muito claro */
            color: #166534 !important; /* Texto verde escuro */
        }

        /* --- CARDS (KPIs) --- */
        /* Cartões brancos flutuando sobre o fundo cinza */
        .ui-card {
            background-color: #FFFFFF; 
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); 
            border: 1px solid #E2E8F0;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .ui-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            border-color: #2E7D32; 
        }

        .card-title {
            color: #64748B; /* Cinza slate para rótulos */
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }

        .card-value {
            color: #0F172A; /* Texto principal forte */
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.2;
        }

        .card-icon {
            float: right;
        }

        /* Estilo para SVG dentro do card */
        .card-icon svg {
            width: 32px;
            height: 32px;
            opacity: 0.8;
        }

        /* --- BOTÕES --- */
        .stButton button {
            border-radius: 8px;
            font-weight: 600;
            border: none;
            transition: all 0.2s;
            padding: 0.5rem 1rem;
        }
        /* Botão Primário (Verde Profissional) */
        .stButton button[kind="primary"] {
            background-color: #16A34A; /* Verde Vibrante */
            color: white;
            box-shadow: 0 2px 4px rgba(22, 163, 74, 0.2);
        }
        .stButton button[kind="primary"]:hover {
            background-color: #15803D; /* Verde Escuro no Hover */
            box-shadow: 0 4px 8px rgba(22, 163, 74, 0.3);
            transform: scale(1.01);
        }
        /* Botão Secundário */
        .stButton button[kind="secondary"] {
            background-color: #FFFFFF;
            color: #334155;
            border: 1px solid #CBD5E1;
        }
        .stButton button[kind="secondary"]:hover {
            background-color: #F8FAFC;
            border-color: #94A3B8;
            color: #0F172A;
        }

        /* --- INPUTS & SELECTBOXES --- */
        /* Fundo branco limpo com bordas cinzas */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input, .stTextArea textarea {
            background-color: #FFFFFF !important;
            color: #1E293B !important;
            border: 1px solid #CBD5E1 !important;
            border-radius: 8px;
        }
        /* Foco */
        .stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within, .stTextArea textarea:focus {
            border-color: #2E7D32 !important;
            box-shadow: 0 0 0 2px rgba(46, 125, 50, 0.2) !important;
        }
        /* Labels */
        .stTextInput label, .stSelectbox label, .stNumberInput label, .stTextArea label, .stDateInput label {
            color: #475569 !important;
            font-weight: 500;
        }

        /* --- TABELAS (Dataframe) --- */
        [data-testid="stDataFrame"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        [data-testid="stDataFrame"] div[class*="css"] {
            color: #334155; 
        }
        /* Cabeçalho da Tabela */
        [data-testid="stDataFrame"] thead th {
            background-color: #F8FAFC !important;
            color: #64748B !important;
            font-weight: 600;
        }

        /* --- EXPANDER --- */
        .streamlit-expanderHeader {
            background-color: #FFFFFF;
            border-radius: 8px;
            border: 1px solid #E2E8F0;
            color: #1E293B;
        }

        /* --- TOAST --- */
        div[data-testid="stToast"] {
            background-color: #FFFFFF;
            color: #1E293B;
            border-left: 5px solid #2E7D32;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }

        /* --- HEADER & DIVISORES --- */
        h1, h2, h3 {
            color: #0F172A !important;
            font-weight: 700;
        }
        .stMarkdown hr {
            border-top: 1px solid #E2E8F0;
        }

        /* Badge de Alerta (Pulsante) */
        .pulse-badge {
            background-color: #FEF2F2;
            color: #DC2626;
            border: 1px solid #FECACA;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: 700;
            animation: pulse-red 2s infinite;
            vertical-align: middle;
            margin-left: 8px;
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
    # Se a cor for muito clara ou transparente, usa um cinza padrão
    if cor_borda in ["#ddd", "#E0E0E0", "transparent", "white"]:
        cor_borda = "#94A3B8"

    # Verifica se é SVG ou Emoji
    if icone.strip().startswith("<svg"):
        # É SVG: usa direto
        icon_html = icone
    else:
        # É Emoji: aplica estilo de fonte/cor
        icon_html = f'<span style="font-size: 1.8rem; color: {cor_borda}; filter: brightness(0.9);">{icone}</span>'

    html = f"""
    <div class="ui-card" style="border-left: 4px solid {cor_borda};">
        <div>
            <div class="card-icon">{icon_html}</div>
            <div class="card-title">{titulo}</div>
            <div class="card-value">{valor}</div>
            <div style="font-size: 0.85em; color: #64748B; margin-top: 5px;">{subtexto}</div>
        </div>
    </div>
    """
    col.markdown(html, unsafe_allow_html=True)