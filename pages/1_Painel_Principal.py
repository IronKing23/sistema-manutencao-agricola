import streamlit as st
import pandas as pd
import plotly.express as px 
import sys
import os
import pytz
from datetime import datetime, timedelta

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from utils_pdf import gerar_relatorio_geral

# --- CONFIGURAÇÃO DA PÁGINA ---
# st.set_page_config deve ser sempre o primeiro comando Streamlit, 
# mas como esta é uma sub-página, ela herda do app.py. 
# Se for rodar isolado, descomente a linha abaixo.
# st.set_page_config(layout="wide", page_title="Painel de Controle")

st.title("🖥️ Painel de Controle de Manutenção")
st.markdown("---")

# Definição do Fuso Horário Local
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

# --- CSS PERSONALIZADO (VISUAL MODERNO) ---
st.markdown("""
<style>
    /* Estilo dos Cards KPI */
    .kpi-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }
    .kpi-title {
        color: #6c757d;
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    .kpi-value {
        color: #212529;
        font-size: 2.2rem;
        font-weight: 800;
    }
    .kpi-icon {
        float: right;
        font-size: 2rem;
        opacity: 0.8;
    }
    
    /* Modo Escuro */
    @media (prefers-color-scheme: dark) {
        .kpi-card {
            background-color: #262730;
            border-color: #3f3f46;
        }
        .kpi-title { color: #a1a1aa; }
        .kpi-value { color: #ffffff; }
    }
    
    /* Badge de Alerta */
    .pulse-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.7em;
        font-weight: bold;
        animation: pulse 2s infinite;
        vertical-align: middle;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÃO DE CARD VISUAL ---
def exibir_kpi(coluna, titulo, valor, icone, cor_borda="#ccc", alerta=False):
    html_alerta = '<span class="pulse-badge">AÇÃO</span>' if alerta and valor > 0 else ''
    coluna.markdown(f"""
    <div class="kpi-card" style="border-left: 5px solid {cor_borda};">
        <div class="kpi-icon">{icone}</div>
        <div class="kpi-title">{titulo} {html_alerta}</div>
        <div class="kpi-value">{valor}</div>
    </div>
    """, unsafe_allow_html=True)

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=60) # Cache de 60 segundos para agilidade
def carregar_filtros():
    conn = get_db_connection()
    try:
        frotas = pd.read_sql("SELECT DISTINCT frota FROM equipamentos ORDER BY frota", conn)
        operacoes = pd.read_sql("SELECT DISTINCT nome FROM tipos_operacao ORDER BY nome", conn)
        gestao = pd.read_sql("SELECT DISTINCT gestao_responsavel FROM equipamentos WHERE gestao_responsavel IS NOT NULL AND gestao_responsavel != '' ORDER BY gestao_responsavel", conn)
        return frotas, operacoes, gestao
    finally:
        conn.close()

frotas_df, operacoes_df, gestao_df = carregar_filtros()

# --- BARRA LATERAL (FILTROS) ---
with st.sidebar:
    st.header("🔍 Filtros Avançados")
    
    with st.expander("🛠️ Status e Prioridade", expanded=True):
        status_options = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças", "Concluído"]
        default_status = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças"]
        filtro_status = st.multiselect("Status", options=status_options, default=default_status)
        filtro_prioridade = st.multiselect("Prioridade", ["Alta", "Média", "Baixa"])

    with st.expander("🚜 Equipamento e Gestão"):
        filtro_frota = st.multiselect("Frota", options=frotas_df['frota'].tolist())
        filtro_gestao = st.multiselect("Gestor Responsável", options=gestao_df['gestao_responsavel'].tolist())
        filtro_operacao = st.multiselect("Tipo de Serviço", options=operacoes_df['nome'].tolist())

    st.markdown("### 📅 Período")
    c1, c2 = st.columns(2)
    data_inicio = c1.date_input("Início", datetime.now() - timedelta(days=30))
    data_fim = c2.date_input("Fim", datetime.now())

# --- CONSTRUÇÃO DA QUERY ---
query_base = """
SELECT 
    os.id as Ticket,
    os.data_hora as Data,
    os.data_encerramento as Fim,
    os.horimetro,
    os.prioridade,
    e.frota,
    e.modelo,
    e.gestao_responsavel as Gestao, 
    f.nome as Executante,
    os.status,
    os.numero_os_oficial as OS_Oficial,
    op.nome as Operacao,
    op.cor as Cor_Hex,
    os.local_atendimento as Local,
    os.descricao
FROM ordens_servico os
JOIN equipamentos e ON os.equipamento_id = e.id
JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
LEFT JOIN funcionarios f ON os.funcionario_id = f.id
WHERE 1=1 
"""

params = []
filtros_sql = ""

if filtro_status:
    filtros_sql += f" AND os.status IN ({','.join(['?'] * len(filtro_status))})"
    params.extend(filtro_status)
if filtro_prioridade: 
    filtros_sql += f" AND os.prioridade IN ({','.join(['?'] * len(filtro_prioridade))})"
    params.extend(filtro_prioridade)
if filtro_frota:
    filtros_sql += f" AND e.frota IN ({','.join(['?'] * len(filtro_frota))})"
    params.extend(filtro_frota)
if filtro_operacao:
    filtros_sql += f" AND op.nome IN ({','.join(['?'] * len(filtro_operacao))})"
    params.extend(filtro_operacao)
if filtro_gestao:
    filtros_sql += f" AND e.gestao_responsavel IN ({','.join(['?'] * len(filtro_gestao))})"
    params.extend(filtro_gestao)

filtros_sql += " AND os.data_hora BETWEEN ? AND ?"
params.extend([datetime.combine(data_inicio, datetime.min.time()), datetime.combine(data_fim, datetime.max.time())])

# Query Final com Ordenação Inteligente
query_final = query_base + filtros_sql + """ 
ORDER BY 
    CASE os.prioridade
        WHEN 'Alta' THEN 1
        WHEN 'Média' THEN 2
        WHEN 'Baixa' THEN 3
        ELSE 4
    END ASC,
    os.data_hora DESC
"""

# Query Global para Gráfico de Frotas (Independente de filtros temporais para contexto histórico)
query_top_frotas = """
SELECT e.frota as Frota, COUNT(os.id) as Qtd
FROM ordens_servico os
JOIN equipamentos e ON os.equipamento_id = e.id
GROUP BY e.frota
ORDER BY Qtd DESC LIMIT 10
"""

# --- EXECUÇÃO DAS QUERIES ---
conn = get_db_connection()
try:
    df_painel = pd.read_sql_query(query_final, conn, params=params)
    df_top_frotas = pd.read_sql_query(query_top_frotas, conn)
finally:
    conn.close()

# --- PROCESSAMENTO DOS DADOS ---
if not df_painel.empty:
    # Conversão de datas
    df_painel['Data_DT'] = pd.to_datetime(df_painel['Data'], format='mixed', dayfirst=True, errors='coerce')
    fim_dt = pd.to_datetime(df_painel['Fim'], format='mixed', dayfirst=True, errors='coerce')
    
    # Cálculo de Tempo em Aberto
    agora = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
    df_painel['delta'] = fim_dt.fillna(agora) - df_painel['Data_DT']
    
    def formatar_tempo(td):
        if pd.isnull(td): return "-"
        ts = int(td.total_seconds())
        d = ts // 86400
        h = (ts % 86400) // 3600
        m = ((ts % 86400) % 3600) // 60
        if d > 0: return f"{d}d {h}h"
        if h > 0: return f"{h}h {m}m"
        return f"{m}m"

    df_painel['Tempo_Aberto'] = df_painel['delta'].apply(formatar_tempo)
    df_painel['Data_Formatada'] = df_painel['Data_DT'].dt.strftime('%d/%m %H:%M')
    
    # Tratamento de Strings
    cols_upper = ['frota', 'modelo', 'Gestao', 'Executante', 'status', 'OS_Oficial', 'Operacao', 'Local', 'descricao', 'prioridade']
    for col in cols_upper:
        if col in df_painel.columns:
            df_painel[col] = df_painel[col].astype(str).str.upper().replace(['NONE', 'NAN'], '-')

# ==============================================================================
# INTERFACE EM ABAS
# ==============================================================================
tab_dash, tab_lista = st.tabs(["📊 Visão Geral (Dashboard)", "📋 Detalhamento (Tabela)"])

# ------------------------------------------------------------------------------
# ABA 1: DASHBOARD
# ------------------------------------------------------------------------------
with tab_dash:
    if df_painel.empty:
        st.info("🔎 Nenhum dado encontrado com os filtros atuais.")
    else:
        # CÁLCULO DE MÉTRICAS
        total = len(df_painel)
        urgentes = len(df_painel[df_painel['prioridade'] == 'ALTA'])
        abertos = len(df_painel[df_painel['status'] != 'CONCLUÍDO'])
        frotas_unicas = df_painel['frota'].nunique()

        # EXIBIÇÃO DOS CARDS
        c1, c2, c3, c4 = st.columns(4)
        exibir_kpi(c1, "Total Tickets", total, "📋", "#3498db")
        exibir_kpi(c2, "Alta Prioridade", urgentes, "🔥", "#e74c3c", alerta=True)
        exibir_kpi(c3, "Em Aberto", abertos, "⏳", "#f1c40f")
        exibir_kpi(c4, "Frotas Ativas", frotas_unicas, "🚜", "#2ecc71")

        st.markdown("---")

        # SEÇÃO DE FROTAS CRÍTICAS (EXPANSÍVEL)
        if urgentes > 0:
            with st.expander(f"🚨 Atenção: {urgentes} Tickets de Alta Prioridade", expanded=True):
                df_critico = df_painel[df_painel['prioridade'] == 'ALTA'].copy()
                st.dataframe(
                    df_critico[['Ticket', 'frota', 'Operacao', 'descricao', 'Tempo_Aberto']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Ticket": st.column_config.NumberColumn("#", format="%d", width="small"),
                        "Tempo_Aberto": "Tempo",
                        "descricao": "Problema"
                    }
                )

        # GRÁFICOS
        g1, g2 = st.columns(2)
        
        with g1:
            st.subheader("🚜 Top 10 Frotas (Histórico)")
            if not df_top_frotas.empty:
                df_top_frotas['Frota'] = df_top_frotas['Frota'].astype(str)
                fig_bar = px.bar(
                    df_top_frotas, x='Qtd', y='Frota', text='Qtd', orientation='h',
                    color='Qtd', color_continuous_scale='Blues'
                )
                fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title=None, yaxis_title=None)
                st.plotly_chart(fig_bar, use_container_width=True)

        with g2:
            st.subheader("🔧 Ocorrências por Tipo")
            df_pie = df_painel['Operacao'].value_counts().reset_index()
            df_pie.columns = ['Tipo', 'Qtd']
            fig_pie = px.pie(df_pie, values='Qtd', names='Tipo', hole=0.4, color_discrete_sequence=px.colors.qualitative.Prism)
            st.plotly_chart(fig_pie, use_container_width=True)

        # TIMELINE INTERATIVA
        st.subheader("📅 Linha do Tempo de Abertura")
        df_timeline = df_painel.sort_values('Data_DT')
        fig_line = px.scatter(
            df_timeline, x='Data_DT', y='prioridade', color='Operacao',
            size='Ticket', size_max=15, hover_data=['frota', 'descricao'],
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_line.update_yaxes(categoryorder='array', categoryarray=['BAIXA', 'MÉDIA', 'ALTA'])
        st.plotly_chart(fig_line, use_container_width=True)

# ------------------------------------------------------------------------------
# ABA 2: TABELA DETALHADA
# ------------------------------------------------------------------------------
with tab_lista:
    if df_painel.empty:
        st.warning("Sem dados para exibir.")
    else:
        # Colunas para exibir
        cols = ['Ticket', 'OS_Oficial', 'frota', 'modelo', 'Gestao', 'prioridade', 'status', 'Local', 'Data_Formatada', 'Tempo_Aberto', 'descricao', 'Operacao']
        df_show = df_painel[ [c for c in cols if c in df_painel.columns] ].copy()

        # CONFIGURAÇÃO VISUAL DA TABELA (Highlight)
        # Transforma colunas de texto em badges coloridos automaticamente
        st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ticket": st.column_config.NumberColumn("# Ticket", format="%d", width="small"),
                "OS_Oficial": st.column_config.TextColumn("OS Oficial", width="small"),
                "frota": st.column_config.TextColumn("Frota", width="small"),
                "modelo": st.column_config.TextColumn("Modelo", width="medium"),
                "Gestao": st.column_config.TextColumn("Gestão", width="medium"),
                "prioridade": st.column_config.Column(
                    "Prioridade",
                    width="small",
                    help="Urgência do atendimento",
                ),
                "status": st.column_config.Column(
                    "Status Atual",
                    width="medium",
                ),
                "Data_Formatada": st.column_config.TextColumn("Abertura", width="medium"),
                "Tempo_Aberto": st.column_config.TextColumn("Tempo", width="small"),
                "descricao": st.column_config.TextColumn("Descrição", width="large"),
                "Operacao": st.column_config.TextColumn("Tipo", width="medium"),
            }
        )

        st.markdown("---")
        
        # ÁREA DE DOWNLOAD
        c_csv, c_pdf = st.columns(2)
        with c_csv:
            csv = df_show.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Planilha (CSV)", csv, "relatorio_manutencao.csv", "text/csv", use_container_width=True)
        
        with c_pdf:
            try:
                pdf_bytes = gerar_relatorio_geral(df_show)
                st.download_button("🖨️ Imprimir Relatório (PDF)", pdf_bytes, "relatorio_geral.pdf", "application/pdf", type="primary", use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
