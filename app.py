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

# from database_schema import inicializar_banco # Descomente se tiver o arquivo

# --- 3. CONFIGURAÇÃO DA PÁGINA (Primeiro comando obrigatório) ---
st.set_page_config(
    layout="wide",
    page_title="Sistema Agrícola",
    page_icon="🚜",
    initial_sidebar_state="expanded"
)

# --- 4. CARREGAMENTO DE ESTILOS E CORREÇÕES VISUAIS ---
# inicializar_banco() # Descomente se tiver o arquivo
load_custom_css()

# CSS Extra para corrigir o cabeçalho branco e ajustes finos
st.markdown("""
    <style>
        /* Torna o cabeçalho padrão do Streamlit transparente */
        header[data-testid="stHeader"] {
            background-color: transparent !important;
            z-index: 1;
        }

        /* Ajusta o espaçamento do topo para não sobrepor o cabeçalho */
        .block-container {
            padding-top: 3.5rem !important; 
        }

        /* Garante que o menu hambúrguer (três pontinhos) seja visível */
        button[kind="header"] {
            background-color: transparent !important;
            color: var(--text-color) !important;
        }

        /* Remove padding excessivo do topo da sidebar */
        [data-testid="stSidebarUserContent"] {
            padding-top: 1.5rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- 5. VERIFICAÇÃO DE SEGURANÇA ---
if not autenticacao.check_password():
    st.stop()


# --- 6. DEFINIÇÃO DA ESTRUTURA DE NAVEGAÇÃO ---
def criar_pagina(arquivo, titulo, icone, default=False):
    """Cria um objeto st.Page apenas se o arquivo existir."""
    if os.path.exists(arquivo):
        return st.Page(arquivo, title=titulo, icon=icone, default=default)
    return None


# Lista de páginas do sistema
paginas_config = [
    # Dashboards (Agora com 7 páginas)
    ("pages/0_Inicio.py", "Início", "🏠", True),
    ("pages/1_Painel_Principal.py", "Visão Geral", "📊", False),
    ("pages/15_Indicadores_KPI.py", "Indicadores (MTBF)", "📈", False),
    ("pages/17_Eficiencia_Apontamentos.py", "Eficiência (PIMS/RH)", "⏱️", False),
    ("pages/7_Historico_Maquina.py", "Prontuário Máquina", "🚜", False),
    ("pages/10_Mapa_Atendimentos.py", "Mapa Geográfico", "🗺️", False),
    ("pages/18_relatorio_gastos.py", "Relatório de Custos", "💰", False),  # <--- VINCULAMOS AQUI

    # Operacional (4 páginas)
    ("pages/5_Nova_Ordem_Servico.py", "Nova O.S.", "📝", False),
    ("pages/6_Gerenciar_Atendimento.py", "Gerenciar O.S.", "🔄", False),
    ("pages/11_Quadro_Avisos.py", "Mural de Avisos", "📌", False),
    ("pages/13_Comunicacao.py", "Central WhatsApp", "📱", False),

    # Cadastros (4 páginas)
    ("pages/2_Cadastro_Equipamentos.py", "Equipamentos", "🚛", False),
    ("pages/3_Cadastro_Funcionarios.py", "Funcionários", "👷", False),
    ("pages/4_Cadastro_Operacoes.py", "Tipos de Operação", "⚙️", False),
    ("pages/14_Cadastro_Areas.py", "Áreas / Talhões", "📍", False),

    # Admin (3 páginas)
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

# Configura a navegação (Ajustei os índices de fatiamento para a nova contagem de páginas)
pg = st.navigation({
    "Dashboards": lista_paginas_validas[:7],  # Do índice 0 ao 6
    "Operacional": lista_paginas_validas[7:11],  # Do índice 7 ao 10
    "Cadastros": lista_paginas_validas[11:15],  # Do índice 11 ao 14
    "Sistema": lista_paginas_validas[15:]  # Do índice 15 em diante
})

# --- 7. BARRA LATERAL (SIDEBAR) ESTILIZADA ---
with st.sidebar:
    # --- CABEÇALHO DINÂMICO ---
    try:
        logo_svg = get_icon("tractor", color="var(--primary-color)", size="54")
    except:
        logo_svg = "🚜"

    st.markdown(f"""<div style="text-align: center; padding: 0 0 20px 0; border-bottom: 1px solid var(--border-color); margin-bottom: 20px;">
<div style="margin-bottom: 12px; display: inline-block; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1)); transition: transform 0.3s ease;" onmouseover="this.style.transform='scale(1.1) rotate(-5deg)'" onmouseout="this.style.transform='scale(1) rotate(0deg)'">
{logo_svg}
</div>
<h1 style="color: var(--text-color) !important; margin: 0; font-size: 20px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.2;">
Controle<br>Agrícola
</h1>
<p style="color: var(--text-secondary); font-size: 10px; margin: 8px 0 0 0; text-transform: uppercase; letter-spacing: 2px; font-weight: 600; opacity: 0.8;">
Gestão de Frotas v2.0
</p>
</div>""", unsafe_allow_html=True)

    # Botão Sair
    if st.button("Sair do Sistema", use_container_width=True):
        try:
            autenticacao.get_manager().delete("manutencao_user")
        except:
            pass
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # --- RODAPÉ DE PERFIL CORRIGIDO ---
    if "user_nome" in st.session_state:
        nome = st.session_state['user_nome']
        iniciais = "".join([n[0] for n in nome.split()[:2]]).upper()

        st.markdown(f"""<div style='margin-top: 30px; border-top: 1px solid var(--border-color); padding-top: 20px; display: flex; align-items: center; gap: 15px;'>
<div style='width: 42px; height: 42px; border-radius: 50%; background-color: var(--hover-bg); color: var(--text-color); display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 1px solid var(--border-color);'>
{iniciais}
</div>
<div style='line-height: 1.2;'>
<span style='color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; font-weight: 500;'>Usuário</span><br>
<span style='color: var(--text-color); font-size: 14px; font-weight: 600;'>{nome}</span>
</div>
</div>""", unsafe_allow_html=True)

# --- 8. EXECUÇÃO ---
pg.run()