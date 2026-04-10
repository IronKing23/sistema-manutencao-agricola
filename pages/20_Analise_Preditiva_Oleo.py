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

# Tentativa segura de importar pacotes para Gráficos no PDF e Geração de Excel
try:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

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
    subtitle="Diagnósticos, Histórico de Ações (Banco de Dados) e Geração de OS Preditiva.",
    icon=icon_oleo
)


# Inicializa Tabela de Fecho de Ciclo no Banco de Dados
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


# Sincroniza o DataFrame da memória com o Banco de Dados
def sincronizar_amostras_bd(df):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Inserir amostras novas no banco (se não existirem)
    for amostra in df['NUM_AMOSTRA'].dropna().unique():
        amostra_str = str(amostra).strip()
        if amostra_str and amostra_str != '-':
            cursor.execute(
                "INSERT OR IGNORE INTO analises_oleo_feedback (amostra, acao_gestao, status_acao) VALUES (?, '', 'Pendente')",
                (amostra_str,))
    conn.commit()

    # Carregar dados salvos e mesclar com o DataFrame em memória
    df_bd = pd.read_sql(
        "SELECT amostra as NUM_AMOSTRA, acao_gestao as ACAO_GESTAO, status_acao as STATUS_ACAO FROM analises_oleo_feedback",
        conn)
    conn.close()

    df['NUM_AMOSTRA'] = df['NUM_AMOSTRA'].astype(str).str.strip()
    df_bd['NUM_AMOSTRA'] = df_bd['NUM_AMOSTRA'].astype(str).str.strip()

    # Limpa colunas antigas caso seja uma ressincronização
    if 'ACAO_GESTAO' in df.columns: df = df.drop(columns=['ACAO_GESTAO', 'STATUS_ACAO'])

    # Left Join para trazer as ações digitadas pela gestão
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
    val_str = str(val).replace(',', '.').replace('<', '').replace('>', '').replace('%', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0


@st.cache_data(show_spinner="Analisando química, decodificando e sincronizando com Banco de Dados...", ttl=600)
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
            'FROTA': find_col(['tag', 'frota', 'chassi']),
            'FAMILIA': find_col(['familia', 'famalia']),
            'MODELO': find_col(['modelo']),
            'CLIENTE': find_col(['cliente', 'empresa']),
            'OBRA': find_col(['obra', 'obraunidade']),
            'NUM_AMOSTRA': find_col(['amostra', 'numero']),
            'DATA_COLETA': find_col(['datadecoleta', 'datacoleta', 'coleta']),
            'DATA_LIBERACAO': find_col(['liberacao', 'resultado']),
            'STATUS_LAUDO': find_col(['status', 'condicao', 'avaliacao']),
            'AVALIACAO': find_col(['avaliao', 'avaliacao', 'parecer']),
            'ACOES_INSPECAO': find_col(['inspeao', 'inspecao']),
            'COMPARTIMENTO': find_col(['compartimento', 'componente']),
            'PARECER_LAB': find_col(['comentario']),
            'HORAS_OLEO': find_col(['horasdooleo', 'holeo']),
            'HORAS_EQUIP': find_col(['horasdoequipamento', 'hequip']),
            'INDICE_PQ': find_col(['pqindex', 'indicepq', 'pq']),
        }

        if not col_map['FROTA'] or not col_map['STATUS_LAUDO']:
            st.error("Não consegui encontrar as colunas de 'Tag / Frota' ou 'Status' no seu arquivo.")
            return None

        rename_dict = {v: k for k, v in col_map.items() if v is not None}
        df = df.rename(columns=rename_dict)

        if 'FROTA' in df.columns:
            df['FROTA'] = df['FROTA'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace('nan', '-')
        if 'NUM_AMOSTRA' in df.columns:
            df['NUM_AMOSTRA'] = df['NUM_AMOSTRA'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace('nan',
                                                                                                               '-')

        if 'DATA_COLETA' in df.columns: df['DATA_COLETA'] = pd.to_datetime(df['DATA_COLETA'], dayfirst=True,
                                                                           errors='coerce')
        if 'DATA_LIBERACAO' in df.columns: df['DATA_LIBERACAO'] = pd.to_datetime(df['DATA_LIBERACAO'], dayfirst=True,
                                                                                 errors='coerce')

        metais_busca = {
            'Ferro': ['ferro'], 'Cobre': ['cobre'], 'Alumínio': ['aluminio', 'alumnio'], 'Cromo': ['cromo'],
            'Chumbo': ['chumbo'], 'Silício': ['silicio', 'silcio'], 'Sódio': ['sodio', 'sdio'], 'Água': ['agua', 'gua'],
            'Viscosidade': ['100oc', '100c', 'viscosidade100', 'viscosidadedooleo'], 'Diluição Diesel': ['diluicao']
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
            if any(x in v for x in ['ALERT', 'ATENÇÃO', 'MONITORAR', 'AMARELO']): return 'Alerta'
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
            if r['STATUS_CORRIGIDO'] == 'Normal': return "✅ Sistema operando dentro dos parâmetros."
            alertas = []
            if r.get('Silício', 0) > 15 and r.get('Ferro', 0) > 15: alertas.append(
                "🌪️ Entrada de poeira (Silício) causando desgaste (Ferro).")
            if r.get('Cobre', 0) > 10: alertas.append("⚙️ Desgaste em bronzinas/mancais.")
            if r.get('INDICE_PQ', 0) > 40: alertas.append("🧲 Possível fadiga severa ou quebra (PQ Alto).")
            if r.get('Diluição Diesel', 0) > 4.0: alertas.append("⛽ Excesso de combustível no óleo.")
            if len(alertas) == 0: return "⚠️ Verificar laudo original."
            return "\n".join(alertas)

        df['DIAGNOSTICO_IA'] = df.apply(gerar_diagnostico_ia, axis=1)

        # Chama a sincronização com o banco de dados antes de devolver o DF
        df = sincronizar_amostras_bd(df)

        return df
    except Exception as e:
        st.error(f"Erro na análise de dados: {e}")
        return None


# ==============================================================================
# GERAÇÃO DE EXCEL E PDF (AGORA COM INTEGRAÇÃO DO BANCO DE DADOS)
# ==============================================================================

@st.cache_data(show_spinner="Gerando Planilha de Ações (Excel)...", ttl=60)
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
        "Sinais Vitais (Química)", "AÇÃO DA GESTÃO / RETORNO"
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
        ws.cell(row=row_num, column=10, value=str(r.get('DADOS_RELEVANTES', ''))).alignment = align_left

        # Puxa a Ação registrada no Banco de Dados
        acao_bd = str(r.get('ACAO_GESTAO', '')).strip()
        action_c = ws.cell(row=row_num, column=11, value=acao_bd)
        action_c.fill = PatternFill(start_color="FEFCE8", end_color="FEFCE8", fill_type="solid")
        action_c.border = border

    ws.column_dimensions['A'].width = 15;
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 20;
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 25;
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 15;
    ws.column_dimensions['H'].width = 50
    ws.column_dimensions['I'].width = 40;
    ws.column_dimensions['J'].width = 40
    ws.column_dimensions['K'].width = 50

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


@st.cache_data(show_spinner="Gerando PDF de Ações (Gerencial + OS)...", ttl=60)
def gerar_pdf_plano_acao(df_pdf):
    pdf = PDFPlanoAcaoALS(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    arquivos_temp = []

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

    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, f"Volume Total: {tot} amostras analisadas neste relatorio.", 0, 1, 'C')
    pdf.ln(5)

    y_kpi = pdf.get_y()
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)

    pdf.rect(15, y_kpi, 50, 20, 'DF')
    pdf.set_fill_color(16, 185, 129);
    pdf.rect(15, y_kpi, 2, 20, 'F')
    pdf.set_xy(20, y_kpi + 4);
    pdf.set_font('Arial', 'B', 8);
    pdf.set_text_color(100, 116, 139);
    pdf.cell(40, 4, "STATUS NORMAL", 0, 1, 'L')
    pdf.set_xy(20, y_kpi + 10);
    pdf.set_font('Arial', 'B', 14);
    pdf.set_text_color(15, 23, 42);
    pdf.cell(40, 6, str(norm), 0, 1, 'L')

    pdf.set_fill_color(248, 250, 252);
    pdf.rect(75, y_kpi, 50, 20, 'DF')
    pdf.set_fill_color(245, 158, 11);
    pdf.rect(75, y_kpi, 2, 20, 'F')
    pdf.set_xy(80, y_kpi + 4);
    pdf.set_font('Arial', 'B', 8);
    pdf.set_text_color(100, 116, 139);
    pdf.cell(40, 4, "EM ALERTA", 0, 1, 'L')
    pdf.set_xy(80, y_kpi + 10);
    pdf.set_font('Arial', 'B', 14);
    pdf.set_text_color(15, 23, 42);
    pdf.cell(40, 6, str(ale), 0, 1, 'L')

    pdf.set_fill_color(248, 250, 252);
    pdf.rect(135, y_kpi, 50, 20, 'DF')
    pdf.set_fill_color(239, 68, 68);
    pdf.rect(135, y_kpi, 2, 20, 'F')
    pdf.set_xy(140, y_kpi + 4);
    pdf.set_font('Arial', 'B', 8);
    pdf.set_text_color(100, 116, 139);
    pdf.cell(40, 4, "STATUS CRITICO", 0, 1, 'L')
    pdf.set_xy(140, y_kpi + 10);
    pdf.set_font('Arial', 'B', 14);
    pdf.set_text_color(15, 23, 42);
    pdf.cell(40, 6, str(crit), 0, 1, 'L')

    pdf.set_y(y_kpi + 30)

    if MATPLOTLIB_AVAILABLE and not df_pdf.empty:
        fig, axes = plt.subplots(1, 2, figsize=(8.5, 4))

        s_counts = df_pdf['STATUS_CORRIGIDO'].value_counts()
        colors = ['#10B981' if s == 'Normal' else ('#F59E0B' if s == 'Alerta' else '#EF4444') for s in s_counts.index]
        axes[0].pie(s_counts, labels=s_counts.index, autopct='%1.1f%%', colors=colors, startangle=90,
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
        img_path = tempfile.mktemp(suffix=".png")
        arquivos_temp.append(img_path)
        fig.savefig(img_path, dpi=200, bbox_inches='tight')
        plt.close(fig)

        pdf.image(img_path, x=15, y=pdf.get_y(), w=180)
        pdf.set_y(pdf.get_y() + 85)

    pdf.add_page()

    # ==========================================
    # PÁGINAS DE ORDENS DE SERVIÇO (CARDS)
    # ==========================================
    for _, row in df_pdf.iterrows():
        start_y = pdf.get_y()
        if start_y > 150:
            pdf.add_page()
            start_y = pdf.get_y()

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
        pdf.rect(10, box_equip_y, 190, 18, 'DF')

        pdf.set_xy(12, box_equip_y + 2)
        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(15, 23, 42)

        frota_str = str(row.get('FROTA', '')).encode('latin-1', 'ignore').decode('latin-1')
        comp_str = str(row.get('COMPARTIMENTO', '')).encode('latin-1', 'ignore').decode('latin-1')
        fam_str = str(row.get('Família do equipamento', '')).encode('latin-1', 'ignore').decode('latin-1')
        mod_str = str(row.get('MODELO', '')).encode('latin-1', 'ignore').decode('latin-1')
        hr_oleo = str(row.get('HORAS_OLEO', '0'))
        hr_eq = str(row.get('HORAS_EQUIP', '0'))

        pdf.cell(90, 5, f"TAG/FROTA: {frota_str}", 0, 0, 'L')
        pdf.cell(90, 5, f"COMPARTIMENTO: {comp_str}", 0, 1, 'L')

        pdf.set_x(12)
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(90, 4, f"FAMILIA / MODELO: {fam_str} - {mod_str}", 0, 0, 'L')
        pdf.cell(90, 4, f"HORAS OLEO: {hr_oleo} h  |  HORAS EQUIP: {hr_eq} h", 0, 1, 'L')

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
        pdf.cell(30, 5, "Ferro (Fe)", 1, 0, 'C', fill=True)
        pdf.cell(30, 5, "Cobre (Cu)", 1, 0, 'C', fill=True)
        pdf.cell(30, 5, "Silicio (Si)", 1, 0, 'C', fill=True)
        pdf.cell(30, 5, "Indice PQ", 1, 0, 'C', fill=True)
        pdf.cell(40, 5, "Viscosidade / Diluicao", 1, 1, 'C', fill=True)

        pdf.set_font('Arial', '', 8)
        pdf.set_x(10)
        pdf.cell(30, 5, f"{row.get('Ferro', 0):.0f}", 1, 0, 'C')
        pdf.cell(30, 5, f"{row.get('Cobre', 0):.0f}", 1, 0, 'C')
        pdf.cell(30, 5, f"{row.get('Silício', 0):.0f}", 1, 0, 'C')
        pdf.cell(30, 5, f"{row.get('INDICE_PQ', 0):.0f}", 1, 0, 'C')
        pdf.cell(40, 5, f"V: {row.get('Viscosidade', 0):.1f} | D: {row.get('Diluição Diesel', 0):.1f}", 1, 1, 'C')

        box_acao_y = pdf.get_y() + 4
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(100, 116, 139)
        pdf.rect(10, box_acao_y, 190, 20, 'D')

        pdf.set_xy(12, box_acao_y + 1)
        pdf.set_font('Arial', 'B', 7)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(190, 4, "PLANO DE ACAO E RETORNO DA OFICINA (A Preencher):", 0, 1, 'L')

        # Inteligência de Banco de Dados na Impressão do PDF
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
        pdf.set_draw_color(30, 41, 59)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.set_y(pdf.get_y() + 4)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = tmp.name
    tmp.close()
    pdf.output(pdf_path)
    with open(pdf_path, "rb") as f:
        bytes_pdf = f.read()
    os.remove(pdf_path)

    for img in arquivos_temp:
        try:
            os.remove(img)
        except:
            pass

    return bytes_pdf


# ==============================================================================
# INTERFACE PRINCIPAL E FILTROS
# ==============================================================================

if 'dataset_oleo' not in st.session_state:
    st.session_state['dataset_oleo'] = None

with st.expander("📂 Importar Laudo Laboratorial (Excel/CSV)", expanded=(st.session_state['dataset_oleo'] is None)):
    file_up = st.file_uploader("Faça upload do arquivo exportado do laboratório", type=['xlsx', 'csv'])
    if file_up and st.button("Processar Laudos Químicos 🧪", type="primary"):
        df_oleo = processar_laudo_oleo(file_up)
        if df_oleo is not None:
            st.session_state['dataset_oleo'] = df_oleo
            st.rerun()

if st.session_state['dataset_oleo'] is None:
    ui_empty_state("Aguardando upload dos laudos para rodar o algoritmo e gerar relatórios.", icon="🔬")
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

c1, c2, c3, c4 = st.columns(4)
ui_kpi_card(c1, "Amostras no Filtro", f"{total_amostras}", "🧪", "#3B82F6", "Volume analisado")
ui_kpi_card(c2, "Estado Normal", f"{normais}", "✅", "#10B981", "Desgaste esperado")
ui_kpi_card(c3, "Em Alerta", f"{alertas}", "⚠️", "#F59E0B", "Atenção nas próximas trocas")
ui_kpi_card(c4, "Estado Crítico", f"{criticas}", "🚨", "#EF4444" if criticas > 0 else "#10B981",
            "Exigem plano de ação imediato")

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# ABAS DE VISUALIZAÇÃO E FECHO DE CICLO
# ==============================================================================
tab_tabela, tab_ia, tab_feedback = st.tabs(
    ["📋 Resumo de Pareceres", "🤖 Diagnóstico Autônomo", "🔄 Fecho de Ciclo (Gestão)"])

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
            hide_index=True,
            use_container_width=True,
            height=300
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
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhuma anomalia crítica detectada neste filtro.")

with tab_feedback:
    st.markdown("##### 🔄 Fecho de Ciclo (Registro de Ações)")
    st.caption(
        "Documente a ação tomada pela gestão para cada laudo. Ao salvar, a informação vai para o banco de dados e sairá automaticamente no relatório PDF.")

    # Mostra apenas o que precisa de ação para não poluir
    df_feed_ui = df_view[df_view['STATUS_CORRIGIDO'].isin(['Crítico', 'Alerta'])].copy()

    if not df_feed_ui.empty:
        colunas_editaveis = ['NUM_AMOSTRA', 'FROTA', 'COMPARTIMENTO', 'STATUS_CORRIGIDO', 'ACAO_GESTAO', 'STATUS_ACAO']
        colunas_editaveis = [c for c in colunas_editaveis if c in df_feed_ui.columns]

        edited_df = st.data_editor(
            df_feed_ui[colunas_editaveis],
            column_config={
                "NUM_AMOSTRA": st.column_config.TextColumn("Amostra", disabled=True),
                "FROTA": st.column_config.TextColumn("Máquina", disabled=True),
                "COMPARTIMENTO": st.column_config.TextColumn("Local", disabled=True),
                "STATUS_CORRIGIDO": st.column_config.TextColumn("Status", disabled=True),
                "ACAO_GESTAO": st.column_config.TextColumn("📝 Ação Tomada pela Gestão (Edite aqui)", required=False,
                                                           width="large"),
                "STATUS_ACAO": st.column_config.SelectboxColumn("Situação",
                                                                options=['Pendente', 'Em Andamento', 'Concluída'],
                                                                required=True)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_feedback"
        )

        if st.button("💾 Salvar Ações no Banco de Dados", type="primary"):
            conn = get_db_connection()
            cursor = conn.cursor()
            for _, row in edited_df.iterrows():
                amostra = str(row['NUM_AMOSTRA']).strip()
                acao = str(row.get('ACAO_GESTAO', '')).strip()
                status_acao = str(row.get('STATUS_ACAO', 'Pendente')).strip()
                if amostra and amostra != '-':
                    cursor.execute(
                        "UPDATE analises_oleo_feedback SET acao_gestao = ?, status_acao = ? WHERE amostra = ?",
                        (acao, status_acao, amostra))
            conn.commit()
            conn.close()

            st.toast("Ações atualizadas no banco de dados com sucesso!", icon="✅")
            st.session_state['dataset_oleo'] = sincronizar_amostras_bd(st.session_state['dataset_oleo'])
            import time;

            time.sleep(1);
            st.rerun()
    else:
        st.success("Não há máquinas críticas aguardando feedback no filtro atual.")

# ==============================================================================
# EXPORTAÇÃO (PLANOS DE AÇÃO)
# ==============================================================================
st.markdown("---")
st.markdown("### 📋 Geração de Planos de Ação (Exportação)")
st.caption(
    "Gere os relatórios (Layout no Padrão ALS). Se você preencheu a aba 'Fecho de Ciclo' acima, os PDFs já sairão preenchidos!")

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
        st.success("Tudo limpo! Não há amostras no filtro atual para gerar plano de ação.")
    else:
        c_pdf, c_excel = st.columns(2)

        with st.spinner("Compilando Gráficos Gerenciais e Ordens de Serviço (Padrão ALS)..."):
            excel_bytes = gerar_excel_plano_acao(df_export)
            pdf_bytes = gerar_pdf_plano_acao(df_export)

        nome_arq = f"Plano_Acao_Oleo_{datetime.now().strftime('%d%m%Y')}"

        with c_pdf:
            st.download_button(
                label=f"📄 Caderno de Ações em PDF (Para Imprimir O.S.)",
                data=pdf_bytes,
                file_name=f"{nome_arq}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )

        with c_excel:
            if excel_bytes:
                st.download_button(
                    label=f"📊 Planilha de Ações em Excel (Para Digitar)",
                    data=excel_bytes,
                    file_name=f"{nome_arq}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            else:
                st.error("Biblioteca 'openpyxl' não instalada para gerar Excel.")