import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from database import get_db_connection
    from utils_ui import load_custom_css
    from utils_icons import get_icon
except ImportError:
    pass

# --- 1. CONFIGURAÇÃO VISUAL PREMIUM ---
load_custom_css()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    .main .block-container {
        padding-top: 2rem !important;
        max-width: 1200px;
        font-family: 'Inter', sans-serif;
    }

    .header-greeting {
        font-size: 2rem;
        font-weight: 800;
        color: var(--text-color);
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    .header-date {
        font-size: 1rem;
        color: #888888;
        margin-bottom: 2rem;
    }

    .kpi-card {
        background-color: var(--secondary-background-color);
        border-radius: 12px;
        padding: 22px;
        border: 1px solid rgba(128, 128, 128, 0.1);
        transition: all 0.3s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    .kpi-card:hover {
        border-color: var(--primary-color);
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.05);
    }
    .kpi-title {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #888888;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .kpi-value {
        font-size: 2.5rem;
        font-weight: 800;
        color: var(--text-color);
        line-height: 1;
    }
    .kpi-desc {
        font-size: 0.85rem;
        color: #666666;
        margin-top: 8px;
    }

    .section-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--text-color);
        margin-top: 3rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .section-title::after {
        content: "";
        flex: 1;
        height: 1px;
        background: rgba(128, 128, 128, 0.1);
    }

    .report-box {
        background: rgba(128, 128, 128, 0.05);
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        border: 1px solid transparent;
        transition: 0.3s;
    }
    .report-box:hover {
        background: rgba(128, 128, 128, 0.1);
        border-color: var(--primary-color);
    }
</style>
""", unsafe_allow_html=True)


# --- 2. MOTOR DE DADOS DE ALTA PERFORMANCE (CACHE) ---

# Mantém os dados na memória por 60 segundos para não sobrecarregar o Banco de Dados
@st.cache_data(ttl=60, show_spinner=False)
def carregar_kpis():
    kpis = {
        'abertas': 0, 'andamento': 0, 'aguardando': 0,
        'pneus_ausente': 0, 'recados': 0
    }
    try:
        conn = get_db_connection()

        # OS Segura (Conta direto pelo banco para ser mais rápido e não quebrar com DF vazio)
        df_os = pd.read_sql("SELECT status FROM ordens_servico", conn)
        if not df_os.empty:
            contagem = df_os['status'].value_counts()
            kpis['abertas'] = int(contagem.get('Aberta', 0))
            kpis['andamento'] = int(contagem.get('Em Andamento', 0))
            kpis['aguardando'] = int(contagem.get('Aguardando Peça', 0))

        # Pneus Segura
        try:
            df_pneus = pd.read_sql("SELECT status FROM controle_pneus_status", conn)
            kpis['pneus_ausente'] = int(df_pneus['status'].value_counts().get('Ausente', 0))
        except:
            pass

        # Avisos Segura
        try:
            df_avisos = pd.read_sql("SELECT COUNT(*) as qtd FROM mural_avisos WHERE ativo = 1", conn)
            kpis['recados'] = int(df_avisos.iloc[0]['qtd'])
        except:
            pass

        conn.close()
    except Exception as e:
        pass  # Falha silenciosa elegante

    return kpis


# Busca os dados no Cache
dados = carregar_kpis()

# --- 3. CABEÇALHO DINÂMICO ---
nome_usuario = st.session_state.get('user_nome', 'Gestor')
primeiro_nome = nome_usuario.split()[0]
data_atual = datetime.now().strftime("%d de %B, %Y")

c_head1, c_head2 = st.columns([4, 1])
with c_head1:
    st.markdown(f'<div class="header-greeting">Bom dia, {primeiro_nome}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="header-date">{data_atual} • Status do Sistema Cedro</div>', unsafe_allow_html=True)
with c_head2:
    st.write("")  # Espaçamento
    if st.button("🔄 Atualizar Painel", use_container_width=True):
        carregar_kpis.clear()  # Limpa o cache para forçar a busca de novos dados
        st.rerun()

# --- 4. DASHBOARD (KPIs) ---
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-title">🛠️ Ativos em Reparo</div>
        <div class="kpi-value" style="color: #3b82f6;">{dados['andamento']}</div>
        <div class="kpi-desc">Equipamentos na oficina agora.</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-title">⏳ Fila de OS</div>
        <div class="kpi-value" style="color: #f59e0b;">{dados['abertas']}</div>
        <div class="kpi-desc">Serviços aguardando técnico.</div>
    </div>""", unsafe_allow_html=True)

