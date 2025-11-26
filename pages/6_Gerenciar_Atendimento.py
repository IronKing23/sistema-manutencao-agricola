import streamlit as st
import pandas as pd
from database import get_db_connection
from datetime import datetime
import sqlite3
import sys
import os
import pytz 

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_pdf import gerar_relatorio_os 
from utils_log import registrar_log

st.title("🔄 Gerenciar Atendimento")

# --- Fuso Horário ---
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

# --- Funções de Carregamento ---
def carregar_operacoes():
    conn = get_db_connection()
    operacoes = pd.read_sql_query("SELECT id, nome FROM tipos_operacao ORDER BY nome", conn)
    conn.close()
    return operacoes

def carregar_funcionarios():
    conn = get_db_connection()
    funcs = pd.read_sql_query("SELECT id, nome, matricula, setor FROM funcionarios ORDER BY nome", conn)
    conn.close()
    if not funcs.empty:
        funcs['display'] = funcs['nome'] + " (" + funcs['matricula'].astype(str) + ")"
    else:
        funcs['display'] = []
    return funcs

def carregar_areas():
    conn = get_db_connection()
    try:
        areas = pd.read_sql_query("SELECT codigo, nome FROM areas ORDER BY codigo", conn)
        if not areas.empty:
            areas['display'] = areas['codigo'] + " - " + areas['nome']
        else:
            areas['display'] = []
        return areas
    except:
        return pd.DataFrame(columns=['display'])
    finally:
        conn.close()

