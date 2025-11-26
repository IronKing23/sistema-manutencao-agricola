from fpdf import FPDF
import pandas as pd
from datetime import datetime

class PDF(FPDF):
    def header(self):
        titulo = 'PAINEL DE CONTROLE DE MANUTENÇÃO AGRÍCOLA'
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, titulo, border=0, align='C')
        self.ln(15)

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
        return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
    except:
        return (255, 255, 255)

def obter_cor_linha(row):
    # Tenta acessar Operacao ou nome
    op_val = row.get('Operacao', '') or row.get('nome', '')
    operacao = str(op_val).lower()
    cor_db = row.get('Cor_Hex')
    
    # 1. Prioridade: Cor do Banco
    if cor_db and isinstance(cor_db, str) and cor_db.startswith('#'):
        return hex_to_rgb(cor_db)

    # 2. Fallback: Cores Padrão
    if 'elet' in operacao or 'elét' in operacao: return (214, 234, 248) # Azul
    if 'mecan' in operacao or 'mecân' in operacao or 'hidraul' in operacao: return (234, 237, 237) # Cinza
    if 'borrach' in operacao or 'pneu' in operacao: return (250, 229, 211) # Laranja
    if 'terceir' in operacao or 'extern' in operacao: return (215, 189, 226) # Roxo
    if 'solda' in operacao or 'funil' in operacao: return (249, 231, 159) # Amarelo
    
    return (255, 255, 255) # Branco

# --- Formatação de Data ---
def formatar_data_segura(valor):
    if valor is None or valor == "" or pd.isnull(valor): return "-"
    try:
        dt = pd.to_datetime(valor, errors='coerce', dayfirst=True)
        if pd.isnull(dt): return str(valor)
        return dt.strftime('%d/%m/%Y %H:%M')
    except: return str(valor)

# --- 1. Ficha Individual (OS Única) ---
def gerar_relatorio_os(dados):
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_draw_color(0, 0, 0); pdf.set_line_width(0.3)
    
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
    titulo = f"ORDEM DE SERVIÇO Nº: {dados.get('numero_os_oficial')}" if dados.get('numero_os_oficial') else f"TICKET DE PENDÊNCIA Nº: {dados.get('id')}"
    pdf.cell(0, 10, titulo, border=1, ln=1, fill=True, align='C')
    
    if dados.get('numero_os_oficial'):
        pdf.set_font('Helvetica', 'I', 8)
        pdf.cell(0, 5, f"(Ref. Ticket #{dados.get('id')})", border=0, ln=1, align='R')
    else: pdf.ln(5)

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
    
    pdf.set_font('Helvetica', 'B', 10); pdf.cell(0, 6, "Descrição:", ln=1)
    pdf.set_font('Helvetica', '', 10)
    desc = str(dados.get('descricao', ''))
    pdf.multi_cell(0, 6, desc, border=1)
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 10); pdf.cell(0, 6, "Relatório Técnico:", ln=1)
    pdf.set_font('Helvetica', '', 10)
    for _ in range(8): pdf.cell(0, 8, "", border=1, ln=1)
    
    pdf.ln(5)
    if pdf.get_y() > 240: pdf.add_page()
    else: pdf.ln(10)
    w = pdf.w / 3.2
    pdf.cell(w, 0, "_"*25, align='C'); pdf.cell(w, 0, "_"*25, align='C'); pdf.cell(0, 0, "_"*25, align='C', ln=1)
    pdf.ln(5); pdf.set_font('Helvetica', '', 8)
    pdf.cell(w, 5, "Solicitante", align='C'); pdf.cell(w, 5, "Mecânico", align='C'); pdf.cell(0, 5, "Gestor", align='C', ln=1)
    
    return bytes(pdf.output(dest='S'))

