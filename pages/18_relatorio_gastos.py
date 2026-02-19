import streamlit as st
import pandas as pd
import re
from fpdf import FPDF
import plotly.express as px
import plotly.graph_objects as go
import os
import io
import tempfile
import sys
from datetime import datetime

# Tentativa segura de importar o matplotlib
try:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import matplotlib.dates as mdates

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils_ui import load_custom_css, ui_header, ui_empty_state
from utils_icons import get_icon

# --- CONFIGURAÇÃO VISUAL ---
load_custom_css()

icon_main = get_icon("dashboard", "#2196F3", "36")
ui_header(
    title="Relatório Gerencial de Custos",
    subtitle="Análise de consumo de materiais e serviços de terceiros por Centro de Custo.",
    icon=icon_main
)


# ==============================================================================
# LÓGICA DE PROCESSAMENTO E PDF
# ==============================================================================

def limpar_numero(valor):
    if isinstance(valor, str):
        valor = valor.replace('.', '').replace(',', '.')
    return pd.to_numeric(valor, errors='coerce')


def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


class RelatorioPDF(FPDF):
    def __init__(self, titulo_relatorio="Relatorio de Custos, Cedro", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.titulo_relatorio = titulo_relatorio

    def header(self):
        caminho_logo = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logo_cedro.png")
        if not os.path.exists(caminho_logo):
            caminho_logo = "logo_cedro.png"

        if os.path.exists(caminho_logo):
            self.image(caminho_logo, 10, 8, 12)

        self.set_font('Arial', 'B', 14)
        self.set_text_color(50, 50, 50)
        titulo = self.titulo_relatorio.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, titulo, 0, 1, 'C')

        self.set_draw_color(200, 200, 200)
        y_linha = max(self.get_y() + 2, 22)
        self.line(10, y_linha, 200, y_linha)
        self.set_y(y_linha + 4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)

        data_hora_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        texto_rodape = f'Gerado em: {data_hora_atual}  |  Pagina {self.page_no()}'
        texto_rodape = texto_rodape.encode('latin-1', 'replace').decode('latin-1')

        self.cell(0, 10, texto_rodape, 0, 0, 'C')


