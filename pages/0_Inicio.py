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

# --- 1. CONFIGURAÇÃO E ESTILO ---
load_custom_css()

# CSS Específico para esta página
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
    .alert-title {
        font-weight: 700;
        font-size: 0.9rem;
        display: flex;
        align-items: center;
        gap: 6px;
    }
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

    /* Estilo para Botão Invisível sobre o Card */
    div.stButton > button:first-child {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 15px;
        width: 100%;
        text-align: left;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    div.stButton > button:first-child:hover {
        border-color: #2E7D32;
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    div.stButton > button:first-child p {
        font-family: 'Inter', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÃO AUXILIAR: Tempo Relativo ---
def calcular_tempo_atras(dt_obj):
    if pd.isnull(dt_obj): return "-"
    try:
        if isinstance(dt_obj, str): dt_obj = pd.to_datetime(dt_obj)
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
    except: return "-"

# --- 2. CARREGAMENTO DE DADOS (SEM CACHE PARA ATUALIZAÇÃO REAL) ---
def carregar_dados_live():
    """Carrega dados em tempo real para os cards."""
    conn = get_db_connection()
    try:
        # Contagens Simples
        qtd_aberta = conn.execute("SELECT COUNT(*) FROM ordens_servico WHERE status != 'Concluído'").fetchone()[0]
        qtd_parada = conn.execute("SELECT COUNT(*) FROM ordens_servico WHERE status != 'Concluído' AND maquina_parada = 1").fetchone()[0]
        qtd_recados = conn.execute("SELECT COUNT(*) FROM recados").fetchone()[0]
        
        # Dados Detalhados para os Popups
        df_pendentes = pd.read_sql_query("SELECT id, descricao, data_hora FROM ordens_servico WHERE status != 'Concluído' ORDER BY data_hora DESC LIMIT 10", conn)
        df_paradas = pd.read_sql_query("SELECT id, descricao, data_hora FROM ordens_servico WHERE status != 'Concluído' AND maquina_parada = 1 ORDER BY data_hora DESC LIMIT 10", conn)
        df_alertas = pd.read_sql_query("""
            SELECT os.id, e.frota, e.modelo, os.descricao, os.data_hora, os.prioridade, os.maquina_parada
            FROM ordens_servico os JOIN equipamentos e ON os.equipamento_id = e.id
            WHERE os.status != 'Concluído' AND (os.prioridade = 'Alta' OR os.maquina_parada = 1)
            ORDER BY os.data_hora DESC LIMIT 5
        """, conn)
        
        df_status_chart = pd.read_sql_query("SELECT status, COUNT(*) as qtd FROM ordens_servico WHERE status != 'Concluído' GROUP BY status ORDER BY qtd DESC", conn)
        
        return qtd_aberta, qtd_parada, qtd_recados, df_pendentes, df_paradas, df_alertas, df_status_chart
    finally:
        conn.close()

# Carrega dados frescos
qtd_aberta, qtd_parada, qtd_recados, df_pendentes, df_paradas, df_alertas, df_status_chart = carregar_dados_live()

# --- 3. CABEÇALHO ---
nome_usuario = st.session_state.get('user_nome', 'Colaborador').split()[0]
st.title(f"Olá, {nome_usuario}! 👋")
st.caption(f"Resumo operacional de {datetime.now().strftime('%d/%m/%Y')}")

# --- DIALOGS (POPUPS) ---
@st.dialog("📋 Pendências em Aberto")
def show_pendencias():
    st.write(f"Últimas {len(df_pendentes)} ordens pendentes:")
    st.dataframe(
        df_pendentes, 
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("# Ticket", width="small"),
            "data_hora": st.column_config.DatetimeColumn("Abertura", format="DD/MM HH:mm"),
            "descricao": "Descrição"
        }
    )
    if st.button("Ir para Gerenciamento Completo", use_container_width=True):
        st.switch_page("pages/6_Gerenciar_Atendimento.py")

@st.dialog("🚜 Máquinas Paradas")
def show_paradas():
    if df_paradas.empty:
        st.success("Nenhuma máquina parada no momento!")
    else:
        st.error(f"{len(df_paradas)} máquinas fora de operação.")
        st.dataframe(
            df_paradas,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "#",
                "data_hora": st.column_config.DatetimeColumn("Desde", format="DD/MM HH:mm"),
                "descricao": "Motivo"
            }
        )

# --- 4. KPIs PRINCIPAIS (AGORA CLICÁVEIS) ---
# Usamos st.button simulando cards para permitir o clique nativo
c1, c2, c3, c4 = st.columns(4)

with c1:
    # Usando HTML dentro do label do botão para simular o card visualmente
    # Nota: Streamlit suporta markdown limitado em labels de botão, mas para visual complexo
    # a melhor prática nativa interativa é usar o botão como container ou st.metric simples.
    # Aqui vou usar uma abordagem híbrida: botão com métrica formatada.
    if st.button(f"📋 Pendências\n\n{qtd_aberta}", use_container_width=True, help="Clique para ver detalhes"):
        show_pendencias()

with c2:
    label_parada = f"🚜 Máquinas Paradas\n\n{qtd_parada}"
    if st.button(label_parada, use_container_width=True, type="primary" if qtd_parada > 0 else "secondary"):
        show_paradas()

with c3:
    if st.button(f"📌 Mural de Avisos\n\n{qtd_recados}", use_container_width=True):
        st.switch_page("pages/11_Quadro_Avisos.py")

with c4:
    # Card estático de sistema (apenas visual)
    st.button("✅ Sistema Online\n\nOK", disabled=True, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- 5. CORPO DA TELA ---
col_main, col_side = st.columns([2, 1.2])

# >> COLUNA ESQUERDA: AÇÃO E GRÁFICO
with col_main:
    st.subheader("🚀 Acesso Rápido")
    g1, g2 = st.columns(2)
    with g1:
        if st.button("📝 Nova Ordem de Serviço", type="primary", use_container_width=True):
            st.switch_page("pages/5_Nova_Ordem_Servico.py")
    with g2:
        if st.button("🔄 Gerenciar Atendimentos", use_container_width=True):
            st.switch_page("pages/6_Gerenciar_Atendimento.py")
            
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    g3, g4 = st.columns(2)
    with g3:
        if st.button("📊 Painel de Indicadores", use_container_width=True):
            st.switch_page("pages/15_Indicadores_KPI.py")
    with g4:
        if st.button("🗺️ Mapa de Frotas", use_container_width=True):
            st.switch_page("pages/10_Mapa_Atendimentos.py")

    # --- GRÁFICO DE GARGALOS ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📊 Raio-X da Oficina")
    
    if not df_status_chart.empty:
        import plotly.express as px
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
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info("Nenhuma ordem pendente.")

# >> COLUNA DIREITA: FEED DE ALERTAS
with col_side:
    st.subheader("🚨 Atenção Requerida")
    if df_alertas.empty:
        st.markdown("""<div style="background-color: #F0FDF4; border: 1px solid #22C55E; border-radius: 8px; padding: 20px; text-align: center; color: #166534;"><div style="font-size: 30px;">🎉</div><b>Tudo Operando!</b></div>""", unsafe_allow_html=True)
    else:
        for _, row in df_alertas.iterrows():
            tempo_decorrido = calcular_tempo_atras(row['data_hora'])
            
            if row['maquina_parada'] == 1:
                icon_svg = get_icon("stop", color="#DC2626", size="20").strip()
                texto_alerta = "PARADA"; cor_titulo = "#991B1B"
            else:
                icon_svg = get_icon("fire", color="#EA580C", size="20").strip()
                texto_alerta = "ALTA PRIO."; cor_titulo = "#C2410C"
            
            st.markdown(f"""
            <div class="alert-card">
                <div class="alert-header">
                    <span class="alert-title" style="color: {cor_titulo};">{icon_svg} {texto_alerta}</span>
                    <span class="time-badge">⏱️ {tempo_decorrido}</span>
                </div>
                <div style="font-weight: 600; color: var(--text-color); margin-bottom: 4px;">{row['frota']} - {row['modelo']}</div>
                <div class="alert-body">{row['descricao'][:55]}...</div>
            </div>
            """, unsafe_allow_html=True)
            
        if st.button("Ver fila completa →", use_container_width=True):
            st.switch_page("pages/1_Painel_Principal.py")
