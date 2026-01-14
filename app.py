import streamlit as st
import os
import sys

# --- 1. CONFIGURAÇÃO DE CAMINHOS ---
# Adiciona o diretório atual ao path para garantir que importações funcionem corretamente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

# --- 2. IMPORTAÇÕES DE MÓDULOS INTERNOS ---
import autenticacao
from utils_ui import load_custom_css
from utils_icons import get_icon

# --- 3. CONFIGURAÇÃO DA PÁGINA (Deve ser o primeiro comando Streamlit) ---
st.set_page_config(
    layout="wide",
    page_title="Sistema Agrícola",
    page_icon="🚜",
    initial_sidebar_state="expanded"
)

# --- 4. CARREGAMENTO DE ESTILOS ---
# Aplica o tema 'Soft Light' definido em utils_ui.py
load_custom_css()

# --- 5. VERIFICAÇÃO DE SEGURANÇA ---
# Se o usuário não estiver logado, interrompe a execução e mostra o login
if not autenticacao.check_password():
    st.stop()


# --- 6. DEFINIÇÃO DA ESTRUTURA DE NAVEGAÇÃO ---
def criar_pagina(arquivo, titulo, icone, default=False):
    """Cria um objeto st.Page apenas se o arquivo existir."""
    if os.path.exists(arquivo):
        return st.Page(arquivo, title=titulo, icon=icone, default=default)
    return None


# Lista mestre de páginas (Caminho, Título no Menu, Ícone, É padrão?)
paginas_config = [
    # --> Dashboards & Visão Geral
    ("pages/0_Inicio.py", "Início", "🏠", True),
    ("pages/1_Painel_Principal.py", "Visão Geral", "📊", False),
    ("pages/15_Indicadores_KPI.py", "Indicadores (MTBF)", "📈", False),
    ("pages/7_Historico_Maquina.py", "Prontuário Máquina", "🚜", False),
    ("pages/10_Mapa_Atendimentos.py", "Mapa Geográfico", "🗺️", False),

    # --> Operacional (Dia a Dia)
    ("pages/5_Nova_Ordem_Servico.py", "Nova O.S.", "📝", False),
    ("pages/6_Gerenciar_Atendimento.py", "Gerenciar O.S.", "🔄", False),
    ("pages/11_Quadro_Avisos.py", "Mural de Avisos", "📌", False),
    ("pages/13_Comunicacao.py", "Central WhatsApp", "📱", False),

    # --> Cadastros (Base de Dados)
    ("pages/2_Cadastro_Equipamentos.py", "Equipamentos", "🚛", False),
    ("pages/3_Cadastro_Funcionarios.py", "Funcionários", "👷", False),
    ("pages/4_Cadastro_Operacoes.py", "Tipos de Operação", "⚙️", False),
    ("pages/14_Cadastro_Areas.py", "Áreas / Talhões", "📍", False),

    # --> Administração & Sistema
    ("pages/9_Gestao_Usuarios.py", "Usuários", "🔐", False),
    ("pages/12_Auditoria.py", "Auditoria", "🕵️", False),
    ("pages/8_Backup_Seguranca.py", "Backup", "💾", False),
]

# Processa a lista e cria os objetos de página
lista_paginas_validas = []
for arq, tit, ico, df in paginas_config:
    pg = criar_pagina(arq, tit, ico, df)
    if pg:
        lista_paginas_validas.append(pg)

if not lista_paginas_validas:
    st.error("Erro crítico: Nenhuma página encontrada. Verifique a pasta 'pages'.")
    st.stop()

# Configura a navegação agrupada por seções
pg = st.navigation({
    "Dashboards": lista_paginas_validas[:5],
    "Operacional": lista_paginas_validas[5:9],
    "Cadastros": lista_paginas_validas[9:13],
    "Sistema": lista_paginas_validas[13:]
})

# --- 7. BARRA LATERAL (SIDEBAR) PERSONALIZADA ---
with st.sidebar:
    # Cabeçalho com Logo SVG e Título
    try:
        logo_svg = get_icon("tractor", color="#2E7D32", size="48")
    except:
        logo_svg = "🚜"  # Fallback caso o ícone falhe

    st.markdown(f"""
    <div style="text-align: center; padding: 20px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 15px;">
        <div style="margin-bottom: 8px;">{logo_svg}</div>
        <h2 style="color: #0F172A; margin: 0; font-size: 18px; font-weight: 700;">Controle Agrícola</h2>
        <p style="color: #64748B; font-size: 11px; margin: 0; text-transform: uppercase; letter-spacing: 1px;">Gestão de Frotas</p>
    </div>
    """, unsafe_allow_html=True)

    # Espaçamento
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    # Botão Sair
    if st.button("Sair do Sistema", use_container_width=True):
        try:
            autenticacao.get_manager().delete("manutencao_user")
        except:
            pass

        # Limpa toda a sessão
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.rerun()

    # Informações do Usuário no Rodapé
    if "user_nome" in st.session_state:
        st.markdown(f"""
        <div style='text-align: center; color: #64748B; font-size: 12px; margin-top: 15px; border-top: 1px solid #E2E8F0; padding-top: 10px;'>
            Usuário: <b style='color: #1E293B;'>{st.session_state['user_nome']}</b>
        </div>
        """, unsafe_allow_html=True)

# --- 8. EXECUÇÃO PRINCIPAL ---
pg.run()