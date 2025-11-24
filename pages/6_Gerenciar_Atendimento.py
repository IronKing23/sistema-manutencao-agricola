import streamlit as st
import pandas as pd
from database import get_db_connection
from datetime import datetime
import sqlite3
import sys
import os

# --- CONFIGURAÇÃO DE CAMINHO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_pdf import gerar_relatorio_os 
from utils_log import registrar_log

st.title("🔄 Gerenciar Atendimento")

# --- Funções de Carregamento ---
def carregar_operacoes():
    conn = get_db_connection()
    operacoes = pd.read_sql_query("SELECT id, nome FROM tipos_operacao ORDER BY nome", conn)
    conn.close()
    return operacoes

def carregar_funcionarios():
    conn = get_db_connection()
    funcs = pd.read_sql_query("SELECT id, nome FROM funcionarios ORDER BY nome", conn)
    conn.close()
    return funcs

# ATUALIZADO: Agora aceita o parâmetro 'ver_todos'
def carregar_atendimentos(ver_todos=False):
    conn = get_db_connection()
    try:
        # Se ver_todos for True, não filtramos. Se for False, escondemos os concluídos.
        filtro_sql = "" if ver_todos else "WHERE os.status != 'Concluído'"

        query = f"""
        SELECT 
            os.*, 
            e.frota, e.modelo, e.gestao_responsavel,
            f.nome as nome_executante,
            op.nome as nome_operacao
        FROM ordens_servico os
        JOIN equipamentos e ON os.equipamento_id = e.id
        LEFT JOIN funcionarios f ON os.funcionario_id = f.id
        LEFT JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
        {filtro_sql}
        ORDER BY os.data_hora DESC
        LIMIT 500
        """
        atendimentos = pd.read_sql_query(query, conn)
        
        if not atendimentos.empty:
            atendimentos['data_hora'] = pd.to_datetime(atendimentos['data_hora'], format='mixed', errors='coerce', dayfirst=True)
            atendimentos['data_encerramento'] = pd.to_datetime(atendimentos['data_encerramento'], format='mixed', errors='coerce', dayfirst=True)
            atendimentos['descricao_curta'] = atendimentos['descricao'].str.slice(0, 40) + '...'
            
            # Cria o display visual
            atendimentos['display'] = "Ticket " + atendimentos['id'].astype(str) + \
                                    " (" + atendimentos['status'] + ") - Frota: " + \
                                    atendimentos['frota'] + " - " + \
                                    atendimentos['descricao_curta']
        else:
            atendimentos['display'] = []

        return atendimentos
    except Exception as e:
        st.error(f"Erro ao carregar atendimentos: {e}")
        return pd.DataFrame()
    finally:
        if conn: conn.close()

# --- Layout ---
tab_editar, tab_excluir = st.tabs(["✏️ Editar / Baixar OS", "🗑️ Excluir (Erro de Cadastro)"])

operacoes_df = carregar_operacoes()
funcionarios_df = carregar_funcionarios()