# --- 2. Relatório Geral (Paisagem) ---
def gerar_relatorio_geral(df):
    pdf = PDF(orientation='L', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    cols = [("Ticket", 15), ("OS Oficial", 25), ("Frota", 20), ("Modelo", 30), ("Prio.", 15),
            ("Status", 25), ("Local", 30), ("Abertura", 30), ("Tipo", 25), ("Descrição", 60)]
    
    pdf.set_font('Helvetica', 'B', 9); pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255, 255, 255)
    for nome, largura in cols: pdf.cell(largura, 8, nome, border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0); pdf.set_font('Helvetica', '', 8)
    line_height = 6
    cores_usadas = {} 
    
    for _, row in df.iterrows():
        dados_linha = [
            str(row.get('Ticket', '')), str(row.get('OS_Oficial', '')) if row.get('OS_Oficial') else "-",
            str(row.get('frota', '')), str(row.get('modelo', ''))[:15], str(row.get('prioridade', '')), str(row.get('status', '')),
            str(row.get('Local', '')), str(row.get('Data', '')), str(row.get('Operacao', '')), str(row.get('descricao', ''))
        ]
        
        max_lines = 1
        for i, texto in enumerate(dados_linha):
            width = cols[i][1]
            if pdf.get_string_width(texto) > (width - 2):
                lines_needed = int(pdf.get_string_width(texto) / (width - 2)) + 1
                if lines_needed > max_lines: max_lines = lines_needed
        if max_lines > 4: max_lines = 4
        row_height = line_height * max_lines
        
        if pdf.get_y() + row_height > pdf.page_break_trigger:
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 9); pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255, 255, 255)
            for nome, largura in cols: pdf.cell(largura, 8, nome, border=1, fill=True, align='C')
            pdf.ln(); pdf.set_text_color(0, 0, 0); pdf.set_font('Helvetica', '', 8)

        rgb_cor = obter_cor_linha(row)
        nome_operacao = str(row.get('Operacao', ''))
        if nome_operacao and nome_operacao not in cores_usadas:
            cores_usadas[nome_operacao] = rgb_cor

        pdf.set_fill_color(*rgb_cor)
        x_start = pdf.get_x(); y_start = pdf.get_y()
        pdf.rect(x_start, y_start, sum(c[1] for c in cols), row_height, 'F')
        
        for i, texto in enumerate(dados_linha):
            width = cols[i][1]; x_current = pdf.get_x()
            align = 'L' if i == 9 else 'C'
            pdf.multi_cell(width, line_height, texto, border=1, align=align, fill=False)
            pdf.set_xy(x_current + width, y_start)
        pdf.set_xy(x_start, y_start + row_height)

    pdf.ln(8)
    if pdf.get_y() > 180: pdf.add_page()
    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(0, 5, "LEGENDA:", ln=1)
    pdf.set_font('Helvetica', '', 8)
    if not cores_usadas: pdf.cell(0, 5, "-", ln=1)
    else:
        for operacao in sorted(cores_usadas.keys()):
            cor_rgb = cores_usadas[operacao]
            if pdf.get_x() > 250: pdf.ln(5)
            pdf.set_fill_color(*cor_rgb)
            pdf.rect(pdf.get_x(), pdf.get_y(), 4, 4, 'F')
            pdf.set_x(pdf.get_x() + 5)
            largura = pdf.get_string_width(operacao) + 10
            pdf.cell(largura, 4, operacao)
            
    return bytes(pdf.output(dest='S'))

