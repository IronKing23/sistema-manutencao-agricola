import streamlit as st
import pandas as pd
import sqlite3
import sys
import os

# Import da raiz (para verificar login)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import autenticacao

# --- 1. SEGURANÇA ---
# O app.py já faz o login, mas aqui garantimos que é ADMIN
user_atual = st.session_state.get("username", "")
if user_atual != "admin":
    st.error("⛔ Acesso Restrito: Apenas administradores podem ver os logs de auditoria.")
    st.stop()

st.title("🕵️ Logs de Auditoria e Rastreabilidade")
st.markdown("Histórico completo de ações realizadas no sistema.")

def get_db_connection():
    conn = sqlite3.connect("manutencao.db")
    return conn

# --- 2. FILTROS ---
with st.expander("🔎 Filtros de Busca", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    conn = get_db_connection()
    # Carrega usuários e ações para o filtro
    try:
        users_list = pd.read_sql("SELECT DISTINCT usuario FROM audit_logs", conn)['usuario'].tolist()
        actions_list = pd.read_sql("SELECT DISTINCT acao FROM audit_logs", conn)['acao'].tolist()
    except:
        users_list = []
        actions_list = []
    finally:
        conn.close()
        
    filtro_user = col1.multiselect("Usuário:", options=users_list)
    filtro_acao = col2.multiselect("Ação:", options=actions_list)
    filtro_texto = col3.text_input("Buscar em Detalhes (ex: número da OS)")

# --- 3. CONSULTA ---
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

query += " ORDER BY data_hora DESC LIMIT 500"

conn = get_db_connection()
df_logs = pd.read_sql_query(query, conn, params=params)
conn.close()

# --- 4. VISUALIZAÇÃO ---
if df_logs.empty:
    st.info("Nenhum registro encontrado.")
else:
    # --- CORREÇÃO DE LEITURA DE DATA ---
    # Garante que a leitura seja feita corretamente mesmo com formatos mistos
    df_logs['data_hora'] = pd.to_datetime(df_logs['data_hora'], format='mixed', dayfirst=True, errors='coerce')
    
    # Formata para exibição BR (Dia/Mês/Ano Hora:Min)
    df_logs['data_formatada'] = df_logs['data_hora'].dt.strftime('%d/%m/%Y %H:%M:%S').fillna("-")
    
    # Tabela interativa
    st.dataframe(
        df_logs,
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "data_formatada": st.column_config.TextColumn("Data/Hora", width="medium"),
            "usuario": st.column_config.TextColumn("Autor", width="medium"),
            "acao": st.column_config.TextColumn("Ação", width="small"),
            "alvo": st.column_config.TextColumn("Alvo", width="medium"),
            "detalhes": st.column_config.TextColumn("Detalhes", width="large"),
            "data_hora": None # Esconde a coluna original de data (usa a formatada)
        }
    )
    
    st.caption(f"Mostrando os últimos {len(df_logs)} registros.")
