import streamlit as st
import sqlite3
import time
import extra_streamlit_components as stx 
from datetime import datetime, timedelta
import sys
import os

# Tenta importar utils_senha, se não der, usa fallback simples
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
    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        try: pass_hash = hash_senha('1234')
        except: pass_hash = '1234'
        cursor.execute("INSERT INTO usuarios VALUES ('admin', ?, 'Administrador Geral', 0)", (pass_hash,))
        conn.commit()
    conn.close()

# --- Gerenciador de Cookies (CORRIGIDO) ---
# Removemos o parametro 'experimental_allow_widgets=True' que causava o erro
@st.cache_resource
def get_manager():
    return stx.CookieManager(key="main_auth_manager")

# --- FUNÇÃO PRINCIPAL ---
def check_password():
    garantir_tabela_usuarios()
    
    # Instancia o gerenciador
    try:
        cookie_manager = get_manager()
    except:
        # Fallback caso o componente falhe na renderização inicial
        return False

    time.sleep(0.1)
    
    # 1. LOGOUT
    if st.session_state.get("logged_in"):
        with st.sidebar:
            st.write(f"👤 **{st.session_state.get('user_nome', 'Usuário')}**")
            
            if st.button("Sair / Logout"):
                try: cookie_manager.delete("manutencao_user")
                except: pass
                
                for key in ["logged_in", "user_nome", "username", "force_change", "login_em_processamento"]:
                    if key in st.session_state: del st.session_state[key]
                
                st.session_state["just_logged_out"] = True
                st.warning("Saindo...")
                time.sleep(0.5)
                st.rerun()
        return True

    # 2. AUTO-LOGIN (COOKIE)
    if not st.session_state.get("just_logged_out"):
        try:
            cookies = cookie_manager.get_all()
            cookie_user = cookies.get("manutencao_user") if cookies else None
            
            if cookie_user:
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
        except: pass
    
    if st.session_state.get("just_logged_out"):
        st.session_state["just_logged_out"] = False

    # 3. LOGIN MANUAL (ANIMAÇÃO)
    if st.session_state.get("login_em_processamento"):
        st.markdown("""
        <style>
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
        .loading-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background-color: #0E1117; z-index: 99999;
            display: flex; flex-direction: column; justify-content: center; align-items: center; color: white;
        }
        .tractor-icon { font-size: 80px; animation: bounce 0.6s infinite alternate; }
        .loading-text { font-family: sans-serif; font-size: 24px; margin-top: 20px; font-weight: bold; }
        </style>
        <div class="loading-overlay"><div class="tractor-icon">🚜</div><div class="loading-text">Acessando Sistema...</div></div>
        """, unsafe_allow_html=True)
        
        time.sleep(2.0)
        
        dados = st.session_state["temp_user_data"]
        st.session_state["logged_in"] = True
        st.session_state["username"] = dados['username']
        st.session_state["user_nome"] = dados['nome']
        st.session_state["force_change"] = (dados['force_change'] == 1)
        
        if st.session_state.get("temp_manter"):
            try:
                expires = datetime.now() + timedelta(days=7)
                cookie_manager.set("manutencao_user", dados['username'], expires_at=expires)
            except: pass
            
        del st.session_state["login_em_processamento"]
        del st.session_state["temp_user_data"]
        st.rerun()
        return True

    # 4. TROCA DE SENHA OBRIGATÓRIA
    if st.session_state.get("logged_in") and st.session_state.get("force_change", False):
        st.title("⚠️ Atualização de Segurança")
        with st.container(border=True):
            st.warning("Sua senha precisa ser redefinida.")
            with st.form("form_force_change"):
                p1 = st.text_input("Nova Senha", type="password")
                p2 = st.text_input("Confirmar", type="password")
                if st.form_submit_button("Salvar"):
                    if p1 != p2 or not p1:
                        st.error("Senhas inválidas.")
                    else:
                        try:
                            senha_nova_hash = hash_senha(p1)
                        except:
                            senha_nova_hash = p1
                            
                        conn = sqlite3.connect("manutencao.db")
                        conn.execute("UPDATE usuarios SET password = ?, force_change_password = 0 WHERE username = ?", (senha_nova_hash, st.session_state["username"]))
                        conn.commit()
                        conn.close()
                        st.session_state["force_change"] = False
                        st.success("Senha alterada!")
                        time.sleep(1)
                        st.rerun()
        return False

    # 5. TELA DE LOGIN
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
                    manter = st.checkbox("Manter conectado", value=True)
                    
                    if st.form_submit_button("ACESSAR", type="primary", use_container_width=True):
                        conn = sqlite3.connect("manutencao.db")
                        cursor = conn.cursor()
                        cursor.execute("SELECT nome, password, force_change_password FROM usuarios WHERE username = ?", (user,))
                        res = cursor.fetchone()
                        conn.close()
                        
                        senha_ok = False
                        if res:
                            senha_banco = res[1]
                            # Verifica Hash ou Texto Puro (Compatibilidade)
                            if verificar_senha(pw, senha_banco): senha_ok = True
                            elif pw == senha_banco: senha_ok = True
                        
                        if senha_ok:
                            st.session_state["login_em_processamento"] = True
                            st.session_state["temp_user_data"] = {'username': user, 'nome': res[0], 'force_change': res[2]}
                            st.session_state["temp_manter"] = manter
                            st.rerun()
                        else:
                            st.error("Acesso Negado.")

    return False
