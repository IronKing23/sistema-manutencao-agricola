import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import io
import os

# Tenta importar o FPDF para geração do PDF.
try:
    from fpdf import FPDF

    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# --- Configurações Básicas ---
ARQUIVO_CADASTRO = "CHECKLIST_TERCEIROS_CADASTRO.csv"

# Configuração global de exibição de colunas no Streamlit para Padrão BR
CONFIG_COLUNAS_BR = {
    "DATA DA VISTORIA": st.column_config.DateColumn("Data Vistoria", format="DD/MM/YYYY"),
    "DATA RETORNO": st.column_config.DateColumn("Data Retorno", format="DD/MM/YYYY"),
}


# --- Funções de Dados ---
def carregar_dados():
    try:
        df = pd.read_csv(ARQUIVO_CADASTRO)
        df['DATA DA VISTORIA'] = pd.to_datetime(df['DATA DA VISTORIA'], errors='coerce').dt.date
        df['DATA RETORNO'] = pd.to_datetime(df['DATA RETORNO'], errors='coerce').dt.date
        # Garante que a coluna observações exista mesmo em arquivos antigos
        if 'OBSERVACOES' not in df.columns:
            df['OBSERVACOES'] = "-"
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=[
            'DATA DA VISTORIA', 'EMPRESA', 'EQUIPAMENTO', 'MODELO',
            'PLACA', 'SITUAÇÃO', 'DATA RETORNO', 'STATUS', 'OBSERVACOES'
        ])


def salvar_dados(df):
    df.to_csv(ARQUIVO_CADASTRO, index=False)


def limpar_texto_pdf(val):
    """Trata valores nulos, remove emojis para evitar bugs no FPDF e codifica para latin-1."""
    if pd.isna(val) or val is None:
        return ""
    val = str(val)
    # Remove emojis que podem estar nos status
    para_remover = ['🚨', '⚠️', '✅', '❌', '🛡️', '🔄']
    for emoji in para_remover:
        val = val.replace(emoji, '').strip()
    return val.encode('latin-1', 'replace').decode('latin-1')


def formatar_data_br(val):
    """Garante que a data vá para o PDF e Excel no formato DD/MM/YYYY"""
    if pd.isna(val) or val is None or val == "":
        return "-"
    if isinstance(val, (date, datetime)):
        return val.strftime("%d/%m/%Y")
    try:
        return pd.to_datetime(val).strftime("%d/%m/%Y")
    except:
        return str(val)


