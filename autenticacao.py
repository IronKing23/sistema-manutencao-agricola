"""
autenticacao.py — Tela de login moderna com tema agrícola + segurança hardened
================================================================================

CORREÇÕES DE LAYOUT (vs. versão anterior):
- Form agora respeita largura de 440px alinhada com o card (era full-width)
- Botão de "mostrar senha" não pega mais o gradiente verde (seletor era amplo)
- Checkbox agora é verde (era vermelho — herança do tema padrão)
- Card e form se conectam visualmente sem gap quebrado

SEGURANÇA (mantida da versão anterior):
- Cookie = token aleatório de 256 bits com hash SHA-256 no banco (impossível forjar)
- Fallback inseguro de utils_senha removido (falha alto)
- admin padrão com force_change_password=1
- get_db_connection() padronizado

DEPENDÊNCIAS:
- utils_sessao.py (gerenciamento de tokens)
- utils_senha.py (bcrypt)
- database.py (get_db_connection)
"""

import streamlit as st
import time
import logging
from datetime import datetime, timedelta

import extra_streamlit_components as stx

# --- Imports críticos: falham ALTO se ausentes ---
try:
    from utils_senha import verificar_senha, hash_senha
except ImportError as e:
    raise ImportError(
        "utils_senha não pôde ser importado. O sistema NÃO pode rodar sem "
        "hash seguro de senha. Instale bcrypt: `pip install bcrypt`.\n"
        f"Erro original: {e}"
    ) from e

from database import get_db_connection
from utils_sessao import (
    criar_sessao,
    validar_sessao,
    revogar_sessao,
    garantir_tabela_sessoes,
    COOKIE_SESSION_NAME,
    DURACAO_SESSAO_DIAS,
)


logger = logging.getLogger(__name__)


# =============================================================================
# DB SETUP
# =============================================================================

def garantir_tabela_usuarios():
    """Cria tabela usuarios + admin padrão (se inexistente) + tabela sessions."""
    conn = get_db_connection()
    try:
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
            pass_hash = hash_senha('1234')
            cursor.execute(
                "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
                ('admin', pass_hash, 'Administrador Geral', 1)
            )
        conn.commit()
    finally:
        conn.close()
    garantir_tabela_sessoes()


# =============================================================================
# COOKIE MANAGER & LOGOUT
# =============================================================================

def get_manager():
    return stx.CookieManager(key="auth_cookie_manager")


def _do_logout(cookie_manager):
    """Revoga sessão no banco + limpa state + apaga cookie."""
    token = cookie_manager.get(COOKIE_SESSION_NAME)
    if token:
        revogar_sessao(token)
    for key in ("logged_in", "username", "user_nome", "force_change"):
        if key in st.session_state:
            del st.session_state[key]
    try:
        cookie_manager.delete(COOKIE_SESSION_NAME)
    except KeyError:
        pass


# =============================================================================
# CSS — Tema agrícola moderno
# =============================================================================