@st.cache_data(show_spinner="Processando arquivos e gerando relatórios...", ttl=600)
def processar_e_gerar_relatorios(df, data_inicio, data_fim, nome_relatorio, label_item):
    df['DATA_UTILIZACAO'] = pd.to_datetime(df['DATA_UTILIZACAO'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['DATA_UTILIZACAO', 'CENTRO_CUSTO'])

    if df['QTD'].dtype == object: df['QTD'] = df['QTD'].apply(limpar_numero)
    if df['VALOR_TOTAL'].dtype == object: df['VALOR_TOTAL'] = df['VALOR_TOTAL'].apply(limpar_numero)

    excel_io = io.BytesIO()

    # Passa o título dinâmico para o PDF
    pdf = RelatorioPDF(titulo_relatorio=nome_relatorio)
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)

    arquivos_temporarios = []

    # --- PÁGINA 1: RESUMO EXECUTIVO + TOP 20 GERAL ---
    mask_global_periodo = (df['DATA_UTILIZACAO'].dt.date >= data_inicio) & (df['DATA_UTILIZACAO'].dt.date <= data_fim)
    df_resumo = df[mask_global_periodo]

    if not df_resumo.empty:
        total_gasto_resumo = df_resumo['VALOR_TOTAL'].sum()

        cc_agrupado_resumo = df_resumo.groupby('CENTRO_CUSTO')['VALOR_TOTAL'].sum().reset_index().sort_values(
            'VALOR_TOTAL', ascending=False)
        centros_de_custo_ordenados = cc_agrupado_resumo['CENTRO_CUSTO'].tolist()

        maior_cc_resumo = cc_agrupado_resumo.iloc[0]['CENTRO_CUSTO']
        maior_valor_resumo = cc_agrupado_resumo.iloc[0]['VALOR_TOTAL']
        percentual_maior_resumo = (maior_valor_resumo / total_gasto_resumo) * 100 if total_gasto_resumo > 0 else 0

        mat_agrupado_resumo = df_resumo.groupby('MATERIAL')['VALOR_TOTAL'].sum().reset_index().sort_values(
            'VALOR_TOTAL', ascending=False)
        maior_mat_resumo = mat_agrupado_resumo.iloc[0]['MATERIAL']
        maior_mat_valor_resumo = mat_agrupado_resumo.iloc[0]['VALOR_TOTAL']

        pdf.add_page()

        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(22, 102, 53)
        str_periodo_resumo = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        pdf.cell(0, 10, f"Resumo Executivo ({str_periodo_resumo})", 0, 1, 'L')
        pdf.ln(3)

        pdf.set_text_color(0, 0, 0)

        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 6, "1. Custo Total no Periodo:", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"   A soma total apurada no periodo foi de {formatar_moeda(total_gasto_resumo)}.", 0, 1)
        pdf.ln(2)

        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 6, "2. Principal Centro de Custo:", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"   O setor '{maior_cc_resumo}' liderou os gastos financeiros.", 0, 1)
        pdf.cell(0, 6,
                 f"   Responsavel por {formatar_moeda(maior_valor_resumo)} ({percentual_maior_resumo:.1f}% do total).",
                 0, 1)
        pdf.ln(2)

        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 6, f"3. {label_item} de Maior Impacto:", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"   O item/servico mais custoso foi '{maior_mat_resumo[:55]}...',", 0, 1)
        pdf.cell(0, 6, f"   totalizando {formatar_moeda(maior_mat_valor_resumo)} em gastos.", 0, 1)
        pdf.ln(8)

        # --- NOVA SEÇÃO: TOP 20 GERAL NA CAPA ---
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(22, 102, 53)
        pdf.cell(0, 8, f"Top 20 {label_item}s de Maior Custo (Visao Global)", 0, 1)

        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(230, 240, 230)
        pdf.cell(115, 6, f" {label_item}", 1, 0, 'L', fill=True)
        pdf.cell(35, 6, " Centro de Custo", 1, 0, 'C', fill=True)
        pdf.cell(40, 6, " Valor Total", 1, 1, 'R', fill=True)

        pdf.set_font('Arial', '', 8)
        top_20_global = df_resumo.groupby(['MATERIAL', 'CENTRO_CUSTO'])['VALOR_TOTAL'].sum().reset_index().sort_values(
            'VALOR_TOTAL', ascending=False).head(20)

        for _, row in top_20_global.iterrows():
            mat_str = str(row['MATERIAL'])[:65].encode('latin-1', 'replace').decode('latin-1')
            cc_str = str(row['CENTRO_CUSTO'])[:18].encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(115, 5, f" {mat_str}", 1)
            pdf.cell(35, 5, cc_str, 1, 0, 'C')
            pdf.cell(40, 5, f"{formatar_moeda(row['VALOR_TOTAL'])} ", 1, 1, 'R')

        pdf.ln(10)

    else:
        centros_de_custo_ordenados = []

    primeiro_centro = True

    with pd.ExcelWriter(excel_io) as writer:
        for centro in centros_de_custo_ordenados:
            df_centro = df[df['CENTRO_CUSTO'] == centro]

            mask_periodo = (df_centro['DATA_UTILIZACAO'].dt.date >= data_inicio) & (
                    df_centro['DATA_UTILIZACAO'].dt.date <= data_fim)
            df_periodo = df_centro[mask_periodo]

            if df_periodo.empty: continue

            nome_aba = re.sub(r'[\\/*?:\[\]]', '', str(centro))[:31]

            totais_diarios = df_centro.groupby('DATA_UTILIZACAO')['VALOR_TOTAL'].sum().reset_index()
            totais_diarios = totais_diarios.sort_values('DATA_UTILIZACAO')

            img_temp = None
            if MATPLOTLIB_AVAILABLE:
                fig, ax = plt.subplots(figsize=(8.5, 3))
                ax.plot(totais_diarios['DATA_UTILIZACAO'], totais_diarios['VALOR_TOTAL'], marker='o', color='#166635',
                        linewidth=1.5, markersize=4)
                ax.set_title(f'Evolucao do Historico: {centro}', fontsize=11)
                ax.set_ylabel('Valor (R$)', fontsize=9)
                ax.grid(True, linestyle='--', alpha=0.5)

                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
                ax.tick_params(axis='x', labelsize=8, rotation=30)
                ax.tick_params(axis='y', labelsize=8)

                def formato_moeda_grafico(x, pos):
                    return f"R$ {x:,.0f}".replace(',', 'X').replace('.', ',').replace('X', '.')

                ax.yaxis.set_major_formatter(ticker.FuncFormatter(formato_moeda_grafico))

                plt.tight_layout()

                img_temp = tempfile.mktemp(suffix=".png")
                arquivos_temporarios.append(img_temp)
                fig.savefig(img_temp, dpi=150)
                plt.close(fig)

            if primeiro_centro:
                pdf.add_page()
                primeiro_centro = False
            else:
                if pdf.get_y() > 190:
                    pdf.add_page()
                else:
                    pdf.ln(10)
                    pdf.set_draw_color(180, 180, 180)
                    pdf.set_line_width(0.5)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(8)

            pdf.set_font('Arial', 'B', 13)
            pdf.set_text_color(50, 50, 50)

            titulo_centro = f"Centro de Custo: {centro}".encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 8, titulo_centro, 0, 1)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

            if img_temp: pdf.image(img_temp, x=10, w=190)
            pdf.ln(2)

            dias_unicos_periodo = sorted(df_periodo['DATA_UTILIZACAO'].dt.date.unique(), reverse=True)
            linhas_excel = []

            for dia in dias_unicos_periodo:
                df_dia = df_periodo[df_periodo['DATA_UTILIZACAO'].dt.date == dia]

                materiais_agrupados = df_dia.groupby('MATERIAL')[['QTD', 'VALOR_TOTAL']].sum().reset_index()
                top_20 = materiais_agrupados.sort_values('VALOR_TOTAL', ascending=False).head(20)

                data_str = pd.to_datetime(dia).strftime('%d/%m/%Y')
                linhas_excel.append({f'{label_item}': f'--- DATA: {data_str} ---', 'Quantidade': '', 'Valor Total': ''})

                pdf.set_font('Arial', 'B', 10)
                pdf.set_fill_color(230, 240, 230)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 6, f" DATA: {data_str} (Top 20)", 1, 1, 'L', fill=True)

                pdf.set_font('Arial', 'B', 8)
                pdf.cell(125, 5, f" {label_item}", 1)
                pdf.cell(25, 5, " Quantidade", 1, 0, 'C')
                pdf.cell(40, 5, " Valor Total", 1, 1, 'R')

                pdf.set_font('Arial', '', 8)
                for _, mat in top_20.iterrows():
                    nome_mat = str(mat['MATERIAL'])[:70].encode('latin-1', 'replace').decode('latin-1')

                    pdf.cell(125, 5, f" {nome_mat}", 1)
                    pdf.cell(25, 5, str(mat['QTD']), 1, 0, 'C')
                    pdf.cell(40, 5, f"{formatar_moeda(mat['VALOR_TOTAL'])} ", 1, 1, 'R')

                    linhas_excel.append(
                        {f'{label_item}': mat['MATERIAL'], 'Quantidade': mat['QTD'], 'Valor Total': mat['VALOR_TOTAL']})

                linhas_excel.append({f'{label_item}': '', 'Quantidade': '', 'Valor Total': ''})
                pdf.ln(3)

            if linhas_excel:
                df_aba = pd.DataFrame(linhas_excel)
                df_aba.to_excel(writer, sheet_name=nome_aba, index=False)

    # --- PÁGINA FINAL: CURVA ABC (PARETO) ---
    if not df_resumo.empty:
        df_pareto = df_resumo.groupby('MATERIAL')['VALOR_TOTAL'].sum().reset_index().sort_values('VALOR_TOTAL',
                                                                                                 ascending=False)
        df_pareto['% Acumulado'] = (df_pareto['VALOR_TOTAL'].cumsum() / df_pareto['VALOR_TOTAL'].sum()) * 100
        df_pareto['Classe'] = pd.cut(df_pareto['% Acumulado'], bins=[0, 80, 95, 100], labels=['A', 'B', 'C'],
                                     right=True)

        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(22, 102, 53)
        pdf.cell(0, 8, "Analise de Pareto (Curva ABC)", 0, 1, 'L')
        pdf.ln(2)

        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(50, 50, 50)
        texto_abc = (
            "A Curva ABC e um metodo de categorizacao de custos baseado no principio de Pareto (80/20). "
            "Os itens classificados como 'Classe A' representam cerca de 80% do valor total consumido no periodo, "
            "sendo os itens de maior impacto financeiro e que exigem controle e negociacao rigorosos por parte da gestao. "
            "Abaixo apresentamos o grafico e a classificacao dos 20 principais itens ofensores."
        )
        pdf.multi_cell(0, 5, texto_abc.encode('latin-1', 'replace').decode('latin-1'))
        pdf.ln(5)

        # Gráfico ABC
        if MATPLOTLIB_AVAILABLE:
            fig, ax1 = plt.subplots(figsize=(8.5, 3.5))
            top_30_pareto = df_pareto.head(30)

            ax1.bar(range(len(top_30_pareto)), top_30_pareto['VALOR_TOTAL'], color='#166635', alpha=0.8)
            ax1.set_ylabel('Valor (R$)', color='#166635', fontsize=9)
            ax1.tick_params(axis='y', labelcolor='#166635', labelsize=8)
            ax1.set_xticks([])

            def formato_moeda_abc(x, pos):
                return f"R$ {x:,.0f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            ax1.yaxis.set_major_formatter(ticker.FuncFormatter(formato_moeda_abc))

            ax2 = ax1.twinx()
            ax2.plot(range(len(top_30_pareto)), top_30_pareto['% Acumulado'], color='#F59E0B', marker='D', ms=3,
                     linewidth=2)
            ax2.set_ylabel('% Acumulado', color='#F59E0B', fontsize=9)
            ax2.tick_params(axis='y', labelcolor='#F59E0B', labelsize=8)
            ax2.set_ylim([0, 105])

            plt.title('Curva ABC - Evolucao de Gastos', fontsize=11)
            plt.tight_layout()

            img_abc = tempfile.mktemp(suffix=".png")
            arquivos_temporarios.append(img_abc)
            fig.savefig(img_abc, dpi=150)
            plt.close(fig)

            pdf.image(img_abc, x=10, w=190)
            pdf.ln(5)

        # Tabela ABC (Top 20 itens)
        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(230, 240, 230)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(105, 6, f" {label_item}", 1, 0, 'L', fill=True)
        pdf.cell(20, 6, " Classe", 1, 0, 'C', fill=True)
        pdf.cell(25, 6, " % Acumulado", 1, 0, 'C', fill=True)
        pdf.cell(40, 6, " Valor Total", 1, 1, 'R', fill=True)

        pdf.set_font('Arial', '', 8)
        for _, row in df_pareto.head(20).iterrows():
            mat_str = str(row['MATERIAL'])[:60].encode('latin-1', 'replace').decode('latin-1')
            classe_str = f"Classe {str(row['Classe'])}"
            pct_str = f"{row['% Acumulado']:.1f}%"
            val_str = formatar_moeda(row['VALOR_TOTAL'])

            pdf.cell(105, 5, f" {mat_str}", 1)
            pdf.cell(20, 5, classe_str, 1, 0, 'C')
            pdf.cell(25, 5, pct_str, 1, 0, 'C')
            pdf.cell(40, 5, f"{val_str} ", 1, 1, 'R')

    bytes_excel = excel_io.getvalue()

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = temp_pdf.name
    temp_pdf.close()

    pdf.output(pdf_path)
    with open(pdf_path, "rb") as f:
        bytes_pdf = f.read()

    os.remove(pdf_path)
    for img in arquivos_temporarios:
        try:
            os.remove(img)
        except:
            pass

    return bytes_excel, bytes_pdf, df


