import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from datetime import datetime, timedelta
from utils_pdf import gerar_prontuario_maquina

st.set_page_config(layout="wide", page_title="Histórico da Máquina")
st.title("🚜 Prontuário / Histórico da Máquina")

# --- FILTROS (SIDEBAR) ---
st.sidebar.header("Filtros de Período")
try:
    dt_inicio = st.sidebar.date_input("De:", datetime.now() - timedelta(days=365)) 
    dt_fim = st.sidebar.date_input("Até:", datetime.now())
except:
    st.sidebar.error("Erro nas datas.")
    dt_inicio = datetime.now()
    dt_fim = datetime.now()

# --- Funções Auxiliares ---
def formatar_duracao(td):
    if pd.isnull(td): return "Em andamento..."
    try:
        total_seconds = int(td.total_seconds())
        if total_seconds < 0: return "0m"
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        return f"{days}d {hours}h"
    except: return "-"

def carregar_frotas():
    conn = get_db_connection()
    # Busca também o gestor e modelo
    frotas = pd.read_sql_query("SELECT id, frota, modelo, gestao_responsavel FROM equipamentos ORDER BY frota", conn)
    conn.close()
    frotas['display'] = frotas['frota'] + " - " + frotas['modelo']
    return frotas

def carregar_historico_frota(equipamento_id, d_inicio, d_fim):
    conn = get_db_connection()
    try:
        d_inicio_str = d_inicio.strftime('%Y-%m-%d 00:00:00')
        d_fim_str = d_fim.strftime('%Y-%m-%d 23:59:59')
        
        # Query atualizada com JOIN para Solicitante e campos KPI
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
            os.classificacao,
            os.maquina_parada,
            f.nome as Executante,
            s.nome as Solicitante
        FROM ordens_servico os
        JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
        LEFT JOIN funcionarios f ON os.funcionario_id = f.id
        LEFT JOIN funcionarios s ON os.solicitante_id = s.id
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

# Seleção da Frota
col_sel1, col_sel2 = st.columns([1.5, 2.5])
with col_sel1:
    frota_selecionada = st.selectbox("Selecione a Máquina:", options=frotas_df['display'], index=None)

