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
    # key fixa é crucial para manter a referência entre reruns
    return stx.CookieManager(key="main_auth_manager")

# --- FUNÇÃO PRINCIPAL DE VERIFICAÇÃO ---
def check_password():
    garantir_tabela_usuarios()
    
    cookie_manager = get_manager()
    
    # ==========================================================================
    # 1. TENTATIVA DE AUTO-LOGIN VIA COOKIE (COM RETRY PARA WEB)
    # ==========================================================================
    # Se o usuário NÃO está logado na sessão atual (RAM), tentamos recuperar via Cookie.
    if not st.session_state.get("logged_in"):
        try:
            # Primeira tentativa de leitura
            cookies = cookie_manager.get_all()
            
            # LÓGICA DE RETENTATIVA (CORREÇÃO PARA CLOUD/WEB)
            # Se a lista de cookies vier vazia ou nula, pode ser apenas latência da rede.
            # Esperamos um pouco e tentamos ler novamente.
            if not cookies or "manutencao_user" not in cookies:
                time.sleep(0.3) # Aguarda o componente JS carregar
                cookies = cookie_manager.get_all()
                
                if not cookies or "manutencao_user" not in cookies:
                    time.sleep(0.3) # Segunda chance
                    cookies = cookie_manager.get_all()

            cookie_user = cookies.get("manutencao_user")
            
            if cookie_user:
                conn = sqlite3.connect("manutencao.db")
                cursor = conn.cursor()
                cursor.execute("SELECT nome, force_change_password FROM usuarios WHERE username = ?", (cookie_user,))
                dados = cursor.fetchone()
                conn.close()
                
                if dados:
                    # RECONSTRÓI A SESSÃO
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = cookie_user
                    st.session_state["user_nome"] = dados[0]
                    st.session_state["force_change"] = (dados[1] == 1)
                    
                    # Força um rerun para atualizar a interface imediatamente com o login feito
                    st.rerun()
                    
        except Exception as e:
            print(f"Debug Cookie: {e}")

    # ==========================================================================
    # 2. SE ESTIVER LOGADO (Sessão ou Cookie validado acima)
    # ==========================================================================
    if st.session_state.get("logged_in"):
        
        # A) Bloqueio de Troca de Senha Obrigatória
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
            return False # Bloqueia o app enquanto não trocar
        
        # B) Acesso Liberado (Sidebar + Logout)
        with st.sidebar:
            st.write(f"👤 **{st.session_state.get('user_nome', 'Usuário')}**")
            
            if st.button("Sair / Logout"):
                # 1. Apaga o cookie (mata a persistência)
                try:
                    cookie_manager.delete("manutencao_user")
                except: pass
                
                # 2. Limpa a sessão (mata a memória RAM)
                for key in ["logged_in", "user_nome", "username", "force_change"]:
                    if key in st.session_state: del st.session_state[key]
                
                st.warning("Saindo...")
                time.sleep(1) # Tempo para o cookie ser deletado no navegador
                st.rerun()
        
        return True # Retorna True para o app.py carregar as páginas

    # ==========================================================================
    # 3. TELA DE LOGIN (Se não tiver cookie nem sessão)
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
                    # Checkbox padrão marcado para facilitar a vida
                    manter_conectado = st.checkbox("Manter conectado por 30 dias", value=True)
                    
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
                            elif pw == senha_banco: senha_ok = True # Fallback texto plano
                        
                        if senha_ok:
                            # 1. Atualiza Sessão Imediata
                            st.session_state["logged_in"] = True
                            st.session_state["username"] = user
                            st.session_state["user_nome"] = res[0]
                            st.session_state["force_change"] = (res[2] == 1)
                            
                            # 2. Grava Cookie Persistente (Se marcado)
                            if manter_conectado:
                                expires = datetime.now() + timedelta(days=30)
                                cookie_manager.set("manutencao_user", user, expires_at=expires)
                            
                            st.success("Login realizado com sucesso!")
                            # Delay maior no login para garantir que o cookie seja gravado antes do rerun
                            time.sleep(1.0) 
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos.")

    return False
