import streamlit as st
import sqlite3
from database import get_db_connection
import pandas as pd
from datetime import datetime
import sys
import os
import pytz 
import io

# Importa o registrador de logs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils_log import registrar_log

st.title("📋 Nova Ordem de Serviço")

# Fuso Horário
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

# --- Funções de Carregamento (COM CACHE) ---

@st.cache_data(ttl=300, show_spinner="Carregando frotas...")
def carregar_frotas():
    conn = get_db_connection()
    # ATUALIZADO: Agora busca também o gestao_responsavel
    frotas = pd.read_sql_query("SELECT id, frota, modelo, gestao_responsavel FROM equipamentos ORDER BY frota", conn)
    conn.close()
    frotas['display'] = frotas['frota'] + " - " + frotas['modelo']
    return frotas

@st.cache_data(ttl=300)
def carregar_operacoes():
    conn = get_db_connection()
    operacoes = pd.read_sql_query("SELECT id, nome FROM tipos_operacao ORDER BY nome", conn)
    conn.close()
    return operacoes

@st.cache_data(ttl=300)
def carregar_funcionarios():
    conn = get_db_connection()
    funcs = pd.read_sql_query("SELECT id, nome, matricula, setor FROM funcionarios ORDER BY nome", conn)
    conn.close()
    if not funcs.empty:
        funcs['display'] = funcs['nome'] + " (" + funcs['matricula'].astype(str) + ")"
    else:
        funcs['display'] = []
    return funcs

@st.cache_data(ttl=300)
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

