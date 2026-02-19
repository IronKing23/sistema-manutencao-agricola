import streamlit as st
import pandas as pd
import re
from fpdf import FPDF
import plotly.express as px
import os
import io
import tempfile
import sys
from datetime import datetime

# Tentativa segura de importar o matplotlib (impede que o app quebre se faltar a biblioteca)
try:
    import matplotlib

    matplotlib.use('Agg')  # Evita abrir janelas no servidor
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
    subtitle="Análise de consumo de materiais por Centro de Custo. Visão gráfica e relatórios para impressão.",
    icon=icon_main
)


# ==============================================================================
# LÓGICA DE PROCESSAMENTO
# ==============================================================================

def limpar_numero(valor):
    if isinstance(valor, str):
        valor = valor.replace('.', '').replace(',', '.')
    return pd.to_numeric(valor, errors='coerce')


def formatar_moeda(valor):
    # Formata para o padrão brasileiro: 1.000,00
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


# Classe personalizada para o PDF otimizada e com Branding
class RelatorioPDF(FPDF):
    def header(self):
        # --- INSERIR LOGO ---
        # Procura pelo arquivo logo_cedro.png na pasta principal do projeto
        caminho_logo = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logo_cedro.png")
        if not os.path.exists(caminho_logo):
            # Tenta na pasta atual como fallback
            caminho_logo = "logo_cedro.png"

        if os.path.exists(caminho_logo):
            # Posiciona o logo no canto superior esquerdo (x=10, y=8, largura=12mm)
            self.image(caminho_logo, 10, 8, 12)

        # --- TÍTULO DO RELATÓRIO ---
        self.set_font('Arial', 'B', 14)
        self.set_text_color(50, 50, 50)
        titulo = 'Relatório Consumo de Materiais, Cedro'.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, titulo, 0, 1, 'C')  # 'C' Centraliza o texto na folha

        # --- LINHA DIVISÓRIA ---
        self.set_draw_color(200, 200, 200)
        y_linha = max(self.get_y() + 2, 22)  # Garante que a linha fique abaixo do logo
        self.line(10, y_linha, 200, y_linha)
        self.set_y(y_linha + 4)

    def footer(self):
        # --- RODAPÉ COM DATA E HORA ---
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)

        data_hora_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        texto_rodape = f'Gerado em: {data_hora_atual}  |  Página {self.page_no()}'
        texto_rodape = texto_rodape.encode('latin-1', 'replace').decode('latin-1')

        self.cell(0, 10, texto_rodape, 0, 0, 'C')


