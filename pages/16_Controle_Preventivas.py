import streamlit as st
import pandas as pd
import sys
import os
import sqlite3
from datetime import datetime, timedelta

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from utils_ui import load_custom_css
from utils_log import registrar_log

# --- 1. CONFIGURAÇÃO VISUAL ---
load_custom_css()

# CSS Refinado para o Kanban Limpo
st.markdown("""
<style>
    /* Card Kanban */
    .kanban-card {
        background-color: white;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-left: 5px solid #ccc;
        transition: transform 0.2s;
    }
    .kanban-card:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }

    /* Cores de Status */
    .card-vencido { border-left-color: #D32F2F !important; }
    .card-urgente { border-left-color: #F57C00 !important; }
    .card-planejamento { border-left-color: #1976D2 !important; }

    /* Títulos das Colunas */
    .col-header {
        padding: 10px;
        text-align: center;
        font-weight: bold;
        color: white;
        border-radius: 6px;
        margin-bottom: 15px;
        text-transform: uppercase;
        font-size: 0.9rem;
    }

    /* Badge de Garantia */
    .badge-garantia {
        background-color: #E3F2FD;
        color: #1565C0;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: bold;
        float: right;
    }

    /* Métricas no topo */
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
</style>
""", unsafe_allow_html=True)


# --- 2. SETUP DO BANCO DE DADOS ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Tabelas essenciais
    cursor.execute("""CREATE TABLE IF NOT EXISTS prev_planos_def (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, intervalo INTEGER, unidade TEXT, tipo TEXT, executante TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS prev_associacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, plano_id INTEGER, frota TEXT, modelo_ref TEXT,
        FOREIGN KEY(plano_id) REFERENCES prev_planos_def(id), UNIQUE(plano_id, frota))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS historico_manutencao (
        id INTEGER PRIMARY KEY AUTOINCREMENT, equipamento_id INTEGER, data_realizacao DATE, 
        horimetro_km_realizado REAL, tipo_servico TEXT, observacao TEXT)""")
    conn.commit()
    conn.close()


init_db()


# --- 3. FUNÇÕES UTILITÁRIAS ---
def limpar_numero(valor):
    if isinstance(valor, str): return float(valor.replace('.', '').replace(',', '.'))
    return float(valor)


def get_dados_basicos():
    conn = get_db_connection()
    try:
        maquinas = pd.read_sql("SELECT id, frota, modelo FROM equipamentos ORDER BY frota", conn)
        planos = pd.read_sql("SELECT id, nome FROM prev_planos_def ORDER BY nome", conn)
    except:
        maquinas, planos = pd.DataFrame(), pd.DataFrame()
    conn.close()
    return maquinas, planos


# --- 4. INTERFACE PRINCIPAL ---
st.title("🛡️ Central de Preventivas")
st.markdown("---")

# Menu Lateral de Configuração (Para limpar a tela principal)
with st.sidebar:
    st.header("⚙️ Parâmetros de Alerta")
    st.info("Defina com quanto tempo de antecedência as ordens aparecem no quadro.")

    with st.expander("⏳ Horas (Tratores/Máquinas)", expanded=True):
        margem_plan_h = st.number_input("Planejamento (h)", value=100, help="Aparece na coluna Azul")
        margem_crit_h = st.number_input("Crítico (h)", value=20, help="Aparece na coluna Laranja")

    with st.expander("🛣️ Quilometragem (Veículos)", expanded=False):
        margem_plan_km = st.number_input("Planejamento (km)", value=1000)
        margem_crit_km = st.number_input("Crítico (km)", value=200)

# Abas Simplificadas
tab_acao, tab_config, tab_baixa = st.tabs([
    "🚀 Painel de Ação (Importar & Visualizar)",
    "⚙️ Configuração (Planos & Frotas)",
    "✅ Baixa Manual"
])

