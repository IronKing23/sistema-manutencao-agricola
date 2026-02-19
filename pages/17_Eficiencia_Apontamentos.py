import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import io

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_ui import load_custom_css, ui_header, ui_kpi_card, ui_empty_state
from utils_icons import get_icon

# --- CONFIGURAÇÃO INICIAL ---
load_custom_css()

icon_main = get_icon("dashboard", "#2196F3", "36")
ui_header(
    title="Análise de Eficiência de Mão de Obra",
    subtitle="Dashboard Gerencial: Cruzamento RH vs. PIMS com filtros de Produtividade e Serviço.",
    icon=icon_main
)


# ==============================================================================
# 1. MOTOR DE PROCESSAMENTO (ETL)
# ==============================================================================

def safe_float(val):
    """Converte strings financeiras/numéricas (0,08) para float (0.08)."""
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    try:
        return float(str(val).replace(',', '.').strip())
    except:
        return 0.0


def parse_rh_time_range(val):
    """
    Decodifica o formato de ponto '06.30/16.30' para horas decimais líquidas.
    Ex: '07.00/17.00' -> 10.0 horas.
    """
    if pd.isna(val) or str(val).strip() in ['-', '', 'FOLGA', 'FERIADO', 'DSR', 'COMPENSADO']: return 0.0
    try:
        val = str(val).replace(',', '.')
        if '/' in val:
            s_str, e_str = val.split('/')

            def to_h(t):
                if '.' in t:
                    parts = t.split('.')
                    return float(parts[0]) + float(parts[1]) / 60.0
                return float(t)

            s, e = to_h(s_str), to_h(e_str)
            if e < s: e += 24.0
            return max(0.0, e - s)
    except:
        return 0.0
    return 0.0


@st.cache_data(show_spinner="Processando inteligência de dados...", ttl=600)
def processar_dados_corporativos(file_pims, file_rh):
    try:
        # --- A. PIMS (PRODUÇÃO) ---
        pims = pd.read_excel(file_pims)
        pims.columns = [c.upper().strip() for c in pims.columns]

        req_pims = ['MATRICULA', 'HORAS']
        if not set(req_pims).issubset(pims.columns):
            st.error(f"PIMS inválido. Faltam: {req_pims}")
            return None

        col_data = 'INICIO' if 'INICIO' in pims.columns else 'DATA'
        pims['DT_REF'] = pd.to_datetime(pims[col_data], dayfirst=True, errors='coerce').dt.date
        pims['HORAS_DEC'] = pims['HORAS'].apply(safe_float)

        # Garante colunas de classificação
        if 'TIPO_OPER' not in pims.columns: pims['TIPO_OPER'] = 'GERAL'
        if 'SERVICO' not in pims.columns: pims['SERVICO'] = pims.get('OPERACAO', 'Geral')

        # Separa horas por tipo (Produtivo vs Improdutivo)
        pims['HORAS_PROD'] = np.where(pims['TIPO_OPER'].astype(str).str.contains('IMPRODUTIVO', na=False, case=False),
                                      0, pims['HORAS_DEC'])
        pims['HORAS_IMPROD'] = np.where(pims['TIPO_OPER'].astype(str).str.contains('IMPRODUTIVO', na=False, case=False),
                                        pims['HORAS_DEC'], 0)

        # Agrupamento PIMS
        pims_agg = pims.groupby(['MATRICULA', 'DT_REF']).agg({
            'HORAS_DEC': 'sum',  # Total
            'HORAS_PROD': 'sum',  # Só Produtivo
            'HORAS_IMPROD': 'sum',  # Só Improdutivo
            'COLABORADOR': 'first',
            # Concatena serviços únicos do dia para filtro de texto
            'SERVICO': lambda x: ' | '.join(list(set([str(v) for v in x if pd.notna(v)]))),
            'TIPO_OPER': lambda x: ' | '.join(list(set([str(v) for v in x if pd.notna(v)])))
        }).reset_index()

        pims_agg['MATRICULA'] = pims_agg['MATRICULA'].astype(str).str.split('.').str[0].str.strip()

        # --- B. RH (PONTO) ---
        rh = pd.read_excel(file_rh, skiprows=2, header=None)
        rh = rh.rename(columns={0: 'PREFIX', 1: 'MAT_ID', 2: 'NOME', 3: 'TURMA', 4: 'DATA', 8: 'REAL_H', 9: 'REAL_I'})
        rh = rh[pd.to_numeric(rh['MAT_ID'], errors='coerce').notna()].copy()

        rh['DT_REF'] = pd.to_datetime(rh['DATA'], dayfirst=False, errors='coerce').dt.date
        rh['PREFIX_S'] = pd.to_numeric(rh['PREFIX'], errors='coerce').fillna(0).astype(int).astype(str)
        rh['ID_S'] = pd.to_numeric(rh['MAT_ID'], errors='coerce').fillna(0).astype(int).astype(str)
        rh['MAT_FULL'] = rh['PREFIX_S'] + rh['ID_S'].str.zfill(5)

        rh['H_TRAB'] = rh['REAL_H'].apply(parse_rh_time_range)
        rh['H_INT'] = rh['REAL_I'].apply(parse_rh_time_range)
        rh['H_LIQ'] = (rh['H_TRAB'] - rh['H_INT']).clip(lower=0)

        rh_agg = rh.groupby(['MAT_FULL', 'DT_REF']).agg({
            'H_LIQ': 'sum', 'NOME': 'first', 'TURMA': 'first'
        }).reset_index()

        # --- C. MERGE ---
        df_final = pd.merge(rh_agg, pims_agg, left_on=['MAT_FULL', 'DT_REF'], right_on=['MATRICULA', 'DT_REF'],
                            how='left')

        # Fill NA
        cols_fill = ['HORAS_DEC', 'HORAS_PROD', 'HORAS_IMPROD']
        df_final[cols_fill] = df_final[cols_fill].fillna(0)
        df_final['SERVICO'] = df_final['SERVICO'].fillna("-")
        df_final['TIPO_OPER'] = df_final['TIPO_OPER'].fillna("-")

        # Classificação de Status
        conditions = [
            (df_final['H_LIQ'] > 4) & (df_final['HORAS_DEC'] < 0.2),
            (df_final['H_LIQ'] > 0),  # Normal
        ]
        choices = ['CRÍTICO (Sem Apont.)', 'NORMAL']
        df_final['STATUS'] = np.select(conditions, choices, default='NORMAL')

        return df_final

    except Exception as e:
        st.error(f"Erro fatal: {e}")
        return None


