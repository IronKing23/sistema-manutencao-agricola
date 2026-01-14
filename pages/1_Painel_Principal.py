import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
import pytz
from datetime import datetime, timedelta

# --- BLINDAGEM DE IMPORTAÇÃO ---
# Garante que o Python encontre os módulos na pasta raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from utils_pdf import gerar_relatorio_geral
from utils_ui import load_custom_css, card_kpi
from utils_icons import get_icon

# --- 1. CONFIGURAÇÃO VISUAL ---
load_custom_css()

# --- HEADER COM AÇÕES RÁPIDAS ---
col_titulo, col_btn_novo = st.columns([3, 1])
with col_titulo:
    st.title("🖥️ Painel de Controle")
    st.caption("Visão geral estratégica e operacional das ordens de serviço.")

with col_btn_novo:
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    if st.button("➕ Nova Ordem de Serviço", type="primary", use_container_width=True):
        st.switch_page("pages/5_Nova_Ordem_Servico.py")

st.markdown("---")

FUSO_HORARIO = pytz.timezone('America/Campo_Grande')


# --- 2. CARREGAMENTO DE DADOS (COM CACHE) ---
@st.cache_data(ttl=60)
def carregar_filtros():
    conn = get_db_connection()
    try:
        frotas = pd.read_sql("SELECT DISTINCT frota FROM equipamentos ORDER BY frota", conn)
        operacoes = pd.read_sql("SELECT DISTINCT nome FROM tipos_operacao ORDER BY nome", conn)
        gestao = pd.read_sql(
            "SELECT DISTINCT gestao_responsavel FROM equipamentos WHERE gestao_responsavel IS NOT NULL AND gestao_responsavel != '' ORDER BY gestao_responsavel",
            conn)
        return frotas, operacoes, gestao
    finally:
        conn.close()


frotas_df, operacoes_df, gestao_df = carregar_filtros()

# --- 3. BARRA LATERAL (FILTROS) ---
with st.sidebar:
    st.header("🔍 Filtros Avançados")

    with st.expander("🛠️ Status e Prioridade", expanded=False):
        status_options = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças", "Concluído"]
        default_status = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças"]
        filtro_status = st.multiselect("Status", options=status_options, default=default_status)
        filtro_prioridade = st.multiselect("Prioridade", ["Alta", "Média", "Baixa"])

    with st.expander("🚜 Equipamento e Gestão", expanded=False):
        filtro_frota = st.multiselect("Frota", options=frotas_df['frota'].tolist())
        filtro_gestao = st.multiselect("Gestor Responsável", options=gestao_df['gestao_responsavel'].tolist())
        filtro_operacao = st.multiselect("Tipo de Serviço", options=operacoes_df['nome'].tolist())

    st.markdown("### 📅 Período")
    c1, c2 = st.columns(2)
    data_inicio = c1.date_input("Início", datetime.now() - timedelta(days=30))
    data_fim = c2.date_input("Fim", datetime.now())

# --- 4. CONSTRUÇÃO DA QUERY ---
query_base = """
SELECT 
    os.id as Ticket,
    os.data_hora as Data,
    os.data_encerramento as Fim,
    os.horimetro,
    os.prioridade,
    e.frota,
    e.modelo,
    e.gestao_responsavel as Gestao, 
    f.nome as Executante,
    os.status,
    os.numero_os_oficial as OS_Oficial,
    op.nome as Operacao,
    op.cor as Cor_Hex,
    os.local_atendimento as Local,
    os.descricao
FROM ordens_servico os
JOIN equipamentos e ON os.equipamento_id = e.id
JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
LEFT JOIN funcionarios f ON os.funcionario_id = f.id
WHERE 1=1 
"""

params = []
filtros_sql = ""

if filtro_status:
    filtros_sql += f" AND os.status IN ({','.join(['?'] * len(filtro_status))})"
    params.extend(filtro_status)
if filtro_prioridade:
    filtros_sql += f" AND os.prioridade IN ({','.join(['?'] * len(filtro_prioridade))})"
    params.extend(filtro_prioridade)
