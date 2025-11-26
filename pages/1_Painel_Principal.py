import streamlit as st
import pandas as pd
import plotly.express as px 
from database import get_db_connection
from datetime import datetime, timedelta
from utils_pdf import gerar_relatorio_geral
import pytz 

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

# Ordenação por Prioridade
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
# PROCESSAMENTO DE DADOS (GLOBAL)
# ==============================================================================
if not df_painel.empty:
    df_painel['Data_DT'] = pd.to_datetime(df_painel['Data'], format='mixed', dayfirst=True, errors='coerce')
    fim_dt = pd.to_datetime(df_painel['Fim'], format='mixed', dayfirst=True, errors='coerce')
    
    agora = datetime.now(FUSO_HORARIO).replace(tzinfo=None)
    fim_calculo = fim_dt.fillna(agora)
    df_painel['delta'] = fim_calculo - df_painel['Data_DT']
    
    def formatar_delta(td):
        if pd.isnull(td): return "-"
        try:
            total_seconds = int(td.total_seconds())
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
    
    df_painel['Data'] = df_painel['Data_DT'].dt.strftime('%d/%m/%Y %H:%M').fillna("-")
    df_painel['Fim'] = fim_dt.dt.strftime('%d/%m/%Y %H:%M').fillna("-")
    
    df_painel['prioridade'] = df_painel['prioridade'].fillna("Média")
    df_painel['horimetro'] = df_painel['horimetro'].fillna(0)

    colunas_texto = ['frota', 'modelo', 'Gestao', 'Executante', 'status', 'OS_Oficial', 'Operacao', 'Local', 'descricao', 'prioridade']
    for col in colunas_texto:
        if col in df_painel.columns:
            df_painel[col] = df_painel[col].astype(str).str.upper().replace(['NONE', 'NAN'], '-')

# --- FUNÇÕES DE ESTILO ---
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

# ==============================================================================
# VISUALIZAÇÃO
# ==============================================================================
tab_lista, tab_dash = st.tabs(["📋 Detalhamento (Tabela)", "📊 Visão Geral (Dashboard)"])

colunas_ordem = ['Ticket', 'OS_Oficial', 'frota', 'modelo', 'Gestao', 'prioridade', 'status', 'Local', 'Data', 'Tempo_Aberto', 'descricao', 'Operacao', 'Cor_Hex']
config_tabela = {
    "Ticket": st.column_config.NumberColumn("Ticket", width="small", format="%d"),
    "OS_Oficial": st.column_config.TextColumn("OS Oficial", width="small"),
    "Tempo_Aberto": st.column_config.TextColumn("Tempo", width="small", help="Tempo decorrido"),
    "Gestao": st.column_config.TextColumn("Gestão Resp.", width="medium"),
    "Cor_Hex": None 
}

# ------------------------------------------------------------------------------
# ABA 1: TABELA DETALHADA
# ------------------------------------------------------------------------------
with tab_lista:
    if df_painel.empty:
        st.info("Nenhum atendimento para listar.")
    else:
        cols_to_show = [c for c in colunas_ordem if c in df_painel.columns]
        df_exibicao = df_painel[cols_to_show]

        try:
            df_styled = df_exibicao.style.apply(colorir_linhas_hibrido, axis=1)
            st.dataframe(df_styled, use_container_width=True, hide_index=True, column_config=config_tabela)
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
# ABA 2: DASHBOARD (UI/UX MODERNIZADA)
# ------------------------------------------------------------------------------
with tab_dash:
    # --- CSS MODERNO PARA OS CARDS ---
    st.markdown("""
    <style>
    /* Cards KPI */
    .kpi-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 15px 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .kpi-card:hover {
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        transform: translateY(-3px);
    }
    .kpi-icon {
        float: right;
        font-size: 1.8rem;
        margin-top: -5px;
    }
    .kpi-title {
        font-size: 0.9rem;
        color: #6c757d;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 5px;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 800;
        color: #212529;
    }
    
    /* Adaptação Dark Mode */
    @media (prefers-color-scheme: dark) {
        .kpi-card {
            background-color: #262730;
            border-color: #3f3f46;
        }
        .kpi-title { color: #a1a1aa; }
        .kpi-value { color: #f4f4f5; }
    }
    
    /* Badge Pulsante */
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(255, 82, 82, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 82, 82, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 82, 82, 0); }
    }
    .badge-pulse {
        background-color: #EF4444; 
        color: white; 
        padding: 4px 10px; 
        border-radius: 12px; 
        font-size: 0.75em; 
        font-weight: bold;
        animation: pulse-red 2s infinite;
        display: inline-block;
        margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Função auxiliar para desenhar o card
    def exibir_card(col, titulo, valor, icone, cor_borda, is_urgente=False):
        # HTML do Card
        html_content = f"""
        <div class="kpi-card" style="border-left: 5px solid {cor_borda};">
            <div>
                <div class="kpi-title">{titulo} <span class="kpi-icon">{icone}</span></div>
                <div class="kpi-value">{valor}</div>
            </div>
            {f'<div class="badge-pulse">⚠️ AÇÃO NECESSÁRIA</div>' if is_urgente and valor > 0 else ''}
        </div>
        """
        col.markdown(html_content, unsafe_allow_html=True)

    if df_painel.empty:
        st.warning("Sem dados.")
    else:
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        
        total = len(df_painel)
        urgentes = len(df_painel[df_painel['prioridade'].astype(str).str.upper() == 'ALTA'])
        pendentes = len(df_painel[df_painel['status'].astype(str).str.upper() != 'CONCLUÍDO'])
        frotas_afetadas = df_painel[df_painel['status'].astype(str).str.upper() != 'CONCLUÍDO']['frota'].nunique()
        
        # --- RENDERIZAÇÃO DOS CARDS MODERNOS ---
        exibir_card(col_kpi1, "Total de Ordens", total, "📋", "#3B82F6") # Azul
        
        # Card de Alta Prioridade com Lógica Especial (Botão Fora do HTML)
        with col_kpi2:
            exibir_card(col_kpi2, "Alta Prioridade", urgentes, "🔥", "#EF4444", is_urgente=True)
            if urgentes > 0:
                if st.button("👁️ Ver Frotas", key="btn_crit_dash", use_container_width=True):
                    st.session_state['show_criticos'] = not st.session_state.get('show_criticos', False)

        exibir_card(col_kpi3, "Em Aberto", pendentes, "⏳", "#F59E0B") # Laranja
        exibir_card(col_kpi4, "Frotas Paradas", frotas_afetadas, "🚜", "#10B981") # Verde
        
        # --- TABELA DE FROTAS CRÍTICAS ---
        if st.session_state.get('show_criticos') and urgentes > 0:
            st.markdown("---")
            st.markdown("### 🚨 Frotas Críticas (Prioridade Alta)")
            df_show = df_painel[df_painel['prioridade'].astype(str).str.upper() == 'ALTA'].copy()
            cols_c = [c for c in colunas_ordem if c in df_show.columns]
            
            try:
                st.dataframe(
                    df_show[cols_c].style.apply(colorir_linhas_hibrido, axis=1),
                    use_container_width=True, 
                    hide_index=True, 
                    column_config=config_tabela
                )
            except: st.dataframe(df_show[cols_c], use_container_width=True)
            
            if st.button("Fechar Lista"): st.session_state['show_criticos'] = False; st.rerun()
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
