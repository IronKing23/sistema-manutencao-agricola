import streamlit as st
import sqlite3
import time
import extra_streamlit_components as stx 
from datetime import datetime, timedelta
import sys
import os

# Tenta importar utils_senha
try:
    from utils_senha import verificar_senha, hash_senha
except ImportError:
    def verificar_senha(plana, hash_db): return plana == hash_db
    def hash_senha(plana): return plana

# --- Banco de Dados ---
def garantir_tabela_usuarios():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            nome TEXT,
            force_change_password INTEGER DEFAULT 0
        )
    """)
    # Cria usuário admin padrão se não existir
    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        try: pass_hash = hash_senha('1234')
        except: pass_hash = '1234'
        cursor.execute("INSERT INTO usuarios VALUES ('admin', ?, 'Administrador Geral', 0)", (pass_hash,))
        conn.commit()
    conn.close()

# --- Gerenciador de Cookies ---
# Removido cache_resource pois causa TypeError com este componente específico
def get_manager():
    return stx.CookieManager(key="main_auth_manager")

# --- FUNÇÃO PRINCIPAL DE VERIFICAÇÃO ---
def check_password():
    garantir_tabela_usuarios()
    
    # Recupera a instância
    cookie_manager = get_manager()
    
    # Pequeno delay inicial para o componente montar
    # (Menor que antes, pois a lógica de retry vai cuidar do resto)
    time.sleep(0.1)

    # ==========================================================================
    # 1. LOGOUT (SAIR)
    # ==========================================================================
    if st.session_state.get("logged_in"):
        if st.sidebar.button("Sair / Logout", key="logout_btn_sidebar"):
            try:
                cookie_manager.delete("manutencao_user")
            except: pass
            
            # Limpa sessão
            keys_to_remove = ["logged_in", "user_nome", "username", "force_change"]
            for key in keys_to_remove:
                if key in st.session_state: del st.session_state[key]
            
            st.session_state["just_logged_out"] = True
            st.warning("Saindo do sistema...")
            time.sleep(1)
            st.rerun()

    # ==========================================================================
    # 2. TENTATIVA DE AUTO-LOGIN VIA COOKIE (COM RETRY PARA WEB)
    # ==========================================================================
    # Só tenta ler cookie se não estiver logado E não acabou de sair
    if not st.session_state.get("logged_in") and not st.session_state.get("just_logged_out"):
        
        placeholder = st.empty()
        cookie_user = None
        
        try:
            # Tenta ler (pode vir None na primeira passada rápida)
            raw_cookies = cookie_manager.get_all()
            cookie_user = raw_cookies.get("manutencao_user") if raw_cookies else None
            
            # LÓGICA DE ESPERA INTELIGENTE
            # Se não achou cookie, espera um pouco e tenta de novo (pode ser latência)
            if not cookie_user:
                with placeholder.container():
                    # Um spinner vazio/invisível apenas para segurar a execução visualmente se necessário
                    time.sleep(0.5) # Espera 0.5s
                    
                    raw_cookies = cookie_manager.get_all()
                    cookie_user = raw_cookies.get("manutencao_user") if raw_cookies else None
                    
                    if not cookie_user:
                        time.sleep(0.5) # Tenta mais uma vez
                        raw_cookies = cookie_manager.get_all()
                        cookie_user = raw_cookies.get("manutencao_user") if raw_cookies else None

        except Exception as e:
            print(f"Erro leitura cookie: {e}")
        
        placeholder.empty()

        # Se achou cookie válido após as tentativas
        if cookie_user:
            try:
                conn = sqlite3.connect("manutencao.db")
                cursor = conn.cursor()
                cursor.execute("SELECT nome, force_change_password FROM usuarios WHERE username = ?", (cookie_user,))
                dados = cursor.fetchone()
                conn.close()
                
                if dados:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = cookie_user
                    st.session_state["user_nome"] = dados[0]
                    st.session_state["force_change"] = (dados[1] == 1)
                    st.rerun()
            except Exception as e:
                print(f"Erro validação banco: {e}")

    if st.session_state.get("just_logged_out"):
        st.session_state["just_logged_out"] = False

    # ==========================================================================
    # 3. SE ESTIVER LOGADO
    # ==========================================================================
    if st.session_state.get("logged_in"):
        
        if st.session_state.get("force_change", False):
            st.markdown("<style>[data-testid='stSidebar'] { display: none; }</style>", unsafe_allow_html=True)
            st.title("⚠️ Atualização de Segurança Obrigatória")
            st.markdown("---")
            
            col_c, col_bx, col_v = st.columns([1, 2, 1])
            with col_bx:
                with st.container(border=True):
                    st.warning("Primeiro acesso detectado. Defina sua senha pessoal.")
                    with st.form("form_force_change"):
                        p1 = st.text_input("Nova Senha", type="password")
                        p2 = st.text_input("Confirmar Nova Senha", type="password")
                        
                        if st.form_submit_button("🔒 Atualizar Senha", type="primary"):
                            if p1 != p2 or not p1:
                                st.error("Senhas inválidas.")
                            else:
                                try: nova_hash = hash_senha(p1)
                                except: nova_hash = p1
                                    
                                conn = sqlite3.connect("manutencao.db")
                                conn.execute("UPDATE usuarios SET password = ?, force_change_password = 0 WHERE username = ?", (nova_hash, st.session_state["username"]))
                                conn.commit()
                                conn.close()
                                
                                st.session_state["force_change"] = False
                                st.success("Senha atualizada! Acesso liberado.")
                                time.sleep(1)
                                st.rerun()
            return False
        
        with st.sidebar:
            st.write(f"👤 **{st.session_state.get('user_nome', 'Usuário')}**")
        
        return True

    # ==========================================================================
    # 4. TELA DE LOGIN
    # ==========================================================================
    st.markdown("<style>[data-testid='stSidebar'] { display: none; }</style>", unsafe_allow_html=True)
    st.markdown("<style>.block-container { padding-top: 3rem; }</style>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 4, 1])
    with c2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center;'>🚜 Controle Agrícola</h2>", unsafe_allow_html=True)
            st.divider()
            
            col_icon, col_form = st.columns([1, 1.5])
            with col_icon:
                st.markdown("<div style='text-align: center; font-size: 80px;'>⚙️</div>", unsafe_allow_html=True)
            
            with col_form:
                with st.form("login_form"):
                    user = st.text_input("Usuário")
                    pw = st.text_input("Senha", type="password")
                    manter_conectado = st.checkbox("Manter conectado (30 dias)", value=True)
                    
                    if st.form_submit_button("ACESSAR", type="primary", use_container_width=True):
                        conn = sqlite3.connect("manutencao.db")
                        cursor = conn.cursor()
                        cursor.execute("SELECT nome, password, force_change_password FROM usuarios WHERE username = ?", (user,))
                        res = cursor.fetchone()
                        conn.close()
                        
                        senha_ok = False
                        if res:
                            senha_banco = res[1]
                            if verificar_senha(pw, senha_banco): senha_ok = True
                            elif pw == senha_banco: senha_ok = True
                        
                        if senha_ok:
                            st.session_state["logged_in"] = True
                            st.session_state["username"] = user
                            st.session_state["user_nome"] = res[0]
                            st.session_state["force_change"] = (res[2] == 1)
                            
                            if manter_conectado:
                                try:
                                    expires = datetime.now() + timedelta(days=30)
                                    cookie_manager.set("manutencao_user", user, expires_at=expires)
                                except Exception as e:
                                    print(f"Erro ao gravar cookie: {e}")
                            
                            st.success("Login realizado! Redirecionando...")
                            time.sleep(1.0)
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos.")

    return False
