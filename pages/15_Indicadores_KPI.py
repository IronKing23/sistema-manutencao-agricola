import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
import numpy as np

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from datetime import datetime, time, timedelta
from utils_pdf import gerar_relatorio_kpi

st.set_page_config(layout="wide", page_title="Indicadores de Confiabilidade")
st.title("📈 Indicadores de Performance & Turnos")

# --- CSS MODERNIZADO ---
st.markdown("""
<style>
.kpi-card {
    background-color: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 15px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    display: flex; flex-direction: column; justify-content: space-between;
}
.kpi-card:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); transition: all 0.3s; }
.kpi-title { font-size: 0.85rem; color: #6c757d; font-weight: 600; text-transform: uppercase; }
.kpi-value { font-size: 1.8rem; font-weight: 800; color: #212529; }
.kpi-sub { font-size: 0.75rem; color: #adb5bd; margin-top: 5px; }
@media (prefers-color-scheme: dark) {
    .kpi-card { background-color: #262730; border-color: #3f3f46; }
    .kpi-title { color: #a1a1aa; }
    .kpi-value { color: #f4f4f5; }
}
</style>
""", unsafe_allow_html=True)


def exibir_card(col, titulo, valor, icone, cor_borda, subtexto=""):
    html_content = f"""
    <div class="kpi-card" style="border-left: 5px solid {cor_borda};">
        <div><div class="kpi-title">{titulo} {icone}</div><div class="kpi-value">{valor}</div><div class="kpi-sub">{subtexto}</div></div>
    </div>
    """
    col.markdown(html_content, unsafe_allow_html=True)


# --- LÓGICA DE TURNOS ---
def classificar_turno(dt):
    if pd.isnull(dt): return "N/A"

    # Converte hora para float para facilitar comparação (ex: 06:30 = 6.5)
    hora_float = dt.hour + dt.minute / 60.0

    # Turno A: 06:30 às 15:00 (6.5 <= h < 15.0)
    if 6.5 <= hora_float < 15.0:
        return "Turno A (Manhã)"
    # Turno B: 15:00 às 23:00 (15.0 <= h < 23.0)
    elif 15.0 <= hora_float < 23.0:
        return "Turno B (Tarde)"
    # Turno C: 23:00 às 06:30 (O resto, cruza a meia noite)
    else:
        return "Turno C (Noite)"


# --- 1. FILTROS E CONFIGURAÇÕES ---
with st.sidebar:
    st.header("Parâmetros")

    horas_operacionais_dia = st.number_input(
        "Horas Operacionais da Frota / Dia",
        min_value=1, max_value=24, value=20,
        help="Usado para calcular o Tempo Total Disponível no período (Considerando 3 turnos)."
    )

    st.divider()
    st.header("Filtros")

    conn = get_db_connection()

    # Filtros de Data
    col_d1, col_d2 = st.columns(2)
    dt_inicio = col_d1.date_input("De:", datetime.now() - timedelta(days=30))
    dt_fim = col_d2.date_input("Até:", datetime.now())

    # Filtros de Equipamento
    try:
        df_modelos = pd.read_sql("SELECT DISTINCT modelo FROM equipamentos ORDER BY modelo", conn)
        lista_modelos = df_modelos['modelo'].dropna().unique()
        filtro_modelo = st.multiselect("Modelo", options=lista_modelos)
    except:
        filtro_modelo = []

    query_frotas = "SELECT DISTINCT frota FROM equipamentos"
    params_frotas = []
    if filtro_modelo:
        query_frotas += f" WHERE modelo IN ({','.join(['?'] * len(filtro_modelo))})"
        params_frotas = filtro_modelo
    query_frotas += " ORDER BY frota"

    df_frotas_db = pd.read_sql(query_frotas, conn, params=params_frotas)
    filtro_frota = st.multiselect("Frota", options=df_frotas_db['frota'].unique())

    # Filtro de Turno (Visualização)
    st.markdown("### Filtro de Turno")
    turnos_selecionados = st.multiselect(
        "Exibir apenas:",
        ["Turno A (Manhã)", "Turno B (Tarde)", "Turno C (Noite)"],
        default=["Turno A (Manhã)", "Turno B (Tarde)", "Turno C (Noite)"]
    )

    conn.close()