# ==============================================================================
# INTERFACE DO STREAMLIT
# ==============================================================================

if not MATPLOTLIB_AVAILABLE:
    st.warning("⚠️ A biblioteca `matplotlib` não está instalada no ambiente. Os gráficos do PDF foram desativados.")

with st.container(border=True):
    st.markdown("##### 📂 Fonte de Dados")
    arquivo_upload = st.file_uploader("Selecione a base de materiais/serviços (Planilha Excel)",
                                      type=['xlsx', 'xls', 'csv'])

if arquivo_upload:
    df_lido = None
    try:
        try:
            df_lido = pd.read_excel(arquivo_upload)
        except Exception as e:
            if 'xlrd' in str(e):
                st.error("⚠️ Falta a biblioteca 'xlrd'. Digite: `pip install xlrd`")
                st.stop()
            else:
                arquivo_upload.seek(0)
                try:
                    df_lido = pd.read_csv(arquivo_upload, sep=None, engine='python', encoding='utf-8')
                except:
                    arquivo_upload.seek(0)
                    df_lido = pd.read_csv(arquivo_upload, sep=None, engine='python', encoding='latin-1')

        if df_lido is not None:
            colunas_necessarias = {'CENTRO_CUSTO', 'DATA_UTILIZACAO', 'MATERIAL', 'QTD', 'VALOR_TOTAL'}
            if not colunas_necessarias.issubset(set(df_lido.columns)):
                st.error(f"Faltam colunas na base. \n\n**Esperadas:** {', '.join(colunas_necessarias)}")
                st.stop()

            # --- VERIFICAÇÃO INTELIGENTE DO TIPO DE ITEM ---
            if 'TIPO_ITEM' not in df_lido.columns:
                st.warning(
                    "A coluna 'TIPO_ITEM' não foi encontrada na planilha. O sistema assumirá que tudo é 'Material'.")
                df_lido['TIPO_ITEM'] = 'MATERIAIS'

            if st.button("🚀 Processar Base de Dados", type="primary", use_container_width=True):
                st.session_state['df_custos'] = df_lido

    except Exception as e:
        st.error(f"Erro inesperado: {e}")

