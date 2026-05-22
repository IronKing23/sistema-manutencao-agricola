import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import unicodedata
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import tempfile
import io
import time
import glob

# --- CLEANUP DE ARQUIVOS TEMPORÁRIOS ÓRFÃOS (PREVINE ERRO DE DISCO CHEIO) ---
try:
    _tmp_dir = tempfile.gettempdir()
    _agora = time.time()
    for _ext in ["*.png", "*.pdf"]:
        for _f in glob.glob(os.path.join(_tmp_dir, _ext)):
            try:
                _basename = os.path.basename(_f)
                if (_basename.startswith("tmp") or _basename.startswith("cedro_oleo_")) and (
                        _agora - os.path.getmtime(_f)) > 1800:
                    os.remove(_f)
            except:
                pass
except:
    pass

# --- BLINDAGEM E IMPORTAÇÃO DO BANCO DE DADOS ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from database import get_db_connection
    from utils_ui import load_custom_css, ui_header, ui_kpi_card, ui_empty_state
    from utils_icons import get_icon
except ImportError:
    def load_custom_css():
        pass


    def ui_header(title, subtitle, icon):
        st.title(f"{icon} {title}"); st.caption(subtitle)


    def ui_empty_state(msg, icon):
        st.info(f"{icon} {msg}")


    def get_icon(name, color, size="36"):
        return "🧪"


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
        import sqlite3
        return sqlite3.connect('manutencao.db', check_same_thread=False)

# Tentativa segura de importar pacotes para Gráficos
try:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import matplotlib.dates as mdates

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# --- CONFIGURAÇÃO INICIAL E BANCO DE DADOS ---
load_custom_css()

icon_oleo = get_icon("droplet", "#3B82F6", "36")
ui_header(
    title="Análise Preditiva de Óleo",
    subtitle="Diagnósticos I.A., Benchmarking de Desgaste e Geração Automática de O.S.",
    icon=icon_oleo
)


