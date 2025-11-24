import streamlit as st
import pandas as pd
import sqlite3
from database import get_db_connection
from datetime import datetime
import pytz # Importante

# Fuso
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

st.title("📌 Quadro de Avisos e Passagem de Turno")

def carregar_recados():
    conn = get_db_connection()
    try:
        query = "SELECT * FROM recados ORDER BY data_hora DESC LIMIT 30"
        return pd.read_sql_query(query, conn)
    except: return pd.DataFrame()
    finally: conn.close()

def excluir_recado(id_recado):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM recados WHERE id = ?", (id_recado,))
        conn.commit()
        st.toast("Mensagem removida!", icon="🗑️")
    except Exception as e: st.error(f"Erro: {e}")
    finally: conn.close()

with st.container(border=True):
    st.markdown("##### 📝 Novo Aviso")
    with st.form("form_novo_aviso", clear_on_submit=True):
        col_txt, col_op = st.columns([3, 1])
        with col_txt: msg_texto = st.text_area("Escreva seu recado:", height=80)
        with col_op:
            st.write(""); st.write("")
            eh_urgente = st.toggle("🔥 É Urgente?", value=False)
        btn_enviar = st.form_submit_button("Publicar", type="primary")

    if btn_enviar:
        if not msg_texto: st.warning("Escreva algo.")
        else:
            autor = st.session_state.get("user_nome", "Colaborador")
            # CORREÇÃO DE HORA
            agora = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
            
            conn = get_db_connection()
            try:
                conn.execute("INSERT INTO recados (data_hora, autor, mensagem, importante) VALUES (?, ?, ?, ?)", (agora, autor, msg_texto, eh_urgente))
                conn.commit()
                st.toast("Publicado!", icon="✅")
                st.rerun()
            finally: conn.close()

st.subheader("Mural de Recados")
df = carregar_recados()

if df.empty: st.info("Nenhum recado.")
else:
    for index, row in df.iterrows():
        try:
            dt_obj = pd.to_datetime(row['data_hora'])
            data_fmt = dt_obj.strftime('%d/%m às %H:%M')
        except: data_fmt = str(row['data_hora'])

        if row['importante']:
            icone = "🚨"; titulo_estilo = ":red[**URGENTE**]"
        else:
            icone = "💬"; titulo_estilo = "**Aviso**"

        with st.container(border=True):
            c1, c2, c3 = st.columns([0.5, 8, 0.5])
            with c1: st.write(f"## {icone}")
            with c2:
                st.markdown(f"{titulo_estilo} | De: **{row['autor']}** | {data_fmt}")
                st.markdown(f"_{row['mensagem']}_")
            with c3:
                usuario_logado = st.session_state.get("user_nome", "")
                username_logado = st.session_state.get("username", "")
                if username_logado == "admin" or usuario_logado == row['autor']:
                    if st.button("🗑️", key=f"del_{row['id']}_{index}"):
                        excluir_recado(row['id'])
                        st.rerun()
