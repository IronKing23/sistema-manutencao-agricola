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

# --- 1. CONFIGURAÇÃO VISUAL (CLEAN & BOLD) ---
load_custom_css()

st.markdown("""
<style>
    /* REMOVE ESPAÇOS DO TOPO */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }

    /* --- ESTILO DOS CARDS (CONTAINERS) --- */
    /* Deixa os containers com borda mais elegantes */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        background-color: var(--card-bg);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s;
    }

    /* Efeito Hover Sutil no Container */
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        transform: translateY(-3px);
    }

    /* --- BARRA DE STATUS --- */
    .status-banner {
        padding: 12px 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        font-weight: 600;
        border: 1px solid transparent;
    }
    .status-ok { background-color: #F0FDF4; color: #166534; border-color: #BBF7D0; }
    .status-critico { background-color: #FEF2F2; color: #991B1B; border-color: #FECACA; animation: pulse-red 2s infinite; }

    /* --- TIPOGRAFIA DE IMPACTO NOS CARDS --- */
    .kpi-title {
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #64748B;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .kpi-value {
        font-size: 3.5rem;
        font-weight: 800;
        color: #0F172A; /* Escuro forte */
        line-height: 1;
        margin-bottom: 12px;
        font-feature-settings: "tnum";
        font-variant-numeric: tabular-nums;
    }

    /* Cores de Texto Específicas */
    .text-red { color: #DC2626; }
    .text-blue { color: #2563EB; }
    .text-orange { color: #D97706; }
    .text-green { color: #16A34A; }

    /* --- BOTÕES DENTRO DOS CARDS --- */
    /* Personaliza o botão secundário para parecer um link de ação */
    div[data-testid="stVerticalBlock"] button[kind="secondary"] {
        width: 100%;
        border: 1px solid #E2E8F0;
        background-color: transparent;
        color: #475569;
        font-weight: 500;
        border-radius: 8px;
    }
    div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
        background-color: #F8FAFC;
        border-color: #94A3B8;
        color: #0F172A;
    }

    /* --- DARK MODE --- */
    @media (prefers-color-scheme: dark) {
        .kpi-title { color: #94A3B8; }
        .kpi-value { color: #F8FAFC; }
        .status-ok { background-color: #064E3B; color: #D1FAE5; border-color: #065F46; }
        .status-critico { background-color: #450A0A; color: #FECACA; border-color: #7F1D1D; }
        .text-red { color: #F87171; }
        .text-blue { color: #60A5FA; }
        .text-orange { color: #FBBF24; }
        .text-green { color: #4ADE80; }

        div[data-testid="stVerticalBlock"] button[kind="secondary"] {
            border-color: #334155;
            color: #94A3B8;
        }
        div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
            background-color: #1E293B;
            color: #F1F5F9;
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

        # Dataframes para os Popups (CORRIGIDO AQUI: 'os.id' para evitar ambiguidade)

        # 1. Pendências
        df_ab = pd.read_sql("""
            SELECT os.id, e.frota, os.descricao, os.data_hora, os.prioridade, os.status 
            FROM ordens_servico os 
            JOIN equipamentos e ON os.equipamento_id = e.id 
            WHERE os.status != 'Concluído' 
            ORDER BY os.prioridade = 'Alta' DESC, os.data_hora DESC LIMIT 20
        """, conn)

        # 2. Paradas
        df_pa = pd.read_sql("""
            SELECT os.id, e.frota, os.descricao, os.data_hora 
            FROM ordens_servico os 
            JOIN equipamentos e ON os.equipamento_id = e.id 
            WHERE os.status != 'Concluído' AND os.maquina_parada = 1 
            ORDER BY os.data_hora DESC
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
        # Direciona para o Painel Geral
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
        # Direciona para o Painel Geral
        if st.button("Ver no Painel Geral 📊", type="primary", use_container_width=True):
            st.switch_page("pages/1_Painel_Principal.py")


# --- 4. HEADER ---
user_first_name = st.session_state.get('user_nome', 'Usuário').split()[0]
current_date = datetime.now().strftime('%d/%m/%Y')

c_head1, c_head2 = st.columns([3, 1])
with c_head1:
    st.markdown(f"<h1 style='margin-bottom:0px;'>Olá, {user_first_name}</h1>", unsafe_allow_html=True)
    st.caption(f"Visão Geral • {current_date}")

# --- BARRA DE STATUS ---
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

# --- 5. DASHBOARD CARDS (CONTAINERS) ---
c1, c2, c3 = st.columns(3)

# --- CARD 1: PARADAS (CRÍTICO) ---
with c1:
    with st.container(border=True):
        # Ícone e Título
        svg_stop = get_icon("stop", "#EF4444", "20").replace('\n', '')
        st.markdown(f'<div class="kpi-title">{svg_stop} Máquinas Paradas</div>', unsafe_allow_html=True)

        # Valor com cor condicional
        cor_val = "text-red" if q_parada > 0 else "text-secondary"
        st.markdown(f'<div class="kpi-value {cor_val}">{q_parada}</div>', unsafe_allow_html=True)

        # Botão de Ação
        label_btn = "Ver Detalhes" if q_parada > 0 else "Sem paradas"
        tipo_btn = "primary" if q_parada > 0 else "secondary"
        if st.button(label_btn, key="btn_parada", use_container_width=True, type=tipo_btn, disabled=(q_parada == 0)):
            popup_paradas()

# --- CARD 2: PENDÊNCIAS (INFO) ---
with c2:
    with st.container(border=True):
        svg_list = get_icon("dashboard", "#3B82F6", "20").replace('\n', '')
        st.markdown(f'<div class="kpi-title">{svg_list} Pendências Totais</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="kpi-value text-blue">{q_aberta}</div>', unsafe_allow_html=True)

        if st.button("Listar Ordens", key="btn_pend", use_container_width=True):
            popup_pendencias()

# --- CARD 3: MURAL (AVISO) ---
with c3:
    with st.container(border=True):
        svg_pin = get_icon("pin", "#F59E0B", "20").replace('\n', '')
        st.markdown(f'<div class="kpi-title">{svg_pin} Mural de Avisos</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="kpi-value text-orange">{q_recados}</div>', unsafe_allow_html=True)

        if st.button("Ler Recados", key="btn_mural", use_container_width=True):
            st.switch_page("pages/11_Quadro_Avisos.py")

st.markdown("<br><br>", unsafe_allow_html=True)

# --- 6. ATALHOS DE AÇÃO (Secundários) ---
st.markdown("##### ⚡ Ações Rápidas")
bt1, bt2, bt3, bt4 = st.columns(4)

with bt1:
    with st.container(border=True):
        if st.button("📝 Criar Ordem", use_container_width=True, type="primary"):
            st.switch_page("pages/5_Nova_Ordem_Servico.py")
        st.caption("Abrir chamado")

with bt2:
    with st.container(border=True):
        if st.button("🔄 Gerenciar", use_container_width=True):
            st.switch_page("pages/6_Gerenciar_Atendimento.py")
        st.caption("Editar status")

with bt3:
    with st.container(border=True):
        if st.button("🗺️ Mapa", use_container_width=True):
            st.switch_page("pages/10_Mapa_Atendimentos.py")
        st.caption("Ver frota")

with bt4:
    with st.container(border=True):
        if st.button("📊 KPIs", use_container_width=True):
            st.switch_page("pages/15_Indicadores_KPI.py")
        st.caption("Relatórios")