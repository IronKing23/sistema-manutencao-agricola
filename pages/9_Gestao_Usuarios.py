import streamlit as st
import sqlite3
import pandas as pd
import sys
import os

# Importa utilitário de senha
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils_senha import hash_senha

st.title("🔐 Gestão de Usuários (Área Administrativa)")

# Verificação Admin
usuario_atual = st.session_state.get("username", "")
if usuario_atual != "admin":
    st.error("⛔ ACESSO NEGADO")
    st.stop()

def get_db_connection():
    conn = sqlite3.connect("manutencao.db")
    conn.row_factory = sqlite3.Row
    return conn

tab_novo, tab_senha, tab_excluir = st.tabs(["➕ Novo Usuário", "🔑 Alterar Senha", "🗑️ Excluir Acesso"])

# ABA 1: NOVO
with tab_novo:
    st.subheader("Criar novo acesso")
    with st.form("form_novo_user", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_nome = st.text_input("Nome Completo")
            new_user = st.text_input("Usuário (Login)")
        with col2:
            new_pass = st.text_input("Senha Temporária", type="password")
            new_pass_conf = st.text_input("Confirmar Senha", type="password")
            
        if st.form_submit_button("Cadastrar Usuário"):
            if not new_user or not new_pass:
                st.error("Preencha os campos.")
            elif new_pass != new_pass_conf:
                st.error("Senhas não conferem.")
            else:
                conn = get_db_connection()
                try:
                    # CRIPTOGRAFA
                    senha_segura = hash_senha(new_pass)
                    conn.execute("INSERT INTO usuarios (username, password, nome, force_change_password) VALUES (?, ?, ?, 1)", (new_user, senha_segura, new_nome))
                    conn.commit()
                    st.success(f"✅ Usuário '{new_user}' criado com segurança!")
                except sqlite3.IntegrityError:
                    st.error("Usuário já existe.")
                finally: conn.close()

# ABA 2: SENHA
with tab_senha:
    st.subheader("Redefinir Senha")
    conn = get_db_connection()
    df_users = pd.read_sql("SELECT username, nome FROM usuarios", conn)
    conn.close()
    user_options = df_users['username'].tolist()
    escolha_user = st.selectbox("Usuário:", options=user_options)
    
    with st.form("form_troca_senha"):
        nova_senha = st.text_input("Nova Senha", type="password")
        forcar = st.checkbox("Obrigar troca no próximo login?", value=True)
        
        if st.form_submit_button("Redefinir"):
            if not nova_senha:
                st.error("Senha vazia.")
            else:
                conn = get_db_connection()
                try:
                    # CRIPTOGRAFA
                    senha_segura = hash_senha(nova_senha)
                    flag = 1 if forcar else 0
                    conn.execute("UPDATE usuarios SET password = ?, force_change_password = ? WHERE username = ?", (senha_segura, flag, escolha_user))
                    conn.commit()
                    st.success(f"✅ Senha de {escolha_user} atualizada e criptografada!")
                finally: conn.close()

# ABA 3: EXCLUIR (MANTIDA IGUAL)
with tab_excluir:
    st.subheader("Remover Acesso")
    user_del = st.selectbox("Usuário para excluir:", options=user_options, key="del_sel")
    if user_del == "admin": st.error("Não pode excluir admin.")
    else:
        with st.container(border=True):
            if st.button("🗑️ Excluir Definitivamente", type="primary"):
                conn = get_db_connection()
                conn.execute("DELETE FROM usuarios WHERE username = ?", (user_del,))
                conn.commit()
                conn.close()
                st.success("Excluído.")
                st.rerun()

st.divider()
with st.expander("📋 Lista de Usuários"):
    st.dataframe(df_users, use_container_width=True)