import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import sys
import os
import io
import tempfile
from datetime import datetime

# --- BLINDAGEM E IMPORTAÇÃO DO BANCO DE DADOS ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from utils_ui import load_custom_css, ui_header, ui_kpi_card, ui_empty_state
from utils_icons import get_icon

# Tentativa segura de importar o matplotlib para gerar gráficos no PDF
try:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import matplotlib.dates as mdates

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# --- CONFIGURAÇÃO INICIAL ---
load_custom_css()

icon_main = get_icon("dashboard", "#2196F3", "36")
ui_header(
    title="Análise de Eficiência e Apontamentos",
    subtitle="Auditoria de Produtividade: Cruzamento de Jornada RH vs. Apontamentos PIMS.",
    icon=icon_main
)


# ==============================================================================
# CLASSES E LÓGICA DE PDF (MODO PAISAGEM / LANDSCAPE)
# ==============================================================================

class RelatorioPDF(FPDF):
    def __init__(self, titulo_relatorio="Relatorio de Eficiencia, Cedro", *args, **kwargs):
        # Força o modo Paisagem (Landscape) na inicialização
        super().__init__(orientation='L', format='A4', *args, **kwargs)
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

        # Linha Divisória adaptada para largura de Paisagem (297mm - margens = ~287mm)
        self.set_draw_color(22, 102, 53)  # Verde Cedro
        self.set_line_width(0.5)
        y_linha = max(self.get_y() + 2, 22)
        self.line(10, y_linha, 287, y_linha)
        self.set_y(y_linha + 5)
        self.set_line_width(0.2)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)

        self.set_draw_color(220, 220, 220)
        self.line(10, self.get_y() - 2, 287, self.get_y() - 2)

        data_hora_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
        texto_rodape = f'Emitido automaticamente via Sistema Cedro em: {data_hora_atual}  |  Pagina {self.page_no()}'
        texto_rodape = texto_rodape.encode('latin-1', 'replace').decode('latin-1')

        self.cell(0, 10, texto_rodape, 0, 0, 'C')


