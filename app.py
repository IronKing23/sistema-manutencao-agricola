import streamlit as st
import os
import sys
import base64

# --- 1. CONFIGURAÇÃO DE CAMINHOS ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

# --- 2. IMPORTAÇÕES DE MÓDULOS INTERNOS ---
import autenticacao
from utils_ui import load_custom_css
from utils_icons import get_icon

# from database_schema import inicializar_banco

# --- 3. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Sistema Agrícola",
    page_icon="🚜",
    initial_sidebar_state="expanded"
)

# --- 4. CARREGAMENTO DE ESTILOS E UI/UX SEGURO ---
load_custom_css()

st.markdown("""
    <style>
        /* =========================================
           CSS SEGURO PARA UI/UX DA NAVEGAÇÃO
           ========================================= */

        /* 1. Limpeza da Interface Padrão */
        header[data-testid="stHeader"] { background-color: transparent !important; z-index: 1; }
        footer { visibility: hidden; } 
        .block-container { padding-top: 3rem !important; }

        /* 2. Estilização da Sidebar (Fundo e Bordas) */
        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(150, 150, 150, 0.15);
            background-color: var(--bg-color);
        }

        /* Remove o padding excessivo do topo da sidebar nativa */
        [data-testid="stSidebarUserContent"] {
            padding-top: 0.5rem !important;
        }

        /* =========================================
           3. EFEITO TÁTIL NO MENU (COMPACTO / HIGH DENSITY)
           ========================================= */
        /* Links do Menu - Extremamente reduzidos */
        [data-testid="stSidebarNav"] a {
            border-radius: 6px !important;
            margin: 1px 12px !important; /* Margem minúscula */
            padding: 4px 10px !important; /* Padding muito mais fino */
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            border: 1px solid transparent !important;
            background-color: transparent !important;
            min-height: 28px !important; /* Força os itens a serem menores na altura */
        }

        /* Tamanho da Fonte dos Links (Ajuste de Proporção para Compacto) */
        [data-testid="stSidebarNav"] a span {
            font-size: 0.75rem !important;
        }

        /* Ajuste do tamanho do ícone nativo do menu */
        [data-testid="stSidebarNav"] a svg {
            width: 14px !important;
            height: 14px !important;
            margin-right: 4px !important;
        }

        /* Hover (Rato em cima) */
        [data-testid="stSidebarNav"] a:hover {
            background-color: rgba(150, 150, 150, 0.06) !important;
            transform: translateX(3px) !important;
            border-color: rgba(150, 150, 150, 0.1) !important;
        }

        /* Active (Clique) */
        [data-testid="stSidebarNav"] a:active {
            transform: scale(0.97) !important; 
            background-color: rgba(150, 150, 150, 0.12) !important;
        }

        /* Aba Selecionada (Pasta Aberta) */
        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background: linear-gradient(90deg, rgba(22, 163, 74, 0.1) 0%, transparent 100%) !important;
            border-left: 3px solid var(--primary-color) !important;
            border-radius: 3px 6px 6px 3px !important;
            font-weight: 600 !important;
        }

        /* Títulos das Categorias (Dashboards, Cadastros...) */
        [data-testid="stSidebarNav"] ul li div {
            font-size: 0.6rem !important; /* Muito pequeno, apenas como guia visual */
            text-transform: uppercase !important;
            letter-spacing: 1px !important;
            color: var(--text-secondary) !important;
            font-weight: 800 !important;
            margin-top: 12px !important; /* Espaço reduzido entre categorias */
            margin-bottom: 2px !important;
            padding-left: 16px !important;
            opacity: 0.7;
        }

        /* =========================================
           4. CARTÃO DE PERFIL DO UTILIZADOR (COMPACTO)
           ========================================= */
        .user-profile-card {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 12px; /* Muito mais apertado */
            background: linear-gradient(145deg, rgba(150,150,150,0.03) 0%, rgba(150,150,150,0.01) 100%);
            border: 1px solid rgba(150, 150, 150, 0.15);
            border-radius: 8px;
            margin: 0px 12px 10px 12px;
            transition: all 0.3s ease;
        }
        .user-profile-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border-color: rgba(22, 163, 74, 0.3);
        }
        .avatar-circle {
            width: 28px; /* Bolinha bem pequena */
            height: 28px;
            min-width: 28px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary-color), #22C55E);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 11px;
            position: relative;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .online-indicator {
            position: absolute;
            bottom: 0px;
            right: -2px;
            width: 8px;
            height: 8px;
            background-color: #10B981;
            border: 2px solid var(--sidebar-bg, #FFFFFF);
            border-radius: 50%;
        }
        .user-info {
            display: flex;
            flex-direction: column;
            line-height: 1.1;
            overflow: hidden;
        }
        .user-name {
            color: var(--text-color);
            font-size: 12px; /* Nome menor */
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .user-role {
            color: var(--text-secondary);
            font-size: 9px; /* Status minúsculo */
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 2px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 5. VERIFICAÇÃO DE SEGURANÇA ---
if not autenticacao.check_password():
    st.stop()


# --- 6. DEFINIÇÃO DA ESTRUTURA DE NAVEGAÇÃO ---
def criar_pagina(arquivo, titulo, icone, default=False):
    if os.path.exists(arquivo):
        return st.Page(arquivo, title=titulo, icon=icone, default=default)
    return None


paginas_config = [
    # Dashboards
    ("pages/0_Inicio.py", "Início", "🏠", True),
    ("pages/1_Painel_Principal.py", "Visão Geral", "📊", False),
    ("pages/15_Indicadores_KPI.py", "Indicadores (MTBF)", "📈", False),
    ("pages/17_Eficiencia_Apontamentos.py", "Eficiência (PIMS/RH)", "⏱️", False),
    ("pages/7_Historico_Maquina.py", "Prontuário Máquina", "🚜", False),
    ("pages/10_Mapa_Atendimentos.py", "Mapa Geográfico", "🗺️", False),
    ("pages/18_relatorio_gastos.py", "Relatório de Custos", "💰", False),

    # Operacional
    ("pages/5_Nova_Ordem_Servico.py", "Nova O.S.", "📝", False),
    ("pages/6_Gerenciar_Atendimento.py", "Gerenciar O.S.", "🔄", False),
    ("pages/11_Quadro_Avisos.py", "Mural de Avisos", "📌", False),
    ("pages/13_Comunicacao.py", "Central WhatsApp", "📱", False),

    # Cadastros
    ("pages/2_Cadastro_Equipamentos.py", "Equipamentos", "🚛", False),
    ("pages/3_Cadastro_Funcionarios.py", "Funcionários", "👷", False),
    ("pages/4_Cadastro_Operacoes.py", "Tipos de Operação", "⚙️", False),
    ("pages/14_Cadastro_Areas.py", "Áreas / Talhões", "📍", False),

    # Admin
    ("pages/9_Gestao_Usuarios.py", "Usuários", "🔐", False),
    ("pages/12_Auditoria.py", "Auditoria", "🕵️", False),
    ("pages/8_Backup_Seguranca.py", "Backup", "💾", False),
]

lista_paginas_validas = []
for arq, tit, ico, df in paginas_config:
    pg = criar_pagina(arq, tit, ico, df)
    if pg: lista_paginas_validas.append(pg)

if not lista_paginas_validas:
    st.error("Erro crítico: Nenhuma página encontrada. Verifique a pasta 'pages'.")
    st.stop()

pg = st.navigation({
    "Dashboards": lista_paginas_validas[:7],
    "Operacional": lista_paginas_validas[7:11],
    "Cadastros": lista_paginas_validas[11:15],
    "Sistema": lista_paginas_validas[15:]
})


# --- FUNÇÃO AUXILIAR PARA IMAGEM EM BASE64 ---
def get_image_base64(path):
    try:
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None


# --- 7. BARRA LATERAL (SIDEBAR) FLUXO NATIVO E ESTÁVEL ---
with st.sidebar:
    # --- 1. CABEÇALHO DA MARCA (COMPACTO) ---
    logo_path = os.path.join(os.path.dirname(__file__), "logo_cedro.png")
    b64_logo = get_image_base64(logo_path)

    if b64_logo:
        # Se a imagem existir, usa-a nativamente e ajusta proporções BEM menores
        logo_render = f'<img src="data:image/png;base64,{b64_logo}" style="width: 32px; height: 32px; object-fit: contain; border-radius: 4px;">'
        bg_style = "background: transparent; padding: 0px;"
    else:
        # Fallback: Se não achar a imagem, usa o ícone de trator
        try:
            logo_svg = get_icon("tractor", color="white", size="20")
            logo_render = logo_svg.replace('\n', '').strip() if logo_svg else "🚜"
        except:
            logo_render = "🚜"
        bg_style = "background: linear-gradient(135deg, var(--primary-color), #4CAF50); padding: 6px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); color: white;"

    st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding-left: 12px; margin-top: -10px;">
            <div style="{bg_style} display: flex; align-items: center; justify-content: center;">
                {logo_render}
            </div>
            <div style="line-height: 1.1;">
                <h1 style="color: var(--text-color); margin: 0; font-size: 15px; font-weight: 800; letter-spacing: -0.5px;">Sistema Cedro</h1>
                <span style="color: var(--text-secondary); font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">Gestão de Frotas</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- 2. PERFIL DE UTILIZADOR DINÂMICO (CARTÃO SUPER COMPACTO) ---
    nome_usuario = st.session_state.get('user_nome', 'Usuário')
    iniciais = "".join([n[0] for n in nome_usuario.split()[:2]]).upper()[:2]
    primeiro_nome = nome_usuario.split()[0]

    st.markdown(f"""
        <div class="user-profile-card">
            <div class="avatar-circle">
                {iniciais}
                <div class="online-indicator"></div>
            </div>
            <div class="user-info">
                <span class="user-name">{primeiro_nome}</span>
                <span class="user-role">Administrador</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- 8. EXECUÇÃO DA NAVEGAÇÃO ---
# O menu lateral aparecerá magicamente AQUI, logo abaixo do cartão de utilizador compacto.
pg.run()