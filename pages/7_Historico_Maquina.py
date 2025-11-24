import streamlit as st
import pandas as pd
import plotly.express as px
from database import get_db_connection
from datetime import datetime, timedelta
from utils_pdf import gerar_prontuario_maquina

st.set_page_config(layout="wide", page_title="Histórico da Máquina")
st.title("🚜 Prontuário / Histórico da Máquina")

# --- FILTROS ---
# Adicionei filtro de data na sidebar para controlar o relatório
st.sidebar.header("Filtros de Período")
dt_inicio = st.sidebar.date_input("De:", datetime.now() - timedelta(days=365)) # Padrão: Último ano
dt_fim = st.sidebar.date_input("Até:", datetime.now())

# --- Funções Auxiliares ---
def formatar_duracao(td):
    if pd.isnull(td): return "Em andamento..."
    total_seconds = int(td.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    return f"{days}d {hours}h"

def carregar_frotas():
    conn = get_db_connection()
    frotas = pd.read_sql_query("SELECT id, frota, modelo FROM equipamentos ORDER BY frota", conn)
    conn.close()
    frotas['display'] = frotas['frota'] + " - " + frotas['modelo']
    return frotas

def carregar_historico_frota(equipamento_id, d_inicio, d_fim):
    conn = get_db_connection()
    try:
        # Filtra por data no SQL
        d_inicio_str = d_inicio.strftime('%Y-%m-%d 00:00:00')
        d_fim_str = d_fim.strftime('%Y-%m-%d 23:59:59')
        
        query = """
        SELECT 
            os.id as Ticket,
            os.data_hora as Data,
            os.data_encerramento as Fim,
            os.horimetro,
            op.nome as Operacao,
            op.cor as Cor_Hex,
            os.status as Status,
            os.numero_os_oficial as OS_Oficial,
            os.descricao as Descricao,
            f.nome as Executante
        FROM ordens_servico os
        JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
        LEFT JOIN funcionarios f ON os.funcionario_id = f.id
        WHERE os.equipamento_id = ? AND os.data_hora BETWEEN ? AND ?
        ORDER BY os.data_hora DESC
        """
        df = pd.read_sql_query(query, conn, params=(equipamento_id, d_inicio_str, d_fim_str))
        return df
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# --- Lógica da Interface ---
frotas_df = carregar_frotas()

col_sel1, col_sel2 = st.columns([1, 2])
with col_sel1:
    frota_selecionada = st.selectbox("Selecione a Máquina:", options=frotas_df['display'], index=None)

if frota_selecionada:
    id_frota = frotas_df[frotas_df['display'] == frota_selecionada]['id'].values[0]
    
    # Carrega dados filtrados por data
    historico_df = carregar_historico_frota(int(id_frota), dt_inicio, dt_fim)
    
    st.divider()
    
    if historico_df.empty:
        st.warning(f"Nenhum registro encontrado para **{frota_selecionada}** neste período ({dt_inicio} a {dt_fim}).")
    else:
        # Processamento
        historico_df['Data_DT'] = pd.to_datetime(historico_df['Data'])
        historico_df['Fim_DT'] = pd.to_datetime(historico_df['Fim'], errors='coerce')
        historico_df['Duracao_Obj'] = historico_df['Fim_DT'] - historico_df['Data_DT']
        historico_df['Duração'] = historico_df['Duracao_Obj'].apply(formatar_duracao)
        historico_df['Data_Fmt'] = historico_df['Data_DT'].dt.strftime('%d/%m/%Y')

        # KPIs
        total_ops = len(historico_df)
        comum = historico_df['Operacao'].mode()[0] if not historico_df.empty else "-"
        tempo_total = historico_df['Duracao_Obj'].sum()
        tempo_str = formatar_duracao(tempo_total)
        ult_data = historico_df['Data_Fmt'].iloc[0]

        # Exibe KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Intervenções", total_ops)
        k2.metric("Defeito + Comum", comum)
        k3.metric("Tempo Parado", tempo_str)
        k4.metric("Última Data", ult_data)
        
        st.divider()

        # --- GRÁFICOS ---
        c_graf1, c_graf2 = st.columns(2)
        
        with c_graf1:
            st.markdown("##### Ocorrências por Tipo")
            df_count = historico_df['Operacao'].value_counts().reset_index()
            df_count.columns = ['Tipo', 'Qtd']
            
            # Cores do banco
            mapa_cores = {}
            if 'Cor_Hex' in historico_df.columns:
                mapa = historico_df[['Operacao', 'Cor_Hex']].dropna().drop_duplicates()
                mapa_cores = dict(zip(mapa['Operacao'], mapa['Cor_Hex']))

            fig = px.bar(df_count, x='Qtd', y='Tipo', orientation='h', text='Qtd', color='Tipo', color_discrete_map=mapa_cores)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with c_graf2:
            st.markdown("##### Evolução do Horímetro")
            # Filtra horímetros válidos
            df_line = historico_df[historico_df['horimetro'] > 0].sort_values('Data_DT')
            if not df_line.empty:
                fig_line = px.line(df_line, x='Data_DT', y='horimetro', markers=True)
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Sem dados de horímetro para gráfico.")

        # --- TABELA DETALHADA ---
        with st.expander("📋 Visualizar Tabela Detalhada", expanded=True):
            st.dataframe(
                historico_df[['Ticket', 'Data_Fmt', 'Operacao', 'Status', 'Duração', 'Descricao']],
                use_container_width=True,
                hide_index=True
            )

        # --- BOTÃO DE DOWNLOAD DO PDF ---
        st.markdown("---")
        col_btn, col_info = st.columns([1, 3])
        
        with col_btn:
            # Prepara dados para o PDF
            kpis = {
                'total': total_ops,
                'comum': comum,
                'tempo': tempo_str,
                'ultima_data': ult_data
            }
            
            try:
                pdf_bytes = gerar_prontuario_maquina(frota_selecionada, historico_df, kpis)
                
                st.download_button(
                    label="🖨️ Baixar Prontuário (PDF)",
                    data=pdf_bytes,
                    file_name=f"Prontuario_{frota_selecionada}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
        
        with col_info:
            st.info("O PDF contém o resumo, os KPIs, um gráfico simplificado e a lista completa de manutenções deste período.")

else:
    st.info("Selecione uma frota para ver o dossiê.")