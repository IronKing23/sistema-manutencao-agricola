import sqlite3
from datetime import datetime
import streamlit as st
import pytz # Biblioteca de fuso horário

# --- Configuração do Fuso Horário ---
# Ajustado para Mato Grosso do Sul ('America/Campo_Grande').
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

def registrar_log(acao, alvo, detalhes=""):
    """
    Grava uma ação no histórico de auditoria com o horário corrigido para o local.
    """
    # Tenta pegar o usuário da sessão, se não tiver, usa 'Sistema'
    usuario = st.session_state.get("user_nome", "Sistema/Anônimo")
    
    # --- CORREÇÃO DE HORA (A MÁGICA ACONTECE AQUI) ---
    # 1. Pega o momento atual no fuso correto (MS)
    agora_local = datetime.now(FUSO_HORARIO)
    
    # 2. Remove a "etiqueta" de fuso (.replace(tzinfo=None))
    # Isso é crucial! O SQLite prefere datas "limpas" (Naive). 
    # Se salvarmos "14:00-04:00", ele pode confundir na leitura.
    # Salvando apenas "14:00", garantimos que a visualização será exata.
    data_hora_salvar = agora_local.replace(tzinfo=None)
    
    try:
        conn = sqlite3.connect("manutencao.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO audit_logs (data_hora, usuario, acao, alvo, detalhes)
            VALUES (?, ?, ?, ?, ?)
        """, (data_hora_salvar, usuario, acao, alvo, detalhes))
        
        conn.commit()
    except Exception as e:
        print(f"Erro ao gravar log: {e}")
    finally:
        conn.close()