# ==============================================================================
# 2. INTERFACE E LÓGICA DE FILTROS AVANÇADOS
# ==============================================================================

if 'dataset_rh' not in st.session_state: st.session_state['dataset_rh'] = None

with st.expander("📂 Carregar Dados (PIMS + RH)", expanded=(st.session_state['dataset_rh'] is None)):
    c1, c2 = st.columns(2)
    f_pims = c1.file_uploader("Produção (PIMS)", type=['xlsx'])
    f_rh = c2.file_uploader("Ponto (RH)", type=['xlsx'])
    if f_pims and f_rh and st.button("Carregar", type="primary"):
        df_proc = processar_dados_corporativos(f_pims, f_rh)
        if df_proc is not None:
            st.session_state['dataset_rh'] = df_proc
            st.rerun()

if st.session_state['dataset_rh'] is None:
    ui_empty_state("Aguardando importação.", icon="📊")
    st.stop()

df = st.session_state['dataset_rh']

# --- SIDEBAR: FILTROS PODEROSOS ---
with st.sidebar:
    st.header("🔍 Filtros Avançados")

    # 1. Data
    min_d, max_d = df['DT_REF'].min(), df['DT_REF'].max()
    datas = st.date_input("Período", [min_d, max_d], min_value=min_d, max_value=max_d)

    # 2. Turma
    lista_turmas = ["Todas"] + sorted(df['TURMA'].dropna().astype(str).unique().tolist())
    sel_turma = st.selectbox("Turma / Setor", lista_turmas)

    # 3. Colaborador
    df_temp = df if sel_turma == "Todas" else df[df['TURMA'].astype(str) == sel_turma]
    lista_nomes = ["Todos"] + sorted(df_temp['NOME'].unique().tolist())
    sel_nome = st.selectbox("Colaborador", lista_nomes)

    st.divider()

    # 4. TIPO DE APONTAMENTO (O que o usuário pediu)
    st.markdown("### ⚙️ Tipo de Serviço")
    tipo_visualizacao = st.radio("Base de Cálculo da Eficiência:",
                                 ["Horas Totais (Geral)", "Apenas Produtivas", "Apenas Improdutivas"])

    # 5. FILTRO POR TEXTO (Serviço específico)
    filtro_servico = st.text_input("Filtrar Serviço (ex: Elétrica, Comboio)",
                                   help="Busca por palavra-chave nos apontamentos")

# --- APLICAÇÃO DOS FILTROS NA DATA ---
df_view = df.copy()
if isinstance(datas, list) and len(datas) == 2:
    df_view = df_view[(df_view['DT_REF'] >= datas[0]) & (df_view['DT_REF'] <= datas[1])]
if sel_turma != "Todas": df_view = df_view[df_view['TURMA'].astype(str) == sel_turma]
if sel_nome != "Todos": df_view = df_view[df_view['NOME'] == sel_nome]

# Filtro de Texto (Serviço)
if filtro_servico:
    # Filtra linhas onde a coluna SERVICO contém o texto (case insensitive)
    df_view = df_view[df_view['SERVICO'].str.contains(filtro_servico, case=False, na=False)]

# --- CÁLCULO DINÂMICO DE EFICIÊNCIA ---
# Define qual coluna de horas usar baseado no Radio Button
col_horas_alvo = 'HORAS_DEC'  # Default Total
if tipo_visualizacao == "Apenas Produtivas":
    col_horas_alvo = 'HORAS_PROD'
elif tipo_visualizacao == "Apenas Improdutivas":
    col_horas_alvo = 'HORAS_IMPROD'

