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
from utils_ui import load_custom_css, card_kpi  # Importa o motor de estilo centralizado

# --- 1. CONFIGURAÇÃO VISUAL ---
# Carrega o CSS global (Sidebar, Fontes, Cards)
load_custom_css()

# --- HEADER COM AÇÕES RÁPIDAS (NOVO) ---
col_titulo, col_btn_novo = st.columns([3, 1])
with col_titulo:
    st.title("🖥️ Painel de Controle")
    st.caption("Visão geral estratégica e operacional das ordens de serviço.")

with col_btn_novo:
    # Espaçamento para alinhar verticalmente com o título
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    if st.button("➕ Nova Ordem de Serviço", type="primary", use_container_width=True):
        st.switch_page("pages/5_Nova_Ordem_Servico.py")

st.markdown("---")

# Definição do Fuso Horário Local
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
        # Por padrão, não mostra os concluídos para focar no backlog
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
# Ajuste para pegar o dia inteiro da data final
params.extend([
    datetime.combine(data_inicio, datetime.min.time()),
    datetime.combine(data_fim, datetime.max.time())
])

# Ordenação Inteligente: Prioridade Alta primeiro, depois data mais recente
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
    # Conversão de datas
    df_painel['Data_DT'] = pd.to_datetime(df_painel['Data'], format='mixed', dayfirst=True, errors='coerce')
    fim_dt = pd.to_datetime(df_painel['Fim'], format='mixed', dayfirst=True, errors='coerce')

    # Cálculo de Tempo em Aberto (SLA)
    agora = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
    # Se não tem data fim, usa 'agora' para calcular tempo decorrido
    df_painel['delta'] = fim_dt.fillna(agora) - df_painel['Data_DT']


    def formatar_tempo(td):
        if pd.isnull(td): return "-"
        ts = int(td.total_seconds())
        d = ts // 86400
        h = (ts % 86400) // 3600
        m = ((ts % 86400) % 3600) // 60
        if d > 0: return f"{d}d {h}h"
        if h > 0: return f"{h}h {m}m"
        return f"{m}m"


    df_painel['Tempo_Aberto'] = df_painel['delta'].apply(formatar_tempo)
    df_painel['Data_Formatada'] = df_painel['Data_DT'].dt.strftime('%d/%m %H:%M')

    # Normalização de strings para maiúsculo (exceto status e prioridade para manter compatibilidade com selectbox)
    cols_upper = ['frota', 'modelo', 'Gestao', 'Executante', 'OS_Oficial', 'Operacao', 'Local', 'descricao']
    for col in cols_upper:
        if col in df_painel.columns:
            df_painel[col] = df_painel[col].astype(str).str.upper().replace(['NONE', 'NAN'], '-')

# ==============================================================================
# 7. LAYOUT DO PAINEL (UI/UX)
# ==============================================================================

if df_painel.empty:
    st.info("🔎 Nenhum dado encontrado com os filtros atuais.")
