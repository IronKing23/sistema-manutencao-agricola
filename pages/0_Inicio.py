import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
from datetime import datetime

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from utils_ui import load_custom_css, card_kpi
from utils_icons import get_icon

# --- 1. CONFIGURAÇÃO E ESTILO ---
load_custom_css()

# CSS Específico para esta página (Feed de Alertas e Badges)
st.markdown("""
<style>
    /* Card de Alerta Crítico */
    .alert-card {
        background-color: #FFFFFF;
        border-left: 5px solid #EF4444;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #E5E7EB;
        transition: transform 0.2s;
    }
    .alert-card:hover {
        transform: translateX(5px);
        border-color: #DC2626;
    }
    .alert-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }

    /* Título do Alerta com Flexbox para alinhar SVG + Texto */
    .alert-title {
        font-weight: 700;
        font-size: 0.9rem;
        display: flex;
        align-items: center;
        gap: 8px; /* Espaço entre ícone e texto */
    }

    .alert-title svg {
        width: 20px;
        height: 20px;
    }

    /* Badge de Tempo */
    .time-badge {
        background-color: #FEF2F2;
        color: #B91C1C;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #FECACA;
        white-space: nowrap;
    }

    .alert-body {
        font-size: 0.9rem;
        color: #374151;
        line-height: 1.4;
    }

    /* Modo Escuro para os Cards de Alerta */
    @media (prefers-color-scheme: dark) {
        .alert-card {
            background-color: #1F2937;
            border-color: #374151; /* Borda padrão */
            border-left-color: #EF4444; /* Borda destaque mantém vermelho */
        }
        .alert-body { color: #D1D5DB; }
        .time-badge {
            background-color: rgba(220, 38, 38, 0.2);
            color: #FCA5A5;
            border-color: #EF4444;
        }
    }
</style>
""", unsafe_allow_html=True)


# --- FUNÇÃO AUXILIAR: Tempo Relativo ---
def calcular_tempo_atras(dt_obj):
    if pd.isnull(dt_obj): return "-"
    try:
        if isinstance(dt_obj, str):
            dt_obj = pd.to_datetime(dt_obj)

        agora = datetime.now()
        diff = agora - dt_obj
        segundos = diff.total_seconds()

        if segundos < 60: return "Agora"
        minutos = int(segundos / 60)
        if minutos < 60: return f"Há {minutos} min"
        horas = int(minutos / 60)
        if horas < 24: return f"Há {horas}h"
        dias = int(horas / 24)
        return f"Há {dias}d"
    except:
        return "-"


# --- 2. CARREGAMENTO DE DADOS ---
conn = get_db_connection()

# KPIs Gerais
qtd_aberta = conn.execute("SELECT COUNT(*) FROM ordens_servico WHERE status != 'Concluído'").fetchone()[0]
qtd_parada = \
conn.execute("SELECT COUNT(*) FROM ordens_servico WHERE status != 'Concluído' AND maquina_parada = 1").fetchone()[0]
qtd_recados = conn.execute("SELECT COUNT(*) FROM recados").fetchone()[0]

# Query: Feed de Alertas (Alta Prioridade ou Parada)
df_alertas = pd.read_sql_query("""
    SELECT 
        os.id, e.frota, e.modelo, os.descricao, os.data_hora, os.prioridade, os.maquina_parada
    FROM ordens_servico os 
    JOIN equipamentos e ON os.equipamento_id = e.id
    WHERE os.status != 'Concluído' 
    AND (os.prioridade = 'Alta' OR os.maquina_parada = 1)
    ORDER BY os.data_hora DESC 
    LIMIT 5
""", conn)

# Query: Distribuição de Status
df_status_chart = pd.read_sql_query("""
    SELECT status, COUNT(*) as qtd 
    FROM ordens_servico 
    WHERE status != 'Concluído' 
    GROUP BY status 
    ORDER BY qtd DESC
""", conn)

conn.close()

# --- 3. CABEÇALHO ---
nome_usuario = st.session_state.get('user_nome', 'Colaborador').split()[0]
st.title(f"Olá, {nome_usuario}! 👋")
st.caption(f"Resumo operacional de {datetime.now().strftime('%d/%m/%Y')}")

# --- 4. KPIs PRINCIPAIS COM ÍCONES SVG ---
c1, c2, c3, c4 = st.columns(4)

# Pendências (Dashboard) - Azul
icon_pend = get_icon("dashboard", color="#3B82F6", size="32")
card_kpi(c1, "Pendências", qtd_aberta, icon_pend, "#3B82F6")

