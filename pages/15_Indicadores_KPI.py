import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# --- BLINDAGEM DE IMPORTAÇÃO (Essencial para Streamlit Cloud) ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from datetime import datetime, timedelta
from utils_pdf import gerar_relatorio_kpi 

st.set_page_config(layout="wide", page_title="Indicadores de Confiabilidade")
st.title("📈 Indicadores de Performance (MTBF & MTTR)")

# --- CSS MODERNO PARA OS CARDS (Mesmo estilo do Painel) ---
st.markdown("""
<style>
/* Cards KPI */
.kpi-card {
    background-color: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 15px 20px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    transition: all 0.3s ease;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.kpi-card:hover {
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    transform: translateY(-3px);
}
.kpi-icon {
    float: right;
    font-size: 1.8rem;
    margin-top: -5px;
}
.kpi-title {
    font-size: 0.9rem;
    color: #6c757d;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 5px;
}
.kpi-value {
    font-size: 2rem;
    font-weight: 800;
    color: #212529;
}
.kpi-sub {
    font-size: 0.8rem;
    color: #adb5bd;
    margin-top: 5px;
}

/* Adaptação Dark Mode */
@media (prefers-color-scheme: dark) {
    .kpi-card {
        background-color: #262730;
        border-color: #3f3f46;
    }
    .kpi-title { color: #a1a1aa; }
    .kpi-value { color: #f4f4f5; }
}
</style>
""", unsafe_allow_html=True)

# Função auxiliar para desenhar o card
def exibir_card(col, titulo, valor, icone, cor_borda, subtexto=""):
    html_content = f"""
    <div class="kpi-card" style="border-left: 5px solid {cor_borda};">
        <div>
            <div class="kpi-title">{titulo} <span class="kpi-icon">{icone}</span></div>
            <div class="kpi-value">{valor}</div>
            <div class="kpi-sub">{subtexto}</div>
        </div>
    </div>
    """
    col.markdown(html_content, unsafe_allow_html=True)

# --- 1. CONFIGURAÇÕES E FILTROS ---
with st.sidebar:
    st.header("Parâmetros de Cálculo")
    
    horas_operacionais_dia = st.number_input(
        "Horas Operacionais / Dia", 
        min_value=1, max_value=24, value=10, 
        help="Usado para calcular o Tempo Total Disponível no período."
    )
    
    st.divider()
    st.header("Filtros")
    
    conn = get_db_connection()
    
    dt_inicio = st.date_input("De:", datetime.now() - timedelta(days=90))
    dt_fim = st.date_input("Até:", datetime.now())
    
    try:
        df_modelos = pd.read_sql("SELECT DISTINCT modelo FROM equipamentos ORDER BY modelo", conn)
        lista_modelos = df_modelos['modelo'].dropna().unique()
        
        if len(lista_modelos) > 0:
            filtro_modelo = st.multiselect("Filtrar por Modelo", options=lista_modelos, placeholder="Todos (Tratores, Colhedoras...)")
        else:
            st.warning("⚠️ Nenhum modelo cadastrado.")
            filtro_modelo = []
            
    except Exception as e:
        st.error("Erro ao carregar modelos.")
        filtro_modelo = []

    query_frotas = "SELECT DISTINCT frota FROM equipamentos"
    params_frotas = []
    
    if filtro_modelo:
        query_frotas += f" WHERE modelo IN ({','.join(['?']*len(filtro_modelo))})"
        params_frotas = filtro_modelo
    
    query_frotas += " ORDER BY frota"
    df_frotas = pd.read_sql(query_frotas, conn, params=params_frotas)
    
    filtro_frota = st.multiselect("Filtrar Frota Específica", options=df_frotas['frota'].unique())
    
    conn.close()

# --- 2. CARREGAR DADOS ---
def carregar_dados_kpi():
    conn = get_db_connection()
    
    query = """
    SELECT 
        os.id, 
        e.frota, 
        e.modelo,
        os.data_hora as abertura, 
        os.data_encerramento as fechamento,
        os.classificacao,
        os.maquina_parada,
        op.nome as tipo_servico
    FROM ordens_servico os
    JOIN equipamentos e ON os.equipamento_id = e.id
    JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
    WHERE os.data_hora BETWEEN ? AND ?
    """
    
    params = [dt_inicio, datetime.combine(dt_fim, datetime.max.time())]
    
    if filtro_modelo:
        query += f" AND e.modelo IN ({','.join(['?']*len(filtro_modelo))})"
        params.extend(filtro_modelo)

    if filtro_frota:
        query += f" AND e.frota IN ({','.join(['?']*len(filtro_frota))})"
        params.extend(filtro_frota)
        
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

df = carregar_dados_kpi()

# --- 3. PROCESSAMENTO DOS DADOS ---
if df.empty:
    st.warning("Sem dados para calcular indicadores com os filtros atuais.")
    st.stop()

df['abertura'] = pd.to_datetime(df['abertura'], format='mixed', errors='coerce')
df['fechamento'] = pd.to_datetime(df['fechamento'], format='mixed', errors='coerce')

agora = datetime.now()
df['fechamento_calc'] = df['fechamento'].fillna(agora)
df['duracao_horas'] = (df['fechamento_calc'] - df['abertura']).dt.total_seconds() / 3600

