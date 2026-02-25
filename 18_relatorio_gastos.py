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
import numpy as np

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
from utils_ui import load_custom_css, ui_header, ui_empty_state, ui_kpi_card
from utils_icons import get_icon

# --- CONFIGURAÇÃO VISUAL ---
load_custom_css()

icon_main = get_icon("dashboard", "#2196F3", "36")
ui_header(
    title="Relatório Gerencial de Custos",
    subtitle="Auditoria financeira, análise de requisições e consumo por Centro de Custo.",
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
    def __init__(self, titulo_relatorio="Relatorio de Custos, Cedro", orientacao='L', *args, **kwargs):
        # A orientação agora é recebida dinamicamente
        super().__init__(orientation=orientacao, format='A4', *args, **kwargs)
        self.titulo_relatorio = titulo_relatorio
        self.orientacao = orientacao
        # Largura útil da folha A4 (210x297): Paisagem = 297-20 = 277mm | Retrato = 210-20 = 190mm
        self.largura_util = 277 if orientacao == 'L' else 190

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

        # Linha Divisória Adaptável
        self.set_draw_color(22, 102, 53)
        self.set_line_width(0.5)
        y_linha = max(self.get_y() + 2, 22)
        self.line(10, y_linha, 10 + self.largura_util, y_linha)
        self.set_y(y_linha + 5)
        self.set_line_width(0.2)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)

        self.set_draw_color(220, 220, 220)
        self.line(10, self.get_y() - 2, 10 + self.largura_util, self.get_y() - 2)

        data_hora_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        texto_rodape = f'Emitido automaticamente via Sistema Cedro em: {data_hora_atual}  |  Pagina {self.page_no()}'
        texto_rodape = texto_rodape.encode('latin-1', 'replace').decode('latin-1')

        self.cell(0, 10, texto_rodape, 0, 0, 'C')


