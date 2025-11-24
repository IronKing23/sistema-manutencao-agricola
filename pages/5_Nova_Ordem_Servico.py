import streamlit as st
import sqlite3
from database import get_db_connection
import pandas as pd
from datetime import datetime
import sys
import os
import pytz # Importante para corrigir a hora

# Importa o registrador de logs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils_log import registrar_log

st.title("📋 Nova Ordem de Serviço")

# --- Configuração de Fuso Horário ---
# Ajuste para o seu fuso (Ex: 'America/Campo_Grande' ou 'America/Sao_Paulo')
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

try:
    frotas_df = carregar_frotas()
    operacoes_df = carregar_operacoes()
    funcionarios_df = carregar_funcionarios()
    areas_df = carregar_areas()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ==============================================================================
# 1. SELEÇÃO DO TIPO (FORA DO FORM PARA ATUALIZAR NA HORA)
# ==============================================================================
st.subheader("Detalhes do Atendimento")

tipo_atendimento = st.radio(
    "Classificação do Problema:",
    ["Pendência (Máquina TRABALHANDO)", "Parada (Máquina PARADA/QUEBRADA)"],
    horizontal=True,
    index=0 
)

# ==============================================================================
# 2. FORMULÁRIO DE DADOS
# ==============================================================================
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

    # Verifica se já existe ordem aberta para avisar
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
            
            # --- CORREÇÃO DE HORA (FUSO HORÁRIO) ---
            # Pega hora no fuso local e remove info de timezone para salvar "limpo" no SQLite
            data_hora_atual = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
            
            ordem_existente = obter_ordem_aberta(int(equipamento_id))
            conn = get_db_connection()
            cursor = conn.cursor()

            if ordem_existente:
                # FUSÃO (ATUALIZAR EXISTENTE)
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
                # NOVO REGISTRO
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
            if conn: conn.close()
