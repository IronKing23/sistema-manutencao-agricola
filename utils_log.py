import sqlite3
from datetime import datetime
import streamlit as st
import pytz # Importante para corrigir a hora

# --- Configuração de Fuso Horário ---
# Garante que os logs fiquem com a hora local do Brasil/MS
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

def registrar_log(acao, alvo, detalhes=""):
    """
    Grava uma ação no histórico de auditoria com o horário corrigido.
    
    Args:
        acao (str): O tipo de ação (CRIAR, EDITAR, EXCLUIR, LOGIN).
        alvo (str): O objeto afetado (ex: "OS #100").
        detalhes (str): Descrição extra (opcional).
    """
    # Tenta pegar o usuário da sessão, se não tiver, usa 'Sistema'
    usuario = st.session_state.get("user_nome", "Sistema/Anônimo")
    
    # CORREÇÃO DE HORA: Pega hora local e remove info de timezone para salvar padrão
    data_hora_local = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
    
    try:
        conn = sqlite3.connect("manutencao.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO audit_logs (data_hora, usuario, acao, alvo, detalhes)
            VALUES (?, ?, ?, ?, ?)
        """, (data_hora_local, usuario, acao, alvo, detalhes))
        
        conn.commit()
    except Exception as e:
        print(f"Erro ao gravar log: {e}")
    finally:
        conn.close()