if frota_selecionada:
    # Dados da Frota Selecionada
    row_frota = frotas_df[frotas_df['display'] == frota_selecionada].iloc[0]
    id_frota = row_frota['id']
    gestor_frota = row_frota['gestao_responsavel'] if row_frota['gestao_responsavel'] else "Não Definido"
    modelo_frota = row_frota['modelo']

    # Header Informativo
    with st.container(border=True):
        c_head1, c_head2, c_head3 = st.columns([1, 2, 1])
        c_head1.markdown(f"**Frota:** {row_frota['frota']}")
        c_head2.markdown(f"**Modelo:** {modelo_frota}")
        c_head3.markdown(f"**Gestão:** {gestor_frota}")

    historico_df = carregar_historico_frota(int(id_frota), dt_inicio, dt_fim)
    
    st.divider()
    
    if historico_df.empty:
        st.warning(f"Nenhum registro encontrado para **{frota_selecionada}** neste período.")
    else:
        # --- TRATAMENTO DE DADOS ---
        historico_df['Data_DT'] = pd.to_datetime(historico_df['Data'], format='mixed', dayfirst=True, errors='coerce')
        historico_df['Fim_DT'] = pd.to_datetime(historico_df['Fim'], format='mixed', dayfirst=True, errors='coerce')
        
        # Duração
        historico_df['Duracao_Obj'] = historico_df['Fim_DT'] - historico_df['Data_DT']
        historico_df['Duração'] = historico_df['Duracao_Obj'].apply(formatar_duracao)
        
        # Formatação
        historico_df['Data_Fmt'] = historico_df['Data_DT'].dt.strftime('%d/%m/%Y %H:%M').fillna("-")
        historico_df['horimetro'] = historico_df['horimetro'].fillna(0)
        
        # Novos Campos (Preenchimento Default)
        if 'classificacao' not in historico_df.columns: historico_df['classificacao'] = 'Corretiva'
        if 'maquina_parada' not in historico_df.columns: historico_df['maquina_parada'] = 1
        
        historico_df['classificacao'] = historico_df['classificacao'].fillna('Corretiva')
        historico_df['maquina_parada'] = historico_df['maquina_parada'].fillna(1).astype(bool) # Bool para Checkbox

        # --- KPIs ---
        total_ops = len(historico_df)
        
        # Filtra falhas (Corretivas)
        df_falhas = historico_df[historico_df['classificacao'].str.contains('Corretiva', case=False, na=False)]
        total_falhas = len(df_falhas)
        
        # Tempo parado (Soma das durações onde houve parada)
        df_parado = historico_df[historico_df['maquina_parada'] == True]
        tempo_total = df_parado['Duracao_Obj'].sum(numeric_only=False)
        tempo_str = formatar_duracao(tempo_total)
        
        comum = historico_df['Operacao'].mode()[0] if not historico_df.empty else "-"
        try: ult_data = historico_df['Data_Fmt'].iloc[0]
        except: ult_data = "-"

        # Exibe KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Intervenções", total_ops)
        k2.metric("Falhas (Quebras)", total_falhas, help="Classificadas como 'Corretiva'")
        k3.metric("Tempo Total Parado", tempo_str, help="Soma da duração onde Máquina Parada = Sim")
        k4.metric("Última Intervenção", ult_data)
        
        st.divider()

        # --- GRÁFICOS ---
        c_graf1, c_graf2 = st.columns(2)
        
        with c_graf1:
            st.markdown("##### Ocorrências por Tipo")
            df_count = historico_df['Operacao'].value_counts().reset_index()
            df_count.columns = ['Tipo', 'Qtd']
            
            mapa_cores = {}
            if 'Cor_Hex' in historico_df.columns:
                mapa = historico_df[['Operacao', 'Cor_Hex']].dropna().drop_duplicates()
                mapa_cores = dict(zip(mapa['Operacao'], mapa['Cor_Hex']))

            fig = px.bar(df_count, x='Qtd', y='Tipo', orientation='h', text='Qtd', color='Tipo', color_discrete_map=mapa_cores)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with c_graf2:
            st.markdown("##### Cronologia (Classificação)")
            # Gráfico de Pizza ou Barra empilhada de Classificação
            df_class = historico_df['classificacao'].value_counts().reset_index()
            df_class.columns = ['Classe', 'Qtd']
            fig_pie = px.pie(df_class, names='Classe', values='Qtd', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- TABELA DETALHADA RICA ---
        st.subheader("📋 Registro Detalhado")
        
        st.dataframe(
            historico_df,
            use_container_width=True,
            hide_index=True,
            column_order=[
                "Ticket", "Data_Fmt", "classificacao", "maquina_parada", 
                "Operacao", "Solicitante", "Executante", "Status", "Duração", "Descricao"
            ],
            column_config={
                "Ticket": st.column_config.NumberColumn("#", width="small", format="%d"),
                "Data_Fmt": st.column_config.TextColumn("Data", width="medium"),
                "classificacao": st.column_config.TextColumn(
                    "Tipo Int.", 
                    width="small",
                    help="Preventiva vs Corretiva"
                ),
                "maquina_parada": st.column_config.CheckboxColumn(
                    "Parou?",
                    width="small",
                ),
                "Operacao": st.column_config.TextColumn("Serviço", width="medium"),
                "Solicitante": st.column_config.TextColumn("Solicitante", width="medium"),
                "Executante": st.column_config.TextColumn("Mecânico", width="medium"),
                "Duração": st.column_config.TextColumn("Tempo", width="small"),
                "Descricao": st.column_config.TextColumn("Descrição", width="large"),
            }
        )

        # --- BOTÃO DE DOWNLOAD DO PDF ---
        st.markdown("---")
        col_btn, col_info = st.columns([1, 3])
        
        with col_btn:
            # Prepara dados resumidos para o PDF
            kpis_pdf = {
                'total': total_ops, 
                'comum': comum, 
                'tempo': tempo_str, 
                'ultima_data': ult_data,
                'falhas': total_falhas
            }
            
            try:
                # Passa também o gestor para o PDF
                pdf_bytes = gerar_prontuario_maquina(frota_selecionada, historico_df, kpis_pdf, gestor=gestor_frota)
                
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
            st.info("O PDF inclui agora os dados de Solicitante, Classificação e Status de Parada.")

else:
    st.info("Selecione uma frota para ver o dossiê completo.")