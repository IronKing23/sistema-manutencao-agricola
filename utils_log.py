import sqlite3
from datetime import datetime
import streamlit as st
import pytz # Biblioteca de fuso horário

# --- Configuração do Fuso Horário ---
# Ajustado para Mato Grosso do Sul. Se quiser Brasília, use 'America/Sao_Paulo'
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

def registrar_log(acao, alvo, detalhes=""):
    """
    Grava uma ação no histórico de auditoria com o horário corrigido para o local.
    """
    # Tenta pegar o usuário da sessão, se não tiver, usa 'Sistema'
    usuario = st.session_state.get("user_nome", "Sistema/Anônimo")
    
    # --- CORREÇÃO DE HORA ROBUSTA ---
    # 1. Pega a hora atual exata em UTC (Tempo Universal)
    utc_now = datetime.now(pytz.utc)
    # 2. Converte matematicamente para o fuso horário local
    local_now = utc_now.astimezone(FUSO_HORARIO)
    # 3. Remove a informação de fuso para salvar como "data simples" no SQLite
    # Isso evita confusão na hora de ler
    data_hora_salvar = local_now.replace(tzinfo=None)
    
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
