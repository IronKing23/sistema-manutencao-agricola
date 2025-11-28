from fpdf import FPDF
import pandas as pd
from datetime import datetime


class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', align='C')


# --- Funções Auxiliares de Cor ---
def hex_to_rgb(hex_color):
    if not hex_color or not isinstance(hex_color, str) or not hex_color.startswith('#'):
        return (255, 255, 255)

    hex_clean = hex_color.lstrip('#')
    try:
        return tuple(int(hex_clean[i:i + 2], 16) for i in (0, 2, 4))
    except:
        return (255, 255, 255)


def obter_cor_linha(row):
    # Tenta acessar Operacao ou nome
    op_val = row.get('Operacao', '') or row.get('nome', '') or row.get('tipo_servico', '')
    operacao = str(op_val).lower()
    cor_db = row.get('Cor_Hex')

    # 1. Prioridade: Cor do Banco
    if cor_db and isinstance(cor_db, str) and cor_db.startswith('#'):
        return hex_to_rgb(cor_db)

    # 2. Fallback: Cores Padrão (Caso não tenha no banco)
    if 'elet' in operacao or 'elét' in operacao: return (214, 234, 248)  # Azul
    if 'mecan' in operacao or 'mecân' in operacao or 'hidraul' in operacao: return (234, 237, 237)  # Cinza
    if 'borrach' in operacao or 'pneu' in operacao: return (250, 229, 211)  # Laranja
    if 'terceir' in operacao or 'extern' in operacao: return (215, 189, 226)  # Roxo
    if 'solda' in operacao or 'funil' in operacao: return (249, 231, 159)  # Amarelo

    return (255, 255, 255)  # Branco


# --- Formatação de Data ---
def formatar_data_segura(valor):
    if valor is None or valor == "" or pd.isnull(valor): return "-"
    try:
        # Tenta converter se for string ou datetime
        dt = pd.to_datetime(valor, errors='coerce', dayfirst=True)
        if pd.isnull(dt): return str(valor)
        return dt.strftime('%d/%m/%Y %H:%M')
    except:
        return str(valor)


# ==============================================================================
# 1. Ficha Individual (OS Única - Página 6)
# ==============================================================================
def gerar_relatorio_os(dados):
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_draw_color(0, 0, 0);
    pdf.set_line_width(0.3)

    # Título do Documento
    titulo_doc = 'PAINEL DE CONTROLE DE MANUTENÇÃO AGRÍCOLA'
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, titulo_doc, border=0, align='C', ln=1)
    pdf.ln(5)

    def campo(rotulo, valor, w=0, ln=0, fill=False):
        valor = str(valor) if valor is not None and valor != "" else "-"
        pdf.set_font('Helvetica', 'B', 10)
        width_rotulo = pdf.get_string_width(rotulo) + 2
        pdf.cell(width_rotulo, 8, rotulo, border='LTB', fill=fill)
        pdf.set_font('Helvetica', '', 10)
        width_valor = (w - width_rotulo) if w > 0 else 0
        pdf.cell(width_valor, 8, valor, border='TRB', ln=ln, fill=fill)

    pdf.set_fill_color(230, 230, 230)
    pdf.set_font('Helvetica', 'B', 14)
    titulo = f"ORDEM DE SERVIÇO Nº: {dados.get('numero_os_oficial')}" if dados.get(
        'numero_os_oficial') else f"TICKET DE PENDÊNCIA Nº: {dados.get('id')}"
    pdf.cell(0, 10, titulo, border=1, ln=1, fill=True, align='C')

    if dados.get('numero_os_oficial'):
        pdf.set_font('Helvetica', 'I', 8)
        pdf.cell(0, 5, f"(Ref. Ticket #{dados.get('id')})", border=0, ln=1, align='R')
    else:
        pdf.ln(5)

    campo("Status:", dados.get('status'), w=65)
    campo("Prioridade:", dados.get('prioridade'), w=65)
    dt_fmt = formatar_data_segura(dados.get('data_hora'))
    campo("Abertura:", dt_fmt, w=0, ln=1)
    pdf.ln(2)

    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, "DADOS DO EQUIPAMENTO", border=1, ln=1, fill=True)
    campo("Frota:", dados.get('frota'), w=50)
    campo("Modelo:", dados.get('modelo'), w=90)
    campo("Horímetro:", f"{dados.get('horimetro', 0)} h", w=0, ln=1)
    campo("Local:", dados.get('local_atendimento'), w=95)
    campo("Gestão:", dados.get('gestao'), w=0, ln=1)
    pdf.ln(4)

    pdf.cell(0, 6, "DETALHES", border=1, ln=1, fill=True)
    campo("Tipo:", dados.get('operacao'), w=95)
    campo("Executante:", dados.get('executante') or "N/A", w=0, ln=1)
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 10);
    pdf.cell(0, 6, "Descrição:", ln=1)
    pdf.set_font('Helvetica', '', 10)
    desc = str(dados.get('descricao', ''))
    pdf.multi_cell(0, 6, desc, border=1)
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 10);
    pdf.cell(0, 6, "Relatório Técnico / Observações:", ln=1)
    pdf.set_font('Helvetica', '', 10)
    for _ in range(8): pdf.cell(0, 8, "", border=1, ln=1)

    pdf.ln(5)
    # Assinaturas
    if pdf.get_y() > 240:
        pdf.add_page()
    else:
        pdf.ln(10)
    w = pdf.w / 3.2
    pdf.cell(w, 0, "_" * 25, align='C');
    pdf.cell(w, 0, "_" * 25, align='C');
    pdf.cell(0, 0, "_" * 25, align='C', ln=1)
    pdf.ln(5);
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(w, 5, "Solicitante", align='C');
    pdf.cell(w, 5, "Mecânico", align='C');
    pdf.cell(0, 5, "Gestor", align='C', ln=1)

    return bytes(pdf.output(dest='S'))


