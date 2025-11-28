import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    cursor: help; 
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


# Função auxiliar para desenhar o card COM TOOLTIP
def exibir_card(col, titulo, valor, icone, cor_borda, subtexto="", tooltip=""):
    dica = tooltip if tooltip else f"{titulo}: {subtexto}"
    html_content = f"""
    <div class="kpi-card" style="border-left: 5px solid {cor_borda};" title="{dica}">
        <div>
            <div class="kpi-title">{titulo} {icone}</div>
            <div class="kpi-value">{valor}</div>
            <div class="kpi-sub">{subtexto}</div>
        </div>
    </div>
    """
    col.markdown(html_content, unsafe_allow_html=True)


# --- LÓGICA DE TURNOS ---
def classificar_turno(dt):
    if pd.isnull(dt): return "N/A"
    hora_float = dt.hour + dt.minute / 60.0

    if 6.5 <= hora_float < 15.0:
        return "Turno A (Manhã)"
    elif 15.0 <= hora_float < 23.0:
        return "Turno B (Tarde)"
    else:
        return "Turno C (Noite)"


# --- DEFINIÇÃO DE CORES DOS TURNOS ---
CORES_TURNOS = {
    "Turno A (Manhã)": "#2ECC71",  # Verde
    "Turno B (Tarde)": "#E67E22",  # Laranja
    "Turno C (Noite)": "#8E44AD"  # Roxo
}

# --- 1. FILTROS E CONFIGURAÇÕES ---
with st.sidebar:
    st.header("Parâmetros")
    horas_operacionais_dia = st.number_input("Horas Operacionais / Dia", 1, 24, 20,
                                             help="Base para cálculo de disponibilidade.")
    st.divider()
    st.header("Filtros")

    conn = get_db_connection()
    col_d1, col_d2 = st.columns(2)
    dt_inicio = col_d1.date_input("De:", datetime.now() - timedelta(days=30))
    dt_fim = col_d2.date_input("Até:", datetime.now())

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

    st.markdown("### Filtro de Turno")
    turnos_selecionados = st.multiselect("Exibir apenas:", ["Turno A (Manhã)", "Turno B (Tarde)", "Turno C (Noite)"],
                                         default=["Turno A (Manhã)", "Turno B (Tarde)", "Turno C (Noite)"])
    conn.close()


