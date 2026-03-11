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

# Tentativa segura de importar o matplotlib para o PDF
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

icon_main = get_icon("tractor", "#F59E0B", "36")
ui_header(
    title="Gestão de Comboio e Lubrificação",
    subtitle="Auditoria volumétrica exata: controle rigoroso de saídas, abastecimento e autonomia isolados por fluido.",
    icon=icon_main
)


# ==============================================================================
# LÓGICA DE PROCESSAMENTO DE DADOS (ETL) E UI CUSTOMIZADA
# ==============================================================================

def limpar_numero(valor):
    if pd.isna(valor): return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    valor_str = str(valor).replace('.', '').replace(',', '.')
    return pd.to_numeric(valor_str, errors='coerce')


def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def formatar_qtd(valor, unidade='L'):
    if pd.isna(valor) or valor == 0: return f"0 {unidade}"
    fmt_val = f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    if fmt_val.endswith(',00'): fmt_val = fmt_val[:-3]
    return f"{fmt_val} {unidade}"


def draw_material_card(col, nome, saida, entrada, unidade):
    """Desenha um cartão HTML customizado focado em um material específico."""
    balanco = entrada - saida
    cor_borda = "#10B981" if balanco >= 0 else "#EF4444"
    cor_balanco = "#166534" if balanco >= 0 else "#991B1B"
    bg_balanco = "#BBF7D0" if balanco >= 0 else "#FECACA"

    nome_curto = str(nome).split('\n')[0][:30] + "..." if len(str(nome)) > 30 else str(nome).split('\n')[0]

    html = f"""
    <div style="background-color: white; border: 1px solid #E2E8F0; border-left: 4px solid {cor_borda}; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); height: 130px; display: flex; flex-direction: column; justify-content: space-between;">
        <div style="font-size: 0.85rem; font-weight: 700; color: #475569; margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{nome}">
            🛢️ {nome_curto}
        </div>
        <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 8px;">
            <div style="text-align: left;">
                <div style="font-size: 0.65rem; color: #64748B; text-transform: uppercase; font-weight: 600;">Saída (Uso)</div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #EF4444; line-height: 1.1;">{formatar_qtd(saida, unidade)}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.65rem; color: #64748B; text-transform: uppercase; font-weight: 600;">Entrada (CB01)</div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #2196F3; line-height: 1.1;">{formatar_qtd(entrada, unidade)}</div>
            </div>
        </div>
        <div style="background-color: {bg_balanco}; color: {cor_balanco}; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; text-align: center;">
            Balanço Físico: {formatar_qtd(balanco, unidade)}
        </div>
    </div>
    """
    col.markdown(html, unsafe_allow_html=True)


# ==============================================================================
# MOTOR DO PDF (GEOMETRIA INTELIGENTE E RESPONSIVA)
# ==============================================================================

class RelatorioPDF(FPDF):
    def __init__(self, titulo_relatorio="Relatorio Evolutivo do Comboio, Cedro", orientacao='L', *args, **kwargs):
        super().__init__(orientation=orientacao, format='A4', *args, **kwargs)
        self.titulo_relatorio = titulo_relatorio
        self.orientacao = orientacao
        self.largura_util = 277 if orientacao == 'L' else 190

    def header(self):
        caminho_logo = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logo_cedro.png")
        if not os.path.exists(caminho_logo): caminho_logo = "logo_cedro.png"
        if os.path.exists(caminho_logo): self.image(caminho_logo, 10, 8, 12)

        self.set_font('Arial', 'B', 14)
        self.set_text_color(50, 50, 50)
        titulo = self.titulo_relatorio.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, titulo, 0, 1, 'C')

        self.set_draw_color(245, 158, 11)
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

    def add_insight_box(self, texto):
        """Desenha a caixa de insight apenas se houver espaço; caso contrário, pula de página."""
        if self.get_y() > (275 if self.orientacao == 'P' else 185) - 25:
            self.add_page()
        else:
            self.ln(3)

        self.set_fill_color(255, 248, 220)
        self.set_draw_color(245, 158, 11)
        self.set_line_width(0.3)

        self.set_font('Arial', 'B', 8)
        self.set_text_color(194, 65, 12)
        self.cell(0, 6, "  INSIGHT EVOLUTIVO ESTRITAMENTE POR MATERIAL", 'L T R', 1, 'L', fill=True)

        self.set_font('Arial', 'I', 8)
        self.set_text_color(60, 60, 60)
        texto_limpo = texto.encode('latin-1', 'replace').decode('latin-1')
        self.multi_cell(0, 5, "  " + texto_limpo, border='L B R', fill=True)
        self.ln(4)

    def check_space(self, required_space):
        """Verifica se há espaço suficiente. Se não houver, adiciona nova página."""
        max_y = 275 if self.orientacao == 'P' else 185
        if self.get_y() + required_space > max_y:
            self.add_page()
            return True
        return False