if 'df_custos' in st.session_state and st.session_state['df_custos'] is not None:
    st.markdown("---")

    df_base = st.session_state['df_custos'].copy()

    df_base['DATA_UTILIZACAO_TEMP'] = pd.to_datetime(df_base['DATA_UTILIZACAO'], dayfirst=True, errors='coerce')
    datas_disponiveis = df_base['DATA_UTILIZACAO_TEMP'].dropna().dt.date
    min_date = datas_disponiveis.min() if not datas_disponiveis.empty else datetime.today().date()
    max_date = datas_disponiveis.max() if not datas_disponiveis.empty else datetime.today().date()

    # --- FILTROS AVANÇADOS NA UI ---
    col_data, col_cc, col_tipo = st.columns([1, 1, 1])
    with col_data:
        datas_selecionadas = st.date_input(
            "📅 Período de Análise:",
            value=(min_date, max_date),
            min_value=min_date, max_value=max_date
        )
    with col_cc:
        centros_disponiveis = sorted(df_base['CENTRO_CUSTO'].dropna().unique().tolist())
        cc_selecionados = st.multiselect("Filtro de Centro de Custo:", options=centros_disponiveis,
                                         default=[], help="Deixe em branco para incluir todos.")
    with col_tipo:
        # NOVO: Filtro para separar Materiais de Serviços
        tipo_filtro = st.selectbox(
            "Tipo de Despesa:",
            options=["🛠️ Materiais (Peças, Combustível)", "👷‍♂️ Serviços de Terceiros", "📊 Visão Consolidada (Ambos)"],
            index=0
        )

    if isinstance(datas_selecionadas, tuple) and len(datas_selecionadas) == 2:
        data_inicio, data_fim = datas_selecionadas
    else:
        st.warning("Selecione a data final para continuar.")
        st.stop()

    str_periodo = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"

    # --- APLICAÇÃO DE FILTROS (CENTRO DE CUSTO E TIPO DE DESPESA) ---
    df_filtrado = df_base.copy()

    if cc_selecionados:
        df_filtrado = df_filtrado[df_filtrado['CENTRO_CUSTO'].isin(cc_selecionados)]

    # Tratamento da coluna TIPO_ITEM e alteração de textos
    df_filtrado['TIPO_ITEM_CLEAN'] = df_filtrado['TIPO_ITEM'].astype(str).str.strip().str.upper()

    if "Materiais" in tipo_filtro:
        df_filtrado = df_filtrado[df_filtrado['TIPO_ITEM_CLEAN'] != 'TERCEIROS']
        nome_relatorio = "Relatorio Consumo de Materiais, Cedro"
        label_item = "Material"
    elif "Serviços" in tipo_filtro:
        df_filtrado = df_filtrado[df_filtrado['TIPO_ITEM_CLEAN'] == 'TERCEIROS']
        nome_relatorio = "Relatorio Servicos de Terceiros, Cedro"
        label_item = "Servico Prestado"
    else:
        # Visão Consolidada, não filtra por TIPO_ITEM
        nome_relatorio = "Relatorio Consolidado de Custos, Cedro"
        label_item = "Item / Servico"

    with st.spinner(f"Compilando {nome_relatorio.lower()}..."):
        excel_bytes, pdf_bytes, df_clean = processar_e_gerar_relatorios(df_filtrado, data_inicio, data_fim,
                                                                        nome_relatorio, label_item)

    mask_ui = (df_clean['DATA_UTILIZACAO'].dt.date >= data_inicio) & (df_clean['DATA_UTILIZACAO'].dt.date <= data_fim)
    df_periodo_ui = df_clean[mask_ui]

    # --- UI: RESUMO EXECUTIVO ---
    if not df_periodo_ui.empty:
        total_gasto = df_periodo_ui['VALOR_TOTAL'].sum()
        cc_agrupado = df_periodo_ui.groupby('CENTRO_CUSTO')['VALOR_TOTAL'].sum().reset_index().sort_values(
            'VALOR_TOTAL', ascending=False)
        maior_cc = cc_agrupado.iloc[0]['CENTRO_CUSTO']
        maior_valor = cc_agrupado.iloc[0]['VALOR_TOTAL']
        percentual_maior = (maior_valor / total_gasto) * 100 if total_gasto > 0 else 0
        mat_agrupado = df_periodo_ui.groupby('MATERIAL')['VALOR_TOTAL'].sum().reset_index().sort_values('VALOR_TOTAL',
                                                                                                        ascending=False)
        maior_mat = mat_agrupado.iloc[0]['MATERIAL']
        maior_mat_valor = mat_agrupado.iloc[0]['VALOR_TOTAL']

        st.markdown(f"### 📝 Resumo Executivo")
        st.caption(f"Dados consolidados para o período de {str_periodo}")

        st.info(f"""
        🔹 **Custo Total no Período:** {formatar_moeda(total_gasto)}

        🔹 **Principal Centro de Custo:** {maior_cc}  
        *(Representa {percentual_maior:.1f}% do total, acumulando {formatar_moeda(maior_valor)})*

        🔹 **{label_item.replace('Servico', 'Serviço')} de Maior Impacto:** {maior_mat}  
        *(Responsável por {formatar_moeda(maior_mat_valor)} em gastos operacionais)*
        """)
    else:
        st.markdown(f"### 📝 Resumo Executivo")
        st.warning(f"Não há registros de consumo para os filtros selecionados.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- ABAS DE ANÁLISE ---
    tab_graficos, tab_abc, tab_detalhes = st.tabs(
        ["📈 Evolução & Pizza", "📊 Curva ABC (Pareto)", "📋 Detalhamento em Tabela"])

    with tab_graficos:
        c_linha, c_pizza = st.columns([2, 1])

        with c_linha:
            st.markdown("##### Evolução de Custos Diários")
            df_timeline = df_clean.groupby(['DATA_UTILIZACAO', 'CENTRO_CUSTO'])['VALOR_TOTAL'].sum().reset_index()
            fig_linha = px.line(df_timeline, x='DATA_UTILIZACAO', y='VALOR_TOTAL', color='CENTRO_CUSTO', markers=True,
                                labels={'DATA_UTILIZACAO': 'Data', 'VALOR_TOTAL': 'Custo (R$)',
                                        'CENTRO_CUSTO': 'Centro'})
            fig_linha.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5))
            st.plotly_chart(fig_linha, use_container_width=True)

        with c_pizza:
            st.markdown("##### Distribuição Global (Histórico)")
            cc_agrupado_global = df_clean.groupby('CENTRO_CUSTO')['VALOR_TOTAL'].sum().reset_index().sort_values(
                'VALOR_TOTAL', ascending=False)
            if len(cc_agrupado_global) > 6:
                top_6 = cc_agrupado_global.head(6)
                outros = pd.DataFrame(
                    [{'CENTRO_CUSTO': 'Outros', 'VALOR_TOTAL': cc_agrupado_global.iloc[6:]['VALOR_TOTAL'].sum()}])
                df_pizza = pd.concat([top_6, outros], ignore_index=True)
            else:
                df_pizza = cc_agrupado_global

            fig_pizza = px.pie(df_pizza, values='VALOR_TOTAL', names='CENTRO_CUSTO', hole=0.4,
                               color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pizza.update_traces(textposition='inside', textinfo='percent')
            fig_pizza.update_layout(showlegend=True,
                                    legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5))
            st.plotly_chart(fig_pizza, use_container_width=True)

    with tab_abc:
        st.markdown(f"##### Análise de Pareto ({label_item.replace('Servico', 'Serviço')} Classe A)")
        st.caption("Identifique rapidamente os 20% de itens que representam 80% do seu custo.")
        if not df_periodo_ui.empty:
            df_pareto = df_periodo_ui.groupby('MATERIAL')['VALOR_TOTAL'].sum().reset_index().sort_values('VALOR_TOTAL',
                                                                                                         ascending=False)
            df_pareto['% Acumulado'] = (df_pareto['VALOR_TOTAL'].cumsum() / df_pareto['VALOR_TOTAL'].sum()) * 100

            # Gráfico de Pareto combinado (Barras + Linha de %)
            fig_pareto = go.Figure()
            fig_pareto.add_trace(
                go.Bar(x=df_pareto['MATERIAL'].head(30), y=df_pareto['VALOR_TOTAL'].head(30), name='Valor Total',
                       marker_color='#166635'))
            fig_pareto.add_trace(
                go.Scatter(x=df_pareto['MATERIAL'].head(30), y=df_pareto['% Acumulado'].head(30), name='% Acumulado',
                           yaxis='y2', mode='lines+markers', line=dict(color='#F59E0B', width=3)))

            fig_pareto.update_layout(
                yaxis=dict(title='Custo (R$)'),
                yaxis2=dict(title='% Acumulado', overlaying='y', side='right', range=[0, 105]),
                legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5),
                margin=dict(t=20, b=10)
            )
            st.plotly_chart(fig_pareto, use_container_width=True)

            # Tabela Curva ABC
            df_pareto['Classe'] = pd.cut(df_pareto['% Acumulado'], bins=[0, 80, 95, 100],
                                         labels=['A (80%)', 'B (15%)', 'C (5%)'], right=True)
            st.dataframe(df_pareto.head(20), use_container_width=True, hide_index=True,
                         column_config={"VALOR_TOTAL": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                                        "% Acumulado": st.column_config.NumberColumn("% Acumulado", format="%.1f%%")})
        else:
            st.info("Nenhum dado para Análise de Pareto.")

    with tab_detalhes:
        st.markdown(f"##### 📋 Top itens consumidos no período")
        if not df_periodo_ui.empty:
            df_display = df_periodo_ui.groupby(['DATA_UTILIZACAO', 'CENTRO_CUSTO', 'MATERIAL'])[
                ['QTD', 'VALOR_TOTAL']].sum().reset_index()
            df_display = df_display.sort_values(by=['DATA_UTILIZACAO', 'CENTRO_CUSTO', 'VALOR_TOTAL'],
                                                ascending=[False, True, False])

            st.dataframe(
                df_display,
                use_container_width=True, hide_index=True,
                column_config={
                    "DATA_UTILIZACAO": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "CENTRO_CUSTO": st.column_config.TextColumn("Centro de Custo"),
                    "MATERIAL": st.column_config.TextColumn(f"{label_item.replace('Servico', 'Serviço')}",
                                                            width="large"),
                    "QTD": st.column_config.NumberColumn("Quantidade"),
                    "VALOR_TOTAL": st.column_config.NumberColumn("Valor Total (R$)", format="R$ %.2f")
                }
            )
        else:
            st.info("Nenhum dado tabular disponível para este filtro.")

    st.markdown("---")

    st.markdown("### 🖨️ Documentos para Impressão")
    st.caption("Relatório otimizado em PDF e detalhamento bruto em Excel considerando os filtros aplicados.")

    tipo_arquivo = "Servicos" if "Serviços" in tipo_filtro else (
        "Materiais" if "Materiais" in tipo_filtro else "Consolidado")
    nome_padrao_arquivo = f"{tipo_arquivo}_{data_inicio.strftime('%d%m%y')}_a_{data_fim.strftime('%d%m%y')}"

    c_pdf, c_excel = st.columns(2)
    with c_pdf:
        st.download_button(
            label="📄 Descarregar Relatório PDF",
            data=pdf_bytes,
            file_name=f"Relatorio_{nome_padrao_arquivo}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    with c_excel:
        st.download_button(
            label="📊 Descarregar Tabela Excel",
            data=excel_bytes,
            file_name=f"Detalhe_{nome_padrao_arquivo}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )