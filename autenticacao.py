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
@st.cache_resource
def get_manager():
    return stx.CookieManager()


cookie_manager = get_manager()


def check_password():
    garantir_tabela_usuarios()

    # Se já logado na sessão RAM, retorna True direto
    if st.session_state.get("logged_in", False):
        return True

    # Puxa o cookie "auth_token"
    token = cookie_manager.get(cookie="auth_token")

    if token:
        try:
            # O token salva: username|nome|timestamp_expiracao
            parts = str(token).split("|")
            if len(parts) == 3:
                user_cookie = parts[0]
                nome_cookie = parts[1]
                exp_timestamp = float(parts[2])

                if datetime.now().timestamp() < exp_timestamp:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = user_cookie
                    st.session_state["user_nome"] = nome_cookie
                    st.rerun()
        except:
            pass

    # --- UI DA TELA DE LOGIN AVANÇADA ---
    st.markdown("""
        <style>
            /* Resetando o fundo para preencher toda a tela */
            .stApp {
                background: linear-gradient(135deg, #1b5e20 0%, #4caf50 100%);
            }

            /* Escondendo cabeçalho e rodapé nativos do Streamlit */
            header[data-testid="stHeader"] { visibility: hidden; }
            footer { visibility: hidden; }

            /* Centralização do conteúdo */
            .block-container {
                padding-top: 0rem !important;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }

            /* Card de Login Flutuante */
            .login-card {
                background: rgba(255, 255, 255, 0.98);
                padding: 40px;
                border-radius: 24px;
                box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3);
                text-align: center;
                width: 100%;
                max-width: 420px;
                margin: auto;
                animation: slideUp 0.8s cubic-bezier(0.25, 0.8, 0.25, 1);
            }

            /* Animação do Card */
            @keyframes slideUp {
                0% { opacity: 0; transform: translateY(50px); }
                100% { opacity: 1; transform: translateY(0); }
            }

            /* Ícone de Trator no Logo pulsando levemente */
            .logo-tractor {
                font-size: 55px;
                margin-bottom: 10px;
                color: #2E7D32;
                animation: pulse 2.5s infinite;
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.05); }
                100% { transform: scale(1); }
            }

            /* Títulos */
            .login-title {
                color: #1b5e20;
                font-size: 30px;
                font-weight: 800;
                margin-bottom: 5px;
                letter-spacing: -0.5px;
            }
            .login-subtitle {
                color: #666;
                font-size: 15px;
                margin-bottom: 30px;
                font-weight: 500;
            }

            /* Ocultando os labels nativos do Streamlit */
            div[data-testid="stTextInput"] label {
                display: none;
            }

            /* Estilizando os inputs */
            div[data-testid="stTextInput"] input {
                border-radius: 12px !important;
                border: 2px solid #e0e0e0 !important;
                padding: 14px 18px !important;
                font-size: 16px !important;
                transition: all 0.3s;
                background-color: #f9f9f9;
            }
            div[data-testid="stTextInput"] input:focus {
                border-color: #4caf50 !important;
                background-color: #ffffff;
                box-shadow: 0 0 0 4px rgba(76, 175, 80, 0.1) !important;
            }

            /* Estilizando o Botão de Login */
            div[data-testid="stButton"] button {
                width: 100%;
                background: linear-gradient(90deg, #1b5e20, #4caf50);
                color: white;
                font-weight: bold;
                border: none;
                padding: 12px 0;
                border-radius: 12px;
                font-size: 17px;
                transition: all 0.3s ease;
                margin-top: 15px;
            }
            div[data-testid="stButton"] button:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(76, 175, 80, 0.4);
                color: white;
                border: none;
            }

            /* Cor do Checkbox */
            div[data-testid="stCheckbox"] label span {
                color: #555;
                font-weight: 500;
            }

            /* --- TELA DE CARREGAMENTO (LOADING) --- */
            @keyframes bounce {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-15px); }
            }
            .jumping-tractor {
                font-size: 70px;
                animation: bounce 1s infinite;
            }
            #loading-screen {
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                background: rgba(255, 255, 255, 0.98);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                z-index: 99999;
            }
            .progress-container {
                width: 250px;
                height: 8px;
                background-color: #e0e0e0;
                border-radius: 10px;
                margin-top: 20px;
                overflow: hidden;
            }
            .progress-bar {
                height: 100%;
                background: linear-gradient(90deg, #1b5e20, #4caf50);
                width: 0%;
                animation: progress 2.5s ease-out forwards;
            }
            @keyframes progress {
                0% { width: 0%; }
                100% { width: 100%; }
            }
        </style>
    """, unsafe_allow_html=True)

    login_container = st.empty()

    # Montando a estrutura visual com colunas vazias para "espremer" o card no centro
    with login_container.container():
        st.markdown("""
            <div class="login-card">
                <div class="logo-tractor">🚜</div>
                <div class="login-title">Sistema Cedro</div>
                <div class="login-subtitle">Gestão de Frotas e Manutenção</div>
            </div>
        """, unsafe_allow_html=True)

        col1, col_center, col3 = st.columns([1, 2, 1])
        with col_center:
            # Inputs com ícones nos placeholders
            user = st.text_input("Usuário", placeholder="👤 Nome de Utilizador")
            pwd = st.text_input("Senha", type="password", placeholder="🔒 Palavra-passe")
            manter_conectado = st.checkbox("Mantenha-me conectado")

            if st.button("Entrar no Sistema"):
                if not user or not pwd:
                    st.error("Por favor, preencha o utilizador e a palavra-passe.")
                    return False

                conn = sqlite3.connect("manutencao.db")
                cursor = conn.cursor()
                cursor.execute("SELECT nome, password, force_change_password FROM usuarios WHERE username=?", (user,))
                res = cursor.fetchone()
                conn.close()

                if res and verificar_senha(pwd, res[1]):
                    # Se "manter_conectado", salva o cookie para 7 dias, senão salva pra 1 hora
                    dias = 7 if manter_conectado else (1 / 24)
                    exp_date = datetime.now() + timedelta(days=dias)
                    cookie_val = f"{user}|{res[0]}|{exp_date.timestamp()}"

                    try:
                        cookie_manager.set(cookie="auth_token", val=cookie_val, expires_at=exp_date)
                    except Exception as e:
                        print(f"Erro ao gravar cookie: {e}")

                    # --- ANIMAÇÃO DE LOADING ---
                    login_container.empty()
                    with login_container:
                        st.markdown("""
                        <div id="loading-screen">
                            <div class="loader-content" style="text-align: center;">
                                <div class="jumping-tractor">🚜</div>
                                <h2 style="color: #2E7D32; margin-bottom: 5px; font-weight: 800;">Iniciando Sistema...</h2>
                                <p style="color: #666; font-size: 15px;">A carregar módulos e painéis de controlo...</p>
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
                    st.error("Acesso Negado. Verifique os seus dados e tente novamente.")

    return False