if 'classificacao' not in df.columns: df['classificacao'] = 'Corretiva'
if 'maquina_parada' not in df.columns: df['maquina_parada'] = 1

df['classificacao'] = df['classificacao'].fillna('Corretiva')
df['maquina_parada'] = df['maquina_parada'].fillna(1).astype(int)

# --- 4. CÁLCULO DOS INDICADORES ---

df_falhas = df[
    (df['classificacao'].str.contains('Corretiva', case=False)) & 
    (df['maquina_parada'] == 1)
]

num_falhas = len(df_falhas)
tempo_total_reparo = df_falhas['duracao_horas'].sum()

dias_periodo = (dt_fim - dt_inicio).days + 1
tempo_total_periodo = dias_periodo * horas_operacionais_dia 

if filtro_frota:
    num_maquinas = len(filtro_frota)
elif filtro_modelo:
    num_maquinas = len(df_frotas) 
else:
    num_maquinas = len(df_frotas)

tempo_total_disponivel_frota = tempo_total_periodo * num_maquinas

if num_falhas > 0:
    mttr = tempo_total_reparo / num_falhas
else:
    mttr = 0

tempo_operacao_real = tempo_total_disponivel_frota - tempo_total_reparo

if num_falhas > 0:
    mtbf = tempo_operacao_real / num_falhas
else:
    mtbf = tempo_operacao_real 

if (mtbf + mttr) > 0:
    disponibilidade = (mtbf / (mtbf + mttr)) * 100
else:
    disponibilidade = 100.0

# --- 5. VISUALIZAÇÃO (DASHBOARD MODERNIZADO) ---

st.caption(f"Analisando **{len(df)}** registros de **{num_maquinas}** máquinas no período.")

c1, c2, c3, c4 = st.columns(4)

# MTBF - Azul (Confiabilidade)
exibir_card(c1, "MTBF (Confiabilidade)", f"{mtbf:.1f} h", "🛡️", "#3B82F6", "Quanto MAIOR, melhor")

# MTTR - Laranja (Eficiência)
exibir_card(c2, "MTTR (Eficiência)", f"{mttr:.1f} h", "🔧", "#F59E0B", "Quanto MENOR, melhor")

# Disponibilidade - Verde (Meta)
exibir_card(c3, "Disponibilidade", f"{disponibilidade:.1f}%", "✅", "#10B981", "% tempo pronta para uso")

# Falhas - Vermelho (Alerta)
exibir_card(c4, "Total de Falhas", num_falhas, "🚨", "#EF4444", "Quebras com parada")

st.divider()

# Gráficos
g1, g2 = st.columns(2)

with g1:
    st.subheader("🛠️ MTTR por Tipo de Serviço")
    if not df_falhas.empty:
        df_tipo = df_falhas.groupby('tipo_servico')['duracao_horas'].mean().reset_index()
        fig_mttr = px.bar(
            df_tipo, x='duracao_horas', y='tipo_servico', orientation='h',
            title="<b>Tempo Médio de Reparo (Horas)</b>",
            text_auto='.1f'
        )
        fig_mttr.update_layout(xaxis_title="Horas", yaxis_title=None)
        st.plotly_chart(fig_mttr, use_container_width=True)
    else:
        st.info("Sem dados de falhas para gráfico.")

with g2:
    st.subheader("🚜 Top 5 Máquinas Menos Confiáveis")
    if not df_falhas.empty:
        df_top = df_falhas['frota'].value_counts().reset_index().head(5)
        df_top.columns = ['Frota', 'Qtd Falhas']
        
        df_top['Frota'] = df_top['Frota'].astype(str)
        
        fig_top = px.bar(
            df_top, 
            x='Frota', 
            y='Qtd Falhas', 
            color='Frota', 
            title="<b>Ranking de Quebras (Qtd)</b>",
            text='Qtd Falhas',
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        
        fig_top.update_layout(
            xaxis_title=None,
            yaxis_title="Ocorrências",
            showlegend=True,
            legend_title_text='Máquina',
            hovermode="x unified"
        )
        
        fig_top.update_xaxes(type='category')
        fig_top.update_traces(textposition='outside', textfont_size=14, cliponaxis=False)
        
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("Tudo operando normalmente.")

# --- ÁREA DE DOWNLOAD ---
st.divider()
col_btn, col_exp = st.columns([1, 4])

with col_btn:
    dados_kpis = {
        'mtbf': f"{mtbf:.1f} h",
        'mttr': f"{mttr:.1f} h",
        'disp': f"{disponibilidade:.1f}%",
        'falhas': num_falhas
    }
    
    texto_filtros = f"Período: {dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
    if filtro_modelo: texto_filtros += f" | Modelos: {len(filtro_modelo)}"
    if filtro_frota: texto_filtros += f" | Frotas: {len(filtro_frota)}"
    
    try:
        pdf_bytes = gerar_relatorio_kpi(dados_kpis, df_falhas, texto_filtros)
        
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

with col_exp:
    with st.expander("🔍 Ver Tabela de Dados"):
        df_exibicao = df_falhas.copy()
        df_exibicao['frota'] = df_exibicao['frota'].astype(str)
        st.dataframe(
            df_exibicao[['frota', 'modelo', 'abertura', 'fechamento', 'duracao_horas', 'tipo_servico', 'classificacao']],
            use_container_width=True
        )
