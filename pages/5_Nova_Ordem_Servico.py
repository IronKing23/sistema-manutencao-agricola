import streamlit as st
import sqlite3
from database import get_db_connection
import pandas as pd
from datetime import datetime
import sys
import os
import pytz 

# Importa o registrador de logs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils_log import registrar_log

st.title("📋 Nova Ordem de Serviço")

# Fuso Horário
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

# --- Funções de Carregamento ---
def carregar_frotas():
    conn = get_db_connection()
    frotas = pd.read_sql_query("SELECT id, frota, modelo FROM equipamentos ORDER BY frota", conn)
    conn.close()
    frotas['display'] = frotas['frota'] + " - " + frotas['modelo']
    return frotas

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

def verificar_duplicidade(equipamento_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT count(*) FROM ordens_servico 
            WHERE equipamento_id = ? AND status != 'Concluído'
        """, (equipamento_id,))
        return cursor.fetchone()[0] > 0
    finally:
        conn.close()

def obter_ordem_aberta(equipamento_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, descricao, status, numero_os_oficial 
            FROM ordens_servico 
            WHERE equipamento_id = ? AND status != 'Concluído'
            ORDER BY id DESC LIMIT 1
        """, (equipamento_id,))
        return cursor.fetchone()
    finally:
        conn.close()

# Carrega dados iniciais
try:
    frotas_df = carregar_frotas()
    operacoes_df = carregar_operacoes()
    funcionarios_df = carregar_funcionarios()
    areas_df = carregar_areas()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# --- LAYOUT EM ABAS ---
tab_manual, tab_importar = st.tabs(["📝 Abertura Manual", "📂 Importação em Lote (Histórico/Excel)"])