@st.cache_data(show_spinner="Compilando relatórios PDF/Excel Avançados...", ttl=600)
def processar_e_gerar_relatorios_eficiencia(df_view, dt_in, dt_out):
    excel_io = io.BytesIO()
    arquivos_temporarios = []

    # 1. Cálculos de KPIs Globais e Controle de Dias
    total_dias_periodo = (dt_out - dt_in).days + 1
    dias_trabalhados = df_view['DT_REF'].nunique()

    efi_media = df_view[df_view['H_REAL_LIQ'] > 0]['EFICIENCIA_GERAL'].mean() if not df_view[
        df_view['H_REAL_LIQ'] > 0].empty else 0
    h_rh = df_view['H_REAL_LIQ'].sum()
    h_prod = df_view['HORAS_PROD'].sum()
    h_improd = df_view['HORAS_IMPROD'].sum()
    h_apont = df_view['HORAS_DEC'].sum()

    perc_produtivo = (h_prod / h_apont * 100) if h_apont > 0 else 0

    df_criticos = df_view[df_view['STATUS'].str.contains('Sem Apontamento|Ponto Não Batido', na=False)]
    df_sem_ref = df_view[df_view['STATUS'] == 'ALERTA (Sem Refeição)']
    fantasmas = df_criticos['NOME_FINAL'].nunique()

    pdf = RelatorioPDF(titulo_relatorio="Relatorio Auditoria de Produtividade (Paisagem), Cedro")
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- PÁGINA 1: RESUMO EXECUTIVO & GRÁFICO GLOBAL ---
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 8, "Resumo Executivo", 0, 1, 'L')

    # Subtítulo com Dias Trabalhados vs Dias Filtrados
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(80, 80, 80)
    str_periodo = f"Periodo Selecionado: {dt_in.strftime('%d/%m/%Y')} a {dt_out.strftime('%d/%m/%Y')} ({total_dias_periodo} dias)  |  Dias Trabalhados: {dias_trabalhados} dias com apontamento na base."
    pdf.cell(0, 6, str_periodo, 0, 1, 'L')
    pdf.ln(4)

    # CARDS KPI NO PDF (Ajustado para o modo paisagem)
    y_kpi = pdf.get_y()
    largura_card = 65

    # Card 1: Eficiência Geral
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.rect(10, y_kpi, largura_card, 22, 'DF')
    pdf.set_xy(10, y_kpi + 4)
    pdf.set_font('Arial', 'B', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(largura_card, 5, "APONTAMENTO (GERAL)", 0, 1, 'C')
    pdf.set_xy(10, y_kpi + 10)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(largura_card, 7, f"{efi_media:.1f}%", 0, 1, 'C')

    # Card 2: Horas Pagas
    pos_x2 = 10 + largura_card + 5
    pdf.rect(pos_x2, y_kpi, largura_card, 22, 'DF')
    pdf.set_xy(pos_x2, y_kpi + 4)
    pdf.set_font('Arial', 'B', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(largura_card, 5, "HORAS PAGAS (RH)", 0, 1, 'C')
    pdf.set_xy(pos_x2, y_kpi + 10)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(largura_card, 7, f"{h_rh:.0f} h", 0, 1, 'C')

    # Card 3: % Produtividade
    pos_x3 = pos_x2 + largura_card + 5
    pdf.rect(pos_x3, y_kpi, largura_card, 22, 'DF')
    pdf.set_xy(pos_x3, y_kpi + 4)
    pdf.set_font('Arial', 'B', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(largura_card, 5, "TAXA PRODUTIVIDADE", 0, 1, 'C')
    pdf.set_xy(pos_x3, y_kpi + 10)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(22, 163, 74)
    pdf.cell(largura_card, 7, f"{perc_produtivo:.1f}%", 0, 1, 'C')

    # Card 4: Falhas
    pos_x4 = pos_x3 + largura_card + 5
    pdf.rect(pos_x4, y_kpi, largura_card, 22, 'DF')
    pdf.set_xy(pos_x4, y_kpi + 4)
    pdf.set_font('Arial', 'B', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(largura_card, 5, "FALHAS (SEM APONT.)", 0, 1, 'C')
    pdf.set_xy(pos_x4, y_kpi + 10)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(220, 38, 38)
    pdf.cell(largura_card, 7, f"{fantasmas} pessoas", 0, 1, 'C')

    pdf.set_xy(10, y_kpi + 28)
    pdf.ln(2)

    # TEXTO DESCRITIVO
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, "1. Produtividade Global:", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6,
             f"   Das {h_apont:.0f} horas totais apontadas no PIMS, {h_prod:.0f}h foram PRODUTIVAS e {h_improd:.0f}h IMPRODUTIVAS.",
             0, 1)
    pdf.ln(1)

    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, "2. Volume de Trabalho vs Apontamento:", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6,
             f"   Foram identificadas {h_rh:.0f} horas liquidas trabalhadas (Jornada RH) contra {h_apont:.0f} horas declaradas.",
             0, 1)
    pdf.ln(1)

    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, "3. Qualidade dos Apontamentos (Auditoria de Refeicao):", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6,
             f"   Foram identificados {len(df_sem_ref)} dias em que o funcionario trabalhou mas nao apontou a 'Refeicao' no sistema.",
             0, 1)
    pdf.ln(4)

    # Gráfico 1: Evolução Diária (Linha)
    if MATPLOTLIB_AVAILABLE and not df_view.empty:
        df_timeline = df_view.groupby('DT_REF').agg({'H_REAL_LIQ': 'sum', 'HORAS_DEC': 'sum'}).reset_index()
        df_timeline['EFI'] = np.where(df_timeline['H_REAL_LIQ'] > 0,
                                      (df_timeline['HORAS_DEC'] / df_timeline['H_REAL_LIQ']) * 100, 0)
        df_timeline = df_timeline.sort_values('DT_REF')

        fig, ax = plt.subplots(figsize=(14, 3.5))
        ax.plot(df_timeline['DT_REF'], df_timeline['EFI'], marker='o', color='#16A34A', lw=2.5, markersize=6)
        ax.fill_between(df_timeline['DT_REF'], df_timeline['EFI'], color='#16A34A', alpha=0.1)
        ax.set_title('Evolucao da Eficiencia Media Diaria (%)', fontsize=12, fontweight='bold', color='#333333')
        ax.grid(True, linestyle='--', alpha=0.4)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#CCCCCC')
        ax.spines['bottom'].set_color('#CCCCCC')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.tick_params(axis='both', labelsize=9, colors='#555555')
        ax.set_ylim(bottom=0)

        plt.tight_layout()
        img_trend = tempfile.mktemp(suffix=".png")
        arquivos_temporarios.append(img_trend)
        fig.savefig(img_trend, dpi=150, bbox_inches='tight')
        plt.close(fig)

        pdf.image(img_trend, x=10, w=277)

    # ==============================================================================
    # PÁGINA 2: RANKING DE DESEMPENHO POR SETOR
    # ==============================================================================
    pdf.add_page()

    # Agrupamento estrito por SETOR
    df_setor = df_view.groupby(['SETOR']).agg({
        'H_REAL_LIQ': 'sum',
        'HORAS_DEC': 'sum',
        'HORAS_PROD': 'sum'
    }).reset_index()

    df_setor['EFI'] = np.where(df_setor['H_REAL_LIQ'] > 0, (df_setor['HORAS_DEC'] / df_setor['H_REAL_LIQ']) * 100, 0)
    df_setor['PROD_PCT'] = np.where(df_setor['HORAS_DEC'] > 0, (df_setor['HORAS_PROD'] / df_setor['HORAS_DEC']) * 100,
                                    0)
    df_setor = df_setor.sort_values('EFI', ascending=False)

    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 8, "Ranking de Desempenho por Equipe (Setor)", 0, 1)
    pdf.ln(2)

    # Gráfico 2: Barras de Setores
    if MATPLOTLIB_AVAILABLE and not df_setor.empty:
        df_setor_plot = df_setor.head(15).sort_values('EFI', ascending=True)
        fig2, ax2 = plt.subplots(figsize=(14, 4))
        ax2.barh(df_setor_plot['SETOR'].str.slice(0, 40), df_setor_plot['EFI'], color='#2196F3', edgecolor='none')
        ax2.set_title('Top Setores por Eficiencia (%)', fontsize=12, fontweight='bold', color='#333333')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color('#CCCCCC')
        ax2.spines['bottom'].set_visible(False)
        ax2.tick_params(axis='both', labelsize=9, colors='#555555')

        for i, v in enumerate(df_setor_plot['EFI']):
            ax2.text(v + 1, i, f"{v:.1f}%", color='#333333', va='center', fontsize=9, fontweight='bold')

        plt.tight_layout()
        img_setor = tempfile.mktemp(suffix=".png")
        arquivos_temporarios.append(img_setor)
        fig2.savefig(img_setor, dpi=150, bbox_inches='tight')
        plt.close(fig2)

        pdf.image(img_setor, x=10, w=277)
        pdf.ln(5)

    # Tabela de Setores
    pdf.set_font('Arial', 'B', 9)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(22, 102, 53)
    pdf.set_draw_color(255, 255, 255)

    # Total da largura deve ser 277mm
    pdf.cell(77, 8, " Equipe (Setor)", 1, 0, 'L', fill=True)
    pdf.cell(40, 8, " Jornada RH", 1, 0, 'C', fill=True)
    pdf.cell(40, 8, " Apontado", 1, 0, 'C', fill=True)
    pdf.cell(40, 8, " Horas Produtivas", 1, 0, 'C', fill=True)
    pdf.cell(40, 8, " Eficiencia", 1, 0, 'C', fill=True)
    pdf.cell(40, 8, " % Produtividade", 1, 1, 'C', fill=True)

    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.set_draw_color(220, 220, 220)
    fill = False
    for _, row in df_setor.iterrows():
        if fill:
            pdf.set_fill_color(245, 247, 250)
        else:
            pdf.set_fill_color(255, 255, 255)

        s_str = str(row['SETOR'])[:45].encode('latin-1', 'replace').decode('latin-1')

        pdf.cell(77, 7, f" {s_str}", 'B', 0, 'L', fill=True)
        pdf.cell(40, 7, f"{row['H_REAL_LIQ']:.1f} h", 'B', 0, 'C', fill=True)
        pdf.cell(40, 7, f"{row['HORAS_DEC']:.1f} h", 'B', 0, 'C', fill=True)
        pdf.cell(40, 7, f"{row['HORAS_PROD']:.1f} h", 'B', 0, 'C', fill=True)
        pdf.cell(40, 7, f"{row['EFI']:.1f}%", 'B', 0, 'C', fill=True)
        pdf.cell(40, 7, f"{row['PROD_PCT']:.1f}%", 'B', 1, 'C', fill=True)
        fill = not fill

    # ==============================================================================
    # PÁGINA 3: RANKING COLABORADORES DETALHADO (Com Gráfico)
    # ==============================================================================
    pdf.add_page()

    # NOVO AGRUPAMENTO E ORDENAÇÃO (INCLUINDO FALTA REFEIÇÃO)
    df_rank = df_view.groupby(['SETOR', 'GESTOR', 'MATRICULA_FINAL', 'NOME_FINAL']).agg({
        'H_REAL_LIQ': 'sum',
        'HORAS_DEC': 'sum',
        'HORAS_PROD': 'sum',
        'HORAS_IMPROD': 'sum',
        'FALTA_REFEICAO': 'sum'
    }).reset_index()

    df_rank['EFI'] = np.where(df_rank['H_REAL_LIQ'] > 0, (df_rank['HORAS_DEC'] / df_rank['H_REAL_LIQ']) * 100, 0)
    df_rank = df_rank.sort_values(['SETOR', 'GESTOR', 'HORAS_DEC'], ascending=[True, True, False])

    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 8, "Desempenho Detalhado por Colaborador", 0, 1)
    pdf.ln(2)

    # Gráfico 3: Desempenho de Todos os Colaboradores (Stacked Bar Adaptável)
    if MATPLOTLIB_AVAILABLE and not df_rank.empty:
        # Ordena pelo maior volume de apontamentos no topo (decrescente)
        df_rank_plot_full = df_rank.sort_values('HORAS_DEC', ascending=False)

        # Quebra em grupos de 20 para não espremer o gráfico nem estourar a página
        chunk_size = 20
        chunks = [df_rank_plot_full[i:i + chunk_size] for i in range(0, len(df_rank_plot_full), chunk_size)]

        for idx, chunk in enumerate(chunks):
            # Inverte o chunk para o matplotlib desenhar o maior no topo visualmente
            chunk_plot = chunk.iloc[::-1]

            # Altura adaptável baseada na quantidade de pessoas neste bloco
            altura_figura = max(3.0, len(chunk_plot) * 0.3)
            fig3, ax3 = plt.subplots(figsize=(14, altura_figura))

            # Cria rótulos mais bonitos pro gráfico
            labels = chunk_plot['NOME_FINAL'].str.slice(0, 20) + " (" + chunk_plot['SETOR'].str.slice(0, 12) + ")"

            ax3.barh(labels, chunk_plot['HORAS_PROD'], color='#22C55E', label='Produtivo', edgecolor='none')
            ax3.barh(labels, chunk_plot['HORAS_IMPROD'], left=chunk_plot['HORAS_PROD'], color='#F59E0B',
                     label='Improdutivo', edgecolor='none')

            titulo = 'Desempenho de Colaboradores (Volume de Horas Apontadas)'
            if len(chunks) > 1:
                titulo += f' - Parte {idx + 1}'

            ax3.set_title(titulo, fontsize=12, fontweight='bold', color='#333333')
            ax3.legend(loc='lower right', frameon=False)
            ax3.spines['top'].set_visible(False)
            ax3.spines['right'].set_visible(False)
            ax3.spines['left'].set_color('#CCCCCC')
            ax3.spines['bottom'].set_visible(False)
            ax3.tick_params(axis='both', labelsize=8, colors='#555555')

            plt.tight_layout()
            img_colab = tempfile.mktemp(suffix=".png")
            arquivos_temporarios.append(img_colab)
            fig3.savefig(img_colab, dpi=150, bbox_inches='tight')
            plt.close(fig3)

            # Se for o segundo gráfico do loop em diante, ou a página não tiver espaço, joga pra folha nova
            if idx > 0 or pdf.get_y() > 130:
                pdf.add_page()

            pdf.image(img_colab, x=10, w=277)
            pdf.ln(5)

    def print_colaboradores_header():
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(22, 102, 53)
        pdf.set_draw_color(255, 255, 255)

        # Largura Total = 277mm. Ordem: Setor -> Colaborador -> Gestor
        pdf.cell(45, 8, " Setor", 1, 0, 'L', fill=True)
        pdf.cell(55, 8, " Colaborador", 1, 0, 'L', fill=True)
        pdf.cell(45, 8, " Gestor", 1, 0, 'L', fill=True)
        pdf.cell(22, 8, " Jornada", 1, 0, 'C', fill=True)
        pdf.cell(22, 8, " Apontado", 1, 0, 'C', fill=True)
        pdf.cell(22, 8, " Produtivo", 1, 0, 'C', fill=True)
        pdf.cell(22, 8, " Improd.", 1, 0, 'C', fill=True)
        pdf.cell(22, 8, " Efic.", 1, 0, 'C', fill=True)
        pdf.cell(22, 8, " S/ Ref. (d)", 1, 1, 'C', fill=True)

    print_colaboradores_header()

    pdf.set_font('Arial', '', 8)
    pdf.set_text_color(40, 40, 40)
    pdf.set_draw_color(220, 220, 220)
    fill = False

    # LOOP COMPLETO de Colaboradores
    for _, row in df_rank.iterrows():
        if pdf.get_y() > 185:  # Margem inferior para paisagem é menor (A4 altura é 210)
            pdf.add_page()
            print_colaboradores_header()
            pdf.set_font('Arial', '', 8)
            pdf.set_text_color(40, 40, 40)

        if fill:
            pdf.set_fill_color(245, 247, 250)
        else:
            pdf.set_fill_color(255, 255, 255)

        s_str = str(row['SETOR'])[:22].encode('latin-1', 'replace').decode('latin-1')
        n_str = str(row['NOME_FINAL'])[:30].encode('latin-1', 'replace').decode('latin-1')
        g_str = str(row['GESTOR'])[:22].encode('latin-1', 'replace').decode('latin-1')

        pdf.cell(45, 6, f" {s_str}", 'B', 0, 'L', fill=True)
        pdf.cell(55, 6, f" {n_str}", 'B', 0, 'L', fill=True)
        pdf.cell(45, 6, f" {g_str}", 'B', 0, 'L', fill=True)
        pdf.cell(22, 6, f"{row['H_REAL_LIQ']:.1f}h", 'B', 0, 'C', fill=True)
        pdf.cell(22, 6, f"{row['HORAS_DEC']:.1f}h", 'B', 0, 'C', fill=True)
        pdf.cell(22, 6, f"{row['HORAS_PROD']:.1f}h", 'B', 0, 'C', fill=True)
        pdf.cell(22, 6, f"{row['HORAS_IMPROD']:.1f}h", 'B', 0, 'C', fill=True)
        pdf.cell(22, 6, f"{row['EFI']:.0f}%", 'B', 0, 'C', fill=True)
        pdf.cell(22, 6, f"{row['FALTA_REFEICAO']}d", 'B', 1, 'C', fill=True)
        fill = not fill

    # --- GERAÇÃO DO EXCEL MULTI-ABA ---
    with pd.ExcelWriter(excel_io) as writer:
        colunas_excel = [
            'DT_REF', 'SETOR', 'NOME_FINAL', 'GESTOR', 'TURMA', 'MATRICULA_FINAL',
            'ESC_H', 'REAL_H', 'H_REAL_LIQ',
            'HORAS_DEC', 'HORAS_PROD', 'HORAS_IMPROD',
            'APONTOU_REFEICAO', 'FALTA_REFEICAO', 'EFICIENCIA_GERAL', 'STATUS'
        ]

        df_export = df_view[colunas_excel].rename(columns={
            'DT_REF': 'Data', 'GESTOR': 'Gestor', 'SETOR': 'Equipe (Setor)',
            'MATRICULA_FINAL': 'Matricula', 'NOME_FINAL': 'Colaborador',
            'ESC_H': 'Escala Programada', 'REAL_H': 'Jornada Realizada',
            'H_REAL_LIQ': 'Horas Pagas (RH)', 'HORAS_DEC': 'Horas Apontadas (PIMS)',
            'HORAS_PROD': 'Hrs Produtivas', 'HORAS_IMPROD': 'Hrs Improdutivas',
            'APONTOU_REFEICAO': 'Apontou Refeicao (Diario)?', 'FALTA_REFEICAO': 'Dias s/ Refeicao',
            'EFICIENCIA_GERAL': 'Eficiencia (%)'
        })

        # Renomeia e ordena para apresentação limpa do Ranking
        df_rank_excel = df_rank.rename(columns={
            'SETOR': 'Equipe (Setor)', 'GESTOR': 'Gestor', 'MATRICULA_FINAL': 'Matricula', 'NOME_FINAL': 'Colaborador',
            'H_REAL_LIQ': 'Jornada (h)', 'HORAS_DEC': 'Apontado (h)', 'HORAS_PROD': 'Produtivo (h)',
            'HORAS_IMPROD': 'Improdutivo (h)', 'FALTA_REFEICAO': 'Dias sem Refeicao', 'EFI': 'Eficiencia (%)'
        })

        # Reordena colunas no Excel: Setor -> Colaborador -> Gestor
        cols_order_rank = ['Equipe (Setor)', 'Colaborador', 'Gestor', 'Matricula', 'Jornada (h)', 'Apontado (h)',
                           'Produtivo (h)', 'Improdutivo (h)', 'Eficiencia (%)', 'Dias sem Refeicao']
        df_rank_excel = df_rank_excel[cols_order_rank]

        df_export.to_excel(writer, sheet_name="Base Detalhada", index=False)
        df_setor.to_excel(writer, sheet_name="Ranking Setores", index=False)
        df_rank_excel.to_excel(writer, sheet_name="Ranking Colaboradores", index=False)

    bytes_excel = excel_io.getvalue()

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = temp_pdf.name
    temp_pdf.close()
    pdf.output(pdf_path)

    with open(pdf_path, "rb") as f:
        bytes_pdf = f.read()

    os.remove(pdf_path)

    # Limpeza de imagens
    for img in arquivos_temporarios:
        try:
            os.remove(img)
        except:
            pass

    return bytes_excel, bytes_pdf