# Máquinas Paradas (Trator) - Vermelho ou Cinza
cor_trator = "#EF4444" if qtd_parada > 0 else "#CBD5E1"
icon_trator = get_icon("tractor", color=cor_trator, size="32")
card_kpi(c2, "Máquinas Paradas", qtd_parada, icon_trator, cor_trator)

# Mural (Pin) - Amarelo ou Cinza
cor_mural = "#F59E0B" if qtd_recados > 0 else "#CBD5E1"
icon_mural = get_icon("pin", color=cor_mural, size="32")
card_kpi(c3, "Mural de Avisos", qtd_recados, icon_mural, cor_mural)

# Sistema (Check) - Verde
icon_check = get_icon("check", color="#10B981", size="32")
card_kpi(c4, "Sistema Online", "OK", icon_check, "#10B981")

st.markdown("<br>", unsafe_allow_html=True)

# --- 5. CORPO DA TELA ---
col_main, col_side = st.columns([2, 1.2])

# >> COLUNA ESQUERDA: AÇÃO E GRÁFICO
with col_main:
    st.subheader("🚀 Acesso Rápido")

    # Grid de botões
    g1, g2 = st.columns(2)
    with g1:
        if st.button("📝 Nova Ordem de Serviço\n\nAbrir chamado para frota", type="primary", use_container_width=True):
            st.switch_page("pages/5_Nova_Ordem_Servico.py")
    with g2:
        if st.button("🔄 Gerenciar Atendimentos\n\nAtualizar status e fechar OS", use_container_width=True):
            st.switch_page("pages/6_Gerenciar_Atendimento.py")

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

    g3, g4 = st.columns(2)
    with g3:
        if st.button("📊 Painel de Indicadores\n\nVer MTBF, MTTR e Turnos", use_container_width=True):
            st.switch_page("pages/15_Indicadores_KPI.py")
    with g4:
        if st.button("🗺️ Mapa de Frotas\n\nGeolocalização das máquinas", use_container_width=True):
            st.switch_page("pages/10_Mapa_Atendimentos.py")

    # --- NOVO: GRÁFICO DE GARGALOS (Raio-X) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📊 Raio-X da Oficina (Status)")

    if not df_status_chart.empty:
        fig = px.bar(
            df_status_chart,
            x='qtd', y='status',
            orientation='h',
            text='qtd',
            color='status',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig.update_layout(
            xaxis_title=None, yaxis_title=None,
            showlegend=False,
            height=200,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info("Nenhuma ordem pendente para análise de gargalo.")

# >> COLUNA DIREITA: FEED DE ALERTAS (COM ÍCONES SVG CORRIGIDOS)
with col_side:
    st.subheader("🚨 Atenção Requerida")

    if df_alertas.empty:
        # HTML Compactado para evitar erro de renderização
        st.markdown(
            """<div style="background-color: #F0FDF4; border: 1px solid #22C55E; border-radius: 8px; padding: 20px; text-align: center; color: #166534;"><div style="font-size: 30px;">🎉</div><b>Tudo Operando!</b><br>Nenhuma parada crítica.</div>""",
            unsafe_allow_html=True)
    else:
        for _, row in df_alertas.iterrows():
            # Cálculo de Tempo
            tempo_decorrido = calcular_tempo_atras(row['data_hora'])

            # Definição do Ícone e Cor baseada no tipo de alerta
            if row['maquina_parada'] == 1:
                # Ícone Stop Vermelho
                icon_svg = get_icon("stop", color="#DC2626", size="20").strip()
                texto_alerta = "PARADA"
                cor_titulo = "#991B1B"
            else:
                # Ícone Fogo Laranja/Vermelho
                icon_svg = get_icon("fire", color="#EA580C", size="20").strip()
                texto_alerta = "ALTA PRIO."
                cor_titulo = "#C2410C"

            # HTML do Card com Badge de Tempo e Ícone SVG
            # Importante: Sem indentação interna para evitar bugs visuais
            st.markdown(f"""<div class="alert-card">
<div class="alert-header">
<span class="alert-title" style="color: {cor_titulo};">{icon_svg} {texto_alerta}</span>
<span class="time-badge">⏱️ {tempo_decorrido}</span>
</div>
<div style="font-weight: 600; color: #1F2937; margin-bottom: 4px;">{row['frota']} - {row['modelo']}</div>
<div class="alert-body">{row['descricao'][:55]}...</div>
</div>""", unsafe_allow_html=True)

        if st.button("Ver fila completa →", use_container_width=True):
            st.switch_page("pages/1_Painel_Principal.py")