# --- 2. CARREGAR E PROCESSAR DADOS ---
def carregar_dados():
    conn = get_db_connection()
    query = """
    SELECT 
        os.id as Ticket, 
        e.frota, e.modelo, os.data_hora as abertura, os.data_encerramento as fechamento,
        os.classificacao, os.maquina_parada, op.nome as tipo_servico,
        f_solic.nome as solicitante
    FROM ordens_servico os
    JOIN equipamentos e ON os.equipamento_id = e.id
    JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
    LEFT JOIN funcionarios f_solic ON os.solicitante_id = f_solic.id
    WHERE os.data_hora BETWEEN ? AND ?
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

# Tratamento
df['abertura'] = pd.to_datetime(df['abertura'], format='mixed', errors='coerce')
df['fechamento'] = pd.to_datetime(df['fechamento'], format='mixed', errors='coerce')
df['Turno'] = df['abertura'].apply(classificar_turno)

if turnos_selecionados:
    df = df[df['Turno'].isin(turnos_selecionados)]

agora = datetime.now()
df['fechamento_calc'] = df['fechamento'].fillna(agora)
df['duracao_horas'] = (df['fechamento_calc'] - df['abertura']).dt.total_seconds() / 3600

if 'classificacao' not in df.columns: df['classificacao'] = 'Corretiva'
if 'maquina_parada' not in df.columns: df['maquina_parada'] = 1
df['classificacao'] = df['classificacao'].fillna('Corretiva')
df['maquina_parada'] = df['maquina_parada'].fillna(1).astype(int)

# Separa Falhas
df_falhas = df[(df['classificacao'].str.contains('Corretiva', case=False)) & (df['maquina_parada'] == 1)].copy()

# --- 3. CÁLCULO DE KPIs ---
num_falhas = len(df_falhas)
tempo_total_reparo = df_falhas['duracao_horas'].sum()
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

exibir_card(c1, "MTBF", f"{mtbf:.1f} h", "🛡️", "#3B82F6", "Confiabilidade",
            tooltip="Tempo Médio Entre Falhas. Quanto maior, melhor.")
exibir_card(c2, "MTTR", f"{mttr:.1f} h", "🔧", "#F59E0B", "Agilidade",
            tooltip="Tempo Médio Para Reparo. Quanto menor, melhor.")
exibir_card(c3, "Disponibilidade", f"{disp:.1f}%", "✅", "#10B981", "Tempo pronta",
            tooltip="% do tempo disponível que a máquina não estava quebrada.")
exibir_card(c4, "Total de Falhas", num_falhas, "🚨", "#EF4444", "Quebras",
            tooltip="Total de ocorrências Corretivas com Parada.")

st.divider()

# --- 5. ANÁLISE DETALHADA ---
st.markdown("### 🕒 Análise de Performance")

# Dicionário para armazenar dados para o PDF
graficos_para_pdf = {}

if df_falhas.empty:
    st.info("Sem dados de falhas para gerar gráficos.")
else:
    tab_t1, tab_t2, tab_t4, tab_t3 = st.tabs(
        ["📊 Comparativo Turnos", "🚜 Top Máquinas", "📅 Tendências & Padrões", "📋 Dados Brutos"])

    # -----------------------------------------------------------
    # ABA 1: Comparativo Direto
    # -----------------------------------------------------------
    with tab_t1:
        col_g1, col_g2 = st.columns(2)

        # Volume
        df_turno_qtd = df_falhas['Turno'].value_counts().reset_index()
        df_turno_qtd.columns = ['Turno', 'Qtd']

        # Guardar para PDF
        graficos_para_pdf['turno_qtd'] = list(df_turno_qtd.itertuples(index=False, name=None))

        fig_vol = px.bar(
            df_turno_qtd, x='Turno', y='Qtd', color='Turno', text='Qtd',
            title="<b>Volume de Ocorrências</b>",
            color_discrete_map=CORES_TURNOS
        )
        col_g1.plotly_chart(fig_vol, use_container_width=True)

        # Eficiência
        df_turno_mttr = df_falhas.groupby('Turno')['duracao_horas'].mean().reset_index()
        df_turno_mttr.columns = ['Turno', 'MTTR (h)']
        fig_eff = px.bar(
            df_turno_mttr, x='Turno', y='MTTR (h)', color='Turno', text_auto='.1f',
            title="<b>Eficiência (MTTR) - Tempo Médio de Reparo</b>",
            color_discrete_map=CORES_TURNOS
        )
        col_g2.plotly_chart(fig_eff, use_container_width=True)

    # -----------------------------------------------------------
    # ABA 2: Máquinas
    # -----------------------------------------------------------
    with tab_t2:
        st.markdown("#### Quais máquinas mais impactam a operação?")
        df_matrix = df_falhas.groupby(['frota', 'Turno']).size().reset_index(name='Contagem')
        top_maquinas = df_falhas['frota'].value_counts().head(10).index
        df_matrix_top = df_matrix[df_matrix['frota'].isin(top_maquinas)].copy()
        df_matrix_top['frota'] = df_matrix_top['frota'].astype(str)

        # Guardar dados das TOP 5 para PDF
        try:
            dados_mq = df_falhas['frota'].value_counts().head(5).reset_index()
            dados_mq.columns = ['Frota', 'Qtd']
            dados_mq['Frota'] = dados_mq['Frota'].astype(str)
            graficos_para_pdf['top_maquinas'] = list(dados_mq.itertuples(index=False, name=None))
        except:
            pass

        # Ordenação
        total_por_frota = df_matrix_top.groupby('frota')['Contagem'].sum().sort_values(ascending=True)

        fig_matrix = px.bar(
            df_matrix_top, y='frota', x='Contagem', color='Turno',
            title="<b>Top 10 Máquinas com Mais Quebras (por Turno)</b>",
            orientation='h', text='Contagem',
            category_orders={'frota': total_por_frota.index.tolist()},
            color_discrete_map=CORES_TURNOS
        )
        fig_matrix.update_yaxes(type='category')
        st.plotly_chart(fig_matrix, use_container_width=True)

    # -----------------------------------------------------------
    # ABA 3: Tendências e Padrões (HEATMAP + PARETO)
    # -----------------------------------------------------------
    with tab_t4:
        c_tend1, c_tend2 = st.columns(2)

        with c_tend1:
            st.markdown("##### 📈 Evolução Temporal")
            df_falhas['Data_Dia'] = df_falhas['abertura'].dt.date
            df_trend = df_falhas.groupby(['Data_Dia', 'Turno']).size().reset_index(name='Qtd')

            fig_trend = px.line(
                df_trend, x='Data_Dia', y='Qtd', color='Turno', markers=True,
                title="<b>Evolução Diária de Falhas por Turno</b>",
                color_discrete_map=CORES_TURNOS
            )
            fig_trend.update_xaxes(title=None)
            st.plotly_chart(fig_trend, use_container_width=True)

        with c_tend2:
            st.markdown("##### 🔥 Mapa de Calor: Hora x Dia")

            df_falhas['Hora'] = df_falhas['abertura'].dt.hour
            df_falhas['Dia_Semana'] = df_falhas['abertura'].dt.day_name()

            dias_trad = {'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 'Thursday': 'Qui', 'Friday': 'Sex',
                         'Saturday': 'Sáb', 'Sunday': 'Dom'}
            df_falhas['Dia_Semana_PT'] = df_falhas['Dia_Semana'].map(dias_trad)

            df_heatmap = df_falhas.groupby(['Dia_Semana_PT', 'Hora']).size().reset_index(name='Qtd')
            ordem_dias = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

            fig_heat = px.density_heatmap(
                df_heatmap, x='Hora', y='Dia_Semana_PT', z='Qtd',
                title="<b>Concentração de Falhas</b>",
                color_continuous_scale='Reds',
                category_orders={'Dia_Semana_PT': ordem_dias},
                nbinsx=24
            )
            fig_heat.update_layout(xaxis_title="Hora (0-23h)", yaxis_title=None, clickmode='event+select')

            # Interatividade
            event_dict = st.plotly_chart(
                fig_heat, use_container_width=True,
                on_select="rerun", selection_mode="points", key="heatmap_interativo"
            )

        # Drill-down do Heatmap
        if event_dict and "selection" in event_dict and event_dict["selection"]["points"]:
            ponto = event_dict['selection']['points'][0]
            dia_sel = ponto['y'];
            hora_sel = ponto['x']

            st.markdown(f"### 🔎 Detalhes: {dia_sel} às {hora_sel}h")
            df_zoom = df_falhas[(df_falhas['Dia_Semana_PT'] == dia_sel) & (df_falhas['Hora'] == hora_sel)].copy()

            if not df_zoom.empty:
                df_zoom['frota'] = df_zoom['frota'].astype(str)
                colunas_zoom = ['Ticket', 'frota', 'modelo', 'abertura', 'duracao_horas', 'tipo_servico', 'solicitante']
                cols_finais = [c for c in colunas_zoom if c in df_zoom.columns]

                st.dataframe(
                    df_zoom[cols_finais].sort_values('abertura'),
                    use_container_width=True, hide_index=True,
                    column_config={"abertura": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
                                   "duracao_horas": st.column_config.NumberColumn("h", format="%.1f")}
                )
            else:
                st.info("Sem registros para este ponto.")

        # --- Gráficos Profundos (Scatter e Pareto) ---
        st.divider()
        c_prof1, c_prof2 = st.columns(2)

        with c_prof1:
            st.markdown("##### 🐌 Dispersão: Frequência x Tempo")
            df_scatter = df_falhas.groupby('frota').agg(
                Qtd_Falhas=('Ticket', 'count'), MTTR_Medio=('duracao_horas', 'mean'), Modelo=('modelo', 'first')
            ).reset_index()

            fig_scatter = px.scatter(
                df_scatter, x='Qtd_Falhas', y='MTTR_Medio', color='Modelo', size='Qtd_Falhas', hover_name='frota',
                title="<b>Dispersão: Frequência x Tempo de Reparo</b>"
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        with c_prof2:
            st.markdown("##### 📉 Pareto de Falhas")
            df_pareto = df_falhas['tipo_servico'].value_counts().reset_index()
            df_pareto.columns = ['Tipo', 'Frequencia']

            # Guardar para PDF
            graficos_para_pdf['pareto'] = list(df_pareto.head(5).itertuples(index=False, name=None))

            df_pareto['Acumulado'] = df_pareto['Frequencia'].cumsum()
            df_pareto['Porcentagem'] = 100 * df_pareto['Acumulado'] / df_pareto['Frequencia'].sum()

            fig_pareto = go.Figure()
            fig_pareto.add_trace(
                go.Bar(x=df_pareto['Tipo'], y=df_pareto['Frequencia'], name='Freq.', marker_color='rgb(55, 83, 109)'))
            fig_pareto.add_trace(go.Scatter(x=df_pareto['Tipo'], y=df_pareto['Porcentagem'], name='Acum. %', yaxis='y2',
                                            mode='lines+markers', marker_color='rgb(192, 57, 43)'))
            fig_pareto.update_layout(title='<b>Pareto de Tipos de Falha</b>', yaxis=dict(title='Frequência'),
                                     yaxis2=dict(title='Acumulado (%)', overlaying='y', side='right', range=[0, 110]),
                                     showlegend=False)
            st.plotly_chart(fig_pareto, use_container_width=True)

    # -----------------------------------------------------------
    # ABA 4: Dados Brutos
    # -----------------------------------------------------------
    with tab_t3:
        if 'Ticket' in df_falhas.columns:
            cols_tab = ['Ticket', 'frota', 'Turno', 'abertura', 'duracao_horas', 'tipo_servico', 'solicitante']
        else:
            df_falhas['Ticket'] = df_falhas.index
            cols_tab = ['Ticket', 'frota', 'Turno', 'abertura', 'duracao_horas', 'tipo_servico', 'solicitante']

        df_show = df_falhas.copy()
        df_show['frota'] = df_show['frota'].astype(str)

        st.dataframe(
            df_show[cols_tab].sort_values('abertura', ascending=False),
            use_container_width=True, hide_index=True,
            column_config={
                "Turno": st.column_config.TextColumn("Turno", width="medium"),
                "tipo_servico": st.column_config.TextColumn("Tipo", width="medium"),
                "abertura": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
                "duracao_horas": st.column_config.NumberColumn("h", format="%.2f")
            }
        )

# --- DOWNLOAD ---
st.divider()
col_b, _ = st.columns([1, 4])
with col_b:
    dados_kpi_pdf = {'mtbf': f"{mtbf:.1f} h", 'mttr': f"{mttr:.1f} h", 'disp': f"{disp:.1f}%", 'falhas': num_falhas}
    texto_filtros = f"Período: {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
    if filtro_modelo: texto_filtros += f" | Modelos: {len(filtro_modelo)}"

    try:
        # Envia os dados dos gráficos para o PDF
        pdf_bytes = gerar_relatorio_kpi(dados_kpi_pdf, df_falhas, texto_filtros, graficos_data=graficos_para_pdf)

        st.download_button(
            label="🖨️ Baixar Relatório (PDF)",
            data=pdf_bytes,
            file_name=f"Relatorio_KPI_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")