@st.cache_data(show_spinner="Processando arquivos e gerando relatórios PDF/Excel...", ttl=600)
def processar_e_gerar_relatorios(df, data_inicio, data_fim, nome_relatorio, label_item, orientacao_pdf='L'):
    df = df.copy()
    df['DATA_UTILIZACAO'] = pd.to_datetime(df['DATA_UTILIZACAO'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['DATA_UTILIZACAO', 'CENTRO_CUSTO'])

    if df['QTD'].dtype == object: df['QTD'] = df['QTD'].apply(limpar_numero)
    if df['VALOR_TOTAL'].dtype == object: df['VALOR_TOTAL'] = df['VALOR_TOTAL'].apply(limpar_numero)

    if 'UN' not in df.columns:
        df['UN'] = '-'
    else:
        df['UN'] = df['UN'].fillna('-').astype(str)

    if 'REQUISITANTE' not in df.columns:
        df['REQUISITANTE'] = 'Não Informado'
    else:
        df['REQUISITANTE'] = df['REQUISITANTE'].fillna('Não Informado').astype(str)
        df['REQUISITANTE'] = df['REQUISITANTE'].replace(['nan', '-', ''], 'Não Informado')

    def integrar_descricao(row):
        mat = str(row['MATERIAL']).strip()
        req = str(row['REQUISITANTE']).strip()
        if req and req != 'Não Informado':
            return f"{mat}\nDetalhamento: {req}"
        return mat

    df['MATERIAL_COMPLETO'] = df.apply(integrar_descricao, axis=1)

    # --- VARIÁVEIS DE GEOMETRIA DINÂMICA (Baseado na Orientação) ---
    w_total = 277 if orientacao_pdf == 'L' else 190

    # Limites estendidos para usar o máximo da folha antes de quebrar a página
    max_y_page = 190 if orientacao_pdf == 'L' else 277

    w_t20 = [160, 67, 50] if orientacao_pdf == 'L' else [100, 50, 40]
    w_rcc = [217, 60] if orientacao_pdf == 'L' else [140, 50]
    w_req = [217, 60] if orientacao_pdf == 'L' else [140, 50]
    w_det = [177, 20, 30, 50] if orientacao_pdf == 'L' else [105, 15, 25, 45]
    w_abc = [177, 30, 30, 40] if orientacao_pdf == 'L' else [105, 20, 25, 40]
    w_cc_hm = 60 if orientacao_pdf == 'L' else 40

    # --- FUNÇÃO OTIMIZADA COM REPETIÇÃO DE CABEÇALHO E CORREÇÃO DE COR ---
    def desenhar_linha_multicell(pdf_obj, textos, larguras, alinhamentos, fill_row, func_cabecalho=None):
        pdf_obj.set_font('Arial', '', 8)
        texto_material = str(textos[0]).encode('latin-1', 'replace').decode('latin-1')

        largura_util = larguras[0] - 2
        largura_texto = pdf_obj.get_string_width(texto_material)
        linhas_estimadas = max(1, int((largura_texto / largura_util) + 0.9))

        altura_linha = 4
        altura_total = max(6, (linhas_estimadas * altura_linha) + 2)

        # Limite dinâmico de segurança contra páginas em branco (e textos cortados)
        if pdf_obj.get_y() + altura_total > max_y_page:
            pdf_obj.add_page()
            if func_cabecalho:
                func_cabecalho()

        x_inicial = pdf_obj.get_x()
        y_inicial = pdf_obj.get_y()

        if fill_row:
            pdf_obj.set_fill_color(245, 247, 250)
        else:
            pdf_obj.set_fill_color(255, 255, 255)

        pdf_obj.rect(x_inicial, y_inicial, sum(larguras), altura_total, 'F')

        pdf_obj.set_draw_color(220, 220, 220)
        pdf_obj.line(x_inicial, y_inicial + altura_total, x_inicial + sum(larguras), y_inicial + altura_total)

        # CORREÇÃO CRUCIAL AQUI: Garante que a cor do texto volta para cinza escuro,
        # impedindo que o texto herde a cor branca usada nos cabeçalhos da tabela!
        pdf_obj.set_text_color(40, 40, 40)

        pdf_obj.set_xy(x_inicial, y_inicial + 1)
        pdf_obj.multi_cell(larguras[0], altura_linha, f" {texto_material}", 0, alinhamentos[0])

        y_final_real = max(y_inicial + altura_total, pdf_obj.get_y() + 1)
        altura_final = y_final_real - y_inicial

        for i in range(1, len(textos)):
            x_atual = x_inicial + sum(larguras[:i])
            pdf_obj.set_xy(x_atual, y_inicial)

            texto_celula = str(textos[i]).encode('latin-1', 'replace').decode('latin-1')
            if alinhamentos[i] == 'R':
                texto_celula = f"{texto_celula} "
            elif alinhamentos[i] == 'L':
                texto_celula = f" {texto_celula}"

            pdf_obj.cell(larguras[i], altura_final, texto_celula, 0, 0, alinhamentos[i])

        pdf_obj.set_xy(x_inicial, y_final_real)

    excel_io = io.BytesIO()

    pdf = RelatorioPDF(titulo_relatorio=nome_relatorio, orientacao=orientacao_pdf)
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)

    arquivos_temporarios = []

    # --- PROCESSAMENTO GLOBAL (RESUMO E PARETO) ---
    mask_global_periodo = (df['DATA_UTILIZACAO'].dt.date >= data_inicio) & (df['DATA_UTILIZACAO'].dt.date <= data_fim)
    df_resumo = df[mask_global_periodo]

    df_pareto = pd.DataFrame()

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

        # Prepara Curva ABC
        df_pareto = mat_agrupado_resumo.copy()
        df_pareto['% Acumulado'] = (df_pareto['VALOR_TOTAL'].cumsum() / df_pareto['VALOR_TOTAL'].sum()) * 100
        df_pareto['Classe'] = pd.cut(df_pareto['% Acumulado'], bins=[0, 80, 95, 100], labels=['A', 'B', 'C'],
                                     right=True)

        pdf.add_page()

        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(22, 102, 53)
        str_periodo_resumo = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
        pdf.cell(0, 10, f"Resumo Executivo ({str_periodo_resumo})", 0, 1, 'L')
        pdf.ln(2)

        # ==============================================================================
        # CARDS DE KPI (DASHBOARD NO PDF)
        # ==============================================================================
        y_kpi = pdf.get_y()
        largura_card = (w_total - 10) / 3

        # CARD 1
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(10, y_kpi, largura_card, 22, 'DF')
        pdf.set_xy(12, y_kpi + 4);
        pdf.set_font('Arial', 'B', 8);
        pdf.set_text_color(100, 116, 139)
        pdf.cell(largura_card - 4, 5, "CUSTO TOTAL NO PERIODO", 0, 1, 'C')
        pdf.set_xy(12, y_kpi + 10);
        pdf.set_font('Arial', 'B', 12);
        pdf.set_text_color(15, 23, 42)
        pdf.cell(largura_card - 4, 7, formatar_moeda(total_gasto_resumo), 0, 1, 'C')

        # CARD 2
        pos_x2 = 10 + largura_card + 5
        pdf.rect(pos_x2, y_kpi, largura_card, 22, 'DF')
        pdf.set_xy(pos_x2 + 2, y_kpi + 4);
        pdf.set_font('Arial', 'B', 8);
        pdf.set_text_color(100, 116, 139)
        pdf.cell(largura_card - 4, 5, "PRINCIPAL CENTRO CUSTO", 0, 1, 'C')
        pdf.set_xy(pos_x2 + 2, y_kpi + 10);
        pdf.set_font('Arial', 'B', 10);
        pdf.set_text_color(15, 23, 42)
        cc_txt = str(maior_cc_resumo)[:20].encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(largura_card - 4, 7, cc_txt, 0, 1, 'C')

        # CARD 3
        pos_x3 = pos_x2 + largura_card + 5
        pdf.rect(pos_x3, y_kpi, largura_card, 22, 'DF')
        pdf.set_xy(pos_x3 + 2, y_kpi + 4);
        pdf.set_font('Arial', 'B', 8);
        pdf.set_text_color(100, 116, 139)
        lbl_impacto = f"MAIOR IMPACTO ({label_item[:10].upper()})"
        pdf.cell(largura_card - 4, 5, lbl_impacto.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'C')
        pdf.set_xy(pos_x3 + 2, y_kpi + 10);
        pdf.set_font('Arial', 'B', 9);
        pdf.set_text_color(15, 23, 42)
        m_str = str(maior_mat_resumo).replace('\n', ' - ')
        mat_txt = (m_str[:26] + '..') if len(m_str) > 28 else m_str
        mat_txt = mat_txt.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(largura_card - 4, 7, mat_txt, 0, 1, 'C')

        pdf.set_xy(10, y_kpi + 28)
        pdf.ln(2)

        # TEXTO DE RESUMO
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
        txt_mat = (m_str[:80] + '...') if len(m_str) > 80 else m_str
        txt_mat = txt_mat.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(0, 6, f"   O item/servico mais custoso foi '{txt_mat}',", 0, 1)
        pdf.cell(0, 6, f"   totalizando {formatar_moeda(maior_mat_valor_resumo)} em gastos.", 0, 1)
        pdf.ln(6)

        # ==============================================================================
        # TABELAS ZEBRA PREMIUM
        # ==============================================================================

        # --- SEÇÃO: TOP 20 GERAL NA CAPA ---
        # Proteção contra título órfão (exige pelo menos 30mm de espaço)
        if pdf.get_y() > max_y_page - 30: pdf.add_page()
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(22, 102, 53)
        pdf.cell(0, 8, f"Top 20 {label_item}s de Maior Custo (Visao Global)", 0, 1)

        def cabecalho_top_20():
            pdf.set_font('Arial', 'B', 9)
            pdf.set_text_color(255, 255, 255);
            pdf.set_fill_color(22, 102, 53);
            pdf.set_draw_color(255, 255, 255)
            lbl_head = f" {label_item} / Detalhamento".encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(w_t20[0], 7, lbl_head, 1, 0, 'L', fill=True)
            pdf.cell(w_t20[1], 7, " Centro de Custo", 1, 0, 'C', fill=True)
            pdf.cell(w_t20[2], 7, " Valor Total", 1, 1, 'R', fill=True)

        cabecalho_top_20()

        top_20_global = df_resumo.groupby(['MATERIAL_COMPLETO', 'CENTRO_CUSTO'])[
            'VALOR_TOTAL'].sum().reset_index().sort_values('VALOR_TOTAL', ascending=False).head(20)

        fill = False
        for _, row in top_20_global.iterrows():
            mat_str = str(row['MATERIAL_COMPLETO'])
            cc_str = str(row['CENTRO_CUSTO'])[:35]
            val_str = formatar_moeda(row['VALOR_TOTAL'])
            desenhar_linha_multicell(pdf, [mat_str, cc_str, val_str], w_t20, ['L', 'C', 'R'], fill,
                                     func_cabecalho=cabecalho_top_20)
            fill = not fill

        pdf.ln(8)

        # --- SEÇÃO: RESUMO POR CENTRO DE CUSTO ---
        if pdf.get_y() > max_y_page - 30: pdf.add_page()
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(22, 102, 53)
        pdf.cell(0, 8, "Resumo por Centro de Custo", 0, 1)

        def cabecalho_resumo_cc():
            pdf.set_font('Arial', 'B', 9)
            pdf.set_text_color(255, 255, 255);
            pdf.set_fill_color(22, 102, 53);
            pdf.set_draw_color(255, 255, 255)
            pdf.cell(w_rcc[0], 7, " Centro de Custo", 1, 0, 'L', fill=True)
            pdf.cell(w_rcc[1], 7, " Valor Total", 1, 1, 'R', fill=True)

        cabecalho_resumo_cc()

        fill = False
        for _, row in cc_agrupado_resumo.iterrows():
            cc_str = str(row['CENTRO_CUSTO'])
            val_str = formatar_moeda(row['VALOR_TOTAL'])
            desenhar_linha_multicell(pdf, [cc_str, val_str], w_rcc, ['L', 'R'], fill,
                                     func_cabecalho=cabecalho_resumo_cc)
            fill = not fill

        pdf.ln(10)

    else:
        centros_de_custo_ordenados = []

    primeiro_centro = True

    # EXPORTAÇÃO EXCEL E LOOP DE CENTROS DE CUSTO PARA O PDF
    with pd.ExcelWriter(excel_io) as writer:

        if not df_pareto.empty:
            df_abc_export = df_pareto.copy()
            df_abc_export.rename(columns={'MATERIAL': label_item}, inplace=True)
            df_abc_export['Classe'] = df_abc_export['Classe'].astype(str)
            df_abc_export.to_excel(writer, sheet_name='Curva ABC Geral', index=False)

        for centro in centros_de_custo_ordenados:
            df_centro = df[df['CENTRO_CUSTO'] == centro]
            mask_periodo = (df_centro['DATA_UTILIZACAO'].dt.date >= data_inicio) & (
                        df_centro['DATA_UTILIZACAO'].dt.date <= data_fim)
            df_periodo = df_centro[mask_periodo]
            if df_periodo.empty: continue

            nome_aba = re.sub(r'[\\/*?:\[\]]', '', str(centro))[:31]
            totais_diarios = df_centro.groupby('DATA_UTILIZACAO')['VALOR_TOTAL'].sum().reset_index().sort_values(
                'DATA_UTILIZACAO')

            img_temp = None
            if MATPLOTLIB_AVAILABLE:
                # Estica os gráficos em modo paisagem para não ocuparem muita altura (evita quebrar de página)
                fig_size = (12, 2.5) if orientacao_pdf == 'L' else (8.5, 2.5)
                fig, ax = plt.subplots(figsize=fig_size)
                ax.fill_between(totais_diarios['DATA_UTILIZACAO'], totais_diarios['VALOR_TOTAL'], color='#166635',
                                alpha=0.1)
                ax.plot(totais_diarios['DATA_UTILIZACAO'], totais_diarios['VALOR_TOTAL'], marker='o', color='#166635',
                        linewidth=2, markersize=5)
                ax.set_title(f'Evolucao de Custos', fontsize=11, fontweight='bold', color='#333333')
                ax.grid(True, linestyle='--', alpha=0.4)
                ax.spines['top'].set_visible(False);
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_color('#CCCCCC');
                ax.spines['bottom'].set_color('#CCCCCC')
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                ax.tick_params(axis='x', labelsize=8, rotation=0, colors='#555555')
                ax.tick_params(axis='y', labelsize=8, colors='#555555')

                def formato_moeda_grafico(x, pos): return f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace(
                    'X', '.')

                ax.yaxis.set_major_formatter(ticker.FuncFormatter(formato_moeda_grafico))
                plt.tight_layout()
                img_temp = tempfile.mktemp(suffix=".png")
                arquivos_temporarios.append(img_temp)
                fig.savefig(img_temp, dpi=150, bbox_inches='tight')
                plt.close(fig)

            # Evitar gráfico, título e cabeçalho órfãos (Necessita ~80mm garantidos)
            espaco_seguranca = 85 if img_temp else 35
            if pdf.get_y() > max_y_page - espaco_seguranca:
                pdf.add_page()
            elif not primeiro_centro:
                pdf.ln(10);
                pdf.set_draw_color(220, 220, 220);
                pdf.set_line_width(0.5)
                pdf.line(10, pdf.get_y(), 10 + w_total, pdf.get_y());
                pdf.ln(8);
                pdf.set_line_width(0.2)

            primeiro_centro = False

            pdf.set_font('Arial', 'B', 14);
            pdf.set_text_color(22, 102, 53)
            titulo_centro = f"Centro de Custo: {centro}".encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 8, titulo_centro, 0, 1)
            pdf.ln(2)

            if img_temp: pdf.image(img_temp, x=10, w=w_total)
            pdf.ln(4)

            dias_unicos_periodo = sorted(df_periodo['DATA_UTILIZACAO'].dt.date.unique(), reverse=True)
            linhas_excel = []

            for dia in dias_unicos_periodo:
                df_dia = df_periodo[df_periodo['DATA_UTILIZACAO'].dt.date == dia]
                materiais_agrupados = df_dia.groupby('MATERIAL_COMPLETO').agg(
                    {'UN': 'first', 'QTD': 'sum', 'VALOR_TOTAL': 'sum'}).reset_index()
                top_20 = materiais_agrupados.sort_values('VALOR_TOTAL', ascending=False).head(20)

                data_str = pd.to_datetime(dia).strftime('%d/%m/%Y')
                linhas_excel.append(
                    {f'{label_item}': f'--- DATA: {data_str} ---', 'UN': '', 'Quantidade': '', 'Valor Total': ''})

                # Função de Cabeçalho Diário para repetir caso quebre página
                def cabecalho_dia():
                    pdf.set_font('Arial', 'B', 10)
                    pdf.set_fill_color(240, 240, 240);
                    pdf.set_text_color(22, 102, 53);
                    pdf.set_draw_color(240, 240, 240)
                    pdf.cell(0, 7, f" DATA DE UTILIZACAO: {data_str} (Top 20)", 1, 1, 'L', fill=True)

                    pdf.set_font('Arial', 'B', 8)
                    pdf.set_text_color(255, 255, 255);
                    pdf.set_fill_color(22, 102, 53);
                    pdf.set_draw_color(255, 255, 255)
                    lbl_head2 = f" {label_item} / Detalhamento".encode('latin-1', 'replace').decode('latin-1')
                    pdf.cell(w_det[0], 6, lbl_head2, 1, 0, 'L', fill=True)
                    pdf.cell(w_det[1], 6, " UN", 1, 0, 'C', fill=True)
                    pdf.cell(w_det[2], 6, " QTD", 1, 0, 'C', fill=True)
                    pdf.cell(w_det[3], 6, " Valor Total", 1, 1, 'R', fill=True)

                # Garante espaço para o cabeçalho e pelo menos 1 linha (~25mm)
                if pdf.get_y() > max_y_page - 25: pdf.add_page()
                cabecalho_dia()

                fill_row = False
                for _, mat in top_20.iterrows():
                    mat_str = str(mat['MATERIAL_COMPLETO'])
                    un_str = str(mat['UN'])[:5]
                    qtd_str = str(mat['QTD'])
                    val_str = formatar_moeda(mat['VALOR_TOTAL'])

                    desenhar_linha_multicell(pdf, [mat_str, un_str, qtd_str, val_str], w_det, ['L', 'C', 'C', 'R'],
                                             fill_row, func_cabecalho=cabecalho_dia)

                    linhas_excel.append({f'{label_item}': mat_str, 'UN': mat['UN'], 'Quantidade': mat['QTD'],
                                         'Valor Total': mat['VALOR_TOTAL']})
                    fill_row = not fill_row

                linhas_excel.append({f'{label_item}': '', 'UN': '', 'Quantidade': '', 'Valor Total': ''})
                pdf.ln(4)

            if linhas_excel:
                df_aba = pd.DataFrame(linhas_excel)
                df_aba.to_excel(writer, sheet_name=nome_aba, index=False)

    # --- PÁGINA FINAL: CURVA ABC (PARETO NO PDF) ---
    if not df_resumo.empty:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(22, 102, 53)
        pdf.cell(0, 8, "Analise de Pareto (Curva ABC)", 0, 1, 'L')
        pdf.ln(2)

        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(60, 60, 60)
        texto_abc = (
            "A Curva ABC e um metodo de categorizacao de custos baseado no principio de Pareto (80/20). "
            "Os itens classificados como 'Classe A' representam cerca de 80% do valor total consumido no periodo, "
            "sendo os itens de maior impacto financeiro e que exigem controle e negociacao rigorosos por parte da gestao. "
            "Abaixo apresentamos o grafico e a classificacao dos 20 principais itens ofensores."
        )
        pdf.multi_cell(0, 5, texto_abc.encode('latin-1', 'replace').decode('latin-1'))
        pdf.ln(5)

        if MATPLOTLIB_AVAILABLE:
            fig_size_abc = (14, 4.5) if orientacao_pdf == 'L' else (8.5, 4.5)
            fig, ax1 = plt.subplots(figsize=fig_size_abc)
            top_30_pareto = df_pareto.head(30)

            ax1.bar(range(len(top_30_pareto)), top_30_pareto['VALOR_TOTAL'], color='#22C55E', alpha=0.9,
                    edgecolor='none')
            ax1.set_ylabel('Valor (R$)', color='#166635', fontsize=9)
            ax1.tick_params(axis='y', labelcolor='#166635', labelsize=8)
            ax1.set_xticks([])

            ax1.spines['top'].set_visible(False);
            ax1.spines['bottom'].set_visible(False);
            ax1.spines['left'].set_color('#CCCCCC')

            def formato_moeda_abc(x, pos): return f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            ax1.yaxis.set_major_formatter(ticker.FuncFormatter(formato_moeda_abc))

            ax2 = ax1.twinx()
            ax2.plot(range(len(top_30_pareto)), top_30_pareto['% Acumulado'], color='#F59E0B', marker='o', ms=4,
                     linewidth=2)
            ax2.set_ylabel('% Acumulado', color='#F59E0B', fontsize=9)
            ax2.tick_params(axis='y', labelcolor='#F59E0B', labelsize=8)
            ax2.set_ylim([0, 105])
            ax2.spines['top'].set_visible(False);
            ax2.spines['right'].set_color('#CCCCCC')

            plt.title('Curva ABC - Visao Financeira', fontsize=12, fontweight='bold', color='#333333')
            plt.tight_layout()

            img_abc = tempfile.mktemp(suffix=".png")
            arquivos_temporarios.append(img_abc)
            fig.savefig(img_abc, dpi=150)
            plt.close(fig)

            pdf.image(img_abc, x=10, w=w_total)
            pdf.ln(5)

        def cabecalho_abc():
            pdf.set_font('Arial', 'B', 9)
            pdf.set_fill_color(22, 102, 53);
            pdf.set_text_color(255, 255, 255);
            pdf.set_draw_color(255, 255, 255)
            lbl_head3 = f" {label_item}".encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(w_abc[0], 7, lbl_head3, 1, 0, 'L', fill=True)
            pdf.cell(w_abc[1], 7, " Classe", 1, 0, 'C', fill=True)
            pdf.cell(w_abc[2], 7, " % Acumul.", 1, 0, 'C', fill=True)
            pdf.cell(w_abc[3], 7, " Valor Total", 1, 1, 'R', fill=True)

        cabecalho_abc()

        fill_abc = False
        for _, row in df_pareto.head(20).iterrows():
            mat_str = str(row['MATERIAL'])
            classe_str = f"Classe {str(row['Classe'])}"
            pct_str = f"{row['% Acumulado']:.1f}%"
            val_str = formatar_moeda(row['VALOR_TOTAL'])
            desenhar_linha_multicell(pdf, [mat_str, classe_str, pct_str, val_str], w_abc, ['L', 'C', 'C', 'R'],
                                     fill_abc, func_cabecalho=cabecalho_abc)
            fill_abc = not fill_abc

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

            if 'TIPO_ITEM' not in df_lido.columns:
                st.warning(
                    "A coluna 'TIPO_ITEM' não foi encontrada na planilha. O sistema assumirá que tudo é 'Material'.")
                df_lido['TIPO_ITEM'] = 'MATERIAIS'

            if 'UN' not in df_lido.columns: df_lido['UN'] = '-'
            if 'REQUISITANTE' not in df_lido.columns:
                df_lido['REQUISITANTE'] = 'Não Informado'
            else:
                df_lido['REQUISITANTE'] = df_lido['REQUISITANTE'].fillna('Não Informado').astype(str)
                df_lido['REQUISITANTE'] = df_lido['REQUISITANTE'].replace(['nan', '-', ''], 'Não Informado')

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
    with st.sidebar:
        st.header("🔍 Filtros de Relatório")

        st.markdown("##### 📅 Período")
        datas_selecionadas = st.date_input("De / Até:", value=(min_date, max_date), min_value=min_date,
                                           max_value=max_date)

        st.markdown("##### 🏢 Centro de Custo")
        centros_disponiveis = sorted(df_base['CENTRO_CUSTO'].dropna().unique().tolist())
        cc_selecionados = st.multiselect("Selecione os Centros:", options=centros_disponiveis, default=[],
                                         help="Deixe em branco para incluir todos.")

        st.markdown("##### 🛠️ Tipo de Despesa")
        tipo_filtro = st.selectbox("Classificação:",
                                   options=["🛠️ Materiais (Peças, Combustível)", "👷‍♂️ Serviços de Terceiros",
                                            "📊 Visão Consolidada (Ambos)"], index=0)

        # --- FILTRO CIRÚRGICO POR MATERIAL ---
        st.markdown("##### 🔎 Busca Específica (Opcional)")
        materiais_disponiveis = sorted(df_base['MATERIAL'].dropna().unique().tolist())
        mat_selecionados = st.multiselect("Filtrar Itens/Serviços específicos:", options=materiais_disponiveis,
                                          default=[], help="Força o relatório a analisar apenas eles.")

        # --- ESCOLHA DE ORIENTAÇÃO DO PDF ---
        st.markdown("---")
        st.markdown("##### 🖨️ Configuração de Impressão")
        orientacao_ui = st.radio("Formato do PDF:", ["Paisagem (Deitado)", "Retrato (Em pé)"], horizontal=True)
        orientacao_pdf = 'L' if 'Paisagem' in orientacao_ui else 'P'

    if isinstance(datas_selecionadas, tuple) and len(datas_selecionadas) == 2:
        data_inicio, data_fim = datas_selecionadas
    else:
        st.warning("Selecione a data final para continuar.")
        st.stop()

    str_periodo = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"

    # --- APLICAÇÃO DE FILTROS ---
    df_filtrado = df_base.copy()

    if cc_selecionados: df_filtrado = df_filtrado[df_filtrado['CENTRO_CUSTO'].isin(cc_selecionados)]
    if mat_selecionados: df_filtrado = df_filtrado[df_filtrado['MATERIAL'].isin(mat_selecionados)]

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
        nome_relatorio = "Relatorio Consolidado de Custos, Cedro"
        label_item = "Item / Servico"

    with st.spinner(f"Compilando {nome_relatorio.lower()}..."):
        excel_bytes, pdf_bytes, df_clean = processar_e_gerar_relatorios(df_filtrado, data_inicio, data_fim,
                                                                        nome_relatorio, label_item, orientacao_pdf)

    mask_ui = (df_clean['DATA_UTILIZACAO'].dt.date >= data_inicio) & (df_clean['DATA_UTILIZACAO'].dt.date <= data_fim)
    df_periodo_ui = df_clean[mask_ui]

    # --- UI: RESUMO EXECUTIVO VISUAL ---
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

        st.markdown(f"### 📝 Resumo Executivo ({str_periodo})")

        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
        ui_kpi_card(c_kpi1, "Custo Total no Período", formatar_moeda(total_gasto), get_icon("dashboard", "#2196F3"),
                    "#2196F3", "Gasto somado de todas as áreas")
        ui_kpi_card(c_kpi2, "Maior Centro de Custo", str(maior_cc)[:18], get_icon("pin", "#F59E0B"), "#F59E0B",
                    f"Consumiu {percentual_maior:.1f}% ({formatar_moeda(maior_valor)})")
        ui_kpi_card(c_kpi3, f"Principal {label_item.replace('Servico', 'Serviço')}", str(maior_mat)[:18] + "...",
                    get_icon("fire", "#EF4444"), "#EF4444", f"Totalizou {formatar_moeda(maior_mat_valor)}")

    else:
        st.markdown(f"### 📝 Resumo Executivo")
        st.warning(f"Não há registros de consumo para os filtros selecionados.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- ABAS DE ANÁLISE ---
    tab_dash, tab_abc, tab_detalhes = st.tabs(["📈 Dashboards Analíticos", "📊 Curva ABC (Pareto)", "📋 Detalhamento"])

    with tab_dash:
        c_linha, c_pizza = st.columns([2, 1])

        with c_linha:
            st.markdown("##### Evolução de Custos Diários")
            df_timeline = df_clean.groupby(['DATA_UTILIZACAO', 'CENTRO_CUSTO'])['VALOR_TOTAL'].sum().reset_index()
            fig_linha = px.line(df_timeline, x='DATA_UTILIZACAO', y='VALOR_TOTAL', color='CENTRO_CUSTO', markers=True,
                                labels={'DATA_UTILIZACAO': 'Data', 'VALOR_TOTAL': 'Custo', 'CENTRO_CUSTO': 'Centro'})
            fig_linha.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                                    yaxis_tickprefix="R$ ", yaxis_tickformat=",.2f", separators=".,")
            st.plotly_chart(fig_linha, use_container_width=True)

        with c_pizza:
            st.markdown("##### Distribuição Global")
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
            fig_pizza.update_traces(textposition='inside', textinfo='percent',
                                    hovertemplate="%{label}<br>R$ %{value:,.2f}<br>%{percent}")
            fig_pizza.update_layout(showlegend=True,
                                    legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5),
                                    separators=".,")
            st.plotly_chart(fig_pizza, use_container_width=True)

    with tab_abc:
        st.markdown(f"##### Análise de Pareto ({label_item.replace('Servico', 'Serviço')} Classe A)")
        st.caption("Identifique rapidamente os 20% de itens que representam 80% do seu custo.")
        if not df_periodo_ui.empty:
            df_pareto = df_periodo_ui.groupby('MATERIAL')['VALOR_TOTAL'].sum().reset_index().sort_values('VALOR_TOTAL',
                                                                                                         ascending=False)
            df_pareto['% Acumulado'] = (df_pareto['VALOR_TOTAL'].cumsum() / df_pareto['VALOR_TOTAL'].sum()) * 100

            fig_pareto = go.Figure()
            fig_pareto.add_trace(
                go.Bar(x=df_pareto['MATERIAL'].head(30), y=df_pareto['VALOR_TOTAL'].head(30), name='Valor Total',
                       marker_color='#166635'))
            fig_pareto.add_trace(
                go.Scatter(x=df_pareto['MATERIAL'].head(30), y=df_pareto['% Acumulado'].head(30), name='% Acumulado',
                           yaxis='y2', mode='lines+markers', line=dict(color='#F59E0B', width=3)))

            fig_pareto.update_layout(
                yaxis=dict(title='Custo', tickprefix="R$ ", tickformat=",.2f"),
                yaxis2=dict(title='% Acumulado', overlaying='y', side='right', range=[0, 105]),
                legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5),
                margin=dict(t=20, b=10),
                separators=".,"
            )
            st.plotly_chart(fig_pareto, use_container_width=True)

            df_pareto['Classe'] = pd.cut(df_pareto['% Acumulado'], bins=[0, 80, 95, 100],
                                         labels=['A (80%)', 'B (15%)', 'C (5%)'], right=True)
            st.dataframe(df_pareto.head(20), use_container_width=True, hide_index=True,
                         column_config={"VALOR_TOTAL": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                                        "% Acumulado": st.column_config.NumberColumn("% Acumulado", format="%.1f%%")})

    with tab_detalhes:
        st.markdown(f"##### 📋 Top itens consumidos no período")
        if not df_periodo_ui.empty:
            df_display = df_periodo_ui.groupby(['DATA_UTILIZACAO', 'CENTRO_CUSTO', 'MATERIAL_COMPLETO']).agg(
                {'UN': 'first', 'QTD': 'sum', 'VALOR_TOTAL': 'sum'}).reset_index()
            df_display = df_display.sort_values(by=['DATA_UTILIZACAO', 'CENTRO_CUSTO', 'VALOR_TOTAL'],
                                                ascending=[False, True, False])
            max_valor_display = float(df_display['VALOR_TOTAL'].max()) if not df_display.empty else 100.0

            st.dataframe(
                df_display,
                use_container_width=True, hide_index=True,
                column_config={
                    "DATA_UTILIZACAO": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "CENTRO_CUSTO": st.column_config.TextColumn("Centro de Custo"),
                    "MATERIAL_COMPLETO": st.column_config.TextColumn(f"{label_item.replace('Servico', 'Serviço')}",
                                                                     width="large"),
                    "UN": st.column_config.TextColumn("UN", width="small"),
                    "QTD": st.column_config.NumberColumn("Quantidade"),
                    "VALOR_TOTAL": st.column_config.ProgressColumn("Valor Total (R$)", format="R$ %.2f", min_value=0,
                                                                   max_value=max_valor_display)
                }
            )

    st.markdown("---")
    st.markdown("### 🖨️ Documentos para Impressão")
    st.caption("Relatório otimizado em PDF e detalhamento bruto em Excel considerando os filtros aplicados.")

    tipo_arquivo = "Servicos" if "Serviços" in tipo_filtro else (
        "Materiais" if "Materiais" in tipo_filtro else "Consolidado")
    nome_padrao_arquivo = f"{tipo_arquivo}_{data_inicio.strftime('%d%m%y')}_a_{data_fim.strftime('%d%m%y')}"

    c_pdf, c_excel = st.columns(2)
    with c_pdf:
        st.download_button(label="📄 Descarregar Relatório PDF", data=pdf_bytes,
                           file_name=f"Relatorio_{nome_padrao_arquivo}.pdf", mime="application/pdf", type="primary",
                           use_container_width=True)
    with c_excel:
        st.download_button(label="📊 Descarregar Tabela Excel", data=excel_bytes,
                           file_name=f"Detalhe_{nome_padrao_arquivo}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)