def inicializar_tabela_feedback():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analises_oleo_feedback (
                amostra TEXT PRIMARY KEY,
                acao_gestao TEXT,
                status_acao TEXT DEFAULT 'Pendente'
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao iniciar banco de dados de óleo: {e}")


inicializar_tabela_feedback()


def sincronizar_amostras_bd(df):
    conn = get_db_connection()
    cursor = conn.cursor()

    for amostra in df['NUM_AMOSTRA'].dropna().unique():
        amostra_str = str(amostra).strip()
        if amostra_str and amostra_str != '-':
            cursor.execute(
                "INSERT OR IGNORE INTO analises_oleo_feedback (amostra, acao_gestao, status_acao) VALUES (?, '', 'Pendente')",
                (amostra_str,))
    conn.commit()

    df_bd = pd.read_sql(
        "SELECT amostra as NUM_AMOSTRA, acao_gestao as ACAO_GESTAO, status_acao as STATUS_ACAO FROM analises_oleo_feedback",
        conn)
    conn.close()

    df['NUM_AMOSTRA'] = df['NUM_AMOSTRA'].astype(str).str.strip()
    df_bd['NUM_AMOSTRA'] = df_bd['NUM_AMOSTRA'].astype(str).str.strip()

    if 'ACAO_GESTAO' in df.columns: df = df.drop(columns=['ACAO_GESTAO', 'STATUS_ACAO'])

    df = pd.merge(df, df_bd, on='NUM_AMOSTRA', how='left')
    df['ACAO_GESTAO'] = df['ACAO_GESTAO'].fillna('')
    df['STATUS_ACAO'] = df['STATUS_ACAO'].fillna('Pendente')

    return df


# ==============================================================================
# MOTOR DE PROCESSAMENTO DO LAUDO (TRADUTOR UNIVERSAL BLINDADO)
# ==============================================================================
def clean_col_name(c):
    c = str(c).lower().replace(' ', '')
    c = unicodedata.normalize('NFKD', c).encode('ASCII', 'ignore').decode('utf-8')
    c = ''.join(e for e in c if e.isalnum())
    return c


def safe_float_lab(val):
    if pd.isna(val) or val == '': return 0.0
    val_str = str(val).strip().replace('<', '').replace('>', '').replace('%', '').strip()
    if ',' in val_str: val_str = val_str.replace('.', '').replace(',', '.')
    try:
        return float(val_str)
    except:
        return 0.0


@st.cache_data(show_spinner="A analisar química, a descodificar e a sincronizar com a Base de Dados...", ttl=600)
def processar_laudo_oleo(file):
    try:
        if file.name.lower().endswith('.csv'):
            try:
                df = pd.read_csv(file, sep=';', encoding='utf-8')
            except:
                file.seek(0)
                try:
                    df = pd.read_csv(file, sep=';', encoding='latin-1')
                except:
                    file.seek(0)
                    df = pd.read_csv(file, sep=None, engine='python', encoding='latin-1')
        else:
            df = pd.read_excel(file)

        original_cols = list(df.columns)
        clean_cols = [clean_col_name(c) for c in original_cols]
        available_cols = dict(zip(clean_cols, original_cols))

        def find_col(keywords):
            for clean_c, orig_c in list(available_cols.items()):
                for kw in keywords:
                    if kw in clean_c:
                        del available_cols[clean_c]
                        return orig_c
            return None

        col_map = {
            'FROTA': find_col(['tagfrota', 'tag', 'frota', 'chassi']),
            'FAMILIA': find_col(['familiadoequipamento', 'familia', 'famalia']),
            'MODELO': find_col(['modelodoequipamento', 'modelo']),
            'CLIENTE': find_col(['nomedocliente', 'cliente', 'empresa']),
            'OBRA': find_col(['obraunidade', 'obra']),
            'NUM_AMOSTRA': find_col(['numerodaamostra', 'amostra', 'numero']),
            'DATA_COLETA': find_col(['datadecoleta', 'datacoleta', 'coleta']),
            'DATA_LIBERACAO': find_col(['datadeliberacaodoresultado', 'liberacao', 'resultado']),
            'STATUS_LAUDO': find_col(['statusdaamostra', 'status', 'condicao']),
            'AVALIACAO': find_col(['avaliacao', 'avaliao', 'parecer']),
            'ACOES_INSPECAO': find_col(['acoesdeinspecao', 'inspeao', 'inspecao']),
            'COMPARTIMENTO': find_col(['nomedocompartimento', 'compartimento', 'componente']),
            'PARECER_LAB': find_col(['comentariodacoleta', 'comentario']),
            'HORAS_OLEO': find_col(['horasdooleo', 'holeo']),
            'HORAS_EQUIP': find_col(['horasdoequipamentonacoleta', 'horasdoequipamento', 'hequip']),
            'INDICE_PQ': find_col(['indicepq', 'pqindex', 'pq']),
            'OLEO_TROCADO': find_col(['oleotrocado', 'trocaoleo', 'trocado']),
        }

        if not col_map['FROTA'] or not col_map['STATUS_LAUDO']:
            st.error("Não foi possível encontrar as colunas de 'Tag / Frota' ou 'Status' no seu ficheiro.")
            return None

        rename_dict = {v: k for k, v in col_map.items() if v is not None}
        df = df.rename(columns=rename_dict)

        if 'FROTA' in df.columns: df['FROTA'] = df['FROTA'].astype(str).str.replace(r'\.0$', '',
                                                                                    regex=True).str.replace('nan', '-')
        if 'NUM_AMOSTRA' in df.columns: df['NUM_AMOSTRA'] = df['NUM_AMOSTRA'].astype(str).str.replace(r'\.0$', '',
                                                                                                      regex=True).str.replace(
            'nan', '-')

        if 'DATA_COLETA' in df.columns: df['DATA_COLETA'] = pd.to_datetime(df['DATA_COLETA'], dayfirst=True,
                                                                           errors='coerce')
        if 'DATA_LIBERACAO' in df.columns: df['DATA_LIBERACAO'] = pd.to_datetime(df['DATA_LIBERACAO'], dayfirst=True,
                                                                                 errors='coerce')

        metais_busca = {
            'Ferro': ['ferro'], 'Cobre': ['cobre'], 'Alumínio': ['aluminio', 'alumnio'], 'Cromo': ['cromo'],
            'Chumbo': ['chumbo'], 'Silício': ['silicio', 'silcio'], 'Sódio': ['sodio', 'sdio'], 'Água': ['agua', 'gua'],
            'Potássio': ['potassio'], 'Molibdênio': ['molibdenio'], 'Fuligem': ['fuligem'],
            'Viscosidade': ['viscosidadea100', 'indicedeviscosidade', '100oc', '100c', 'v100', 'cst'],
            'Diluição Diesel': ['diluicaopordiesel', 'diluicao']
        }

        colunas_quimicas_encontradas = []
        for nome_sistema, palavras_chave in metais_busca.items():
            col_match = find_col(palavras_chave)
            if col_match and col_match in df.columns:
                df[nome_sistema] = df[col_match].apply(safe_float_lab)
                colunas_quimicas_encontradas.append(nome_sistema)
            else:
                df[nome_sistema] = 0.0

        if 'INDICE_PQ' in df.columns:
            df['INDICE_PQ'] = df['INDICE_PQ'].apply(safe_float_lab)
            colunas_quimicas_encontradas.append('INDICE_PQ')
        else:
            df['INDICE_PQ'] = 0.0

        if 'OLEO_TROCADO' in df.columns:
            df['OLEO_TROCADO'] = df['OLEO_TROCADO'].astype(str).str.upper()
            df['TROCOU_OLEO_FLAG'] = df['OLEO_TROCADO'].apply(lambda x: 'Sim' if 'S' in x else 'Não')
        else:
            df['TROCOU_OLEO_FLAG'] = 'Não'

        def compilar_relevantes(row):
            relevantes = []
            for col in colunas_quimicas_encontradas:
                val = row.get(col, 0)
                if val > 0: relevantes.append(f"{col}: {val:g}")
            return " | ".join(relevantes) if relevantes else "-"

        df['DADOS_RELEVANTES'] = df.apply(compilar_relevantes, axis=1)
        df['STATUS_LAUDO'] = df.get('STATUS_LAUDO', 'Normal').fillna('Normal')

        def padronizar_status(val):
            v = str(val).upper()
            if any(x in v for x in ['CRÍT', 'CRIT', 'INTERVENÇÃO', 'AÇÃO', 'VERMELHO']): return 'Crítico'
            if any(x in v for x in ['ALERT', 'ATENÇÃO', 'MONITORAR', 'AMARELO', 'ANORMAL', 'LARANJA']): return 'Alerta'
            return 'Normal'

        df['STATUS_CORRIGIDO'] = df['STATUS_LAUDO'].apply(padronizar_status)
        df['AVALIACAO'] = df.get('AVALIACAO', 'Sem avaliação do lab.').fillna('Sem avaliação do lab.')
        df['ACOES_INSPECAO'] = df.get('ACOES_INSPECAO', 'Nenhuma ação de inspeção sugerida.').fillna(
            'Nenhuma ação sugerida.')
        df['Família do equipamento'] = df.get('FAMILIA', 'N/A').fillna('N/A')
        df['MODELO'] = df.get('MODELO', '-').fillna('-')
        df['CLIENTE'] = df.get('CLIENTE', 'N/I').fillna('N/I')
        df['OBRA'] = df.get('OBRA', 'N/I').fillna('N/I')
        df['HORAS_OLEO'] = df.get('HORAS_OLEO', 0).fillna(0)
        df['HORAS_EQUIP'] = df.get('HORAS_EQUIP', 0).fillna(0)

        def classificar_compartimento(val):
            v = str(val).upper()
            if 'MOTOR' in v: return 'Motor'
            if any(x in v for x in ['TRANSMISS', 'CAIXA', 'CÂMBIO', 'CONVERSOR']): return 'Transmissão'
            if 'DIFERENCIAL' in v or 'EIXO' in v: return 'Diferencial'
            if 'CUBO' in v or 'COMANDO FINAL' in v or 'RODA' in v: return 'Cubos/Comandos Finais'
            if 'HIDRÁULIC' in v or 'HIDRAULIC' in v: return 'Hidráulico'
            return 'Outros'

        df['TIPO_COMPARTIMENTO'] = df.get('COMPARTIMENTO', 'Outros').fillna('Outros').apply(classificar_compartimento)

        def gerar_diagnostico_ia(r):
            if r['STATUS_CORRIGIDO'] == 'Normal': return "✅ Sistema a operar dentro dos parâmetros."
            alertas = []
            if r.get('Silício', 0) > 15 and r.get('Ferro', 0) > 15: alertas.append(
                "🌪️ Entrada de poeira (Silício) a causar desgaste (Ferro).")
            if r.get('Cobre', 0) > 10: alertas.append("⚙️ Desgaste em bronzinas/mancais.")
            if r.get('INDICE_PQ', 0) > 40: alertas.append("🧲 Possível fadiga severa ou quebra (PQ Alto).")
            if r.get('Diluição Diesel', 0) > 4.0: alertas.append("⛽ Excesso de combustível no óleo.")
            if r.get('Potássio', 0) > 15 or r.get('Sódio', 0) > 15: alertas.append(
                "💧 Possível contaminação por líquido de arrefecimento (Potássio/Sódio altos).")
            if r.get('Fuligem', 0) > 50: alertas.append(
                "⬛ Excesso de fuligem (falha de queima, filtro ou bicos injetores).")

            if len(alertas) == 0: return "⚠️ Verificar laudo original do laboratório."
            return "\n".join(alertas)

        df['DIAGNOSTICO_IA'] = df.apply(gerar_diagnostico_ia, axis=1)

        df = sincronizar_amostras_bd(df)
        return df
    except Exception as e:
        st.error(f"Erro na análise de dados: {e}")
        return None


# ==============================================================================
# GERAÇÃO DE EXCEL E PDF
# ==============================================================================

@st.cache_data(show_spinner="A gerar Planilha de Ações (Excel)...", ttl=60)
def gerar_excel_plano_acao(df_export):
    if not OPENPYXL_AVAILABLE: return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Plano de Ação - Óleo"

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    action_fill = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    action_font = Font(color="A16207", bold=True)
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'),
                    bottom=Side(style='thin'))
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    colunas = [
        "Amostra", "Frota", "Família", "Modelo", "Compartimento", "Data Coleta",
        "Status", "Avaliação do Laboratório", "Ações de Inspeção Recomendadas",
        "Diagnóstico I.A.", "Fe", "Cu", "Si", "Na", "K", "Mo", "Fuligem", "PQ", "Visc.", "Diluição", "Trocou Óleo",
        "AÇÃO DA GESTÃO / RETORNO"
    ]

    for col_num, col_name in enumerate(colunas, 1):
        cell = ws.cell(row=1, column=col_num, value=col_name)
        if "RETORNO" in col_name:
            cell.fill = action_fill;
            cell.font = action_font
        else:
            cell.fill = header_fill;
            cell.font = header_font
        cell.alignment = align_center;
        cell.border = border

    for row_num, (_, r) in enumerate(df_export.iterrows(), 2):
        ws.cell(row=row_num, column=1, value=str(r.get('NUM_AMOSTRA', ''))).alignment = align_center
        ws.cell(row=row_num, column=2, value=str(r.get('FROTA', ''))).alignment = align_center
        ws.cell(row=row_num, column=3, value=str(r.get('Família do equipamento', ''))).alignment = align_center
        ws.cell(row=row_num, column=4, value=str(r.get('MODELO', ''))).alignment = align_center
        ws.cell(row=row_num, column=5, value=str(r.get('COMPARTIMENTO', ''))).alignment = align_center

        dt_str = r['DATA_COLETA'].strftime('%d/%m/%Y') if pd.notnull(r.get('DATA_COLETA')) else "-"
        ws.cell(row=row_num, column=6, value=dt_str).alignment = align_center

        status_cell = ws.cell(row=row_num, column=7, value=str(r.get('STATUS_CORRIGIDO', '')))
        status_cell.alignment = align_center
        if r.get('STATUS_CORRIGIDO') == 'Crítico':
            status_cell.font = Font(color="DC2626", bold=True)
        elif r.get('STATUS_CORRIGIDO') == 'Alerta':
            status_cell.font = Font(color="D97706", bold=True)
        else:
            status_cell.font = Font(color="16A34A", bold=True)

        ws.cell(row=row_num, column=8, value=str(r.get('AVALIACAO', ''))).alignment = align_left
        ws.cell(row=row_num, column=9, value=str(r.get('ACOES_INSPECAO', ''))).alignment = align_left
        ws.cell(row=row_num, column=10, value=str(r.get('DIAGNOSTICO_IA', ''))).alignment = align_left

        ws.cell(row=row_num, column=11, value=r.get('Ferro', 0)).alignment = align_center
        ws.cell(row=row_num, column=12, value=r.get('Cobre', 0)).alignment = align_center
        ws.cell(row=row_num, column=13, value=r.get('Silício', 0)).alignment = align_center
        ws.cell(row=row_num, column=14, value=r.get('Sódio', 0)).alignment = align_center
        ws.cell(row=row_num, column=15, value=r.get('Potássio', 0)).alignment = align_center
        ws.cell(row=row_num, column=16, value=r.get('Molibdênio', 0)).alignment = align_center
        ws.cell(row=row_num, column=17, value=r.get('Fuligem', 0)).alignment = align_center
        ws.cell(row=row_num, column=18, value=r.get('INDICE_PQ', 0)).alignment = align_center
        ws.cell(row=row_num, column=19, value=r.get('Viscosidade', 0)).alignment = align_center
        ws.cell(row=row_num, column=20, value=r.get('Diluição Diesel', 0)).alignment = align_center
        ws.cell(row=row_num, column=21, value=str(r.get('TROCOU_OLEO_FLAG', 'Não'))).alignment = align_center

        acao_bd = str(r.get('ACAO_GESTAO', '')).strip()
        action_c = ws.cell(row=row_num, column=22, value=acao_bd)
        action_c.fill = PatternFill(start_color="FEFCE8", end_color="FEFCE8", fill_type="solid")
        action_c.border = border

    ws.column_dimensions['A'].width = 15;
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 20;
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 25;
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 15;
    ws.column_dimensions['H'].width = 40
    ws.column_dimensions['I'].width = 30;
    ws.column_dimensions['J'].width = 40
    for col_l in ['K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U']:
        ws.column_dimensions[col_l].width = 8
    ws.column_dimensions['V'].width = 50

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