if filtro_frota:
    filtros_sql += f" AND e.frota IN ({','.join(['?'] * len(filtro_frota))})"
    params.extend(filtro_frota)
if filtro_operacao:
    filtros_sql += f" AND op.nome IN ({','.join(['?'] * len(filtro_operacao))})"
    params.extend(filtro_operacao)
if filtro_gestao:
    filtros_sql += f" AND e.gestao_responsavel IN ({','.join(['?'] * len(filtro_gestao))})"
    params.extend(filtro_gestao)

filtros_sql += " AND os.data_hora BETWEEN ? AND ?"
params.extend([
    datetime.combine(data_inicio, datetime.min.time()),
    datetime.combine(data_fim, datetime.max.time())
])

query_final = query_base + filtros_sql + """ 
ORDER BY 
    CASE os.prioridade
        WHEN 'Alta' THEN 1
        WHEN 'Média' THEN 2
        WHEN 'Baixa' THEN 3
        ELSE 4
    END ASC,
    os.data_hora DESC
"""

# --- 5. EXECUÇÃO E DATAFRAME ---
conn = get_db_connection()
try:
    df_painel = pd.read_sql_query(query_final, conn, params=params)
finally:
    conn.close()

# --- 6. PROCESSAMENTO DE DADOS ---
if not df_painel.empty:
    df_painel['Data_DT'] = pd.to_datetime(df_painel['Data'], format='mixed', dayfirst=True, errors='coerce')
    fim_dt = pd.to_datetime(df_painel['Fim'], format='mixed', dayfirst=True, errors='coerce')

    agora = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
    df_painel['delta'] = fim_dt.fillna(agora) - df_painel['Data_DT']


    def formatar_tempo(td):
        if pd.isnull(td): return "-"
        ts = int(td.total_seconds())
        d = ts // 86400;
        h = (ts % 86400) // 3600;
        m = ((ts % 86400) % 3600) // 60
        if d > 0: return f"{d}d {h}h"
        if h > 0: return f"{h}h {m}m"
        return f"{m}m"


    df_painel['Tempo_Aberto'] = df_painel['delta'].apply(formatar_tempo)
    df_painel['Data_Formatada'] = df_painel['Data_DT'].dt.strftime('%d/%m %H:%M')

    cols_upper = ['frota', 'modelo', 'Gestao', 'Executante', 'OS_Oficial', 'Operacao', 'Local', 'descricao']
    for col in cols_upper:
        if col in df_painel.columns:
            df_painel[col] = df_painel[col].astype(str).str.upper().replace(['NONE', 'NAN'], '-')


# --- FUNÇÃO AUXILIAR DE COR (Para Visualização) ---
def highlight_type(row):
    color = row.get('Cor_Hex')
    if pd.isna(color) or not str(color).startswith('#'):
        return [''] * len(row)
    # Aplica cor de fundo na célula 'Operacao' com transparência e borda
    return [f'background-color: {color}40; border-left: 5px solid {color}' if col == 'Operacao' else '' for col in
            row.index]


# ==============================================================================
# 7. LAYOUT DO PAINEL (UI/UX)
# ==============================================================================

if df_painel.empty:
    st.info("🔎 Nenhum dado encontrado com os filtros atuais.")
