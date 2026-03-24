import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import re
import plotly.express as px
import streamlit.components.v1 as components
from fpdf import FPDF
import tempfile
import sqlite3
from datetime import datetime

# --- BLINDAGEM E IMPORTAÇÃO DO BANCO DE DADOS ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils_ui import load_custom_css, ui_header, ui_kpi_card, ui_empty_state
    from utils_icons import get_icon
    from database import get_db_connection
except ImportError:
    def load_custom_css():
        pass


    def ui_header(title, subtitle, icon):
        st.title(f"{icon} {title}"); st.caption(subtitle)


    def ui_empty_state(msg, icon):
        st.info(f"{icon} {msg}")


    def get_icon(name, color, size="36"):
        return "🚜"


    def ui_kpi_card(col, title, value, icon, color, desc):
        with col:
            st.markdown(f"""
            <div style="background:white; padding:15px; border-radius:10px; border-left: 5px solid {color}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size:12px; color:#64748B;">{title}</div>
                <div style="font-size:24px; font-weight:bold; color:#1E293B;">{value}</div>
                <div style="font-size:11px; color:#94A3B8;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)


    def get_db_connection():
        return sqlite3.connect("manutencao.db")


# ==============================================================================
# INICIALIZAÇÃO DA TABELA DE HISTÓRICO (EVOLUÇÃO DIÁRIA)
# ==============================================================================
def criar_tabelas_historico():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_saude_pneus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_registro DATE,
            equip_cod TEXT,
            equip_desc TEXT,
            total_pos INTEGER,
            instalados INTEGER,
            ausentes INTEGER,
            percentual REAL
        )
    """)
    conn.commit()
    conn.close()


# Executa a verificação/criação ao abrir a página
criar_tabelas_historico()


def carregar_historico_salvo():
    conn = get_db_connection()
    df_hist = pd.read_sql("SELECT * FROM historico_saude_pneus ORDER BY data_registro ASC", conn)
    conn.close()
    if not df_hist.empty:
        df_hist['data_registro'] = pd.to_datetime(df_hist['data_registro']).dt.date
    return df_hist


# Tentativa segura de importar o matplotlib para gráficos na Capa do PDF
try:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# --- CONFIGURAÇÃO INICIAL ---
load_custom_css()

icon_pneu = get_icon("circle", "#F59E0B", "36")
ui_header(
    title="Controlo de Movimentação de Pneus",
    subtitle="Gestão da Borracharia, posições e auditoria visual de croquis da frota.",
    icon=icon_pneu
)


# ==============================================================================
# MOTOR DE PROCESSAMENTO DO EXCEL (LIMPEZA E BLINDAGEM)
# ==============================================================================

@st.cache_data(show_spinner="Processando estrutura de pneus e posições...", ttl=600)
def processar_dados_pneus(file):
    try:
        if file.name.lower().endswith('.csv'):
            try:
                df_raw = pd.read_csv(file, header=None, dtype=str, encoding='utf-8')
            except:
                file.seek(0)
                df_raw = pd.read_csv(file, header=None, dtype=str, encoding='latin-1')
        else:
            df_raw = pd.read_excel(file, header=None, dtype=str)

        df = df_raw.iloc[2:, 1:7].copy()
        df.columns = ['Equip_Cod', 'Equip_Desc', 'Pos_Cod', 'Pos_Desc', 'Pneu_Fogo', 'Pneu_Desc']

        df['Equip_Cod'] = df['Equip_Cod'].replace(['nan', 'NaN', 'None', ''], np.nan).ffill()
        df['Equip_Desc'] = df['Equip_Desc'].replace(['nan', 'NaN', 'None', ''], np.nan).ffill()

        df = df[df['Pos_Cod'].notna() & (df['Pos_Cod'].astype(str).str.lower() != 'nan')]
        df = df[~df['Pos_Cod'].astype(str).str.contains('Código', case=False, na=False)]

        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.replace('\n', ' ').str.replace('\r', '')

        df['Pneu_Fogo'] = df['Pneu_Fogo'].replace(['nan', 'NaN', 'None', ''], 'S/ FOGO').fillna('S/ FOGO')
        df['Pneu_Desc'] = df['Pneu_Desc'].replace(['nan', 'NaN', 'None', ''], 'SEM INFORMAÇÃO').fillna('SEM INFORMAÇÃO')

        df['Pneu_Fogo'] = df['Pneu_Fogo'].apply(lambda x: x[:-2] if str(x).endswith('.0') else x)

        df['Status'] = np.where(df['Pneu_Desc'].str.upper().str.contains('AUSENTE', na=False), 'Ausente', 'Instalado')

        def get_eixo(pos):
            match = re.search(r'(\d+)', str(pos))
            if match: return int(match.group(1))
            if str(pos).upper().startswith('T'): return 2
            return 1

        df['Eixo'] = df['Pos_Desc'].apply(get_eixo)

        def map_slot(pos):
            pos = str(pos).upper()
            if 'IE' in pos: return 'LI'
            if 'ID' in pos: return 'RI'
            if 'EE' in pos or re.search(r'\dE$', pos) or pos.endswith('E'): return 'LO'
            if 'ED' in pos or re.search(r'\dD$', pos) or pos.endswith('D'): return 'RO'
            return 'LO'

        df['Slot_Visual'] = df['Pos_Desc'].apply(map_slot)

        return df
    except Exception as e:
        st.error(f"Erro ao processar o ficheiro. Verifique o padrão de exportação. Detalhe: {e}")
        return None


# ==============================================================================
# MOTOR DE RENDERIZAÇÃO DO CROQUI NA TELA (HTML ISOLADO + INTERATIVIDADE)
# ==============================================================================

