import streamlit as st
import sqlite3
import pandas as pd
import sys
import os

# Importa utilitário de senha da raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Tenta importar a função de hash. Se não der, usa fallback.
try:
    from utils_senha import hash_senha
except ImportError:
    def hash_senha(senha): return senha

import autenticacao

st.set_page_config(layout="wide", page_title="Gestão de Usuários")

# --- VERIFICAÇÃO DE LOGIN E ADMIN ---
# O app.py já carrega o login, mas aqui validamos se é ADMIN
if not st.session_state.get("logged_in"):
    st.warning("Por favor, faça login.")
    st.stop()

usuario_atual = st.session_state.get("username", "")
if usuario_atual != "admin":
    st.error("⛔ ACESSO NEGADO")
    st.markdown(f"""
    Você está logado como **{usuario_atual}**.
    Apenas o usuário **admin** (Administrador Geral) tem permissão para gerenciar acessos.
    """)
    st.stop()

st.title("🔐 Gestão de Usuários (Área Administrativa)")

def get_db_connection():
    conn = sqlite3.connect("manutencao.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- ABAS ---
tab_novo, tab_senha, tab_excluir = st.tabs(["➕ Novo Usuário", "🔑 Alterar Senha", "🗑️ Excluir Acesso"])

# ==============================================================================
# ABA 1: CADASTRAR NOVO USUÁRIO (COM OBRIGAÇÃO DE TROCA)
# ==============================================================================
with tab_novo:
    st.subheader("Criar novo acesso")
    st.info("ℹ️ Nota: O novo usuário será **obrigado** a criar uma senha pessoal no primeiro login.")
    
    with st.form("form_novo_user", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_nome = st.text_input("Nome Completo", placeholder="Ex: João da Silva")
            new_user = st.text_input("Usuário (Login)", placeholder="Ex: joao.silva")
        with col2:
            new_pass = st.text_input("Senha Temporária", type="password")
            new_pass_conf = st.text_input("Confirmar Senha", type="password")
            
        btn_criar = st.form_submit_button("Cadastrar Usuário")
        
        if btn_criar:
            if not new_user or not new_pass or not new_nome:
                st.error("Preencha todos os campos.")
            elif new_pass != new_pass_conf:
                st.error("As senhas não conferem.")
            else:
                conn = get_db_connection()
                try:
                    # Criptografa a senha
                    senha_segura = hash_senha(new_pass)
                    
                    # --- AQUI ESTÁ A MÁGICA ---
                    # Inserimos '1' na coluna force_change_password
                    conn.execute(
                        """
                        INSERT INTO usuarios (username, password, nome, force_change_password) 
                        VALUES (?, ?, ?, 1)
                        """, 
                        (new_user, senha_segura, new_nome)
                    )
                    conn.commit()
                    st.success(f"✅ Usuário '{new_user}' criado! A troca de senha foi agendada.")
                    
                    # Log de Auditoria (Opcional, se quiser rastrear quem criou)
                    # from utils_log import registrar_log
                    # registrar_log("CRIAR USUÁRIO", f"User: {new_user}", "Criação administrativa")

                except sqlite3.IntegrityError:
                    st.error("Erro: Este nome de usuário já existe.")
                except Exception as e:
                    st.error(f"Erro técnico: {e}")
                finally:
                    conn.close()

# ==============================================================================
# ABA 2: ALTERAR SENHA (RESET)
# ==============================================================================
with tab_senha:
    st.subheader("Redefinir Senha de Usuários")
    
    conn = get_db_connection()
    df_users = pd.read_sql("SELECT username, nome FROM usuarios", conn)
    conn.close()
    
    user_options = df_users['username'].tolist()
    escolha_user = st.selectbox("Selecione o Usuário para Resetar:", options=user_options)
    
    with st.form("form_troca_senha"):
        st.warning(f"⚠️ Você está alterando a senha de **{escolha_user}**.")
        nova_senha = st.text_input("Nova Senha", type="password")
        
        # Opção para forçar troca novamente (Marcado por padrão)
        forcar_troca = st.checkbox("Obrigar usuário a trocar esta senha no próximo login?", value=True)
        
        btn_trocar = st.form_submit_button("Redefinir Senha")
        
        if btn_trocar:
            if not nova_senha:
                st.error("A senha não pode ser vazia.")
            else:
                conn = get_db_connection()
                try:
                    senha_segura = hash_senha(nova_senha)
                    flag = 1 if forcar_troca else 0
                    
                    conn.execute(
                        "UPDATE usuarios SET password = ?, force_change_password = ? WHERE username = ?",
                        (senha_segura, flag, escolha_user)
                    )
                    conn.commit()
                    st.success(f"✅ Senha de {escolha_user} redefinida com sucesso!")
                except Exception as e:
                    st.error(f"Erro: {e}")
                finally:
                    conn.close()

# ==============================================================================
# ABA 3: EXCLUIR USUÁRIO
# ==============================================================================
with tab_excluir:
    st.subheader("Remover Acesso")
    
    user_to_delete = st.selectbox("Selecione para excluir:", options=user_options, key="del_select")
    
    if user_to_delete == "admin":
        st.error("⛔ O usuário 'admin' principal não pode ser excluído.")
    else:
        with st.container(border=True):
            st.markdown(f"Tem certeza que deseja excluir o usuário **{user_to_delete}**?")
            confirm = st.checkbox("Sim, tenho certeza absoluta.")
            
            if st.button("🗑️ Excluir Usuário", type="primary", disabled=not confirm):
                conn = get_db_connection()
                try:
                    conn.execute("DELETE FROM usuarios WHERE username = ?", (user_to_delete,))
                    conn.commit()
                    st.success(f"Usuário {user_to_delete} removido.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
                finally:
                    conn.close()

st.divider()
with st.expander("📋 Ver Lista de Usuários Cadastrados"):
    st.dataframe(df_users, use_container_width=True, hide_index=True)
