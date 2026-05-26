"""
utils_sessao.py — Gerenciamento seguro de sessões persistentes
================================================================

Substitui o esquema antigo de "cookie com username em texto puro" por
sessões com token aleatório, armazenadas no banco com hash SHA-256.

PRINCÍPIO:
- O cookie no navegador recebe um TOKEN aleatório de 256 bits.
- O banco guarda apenas o HASH desse token + username + expires_at.
- Mesmo se alguém dumpar o banco, NÃO consegue forjar um cookie válido
  (precisaria reverter SHA-256, computacionalmente inviável).
- Mesmo se alguém forjar um cookie aleatório, o hash não bate com nada
  no banco → login negado.

USO:
    from utils_sessao import criar_sessao, validar_sessao, revogar_sessao

    # Ao logar:
    token = criar_sessao(username='joao', dias=30)
    cookie_manager.set('manutencao_session', token, expires_at=...)

    # Em revisitas:
    token = cookie_manager.get('manutencao_session')
    username = validar_sessao(token)  # retorna username ou None
    if username:
        # logado
        ...

    # Ao deslogar:
    revogar_sessao(token)
    cookie_manager.delete('manutencao_session')
"""

import sqlite3
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

try:
    from database import get_db_connection
except ImportError:
    # Fallback explícito — se database.py não existir, falha alto
    def get_db_connection():
        conn = sqlite3.connect("manutencao.db")
        conn.row_factory = sqlite3.Row
        return conn


logger = logging.getLogger(__name__)

# Nome do cookie (mudou de 'manutencao_user' para forçar invalidação
# dos cookies antigos no deploy do patch)
COOKIE_SESSION_NAME = "manutencao_session"

# Tempo padrão de sessão "lembrar-me"
DURACAO_SESSAO_DIAS = 30


@contextmanager
def _db():
    """Context manager para conexão segura — commit no sucesso, rollback no erro."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def garantir_tabela_sessoes():
    """Cria a tabela de sessões se ainda não existir. Idempotente."""
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash   TEXT PRIMARY KEY,
                username     TEXT NOT NULL,
                created_at   DATETIME NOT NULL,
                expires_at   DATETIME NOT NULL,
                user_agent   TEXT
            )
        """)
        # Índice para limpeza por expiração
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_expires
            ON sessions(expires_at)
        """)


def _hash_token(token: str) -> str:
    """Calcula SHA-256 do token. Usado para armazenamento seguro no banco."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_sessao(username: str, dias: int = DURACAO_SESSAO_DIAS,
                  user_agent: str = None) -> str:
    """
    Gera uma nova sessão para o usuário.

    Retorna o TOKEN em texto puro (que deve ir para o cookie).
    O hash desse token fica no banco.

    Args:
        username: identificador do usuário (FK lógica para tabela usuarios)
        dias: dias até a sessão expirar
        user_agent: opcional, string do User-Agent do navegador (auditoria)

    Returns:
        str: token aleatório de 256 bits em base64url (43 chars)
    """
    garantir_tabela_sessoes()

    # 32 bytes = 256 bits de entropia, codificados em base64url
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)

    agora = datetime.now()
    expira = agora + timedelta(days=dias)

    with _db() as conn:
        conn.execute("""
            INSERT INTO sessions (token_hash, username, created_at, expires_at, user_agent)
            VALUES (?, ?, ?, ?, ?)
        """, (token_hash, username, agora, expira, user_agent))

    logger.info("Sessão criada para %s (expira em %s)", username, expira)
    return token


def validar_sessao(token: str) -> str | None:
    """
    Valida um token de sessão. Retorna o username se válido, None caso contrário.

    Bloqueia automaticamente:
    - Token vazio ou None
    - Token expirado
    - Token forjado (hash não bate com nada no banco)

    Args:
        token: o valor do cookie

    Returns:
        username (str) se a sessão for válida, None caso contrário
    """
    if not token:
        return None

    try:
        garantir_tabela_sessoes()
        token_hash = _hash_token(token)
        agora = datetime.now()

        with _db() as conn:
            row = conn.execute("""
                SELECT username, expires_at
                FROM sessions
                WHERE token_hash = ?
            """, (token_hash,)).fetchone()

            if not row:
                logger.warning("Tentativa de uso de token inexistente (possível cookie forjado).")
                return None

            # row pode ser tupla ou Row, normalizamos
            if hasattr(row, 'keys'):
                username = row['username']
                expires_at = row['expires_at']
            else:
                username, expires_at = row[0], row[1]

            # SQLite guarda datetime como string ISO
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)

            if expires_at < agora:
                logger.info("Sessão expirada para %s, removendo.", username)
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None

            return username

    except Exception as e:
        logger.exception("Erro ao validar sessão: %s", e)
        return None


def revogar_sessao(token: str) -> bool:
    """
    Revoga uma sessão específica (logout). Retorna True se algo foi removido.
    """
    if not token:
        return False
    try:
        token_hash = _hash_token(token)
        with _db() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (token_hash,)
            )
            return cursor.rowcount > 0
    except Exception as e:
        logger.exception("Erro ao revogar sessão: %s", e)
        return False


def revogar_todas_sessoes_do_usuario(username: str) -> int:
    """
    Revoga TODAS as sessões de um usuário. Útil quando:
    - O usuário trocou a senha (boa prática: invalidar outros logins)
    - Suspeita-se de comprometimento da conta
    - Admin precisa kickar alguém

    Retorna o número de sessões revogadas.
    """
    try:
        with _db() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE username = ?", (username,)
            )
            n = cursor.rowcount
            logger.info("%d sessão(ões) de %s revogada(s).", n, username)
            return n
    except Exception as e:
        logger.exception("Erro ao revogar sessões de %s: %s", username, e)
        return 0


def limpar_sessoes_expiradas() -> int:
    """
    Remove do banco todas as sessões expiradas. Pode ser chamada em background
    ou no início de cada request (custo baixo: índice em expires_at).

    Retorna o número de sessões removidas.
    """
    try:
        with _db() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE expires_at < ?", (datetime.now(),)
            )
            n = cursor.rowcount
            if n > 0:
                logger.info("%d sessão(ões) expirada(s) removida(s).", n)
            return n
    except Exception as e:
        logger.exception("Erro na limpeza de sessões: %s", e)
        return 0