@st.cache_data(show_spinner="Renderizando relatório PDF responsivo...", ttl=600)
def compilar_relatorios_comboio_evolutivo(df_view, df_base_data_filtrada, df_estoque, df_autonomia, dt_in, dt_out,
                                          orientacao_pdf='L'):
    excel_io = io.BytesIO()
    arquivos_temporarios = []

    # Isola saídas e entradas estritamente por produto
    df_saidas = df_view[df_view['CATEGORIA_OPERACAO'].str.contains('Saída|Estorno')].copy()
    df_abast = df_base_data_filtrada[df_base_data_filtrada['CATEGORIA_OPERACAO'] == 'Entrada (Abastecimento)']

    df_saida_pdf = df_saidas.groupby(['ITEM_COMPLETO', 'UNIDADE'])['QTD_DASHBOARD'].sum().reset_index(name='SAIDA')
    df_abast_pdf = df_abast.groupby(['ITEM_COMPLETO', 'UNIDADE'])['QTD_DASHBOARD'].sum().reset_index(name='ENTRADA')

    df_kpi_pdf = pd.merge(df_saida_pdf, df_abast_pdf, on=['ITEM_COMPLETO', 'UNIDADE'], how='outer').fillna(0)
    df_kpi_pdf['BALANCO'] = df_kpi_pdf['ENTRADA'] - df_kpi_pdf['SAIDA']
    df_kpi_pdf = df_kpi_pdf.sort_values('SAIDA', ascending=False)

    w_total = 277 if orientacao_pdf == 'L' else 190
    max_y_page = 190 if orientacao_pdf == 'L' else 277
    w_ext = [22, 60, 25, 110, 25, 35] if orientacao_pdf == 'L' else [18, 40, 20, 69, 18, 25]

    def desenhar_linha_multicell(pdf_obj, textos, larguras, alinhamentos, fill_row, func_cabecalho=None):
        pdf_obj.set_font('Arial', '', 7.5)
        texto_material = str(textos[3]).encode('latin-1', 'replace').decode('latin-1')

        largura_util = larguras[3] - 2
        largura_texto = pdf_obj.get_string_width(texto_material)
        linhas_estimadas = max(1, int((largura_texto / largura_util) + 0.9))

        altura_linha = 4.5
        altura_total = max(6, (linhas_estimadas * altura_linha) + 2)

        if pdf_obj.get_y() + altura_total > max_y_page:
            pdf_obj.add_page()
            if func_cabecalho: func_cabecalho()

        x_inicial = pdf_obj.get_x()
        y_inicial = pdf_obj.get_y()

        if fill_row:
            pdf_obj.set_fill_color(245, 247, 250)
        else:
            pdf_obj.set_fill_color(255, 255, 255)

        pdf_obj.rect(x_inicial, y_inicial, sum(larguras), altura_total, 'F')

        pdf_obj.set_draw_color(220, 220, 220)
        pdf_obj.line(x_inicial, y_inicial + altura_total, x_inicial + sum(larguras), y_inicial + altura_total)

        pdf_obj.set_text_color(40, 40, 40)

        for i in range(len(textos)):
            x_atual = x_inicial + sum(larguras[:i])
            pdf_obj.set_xy(x_atual, y_inicial)

            if i == 3:
                pdf_obj.set_xy(x_atual, y_inicial + 1)
                pdf_obj.multi_cell(larguras[i], altura_linha, f" {texto_material}", 0, alinhamentos[i])
            else:
                texto_celula = str(textos[i])
                if i == 1 and len(texto_celula) > 35: texto_celula = texto_celula[:32] + "..."
                texto_celula = texto_celula.encode('latin-1', 'replace').decode('latin-1')

                if alinhamentos[i] == 'R':
                    texto_celula = f"{texto_celula} "
                elif alinhamentos[i] == 'L':
                    texto_celula = f" {texto_celula}"

                y_centralizado = y_inicial + (altura_total - 4) / 2
                pdf_obj.set_xy(x_atual, y_centralizado)
                pdf_obj.cell(larguras[i], 4, texto_celula, 0, 0, alinhamentos[i])

        y_final_real = max(y_inicial + altura_total, pdf_obj.get_y() + 1)
        pdf_obj.set_xy(x_inicial, y_final_real)

    pdf = RelatorioPDF(titulo_relatorio="Auditoria Volumetrica do Comboio, Cedro", orientacao=orientacao_pdf)
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- SEÇÃO 1: GRADE DE MATERIAIS ---
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Grade de Consumo e Balanco por Material", 0, 1, 'L')

    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5,
             f"Periodo Auditado: {dt_in.strftime('%d/%m/%Y')} a {dt_out.strftime('%d/%m/%Y')} (Sem misturas de fluidos)",
             0, 1, 'L')
    pdf.ln(4)

    def desenhar_card_material(pdf_obj, x, y, largura, titulo, valor_saida, cor_borda_r, cor_borda_g, cor_borda_b,
                               subtexto=""):
        pdf_obj.set_fill_color(248, 250, 252)
        pdf_obj.set_draw_color(cor_borda_r, cor_borda_g, cor_borda_b)
        pdf_obj.set_line_width(0.8)
        pdf_obj.rect(x, y, largura, 22, 'DF')
        pdf_obj.set_line_width(0.2)

        pdf_obj.set_xy(x + 2, y + 3)
        pdf_obj.set_font('Arial', 'B', 7)
        pdf_obj.set_text_color(71, 85, 105)
        pdf_obj.cell(largura - 4, 4, titulo.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'C')

        pdf_obj.set_xy(x + 2, y + 8)
        pdf_obj.set_font('Arial', 'B', 10)
        pdf_obj.set_text_color(239, 68, 68)
        pdf_obj.cell(largura - 4, 7, valor_saida.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'C')

        if subtexto:
            pdf_obj.set_xy(x + 2, y + 16)
            pdf_obj.set_font('Arial', '', 6)
            pdf_obj.set_text_color(cor_borda_r, cor_borda_g, cor_borda_b)
            pdf_obj.cell(largura - 4, 4, subtexto.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'C')

    # Paginação inteligente dos Cartões:
    # Paisagem = 4 cartões por linha | Retrato = 2 cartões por linha (Evita cartões minúsculos)
    max_cols = 4 if orientacao_pdf == 'L' else 2
    espaco_entre = 4
    largura_card = (w_total - (espaco_entre * (max_cols - 1))) / max_cols
    espaco_linha = 4

    y_kpi = pdf.get_y()
    col_idx = 0

    if df_kpi_pdf.empty:
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 5, "Nenhuma movimentacao de materiais registrada.", 0, 1)
        y_kpi = pdf.get_y()
    else:
        # Loop alterado: Imprime a lista COMPLETA de cartões de material!
        for row in df_kpi_pdf.itertuples():
            if col_idx == max_cols:
                col_idx = 0
                y_kpi += 22 + espaco_linha
                if y_kpi + 22 > max_y_page:
                    pdf.add_page()
                    y_kpi = pdf.get_y()

            pos_x = 10 + col_idx * (largura_card + espaco_entre)

            titulo_mat = str(row.ITEM_COMPLETO).split('\n')[0][:30]
            val_saida = f"SAIDA: {formatar_qtd(row.SAIDA, row.UNIDADE)}"
            val_in = formatar_qtd(row.ENTRADA, row.UNIDADE)
            val_bal = formatar_qtd(row.BALANCO, row.UNIDADE)
            cor_r, cor_g, cor_b = (16, 185, 129) if row.BALANCO >= 0 else (239, 68, 68)

            desenhar_card_material(pdf, pos_x, y_kpi, largura_card, titulo_mat, val_saida, cor_r, cor_g, cor_b,
                                   f"Entrou: {val_in} | Bal: {val_bal}")
            col_idx += 1

    pdf.set_y(y_kpi + 22 + 8)

    # --- SEÇÃO 2: GRÁFICO ÁREA EMPILHADA ---
    df_litros_out = df_saidas[df_saidas['UNIDADE'] == 'L']
    if MATPLOTLIB_AVAILABLE and not df_litros_out.empty:
        # Geometria flexível para o Gráfico 1 (Necessita de ~100mm)
        pdf.check_space(105)

        df_evo = df_litros_out.groupby([df_litros_out['DATA'].dt.date, 'ITEM_COMPLETO'])[
            'QTD_DASHBOARD'].sum().reset_index()
        df_evo['ITEM_CURTO'] = df_evo['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:20] + '..')

        top_mats = df_evo.groupby('ITEM_CURTO')['QTD_DASHBOARD'].sum().nlargest(5).index
        df_evo['MAT_FILTER'] = np.where(df_evo['ITEM_CURTO'].isin(top_mats), df_evo['ITEM_CURTO'], 'Outros Óleos')
        pivot_evo = df_evo.pivot_table(index='DATA', columns='MAT_FILTER', values='QTD_DASHBOARD',
                                       aggfunc='sum').fillna(0)

        # Ajusta a proporção para caber perfeito sem distorcer
        fig_size_evo = (11.0, 4.0) if orientacao_pdf == 'L' else (7.4, 4.0)
        fig_evo, ax_evo = plt.subplots(figsize=fig_size_evo)

        colors = plt.cm.tab10.colors
        ax_evo.stackplot(pivot_evo.index, pivot_evo.T.values, labels=pivot_evo.columns, colors=colors, alpha=0.85)

        ax_evo.set_title('Evolucao Diaria de Consumo por Tipo de Fluido (Litros)', fontsize=11, fontweight='bold',
                         color='#333333')
        ax_evo.grid(True, axis='y', linestyle='--', alpha=0.4)
        ax_evo.spines['top'].set_visible(False);
        ax_evo.spines['right'].set_visible(False)
        ax_evo.spines['left'].set_color('#CCCCCC');
        ax_evo.spines['bottom'].set_color('#CCCCCC')
        ax_evo.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax_evo.tick_params(axis='both', labelsize=8, colors='#555555')
        ax_evo.yaxis.set_major_formatter(ticker.FuncFormatter(lambda val, pos: f"{val:,.0f}".replace(',', '.')))

        ax_evo.legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7, frameon=False)

        plt.tight_layout()
        img_evo = tempfile.mktemp(suffix=".png")
        arquivos_temporarios.append(img_evo)
        fig_evo.savefig(img_evo, dpi=200, bbox_inches='tight')
        plt.close(fig_evo)

        # No Retrato a legenda pode exigir um pouco mais de margem à direita
        largura_img = w_total - 25 if orientacao_pdf == 'L' else w_total - 20
        pdf.image(img_evo, x=10, w=largura_img)

        mat_top_geral = df_litros_out.groupby('ITEM_COMPLETO')['QTD_DASHBOARD'].sum().idxmax()
        mat_top_geral_nome = str(mat_top_geral).split('\n')[0][:40]
        texto_evo = f"O grafico de Area Empilhada ilustra a montanha de consumo diario isolada por produto. Neste periodo, o item '{mat_top_geral_nome}' dominou a volumetria. Picos indicam dias de alta demanda."
        pdf.add_insight_box(texto_evo)

    # --- SEÇÃO 3: EVOLUÇÃO DOS TOP 3 CENTROS DE CUSTO ---
    if MATPLOTLIB_AVAILABLE and not df_litros_out.empty:
        # Verifica espaço para título + gráfico 2 (~110mm)
        if not pdf.check_space(110): pdf.ln(10)

        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(245, 158, 11)
        pdf.cell(0, 8, "Rastreio Temporal: Top 3 Centros de Custo Consumidores", 0, 1)
        pdf.ln(2)

        top3_ccs = df_litros_out.groupby('CENTRO_CUSTO')['QTD_DASHBOARD'].sum().nlargest(3).index.tolist()
        df_top3 = df_litros_out[df_litros_out['CENTRO_CUSTO'].isin(top3_ccs)].copy()
        pivot_top3 = df_top3.pivot_table(index=df_top3['DATA'].dt.date, columns='CENTRO_CUSTO', values='QTD_DASHBOARD',
                                         aggfunc='sum').fillna(0)

        idx_dates = pd.date_range(start=df_top3['DATA'].min(), end=df_top3['DATA'].max()).date
        pivot_top3 = pivot_top3.reindex(idx_dates, fill_value=0)

        fig_size_top3 = (11.0, 4.0) if orientacao_pdf == 'L' else (7.4, 4.0)
        fig_top3, ax_top3 = plt.subplots(figsize=fig_size_top3)

        cores_linhas = ['#EF4444', '#F59E0B', '#2196F3']
        for i, cc in enumerate(pivot_top3.columns):
            ax_top3.plot(pivot_top3.index, pivot_top3[cc], marker='o', linewidth=2.5, markersize=4, label=str(cc),
                         color=cores_linhas[i % len(cores_linhas)])

        ax_top3.set_title('Curvas de Consumo (Litros/Dia) dos Principais Ofensores', fontsize=11, fontweight='bold',
                          color='#333333')
        ax_top3.grid(True, linestyle='--', alpha=0.4)
        ax_top3.spines['top'].set_visible(False);
        ax_top3.spines['right'].set_visible(False)
        ax_top3.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax_top3.tick_params(axis='both', labelsize=8)
        ax_top3.yaxis.set_major_formatter(ticker.FuncFormatter(lambda val, pos: f"{val:,.0f}".replace(',', '.')))
        ax_top3.legend(loc='upper right', frameon=True, fontsize=8)

        plt.tight_layout()
        img_top3 = tempfile.mktemp(suffix=".png")
        arquivos_temporarios.append(img_top3)
        fig_top3.savefig(img_top3, dpi=200, bbox_inches='tight')
        plt.close(fig_top3)

        pdf.image(img_top3, x=10, w=w_total - 5)

        if top3_ccs:
            cc_critico = top3_ccs[0]
            df_cc_critico = df_litros_out[df_litros_out['CENTRO_CUSTO'] == cc_critico]
            vol_critico = df_cc_critico['QTD_DASHBOARD'].sum()

            if not df_cc_critico.empty:
                mat_critico = df_cc_critico.groupby('ITEM_COMPLETO')['QTD_DASHBOARD'].sum().idxmax()
                mat_critico_nome = str(mat_critico).split('\n')[0][:45]
                texto_top3 = f"Isolar o consumo no tempo permite identificar vazamentos ou desperdicios padronizados. O Centro de Custo '{cc_critico}' foi o ofensor principal do periodo, consumindo um total de {formatar_qtd(vol_critico, 'L')}, puxado principalmente pelo uso de '{mat_critico_nome}'. Avalie os picos dessa linha para justificar a aplicacao."
            else:
                texto_top3 = f"Isolar o consumo no tempo permite identificar vazamentos ou desperdicios. O Centro de Custo '{cc_critico}' foi o ofensor principal do periodo, consumindo um total de {formatar_qtd(vol_critico, 'L')}."
        else:
            texto_top3 = "Sem dados suficientes para rastrear ofensores volumetricos neste periodo."

        pdf.add_insight_box(texto_top3)

    # --- SEÇÃO 4: MATRIZ DE CONSUMO PRODUTO X CENTRO DE CUSTO (VOLUME) ---
    if not df_litros_out.empty:
        pdf.check_space(60)  # Matriz precisa de espaço para Título + Header + Algumas linhas
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 14);
        pdf.set_text_color(245, 158, 11)
        pdf.cell(0, 8, "Matriz Volumetrica Cruzada (Centro de Custo vs Produto)", 0, 1)

        pdf.set_font('Arial', '', 8);
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5, "Legenda: Litros exatos consumidos por fluido.", 0, 1)
        pdf.ln(2)

        df_matriz_copy = df_litros_out.copy()
        df_matriz_copy['MAT_SIMPLES'] = df_matriz_copy['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:18])

        n_cols_prod = 7 if orientacao_pdf == 'L' else 4
        top_mats = df_matriz_copy.groupby('MAT_SIMPLES')['QTD_DASHBOARD'].sum().nlargest(n_cols_prod).index.tolist()

        df_top_mats = df_matriz_copy[df_matriz_copy['MAT_SIMPLES'].isin(top_mats)]
        pivot_prod = df_top_mats.pivot_table(index='CENTRO_CUSTO', columns='MAT_SIMPLES', values='QTD_DASHBOARD',
                                             aggfunc='sum').fillna(0)

        colunas_plot = top_mats
        w_cc_prod = 45 if orientacao_pdf == 'L' else 35
        # Reduz 0.1 na divisão para evitar estouro de ponto flutuante em folhas exatas
        w_prod = (w_total - w_cc_prod - 0.1) / len(colunas_plot)

        def print_prod_header():
            pdf.set_font('Arial', 'B', 7)
            pdf.set_fill_color(245, 158, 11);
            pdf.set_text_color(255, 255, 255)
            pdf.cell(w_cc_prod, 8, " Centro de Custo", 1, 0, 'L', fill=True)
            for c in colunas_plot:
                c_clean = c.encode('latin-1', 'replace').decode('latin-1')
                pdf.cell(w_prod, 8, c_clean, 1, 0, 'C', fill=True)
            pdf.ln()

        print_prod_header()
        pdf.set_font('Arial', 'B', 6);
        pdf.set_draw_color(220, 220, 220)

        fill_prod = False
        for cc, row in pivot_prod.iterrows():
            if pdf.get_y() > max_y_page - 10:
                pdf.add_page();
                print_prod_header();
                pdf.set_font('Arial', 'B', 6)

            if fill_prod:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(255, 255, 255)

            cc_str = str(cc)[:20].encode('latin-1', 'replace').decode('latin-1')
            pdf.set_text_color(40, 40, 40)
            pdf.cell(w_cc_prod, 6, f" {cc_str}", 1, 0, 'L', fill=True)

            for c in colunas_plot:
                val = row.get(c, 0)
                if val <= 0:
                    pdf.set_text_color(180, 180, 180)
                    pdf.cell(w_prod, 6, "-", 1, 0, 'C', fill=True)
                else:
                    txt = f"{val:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    pdf.set_text_color(40, 40, 40)
                    pdf.cell(w_prod, 6, txt, 1, 0, 'C', fill=True)

            pdf.ln()
            fill_prod = not fill_prod

    # --- SEÇÃO 5: MATRIZ DE TRANSFERÊNCIAS (ENTRADAS NO COMBOIO) ---
    df_transf_pdf = df_base_data_filtrada[
        df_base_data_filtrada['CATEGORIA_OPERACAO'] == 'Entrada (Abastecimento)'].copy()
    if not df_transf_pdf.empty:
        pdf.check_space(60)
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 14);
        pdf.set_text_color(245, 158, 11)
        pdf.cell(0, 8, "Matriz Diaria de Transferencias (Almoxarifado -> Comboio)", 0, 1)

        pdf.set_font('Arial', '', 8);
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5, "Legenda: Entradas de abastecimento no tanque do Comboio.", 0, 1)
        pdf.ln(2)

        df_transf_pdf['MAT_SIMPLES'] = df_transf_pdf['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:18])
        n_cols_transf = 7 if orientacao_pdf == 'L' else 4
        top_mats_t = df_transf_pdf.groupby('MAT_SIMPLES')['QTD_DASHBOARD'].sum().nlargest(n_cols_transf).index.tolist()
        df_top_mats_t = df_transf_pdf[df_transf_pdf['MAT_SIMPLES'].isin(top_mats_t)]
        pivot_transf_pdf = df_top_mats_t.pivot_table(index=df_top_mats_t['DATA'].dt.date, columns='MAT_SIMPLES',
                                                     values='QTD_DASHBOARD', aggfunc='sum').fillna(0)

        w_data_t = 30 if orientacao_pdf == 'L' else 25
        w_prod_t = (w_total - w_data_t - 0.1) / len(top_mats_t)

        def print_transf_header():
            pdf.set_font('Arial', 'B', 7)
            pdf.set_fill_color(245, 158, 11);
            pdf.set_text_color(255, 255, 255)
            pdf.cell(w_data_t, 8, " Data", 1, 0, 'C', fill=True)
            for c in top_mats_t:
                c_clean = c.encode('latin-1', 'replace').decode('latin-1')
                pdf.cell(w_prod_t, 8, c_clean, 1, 0, 'C', fill=True)
            pdf.ln()

        print_transf_header()
        pdf.set_font('Arial', 'B', 6);
        pdf.set_draw_color(220, 220, 220)

        fill_t = False
        for data_dt, row in pivot_transf_pdf.iterrows():
            if pdf.get_y() > max_y_page - 10:
                pdf.add_page();
                print_transf_header();
                pdf.set_font('Arial', 'B', 6)

            if fill_t:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(255, 255, 255)

            dt_str = data_dt.strftime('%d/%m/%Y')
            pdf.set_text_color(40, 40, 40)
            pdf.cell(w_data_t, 6, f" {dt_str}", 1, 0, 'C', fill=True)

            for c in top_mats_t:
                val = row.get(c, 0)
                if val <= 0:
                    pdf.set_text_color(180, 180, 180)
                    pdf.cell(w_prod_t, 6, "-", 1, 0, 'C', fill=True)
                else:
                    txt = f"{val:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    pdf.set_text_color(40, 40, 40)
                    pdf.cell(w_prod_t, 6, txt, 1, 0, 'C', fill=True)

            pdf.ln()
            fill_t = not fill_t

    # --- SEÇÃO FINAL: EXTRATO COMPLETO ---
    pdf.add_page()  # Extrato sempre quebra de página por ser longo
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(245, 158, 11)
    pdf.cell(0, 8, "Extrato Auditavel de Movimentacoes", 0, 1)

    def cabecalho_extrato():
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(245, 158, 11)
        pdf.cell(w_ext[0], 7, " Data", 1, 0, 'C', fill=True)
        pdf.cell(w_ext[1], 7, " Operacao", 1, 0, 'L', fill=True)
        pdf.cell(w_ext[2], 7, " C.Custo", 1, 0, 'C', fill=True)
        pdf.cell(w_ext[3], 7, " Material / Descricao", 1, 0, 'L', fill=True)
        pdf.cell(w_ext[4], 7, " Qtd", 1, 0, 'C', fill=True)
        pdf.cell(w_ext[5], 7, " Valor (R$)", 1, 1, 'R', fill=True)

    cabecalho_extrato()

    df_extrato = df_view.sort_values(by=['DATA', 'VALOR_DASHBOARD'], ascending=[False, False])

    def formatar_linha_multicell(pdf_obj, textos, larguras, alinhamentos, fill_row, func_cabecalho=None):
        pdf_obj.set_font('Arial', '', 7.5)
        texto_material = str(textos[3]).encode('latin-1', 'replace').decode('latin-1')
        largura_util = larguras[3] - 2
        largura_texto = pdf_obj.get_string_width(texto_material)
        linhas_estimadas = max(1, int((largura_texto / largura_util) + 0.9))
        altura_linha = 4.5
        altura_total = max(6, (linhas_estimadas * altura_linha) + 2)

        if pdf_obj.get_y() + altura_total > max_y_page:
            pdf_obj.add_page();
            func_cabecalho()

        x_inicial = pdf_obj.get_x();
        y_inicial = pdf_obj.get_y()

        if fill_row:
            pdf_obj.set_fill_color(245, 247, 250)
        else:
            pdf_obj.set_fill_color(255, 255, 255)

        pdf_obj.rect(x_inicial, y_inicial, sum(larguras), altura_total, 'F')
        pdf_obj.set_draw_color(220, 220, 220)
        pdf_obj.line(x_inicial, y_inicial + altura_total, x_inicial + sum(larguras), y_inicial + altura_total)
        pdf_obj.set_text_color(40, 40, 40)

        for i in range(len(textos)):
            x_atual = x_inicial + sum(larguras[:i])
            pdf_obj.set_xy(x_atual, y_inicial)
            if i == 3:
                pdf_obj.set_xy(x_atual, y_inicial + 1)
                pdf_obj.multi_cell(larguras[i], altura_linha, f" {texto_material}", 0, alinhamentos[i])
            else:
                texto_celula = str(textos[i])
                if i == 1 and len(texto_celula) > 35: texto_celula = texto_celula[:32] + "..."
                texto_celula = texto_celula.encode('latin-1', 'replace').decode('latin-1')
                if alinhamentos[i] == 'R':
                    texto_celula = f"{texto_celula} "
                elif alinhamentos[i] == 'L':
                    texto_celula = f" {texto_celula}"

                y_centralizado = y_inicial + (altura_total - 4) / 2
                pdf_obj.set_xy(x_atual, y_centralizado)
                pdf_obj.cell(larguras[i], 4, texto_celula, 0, 0, alinhamentos[i])

        y_final_real = max(y_inicial + altura_total, pdf_obj.get_y() + 1)
        pdf_obj.set_xy(x_inicial, y_final_real)

    fill_row = False
    for _, row in df_extrato.iterrows():
        dt_str = row['DATA'].strftime('%d/%m/%y') if pd.notna(row['DATA']) else "-"
        op_str = str(row['OPERACAO_FULL'])
        cc_str = str(row['CENTRO_CUSTO'])[:12]
        mat_str = str(row['ITEM_COMPLETO'])

        un = str(row['UNIDADE']).upper()
        if un == 'L':
            qtd_str = f"{row['QTD_DASHBOARD']:,.2f} L".replace(',', 'X').replace('.', ',').replace('X', '.')
        else:
            qtd_str = f"{row['QTD_DASHBOARD']:,.0f} {un}".replace(',', 'X').replace('.', ',').replace('X', '.')

        val_str = formatar_moeda(row['VALOR_DASHBOARD'])

        textos = [dt_str, op_str, cc_str, mat_str, qtd_str, val_str]
        alinhamentos = ['C', 'L', 'C', 'L', 'C', 'R']

        formatar_linha_multicell(pdf, textos, w_ext, alinhamentos, fill_row, func_cabecalho=cabecalho_extrato)
        fill_row = not fill_row

    # ==============================================================================
    # EXPORTAÇÃO EXCEL MULTI-ABA
    # ==============================================================================
    with pd.ExcelWriter(excel_io) as writer:
        colunas_exibir = ['DATA', 'OPERACAO_FULL', 'CENTRO_CUSTO', 'ITEM_COMPLETO', 'QTD_ORIGINAL_SAP', 'QTD_DASHBOARD',
                          'UNIDADE', 'VALOR_DASHBOARD', 'CATEGORIA_OPERACAO']
        df_export = df_extrato[colunas_exibir].copy().rename(columns={'OPERACAO_FULL': 'Movimentação'})
        df_export.to_excel(writer, sheet_name="Extrato SAP", index=False)

        if not df_autonomia.empty:
            df_auto_export = df_autonomia[
                ['ITEM_COMPLETO', 'QTD_ATUAL', 'UNIDADE', 'VALOR_ATUAL', 'CONSUMO_MEDIO_DIA', 'AUTONOMIA_DIAS']].copy()
            df_auto_export.columns = ['Material', 'Qtd Estoque', 'UN', 'Valor Financeiro (R$)', 'Consumo Médio Diário',
                                      'Autonomia (Dias)']
            df_auto_export.to_excel(writer, sheet_name="Posição Estoque", index=False)

        if not df_saidas.empty:
            pivot_excel = df_saidas.pivot_table(index='CENTRO_CUSTO', columns='ITEM_COMPLETO', values='QTD_DASHBOARD',
                                                aggfunc='sum').fillna(0)
            pivot_excel.to_excel(writer, sheet_name="Matriz Volume C.Custo")

        if not df_abast.empty:
            pivot_transf_ex = df_abast.pivot_table(index=df_abast['DATA'].dt.date, columns='ITEM_COMPLETO',
                                                   values='QTD_DASHBOARD', aggfunc='sum').fillna(0)
            pivot_transf_ex.to_excel(writer, sheet_name="Transferências Diárias")

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


@st.cache_data(show_spinner="Processando arquivos SAP e cruzando dados...", ttl=600)
def processar_bases_comboio(file_export, file_codigos, file_estoque):
    try:
        def ler_arquivo(f):
            if f.name.endswith('.csv'):
                try:
                    return pd.read_csv(f, sep=None, engine='python', encoding='utf-8')
                except:
                    f.seek(0)
                    return pd.read_csv(f, sep=None, engine='python', encoding='latin-1')
            else:
                return pd.read_excel(f)

        # 1. Carrega Movimentações
        df_exp = ler_arquivo(file_export)
        df_cod = ler_arquivo(file_codigos)

        df_exp.columns = [str(c).upper().strip().replace('  ', ' ') for c in df_exp.columns]
        df_cod.columns = [str(c).upper().strip() for c in df_cod.columns]

        col_mat = next((c for c in df_exp.columns if 'MATERIAL' in c and 'TEXTO' not in c), 'MATERIAL')
        col_desc = next((c for c in df_exp.columns if 'TEXTO' in c), 'TEXTO BREVE MATERIAL')
        col_cc = next((c for c in df_exp.columns if 'CENTRO CUSTO' in c), 'CENTRO CUSTO')
        col_mov = next((c for c in df_exp.columns if 'TIPO DE MOVIMENTO' in c), 'TIPO DE MOVIMENTO')
        col_qtd = next((c for c in df_exp.columns if 'QTD' in c), 'QTD. UM REGISTRO')
        col_um = next((c for c in df_exp.columns if 'UM REGISTRO' in c and 'QTD' not in c), 'UM REGISTRO')
        col_valor = next((c for c in df_exp.columns if 'MONTANTE' in c), 'MONTANTE EM MI')
        col_data = next((c for c in df_exp.columns if 'DATA' in c), 'DATA DE LANÇAMENTO')

        col_cod_id = next((c for c in df_cod.columns if 'CODIGO' in c or 'CÓDIGO' in c), 'CODIGO')
        col_cod_desc = next((c for c in df_cod.columns if 'MOV' in c or 'DESC' in c), 'MOVIMENTAÇÃO')

        df_exp = df_exp.dropna(subset=[col_mov, col_data]).copy()

        df_exp[col_mov] = df_exp[col_mov].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()
        df_cod[col_cod_id] = df_cod[col_cod_id].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()
        df_exp[col_mat] = df_exp[col_mat].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if col_cc in df_exp.columns:
            df_exp[col_cc] = df_exp[col_cc].fillna('Não Informado').astype(str).str.replace(r'\.0$', '',
                                                                                            regex=True).str.strip()
        else:
            df_exp['CENTRO CUSTO'] = 'Não Informado'
            col_cc = 'CENTRO CUSTO'

        df_exp[col_qtd] = df_exp[col_qtd].apply(limpar_numero)
        df_exp[col_valor] = df_exp[col_valor].apply(limpar_numero)
        df_exp[col_data] = pd.to_datetime(df_exp[col_data], dayfirst=True, errors='coerce')

        df_final = pd.merge(df_exp, df_cod[[col_cod_id, col_cod_desc]], left_on=col_mov, right_on=col_cod_id,
                            how='left')
        df_final['DESCRICAO_MOVIMENTO'] = df_final[col_cod_desc].fillna('Operação Padrão')

        def definir_categoria(mov):
            mov = str(mov)
            if mov.startswith('2') and not mov.endswith('2'): return 'Saída (Consumo)'
            if mov.startswith('2') and mov.endswith('2'): return 'Entrada (Estorno)'
            if mov.startswith('3'): return 'Entrada (Abastecimento)'
            return 'Outras Operações'

        df_final['CATEGORIA_OPERACAO'] = df_final[col_mov].apply(definir_categoria)

        df_final['QTD_DASHBOARD'] = np.where(
            df_final['CATEGORIA_OPERACAO'].str.contains('Saída'),
            df_final[col_qtd] * -1,
            df_final[col_qtd].abs()
        )

        df_final['VALOR_DASHBOARD'] = np.where(
            df_final['CATEGORIA_OPERACAO'].str.contains('Saída'),
            df_final[col_valor] * -1,
            df_final[col_valor].abs()
        )

        df_final['ITEM_COMPLETO'] = df_final[col_mat].astype(str) + " - " + df_final[col_desc].astype(str)
        df_final['OPERACAO_FULL'] = df_final[col_mov].astype(str) + " - " + df_final['DESCRICAO_MOVIMENTO']

        cols_renomear = {
            col_data: 'DATA',
            col_cc: 'CENTRO_CUSTO',
            col_mov: 'MOVIMENTO',
            col_um: 'UNIDADE',
            col_qtd: 'QTD_ORIGINAL_SAP',
            col_valor: 'VALOR_ORIGINAL_SAP'
        }
        df_final = df_final.rename(columns=cols_renomear)

        df_est = ler_arquivo(file_estoque)
        df_est.columns = [str(c).upper().strip().replace('  ', ' ') for c in df_est.columns]

        col_mat_est = next((c for c in df_est.columns if 'MATERIAL' in c and 'TEXTO' not in c), 'MATERIAL')
        col_desc_est = next((c for c in df_est.columns if 'TEXTO' in c), 'TEXTO BREVE MATERIAL')
        col_qtd_est = next((c for c in df_est.columns if 'LIVRE' in c and 'VAL' not in c), 'UTILIZAÇÃO LIVRE')
        col_val_est = next((c for c in df_est.columns if 'VAL.UTILIZ' in c or 'VALOR' in c), 'VAL.UTILIZ.LIVRE')
        col_um_est = next((c for c in df_est.columns if 'UM' in c or 'MEDIDA' in c), 'UM BÁSICA')

        df_est[col_mat_est] = df_est[col_mat_est].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        df_est[col_qtd_est] = df_est[col_qtd_est].apply(limpar_numero)
        df_est[col_val_est] = df_est[col_val_est].apply(limpar_numero)

        df_estoque_final = df_est[[col_mat_est, col_desc_est, col_um_est, col_qtd_est, col_val_est]].copy()
        df_estoque_final.columns = ['MATERIAL', 'DESCRICAO', 'UNIDADE', 'QTD_ATUAL', 'VALOR_ATUAL']
        df_estoque_final['ITEM_COMPLETO'] = df_estoque_final['MATERIAL'] + " - " + df_estoque_final['DESCRICAO']

        return df_final, df_estoque_final

    except Exception as e:
        st.error(f"Erro ao processar os arquivos: {str(e)}")
        return None, None


# ==============================================================================
# INTERFACE E UPLOAD
# ==============================================================================

if 'df_comboio' not in st.session_state:
    st.session_state['df_comboio'] = None
    st.session_state['df_estoque_comboio'] = None

with st.expander("📂 Carregar Dados do SAP (Comboio)", expanded=(st.session_state['df_comboio'] is None)):
    c1, c2, c3 = st.columns(3)
    f_export = c1.file_uploader("1. Relatório (EXPORT)", type=['xlsx', 'csv'])
    f_codigos = c2.file_uploader("2. Dicionário (CODIGOS)", type=['xlsx', 'csv'])
    f_estoque = c3.file_uploader("3. Posição Atual (ESTOQUE)", type=['xlsx', 'csv'])

    if f_export and f_codigos and f_estoque and st.button("🚀 Cruzar e Analisar Dados", type="primary",
                                                          use_container_width=True):
        df_mov, df_est = processar_bases_comboio(f_export, f_codigos, f_estoque)
        if df_mov is not None and df_est is not None:
            st.session_state['df_comboio'] = df_mov
            st.session_state['df_estoque_comboio'] = df_est
            st.rerun()

if st.session_state['df_comboio'] is None:
    ui_empty_state("Faça o upload do Export, Códigos e Estoque Atual para gerar a análise.", icon="🚚")
    st.stop()

df_base = st.session_state['df_comboio'].copy()
df_estoque_base = st.session_state['df_estoque_comboio'].copy()

# ==============================================================================
# FILTROS AVANÇADOS E CÁLCULO DE AUTONOMIA
# ==============================================================================
st.markdown("---")

min_date = df_base['DATA'].min().date()
max_date = df_base['DATA'].max().date()

with st.sidebar:
    st.header("🔍 Filtros Analíticos")
    datas = st.date_input("Período de Análise:", value=[min_date, max_date], min_value=min_date, max_value=max_date)

    cat_disponiveis = sorted(df_base['CATEGORIA_OPERACAO'].unique().tolist())
    default_cat = [c for c in cat_disponiveis if 'Saída' in c or 'Estorno' in c]
    f_categoria = st.multiselect("Categoria de Operação:", options=cat_disponiveis, default=default_cat)

    cc_disponiveis = sorted(df_base['CENTRO_CUSTO'].unique().tolist())
    f_cc = st.multiselect("Centro de Custo:", options=cc_disponiveis, default=[],
                          help="Filtre áreas ou equipamentos específicos.")

    mat_disponiveis = sorted(df_base['ITEM_COMPLETO'].dropna().unique().tolist())
    f_mat = st.multiselect("Material Específico (Opcional):", options=mat_disponiveis, default=[])

    st.markdown("---")
    st.markdown("##### 🖨️ Formato de Impressão (PDF)")
    orientacao_ui = st.radio("Selecione o formato:", ["Paisagem (Deitado)", "Retrato (Em pé)"], horizontal=True,
                             label_visibility="collapsed")
    orientacao_pdf = 'L' if 'Paisagem' in orientacao_ui else 'P'

if len(datas) == 2:
    d_in, d_out = datas[0], datas[1]
else:
    d_in = d_out = datas[0]

mask_data = (df_base['DATA'].dt.date >= d_in) & (df_base['DATA'].dt.date <= d_out)
if f_mat: mask_data = mask_data & (df_base['ITEM_COMPLETO'].isin(f_mat))
df_base_data_filtrada = df_base[mask_data].copy()

mask = mask_data
if f_categoria: mask = mask & (df_base['CATEGORIA_OPERACAO'].isin(f_categoria))
if f_cc: mask = mask & (df_base['CENTRO_CUSTO'].isin(f_cc))

df_view = df_base[mask]

df_estoque = df_estoque_base.copy()
if f_mat: df_estoque = df_estoque[df_estoque['ITEM_COMPLETO'].isin(f_mat)]

total_dias_filtro = max((d_out - d_in).days + 1, 1)
df_consumo_calc = df_view[df_view['CATEGORIA_OPERACAO'].str.contains('Saída|Estorno')]
consumo_por_item = df_consumo_calc.groupby('ITEM_COMPLETO')['QTD_DASHBOARD'].sum().reset_index()
consumo_por_item.columns = ['ITEM_COMPLETO', 'CONSUMO_PERIODO']
consumo_por_item['CONSUMO_MEDIO_DIA'] = consumo_por_item['CONSUMO_PERIODO'] / total_dias_filtro

df_autonomia = pd.merge(df_estoque, consumo_por_item, on='ITEM_COMPLETO', how='left').fillna(0)
df_autonomia['AUTONOMIA_DIAS'] = np.where(df_autonomia['CONSUMO_MEDIO_DIA'] > 0,
                                          df_autonomia['QTD_ATUAL'] / df_autonomia['CONSUMO_MEDIO_DIA'], np.inf)

# ==============================================================================
# DASHBOARD EXECUTIVO (GRADE DE MATERIAIS ESPECÍFICOS)
# ==============================================================================

if df_view.empty and df_estoque.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

st.markdown(
    f"**🗓️ Rastreio Volumétrico (Isolado por Material):** {d_in.strftime('%d/%m/%Y')} a {d_out.strftime('%d/%m/%Y')} ({total_dias_filtro} dias)")
st.caption("Visão exata do que foi consumido e reabastecido. **Não há misturas ou médias de materiais diferentes.**")

df_saida_ui = df_consumo_calc.groupby(['ITEM_COMPLETO', 'UNIDADE'])['QTD_DASHBOARD'].sum().reset_index(name='SAIDA')
df_entrada_ui = df_base_data_filtrada[df_base_data_filtrada['CATEGORIA_OPERACAO'] == 'Entrada (Abastecimento)'].groupby(
    ['ITEM_COMPLETO', 'UNIDADE'])['QTD_DASHBOARD'].sum().reset_index(name='ENTRADA')

df_kpi_ui = pd.merge(df_saida_ui, df_entrada_ui, on=['ITEM_COMPLETO', 'UNIDADE'], how='outer').fillna(0)
df_kpi_ui['BALANCO'] = df_kpi_ui['ENTRADA'] - df_kpi_ui['SAIDA']
df_kpi_ui = df_kpi_ui.sort_values('SAIDA', ascending=False)

if df_kpi_ui.empty:
    st.info("Nenhum fluxo volumétrico nos filtros selecionados.")
else:
    for i in range(0, len(df_kpi_ui), 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < len(df_kpi_ui):
                r = df_kpi_ui.iloc[i + j]
                draw_material_card(cols[j], r['ITEM_COMPLETO'], r['SAIDA'], r['ENTRADA'], r['UNIDADE'])

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# ABAS ANALÍTICAS DA UI INTERATIVA
# ==============================================================================
tab_evolucao, tab_maquinas, tab_estoque, tab_matriz, tab_transf, tab_tabela = st.tabs([
    "📈 Evolução de Consumo",
    "🚜 Perfil por C. Custo",
    "📦 Balanço de Estoque",
    "🧩 Matriz (C. Custo x Produto)",
    "🚚 Transferências",
    "📋 Extrato Bruto"
])

with tab_evolucao:
    st.markdown("##### ⛰️ Evolução Volumétrica Empilhada")
    st.caption("Visão da linha do tempo. A espessura das cores revela exatamente qual item gerou o pico do dia.")

    df_litros = df_consumo_calc[df_consumo_calc['UNIDADE'] == 'L']

    if not df_litros.empty:
        df_evo = df_litros.groupby([df_litros['DATA'].dt.date, 'ITEM_COMPLETO'])['QTD_DASHBOARD'].sum().reset_index()
        df_evo['MAT_SIMPLES'] = df_evo['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:30] + '...')

        top_5_mats = df_evo.groupby('MAT_SIMPLES')['QTD_DASHBOARD'].sum().nlargest(5).index
        df_evo['MATERIAL'] = np.where(df_evo['MAT_SIMPLES'].isin(top_5_mats), df_evo['MAT_SIMPLES'], 'Outros Materiais')
        df_evo = df_evo.groupby(['DATA', 'MATERIAL'])['QTD_DASHBOARD'].sum().reset_index()

        fig_evo = px.area(df_evo, x='DATA', y='QTD_DASHBOARD', color='MATERIAL',
                          line_group='MATERIAL', title="Consumo Diário por Produto (Litros)")
        fig_evo.update_traces(mode='lines+markers')
        fig_evo.update_layout(separators=".,", xaxis_title="Data", yaxis_title="Volume Consumido",
                              legend_title="Tipo de Fluido", margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_evo, use_container_width=True)

        st.markdown("---")
        c_burn1, c_burn2 = st.columns([1, 2])
        with c_burn1:
            st.markdown("##### 🔥 Velocidade de Consumo")
            if not consumo_por_item.empty:
                mat_top = consumo_por_item.sort_values('CONSUMO_MEDIO_DIA', ascending=False).iloc[0]
                nome_mat_top = mat_top['ITEM_COMPLETO'].split('\n')[0]
                st.info(
                    f"O produto de maior queima da operação é o **{nome_mat_top}**, atingindo uma velocidade de **{formatar_qtd(mat_top['CONSUMO_MEDIO_DIA'], '')}** por dia (baseado na média do período).")
            else:
                st.info("Não há histórico de queima suficiente para cálculo de velocidade.")

        with c_burn2:
            st.markdown("##### 📈 Curva de 'Queima' (Acumulado no Mês)")
            st.caption("Mostra a rapidez com que os tanques dos top 3 produtos estão a esvaziar ao longo do tempo.")
            top3_burn = df_litros.groupby('ITEM_COMPLETO')['QTD_DASHBOARD'].sum().nlargest(3).index
            if len(top3_burn) > 0:
                df_cum = df_litros[df_litros['ITEM_COMPLETO'].isin(top3_burn)].groupby(['DATA', 'ITEM_COMPLETO'])[
                    'QTD_DASHBOARD'].sum().reset_index()
                df_cum = df_cum.sort_values(['ITEM_COMPLETO', 'DATA'])
                df_cum['ACUMULADO'] = df_cum.groupby('ITEM_COMPLETO')['QTD_DASHBOARD'].cumsum()

                df_cum['MAT_SIMPLES'] = df_cum['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:30])

                fig_cum = px.line(df_cum, x='DATA', y='ACUMULADO', color='MAT_SIMPLES', markers=True)
                fig_cum.update_layout(separators=".,", xaxis_title="Data", yaxis_title="Litros Acumulados",
                                      legend_title="Produto", margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_cum, use_container_width=True)
    else:
        st.info("Nenhum consumo líquido registrado neste período.")

with tab_maquinas:
    st.markdown("##### 🚜 Rastreio Individual (C. Custo)")
    st.caption("Isola e audita o comportamento de um Centro de Custo específico.")

    if not df_consumo_calc.empty:
        top_ccs = df_consumo_calc.groupby('CENTRO_CUSTO')['QTD_DASHBOARD'].sum().nlargest(10).reset_index()

        c_sel, _ = st.columns([1, 2])
        cc_alvo = c_sel.selectbox("Selecione o Centro de Custo:",
                                  options=sorted(df_consumo_calc['CENTRO_CUSTO'].unique()), index=0)

        df_cc_isolado = df_consumo_calc[df_consumo_calc['CENTRO_CUSTO'] == cc_alvo].copy()

        c_m1, c_m2 = st.columns([1.5, 1])
        with c_m1:
            df_evo_cc = df_cc_isolado.groupby([df_cc_isolado['DATA'].dt.date, 'ITEM_COMPLETO'])[
                'QTD_DASHBOARD'].sum().reset_index()
            df_evo_cc['MAT_SIMPLES'] = df_evo_cc['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:30])

            fig_cc_line = px.bar(df_evo_cc, x='DATA', y='QTD_DASHBOARD', color='MAT_SIMPLES', barmode='stack',
                                 title=f"Histórico Diário: {cc_alvo}")
            fig_cc_line.update_layout(separators=".,", xaxis_title="Data", yaxis_title="Quantidade Consumida",
                                      legend_title="Produto")
            st.plotly_chart(fig_cc_line, use_container_width=True)

        with c_m2:
            st.markdown(f"###### 📊 O que {cc_alvo} consumiu:")
            resumo_mat = df_cc_isolado.groupby(['ITEM_COMPLETO', 'UNIDADE'])[
                'QTD_DASHBOARD'].sum().reset_index().sort_values('QTD_DASHBOARD', ascending=False)
            resumo_mat['ITEM_COMPLETO'] = resumo_mat['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:40])

            resumo_mat['QTD_FORMAT'] = resumo_mat.apply(lambda x: formatar_qtd(x['QTD_DASHBOARD'], x['UNIDADE']),
                                                        axis=1)

            st.dataframe(resumo_mat[['ITEM_COMPLETO', 'QTD_FORMAT']], hide_index=True,
                         column_config={"ITEM_COMPLETO": "Material", "QTD_FORMAT": "Quantidade Gasta"})
    else:
        st.info("Nenhum dado volumétrico disponível.")

with tab_estoque:
    st.markdown("##### 📦 Saúde e Autonomia do Estoque Físico")
    st.caption(
        "Visão do capital investido no comboio no momento e projeção de quantos dias cada item durará baseado na média de consumo.")

    if not df_autonomia.empty:
        c_est1, c_est2 = st.columns([1, 2])

        with c_est1:
            df_est_chart = df_autonomia.sort_values('VALOR_ATUAL', ascending=False).head(10)
            df_est_chart['DESC_CURTA'] = df_est_chart['DESCRICAO'].apply(lambda x: str(x)[:30] + '...')
            fig_est = px.bar(df_est_chart.sort_values('VALOR_ATUAL', ascending=True),
                             x='VALOR_ATUAL', y='DESC_CURTA', orientation='h',
                             color='VALOR_ATUAL', color_continuous_scale='Teal',
                             title="Top 10 Capital Parado (R$)")
            fig_est.update_traces(texttemplate='R$ %{x:,.2f}', textposition='outside', cliponaxis=False)
            fig_est.update_layout(separators=".,", yaxis={'categoryorder': 'total ascending'},
                                  xaxis_title="Valor Financeiro (R$)", yaxis_title="Material",
                                  margin=dict(l=10, r=40, t=30, b=10))
            st.plotly_chart(fig_est, use_container_width=True)

        with c_est2:
            df_table_auto = df_autonomia[
                ['ITEM_COMPLETO', 'QTD_ATUAL', 'UNIDADE', 'CONSUMO_MEDIO_DIA', 'AUTONOMIA_DIAS',
                 'VALOR_ATUAL']].sort_values('VALOR_ATUAL', ascending=False)
            st.dataframe(
                df_table_auto, use_container_width=True, hide_index=True, height=450,
                column_config={
                    "ITEM_COMPLETO": st.column_config.TextColumn("Material", width="large"),
                    "QTD_ATUAL": st.column_config.NumberColumn("Qtd Atual", format="%.2f"),
                    "UNIDADE": "UN",
                    "CONSUMO_MEDIO_DIA": st.column_config.NumberColumn("Consumo Diário", format="%.2f"),
                    "AUTONOMIA_DIAS": st.column_config.NumberColumn("Autonomia (Dias)", format="%.1f",
                                                                    help="Inf = Sem consumo no período"),
                    "VALOR_ATUAL": st.column_config.ProgressColumn("Valor no Tanque (R$)", format="R$ %.2f",
                                                                   min_value=0,
                                                                   max_value=float(df_table_auto['VALOR_ATUAL'].max()))
                }
            )
    else:
        st.info("Não há dados de estoque atualizados na base importada.")

with tab_matriz:
    st.markdown("##### 🧩 Matriz de Consumo Cruzado (C. Custo x Produto)")
    st.caption(
        "Visão rigorosa de quantidade (Litros / Peças) gasta por Centro de Custo. Cada coluna é um item independente.")

    if not df_consumo_calc.empty:
        df_matriz_copy = df_consumo_calc.copy()
        df_matriz_copy['MAT_SIMPLES'] = df_matriz_copy['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:40])

        pivot_ui = df_matriz_copy.pivot_table(index='CENTRO_CUSTO', columns='MAT_SIMPLES', values='QTD_DASHBOARD',
                                              aggfunc='sum').fillna(0)
        dict_unidades = df_matriz_copy.set_index('MAT_SIMPLES')['UNIDADE'].to_dict()


        def formata_celula(val, col_name):
            if val == 0: return "-"
            un = dict_unidades.get(col_name, '')
            fmt = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            if fmt.endswith(',00'): fmt = fmt[:-3]
            return f"{fmt} {un}"


        def cor_heatmap(s):
            max_col = s.max()
            if max_col == 0: max_col = 1
            pct = s / max_col
            return [
                'color: #9CA3AF;' if v == 0 else
                'background-color: #FECACA; color: #991B1B; font-weight: bold;' if p > 0.7 else
                'background-color: #FEF08A; color: #A16207;' if p > 0.3 else
                'background-color: #BBF7D0; color: #166534;'
                for v, p in zip(s, pct)
            ]


        format_dict = {col: lambda x, c=col: formata_celula(x, c) for col in pivot_ui.columns}
        styled_df = pivot_ui.style.apply(cor_heatmap, axis=0).format(format_dict)
        st.dataframe(styled_df, use_container_width=True, height=500)
    else:
        st.info("Nenhum dado de quantidade para renderizar a matriz cruzada.")

with tab_transf:
    st.markdown("##### 🚚 Matriz de Transferência (Almoxarifado ➔ Comboio)")
    st.caption(
        "Visão quantitativa de abastecimento do Comboio CB01. Acompanhe os dias e os itens exatos que foram inseridos no tanque.")

    df_transf_ui = df_base_data_filtrada[
        df_base_data_filtrada['CATEGORIA_OPERACAO'] == 'Entrada (Abastecimento)'].copy()
    if not df_transf_ui.empty:
        df_transf_ui['MAT_SIMPLES'] = df_transf_ui['ITEM_COMPLETO'].apply(lambda x: str(x).split('\n')[0][:40])

        pivot_transf = df_transf_ui.pivot_table(index=df_transf_ui['DATA'].dt.date, columns='MAT_SIMPLES',
                                                values='QTD_DASHBOARD', aggfunc='sum').fillna(0)
        pivot_transf.index = [d.strftime('%d/%m/%Y') for d in pivot_transf.index]
        dict_un_t = df_transf_ui.set_index('MAT_SIMPLES')['UNIDADE'].to_dict()


        def formata_transf(val, col_name):
            if val == 0: return "-"
            un = dict_un_t.get(col_name, '')
            fmt = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            if fmt.endswith(',00'): fmt = fmt[:-3]
            return f"{fmt} {un}"


        def cor_heatmap_t(s):
            max_col = s.max()
            if max_col == 0: max_col = 1
            pct = s / max_col
            return [
                'color: #9CA3AF;' if v == 0 else
                'background-color: #BFDBFE; color: #1E3A8A; font-weight: bold;' if p > 0.7 else
                'background-color: #DBEAFE; color: #1D4ED8;' if p > 0.3 else
                'background-color: #EFF6FF; color: #2563EB;'
                for v, p in zip(s, pct)
            ]


        format_dict_t = {col: lambda x, c=col: formata_transf(x, c) for col in pivot_transf.columns}
        styled_transf = pivot_transf.style.apply(cor_heatmap_t, axis=0).format(format_dict_t)
        st.dataframe(styled_transf, use_container_width=True, height=500)
    else:
        st.info("Nenhuma transferência do Almoxarifado para o Comboio registrada neste período.")

with tab_tabela:
    st.markdown("##### Extrato de Movimentações (Auditável)")

    colunas_exibir = ['DATA', 'OPERACAO_FULL', 'CENTRO_CUSTO', 'ITEM_COMPLETO', 'QTD_ORIGINAL_SAP', 'QTD_DASHBOARD',
                      'UNIDADE', 'VALOR_DASHBOARD']
    df_mostrar = df_view[colunas_exibir].sort_values(by=['DATA', 'VALOR_DASHBOARD'], ascending=[False, False])

    st.dataframe(
        df_mostrar, use_container_width=True, hide_index=True,
        column_config={
            "DATA": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "OPERACAO_FULL": "Operação",
            "CENTRO_CUSTO": "C. Custo",
            "ITEM_COMPLETO": st.column_config.TextColumn("Material Solicitado", width="large"),
            "QTD_ORIGINAL_SAP": st.column_config.NumberColumn("Qtd. SAP"),
            "QTD_DASHBOARD": st.column_config.NumberColumn("Qtd. Corrigida", format="%.2f"),
            "UNIDADE": "UN",
            "VALOR_DASHBOARD": st.column_config.NumberColumn("Valor Líquido", format="R$ %.2f")
        }
    )

st.markdown("---")
st.markdown("### 🖨️ Extração de Relatórios Oficiais")
st.caption("O PDF foi totalmente formatado para aproveitamento de espaço.")

with st.spinner("Desenhando relatório com layout otimizado..."):
    excel_bytes, pdf_bytes = compilar_relatorios_comboio_evolutivo(df_view, df_base_data_filtrada, df_estoque,
                                                                   df_autonomia, d_in, d_out, orientacao_pdf)

nome_padrao_arquivo = f"Comboio_Volumetrico_{d_in.strftime('%d%m')}_a_{d_out.strftime('%d%m')}"

c_pdf, c_excel = st.columns(2)
with c_pdf:
    st.download_button(label="📄 Descarregar Relatório PDF Evolutivo", data=pdf_bytes,
                       file_name=f"{nome_padrao_arquivo}.pdf", mime="application/pdf", type="primary",
                       use_container_width=True)
with c_excel:
    st.download_button(label="📊 Descarregar Matrizes (Excel)", data=excel_bytes,
                       file_name=f"{nome_padrao_arquivo}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)