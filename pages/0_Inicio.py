import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from utils_ui import load_custom_css
from utils_icons import get_icon

# --- 1. CONFIGURAÇÃO VISUAL (PREMIUM & TACTILE) ---
load_custom_css()

st.markdown("""
<style>
    /* REMOVE ESPAÇOS DO TOPO */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
    }

    /* --- ESTILO DOS CARDS (CONTAINERS) --- */
    /* Container Base */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px;
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        overflow: hidden;
        position: relative;
    }

    /* Efeito Tactil no Hover (Levantar + Sombra Profunda) */
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        border-color: var(--primary-color);
    }

    /* Animação do Ícone no Hover do Card */
    [data-testid="stVerticalBlockBorderWrapper"]:hover .kpi-icon-box svg {
        transform: scale(1.15) rotate(5deg);
        filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));
    }

    /* --- TIPOGRAFIA DE IMPACTO --- */
    .kpi-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 15px;
    }

    .kpi-label {
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-secondary);
        margin-bottom: 4px;
        display: block;
    }

    .kpi-status-text {
        font-size: 0.75rem;
        font-weight: 500;
        opacity: 0.8;
    }

    .kpi-icon-box svg {
        width: 42px; /* Ícone Grande */
        height: 42px;
        transition: transform 0.4s ease;
    }

    .kpi-value {
        font-size: 3.5rem;
        font-weight: 800;
        color: var(--text-color);
        line-height: 1;
        margin-bottom: 20px;
        font-variant-numeric: tabular-nums;
        letter-spacing: -1px;
    }

    /* Cores Vibrantes (Classes Utilitárias) */
    .color-red { color: #DC2626; }
    .color-blue { color: #2563EB; }
    .color-orange { color: #D97706; }
    .color-green { color: #16A34A; }
    .color-gray { color: #64748B; }

    /* --- BOTÕES DE AÇÃO INTERNA --- */
    /* Estiliza o botão secundário dentro do container para parecer um link de ação */
    div[data-testid="stVerticalBlock"] button[kind="secondary"] {
        width: 100%;
        border: 1px solid var(--border-color);
        background-color: transparent;
        color: var(--text-secondary);
        font-weight: 600;
        font-size: 0.9rem;
        border-radius: 8px;
        transition: all 0.2s;
    }
    div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
        background-color: var(--hover-bg);
        border-color: var(--primary-color);
        color: var(--primary-color);
    }

    /* --- BARRA DE STATUS (Banner) --- */
    .status-banner {
        padding: 12px 20px;
        border-radius: 12px;
        margin-bottom: 30px;
        display: flex;
        align-items: center;
        gap: 12px;
        font-weight: 600;
        border: 1px solid transparent;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    }
    .status-ok { background-color: #F0FDF4; color: #166534; border-color: #BBF7D0; }
    .status-critico { background-color: #FEF2F2; color: #991B1B; border-color: #FECACA; animation: pulse-border 2s infinite; }

    @keyframes pulse-border {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
        70% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }

    /* Dark Mode Overrides */
    @media (prefers-color-scheme: dark) {
        .color-red { color: #F87171; }
        .color-blue { color: #60A5FA; }
        .color-orange { color: #FBBF24; }
        .color-green { color: #4ADE80; }
        .color-gray { color: #94A3B8; }

        .status-ok { background-color: #064E3B; color: #D1FAE5; border-color: #065F46; }
        .status-critico { background-color: #450A0A; color: #FECACA; border-color: #7F1D1D; }

        div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
            background-color: #1E293B;
        }
    }
</style>
""", unsafe_allow_html=True)


# --- 2. DADOS (SEM CACHE) ---
def get_data():
    conn = get_db_connection()
    try:
        # Contadores
        q_aberta = conn.execute("SELECT COUNT(*) FROM ordens_servico WHERE status != 'Concluído'").fetchone()[0]
        q_parada = conn.execute(
            "SELECT COUNT(*) FROM ordens_servico WHERE status != 'Concluído' AND maquina_parada = 1").fetchone()[0]
        q_recados = conn.execute("SELECT COUNT(*) FROM recados").fetchone()[0]

        # Dataframes para os Popups
        df_ab = pd.read_sql("""
            SELECT os.id, e.frota, os.descricao, os.data_hora, os.prioridade, os.status 
            FROM ordens_servico os JOIN equipamentos e ON os.equipamento_id = e.id 
            WHERE os.status != 'Concluído' ORDER BY os.prioridade = 'Alta' DESC, os.data_hora DESC LIMIT 20
        """, conn)

        df_pa = pd.read_sql("""
            SELECT os.id, e.frota, os.descricao, os.data_hora 
            FROM ordens_servico os JOIN equipamentos e ON os.equipamento_id = e.id 
            WHERE os.status != 'Concluído' AND os.maquina_parada = 1 ORDER BY os.data_hora DESC
        """, conn)

        return q_aberta, q_parada, q_recados, df_ab, df_pa
    finally:
        conn.close()


q_aberta, q_parada, q_recados, df_aberta, df_parada = get_data()


# --- 3. DIALOGS (POPUPS) ---
@st.dialog("📋 Pendências do Dia", width="large")
def popup_pendencias():
    if df_aberta.empty:
        st.success("Tudo em dia! Nenhuma pendência.")
    else:
        st.dataframe(
            df_aberta, use_container_width=True, hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("#", width="small"),
                "frota": "Frota",
                "prioridade": "Prio.",
                "status": "Status",
                "data_hora": st.column_config.DatetimeColumn("Desde", format="DD/MM HH:mm"),
                "descricao": "Detalhe"
            }
        )
        c1, c2 = st.columns([1, 2])
        if c2.button("Ver no Painel Geral 📊", type="primary", use_container_width=True):
            st.switch_page("pages/1_Painel_Principal.py")
        if c1.button("Fechar", use_container_width=True):
            st.rerun()