# ==============================================================================
# 2. Relatório Geral (Paisagem - Página 1) -> ATUALIZADO AQUI
# ==============================================================================
def gerar_relatorio_geral(df):
    # Formato A4 Paisagem (Width ~297mm)
    pdf = PDF(orientation='L', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    titulo = 'RELATÓRIO GERAL DE ORDENS DE SERVIÇO'
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, titulo, border=0, align='C', ln=1)
    pdf.ln(5)

    # --- DEFINIÇÃO DAS COLUNAS (Largura Ajustada para caber na folha) ---
    # Total Width Disponível: ~277mm (com margens de 10mm)
    # Colunas: Ticket, OS, Frota, Modelo, Gestão, Prio, Status, Local, Data, Tempo, Tipo, Descrição
    cols = [
        ("Tk", 10),
        ("OS", 15),
        ("Frota", 18),
        ("Modelo", 22),
        ("Gestão", 20),  # NOVA
        ("Prio", 12),
        ("Status", 20),
        ("Local", 25),
        ("Data", 25),
        ("Tempo", 15),  # NOVA
        ("Tipo", 25),
        ("Descrição", 65)
    ]

    # Cabeçalho da Tabela
    pdf.set_font('Helvetica', 'B', 8);
    pdf.set_fill_color(50, 50, 50);
    pdf.set_text_color(255, 255, 255)
    for nome, largura in cols: pdf.cell(largura, 8, nome, border=1, fill=True, align='C')
    pdf.ln()

    pdf.set_text_color(0, 0, 0);
    pdf.set_font('Helvetica', '', 7)  # Fonte menor para caber tudo
    line_height = 6
    cores_usadas = {}

    for _, row in df.iterrows():
        # Busca dados do DataFrame (usando .get para evitar erro se coluna não existir)
        dados_linha = [
            str(row.get('Ticket', '')),
            str(row.get('OS_Oficial', '')) if row.get('OS_Oficial') else "-",
            str(row.get('frota', '')),
            str(row.get('modelo', ''))[:12],  # Trunca modelo longo
            str(row.get('Gestao', ''))[:12],  # Trunca gestão longa
            str(row.get('prioridade', ''))[:3],  # Alta -> Alt
            str(row.get('status', '')),
            str(row.get('Local', ''))[:15],
            str(row.get('Data', '')),
            str(row.get('Tempo_Aberto', '')),
            str(row.get('Operacao', ''))[:15],
            str(row.get('descricao', ''))
        ]

        # Calcula altura da linha (baseado na descrição que é a maior)
        max_lines = 1
        for i, texto in enumerate(dados_linha):
            width = cols[i][1]
            if pdf.get_string_width(texto) > (width - 2):
                lines_needed = int(pdf.get_string_width(texto) / (width - 2)) + 1
                if lines_needed > max_lines: max_lines = lines_needed
        if max_lines > 4: max_lines = 4
        row_height = line_height * max_lines

        # Quebra de página
        if pdf.get_y() + row_height > pdf.page_break_trigger:
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 8);
            pdf.set_fill_color(50, 50, 50);
            pdf.set_text_color(255, 255, 255)
            for nome, largura in cols: pdf.cell(largura, 8, nome, border=1, fill=True, align='C')
            pdf.ln();
            pdf.set_text_color(0, 0, 0);
            pdf.set_font('Helvetica', '', 7)

        # Cor da Linha
        rgb_cor = obter_cor_linha(row)
        nome_operacao = str(row.get('Operacao', ''))
        if nome_operacao and nome_operacao not in cores_usadas:
            cores_usadas[nome_operacao] = rgb_cor

        pdf.set_fill_color(*rgb_cor)
        x_start = pdf.get_x();
        y_start = pdf.get_y()
        pdf.rect(x_start, y_start, sum(c[1] for c in cols), row_height, 'F')

        for i, texto in enumerate(dados_linha):
            width = cols[i][1];
            x_current = pdf.get_x()
            align = 'L' if i == 11 else 'C'  # Descrição alinhada à esquerda
            pdf.multi_cell(width, line_height, texto, border=1, align=align, fill=False)
            pdf.set_xy(x_current + width, y_start)
        pdf.set_xy(x_start, y_start + row_height)

    return bytes(pdf.output(dest='S'))