# ==============================================================================
# ABA 1: PAINEL DE AÇÃO (TUDO ACONTECE AQUI)
# ==============================================================================
with tab_acao:
    # 1. Área de Upload Limpa
    c_up, c_stats = st.columns([1, 2])
    uploaded_file = c_up.file_uploader("📂 Importar Planilha de Abastecimentos", type=['csv', 'xlsx'])

    if uploaded_file:
        try:
            # Processamento Silencioso
            if uploaded_file.name.endswith('.csv'):
                try:
                    df_log = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
                except:
                    df_log = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
            else:
                df_log = pd.read_excel(uploaded_file)

            df_log.columns = [str(c).upper().strip() for c in df_log.columns]

            # Tratamento Rápido
            if {'FROTA', 'NO_HOR_ODOM'}.issubset(df_log.columns):
                df_log['HR_OPERACAO'] = pd.to_datetime(df_log['HR_OPERACAO'], dayfirst=True, errors='coerce')
                df_log = df_log.dropna(subset=['HR_OPERACAO', 'NO_HOR_ODOM', 'FROTA']).sort_values('HR_OPERACAO')
                df_log['NO_HOR_ODOM'] = df_log['NO_HOR_ODOM'].apply(limpar_numero)
                df_log['FROTA'] = df_log['FROTA'].astype(str)

                # Pega último registro de cada máquina
                df_status = df_log.groupby('FROTA').last().reset_index()

                # Busca Regras no Banco
                conn = get_db_connection()
                df_regras = pd.read_sql("""
                    SELECT a.frota, p.nome as plano, p.intervalo, p.unidade, p.executante,
                    (SELECT MAX(horimetro_km_realizado) FROM historico_manutencao h 
                     WHERE h.tipo_servico = p.nome AND h.equipamento_id = (SELECT id FROM equipamentos WHERE frota = a.frota)) as ult_exec
                    FROM prev_associacoes a JOIN prev_planos_def p ON a.plano_id = p.id
                """, conn)
                conn.close()

                # Algoritmo de Cruzamento
                alertas = []
                for row in df_status.itertuples():
                    regras = df_regras[df_regras['frota'] == row.FROTA]
                    for reg in regras.itertuples():
                        # Define limites baseados na unidade
                        lim_plan = margem_plan_km if reg.unidade == 'KM' else margem_plan_h
                        lim_crit = margem_crit_km if reg.unidade == 'KM' else margem_crit_h

                        # Calcula Meta
                        atual = row.NO_HOR_ODOM
                        if pd.notna(reg.ult_exec):
                            meta = reg.ult_exec + reg.intervalo
                        else:
                            meta = (int(atual // reg.intervalo) + 1) * reg.intervalo

                        restante = meta - atual

                        # Triagem
                        status = None
                        if restante < 0:
                            status = "VENCIDA"
                        elif restante <= lim_crit:
                            status = "URGENTE"
                        elif restante <= lim_plan:
                            status = "PLANEJAMENTO"

                        if status:
                            alertas.append({
                                "Frota": row.FROTA, "Modelo": getattr(row, 'MODELO', 'N/D'),
                                "Plano": reg.plano, "Status": status, "Restante": restante,
                                "Meta": meta, "Atual": atual, "Executante": reg.executante, "Unidade": reg.unidade
                            })

                # --- RENDERIZAÇÃO DO KANBAN ---
                if alertas:
                    df_k = pd.DataFrame(alertas)

                    # KPIs Rápidos
                    with c_stats:
                        k1, k2, k3 = st.columns(3)
                        k1.metric("🚨 Vencidas", len(df_k[df_k['Status'] == 'VENCIDA']))
                        k2.metric("📅 Planejamento", len(df_k))
                        k3.download_button("📥 Exportar Lista PIMS", df_k.to_csv(sep=';', index=False),
                                           "pims_export.csv", "text/csv")

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Colunas do Kanban
                    col_v, col_u, col_p = st.columns(3)


                    def render_card(container, row, cor_header, classe_card, titulo_col):
                        garantia = "<div class='badge-garantia'>GARANTIA</div>" if "CONCESSIONARIA" in str(
                            row['Executante']) else ""
                        html = f"""
                        <div class='kanban-card {classe_card}'>
                            <div style="display:flex; justify-content:space-between; align-items:start;">
                                <div>
                                    <span style="font-weight:bold; font-size:1.1rem">🚜 {row['Frota']}</span>
                                    <div style="font-size:0.8rem; color:#666; margin-bottom:4px;">{row['Modelo']}</div>
                                </div>
                                {garantia}
                            </div>
                            <div style="font-weight:bold; color:#333; margin-top:5px;">{row['Plano']}</div>
                            <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#555; margin-top:8px; border-top:1px solid #eee; padding-top:5px;">
                                <span>Atual: {int(row['Atual'])}</span>
                                <span>Meta: {int(row['Meta'])}</span>
                            </div>
                            <div style="text-align:right; font-weight:bold; margin-top:8px; color:{cor_header}">
                                {int(row['Restante'])} {row['Unidade']} (Restante)
                            </div>
                        </div>
                        """
                        container.markdown(html, unsafe_allow_html=True)


                    # Preenchimento das Colunas
                    with col_v:
                        st.markdown(
                            f"<div class='col-header' style='background-color:#D32F2F'>🚨 VENCIDAS (Gerar Agora)</div>",
                            unsafe_allow_html=True)
                        for _, r in df_k[df_k['Status'] == 'VENCIDA'].sort_values('Restante').iterrows():
                            render_card(col_v, r, "#D32F2F", "card-vencido", "Vencida")

                    with col_u:
                        st.markdown(
                            f"<div class='col-header' style='background-color:#F57C00'>⚠️ URGENTE (Próxima Semana)</div>",
                            unsafe_allow_html=True)
                        for _, r in df_k[df_k['Status'] == 'URGENTE'].sort_values('Restante').iterrows():
                            render_card(col_u, r, "#EF6C00", "card-urgente", "Urgente")

                    with col_p:
                        st.markdown(
                            f"<div class='col-header' style='background-color:#1976D2'>📅 PLANEJAMENTO (Futuro)</div>",
                            unsafe_allow_html=True)
                        for _, r in df_k[df_k['Status'] == 'PLANEJAMENTO'].sort_values('Restante').iterrows():
                            render_card(col_p, r, "#1565C0", "card-planejamento", "Planejamento")

                else:
                    c_stats.success("✅ Tudo em dia! Nenhuma máquina próxima do vencimento nas margens configuradas.")

            else:
                st.error("Planilha inválida. Verifique colunas FROTA e NO_HOR_ODOM.")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
    else:
        # Estado Inicial (Sem arquivo)
        with c_stats:
            st.info("👆 Importe a planilha de abastecimentos para ver o quadro atualizado.")

        # Mostra um resumo do cadastro atual para não ficar vazio
        conn = get_db_connection()
        qtd_planos = conn.execute("SELECT count(*) FROM prev_planos_def").fetchone()[0]
        qtd_assoc = conn.execute("SELECT count(*) FROM prev_associacoes").fetchone()[0]
        conn.close()

        st.divider()
        k1, k2 = st.columns(2)
        k1.metric("Planos Cadastrados", qtd_planos)
        k2.metric("Frotas Monitoradas (Associações)", qtd_assoc)

# ==============================================================================
# ABA 2: CONFIGURAÇÃO (CADASTROS UNIFICADOS)
# ==============================================================================
with tab_config:
    st.markdown("#### 🛠️ Gerenciar Regras de Manutenção")

    col_criar, col_vincular = st.columns([1, 1], gap="large")

    # --- ESQUERDA: CRIAR O PLANO ---
    with col_criar:
        st.subheader("1. Criar Plano")
        with st.form("form_plano", clear_on_submit=True):
            nome = st.text_input("Nome (Ex: Revisão 250h)")
            c1, c2 = st.columns(2)
            interv = c1.number_input("Intervalo", 250)
            unid = c2.selectbox("Unidade", ["HORAS", "KM"])
            execut = st.selectbox("Executante", ["INTERNA", "CONCESSIONARIA"])

            if st.form_submit_button("💾 Salvar Plano"):
                conn = get_db_connection()
                conn.execute(
                    "INSERT INTO prev_planos_def (nome, intervalo, unidade, tipo, executante) VALUES (?,?,?,?,?)",
                    (nome, interv, unid, "Geral", execut))
                conn.commit()
                conn.close()
                st.toast("Plano criado!")
                st.rerun()

        # Lista de Planos Existentes
        st.markdown("---")
        st.caption("Planos Ativos (Clique para excluir):")
        conn = get_db_connection()
        df_p = pd.read_sql("SELECT id, nome, intervalo, unidade FROM prev_planos_def", conn)
        conn.close()

        for _, row in df_p.iterrows():
            c_txt, c_del = st.columns([4, 1])
            c_txt.text(f"{row['nome']} ({row['intervalo']} {row['unidade']})")
            if c_del.button("🗑️", key=f"del_{row['id']}"):
                conn = get_db_connection()
                conn.execute("DELETE FROM prev_planos_def WHERE id=?", (row['id'],))
                conn.execute("DELETE FROM prev_associacoes WHERE plano_id=?", (row['id'],))
                conn.commit()
                conn.close()
                st.rerun()

    # --- DIREITA: VINCULAR ÀS MÁQUINAS ---
    with col_vincular:
        st.subheader("2. Aplicar às Frotas")
        maquinas, planos = get_dados_basicos()

        if not planos.empty and not maquinas.empty:
            plano_sel = st.selectbox("Selecione o Plano:", planos['id'],
                                     format_func=lambda x: planos[planos['id'] == x]['nome'].values[0])

            # Filtros inteligentes
            filtro_modelo = st.multiselect("Filtrar por Modelo:", maquinas['modelo'].unique())
            df_m_filt = maquinas[maquinas['modelo'].isin(filtro_modelo)] if filtro_modelo else maquinas

            frotas_sel = st.multiselect("Selecione as Frotas:", df_m_filt['frota'].unique())

            if st.button("🔗 Vincular Selecionadas", type="primary"):
                if frotas_sel:
                    conn = get_db_connection()
                    count = 0
                    for f in frotas_sel:
                        try:
                            mod = maquinas[maquinas['frota'] == f]['modelo'].values[0]
                            conn.execute("INSERT INTO prev_associacoes (plano_id, frota, modelo_ref) VALUES (?,?,?)",
                                         (plano_sel, f, mod))
                            count += 1
                        except:
                            pass
                    conn.commit()
                    conn.close()
                    st.success(f"{count} máquinas vinculadas!")

            # Ver quem já está vinculado
            with st.expander("Ver máquinas já vinculadas a este plano"):
                conn = get_db_connection()
                vinc = pd.read_sql("SELECT frota, modelo_ref FROM prev_associacoes WHERE plano_id=?", conn,
                                   params=(plano_sel,))
                conn.close()
                st.dataframe(vinc, use_container_width=True)

# ==============================================================================
# ABA 3: BAIXA MANUAL
# ==============================================================================
with tab_baixa:
    st.subheader("Registrar Execução (Dar Baixa)")
    c_form, c_hist = st.columns([1, 1])

    maquinas, _ = get_dados_basicos()

    with c_form:
        with st.container(border=True):
            frota = st.selectbox("Frota", maquinas['frota'].unique()) if not maquinas.empty else None

            if frota:
                conn = get_db_connection()
                planos_disp = pd.read_sql(
                    "SELECT p.nome FROM prev_associacoes a JOIN prev_planos_def p ON a.plano_id = p.id WHERE a.frota=?",
                    conn, params=(frota,))
                conn.close()

                opcoes = planos_disp['nome'].tolist() + ["Corretiva / Outro"]
                plano = st.selectbox("Serviço Realizado", opcoes)

                c1, c2 = st.columns(2)
                dt = c1.date_input("Data", datetime.today())
                val = c2.number_input("Horímetro na Baixa", 0.0)
                obs = st.text_area("Observações")

                if st.button("Confirmar Baixa", type="primary", use_container_width=True):
                    conn = get_db_connection()
                    id_eq = conn.execute("SELECT id FROM equipamentos WHERE frota=?", (frota,)).fetchone()
                    if id_eq:
                        conn.execute(
                            "INSERT INTO historico_manutencao (equipamento_id, data_realizacao, horimetro_km_realizado, tipo_servico, observacao) VALUES (?,?,?,?,?)",
                            (id_eq[0], dt, val, plano, obs))
                        conn.commit()
                        st.toast("Baixa realizada com sucesso!", icon="✅")
                    conn.close()