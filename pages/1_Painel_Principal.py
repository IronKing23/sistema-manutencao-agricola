import streamlit as st
import pandas as pd
import plotly.express as px 
from database import get_db_connection
from datetime import datetime, timedelta
from utils_pdf import gerar_relatorio_geral
import pytz # Importante para corrigir o fuso horário

# --- Configuração Inicial ---
st.title("🖥️ Painel de Controle de Manutenção Agrícola")

# Definição do Fuso Horário Local
FUSO_HORARIO = pytz.timezone('America/Campo_Grande')

# --- CONFIGURAÇÃO DOS FILTROS ---
st.sidebar.header("Filtros de Visualização")

conn = None
try:
    conn = get_db_connection()
    frotas_list = pd.read_sql_query("SELECT DISTINCT frota FROM equipamentos ORDER BY frota", conn)
    operacoes_list = pd.read_sql_query("SELECT DISTINCT nome FROM tipos_operacao ORDER BY nome", conn)
    gestao_list = pd.read_sql_query("SELECT DISTINCT gestao_responsavel FROM equipamentos WHERE gestao_responsavel IS NOT NULL AND gestao_responsavel != '' ORDER BY gestao_responsavel", conn)
except Exception as e:
    st.error(f"Erro filtros: {e}")
    frotas_list = pd.DataFrame(); operacoes_list = pd.DataFrame(); gestao_list = pd.DataFrame()
finally:
    if conn: conn.close()

status_options = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças", "Concluído"]
default_selection = ["Pendente", "Aberto (Parada)", "Em Andamento", "Aguardando Peças"]
filtro_status = st.sidebar.multiselect("Status:", options=status_options, default=default_selection)
filtro_prioridade = st.sidebar.multiselect("Prioridade:", ["Alta", "Média", "Baixa"])
filtro_frota = st.sidebar.multiselect("Frota:", options=frotas_list['frota'].tolist())
filtro_operacao = st.sidebar.multiselect("Tipo Operação:", options=operacoes_list['nome'].tolist())
filtro_gestao = st.sidebar.multiselect("Gestor:", options=gestao_list['gestao_responsavel'].tolist())

st.sidebar.markdown("---")
try:
    data_inicio = st.sidebar.date_input("De:", datetime.now() - timedelta(days=30))
    data_fim = st.sidebar.date_input("Até:", datetime.now())
except: pass

# --- Query Global (Top Frotas) ---
query_global = """
SELECT e.frota as Frota, COUNT(os.id) as Qtd
FROM ordens_servico os
JOIN equipamentos e ON os.equipamento_id = e.id
GROUP BY e.frota
ORDER BY Qtd DESC LIMIT 10
"""

# --- Query Principal ---
query = """
SELECT 
    os.id as Ticket,
    os.data_hora as Data,
    os.data_encerramento as Fim,
    os.horimetro,
    os.prioridade,
    e.frota,
    e.modelo,
    e.gestao_responsavel as Gestao, 
    f.nome as Executante,
    os.status,
    os.numero_os_oficial as OS_Oficial,
    op.nome as Operacao,
    op.cor as Cor_Hex,
    os.local_atendimento as Local,
    os.descricao
FROM ordens_servico os
JOIN equipamentos e ON os.equipamento_id = e.id
JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
LEFT JOIN funcionarios f ON os.funcionario_id = f.id
WHERE 1=1 
"""
params = []

if filtro_status:
    query += f" AND os.status IN ({','.join(['?'] * len(filtro_status))})"
    params.extend(filtro_status)
if filtro_prioridade: 
    query += f" AND os.prioridade IN ({','.join(['?'] * len(filtro_prioridade))})"
    params.extend(filtro_prioridade)
if filtro_frota:
    query += f" AND e.frota IN ({','.join(['?'] * len(filtro_frota))})"
    params.extend(filtro_frota)
if filtro_operacao:
    query += f" AND op.nome IN ({','.join(['?'] * len(filtro_operacao))})"
    params.extend(filtro_operacao)