# ==============================================================================
# ABA 1: MANUAL
# ==============================================================================
with tab_manual:
    st.subheader("Detalhes do Atendimento")

    tipo_atendimento = st.radio(
        "Classificação do Problema:",
        ["Pendência (Máquina TRABALHANDO)", "Parada (Máquina PARADA/QUEBRADA)"],
        horizontal=True,
        index=0,
        key="radio_tipo_manual"
    )

    with st.form("form_os", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            frota_display = st.selectbox("Frota Atendida*", options=frotas_df['display'], index=None, placeholder="Selecione a frota...")
        
        with col2:
            opcoes_local = areas_df['display'].tolist() if not areas_df.empty else []
            local_atendimento = st.selectbox("Local / Talhão*", options=opcoes_local, index=None, placeholder="Selecione a área..." if opcoes_local else "Nenhuma área cadastrada!")
            if not opcoes_local: st.caption("⚠️ Cadastre as áreas no menu 'Cadastros > Áreas'.")

        with col3:
            horimetro = st.number_input("Horímetro Atual (Horas)", min_value=0.0, step=0.1, format="%.1f")

        with st.expander("📍 Localização GPS (Opcional - Para Mapa)"):
            c_lat, c_lon = st.columns(2)
            lat = c_lat.number_input("Latitude", value=0.0, format="%.6f", help="Ex: -23.5505")
            lon = c_lon.number_input("Longitude", value=0.0, format="%.6f", help="Ex: -46.6333")
            st.caption("Dica: Pegue no Google Maps ou Solinftec.")

        if frota_display:
            equip_id_check = frotas_df[frotas_df['display'] == frota_display]['id'].values[0]
            ordem_existente = obter_ordem_aberta(int(equip_id_check))
            if ordem_existente:
                st.info(f"ℹ️ NOTA: Já existe o Ticket #{ordem_existente[0]} aberto. As novas informações serão adicionadas a ele.")

        col4, col5, col6 = st.columns(3)
        with col4: operacao_display = st.selectbox("Sistema Afetado / Operação*", options=operacoes_df['nome'], index=None)
        with col5: funcionario_display = st.selectbox("Executante / Responsável", options=funcionarios_df['display'], index=None, placeholder="Busque por Nome ou Matrícula...")
        with col6: prioridade = st.selectbox("Prioridade / Urgência", options=["🔴 Alta (Urgente)", "🟡 Média (Normal)", "🔵 Baixa (Pode esperar)"], index=1)

        descricao = st.text_area("Descrição Detalhada do Problema*", placeholder="Descreva o problema...")
        
        num_os_oficial = None
        status_inicial = "Pendente"

        if "Parada" in tipo_atendimento:
            st.markdown("---"); st.error("🔴 **Dados de Máquina Parada (Obrigatório)**")
            col_os, col_status = st.columns(2)
            with col_os:
                input_os = st.text_input("Número da OS Oficial")
                if input_os: num_os_oficial = input_os
            with col_status:
                status_inicial = st.selectbox("Status Inicial", options=["Aberto (Parada)", "Em Andamento", "Aguardando Peças"], index=0)

        st.markdown("---")
        submitted = st.form_submit_button("✅ Processar Solicitação")

    if submitted:
        if not frota_display or not operacao_display or not descricao or not local_atendimento:
            st.error("Preencha os campos obrigatórios: Frota, Local, Operação e Descrição.")
        elif "Parada" in tipo_atendimento and not num_os_oficial:
            st.error("Para atendimento tipo 'Parada', o Número da OS Oficial é obrigatório.")
        else:
            conn = None 
            try:
                equipamento_id = frotas_df[frotas_df['display'] == frota_display]['id'].values[0]
                tipo_operacao_id = operacoes_df[operacoes_df['nome'] == operacao_display]['id'].values[0]
                
                func_id = None
                if funcionario_display:
                    func_id = funcionarios_df[funcionarios_df['display'] == funcionario_display]['id'].values[0]
                    func_id = int(func_id)

                prioridade_clean = prioridade.split(" ")[1]
                val_lat = lat if lat != 0.0 else None
                val_lon = lon if lon != 0.0 else None
                
                data_hora_atual = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
                
                ordem_existente = obter_ordem_aberta(int(equipamento_id))
                conn = get_db_connection()
                cursor = conn.cursor()

                if ordem_existente:
                    id_antigo = ordem_existente[0]
                    desc_antiga = ordem_existente[1]
                    status_antigo = ordem_existente[2]
                    os_antiga = ordem_existente[3]
                    
                    nova_nota = f"\n\n--- [Adicionado em {data_hora_atual.strftime('%d/%m %H:%M')}] ---\nTipo: {operacao_display} | Prio: {prioridade_clean}\nRelato: {descricao}"
                    descricao_final = desc_antiga + nova_nota
                    
                    status_final = status_antigo
                    os_final = os_antiga
                    if "Parada" in tipo_atendimento:
                        status_final = status_inicial
                        if num_os_oficial: os_final = num_os_oficial
                    
                    cursor.execute("""
                        UPDATE ordens_servico SET descricao = ?, horimetro = ?, local_atendimento = ?, prioridade = ?,
                            latitude = ?, longitude = ?, status = ?, numero_os_oficial = ?, funcionario_id = ?, tipo_operacao_id = ?
                        WHERE id = ?
                    """, (descricao_final, horimetro, local_atendimento, prioridade_clean, val_lat, val_lon, status_final, os_final, func_id, int(tipo_operacao_id), id_antigo))
                    
                    conn.commit()
                    registrar_log("EDITAR (FUSÃO)", f"OS #{id_antigo}", f"Adicionada nova ocorrência: {operacao_display}")
                    st.success(f"🔄 Informações unificadas no Ticket #{id_antigo}!")

                else:
                    cursor.execute("""
                        INSERT INTO ordens_servico (data_hora, equipamento_id, local_atendimento, descricao, tipo_operacao_id, status, numero_os_oficial, funcionario_id, horimetro, prioridade, latitude, longitude)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (data_hora_atual, int(equipamento_id), local_atendimento, descricao, int(tipo_operacao_id), status_inicial, num_os_oficial, func_id, horimetro, prioridade_clean, val_lat, val_lon))
                    
                    ticket_id = cursor.lastrowid 
                    conn.commit()
                    
                    exec_log = f" | Exec: {funcionario_display}" if funcionario_display else ""
                    detalhes_log = f"Frota: {frota_display} | Tipo: {operacao_display} | Prio: {prioridade_clean}{exec_log}"
                    registrar_log("CRIAR", f"OS #{ticket_id}", detalhes_log)
                    
                    msg_tipo = "🚨 PARADA" if "Parada" in tipo_atendimento else "⚠️ PENDÊNCIA"
                    st.success(f"{msg_tipo} gerada com sucesso! Ticket #{ticket_id}")
            
            except Exception as e:
                st.error(f"Erro ao salvar OS: {e}")
            finally:
                # CORREÇÃO AQUI: Indentação correta do finally
                if conn:
                    conn.close()

# ==============================================================================
# ABA 2: IMPORTAÇÃO EM LOTE (HISTÓRICO + DATA/HORA + CORREÇÃO DE FROTA)
# ==============================================================================
with tab_importar:
    st.subheader("Importação de Legado / Histórico")
    st.info("Utilize esta aba para carregar planilhas antigas e alimentar o histórico do sistema.")
    
    st.markdown("""
    **Colunas Aceitas (Excel):**
    - `Frota` (Obrigatório) | `Operacao` (Obrigatório) | `Descricao` (Obrigatório) | `Local` (Obrigatório)
    - `Data_Abertura` (Ex: 01/01/2024 14:30) | `Data_Encerramento` (Ex: 02/01/2024 08:00)
    - `Prioridade`, `Horimetro`, `OS_Oficial`
    """)
    
    uploaded_os = st.file_uploader("Carregar Planilha de Histórico", type=['xlsx', 'csv'], key="upload_os_hist")
    
    if uploaded_os:
        try:
            if uploaded_os.name.endswith('.csv'): df_up = pd.read_csv(uploaded_os)
            else: df_up = pd.read_excel(uploaded_os)
            
            st.dataframe(df_up.head(), use_container_width=True)
            
            if st.button("🚀 Processar Histórico"):
                df_up.columns = [c.title().strip() for c in df_up.columns]
                df_up.columns = [c.replace(' ', '_').replace('ç', 'c').replace('ã', 'a') for c in df_up.columns]

                req_cols = {'Frota', 'Operacao', 'Descricao', 'Local'}
                
                if not req_cols.issubset(df_up.columns):
                    st.error(f"Colunas faltando. Necessário: {req_cols}. Encontrado: {list(df_up.columns)}")
                else:
                    conn = get_db_connection()
                    sucessos = 0
                    erros = 0
                    lista_erros = []
                    
                    progress_bar = st.progress(0)
                    total_lines = len(df_up)
                    
                    map_frota = {str(k).strip().upper(): v for k, v in zip(frotas_df['frota'], frotas_df['id'])}
                    map_op = {str(k).strip().upper(): v for k, v in zip(operacoes_df['nome'], operacoes_df['id'])}
                    
                    for index, row in df_up.iterrows():
                        progress_bar.progress((index + 1) / total_lines)
                        try:
                            # --- CORREÇÃO DA FROTA (FIX .0) ---
                            raw_frota = row['Frota']
                            try:
                                if isinstance(raw_frota, float) and raw_frota.is_integer():
                                    raw_frota = int(raw_frota)
                            except: pass
                            
                            f_nome = str(raw_frota).strip().upper()
                            if f_nome.endswith(".0"): f_nome = f_nome[:-2]

                            op_nome_original = str(row['Operacao']).strip()
                            op_nome_key = op_nome_original.upper()
                            
                            if f_nome not in map_frota:
                                lista_erros.append(f"Linha {index+2}: Frota '{f_nome}' não cadastrada.")
                                erros += 1; continue
                            equip_id = map_frota[f_nome]

                            # Auto-cadastro de Operação
                            op_id = map_op.get(op_nome_key)
                            if not op_id:
                                try:
                                    cur_op = conn.cursor()
                                    cur_op.execute("INSERT INTO tipos_operacao (nome, cor) VALUES (?, ?)", (op_nome_original, '#95A5A6'))
                                    new_id = cur_op.lastrowid
                                    map_op[op_nome_key] = new_id
                                    op_id = new_id
                                except:
                                    erros += 1; continue

                            desc = str(row['Descricao'])
                            local = str(row['Local'])
                            prio = str(row.get('Prioridade', 'Média')).title()
                            prio = prio if prio in ["Alta", "Média", "Baixa"] else "Média"
                            try: horim = float(row.get('Horimetro', 0))
                            except: horim = 0.0
                            
                            os_oficial = str(row['OS_Oficial']) if 'OS_Oficial' in df_up.columns and pd.notna(row['OS_Oficial']) else None
                            
                            # Datas
                            data_abertura = None
                            if 'Data_Abertura' in df_up.columns and pd.notna(row['Data_Abertura']):
                                try:
                                    data_abertura = pd.to_datetime(row['Data_Abertura'], dayfirst=True).to_pydatetime()
                                except: pass
                            
                            if not data_abertura:
                                data_abertura = datetime.now(FUSO_HORARIO).replace(tzinfo=None)

                            data_encerramento = None
                            status = "Aberto (Parada)" if os_oficial else "Pendente"
                            
                            if 'Data_Encerramento' in df_up.columns and pd.notna(row['Data_Encerramento']):
                                try:
                                    data_encerramento = pd.to_datetime(row['Data_Encerramento'], dayfirst=True).to_pydatetime()
                                    status = "Concluído"
                                except: pass
                            
                            conn.execute("""
                                INSERT INTO ordens_servico 
                                (data_hora, equipamento_id, local_atendimento, descricao, tipo_operacao_id, status, numero_os_oficial, horimetro, prioridade, data_encerramento)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (data_abertura, equip_id, local, desc, op_id, status, os_oficial, horim, prio, data_encerramento))
                            
                            sucessos += 1
                            
                        except Exception as e:
                            erros += 1
                            lista_erros.append(f"Linha {index+2}: Erro interno ({str(e)})")

                    conn.commit()
                    conn.close()
                    
                    if sucessos > 0:
                        st.success(f"✅ Importação de Histórico: {sucessos} registros inseridos.")
                        registrar_log("IMPORTAÇÃO", "Carga de Legado", f"{sucessos} registros históricos importados")
                    
                    if erros > 0:
                        st.error(f"❌ {erros} falhas.")
                        with st.expander("Ver erros"):
                            for erro in lista_erros: st.write(f"- {erro}")

        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