def gerar_html_croqui(df_equip):
    if df_equip.empty: return ""

    nome_equip = df_equip.iloc[0]['Equip_Desc']
    cod_equip = df_equip.iloc[0]['Equip_Cod']
    max_eixo = df_equip['Eixo'].max()

    axles_html = ""
    for eixo in range(1, max_eixo + 1):
        df_eixo = df_equip[df_equip['Eixo'] == eixo]
        if df_eixo.empty: continue

        p_lo = df_eixo[df_eixo['Slot_Visual'] == 'LO']
        p_li = df_eixo[df_eixo['Slot_Visual'] == 'LI']
        p_ri = df_eixo[df_eixo['Slot_Visual'] == 'RI']
        p_ro = df_eixo[df_eixo['Slot_Visual'] == 'RO']

        def build_tire(p_df):
            if p_df.empty: return ""
            row = p_df.iloc[0]
            pos = row['Pos_Desc']
            fogo = str(row['Pneu_Fogo'])
            desc_html = str(row['Pneu_Desc']).replace("'", "&#39;").replace('"', '&quot;')

            tooltip = f"<div class='tooltip'><b>ID:</b> {fogo}<br><b>Pos:</b> {pos}<br><b>Desc:</b> {desc_html}</div>"

            if row['Status'] == 'Ausente':
                return f"<div class='tire ausente'>{tooltip}<div class='tire-pos'>{pos}</div><div class='tire-fogo'>FALTA</div></div>"
            return f"<div class='tire installed'>{tooltip}<div class='tire-pos'>{pos}</div><div class='tire-fogo'>{fogo}</div></div>"

        axles_html += f"""
        <div class="axle-container">
            <div class="tire-group left">
                {build_tire(p_lo)}
                {build_tire(p_li)}
            </div>
            <div class="axle-bar">EIXO {eixo}</div>
            <div class="tire-group right">
                {build_tire(p_ri)}
                {build_tire(p_ro)}
            </div>
        </div>
        """

    html_completo = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; background-color: transparent; margin: 0; padding: 30px 20px; display: flex; flex-direction: column; align-items: center; }}
            .title-box {{ text-align: center; margin-bottom: 25px; background: white; padding: 15px 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #E2E8F0; z-index: 10; position: relative; }}
            .title-box h2 {{ margin: 0; color: #1E293B; font-size: 1.3rem; font-weight: 800; }}
            .title-box p {{ margin: 4px 0 0 0; color: #64748B; font-size: 0.85rem; font-weight: 600; }}
            .front-arrow {{ background: #E2E8F0; padding: 6px 24px; border-radius: 20px; font-weight: 800; color: #475569; margin-bottom: 35px; letter-spacing: 3px; font-size: 0.75rem; box-shadow: inset 0 1px 2px rgba(0,0,0,0.1); z-index: 10; position: relative; }}
            .chassis {{ position: relative; display: flex; flex-direction: column; gap: 50px; align-items: center; padding: 20px 0; width: 100%; }}
            .central-bar {{ position: absolute; width: 14px; background: #94A3B8; top: -20px; bottom: -20px; left: 50%; transform: translateX(-50%); border-radius: 8px; z-index: 1; box-shadow: inset 0 2px 4px rgba(0,0,0,0.2); }}
            .axle-container {{ display: flex; align-items: center; justify-content: center; position: relative; width: 100%; z-index: 2; }}
            .axle-bar {{ position: absolute; height: 18px; width: 220px; background: #475569; left: 50%; transform: translateX(-50%); border-radius: 10px; z-index: 1; display: flex; align-items: center; justify-content: center; color: white; font-size: 0.65rem; font-weight: 800; letter-spacing: 1px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }}
            .tire-group {{ display: flex; gap: 8px; z-index: 3; width: 140px; }}
            .tire-group.left {{ justify-content: flex-end; padding-right: 120px; }}
            .tire-group.right {{ justify-content: flex-start; padding-left: 120px; }}

            .tire {{ width: 55px; height: 100px; border-radius: 10px; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; box-shadow: 0 6px 12px rgba(0,0,0,0.3); transition: transform 0.2s; cursor: pointer; }}
            .tire:hover {{ transform: scale(1.05); z-index: 50; }}
            .tire.installed {{ background: #1E293B; border: 3px solid #0F172A; }}
            .tire.installed::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: repeating-linear-gradient(0deg, transparent, transparent 6px, rgba(255,255,255,0.05) 6px, rgba(255,255,255,0.05) 12px); border-radius: 6px; pointer-events: none; }}
            .tire.ausente {{ background: #FEF2F2; border: 2px dashed #EF4444; box-shadow: 0 0 15px rgba(239,68,68,0.2); }}
            .tire-pos {{ font-size: 0.65rem; font-weight: 800; z-index: 2; margin-bottom: 6px; text-align: center; }}
            .installed .tire-pos {{ color: #94A3B8; }}
            .ausente .tire-pos {{ color: #991B1B; }}
            .tire-fogo {{ font-size: 0.7rem; font-weight: 800; z-index: 2; padding: 3px 6px; border-radius: 4px; text-align: center; max-width: 90%; word-wrap: break-word; }}
            .installed .tire-fogo {{ background: rgba(0,0,0,0.7); color: #F8FAFC; border: 1px solid rgba(255,255,255,0.1); }}
            .ausente .tire-fogo {{ color: #DC2626; font-size: 0.6rem; }}

            /* TOOLTIP INTERATIVO */
            .tooltip {{
                visibility: hidden;
                width: 160px;
                background-color: rgba(15, 23, 42, 0.95);
                color: #F8FAFC;
                text-align: center;
                border-radius: 8px;
                padding: 10px;
                position: absolute;
                z-index: 100;
                bottom: 110%;
                left: 50%;
                transform: translateX(-50%);
                opacity: 0;
                transition: opacity 0.3s;
                font-size: 0.7rem;
                font-weight: 500;
                line-height: 1.4;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
                border: 1px solid #334155;
                pointer-events: none;
            }}
            .tooltip b {{ color: #38BDF8; font-weight: 800; }}
            .tooltip::after {{
                content: "";
                position: absolute;
                top: 100%;
                left: 50%;
                margin-left: -6px;
                border-width: 6px;
                border-style: solid;
                border-color: rgba(15, 23, 42, 0.95) transparent transparent transparent;
            }}
            .tire:hover .tooltip {{
                visibility: visible;
                opacity: 1;
            }}
        </style>
    </head>
    <body>
        <div class="title-box">
            <h2>{nome_equip}</h2>
            <p>CÓD: {cod_equip}</p>
        </div>
        <div class="front-arrow">SENTIDO DE MARCHA ⬆</div>
        <div class="chassis">
            <div class="central-bar"></div>
            {axles_html}
        </div>
    </body>
    </html>
    """
    return html_completo


# ==============================================================================
# MOTOR DE RENDERIZAÇÃO VETORIAL DO CROQUI PARA PDF E CAPA GERENCIAL
# ==============================================================================

class CroquiPDF(FPDF):
    def __init__(self, orientacao='L', *args, **kwargs):
        super().__init__(orientation=orientacao, *args, **kwargs)
        self.orientacao = orientacao
        self.largura_util = 277 if orientacao == 'L' else 190

    def header(self):
        caminho_logo = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logo_cedro.png")
        if os.path.exists(caminho_logo):
            self.image(caminho_logo, 10, 8, 12)

        self.set_font('Arial', 'B', 14)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, 'Caderno de Inspecao de Pneus e Croquis - Cedro', 0, 1, 'C')

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
        self.cell(0, 10, texto_rodape, 0, 0, 'C')


@st.cache_data(show_spinner="Desenhando capa e croquis vetoriais para o PDF...", ttl=600)
def gerar_pdf_pneus_frota(df, orientacao_pdf='L', filtros=None):
    if filtros is None: filtros = {}

    pdf = CroquiPDF(orientacao=orientacao_pdf, unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    arquivos_temp = []
    w_total = 277 if orientacao_pdf == 'L' else 190
    max_y_page = 190 if orientacao_pdf == 'L' else 277

    # PÁGINA 1: CAPA (RESUMO EXECUTIVO DA FROTA)
    pdf.set_font('Arial', 'B', 18)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 10, "Resumo Executivo da Frota", 0, 1, 'C')

    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(100, 116, 139)
    filtro_txt = f"Filtros: Status ({filtros.get('status', 'Todos')}) | Tipos ({filtros.get('tipo', 'Todos')}) | Fogo ({filtros.get('fogo', 'Nenhum')}) | Excluidas ({filtros.get('excluidas', 'Nenhuma')})"
    pdf.cell(0, 5, filtro_txt.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'C')
    pdf.ln(8)

    total_equip = df['Equip_Cod'].nunique()
    frotas_falta = df[df['Status'] == 'Ausente']['Equip_Cod'].nunique()
    total_pneus = len(df[df['Status'] == 'Instalado'])
    ausentes = len(df[df['Status'] == 'Ausente'])

    y_kpi = pdf.get_y()
    w_card = (w_total - 15) / 4

    def draw_kpi_card(x, y, w, title, value, color_r, color_g, color_b):
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(x, y, w, 20, 'DF')
        pdf.set_fill_color(color_r, color_g, color_b)
        pdf.rect(x, y, 2, 20, 'F')
        pdf.set_font('Arial', 'B', 7)
        pdf.set_text_color(100, 116, 139)
        pdf.set_xy(x + 4, y + 4)
        pdf.cell(w - 6, 4, title.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'L')
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(30, 41, 59)
        pdf.set_xy(x + 4, y + 10)
        pdf.cell(w - 6, 6, str(value), 0, 1, 'L')

    draw_kpi_card(10, y_kpi, w_card, "FROTAS MAPEADAS", total_equip, 59, 130, 246)
    draw_kpi_card(10 + w_card + 5, y_kpi, w_card, "FROTAS C/ FALTA", frotas_falta, 239, 68, 68)
    draw_kpi_card(10 + 2 * (w_card + 5), y_kpi, w_card, "PNEUS INSTALADOS", total_pneus, 16, 185, 129)
    draw_kpi_card(10 + 3 * (w_card + 5), y_kpi, w_card, "POSICOES VAZIAS", ausentes, 245, 158, 11)

    pdf.set_y(y_kpi + 28)

    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 6, "Analise Geral de Calibragem e Posicoes", 0, 1, 'L')

    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(80, 80, 80)
    pct_faltas = (ausentes / (total_pneus + ausentes) * 100) if (total_pneus + ausentes) > 0 else 0
    texto_resumo = f"Este relatorio audita e detalha {total_equip} maquinas/implementos da operacao baseado no filtro selecionado. " \
                   f"Atualmente, a taxa de posicoes descalcadas e de {pct_faltas:.1f}% ({ausentes} pneus ausentes na base). " \
                   f"Registamos {frotas_falta} maquinas circulando com pendencia ou falha na montagem de borracha. " \
                   f"Abaixo seguem os principais indicadores, e nas paginas seguintes a visao do croqui."
    pdf.multi_cell(0, 5, texto_resumo.encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(6)

    if MATPLOTLIB_AVAILABLE and not df.empty:
        fig_w = 10 if orientacao_pdf == 'L' else 7.5
        fig_h = 3.8 if orientacao_pdf == 'L' else 3.5
        fig, axes = plt.subplots(1, 2, figsize=(fig_w, fig_h))

        s_counts = df['Status'].value_counts()
        colors = ['#10B981' if s == 'Instalado' else '#EF4444' for s in s_counts.index]
        axes[0].pie(s_counts, labels=s_counts.index, autopct='%1.1f%%', colors=colors, startangle=90,
                    wedgeprops={'width': 0.4, 'edgecolor': 'w'})
        axes[0].set_title('Saude das Posicoes', fontsize=10, fontweight='bold', color='#333333')

        df_ausentes = df[df['Status'] == 'Ausente']
        if not df_ausentes.empty:
            top_ausentes = df_ausentes['Equip_Cod'].value_counts().head(5).sort_values(ascending=True)
            axes[1].barh(top_ausentes.index.astype(str), top_ausentes.values, color='#EF4444')
            axes[1].set_title('Frotas c/ Mais Ausencias (Top 5)', fontsize=10, fontweight='bold', color='#333333')
        else:
            top_eq = df['Equip_Desc'].value_counts().head(5).sort_values(ascending=True)
            axes[1].barh(top_eq.index.astype(str).str.slice(0, 15), top_eq.values, color='#3B82F6')
            axes[1].set_title('Tipos de Frota Mapeados (Top 5)', fontsize=10, fontweight='bold', color='#333333')

        axes[1].xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        axes[1].spines['top'].set_visible(False)
        axes[1].spines['right'].set_visible(False)
        axes[1].spines['bottom'].set_color('#CCCCCC')
        axes[1].spines['left'].set_color('#CCCCCC')
        axes[1].tick_params(axis='both', labelsize=8, colors='#555555')

        plt.tight_layout()
        img_path = tempfile.mktemp(suffix=".png")
        arquivos_temp.append(img_path)
        fig.savefig(img_path, dpi=200, bbox_inches='tight')
        plt.close(fig)

        img_width = 240 if orientacao_pdf == 'L' else 170
        img_x = (w_total + 20 - img_width) / 2
        pdf.image(img_path, x=img_x, y=pdf.get_y(), w=img_width)

    pdf.add_page()

    # PÁGINAS SEGUINTES: CROQUIS VETORIAIS
    frotas = df['Equip_Cod'].unique()

    for frota in frotas:
        df_f = df[df['Equip_Cod'] == frota].copy()
        nome_equip = df_f.iloc[0]['Equip_Desc']
        max_eixo = df_f['Eixo'].max()

        axle_spacing = 16
        tire_w = 14
        tire_h = 13

        croqui_h = 10 + (max_eixo * axle_spacing) + 5
        table_h = 6 + (len(df_f) * 4)
        block_h = max(croqui_h, table_h) + 10

        if pdf.get_y() + block_h > max_y_page:
            pdf.add_page()

        y_start_block = pdf.get_y()

        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(30, 41, 59)
        pdf.set_xy(10, y_start_block)
        pdf.cell(80, 4, f"{nome_equip[:30]} (Cód: {frota})".encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'L')

        y_content = pdf.get_y() + 2

        center_x = 42 if orientacao_pdf == 'P' else 50
        y_start_croqui = y_content + 4

        pdf.set_fill_color(226, 232, 240)
        pdf.rect(center_x - 12, y_start_croqui - 4, 24, 3, 'F')
        pdf.set_font('Arial', 'B', 4.5)
        pdf.set_text_color(71, 85, 105)
        pdf.set_xy(center_x - 12, y_start_croqui - 4)
        pdf.cell(24, 3, "FRENTE", 0, 0, 'C')

        chassi_h = (max_eixo * axle_spacing) if max_eixo > 0 else axle_spacing
        pdf.set_fill_color(148, 163, 184)
        pdf.rect(center_x - 1.5, y_start_croqui, 3, chassi_h, 'F')

        for eixo in range(1, max_eixo + 1):
            df_e = df_f[df_f['Eixo'] == eixo]
            y_axle = y_start_croqui + (eixo - 1) * axle_spacing + 1

            pdf.set_fill_color(71, 85, 105)
            pdf.rect(center_x - 22, y_axle + (tire_h / 2) - 1, 44, 2, 'F')

            pdf.set_fill_color(71, 85, 105)
            pdf.rect(center_x - 6, y_axle + (tire_h / 2) - 2, 12, 4, 'F')
            pdf.set_xy(center_x - 6, y_axle + (tire_h / 2) - 2)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 4)
            pdf.cell(12, 4, f"EIXO {eixo}", 0, 0, 'C')

            def draw_tire(p_df, pos_type):
                if p_df.empty: return
                row = p_df.iloc[0]

                if pos_type == 'LO':
                    tx = center_x - 23 - tire_w
                elif pos_type == 'LI':
                    tx = center_x - 8 - tire_w
                elif pos_type == 'RI':
                    tx = center_x + 8
                elif pos_type == 'RO':
                    tx = center_x + 23
                else:
                    return

                ty = y_axle
                pos_str = str(row['Pos_Desc'])[:5].strip().encode('latin-1', 'replace').decode('latin-1')
                fogo_str = str(row['Pneu_Fogo'])[:8].strip().encode('latin-1', 'replace').decode('latin-1')

                if row['Status'] == 'Ausente':
                    pdf.set_fill_color(254, 242, 242)
                    pdf.set_draw_color(239, 68, 68)
                    pdf.rect(tx, ty, tire_w, tire_h, 'FD')

                    pdf.set_text_color(153, 27, 27)
                    pdf.set_font('Arial', 'B', 4.5)
                    pdf.set_xy(tx, ty + 1.5)
                    pdf.cell(tire_w, 3, pos_str, 0, 0, 'C')

                    pdf.set_font('Arial', 'B', 4.5)
                    pdf.set_xy(tx, ty + 7.5)
                    pdf.cell(tire_w, 3, "FALTA", 0, 0, 'C')
                else:
                    pdf.set_fill_color(30, 41, 59)
                    pdf.set_draw_color(15, 23, 42)
                    pdf.rect(tx, ty, tire_w, tire_h, 'FD')

                    pdf.set_text_color(148, 163, 184)
                    pdf.set_font('Arial', 'B', 4.5)
                    pdf.set_xy(tx, ty + 1.5)
                    pdf.cell(tire_w, 3, pos_str, 0, 0, 'C')

                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font('Arial', 'B', 4.5)
                    pdf.set_xy(tx, ty + 7.5)
                    pdf.cell(tire_w, 3, fogo_str, 0, 0, 'C')

            draw_tire(df_e[df_e['Slot_Visual'] == 'LO'], 'LO')
            draw_tire(df_e[df_e['Slot_Visual'] == 'LI'], 'LI')
            draw_tire(df_e[df_e['Slot_Visual'] == 'RI'], 'RI')
            draw_tire(df_e[df_e['Slot_Visual'] == 'RO'], 'RO')

        y_croqui_end = y_start_croqui + chassi_h + 5

        y_table_start = y_start_block

        if orientacao_pdf == 'L':
            x_table = 95
            w_cols = [15, 20, 30, 20, 95]
            desc_len = 65
        else:
            x_table = 85
            w_cols = [9, 11, 20, 15, 48]
            desc_len = 24

        pdf.set_xy(x_table, y_table_start)
        pdf.set_font('Arial', 'B', 7)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 4, "Detalhamento de Posicoes", 0, 1, 'L')

        pdf.set_xy(x_table, pdf.get_y())
        pdf.set_fill_color(226, 232, 240)
        pdf.set_text_color(71, 85, 105)
        pdf.set_font('Arial', 'B', 5 if orientacao_pdf == 'P' else 6)
        pdf.set_draw_color(255, 255, 255)

        pdf.cell(w_cols[0], 4, " Pos.", 1, 0, 'C', fill=True)
        pdf.cell(w_cols[1], 4, " Local", 1, 0, 'C', fill=True)
        pdf.cell(w_cols[2], 4, " Num Fogo", 1, 0, 'C', fill=True)
        pdf.cell(w_cols[3], 4, " Situacao", 1, 0, 'C', fill=True)
        pdf.cell(w_cols[4], 4, " Descricao do Pneu", 1, 1, 'L', fill=True)

        pdf.set_font('Arial', '', 5 if orientacao_pdf == 'P' else 6)
        pdf.set_draw_color(230, 230, 230)
        fill = False

        for _, row in df_f.iterrows():
            pdf.set_xy(x_table, pdf.get_y())

            if fill:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(255, 255, 255)

            pdf.set_text_color(40, 40, 40)
            pdf.cell(w_cols[0], 4, str(row['Pos_Cod'])[:8].strip().encode('latin-1', 'replace').decode('latin-1'), 'B',
                     0, 'C', fill=fill)
            pdf.cell(w_cols[1], 4, str(row['Pos_Desc'])[:10].strip().encode('latin-1', 'replace').decode('latin-1'),
                     'B', 0, 'C', fill=fill)
            pdf.cell(w_cols[2], 4, str(row['Pneu_Fogo'])[:15].strip().encode('latin-1', 'replace').decode('latin-1'),
                     'B', 0, 'C', fill=fill)

            if row['Status'] == 'Ausente':
                pdf.set_text_color(220, 38, 38)
            else:
                pdf.set_text_color(22, 163, 74)
            pdf.cell(w_cols[3], 4, str(row['Status']).upper()[:10].encode('latin-1', 'replace').decode('latin-1'), 'B',
                     0, 'C', fill=fill)

            pdf.set_text_color(40, 40, 40)
            desc_limpa = str(row['Pneu_Desc']).replace('nan', 'SEM INFO').strip()
            pdf.cell(w_cols[4], 4, f" {desc_limpa[:desc_len]}".encode('latin-1', 'replace').decode('latin-1'), 'B', 1,
                     'L', fill=fill)

            fill = not fill

        y_table_end = pdf.get_y()

        next_y = max(y_croqui_end, y_table_end) + 4
        pdf.set_y(next_y)

        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, next_y - 2, w_total + 10, next_y - 2)

    # ==============================================================================
    # PÁGINA FINAL: SCORE DE SAÚDE DA FROTA (NOVA FUNCIONALIDADE)
    # ==============================================================================
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(22, 102, 53)
    pdf.cell(0, 10, "Quadro Analitico: Score de Saude por Maquina", 0, 1, 'C')

    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, "Consolidacao automatica do percentual de pneus instalados para cada equipamento auditado.", 0, 1,
             'C')
    pdf.ln(6)

    df_health = df.groupby(['Equip_Cod', 'Equip_Desc']).agg(
        Total_Pos=('Pos_Cod', 'count'),
        Instalados=('Status', lambda x: (x == 'Instalado').sum())
    ).reset_index()

    df_health['Percentual'] = (df_health['Instalados'] / df_health['Total_Pos']) * 100
    df_health['Faltas'] = df_health['Total_Pos'] - df_health['Instalados']
    df_health = df_health.sort_values(by=['Percentual', 'Faltas'], ascending=[True, False])

    if orientacao_pdf == 'L':
        w_h = [40, 117, 30, 30, 30, 30]
    else:
        w_h = [25, 65, 25, 25, 25, 25]

    def cabecalho_health():
        pdf.set_font('Arial', 'B', 8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(22, 102, 53)
        pdf.set_draw_color(255, 255, 255)

        pdf.cell(w_h[0], 7, " Maquina", 1, 0, 'C', fill=True)
        pdf.cell(w_h[1], 7, " Descricao", 1, 0, 'L', fill=True)
        pdf.cell(w_h[2], 7, " Posicoes", 1, 0, 'C', fill=True)
        pdf.cell(w_h[3], 7, " Instalados", 1, 0, 'C', fill=True)
        pdf.cell(w_h[4], 7, " Faltas", 1, 0, 'C', fill=True)
        pdf.cell(w_h[5], 7, " % Calcado", 1, 1, 'C', fill=True)

    cabecalho_health()

    pdf.set_font('Arial', 'B', 7)
    pdf.set_draw_color(230, 230, 230)
    fill = False

    for _, row in df_health.iterrows():
        if pdf.get_y() > max_y_page - 10:
            pdf.add_page()
            cabecalho_health()
            pdf.set_font('Arial', 'B', 7)

        if fill:
            pdf.set_fill_color(245, 247, 250)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.set_text_color(40, 40, 40)
        pdf.cell(w_h[0], 6, str(row['Equip_Cod'])[:15], 'B', 0, 'C', fill=fill)
        desc_limpa = str(row['Equip_Desc']).encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(w_h[1], 6, f" {desc_limpa[:45]}", 'B', 0, 'L', fill=fill)

        pdf.cell(w_h[2], 6, str(row['Total_Pos']), 'B', 0, 'C', fill=fill)
        pdf.cell(w_h[3], 6, str(row['Instalados']), 'B', 0, 'C', fill=fill)

        if row['Faltas'] > 0:
            pdf.set_text_color(220, 38, 38)
        else:
            pdf.set_text_color(40, 40, 40)
        pdf.cell(w_h[4], 6, str(row['Faltas']), 'B', 0, 'C', fill=fill)

        if row['Percentual'] == 100:
            pdf.set_text_color(22, 163, 74)
        elif row['Percentual'] >= 70:
            pdf.set_text_color(161, 98, 7)
        else:
            pdf.set_text_color(220, 38, 38)

        pdf.cell(w_h[5], 6, f"{row['Percentual']:.1f}%", 'B', 1, 'C', fill=fill)
        fill = not fill

    # Salvamento do arquivo
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = tmp.name
    tmp.close()

    pdf.output(pdf_path)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    os.remove(pdf_path)

    for img in arquivos_temp:
        try:
            os.remove(img)
        except:
            pass

    return pdf_bytes


# ==============================================================================
# INTERFACE PRINCIPAL
# ==============================================================================

if 'dataset_pneus' not in st.session_state:
    st.session_state['dataset_pneus'] = None

with st.expander("📂 Importar Relatório da Borracharia (DADOS.xlsx)",
                 expanded=(st.session_state['dataset_pneus'] is None)):
    file_up = st.file_uploader("Anexe o relatório de Posições (Excel ou CSV exportado)", type=['xlsx', 'csv'])
    if file_up and st.button("Processar Croquis 🚜", type="primary"):
        df_pneus = processar_dados_pneus(file_up)
        if df_pneus is not None:
            st.session_state['dataset_pneus'] = df_pneus
            st.rerun()

if st.session_state['dataset_pneus'] is None:
    ui_empty_state("Aguardando importação do relatório para gerar os croquis visuais.", icon="🛞")
    st.stop()

df = st.session_state['dataset_pneus']

# ==============================================================================
# BARRA LATERAL: FILTROS E SALVAMENTO DE HISTÓRICO
# ==============================================================================
with st.sidebar:
    st.header("🔍 Filtros de Busca")

    filtro_status_frota = st.radio(
        "Status da Frota:",
        ["Todas as Frotas", "🚨 Com Pneus Ausentes", "✅ 100% Calçadas"],
        help="Filtra a lista de frotas e o PDF gerado."
    )

    tipos_equip = sorted(df['Equip_Desc'].dropna().unique().tolist())
    filtro_tipo = st.multiselect("Tipo de Equipamento:", options=tipos_equip, placeholder="Selecione (Opcional)")

    busca_fogo = st.text_input("🔎 Buscar por Nº de Fogo (ID):", placeholder="Ex: 912460",
                               help="Encontra a frota que está com este pneu exato.")

    st.markdown("---")

    frotas_disponiveis = sorted(df['Equip_Cod'].dropna().unique().tolist())
    filtro_excluir_frota = st.multiselect(
        "🚫 Ocultar Frota(s):",
        options=frotas_disponiveis,
        placeholder="Excluir do relatório (Opcional)",
        help="As frotas selecionadas aqui serão removidas do painel e não sairão no relatório PDF."
    )

    st.markdown("---")
    st.markdown("##### 💾 Histórico Diário")
    st.caption("Salve o status global para acompanhar a evolução na aba de Histórico.")
    if st.button("Gravar Posição do Dia", use_container_width=True, type="primary"):
        # Recalcula a saúde para a frota completa (ignorando os filtros laterais)
        df_health_total = df.groupby(['Equip_Cod', 'Equip_Desc']).agg(
            Total_Pos=('Pos_Cod', 'count'),
            Instalados=('Status', lambda x: (x == 'Instalado').sum())
        ).reset_index()

        df_health_total['Percentual'] = (df_health_total['Instalados'] / df_health_total['Total_Pos']) * 100
        df_health_total['Faltas'] = df_health_total['Total_Pos'] - df_health_total['Instalados']

        conn = get_db_connection()
        cursor = conn.cursor()
        data_atual = datetime.now().date()

        # Apaga o registro de hoje se já existir para não duplicar (mantém o snapshot mais recente do dia)
        cursor.execute("DELETE FROM historico_saude_pneus WHERE data_registro = ?", (data_atual,))

        for _, row in df_health_total.iterrows():
            cursor.execute("""
                INSERT INTO historico_saude_pneus (data_registro, equip_cod, equip_desc, total_pos, instalados, ausentes, percentual)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (data_atual, row['Equip_Cod'], row['Equip_Desc'], row['Total_Pos'], row['Instalados'], row['Faltas'],
                  row['Percentual']))

        conn.commit()
        conn.close()
        st.toast("Posição do dia salva no Histórico!", icon="✅")
        # Usa um pequeno delay para o toast aparecer antes de recarregar
        import time;

        time.sleep(1);
        st.rerun()

# --- APLICAÇÃO DOS FILTROS ---
frotas_validas = df['Equip_Cod'].unique().tolist()

if filtro_status_frota == "🚨 Com Pneus Ausentes":
    frotas_com_ausencia = df[df['Status'] == 'Ausente']['Equip_Cod'].unique()
    frotas_validas = [f for f in frotas_validas if f in frotas_com_ausencia]
elif filtro_status_frota == "✅ 100% Calçadas":
    frotas_com_ausencia = df[df['Status'] == 'Ausente']['Equip_Cod'].unique()
    frotas_validas = [f for f in frotas_validas if f not in frotas_com_ausencia]

if filtro_tipo:
    frotas_do_tipo = df[df['Equip_Desc'].isin(filtro_tipo)]['Equip_Cod'].unique()
    frotas_validas = [f for f in frotas_validas if f in frotas_do_tipo]

if busca_fogo:
    fogo_limpo = str(busca_fogo).strip().upper()
    frotas_com_fogo = df[df['Pneu_Fogo'].str.upper().str.contains(fogo_limpo, na=False)]['Equip_Cod'].unique()
    frotas_validas = [f for f in frotas_validas if f in frotas_com_fogo]

if filtro_excluir_frota:
    frotas_validas = [f for f in frotas_validas if f not in filtro_excluir_frota]

df_view = df[df['Equip_Cod'].isin(frotas_validas)].copy()

st.markdown("---")

# --- KPIs GERAIS ---
total_equip = df_view['Equip_Cod'].nunique()
total_pneus = len(df_view[df_view['Status'] == 'Instalado'])
ausentes = len(df_view[df_view['Status'] == 'Ausente'])

c1, c2, c3 = st.columns(3)
ui_kpi_card(c1, "Frotas Filtradas", f"{total_equip}", "🚜", "#3B82F6", "Máquinas no contexto atual")
ui_kpi_card(c2, "Pneus Instalados", f"{total_pneus}", "🛞", "#10B981", "Rodando atualmente nestas máquinas")
ui_kpi_card(c3, "Faltas (Ausentes)", f"{ausentes}", "🚨", "#EF4444" if ausentes > 0 else "#10B981",
            "Posições vazias detetadas")

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# ALERTAS GLOBAIS (VALIDAÇÃO DE ANOMALIAS E FALTAS)
# ==============================================================================

# Validador de Anomalias (Pneus Clonados)
df_valid_tires = df_view[~df_view['Pneu_Fogo'].isin(['S/ FOGO', 'FALTA', ''])]
duplicados = df_valid_tires.groupby('Pneu_Fogo')['Equip_Cod'].nunique()
pneus_clonados = duplicados[duplicados > 1].index.tolist()

if pneus_clonados:
    st.error(
        f"🚨 **ALERTA DE ANOMALIA:** Foram detetados **{len(pneus_clonados)} pneus** apontados em mais de uma máquina simultaneamente! Isso indica erro de digitação no sistema PIMS.")
    with st.expander("🔍 Ver Pneus Clonados e Máquinas Afetadas"):
        df_clonados = df_valid_tires[df_valid_tires['Pneu_Fogo'].isin(pneus_clonados)][
            ['Pneu_Fogo', 'Equip_Cod', 'Equip_Desc', 'Pos_Desc']].copy()
        df_clonados = df_clonados.sort_values('Pneu_Fogo')
        st.dataframe(
            df_clonados,
            column_config={
                "Pneu_Fogo": st.column_config.TextColumn("Nº Fogo Clonado"),
                "Equip_Cod": "Máquina",
                "Equip_Desc": "Descrição da Máquina",
                "Pos_Desc": "Posição"
            },
            hide_index=True, use_container_width=True
        )

# Alerta de Frotas com Pneus Ausentes
df_alertas = df_view[df_view['Status'] == 'Ausente']
if not df_alertas.empty:
    frotas_alerta = df_alertas['Equip_Cod'].unique()
    st.warning(f"⚠️ **{len(frotas_alerta)} máquinas** no seu filtro estão com pneu ausente!")
    with st.expander("Ver Frotas Críticas"):
        for f in frotas_alerta:
            desc = df_view[df_view['Equip_Cod'] == f].iloc[0]['Equip_Desc']
            st.markdown(f"🔴 **{f}** - {desc}")
else:
    st.success("✅ Frota 100% calçada neste filtro. Tudo em ordem!")

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# ABAS DA INTERFACE PRINCIPAL
# ==============================================================================
tab_dash, tab_croqui, tab_saude, tab_evolucao = st.tabs(
    ["📈 Dashboard Executivo", "🔍 Inspeção Visual (Croqui)", "💯 Saúde da Frota", "📉 Evolução Histórica"])

with tab_dash:
    st.markdown("##### Visão Geral da Frota Filtrada")
    if not df_view.empty:
        c_dash1, c_dash2 = st.columns([1, 1.5])

        with c_dash1:
            s_counts = df_view['Status'].value_counts().reset_index()
            s_counts.columns = ['Status', 'Quantidade']
            fig_pie = px.pie(s_counts, values='Quantidade', names='Status', hole=0.5,
                             color='Status', color_discrete_map={'Instalado': '#10B981', 'Ausente': '#EF4444'},
                             title="Saúde das Posições (%)")
            fig_pie.update_layout(margin=dict(t=40, b=20, l=10, r=10), showlegend=True,
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            st.plotly_chart(fig_pie, use_container_width=True)

        with c_dash2:
            if not df_alertas.empty:
                top_ausentes_web = df_alertas['Equip_Cod'].value_counts().head(10).reset_index()
                top_ausentes_web.columns = ['Equipamento', 'Faltas']
                top_ausentes_web['Equipamento'] = top_ausentes_web['Equipamento'].astype(str)

                fig_bar = px.bar(top_ausentes_web.sort_values('Faltas', ascending=True),
                                 x='Faltas', y='Equipamento', orientation='h',
                                 title="Top Frotas com Mais Ausências",
                                 color_discrete_sequence=['#EF4444'], text_auto=True)
                fig_bar.update_layout(xaxis_title="Qtd de Pneus Ausentes", yaxis_title="Máquina",
                                      margin=dict(t=40, b=20, l=10, r=10), yaxis={'type': 'category'})
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                top_eq_web = df_view['Equip_Desc'].value_counts().head(10).reset_index()
                top_eq_web.columns = ['Tipo', 'Quantidade']
                top_eq_web['Tipo'] = top_eq_web['Tipo'].astype(str)

                fig_bar = px.bar(top_eq_web.sort_values('Quantidade', ascending=True),
                                 x='Quantidade', y='Tipo', orientation='h',
                                 title="Perfil da Frota (Tipos Mapeados)",
                                 color_discrete_sequence=['#3B82F6'], text_auto=True)
                fig_bar.update_layout(xaxis_title="Qtd de Posições Mapeadas", yaxis_title="Tipo de Máquina",
                                      margin=dict(t=40, b=20, l=10, r=10), yaxis={'type': 'category'})
                st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Sem dados para apresentar gráficos.")

with tab_croqui:
    st.markdown("##### Seletor de Equipamento")
    if df_view.empty:
        st.warning("Nenhuma frota encontrada com os filtros selecionados na barra lateral.")
        frota_selecionada = None
    else:
        lista_frotas = df_view.apply(lambda x: f"{x['Equip_Cod']} - {x['Equip_Desc']}", axis=1).unique().tolist()
        frota_selecionada = st.selectbox("Selecione a máquina para renderizar o croqui interativo:",
                                         sorted(lista_frotas), label_visibility="collapsed")

    if frota_selecionada and not df_view.empty:
        st.markdown("---")
        cod_selecionado = frota_selecionada.split(" - ")[0]
        df_frota = df_view[df_view['Equip_Cod'] == cod_selecionado]

        col_croqui, col_dados = st.columns([1.2, 1.5])

        with col_croqui:
            html_seguro = gerar_html_croqui(df_frota)
            components.html(html_seguro, height=750, scrolling=True)

        with col_dados:
            st.markdown("#### 📋 Detalhamento das Posições")

            df_exibir = df_frota[['Pos_Cod', 'Pos_Desc', 'Pneu_Fogo', 'Status', 'Pneu_Desc']].copy()


            def highlight_fogo(val):
                if busca_fogo and str(busca_fogo).strip().upper() in str(val).upper():
                    return 'background-color: #FEF08A; color: #9A3412; font-weight: bold;'
                return ''


            styled_df = df_exibir.style.map(highlight_fogo, subset=['Pneu_Fogo'])

            st.dataframe(
                styled_df,
                column_config={
                    "Pos_Cod": "Pos",
                    "Pos_Desc": "Local",
                    "Pneu_Fogo": st.column_config.TextColumn("Nº Fogo", width="medium"),
                    "Status": st.column_config.TextColumn("Situação"),
                    "Pneu_Desc": st.column_config.TextColumn("Descrição do Pneu", width="large")
                },
                hide_index=True,
                use_container_width=True,
                height=600
            )

with tab_saude:
    st.markdown("##### Score de Saúde por Máquina")
    st.caption("Consolidação automática do percentual de pneus instalados para cada equipamento.")

    if not df_view.empty:
        df_health = df_view.groupby(['Equip_Cod', 'Equip_Desc']).agg(
            Total_Pos=('Pos_Cod', 'count'),
            Instalados=('Status', lambda x: (x == 'Instalado').sum())
        ).reset_index()

        df_health['Percentual'] = (df_health['Instalados'] / df_health['Total_Pos']) * 100
        df_health['Faltas'] = df_health['Total_Pos'] - df_health['Instalados']

        df_health = df_health.sort_values(by=['Percentual', 'Faltas'], ascending=[True, False])

        st.dataframe(
            df_health,
            column_config={
                "Equip_Cod": st.column_config.TextColumn("Máquina", width="small"),
                "Equip_Desc": st.column_config.TextColumn("Descrição", width="medium"),
                "Total_Pos": st.column_config.NumberColumn("Total de Posições", format="%d"),
                "Instalados": st.column_config.NumberColumn("Pneus Instalados", format="%d"),
                "Faltas": st.column_config.NumberColumn("Faltas", format="%d"),
                "Percentual": st.column_config.ProgressColumn("% Calçado", format="%.1f%%", min_value=0, max_value=100)
            },
            hide_index=True,
            use_container_width=True,
            height=500
        )
    else:
        st.info("Nenhuma frota disponível para gerar o Score de Saúde.")

with tab_evolucao:
    st.markdown("##### 📈 Evolução Histórica (Linha do Tempo)")
    st.caption("Acompanhe como a saúde e o número de faltas progridem dia a dia.")

    df_historico = carregar_historico_salvo()

    if df_historico.empty:
        st.info(
            "Nenhum histórico gravado ainda. Utilize o botão 'Gravar Posição do Dia' na barra lateral para iniciar o seu histórico.")
    else:
        # Agrupamento Global (Todos os dados gravados por dia)
        df_hist_global = df_historico.groupby('data_registro').agg(
            Total_Pos=('total_pos', 'sum'),
            Total_Instalados=('instalados', 'sum'),
            Total_Faltas=('ausentes', 'sum')
        ).reset_index()

        df_hist_global['Saude_Global_Pct'] = (df_hist_global['Total_Instalados'] / df_hist_global['Total_Pos']) * 100

        c_evo1, c_evo2 = st.columns(2)
        with c_evo1:
            fig_saude_evo = px.line(df_hist_global, x='data_registro', y='Saude_Global_Pct', markers=True,
                                    title="Evolução da Saúde Global da Frota (%)", color_discrete_sequence=['#10B981'])
            fig_saude_evo.update_layout(yaxis_title="% Calçado", xaxis_title="Data do Registro", yaxis_range=[0, 105],
                                        margin=dict(t=40, b=10, l=10, r=10))
            st.plotly_chart(fig_saude_evo, use_container_width=True)

        with c_evo2:
            fig_faltas_evo = px.line(df_hist_global, x='data_registro', y='Total_Faltas', markers=True,
                                     title="Curva de Faltas (Pneus Ausentes)", color_discrete_sequence=['#EF4444'])
            fig_faltas_evo.update_layout(yaxis_title="Total de Faltas", xaxis_title="Data do Registro",
                                         yaxis={'rangemode': 'tozero'}, margin=dict(t=40, b=10, l=10, r=10))
            st.plotly_chart(fig_faltas_evo, use_container_width=True)

        st.markdown("---")
        st.markdown("###### 🔍 Rastreio Específico por Máquina")
        maquinas_historicas = sorted(df_historico['equip_cod'].unique().tolist())
        maq_selecionadas = st.multiselect("Selecione até 5 máquinas para comparar a evolução de saúde lado a lado:",
                                          options=maquinas_historicas, max_selections=5)

        if maq_selecionadas:
            df_hist_maq = df_historico[df_historico['equip_cod'].isin(maq_selecionadas)]
            fig_maq_evo = px.line(df_hist_maq, x='data_registro', y='percentual', color='equip_cod', markers=True,
                                  title="Comparativo de Saúde (%) por Máquina")
            fig_maq_evo.update_layout(yaxis_title="% Calçado", xaxis_title="Data do Registro", yaxis_range=[0, 105],
                                      margin=dict(t=40, b=10, l=10, r=10))
            st.plotly_chart(fig_maq_evo, use_container_width=True)

# ==============================================================================
# EXPORTAÇÃO OFICIAL DO RELATÓRIO (PDF E VETORIAL LADO A LADO)
# ==============================================================================
st.markdown("---")
st.markdown("### 🖨️ Caderno de Croquis (Relatório Oficial)")
st.caption(
    "Exporte o relatório consolidado em PDF respeitando os filtros aplicados na barra lateral. Ideal para imprimir somente as frotas com divergências.")

orientacao_ui = st.radio("Orientação do PDF:", ["Retrato (Em pé)", "Paisagem (Deitado)"], horizontal=True)
orientacao_escolhida = 'P' if 'Retrato' in orientacao_ui else 'L'

if df_view.empty:
    st.info("Ajuste os filtros para visualizar e exportar o relatório.")
else:
    with st.spinner("Desenhando vetores e calculando dimensões de página..."):
        filtros_aplicados = {
            'status': filtro_status_frota,
            'tipo': ", ".join(filtro_tipo) if filtro_tipo else "Todos os Tipos",
            'fogo': busca_fogo if busca_fogo else "Nenhum",
            'excluidas': ", ".join(filtro_excluir_frota) if filtro_excluir_frota else "Nenhuma"
        }
        pdf_oficial = gerar_pdf_pneus_frota(df_view, orientacao_pdf=orientacao_escolhida, filtros=filtros_aplicados)

    st.download_button(
        label=f"📄 Descarregar PDF ({total_equip} frotas listadas)",
        data=pdf_oficial,
        file_name=f"Caderno_Pneus_Compacto_{datetime.now().strftime('%d%m%Y')}.pdf",
        mime="application/pdf",
        type="primary"
    )