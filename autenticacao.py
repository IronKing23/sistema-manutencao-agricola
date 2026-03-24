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
    def verificar_senha(plana, hash_db):
        return plana == hash_db


    def hash_senha(plana):
        return plana


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
        try:
            pass_hash = hash_senha('1234')
        except:
            pass_hash = '1234'
        cursor.execute("INSERT INTO usuarios VALUES ('admin', ?, 'Administrador Geral', 0)", (pass_hash,))
        conn.commit()
    conn.close()


# --- Gerenciador de Cookies ---
# Removido cache_resource para evitar TypeError, o componente gerencia seu estado
def get_manager():
    return stx.CookieManager(key="auth_cookie_manager")


def check_password():
    """Retorna `True` se o usuário tiver uma senha correta / cookie válido."""
    garantir_tabela_usuarios()
    cookie_manager = get_manager()

    # 1. Verifica se já está logado na sessão atual (RAM)
    if st.session_state.get("logged_in", False):
        # Botão de Logout no Sidebar
        with st.sidebar:
            st.markdown("---")
            if st.button("🚪 Sair do Sistema", use_container_width=True):
                # Limpa o estado da sessão local
                st.session_state["logged_in"] = False
                if "username" in st.session_state: del st.session_state["username"]
                if "user_nome" in st.session_state: del st.session_state["user_nome"]
                if "force_change" in st.session_state: del st.session_state["force_change"]

                # Tenta apagar o cookie com segurança (evita KeyError se já não existir)
                try:
                    cookie_manager.delete("manutencao_user")
                except KeyError:
                    pass  # Se o cookie já não estiver no dicionário, apenas ignora

                st.rerun()
        return True

    # 2. Verifica se tem Cookie válido salvo
    token = cookie_manager.get("manutencao_user")
    if token:
        try:
            # O token salvo é o username direto
            conn = sqlite3.connect("manutencao.db")
            cursor = conn.cursor()
            cursor.execute("SELECT nome, force_change_password FROM usuarios WHERE username = ?", (token,))
            res = cursor.fetchone()
            conn.close()

            if res:
                st.session_state["logged_in"] = True
                st.session_state["username"] = token
                st.session_state["user_nome"] = res[0]
                st.session_state["force_change"] = (res[1] == 1)
                st.rerun()  # Recarrega a página para entrar
        except Exception as e:
            print(f"Erro ao ler cookie: {e}")

    # 3. Se não está logado e não tem cookie válido, mostra tela de Login
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 40px auto;
            padding: 30px;
            background-color: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border: 1px solid #E2E8F0;
        }
        .login-logo {
            text-align: center;
            margin-bottom: 20px;
            font-size: 40px;
        }
        .login-title {
            text-align: center;
            color: #1E293B;
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 5px;
        }
        .login-subtitle {
            text-align: center;
            color: #64748B;
            font-size: 14px;
            margin-bottom: 30px;
        }
        /* Loading animation */
        .loader-content {
            text-align: center;
            padding: 40px 20px;
        }
        .jumping-tractor {
            font-size: 50px;
            animation: jump 0.8s infinite alternate;
            display: inline-block;
            margin-bottom: 15px;
        }
        @keyframes jump {
            0% { transform: translateY(0); }
            100% { transform: translateY(-20px); }
        }
        .progress-container {
            width: 100%;
            background-color: #E2E8F0;
            border-radius: 10px;
            height: 8px;
            margin-top: 20px;
            overflow: hidden;
        }
        .progress-bar {
            height: 100%;
            background-color: #2E7D32;
            width: 0%;
            animation: progress 2.5s ease-in-out forwards;
        }
        @keyframes progress {
            0% { width: 0%; }
            100% { width: 100%; }
        }
    </style>
    """, unsafe_allow_html=True)

    login_container = st.empty()

    with login_container.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<div class="login-logo">🚜</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Acesso Restrito</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Sistema de Gestão de Frotas</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            user = st.text_input("Usuário", placeholder="Digite seu usuário")
            password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            lembrar = st.checkbox("Lembrar meu acesso", value=True)

            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

            if submitted:
                conn = sqlite3.connect("manutencao.db")
                cursor = conn.cursor()
                cursor.execute("SELECT nome, password, force_change_password FROM usuarios WHERE username = ?", (user,))
                res = cursor.fetchone()
                conn.close()

                if res and verificar_senha(password, res[1]):
                    # Salva Cookie se marcou 'lembrar'
                    if lembrar:
                        try:
                            # Define expiração para 30 dias
                            expire_date = datetime.now() + timedelta(days=30)
                            cookie_manager.set("manutencao_user", user, expires_at=expire_date)
                        except Exception as e:
                            print(f"Erro ao gravar cookie: {e}")

                    # --- ANIMAÇÃO DE LOADING ---
                    login_container.empty()
                    with login_container:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        st.markdown("""
                        <div id="loading-screen">
                            <div class="loader-content">
                                <div class="jumping-tractor">🚜</div>
                                <h2 style="color: #2E7D32; margin-bottom: 5px;">Iniciando Sistema...</h2>
                                <p style="color: #888; font-size: 14px;">Carregando módulos e dados...</p>
                                <div class="progress-container"><div class="progress-bar"></div></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        time.sleep(2.5)

                        # Define Sessão RAM
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = user
                    st.session_state["user_nome"] = res[0]
                    st.session_state["force_change"] = (res[2] == 1)

                    st.rerun()
                else:
                    st.error("Acesso Negado. Verifique seus dados.")

        st.markdown('</div>', unsafe_allow_html=True)

    return False