else:
    # --- BLOCO A: KPIs (CARDS COM SVG) ---
    total = len(df_painel)
    urgentes = len(df_painel[df_painel['prioridade'].str.upper() == 'ALTA'])
    abertos = len(df_painel[~df_painel['status'].str.upper().isin(['CONCLUÍDO', 'CONCLUIDO'])])
    frotas_unicas = df_painel['frota'].nunique()

    c1, c2, c3, c4 = st.columns(4)

    icon_list = get_icon("dashboard", color="#2196F3", size="32")
    icon_fire = get_icon("fire", color="#FF5252" if urgentes > 0 else "#E0E0E0", size="32")
    icon_clock = get_icon("clock", color="#FFC107", size="32")
    icon_trac = get_icon("tractor", color="#4CAF50", size="32")

    card_kpi(c1, "Total Tickets", total, icon_list, "#2196F3")
    card_kpi(c2, "Alta Prioridade", urgentes, icon_fire, "#FF5252" if urgentes > 0 else "#E0E0E0")
    card_kpi(c3, "Em Aberto", abertos, icon_clock, "#FFC107")
    card_kpi(c4, "Frotas na Oficina", frotas_unicas, icon_trac, "#4CAF50")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- BLOCO B: ALERTA DE CRÍTICOS ---
    if urgentes > 0:
        st.markdown(
            f"""<div style='background-color: #FEF2F2; padding: 15px; border-radius: 8px; border-left: 5px solid #FF5252; color: #991B1B; margin-bottom: 20px; display: flex; align-items: center; gap: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'><span style='font-size: 24px;'>🚨</span><div><strong style='font-size: 16px;'>Atenção Necessária</strong><br>Existem <b>{urgentes}</b> ordens de serviço de ALTA prioridade pendentes de resolução.</div></div>""",
            unsafe_allow_html=True)

        with st.expander("Visualizar Frotas Críticas", expanded=False):
            df_critico = df_painel[df_painel['prioridade'].str.upper() == 'ALTA'].copy()
            st.dataframe(
                df_critico[['Ticket', 'frota', 'Operacao', 'descricao', 'Tempo_Aberto']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Ticket": st.column_config.NumberColumn("#", format="%d", width="small"),
                    "descricao": "Descrição do Problema"
                }
            )

    # --- BLOCO C: TABELA PRINCIPAL ---
    c_head, c_toggle = st.columns([4, 1])
    c_head.subheader("📋 Listagem Geral de Manutenção")
    # Toggle para Alternar Modos
    modo_visual = c_toggle.toggle("🎨 Modo Visual", help="Ativa cores nos tipos de serviço (Modo Leitura)")

    # Incluímos 'Cor_Hex' na lista para uso no style, mas ocultamos depois
    cols_view = ['Ticket', 'OS_Oficial', 'frota', 'modelo', 'Gestao', 'prioridade', 'status', 'Local', 'Data_Formatada',
                 'Tempo_Aberto', 'descricao', 'Operacao', 'Cor_Hex']
    cols_existentes = [c for c in cols_view if c in df_painel.columns]
    df_show = df_painel[cols_existentes].copy()

    df_show.insert(0, "Selecionar", False)

    if 'prioridade' in df_show.columns:
        df_show['prioridade'] = df_show['prioridade'].str.title().apply(
            lambda x: x if x in ["Alta", "Média", "Baixa"] else "Média")

    # --- MODO DE VISUALIZAÇÃO ---
    if modo_visual:
        # Usa st.dataframe para permitir estilização (cores dinâmicas)
        st.dataframe(
            df_show.drop(columns=["Selecionar"]).style.apply(highlight_type, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Cor_Hex": None,  # Oculta a coluna de código de cor
                "Ticket": st.column_config.NumberColumn("# Ticket", format="%d", width="small"),
                "status": st.column_config.Column("Status", width="medium"),
                "prioridade": st.column_config.Column("Prioridade", width="small"),
                # ... outras configurações visuais
            }
        )

    # --- MODO DE EDIÇÃO (PADRÃO) ---
    else:
        edited_df = st.data_editor(
            df_show,
            use_container_width=True,
            hide_index=True,
            key="editor_painel_principal",
            column_config={
                "Cor_Hex": None,
                "Selecionar": st.column_config.CheckboxColumn("Editar?", width="small", help="Marque para editar"),
                "Ticket": st.column_config.NumberColumn("# Ticket", format="%d", width="small", disabled=True),
                "OS_Oficial": st.column_config.TextColumn("OS Oficial", width="small", disabled=False),
                "frota": st.column_config.TextColumn("Frota", width="small", disabled=True),
                "modelo": st.column_config.TextColumn("Modelo", width="medium", disabled=True),
                "Gestao": st.column_config.TextColumn("Gestão", width="medium", disabled=True),

                "prioridade": st.column_config.SelectboxColumn("Prioridade", width="small",
                                                               options=["Alta", "Média", "Baixa"], required=True),
                "status": st.column_config.SelectboxColumn("Status", width="medium",
                                                           options=["Pendente", "Aberto (Parada)", "Em Andamento",
                                                                    "Aguardando Peças", "Concluído"], required=True),

                "Data_Formatada": st.column_config.TextColumn("Abertura", width="medium", disabled=True),
                "Tempo_Aberto": st.column_config.TextColumn("Tempo", width="small", disabled=True),
                "descricao": st.column_config.TextColumn("Descrição", width="large", disabled=True),
                "Operacao": st.column_config.TextColumn("Tipo", width="medium", disabled=True),
            },
            disabled=[c for c in cols_existentes if c not in ['status', 'prioridade', 'OS_Oficial', 'Selecionar']]
        )

        # AÇÃO PÓS-SELEÇÃO
        rows_selected = edited_df[edited_df["Selecionar"]]
        if not rows_selected.empty:
            sel_tk = int(rows_selected.iloc[0]["Ticket"])
            sel_fr = rows_selected.iloc[0]["frota"]
            with st.container(border=True):
                cm, cb = st.columns([3, 1])
                cm.info(f"🖊️ **Ticket #{sel_tk} ({sel_fr})** selecionado.")
                if cb.button("🚀 Ir para Gerenciamento", type="primary", use_container_width=True):
                    st.session_state['ticket_para_editar'] = int(sel_tk)
                    st.switch_page("pages/6_Gerenciar_Atendimento.py")

        # SALVAMENTO AUTOMÁTICO
        df_orig = df_show.drop(columns=["Selecionar"])
        df_new = edited_df.drop(columns=["Selecionar"])

        if not df_orig.equals(df_new):
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                dict_orig = df_orig.set_index('Ticket').to_dict('index')
                dict_edit = df_new.set_index('Ticket').to_dict('index')

                alt = 0
                for ticket_id, row_edit in dict_edit.items():
                    row_orig = dict_orig.get(ticket_id)
                    if (row_edit['status'] != row_orig['status']) or \
                            (row_edit['prioridade'] != row_orig['prioridade']) or \
                            (row_edit['OS_Oficial'] != row_orig['OS_Oficial']):

                        ups = ["status=?", "prioridade=?", "numero_os_oficial=?"]
                        vals = [row_edit['status'], row_edit['prioridade'], row_edit['OS_Oficial']]

                        if row_edit['status'] == "Concluído" and row_orig['status'] != "Concluído":
                            ups.append("data_encerramento=?")
                            vals.append(datetime.now(FUSO_HORARIO).replace(tzinfo=None))
                        elif row_edit['status'] != "Concluído" and row_orig['status'] == "Concluído":
                            ups.append("data_encerramento=NULL")

                        vals.append(ticket_id)
                        cursor.execute(f"UPDATE ordens_servico SET {', '.join(ups)} WHERE id=?", tuple(vals))
                        alt += 1

                if alt > 0:
                    conn.commit()
                    st.toast(f"✅ {alt} registro(s) salvo(s)!", icon="💾")
                    import time;

                    time.sleep(1);
                    st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
            finally:
                conn.close()

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. ÁREA DE DOWNLOAD
    c_csv, c_pdf = st.columns(2)
    with c_csv:
        csv = df_show.drop(columns=["Selecionar"], errors='ignore').to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha (CSV)", csv, "relatorio.csv", "text/csv", use_container_width=True)
    with c_pdf:
        try:
            pdf_bytes = gerar_relatorio_geral(df_show.drop(columns=["Selecionar"], errors='ignore'))
            st.download_button("🖨️ Imprimir Relatório (PDF)", pdf_bytes, "relatorio.pdf", "application/pdf",
                               type="primary", use_container_width=True)
        except:
            pass
