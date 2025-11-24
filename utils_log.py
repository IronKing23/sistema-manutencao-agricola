import sqlite3
from datetime import datetime
import streamlit as st

def registrar_log(acao, alvo, detalhes=""):
    """
    Grava uma ação no histórico de auditoria.
    
    Args:
        acao (str): O tipo de ação (CRIAR, EDITAR, EXCLUIR, LOGIN).
        alvo (str): O objeto afetado (ex: "OS #100").
        detalhes (str): Descrição extra (opcional).
    """
    # Tenta pegar o usuário da sessão, se não tiver, usa 'Sistema'
    usuario = st.session_state.get("user_nome", "Sistema/Anônimo")
    
    try:
        conn = sqlite3.connect("manutencao.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO audit_logs (data_hora, usuario, acao, alvo, detalhes)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now(), usuario, acao, alvo, detalhes))
        
        conn.commit()
    except Exception as e:
        print(f"Erro ao gravar log: {e}")
    finally:
        conn.close()