class PDFPlanoAcaoALS(FPDF):
    def header(self):
        caminho_logo = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logo_cedro.png")
        if os.path.exists(caminho_logo):
            self.image(caminho_logo, 10, 8, 15)
        self.set_font('Arial', 'B', 16)
        self.set_text_color(30, 41, 59)
        self.set_xy(30, 10)
        self.cell(0, 8, 'RELATORIO DE ANALISE PREDITIVA E ORDEM DE SERVICO', 0, 1, 'L')
        self.set_font('Arial', '', 9)
        self.set_text_color(100, 116, 139)
        self.set_x(30)
        self.cell(0, 4, 'Gestao de Frotas | Extracao do Laboratorio', 0, 1, 'L')
        self.set_draw_color(226, 232, 240)
        self.line(10, 24, 200, 24)
        self.set_y(28)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Gerado via Sistema Cedro | Pagina {self.page_no()}', 0, 0, 'C')


@st.cache_data(show_spinner="A gerar PDF de Ações (Gerencial + OS)...", ttl=60)
def gerar_pdf_plano_acao(df_pdf, df_full):
    arquivos_temp = []
    try:
        pdf = PDFPlanoAcaoALS(orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # ==========================================
        # PÁGINA 1: RESUMO GERENCIAL E KPIs
        # ==========================================
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, "Resumo Executivo do Lote de Amostras", 0, 1, 'C')

        tot = len(df_pdf)
        crit = len(df_pdf[df_pdf['STATUS_CORRIGIDO'] == 'Crítico'])
        ale = len(df_pdf[df_pdf['STATUS_CORRIGIDO'] == 'Alerta'])
        norm = len(df_pdf[df_pdf['STATUS_CORRIGIDO'] == 'Normal'])

        pct_norm = 0.0;
        pct_ale = 0.0;
        pct_crit = 0.0

        if tot > 0:
            pct_norm = round((norm / tot) * 100, 1)
            pct_ale = round((ale / tot) * 100, 1)
            pct_crit = round((crit / tot) * 100, 1)

            diff = round(100.0 - (pct_norm + pct_ale + pct_crit), 1)
            if diff != 0:
                if norm >= ale and norm >= crit:
                    pct_norm = round(pct_norm + diff, 1)
                elif ale >= crit:
                    pct_ale = round(pct_ale + diff, 1)
                else:
                    pct_crit = round(pct_crit + diff, 1)

        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, f"Volume Total: {tot} amostras analisadas neste relatorio.", 0, 1, 'C')
        pdf.ln(5)

        y_kpi = pdf.get_y()
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)

        # Box Normal
        pdf.rect(15, y_kpi, 50, 20, 'DF')
        pdf.set_fill_color(16, 185, 129);
        pdf.rect(15, y_kpi, 2, 20, 'F')
        pdf.set_xy(20, y_kpi + 4);
        pdf.set_font('Arial', 'B', 8);
        pdf.set_text_color(100, 116, 139)
        pdf.cell(40, 4, "STATUS NORMAL", 0, 1, 'L')
        pdf.set_xy(20, y_kpi + 10);
        pdf.set_font('Arial', 'B', 12);
        pdf.set_text_color(15, 23, 42)
        pdf.cell(40, 6, f"{norm} ({pct_norm:.1f}%)", 0, 1, 'L')

        # Box Alerta
        pdf.set_fill_color(248, 250, 252);
        pdf.rect(75, y_kpi, 50, 20, 'DF')
        pdf.set_fill_color(245, 158, 11);
        pdf.rect(75, y_kpi, 2, 20, 'F')
        pdf.set_xy(80, y_kpi + 4);
        pdf.set_font('Arial', 'B', 8);
        pdf.set_text_color(100, 116, 139)
        pdf.cell(40, 4, "EM ALERTA", 0, 1, 'L')
        pdf.set_xy(80, y_kpi + 10);
        pdf.set_font('Arial', 'B', 12);
        pdf.set_text_color(15, 23, 42)
        pdf.cell(40, 6, f"{ale} ({pct_ale:.1f}%)", 0, 1, 'L')

        # Box Crítico
        pdf.set_fill_color(248, 250, 252);
        pdf.rect(135, y_kpi, 50, 20, 'DF')
        pdf.set_fill_color(239, 68, 68);
        pdf.rect(135, y_kpi, 2, 20, 'F')
        pdf.set_xy(140, y_kpi + 4);
        pdf.set_font('Arial', 'B', 8);
        pdf.set_text_color(100, 116, 139)
        pdf.cell(40, 4, "STATUS CRITICO", 0, 1, 'L')
        pdf.set_xy(140, y_kpi + 10);
        pdf.set_font('Arial', 'B', 12);
        pdf.set_text_color(15, 23, 42)
        pdf.cell(40, 6, f"{crit} ({pct_crit:.1f}%)", 0, 1, 'L')

        pdf.set_y(y_kpi + 30)

        if MATPLOTLIB_AVAILABLE and not df_pdf.empty:
            fig, axes = plt.subplots(1, 2, figsize=(8.5, 4))
            s_counts = df_pdf['STATUS_CORRIGIDO'].value_counts()
            colors = ['#10B981' if s == 'Normal' else ('#F59E0B' if s == 'Alerta' else '#EF4444') for s in
                      s_counts.index]
            adjusted_pcts_dict = {'Normal': pct_norm, 'Alerta': pct_ale, 'Crítico': pct_crit}
            pie_values = [adjusted_pcts_dict.get(s, 0) for s in s_counts.index]

            axes[0].pie(pie_values, labels=s_counts.index, autopct='%1.1f%%', colors=colors, startangle=90,
                        wedgeprops={'width': 0.5, 'edgecolor': 'w'})
            axes[0].set_title('Distribuicao de Saude (Volume)', fontsize=10, fontweight='bold', color='#333333')

            df_prob = df_pdf[df_pdf['STATUS_CORRIGIDO'].isin(['Crítico', 'Alerta'])]
            if not df_prob.empty:
                top_prob = df_prob['FROTA'].astype(str).value_counts().head(5).sort_values(ascending=True)
                axes[1].barh(top_prob.index, top_prob.values, color='#EF4444')
                axes[1].set_title('Top 5 Frotas c/ Anomalias', fontsize=10, fontweight='bold', color='#333333')
                axes[1].xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
            else:
                axes[1].text(0.5, 0.5, 'Frota Saudavel\n(Nenhum Alerta)', ha='center', va='center', color='#10B981',
                             fontsize=10, fontweight='bold')
                axes[1].axis('off')

            axes[1].spines['top'].set_visible(False);
            axes[1].spines['right'].set_visible(False)
            axes[1].tick_params(axis='both', labelsize=8, colors='#555555')

            plt.tight_layout()

            tmp_img = tempfile.NamedTemporaryFile(prefix="cedro_oleo_", suffix=".png", delete=False)
            img_path = tmp_img.name
            tmp_img.close()
            arquivos_temp.append(img_path)

            fig.savefig(img_path, dpi=200, bbox_inches='tight')
            plt.close(fig)

            pdf.image(img_path, x=15, y=pdf.get_y(), w=180)
            pdf.set_y(pdf.get_y() + 85)

        pdf.add_page()

        # ==========================================
        # PÁGINAS DE ORDENS DE SERVIÇO (CARDS) E TIMELINE DUPLA
        # ==========================================
        for _, row in df_pdf.iterrows():
            start_y = pdf.get_y()
            # Margem de segurança maior devido ao gráfico duplo
            if start_y > 100:
                pdf.add_page()
                start_y = pdf.get_y()

            # --- HEADER DA O.S. ---
            status_v = row.get('STATUS_CORRIGIDO', '')
            if status_v == 'Crítico':
                bg_r, bg_g, bg_b = 239, 68, 68
                txt_status = "CRITICO  STOP"
            elif status_v == 'Alerta':
                bg_r, bg_g, bg_b = 245, 158, 11
                txt_status = "ATENCAO  !"
            else:
                bg_r, bg_g, bg_b = 16, 185, 129
                txt_status = "NORMAL  OK"

            pdf.set_fill_color(bg_r, bg_g, bg_b)
            pdf.rect(140, start_y, 60, 10, 'F')
            pdf.set_xy(140, start_y + 2)
            pdf.set_font('Arial', 'B', 12)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(60, 6, txt_status, 0, 0, 'C')

            # --- INFOGRÁFICO: RÉGUA DE HISTÓRICO ---
            frota_alvo = row.get('FROTA')
            comp_alvo = row.get('COMPARTIMENTO')
            df_hist = df_full[(df_full['FROTA'] == frota_alvo) & (df_full['COMPARTIMENTO'] == comp_alvo)].copy()
            df_hist = df_hist.dropna(subset=['DATA_COLETA']).sort_values(by='DATA_COLETA').tail(5)

            if not df_hist.empty and len(df_hist) > 0:
                pdf.set_xy(140, start_y + 11)
                pdf.set_font('Arial', 'B', 6)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(60, 3, "HISTORICO RECENTE:", 0, 1, 'R')

                q_width = 8
                q_space = 2
                total_w = len(df_hist) * (q_width + q_space) - q_space
                start_q_x = 200 - total_w

                y_q = start_y + 15
                for _, h_row in df_hist.iterrows():
                    h_stat = h_row.get('STATUS_CORRIGIDO', '')
                    if h_stat == 'Crítico':
                        pdf.set_fill_color(239, 68, 68)
                    elif h_stat == 'Alerta':
                        pdf.set_fill_color(245, 158, 11)
                    else:
                        pdf.set_fill_color(16, 185, 129)

                    pdf.rect(start_q_x, y_q, q_width, 4, 'F')
                    start_q_x += (q_width + q_space)

            # --- DADOS DO EQUIPAMENTO E CLIENTE ---
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(71, 85, 105)
            pdf.set_xy(10, start_y)

            cliente_str = str(row.get('CLIENTE', '')).encode('latin-1', 'ignore').decode('latin-1')[:45]
            obra_str = str(row.get('OBRA', '')).encode('latin-1', 'ignore').decode('latin-1')[:45]
            amostra_str = str(row.get('NUM_AMOSTRA', '')).encode('latin-1', 'ignore').decode('latin-1')
            dt_str = row['DATA_COLETA'].strftime('%d/%m/%Y') if pd.notnull(row.get('DATA_COLETA')) else "-"

            pdf.cell(100, 4, f"CLIENTE: {cliente_str}", 0, 1, 'L')
            pdf.cell(100, 4, f"UNIDADE/OBRA: {obra_str}", 0, 1, 'L')
            pdf.cell(100, 4, f"AMOSTRA: {amostra_str}  |  DATA DA COLETA: {dt_str}", 0, 1, 'L')

            box_equip_y = start_y + 14
            pdf.set_fill_color(248, 250, 252)
            pdf.set_draw_color(226, 232, 240)
            pdf.rect(10, box_equip_y, 125, 18, 'DF')

            pdf.set_xy(12, box_equip_y + 2)
            pdf.set_font('Arial', 'B', 9)
            pdf.set_text_color(15, 23, 42)

            frota_str = str(row.get('FROTA', '')).encode('latin-1', 'ignore').decode('latin-1')
            comp_str = str(row.get('COMPARTIMENTO', '')).encode('latin-1', 'ignore').decode('latin-1')
            fam_str = str(row.get('Família do equipamento', '')).encode('latin-1', 'ignore').decode('latin-1')
            mod_str = str(row.get('MODELO', '')).encode('latin-1', 'ignore').decode('latin-1')
            hr_oleo = str(row.get('HORAS_OLEO', '0'))
            hr_eq = str(row.get('HORAS_EQUIP', '0'))
            tr_oleo = str(row.get('TROCOU_OLEO_FLAG', 'Não'))

            pdf.cell(90, 5, f"TAG/FROTA: {frota_str}", 0, 0, 'L')
            pdf.cell(90, 5, f"COMPARTIMENTO: {comp_str}", 0, 1, 'L')

            pdf.set_x(12)
            pdf.set_font('Arial', '', 8)
            pdf.set_text_color(71, 85, 105)
            pdf.cell(90, 4, f"FAMILIA / MODELO: {fam_str} - {mod_str}", 0, 0, 'L')
            pdf.cell(90, 4, f"HR EQUIP: {hr_eq} h | HR OLEO: {hr_oleo} h | TROCA: {tr_oleo}", 0, 1, 'L')

            av_y = box_equip_y + 20
            pdf.set_xy(10, av_y)
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(190, 5, "AVALIACAO:", 0, 1, 'L')

            pdf.set_x(10)
            pdf.set_font('Arial', '', 8)
            av_str = str(row.get('AVALIACAO', '')).encode('latin-1', 'ignore').decode('latin-1')
            pdf.multi_cell(190, 4, av_str, 0, 'L')

            ac_y = pdf.get_y() + 2
            pdf.set_xy(10, ac_y)
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(190, 5, "ACOES DE INSPECAO:", 0, 1, 'L')

            pdf.set_x(10)
            pdf.set_font('Arial', '', 8)
            ac_str = str(row.get('ACOES_INSPECAO', '')).encode('latin-1', 'ignore').decode('latin-1')
            pdf.multi_cell(190, 4, ac_str, 0, 'L')

            qui_y = pdf.get_y() + 3
            pdf.set_xy(10, qui_y)

            pdf.set_font('Arial', 'B', 7)
            pdf.set_fill_color(226, 232, 240)
            pdf.cell(38, 5, "Ferro / Cobre (ppm)", 1, 0, 'C', fill=True)
            pdf.cell(38, 5, "Silicio / Sodio (ppm)", 1, 0, 'C', fill=True)
            pdf.cell(38, 5, "Potassio / Molib. (ppm)", 1, 0, 'C', fill=True)
            pdf.cell(38, 5, "Fuligem / Indice PQ", 1, 0, 'C', fill=True)
            pdf.cell(38, 5, "Visc. / Diluicao (%)", 1, 1, 'C', fill=True)

            pdf.set_font('Arial', '', 8)
            pdf.set_x(10)
            pdf.cell(38, 5, f"{row.get('Ferro', 0):.0f} / {row.get('Cobre', 0):.0f}", 1, 0, 'C')
            pdf.cell(38, 5, f"{row.get('Silício', 0):.0f} / {row.get('Sódio', 0):.0f}", 1, 0, 'C')
            pdf.cell(38, 5, f"{row.get('Potássio', 0):.0f} / {row.get('Molibdênio', 0):.0f}", 1, 0, 'C')
            pdf.cell(38, 5, f"{row.get('Fuligem', 0):.0f} / {row.get('INDICE_PQ', 0):.0f}", 1, 0, 'C')
            pdf.cell(38, 5, f"{row.get('Viscosidade', 0):.1f} / {row.get('Diluição Diesel', 0):.1f}", 1, 1, 'C')

            box_acao_y = pdf.get_y() + 4
            pdf.set_fill_color(255, 255, 255)
            pdf.set_draw_color(100, 116, 139)
            pdf.rect(10, box_acao_y, 190, 20, 'D')

            pdf.set_xy(12, box_acao_y + 1)
            pdf.set_font('Arial', 'B', 7)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(190, 4, "PLANO DE ACAO E RETORNO DA OFICINA (A Preencher):", 0, 1, 'L')

            acao_bd = str(row.get('ACAO_GESTAO', '')).strip()
            if acao_bd and acao_bd.upper() != 'NAN':
                pdf.set_xy(12, box_acao_y + 6)
                pdf.set_font('Arial', 'I', 8)
                pdf.set_text_color(30, 41, 59)
                pdf.multi_cell(186, 4, acao_bd.encode('latin-1', 'ignore').decode('latin-1'), 0, 'L')
            else:
                pdf.set_draw_color(226, 232, 240)
                pdf.line(12, box_acao_y + 9, 198, box_acao_y + 9)
                pdf.line(12, box_acao_y + 14, 198, box_acao_y + 14)
                pdf.line(12, box_acao_y + 19, 198, box_acao_y + 19)

            pdf.set_y(box_acao_y + 24)

            # --- INSERÇÃO DE GRÁFICO DUPLO NO PDF (PPM + STATUS TIMELINE COM P&B SEGURO) ---
            if MATPLOTLIB_AVAILABLE:
                try:
                    if not df_hist.empty and len(df_hist) > 0:
                        elementos_analise = ['Ferro', 'Silício', 'Cobre', 'Sódio', 'Potássio', 'Fuligem', 'INDICE_PQ']
                        plot_cols = [c for c in elementos_analise if c in df_hist.columns and df_hist[c].sum() > 0]

                        if plot_cols:
                            # Criação do painel duplo (Dois gráficos em um, compartilhando o eixo X/Datas)
                            fig_mini, (ax_ppm, ax_status) = plt.subplots(
                                nrows=2, ncols=1, figsize=(8, 3.5), sharex=True,
                                gridspec_kw={'height_ratios': [2, 1.2]}
                            )

                            # --- GRÁFICO SUPERIOR: Evolução Química (PPM) ---
                            line_styles = ['-', '--', '-.', ':', (0, (3, 1, 1, 1))]  # Diferentes traços para P&B
                            last_points = []

                            for idx, col in enumerate(plot_cols[:5]):
                                valid_data = df_hist[['DATA_COLETA', col]].dropna()
                                if not valid_data.empty:
                                    style = line_styles[idx % len(line_styles)]
                                    line_obj = ax_ppm.plot(df_hist['DATA_COLETA'], df_hist[col],
                                                           marker='o', label=col, markersize=3,
                                                           linewidth=1.5, linestyle=style)[0]

                                    last_x_date = valid_data['DATA_COLETA'].iloc[-1]
                                    last_x_num = mdates.date2num(last_x_date)
                                    last_y = valid_data[col].iloc[-1]

                                    last_points.append({
                                        'col': col, 'x_date': last_x_date, 'x_num': last_x_num,
                                        'y': last_y, 'color': line_obj.get_color()
                                    })

                            # Anti-Sobreposição dos Rótulos (para P&B ser legível)
                            if last_points:
                                last_points.sort(key=lambda p: p['y'])
                                fig_mini.canvas.draw()

                                y_pixels = []
                                for pt in last_points:
                                    coord = ax_ppm.transData.transform((pt['x_num'], pt['y']))
                                    y_pixels.append(coord[1])

                                min_pixel_dist = 14.0
                                for _ in range(20):
                                    for i in range(len(y_pixels) - 1):
                                        if (y_pixels[i + 1] - y_pixels[i]) < min_pixel_dist:
                                            overlap = min_pixel_dist - (y_pixels[i + 1] - y_pixels[i])
                                            y_pixels[i] -= overlap / 2.0
                                            y_pixels[i + 1] += overlap / 2.0

                                for i, pt in enumerate(last_points):
                                    orig_y_pixel = ax_ppm.transData.transform((pt['x_num'], pt['y']))[1]
                                    offset_y = y_pixels[i] - orig_y_pixel

                                    ax_ppm.annotate(f" {pt['col']}",
                                                    xy=(pt['x_date'], pt['y']), xytext=(8, offset_y),
                                                    textcoords="offset points", fontsize=7, fontweight='bold',
                                                    color=pt['color'], va='center',
                                                    arrowprops=dict(arrowstyle="-", color=pt['color'], lw=0.5,
                                                                    alpha=0.6) if abs(offset_y) > 3 else None)

                            left, right = ax_ppm.get_xlim()
                            ax_ppm.set_xlim(left, right + (right - left) * 0.20)
                            ax_ppm.set_title(f"Evolucao Quimica (PPM): {comp_alvo} - {frota_alvo}", fontsize=8,
                                             color='#333333', loc='left', pad=3)
                            ax_ppm.tick_params(axis='both', labelsize=6)
                            ax_ppm.grid(True, linestyle='--', alpha=0.3)
                            ax_ppm.legend(fontsize=6, loc='center left', bbox_to_anchor=(1, 0.5))
                            ax_ppm.spines['top'].set_visible(False);
                            ax_ppm.spines['right'].set_visible(False)

                            # --- GRÁFICO INFERIOR: Timeline de Status e Troca de Óleo ---
                            df_hist['STATUS_NUM'] = df_hist['STATUS_CORRIGIDO'].map(
                                {'Normal': 1, 'Alerta': 2, 'Crítico': 3})

                            # Linha conectora de fundo
                            ax_status.plot(df_hist['DATA_COLETA'], df_hist['STATUS_NUM'], color='gray', linestyle='-',
                                           linewidth=1, alpha=0.4)

                            # Plot de Status com formas distintas para P&B (Círculo, Triângulo, Quadrado)
                            for s_nome, s_val, s_cor, s_marker in [('Normal', 1, '#10B981', 'o'),
                                                                   ('Alerta', 2, '#F59E0B', '^'),
                                                                   ('Crítico', 3, '#EF4444', 's')]:
                                mask = df_hist['STATUS_CORRIGIDO'] == s_nome
                                if mask.any():
                                    ax_status.scatter(df_hist.loc[mask, 'DATA_COLETA'], df_hist.loc[mask, 'STATUS_NUM'],
                                                      color=s_cor, marker=s_marker, s=40, label=s_nome, zorder=5)

                            # Destaque para a Troca de Óleo
                            mask_oleo = df_hist['TROCOU_OLEO_FLAG'] == 'Sim'
                            if mask_oleo.any():
                                ax_status.scatter(df_hist.loc[mask_oleo, 'DATA_COLETA'],
                                                  df_hist.loc[mask_oleo, 'STATUS_NUM'],
                                                  facecolors='none', edgecolors='black', marker='D', s=80,
                                                  linewidths=1.5, label='Troca de Oleo', zorder=6)
                                for _, row_oil in df_hist[mask_oleo].iterrows():
                                    ax_status.annotate("Troca", xy=(row_oil['DATA_COLETA'], row_oil['STATUS_NUM']),
                                                       xytext=(0, 12), textcoords="offset points", ha='center',
                                                       fontsize=6, fontweight='bold', color='black')

                            ax_status.set_yticks([1, 2, 3])
                            ax_status.set_yticklabels(['Normal', 'Alerta', 'Critico'], fontsize=7, fontweight='bold')
                            ax_status.set_ylim(0.5, 3.8)  # Um pouco mais de espaço para o texto "Troca"
                            ax_status.grid(True, axis='y', linestyle='--', alpha=0.3)
                            ax_status.legend(fontsize=6, loc='center left', bbox_to_anchor=(1, 0.5))
                            ax_status.spines['top'].set_visible(False);
                            ax_status.spines['right'].set_visible(False)
                            ax_status.set_title("Timeline de Saude (Status)", fontsize=8, color='#333333', loc='left',
                                                pad=3)

                            # Formatação da Data (Aplica no eixo inferior automaticamente pelo sharex)
                            ax_status.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%y'))
                            fig_mini.autofmt_xdate(rotation=0, ha='center')

                            plt.tight_layout()

                            tmp_trend = tempfile.NamedTemporaryFile(prefix="cedro_oleo_", suffix=".png", delete=False)
                            img_trend = tmp_trend.name
                            tmp_trend.close()
                            arquivos_temp.append(img_trend)

                            fig_mini.savefig(img_trend, dpi=150, bbox_inches='tight')
                            plt.close(fig_mini)

                            if pdf.get_y() > 200:  # Ajustado pois a imagem agora é mais alta
                                pdf.add_page()

                            pdf.image(img_trend, x=10, y=pdf.get_y() + 2, w=190)
                            pdf.set_y(pdf.get_y() + 85)  # Deslocamento maior devido aos 2 gráficos

                except Exception as e:
                    pass

            pdf.set_draw_color(30, 41, 59)
            pdf.set_line_width(0.5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.set_y(pdf.get_y() + 4)

        tmp_pdf = tempfile.NamedTemporaryFile(prefix="cedro_oleo_", suffix=".pdf", delete=False)
        pdf_path = tmp_pdf.name
        tmp_pdf.close()
        arquivos_temp.append(pdf_path)

        pdf.output(pdf_path)
        with open(pdf_path, "rb") as f:
            bytes_pdf = f.read()

        return bytes_pdf

    finally:
        if MATPLOTLIB_AVAILABLE:
            plt.close('all')

        for tmp_f in arquivos_temp:
            try:
                if os.path.exists(tmp_f):
                    os.remove(tmp_f)
            except:
                pass


# ==============================================================================
# INTERFACE PRINCIPAL E FILTROS
# ==============================================================================

if 'dataset_oleo' not in st.session_state:
    st.session_state['dataset_oleo'] = None

with st.expander("📂 Importar Laudo Laboratorial (Excel/CSV)", expanded=(st.session_state['dataset_oleo'] is None)):
    file_up = st.file_uploader("Faça upload do ficheiro exportado do laboratório", type=['xlsx', 'csv'])
    if file_up and st.button("Processar Laudos Químicos 🧪", type="primary"):
        df_oleo = processar_laudo_oleo(file_up)
        if df_oleo is not None:
            st.session_state['dataset_oleo'] = df_oleo
            st.rerun()

if st.session_state['dataset_oleo'] is None:
    ui_empty_state("A aguardar upload dos laudos para rodar o algoritmo e gerar relatórios.", icon="🔬")
    st.stop()

df = st.session_state['dataset_oleo'].copy()

# ==============================================================================
# BARRA LATERAL: FILTROS DE BUSCA
# ==============================================================================
with st.sidebar:
    st.header("🔍 Filtros de Análise")

    if 'DATA_COLETA' in df.columns:
        datas_validas = df['DATA_COLETA'].dropna()
        if not datas_validas.empty:
            min_d = datas_validas.min().date()
            max_d = datas_validas.max().date()
            datas = st.date_input("Período da Coleta", [min_d, max_d])
        else:
            datas = None
    else:
        datas = None

    filtro_status = st.radio("Condição da Amostra:", ["🚨 Apenas Críticas/Alertas", "Todas", "✅ Apenas Normais"],
                             index=1)

    if 'Família do equipamento' in df.columns:
        familias = sorted(df['Família do equipamento'].dropna().astype(str).unique().tolist())
        filtro_familias = st.multiselect("Família de Máquina:", options=familias)
    else:
        filtro_familias = []

# --- APLICAÇÃO DOS FILTROS ---
df_view = df.copy()

if datas and len(datas) == 2:
    d_inicio = pd.to_datetime(datas[0])
    d_fim = pd.to_datetime(datas[1])
    df_view = df_view[(df_view['DATA_COLETA'] >= d_inicio) & (df_view['DATA_COLETA'] <= d_fim)]

if filtro_status == "🚨 Apenas Críticas/Alertas":
    df_view = df_view[df_view['STATUS_CORRIGIDO'].isin(['Crítico', 'Alerta'])]
elif filtro_status == "✅ Apenas Normais":
    df_view = df_view[df_view['STATUS_CORRIGIDO'] == 'Normal']

if filtro_familias:
    df_view = df_view[df_view['Família do equipamento'].isin(filtro_familias)]

st.markdown("---")

# --- KPIs GERAIS ---
total_amostras = len(df_view)
criticas = len(df_view[df_view['STATUS_CORRIGIDO'] == 'Crítico'])
alertas = len(df_view[df_view['STATUS_CORRIGIDO'] == 'Alerta'])
normais = len(df_view[df_view['STATUS_CORRIGIDO'] == 'Normal'])

pct_normais = 0.0;
pct_alertas = 0.0;
pct_criticas = 0.0

if total_amostras > 0:
    pct_normais = round((normais / total_amostras) * 100, 1)
    pct_alertas = round((alertas / total_amostras) * 100, 1)
    pct_criticas = round((criticas / total_amostras) * 100, 1)

    diff = round(100.0 - (pct_normais + pct_alertas + pct_criticas), 1)
    if diff != 0:
        if normais >= alertas and normais >= criticas:
            pct_normais = round(pct_normais + diff, 1)
        elif alertas >= criticas:
            pct_alertas = round(pct_alertas + diff, 1)
        else:
            pct_criticas = round(pct_criticas + diff, 1)

c1, c2, c3, c4 = st.columns(4)
ui_kpi_card(c1, "Amostras no Filtro", f"{total_amostras}", "🧪", "#3B82F6", "Volume analisado")
ui_kpi_card(c2, "Estado Normal", f"{normais} ({pct_normais:.1f}%)", "✅", "#10B981", "Desgaste esperado")
ui_kpi_card(c3, "Em Alerta", f"{alertas} ({pct_alertas:.1f}%)", "⚠️", "#F59E0B", "Atenção nas próximas trocas")
ui_kpi_card(c4, "Estado Crítico", f"{criticas} ({pct_criticas:.1f}%)", "🚨", "#EF4444" if criticas > 0 else "#10B981",
            "Exigem plano de ação")

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# ABAS DE VISUALIZAÇÃO E FECHO DE CICLO
# ==============================================================================
tab_tabela, tab_ia, tab_tendencia, tab_feedback = st.tabs(
    ["📋 Resumo de Pareceres", "🤖 Diagnóstico Autônomo", "📈 Evolução Histórica (Timeline)", "🔄 Fecho de Ciclo (Gestão)"])

with tab_tabela:
    st.markdown("##### Dashboards Analíticos")
    st.caption("Visão sumarizada das amostras. Os detalhes completos de Ação estão disponíveis no PDF exportado.")

    if not df_view.empty:
        c_graf1, c_graf2 = st.columns(2)
        with c_graf1:
            fig_fam = px.histogram(df_view, y='Família do equipamento', color='STATUS_CORRIGIDO',
                                   orientation='h',
                                   color_discrete_map={'Normal': '#10B981', 'Alerta': '#F59E0B', 'Crítico': '#EF4444'},
                                   title="Amostras por Família de Equipamento")
            fig_fam.update_layout(yaxis_title="", margin=dict(t=40, b=10, l=10, r=10))
            st.plotly_chart(fig_fam, use_container_width=True)

        with c_graf2:
            if df_view['DATA_COLETA'].notna().sum() > 0:
                fig_time = px.histogram(df_view, x='DATA_COLETA', color='STATUS_CORRIGIDO',
                                        color_discrete_map={'Normal': '#10B981', 'Alerta': '#F59E0B',
                                                            'Crítico': '#EF4444'},
                                        title="Volume de Coletas no Tempo")
                fig_time.update_layout(xaxis_title="Data", yaxis_title="Qtd", margin=dict(t=40, b=10, l=10, r=10))
                st.plotly_chart(fig_time, use_container_width=True)

        st.markdown("###### 📑 Tabela Resumo")


        def format_status(val):
            if val == 'Crítico': return 'background-color: #FECACA; color: #991B1B; font-weight: bold;'
            if val == 'Alerta': return 'background-color: #FEF08A; color: #A16207; font-weight: bold;'
            return 'color: #166534;'


        col_view = ['FROTA', 'COMPARTIMENTO', 'DATA_COLETA', 'STATUS_CORRIGIDO', 'AVALIACAO']
        col_view = [c for c in col_view if c in df_view.columns]

        st.dataframe(
            df_view[col_view].style.applymap(format_status, subset=['STATUS_CORRIGIDO']) if hasattr(df_view.style,
                                                                                                    'applymap') else
            df_view[col_view].style.map(format_status, subset=['STATUS_CORRIGIDO']),
            column_config={
                "FROTA": st.column_config.TextColumn("Máquina", width="small"),
                "COMPARTIMENTO": "Compartimento",
                "DATA_COLETA": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "STATUS_CORRIGIDO": "Status",
                "AVALIACAO": st.column_config.TextColumn("Parecer Resumido", width="large")
            },
            hide_index=True, use_container_width=True, height=300
        )
    else:
        st.success("Não há resultados para os filtros selecionados.")

with tab_ia:
    st.markdown("##### 🌳 Diagnóstico Automático (Árvore de Causa e Efeito)")
    st.caption("O sistema cruza os elementos químicos e gera a provável causa raiz do problema.")

    df_problemas = df_view[df_view['STATUS_CORRIGIDO'].isin(['Crítico', 'Alerta'])].copy()
    if not df_problemas.empty:
        def format_diagnostico(val):
            return f"background-color: #FEF2F2; color: #991B1B; font-weight: 500;" if '✅' not in val else ""


        col_view = ['FROTA', 'COMPARTIMENTO', 'STATUS_CORRIGIDO', 'DIAGNOSTICO_IA', 'DADOS_RELEVANTES']
        col_view = [c for c in col_view if c in df_problemas.columns]

        st.dataframe(
            df_problemas[col_view].style.applymap(format_diagnostico, subset=['DIAGNOSTICO_IA']) if hasattr(
                df_problemas.style, 'applymap') else df_problemas[col_view].style.map(format_diagnostico,
                                                                                      subset=['DIAGNOSTICO_IA']),
            column_config={
                "FROTA": st.column_config.TextColumn("Máquina", width="small"),
                "COMPARTIMENTO": "Compartimento",
                "STATUS_CORRIGIDO": "Veredito",
                "DIAGNOSTICO_IA": st.column_config.TextColumn("Diagnóstico IA (Causa Provável)", width="large"),
                "DADOS_RELEVANTES": st.column_config.TextColumn("Química Relevante", width="medium")
            },
            hide_index=True, use_container_width=True
        )
    else:
        st.info("Nenhuma anomalia crítica detetada neste filtro.")

with tab_tendencia:
    st.markdown("##### 📈 Evolução Histórica e Benchmarking")
    st.caption("Analise o desgaste de uma frota ou cruze os dados de várias máquinas para comparação (Benchmarking).")

    if not df_view.empty and 'FROTA' in df_view.columns:
        frotas_disponiveis = sorted(df_view['FROTA'].dropna().unique().tolist())
        # --- ATUALIZADO: Seleção Múltipla para Benchmarking ---
        frotas_selecionadas = st.multiselect("Selecione a(s) Frota(s) para análise e comparação:",
                                             options=frotas_disponiveis)

        if frotas_selecionadas:
            df_frota = df_view[df_view['FROTA'].isin(frotas_selecionadas)].copy()
            df_frota = df_frota.sort_values(by='DATA_COLETA')

            if not df_frota.empty:
                # --- ATUALIZADO: Alerta de Degradação Acelerada Matemática ---
                elementos_criticos = ['Ferro', 'Silício', 'Cobre', 'Chumbo', 'Alumínio']
                alertas_globais_degradacao = []

                for frota in frotas_selecionadas:
                    comps = df_frota[df_frota['FROTA'] == frota]['COMPARTIMENTO'].unique()
                    for comp in comps:
                        df_sub = df_frota[
                            (df_frota['FROTA'] == frota) & (df_frota['COMPARTIMENTO'] == comp)].sort_values(
                            'DATA_COLETA')
                        if len(df_sub) >= 2:
                            last = df_sub.iloc[-1]
                            prev = df_sub.iloc[-2]
                            for el in elementos_criticos:
                                if el in df_sub.columns:
                                    if last[el] > 15 and prev[el] > 0 and last[el] > (prev[el] * 1.5):
                                        alertas_globais_degradacao.append(
                                            f"**{frota} ({comp}):** {el} subiu de {prev[el]} para {last[el]} (+{((last[el] / prev[el]) - 1) * 100:.0f}%)")
                                    elif last[el] > 15 and prev[el] == 0:
                                        alertas_globais_degradacao.append(
                                            f"**{frota} ({comp}):** {el} disparou de 0 para {last[el]}")

                if alertas_globais_degradacao:
                    st.error("🚨 **ALERTA DE DEGRADAÇÃO ACELERADA DETECTADA** nas últimas amostras:\n" + "\n".join(
                        [f"- {a}" for a in alertas_globais_degradacao]))

                # --- Análise de Volatilidade ---
                mudancas_status = (df_frota['STATUS_CORRIGIDO'] != df_frota['STATUS_CORRIGIDO'].shift()).sum() - 1
                mudancas_status = max(0, mudancas_status)

                cor_volatilidade = "green" if mudancas_status <= 1 else ("orange" if mudancas_status <= 3 else "red")
                if len(frotas_selecionadas) == 1:
                    st.markdown(
                        f"**Índice de Estabilidade:** <span style='color:{cor_volatilidade}'>Mudou de estado {mudancas_status} vezes no histórico analisado.</span>",
                        unsafe_allow_html=True)

                # --- Gráfico de Timeline de Status (Saúde) ---
                df_frota['STATUS_VALOR'] = df_frota['STATUS_CORRIGIDO'].map({'Normal': 1, 'Alerta': 2, 'Crítico': 3})
                df_frota['FROTA_COMPARTIMENTO'] = df_frota['FROTA'] + " - " + df_frota['COMPARTIMENTO']
                df_frota['MARCADOR'] = df_frota['TROCOU_OLEO_FLAG'].apply(
                    lambda x: 'diamond' if x == 'Sim' else 'circle')

                fig_status = px.scatter(
                    df_frota, x='DATA_COLETA', y='STATUS_CORRIGIDO', color='STATUS_CORRIGIDO',
                    color_discrete_map={'Normal': '#10B981', 'Alerta': '#F59E0B', 'Crítico': '#EF4444'},
                    symbol='TROCOU_OLEO_FLAG', symbol_sequence=['circle', 'diamond'],
                    hover_data=['FROTA_COMPARTIMENTO', 'AVALIACAO'],
                    title=f"Linha do Tempo de Saúde",
                    labels={'DATA_COLETA': 'Data', 'STATUS_CORRIGIDO': 'Estado',
                            'TROCOU_OLEO_FLAG': 'Houve Troca de Óleo?'}
                )

                for f_c in df_frota['FROTA_COMPARTIMENTO'].unique():
                    df_linha = df_frota[df_frota['FROTA_COMPARTIMENTO'] == f_c]
                    fig_status.add_trace(go.Scatter(
                        x=df_linha['DATA_COLETA'], y=df_linha['STATUS_CORRIGIDO'],
                        mode='lines', line=dict(color='rgba(150, 150, 150, 0.4)', width=2),
                        name=f_c, hoverinfo='skip', showlegend=False
                    ))

                fig_status.update_traces(marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')))
                fig_status.update_yaxes(categoryorder='array', categoryarray=['Normal', 'Alerta', 'Crítico'])
                st.plotly_chart(fig_status, use_container_width=True)

                st.markdown("---")

                # --- Gráfico de Linha PPM (Química) ---
                elementos_quimicos = ['Ferro', 'Silício', 'Cobre', 'Alumínio', 'Cromo', 'Chumbo', 'Viscosidade',
                                      'Diluição Diesel', 'INDICE_PQ', 'Potássio', 'Molibdênio', 'Fuligem']
                elementos_disponiveis = [e for e in elementos_quimicos if
                                         e in df_frota.columns and df_frota[e].sum() > 0]

                if elementos_disponiveis:
                    elementos_selecionados = st.multiselect(
                        "Selecione os indicadores químicos para cruzar (em ppm / %):",
                        options=elementos_disponiveis,
                        default=[e for e in ['Ferro', 'Silício'] if
                                 e in elementos_disponiveis] or elementos_disponiveis[:1]
                    )

                    if elementos_selecionados:
                        fig_trend = px.line(
                            df_frota, x='DATA_COLETA', y=elementos_selecionados, color='FROTA_COMPARTIMENTO',
                            markers=True,
                            title=f"Evolução Química (PPM)",
                            labels={'value': 'Concentração', 'DATA_COLETA': 'Data da Coleta', 'variable': 'Indicador',
                                    'FROTA_COMPARTIMENTO': 'Equipamento'}
                        )
                        fig_trend.update_layout(hovermode="x unified")
                        st.plotly_chart(fig_trend, use_container_width=True)

                        st.markdown(f"###### Histórico Tabular Recente")
                        col_hist = ['DATA_COLETA', 'FROTA', 'COMPARTIMENTO', 'STATUS_CORRIGIDO',
                                    'TROCOU_OLEO_FLAG'] + elementos_selecionados
                        st.dataframe(df_frota[col_hist].sort_values(by='DATA_COLETA', ascending=False), hide_index=True,
                                     use_container_width=True)
                else:
                    st.warning("Nenhum dado numérico de elementos químicos encontrado para esta frota.")
            else:
                st.info("Sem dados temporais disponíveis.")
    else:
        st.info("Selecione uma ou mais frotas para analisar o histórico e a degradação.")

with tab_feedback:
    st.markdown("##### 🔄 Fecho de Ciclo e Geração de Ordem de Serviço")
    st.caption(
        "Marque a caixa 'Gerar O.S.' para abrir um ticket direto para a oficina e salvar no banco de dados da Manutenção!")

    df_feed_ui = df_view[df_view['STATUS_CORRIGIDO'].isin(['Crítico', 'Alerta'])].copy()

    if not df_feed_ui.empty:
        # Adiciona a caixa de seleção para a inteligência de OS
        df_feed_ui.insert(0, 'Gerar_OS', False)

        colunas_editaveis = ['Gerar_OS', 'NUM_AMOSTRA', 'FROTA', 'COMPARTIMENTO', 'STATUS_CORRIGIDO', 'ACAO_GESTAO',
                             'STATUS_ACAO']
        colunas_editaveis = [c for c in colunas_editaveis if c in df_feed_ui.columns]

        edited_df = st.data_editor(
            df_feed_ui[colunas_editaveis],
            column_config={
                "Gerar_OS": st.column_config.CheckboxColumn("⚙️ Criar O.S.?",
                                                            help="Abre uma Ordem de Serviço automática.",
                                                            default=False),
                "NUM_AMOSTRA": st.column_config.TextColumn("Amostra", disabled=True),
                "FROTA": st.column_config.TextColumn("Máquina", disabled=True),
                "COMPARTIMENTO": st.column_config.TextColumn("Local", disabled=True),
                "STATUS_CORRIGIDO": st.column_config.TextColumn("Status", disabled=True),
                "ACAO_GESTAO": st.column_config.TextColumn("📝 Observações / Ação", required=False, width="large"),
                "STATUS_ACAO": st.column_config.SelectboxColumn("Situação",
                                                                options=['Pendente', 'Em Andamento', 'Concluída'],
                                                                required=True)
            },
            hide_index=True, use_container_width=True, key="editor_feedback"
        )

        if st.button("💾 Executar Ações e Gerar O.S.", type="primary"):
            conn = get_db_connection()
            cursor = conn.cursor()

            # Puxar o mapeamento das Frotas e Operações para a O.S.
            cursor.execute("SELECT id, frota FROM equipamentos")
            map_eq = {row[1].upper().strip(): row[0] for row in cursor.fetchall()}

            cursor.execute("SELECT id, nome FROM tipos_operacao")
            map_op = {row[1].upper().strip(): row[0] for row in cursor.fetchall()}
            op_id_preditiva = map_op.get('MECÂNICA', map_op.get('MECANICA', 1))  # Usa a ID genérica se não achar exato

            os_geradas = 0

            for _, row in edited_df.iterrows():
                amostra = str(row['NUM_AMOSTRA']).strip()
                acao = str(row.get('ACAO_GESTAO', '')).strip()
                status_acao = str(row.get('STATUS_ACAO', 'Pendente')).strip()

                # --- NOVA LÓGICA DE GERAÇÃO DE O.S. ---
                if row.get('Gerar_OS', False):
                    f_key = str(row['FROTA']).upper().strip()
                    if f_key in map_eq:
                        eq_id = map_eq[f_key]
                        desc_os = f"[GERADO VIA PREDITIVA DE ÓLEO]\nAmostra: {amostra}\nCompartimento: {row['COMPARTIMENTO']}\nDiagnóstico Lab: {row['STATUS_CORRIGIDO']}\nAção da Gestão: {acao}"
                        prio_os = "Alta" if row['STATUS_CORRIGIDO'] == 'Crítico' else "Média"

                        cursor.execute("""
                            INSERT INTO ordens_servico (data_hora, equipamento_id, descricao, tipo_operacao_id, status, prioridade, classificacao, maquina_parada)
                            VALUES (?, ?, ?, ?, 'Pendente', ?, 'Preditiva', 0)
                        """, (datetime.now(), eq_id, desc_os, op_id_preditiva, prio_os))

                        nova_os_id = cursor.lastrowid
                        acao = f"✅ OS #{nova_os_id} Gerada Automática. " + acao
                        os_geradas += 1

                if amostra and amostra != '-':
                    cursor.execute(
                        "UPDATE analises_oleo_feedback SET acao_gestao = ?, status_acao = ? WHERE amostra = ?",
                        (acao, status_acao, amostra))

            conn.commit()
            conn.close()

            if os_geradas > 0:
                st.balloons()
                st.success(f"Ações atualizadas com sucesso e {os_geradas} Ordens de Serviço enviadas para a oficina!")
            else:
                st.toast("Ações de feedback atualizadas com sucesso!", icon="✅")

            st.session_state['dataset_oleo'] = sincronizar_amostras_bd(st.session_state['dataset_oleo'])
            time.sleep(1.5)
            st.rerun()
    else:
        st.success("Não há máquinas críticas a aguardar feedback no filtro atual.")

# ==============================================================================
# EXPORTAÇÃO (PLANOS DE AÇÃO)
# ==============================================================================
st.markdown("---")
st.markdown("### 📋 Geração de Planos de Ação (Exportação)")
st.caption("Gere os relatórios. Se preencheu a aba 'Fecho de Ciclo' acima, os PDFs já sairão preenchidos!")

tipo_exportacao = st.radio(
    "Quais amostras deseja incluir no relatório final?",
    ["🚨 Apenas Críticas e em Alerta (Focado em Ação Imediata)",
     "📑 Todas as Amostras do Filtro Atual (Histórico Completo)"],
    horizontal=True
)

if df_view.empty:
    st.info("Ajuste os filtros para gerar o relatório.")
else:
    if "Apenas" in tipo_exportacao:
        df_export = df_view[df_view['STATUS_CORRIGIDO'].isin(['Crítico', 'Alerta'])].copy()
    else:
        df_export = df_view.copy()

    if df_export.empty:
        st.success("Tudo limpo! Não há amostras no filtro atual para gerar o plano de ação.")
    else:
        c_pdf, c_excel = st.columns(2)

        with st.spinner("A compilar Gráficos Gerenciais e Ordens de Serviço..."):
            excel_bytes = gerar_excel_plano_acao(df_export)
            pdf_bytes = gerar_pdf_plano_acao(df_export, df)

        nome_arq = f"Plano_Acao_Oleo_{datetime.now().strftime('%d%m%Y')}"

        with c_pdf:
            st.download_button(label=f"📄 Caderno de Ações em PDF", data=pdf_bytes, file_name=f"{nome_arq}.pdf",
                               mime="application/pdf", type="primary", use_container_width=True)

        with c_excel:
            if excel_bytes:
                st.download_button(label=f"📊 Planilha de Ações em Excel", data=excel_bytes,
                                   file_name=f"{nome_arq}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   type="primary", use_container_width=True)
            else:
                st.error("Biblioteca 'openpyxl' não instalada para gerar o ficheiro Excel.")