@st.cache_data(show_spinner="Processando arquivos e gerando relatórios...", ttl=600)
def processar_e_gerar_relatorios(df, data_inicio, data_fim):
    """
    Recebe o DataFrame e o período escolhido pelo usuário.
    Gera página de resumo, gráficos com histórico e tabelas do período alvo de forma otimizada.
    """
    # Limpeza e Conversão
    df['DATA_UTILIZACAO'] = pd.to_datetime(df['DATA_UTILIZACAO'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['DATA_UTILIZACAO', 'CENTRO_CUSTO'])

    if df['QTD'].dtype == object: df['QTD'] = df['QTD'].apply(limpar_numero)
    if df['VALOR_TOTAL'].dtype == object: df['VALOR_TOTAL'] = df['VALOR_TOTAL'].apply(limpar_numero)

    # Preparar Excel em Memória
    excel_io = io.BytesIO()

    # Preparar PDF com margens menores para aproveitar melhor a folha
    pdf = RelatorioPDF()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)

    arquivos_temporarios = []

    # --- PÁGINA 1 DO PDF E ORDENAÇÃO: RESUMO EXECUTIVO (FILTRADO) ---
    mask_global_periodo = (df['DATA_UTILIZACAO'].dt.date >= data_inicio) & (df['DATA_UTILIZACAO'].dt.date <= data_fim)
    df_resumo = df[mask_global_periodo]

    # Ordena de forma inteligente os centros de custo: Do maior gasto para o menor
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

        # Título da Seção
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(22, 102, 53)  # Verde escuro (inspirado no seu logo)
        str_periodo_resumo = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        pdf.cell(0, 10, f"Resumo Executivo ({str_periodo_resumo})", 0, 1, 'L')
        pdf.ln(5)

        # Formatação de Tópicos
        pdf.set_text_color(0, 0, 0)

        # Tópico 1
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 6, "1. Custo Total no Periodo:", 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 6, f"   A soma de todos os materiais consumidos foi de {formatar_moeda(total_gasto_resumo)}.", 0, 1)
        pdf.ln(4)

        # Tópico 2
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 6, "2. Principal Centro de Custo:", 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 6, f"   O setor '{maior_cc_resumo}' liderou o consumo financeiro.", 0, 1)
        pdf.cell(0, 6,
                 f"   Responsavel por {formatar_moeda(maior_valor_resumo)} ({percentual_maior_resumo:.1f}% do total).",
                 0, 1)
        pdf.ln(4)

        # Tópico 3
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 6, "3. Material de Maior Impacto:", 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 6, f"   O item mais custoso foi '{maior_mat_resumo[:60]}...',", 0, 1)
        pdf.cell(0, 6, f"   totalizando {formatar_moeda(maior_mat_valor_resumo)} em gastos.", 0, 1)
        pdf.ln(10)
    else:
        centros_de_custo_ordenados = []

    primeiro_centro = True

    # Usando o motor padrão do pandas (openpyxl)
    with pd.ExcelWriter(excel_io) as writer:
        for centro in centros_de_custo_ordenados:
            df_centro = df[df['CENTRO_CUSTO'] == centro]

            mask_periodo = (df_centro['DATA_UTILIZACAO'].dt.date >= data_inicio) & (
                        df_centro['DATA_UTILIZACAO'].dt.date <= data_fim)
            df_periodo = df_centro[mask_periodo]

            # Se a categoria NÃO tem dados no período filtrado, pula
            if df_periodo.empty:
                continue

            nome_aba = re.sub(r'[\\/*?:\[\]]', '', str(centro))[:31]

            totais_diarios = df_centro.groupby('DATA_UTILIZACAO')['VALOR_TOTAL'].sum().reset_index()
            totais_diarios = totais_diarios.sort_values('DATA_UTILIZACAO')

            # --- GERAR GRÁFICO MAIS COMPACTO ---
            img_temp = None
            if MATPLOTLIB_AVAILABLE:
                # figsize reduzida (altura de 4 para 3) para ocupar menos espaço da folha
                fig, ax = plt.subplots(figsize=(8.5, 3))
                ax.plot(totais_diarios['DATA_UTILIZACAO'], totais_diarios['VALOR_TOTAL'], marker='o', color='#166635',
                        linewidth=1.5, markersize=4)  # Cor verde Cedro
                ax.set_title(f'Evolução do Histórico: {centro}', fontsize=11)
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

            # --- MONTAR PÁGINA DO PDF (LÓGICA OTIMIZADA) ---
            if primeiro_centro:
                pdf.add_page()
                primeiro_centro = False
            else:
                # Otimização de espaço: Se não couber cabeçalho + gráfico (~85mm), vai pra nova página
                # A altura de uma página A4 é 297mm. Subtraindo a margem inferior, o limite seguro é ~200mm.
                if pdf.get_y() > 190:
                    pdf.add_page()
                else:
                    pdf.ln(10)
                    pdf.set_draw_color(180, 180, 180)
                    pdf.set_line_width(0.5)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())  # Linha divisória limpa
                    pdf.ln(8)

            pdf.set_font('Arial', 'B', 13)
            pdf.set_text_color(50, 50, 50)

            titulo_centro = f"Centro de Custo: {centro}".encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 8, titulo_centro, 0, 1)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

            # Insere o gráfico menor
            if img_temp:
                pdf.image(img_temp, x=10, w=190)

            pdf.ln(2)

            # --- PREPARAR AS TABELAS MAIS COMPACTAS ---
            dias_unicos_periodo = sorted(df_periodo['DATA_UTILIZACAO'].dt.date.unique(), reverse=True)
            linhas_excel = []

            for dia in dias_unicos_periodo:
                df_dia = df_periodo[df_periodo['DATA_UTILIZACAO'].dt.date == dia]

                materiais_agrupados = df_dia.groupby('MATERIAL')[['QTD', 'VALOR_TOTAL']].sum().reset_index()
                top_20 = materiais_agrupados.sort_values('VALOR_TOTAL', ascending=False).head(20)

                data_str = pd.to_datetime(dia).strftime('%d/%m/%Y')
                linhas_excel.append({'Material': f'--- DATA: {data_str} ---', 'Quantidade': '', 'Valor Total': ''})

                # Cabeçalho da Data
                pdf.set_font('Arial', 'B', 10)
                pdf.set_fill_color(230, 240, 230)  # Fundo verde bem clarinho
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 6, f" DATA: {data_str} (Top 20)", 1, 1, 'L', fill=True)

                # Cabeçalhos Colunas (Altura 5 para otimizar espaço)
                pdf.set_font('Arial', 'B', 8)
                pdf.cell(125, 5, " Material", 1)
                pdf.cell(25, 5, " Quantidade", 1, 0, 'C')
                pdf.cell(40, 5, " Valor Total", 1, 1, 'R')

                # Linhas da tabela (Altura 5)
                pdf.set_font('Arial', '', 8)
                for _, mat in top_20.iterrows():
                    nome_mat = str(mat['MATERIAL'])[:70]  # Permite um pouco mais de texto
                    nome_mat = nome_mat.encode('latin-1', 'replace').decode('latin-1')

                    pdf.cell(125, 5, f" {nome_mat}", 1)
                    pdf.cell(25, 5, str(mat['QTD']), 1, 0, 'C')
                    pdf.cell(40, 5, f"{formatar_moeda(mat['VALOR_TOTAL'])} ", 1, 1, 'R')

                    linhas_excel.append({
                        'Material': mat['MATERIAL'],
                        'Quantidade': mat['QTD'],
                        'Valor Total': mat['VALOR_TOTAL']
                    })

                linhas_excel.append({'Material': '', 'Quantidade': '', 'Valor Total': ''})
                pdf.ln(3)  # Espaço menor entre dias

            if linhas_excel:
                df_aba = pd.DataFrame(linhas_excel)
                df_aba.to_excel(writer, sheet_name=nome_aba, index=False)

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
    st.warning(
        "⚠️ **Atenção:** A biblioteca `matplotlib` não está instalada no ambiente. Os gráficos do PDF foram desativados. Digite: `pip install matplotlib` no terminal.")