# --- 3. Prontuário da Máquina (ATUALIZADO COM CORES E GRÁFICO) ---
def gerar_prontuario_maquina(frota_nome, df_historico, kpis):
    pdf = PDF()
    pdf.add_page()
    
    # --- TÍTULO ---
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 10, f"PRONTUÁRIO: {frota_nome}", 0, 1, 'C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f"Gerado em {datetime.now().strftime('%d/%m/%Y')}", 0, 1, 'C')
    pdf.ln(5)
    
    # --- KPIs ---
    pdf.set_fill_color(240, 248, 255)
    pdf.rect(10, pdf.get_y(), 190, 25, 'F')
    pdf.set_xy(10, pdf.get_y()+2)
    col_w = 190/4
    
    def kpi(t, v, x):
        pdf.set_xy(x, pdf.get_y())
        pdf.set_font('Helvetica', '', 8); pdf.set_text_color(100)
        pdf.cell(col_w, 5, t, 0, 2, 'C')
        pdf.set_font('Helvetica', 'B', 12); pdf.set_text_color(0)
        pdf.cell(col_w, 8, str(v), 0, 0, 'C')
        
    y = pdf.get_y()
    kpi("TOTAL", kpis['total'], 10)
    pdf.set_y(y); kpi("DEFEITO", kpis['comum'], 10+col_w)
    pdf.set_y(y); kpi("TEMPO", kpis['tempo'], 10+col_w*2)
    pdf.set_y(y); kpi("ÚLTIMA", kpis['ultima_data'], 10+col_w*3)
    pdf.ln(20)

    # --- GRÁFICO DE BARRAS COLORIDO (NOVO) ---
    if not df_historico.empty:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 8, "DISTRIBUIÇÃO DE OCORRÊNCIAS", 0, 1, 'L')
        
        contagem = df_historico['Operacao'].value_counts().head(5)
        max_val = contagem.max()
        bar_h = 6
        start_x = 40
        max_bar_w = 130
        
        pdf.set_font('Helvetica', '', 8)
        
        # Cria mapa de cores temporário para o gráfico
        mapa_cores = {}
        for _, row in df_historico.iterrows():
            op = str(row.get('Operacao', ''))
            if op not in mapa_cores:
                mapa_cores[op] = obter_cor_linha(row)

        for op, qtd in contagem.items():
            op_str = str(op)
            pdf.set_xy(10, pdf.get_y())
            pdf.cell(30, bar_h, op_str[:15], 0, 0, 'R')
            
            largura = (qtd / max_val) * max_bar_w if max_val > 0 else 0
            
            # Usa a cor específica da operação
            cor = mapa_cores.get(op_str, (200, 200, 200))
            pdf.set_fill_color(*cor)
            
            pdf.rect(start_x, pdf.get_y()+1, largura, bar_h-2, 'F')
            pdf.set_xy(start_x + largura + 2, pdf.get_y())
            pdf.cell(10, bar_h, str(qtd), 0, 1)
            
        pdf.ln(5)

    # --- TABELA DETALHADA COLORIDA ---
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 8, "REGISTRO DE ATIVIDADES", 0, 1, 'L')
    
    cols = [("Data", 25), ("Tipo", 30), ("Status", 25), ("Ticket", 15), ("Descrição", 95)]
    pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255); pdf.set_font('Helvetica', 'B', 8)
    for n, w in cols: pdf.cell(w, 7, n, 1, 0, 'C', True)
    pdf.ln(); pdf.set_text_color(0); pdf.set_font('Helvetica', '', 8)
    
    for _, row in df_historico.iterrows():
        # Usa a cor da operação para o fundo da linha
        rgb_cor = obter_cor_linha(row)
        pdf.set_fill_color(*rgb_cor)
        
        desc = str(row.get('Descricao', ''))
        # Calcula altura
        lines = pdf.multi_cell(95, 5, desc, split_only=True)
        h = max(len(lines)*5, 6)
        
        if pdf.get_y() + h > 270:
            pdf.add_page()
            pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255); pdf.set_font('Helvetica', 'B', 8)
            for n, w in cols: pdf.cell(w, 7, n, 1, 0, 'C', True)
            pdf.ln(); pdf.set_text_color(0); pdf.set_font('Helvetica', '', 8)
            pdf.set_fill_color(*rgb_cor) # Restaura cor

        # Desenha Fundo Colorido
        x = pdf.get_x(); y = pdf.get_y()
        pdf.rect(x, y, 190, h, 'F')
        
        dt_val = row.get('Data')
        dt = formatar_data_segura(dt_val).split(' ')[0]
        
        # Escreve dados (fill=False pois já desenhamos o retângulo)
        pdf.cell(25, h, dt, 1, 0, 'C', False)
        pdf.cell(30, h, str(row.get('Operacao', ''))[:15], 1, 0, 'C', False)
        pdf.cell(25, h, str(row.get('Status', '')), 1, 0, 'C', False)
        pdf.cell(15, h, str(row.get('Ticket', '')), 1, 0, 'C', False)
        
        pdf.set_xy(x + 95, y) # Ajusta X para a descrição
        pdf.multi_cell(95, 5, desc, 1, 'L', False)
        
        pdf.set_xy(10, y + h) # Próxima linha

    return bytes(pdf.output(dest='S'))

