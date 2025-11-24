import streamlit as st
import pandas as pd
from database import get_db_connection

# --- Função para buscar resumo rápido (MANTIDA) ---
def carregar_resumo_rapido():
    conn = get_db_connection()
    try:
        query = """
        SELECT 
            os.id as Ticket,
            e.frota as Frota,
            os.status as Status,
            os.prioridade as Prioridade,
            op.nome as Operacao,
            op.cor as Cor_Hex
        FROM ordens_servico os
        JOIN equipamentos e ON os.equipamento_id = e.id
        LEFT JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
        WHERE os.status != 'Concluído'
        ORDER BY 
            CASE os.prioridade
                WHEN 'Alta' THEN 1
                WHEN 'Média' THEN 2
                WHEN 'Baixa' THEN 3
                ELSE 4
            END ASC,
            os.data_hora DESC
        LIMIT 10
        """
        return pd.read_sql_query(query, conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()

# --- Função Contar Recados (MANTIDA) ---
def contar_recados():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM recados")
        return cursor.fetchone()[0]
    except:
        return 0
    finally:
        conn.close()

# --- Lógica de Cores (MANTIDA) ---
def hex_to_rgba(hex_code, opacity=0.25):
    if not hex_code or not isinstance(hex_code, str) or not hex_code.startswith('#'): return None 
    hex_code = hex_code.lstrip('#')
    try:
        rgb = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
        return f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
    except: return None

def colorir_linhas(row):
    operacao = str(row['Operacao']).lower() if pd.notna(row['Operacao']) else ""
    cor_db = row.get('Cor_Hex')
    cor_final = hex_to_rgba(cor_db, opacity=0.25)
    if not cor_final:
        if 'elet' in operacao or 'elét' in operacao: cor_final = 'rgba(33, 150, 243, 0.25)'
        elif 'mecan' in operacao or 'mecân' in operacao or 'hidraul' in operacao: cor_final = 'rgba(158, 158, 158, 0.25)'
        elif 'borrach' in operacao or 'pneu' in operacao: cor_final = 'rgba(255, 152, 0, 0.25)'   
        elif 'terceir' in operacao or 'extern' in operacao: cor_final = 'rgba(156, 39, 176, 0.25)'  
        elif 'solda' in operacao or 'funil' in operacao: cor_final = 'rgba(255, 235, 59, 0.25)'  
        else: cor_final = 'transparent'
    return [f'background-color: {cor_final}' for _ in row]

# --- ESTILOS CSS PARA ANIMAÇÃO (NOVO!) ---
st.markdown("""
<style>
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(255, 82, 82, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(255, 82, 82, 0); }
    100% { box-shadow: 0 0 0 0 rgba(255, 82, 82, 0); }
}
.notification-badge {
    background-color: #FF5252;
    color: white;
    padding: 4px 12px;
    border-radius: 15px;
    font-weight: bold;
    font-size: 0.9em;
    animation: pulse 2s infinite;
    vertical-align: middle;
    margin-left: 10px;
}
.clean-badge {
    background-color: #4CAF50;
    color: white;
    padding: 4px 12px;
    border-radius: 15px;
    font-size: 0.8em;
    font-weight: bold;
    vertical-align: middle;
    margin-left: 10px;
}
</style>
""", unsafe_allow_html=True)

# --- LAYOUT DO TOPO ---
col_texto, col_painel = st.columns([1.8, 1.2])

# >> LADO ESQUERDO <<
with col_texto:
    st.title("Bem-vindo ao Sistema")
    
    nome_usuario = st.session_state.get('user_nome', 'Colaborador')
    st.subheader(f"Olá, {nome_usuario}! 👋")
    st.markdown("O que você deseja fazer agora?")
    
    st.markdown("") 
    
    # --- WIDGET DE AVISOS (MODERNO E PERMANENTE) ---
    qtd_recados = contar_recados()
    
    # Define o visual dinâmico do container
    if qtd_recados > 0:
        # Com Recados: Borda Vermelha e Badge Pulsante
        with st.container(border=True):
            c1, c2, c3 = st.columns([0.5, 4, 1.5])
            with c1:
                st.markdown("## 🔔") # Sino
            with c2:
                # HTML personalizado para injetar a animação
                st.markdown(f"**Mural de Avisos** <span class='notification-badge'>{qtd_recados} NOVOS</span>", unsafe_allow_html=True)
                st.caption("Há mensagens pendentes de leitura ou ação.")
            with c3:
                st.write("") # Espaço para alinhar botão
                if st.button("Ler Recados", type="primary", use_container_width=True):
                    st.switch_page("pages/11_Quadro_Avisos.py")
    else:
        # Sem Recados: Visual Clean/Neutro
        with st.container(border=True):
            c1, c2, c3 = st.columns([0.5, 4, 1.5])
            with c1:
                st.markdown("## 📌") # Pin
            with c2:
                st.markdown(f"**Mural de Avisos** <span class='clean-badge'>0</span>", unsafe_allow_html=True)
                st.caption("Nenhuma pendência no quadro. Tudo tranquilo!")
            with c3:
                st.write("")
                if st.button("Acessar", use_container_width=True):
                    st.switch_page("pages/11_Quadro_Avisos.py")
    
    # Resumo Tabela (Apenas info de texto)
    st.markdown("")
    df_resumo = carregar_resumo_rapido()
    qtd_aberta = len(df_resumo)
    if qtd_aberta > 0:
        st.info(f"⚠️ Atenção: Existem **{qtd_aberta}** atendimentos na fila de espera.")
    else:
        st.success("✅ Tudo limpo! Nenhuma pendência no momento.")

# >> LADO DIREITO (Tabela Colorida Mantida) <<
with col_painel:
    with st.container(border=True):
        st.markdown("##### 🚨 Em Aberto (Prioritários)")
        
        if df_resumo.empty:
            st.caption("Nenhuma ordem aberta.")
        else:
            try:
                df_resumo['Prioridade'] = df_resumo['Prioridade'].fillna("Média")
                df_styled = df_resumo.style.apply(colorir_linhas, axis=1)
                
                st.dataframe(
                    df_styled,
                    use_container_width=True,
                    hide_index=True,
                    height=250,
                    column_config={
                        "Ticket": st.column_config.NumberColumn("TICKET", width="small", format="%d"),
                        "Frota": st.column_config.TextColumn("Frota", width="small"),
                        "Operacao": st.column_config.TextColumn("Tipo", width="small"),
                        "Status": st.column_config.TextColumn("Status", width="small"),
                        "Prioridade": st.column_config.TextColumn("Prio.", width="small"),
                        "Cor_Hex": None 
                    }
                )
            except Exception as e:
                st.error("Erro visual.")
                st.dataframe(df_resumo, use_container_width=True)
            
            if st.button("Ver Todos", use_container_width=True, key="btn_ver_todos_resumo"):
                st.switch_page("pages/1_Painel_Principal.py")

st.divider()

# --- BOTÕES GRANDES ---
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.markdown("### 📝 Abrir Chamado")
        st.markdown("Registrar uma nova pendência ou máquina parada.")
        if st.button("Nova Ordem de Serviço", use_container_width=True, type="primary"):
            st.switch_page("pages/5_Nova_Ordem_Servico.py")

with col2:
    with st.container(border=True):
        st.markdown("### 🔄 Gerenciar")
        st.markdown("Atualizar status, fechar ordens ou imprimir.")
        if st.button("Meus Atendimentos", use_container_width=True):
            st.switch_page("pages/6_Gerenciar_Atendimento.py")

st.markdown("---")
st.markdown("##### Acesso Rápido")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📊 Dashboards Gerais", use_container_width=True):
        st.switch_page("pages/1_Painel_Principal.py")
with c2:
    if st.button("🗺️ Mapa de Frotas", use_container_width=True):
        st.switch_page("pages/10_Mapa_Atendimentos.py")
with c3:
    if st.button("🚜 Histórico / Prontuário", use_container_width=True):
        st.switch_page("pages/7_Historico_Maquina.py")