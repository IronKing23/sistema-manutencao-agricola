import streamlit as st
import pandas as pd
import sqlite3
from database import get_db_connection
from datetime import datetime

# OBS: NÃO TEM st.set_page_config AQUI (Já está no app.py)

st.title("📌 Quadro de Avisos e Passagem de Turno")

# --- Função: Carregar Recados ---
def carregar_recados():
    conn = get_db_connection()
    try:
        # Busca os últimos 30 recados
        query = "SELECT * FROM recados ORDER BY data_hora DESC LIMIT 30"
        return pd.read_sql_query(query, conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()

# --- Função: Excluir Recado ---
def excluir_recado(id_recado):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM recados WHERE id = ?", (id_recado,))
        conn.commit()
        st.toast("Mensagem removida!", icon="🗑️") # Notificação discreta
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")
    finally:
        conn.close()

# ==============================================================================
# 1. ÁREA DE PUBLICAÇÃO (FORMULÁRIO LIMPO)
# ==============================================================================
with st.container(border=True):
    st.markdown("##### 📝 Novo Aviso")
    
    with st.form("form_novo_aviso", clear_on_submit=True):
        col_texto, col_opcoes = st.columns([3, 1])
        
        with col_texto:
            msg_texto = st.text_area("Escreva seu recado:", height=80, placeholder="Ex: Atenção na troca de turno, máquina 50 ficou sem diesel...")
        
        with col_opcoes:
            st.write("") # Espaçamento
            st.write("")
            eh_urgente = st.toggle("🔥 É Urgente?", value=False)
            
        # Botão de envio
        btn_enviar = st.form_submit_button("Publicar no Quadro", type="primary")

    if btn_enviar:
        if not msg_texto:
            st.warning("O recado não pode estar vazio.")
        else:
            autor = st.session_state.get("user_nome", "Colaborador")
            agora = datetime.now()
            
            conn = get_db_connection()
            try:
                conn.execute(
                    "INSERT INTO recados (data_hora, autor, mensagem, importante) VALUES (?, ?, ?, ?)",
                    (agora, autor, msg_texto, eh_urgente)
                )
                conn.commit()
                st.toast("Recado publicado com sucesso!", icon="✅")
                st.rerun()
            finally:
                conn.close()

# ==============================================================================
# 2. MURAL (FEED DE NOTÍCIAS VISUAL)
# ==============================================================================
st.subheader("Mural de Recados")

df = carregar_recados()

if df.empty:
    st.info("Nenhum recado recente. O quadro está limpo! 👍")
else:
    for index, row in df.iterrows():
        # Formatação de Data
        try:
            dt_obj = pd.to_datetime(row['data_hora'])
            data_fmt = dt_obj.strftime('%d/%m às %H:%M')
        except:
            data_fmt = str(row['data_hora'])

        # Definição de Estilo (Urgente vs Normal)
        if row['importante']:
            cor_borda = "red"
            icone = "🚨"
            titulo_estilo = ":red[**URGENTE**]"
            fundo_css = """
            <style>
            div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stMarkdownContainer"] p:contains("URGENTE")) {
                border: 1px solid #ff4b4b;
                background-color: rgba(255, 75, 75, 0.05);
            }
            </style>
            """
        else:
            cor_borda = "gray"
            icone = "💬"
            titulo_estilo = "**Aviso**"
            fundo_css = ""

        # --- CARTÃO DO RECADO ---
        with st.container(border=True):
            # Cabeçalho do Cartão: Ícone | Autor e Data | Botão Excluir
            col_ico, col_info, col_del = st.columns([0.5, 8, 0.5])
            
            with col_ico:
                st.write(f"## {icone}")
            
            with col_info:
                st.markdown(f"{titulo_estilo} | De: **{row['autor']}** | {data_fmt}")
                st.markdown(f"_{row['mensagem']}_") # Mensagem em itálico para destacar
            
            with col_del:
                # Lógica de Permissão para Excluir
                usuario_logado = st.session_state.get("user_nome", "")
                username_logado = st.session_state.get("username", "")
                
                # Pode excluir se for Admin OU se for o dono do recado
                if username_logado == "admin" or usuario_logado == row['autor']:
                    # Chave única garantida para o botão não duplicar
                    if st.button("🗑️", key=f"del_btn_{row['id']}_{index}", help="Excluir este recado"):
                        excluir_recado(row['id'])
                        st.rerun()