# Classe FPDF Customizada para adicionar Rodapé com número de páginas
class PDFCedro(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')


def gerar_pdf(df, titulo_relatorio="Relatório de Vistorias de Terceiros"):
    """Gera um PDF Avançado em formato Paisagem (Landscape) com limite seguro de células."""
    pdf = PDFCedro(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- CABEÇALHO ---
    caminho_logo = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logo_cedro.png")
    if os.path.exists(caminho_logo):
        try:
            pdf.image(caminho_logo, x=10, y=8, w=25)
        except:
            pass

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 8, limpar_texto_pdf(titulo_relatorio), ln=True, align='C')

    pdf.set_font("Arial", 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", ln=True, align='C')
    pdf.ln(8)

    # --- TABELA DE DADOS ---
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 8)

    # Ajuste preciso das larguras (Total máx: ~277mm)
    col_widths = [19, 45, 28, 19, 19, 23, 26, 98]
    headers = ['Vistoria', 'Empresa', 'Equipamento', 'Placa', 'Retorno', 'Situação', 'Status', 'Observações']

    # Renderiza Cabeçalho da Tabela com cor de fundo
    pdf.set_fill_color(220, 220, 220)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 8, limpar_texto_pdf(header), border=1, align='C', fill=True)
    pdf.ln()

    # --- FUNÇÃO INTERNA PARA PREVENIR SOBREPOSIÇÃO ---
    def encaixar_texto(texto, largura_maxima):
        """Calcula a largura da string no PDF e trunca com '...' se for maior que a célula."""
        largura_segura = largura_maxima - 2  # 2mm de margem interna
        if pdf.get_string_width(texto) <= largura_segura:
            return texto
        while pdf.get_string_width(texto + "...") > largura_segura and len(texto) > 0:
            texto = texto[:-1]
        return texto + "..."

    # Renderiza as Linhas (Zebrado)
    pdf.set_font("Arial", '', 8)
    fill = False

    for index, row in df.iterrows():
        # Alterna as cores de fundo (Branco e Cinza claro)
        if fill:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)

        # Formatação das datas
        data_v = formatar_data_br(row.get('DATA DA VISTORIA', ''))
        data_r = formatar_data_br(row.get('DATA RETORNO', ''))

        # O pulo do gato: Aplica a função de truncar exatamente na medida da coluna
        empresa = encaixar_texto(limpar_texto_pdf(row.get('EMPRESA', '')), col_widths[1])
        equip = encaixar_texto(limpar_texto_pdf(row.get('EQUIPAMENTO', '')), col_widths[2])
        placa = encaixar_texto(limpar_texto_pdf(row.get('PLACA', '')), col_widths[3])
        situacao = encaixar_texto(limpar_texto_pdf(row.get('SITUAÇÃO', '')), col_widths[5])

        status_raw = limpar_texto_pdf(row.get('STATUS', ''))
        status = encaixar_texto(status_raw, col_widths[6])

        obs = encaixar_texto(limpar_texto_pdf(row.get('OBSERVACOES', '-')), col_widths[7])

        # --- DESENHA AS CÉLULAS COM CORES DINÂMICAS ---
        pdf.set_text_color(0, 0, 0)  # Volta pra preto
        pdf.cell(col_widths[0], 7, data_v, border=1, align='C', fill=fill)
        pdf.cell(col_widths[1], 7, empresa, border=1, align='L', fill=fill)
        pdf.cell(col_widths[2], 7, equip, border=1, align='C', fill=fill)
        pdf.cell(col_widths[3], 7, placa, border=1, align='C', fill=fill)
        pdf.cell(col_widths[4], 7, data_r, border=1, align='C', fill=fill)
        pdf.cell(col_widths[5], 7, situacao, border=1, align='C', fill=fill)

        # Coluna de Status colorida para o relatório físico
        if 'VENCIDO' in status_raw:
            pdf.set_text_color(220, 0, 0)  # Vermelho
            pdf.set_font("Arial", 'B', 8)  # Negrito
        elif 'VENCE HOJE' in status_raw:
            pdf.set_text_color(220, 110, 0)  # Laranja
            pdf.set_font("Arial", 'B', 8)
        elif 'NO PRAZO' in status_raw:
            pdf.set_text_color(0, 130, 0)  # Verde
            pdf.set_font("Arial", 'B', 8)

        pdf.cell(col_widths[6], 7, status, border=1, align='C', fill=fill)

        # Reseta cor para observações
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", '', 8)
        pdf.cell(col_widths[7], 7, obs, border=1, align='L', fill=fill)
        pdf.ln()

        fill = not fill  # Inverte para zebrado

    return pdf.output(dest='S').encode('latin-1')


def style_status(val):
    """Aplica cores na tabela baseadas no status da vistoria."""
    if 'VENCIDO' in str(val):
        return 'background-color: #ffcccc; color: #990000; font-weight: bold;'
    elif 'VENCE HOJE' in str(val):
        return 'background-color: #fff9c4; color: #f57f17; font-weight: bold;'
    elif 'NO PRAZO' in str(val):
        return 'background-color: #c8e6c9; color: #2e7d32;'
    return ''


# --- Inicialização da Interface ---
st.title("📋 Controle de Vistorias de Terceiros")
st.markdown("Gerenciamento, cadastro e emissão de relatórios de frotas e equipamentos terceirizados.")

# Carrega os dados atualizados
df_vistorias = carregar_dados()