with st.container(border=True):
    st.markdown("##### 📂 Fonte de Dados")
    arquivo_upload = st.file_uploader("Selecione a base de materiais (Planilha Excel)", type=['xlsx', 'xls', 'csv'])

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

            if st.button("🚀 Processar Base de Dados", type="primary", use_container_width=True):
                st.session_state['df_custos'] = df_lido

    except Exception as e:
        st.error(f"Erro inesperado: {e}")

if 'df_custos' in st.session_state and st.session_state['df_custos'] is not None:
    st.markdown("---")

    df_base = st.session_state['df_custos'].copy()

    df_base['DATA_UTILIZACAO_TEMP'] = pd.to_datetime(df_base['DATA_UTILIZACAO'], dayfirst=True, errors='coerce')
    datas_disponiveis = df_base['DATA_UTILIZACAO_TEMP'].dropna().dt.date
    if not datas_disponiveis.empty:
        min_date = datas_disponiveis.min()
        max_date = datas_disponiveis.max()
    else:
        min_date = datetime.today().date()
        max_date = datetime.today().date()

    col_data, _ = st.columns([2, 2])
    with col_data:
        datas_selecionadas = st.date_input(
            "📅 Período Específico para Análise:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    if isinstance(datas_selecionadas, tuple) and len(datas_selecionadas) == 2:
        data_inicio, data_fim = datas_selecionadas
    else:
        st.warning("Selecione a data final para continuar.")
        st.stop()

    str_periodo = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"

    with st.spinner("Compilando relatórios e formatando a interface..."):
        excel_bytes, pdf_bytes, df_clean = processar_e_gerar_relatorios(df_base, data_inicio, data_fim)

    mask_ui = (df_clean['DATA_UTILIZACAO'].dt.date >= data_inicio) & (df_clean['DATA_UTILIZACAO'].dt.date <= data_fim)
    df_periodo_ui = df_clean[mask_ui]

    # --- UI: RESUMO EXECUTIVO REFINADO ---
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

        🔹 **Material de Maior Impacto:** {maior_mat}  
        *(Responsável por {formatar_moeda(maior_mat_valor)} em gastos operacionais)*
        """)
    else:
        st.markdown(f"### 📝 Resumo Executivo")
        st.warning(f"Não há registros de consumo para o período de {str_periodo}.")

    st.markdown("<br>", unsafe_allow_html=True)

    tab_graficos, tab_detalhes = st.tabs(["📈 Visão Gráfica", "📋 Detalhamento em Tabela"])

    with tab_graficos:
        c_linha, c_pizza = st.columns([2, 1])

        with c_linha:
            st.markdown("##### Evolução de Custos Diários")
            df_timeline = df_clean.groupby(['DATA_UTILIZACAO', 'CENTRO_CUSTO'])['VALOR_TOTAL'].sum().reset_index()
            # Gráfico de linhas usa verde Cedro e outras cores padrão do plotly
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

    with tab_detalhes:
        st.markdown(f"##### 📋 Top materiais consumidos no período")
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
                    "MATERIAL": st.column_config.TextColumn("Material Utilizado", width="large"),
                    "QTD": st.column_config.NumberColumn("Quantidade"),
                    "VALOR_TOTAL": st.column_config.NumberColumn("Valor Total (R$)", format="R$ %.2f")
                }
            )
        else:
            st.info("Nenhum dado tabular disponível para este filtro.")

    st.markdown("---")

    st.markdown("### 🖨️ Documentos para Impressão")
    st.caption("Relatório otimizado em PDF (com resumo executivo e gráficos) e detalhamento bruto em Excel.")

    nome_padrao_arquivo = f"Custos_{data_inicio.strftime('%d%m%y')}_a_{data_fim.strftime('%d%m%y')}"

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