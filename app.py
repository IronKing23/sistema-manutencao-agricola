import streamlit as st
import streamlit.components.v1 as components
import os
import sys

# --- BLINDAGEM DE CAMINHO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Importa módulos internos
import autenticacao
from utils_ui import load_custom_css  # Importa estilos globais
from utils_icons import get_icon  # <--- NOVO IMPORT DOS ÍCONES

# --- 1. CONFIGURAÇÃO INICIAL (Deve ser a primeira linha) ---
st.set_page_config(
    layout="wide",
    page_title="Sistema Agrícola",
    page_icon="🚜",
    initial_sidebar_state="expanded"
)

# --- 2. CARREGA ESTILOS GLOBAIS ---
load_custom_css()

# --- 3. VERIFICAÇÃO DE LOGIN ---
if not autenticacao.check_password():
    st.stop()


# --- 4. DEFINIÇÃO DAS PÁGINAS ---
def criar_pagina(arquivo, titulo, icone, default=False):
    if os.path.exists(arquivo):
        return st.Page(arquivo, title=titulo, icon=icone, default=default)
    return None


# Estrutura do Menu
paginas_brutas = [
    # Dashboards
    ("pages/0_Inicio.py", "Início", "🏠", True),
    ("pages/1_Painel_Principal.py", "Visão Geral", "📊", False),
    ("pages/15_Indicadores_KPI.py", "Indicadores (MTBF)", "📈", False),
    ("pages/7_Historico_Maquina.py", "Prontuário Máquina", "🚜", False),
    ("pages/10_Mapa_Atendimentos.py", "Mapa Geográfico", "🗺️", False),

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

lista_paginas = []
for arq, tit, ico, df in paginas_brutas:
    pg = criar_pagina(arq, tit, ico, df)
    if pg: lista_paginas.append(pg)

# --- 5. NAVEGAÇÃO E SIDEBAR ---
if not lista_paginas:
    st.error("Erro crítico: Páginas não encontradas.")
    st.stop()

# Configuração da Navegação
pg = st.navigation({
    "Dashboards": lista_paginas[:5],
    "Operacional": lista_paginas[5:9],
    "Cadastros": lista_paginas[9:13],
    "Sistema": lista_paginas[13:]
})

with st.sidebar:
    # --- CABEÇALHO COM ÍCONE SVG ---
    # Gera o ícone do trator em verde (#2E7D32) e tamanho grande (48px)
    logo_svg = get_icon("tractor", color="#2E7D32", size="48")

    st.markdown(f"""
    <div style="text-align: center; padding: 20px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 15px;">
        <div style="margin-bottom: 8px;">{logo_svg}</div>
        <h2 style="color: #0F172A; margin: 0; font-size: 18px; font-weight: 700;">Controle Agrícola</h2>
        <p style="color: #64748B; font-size: 11px; margin: 0; text-transform: uppercase; letter-spacing: 1px;">Gestão de Frotas</p>
    </div>
    """, unsafe_allow_html=True)

    # Botão Sair Estilizado
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    if st.button("Sair do Sistema", use_container_width=True):
        try:
            autenticacao.get_manager().delete("manutencao_user")
        except:
            pass
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    if "user_nome" in st.session_state:
        st.markdown(f"""
        <div style='text-align: center; color: #64748B; font-size: 12px; margin-top: 10px;'>
            Usuário: <b style='color: #1E293B;'>{st.session_state['user_nome']}</b>
        </div>
        """, unsafe_allow_html=True)

pg.run()