# --- 3. Prontuário da Máquina ---
def gerar_prontuario_maquina(frota_nome, df_historico, kpis, gestor=""):
    pdf = PDF()
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, f"PRONTUÁRIO: {frota_nome}", 0, 1, 'C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f"Gerado em {datetime.now().strftime('%d/%m/%Y')} | Gestor Resp.: {gestor}", 0, 1, 'C')
    pdf.ln(5)

    pdf.set_fill_color(240, 248, 255)
    pdf.rect(10, pdf.get_y(), 190, 25, 'F')
    pdf.set_xy(10, pdf.get_y() + 2)
    col_w = 190 / 4

    def kpi(t, v, x):
        pdf.set_xy(x, pdf.get_y())
        pdf.set_font('Helvetica', '', 8);
        pdf.set_text_color(100)
        pdf.cell(col_w, 5, t, 0, 2, 'C')
        pdf.set_font('Helvetica', 'B', 12);
        pdf.set_text_color(0)
        pdf.cell(col_w, 8, str(v), 0, 0, 'C')

    y = pdf.get_y()
    kpi("INTERVENÇÕES", kpis['total'], 10)
    pdf.set_y(y);
    kpi("FALHAS (CORRETIVA)", kpis.get('falhas', 0), 10 + col_w)
    pdf.set_y(y);
    kpi("TEMPO PARADO", kpis['tempo'], 10 + col_w * 2)
    pdf.set_y(y);
    kpi("ÚLTIMA DATA", kpis['ultima_data'], 10 + col_w * 3)
    pdf.ln(25)

    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, "HISTÓRICO DE MANUTENÇÕES", 0, 1, 'L')

    cols = [("Data", 25), ("Tipo", 30), ("Status", 25), ("Ticket", 15), ("Detalhes & Descrição", 95)]
    pdf.set_fill_color(50, 50, 50);
    pdf.set_text_color(255);
    pdf.set_font('Helvetica', 'B', 8)
    for n, w in cols: pdf.cell(w, 7, n, 1, 0, 'C', True)
    pdf.ln();
    pdf.set_text_color(0);
    pdf.set_font('Helvetica', '', 8)

    for _, row in df_historico.iterrows():
        rgb_cor = obter_cor_linha(row)
        pdf.set_fill_color(*rgb_cor)

        solic = str(row.get('Solicitante', '')) or 'N/A'
        classe = str(row.get('classificacao', ''))
        parada = "SIM" if row.get('maquina_parada') == 1 else "NÃO"

        desc_completa = f"SOLIC.: {solic} | CLASSE: {classe} | PAROU: {parada}\nDESCRIÇÃO: {str(row.get('Descricao', ''))}"

        lines = pdf.multi_cell(95, 4, desc_completa, split_only=True)
        h = max(len(lines) * 4 + 2, 8)

        if pdf.get_y() + h > 275:
            pdf.add_page()
            pdf.set_fill_color(50, 50, 50);
            pdf.set_text_color(255);
            pdf.set_font('Helvetica', 'B', 8)
            for n, w in cols: pdf.cell(w, 7, n, 1, 0, 'C', True)
            pdf.ln();
            pdf.set_text_color(0);
            pdf.set_font('Helvetica', '', 8)
            pdf.set_fill_color(*rgb_cor)

        x = pdf.get_x();
        y = pdf.get_y()
        pdf.rect(x, y, 190, h, 'F')

        dt = formatar_data_segura(row.get('Data')).split(' ')[0]

        pdf.cell(25, h, dt, 1, 0, 'C', False)
        pdf.cell(30, h, str(row.get('Operacao', ''))[:15], 1, 0, 'C', False)
        pdf.cell(25, h, str(row.get('Status', '')), 1, 0, 'C', False)
        pdf.cell(15, h, str(row.get('Ticket', '')), 1, 0, 'C', False)

        pdf.set_xy(x + 95, y + 1)
        pdf.multi_cell(95, 4, desc_completa, 0, 'L', False)
        pdf.set_xy(10, y + h)

    return bytes(pdf.output(dest='S'))


