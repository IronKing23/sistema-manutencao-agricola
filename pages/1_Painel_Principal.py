import streamlit as st
import pandas as pd
import plotly.express as px 
import sys
import os
import pytz
from datetime import datetime, timedelta

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from utils_pdf import gerar_relatorio_geral

# --- CONFIGURAÇÃO DA PÁGINA ---
# st.set_page_config(layout="wide", page_title="Painel de Controle")

st.title("🖥️ Painel de Controle de Manutenção")
st.markdown("---")

# Definição do Fuso Horário Local
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

# --- CSS PERSONALIZADO (VISUAL MODERNO) ---
st.markdown("""
<style>
    /* Estilo dos Cards KPI */
    .kpi-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }
    .kpi-title {
        color: #6c757d;
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    .kpi-value {
        color: #212529;
        font-size: 2.2rem;
        font-weight: 800;
    }
    .kpi-icon {
        float: right;
        font-size: 2rem;
        opacity: 0.8;
    }
    
    /* Modo Escuro */
    @media (prefers-color-scheme: dark) {
        .kpi-card {
            background-color: #262730;
            border-color: #3f3f46;
        }
        .kpi-title { color: #a1a1aa; }
        .kpi-value { color: #ffffff; }
    }
    
    /* Badge de Alerta */
    .pulse-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.7em;
        font-weight: bold;
        animation: pulse 2s infinite;
        vertical-align: middle;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÃO DE CARD VISUAL ---
def exibir_kpi(coluna, titulo, valor, icone, cor_borda="#ccc", alerta=False):
    html_alerta = '<span class="pulse-badge">AÇÃO</span>' if alerta and valor > 0 else ''
    coluna.markdown(f"""
    <div class="kpi-card" style="border-left: 5px solid {cor_borda};">
        <div class="kpi-icon">{icone}</div>
        <div class="kpi-title">{titulo} {html_alerta}</div>
        <div class="kpi-value">{valor}</div>
    </div>
    """, unsafe_allow_html=True)

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=60) 
def carregar_filtros():
    conn = get_db_connection()
    try:
        frotas = pd.read_sql("SELECT DISTINCT frota FROM equipamentos ORDER BY frota", conn)
        operacoes = pd.read_sql("SELECT DISTINCT nome FROM tipos_operacao ORDER BY nome", conn)
        gestao = pd.read_sql("SELECT DISTINCT gestao_responsavel FROM equipamentos WHERE gestao_responsavel IS NOT NULL AND gestao_responsavel != '' ORDER BY gestao_responsavel", conn)
        return frotas, operacoes, gestao
    finally:
        conn.close()

frotas_df, operacoes_df, gestao_df = carregar_filtros()

# --- BARRA LATERAL (FILTROS) ---
with st.sidebar:
    st.header("🔍 Filtros Avançados")
    
    with st.expander("🛠️ Status e Prioridade", expanded=True):
        status_options = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças", "Concluído"]
        default_status = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças"]
        filtro_status = st.multiselect("Status", options=status_options, default=default_status)
        filtro_prioridade = st.multiselect("Prioridade", ["Alta", "Média", "Baixa"])

    with st.expander("🚜 Equipamento e Gestão"):
        filtro_frota = st.multiselect("Frota", options=frotas_df['frota'].tolist())
        filtro_gestao = st.multiselect("Gestor Responsável", options=gestao_df['gestao_responsavel'].tolist())
        filtro_operacao = st.multiselect("Tipo de Serviço", options=operacoes_df['nome'].tolist())

    st.markdown("### 📅 Período")
    c1, c2 = st.columns(2)
    data_inicio = c1.date_input("Início", datetime.now() - timedelta(days=30))
    data_fim = c2.date_input("Fim", datetime.now())

# --- CONSTRUÇÃO DA QUERY ---
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
params.extend([datetime.combine(data_inicio, datetime.min.time()), datetime.combine(data_fim, datetime.max.time())])

# Query Final com Ordenação Inteligente
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

# --- EXECUÇÃO DA QUERY ---
conn = get_db_connection()
try:
    df_painel = pd.read_sql_query(query_final, conn, params=params)
finally:
    conn.close()

# --- PROCESSAMENTO DOS DADOS ---
if not df_painel.empty:
    df_painel['Data_DT'] = pd.to_datetime(df_painel['Data'], format='mixed', dayfirst=True, errors='coerce')
    fim_dt = pd.to_datetime(df_painel['Fim'], format='mixed', dayfirst=True, errors='coerce')
    
    agora = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
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
    
    cols_upper = ['frota', 'modelo', 'Gestao', 'Executante', 'status', 'OS_Oficial', 'Operacao', 'Local', 'descricao', 'prioridade']
    for col in cols_upper:
        if col in df_painel.columns:
            # Não converter 'status' para maiúsculo aqui para bater com as opções do selectbox
            if col != 'status':
                df_painel[col] = df_painel[col].astype(str).str.upper().replace(['NONE', 'NAN'], '-')

# ==============================================================================
# PAINEL ÚNICO DINÂMICO
# ==============================================================================

if df_painel.empty:
    st.info("🔎 Nenhum dado encontrado com os filtros atuais.")
else:
    # 1. RESUMO DE TOPO (KPIs)
    st.markdown("### 📊 Resumo Operacional")
    
    total = len(df_painel)
    # Ajuste: busca 'ALTA' (se veio do banco em maiúsculo) ou 'Alta'
    urgentes = len(df_painel[df_painel['prioridade'].str.upper() == 'ALTA'])
    
    # Status pode vir misto, normaliza para contagem
    abertos = len(df_painel[~df_painel['status'].str.upper().isin(['CONCLUÍDO', 'CONCLUIDO'])])
    frotas_unicas = df_painel['frota'].nunique()

    c1, c2, c3, c4 = st.columns(4)
    exibir_kpi(c1, "Total Tickets", total, "📋", "#3498db")
    exibir_kpi(c2, "Alta Prioridade", urgentes, "🔥", "#e74c3c", alerta=True)
    exibir_kpi(c3, "Em Aberto", abertos, "⏳", "#f1c40f")
    exibir_kpi(c4, "Frotas Ativas", frotas_unicas, "🚜", "#2ecc71")

    st.markdown("---")

    # 2. ALERTA DE CRÍTICOS (SE EXISTIR)
    if urgentes > 0:
        st.markdown(f"#### 🚨 Atenção: {urgentes} Tickets de Alta Prioridade")
        df_critico = df_painel[df_painel['prioridade'].str.upper() == 'ALTA'].copy()
        
        st.dataframe(
            df_critico[['Ticket', 'frota', 'Operacao', 'descricao', 'Tempo_Aberto']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ticket": st.column_config.NumberColumn("#", format="%d", width="small"),
                "Tempo_Aberto": "Tempo",
                "descricao": "Problema Detalhado"
            }
        )
        st.markdown("---")

    # 3. TABELA PRINCIPAL DO PAINEL (EDITÁVEL)
    st.markdown("### 📋 Listagem Geral de Manutenção")
    
    cols = ['Ticket', 'OS_Oficial', 'frota', 'modelo', 'Gestao', 'prioridade', 'status', 'Local', 'Data_Formatada', 'Tempo_Aberto', 'descricao', 'Operacao']
    df_show = df_painel[ [c for c in cols if c in df_painel.columns] ].copy()

    # --- EDIÇÃO DE STATUS NA TABELA ---
    # Usamos st.data_editor no lugar de st.dataframe
    edited_df = st.data_editor(
        df_show,
        use_container_width=True,
        hide_index=True,
        key="editor_painel_principal",
        column_config={
            "Ticket": st.column_config.NumberColumn("# Ticket", format="%d", width="small", disabled=True),
            "OS_Oficial": st.column_config.TextColumn("OS Oficial", width="small", disabled=True),
            "frota": st.column_config.TextColumn("Frota", width="small", disabled=True),
            "modelo": st.column_config.TextColumn("Modelo", width="medium", disabled=True),
            "Gestao": st.column_config.TextColumn("Gestão", width="medium", disabled=True),
            "prioridade": st.column_config.Column(
                "Prioridade",
                width="small",
                help="Urgência do atendimento",
                disabled=True
            ),
            # COLUNA EDITÁVEL: STATUS
            "status": st.column_config.SelectboxColumn(
                "Status Atual",
                width="medium",
                options=["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças", "Concluído"],
                required=True,
                help="Selecione para mudar o status"
            ),
            "Data_Formatada": st.column_config.TextColumn("Abertura", width="medium", disabled=True),
            "Tempo_Aberto": st.column_config.TextColumn("Tempo", width="small", disabled=True),
            "descricao": st.column_config.TextColumn("Descrição", width="large", disabled=True),
            "Operacao": st.column_config.TextColumn("Tipo", width="medium", disabled=True),
        },
        disabled=["Ticket", "OS_Oficial", "frota", "modelo", "Gestao", "prioridade", "Data_Formatada", "Tempo_Aberto", "descricao", "Operacao"]
    )

    # --- LÓGICA DE SALVAMENTO AUTOMÁTICO ---
    # Verifica se houve mudanças comparando com o dataframe original
    # O Streamlit rerunna o script quando há edição, então comparamos o estado
    
    # Identificar linhas alteradas
    if not df_show.equals(edited_df):
        # Encontra as diferenças
        # Como Ticket é único, usamos ele para achar a linha
        
        # Converte para dict para facilitar a comparação linha a linha
        original_dict = df_show.set_index('Ticket')['status'].to_dict()
        edited_dict = edited_df.set_index('Ticket')['status'].to_dict()
        
        alteracoes = []
        for ticket_id, novo_status in edited_dict.items():
            status_antigo = original_dict.get(ticket_id)
            if status_antigo != novo_status:
                alteracoes.append((ticket_id, novo_status))
        
        if alteracoes:
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                for ticket, status in alteracoes:
                    # Se for concluído, atualiza data de encerramento também
                    if status == "Concluído":
                        dt_fim_atual = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
                        cursor.execute("UPDATE ordens_servico SET status = ?, data_encerramento = ? WHERE id = ?", (status, dt_fim_atual, ticket))
                    else:
                        # Se reabriu ou mudou para outro status, limpa a data de fim (opcional, mas bom pra consistência)
                        # Ou mantém a data se não quiser perder histórico. Aqui vou limpar para indicar que está aberto.
                        cursor.execute("UPDATE ordens_servico SET status = ?, data_encerramento = NULL WHERE id = ?", (status, ticket))
                
                conn.commit()
                st.toast(f"✅ {len(alteracoes)} status atualizado(s) com sucesso!", icon="💾")
                
                # Pequeno delay para garantir que o toast seja visto antes do rerun
                import time
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
            finally:
                conn.close()

    st.markdown("<br>", unsafe_allow_html=True)
    
    # 4. ÁREA DE DOWNLOAD
    c_csv, c_pdf = st.columns(2)
    with c_csv:
        csv = df_show.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha (CSV)", csv, "relatorio_manutencao.csv", "text/csv", use_container_width=True)
    
    with c_pdf:
        try:
            pdf_bytes = gerar_relatorio_geral(df_show)
            st.download_button("🖨️ Imprimir Relatório (PDF)", pdf_bytes, "relatorio_geral.pdf", "application/pdf", type="primary", use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")
