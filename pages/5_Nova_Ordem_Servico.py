import streamlit as st
import sqlite3
from database import get_db_connection
import pandas as pd
from datetime import datetime
import sys
import os

# Importa o registrador de logs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils_log import registrar_log

st.title("📋 Nova Ordem de Serviço")

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
    # Busca matricula e cria formato de pesquisa inteligente
    funcs = pd.read_sql_query("SELECT id, nome, matricula, setor FROM funcionarios ORDER BY nome", conn)
    conn.close()
    # Cria coluna visual: "João Silva (1050)"
    if not funcs.empty:
        funcs['display'] = funcs['nome'] + " (" + funcs['matricula'].astype(str) + ")"
    else:
        funcs['display'] = []
    return funcs

def carregar_areas():
    conn = get_db_connection()
    try:
        areas = pd.read_sql_query("SELECT codigo, nome FROM areas ORDER BY codigo", conn)
        # Cria lista formatada "TL-01 - Talhão Norte"
        if not areas.empty:
            areas['display'] = areas['codigo'] + " - " + areas['nome']
        else:
            areas['display'] = []
        return areas
    except:
        return pd.DataFrame(columns=['display'])
    finally:
        conn.close()

# NOVA FUNÇÃO: Buscar dados da ordem aberta (se houver)
def obter_ordem_aberta(equipamento_id):
    """Retorna os dados da OS aberta para esta frota, se existir."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Pega a mais recente que não esteja concluída
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

# ==============================================================================
# 1. SELEÇÃO DO TIPO
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
        frota_display = st.selectbox(
            "Frota Atendida*", 
            options=frotas_df['display'], 
            index=None,
            placeholder="Selecione a frota..."
        )
    
    with col2:
        opcoes_local = areas_df['display'].tolist() if not areas_df.empty else []
        local_atendimento = st.selectbox(
            "Local / Talhão*", 
            options=opcoes_local,
            index=None,
            placeholder="Selecione a área..." if opcoes_local else "Nenhuma área cadastrada!"
        )
        if not opcoes_local:
            st.caption("⚠️ Cadastre as áreas no menu 'Cadastros > Áreas'.")

    with col3:
        horimetro = st.number_input("Horímetro Atual (Horas)", min_value=0.0, step=0.1, format="%.1f")

    # --- LOCALIZAÇÃO GPS ---
    with st.expander("📍 Localização GPS (Opcional - Para Mapa)"):
        c_lat, c_lon = st.columns(2)
        lat = c_lat.number_input("Latitude", value=0.0, format="%.6f", help="Ex: -23.5505")
        lon = c_lon.number_input("Longitude", value=0.0, format="%.6f", help="Ex: -46.6333")

    # Alerta Visual de Duplicidade/Fusão (Informativo)
    msg_fusao = ""
    if frota_display:
        equip_id_check = frotas_df[frotas_df['display'] == frota_display]['id'].values[0]
        ordem_existente = obter_ordem_aberta(int(equip_id_check))
        if ordem_existente:
            id_existente = ordem_existente[0]
            st.info(f"ℹ️ NOTA: Já existe o Ticket #{id_existente} aberto para esta frota. As novas informações serão adicionadas a ele automaticamente.")

    col4, col5, col6 = st.columns(3)
    
    with col4:
        operacao_display = st.selectbox("Sistema Afetado / Operação*", options=operacoes_df['nome'], index=None)
    
    with col5:
        funcionario_display = st.selectbox(
            "Executante / Responsável", 
            options=funcionarios_df['display'], 
            index=None,
            placeholder="Busque por Nome ou Matrícula..."
        )
        
    with col6:
        prioridade = st.selectbox(
            "Prioridade / Urgência", 
            options=["🔴 Alta (Urgente)", "🟡 Média (Normal)", "🔵 Baixa (Pode esperar)"],
            index=1
        )

    descricao = st.text_area("Descrição Detalhada do Problema*", placeholder="Descreva o problema...")
    
    # --- CAMPOS CONDICIONAIS ---
    num_os_oficial = None
    status_inicial = "Pendente"

    if "Parada" in tipo_atendimento:
        st.markdown("---")
        st.error("🔴 **Dados de Máquina Parada (Obrigatório)**")
        col_os, col_status = st.columns(2)
        with col_os:
            input_os = st.text_input("Número da OS Oficial")
            if input_os: num_os_oficial = input_os
        with col_status:
            status_inicial = st.selectbox(
                "Status Inicial",
                options=["Aberto (Parada)", "Em Andamento", "Aguardando Peças"],
                index=0 
            )

    st.markdown("---")
    submitted = st.form_submit_button("✅ Processar Solicitação")

# --- Lógica de Salvar / Fundir ---
if submitted:
    # Validação Obrigatória
    if not frota_display or not operacao_display or not descricao or not local_atendimento:
        st.error("Preencha os campos obrigatórios: Frota, Local, Operação e Descrição.")
    
    elif "Parada" in tipo_atendimento and not num_os_oficial:
        # Se for fusão, talvez não precise de OS nova, mas vamos manter a regra de preenchimento se selecionou Parada
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
            data_hora_atual = datetime.now()
            
            # --- VERIFICAÇÃO INTELIGENTE DE FUSÃO ---
            ordem_existente = obter_ordem_aberta(int(equipamento_id))
            
            conn = get_db_connection()
            cursor = conn.cursor()

            if ordem_existente:
                # --- CENÁRIO DE ATUALIZAÇÃO (FUSÃO) ---
                id_antigo = ordem_existente[0]
                desc_antiga = ordem_existente[1]
                status_antigo = ordem_existente[2]
                os_antiga = ordem_existente[3]
                
                # 1. Monta a nova descrição (Histórico)
                nova_nota = f"\n\n--- [Adicionado em {data_hora_atual.strftime('%d/%m %H:%M')}] ---\n"
                nova_nota += f"Tipo: {operacao_display} | Prio: {prioridade_clean}\n"
                nova_nota += f"Relato: {descricao}"
                descricao_final = desc_antiga + nova_nota
                
                # 2. Decide Status e OS (Prioridade Maior Vence)
                status_final = status_antigo
                os_final = os_antiga
                
                if "Parada" in tipo_atendimento:
                    status_final = status_inicial # Atualiza para o status de parada novo
                    if num_os_oficial: 
                        os_final = num_os_oficial # Atualiza/Insere o número da OS
                
                # 3. Executa Update (ATUALIZADO: Incluindo tipo_operacao_id)
                cursor.execute("""
                    UPDATE ordens_servico 
                    SET descricao = ?, 
                        horimetro = ?, 
                        local_atendimento = ?, 
                        prioridade = ?,
                        latitude = ?, longitude = ?,
                        status = ?, numero_os_oficial = ?,
                        funcionario_id = ?, -- Atualiza para o último executante citado
                        tipo_operacao_id = ? -- Atualiza para a operação mais recente
                    WHERE id = ?
                """, (descricao_final, horimetro, local_atendimento, prioridade_clean, val_lat, val_lon, status_final, os_final, func_id, int(tipo_operacao_id), id_antigo))
                
                conn.commit()
                
                # Log de Auditoria (Edição Automática)
                registrar_log("EDITAR (FUSÃO)", f"OS #{id_antigo}", f"Adicionada nova ocorrência: {operacao_display}")
                
                st.success(f"🔄 Informações adicionadas ao Ticket existente #{id_antigo} com sucesso!")
                st.info("O sistema detectou um chamado aberto e unificou as informações.")

            else:
                # --- CENÁRIO DE CRIAÇÃO (NOVO) ---
                cursor.execute(
                    """
                    INSERT INTO ordens_servico 
                    (data_hora, equipamento_id, local_atendimento, descricao, tipo_operacao_id, status, numero_os_oficial, funcionario_id, horimetro, prioridade, latitude, longitude)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (data_hora_atual, int(equipamento_id), local_atendimento, descricao, int(tipo_operacao_id), status_inicial, num_os_oficial, func_id, horimetro, prioridade_clean, val_lat, val_lon)
                )
                ticket_id = cursor.lastrowid 
                conn.commit()
                
                # Log de Auditoria (Criação)
                detalhes_log = f"Frota: {frota_display} | Tipo: {operacao_display} | Prio: {prioridade_clean}"
                registrar_log("CRIAR", f"OS #{ticket_id}", detalhes_log)
                
                msg_tipo = "🚨 PARADA" if "Parada" in tipo_atendimento else "⚠️ PENDÊNCIA"
                st.success(f"{msg_tipo} gerada com sucesso! Ticket #{ticket_id}")
            
        except Exception as e:
            st.error(f"Erro ao processar OS: {e}")
        finally:
            if conn: conn.close()