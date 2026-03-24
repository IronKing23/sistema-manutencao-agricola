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
import base64
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

# --- CONFIGURAÇÃO INICIAL E FOTOS ---
load_custom_css()

icon_main = get_icon("dashboard", "#2196F3", "36")
ui_header(
    title="Análise de Eficiência e Apontamentos",
    subtitle="Auditoria de Produtividade: Cruzamento de Jornada RH vs. Apontamentos PIMS.",
    icon=icon_main
)

FOTOS_DIR = "fotos_funcionarios"


def get_foto_base64(matricula_ou_nome):
    """Gera um data URI base64 para a foto do colaborador ou gestor"""
    # Tenta por matricula ou nome exato
    caminho = os.path.join(FOTOS_DIR, f"{str(matricula_ou_nome).strip()}.jpg")
    if os.path.exists(caminho):
        try:
            with open(caminho, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                return f"data:image/jpeg;base64,{b64}"
        except:
            pass
    return "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"


# ==============================================================================
# CLASSES E LÓGICA DE PDF
# ==============================================================================

class RelatorioPDF(FPDF):
    def __init__(self, titulo_relatorio="Relatorio de Eficiencia, Cedro", orientacao='L', *args, **kwargs):
        super().__init__(orientation=orientacao, format='A4', *args, **kwargs)
        self.titulo_relatorio = titulo_relatorio
        self.orientacao = orientacao
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


@st.cache_data(show_spinner="Compilando relatórios PDF/Excel Avançados...", ttl=600)
def processar_e_gerar_relatorios_eficiencia(df_view, df_improd_global, dt_in, dt_out, df_espelho, orientacao_pdf='L',
                                            criterio_ranking="Engajamento (Horas Válidas)"):
    excel_io = io.BytesIO()
    arquivos_temporarios = []

    # Variáveis Geométricas Dinâmicas
    w_total = 277 if orientacao_pdf == 'L' else 190
    max_y_page = 185 if orientacao_pdf == 'L' else 275

    total_dias_periodo = (dt_out - dt_in).days + 1
    dias_trabalhados = df_view['DT_REF'].nunique()

    efi_media = df_view[df_view['H_REAL_LIQ'] > 0]['EFICIENCIA_GERAL'].mean() if not df_view[
        df_view['H_REAL_LIQ'] > 0].empty else 0
    h_rh = df_view['H_REAL_LIQ'].sum()
    h_prod = df_view['HORAS_PROD'].sum()
    h_improd = df_view['HORAS_IMPROD'].sum()
    h_apont = df_view['HORAS_DEC'].sum()

    perc_produtivo = min((h_prod / h_apont * 100) if h_apont > 0 else 0, 100)

    df_criticos = df_view[df_view['STATUS'].str.contains('Sem Apontamento|Ponto Não Batido', na=False)]
    df_sem_ref = df_view[df_view['STATUS'] == 'ALERTA (Sem Refeição)']
    fantasmas = df_criticos['NOME_FINAL'].nunique()

    # --- HELPER: SISTEMA DE AVATARES CIRCULARES ---
    avatar_cache = {}

    def get_circular_avatar(identificador, bg_color):
        cache_key = f"{identificador}_{bg_color}"
        if cache_key in avatar_cache:
            return avatar_cache[cache_key]

        foto_path = os.path.join(FOTOS_DIR, f"{str(identificador).strip()}.jpg")
        if not os.path.exists(foto_path):
            avatar_cache[cache_key] = None
            return None

        try:
            from PIL import Image, ImageDraw
            img = Image.open(foto_path).convert("RGBA")
            iw, ih = img.size
            min_dim = min(iw, ih)
            img = img.crop(((iw - min_dim) // 2, (ih - min_dim) // 2, (iw + min_dim) // 2, (ih + min_dim) // 2))

            hr_size = 150
            img = img.resize((hr_size, hr_size), Image.LANCZOS)

            bg = Image.new('RGB', (hr_size, hr_size), bg_color)
            draw = ImageDraw.Draw(bg)

            draw.ellipse((0, 0, hr_size, hr_size), fill=(226, 232, 240))

            mask = Image.new('L', (hr_size, hr_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            b_w = 4
            mask_draw.ellipse((b_w, b_w, hr_size - b_w, hr_size - b_w), fill=255)

            bg.paste(img, (0, 0), mask)

            temp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            bg.save(temp.name, 'JPEG', quality=95)
            arquivos_temporarios.append(temp.name)
            avatar_cache[cache_key] = temp.name
            return temp.name
        except Exception:
            avatar_cache[cache_key] = None
            return None

    # Passa a orientação para a inicialização do PDF
    titulo_rel = "Relatorio Auditoria de Produtividade (Paisagem)" if orientacao_pdf == 'L' else "Relatorio Auditoria de Produtividade (Retrato)"
    pdf = RelatorioPDF(titulo_relatorio=f"{titulo_rel}, Cedro", orientacao=orientacao_pdf)
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- PÁGINA 1: RESUMO EXECUTIVO ---
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 8, "Resumo Executivo", 0, 1, 'L')

    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(80, 80, 80)
    str_periodo = f"Periodo Selecionado: {dt_in.strftime('%d/%m/%Y')} a {dt_out.strftime('%d/%m/%Y')} ({total_dias_periodo} dias)  |  Dias Trabalhados: {dias_trabalhados} dias com apontamento na base."
    pdf.cell(0, 6, str_periodo, 0, 1, 'L')
    pdf.ln(4)

    y_kpi = pdf.get_y()
    largura_card = (w_total - 15) / 4

    fnt_kpi_t = 8 if orientacao_pdf == 'L' else 6
    fnt_kpi_v = 14 if orientacao_pdf == 'L' else 10

    # Cards KPI
    pos_x1 = 10
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.rect(pos_x1, y_kpi, largura_card, 22, 'DF')
    pdf.set_xy(pos_x1, y_kpi + 4)
    pdf.set_font('Arial', 'B', fnt_kpi_t)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(largura_card, 5, "APONTAMENTO (GERAL)", 0, 1, 'C')
    pdf.set_xy(pos_x1, y_kpi + 10)
    pdf.set_font('Arial', 'B', fnt_kpi_v)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(largura_card, 7, f"{efi_media:.1f}%", 0, 1, 'C')

    pos_x2 = pos_x1 + largura_card + 5
    pdf.rect(pos_x2, y_kpi, largura_card, 22, 'DF')
    pdf.set_xy(pos_x2, y_kpi + 4)
    pdf.set_font('Arial', 'B', fnt_kpi_t)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(largura_card, 5, "HORAS PAGAS (RH)", 0, 1, 'C')
    pdf.set_xy(pos_x2, y_kpi + 10)
    pdf.set_font('Arial', 'B', fnt_kpi_v)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(largura_card, 7, f"{h_rh:.0f} h", 0, 1, 'C')

    pos_x3 = pos_x2 + largura_card + 5
    pdf.rect(pos_x3, y_kpi, largura_card, 22, 'DF')
    pdf.set_xy(pos_x3, y_kpi + 4)
    pdf.set_font('Arial', 'B', fnt_kpi_t)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(largura_card, 5, "TAXA PRODUTIVIDADE", 0, 1, 'C')
    pdf.set_xy(pos_x3, y_kpi + 10)
    pdf.set_font('Arial', 'B', fnt_kpi_v)
    pdf.set_text_color(22, 163, 74)
    pdf.cell(largura_card, 7, f"{perc_produtivo:.1f}%", 0, 1, 'C')

    pos_x4 = pos_x3 + largura_card + 5
    pdf.rect(pos_x4, y_kpi, largura_card, 22, 'DF')
    pdf.set_xy(pos_x4, y_kpi + 4)
    pdf.set_font('Arial', 'B', fnt_kpi_t)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(largura_card, 5, "FALHAS (SEM APONT.)", 0, 1, 'C')
    pdf.set_xy(pos_x4, y_kpi + 10)
    pdf.set_font('Arial', 'B', fnt_kpi_v)
    pdf.set_text_color(220, 38, 38)
    pdf.cell(largura_card, 7, f"{fantasmas} pessoas", 0, 1, 'C')

    pdf.set_xy(10, y_kpi + 28)
    pdf.ln(2)

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

    if MATPLOTLIB_AVAILABLE and not df_view.empty:
        df_timeline = df_view.groupby('DT_REF').agg({'H_REAL_LIQ': 'sum', 'HORAS_DEC': 'sum'}).reset_index()
        df_timeline['EFI'] = np.where(df_timeline['H_REAL_LIQ'] > 0,
                                      (df_timeline['HORAS_DEC'] / df_timeline['H_REAL_LIQ']) * 100, 0)
        df_timeline['EFI'] = df_timeline['EFI'].clip(upper=100)
        df_timeline = df_timeline.sort_values('DT_REF')

        fig_w = 14 if orientacao_pdf == 'L' else 9
        fig, ax = plt.subplots(figsize=(fig_w, 3.5))
        ax.plot(df_timeline['DT_REF'], df_timeline['EFI'], marker='o', color='#16A34A', lw=2.5, markersize=6)
        ax.fill_between(df_timeline['DT_REF'], df_timeline['EFI'], color='#16A34A', alpha=0.1)
        ax.set_title('Evolucao da Eficiencia Media Diaria (%)', fontsize=12, fontweight='bold', color='#333333')
        ax.grid(True, linestyle='--', alpha=0.4)
        ax.spines['top'].set_visible(False);
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#CCCCCC');
        ax.spines['bottom'].set_color('#CCCCCC')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.tick_params(axis='both', labelsize=9, colors='#555555')
        ax.set_ylim(bottom=0)

        plt.tight_layout()
        img_trend = tempfile.mktemp(suffix=".png")
        arquivos_temporarios.append(img_trend)
        fig.savefig(img_trend, dpi=150, bbox_inches='tight')
        plt.close(fig)

        pdf.image(img_trend, x=10, w=w_total)

    # ==============================================================================
    # PÁGINA 2: RANKING DE DESEMPENHO POR SETOR
    # ==============================================================================
    pdf.add_page()

    df_setor = df_view.groupby(['SETOR']).agg(
        {'H_REAL_LIQ': 'sum', 'HORAS_DEC': 'sum', 'HORAS_PROD': 'sum'}).reset_index()
    df_setor['EFI'] = np.where(df_setor['H_REAL_LIQ'] > 0, (df_setor['HORAS_DEC'] / df_setor['H_REAL_LIQ']) * 100,
                               0).clip(max=100)
    df_setor['PROD_PCT'] = np.where(df_setor['HORAS_DEC'] > 0, (df_setor['HORAS_PROD'] / df_setor['HORAS_DEC']) * 100,
                                    0).clip(max=100)
    df_setor = df_setor.sort_values('EFI', ascending=False)

    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 8, "Desempenho Geral por Equipes (Setores)", 0, 1)
    pdf.ln(2)

    if MATPLOTLIB_AVAILABLE and not df_setor.empty:
        df_setor_plot = df_setor.head(15).sort_values('EFI', ascending=True)
        fig_w = 14 if orientacao_pdf == 'L' else 9
        fig2, ax2 = plt.subplots(figsize=(fig_w, 4))
        ax2.barh(df_setor_plot['SETOR'].str.slice(0, 40), df_setor_plot['EFI'], color='#2196F3', edgecolor='none')
        ax2.set_title('Top Setores por Eficiencia (%)', fontsize=12, fontweight='bold', color='#333333')
        ax2.spines['top'].set_visible(False);
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color('#CCCCCC');
        ax2.spines['bottom'].set_visible(False)
        ax2.tick_params(axis='both', labelsize=9, colors='#555555')

        for i, v in enumerate(df_setor_plot['EFI']):
            ax2.text(v + 1, i, f"{v:.1f}%", color='#333333', va='center', fontsize=9, fontweight='bold')

        plt.tight_layout()
        img_setor = tempfile.mktemp(suffix=".png")
        arquivos_temporarios.append(img_setor)
        fig2.savefig(img_setor, dpi=150, bbox_inches='tight')
        plt.close(fig2)

        pdf.image(img_setor, x=10, w=w_total)
        pdf.ln(5)

    pdf.set_font('Arial', 'B', 8 if orientacao_pdf == 'P' else 9)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(22, 102, 53)
    pdf.set_draw_color(255, 255, 255)

    w_s = [77, 40, 40, 40, 40, 40] if orientacao_pdf == 'L' else [50, 25, 25, 30, 30, 30]

    pdf.cell(w_s[0], 8, " Equipe (Setor)", 1, 0, 'L', fill=True)
    pdf.cell(w_s[1], 8, " Jornada RH", 1, 0, 'C', fill=True)
    pdf.cell(w_s[2], 8, " Apontado", 1, 0, 'C', fill=True)
    pdf.cell(w_s[3], 8, " Hrs Produtivas", 1, 0, 'C', fill=True)
    pdf.cell(w_s[4], 8, " Eficiencia", 1, 0, 'C', fill=True)
    pdf.cell(w_s[5], 8, " % Prod.", 1, 1, 'C', fill=True)

    pdf.set_font('Arial', '', 8 if orientacao_pdf == 'P' else 9)
    pdf.set_text_color(40, 40, 40)
    pdf.set_draw_color(220, 220, 220)
    fill = False

    for _, row in df_setor.iterrows():
        if pdf.get_y() > max_y_page - 8:
            pdf.add_page()

        if fill:
            pdf.set_fill_color(245, 247, 250)
        else:
            pdf.set_fill_color(255, 255, 255)

        s_str = str(row['SETOR'])[:(45 if orientacao_pdf == 'L' else 25)].encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(w_s[0], 7, f" {s_str}", 'B', 0, 'L', fill=True)
        pdf.cell(w_s[1], 7, f"{row['H_REAL_LIQ']:.1f} h", 'B', 0, 'C', fill=True)
        pdf.cell(w_s[2], 7, f"{row['HORAS_DEC']:.1f} h", 'B', 0, 'C', fill=True)
        pdf.cell(w_s[3], 7, f"{row['HORAS_PROD']:.1f} h", 'B', 0, 'C', fill=True)
        pdf.cell(w_s[4], 7, f"{row['EFI']:.1f}%", 'B', 0, 'C', fill=True)
        pdf.cell(w_s[5], 7, f"{row['PROD_PCT']:.1f}%", 'B', 1, 'C', fill=True)
        fill = not fill

    # ==============================================================================
    # PÁGINA 3: RAIO-X DA IMPRODUTIVIDADE
    # ==============================================================================
    valid_keys = df_view[['MATRICULA_FINAL', 'DT_REF']].drop_duplicates()
    valid_keys.columns = ['MATRICULA', 'DT_REF']
    improd_filtered = pd.merge(df_improd_global, valid_keys, on=['MATRICULA', 'DT_REF'],
                               how='inner') if not df_improd_global.empty else pd.DataFrame()

    if not improd_filtered.empty:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(22, 102, 53)
        pdf.cell(0, 8, "Raio-X da Improdutividade (Motivos de Parada)", 0, 1)
        pdf.ln(2)

        improd_agrupado = improd_filtered.groupby('OPERACAO_NOME')['HORAS_DEC'].sum().reset_index().sort_values(
            'HORAS_DEC', ascending=False)

        if MATPLOTLIB_AVAILABLE:
            df_improd_plot = improd_agrupado.head(15).sort_values('HORAS_DEC', ascending=True)
            fig_w = 14 if orientacao_pdf == 'L' else 9
            fig_imp, ax_imp = plt.subplots(figsize=(fig_w, 4.5))
            ax_imp.barh(df_improd_plot['OPERACAO_NOME'].str.slice(0, 50), df_improd_plot['HORAS_DEC'], color='#F59E0B',
                        edgecolor='none')
            ax_imp.set_title('Top 15 Motivos de Improdutividade (Horas Totais)', fontsize=12, fontweight='bold',
                             color='#333333')
            ax_imp.spines['top'].set_visible(False);
            ax_imp.spines['right'].set_visible(False)
            ax_imp.spines['left'].set_color('#CCCCCC');
            ax_imp.spines['bottom'].set_visible(False)
            ax_imp.tick_params(axis='both', labelsize=9, colors='#555555')
            for i, v in enumerate(df_improd_plot['HORAS_DEC']):
                ax_imp.text(v + 0.5, i, f"{v:.1f}h", color='#333333', va='center', fontsize=9, fontweight='bold')
            plt.tight_layout()
            img_imp = tempfile.mktemp(suffix=".png")
            arquivos_temporarios.append(img_imp)
            fig_imp.savefig(img_imp, dpi=150, bbox_inches='tight')
            plt.close(fig_imp)
            pdf.image(img_imp, x=10, w=w_total)
            pdf.ln(5)

        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(22, 102, 53)

        w_rx = [200, 77] if orientacao_pdf == 'L' else [130, 60]

        pdf.cell(w_rx[0], 8, " Motivo / Operacao", 1, 0, 'L', fill=True)
        pdf.cell(w_rx[1], 8, " Total Desperdicado", 1, 1, 'C', fill=True)

        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(40, 40, 40)
        fill = False
        for _, row in improd_agrupado.iterrows():
            if pdf.get_y() > max_y_page - 8:
                pdf.add_page()
                pdf.set_font('Arial', 'B', 9);
                pdf.set_text_color(255, 255, 255);
                pdf.set_fill_color(22, 102, 53)
                pdf.cell(w_rx[0], 8, " Motivo / Operacao", 1, 0, 'L', fill=True)
                pdf.cell(w_rx[1], 8, " Total Desperdicado", 1, 1, 'C', fill=True)
                pdf.set_font('Arial', '', 9);
                pdf.set_text_color(40, 40, 40)

            if fill:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(255, 255, 255)
            op_str = str(row['OPERACAO_NOME'])[:(100 if orientacao_pdf == 'L' else 60)].encode('latin-1',
                                                                                               'replace').decode(
                'latin-1')
            pdf.cell(w_rx[0], 7, f" {op_str}", 'B', 0, 'L', fill=True)
            pdf.cell(w_rx[1], 7, f"{row['HORAS_DEC']:.1f} h", 'B', 1, 'C', fill=True)
            fill = not fill

    # ==============================================================================
    # PÁGINA 4: RANKING COLABORADORES DETALHADO
    # ==============================================================================
    pdf.add_page()

    df_rank = df_view.groupby(['SETOR', 'GESTOR', 'MATRICULA_FINAL', 'NOME_FINAL']).agg({
        'H_REAL_LIQ': 'sum', 'HORAS_DEC': 'sum', 'HORAS_PROD': 'sum', 'HORAS_IMPROD': 'sum', 'FALTA_REFEICAO': 'sum'
    }).reset_index()

    df_rank['EFI'] = np.where(df_rank['H_REAL_LIQ'] > 0, (df_rank['HORAS_DEC'] / df_rank['H_REAL_LIQ']) * 100, 0).clip(
        max=100)
    df_rank = df_rank.sort_values(['SETOR', 'GESTOR', 'HORAS_DEC'], ascending=[True, True, False])

    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 8, "Desempenho Detalhado por Colaborador", 0, 1)
    pdf.ln(2)

    if MATPLOTLIB_AVAILABLE and not df_rank.empty:
        df_rank_plot_full = df_rank.sort_values('HORAS_DEC', ascending=False)
        chunk_size = 20
        chunks = [df_rank_plot_full[i:i + chunk_size] for i in range(0, len(df_rank_plot_full), chunk_size)]

        for idx, chunk in enumerate(chunks):
            chunk_plot = chunk.iloc[::-1]
            altura_figura = max(3.0, len(chunk_plot) * 0.3)
            fig_w = 14 if orientacao_pdf == 'L' else 9
            fig3, ax3 = plt.subplots(figsize=(fig_w, altura_figura))

            labels = chunk_plot['NOME_FINAL'].str.slice(0, 20) + " (" + chunk_plot['SETOR'].str.slice(0, 12) + ")"

            ax3.barh(labels, chunk_plot['HORAS_PROD'], color='#22C55E', label='Produtivo', edgecolor='none')
            ax3.barh(labels, chunk_plot['HORAS_IMPROD'], left=chunk_plot['HORAS_PROD'], color='#F59E0B',
                     label='Improdutivo', edgecolor='none')

            titulo = 'Desempenho de Colaboradores (Volume de Horas Apontadas)'
            if len(chunks) > 1: titulo += f' - Parte {idx + 1}'

            ax3.set_title(titulo, fontsize=12, fontweight='bold', color='#333333')
            ax3.legend(loc='lower right', frameon=False)
            ax3.spines['top'].set_visible(False);
            ax3.spines['right'].set_visible(False)
            ax3.spines['left'].set_color('#CCCCCC');
            ax3.spines['bottom'].set_visible(False)
            ax3.tick_params(axis='both', labelsize=8, colors='#555555')

            plt.tight_layout()
            img_colab = tempfile.mktemp(suffix=".png")
            arquivos_temporarios.append(img_colab)
            fig3.savefig(img_colab, dpi=150, bbox_inches='tight')
            plt.close(fig3)

            if idx > 0 or pdf.get_y() > (130 if orientacao_pdf == 'L' else 200): pdf.add_page()
            pdf.image(img_colab, x=10, w=w_total)
            pdf.ln(5)

    w_c = [16, 36, 48, 43, 22, 22, 22, 22, 22, 22] if orientacao_pdf == 'L' else [14, 20, 36, 30, 15, 15, 15, 15, 15,
                                                                                  15]

    def print_colaboradores_header():
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(22, 102, 53)
        pdf.cell(w_c[0], 8, " Foto", 1, 0, 'C', fill=True)
        pdf.cell(w_c[1], 8, " Setor", 1, 0, 'L', fill=True)
        pdf.cell(w_c[2], 8, " Colaborador", 1, 0, 'L', fill=True)
        pdf.cell(w_c[3], 8, " Gestor", 1, 0, 'L', fill=True)
        pdf.cell(w_c[4], 8, " Jornada", 1, 0, 'C', fill=True)
        pdf.cell(w_c[5], 8, " Apontado", 1, 0, 'C', fill=True)
        pdf.cell(w_c[6], 8, " Prod.", 1, 0, 'C', fill=True)
        pdf.cell(w_c[7], 8, " Improd.", 1, 0, 'C', fill=True)
        pdf.cell(w_c[8], 8, " Efic.", 1, 0, 'C', fill=True)
        pdf.cell(w_c[9], 8, " S/ Ref.", 1, 1, 'C', fill=True)

    print_colaboradores_header()
    pdf.set_font('Arial', '', 7 if orientacao_pdf == 'P' else 8)
    pdf.set_text_color(40, 40, 40)
    pdf.set_draw_color(220, 220, 220)
    fill = False

    for _, row in df_rank.iterrows():
        if pdf.get_y() > max_y_page - 14:
            pdf.add_page()
            print_colaboradores_header()
            pdf.set_font('Arial', '', 7 if orientacao_pdf == 'P' else 8)
            pdf.set_text_color(40, 40, 40)

        bg_rgb = (245, 247, 250) if fill else (255, 255, 255)
        pdf.set_fill_color(*bg_rgb)

        s_str = str(row['SETOR'])[:(18 if orientacao_pdf == 'L' else 10)].encode('latin-1', 'replace').decode('latin-1')
        n_str = str(row['NOME_FINAL'])[:(25 if orientacao_pdf == 'L' else 18)].encode('latin-1', 'replace').decode(
            'latin-1')
        g_str = str(row['GESTOR'])[:(22 if orientacao_pdf == 'L' else 12)].encode('latin-1', 'replace').decode(
            'latin-1')

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        pdf.cell(w_c[0], 12, "", 'B', 0, 'C', fill=True)

        matricula = str(row['MATRICULA_FINAL']).strip()
        circ_img = get_circular_avatar(matricula, bg_rgb)
        img_s = 10 if orientacao_pdf == 'P' else 11
        img_x = x_start + (w_c[0] - img_s) / 2
        img_y = y_start + (12 - img_s) / 2

        if circ_img:
            pdf.image(circ_img, x=img_x, y=img_y, w=img_s, h=img_s)
        else:
            pdf.set_draw_color(220, 220, 220)
            pdf.rect(img_x, img_y, img_s, img_s, 'D')

        pdf.cell(w_c[1], 12, f" {s_str}", 'B', 0, 'L', fill=True)
        pdf.cell(w_c[2], 12, f" {n_str}", 'B', 0, 'L', fill=True)
        pdf.cell(w_c[3], 12, f" {g_str}", 'B', 0, 'L', fill=True)
        pdf.cell(w_c[4], 12, f"{row['H_REAL_LIQ']:.1f}h", 'B', 0, 'C', fill=True)
        pdf.cell(w_c[5], 12, f"{row['HORAS_DEC']:.1f}h", 'B', 0, 'C', fill=True)
        pdf.cell(w_c[6], 12, f"{row['HORAS_PROD']:.1f}h", 'B', 0, 'C', fill=True)
        pdf.cell(w_c[7], 12, f"{row['HORAS_IMPROD']:.1f}h", 'B', 0, 'C', fill=True)
        pdf.cell(w_c[8], 12, f"{row['EFI']:.0f}%", 'B', 0, 'C', fill=True)
        pdf.cell(w_c[9], 12, f"{row['FALTA_REFEICAO']}d", 'B', 1, 'C', fill=True)
        fill = not fill

    # ==============================================================================
    # PÁGINA 5: MATRIZ DE CALENDÁRIO DIÁRIO (COM FOTO)
    # ==============================================================================
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 8, "Matriz de Apontamentos Diarios (Eficiencia %)", 0, 1)

    pdf.set_font('Arial', '', 8)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5,
             "Legenda: Verde (>=85%) | Amarelo (70 a 84%) | Vermelho (<70%) | Laranja (Sem Apont.) | Roxo (>100% Super-Apont.) | Cinza (Folga)",
             0, 1)
    pdf.ln(2)

    dias_unicos = sorted(df_view['DT_REF'].dropna().unique())
    max_dias = min(len(dias_unicos), 31)
    dias_to_plot = dias_unicos[:max_dias]

    w_foto_m = 12
    w_setor_m = 28 if orientacao_pdf == 'L' else 18
    w_nome_m = 45 if orientacao_pdf == 'L' else 35
    w_dia_m = (w_total - w_nome_m - w_setor_m - w_foto_m) / max_dias if max_dias > 0 else 10

    def print_matrix_header():
        pdf.set_font('Arial', 'B', 7)
        pdf.set_fill_color(22, 102, 53)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(w_foto_m, 6, " Foto", 1, 0, 'C', fill=True)
        pdf.cell(w_setor_m, 6, " Setor", 1, 0, 'L', fill=True)
        pdf.cell(w_nome_m, 6, " Colaborador", 1, 0, 'L', fill=True)
        for d in dias_to_plot:
            pdf.cell(w_dia_m, 6, d.strftime('%d'), 1, 0, 'C', fill=True)
        pdf.ln()

    if max_dias > 0:
        print_matrix_header()

        df_view_pdf = df_view.copy()
        df_view_pdf['MATRIZ_VAL'] = df_view_pdf['EFICIENCIA_VISUAL']
        mask_falta_pdf = (df_view_pdf['STATUS'] == 'CRÍTICO (Sem Apontamento)')
        mask_super_pdf = (df_view_pdf['STATUS'] == 'ALERTA (Super-Apontamento)')

        df_view_pdf.loc[mask_falta_pdf, 'MATRIZ_VAL'] = -1
        df_view_pdf.loc[mask_super_pdf, 'MATRIZ_VAL'] = -2

        pivot_matrix = df_view_pdf.pivot_table(index=['SETOR', 'MATRICULA_FINAL', 'NOME_FINAL'], columns='DT_REF',
                                               values='MATRIZ_VAL',
                                               aggfunc='mean')
        pivot_matrix = pivot_matrix.sort_index(level=[0, 1, 2])

        pdf.set_font('Arial', 'B', 5 if orientacao_pdf == 'P' else 6)
        pdf.set_draw_color(220, 220, 220)

        for idx, row in pivot_matrix.iterrows():
            if pdf.get_y() > max_y_page - 12:
                pdf.add_page()
                print_matrix_header()

            setor, matricula, nome = idx
            setor_str = str(setor)[:(15 if orientacao_pdf == 'L' else 10)].encode('latin-1', 'replace').decode(
                'latin-1')
            nome_str = str(nome)[:(22 if orientacao_pdf == 'L' else 16)].encode('latin-1', 'replace').decode('latin-1')

            x_curr = pdf.get_x()
            y_curr = pdf.get_y()

            bg_rgb = (245, 247, 250)
            pdf.set_fill_color(*bg_rgb)
            pdf.rect(x_curr, y_curr, w_foto_m, 10, 'DF')

            circ_img = get_circular_avatar(matricula, bg_rgb)
            img_s = 8
            img_x = x_curr + (w_foto_m - img_s) / 2
            img_y = y_curr + (10 - img_s) / 2

            if circ_img:
                pdf.image(circ_img, x=img_x, y=img_y, w=img_s, h=img_s)
            else:
                pdf.set_draw_color(200, 200, 200)
                pdf.rect(img_x, img_y, img_s, img_s, 'D')

            pdf.set_xy(x_curr + w_foto_m, y_curr)

            pdf.set_text_color(40, 40, 40)
            pdf.cell(w_setor_m, 10, f" {setor_str}", 1, 0, 'L', fill=True)
            pdf.cell(w_nome_m, 10, f" {nome_str}", 1, 0, 'L', fill=True)

            for d in dias_to_plot:
                val = row.get(d, np.nan)

                if pd.isna(val) or val == 0:
                    pdf.set_fill_color(240, 240, 240)
                    txt = "-"
                    pdf.set_text_color(180, 180, 180)
                elif val == -1:
                    pdf.set_fill_color(254, 215, 170)
                    txt = "0"
                    pdf.set_text_color(154, 52, 18)
                elif val == -2:
                    pdf.set_fill_color(233, 213, 255)
                    txt = ">100"
                    pdf.set_text_color(107, 33, 168)
                else:
                    txt = f"{val:.0f}"
                    if val >= 85:
                        pdf.set_fill_color(187, 247, 208)
                        pdf.set_text_color(22, 101, 52)
                    elif val >= 70:
                        pdf.set_fill_color(254, 240, 138)
                        pdf.set_text_color(161, 98, 7)
                    else:
                        pdf.set_fill_color(254, 202, 202)
                        pdf.set_text_color(153, 27, 27)

                pdf.cell(w_dia_m, 10, txt, 1, 0, 'C', fill=True)
            pdf.ln()

    # ==============================================================================
    # PÁGINA 6: ESPELHO DE PONTO DIÁRIO (COM FOTOS E TOTALIZADOR)
    # ==============================================================================
    dias_unicos_espelho = sorted(df_espelho['DT_REF'].dropna().unique())
    max_dias_espelho = min(len(dias_unicos_espelho), 31)
    dias_to_plot_espelho = dias_unicos_espelho[:max_dias_espelho]

    if max_dias_espelho > 0:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(22, 102, 53)
        pdf.cell(0, 8, "Espelho de Ponto Diario (Jornada Realizada no RH)", 0, 1)

        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5,
                 "Legenda: Horarios exibidos em duas linhas (Entrada em cima, Saida embaixo). F = Folga, Feriado ou Compensado | - = Sem Registro",
                 0, 1)
        pdf.ln(2)

        w_foto_p = 12
        w_setor_p = 28 if orientacao_pdf == 'L' else 18
        w_nome_p = 45 if orientacao_pdf == 'L' else 35
        w_saldo_p = 16 if orientacao_pdf == 'L' else 14
        w_dia_p = (
                              w_total - w_nome_p - w_setor_p - w_foto_p - w_saldo_p) / max_dias_espelho if max_dias_espelho > 0 else 10

        def print_matrix_ponto_header():
            pdf.set_font('Arial', 'B', 7)
            pdf.set_fill_color(22, 102, 53)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(w_foto_p, 6, " Foto", 1, 0, 'C', fill=True)
            pdf.cell(w_setor_p, 6, " Setor", 1, 0, 'L', fill=True)
            pdf.cell(w_nome_p, 6, " Colaborador", 1, 0, 'L', fill=True)
            for d in dias_to_plot:
                pdf.cell(w_dia_p, 6, d.strftime('%d'), 1, 0, 'C', fill=True)
            pdf.cell(w_saldo_p, 6, " Saldo", 1, 0, 'C', fill=True)
            pdf.ln()

        print_matrix_ponto_header()

        pivot_ponto = df_espelho.pivot_table(index=['SETOR', 'MATRICULA_FINAL', 'NOME_FINAL'], columns='DT_REF',
                                             values='REAL_H', aggfunc='first')
        pivot_ponto = pivot_ponto.sort_index(level=[0, 1, 2])

        pdf.set_draw_color(220, 220, 220)

        df_rank_stats = df_view.groupby(['SETOR', 'MATRICULA_FINAL']).agg(
            {'H_REAL_LIQ': 'sum', 'HORAS_DEC': 'sum'}).reset_index()

        for idx, row in pivot_ponto.iterrows():
            if pdf.get_y() > max_y_page - 12:
                pdf.add_page()
                print_matrix_ponto_header()

            setor, matricula, nome = idx
            setor_str = str(setor)[:(15 if orientacao_pdf == 'L' else 10)].encode('latin-1', 'replace').decode(
                'latin-1')
            nome_str = str(nome)[:(22 if orientacao_pdf == 'L' else 16)].encode('latin-1', 'replace').decode('latin-1')

            x_start_row = pdf.get_x()
            y_start_row = pdf.get_y()

            bg_rgb = (245, 247, 250)
            pdf.set_fill_color(*bg_rgb)
            pdf.rect(x_start_row, y_start_row, w_foto_p, 10, 'DF')

            circ_img = get_circular_avatar(matricula, bg_rgb)
            img_s = 8
            img_x = x_start_row + (w_foto_p - img_s) / 2
            img_y = y_start_row + (10 - img_s) / 2

            if circ_img:
                pdf.image(circ_img, x=img_x, y=img_y, w=img_s, h=img_s)
            else:
                pdf.set_draw_color(200, 200, 200)
                pdf.rect(img_x, img_y, img_s, img_s, 'D')

            pdf.set_text_color(40, 40, 40)
            pdf.set_font('Arial', 'B', 6)

            x_setor = x_start_row + w_foto_p
            pdf.rect(x_setor, y_start_row, w_setor_p, 10, 'DF')
            pdf.set_xy(x_setor, y_start_row + 2)
            pdf.cell(w_setor_p, 6, f" {setor_str}", 0, 0, 'L')

            x_nome = x_setor + w_setor_p
            pdf.rect(x_nome, y_start_row, w_nome_p, 10, 'DF')
            pdf.set_xy(x_nome, y_start_row + 2)
            pdf.cell(w_nome_p, 6, f" {nome_str}", 0, 0, 'L')

            pdf.set_xy(x_nome + w_nome_p, y_start_row)
            pdf.set_font('Arial', '', 4.5)

            for d in dias_to_plot_espelho:
                val = row.get(d, np.nan)
                val_str = str(val).strip().upper()

                if pd.isna(val) or val_str == 'NAN' or val_str == '-' or val_str == '':
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_text_color(180, 180, 180)
                    parts = ["-"]
                elif any(k in val_str for k in ['FOLGA', 'FERIADO', 'DSR', 'COMPENSADO']):
                    pdf.set_fill_color(219, 234, 254)
                    pdf.set_text_color(30, 58, 138)
                    parts = ["F"]
                else:
                    pdf.set_fill_color(255, 255, 255)
                    pdf.set_text_color(40, 40, 40)
                    val_clean = val_str.replace(',', '.')
                    parts = val_clean.split('/') if '/' in val_clean else [val_clean]

                x_curr = pdf.get_x()
                y_curr = pdf.get_y()

                pdf.rect(x_curr, y_curr, w_dia_p, 10, 'DF')

                if len(parts) == 1:
                    pdf.set_xy(x_curr, y_curr + 2)
                    pdf.cell(w_dia_p, 6, parts[0], 0, 0, 'C')
                else:
                    pdf.set_xy(x_curr, y_curr + 1)
                    pdf.cell(w_dia_p, 4, parts[0], 0, 0, 'C')
                    pdf.set_xy(x_curr, y_curr + 5)
                    pdf.cell(w_dia_p, 4, parts[1], 0, 0, 'C')

                pdf.set_xy(x_curr + w_dia_p, y_curr)

            emp_stats = df_rank_stats[
                (df_rank_stats['MATRICULA_FINAL'] == matricula) & (df_rank_stats['SETOR'] == setor)]
            if not emp_stats.empty:
                tot_rh = emp_stats.iloc[0]['H_REAL_LIQ']
                tot_pims = emp_stats.iloc[0]['HORAS_DEC']
            else:
                tot_rh, tot_pims = 0, 0

            x_curr = pdf.get_x()
            y_curr = pdf.get_y()
            pdf.set_fill_color(248, 250, 252)
            pdf.rect(x_curr, y_curr, w_saldo_p, 10, 'DF')

            pdf.set_font('Arial', 'B', 4.5)
            pdf.set_text_color(30, 58, 138)
            pdf.set_xy(x_curr, y_curr + 2)
            pdf.cell(w_saldo_p, 3, f"RH: {tot_rh:.1f}h", 0, 0, 'C')

            pdf.set_text_color(22, 101, 52)
            pdf.set_xy(x_curr, y_curr + 5.5)
            pdf.cell(w_saldo_p, 3, f"PIMS: {tot_pims:.1f}h", 0, 0, 'C')

            pdf.set_xy(10, y_start_row + 10)

    # ==============================================================================
    # PÁGINA 7: RANKING TOP 10 (COLABORADORES)
    # ==============================================================================

    df_top10 = df_view.groupby(['MATRICULA_FINAL', 'NOME_FINAL', 'SETOR']).agg({
        'HORAS_PROD': 'sum', 'HORAS_DEC': 'sum', 'H_REAL_LIQ': 'sum'
    }).reset_index()

    df_top10 = df_top10[df_top10['H_REAL_LIQ'] > 0]
    df_top10['HORAS_VALIDAS'] = df_top10[['HORAS_DEC', 'H_REAL_LIQ']].min(axis=1)
    df_top10['PCT_VISUAL'] = np.where(df_top10['H_REAL_LIQ'] > 0,
                                      (df_top10['HORAS_DEC'] / df_top10['H_REAL_LIQ']) * 100, 0).clip(max=100)
    df_top10['EFI_PROD'] = np.where(df_top10['HORAS_DEC'] > 0, (df_top10['HORAS_PROD'] / df_top10['HORAS_DEC']) * 100,
                                    0).clip(max=100)

    if "Eficiência" in criterio_ranking:
        df_top10 = df_top10.sort_values(by=['EFI_PROD', 'HORAS_VALIDAS'], ascending=[False, False]).head(10)
        sub_title_pdf = "Ranking focado na Eficiencia Produtiva (maior % de tempo produtivo / maquina operando)."
    elif "Volume" in criterio_ranking:
        df_top10 = df_top10.sort_values(by=['HORAS_DEC', 'EFI_PROD'], ascending=[False, False]).head(10)
        sub_title_pdf = "Ranking focado no Volume Bruto de Horas Apontadas no PIMS (Produtivas + Improdutivas)."
    else:
        df_top10 = df_top10.sort_values(by=['HORAS_VALIDAS', 'EFI_PROD'], ascending=[False, False]).head(10)
        sub_title_pdf = "Ranking focado em Volume Valido (PIMS alinhado ao RH), bloqueando super-apontamentos indevidos."

    if not df_top10.empty:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(22, 102, 53)
        titulo_ranking = f"Ranking de Excelencia: Os 10 Melhores Apontamentos ({dt_in.strftime('%d/%m')} a {dt_out.strftime('%d/%m')})"
        pdf.cell(0, 8, titulo_ranking, 0, 1, 'C')

        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 4, sub_title_pdf, 0, 1, 'C')

        y_base = pdf.get_y() + 20

        top_list = df_top10.to_dict('records')
        while len(top_list) < 10:
            top_list.append(None)

        def draw_pdf_podium_card(pdf_obj, rank, row, x, y, w, color_r, color_g, color_b):
            if not row: return y
            h = 42

            pdf_obj.set_fill_color(252, 253, 254)
            pdf_obj.rect(x, y, w, h, 'F')

            pdf_obj.set_draw_color(226, 232, 240)
            pdf_obj.set_line_width(0.2)
            pdf_obj.rect(x, y, w, h, 'D')

            pdf_obj.set_fill_color(color_r, color_g, color_b)
            pdf_obj.rect(x, y, w, 3, 'F')

            img_s = 20
            img_x = x + (w - img_s) / 2
            img_y = y - (img_s / 2) - 2

            foto_path = os.path.join(FOTOS_DIR, f"{str(row['MATRICULA_FINAL']).strip()}.jpg")
            circ_img_path = None

            if os.path.exists(foto_path):
                try:
                    from PIL import Image, ImageDraw
                    img = Image.open(foto_path).convert("RGBA")
                    iw, ih = img.size
                    min_dim = min(iw, ih)
                    img = img.crop(((iw - min_dim) // 2, (ih - min_dim) // 2, (iw + min_dim) // 2, (ih + min_dim) // 2))

                    hr_size = 300
                    img = img.resize((hr_size, hr_size), Image.LANCZOS)

                    bg = Image.new('RGB', (hr_size, hr_size), (255, 255, 255))
                    draw = ImageDraw.Draw(bg)
                    draw.ellipse((0, 0, hr_size, hr_size), fill=(color_r, color_g, color_b))

                    mask = Image.new('L', (hr_size, hr_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    b_w = 16
                    mask_draw.ellipse((b_w, b_w, hr_size - b_w, hr_size - b_w), fill=255)

                    bg.paste(img, (0, 0), mask)
                    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    bg.save(temp.name, 'JPEG', quality=95)
                    arquivos_temporarios.append(temp.name)
                    circ_img_path = temp.name
                except:
                    pass

            if circ_img_path:
                pdf_obj.image(circ_img_path, x=img_x, y=img_y, w=img_s, h=img_s)
            else:
                pdf_obj.set_fill_color(color_r, color_g, color_b)
                pdf_obj.rect(img_x, img_y, img_s, img_s, 'F')
                pdf_obj.set_fill_color(220, 220, 220)
                pdf_obj.rect(img_x + 1, img_y + 1, img_s - 2, img_s - 2, 'F')

            badge_w = 6
            badge_x = img_x + img_s - badge_w + 1
            badge_y = img_y + img_s - badge_w + 1

            pdf_obj.set_fill_color(color_r, color_g, color_b)
            pdf_obj.rect(badge_x, badge_y, badge_w, badge_w, 'F')
            pdf_obj.set_draw_color(255, 255, 255)
            pdf_obj.set_line_width(0.4)
            pdf_obj.rect(badge_x, badge_y, badge_w, badge_w, 'D')

            pdf_obj.set_font('Arial', 'B', 9)
            pdf_obj.set_text_color(255, 255, 255)
            pdf_obj.set_xy(badge_x, badge_y)
            pdf_obj.cell(badge_w, badge_w, f"{rank}", 0, 0, 'C')

            y_text = y + 10
            pdf_obj.set_xy(x + 2, y_text)
            pdf_obj.set_font('Arial', 'B', 9)
            pdf_obj.set_text_color(30, 41, 59)
            nome_curto = str(row['NOME_FINAL']).encode('latin-1', 'replace').decode('latin-1')[
                :(22 if orientacao_pdf == 'L' else 15)]
            pdf_obj.cell(w - 4, 5, nome_curto, 0, 1, 'C')

            pdf_obj.set_xy(x + 2, pdf_obj.get_y())
            pdf_obj.set_font('Arial', '', 7)
            pdf_obj.set_text_color(100, 116, 139)
            setor_curto = str(row['SETOR']).encode('latin-1', 'replace').decode('latin-1')[
                :(26 if orientacao_pdf == 'L' else 20)]
            pdf_obj.cell(w - 4, 3, f"{setor_curto}", 0, 1, 'C')

            if "Eficiência" in criterio_ranking:
                val_destaque = f"{row['EFI_PROD']:.0f}% Efic."
                val_sec = f"{row['PCT_VISUAL']:.0f}% Apontado"
                is_good = row['EFI_PROD'] >= 85
            elif "Volume" in criterio_ranking:
                val_destaque = f"{row['HORAS_DEC']:.1f}h Apont."
                val_sec = f"Efic: {row['EFI_PROD']:.1f}%"
                is_good = True
            else:
                val_destaque = f"{row['PCT_VISUAL']:.0f}% Apont."
                val_sec = f"Efic: {row['EFI_PROD']:.1f}%"
                is_good = row['PCT_VISUAL'] >= 85

            y_kpi = pdf_obj.get_y() + 4
            pdf_obj.set_xy(x + 4, y_kpi)
            if is_good:
                pdf_obj.set_fill_color(220, 252, 231);
                pdf_obj.set_text_color(22, 101, 52)
            else:
                pdf_obj.set_fill_color(254, 240, 138);
                pdf_obj.set_text_color(161, 98, 7)

            pdf_obj.set_font('Arial', 'B', 10)
            pdf_obj.cell(w - 8, 6, val_destaque, 0, 1, 'C', fill=True)

            pdf_obj.set_xy(x + 2, pdf_obj.get_y() + 2)
            pdf_obj.set_font('Arial', 'B', 8)
            if "Volume" in criterio_ranking:
                pdf_obj.set_text_color(100, 116, 139)
            else:
                pdf_obj.set_text_color(34, 197, 94)
            pdf_obj.cell(w - 4, 4, val_sec, 0, 1, 'C')

            return y + h

        center_x = 297 / 2 if orientacao_pdf == 'L' else 210 / 2
        card_w = 65 if orientacao_pdf == 'L' else 50
        gap = 4 if orientacao_pdf == 'L' else 2

        x_1st = center_x - (card_w / 2)
        x_2nd = x_1st - card_w - gap
        x_3rd = x_1st + card_w + gap

        y_1st = y_base
        y_2nd = y_base + 10
        y_3rd = y_base + 18

        y_end_1 = draw_pdf_podium_card(pdf, 2, top_list[1], x_2nd, y_2nd, card_w, 148, 163, 184)
        y_end_2 = draw_pdf_podium_card(pdf, 1, top_list[0], x_1st, y_1st, card_w, 250, 191, 36)
        y_end_3 = draw_pdf_podium_card(pdf, 3, top_list[2], x_3rd, y_3rd, card_w, 180, 83, 9)

        max_y_podium = max(y_end_1, y_end_2, y_end_3)

        start_y = max_y_podium + 10
        pdf.set_y(start_y)

        pdf.set_draw_color(226, 232, 240)
        pdf.set_line_width(0.3)
        pdf.line(10, start_y, w_total + 10, start_y)

        cols = 2 if orientacao_pdf == 'L' else 1
        card_w_list = 130 if orientacao_pdf == 'L' else 150
        gap_x = 8 if orientacao_pdf == 'L' else 0
        total_w = (card_w_list * cols) + (gap_x * (cols - 1))
        margin_l = (297 - total_w) / 2 if orientacao_pdf == 'L' else (210 - total_w) / 2

        y_atual = start_y + 4

        for idx, row in enumerate(top_list[3:], start=4):
            if not row: continue

            col_index = (idx - 4) % cols

            if col_index == 0 and idx > 4:
                y_atual += 14

            x_start = margin_l + col_index * (card_w_list + gap_x)

            pdf.set_fill_color(252, 253, 254)
            pdf.rect(x_start, y_atual, card_w_list, 12, 'F')
            pdf.set_draw_color(226, 232, 240)
            pdf.rect(x_start, y_atual, card_w_list, 12, 'D')

            pdf.set_fill_color(241, 245, 249)
            pdf.rect(x_start, y_atual, 10, 12, 'F')
            pdf.set_font('Arial', 'B', 9)
            pdf.set_text_color(100, 116, 139)
            pdf.set_xy(x_start, y_atual + 3)
            pdf.cell(10, 6, f"{idx}o", 0, 0, 'C')

            foto_path = os.path.join(FOTOS_DIR, f"{str(row['MATRICULA_FINAL']).strip()}.jpg")
            img_s = 10
            img_x = x_start + 12
            img_y = y_atual + 1
            circ_img_list = None

            if os.path.exists(foto_path):
                try:
                    from PIL import Image, ImageDraw
                    img = Image.open(foto_path).convert("RGBA")
                    iw, ih = img.size
                    min_dim = min(iw, ih)
                    img = img.crop(((iw - min_dim) // 2, (ih - min_dim) // 2, (iw + min_dim) // 2, (ih + min_dim) // 2))
                    hr_size = 150
                    img = img.resize((hr_size, hr_size), Image.LANCZOS)
                    bg = Image.new('RGB', (hr_size, hr_size), (252, 253, 254))
                    draw = ImageDraw.Draw(bg)
                    draw.ellipse((0, 0, hr_size, hr_size), fill=(226, 232, 240))

                    mask = Image.new('L', (hr_size, hr_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    b_w = 6
                    mask_draw.ellipse((b_w, b_w, hr_size - b_w, hr_size - b_w), fill=255)
                    bg.paste(img, (0, 0), mask)

                    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    bg.save(temp.name, 'JPEG', quality=95)
                    arquivos_temporarios.append(temp.name)
                    circ_img_list = temp.name
                except:
                    pass

            if circ_img_list:
                pdf.image(circ_img_list, x=img_x, y=img_y, w=img_s, h=img_s)
            else:
                pdf.set_draw_color(220, 220, 220)
                pdf.rect(img_x, img_y, img_s, img_s, 'D')

            pdf.set_text_color(30, 41, 59)
            pdf.set_font('Arial', 'B', 8)
            pdf.set_xy(x_start + 24, y_atual + 2)
            nome_linha = str(row['NOME_FINAL']).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(50, 4, nome_linha[:(25 if orientacao_pdf == 'L' else 35)], 0, 1, 'L')

            pdf.set_font('Arial', '', 6)
            pdf.set_text_color(100, 116, 139)
            pdf.set_xy(x_start + 24, y_atual + 6)
            setor_linha = str(row['SETOR']).encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(50, 4, setor_linha[:(30 if orientacao_pdf == 'L' else 40)], 0, 1, 'L')

            w_stat = 20
            x_stat1 = x_start + card_w_list - (w_stat * 2) - 4
            x_stat2 = x_start + card_w_list - w_stat - 2

            if "Eficiência" in criterio_ranking:
                val_main = f"{row['EFI_PROD']:.0f}%"
                lbl_main = "Efic."
                val_sec = f"{row['PCT_VISUAL']:.0f}%"
                lbl_sec = "Apontado"
                is_good = row['EFI_PROD'] >= 85
            elif "Volume" in criterio_ranking:
                val_main = f"{row['HORAS_DEC']:.1f}h"
                lbl_main = "Apont."
                val_sec = f"{row['EFI_PROD']:.1f}%"
                lbl_sec = "Efic."
                is_good = True
            else:
                val_main = f"{row['PCT_VISUAL']:.0f}%"
                lbl_main = "Apont."
                val_sec = f"{row['EFI_PROD']:.1f}%"
                lbl_sec = "Efic."
                is_good = row['PCT_VISUAL'] >= 85

            if is_good:
                pdf.set_fill_color(220, 252, 231);
                pdf.set_text_color(22, 101, 52)
            else:
                pdf.set_fill_color(254, 240, 138);
                pdf.set_text_color(161, 98, 7)

            pdf.set_xy(x_stat1, y_atual + 2)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(18, 4, val_main, 0, 0, 'C', fill=True)
            pdf.set_text_color(100, 116, 139);
            pdf.set_font('Arial', '', 5)
            pdf.set_xy(x_stat1, y_atual + 7);
            pdf.cell(18, 3, lbl_main, 0, 1, 'C')

            pdf.set_text_color(71, 85, 105)
            pdf.set_font('Arial', 'B', 8)
            pdf.set_xy(x_stat2, y_atual + 2)
            pdf.cell(20, 4, val_sec, 0, 0, 'C')
            pdf.set_text_color(100, 116, 139);
            pdf.set_font('Arial', '', 5)
            pdf.set_xy(x_stat2, y_atual + 7);
            pdf.cell(20, 3, lbl_sec, 0, 1, 'C')

    # ==============================================================================
    # PÁGINA 8: RANKING DA GESTÃO (LIDERANÇA) - BASEADO NO NOVO ESTILO VISUAL
    # ==============================================================================
    df_gestao = df_view.groupby('GESTOR').agg({
        'HORAS_PROD': 'sum', 'HORAS_IMPROD': 'sum', 'HORAS_DEC': 'sum', 'H_REAL_LIQ': 'sum'
    }).reset_index()

    # Remove gestores sem horas no RH ou marcados como "Não Definido"
    df_gestao = df_gestao[(df_gestao['H_REAL_LIQ'] > 0) & (df_gestao['GESTOR'] != 'Não Definido')]

    df_gestao['HORAS_VALIDAS'] = df_gestao[['HORAS_DEC', 'H_REAL_LIQ']].min(axis=1)
    df_gestao['PCT_VISUAL'] = np.where(df_gestao['H_REAL_LIQ'] > 0,
                                       (df_gestao['HORAS_DEC'] / df_gestao['H_REAL_LIQ']) * 100, 0).clip(max=100)
    df_gestao['EFI_PROD'] = np.where(df_gestao['HORAS_DEC'] > 0,
                                     (df_gestao['HORAS_PROD'] / df_gestao['HORAS_DEC']) * 100, 0).clip(max=100)

    if "Eficiência" in criterio_ranking:
        df_gestao = df_gestao.sort_values(by=['EFI_PROD', 'HORAS_VALIDAS'], ascending=[False, False]).head(10)
        sub_title_gestao = "Classificacao da Lideranca com base na media de Eficiencia Produtiva das suas equipes."
    elif "Volume" in criterio_ranking:
        df_gestao = df_gestao.sort_values(by=['HORAS_DEC', 'EFI_PROD'], ascending=[False, False]).head(10)
        sub_title_gestao = "Classificacao da Lideranca com base no Volume Bruto de horas apontadas pelas equipes."
    else:
        df_gestao = df_gestao.sort_values(by=['HORAS_VALIDAS', 'EFI_PROD'], ascending=[False, False]).head(10)
        sub_title_gestao = "Classificacao da Lideranca com base no Engajamento medio (Apontamento valido vs Jornada RH)."

    if not df_gestao.empty:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(22, 102, 53)
        pdf.cell(0, 8, f"Ranking da Lideranca: Desempenho por Gestor", 0, 1, 'C')

        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 4, sub_title_gestao, 0, 1, 'C')

        start_y = pdf.get_y() + 10

        cols = 2 if orientacao_pdf == 'L' else 1
        card_w_list = 120 if orientacao_pdf == 'L' else 170
        gap_x = 10 if orientacao_pdf == 'L' else 0
        total_w = (card_w_list * cols) + (gap_x * (cols - 1))
        margin_l = (297 - total_w) / 2 if orientacao_pdf == 'L' else (210 - total_w) / 2

        y_atual = start_y

        for idx, row in enumerate(df_gestao.to_dict('records'), start=1):
            col_index = (idx - 1) % cols

            if col_index == 0 and idx > 1:
                y_atual += 18

            if y_atual + 16 > max_y_page:
                pdf.add_page()
                y_atual = 20

            x_start = margin_l + col_index * (card_w_list + gap_x)

            # Fundo do Card Estilo Imagem (Branco, borda fina)
            pdf.set_fill_color(252, 253, 254)
            pdf.rect(x_start, y_atual, card_w_list, 16, 'F')
            pdf.set_draw_color(226, 232, 240)
            pdf.rect(x_start, y_atual, card_w_list, 16, 'D')

            # Faixa do Rank Esquerda
            if idx == 1:
                pdf.set_fill_color(250, 191, 36)  # Ouro
                pdf.set_text_color(255, 255, 255)
            elif idx == 2:
                pdf.set_fill_color(148, 163, 184)  # Prata
                pdf.set_text_color(255, 255, 255)
            elif idx == 3:
                pdf.set_fill_color(180, 83, 9)  # Bronze
                pdf.set_text_color(255, 255, 255)
            else:
                pdf.set_fill_color(241, 245, 249)  # Normal
                pdf.set_text_color(100, 116, 139)

            pdf.rect(x_start, y_atual, 12, 16, 'F')
            pdf.set_font('Arial', 'B', 10)
            pdf.set_xy(x_start, y_atual + 5)
            pdf.cell(12, 6, f"{idx}o", 0, 0, 'C')

            # Avatar Circular (Nome do Gestor)
            gestor_nome = str(row['GESTOR']).strip()
            circ_img = get_circular_avatar(gestor_nome, (252, 253, 254))
            img_s = 12
            img_x = x_start + 15
            img_y = y_atual + 2

            if circ_img:
                pdf.image(circ_img, x=img_x, y=img_y, w=img_s, h=img_s)
            else:
                # Fallback: Um círculo genérico com a inicial do Gestor
                pdf.set_fill_color(226, 232, 240)
                pdf.set_draw_color(200, 200, 200)
                pdf.rect(img_x, img_y, img_s, img_s, 'FD')
                pdf.set_text_color(100, 116, 139)
                pdf.set_font('Arial', 'B', 6)
                pdf.set_xy(img_x, img_y + 3)
                pdf.cell(img_s, img_s / 2, gestor_nome[0] if len(gestor_nome) > 0 else "?", 0, 0, 'C')

            # Nome e Função
            pdf.set_text_color(30, 41, 59)
            pdf.set_font('Arial', 'B', 9)
            pdf.set_xy(x_start + 30, y_atual + 3)
            nome_linha = gestor_nome.encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(45, 5, nome_linha[:22], 0, 1, 'L')

            pdf.set_font('Arial', '', 7)
            pdf.set_text_color(100, 116, 139)
            pdf.set_xy(x_start + 30, y_atual + 8)
            pdf.cell(45, 4, "Gestor de Equipe", 0, 1, 'L')

            # Métricas Lado Direito (Badges)
            w_stat = 20
            x_stat1 = x_start + card_w_list - (w_stat * 2) - 6
            x_stat2 = x_start + card_w_list - w_stat - 2

            if "Eficiência" in criterio_ranking:
                val_main = f"{row['EFI_PROD']:.0f}%"
                lbl_main = "Eficiencia"
                val_sec = f"{row['HORAS_DEC']:.0f}h"
                lbl_sec = "Horas Totais"
                is_good = row['EFI_PROD'] >= 85
            elif "Volume" in criterio_ranking:
                val_main = f"{row['HORAS_DEC']:.0f}h"
                lbl_main = "Apontadas"
                val_sec = f"{row['EFI_PROD']:.0f}%"
                lbl_sec = "Eficiencia"
                is_good = True
            else:
                val_main = f"{row['PCT_VISUAL']:.0f}%"
                lbl_main = "Apontado"
                val_sec = f"{row['HORAS_DEC']:.0f}h"
                lbl_sec = "Horas Totais"
                is_good = row['PCT_VISUAL'] >= 85

            # Badge Destaque
            if is_good:
                pdf.set_fill_color(220, 252, 231);
                pdf.set_text_color(22, 101, 52)
            else:
                pdf.set_fill_color(254, 240, 138);
                pdf.set_text_color(161, 98, 7)

            pdf.set_xy(x_stat1, y_atual + 3)
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(18, 5, val_main, 0, 0, 'C', fill=True)
            pdf.set_text_color(100, 116, 139);
            pdf.set_font('Arial', '', 5)
            pdf.set_xy(x_stat1, y_atual + 9);
            pdf.cell(18, 3, lbl_main, 0, 1, 'C')

            # Texto Secundário
            pdf.set_text_color(71, 85, 105)
            pdf.set_font('Arial', 'B', 8)
            pdf.set_xy(x_stat2, y_atual + 4)
            pdf.cell(20, 4, val_sec, 0, 0, 'C')
            pdf.set_text_color(100, 116, 139);
            pdf.set_font('Arial', '', 5)
            pdf.set_xy(x_stat2, y_atual + 9);
            pdf.cell(20, 3, lbl_sec, 0, 1, 'C')

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

        df_rank_excel = df_rank.rename(columns={
            'SETOR': 'Equipe (Setor)', 'GESTOR': 'Gestor', 'MATRICULA_FINAL': 'Matricula', 'NOME_FINAL': 'Colaborador',
            'H_REAL_LIQ': 'Jornada (h)', 'HORAS_DEC': 'Apontado (h)', 'HORAS_PROD': 'Produtivo (h)',
            'HORAS_IMPROD': 'Improdutivo (h)', 'FALTA_REFEICAO': 'Dias sem Refeicao', 'EFI': 'Eficiencia (%)'
        })

        cols_order_rank = ['Equipe (Setor)', 'Colaborador', 'Gestor', 'Matricula', 'Jornada (h)', 'Apontado (h)',
                           'Produtivo (h)', 'Improdutivo (h)', 'Eficiencia (%)', 'Dias sem Refeicao']
        df_rank_excel = df_rank_excel[cols_order_rank]

        # Excel 1: Matriz de Eficiência
        df_matriz_excel = df_view.copy()
        df_matriz_excel['MATRIZ_VAL'] = df_matriz_excel['EFICIENCIA_VISUAL']
        mask_falta_ex = (df_matriz_excel['STATUS'] == 'CRÍTICO (Sem Apontamento)')
        mask_super_ex = (df_matriz_excel['STATUS'] == 'ALERTA (Super-Apontamento)')
        df_matriz_excel.loc[mask_falta_ex, 'MATRIZ_VAL'] = -1
        df_matriz_excel.loc[mask_super_ex, 'MATRIZ_VAL'] = -2

        pivot_excel = df_matriz_excel.pivot_table(index=['SETOR', 'GESTOR', 'MATRICULA_FINAL', 'NOME_FINAL'],
                                                  columns='DT_REF',
                                                  values='MATRIZ_VAL', aggfunc='mean').reset_index()

        novas_colunas = []
        for c in pivot_excel.columns:
            if isinstance(c, datetime) or hasattr(c, 'strftime'):
                col_name = c.strftime('%d/%m')
                novas_colunas.append(col_name)
                pivot_excel[c] = pivot_excel[c].apply(lambda x: "Sem Apont." if x == -1 else (
                    ">100%" if x == -2 else ("-" if pd.isna(x) or x == 0 else round(x, 1))))
            else:
                novas_colunas.append(str(c))

        pivot_excel.columns = novas_colunas

        # Excel 2: ESPELHO DE PONTO DO RH
        pivot_excel_ponto = df_espelho.pivot_table(index=['SETOR', 'GESTOR', 'MATRICULA_FINAL', 'NOME_FINAL'],
                                                   columns='DT_REF',
                                                   values='REAL_H', aggfunc='first').reset_index()
        novas_colunas_pt = []
        for c in pivot_excel_ponto.columns:
            if isinstance(c, datetime) or hasattr(c, 'strftime'):
                novas_colunas_pt.append(c.strftime('%d/%m'))
            else:
                novas_colunas_pt.append(str(c))

        pivot_excel_ponto.columns = novas_colunas_pt
        pivot_excel_ponto.fillna('-', inplace=True)

        # Salva as Abas
        df_export.to_excel(writer, sheet_name="Base Detalhada", index=False)
        df_setor.to_excel(writer, sheet_name="Ranking Setores", index=False)
        df_rank_excel.to_excel(writer, sheet_name="Ranking Colaboradores", index=False)
        pivot_excel.to_excel(writer, sheet_name="Matriz Diaria", index=False)
        pivot_excel_ponto.to_excel(writer, sheet_name="Espelho de Ponto", index=False)

        if not improd_filtered.empty:
            improd_agrupado.to_excel(writer, sheet_name="Raio-X Improdutividade", index=False)

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
        pims['OPERACAO_NOME'] = pims['OPERACAO'].astype(str).str.title().str.strip()

        pims['IS_REFEICAO'] = pims['OPERACAO_CLEAN'].str.contains('REFEI', na=False)
        pims['HORAS_PROD'] = np.where(pims['TIPO_OPER_CLEAN'] == 'PRODUTIVO', pims['HORAS_DEC'], 0)
        pims['HORAS_IMPROD'] = np.where(pims['TIPO_OPER_CLEAN'] == 'IMPRODUTIVO', pims['HORAS_DEC'], 0)

        pims_agg = pims.groupby(['MATRICULA', 'DT_REF']).agg({
            'COLABORADOR': 'first', 'HORAS_DEC': 'sum', 'HORAS_PROD': 'sum', 'HORAS_IMPROD': 'sum', 'IS_REFEICAO': 'max'
        }).reset_index()

        pims_agg['MATRICULA'] = pims_agg['MATRICULA'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        pims_agg['APONTOU_REFEICAO'] = np.where(pims_agg['IS_REFEICAO'] > 0, 'Sim', 'Não')

        # RAIO-X IMPRODUTIVO: Agrupa horas improdutivas detalhadas
        pims_improd = pims[pims['TIPO_OPER_CLEAN'] == 'IMPRODUTIVO'].groupby(['MATRICULA', 'DT_REF', 'OPERACAO_NOME'])[
            'HORAS_DEC'].sum().reset_index()
        pims_improd['MATRICULA'] = pims_improd['MATRICULA'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if file_rh.name.lower().endswith('.csv'):
            try:
                rh = pd.read_csv(file_rh, header=None, sep=None, engine='python', encoding='utf-8')
            except:
                file_rh.seek(0)
                rh = pd.read_csv(file_rh, header=None, sep=None, engine='python', encoding='latin-1')
        else:
            rh = pd.read_excel(file_rh, header=None)

        rh['SETOR'] = np.where(
            rh[1].isna() & rh[0].notna() & (
                ~rh[0].astype(str).str.contains('FUNCIONÁRIO|Horário|nan', case=False, na=False)),
            rh[0].astype(str).str.strip(), np.nan
        )
        rh['SETOR'] = rh['SETOR'].ffill()

        rh = rh[pd.to_numeric(rh[1], errors='coerce').notna()].copy()
        rh = rh.rename(columns={
            0: 'PREFIX', 1: 'MAT_ID', 2: 'NOME', 3: 'TURMA', 4: 'DATA', 5: 'ESC_H', 6: 'ESC_I', 8: 'REAL_H', 9: 'REAL_I'
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
            'NOME': 'first', 'TURMA': 'first', 'SETOR': 'first', 'ESC_H': 'first', 'REAL_H': 'first',
            'H_REAL_LIQ': 'sum'
        }).reset_index()

        # Limpeza e Abreviação dos Nomes de Setor
        rh_agg['SETOR'] = rh_agg['SETOR'].str.replace(r'^\d+\s*-\s*', '', regex=True)
        rh_agg['SETOR'] = rh_agg['SETOR'].str.replace(r'(?i)^SETOR\s+(DE\s+)?', '', regex=True)
        rh_agg['SETOR'] = rh_agg['SETOR'].str.replace(r'(?i)^MANUTEN[CÇ][AÃ]O\s+', '', regex=True)
        rh_agg['SETOR'] = rh_agg['SETOR'].str.strip().str.upper()

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

        df_final['FALTA_REFEICAO'] = np.where((df_final['H_REAL_LIQ'] > 4.0) & (df_final['APONTOU_REFEICAO'] == 'Não'),
                                              1, 0)

        # NOVA AUDITORIA: ALERTA DE SUPER-APONTAMENTO (Tolerância de 0.5h/30 min)
        conditions = [
            (df_final['H_REAL_LIQ'] > 0.1) & (df_final['HORAS_DEC'] > (df_final['H_REAL_LIQ'] + 0.5)),
            (df_final['H_REAL_LIQ'] > 0.1) & (df_final['HORAS_DEC'] < 0.1),
            (df_final['H_REAL_LIQ'] < 0.1) & (df_final['HORAS_DEC'] > 0.1),
            (df_final['H_REAL_LIQ'] > 4.0) & (df_final['APONTOU_REFEICAO'] == 'Não'),
            (df_final['H_REAL_LIQ'] > 0.1) | (df_final['HORAS_DEC'] > 0.1)
        ]
        choices = [
            'ALERTA (Super-Apontamento)',
            'CRÍTICO (Sem Apontamento)',
            'ALERTA (Ponto Não Batido)',
            'ALERTA (Sem Refeição)',
            'OK'
        ]
        df_final['STATUS'] = np.select(conditions, choices, default='-')

        df_final['EFICIENCIA_GERAL'] = np.where(df_final['H_REAL_LIQ'] > 0,
                                                (df_final['HORAS_DEC'] / df_final['H_REAL_LIQ']) * 100, 0)
        df_final['EFICIENCIA_GERAL'] = df_final['EFICIENCIA_GERAL'].clip(upper=100)  # Trava 100%
        df_final['EFICIENCIA_VISUAL'] = df_final['EFICIENCIA_GERAL']

        return df_final, pims_improd

    except Exception as e:
        st.error(f"Erro fatal ao processar: {e}")
        return None


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
        res = processar_dados_corporativos(f_pims, f_rh)
        if res is not None:
            df_proc, df_improd = res
            df_sincronizado = aplicar_sincronizacao_banco(df_proc)
            st.session_state['dataset_rh'] = df_sincronizado
            st.session_state['dataset_improd'] = df_improd
            st.rerun()

if st.session_state['dataset_rh'] is None:
    ui_empty_state("Aguardando importação para iniciar a auditoria.", icon="📊")
    st.stop()

df = st.session_state['dataset_rh']

st.markdown("---")
with st.expander("⚙️ Estrutura de Liderança (Banco de Dados)", expanded=False):
    tab_map_manual, tab_map_lote = st.tabs(["✍️ Edição Manual", "📂 Importação em Lote"])
    with tab_map_manual:
        conn_map = get_db_connection()
        df_mapa_bd = pd.read_sql("SELECT matricula, nome, setor, gestor FROM mapa_gestores ORDER BY nome", conn_map)
        edited_map = st.data_editor(
            df_mapa_bd, use_container_width=True, hide_index=True,
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

            time.sleep(1);
            st.rerun()
        else:
            conn_map.close()
    with tab_map_lote:
        st.markdown("1. **Baixe a planilha atual** com todos os funcionários cadastrados no banco.")


        def gerar_excel_mapeamento():
            conn_xl = get_db_connection()
            df_xl = pd.read_sql("SELECT matricula, nome, setor, gestor FROM mapa_gestores ORDER BY nome", conn_xl)
            conn_xl.close();
            output = io.BytesIO()
            with pd.ExcelWriter(output) as writer: df_xl.to_excel(writer, index=False,
                                                                  sheet_name="Mapeamento_Lideranca")
            output.seek(0)
            return output


        st.download_button("📥 Baixar Planilha de Mapeamento", data=gerar_excel_mapeamento(),
                           file_name="mapeamento_gestores.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
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
                        conn_imp = get_db_connection();
                        cursor_imp = conn_imp.cursor()
                        atualizados = 0
                        for _, row in df_up_mapa.iterrows():
                            mat_val = str(row['matricula']).strip();
                            gestor_val = str(row['gestor']).strip()
                            if pd.notna(gestor_val) and gestor_val.lower() != 'nan' and gestor_val != '':
                                cursor_imp.execute("UPDATE mapa_gestores SET gestor = ? WHERE matricula = ?",
                                                   (gestor_val, mat_val))
                                atualizados += 1
                        conn_imp.commit();
                        conn_imp.close()
                        st.toast(f"Importação concluída! {atualizados} registros atualizados.", icon="✅")
                        st.session_state['dataset_rh'] = aplicar_sincronizacao_banco(st.session_state['dataset_rh'])
                        import time;

                        time.sleep(1);
                        st.rerun()
                else:
                    st.error("A planilha deve conter obrigatoriamente as colunas 'matricula' e 'gestor'.")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")

with st.sidebar:
    st.header("🔍 Filtros de Auditoria")
    min_d, max_d = df['DT_REF'].min(), df['DT_REF'].max()
    datas = st.date_input("Período de Análise", [min_d, max_d])

    lista_gestores = sorted(df['GESTOR'].unique().tolist())
    sel_gestores = st.multiselect("Liderança (Gestor)", options=lista_gestores, default=lista_gestores,
                                  help="Remova no 'X' as lideranças que não deseja ver")
    df_temp_g = df.iloc[0:0] if not sel_gestores else df[df['GESTOR'].isin(sel_gestores)]

    lista_setores = sorted(df_temp_g['SETOR'].unique().tolist())
    sel_setores = st.multiselect("Equipe / Setor", options=lista_setores, default=lista_setores,
                                 help="Remova no 'X' as equipes que não deseja ver")
    df_temp_s = df_temp_g.iloc[0:0] if not sel_setores else df_temp_g[df_temp_g['SETOR'].isin(sel_setores)]

    lista_turmas = sorted(df_temp_s['TURMA'].dropna().astype(str).unique().tolist())
    sel_turmas = st.multiselect("Turma de Turno", options=lista_turmas, default=[],
                                help="Deixe vazio para selecionar todas")
    df_temp_t = df_temp_s[df_temp_s['TURMA'].astype(str).isin(sel_turmas)] if sel_turmas else df_temp_s

    lista_nomes = sorted(df_temp_t['NOME_FINAL'].unique().tolist())
    sel_nomes = st.multiselect("Colaborador", options=lista_nomes, default=[], help="Deixe vazio para selecionar todos")

    st.markdown("---")
    st.markdown("### ⚡ Filtros Rápidos de Auditoria")
    filtro_rapido = st.radio("Isolar anomalias:",
                             ["👁️ Mostrar Todos", "🚨 Sem Apontamento", "🟠 Falta de Refeição", "🟣 Super-Apontamento",
                              "⚠️ Ponto Não Batido"],
                             horizontal=True,
                             label_visibility="collapsed"
                             )

    st.markdown("---")
    st.markdown("### 🏆 Configuração do Ranking")
    criterio_ranking = st.radio(
        "Ordenar e Destacar por:",
        ["Engajamento (Horas Válidas)", "Eficiência Produtiva (%)", "Volume Bruto (Total)"],
        index=0,
        help="Altera a ordem dos colaboradores no Pódio e na Lista, tanto na visualização da tela quanto no PDF. Inverte a métrica em destaque."
    )

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

# --- CAPTURA DA BASE DO ESPELHO DE PONTO (SEM FILTROS EXCETO DATA) ---
df_espelho = df_view.copy()

# --- APLICAÇÃO DOS DEMAIS FILTROS APENAS PARA O RELATÓRIO GERAL ---
df_view = df_view[df_view['GESTOR'].isin(sel_gestores)]
df_view = df_view[df_view['SETOR'].isin(sel_setores)]
if sel_turmas: df_view = df_view[df_view['TURMA'].astype(str).isin(sel_turmas)]
if sel_nomes: df_view = df_view[df_view['NOME_FINAL'].isin(sel_nomes)]

if "Sem Apontamento" in filtro_rapido:
    df_view = df_view[df_view['STATUS'] == 'CRÍTICO (Sem Apontamento)']
elif "Falta de Refeição" in filtro_rapido:
    df_view = df_view[df_view['STATUS'] == 'ALERTA (Sem Refeição)']
elif "Super-Apontamento" in filtro_rapido:
    df_view = df_view[df_view['STATUS'] == 'ALERTA (Super-Apontamento)']
elif "Ponto Não Batido" in filtro_rapido:
    df_view = df_view[df_view['STATUS'] == 'ALERTA (Ponto Não Batido)']

# ==============================================================================
# 3. DASHBOARD GERENCIAL UI
# ==============================================================================
total_dias_periodo = (d_out - d_in).days + 1
dias_trabalhados = df_view['DT_REF'].nunique()

efi_media = df_view[df_view['H_REAL_LIQ'] > 0]['EFICIENCIA_GERAL'].mean() if not df_view[
    df_view['H_REAL_LIQ'] > 0].empty else 0
h_rh = df_view['H_REAL_LIQ'].sum()
h_produtivas = df_view['HORAS_PROD'].sum()
h_improdutivas = df_view['HORAS_IMPROD'].sum()
h_total_pims = df_view['HORAS_DEC'].sum()

taxa_produtividade = (h_produtivas / h_total_pims * 100) if h_total_pims > 0 else 0
taxa_produtividade = min(taxa_produtividade, 100)

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

# ABAS DE ANÁLISE
tab_setor, tab_top10, tab_gestao, tab_rank, tab_ofensores, tab_improd, tab_matriz, tab_dados = st.tabs([
    "🏆 Ranking de Setores",
    "⭐ Top 10 Destaques",
    "👔 Ranking da Gestão",
    "🏅 Desempenho (Geral)",
    "🚨 Atenção RH (Ofensores)",
    "📉 Raio-X Improdutivo",
    "📅 Matriz de Apontamento",
    "📋 Tabela Analítica"
])

with tab_setor:
    st.markdown("##### 🏆 Desempenho de Equipes (Por Setor)")
    if not df_view.empty:
        df_g = df_view.groupby(['SETOR']).agg(
            {'H_REAL_LIQ': 'sum', 'HORAS_DEC': 'sum', 'HORAS_PROD': 'sum'}).reset_index()
        df_g['EFICIENCIA_GERAL'] = np.where(df_g['H_REAL_LIQ'] > 0, (df_g['HORAS_DEC'] / df_g['H_REAL_LIQ']) * 100,
                                            0).clip(max=100)
        df_g['PROD_PCT'] = np.where(df_g['HORAS_DEC'] > 0, (df_g['HORAS_PROD'] / df_g['HORAS_DEC']) * 100, 0).clip(
            max=100)
        df_g = df_g.sort_values('EFICIENCIA_GERAL', ascending=False)

        c_chart, c_table = st.columns([1, 1.2])
        with c_chart:
            df_plot = df_g.sort_values('EFICIENCIA_GERAL', ascending=True)
            altura_g = max(400, len(df_plot) * 35)
            fig_g = px.bar(df_plot, x='EFICIENCIA_GERAL', y='SETOR', orientation='h', color='EFICIENCIA_GERAL',
                           color_continuous_scale='RdYlGn', text_auto='.1f', title="Eficiência % (Todas as Equipes)")
            fig_g.update_layout(yaxis_title="", margin=dict(l=10, r=10, t=40, b=10), height=altura_g)
            st.plotly_chart(fig_g, use_container_width=True)
        with c_table:
            st.dataframe(df_g, use_container_width=True, hide_index=True,
                         column_config={"SETOR": st.column_config.TextColumn("Equipe / Setor", width="large"),
                                        "EFICIENCIA_GERAL": st.column_config.ProgressColumn("Eficiência",
                                                                                            format="%.1f%%",
                                                                                            min_value=0, max_value=100),
                                        "PROD_PCT": st.column_config.NumberColumn("% Produtivas", format="%.1f%%")})

with tab_top10:
    st.markdown(f"##### ⭐ Top 10: Melhores Apontamentos")

    df_top10_ui = df_view.groupby(['MATRICULA_FINAL', 'NOME_FINAL', 'SETOR']).agg({
        'HORAS_PROD': 'sum', 'HORAS_IMPROD': 'sum', 'HORAS_DEC': 'sum', 'H_REAL_LIQ': 'sum'
    }).reset_index()

    df_top10_ui = df_top10_ui[df_top10_ui['H_REAL_LIQ'] > 0]
    df_top10_ui['HORAS_VALIDAS'] = df_top10_ui[['HORAS_DEC', 'H_REAL_LIQ']].min(axis=1)
    df_top10_ui['PCT_VISUAL'] = np.where(df_top10_ui['H_REAL_LIQ'] > 0,
                                         (df_top10_ui['HORAS_DEC'] / df_top10_ui['H_REAL_LIQ']) * 100, 0).clip(max=100)
    df_top10_ui['EFI_PROD'] = np.where(df_top10_ui['HORAS_DEC'] > 0,
                                       (df_top10_ui['HORAS_PROD'] / df_top10_ui['HORAS_DEC']) * 100, 0).clip(max=100)

    if "Eficiência" in criterio_ranking:
        df_top10_ui = df_top10_ui.sort_values(by=['EFI_PROD', 'HORAS_VALIDAS'], ascending=[False, False]).head(10)
        st.caption("Ranking focado na **Eficiência Produtiva**. Recompensa quem converteu o tempo em máquina operando.")
    elif "Volume" in criterio_ranking:
        df_top10_ui = df_top10_ui.sort_values(by=['HORAS_DEC', 'EFI_PROD'], ascending=[False, False]).head(10)
        st.caption("Ranking focado no **Volume Bruto Apontado** (Produtivas + Improdutivas).")
    else:
        df_top10_ui = df_top10_ui.sort_values(by=['HORAS_VALIDAS', 'EFI_PROD'], ascending=[False, False]).head(10)
        st.caption("Ranking focado no **Volume Válido** de horas (evita fraudes de super-apontamento).")

    if not df_top10_ui.empty:
        top_list = df_top10_ui.to_dict('records')
        while len(top_list) < 3:
            top_list.append(None)


        def render_podium_col(row, rank, height_px, color_hex, color_bg, medal_emoji, img_size):
            if not row: return "<div style='width: 30%;'></div>"
            b64 = get_foto_base64(row['MATRICULA_FINAL'])
            nome = str(row['NOME_FINAL'])[:20]

            if "Eficiência" in criterio_ranking:
                val_badge = f"{row['EFI_PROD']:.1f}% Efic."
                val_sec = f"{row['PCT_VISUAL']:.0f}% Apontado"
                prog_val = row['EFI_PROD']
            elif "Volume" in criterio_ranking:
                val_badge = f"{row['HORAS_DEC']:.1f}h Apontadas"
                val_sec = f"Efic: {row['EFI_PROD']:.1f}%"
                prog_val = 100
            else:
                val_badge = f"{row['PCT_VISUAL']:.0f}% Apontado"
                val_sec = f"Efic: {row['EFI_PROD']:.1f}%"
                prog_val = row['PCT_VISUAL']

            bg_efic = "#FEF08A" if prog_val < 85 else "#BBF7D0"
            cor_efic = "#A16207" if prog_val < 85 else "#166534"

            html_ret = f"<div style='display: flex; flex-direction: column; align-items: center; width: 30%; position: relative;'><div style='position: relative; z-index: 2; margin-bottom: -15px;'><img src='{b64}' style='width: {img_size}px; height: {img_size}px; border-radius: 50%; object-fit: cover; border: 4px solid {color_hex}; background-color: #fff;'/><div style='position: absolute; bottom: -5px; right: -5px; font-size: 24px; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.2));'>{medal_emoji}</div></div><div style='background-color: {color_bg}; border-top: 6px solid {color_hex}; width: 100%; text-align: center; padding: 25px 5px 10px 5px; border-radius: 12px 12px 0 0; box-shadow: 0 4px 10px rgba(0,0,0,0.1); height: {height_px}px; line-height: 1.2;'><h1 style='margin:0; color: {color_hex}; font-size: 32px;'>{rank}º</h1><div style='font-weight: 800; font-size: 14px; margin-top: 6px; color: #1E293B;'>{nome}</div><div style='background-color: {bg_efic}; color: {cor_efic}; font-weight: bold; padding: 4px 10px; border-radius: 6px; font-size: 14px; margin: 8px auto 4px auto; width: fit-content;'>{val_badge}</div><div style='font-size: 11px; color: #64748B; font-weight: 600;'>{val_sec}</div></div></div>"
            return html_ret


        html_podium = f"<div style='display: flex; justify-content: center; align-items: flex-end; gap: 15px; margin: 40px 0 20px 0;'>{render_podium_col(top_list[1], 2, 120, '#94A3B8', '#F8FAFC', '🥈', 80)}{render_podium_col(top_list[0], 1, 150, '#FABF24', '#FEFCE8', '🥇', 100)}{render_podium_col(top_list[2], 3, 100, '#B45309', '#FFF7ED', '🥉', 80)}</div>"
        st.markdown(html_podium, unsafe_allow_html=True)

        if len(top_list) > 3:
            st.markdown("---")
            max_horas_dec = df_top10_ui['HORAS_DEC'].max() if not df_top10_ui.empty else 1

            html_list = "<div style='display: flex; flex-wrap: wrap; gap: 15px; max-width: 900px; margin: 0 auto; padding-bottom: 20px;'>"
            for idx, row in enumerate(top_list[3:], start=4):
                if not row: continue
                b64 = get_foto_base64(row['MATRICULA_FINAL'])

                if "Eficiência" in criterio_ranking:
                    val_main_list = f"{row['EFI_PROD']:.0f}%"
                    lbl_main_list = "Efic."
                    val_sec_list = f"{row['PCT_VISUAL']:.0f}%"
                    lbl_sec_list = "Apontado"
                    prog_val = row['EFI_PROD']
                elif "Volume" in criterio_ranking:
                    val_main_list = f"{row['HORAS_DEC']:.1f}h"
                    lbl_main_list = "Apontadas"
                    val_sec_list = f"{row['EFI_PROD']:.1f}%"
                    lbl_sec_list = "Efic."
                    prog_val = min((row['HORAS_DEC'] / max_horas_dec) * 100, 100) if max_horas_dec > 0 else 0
                else:
                    val_main_list = f"{row['PCT_VISUAL']:.0f}%"
                    lbl_main_list = "Apontado"
                    val_sec_list = f"{row['EFI_PROD']:.1f}%"
                    lbl_sec_list = "Efic."
                    prog_val = row['PCT_VISUAL']

                bg_efic = "#FEF08A" if prog_val < 85 else "#BBF7D0"
                cor_efic = "#A16207" if prog_val < 85 else "#166534"

                html_list += f"<div style='flex: 1 1 45%; display: flex; align-items: center; justify-content: space-between; background: white; padding: 10px 15px; border-radius: 8px; border: 1px solid #E2E8F0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'><div style='display: flex; align-items: center; gap: 12px;'><div style='font-size: 16px; font-weight: bold; color: #94A3B8; width: 25px;'>{idx}º</div><img src='{b64}' style='width: 40px; height: 40px; border-radius: 50%; object-fit: cover; background-color: #f1f5f9; border: 1px solid #E2E8F0;'/><div style='line-height: 1.2;'><div style='font-weight: bold; color: #1E293B; font-size: 13px;'>{row['NOME_FINAL']}</div><div style='font-size: 11px; color: #64748B;'>{row['SETOR']}</div></div></div><div style='display: flex; gap: 15px; align-items: center; text-align: center; line-height: 1.2;'><div style='display: flex; flex-direction: column; align-items: center; width: 60px;'><div style='background-color: {bg_efic}; color: {cor_efic}; font-weight: bold; padding: 4px 0px; border-radius: 4px; font-size: 14px; width: 100%;'>{val_main_list}</div><div style='background: #e2e8f0; width: 100%; height: 4px; margin-top: 5px; border-radius: 2px; overflow: hidden;'><div style='background: {cor_efic}; width: {prog_val}%; height: 100%; border-radius: 2px;'></div></div><div style='font-size: 9px; color: #64748B; margin-top: 3px;'>{lbl_main_list}</div></div><div style='display: flex; flex-direction: column; align-items: center;'><div style='font-weight: bold; color: #475569; font-size: 12px;'>{val_sec_list}</div><div style='font-size: 9px; color: #64748B; margin-top: 2px;'>{lbl_sec_list}</div></div></div></div>"
            html_list += "</div>"
            st.markdown(html_list, unsafe_allow_html=True)
    else:
        st.info("Não há apontamentos suficientes para gerar o pódio.")

with tab_gestao:
    st.markdown("##### 👔 Ranking da Liderança (Desempenho por Gestor)")
    st.caption(
        "Agrupa todas as horas das equipes sob responsabilidade de cada gestor e cria um ranking geral da liderança.")

    df_gestao_ui = df_view.groupby('GESTOR').agg({
        'HORAS_PROD': 'sum', 'HORAS_IMPROD': 'sum', 'HORAS_DEC': 'sum', 'H_REAL_LIQ': 'sum'
    }).reset_index()

    # Remove gestores sem horas ou não definidos
    df_gestao_ui = df_gestao_ui[(df_gestao_ui['H_REAL_LIQ'] > 0) & (df_gestao_ui['GESTOR'] != 'Não Definido')]
    df_gestao_ui['HORAS_VALIDAS'] = df_gestao_ui[['HORAS_DEC', 'H_REAL_LIQ']].min(axis=1)
    df_gestao_ui['PCT_VISUAL'] = np.where(df_gestao_ui['H_REAL_LIQ'] > 0,
                                          (df_gestao_ui['HORAS_DEC'] / df_gestao_ui['H_REAL_LIQ']) * 100, 0).clip(
        max=100)
    df_gestao_ui['EFI_PROD'] = np.where(df_gestao_ui['HORAS_DEC'] > 0,
                                        (df_gestao_ui['HORAS_PROD'] / df_gestao_ui['HORAS_DEC']) * 100, 0).clip(max=100)

    if "Eficiência" in criterio_ranking:
        df_gestao_ui = df_gestao_ui.sort_values(by=['EFI_PROD', 'HORAS_VALIDAS'], ascending=[False, False])
    elif "Volume" in criterio_ranking:
        df_gestao_ui = df_gestao_ui.sort_values(by=['HORAS_DEC', 'EFI_PROD'], ascending=[False, False])
    else:
        df_gestao_ui = df_gestao_ui.sort_values(by=['HORAS_VALIDAS', 'EFI_PROD'], ascending=[False, False])

    if not df_gestao_ui.empty:
        max_horas_gestao = df_gestao_ui['HORAS_DEC'].max() if not df_gestao_ui.empty else 1

        html_gestao = "<div style='display: flex; flex-direction: column; gap: 15px; max-width: 700px; margin: 20px auto;'>"
        for idx, row in enumerate(df_gestao_ui.to_dict('records'), start=1):
            gestor_nome = str(row['GESTOR']).strip()
            b64_g = get_foto_base64(gestor_nome)

            # Cores de Posição
            if idx == 1:
                color_bg, color_border, medal_text = '#FEFCE8', '#FABF24', '🥇 1º Lugar'
            elif idx == 2:
                color_bg, color_border, medal_text = '#F8FAFC', '#94A3B8', '🥈 2º Lugar'
            elif idx == 3:
                color_bg, color_border, medal_text = '#FFF7ED', '#B45309', '🥉 3º Lugar'
            else:
                color_bg, color_border, medal_text = 'white', '#E2E8F0', f'{idx}º Lugar'

            if "Eficiência" in criterio_ranking:
                val_main = f"{row['EFI_PROD']:.0f}%"
                lbl_main = "Efic. da Equipe"
                val_sec = f"{row['HORAS_DEC']:.0f}h"
                lbl_sec = "Total Apontado"
                prog_val = row['EFI_PROD']
            elif "Volume" in criterio_ranking:
                val_main = f"{row['HORAS_DEC']:.0f}h"
                lbl_main = "Total Apontado"
                val_sec = f"{row['EFI_PROD']:.0f}%"
                lbl_sec = "Efic. da Equipe"
                prog_val = min((row['HORAS_DEC'] / max_horas_gestao) * 100, 100) if max_horas_gestao > 0 else 0
            else:
                val_main = f"{row['PCT_VISUAL']:.0f}%"
                lbl_main = "Engajamento"
                val_sec = f"{row['HORAS_DEC']:.0f}h"
                lbl_sec = "Total Apontado"
                prog_val = row['PCT_VISUAL']

            bg_efic = "#FEF08A" if prog_val < 85 else "#BBF7D0"
            cor_efic = "#A16207" if prog_val < 85 else "#166534"

            html_gestao += f"<div style='display: flex; align-items: center; justify-content: space-between; background: {color_bg}; padding: 15px 20px; border-radius: 12px; border: 2px solid {color_border}; box-shadow: 0 4px 6px rgba(0,0,0,0.05);'><div style='display: flex; align-items: center; gap: 15px;'><div style='font-size: 16px; font-weight: bold; color: {color_border}; width: 85px;'>{medal_text}</div><img src='{b64_g}' style='width: 50px; height: 50px; border-radius: 50%; object-fit: cover; background-color: #f1f5f9; border: 2px solid {color_border};'/><div style='line-height: 1.3;'><div style='font-weight: 800; color: #1E293B; font-size: 15px;'>{gestor_nome}</div><div style='font-size: 12px; color: #64748B;'>Líder de Equipe</div></div></div><div style='display: flex; gap: 20px; align-items: center; text-align: center; line-height: 1.2;'><div style='display: flex; flex-direction: column; align-items: center; width: 80px;'><div style='background-color: {bg_efic}; color: {cor_efic}; font-weight: bold; padding: 6px 0px; border-radius: 6px; font-size: 16px; width: 100%;'>{val_main}</div><div style='background: #e2e8f0; width: 100%; height: 5px; margin-top: 6px; border-radius: 3px; overflow: hidden;'><div style='background: {cor_efic}; width: {prog_val}%; height: 100%; border-radius: 3px;'></div></div><div style='font-size: 10px; color: #64748B; margin-top: 4px; font-weight: 600;'>{lbl_main}</div></div><div style='display: flex; flex-direction: column; align-items: center;'><div style='font-weight: bold; color: #475569; font-size: 14px;'>{val_sec}</div><div style='font-size: 10px; color: #64748B; margin-top: 4px;'>{lbl_sec}</div></div></div></div>"
        html_gestao += "</div>"
        st.markdown(html_gestao, unsafe_allow_html=True)
    else:
        st.info("Não há dados de gestores suficientes para este período.")

with tab_rank:
    st.markdown("##### 🏅 Desempenho Geral por Colaborador")
    df_rank = df_view.groupby(['SETOR', 'GESTOR', 'MATRICULA_FINAL', 'NOME_FINAL']).agg(
        {'HORAS_PROD': 'sum', 'HORAS_IMPROD': 'sum', 'HORAS_DEC': 'sum', 'H_REAL_LIQ': 'sum'}).reset_index()

    df_rank['PCT_APONTADO'] = np.where(df_rank['H_REAL_LIQ'] > 0, (df_rank['HORAS_DEC'] / df_rank['H_REAL_LIQ']) * 100,
                                       0).clip(max=100)
    df_rank['EFI_PROD'] = np.where(df_rank['HORAS_DEC'] > 0, (df_rank['HORAS_PROD'] / df_rank['HORAS_DEC']) * 100,
                                   0).clip(max=100)

    df_rank = df_rank.sort_values(['SETOR', 'GESTOR', 'HORAS_DEC'], ascending=[True, True, True])

    if not df_rank.empty:
        altura_dinamica_grafico = max(500, len(df_rank) * 28)
        fig_rank = go.Figure()
        fig_rank.add_trace(
            go.Bar(y=df_rank['NOME_FINAL'] + ' (' + df_rank['SETOR'].str.slice(0, 10) + ')', x=df_rank['HORAS_PROD'],
                   name='Produtivo', orientation='h', marker=dict(color='#22C55E')))
        fig_rank.add_trace(
            go.Bar(y=df_rank['NOME_FINAL'] + ' (' + df_rank['SETOR'].str.slice(0, 10) + ')', x=df_rank['HORAS_IMPROD'],
                   name='Improdutivo', orientation='h', marker=dict(color='#F59E0B')))
        fig_rank.update_layout(barmode='stack', height=altura_dinamica_grafico, margin=dict(l=10, r=10, t=30, b=10),
                               legend=dict(orientation="h", yanchor="bottom", y=-0.05, xanchor="center", x=0.5))
        st.plotly_chart(fig_rank, use_container_width=True)

        st.markdown("###### 📋 Tabela Detalhada de Desempenho")

        df_rank_table = df_rank.copy()
        df_rank_table['FOTO'] = df_rank_table['MATRICULA_FINAL'].apply(get_foto_base64)

        # Inteligência de Média do Setor
        media_equipe = df_rank_table.groupby('SETOR')['PCT_APONTADO'].transform('mean')
        condicoes = [
            df_rank_table['PCT_APONTADO'] >= media_equipe + 5,
            df_rank_table['PCT_APONTADO'] <= media_equipe - 5
        ]
        df_rank_table['TENDENCIA'] = np.select(condicoes, ['🟢 ↑ Acima', '🔴 ↓ Abaixo'], default='🟡 ↔ Média')

        st.dataframe(
            df_rank_table[
                ['FOTO', 'NOME_FINAL', 'SETOR', 'GESTOR', 'HORAS_PROD', 'HORAS_DEC', 'PCT_APONTADO', 'TENDENCIA']],
            column_config={
                "FOTO": st.column_config.ImageColumn("Foto", width="small"),
                "NOME_FINAL": "Colaborador",
                "SETOR": "Setor",
                "GESTOR": "Gestor",
                "HORAS_PROD": st.column_config.NumberColumn("Produtivo", format="%.1f h"),
                "HORAS_DEC": st.column_config.NumberColumn("Total PIMS", format="%.1f h"),
                "PCT_APONTADO": st.column_config.ProgressColumn("% Apontado", format="%.1f%%", min_value=0,
                                                                max_value=100),
                "TENDENCIA": "vs Média Equipe"
            },
            hide_index=True,
            use_container_width=True
        )

with tab_ofensores:
    st.markdown("##### 🚨 Top Ofensores (Baixo Engajamento)")
    st.caption(
        "Colaboradores com menos de 75% da jornada apontada no PIMS. Requer atenção imediata do RH/Gestor para correção.")

    df_ofensores = df_view.groupby(['MATRICULA_FINAL', 'NOME_FINAL', 'SETOR', 'GESTOR']).agg({
        'HORAS_DEC': 'sum', 'H_REAL_LIQ': 'sum'
    }).reset_index()

    df_ofensores['PCT_APONTADO'] = np.where(df_ofensores['H_REAL_LIQ'] > 0,
                                            (df_ofensores['HORAS_DEC'] / df_ofensores['H_REAL_LIQ']) * 100, 0).clip(
        max=100)
    df_ofensores = df_ofensores[(df_ofensores['PCT_APONTADO'] < 75) & (df_ofensores['H_REAL_LIQ'] > 0)]
    df_ofensores = df_ofensores.sort_values('PCT_APONTADO', ascending=True)

    if not df_ofensores.empty:
        df_ofensores['FOTO'] = df_ofensores['MATRICULA_FINAL'].apply(get_foto_base64)
        df_ofensores['PERDA_HORAS'] = df_ofensores['H_REAL_LIQ'] - df_ofensores['HORAS_DEC']

        st.dataframe(
            df_ofensores[
                ['FOTO', 'NOME_FINAL', 'SETOR', 'GESTOR', 'H_REAL_LIQ', 'HORAS_DEC', 'PERDA_HORAS', 'PCT_APONTADO']],
            column_config={
                "FOTO": st.column_config.ImageColumn("Foto", width="small"),
                "NOME_FINAL": "Colaborador",
                "SETOR": "Setor",
                "GESTOR": "Gestor",
                "H_REAL_LIQ": st.column_config.NumberColumn("Jornada RH", format="%.1f h"),
                "HORAS_DEC": st.column_config.NumberColumn("Apontado PIMS", format="%.1f h"),
                "PERDA_HORAS": st.column_config.NumberColumn("Horas Sem Apontamento", format="%.1f h"),
                "PCT_APONTADO": st.column_config.ProgressColumn("% Engajamento", format="%.1f%%", min_value=0,
                                                                max_value=100)
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.success("Excelente! Nenhum colaborador com engajamento crítico (< 75%) neste período.")

with tab_improd:
    st.markdown("##### 📉 Raio-X da Improdutividade")
    st.caption("Detalhamento de onde o tempo improdutivo foi gasto baseado nos filtros ativos no momento.")

    df_improd_global = st.session_state.get('dataset_improd', pd.DataFrame())
    if not df_improd_global.empty and not df_view.empty:
        valid_keys = df_view[['MATRICULA_FINAL', 'DT_REF']].drop_duplicates()
        valid_keys.columns = ['MATRICULA', 'DT_REF']
        improd_filtered = pd.merge(df_improd_global, valid_keys, on=['MATRICULA', 'DT_REF'], how='inner')

        if not improd_filtered.empty:
            improd_agrupado = improd_filtered.groupby('OPERACAO_NOME')['HORAS_DEC'].sum().reset_index().sort_values(
                'HORAS_DEC', ascending=False)

            c_chart, c_table = st.columns([1.5, 1])
            with c_chart:
                fig_pie = px.pie(improd_agrupado, values='HORAS_DEC', names='OPERACAO_NOME', hole=0.4,
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(margin=dict(t=20, b=20, l=10, r=10))
                st.plotly_chart(fig_pie, use_container_width=True)
            with c_table:
                st.dataframe(improd_agrupado, column_config={"OPERACAO_NOME": "Motivo (Operação PIMS)",
                                                             "HORAS_DEC": st.column_config.NumberColumn(
                                                                 "Total de Horas", format="%.1f h")}, hide_index=True,
                             use_container_width=True)
        else:
            st.info("Nenhuma hora improdutiva registrada para as pessoas filtradas neste período.")
    else:
        st.info("Sem dados de improdutividade na base atual.")

with tab_matriz:
    st.markdown("##### 🗓️ Matriz de Eficiência por Dia do Mês (%)")
    st.caption(
        "Verde: >=85% | Amarelo: 70 a 84% | Vermelho: <70% | 🟠 **Laranja: Falta de Apontamento** | 🟣 **Roxo: >100% Super-Apontamento** | Cinza Claro: Folga.")

    if not df_view.empty:
        df_matriz = df_view.copy()
        df_matriz['MATRIZ_VAL'] = df_matriz['EFICIENCIA_VISUAL']
        mask_falta = (df_matriz['STATUS'] == 'CRÍTICO (Sem Apontamento)')
        mask_super = (df_matriz['STATUS'] == 'ALERTA (Super-Apontamento)')
        df_matriz.loc[mask_falta, 'MATRIZ_VAL'] = -1
        df_matriz.loc[mask_super, 'MATRIZ_VAL'] = -2

        pivot_ui = df_matriz.pivot_table(index=['SETOR', 'MATRICULA_FINAL', 'NOME_FINAL'], columns='DT_REF',
                                         values='MATRIZ_VAL',
                                         aggfunc='mean').reset_index()

        novas_cols = []
        date_cols = []
        for c in pivot_ui.columns:
            if isinstance(c, datetime) or hasattr(c, 'strftime'):
                col_str = c.strftime('%d/%m')
                novas_cols.append(col_str)
                date_cols.append(col_str)
            else:
                novas_cols.append(str(c))
        pivot_ui.columns = novas_cols

        pivot_ui.insert(0, 'FOTO', pivot_ui['MATRICULA_FINAL'].apply(get_foto_base64))


        def color_efficiency(val):
            if pd.isna(val) or val == 0: return 'background-color: #F3F4F6; color: #9CA3AF;'
            if val == -1: return 'background-color: #FED7AA; color: #9A3412; font-weight: bold;'
            if val == -2: return 'background-color: #E9D5FF; color: #6B21A8; font-weight: bold;'
            if val >= 85: return 'background-color: #BBF7D0; color: #166534; font-weight: bold;'
            if val >= 70: return 'background-color: #FEF08A; color: #A16207; font-weight: bold;'
            return 'background-color: #FECACA; color: #991B1B; font-weight: bold;'


        def format_val(val):
            if pd.isna(val) or val == 0: return "-"
            if val == -1: return "0"
            if val == -2: return ">100"
            return f"{val:.0f}"


        try:
            styled_df = pivot_ui.style.map(color_efficiency, subset=date_cols).format(format_val, subset=date_cols)
        except AttributeError:
            styled_df = pivot_ui.style.applymap(color_efficiency, subset=date_cols).format(format_val, subset=date_cols)

        st.dataframe(styled_df, use_container_width=True, height=600, hide_index=True, column_config={
            "FOTO": st.column_config.ImageColumn("Foto", width="small"),
            "MATRICULA_FINAL": None,
            "NOME_FINAL": "Colaborador",
            "SETOR": "Setor"
        })
    else:
        st.info("Sem dados para renderizar a matriz de calendário.")

with tab_dados:
    st.markdown("##### 🔍 Extração Analítica")
    colunas_exibicao = ['DT_REF', 'SETOR', 'NOME_FINAL', 'GESTOR', 'ESC_H', 'REAL_H', 'H_REAL_LIQ', 'HORAS_DEC',
                        'HORAS_PROD', 'HORAS_IMPROD', 'APONTOU_REFEICAO', 'FALTA_REFEICAO', 'EFICIENCIA_GERAL',
                        'STATUS']
    st.dataframe(df_view[colunas_exibicao], use_container_width=True, column_config={
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
        "EFICIENCIA_GERAL": st.column_config.ProgressColumn("Efic. (%)", format="%.0f%%", min_value=0, max_value=100),
        "APONTOU_REFEICAO": st.column_config.TextColumn("Refeição Diária?"),
        "FALTA_REFEICAO": st.column_config.NumberColumn("Alerta S/ Refeicao", format="%d"),
        "STATUS": st.column_config.TextColumn("Status")
    })

# ==============================================================================
# IMPRESSÃO E RELATÓRIOS
# ==============================================================================
st.markdown("---")
st.markdown("### 🖨️ Relatórios Executivos")
st.caption("Exporte a análise cruzada num formato PDF otimizado (A4 deitado ou em pé) para apresentar à diretoria.")

orientacao_ui = st.radio("Orientação do PDF:", ["Paisagem (Deitado)", "Retrato (Em pé)"], horizontal=True,
                         label_visibility="collapsed")
orientacao_escolhida = 'L' if 'Paisagem' in orientacao_ui else 'P'

with st.spinner("Desenhando gráficos e compilando PDF..."):
    df_improd_global = st.session_state.get('dataset_improd', pd.DataFrame())

    excel_bytes, pdf_bytes = processar_e_gerar_relatorios_eficiencia(
        df_view,
        df_improd_global,
        d_in, d_out,
        df_espelho,
        orientacao_pdf=orientacao_escolhida,
        criterio_ranking=criterio_ranking
    )

nome_padrao_arquivo = f"Auditoria_PeopleAnalytics_{d_in.strftime('%d%m%y')}_a_{d_out.strftime('%d%m%y')}"

c_pdf, c_excel = st.columns(2)
with c_pdf:
    st.download_button(label="📄 Descarregar Relatório PDF", data=pdf_bytes, file_name=f"{nome_padrao_arquivo}.pdf",
                       mime="application/pdf", type="primary", use_container_width=True)
with c_excel:
    st.download_button(label="📊 Descarregar Tabela Excel", data=excel_bytes, file_name=f"{nome_padrao_arquivo}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)