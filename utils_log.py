import sqlite3
from datetime import datetime
import streamlit as st
import pytz

# --- Configuração do Fuso Horário ---
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

def garantir_tabela_logs():
    """Cria a tabela de logs se ela não existir."""
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora DATETIME,
                usuario TEXT,
                acao TEXT,
                alvo TEXT,
                detalhes TEXT
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"Erro ao criar tabela de logs: {e}")
    finally:
        conn.close()

def registrar_log(acao, alvo, detalhes=""):
    """
    Grava uma ação no histórico de auditoria com o horário corrigido.
    Cria a tabela automaticamente se necessário.
    """
    # 1. Garante que a tabela existe antes de gravar
    garantir_tabela_logs()
    
    # 2. Identifica o usuário
    usuario = st.session_state.get("user_nome", "Sistema/Anônimo")
    
    # 3. Ajusta a hora (UTC -> Local -> Naive)
    try:
        utc_now = datetime.now(pytz.utc)
        local_now = utc_now.astimezone(FUSO_HORARIO)
        data_hora_salvar = local_now.replace(tzinfo=None)
    except:
        # Fallback se der erro de fuso
        data_hora_salvar = datetime.now()
    
    try:
        conn = sqlite3.connect("manutencao.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO audit_logs (data_hora, usuario, acao, alvo, detalhes)
            VALUES (?, ?, ?, ?, ?)
        """, (data_hora_salvar, usuario, acao, alvo, detalhes))
        
        conn.commit()
    except Exception as e:
        # Mostra erro no terminal/console para debug
        print(f"ERRO AO GRAVAR LOG: {e}")
    finally:
        conn.close()