# --- 2. CARREGAR E PROCESSAR DADOS ---
def carregar_dados():
    conn = get_db_connection()
    # Renomeamos 'os.id' para 'Ticket' DIRETAMENTE NA QUERY
    query = """
            SELECT os.id                as Ticket, \
                   e.frota, \
                   e.modelo, \
                   os.data_hora         as abertura, \
                   os.data_encerramento as fechamento, \
                   os.classificacao, \
                   os.maquina_parada, \
                   op.nome              as tipo_servico, \
                   f_solic.nome         as solicitante
            FROM ordens_servico os
                     JOIN equipamentos e ON os.equipamento_id = e.id
                     JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
                     LEFT JOIN funcionarios f_solic ON os.solicitante_id = f_solic.id
            WHERE os.data_hora BETWEEN ? AND ? \
            """
    params = [dt_inicio, datetime.combine(dt_fim, datetime.max.time())]

    if filtro_modelo:
        query += f" AND e.modelo IN ({','.join(['?'] * len(filtro_modelo))})"
        params.extend(filtro_modelo)
    if filtro_frota:
        query += f" AND e.frota IN ({','.join(['?'] * len(filtro_frota))})"
        params.extend(filtro_frota)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


df = carregar_dados()

if df.empty:
    st.warning("Sem dados para o período selecionado.")
    st.stop()

# Tratamento de Dados
df['abertura'] = pd.to_datetime(df['abertura'], format='mixed', errors='coerce')
df['fechamento'] = pd.to_datetime(df['fechamento'], format='mixed', errors='coerce')

# Aplica a classificação de turno
df['Turno'] = df['abertura'].apply(classificar_turno)

# Filtra pelo turno selecionado na sidebar
if turnos_selecionados:
    df = df[df['Turno'].isin(turnos_selecionados)]

# Cálculos de Tempo
agora = datetime.now()
df['fechamento_calc'] = df['fechamento'].fillna(agora)
df['duracao_horas'] = (df['fechamento_calc'] - df['abertura']).dt.total_seconds() / 3600

if 'classificacao' not in df.columns: df['classificacao'] = 'Corretiva'
if 'maquina_parada' not in df.columns: df['maquina_parada'] = 1
df['classificacao'] = df['classificacao'].fillna('Corretiva')
df['maquina_parada'] = df['maquina_parada'].fillna(1).astype(int)

# Separa Falhas (Corretivas com Parada)
df_falhas = df[(df['classificacao'].str.contains('Corretiva', case=False)) & (df['maquina_parada'] == 1)]

# --- 3. CÁLCULO DE KPIs GERAIS ---
num_falhas = len(df_falhas)
tempo_total_reparo = df_falhas['duracao_horas'].sum()

# Estimativa de Máquinas (se não filtrou, assume total do DF)
num_maquinas = df['frota'].nunique()
dias_periodo = (dt_fim - dt_inicio).days + 1
tempo_total_disponivel = dias_periodo * horas_operacionais_dia * num_maquinas

mttr = (tempo_total_reparo / num_falhas) if num_falhas > 0 else 0
tempo_operacao = tempo_total_disponivel - tempo_total_reparo
mtbf = (tempo_operacao / num_falhas) if num_falhas > 0 else tempo_operacao
disp = (mtbf / (mtbf + mttr)) * 100 if (mtbf + mttr) > 0 else 100.0

# --- 4. DASHBOARD GLOBAL ---
st.markdown("### 📊 Visão Geral")
c1, c2, c3, c4 = st.columns(4)
exibir_card(c1, "MTBF (Confiabilidade)", f"{mtbf:.1f} h", "🛡️", "#3B82F6", "Tempo médio entre falhas")
exibir_card(c2, "MTTR (Agilidade)", f"{mttr:.1f} h", "🔧", "#F59E0B", "Tempo médio de reparo")
exibir_card(c3, "Disponibilidade", f"{disp:.1f}%", "✅", "#10B981", "% tempo máquina pronta")
exibir_card(c4, "Total de Falhas", num_falhas, "🚨", "#EF4444", "Ocorrências com parada")

st.divider()

# --- 5. ANÁLISE POR TURNO (O CORAÇÃO DA SUA SOLICITAÇÃO) ---
st.markdown("### 🕒 Análise Comparativa por Turno")

if df_falhas.empty:
    st.info("Sem falhas registradas para análise de turno.")