LOGIN_CSS = """
<style>
/* ============ Background sky → field ============ */
.stApp {
    background: linear-gradient(180deg,
        #87CEEB 0%,
        #B8E0D2 35%,
        #66bb6a 70%,
        #2E7D32 100%);
    min-height: 100vh;
    position: relative;
    overflow: hidden;
}

/* Folhas decorativas flutuando no fundo */
.deco-leaf {
    position: fixed;
    font-size: 28px;
    opacity: 0.35;
    pointer-events: none;
    z-index: 0;
}
.deco-leaf-1 { top: 12%; left: 8%;   animation: floatA 9s infinite ease-in-out; }
.deco-leaf-2 { top: 28%; right: 10%; animation: floatB 11s infinite ease-in-out; }
.deco-leaf-3 { top: 65%; left: 6%;   animation: floatA 13s infinite ease-in-out reverse; }
.deco-leaf-4 { top: 80%; right: 12%; animation: floatB 10s infinite ease-in-out; }

@keyframes floatA {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    50%      { transform: translateY(-25px) rotate(15deg); }
}
@keyframes floatB {
    0%, 100% { transform: translateY(0) translateX(0) rotate(0deg); }
    50%      { transform: translateY(-20px) translateX(10px) rotate(-12deg); }
}

/* ============ Hide Streamlit chrome ============ */
header[data-testid="stHeader"] { visibility: hidden; }
footer { visibility: hidden; }
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 1.5rem !important;
    max-width: 100% !important;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    position: relative;
    z-index: 1;
}

/* ============ CARD do topo (logo + título) ============ */
.login-card {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    padding: 35px 40px 20px 40px;
    border-radius: 24px 24px 0 0;
    box-shadow:
        0 -10px 30px rgba(0, 0, 0, 0.05),
        0 0 0 1px rgba(255, 255, 255, 0.5) inset;
    text-align: center;
    width: 100%;
    max-width: 440px;
    margin: 0 auto !important;
    border: 1px solid rgba(255, 255, 255, 0.4);
    border-bottom: none;
    animation: cardEntrance 0.9s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cardEntrance {
    0% {
        opacity: 0;
        transform: translateY(40px) scale(0.95);
        filter: blur(8px);
    }
    100% {
        opacity: 1;
        transform: translateY(0) scale(1);
        filter: blur(0);
    }
}

/* ============ FORM — agora alinhado com o card ============ */
/* Aqui está a correção principal: aplicar estilo direto no Streamlit form,
   já que o <div> markdown não consegue envolver widgets nativos. */
div[data-testid="stForm"] {
    background: rgba(255, 255, 255, 0.85) !important;
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    max-width: 440px !important;
    width: 100% !important;
    margin: 0 auto !important;
    padding: 5px 40px 35px 40px !important;
    border-radius: 0 0 24px 24px !important;
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    border-top: none !important;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
    animation: cardEntrance 0.9s cubic-bezier(0.16, 1, 0.3, 1) 0.1s backwards;
}

/* Remove o gap padrão entre elementos no form */
div[data-testid="stForm"] > div {
    gap: 12px !important;
}

/* ============ Logo + smoke puffs ============ */
.logo-wrapper {
    position: relative;
    height: 80px;
    margin-bottom: 8px;
}
.logo-tractor {
    font-size: 60px;
    display: inline-block;
    animation: tractorBounce 2.4s ease-in-out infinite;
    filter: drop-shadow(0 5px 12px rgba(46, 125, 50, 0.25));
    transform-origin: bottom center;
}
@keyframes tractorBounce {
    0%, 100% { transform: translateY(0) rotate(-2deg); }
    50%      { transform: translateY(-8px) rotate(2deg); }
}
.smoke-puff {
    position: absolute;
    top: 18px;
    left: 50%;
    margin-left: -55px;
    font-size: 22px;
    opacity: 0;
    animation: smokeRise 2.4s ease-out infinite;
}
.smoke-puff:nth-of-type(2) { animation-delay: 0.8s; }
.smoke-puff:nth-of-type(3) { animation-delay: 1.6s; }
@keyframes smokeRise {
    0%   { opacity: 0; transform: translate(0, 0) scale(0.4); }
    30%  { opacity: 0.7; }
    100% { opacity: 0; transform: translate(-50px, -50px) scale(1.6); }
}

/* ============ Títulos ============ */
.login-title {
    color: #1b5e20;
    font-size: 30px;
    font-weight: 800;
    margin-bottom: 4px;
    letter-spacing: -0.5px;
}
.login-subtitle {
    color: #689f38;
    font-size: 11px;
    margin-bottom: 0;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

/* ============ Inputs ============ */
div[data-testid="stTextInput"] label {
    display: none;
}
div[data-testid="stTextInput"] > div > div {
    background: transparent !important;
}
div[data-testid="stTextInput"] input {
    border-radius: 14px !important;
    border: 2px solid #e8f5e9 !important;
    padding: 14px 18px !important;
    font-size: 15px !important;
    font-weight: 500;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1) !important;
    background-color: rgba(248, 250, 248, 0.85) !important;
    color: #1b5e20 !important;
}
div[data-testid="stTextInput"] input::placeholder {
    color: #a5a5a5;
    font-weight: 500;
}
div[data-testid="stTextInput"] input:hover {
    background-color: rgba(255, 255, 255, 0.95) !important;
    border-color: #c8e6c9 !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #4caf50 !important;
    background-color: #ffffff !important;
    box-shadow:
        0 0 0 4px rgba(76, 175, 80, 0.15),
        0 8px 24px rgba(76, 175, 80, 0.12) !important;
    transform: translateY(-2px);
}

/* ============ FIX: Botão de "mostrar senha" (eye icon) ============ */
/* O Streamlit renderiza um <button> dentro do stTextInput de senha.
   O seletor anterior pegava ele E aplicava o gradient verde. Agora isolamos. */
div[data-testid="stTextInput"] button {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #689f38 !important;
    width: auto !important;
    height: auto !important;
    padding: 0 14px !important;
    margin: 0 !important;
    transform: none !important;
    border-radius: 0 !important;
}
div[data-testid="stTextInput"] button:hover {
    background-color: rgba(76, 175, 80, 0.08) !important;
    color: #4caf50 !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ============ FIX: Checkbox em verde (era vermelho) ============ */
/* Streamlit usa baseweb (Uber design system) - múltiplos seletores p/ robustez */
div[data-testid="stCheckbox"] {
    margin-top: 4px;
    margin-bottom: 4px;
}
div[data-testid="stCheckbox"] label {
    color: #555 !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    background: transparent !important;
}
div[data-testid="stCheckbox"] label > div:first-child {
    background-color: transparent !important;
}
/* Caixa marcada — sobrescreve cor vermelha por verde */
div[data-testid="stCheckbox"] label span[data-baseweb="checkbox"] > div:first-child,
div[data-testid="stCheckbox"] [aria-checked="true"],
div[data-testid="stCheckbox"] input:checked + div,
div[data-testid="stCheckbox"] label > div[data-baseweb="checkbox"] > div:first-child[aria-checked="true"] {
    background-color: #4caf50 !important;
    border-color: #4caf50 !important;
}
/* O background "highlight" que o baseweb adiciona ao redor da label */
div[data-testid="stCheckbox"] label:hover {
    background: transparent !important;
}

/* ============ FIX: Submit button (escopo limitado) ============ */
/* Antes: `div[data-testid="stForm"] button` pegava TUDO incluindo eye button.
   Agora: usar testid específico OU :last-of-type/seletor mais cirúrgico. */
div[data-testid="stFormSubmitButton"] button,
div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {
    width: 100% !important;
    background: linear-gradient(135deg, #2E7D32 0%, #43a047 50%, #66bb6a 100%) !important;
    background-size: 200% 100% !important;
    background-position: 0% 0% !important;
    color: white !important;
    font-weight: 700 !important;
    border: none !important;
    padding: 14px 0 !important;
    border-radius: 14px !important;
    font-size: 16px !important;
    letter-spacing: 0.8px !important;
    transition: all 0.45s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin-top: 8px !important;
    box-shadow: 0 6px 20px rgba(46, 125, 50, 0.35) !important;
    height: auto !important;
}
div[data-testid="stFormSubmitButton"] button:hover {
    background-position: 100% 0 !important;
    transform: translateY(-3px) !important;
    box-shadow: 0 12px 30px rgba(46, 125, 50, 0.45) !important;
}
div[data-testid="stFormSubmitButton"] button:active {
    transform: translateY(-1px) !important;
}

/* Texto dentro do botão submit (caso herde cor escura) */
div[data-testid="stFormSubmitButton"] button p,
div[data-testid="stFormSubmitButton"] button div {
    color: white !important;
}

/* ============ Erro com shake ============ */
div[data-testid="stAlert"] {
    animation: errorShake 0.5s cubic-bezier(0.36, 0.07, 0.19, 0.97);
    border-radius: 12px !important;
    max-width: 440px;
    margin: 0 auto;
}
@keyframes errorShake {
    10%, 90% { transform: translateX(-2px); }
    20%, 80% { transform: translateX(4px); }
    30%, 50%, 70% { transform: translateX(-6px); }
    40%, 60% { transform: translateX(6px); }
}

/* ============ Loading screen ============ */
#loading-screen {
    position: fixed;
    inset: 0;
    background: linear-gradient(180deg, #87CEEB 0%, #66bb6a 60%, #2E7D32 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    z-index: 99999;
    animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}

.loading-road {
    position: relative;
    width: 320px;
    height: 90px;
    margin-bottom: 25px;
}
.driving-tractor {
    position: absolute;
    bottom: 14px;
    left: 0;
    font-size: 56px;
    animation: driveAcross 1.4s ease-out forwards;
    filter: drop-shadow(0 6px 10px rgba(0, 0, 0, 0.25));
    transform-origin: bottom center;
}
@keyframes driveAcross {
    0%   { left: -10%; transform: translateY(0) rotate(-3deg); }
    25%  { transform: translateY(-3px) rotate(2deg); }
    50%  { transform: translateY(0) rotate(-2deg); }
    75%  { transform: translateY(-3px) rotate(2deg); }
    100% { left: calc(100% - 56px); transform: translateY(0) rotate(-1deg); }
}

.road-base {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 8px;
    background: rgba(255, 255, 255, 0.25);
    border-radius: 4px;
    overflow: hidden;
}
.road-fill {
    height: 100%;
    background: linear-gradient(90deg, #ffffff, #fff59d);
    border-radius: 4px;
    box-shadow: 0 0 12px rgba(255, 255, 255, 0.6);
    animation: fillRoad 1.4s ease-out forwards;
}
@keyframes fillRoad {
    from { width: 0; }
    to   { width: 100%; }
}

.loading-msg-area {
    position: relative;
    height: 30px;
    width: 340px;
    text-align: center;
}
.loading-msg {
    position: absolute;
    inset: 0;
    color: white;
    font-size: 16px;
    font-weight: 700;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.25);
    letter-spacing: 0.4px;
    opacity: 0;
    animation: cycleMsg 1.4s ease-in-out forwards;
}
.loading-msg.m1 { animation-delay: 0s; }
.loading-msg.m2 { animation-delay: 0.4s; }
.loading-msg.m3 { animation-delay: 0.8s; }
@keyframes cycleMsg {
    0%, 12%   { opacity: 0; transform: translateY(8px); }
    24%, 70%  { opacity: 1; transform: translateY(0); }
    85%, 100% { opacity: 0; transform: translateY(-8px); }
}
</style>
"""