if filtro_gestao:
    query += f" AND e.gestao_responsavel IN ({','.join(['?'] * len(filtro_gestao))})"
    params.extend(filtro_gestao)

data_inicio_dt = datetime.combine(data_inicio, datetime.min.time())
data_fim_dt = datetime.combine(data_fim, datetime.max.time())
query += " AND os.data_hora BETWEEN ? AND ?"
params.extend([data_inicio_dt, data_fim_dt])

# Ordenação por Prioridade (CASE WHEN)
query += """ 
ORDER BY 
    CASE os.prioridade
        WHEN 'Alta' THEN 1
        WHEN 'Média' THEN 2
        WHEN 'Baixa' THEN 3
        ELSE 4
    END ASC,
    os.data_hora DESC
"""

conn = None 
try:
    conn = get_db_connection()
    df_painel = pd.read_sql_query(query, conn, params=params)
    df_frotas_global = pd.read_sql_query(query_global, conn)
except Exception as e:
    st.error(f"Erro SQL: {e}")
    df_painel = pd.DataFrame() 
    df_frotas_global = pd.DataFrame()
finally:
    if conn: conn.close()

# ==============================================================================
# VISUALIZAÇÃO
# ==============================================================================
tab_lista, tab_dash = st.tabs(["📋 Detalhamento (Tabela)", "📊 Visão Geral (Dashboard)"])

# ------------------------------------------------------------------------------
# ABA 1: TABELA DETALHADA
# ------------------------------------------------------------------------------
with tab_lista:
    if df_painel.empty:
        st.info("Nenhum atendimento para listar.")
    else:
        # 1. Formatação de Datas e Nulos (BLINDADO)
        df_painel['Data_DT'] = pd.to_datetime(df_painel['Data'], format='mixed', dayfirst=True, errors='coerce')
        fim_dt = pd.to_datetime(df_painel['Fim'], format='mixed', dayfirst=True, errors='coerce')
        
        # --- CÁLCULO TEMPO ABERTO CORRIGIDO ---
        # Pega o 'agora' no fuso horário correto (MS)
        # .replace(tzinfo=None) remove a info de fuso para fazer conta com a data 'naive' do banco
        agora = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
        
        fim_calculo = fim_dt.fillna(agora)
        df_painel['delta'] = fim_calculo - df_painel['Data_DT']
        
        def formatar_delta(td):
            if pd.isnull(td): return "-"
            try:
                total_seconds = int(td.total_seconds())
                # Se der negativo (por erro de fuso ou relógio desajustado), retorna 0m
                if total_seconds < 0: return "0m"
                
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                minutes = ((total_seconds % 86400) % 3600) // 60
                
                parts = []
                if days > 0: parts.append(f"{days}d")
                if hours > 0: parts.append(f"{hours}h")
                if minutes > 0: parts.append(f"{minutes}m")
                return " ".join(parts) if parts else "< 1m"
            except: return "-"

        df_painel['Tempo_Aberto'] = df_painel['delta'].apply(formatar_delta)
        
        # Formatação para String (Visualização)
        df_painel['Data'] = df_painel['Data_DT'].dt.strftime('%d/%m/%Y %H:%M').fillna("-")
        df_painel['Fim'] = fim_dt.dt.strftime('%d/%m/%Y %H:%M').fillna("-")
        
        df_painel['prioridade'] = df_painel['prioridade'].fillna("Média")
        df_painel['horimetro'] = df_painel['horimetro'].fillna(0)

        # 2. CONVERSÃO PARA MAIÚSCULAS
        colunas_texto = ['frota', 'modelo', 'Gestao', 'Executante', 'status', 'OS_Oficial', 'Operacao', 'Local', 'descricao', 'prioridade']
        for col in colunas_texto:
            if col in df_painel.columns:
                df_painel[col] = df_painel[col].astype(str).str.upper().replace(['NONE', 'NAN'], '-')

        # 3. Seleção e Ordem das Colunas
        colunas_ordem = ['Ticket', 'OS_Oficial', 'frota', 'modelo', 'prioridade', 'status', 'Local', 'Data', 'Tempo_Aberto', 'descricao', 'Operacao', 'Cor_Hex']
        cols_to_show = [c for c in colunas_ordem if c in df_painel.columns]
        df_exibicao = df_painel[cols_to_show]

        # --- Lógica de Cores ---
        def hex_to_rgba(hex_code, opacity=0.25):
            if not hex_code or not isinstance(hex_code, str) or not hex_code.startswith('#'): return None 
            hex_code = hex_code.lstrip('#')
            try:
                rgb = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
                return f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
            except: return None

        def colorir_linhas_hibrido(row):
            operacao = str(row['Operacao']).lower()
            cor_db = row.get('Cor_Hex')
            cor_final = hex_to_rgba(cor_db, opacity=0.25)
            if not cor_final:
                if 'elet' in operacao: cor_final = 'rgba(33, 150, 243, 0.25)'
                elif 'mecan' in operacao: cor_final = 'rgba(158, 158, 158, 0.25)'
                elif 'borrach' in operacao: cor_final = 'rgba(255, 152, 0, 0.25)'   
                else: cor_final = 'transparent'
            return [f'background-color: {cor_final}' for _ in row]

        try:
            df_styled = df_exibicao.style.apply(colorir_linhas_hibrido, axis=1)
            st.dataframe(
                df_styled, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Ticket": st.column_config.NumberColumn("Ticket", width="small", format="%d"),
                    "OS_Oficial": st.column_config.TextColumn("OS Oficial", width="small"),
                    "Tempo_Aberto": st.column_config.TextColumn("Tempo", width="small", help="Tempo decorrido"),
                    "Cor_Hex": None 
                }
            )
        except:
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            @st.cache_data
            def convert_df(df): return df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar CSV", convert_df(df_exibicao), 'relatorio.csv', 'text/csv', use_container_width=True)
        with col_dl2:
            try:
                pdf_bytes = gerar_relatorio_geral(df_exibicao)
                st.download_button("🖨️ Baixar PDF (Paisagem)", pdf_bytes, 'relatorio_geral.pdf', 'application/pdf', type='primary', use_container_width=True)
            except Exception as e: st.error(f"Erro PDF: {e}")