else:
    tab_t1, tab_t2, tab_t3 = st.tabs(["📊 Gráficos de Turno", "🚜 Máquinas por Turno", "📋 Dados Brutos"])

    with tab_t1:
        col_g1, col_g2 = st.columns(2)

        # A) Volume de Falhas por Turno
        df_turno_qtd = df_falhas['Turno'].value_counts().reset_index()
        df_turno_qtd.columns = ['Turno', 'Qtd']

        fig_vol = px.bar(
            df_turno_qtd, x='Turno', y='Qtd', color='Turno',
            text='Qtd', title="Volume de Ocorrências por Turno",
            color_discrete_map={
                "Turno A (Manhã)": "#FF9F36",  # Laranja Manhã
                "Turno B (Tarde)": "#4B8BBE",  # Azul Tarde
                "Turno C (Noite)": "#306998"  # Azul Escuro Noite
            }
        )
        fig_vol.update_traces(textposition='outside')
        col_g1.plotly_chart(fig_vol, use_container_width=True)

        # B) Eficiência (MTTR) por Turno
        # Agrupa para ver onde o reparo demora mais
        df_turno_mttr = df_falhas.groupby('Turno')['duracao_horas'].mean().reset_index()
        df_turno_mttr.columns = ['Turno', 'MTTR (h)']

        fig_eff = px.bar(
            df_turno_mttr, x='Turno', y='MTTR (h)', color='Turno',
            text_auto='.1f', title="Eficiência (MTTR) por Turno - Onde demora mais?",
        )
        col_g2.plotly_chart(fig_eff, use_container_width=True)

        # C) Insight Rápido
        turno_pior_qtd = df_turno_qtd.iloc[0]['Turno'] if not df_turno_qtd.empty else "-"
        turno_pior_mttr = df_turno_mttr.sort_values('MTTR (h)', ascending=False).iloc[0][
            'Turno'] if not df_turno_mttr.empty else "-"

        st.info(
            f"💡 **Insight:** O turno com mais quebras é o **{turno_pior_qtd}**, mas os reparos mais demorados ocorrem no **{turno_pior_mttr}**.")

    with tab_t2:
        st.markdown("#### Quais máquinas quebram em qual turno?")

        # --- CORREÇÃO DO GRÁFICO ---
        # 1. Agrupamento correto
        df_matrix = df_falhas.groupby(['frota', 'Turno']).size().reset_index(name='Contagem')

        # 2. Top 10 Máquinas
        top_maquinas = df_falhas['frota'].value_counts().head(10).index
        df_matrix_top = df_matrix[df_matrix['frota'].isin(top_maquinas)].copy()

        # 3. Conversão para String (Evita erro 64k)
        df_matrix_top['frota'] = df_matrix_top['frota'].astype(str)

        # 4. Ordenação (Mais quebras no topo)
        total_por_frota = df_matrix_top.groupby('frota')['Contagem'].sum().sort_values(ascending=True)
        ordem_frotas = total_por_frota.index.tolist()

        fig_matrix = px.bar(
            df_matrix_top,
            y='frota',
            x='Contagem',
            color='Turno',
            title="<b>Top 10 Máquinas: Distribuição de Quebras por Turno</b>",
            orientation='h',
            barmode='stack',
            text='Contagem',
            category_orders={'frota': ordem_frotas},  # Ordena eixo Y
            color_discrete_map={
                "Turno A (Manhã)": "#FF9F36",
                "Turno B (Tarde)": "#4B8BBE",
                "Turno C (Noite)": "#306998"
            }
        )

        # --- FORÇA EIXO CATEGÓRICO (Resolve o problema do "k") ---
        fig_matrix.update_yaxes(type='category')

        fig_matrix.update_layout(
            xaxis_title="Quantidade de Falhas",
            yaxis_title="Máquina / Frota",
            legend_title="Turno",
            hovermode="y unified"
        )
        fig_matrix.update_traces(textposition='inside', insidetextanchor='middle')

        st.plotly_chart(fig_matrix, use_container_width=True)

    with tab_t3:
        # CORREÇÃO DE VISUALIZAÇÃO NA TABELA
        if 'Ticket' in df_falhas.columns:
            colunas_tabela = ['Ticket', 'frota', 'Turno', 'abertura', 'duracao_horas', 'tipo_servico', 'solicitante']
        else:
            df_falhas['Ticket'] = df_falhas.index
            colunas_tabela = ['Ticket', 'frota', 'Turno', 'abertura', 'duracao_horas', 'tipo_servico', 'solicitante']

        # Converte frota para string na tabela também para consistência
        df_exibicao = df_falhas.copy()
        df_exibicao['frota'] = df_exibicao['frota'].astype(str)

        st.dataframe(
            df_exibicao[colunas_tabela].sort_values('abertura', ascending=False),
            use_container_width=True,
            hide_index=True
        )

# --- DOWNLOAD ---
st.divider()
col_b, _ = st.columns([1, 4])
with col_b:
    dados_kpi_pdf = {
        'mtbf': f"{mtbf:.1f} h", 'mttr': f"{mttr:.1f} h", 'disp': f"{disp:.1f}%", 'falhas': num_falhas
    }
    try:
        pdf_bytes = gerar_relatorio_kpi(dados_kpi_pdf, df_falhas, f"Período: {dt_inicio} a {dt_fim}")
        st.download_button("🖨️ Baixar Relatório PDF", pdf_bytes, "Relatorio_KPI_Turnos.pdf", "application/pdf",
                           type="primary")
    except:
        pass