# Função para gerar o template Excel (CORRIGIDA: Removida dependência explícita de xlsxwriter)
def gerar_template_excel(frotas, operacoes, areas):
    output = io.BytesIO()
    
    # Tenta usar a engine padrão disponível (openpyxl é o padrão moderno)
    # Se falhar, tentamos CSV como fallback
    try:
        with pd.ExcelWriter(output) as writer: # Removido engine='xlsxwriter'
            # 1. Aba Principal (Template Vazio)
            df_template = pd.DataFrame(columns=[
                'Frota', 'Operacao', 'Descricao', 'Local', 
                'Prioridade', 'Horimetro', 'OS_Oficial', 
                'Data_Abertura', 'Data_Encerramento'
            ])
            
            # Adiciona exemplos para ajudar
            df_template.loc[0] = [
                'Ex: 64080', 'Ex: Elétrica', 'Descrição do problema...', 'Ex: TALHÃO 10', 
                'Alta/Média/Baixa', '1234.5', '12345', 
                datetime.now().strftime('%d/%m/%Y'), ''
            ]
            
            df_template.to_excel(writer, sheet_name='Preencher_Aqui', index=False)
            
            # 2. Abas de Referência (Dados do Sistema)
            # Frotas
            if not frotas.empty:
                frotas[['frota', 'modelo']].to_excel(writer, sheet_name='Ref_Frotas', index=False)
                
            # Operações
            if not operacoes.empty:
                operacoes[['nome']].to_excel(writer, sheet_name='Ref_Operacoes', index=False)
                
            # Locais
            if not areas.empty:
                areas[['display']].to_excel(writer, sheet_name='Ref_Locais', index=False)
                
    except Exception as e:
        # Fallback de erro silencioso se nenhuma engine Excel estiver instalada
        st.error(f"Erro ao gerar Excel (Falta biblioteca openpyxl ou xlsxwriter): {e}")
        return None
            
    output.seek(0)
    return output

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
        # --- LINHA 1: FROTA E GESTOR ---
        col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 1])
        
        with col_f1:
            frota_display = st.selectbox("Frota Atendida*", options=frotas_df['display'], index=None, placeholder="Selecione...")
        
        gestor_atual = ""
        if frota_display:
            try:
                row_frota = frotas_df[frotas_df['display'] == frota_display].iloc[0]
                val_gestor = row_frota['gestao_responsavel']
                if val_gestor: gestor_atual = val_gestor
            except: pass
            
        with col_f2:
            st.text_input("Gestor Responsável (Automático)", value=gestor_atual, disabled=True)

        with col_f3:
            horimetro = st.number_input("Horímetro Atual", min_value=0.0, step=0.1, format="%.1f")

        # Alerta Duplicidade
        if frota_display:
            try:
                eid = frotas_df[frotas_df['display'] == frota_display]['id'].values[0]
                if obter_ordem_aberta(int(eid)):
                    st.info("ℹ️ Já existe um chamado aberto. As informações serão unificadas.")
            except: pass

        # --- LINHA 2: LOCAL E SOLICITANTE ---
        col_loc, col_solic = st.columns(2)
        with col_loc:
            opcoes_local = areas_df['display'].tolist() if not areas_df.empty else []
            local_atendimento = st.selectbox("Local / Talhão*", options=opcoes_local, index=None, placeholder="Selecione...")
        
        with col_solic:
            solicitante_display = st.selectbox(
                "Solicitante (Quem pediu)*", 
                options=funcionarios_df['display'], 
                index=None, 
                placeholder="Pesquise por nome ou matrícula..."
            )

        with st.expander("📍 GPS (Opcional)"):
            c_lat, c_lon = st.columns(2)
            lat = c_lat.number_input("Latitude", value=0.0, format="%.6f")
            lon = c_lon.number_input("Longitude", value=0.0, format="%.6f")

        # --- LINHA 3: OPERAÇÃO E EXECUTANTE ---
        col4, col5, col6 = st.columns(3)
        with col4: operacao_display = st.selectbox("Operação (Defeito)*", options=operacoes_df['nome'], index=None)
        
        with col5: 
            # OPCIONAL NOVAMENTE (Sem o asterisco e sem trava)
            funcionario_display = st.selectbox("Executante (Mecânico)", options=funcionarios_df['display'], index=None, placeholder="Definir depois...")
            
        with col6: prioridade = st.selectbox("Prioridade", options=["🔴 Alta (Urgente)", "🟡 Média (Normal)", "🔵 Baixa"], index=1)

        # --- DADOS KPI ---
        st.markdown("---")
        st.markdown("###### 🔧 Dados para Indicadores (KPI)")
        c_class1, c_class2 = st.columns(2)

        with c_class1:
            classificacao = st.radio(
                "Tipo de Intervenção", 
                options=["Corretiva (Quebra)", "Preventiva (Planejada)", "Preditiva / Melhoria"],
                horizontal=True
            )

        with c_class2:
            parada_default = True if "Parada" in tipo_atendimento else False
            maquina_parada = st.checkbox("A máquina ficou PARADA?", value=parada_default)
        
        st.markdown("---")

        descricao = st.text_area("Descrição*", placeholder="Detalhes do problema...")
        
        num_os_oficial = None
        status_inicial = "Pendente"

        if "Parada" in tipo_atendimento:
            st.error("🔴 **Dados Obrigatórios para Parada**")
            c_os, c_st = st.columns(2)
            with c_os: 
                input_os = st.text_input("Número da OS Oficial")
                if input_os: num_os_oficial = input_os
            with c_st: 
                status_inicial = st.selectbox("Status Inicial", ["Aberto (Parada)", "Em Andamento", "Aguardando Peças"])

        st.markdown("---")
        submitted = st.form_submit_button("✅ Processar Solicitação")

    if submitted:
        # --- VALIDAÇÃO ATUALIZADA: Mecânico NÃO é mais obrigatório ---
        if not frota_display or not operacao_display or not descricao or not local_atendimento or not solicitante_display:
            st.error("Preencha os campos obrigatórios (Frota, Local, Solicitante, Operação, Descrição).")
        elif "Parada" in tipo_atendimento and not num_os_oficial:
            st.error("Para Parada, o Nº da OS é obrigatório.")
        else:
            conn = None 
            try:
                equipamento_id = frotas_df[frotas_df['display'] == frota_display]['id'].values[0]
                tipo_operacao_id = operacoes_df[operacoes_df['nome'] == operacao_display]['id'].values[0]
                
                # IDs
                # Executante pode ser None se não selecionado
                func_id = None
                if funcionario_display:
                    func_id = funcionarios_df[funcionarios_df['display'] == funcionario_display]['id'].values[0]
                
                # Solicitante é obrigatório
                solic_id = funcionarios_df[funcionarios_df['display'] == solicitante_display]['id'].values[0]

                prioridade_clean = prioridade.split(" ")[1]
                val_lat = lat if lat != 0.0 else None; val_lon = lon if lon != 0.0 else None
                data_hora_atual = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
                
                # KPI
                tipo_classificacao = classificacao.split(" ")[0] 
                flag_parada = 1 if maquina_parada else 0

                ordem_existente = obter_ordem_aberta(int(equipamento_id))
                conn = get_db_connection()
                cursor = conn.cursor()

                if ordem_existente:
                    # UPDATE
                    id_antigo, desc_antiga, status_antigo, os_antiga = ordem_existente
                    
                    nova_nota = f"\n\n--- [Add em {data_hora_atual.strftime('%d/%m %H:%M')}] ---\nSolicitante: {solicitante_display}\nMecânico: {funcionario_display or 'Não definido'}\nTipo: {operacao_display} | Classe: {tipo_classificacao}\nDesc: {descricao}"
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
                    # INSERT
                    cursor.execute("""
                        INSERT INTO ordens_servico (
                            data_hora, equipamento_id, local_atendimento, descricao, 
                            tipo_operacao_id, status, numero_os_oficial, funcionario_id, 
                            horimetro, prioridade, latitude, longitude,
                            classificacao, maquina_parada, solicitante_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data_hora_atual, int(equipamento_id), local_atendimento, descricao, 
                        int(tipo_operacao_id), status_inicial, num_os_oficial, func_id, 
                        horimetro, prioridade_clean, val_lat, val_lon,
                        tipo_classificacao, flag_parada, int(solic_id)
                    ))
                    
                    tid = cursor.lastrowid; conn.commit()
                    registrar_log("CRIAR", f"OS #{tid}", f"Frota: {frota_display} | Mec: {funcionario_display}")
                    st.success(f"✅ Ticket #{tid} criado com sucesso!")
                
            except Exception as e:
                st.error(f"Erro: {e}")
            finally:
                if conn:
                    conn.close()

# ==============================================================================
# ABA 2: IMPORTAÇÃO EM LOTE (MANTIDA)
# ==============================================================================
with tab_importar:
    st.subheader("Importação Inteligente")
    
    # --- NOVO: Botão de Download do Template ---
    c_info, c_btn = st.columns([2, 1])
    with c_info:
        st.info("Baixe a planilha modelo abaixo, preencha os dados e faça o upload.")
        st.markdown("""
        **Colunas Obrigatórias:**
        `Frota`, `Operacao`, `Descricao`, `Local`.
        """)
        
    with c_btn:
        excel_bytes = gerar_template_excel(frotas_df, operacoes_df, areas_df)
        if excel_bytes:
            st.download_button(
                label="📥 Baixar Modelo (Excel)",
                data=excel_bytes,
                file_name="modelo_importacao_os.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
    
    st.divider()
    
    uploaded_os = st.file_uploader("Carregar Planilha Preenchida", type=['xlsx', 'csv'], key="upload_os_hist")
    
    if uploaded_os:
        try:
            if uploaded_os.name.endswith('.csv'): df_up = pd.read_csv(uploaded_os)
            else: df_up = pd.read_excel(uploaded_os)
            
            st.dataframe(df_up.head(), use_container_width=True)
            
            if st.button("🚀 Processar Importação"):
                df_up.columns = [c.title().strip() for c in df_up.columns]
                df_up.columns = [c.replace(' ', '_').replace('ç', 'c').replace('ã', 'a') for c in df_up.columns]

                req_cols = {'Frota', 'Operacao', 'Descricao', 'Local'}
                
                if not req_cols.issubset(df_up.columns):
                    st.error(f"Colunas faltando. Necessário: {req_cols}. Encontrado: {list(df_up.columns)}")
                else:
                    conn = get_db_connection()
                    criados = 0
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
                            # --- TRATAMENTO FROTA ---
                            raw_frota = row['Frota']
                            try:
                                if isinstance(raw_frota, float) and raw_frota.is_integer(): raw_frota = int(raw_frota)
                            except: pass
                            f_nome = str(raw_frota).strip().upper()
                            if f_nome.endswith(".0"): f_nome = f_nome[:-2]

                            if f_nome not in map_frota:
                                lista_erros.append(f"Linha {index+2}: Frota '{f_nome}' não encontrada.")
                                erros += 1; continue
                            equip_id = map_frota[f_nome]

                            # --- TRATAMENTO OPERAÇÃO ---
                            op_nome = str(row['Operacao']).strip()
                            op_key = op_nome.upper()
                            op_id = map_op.get(op_key)
                            if not op_id:
                                # Auto-cadastro simples
                                try:
                                    cur = conn.cursor()
                                    cur.execute("INSERT INTO tipos_operacao (nome) VALUES (?)", (op_nome,))
                                    op_id = cur.lastrowid
                                    map_op[op_key] = op_id
                                except: erros += 1; continue

                            # --- DADOS ---
                            desc = str(row['Descricao'])
                            local = str(row['Local'])
                            prio = str(row.get('Prioridade', 'Média')).title()
                            if prio not in ["Alta", "Média", "Baixa"]: prio = "Média"
                            try: horim = float(row.get('Horimetro', 0))
                            except: horim = 0.0
                            os_oficial = str(row['OS_Oficial']) if 'OS_Oficial' in df_up.columns and pd.notna(row['OS_Oficial']) else None
                            
                            data_ab = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
                            if 'Data_Abertura' in df_up.columns and pd.notna(row['Data_Abertura']):
                                try: data_ab = pd.to_datetime(row['Data_Abertura'], dayfirst=True).to_pydatetime()
                                except: pass
                            
                            data_enc = None
                            if 'Data_Encerramento' in df_up.columns and pd.notna(row['Data_Encerramento']):
                                try: data_enc = pd.to_datetime(row['Data_Encerramento'], dayfirst=True).to_pydatetime()
                                except: pass

                            # --- UPDATE / INSERT ---
                            cursor = conn.cursor()
                            cursor.execute("SELECT id, descricao FROM ordens_servico WHERE equipamento_id=? AND status!='Concluído'", (equip_id,))
                            existente = cursor.fetchone()
                            
                            if existente:
                                id_ant, desc_ant = existente
                                if data_enc:
                                    new_desc = desc_ant + f"\n[Fechamento Lote]: {desc}"
                                    conn.execute("UPDATE ordens_servico SET descricao=?, status='Concluído', data_encerramento=?, horimetro=? WHERE id=?", (new_desc, data_enc, horim, id_ant))
                                    atualizados += 1
                                else:
                                    new_desc = desc_ant + f"\n[Atualização Lote]: {desc}"
                                    conn.execute("UPDATE ordens_servico SET descricao=?, horimetro=? WHERE id=?", (new_desc, horim, id_ant))
                                    atualizados += 1
                            else:
                                st_inicial = "Concluído" if data_enc else ("Aberto (Parada)" if os_oficial else "Pendente")
                                # Importação: Assume Corretiva, Parada e Sem Solicitante
                                conn.execute("""
                                    INSERT INTO ordens_servico (data_hora, equipamento_id, local_atendimento, descricao, tipo_operacao_id, status, numero_os_oficial, horimetro, prioridade, data_encerramento, classificacao, maquina_parada, solicitante_id)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Corretiva', 1, NULL)
                                """, (data_ab, equip_id, local, desc, op_id, st_inicial, os_oficial, horim, prio, data_enc))
                                criados += 1

                        except Exception as e:
                            erros += 1
                            lista_erros.append(f"Linha {index+2}: {str(e)}")

                    conn.commit()
                    conn.close()
                    
                    if criados > 0 or atualizados > 0:
                        st.success(f"✅ Processado: {criados} novas, {atualizados} atualizadas.")
                        registrar_log("IMPORTAÇÃO", "Lote", f"Novas: {criados}, Atualizadas: {atualizados}")
                    
                    if erros > 0:
                        st.error(f"❌ {erros} linhas falharam.")
                        with st.expander("Ver Detalhes dos Erros"):
                            for erro in lista_erros: st.write(f"- {erro}")
                    
        except Exception as e: st.error(f"Erro arquivo: {e}")