# ------------------------------------------------------------------------------
# ABA 2: DASHBOARD
# ------------------------------------------------------------------------------
with tab_dash:
    # CSS
    st.markdown("""
    <style>
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(255, 82, 82, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 82, 82, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 82, 82, 0); }
    }
    .badge-pulse {
        background-color: #FF5252; color: white; 
        padding: 4px 10px; border-radius: 12px; font-size: 0.8em; font-weight: bold;
        animation: pulse-red 2s infinite; display: inline-block;
    }
    div.stButton > button[kind="primary"] {
        background-color: #2196F3; color: white; border: none; font-weight: bold;
        transition: all 0.2s ease;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #1976D2; transform: scale(1.02);
    }
    </style>
    """, unsafe_allow_html=True)

    if df_painel.empty:
        st.warning("Sem dados.")
    else:
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        total = len(df_painel)
        urgentes = len(df_painel[df_painel['prioridade'].astype(str).str.upper() == 'ALTA'])
        pendentes = len(df_painel[df_painel['status'].astype(str).str.upper() != 'CONCLUÍDO'])
        frotas_afetadas = df_painel[df_painel['status'].astype(str).str.upper() != 'CONCLUÍDO']['frota'].nunique()
        
        col_kpi1.metric("Total", total)
        
        with col_kpi2:
            if urgentes > 0:
                lista_frotas = sorted(df_painel[df_painel['prioridade'].astype(str).str.upper() == 'ALTA']['frota'].astype(str).unique())
                tooltip_text = "⚠️ FROTAS CRÍTICAS (ALTA):&#10;" + "&#10;".join(lista_frotas)
                st.markdown(f"""
                <div style="text-align:center; cursor: help;" title="{tooltip_text}">
                    <p style="margin:0; color:#666; font-size:0.9rem;">Alta Prioridade</p>
                    <p style="margin:0; font-size:2rem; font-weight:bold;">{urgentes}</p>
                    <span class="badge-pulse">⚠️ AÇÃO</span>
                </div>
                """, unsafe_allow_html=True)
                st.write("")
                if st.button("👁️ Ver", key="btn_crit", type="primary", use_container_width=True):
                    st.session_state['show_criticos'] = not st.session_state.get('show_criticos', False)
            else:
                st.metric("Alta Prioridade", 0)

        col_kpi3.metric("Em Aberto", pendentes)
        col_kpi4.metric("Frotas Afetadas", frotas_afetadas)
        
        if st.session_state.get('show_criticos') and urgentes > 0:
            st.markdown("---")
            st.markdown("### 🚨 Frotas Críticas")
            df_show = df_painel[df_painel['prioridade'].astype(str).str.upper() == 'ALTA'].copy()
            cols_c = ['Ticket', 'frota', 'modelo', 'Local', 'Operacao', 'descricao', 'Data', 'Cor_Hex']
            cols_c = [c for c in cols_c if c in df_show.columns]
            
            try:
                st.dataframe(
                    df_show[cols_c].style.apply(colorir_linhas_hibrido, axis=1),
                    use_container_width=True, hide_index=True, column_config={"Cor_Hex": None}
                )
            except: st.dataframe(df_show[cols_c], use_container_width=True)
            
            if st.button("Fechar"): st.session_state['show_criticos'] = False; st.rerun()
            st.markdown("---")

        st.divider()
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.markdown("##### 🚜 Top Frotas (Histórico Geral)")
            if not df_frotas_global.empty:
                df_frotas_global['Frota'] = df_frotas_global['Frota'].astype(str)
                fig_bar = px.bar(df_frotas_global, x='Qtd', y='Frota', text='Qtd', color='Qtd', orientation='h')
                fig_bar.update_yaxes(type='category') 
                fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_bar, use_container_width=True)

        with col_graf2:
            st.markdown("##### 🔧 Por Tipo")
            df_chart_pie = df_painel.groupby('Operacao').agg(Qtd=('Ticket', 'count'), Lista=('frota', lambda x: ",".join(sorted(x.unique())))).reset_index()
            mapa = dict(zip(df_painel['Operacao'], df_painel['Cor_Hex'])) if 'Cor_Hex' in df_painel.columns else {}
            fig_pie = px.pie(df_chart_pie, values='Qtd', names='Operacao', color='Operacao', color_discrete_map=mapa, custom_data=['Lista'], hole=0.4)
            fig_pie.update_traces(hovertemplate="<b>%{label}</b><br>Qtd: %{value}<br>%{customdata[0]}")
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("##### 📅 Linha do Tempo (Interativa)")
    with st.container(border=True):
        if not df_painel.empty:
            df_timeline = df_painel.copy()
            df_timeline['Data_DT'] = pd.to_datetime(df_timeline['Data_DT'])
            mapa = dict(zip(df_timeline['Operacao'], df_timeline['Cor_Hex'])) if 'Cor_Hex' in df_timeline.columns else {}
            
            fig_sc = px.scatter(df_timeline, x='Data_DT', y='prioridade', color='Operacao', size='Ticket', size_max=12,
                hover_data={'Data_DT': '|%d/%m %H:%M', 'prioridade':False, 'Ticket':True, 'frota':True, 'descricao':True}, color_discrete_map=mapa)
            fig_sc.update_yaxes(categoryorder='array', categoryarray=['BAIXA', 'MÉDIA', 'ALTA'])
            
            ev = st.plotly_chart(fig_sc, use_container_width=True, on_select="rerun", selection_mode="points")
            
            if ev and len(ev['selection']['points']) > 0:
                idx = ev['selection']['points'][0]['point_index']
                row = df_timeline.iloc[idx]
                st.divider()
                st.markdown(f"### 🔍 Detalhes #{row['Ticket']}")
                c1, c2, c3 = st.columns(3)
                c1.info(f"**Frota:** {row['frota']}"); c2.warning(f"**Tipo:** {row['Operacao']}"); c3.error(f"**Prio:** {row['prioridade']}")
                st.caption(row['descricao'])