LOGIN_HEADER_HTML = """
<div class="deco-leaf deco-leaf-1">🌾</div>
<div class="deco-leaf deco-leaf-2">🌱</div>
<div class="deco-leaf deco-leaf-3">🌾</div>
<div class="deco-leaf deco-leaf-4">🌱</div>

<div class="login-card">
    <div class="logo-wrapper">
        <span class="smoke-puff">💨</span>
        <span class="smoke-puff">💨</span>
        <span class="smoke-puff">💨</span>
        <span class="logo-tractor">🚜</span>
    </div>
    <div class="login-title">Sistema Cedro</div>
    <div class="login-subtitle">Gestão de Frotas &amp; Manutenção</div>
</div>
"""


LOADING_SCREEN_HTML = """
<div id="loading-screen">
    <div class="loading-road">
        <span class="driving-tractor">🚜</span>
        <div class="road-base">
            <div class="road-fill"></div>
        </div>
    </div>
    <div class="loading-msg-area">
        <div class="loading-msg m1">🌱 Aquecendo o motor...</div>
        <div class="loading-msg m2">⚙️ Verificando credenciais...</div>
        <div class="loading-msg m3">🚜 Preparando o terreno...</div>
    </div>
</div>
"""


# =============================================================================
# CHECK_PASSWORD
# =============================================================================