# ==============================================================================
# ABA 1: EDITAR
# ==============================================================================
with tab_editar:
    col_titulo, col_check = st.columns([3, 1])
    with col_titulo:
        st.subheader("Atualizar Status, GPS ou Imprimir")
    with col_check:
        # O CHECKBOX MÁGICO
        mostrar_concluidos = st.checkbox("Ver Concluídos?", value=False, help="Marque para editar ordens antigas/fechadas")

    # Carrega dados baseado no checkbox
    atendimentos_df = carregar_atendimentos(ver_todos=mostrar_concluidos)
    
    if atendimentos_df.empty:
        msg = "Nenhum atendimento encontrado." if mostrar_concluidos else "Nenhum atendimento pendente! 🎉"
        st.info(msg)
    else:
        option_display = st.selectbox(
            "Selecione o Atendimento:",
            options=atendimentos_df['display'],
            index=None,
            placeholder="Busque pelo ticket ou frota...",
            key="sb_edit_os"
        )

        if option_display:
            selected_row = atendimentos_df[atendimentos_df['display'] == option_display].iloc[0]
            selected_id = int(selected_row['id'])
            
            # --- HEADER ---
            col_info, col_print = st.columns([3, 1])
            with col_info:
                st.info(f"Ticket: **{selected_id}** | Frota: **{selected_row['frota']}** ({selected_row['modelo']})")
            
            with col_print:
                # Dados PDF
                dados_para_pdf = {
                    'id': selected_id,
                    'numero_os_oficial': selected_row['numero_os_oficial'],
                    'frota': selected_row['frota'],
                    'modelo': selected_row['modelo'],
                    'gestao': selected_row['gestao_responsavel'],
                    'horimetro': selected_row['horimetro'],
                    'local_atendimento': selected_row['local_atendimento'],
                    'status': selected_row['status'],
                    'prioridade': selected_row['prioridade'],
                    'operacao': selected_row['nome_operacao'],
                    'executante': selected_row['nome_executante'],
                    'descricao': selected_row['descricao'],
                    'data_hora': selected_row['data_hora']
                }
                try:
                    pdf_bytes = gerar_relatorio_os(dados_para_pdf)
                    nome_arq = f"OS_{selected_row['numero_os_oficial']}.pdf" if selected_row['numero_os_oficial'] else f"Ticket_{selected_id}.pdf"
                    st.download_button(label="🖨️ Imprimir Ficha A4", data=pdf_bytes, file_name=nome_arq, mime="application/pdf", type="primary")
                except Exception as e: st.error(f"Erro PDF: {e}")

            st.divider()
            
            # --- FORMULÁRIO ---
            with st.form("form_update_os"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    status_options = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças", "Concluído"]
                    idx_st = status_options.index(selected_row['status']) if selected_row['status'] in status_options else 0
                    novo_status = st.selectbox("Status Atual", options=status_options, index=idx_st)
                with col2:
                    prio_options = ["Alta", "Média", "Baixa"]
                    val_prio = selected_row['prioridade'] if pd.notna(selected_row['prioridade']) else "Média"
                    idx_pr = prio_options.index(val_prio) if val_prio in prio_options else 1
                    nova_prioridade = st.selectbox("Prioridade", options=prio_options, index=idx_pr)
                with col3:
                    val_os = selected_row['numero_os_oficial'] if selected_row['numero_os_oficial'] else ""
                    novo_num_os = st.text_input("Número da OS Oficial", value=val_os)

                col4, col5, col6 = st.columns(3)
                with col4:
                    ops_list = operacoes_df['nome'].tolist()
                    idx_op = ops_list.index(selected_row['nome_operacao']) if selected_row['nome_operacao'] in ops_list else 0
                    novo_op_nome = st.selectbox("Tipo de Operação", options=ops_list, index=idx_op)
                with col5:
                    funcs_list = funcionarios_df['nome'].tolist()
                    idx_func = None
                    if pd.notna(selected_row['nome_executante']) and selected_row['nome_executante'] in funcs_list:
                        idx_func = funcs_list.index(selected_row['nome_executante'])
                    novo_func_nome = st.selectbox("Executante", options=funcs_list, index=idx_func)
                with col6:
                    val_hor = float(selected_row['horimetro']) if pd.notna(selected_row['horimetro']) else 0.0
                    novo_horimetro = st.number_input("Horímetro", value=val_hor, min_value=0.0, step=0.1, format="%.1f")

                st.markdown("###### 📅 Datas e Horários")
                val_abertura = selected_row['data_hora']
                if pd.isnull(val_abertura): dt_abertura_db = datetime.now()
                else: dt_abertura_db = val_abertura.to_pydatetime()
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    d_ab = st.date_input("Data Abertura", value=dt_abertura_db.date())
                    t_ab = st.time_input("Hora Abertura", value=dt_abertura_db.time())
                
                nova_data_fim = None; nova_hora_fim = None
                with col_d2:
                    if novo_status == "Concluído":
                        val_fim = selected_row['data_encerramento']
                        if pd.isnull(val_fim): dt_fim_db = datetime.now()
                        else: dt_fim_db = val_fim.to_pydatetime()
                        nova_data_fim = st.date_input("Data Encerramento", value=dt_fim_db.date())
                        nova_hora_fim = st.time_input("Hora Encerramento", value=dt_fim_db.time())
                    else:
                        st.info("Mude status para 'Concluído' para editar data final.")

                st.markdown("###### 📍 Localização")
                col_loc, col_lat, col_lon = st.columns([2, 1, 1])
                with col_loc: novo_local = st.text_input("Local / Talhão", value=selected_row['local_atendimento'])
                lat_atual = float(selected_row['latitude']) if pd.notna(selected_row['latitude']) else 0.0
                lon_atual = float(selected_row['longitude']) if pd.notna(selected_row['longitude']) else 0.0
                with col_lat: nova_lat = st.number_input("Latitude", value=lat_atual, format="%.6f")
                with col_lon: nova_lon = st.number_input("Longitude", value=lon_atual, format="%.6f")

                nova_descricao = st.text_area("Descrição", value=selected_row['descricao'], height=100)
                submitted = st.form_submit_button("💾 Salvar Alterações")
                
                if submitted:
                    conn = None
                    try:
                        novo_op_id = operacoes_df[operacoes_df['nome'] == novo_op_nome]['id'].values[0]
                        novo_func_id = None
                        if novo_func_nome:
                            novo_func_id = funcionarios_df[funcionarios_df['nome'] == novo_func_nome]['id'].values[0]
                            novo_func_id = int(novo_func_id)

                        final_abertura = datetime.combine(d_ab, t_ab)
                        final_encerramento = None
                        if novo_status == "Concluído" and nova_data_fim:
                            final_encerramento = datetime.combine(nova_data_fim, nova_hora_fim)
                            if final_encerramento < final_abertura: st.warning("Data fim menor que inicio.")

                        final_lat = nova_lat if nova_lat != 0.0 else None
                        final_lon = nova_lon if nova_lon != 0.0 else None
                        
                        conn = get_db_connection()
                        sql = """
                            UPDATE ordens_servico 
                            SET status=?, local_atendimento=?, descricao=?, tipo_operacao_id=?, 
                                numero_os_oficial=?, funcionario_id=?, horimetro=?, prioridade=?, 
                                latitude=?, longitude=?, data_hora=?, data_encerramento=?
                            WHERE id=?
                        """
                        params = (novo_status, novo_local, nova_descricao, int(novo_op_id), 
                                  novo_num_os, novo_func_id, novo_horimetro, nova_prioridade,
                                  final_lat, final_lon, final_abertura, final_encerramento, selected_id)

                        conn.execute(sql, params)
                        conn.commit()
                        
                        detalhes = f"Status: {novo_status} | Abertura: {final_abertura}"
                        registrar_log("EDITAR", f"OS #{selected_id}", detalhes)

                        st.success(f"✅ Ticket {selected_id} atualizado!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
                    finally:
                        if conn: conn.close()

# ==============================================================================
# ABA 2: EXCLUIR
# ==============================================================================
with tab_excluir:
    st.subheader("Remover Atendimento")
    # Aqui sempre permitimos buscar qualquer um para exclusão (mesmo concluído) caso tenha sido erro
    # Se quiser restringir, use carregar_atendimentos(ver_todos=False)
    df_del = carregar_atendimentos(ver_todos=True) 
    
    if df_del.empty:
        st.info("Nada para excluir.")
    else:
        option_del = st.selectbox("Selecione:", options=df_del['display'], index=None, key="sb_del_os")
        if option_del:
            row_del = df_del[df_del['display'] == option_del].iloc[0]
            id_del = int(row_del['id'])
            with st.container(border=True):
                st.markdown(f"### 🎫 Ticket {id_del}")
                st.markdown(f"**Frota:** {row_del['frota']}")
                st.divider()
                confirmacao = st.checkbox(f"⚠️ Confirmo exclusão permanente do Ticket {id_del}.")
                if st.button("🗑️ Excluir Ticket", type="primary", disabled=not confirmacao):
                    conn = None
                    try:
                        conn = get_db_connection()
                        conn.execute("DELETE FROM ordens_servico WHERE id = ?", (id_del,))
                        conn.commit()
                        registrar_log("EXCLUIR", f"OS #{id_del}", f"Frota: {row_del['frota']}")
                        st.success("Ticket excluído.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
                    finally:
                        if conn: conn.close()