# Recalcula eficiência na view filtrada
df_view['EFICIENCIA_DINAMICA'] = np.where(
    df_view['H_LIQ'] > 0.1,
    (df_view[col_horas_alvo] / df_view['H_LIQ']) * 100,
    0.0
)
df_view['EFICIENCIA_VISUAL'] = df_view['EFICIENCIA_DINAMICA'].clip(0, 120)

# --- DASHBOARD ---
# KPIs
efi_media = df_view['EFICIENCIA_DINAMICA'].mean()
h_rh = df_view['H_LIQ'].sum()
h_alvo = df_view[col_horas_alvo].sum()
fantasmas = df_view[df_view['STATUS'] == 'CRÍTICO (Sem Apont.)']['NOME'].nunique()

c1, c2, c3, c4 = st.columns(4)
cor_kpi = "#10B981" if efi_media >= 85 else ("#F59E0B" if efi_media >= 70 else "#EF4444")

label_horas = "Horas Totais"
if tipo_visualizacao == "Apenas Produtivas": label_horas = "Horas Produtivas"
if tipo_visualizacao == "Apenas Improdutivas": label_horas = "Horas Improdutivas"

ui_kpi_card(c1, "Eficiência", f"{efi_media:.1f}%", get_icon("check", cor_kpi), cor_kpi, f"Base: {tipo_visualizacao}")
ui_kpi_card(c2, "Horas Pagas (RH)", f"{h_rh:.0f} h", get_icon("clock", "#3B82F6"), "#3B82F6")
ui_kpi_card(c3, label_horas, f"{h_alvo:.0f} h", get_icon("gear", "#F59E0B"), "#F59E0B")
ui_kpi_card(c4, "Sem Apontamento", f"{fantasmas}", get_icon("fire", "#EF4444"), "#EF4444",
            "Pessoas Presentes s/ Produção")

st.markdown("<br>", unsafe_allow_html=True)

# ABAS
tab1, tab2, tab3 = st.tabs(["📅 Calendário Gerencial", "📊 Ranking & Serviços", "📋 Dados Analíticos"])

with tab1:
    st.markdown("##### Mapa de Calor: Eficiência da Equipe")
    try:
        pivot = df_view.pivot_table(index='NOME', columns='DT_REF', values='EFICIENCIA_VISUAL', aggfunc='mean').fillna(
            0)
        h_calc = max(400, len(pivot) * 25)
        fig = px.imshow(pivot, aspect="auto", color_continuous_scale=['#EF4444', '#F59E0B', '#10B981'],
                        labels=dict(x="Dia", y="Colaborador", color="Eficiência %"),
                        x=[d.strftime('%d/%m') for d in pivot.columns])
        fig.update_layout(height=h_calc)
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.info("Sem dados para o calendário.")

with tab2:
    c_l, c_r = st.columns(2)
    with c_l:
        st.markdown(f"##### 🏆 Ranking ({label_horas})")
        df_rank = df_view.groupby('NOME').agg({col_horas_alvo: 'sum', 'EFICIENCIA_DINAMICA': 'mean'}).reset_index()
        df_rank = df_rank.sort_values(col_horas_alvo, ascending=True).tail(15)
        fig_bar = px.bar(df_rank, x=col_horas_alvo, y='NOME', orientation='h', text_auto='.0f',
                         color='EFICIENCIA_DINAMICA', color_continuous_scale='RdYlGn')
        st.plotly_chart(fig_bar, use_container_width=True)

    with c_r:
        if filtro_servico:
            st.info(f"Visualizando dados filtrados por termo: '{filtro_servico}'")
        st.markdown("##### ⚙️ Tipo de Atividade (Prod vs Improd)")
        # Gráfico simples comparando total produtivo vs improdutivo no período filtrado
        total_prod = df_view['HORAS_PROD'].sum()
        total_improd = df_view['HORAS_IMPROD'].sum()
        df_pie = pd.DataFrame({'Tipo': ['Produtivo', 'Improdutivo'], 'Horas': [total_prod, total_improd]})
        fig_pie = px.pie(df_pie, values='Horas', names='Tipo', hole=0.4, color_discrete_sequence=['#10B981', '#EF4444'])
        st.plotly_chart(fig_pie, use_container_width=True)

with tab3:
    st.markdown("##### Base de Dados Detalhada")
    st.dataframe(
        df_view[['DT_REF', 'NOME', 'TURMA', 'H_LIQ', col_horas_alvo, 'EFICIENCIA_DINAMICA', 'SERVICO']],
        use_container_width=True,
        column_config={
            "DT_REF": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "EFICIENCIA_DINAMICA": st.column_config.ProgressColumn("Eficiência", format="%.0f%%", min_value=0,
                                                                   max_value=120),
            "H_LIQ": st.column_config.NumberColumn("Horas RH", format="%.2f"),
            col_horas_alvo: st.column_config.NumberColumn(f"Horas {tipo_visualizacao}", format="%.2f"),
            "SERVICO": st.column_config.TextColumn("Serviços Realizados", width="large")
        }
    )