else:
    # --- BLOCO A: KPIs (CARDS) ---
    total = len(df_painel)
    # Conta prioridade ALTA ou Alta (independente do case)
    urgentes = len(df_painel[df_painel['prioridade'].str.upper() == 'ALTA'])
    # Conta tudo que não está concluído
    abertos = len(df_painel[~df_painel['status'].str.upper().isin(['CONCLUÍDO', 'CONCLUIDO'])])
    frotas_unicas = df_painel['frota'].nunique()

    c1, c2, c3, c4 = st.columns(4)
    card_kpi(c1, "Total Tickets", total, "📋", "#2196F3")  # Azul
    card_kpi(c2, "Alta Prioridade", urgentes, "🔥", "#FF5252" if urgentes > 0 else "#E0E0E0")  # Vermelho
    card_kpi(c3, "Em Aberto", abertos, "⏳", "#FFC107")  # Amarelo
    card_kpi(c4, "Frotas na Oficina", frotas_unicas, "🚜", "#4CAF50")  # Verde

    st.markdown("<br>", unsafe_allow_html=True)

    # --- BLOCO B: ALERTA DE CRÍTICOS ---
    if urgentes > 0:
        st.markdown(f"""
        <div style='background-color: #FEF2F2; padding: 15px; border-radius: 8px; 
                    border-left: 5px solid #FF5252; color: #991B1B; margin-bottom: 20px; 
                    display: flex; align-items: center; gap: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>
            <span style='font-size: 24px;'>🚨</span>
            <div>
                <strong style='font-size: 16px;'>Atenção Necessária</strong><br>
                Existem <b>{urgentes}</b> ordens de serviço de ALTA prioridade pendentes de resolução.
            </div>
        </div>
        """, unsafe_allow_html=True)

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

    # --- BLOCO C: TABELA PRINCIPAL (EDITÁVEL) ---
    st.subheader("📋 Listagem Geral de Manutenção")

    cols_view = ['Ticket', 'OS_Oficial', 'frota', 'modelo', 'Gestao', 'prioridade', 'status', 'Local', 'Data_Formatada',
                 'Tempo_Aberto', 'descricao', 'Operacao']
    # Garante que só selecionamos colunas que existem
    cols_existentes = [c for c in cols_view if c in df_painel.columns]
    df_show = df_painel[cols_existentes].copy()

    # [MELHORIA] Inserir coluna de seleção no início
    df_show.insert(0, "Selecionar", False)

    # Normaliza prioridade para edição correta
    if 'prioridade' in df_show.columns:
        df_show['prioridade'] = df_show['prioridade'].str.title()
        df_show['prioridade'] = df_show['prioridade'].apply(lambda x: x if x in ["Alta", "Média", "Baixa"] else "Média")

    # Editor de Dados
    edited_df = st.data_editor(
        df_show,
        use_container_width=True,
        hide_index=True,
        key="editor_painel_principal",
        column_config={
            # Coluna de Seleção para Ação
            "Selecionar": st.column_config.CheckboxColumn(
                "Editar?",
                width="small",
                help="Selecione para editar detalhes completos"
            ),
            "Ticket": st.column_config.NumberColumn("# Ticket", format="%d", width="small", disabled=True),
            "OS_Oficial": st.column_config.TextColumn("OS Oficial", width="small", disabled=False, help="Editável"),
            "frota": st.column_config.TextColumn("Frota", width="small", disabled=True),
            "modelo": st.column_config.TextColumn("Modelo", width="medium", disabled=True),
            "Gestao": st.column_config.TextColumn("Gestão", width="medium", disabled=True),

            "prioridade": st.column_config.SelectboxColumn(
                "Prioridade",
                width="small",
                options=["Alta", "Média", "Baixa"],
                required=True,
                help="Mude a urgência do ticket"
            ),

            "status": st.column_config.SelectboxColumn(
                "Status (Clique para Mudar)",
                width="medium",
                options=["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças", "Concluído"],
                required=True,
            ),

            "Data_Formatada": st.column_config.TextColumn("Abertura", width="medium", disabled=True),
            "Tempo_Aberto": st.column_config.TextColumn("Tempo", width="small", disabled=True),
            "descricao": st.column_config.TextColumn("Descrição", width="large", disabled=True),
            "Operacao": st.column_config.TextColumn("Tipo", width="medium", disabled=True),
        },
        # Trava colunas que não devem ser editadas aqui
        disabled=[c for c in cols_existentes if c not in ['status', 'prioridade', 'OS_Oficial', 'Selecionar']]
    )

    # --- [MELHORIA] LÓGICA DE AÇÃO PÓS-SELEÇÃO ---
    # Verifica se alguma linha foi selecionada
    rows_selected = edited_df[edited_df["Selecionar"]]

    if not rows_selected.empty:
        # Pega o primeiro item selecionado (caso usuário marque vários)
        selected_ticket = rows_selected.iloc[0]["Ticket"]
        selected_frota = rows_selected.iloc[0]["frota"]

        # Mostra container de ação em destaque
        with st.container(border=True):
            col_msg, col_action = st.columns([3, 1])
            with col_msg:
                st.info(f"🖊️ **Ticket #{selected_ticket} ({selected_frota})** selecionado para edição detalhada.")
            with col_action:
                if st.button("Ir para Gerenciamento 🚀", type="primary", use_container_width=True):
                    # Salva o ID na sessão para a página de gerenciamento ler
                    st.session_state['ticket_para_editar'] = int(selected_ticket)
                    st.switch_page("pages/6_Gerenciar_Atendimento.py")

    # --- LÓGICA DE SALVAMENTO AUTOMÁTICO (MULTICOLUNA) ---
    # Compara ignorando a coluna 'Selecionar'
    df_data_orig = df_show.drop(columns=["Selecionar"])
    df_data_edit = edited_df.drop(columns=["Selecionar"])

    if not df_data_orig.equals(df_data_edit):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            dict_orig = df_data_orig.set_index('Ticket').to_dict('index')
            dict_edit = df_data_edit.set_index('Ticket').to_dict('index')

            alteracoes_count = 0

            for ticket_id, row_edit in dict_edit.items():
                row_orig = dict_orig.get(ticket_id)

                # Verifica mudanças
                novo_status = row_edit.get('status')
                nova_prio = row_edit.get('prioridade')
                nova_os = row_edit.get('OS_Oficial')

                status_mudou = novo_status != row_orig.get('status')
                prio_mudou = nova_prio != row_orig.get('prioridade')
                os_mudou = nova_os != row_orig.get('OS_Oficial')

                if status_mudou or prio_mudou or os_mudou:
                    updates = []
                    params_update = []

                    if status_mudou:
                        updates.append("status = ?")
                        params_update.append(novo_status)
                        if novo_status == "Concluído":
                            updates.append("data_encerramento = ?")
                            params_update.append(datetime.now(FUSO_HORARIO).replace(tzinfo=None))
                        elif row_orig.get('status') == "Concluído" and novo_status != "Concluído":
                            updates.append("data_encerramento = NULL")

                    if prio_mudou:
                        updates.append("prioridade = ?")
                        params_update.append(nova_prio)

                    if os_mudou:
                        updates.append("numero_os_oficial = ?")
                        params_update.append(nova_os)

                    if updates:
                        sql = f"UPDATE ordens_servico SET {', '.join(updates)} WHERE id = ?"
                        params_update.append(ticket_id)
                        cursor.execute(sql, tuple(params_update))
                        alteracoes_count += 1

            if alteracoes_count > 0:
                conn.commit()
                st.toast(f"✅ {alteracoes_count} registro(s) atualizado(s)!", icon="💾")
                import time;

                time.sleep(1);
                st.rerun()

        except Exception as e:
            st.error(f"Erro ao salvar alterações: {e}")
        finally:
            conn.close()

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. ÁREA DE DOWNLOAD
    c_csv, c_pdf = st.columns(2)
    with c_csv:
        csv = df_show.drop(columns=["Selecionar"]).to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Planilha (CSV)",
            data=csv,
            file_name="relatorio_manutencao.csv",
            mime="text/csv",
            use_container_width=True
        )

    with c_pdf:
        try:
            pdf_bytes = gerar_relatorio_geral(df_show.drop(columns=["Selecionar"]))
            st.download_button(
                label="🖨️ Imprimir Relatório (PDF)",
                data=pdf_bytes,
                file_name="relatorio_geral.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")