# Atualização Inteligente de "STATUS" baseado na Data Atual
hoje = date.today()
if not df_vistorias.empty:
    for idx, row in df_vistorias.iterrows():
        # Se aprovado, verifica se o prazo já venceu e adiciona ícones
        if row['SITUAÇÃO'] == "APROVADO" and pd.notna(row['DATA RETORNO']):
            if row['DATA RETORNO'] < hoje:
                df_vistorias.at[idx, 'STATUS'] = "🚨 VENCIDO"
            elif row['DATA RETORNO'] == hoje:
                df_vistorias.at[idx, 'STATUS'] = "⚠️ VENCE HOJE"
            else:
                df_vistorias.at[idx, 'STATUS'] = "✅ NO PRAZO"
        else:
            df_vistorias.at[idx, 'STATUS'] = "❌ PENDENTE"

# --- Navegação por Abas (Nova Estrutura) ---
aba_Painel, aba_Retornos, aba_Cadastro, aba_Importar, aba_Gerenciar = st.tabs([
    "📊 Painel e Relatórios",
    "📅 Retornos e Atrasos",
    "➕ Nova Vistoria",
    "📥 Importar Dados",
    "✏️ Gerenciar"
])

# ==========================================
# ABA 1: PAINEL E RELATÓRIOS (GERAL)
# ==========================================
with aba_Painel:
    if not df_vistorias.empty:
        # Indicadores Rápidos (KPIs)
        total_vistorias = len(df_vistorias)
        vencidos = len(df_vistorias[df_vistorias['STATUS'] == '🚨 VENCIDO'])
        aprovados = len(df_vistorias[df_vistorias['SITUAÇÃO'] == 'APROVADO'])
        reprovados = len(df_vistorias[df_vistorias['SITUAÇÃO'] == 'REPROVADO'])

        saude_frota = 100 if aprovados == 0 else round(((aprovados - vencidos) / aprovados) * 100, 1)

        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        kpi1.metric("Total Registros", total_vistorias)
        kpi2.metric("Aprovados", f"✅ {aprovados}")
        kpi3.metric("Reprovados", f"❌ {reprovados}")
        kpi4.metric("Vencidas", f"🚨 {vencidos}", delta="- Ação Necessária" if vencidos > 0 else "Tudo OK",
                    delta_color="inverse")
        kpi5.metric("Saúde da Frota", f"🛡️ {saude_frota}%",
                    help="Percentual de equipamentos aprovados e dentro do prazo.")

        st.markdown("---")

        # Secão de Filtros
        st.subheader("🔍 Filtros de Busca Avançados")

        # Filtros Iniciais
        col_b, col_s = st.columns([2, 2])
        with col_b:
            busca_texto = st.text_input("🔍 Busca por Placa, Empresa ou Modelo", "")
        with col_s:
            opcoes_status = ["Todos", "🚨 VENCIDO", "⚠️ VENCE HOJE", "✅ NO PRAZO", "❌ PENDENTE"]
            status_sel = st.multiselect("Filtrar por Status", opcoes_status, default=["Todos"])

        f_col1, f_col2, f_col3, f_col4 = st.columns(4)

        with f_col1:
            empresas_disponiveis = ["Todas"] + sorted(df_vistorias['EMPRESA'].dropna().astype(str).unique().tolist())
            empresa_sel = st.selectbox("Empresa", empresas_disponiveis)

        with f_col2:
            equip_disp = ["Todos"] + sorted(df_vistorias['EQUIPAMENTO'].dropna().astype(str).unique().tolist())
            equip_sel = st.selectbox("Equipamento", equip_disp)

        with f_col3:
            placas_disp = sorted(df_vistorias['PLACA'].dropna().astype(str).unique().tolist())
            placas_sel = st.multiselect("Placa", options=placas_disp, placeholder="Selecione as placas...")

        with f_col4:
            situacao_sel = st.selectbox("Situação", ["Todas", "APROVADO", "REPROVADO"])

        # Aplicando filtros
        df_filtrado = df_vistorias.copy()

        if "Todos" not in status_sel and len(status_sel) > 0:
            df_filtrado = df_filtrado[df_filtrado['STATUS'].isin(status_sel)]

        if empresa_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado['EMPRESA'] == empresa_sel]
        if equip_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado['EQUIPAMENTO'] == equip_sel]
        if situacao_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado['SITUAÇÃO'] == situacao_sel]
        if placas_sel:
            df_filtrado = df_filtrado[df_filtrado['PLACA'].isin(placas_sel)]

        # Filtro de Busca de Texto Inteligente
        if busca_texto:
            busca_lower = busca_texto.lower()
            mascara = (
                    df_filtrado['PLACA'].astype(str).str.lower().str.contains(busca_lower) |
                    df_filtrado['EMPRESA'].astype(str).str.lower().str.contains(busca_lower) |
                    df_filtrado['MODELO'].astype(str).str.lower().str.contains(busca_lower) |
                    df_filtrado['OBSERVACOES'].astype(str).str.lower().str.contains(busca_lower)
            )
            df_filtrado = df_filtrado[mascara]

        # Tabela Visual Formatada (Condicional de Cores + Formatação de Data BR)
        st.write(f"### Registros Encontrados: {len(df_filtrado)}")
        styled_df = df_filtrado.style.map(style_status, subset=['STATUS'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True, column_config=CONFIG_COLUNAS_BR)

        # Gráficos Analíticos
        if not df_filtrado.empty:
            with st.expander("📈 Ver Gráficos de Distribuição"):
                g_col1, g_col2 = st.columns(2)
                with g_col1:
                    st.write("**Vistorias por Empresa**")
                    emp_counts = df_filtrado['EMPRESA'].value_counts()
                    st.bar_chart(emp_counts, color="#2196F3")
                with g_col2:
                    st.write("**Balanço de Prazos (Status)**")
                    status_counts = df_filtrado['STATUS'].value_counts()
                    st.bar_chart(status_counts, color="#FF9800")

        st.markdown("---")
        # Exportações
        st.subheader("📥 Exportar Relatório Filtrado")
        exp_col1, exp_col2, _ = st.columns([1, 1, 4])

        # Exportação Excel limpa
        df_export_excel = df_filtrado.copy()
        df_export_excel['DATA DA VISTORIA'] = pd.to_datetime(df_export_excel['DATA DA VISTORIA']).dt.strftime(
            '%d/%m/%Y')
        df_export_excel['DATA RETORNO'] = pd.to_datetime(df_export_excel['DATA RETORNO']).dt.strftime('%d/%m/%Y')

        with exp_col1:
            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='xlsxwriter') as writer:
                df_export_excel.to_excel(writer, index=False, sheet_name='Vistorias')

            st.download_button(
                label="📊 Exportar Excel",
                data=buffer_excel.getvalue(),
                file_name=f"Vistorias_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )

        with exp_col2:
            if HAS_FPDF:
                if not df_filtrado.empty:
                    titulo_pdf = "Relatório de Vistorias de Terceiros"
                    pdf_bytes = gerar_pdf(df_filtrado, titulo_relatorio=titulo_pdf)
                    st.download_button(
                        label="📄 Exportar PDF Timbrado",
                        data=pdf_bytes,
                        file_name=f"Vistorias_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.button("📄 Exportar PDF", disabled=True, help="A tabela está vazia.")
            else:
                st.error("Biblioteca 'fpdf' ausente. (`pip install fpdf`)")

    else:
        st.info("Nenhum registro encontrado. Vá a Importar ou Nova Vistoria.")

# ==========================================
# ABA 2: RETORNOS E ATRASOS (PROGRAMAÇÃO)
# ==========================================
with aba_Retornos:
    st.subheader("📅 Programação do Dia e Pendências")
    hoje_str = hoje.strftime("%d/%m/%Y")
    st.write(f"**Data base:** {hoje_str}")

    if not df_vistorias.empty:
        df_hoje = df_vistorias[df_vistorias['STATUS'] == '⚠️ VENCE HOJE']
        df_vencidos = df_vistorias[df_vistorias['STATUS'] == '🚨 VENCIDO']

        col_hoje, col_atraso = st.columns(2)

        with col_hoje:
            st.info(f"🔄 **Retornos de Hoje ({len(df_hoje)})**")
            st.dataframe(df_hoje.style.map(style_status, subset=['STATUS']), use_container_width=True, hide_index=True,
                         column_config=CONFIG_COLUNAS_BR)
            if HAS_FPDF and not df_hoje.empty:
                pdf_hoje = gerar_pdf(df_hoje, titulo_relatorio=f"Retornos Programados - {hoje_str}")
                st.download_button("📄 PDF - Retornos Hoje", data=pdf_hoje, file_name=f"Retornos_Hoje.pdf",
                                   mime="application/pdf", use_container_width=True)

        with col_atraso:
            st.error(f"🚨 **Em Atraso ({len(df_vencidos)})**")
            st.dataframe(df_vencidos.style.map(style_status, subset=['STATUS']), use_container_width=True,
                         hide_index=True, column_config=CONFIG_COLUNAS_BR)
            if HAS_FPDF and not df_vencidos.empty:
                pdf_vencidos = gerar_pdf(df_vencidos, titulo_relatorio="Relatório Geral de Atrasos")
                st.download_button("📄 PDF - Atrasos", data=pdf_vencidos, file_name=f"Relatorio_Atrasos.pdf",
                                   mime="application/pdf", use_container_width=True)
    else:
        st.warning("Sem dados para analisar.")

# ==========================================
# ABA 3: CADASTRO RÁPIDO
# ==========================================
with aba_Cadastro:
    st.subheader("Formulário de Entrada de Dados")

    with st.form("nova_vistoria_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 3])

        with c1:
            data_vistoria = st.date_input("Data da Vistoria", hoje, format="DD/MM/YYYY")
            empresa = st.text_input("Empresa Terceirizada").upper().strip()
            equipamento = st.selectbox("Equipamento", ["ONIBUS", "CAMINHÃO", "CARRO", "TRATOR", "ESCAVADEIRA", "PATROL",
                                                       "PÁ CARREGADORA", "OUTROS"])

        with c2:
            placa = st.text_input("Placa / Identificação").upper().strip().replace("-", "").replace(" ", "")
            modelo = st.text_input("Modelo (Opcional)").upper().strip()
            situacao = st.selectbox("Situação Inicial", ["APROVADO", "REPROVADO"])

        with c3:
            obs = st.text_area("Observações (Motivo de reprova, pendências, etc)", height=185)

        botao_salvar = st.form_submit_button("Gravar Vistoria", use_container_width=True)

        if botao_salvar:
            if not empresa or not placa:
                st.error("Campos obrigatórios: Empresa e Placa/Identificação.")
            else:
                dias_prazo = 30 if equipamento == "ONIBUS" else 90
                data_retorno_calculada = data_vistoria + timedelta(days=dias_prazo)
                status_inicial = "❌ PENDENTE" if situacao == "REPROVADO" else "✅ NO PRAZO"

                novo_registro = {
                    'DATA DA VISTORIA': data_vistoria,
                    'EMPRESA': empresa,
                    'EQUIPAMENTO': equipamento,
                    'MODELO': modelo if modelo else "-",
                    'PLACA': placa,
                    'SITUAÇÃO': situacao,
                    'DATA RETORNO': data_retorno_calculada,
                    'STATUS': status_inicial,
                    'OBSERVACOES': obs if obs else "-"
                }

                df_vistorias = pd.concat([df_vistorias, pd.DataFrame([novo_registro])], ignore_index=True)
                salvar_dados(df_vistorias)

                st.success(
                    f"✅ Vistoria da frota {placa} salva! Retorno em: {data_retorno_calculada.strftime('%d/%m/%Y')}")
                st.rerun()

# ==========================================
# ABA 4: IMPORTAÇÃO DE DADOS LEGADOS
# ==========================================
with aba_Importar:
    st.subheader("📥 Importar Banco de Dados do Excel/CSV")

    col_up, col_modelo = st.columns([2, 1])

    with col_up:
        arquivo_upload = st.file_uploader("Selecione o arquivo (Excel ou CSV)", type=['xlsx', 'xls', 'csv'])

    with col_modelo:
        st.write("Precisa do modelo padrão?")
        df_modelo = pd.DataFrame(
            columns=['DATA DA VISTORIA', 'EMPRESA', 'EQUIPAMENTO', 'MODELO', 'PLACA', 'SITUAÇÃO', 'DATA RETORNO',
                     'STATUS', 'OBSERVACOES'])
        buffer_modelo = io.BytesIO()
        with pd.ExcelWriter(buffer_modelo, engine='xlsxwriter') as writer:
            df_modelo.to_excel(writer, index=False, sheet_name='Modelo_Importacao')

        st.download_button(
            label="📄 Baixar Modelo em Branco",
            data=buffer_modelo.getvalue(),
            file_name="Modelo_Vistorias.xlsx",
            mime="application/vnd.ms-excel",
        )

    if arquivo_upload is not None:
        if st.button("Processar e Integrar Dados", type="primary"):
            try:
                if arquivo_upload.name.endswith('.csv'):
                    df_importado = pd.read_csv(arquivo_upload)
                else:
                    df_importado = pd.read_excel(arquivo_upload)

                df_importado.columns = df_importado.columns.str.strip().str.upper()

                if 'PLACA' in df_importado.columns and 'EMPRESA' in df_importado.columns:
                    df_importado = df_importado.dropna(subset=['PLACA', 'EMPRESA'], how='all')
                    df_importado['PLACA'] = df_importado['PLACA'].astype(str).str.strip().str.replace('-',
                                                                                                      '').str.replace(
                        ' ', '').str.upper()

                colunas_padrao = ['DATA DA VISTORIA', 'EMPRESA', 'EQUIPAMENTO', 'MODELO', 'PLACA', 'SITUAÇÃO',
                                  'DATA RETORNO', 'STATUS', 'OBSERVACOES']
                df_limpo = pd.DataFrame()

                for col in colunas_padrao:
                    if col in df_importado.columns:
                        df_limpo[col] = df_importado[col]
                    else:
                        df_limpo[col] = "-"

                df_limpo['DATA DA VISTORIA'] = pd.to_datetime(df_limpo['DATA DA VISTORIA'], errors='coerce').dt.date
                df_limpo['DATA RETORNO'] = pd.to_datetime(df_limpo['DATA RETORNO'], errors='coerce').dt.date

                df_limpo = df_limpo[df_limpo['PLACA'].notna() & (df_limpo['PLACA'] != 'NAN')]

                df_final = pd.concat([df_vistorias, df_limpo], ignore_index=True)
                df_final = df_final.drop_duplicates(subset=['PLACA', 'DATA DA VISTORIA'], keep='last')

                salvar_dados(df_final)
                st.success("🎉 Importação concluída!")
                st.rerun()

            except Exception as e:
                st.error(f"Erro ao processar. Verifique se o formato e as bibliotecas estão corretos. Erro: {e}")

# ==========================================
# ABA 5: GERENCIAR (EDIÇÃO E EXCLUSÃO)
# ==========================================
with aba_Gerenciar:
    st.subheader("Edição Rápida e Exclusão")
    st.markdown(
        "Dê um **duplo clique** para editar uma célula. Para apagar, marque a caixa na esquerda e use a lixeira 🗑️.")

    if not df_vistorias.empty:
        df_editado = st.data_editor(
            df_vistorias,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "DATA DA VISTORIA": st.column_config.DateColumn("Data Vistoria", format="DD/MM/YYYY"),
                "DATA RETORNO": st.column_config.DateColumn("Data Retorno", format="DD/MM/YYYY"),
                "SITUAÇÃO": st.column_config.SelectboxColumn("Situação", options=["APROVADO", "REPROVADO"]),
                "STATUS": st.column_config.Column("Status", disabled=True),  # Bloqueia status (é automático)
            }
        )

        if st.button("💾 Salvar Alterações na Base", type="primary"):
            salvar_dados(df_editado)
            st.success("Alterações consolidadas!")
            st.rerun()
    else:
        st.warning("Base de dados vazia.")