# --- Função Auxiliar de Desenho de Gráfico de Barras ---
def desenhar_grafico_barras(pdf, titulo, dados, y_pos, cor_barra=(100, 100, 100), max_w=180):
    """
    dados: lista de tuplas [(rótulo, valor_num), ...]
    """
    pdf.set_xy(10, y_pos)
    pdf.set_font('Helvetica', 'B', 10);
    pdf.set_text_color(0)
    pdf.cell(0, 8, titulo, 0, 1, 'L')

    if not dados:
        pdf.set_font('Helvetica', 'I', 9);
        pdf.cell(0, 6, "Sem dados.", 0, 1)
        return pdf.get_y() + 5

    # Encontra o máximo para escala
    max_val = max([v for k, v in dados]) if dados else 1
    if max_val == 0: max_val = 1

    bar_height = 6
    label_w = 45  # Largura para o rótulo

    pdf.set_font('Helvetica', '', 8)

    for rotulo, valor in dados:
        # Rótulo
        pdf.cell(label_w, bar_height, str(rotulo)[:25], 0, 0, 'R')

        # Barra
        bar_w = (valor / max_val) * (max_w - label_w - 20)
        pdf.set_fill_color(*cor_barra)
        pdf.rect(pdf.get_x() + 2, pdf.get_y() + 1, bar_w, bar_height - 2, 'F')

        # Valor texto
        pdf.set_xy(pdf.get_x() + 2 + bar_w + 2, pdf.get_y())
        pdf.cell(15, bar_height, str(valor), 0, 1, 'L')

    return pdf.get_y() + 8


