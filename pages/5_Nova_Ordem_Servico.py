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
            frota_display = st.selectbox("Frota Atendida*", options=frotas_df['display'], index=None, placeholder="Selecione...")
        
        with col2:
            opcoes_local = areas_df['display'].tolist() if not areas_df.empty else []
            local_atendimento = st.selectbox("Local / Talhão*", options=opcoes_local, index=None, placeholder="Selecione...")
            if not opcoes_local: st.caption("⚠️ Cadastre as áreas primeiro.")

        with col3:
            horimetro = st.number_input("Horímetro Atual", min_value=0.0, step=0.1, format="%.1f")

        with st.expander("📍 GPS (Opcional)"):
            c_lat, c_lon = st.columns(2)
            lat = c_lat.number_input("Latitude", value=0.0, format="%.6f")
            lon = c_lon.number_input("Longitude", value=0.0, format="%.6f")

        # Alerta Duplicidade Visual
        if frota_display:
            try:
                eid = frotas_df[frotas_df['display'] == frota_display]['id'].values[0]
                if obter_ordem_aberta(int(eid)):
                    st.info("ℹ️ Já existe um chamado aberto. As informações serão unificadas.")
            except: pass

        col4, col5, col6 = st.columns(3)
        with col4: operacao_display = st.selectbox("Operação*", options=operacoes_df['nome'], index=None)
        with col5: funcionario_display = st.selectbox("Executante", options=funcionarios_df['display'], index=None)
        with col6: prioridade = st.selectbox("Prioridade", options=["🔴 Alta (Urgente)", "🟡 Média (Normal)", "🔵 Baixa"], index=1)

        descricao = st.text_area("Descrição*", placeholder="Detalhes...")
        
        num_os_oficial = None
        status_inicial = "Pendente"

        if "Parada" in tipo_atendimento:
            st.markdown("---"); st.error("🔴 **Dados Obrigatórios para Parada**")
            c_os, c_st = st.columns(2)
            with c_os: 
                input_os = st.text_input("Número da OS Oficial")
                if input_os: num_os_oficial = input_os
            with c_st: 
                status_inicial = st.selectbox("Status Inicial", ["Aberto (Parada)", "Em Andamento", "Aguardando Peças"])

        st.markdown("---")
        submitted = st.form_submit_button("✅ Processar Solicitação")

    if submitted:
        if not frota_display or not operacao_display or not descricao or not local_atendimento:
            st.error("Preencha os campos obrigatórios.")
        elif "Parada" in tipo_atendimento and not num_os_oficial:
            st.error("Para Parada, o Nº da OS é obrigatório.")
        else:
            conn = None 
            try:
                equipamento_id = frotas_df[frotas_df['display'] == frota_display]['id'].values[0]
                tipo_operacao_id = operacoes_df[operacoes_df['nome'] == operacao_display]['id'].values[0]
                
                func_id = None
                if funcionario_display:
                    func_id = funcionarios_df[funcionarios_df['display'] == funcionario_display]['id'].values[0]

                prioridade_clean = prioridade.split(" ")[1]
                val_lat = lat if lat != 0.0 else None; val_lon = lon if lon != 0.0 else None
                data_hora_atual = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
                
                ordem_existente = obter_ordem_aberta(int(equipamento_id))
                conn = get_db_connection()
                cursor = conn.cursor()

                if ordem_existente:
                    id_antigo, desc_antiga, status_antigo, os_antiga = ordem_existente
                    
                    nova_nota = f"\n\n--- [Add em {data_hora_atual.strftime('%d/%m %H:%M')}] ---\nTipo: {operacao_display} | Prio: {prioridade_clean}\nDesc: {descricao}"
                    descricao_final = desc_antiga + nova_nota
                    
                    status_final = status_antigo
                    os_final = os_antiga
                    if "Parada" in tipo_atendimento:
                        status_final = status_inicial
                        if num_os_oficial: os_final = num_os_oficial
                    
                    cursor.execute("""
                        UPDATE ordens_servico SET descricao=?, horimetro=?, local_atendimento=?, prioridade=?,
                        latitude=?, longitude=?, status=?, numero_os_oficial=?, funcionario_id=?, tipo_operacao_id=?
                        WHERE id=?
                    """, (descricao_final, horimetro, local_atendimento, prioridade_clean, val_lat, val_lon, status_final, os_final, func_id, int(tipo_operacao_id), id_antigo))
                    
                    conn.commit()
                    registrar_log("EDITAR (FUSÃO)", f"OS #{id_antigo}", "Atualização manual")
                    st.success(f"🔄 Unificado no Ticket #{id_antigo}!")
                else:
                    cursor.execute("""
                        INSERT INTO ordens_servico (data_hora, equipamento_id, local_atendimento, descricao, tipo_operacao_id, status, numero_os_oficial, funcionario_id, horimetro, prioridade, latitude, longitude)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (data_hora_atual, int(equipamento_id), local_atendimento, descricao, int(tipo_operacao_id), status_inicial, num_os_oficial, func_id, horimetro, prioridade_clean, val_lat, val_lon))
                    
                    tid = cursor.lastrowid; conn.commit()
                    registrar_log("CRIAR", f"OS #{tid}", f"Frota: {frota_display}")
                    st.success(f"✅ Ticket #{tid} criado!")
                
            except Exception as e: st.error(f"Erro: {e}")
            finally: if conn: conn.close()

# ==============================================================================
# ABA 2: IMPORTAÇÃO EM LOTE (INTELIGENTE: PROMOÇÃO DE STATUS)
# ==============================================================================
with tab_importar:
    st.subheader("Importação de Legado / Histórico")
    st.info("Utilize esta aba para carregar planilhas antigas e alimentar o histórico do sistema.")
    
    st.markdown("""
    **Colunas Aceitas (Excel):**
    - `Frota`, `Operacao`, `Descricao`, `Local` (Obrigatórios)
    - `Data_Abertura` (Opcional)
    - `Data_Encerramento` (Opcional - **Se preenchido, encerra a ordem**)
    - `OS_Oficial` (Opcional - **Se preenchido, promove para Parada**)
    - `Prioridade`, `Horimetro`
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
                    atualizados = 0
                    erros = 0
                    lista_erros = []
                    
                    progress_bar = st.progress(0)
                    total_lines = len(df_up)
                    
                    map_frota = {str(k).strip().upper(): v for k, v in zip(frotas_df['frota'], frotas_df['id'])}
                    map_op = {str(k).strip().upper(): v for k, v in zip(operacoes_df['nome'], operacoes_df['id'])}
                    
                    for index, row in df_up.iterrows():
                        progress_bar.progress((index + 1) / total_lines)
                        try:
                            # --- TRATAMENTO DE FROTA ---
                            raw_frota = row['Frota']
                            try:
                                if isinstance(raw_frota, float) and raw_frota.is_integer(): raw_frota = int(raw_frota)
                            except: pass
                            f_nome = str(raw_frota).strip().upper()
                            if f_nome.endswith(".0"): f_nome = f_nome[:-2]

                            if f_nome not in map_frota:
                                lista_erros.append(f"Linha {index+2}: Frota '{f_nome}' não cadastrada.")
                                erros += 1; continue
                            equip_id = map_frota[f_nome]

                            # --- OPERAÇÃO ---
                            op_nome_key = str(row['Operacao']).strip().upper()
                            op_id = map_op.get(op_nome_key)
                            if not op_id:
                                try:
                                    cur_op = conn.cursor()
                                    cur_op.execute("INSERT INTO tipos_operacao (nome, cor) VALUES (?, ?)", (str(row['Operacao']).strip(), '#95A5A6'))
                                    new_id = cur_op.lastrowid
                                    map_op[op_nome_key] = new_id
                                    op_id = new_id
                                except: erros += 1; continue

                            # --- DADOS ---
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
                                try: data_abertura = pd.to_datetime(row['Data_Abertura'], dayfirst=True).to_pydatetime()
                                except: pass
                            if not data_abertura: data_abertura = datetime.now(FUSO_HORARIO).replace(tzinfo=None)

                            data_encerramento = None
                            if 'Data_Encerramento' in df_up.columns and pd.notna(row['Data_Encerramento']):
                                try: data_encerramento = pd.to_datetime(row['Data_Encerramento'], dayfirst=True).to_pydatetime()
                                except: pass

                            # --- LÓGICA INTELIGENTE ---
                            cursor = conn.cursor()
                            cursor.execute("""
                                SELECT id, descricao, status, numero_os_oficial FROM ordens_servico 
                                WHERE equipamento_id = ? AND status != 'Concluído'
                                ORDER BY id DESC LIMIT 1
                            """, (equip_id,))
                            ordem_existente = cursor.fetchone()
                            
                            if ordem_existente:
                                # ATUALIZAR
                                id_antigo, desc_antiga, status_antigo, os_antiga = ordem_existente
                                
                                # Prioridade de Status: Concluído > Parada > Pendente
                                novo_status = status_antigo
                                novo_os = os_antiga
                                
                                # 1. Se tiver data fim, Conclui
                                if data_encerramento:
                                    novo_status = "Concluído"
                                    # Se veio OS nova, atualiza ela também
                                    if os_oficial: novo_os = os_oficial
                                    
                                    nova_desc = desc_antiga + f"\n[Fechamento Excel]: {desc}"
                                    conn.execute("""
                                        UPDATE ordens_servico 
                                        SET descricao=?, horimetro=?, status=?, data_encerramento=?, tipo_operacao_id=?, numero_os_oficial=?
                                        WHERE id=?
                                    """, (nova_desc, horim, novo_status, data_encerramento, op_id, novo_os, id_antigo))
                                    
                                else:
                                    # 2. Se não fecha, verifica PROMOÇÃO
                                    if os_oficial:
                                        novo_status = "Aberto (Parada)"
                                        novo_os = os_oficial
                                    
                                    nova_desc = desc_antiga + f"\n[Atualização Excel]: {desc}"
                                    conn.execute("""
                                        UPDATE ordens_servico 
                                        SET descricao=?, horimetro=?, status=?, numero_os_oficial=?
                                        WHERE id=?
                                    """, (nova_desc, horim, novo_status, novo_os, id_antigo))
                                    
                                atualizados += 1
                                    
                            else:
                                # CRIAR NOVA
                                status = "Concluído" if data_encerramento else ("Aberto (Parada)" if os_oficial else "Pendente")
                                conn.execute("""
                                    INSERT INTO ordens_servico 
                                    (data_hora, equipamento_id, local_atendimento, descricao, tipo_operacao_id, status, numero_os_oficial, horimetro, prioridade, data_encerramento)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (data_abertura, equip_id, local, desc, op_id, status, os_oficial, horim, prio, data_encerramento))
                                criados += 1
                            
                        except Exception as e:
                            erros += 1
                            lista_erros.append(f"Linha {index+2}: {str(e)}")

                    conn.commit()
                    conn.close()
                    
                    if sucessos > 0 or atualizados > 0:
                        st.success(f"✅ Finalizado! {criados} novas, {atualizados} atualizadas.")
                        registrar_log("IMPORTAÇÃO", "Lote", f"{criados} novos, {atualizados} updates")
                    
                    if erros > 0:
                        st.error(f"❌ {erros} falhas.")
                        with st.expander("Ver erros"):
                            for erro in lista_erros: st.write(f"- {erro}")

        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