def carregar_atendimentos(ver_todos=False):
    conn = get_db_connection()
    try:
        filtro_sql = "" if ver_todos else "WHERE os.status != 'Concluído'"
        
        # Query atualizada com JOIN duplo para funcionários (Executante e Solicitante)
        query = f"""
        SELECT 
            os.*, 
            e.frota, e.modelo, e.gestao_responsavel,
            f.nome as nome_executante,
            f_solic.nome as nome_solicitante,
            f_solic.matricula as mat_solicitante,
            op.nome as nome_operacao
        FROM ordens_servico os
        JOIN equipamentos e ON os.equipamento_id = e.id
        LEFT JOIN funcionarios f ON os.funcionario_id = f.id
        LEFT JOIN funcionarios f_solic ON os.solicitante_id = f_solic.id
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
            
            # Tratamento de Nulos para Display
            atendimentos['display'] = "Ticket " + atendimentos['id'].astype(str) + \
                                    " (" + atendimentos['status'] + ") - Frota: " + \
                                    atendimentos['frota'] + " - " + \
                                    atendimentos['descricao_curta']
            
            # Garante que as colunas novas existam no DF mesmo se vierem vazias
            if 'classificacao' not in atendimentos.columns: atendimentos['classificacao'] = 'Corretiva'
            if 'maquina_parada' not in atendimentos.columns: atendimentos['maquina_parada'] = 1
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
areas_df = carregar_areas()

# ==============================================================================
# ABA 1: EDITAR
# ==============================================================================
with tab_editar:
    col_titulo, col_check = st.columns([3, 1])
    with col_titulo:
        st.subheader("Atualizar Status, GPS ou Imprimir")
    with col_check:
        mostrar_concluidos = st.checkbox("Ver Concluídos?", value=False, help="Marque para editar ordens antigas")

    atendimentos_df = carregar_atendimentos(ver_todos=mostrar_concluidos)
    
    if atendimentos_df.empty:
        st.info("Nenhum atendimento encontrado.")
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
            
            # --- HEADER DO TICKET ---
            col_info, col_print = st.columns([3, 1])
            with col_info:
                st.info(f"Ticket: **{selected_id}** | Frota: **{selected_row['frota']}** ({selected_row['modelo']})")
            
            with col_print:
                # Prepara dados para impressão
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
                except Exception as e: st.error(f"Erro ao gerar PDF: {e}")

            st.divider()
            
            # --- FORMULÁRIO DE EDIÇÃO ---
            with st.form("form_update_os"):
                st.markdown("###### 📋 Dados Gerais")
                
                # Linha 1
                col1, col2, col3 = st.columns(3)
                with col1:
                    status_ops = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças", "Concluído"]
                    try: idx_st = status_ops.index(selected_row['status']) 
                    except: idx_st = 0
                    novo_status = st.selectbox("Status Atual", options=status_ops, index=idx_st)
                
                with col2:
                    prio_ops = ["Alta", "Média", "Baixa"]
                    val_p = selected_row['prioridade'] if pd.notna(selected_row['prioridade']) else "Média"
                    try: idx_p = prio_ops.index(val_p) 
                    except: idx_p = 1
                    nova_prioridade = st.selectbox("Prioridade", options=prio_ops, index=idx_p)

                with col3:
                    val_os = selected_row['numero_os_oficial'] if selected_row['numero_os_oficial'] else ""
                    novo_num_os = st.text_input("Número da OS Oficial", value=val_os)

                # Linha 2
                col4, col5, col6 = st.columns(3)
                with col4:
                    ops_list = operacoes_df['nome'].tolist()
                    try: idx_op = ops_list.index(selected_row['nome_operacao']) 
                    except: idx_op = 0
                    novo_op_nome = st.selectbox("Tipo de Operação", options=ops_list, index=idx_op)

                with col5:
                    funcs_list = funcionarios_df['display'].tolist()
                    # Tenta encontrar o executante atual na lista formatada
                    idx_f = None
                    nome_atual = selected_row['nome_executante']
                    if pd.notna(nome_atual):
                        # Procura parcial ou exata
                        match = [f for f in funcs_list if nome_atual in f]
                        if match: idx_f = funcs_list.index(match[0])
                    
                    novo_func_display = st.selectbox("Executante", options=funcs_list, index=idx_f)

                with col6:
                    val_h = float(selected_row['horimetro']) if pd.notna(selected_row['horimetro']) else 0.0
                    novo_horimetro = st.number_input("Horímetro", value=val_h, min_value=0.0, step=0.1, format="%.1f")

                # Linha 3 (NOVO): Solicitante e Gestor
                col_solic, col_gestor = st.columns(2)
                with col_solic:
                    # Lógica para encontrar o solicitante atual
                    idx_s = None
                    nome_solic_atual = selected_row['nome_solicitante']
                    mat_solic_atual = selected_row['mat_solicitante']
                    
                    if pd.notna(nome_solic_atual):
                        # Tenta casar nome e matrícula
                        match_s = [f for f in funcs_list if nome_solic_atual in f]
                        if match_s: idx_s = funcs_list.index(match_s[0])

                    novo_solicitante_display = st.selectbox(
                        "Solicitante (Quem pediu)", 
                        options=funcs_list, 
                        index=idx_s,
                        placeholder="Selecione..."
                    )
                
                with col_gestor:
                    # Gestor é read-only, puxado do banco
                    gestor_bd = selected_row['gestao_responsavel'] if pd.notna(selected_row['gestao_responsavel']) else "-"
                    st.text_input("Gestor Responsável (Da Frota)", value=gestor_bd, disabled=True)

                # Linha 4 (NOVO): KPI
                st.markdown("###### 🔧 Classificação (KPI)")
                col_kpi1, col_kpi2 = st.columns(2)
                with col_kpi1:
                    # Classificação
                    opcoes_class = ["Corretiva", "Preventiva", "Preditiva"]
                    val_class = selected_row.get('classificacao', 'Corretiva')
                    # Tenta limpar valor antigo se vier sujo
                    val_class_clean = val_class.split(' ')[0] if val_class else 'Corretiva'
                    if val_class_clean not in opcoes_class: val_class_clean = 'Corretiva'
                    
                    nova_classificacao = st.selectbox("Tipo de Intervenção", options=opcoes_class, index=opcoes_class.index(val_class_clean))
                
                with col_kpi2:
                    # Máquina Parada
                    val_parada = bool(selected_row.get('maquina_parada', 1))
                    nova_parada = st.checkbox("Máquina Parada?", value=val_parada)

                st.markdown("###### 📅 Datas e Local")
                val_abertura = selected_row['data_hora']
                if pd.isnull(val_abertura): dt_ab_db = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
                else: dt_ab_db = val_abertura.to_pydatetime()
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    d_ab = st.date_input("Data Abertura", value=dt_ab_db.date())
                    t_ab = st.time_input("Hora Abertura", value=dt_ab_db.time())
                
                nova_data_fim = None; nova_hora_fim = None
                with col_d2:
                    if novo_status == "Concluído":
                        val_fim = selected_row['data_encerramento']
                        if pd.isnull(val_fim): dt_fim_db = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
                        else: dt_fim_db = val_fim.to_pydatetime()
                        nova_data_fim = st.date_input("Data Encerramento", value=dt_fim_db.date())
                        nova_hora_fim = st.time_input("Hora Encerramento", value=dt_fim_db.time())
                    else:
                        st.info("Mude para 'Concluído' para fechar a data.")

                col_loc, col_lat, col_lon = st.columns([2, 1, 1])
                with col_loc:
                    opcoes_local = areas_df['display'].tolist() if not areas_df.empty else []
                    val_local_atual = selected_row['local_atendimento']
                    idx_local = None
                    if val_local_atual in opcoes_local: idx_local = opcoes_local.index(val_local_atual)
                    novo_local = st.selectbox("Local / Talhão", options=opcoes_local, index=idx_local)
                    if val_local_atual and val_local_atual not in opcoes_local:
                        st.caption(f"Valor anterior: {val_local_atual}")
                
                lat_at = float(selected_row['latitude']) if pd.notna(selected_row['latitude']) else 0.0
                lon_at = float(selected_row['longitude']) if pd.notna(selected_row['longitude']) else 0.0
                with col_lat: nova_lat = st.number_input("Latitude", value=lat_at, format="%.6f")
                with col_lon: nova_lon = st.number_input("Longitude", value=lon_at, format="%.6f")

                nova_descricao = st.text_area("Descrição", value=selected_row['descricao'], height=100)

                submitted = st.form_submit_button("💾 Salvar Alterações")
                
                if submitted:
                    conn = None
                    try:
                        novo_op_id = operacoes_df[operacoes_df['nome'] == novo_op_nome]['id'].values[0]
                        
                        # ID do Executante
                        novo_func_id = None
                        if novo_func_display:
                            novo_func_id = funcionarios_df[funcionarios_df['display'] == novo_func_display]['id'].values[0]

                        # ID do Solicitante (NOVO)
                        novo_solic_id = None
                        if novo_solicitante_display:
                            novo_solic_id = funcionarios_df[funcionarios_df['display'] == novo_solicitante_display]['id'].values[0]

                        final_abertura = datetime.combine(d_ab, t_ab)
                        final_encerramento = None
                        if novo_status == "Concluído" and nova_data_fim:
                            final_encerramento = datetime.combine(nova_data_fim, nova_hora_fim)
                        elif novo_status == "Concluído" and final_encerramento is None:
                             final_encerramento = datetime.now(FUSO_HORARIO).replace(tzinfo=None)

                        final_lat = nova_lat if nova_lat != 0.0 else None
                        final_lon = nova_lon if nova_lon != 0.0 else None
                        
                        # KPI
                        final_parada = 1 if nova_parada else 0
                        
                        conn = get_db_connection()
                        # QUERY ATUALIZADA
                        sql = """
                            UPDATE ordens_servico 
                            SET status=?, local_atendimento=?, descricao=?, tipo_operacao_id=?, 
                                numero_os_oficial=?, funcionario_id=?, horimetro=?, prioridade=?, 
                                latitude=?, longitude=?, data_hora=?, data_encerramento=?,
                                classificacao=?, maquina_parada=?, solicitante_id=?
                            WHERE id=?
                        """
                        params = (novo_status, novo_local, nova_descricao, int(novo_op_id), 
                                  novo_num_os, novo_func_id, novo_horimetro, nova_prioridade,
                                  final_lat, final_lon, final_abertura, final_encerramento,
                                  nova_classificacao, final_parada, novo_solic_id, selected_id)
                        
                        conn.execute(sql, params)
                        conn.commit()
                        
                        detalhes = f"Status: {novo_status} | Class: {nova_classificacao}"
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
    df_del = carregar_atendimentos(ver_todos=True)
    if df_del.empty: st.info("Nada para excluir.")
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