import streamlit as st
import pandas as pd
import sqlite3

# OBS: Não importamos mais autenticacao aqui para evitar conflito.
# O app.py já garantiu o login.

st.title("🕵️ Logs de Auditoria e Rastreabilidade")
st.markdown("Histórico completo de ações realizadas no sistema.")

# --- 1. VERIFICAÇÃO DE SEGURANÇA (SOMENTE ADMIN) ---
# Pegamos o usuário direto da sessão (que o app.py preencheu)
user_atual = st.session_state.get("username", "")

if user_atual != "admin":
    st.error("⛔ Acesso Restrito: Apenas administradores podem ver os logs de auditoria.")
    st.stop() # Para a execução aqui se não for admin

def get_db_connection():
    conn = sqlite3.connect("manutencao.db")
    return conn

# --- 2. FILTROS DE BUSCA ---
with st.expander("🔎 Filtros de Busca Avançada", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    conn = get_db_connection()
    # Carrega listas únicas para os filtros
    try:
        users_list = pd.read_sql("SELECT DISTINCT usuario FROM audit_logs ORDER BY usuario", conn)['usuario'].tolist()
        actions_list = pd.read_sql("SELECT DISTINCT acao FROM audit_logs ORDER BY acao", conn)['acao'].tolist()
    except:
        users_list = []
        actions_list = []
    finally:
        conn.close()
        
    filtro_user = col1.multiselect("Filtrar por Usuário:", options=users_list)
    filtro_acao = col2.multiselect("Filtrar por Ação:", options=actions_list)
    filtro_texto = col3.text_input("Buscar em Detalhes (ex: número da OS, placa, frota)")

# --- 3. CONSULTA AO BANCO ---
query = "SELECT * FROM audit_logs WHERE 1=1"
params = []

if filtro_user:
    query += f" AND usuario IN ({','.join(['?']*len(filtro_user))})"
    params.extend(filtro_user)

if filtro_acao:
    query += f" AND acao IN ({','.join(['?']*len(filtro_acao))})"
    params.extend(filtro_acao)

if filtro_texto:
    query += " AND (alvo LIKE ? OR detalhes LIKE ?)"
    term = f"%{filtro_texto}%"
    params.extend([term, term])

query += " ORDER BY data_hora DESC LIMIT 1000" # Limite de segurança

conn = get_db_connection()
try:
    df_logs = pd.read_sql_query(query, conn, params=params)
except Exception as e:
    st.error(f"Erro ao ler logs: {e}")
    df_logs = pd.DataFrame()
finally:
    conn.close()

# --- 4. VISUALIZAÇÃO ---
if df_logs.empty:
    st.info("Nenhum registro encontrado com os filtros atuais.")
else:
    # --- TRATAMENTO DE DATAS ROBUSTO ---
    # format='mixed' garante que o Pandas leia tanto datas com milissegundos quanto sem
    df_logs['data_hora'] = pd.to_datetime(df_logs['data_hora'], format='mixed', dayfirst=True, errors='coerce')
    
    # Formata para exibição brasileira (Dia/Mês/Ano Hora:Min:Seg)
    # Como removemos o tzinfo na hora de salvar (no utils_log), aqui ele exibe exatamente o que salvou (Hora Local)
    df_logs['data_formatada'] = df_logs['data_hora'].dt.strftime('%d/%m/%Y %H:%M:%S').fillna("-")
    
    # Exibição da Tabela
    st.dataframe(
        df_logs,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID Log", width="small"),
            "data_formatada": st.column_config.TextColumn("Data/Hora", width="medium"),
            "usuario": st.column_config.TextColumn("Autor da Ação", width="medium"),
            "acao": st.column_config.TextColumn("Tipo de Ação", width="small"),
            "alvo": st.column_config.TextColumn("Alvo (ID)", width="medium"),
            "detalhes": st.column_config.TextColumn("Detalhes da Operação", width="large"),
            "data_hora": None # Oculta a coluna original de data
        }
    )
    
    st.caption(f"Mostrando os últimos {len(df_logs)} registros encontrados.")