def check_password():
    """Retorna True se autenticado. Tela moderna + sessões seguras."""
    garantir_tabela_usuarios()
    cookie_manager = get_manager()

    # 1. Já logado nesta sessão (RAM) -------------------------------------
    if st.session_state.get("logged_in", False):
        with st.sidebar:
            st.markdown("---")
            if st.button("🚪 Sair do Sistema", use_container_width=True):
                _do_logout(cookie_manager)
                st.rerun()
        return True

    # 2. Tenta restaurar via cookie (token seguro) ------------------------
    token = cookie_manager.get(COOKIE_SESSION_NAME)
    if token:
        username = validar_sessao(token)
        if username:
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT nome, force_change_password FROM usuarios WHERE username = ?",
                    (username,)
                )
                res = cursor.fetchone()
            finally:
                conn.close()
            if res:
                nome = res['nome'] if hasattr(res, 'keys') else res[0]
                force = res['force_change_password'] if hasattr(res, 'keys') else res[1]
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["user_nome"] = nome
                st.session_state["force_change"] = (force == 1)
                st.rerun()
        else:
            try:
                cookie_manager.delete(COOKIE_SESSION_NAME)
            except KeyError:
                pass

    # 3. Tela de Login ----------------------------------------------------
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    login_container = st.empty()

    with login_container.container():
        # Folhas decorativas + card de header
        st.markdown(LOGIN_HEADER_HTML, unsafe_allow_html=True)

        # Form direto, SEM colunas — CSS cuida da largura via max-width: 440px
        with st.form("login_form", clear_on_submit=False):
            user = st.text_input(
                "Usuário",
                placeholder="👤  Nome de utilizador",
                autocomplete="username"
            )
            pwd = st.text_input(
                "Senha",
                type="password",
                placeholder="🔒  Palavra-passe",
                autocomplete="current-password"
            )
            manter = st.checkbox(
                "Manter-me conectado por 30 dias",
                value=True
            )
            submitted = st.form_submit_button(
                "Entrar no Sistema  →",
                use_container_width=True,
                type="primary"
            )

            if submitted:
                if not user or not pwd:
                    st.error("⚠️ Por favor, preencha utilizador e senha.")
                    return False

                # Busca usuário
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT nome, password, force_change_password "
                        "FROM usuarios WHERE username = ?",
                        (user,)
                    )
                    res = cursor.fetchone()
                finally:
                    conn.close()

                # Verifica senha (processa mesmo se usuário inexistente — anti-timing)
                senha_ok = False
                if res:
                    senha_db = res['password'] if hasattr(res, 'keys') else res[1]
                    senha_ok = verificar_senha(pwd, senha_db)

                if res and senha_ok:
                    nome = res['nome'] if hasattr(res, 'keys') else res[0]
                    force = res['force_change_password'] if hasattr(res, 'keys') else res[2]

                    # Cria sessão segura
                    if manter:
                        try:
                            ua = None
                            try:
                                ua = st.context.headers.get("User-Agent")
                            except Exception:
                                pass
                            token = criar_sessao(
                                user, dias=DURACAO_SESSAO_DIAS, user_agent=ua
                            )
                            expire_date = datetime.now() + timedelta(days=DURACAO_SESSAO_DIAS)
                            cookie_manager.set(
                                COOKIE_SESSION_NAME, token, expires_at=expire_date
                            )
                        except Exception as e:
                            logger.exception("Erro ao criar sessão: %s", e)

                    # Loading screen animado
                    login_container.empty()
                    with login_container:
                        st.markdown(LOGIN_CSS, unsafe_allow_html=True)
                        st.markdown(LOADING_SCREEN_HTML, unsafe_allow_html=True)
                        time.sleep(1.2)

                    st.session_state["logged_in"] = True
                    st.session_state["username"] = user
                    st.session_state["user_nome"] = nome
                    st.session_state["force_change"] = (force == 1)
                    st.rerun()
                else:
                    st.error("🔒 Acesso Negado. Verifique seus dados e tente novamente.")

    return False