@st.dialog("🚨 Máquinas Paradas", width="large")
def popup_paradas():
    if df_parada.empty:
        st.success("Frota 100% Operacional!")
    else:
        st.error(f"{len(df_parada)} equipamentos parados impactando a operação.")
        st.dataframe(
            df_parada, use_container_width=True, hide_index=True,
            column_config={
                "id": "#",
                "frota": "Máquina",
                "data_hora": st.column_config.DatetimeColumn("Parada Desde", format="DD/MM HH:mm"),
                "descricao": "Motivo"
            }
        )
        if st.button("Ver no Painel Geral 📊", type="primary", use_container_width=True):
            st.switch_page("pages/1_Painel_Principal.py")


# --- 4. HEADER ---
user_first_name = st.session_state.get('user_nome', 'Usuário').split()[0]
current_date = datetime.now().strftime('%d/%m/%Y')

c_head1, c_head2 = st.columns([3, 1])
with c_head1:
    st.markdown(f"<h1 style='margin-bottom:0px;'>Olá, {user_first_name}</h1>", unsafe_allow_html=True)
    st.caption(f"Painel de Controle • {current_date}")

# --- BARRA DE STATUS (BANNER) ---
if q_parada > 0:
    st.markdown(f"""
    <div class="status-banner status-critico">
        <span style="font-size: 1.2rem;">🚨</span>
        <span>ATENÇÃO: Operação com {q_parada} Máquinas Paradas</span>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="status-banner status-ok">
        <span style="font-size: 1.2rem;">✅</span>
        <span>Operação Saudável: Nenhuma Máquina Parada</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- 5. CARDS DE INDICADORES (TOPO) ---
# Usamos Containers para criar o visual "Card" completo com HTML interno
c1, c2, c3 = st.columns(3)

# CARD 1: PARADAS
with c1:
    with st.container(border=True):
        # Definição de Cores e Ícones
        icon_svg = get_icon("stop", "#EF4444", "42").replace('\n', '')
        val_color = "color-red" if q_parada > 0 else "color-gray"
        status_txt = "Impacto Crítico" if q_parada > 0 else "Operação Normal"

        # HTML do Conteúdo
        st.markdown(f"""
        <div class="kpi-header">
            <div>
                <span class="kpi-label">Máquinas Paradas</span>
                <span class="kpi-status-text {val_color}">{status_txt}</span>
            </div>
            <div class="kpi-icon-box">{icon_svg}</div>
        </div>
        <div class="kpi-value {val_color}">{q_parada}</div>
        """, unsafe_allow_html=True)

        # Botão de Ação
        btn_label = "Ver Detalhes" if q_parada > 0 else "Sem ocorrências"
        if st.button(btn_label, key="btn_parada", use_container_width=True, disabled=(q_parada == 0)):
            popup_paradas()

# CARD 2: PENDÊNCIAS
with c2:
    with st.container(border=True):
        icon_svg = get_icon("dashboard", "#3B82F6", "42").replace('\n', '')

        st.markdown(f"""
        <div class="kpi-header">
            <div>
                <span class="kpi-label">Pendências Totais</span>
                <span class="kpi-status-text color-blue">Ordens em aberto</span>
            </div>
            <div class="kpi-icon-box">{icon_svg}</div>
        </div>
        <div class="kpi-value color-blue">{q_aberta}</div>
        """, unsafe_allow_html=True)

        if st.button("Listar Ordens", key="btn_pend", use_container_width=True):
            popup_pendencias()

# CARD 3: MURAL
with c3:
    with st.container(border=True):
        icon_svg = get_icon("pin", "#F59E0B", "42").replace('\n', '')
        color_cls = "color-orange" if q_recados > 0 else "color-gray"

        st.markdown(f"""
        <div class="kpi-header">
            <div>
                <span class="kpi-label">Mural de Avisos</span>
                <span class="kpi-status-text {color_cls}">Novos recados</span>
            </div>
            <div class="kpi-icon-box">{icon_svg}</div>
        </div>
        <div class="kpi-value {color_cls}">{q_recados}</div>
        """, unsafe_allow_html=True)

        if st.button("Ler Mural", key="btn_mural", use_container_width=True):
            st.switch_page("pages/11_Quadro_Avisos.py")

st.markdown("<br><br>", unsafe_allow_html=True)

# --- 6. CARDS DE AÇÃO (BAIXO - Atalhos) ---
st.markdown("##### ⚡ Ações Rápidas")
bt1, bt2, bt3, bt4 = st.columns(4)

with bt1:
    with st.container(border=True):
        if st.button("📝 Criar Ordem", use_container_width=True, type="primary"):
            st.switch_page("pages/5_Nova_Ordem_Servico.py")
        st.caption("Abrir chamado para frota")

with bt2:
    with st.container(border=True):
        if st.button("🔄 Gerenciar", use_container_width=True):
            st.switch_page("pages/6_Gerenciar_Atendimento.py")
        st.caption("Editar status e fechar OS")

with bt3:
    with st.container(border=True):
        if st.button("🗺️ Mapa", use_container_width=True):
            st.switch_page("pages/10_Mapa_Atendimentos.py")
        st.caption("Geolocalização das máquinas")

with bt4:
    with st.container(border=True):
        if st.button("📊 KPIs", use_container_width=True):
            st.switch_page("pages/15_Indicadores_KPI.py")
        st.caption("Relatórios de performance")