with k3:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-title">📦 Pendência Peças</div>
        <div class="kpi-value" style="color: #ef4444;">{dados['aguardando']}</div>
        <div class="kpi-desc">Aguardando suprimentos.</div>
    </div>""", unsafe_allow_html=True)

with k4:
    cor_txt = "#ef4444" if dados['pneus_ausente'] > 0 else "#10b981"
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-title">🛞 Status Pneus</div>
        <div class="kpi-value" style="color: {cor_txt};">{dados['pneus_ausente']}</div>
        <div class="kpi-desc">Alertas de frotas descalçadas.</div>
    </div>""", unsafe_allow_html=True)

# --- 5. OPERAÇÕES RÁPIDAS ---
st.markdown('<div class="section-title">⚡ Operações de Campo</div>', unsafe_allow_html=True)

col_op1, col_op2, col_op3, col_op4 = st.columns(4)

with col_op1:
    if st.button("📝 Nova OS", use_container_width=True, type="primary"):
        st.switch_page("pages/5_Nova_Ordem_Servico.py")
with col_op2:
    if st.button("🛞 Gestão Pneus", use_container_width=True):
        st.switch_page("pages/18_Controle_Pneus.py")
with col_op3:
    if st.button("⛽ Comboio", use_container_width=True):
        st.switch_page("pages/19_Gestao_Comboio.py")
with col_op4:
    if st.button("🗺️ Mapa Frotas", use_container_width=True):
        st.switch_page("pages/10_Mapa_Atendimentos.py")

# --- 6. RELATÓRIOS E INTELIGÊNCIA ---
st.markdown('<div class="section-title">📊 Inteligência e Gestão</div>', unsafe_allow_html=True)

r1, r2, r3, r4 = st.columns(4)

with r1:
    st.markdown('<div class="report-box">📈</div>', unsafe_allow_html=True)
    if st.button("Indicadores KPI", use_container_width=True):
        st.switch_page("pages/15_Indicadores_KPI.py")

with r2:
    st.markdown('<div class="report-box">⏱️</div>', unsafe_allow_html=True)
    if st.button("Eficiência RH", use_container_width=True):
        st.switch_page("pages/17_Eficiencia_Apontamentos.py")

with r3:
    st.markdown('<div class="report-box">💰</div>', unsafe_allow_html=True)
    if st.button("Custos Totais", use_container_width=True):
        st.switch_page("pages/18_relatorio_gastos.py")

with r4:
    st.markdown('<div class="report-box">🧪</div>', unsafe_allow_html=True)
    if st.button("Análise Óleo", use_container_width=True):
        st.switch_page("pages/20_Analise_Preditiva_Oleo.py")

# --- 7. MURAL DE AVISOS ---
st.markdown('<div class="section-title">📢 Comunicação Interna</div>', unsafe_allow_html=True)

with st.container(border=True):
    col_icon, col_msg, col_btn = st.columns([0.4, 3, 1])
    with col_icon:
        st.markdown("<h1 style='text-align: center; margin: 0;'>📣</h1>", unsafe_allow_html=True)
    with col_msg:
        st.markdown(f"**Mural da Equipe**")
        if dados['recados'] > 0:
            st.markdown(
                f"Atenção: Você tem <strong style='color:#f59e0b;'>{dados['recados']} novos avisos</strong> pendentes de leitura.",
                unsafe_allow_html=True)
        else:
            st.markdown("Nenhum aviso novo no quadro de comunicações.")
    with col_btn:
        st.write("")
        if st.button("Acessar Mural", use_container_width=True):
            st.switch_page("pages/11_Quadro_Avisos.py")

st.markdown("<br><br>", unsafe_allow_html=True)