# --- 4. Relatório de KPIs (MTBF/MTTR) ---
def gerar_relatorio_kpi(kpis, df_falhas, filtros_texto):
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

    # --- QUADRO DE INDICADORES (GRID 2x2) ---
    pdf.set_fill_color(240, 248, 255) # Azul clarinho
    y_start = pdf.get_y()
    
    # Desenha o fundo do quadro
    pdf.rect(10, y_start, 190, 30, 'F')
    
    # Configurações das células
    w_col = 190 / 4
    h_row = 15
    
    def desenhar_kpi(titulo, valor, x, y, destaque=False):
        pdf.set_xy(x, y)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(w_col, 6, titulo, 0, 2, 'C')
        
        pdf.set_font('Helvetica', 'B', 14)
        if destaque: pdf.set_text_color(200, 0, 0) # Vermelho para destaque negativo
        else: pdf.set_text_color(0, 0, 0)
        pdf.cell(w_col, 8, str(valor), 0, 0, 'C')

    # Linha única com 4 colunas
    desenhar_kpi("MTBF (Confiabilidade)", kpis['mtbf'], 10, y_start+8)
    desenhar_kpi("MTTR (Eficiência)", kpis['mttr'], 10 + w_col, y_start+8)
    desenhar_kpi("DISPONIBILIDADE", kpis['disp'], 10 + w_col*2, y_start+8)
    desenhar_kpi("TOTAL DE FALHAS", kpis['falhas'], 10 + w_col*3, y_start+8)

    pdf.ln(35)

    # --- TOP MAQUINAS QUEBRADAS (Simulação de Gráfico) ---
    if not df_falhas.empty:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, "TOP 5 - MÁQUINAS COM MAIS FALHAS", 0, 1, 'L')
        
        contagem = df_falhas['frota'].astype(str).value_counts().head(5)
        max_val = contagem.max()
        bar_h = 6
        start_x = 40
        max_bar_w = 130
        
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(0)
        
        for frota, qtd in contagem.items():
            pdf.set_xy(10, pdf.get_y())
            pdf.cell(30, bar_h, frota[:15], 0, 0, 'R')
            
            largura = (qtd / max_val) * max_bar_w if max_val > 0 else 0
            
            # Cor vermelha suave para as barras
            pdf.set_fill_color(231, 76, 60)
            pdf.rect(start_x, pdf.get_y()+1, largura, bar_h-2, 'F')
            
            pdf.set_xy(start_x + largura + 2, pdf.get_y())
            pdf.cell(10, bar_h, str(qtd), 0, 1)
        
        pdf.ln(8)

    # --- TABELA DE DADOS ---
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, "REGISTRO DETALHADO DE FALHAS", 0, 1, 'L')
    
    # Cabeçalho da Tabela
    cols = [("Data", 25), ("Frota", 25), ("Modelo", 35), ("Duração", 20), ("Tipo", 30), ("Causa/Desc.", 55)]
    pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255); pdf.set_font('Helvetica', 'B', 8)
    for n, w in cols: pdf.cell(w, 7, n, 1, 0, 'C', True)
    pdf.ln(); pdf.set_text_color(0); pdf.set_font('Helvetica', '', 8)
    
    # Linhas
    for _, row in df_falhas.iterrows():
        # Zebrado ou cor por tipo (opcional, aqui usando cor simples alternada ou branca)
        rgb_cor = obter_cor_linha(row) # Usa a mesma lógica de cores do sistema
        pdf.set_fill_color(*rgb_cor)

        desc = str(row.get('classificacao', '')) + ": " + str(row.get('tipo_servico', ''))
        # Calcula altura baseada no tamanho do modelo (que pode ser grande)
        modelo_str = str(row.get('modelo', ''))
        
        h = 7
        
        # Verifica quebra de página
        if pdf.get_y() + h > 270:
            pdf.add_page()
            pdf.set_fill_color(50, 50, 50); pdf.set_text_color(255); pdf.set_font('Helvetica', 'B', 8)
            for n, w in cols: pdf.cell(w, 7, n, 1, 0, 'C', True)
            pdf.ln(); pdf.set_text_color(0); pdf.set_font('Helvetica', '', 8)
            pdf.set_fill_color(*rgb_cor)

        # Dados Formatados
        dt = formatar_data_segura(row.get('abertura')).split(' ')[0]
        duracao = f"{row.get('duracao_horas', 0):.1f} h"
        
        x = pdf.get_x(); y = pdf.get_y()
        
        pdf.cell(25, h, dt, 1, 0, 'C', True)
        pdf.cell(25, h, str(row.get('frota', '')), 1, 0, 'C', True)
        
        # Modelo (Trunca se for muito grande)
        pdf.cell(35, h, modelo_str[:18], 1, 0, 'L', True)
        
        pdf.cell(20, h, duracao, 1, 0, 'C', True)
        pdf.cell(30, h, str(row.get('tipo_servico', ''))[:15], 1, 0, 'C', True)
        pdf.cell(55, h, str(row.get('classificacao', '')), 1, 0, 'L', True) # Usando classificação como desc
        
        pdf.ln()

    return bytes(pdf.output(dest='S'))