# ==============================================================================
# 1. MOTOR DE PROCESSAMENTO E BANCO DE DADOS
# ==============================================================================

def safe_float(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    try:
        return float(str(val).replace(',', '.').strip())
    except:
        return 0.0


def parse_rh_time_range(val):
    if pd.isna(val) or str(val).strip() in ['-', '', 'FOLGA', 'FERIADO', 'DSR', 'COMPENSADO', 'null']: return 0.0
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
        pass
    return 0.0


@st.cache_data(show_spinner="Cruzando dados do PIMS e do RH...", ttl=600)
def processar_dados_corporativos(file_pims, file_rh):
    try:
        # --- A. LEITURA ROBUSTA DO PIMS ---
        if file_pims.name.lower().endswith('.csv'):
            try:
                pims = pd.read_csv(file_pims, sep=None, engine='python', encoding='utf-8')
            except:
                file_pims.seek(0)
                pims = pd.read_csv(file_pims, sep=None, engine='python', encoding='latin-1')
        else:
            pims = pd.read_excel(file_pims)

        pims.columns = [str(c).upper().strip() for c in pims.columns]

        req_pims = ['MATRICULA', 'COLABORADOR', 'HORAS', 'TIPO_OPER', 'OPERACAO']
        if not set(req_pims).issubset(pims.columns):
            st.error(f"PIMS inválido. As colunas obrigatórias são: {req_pims}")
            return None

        col_data = 'INICIO' if 'INICIO' in pims.columns else 'DATA'
        pims['DT_REF'] = pd.to_datetime(pims[col_data], dayfirst=True, errors='coerce').dt.date
        pims['HORAS_DEC'] = pims['HORAS'].apply(safe_float)

        pims['TIPO_OPER_CLEAN'] = pims['TIPO_OPER'].astype(str).str.strip().str.upper()
        pims['OPERACAO_CLEAN'] = pims['OPERACAO'].astype(str).str.strip().str.upper()

        pims['IS_REFEICAO'] = pims['OPERACAO_CLEAN'].str.contains('REFEI', na=False)
        pims['HORAS_PROD'] = np.where(pims['TIPO_OPER_CLEAN'] == 'PRODUTIVO', pims['HORAS_DEC'], 0)
        pims['HORAS_IMPROD'] = np.where(pims['TIPO_OPER_CLEAN'] == 'IMPRODUTIVO', pims['HORAS_DEC'], 0)

        pims_agg = pims.groupby(['MATRICULA', 'DT_REF']).agg({
            'COLABORADOR': 'first',
            'HORAS_DEC': 'sum',
            'HORAS_PROD': 'sum',
            'HORAS_IMPROD': 'sum',
            'IS_REFEICAO': 'max'
        }).reset_index()

        pims_agg['MATRICULA'] = pims_agg['MATRICULA'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        pims_agg['APONTOU_REFEICAO'] = np.where(pims_agg['IS_REFEICAO'] > 0, 'Sim', 'Não')

        # --- B. LEITURA ROBUSTA DO RH (PONTO) ---
        if file_rh.name.lower().endswith('.csv'):
            try:
                rh = pd.read_csv(file_rh, header=None, sep=None, engine='python', encoding='utf-8')
            except:
                file_rh.seek(0)
                rh = pd.read_csv(file_rh, header=None, sep=None, engine='python', encoding='latin-1')
        else:
            rh = pd.read_excel(file_rh, header=None)

        rh['SETOR'] = np.where(
            rh[1].isna() &
            rh[0].notna() &
            (~rh[0].astype(str).str.contains('FUNCIONÁRIO|Horário|nan', case=False, na=False)),
            rh[0].astype(str).str.strip(),
            np.nan
        )
        rh['SETOR'] = rh['SETOR'].ffill()

        rh = rh[pd.to_numeric(rh[1], errors='coerce').notna()].copy()
        rh = rh.rename(columns={
            0: 'PREFIX', 1: 'MAT_ID', 2: 'NOME', 3: 'TURMA', 4: 'DATA',
            5: 'ESC_H', 6: 'ESC_I', 8: 'REAL_H', 9: 'REAL_I'
        })

        rh['DT_REF'] = pd.to_datetime(rh['DATA'], dayfirst=False, errors='coerce').dt.date

        rh['PREFIX'] = rh['PREFIX'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        rh['PREFIX_S'] = pd.to_numeric(rh['PREFIX'], errors='coerce').fillna(0).astype(int).astype(str)
        rh['ID_S'] = pd.to_numeric(rh['MAT_ID'], errors='coerce').fillna(0).astype(int).astype(str)
        rh['MAT_FULL'] = rh['PREFIX_S'] + rh['ID_S'].str.zfill(5)
        rh['MAT_FULL'] = rh['MAT_FULL'].astype(str).str.strip()

        rh['ESC_H'] = rh['ESC_H'].astype(str).replace('nan', '-')
        rh['REAL_H'] = rh['REAL_H'].astype(str).replace('nan', '-')

        rh['H_TRAB'] = rh['REAL_H'].apply(parse_rh_time_range)
        rh['H_INT'] = rh['REAL_I'].apply(parse_rh_time_range)
        rh['H_REAL_LIQ'] = (rh['H_TRAB'] - rh['H_INT']).clip(lower=0)

        rh_agg = rh.groupby(['MAT_FULL', 'DT_REF']).agg({
            'NOME': 'first',
            'TURMA': 'first',
            'SETOR': 'first',
            'ESC_H': 'first',
            'REAL_H': 'first',
            'H_REAL_LIQ': 'sum'
        }).reset_index()

        rh_agg['SETOR'] = rh_agg['SETOR'].str.replace(r'^\d+\s*-\s*', '', regex=True)

        # --- C. MERGE FINAL (CRUZAMENTO) ---
        df_final = pd.merge(rh_agg, pims_agg, left_on=['MAT_FULL', 'DT_REF'], right_on=['MATRICULA', 'DT_REF'],
                            how='outer')

        df_final['MATRICULA_FINAL'] = df_final['MAT_FULL'].fillna(df_final['MATRICULA'])
        df_final['NOME_FINAL'] = df_final['NOME'].fillna(df_final['COLABORADOR'])
        df_final['SETOR'] = df_final['SETOR'].fillna('NÃO IDENTIFICADO (SÓ PIMS)')
        df_final['TURMA'] = df_final['TURMA'].fillna('-')

        df_final['H_REAL_LIQ'] = df_final['H_REAL_LIQ'].fillna(0.0)
        df_final['ESC_H'] = df_final['ESC_H'].fillna('-')
        df_final['REAL_H'] = df_final['REAL_H'].fillna('-')
        cols_fill = ['HORAS_DEC', 'HORAS_PROD', 'HORAS_IMPROD']
        df_final[cols_fill] = df_final[cols_fill].fillna(0)
        df_final['APONTOU_REFEICAO'] = df_final['APONTOU_REFEICAO'].fillna('Não')

        # NOVA MÉTRICA: Contabiliza Falta de Refeição Apenas para quem teve Jornada Longa
        df_final['FALTA_REFEICAO'] = np.where((df_final['H_REAL_LIQ'] > 4.0) & (df_final['APONTOU_REFEICAO'] == 'Não'),
                                              1, 0)

        conditions = [
            (df_final['H_REAL_LIQ'] > 0.1) & (df_final['HORAS_DEC'] < 0.1),
            (df_final['H_REAL_LIQ'] < 0.1) & (df_final['HORAS_DEC'] > 0.1),
            (df_final['H_REAL_LIQ'] > 4.0) & (df_final['APONTOU_REFEICAO'] == 'Não'),
            (df_final['H_REAL_LIQ'] > 0.1) | (df_final['HORAS_DEC'] > 0.1)
        ]
        choices = [
            'CRÍTICO (Sem Apontamento)',
            'ALERTA (Ponto Não Batido)',
            'ALERTA (Sem Refeição)',
            'OK'
        ]
        df_final['STATUS'] = np.select(conditions, choices, default='-')

        df_final['EFICIENCIA_GERAL'] = np.where(df_final['H_REAL_LIQ'] > 0,
                                                (df_final['HORAS_DEC'] / df_final['H_REAL_LIQ']) * 100, 0)
        df_final['EFICIENCIA_VISUAL'] = df_final['EFICIENCIA_GERAL'].clip(0, 120)

        return df_final

    except Exception as e:
        st.error(f"Erro fatal ao processar: {e}")
        return None


# Função para alimentar o Banco de Dados com novos gestores e aplicar ao Dataframe
def aplicar_sincronizacao_banco(df):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mapa_gestores (
            matricula TEXT PRIMARY KEY,
            nome TEXT,
            setor TEXT,
            gestor TEXT
        )
    """)

    df_unicos = df[['MATRICULA_FINAL', 'NOME_FINAL', 'SETOR']].drop_duplicates('MATRICULA_FINAL')
    df_banco = pd.read_sql("SELECT matricula, gestor FROM mapa_gestores", conn)
    mapa_existente = dict(zip(df_banco['matricula'].astype(str), df_banco['gestor']))

    novos = []
    for _, row in df_unicos.iterrows():
        mat = str(row['MATRICULA_FINAL']).strip()
        if mat not in mapa_existente:
            novos.append((mat, row['NOME_FINAL'], row['SETOR'], 'Não Definido'))
            mapa_existente[mat] = 'Não Definido'

    if novos:
        cursor.executemany("INSERT INTO mapa_gestores (matricula, nome, setor, gestor) VALUES (?, ?, ?, ?)", novos)
        conn.commit()

    conn.close()

    df['GESTOR'] = df['MATRICULA_FINAL'].astype(str).str.strip().map(mapa_existente).fillna('Não Definido')
    return df


# ==============================================================================
# 2. INTERFACE E LÓGICA DE FILTROS AVANÇADOS
# ==============================================================================

if 'dataset_rh' not in st.session_state: st.session_state['dataset_rh'] = None

with st.expander("📂 Carregar Dados (PIMS + RH)", expanded=(st.session_state['dataset_rh'] is None)):
    c1, c2 = st.columns(2)
    f_pims = c1.file_uploader("Produção (PIMS)", type=['xlsx', 'csv'])
    f_rh = c2.file_uploader("Ponto (RH)", type=['xlsx', 'csv'])
    if f_pims and f_rh and st.button("Cruzar Apontamentos 🚀", type="primary"):
        df_proc = processar_dados_corporativos(f_pims, f_rh)
        if df_proc is not None:
            df_sincronizado = aplicar_sincronizacao_banco(df_proc)
            st.session_state['dataset_rh'] = df_sincronizado
            st.rerun()

if st.session_state['dataset_rh'] is None:
    ui_empty_state("Aguardando importação para iniciar a auditoria.", icon="📊")
    st.stop()

df = st.session_state['dataset_rh']

# --- CONFIGURAÇÃO DE GESTORES PELO BANCO DE DADOS ---
st.markdown("---")
with st.expander("⚙️ Estrutura de Liderança (Banco de Dados)", expanded=False):
    st.write(
        "Vincule cada colaborador ao seu respectivo Gestor. Esta tabela reflete e **salva direto no Banco de Dados** do sistema de forma permanente.")

    tab_map_manual, tab_map_lote = st.tabs(["✍️ Edição Manual", "📂 Importação em Lote"])

    with tab_map_manual:
        conn_map = get_db_connection()
        df_mapa_bd = pd.read_sql("SELECT matricula, nome, setor, gestor FROM mapa_gestores ORDER BY nome", conn_map)

        edited_map = st.data_editor(
            df_mapa_bd,
            use_container_width=True,
            hide_index=True,
            column_config={
                "matricula": st.column_config.TextColumn("Matrícula", disabled=True),
                "nome": st.column_config.TextColumn("Colaborador", disabled=True, width="medium"),
                "setor": st.column_config.TextColumn("Setor (Referência)", disabled=True, width="medium"),
                "gestor": st.column_config.TextColumn("👤 Nome do Gestor (Edite aqui)", required=True)
            }
        )

        if st.button("💾 Salvar Relações de Liderança", type="primary"):
            cursor_map = conn_map.cursor()
            for _, row in edited_map.iterrows():
                cursor_map.execute("UPDATE mapa_gestores SET gestor = ? WHERE matricula = ?",
                                   (row['gestor'], row['matricula']))
            conn_map.commit()
            conn_map.close()
            st.toast("Relações salvas no Banco de Dados com Sucesso!", icon="✅")
            st.session_state['dataset_rh'] = aplicar_sincronizacao_banco(st.session_state['dataset_rh'])
            import time;

            time.sleep(1)
            st.rerun()
        else:
            conn_map.close()

    with tab_map_lote:
        st.markdown("1. **Baixe a planilha atual** com todos os funcionários cadastrados no banco.")


        def gerar_excel_mapeamento():
            conn_xl = get_db_connection()
            df_xl = pd.read_sql("SELECT matricula, nome, setor, gestor FROM mapa_gestores ORDER BY nome", conn_xl)
            conn_xl.close()
            output = io.BytesIO()
            with pd.ExcelWriter(output) as writer:
                df_xl.to_excel(writer, index=False, sheet_name="Mapeamento_Lideranca")
            output.seek(0)
            return output


        st.download_button(
            label="📥 Baixar Planilha de Mapeamento",
            data=gerar_excel_mapeamento(),
            file_name="mapeamento_gestores.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.markdown("2. Edite a coluna **`gestor`** no Excel e faça o upload do arquivo salvo.")
        uploaded_mapa = st.file_uploader("Carregar Planilha Preenchida", type=['xlsx', 'csv'], key="up_mapa_lote")

        if uploaded_mapa:
            try:
                df_up_mapa = pd.read_excel(uploaded_mapa) if uploaded_mapa.name.endswith('.xlsx') else pd.read_csv(
                    uploaded_mapa)
                df_up_mapa.columns = [str(c).lower().strip() for c in df_up_mapa.columns]

                if 'matricula' in df_up_mapa.columns and 'gestor' in df_up_mapa.columns:
                    st.dataframe(df_up_mapa.head(3), use_container_width=True)
                    if st.button("🚀 Processar Importação em Lote", type="primary"):
                        conn_imp = get_db_connection()
                        cursor_imp = conn_imp.cursor()

                        atualizados = 0
                        for _, row in df_up_mapa.iterrows():
                            mat_val = str(row['matricula']).strip()
                            gestor_val = str(row['gestor']).strip()

                            if pd.notna(gestor_val) and gestor_val.lower() != 'nan' and gestor_val != '':
                                cursor_imp.execute("UPDATE mapa_gestores SET gestor = ? WHERE matricula = ?",
                                                   (gestor_val, mat_val))
                                atualizados += 1

                        conn_imp.commit()
                        conn_imp.close()

                        st.toast(f"Importação concluída! {atualizados} registros atualizados.", icon="✅")
                        st.session_state['dataset_rh'] = aplicar_sincronizacao_banco(st.session_state['dataset_rh'])
                        import time;

                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("A planilha deve conter obrigatoriamente as colunas 'matricula' e 'gestor'.")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")

# --- SIDEBAR: FILTROS PODEROSOS (CASCATA & TODOS DE MÚLTIPLA ESCOLHA PRÉ-SELECIONADOS) ---
with st.sidebar:
    st.header("🔍 Filtros de Auditoria")

    min_d, max_d = df['DT_REF'].min(), df['DT_REF'].max()
    # MODIFICAÇÃO: Removido min_value e max_value. Agora você pode selecionar qualquer data (ex: mês inteiro)
    datas = st.date_input("Período de Análise", [min_d, max_d])

    # 1. Filtro MÚLTIPLO de Gestor (Pré-Selecionado por padrão)
    lista_gestores = sorted(df['GESTOR'].unique().tolist())
    sel_gestores = st.multiselect("Liderança (Gestor)", options=lista_gestores, default=lista_gestores,
                                  help="Remova no 'X' as lideranças que não deseja ver")

    # Previne quebra se o usuário desmarcar tudo
    if not sel_gestores:
        df_temp_g = df.iloc[0:0]
    else:
        df_temp_g = df[df['GESTOR'].isin(sel_gestores)]

    # 2. Filtro MÚLTIPLO de Setor (Pré-Selecionado por padrão)
    lista_setores = sorted(df_temp_g['SETOR'].unique().tolist())
    sel_setores = st.multiselect("Equipe / Setor", options=lista_setores, default=lista_setores,
                                 help="Remova no 'X' as equipes que não deseja ver")

    if not sel_setores:
        df_temp_s = df_temp_g.iloc[0:0]
    else:
        df_temp_s = df_temp_g[df_temp_g['SETOR'].isin(sel_setores)]

    # 3. Filtro MÚLTIPLO de Turma (Vazio = Todos)
    lista_turmas = sorted(df_temp_s['TURMA'].dropna().astype(str).unique().tolist())
    sel_turmas = st.multiselect("Turma de Turno", options=lista_turmas, default=[],
                                help="Deixe vazio para selecionar todas")
    df_temp_t = df_temp_s[df_temp_s['TURMA'].astype(str).isin(sel_turmas)] if sel_turmas else df_temp_s

    # 4. Filtro MÚLTIPLO de Colaborador (Vazio = Todos)
    lista_nomes = sorted(df_temp_t['NOME_FINAL'].unique().tolist())
    sel_nomes = st.multiselect("Colaborador", options=lista_nomes, default=[], help="Deixe vazio para selecionar todos")

# --- APLICAÇÃO DOS FILTROS NA VIEW ---
df_view = df.copy()

if type(datas) in (tuple, list):
    if len(datas) == 2:
        d_in, d_out = datas[0], datas[1]
    elif len(datas) == 1:
        d_in = d_out = datas[0]
    else:
        d_in, d_out = min_d, max_d
    df_view = df_view[(df_view['DT_REF'] >= d_in) & (df_view['DT_REF'] <= d_out)]
else:
    d_in, d_out = min_d, max_d

# Aplicação estrita baseada nas seleções do usuário
df_view = df_view[df_view['GESTOR'].isin(sel_gestores)]
df_view = df_view[df_view['SETOR'].isin(sel_setores)]
if sel_turmas: df_view = df_view[df_view['TURMA'].astype(str).isin(sel_turmas)]
if sel_nomes: df_view = df_view[df_view['NOME_FINAL'].isin(sel_nomes)]

# ==============================================================================
# 3. DASHBOARD GERENCIAL UI
# ==============================================================================

# Calcula KPIs para o Dashboard
total_dias_periodo = (d_out - d_in).days + 1
dias_trabalhados = df_view['DT_REF'].nunique()

efi_media = df_view[df_view['H_REAL_LIQ'] > 0]['EFICIENCIA_GERAL'].mean() if not df_view[
    df_view['H_REAL_LIQ'] > 0].empty else 0
h_rh = df_view['H_REAL_LIQ'].sum()
h_produtivas = df_view['HORAS_PROD'].sum()
h_improdutivas = df_view['HORAS_IMPROD'].sum()
h_total_pims = df_view['HORAS_DEC'].sum()

taxa_produtividade = (h_produtivas / h_total_pims * 100) if h_total_pims > 0 else 0

dias_sem_refeicao = len(df_view[df_view['STATUS'] == 'ALERTA (Sem Refeição)'])

st.markdown(
    f"**🗓️ Período Selecionado:** {d_in.strftime('%d/%m/%Y')} a {d_out.strftime('%d/%m/%Y')} ({total_dias_periodo} dias) &nbsp;&bull;&nbsp; **Dias Trabalhados:** {dias_trabalhados} dias com apontamento na base.")
st.markdown("<br>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
cor_efi = "#10B981" if efi_media >= 85 else ("#F59E0B" if efi_media >= 70 else "#EF4444")
cor_prod = "#10B981" if taxa_produtividade >= 70 else "#F59E0B"

ui_kpi_card(c1, "Eficiência de Apontamento", f"{efi_media:.1f}%", get_icon("check", cor_efi), cor_efi,
            "Horas PIMS vs Jornada RH")
ui_kpi_card(c2, "Horas Produtivas", f"{h_produtivas:.0f} h", get_icon("gear", cor_prod), cor_prod,
            f"Equivale a {taxa_produtividade:.1f}% do tempo")
ui_kpi_card(c3, "Horas Improdutivas", f"{h_improdutivas:.0f} h", get_icon("clock", "#EF4444"), "#EF4444",
            "Viagens, Refeição, etc.")
ui_kpi_card(c4, "Alerta Refeição", f"{dias_sem_refeicao}",
            get_icon("fire", "#EF4444" if dias_sem_refeicao > 0 else "#10B981"),
            "#EF4444" if dias_sem_refeicao > 0 else "#10B981", "Dias sem apontar refeição")

st.markdown("<br>", unsafe_allow_html=True)

# ABAS
tab_setor, tab_rank, tab_cal, tab_dados = st.tabs(
    ["🏆 Ranking de Setores", "🏅 Desempenho de Colaboradores", "📅 Calendário", "📋 Tabela Analítica"])

with tab_setor:
    st.markdown("##### 🏆 Desempenho de Equipes (Por Setor)")
    st.caption("Avaliando quais setores (independente de gestor) possuem as melhores práticas operacionais.")

    if not df_view.empty:
        df_g = df_view.groupby(['SETOR']).agg({
            'H_REAL_LIQ': 'sum',
            'HORAS_DEC': 'sum',
            'HORAS_PROD': 'sum'
        }).reset_index()
        df_g['EFICIENCIA_GERAL'] = np.where(df_g['H_REAL_LIQ'] > 0, (df_g['HORAS_DEC'] / df_g['H_REAL_LIQ']) * 100, 0)
        df_g['PROD_PCT'] = np.where(df_g['HORAS_DEC'] > 0, (df_g['HORAS_PROD'] / df_g['HORAS_DEC']) * 100, 0)

        df_g = df_g.sort_values('EFICIENCIA_GERAL', ascending=False)

        c_chart, c_table = st.columns([1, 1.2])
        with c_chart:
            df_plot = df_g.sort_values('EFICIENCIA_GERAL', ascending=True)
            altura_g = max(400, len(df_plot) * 35)

            fig_g = px.bar(df_plot, x='EFICIENCIA_GERAL', y='SETOR', orientation='h',
                           color='EFICIENCIA_GERAL', color_continuous_scale='RdYlGn',
                           text_auto='.1f', title="Eficiência % (Todas as Equipes)")
            fig_g.update_layout(yaxis_title="", margin=dict(l=10, r=10, t=40, b=10), height=altura_g)
            st.plotly_chart(fig_g, use_container_width=True)

        with c_table:
            st.dataframe(
                df_g, use_container_width=True, hide_index=True,
                column_config={
                    "SETOR": st.column_config.TextColumn("Equipe / Setor", width="large"),
                    "EFICIENCIA_GERAL": st.column_config.ProgressColumn("Eficiência", format="%.1f%%", min_value=0,
                                                                        max_value=120),
                    "PROD_PCT": st.column_config.NumberColumn("% Produtivas", format="%.1f%%")
                }
            )

with tab_rank:
    st.markdown("##### 🏅 Desempenho por Colaborador (Produtivo vs Improdutivo)")
    st.caption("Gráfico adaptável: Todos os colaboradores filtrados serão mostrados sem limite de quantidade.")

    df_rank = df_view.groupby(['SETOR', 'GESTOR', 'NOME_FINAL']).agg({
        'HORAS_PROD': 'sum',
        'HORAS_IMPROD': 'sum',
        'HORAS_DEC': 'sum'
    }).reset_index()

    df_rank = df_rank.sort_values(['SETOR', 'GESTOR', 'HORAS_DEC'], ascending=[True, True, True])

    if not df_rank.empty:
        altura_dinamica_grafico = max(500, len(df_rank) * 28)

        fig_rank = go.Figure()
        fig_rank.add_trace(go.Bar(
            y=df_rank['NOME_FINAL'] + ' (' + df_rank['SETOR'].str.slice(0, 10) + ')',
            x=df_rank['HORAS_PROD'],
            name='Produtivo', orientation='h', marker=dict(color='#22C55E')
        ))
        fig_rank.add_trace(go.Bar(
            y=df_rank['NOME_FINAL'] + ' (' + df_rank['SETOR'].str.slice(0, 10) + ')',
            x=df_rank['HORAS_IMPROD'],
            name='Improdutivo', orientation='h', marker=dict(color='#F59E0B')
        ))

        fig_rank.update_layout(
            barmode='stack',
            height=altura_dinamica_grafico,
            margin=dict(l=10, r=10, t=30, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.05, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_rank, use_container_width=True)

with tab_cal:
    st.markdown("##### Mapa de Calor: Assiduidade e Apontamento")
    try:
        pivot = df_view.pivot_table(index='NOME_FINAL', columns='DT_REF', values='EFICIENCIA_VISUAL',
                                    aggfunc='mean').fillna(0)
        h_calc = max(400, len(pivot) * 25)
        fig = px.imshow(pivot, aspect="auto", color_continuous_scale=['#EF4444', '#F59E0B', '#10B981'],
                        labels=dict(x="Dia", y="Colaborador", color="Eficiência %"),
                        x=[d.strftime('%d/%m') for d in pivot.columns])
        fig.update_layout(height=h_calc)
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.info("Sem dados para o calendário.")

with tab_dados:
    st.markdown("##### 🔍 Extração Analítica")

    colunas_exibicao = [
        'DT_REF', 'SETOR', 'NOME_FINAL', 'GESTOR',
        'ESC_H', 'REAL_H', 'H_REAL_LIQ',
        'HORAS_DEC', 'HORAS_PROD', 'HORAS_IMPROD',
        'APONTOU_REFEICAO', 'FALTA_REFEICAO', 'EFICIENCIA_GERAL', 'STATUS'
    ]

    st.dataframe(
        df_view[colunas_exibicao],
        use_container_width=True,
        column_config={
            "DT_REF": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "SETOR": st.column_config.TextColumn("Equipe / Setor", width="medium"),
            "NOME_FINAL": st.column_config.TextColumn("Colaborador", width="medium"),
            "GESTOR": st.column_config.TextColumn("Gestor", width="medium"),
            "ESC_H": st.column_config.TextColumn("Escala Programada"),
            "REAL_H": st.column_config.TextColumn("Jornada Realizada"),
            "H_REAL_LIQ": st.column_config.NumberColumn("Horas Pagas", format="%.1f"),
            "HORAS_DEC": st.column_config.NumberColumn("Total PIMS", format="%.1f"),
            "HORAS_PROD": st.column_config.NumberColumn("Produtivas", format="%.1f"),
            "HORAS_IMPROD": st.column_config.NumberColumn("Improdutivas", format="%.1f"),
            "EFICIENCIA_GERAL": st.column_config.ProgressColumn("Efic. (%)", format="%.0f%%", min_value=0,
                                                                max_value=120),
            "APONTOU_REFEICAO": st.column_config.TextColumn("Refeição Diária?"),
            "FALTA_REFEICAO": st.column_config.NumberColumn("Alerta S/ Refeicao", format="%d"),
            "STATUS": st.column_config.TextColumn("Status")
        }
    )

# ==============================================================================
# IMPRESSÃO E RELATÓRIOS
# ==============================================================================
st.markdown("---")
st.markdown("### 🖨️ Relatórios Executivos (Paisagem)")
st.caption("Exporte a análise cruzada num formato PDF otimizado (A4 deitado) para apresentar à diretoria.")

with st.spinner("Desenhando gráficos e compilando PDF..."):
    excel_bytes, pdf_bytes = processar_e_gerar_relatorios_eficiencia(df_view, d_in, d_out)

nome_padrao_arquivo = f"Auditoria_PeopleAnalytics_{d_in.strftime('%d%m%y')}_a_{d_out.strftime('%d%m%y')}"

c_pdf, c_excel = st.columns(2)
with c_pdf:
    st.download_button(
        label="📄 Descarregar Relatório PDF",
        data=pdf_bytes,
        file_name=f"{nome_padrao_arquivo}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )
with c_excel:
    st.download_button(
        label="📊 Descarregar Tabela Excel",
        data=excel_bytes,
        file_name=f"{nome_padrao_arquivo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )