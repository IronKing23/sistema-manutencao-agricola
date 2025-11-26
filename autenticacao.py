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
def get_manager():
    return stx.CookieManager(key="main_auth_manager")

# --- FUNÇÃO PRINCIPAL DE VERIFICAÇÃO ---
def check_password():
    garantir_tabela_usuarios()
    cookie_manager = get_manager()
    
    time.sleep(0.1)

    # ==========================================================================
    # 1. LOGOUT (SAIR)
    # ==========================================================================
    if st.session_state.get("logged_in"):
        if st.sidebar.button("Sair / Logout", key="logout_btn_sidebar"):
            try: cookie_manager.delete("manutencao_user")
            except: pass
            
            for key in ["logged_in", "user_nome", "username", "force_change"]:
                if key in st.session_state: del st.session_state[key]
            
            st.session_state["just_logged_out"] = True
            st.toast("Sessão encerrada.", icon="👋")
            time.sleep(1)
            st.rerun()

    # ==========================================================================
    # 2. TENTATIVA DE AUTO-LOGIN (COOKIE)
    # ==========================================================================
    if not st.session_state.get("logged_in") and not st.session_state.get("just_logged_out"):
        placeholder = st.empty()
        cookie_user = None
        
        try:
            raw_cookies = cookie_manager.get_all()
            cookie_user = raw_cookies.get("manutencao_user") if raw_cookies else None
            
            if not cookie_user:
                with placeholder.container():
                    time.sleep(0.5)
                    raw_cookies = cookie_manager.get_all()
                    cookie_user = raw_cookies.get("manutencao_user") if raw_cookies else None
                    
                    if not cookie_user:
                        time.sleep(0.5)
                        raw_cookies = cookie_manager.get_all()
                        cookie_user = raw_cookies.get("manutencao_user") if raw_cookies else None
        except: pass
        
        placeholder.empty()

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
            except: pass

    if st.session_state.get("just_logged_out"):
        st.session_state["just_logged_out"] = False

    # ==========================================================================
    # 3. SE ESTIVER LOGADO
    # ==========================================================================
    if st.session_state.get("logged_in"):
        if st.session_state.get("force_change", False):
            st.markdown("<style>[data-testid='stSidebar'] { display: none; }</style>", unsafe_allow_html=True)
            st.title("⚠️ Segurança")
            col_bx, _ = st.columns([2, 1])
            with col_bx:
                with st.container(border=True):
                    st.warning("Defina sua senha pessoal.")
                    with st.form("form_force_change"):
                        p1 = st.text_input("Nova Senha", type="password")
                        p2 = st.text_input("Confirmar", type="password")
                        if st.form_submit_button("Salvar"):
                            if p1==p2 and p1:
                                try: nh = hash_senha(p1)
                                except: nh = p1
                                conn = sqlite3.connect("manutencao.db")
                                conn.execute("UPDATE usuarios SET password=?, force_change_password=0 WHERE username=?", (nh, st.session_state["username"]))
                                conn.commit(); conn.close()
                                st.session_state["force_change"] = False
                                st.rerun()
                            else: st.error("Erro na senha.")
            return False
        
        with st.sidebar:
            st.write(f"👤 **{st.session_state.get('user_nome', 'Usuário')}**")
        return True

    # ==========================================================================
    # 4. TELA DE LOGIN (VISUAL CORRIGIDO + ANIMAÇÃO FULLSCREEN)
    # ==========================================================================
    st.markdown("<style>[data-testid='stSidebar'] { display: none; }</style>", unsafe_allow_html=True)
    
    st.markdown("""
    <style>
    .block-container { padding-top: 5rem; }
    
    /* Remove borda e fundo do formulário para ele se fundir ao container */
    [data-testid="stForm"] {
        border: none;
        padding: 0;
        box-shadow: none;
        background-color: transparent;
    }
    
    /* Animações Básicas */
    @keyframes bounce-tractor {
        0%, 20%, 50%, 80%, 100% {transform: translateY(0);}
        40% {transform: translateY(-10px);}
        60% {transform: translateY(-5px);}
    }
    .anim-tractor {
        display: inline-block;
        animation: bounce-tractor 2.5s infinite;
        line-height: 1;
    }

    @keyframes spin-gear {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .anim-gear {
        display: inline-block;
        animation: spin-gear 12s linear infinite;
        transform-origin: center;
        cursor: help;
        line-height: 1;
    }
    
    /* Título */
    .login-title {
        font-family: 'Helvetica', sans-serif;
        font-weight: 800; 
        font-size: 26px; 
        color: #2E7D32; 
        line-height: 1.1;
    }
    
    /* --- TELA DE CARREGAMENTO (FULLSCREEN) --- */
    #loading-screen {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-color: #0e1117; /* Cor de fundo escura moderna */
        z-index: 99999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: white;
        font-family: 'Helvetica', sans-serif;
    }
    
    .loader-content {
        text-align: center;
        animation: fadeIn 0.5s ease-in;
    }
    
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    
    .progress-container {
        width: 300px;
        height: 6px;
        background-color: #333;
        border-radius: 10px;
        margin-top: 20px;
        overflow: hidden;
        position: relative;
    }
    
    .progress-bar {
        height: 100%;
        background-color: #2E7D32; /* Verde do sistema */
        width: 0%;
        animation: load 2.5s ease-out forwards;
        border-radius: 10px;
    }
    
    @keyframes load {
        0% { width: 0%; }
        50% { width: 60%; }
        100% { width: 100%; }
    }
    
    .jumping-tractor {
        font-size: 80px;
        animation: bounce-tractor 1s infinite;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.2, 1])
    
    # Container da tela de login
    login_container = c2.container(border=True)
    
    with login_container:
        
        # --- CABEÇALHO ---
        st.markdown("""
        <div style="display: flex; align-items: center; justify-content: center; margin-top: 20px; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 15px;">
                <div class="anim-tractor" style="font-size: 48px;">🚜</div>
                <div class="login-title">
                    Controle<br>Agrícola
                </div>
            </div>
            <div class="anim-gear" style="font-size: 36px; color: #2E7D32; margin-left: 20px;">
                ⚙️
            </div>
        </div>
        <p style="text-align: center; color: #6c757d; font-size: 0.9rem; margin-bottom: 20px;">
            Bem-vindo! Insira suas credenciais.
        </p>
        """, unsafe_allow_html=True)
        
        # --- FORMULÁRIO ---
        with st.form("login_form"):
            user = st.text_input("Usuário", placeholder="Digite seu usuário...")
            pw = st.text_input("Senha", type="password", placeholder="••••••••")
            
            st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
            manter = st.checkbox("Manter conectado (30 dias)", value=True)
            st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
            
            submitted = st.form_submit_button("ACESSAR SISTEMA", type="primary", use_container_width=True)
            
            if submitted:
                conn = sqlite3.connect("manutencao.db")
                cursor = conn.cursor()
                cursor.execute("SELECT nome, password, force_change_password FROM usuarios WHERE username = ?", (user,))
                res = cursor.fetchone()
                conn.close()
                
                senha_ok = False
                if res:
                    if verificar_senha(pw, res[1]): senha_ok = True
                    elif pw == res[1]: senha_ok = True
                
                if senha_ok:
                    # --- ANIMAÇÃO FULLSCREEN ---
                    login_container.empty()
                    
                    with login_container:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        st.markdown("""
                        <div id="loading-screen">
                            <div class="loader-content">
                                <div class="jumping-tractor">🚜</div>
                                <h2 style="color: #2E7D32; margin-bottom: 5px;">Iniciando Sistema...</h2>
                                <p style="color: #888; font-size: 14px;">Carregando módulos e dados...</p>
                                <div class="progress-container">
                                    <div class="progress-bar"></div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        time.sleep(2.2) 
                    
                    # Registra Sessão
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = user
                    st.session_state["user_nome"] = res[0]
                    st.session_state["force_change"] = (res[2] == 1)
                    
                    if manter:
                        try:
                            # CORREÇÃO AQUI: Garantindo data válida para o cookie
                            expires_at = datetime.now() + timedelta(days=30)
                            cookie_manager.set("manutencao_user", user, expires_at=expires_at)
                        except Exception as e:
                            print(f"Erro cookie: {e}")
                    
                    st.rerun()
                else:
                    st.error("Acesso Negado. Verifique seus dados.")

    return False