# --- 4. Relatório de KPIs (ATUALIZADO COM MÚLTIPLOS GRÁFICOS) ---
def gerar_relatorio_kpi(kpis, df_falhas, filtros_texto, graficos_data=None):
    pdf = PDF()
    pdf.add_page()

    # --- CABEÇALHO ---
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, "RELATÓRIO DE PERFORMANCE (MTBF & MTTR)", 0, 1, 'C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'C')
    pdf.set_font('Helvetica', 'I', 8)
    pdf.multi_cell(0, 5, f"Filtros Aplicados: {filtros_texto}", 0, 'C')
    pdf.ln(5)

    # --- QUADRO DE INDICADORES ---
    pdf.set_fill_color(240, 248, 255)
    y_start = pdf.get_y()
    pdf.rect(10, y_start, 190, 30, 'F')
    w_col = 190 / 4

    def desenhar_kpi(titulo, valor, x, y):
        pdf.set_xy(x, y)
        pdf.set_font('Helvetica', '', 9);
        pdf.set_text_color(100, 100, 100)
        pdf.cell(w_col, 6, titulo, 0, 2, 'C')
        pdf.set_font('Helvetica', 'B', 14);
        pdf.set_text_color(0, 0, 0)
        pdf.cell(w_col, 8, str(valor), 0, 0, 'C')

    desenhar_kpi("MTBF (Confiabilidade)", kpis['mtbf'], 10, y_start + 8)
    desenhar_kpi("MTTR (Eficiência)", kpis['mttr'], 10 + w_col, y_start + 8)
    desenhar_kpi("DISPONIBILIDADE", kpis['disp'], 10 + w_col * 2, y_start + 8)
    desenhar_kpi("TOTAL DE FALHAS", kpis['falhas'], 10 + w_col * 3, y_start + 8)

    pdf.ln(35)

    # --- GRÁFICOS RESUMIDOS ---
    if graficos_data:
        current_y = pdf.get_y()

        # 1. Volume por Turno
        if 'turno_qtd' in graficos_data:
            current_y = desenhar_grafico_barras(
                pdf,
                "VOLUME DE OCORRÊNCIAS POR TURNO",
                graficos_data['turno_qtd'],
                current_y,
                cor_barra=(52, 152, 219)  # Azul
            )

        # 2. Top Máquinas
        if 'top_maquinas' in graficos_data and (pdf.get_y() < 200):
            current_y = desenhar_grafico_barras(
                pdf,
                "TOP 5 MÁQUINAS COM MAIS FALHAS",
                graficos_data['top_maquinas'],
                current_y,
                cor_barra=(231, 76, 60)  # Vermelho
            )

        # 3. Pareto (Top Tipos)
        if 'pareto' in graficos_data:
            # Verifica se cabe na página, senão cria nova
            if current_y > 220:
                pdf.add_page();
                current_y = 20

            current_y = desenhar_grafico_barras(
                pdf,
                "TOP TIPOS DE DEFEITO (PARETO)",
                graficos_data['pareto'],
                current_y,
                cor_barra=(155, 89, 182)  # Roxo
            )

    pdf.ln(10)

    # --- TABELA DE DADOS ---
    if pdf.get_y() > 250: pdf.add_page()

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, "REGISTRO DETALHADO DE FALHAS", 0, 1, 'L')

    cols = [("Data", 25), ("Frota", 25), ("Trn", 10), ("Modelo", 30), ("Dur.", 15), ("Tipo", 25), ("Defeito", 55)]
    pdf.set_fill_color(50, 50, 50);
    pdf.set_text_color(255);
    pdf.set_font('Helvetica', 'B', 8)
    for n, w in cols: pdf.cell(w, 7, n, 1, 0, 'C', True)
    pdf.ln();
    pdf.set_text_color(0);
    pdf.set_font('Helvetica', '', 8)

    for _, row in df_falhas.iterrows():
        rgb_cor = obter_cor_linha(row)
        pdf.set_fill_color(*rgb_cor)

        h = 7
        if pdf.get_y() + h > 275:
            pdf.add_page()
            pdf.set_fill_color(50, 50, 50);
            pdf.set_text_color(255);
            pdf.set_font('Helvetica', 'B', 8)
            for n, w in cols: pdf.cell(w, 7, n, 1, 0, 'C', True)
            pdf.ln();
            pdf.set_text_color(0);
            pdf.set_font('Helvetica', '', 8)
            pdf.set_fill_color(*rgb_cor)

        dt = formatar_data_segura(row.get('abertura')).split(' ')[0]
        duracao = f"{row.get('duracao_horas', 0):.1f} h"

        # Turno abreviado
        turno_full = str(row.get('Turno', ''))
        turno_short = "A" if "A" in turno_full else ("B" if "B" in turno_full else ("C" if "C" in turno_full else "-"))

        pdf.cell(25, h, dt, 1, 0, 'C', True)
        pdf.cell(25, h, str(row.get('frota', '')), 1, 0, 'C', True)
        pdf.cell(10, h, turno_short, 1, 0, 'C', True)
        pdf.cell(30, h, str(row.get('modelo', ''))[:15], 1, 0, 'L', True)
        pdf.cell(15, h, duracao, 1, 0, 'C', True)
        pdf.cell(25, h, str(row.get('tipo_servico', ''))[:12], 1, 0, 'C', True)
        pdf.cell(55, h, str(row.get('classificacao', '')), 1, 0, 'L', True)
        pdf.ln()

    return bytes(pdf.output(dest='S'))